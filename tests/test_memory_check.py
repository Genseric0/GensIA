"""Real SQLite recovery preflight with synthetic data and controlled failures."""
from contextlib import closing, contextmanager, redirect_stdout, redirect_stderr
from io import StringIO
from itertools import chain, repeat
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from gensia.cli import main
from gensia.memory import MemoryError, MemoryStore
from gensia.memory_backup import backup_notes
from gensia.memory_restore import restore_notes
from gensia.memory_check import check_memory


class MemoryCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = MemoryStore(self.root / 'notes.sqlite3')

    def test_valid_memory_and_empty_table_are_read_only_and_private(self):
        self.store.set('PRIVATE_KEY', 'PRIVATE_VALUE 😀')
        before = self.store.path.read_bytes()
        report = check_memory(self.store)
        self.assertTrue(report['ok'])
        self.assertEqual(report['notes_checked'], 1)
        self.assertFalse(report['mutations_requested'])
        self.assertFalse(report['recovery_tested'])
        self.assertNotIn('PRIVATE', json.dumps(report))
        self.assertEqual(before, self.store.path.read_bytes())
        self.store.delete('PRIVATE_KEY', True)
        self.assertEqual(check_memory(self.store)['notes_checked'], 0)

    def test_missing_database_and_non_sqlite_are_not_created_or_repaired(self):
        with self.assertRaises(MemoryError):
            check_memory(self.store)
        self.assertFalse(self.store.path.exists())
        self.store.path.write_bytes(b'PRIVATE corrupt database')
        before = self.store.path.read_bytes()
        with self.assertRaises(MemoryError) as error:
            check_memory(self.store)
        self.assertNotIn('PRIVATE', str(error.exception))
        self.assertEqual(before, self.store.path.read_bytes())

    def test_corrupted_btree_is_detected_without_modification(self):
        self.store.set('PRIVATE_KEY', 'PRIVATE_VALUE')
        with closing(sqlite3.connect(self.store.path)) as db:
            page_size = db.execute('PRAGMA page_size').fetchone()[0]
            root = db.execute("SELECT rootpage FROM sqlite_schema WHERE name='memories'").fetchone()[0]
        raw = bytearray(self.store.path.read_bytes())
        raw[(root - 1) * page_size] = 0  # Invalid table btree page type.
        self.store.path.write_bytes(raw)
        with self.assertRaises(MemoryError) as error:
            check_memory(self.store)
        self.assertNotIn('PRIVATE', str(error.exception))
        self.assertEqual(bytes(raw), self.store.path.read_bytes())

    def test_duplicate_invalid_and_oversized_logical_notes_fail_closed(self):
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute('CREATE TABLE memories(key, value, updated_at)')
        fixtures = [
            [('key', 'value', '2026-10-21T00:00:00+02:00')] * 2,
            [('PRIVATE', 'value', 'not-a-date')],
            [('PRIVATE', 'x' * 4001, '2026-10-21T00:00:00+02:00')],
            [('PRIVATE', 'bad\x00value', '2026-10-21T00:00:00+02:00')],
        ]
        for notes in fixtures:
            with closing(sqlite3.connect(self.store.path)) as db, db:
                db.execute('DELETE FROM memories')
                db.executemany('INSERT INTO memories VALUES(?,?,?)', notes)
            with self.assertRaises(MemoryError) as error:
                check_memory(self.store)
            self.assertNotIn('PRIVATE', str(error.exception))

    def test_secondary_index_corruption_is_detected_by_full_integrity_check(self):
        self.store.set('key', 'PRIVATE_VALUE')
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute('CREATE INDEX extra_value_index ON memories(value)')
            size = db.execute('PRAGMA page_size').fetchone()[0]
            root = db.execute("SELECT rootpage FROM sqlite_schema WHERE name='extra_value_index'").fetchone()[0]
        raw = bytearray(self.store.path.read_bytes())
        raw[(root - 1) * size] = 0
        self.store.path.write_bytes(raw)
        # Normal notes still read; the otherwise unused secondary index is bad.
        self.assertEqual(self.store.get('key')['value'], 'PRIVATE_VALUE')
        with self.assertRaises(MemoryError):
            check_memory(self.store)
        self.assertEqual(bytes(raw), self.store.path.read_bytes())

    def test_wal_commits_are_visible_and_uncommitted_changes_are_excluded(self):
        self.store.set('a', 'one')
        with closing(sqlite3.connect(self.store.path)) as writer:
            writer.execute('PRAGMA journal_mode=WAL')
            writer.execute('INSERT INTO memories VALUES(?,?,?)',
                           ('b', 'two', '2026-10-21T00:00:00+02:00'))
            writer.commit()
            writer.execute('INSERT INTO memories VALUES(?,?,?)',
                           ('c', 'uncommitted', '2026-10-21T00:00:00+02:00'))
            self.assertEqual(check_memory(self.store)['notes_checked'], 2)
            writer.rollback()

    def test_view_is_rejected_before_reading_its_expression(self):
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute('CREATE VIEW memories AS SELECT randomblob(1000000000) AS value')
        with self.assertRaisesRegex(MemoryError, 'incompatível'):
            check_memory(self.store)

    def test_check_connection_refuses_oversized_sqlite_blob_allocation(self):
        self.store.set('key', 'value')
        original = self.store.connect
        checked = []

        @contextmanager
        def inspected_connection():
            with original() as db:
                yield db
                with self.assertRaises(sqlite3.DataError):
                    db.execute('SELECT randomblob(8388608)').fetchone()
                checked.append(True)

        with patch.object(self.store, 'connect', inspected_connection):
            self.assertTrue(check_memory(self.store)['ok'])
        self.assertEqual(checked, [True])

    def test_row_and_processing_limits_never_report_success(self):
        self.store.set('a', 'one')
        self.store.set('b', 'two')
        with patch('gensia.memory_check.MAX_NOTES', 1):
            with self.assertRaisesRegex(MemoryError, 'incompleta'):
                check_memory(self.store)
        with patch('gensia.memory_check.time.monotonic', side_effect=chain([0], repeat(3))):
            with self.assertRaises(MemoryError):
                check_memory(self.store)
        # Force a real SQLite VM interruption and verify a later check recovers.
        with patch('gensia.memory_check.PROGRESS_INTERVAL', 1), patch('gensia.memory_check.MAX_VM_STEPS', 1):
            with self.assertRaises(MemoryError):
                check_memory(self.store)
        self.assertTrue(check_memory(self.store)['ok'])

    def test_verified_backup_restores_to_new_database_without_changing_source(self):
        self.store.set('idioma', 'Português 😀')
        before = self.store.path.read_bytes()
        backup = self.root / 'notes.json'
        backup_notes(self.store, backup)
        recovered = MemoryStore(self.root / 'restored.sqlite3')
        restore_notes(recovered, backup, True)
        self.assertEqual(check_memory(recovered)['notes_checked'], 1)
        self.assertEqual(recovered.get('idioma')['value'], 'Português 😀')
        self.assertEqual(before, self.store.path.read_bytes())

    def test_cli_success_and_failure_codes_do_not_disclose_note_contents(self):
        self.store.set('PRIVATE', 'PRIVATE_VALUE')
        output, errors = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = main(['memory', '--db', str(self.store.path), 'check'])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output.getvalue())['ok'])
        self.assertNotIn('PRIVATE', output.getvalue() + errors.getvalue())
        self.store.path.write_bytes(b'PRIVATE_CORRUPTION')
        with redirect_stdout(output), redirect_stderr(errors):
            code = main(['memory', '--db', str(self.store.path), 'check'])
        self.assertEqual(code, 6)
        self.assertNotIn('PRIVATE', errors.getvalue())
