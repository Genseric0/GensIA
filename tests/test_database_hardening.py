"""Synthetic regressions for the 2026-10-22 release database review."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from gensia.cli import main
from gensia.memory import MemoryError, MemoryStore
from gensia.memory_backup import BACKUP_SQL, backup_notes
from gensia.memory_restore import restore_notes


STAMP = '2026-10-20T00:00:00+02:00'


class DatabaseHardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = MemoryStore(self.root / 'notes.sqlite3')

    def flexible_fixture(self, name, key='synthetic', value='synthetic', stamp=STAMP):
        store = MemoryStore(self.root / (name + '.sqlite3'))
        with sqlite3.connect(store.path) as db:
            db.execute('CREATE TABLE memories (key, value, updated_at)')
            db.execute('INSERT INTO memories VALUES (?,?,?)', (key, value, stamp))
        return store

    def assert_backup_refused(self, store):
        before = store.path.read_bytes()
        output = store.path.with_suffix('.json')
        with self.assertRaises(MemoryError) as error:
            backup_notes(store, output)
        self.assertNotIn('PRIVATE', str(error.exception))
        self.assertFalse(output.exists())
        self.assertEqual(store.path.read_bytes(), before)

    def test_delete_requires_exact_true_and_keeps_data_for_false_strings(self):
        self.store.set('synthetic', 'keep')
        for approved in (False, None, 0, 1, 'false', 'true', [], {}, object()):
            with self.subTest(type=type(approved).__name__):
                with self.assertRaises(MemoryError):
                    self.store.delete('synthetic', approved=approved)
                self.assertEqual(self.store.get('synthetic')['value'], 'keep')
        self.assertTrue(self.store.delete('synthetic', approved=True)['deleted'])

    @unittest.skipUnless(os.name == 'posix', 'POSIX mode bits are not Windows ACLs')
    def test_new_database_private_even_with_permissive_umask(self):
        previous = os.umask(0)
        try:
            self.store.set('synthetic', 'value')
        finally:
            os.umask(previous)
        self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)

    def test_hardlink_read_and_write_refused_without_mutating_original(self):
        self.store.set('synthetic', 'keep')
        alias = self.root / 'alias.sqlite3'
        try:
            os.link(self.store.path, alias)
        except OSError:
            self.skipTest('Hard links unavailable')
        before = self.store.path.read_bytes()
        linked = MemoryStore(alias)
        for operation in (lambda: linked.get('synthetic'), lambda: linked.list(),
                          lambda: linked.set('synthetic', 'changed'),
                          lambda: linked.delete('synthetic', True)):
            with self.assertRaises(MemoryError):
                operation()
        self.assertEqual(self.store.path.read_bytes(), before)

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'Requires POSIX FIFO')
    def test_fifo_rejected_before_opening_sqlite(self):
        os.mkfifo(self.store.path)
        with patch('gensia.memory.sqlite3.connect') as connect:
            with self.assertRaises(MemoryError):
                self.store.list()
        connect.assert_not_called()

    def test_existing_and_dangling_symlink_refused(self):
        self.store.set('synthetic', 'keep')
        for target in (self.store.path, self.root / 'not-created'):
            link = self.root / ('link-' + target.name)
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest('Symlinks unavailable')
            linked = MemoryStore(link)
            with self.assertRaises(MemoryError):
                linked.set('synthetic', 'changed')
        self.assertEqual(self.store.get('synthetic')['value'], 'keep')
        self.assertFalse((self.root / 'not-created').exists())

    def test_unicode_surrogates_refused_before_parent_or_database_creation(self):
        missing = MemoryStore(self.root / 'absent' / 'notes.sqlite3')
        for text in ('\ud800', '\udfff', 'PRIVATE\ud800', '\ud83d\ude00'):
            for key, value in ((text, 'safe'), ('safe', text)):
                with self.assertRaises(MemoryError) as error:
                    missing.set(key, value)
                self.assertNotIn('PRIVATE', str(error.exception))
                self.assertFalse(missing.path.parent.exists())

    def test_invalid_pagination_rejected_before_existence_lookup(self):
        class IntegerSubclass(int):
            pass
        for value in (True, False, 1.0, 1.5, '1', None, [], {}, IntegerSubclass(1)):
            for limit, offset in ((value, 0), (1, value)):
                for operation in (lambda: self.store.list(limit, offset),
                                  lambda: self.store.search('synthetic', limit, offset)):
                    with patch.object(Path, 'exists', side_effect=AssertionError('disk accessed')):
                        with self.assertRaises(MemoryError):
                            operation()

    def test_out_of_range_pagination_rejected_for_existing_database(self):
        self.store.set('synthetic', 'keep')
        before = self.store.path.read_bytes()
        for limit, offset in ((0, 0), (201, 0), (1, -1), (1, 2**63), (1, 10**100)):
            for operation in (lambda: self.store.list(limit, offset),
                              lambda: self.store.search('synthetic', limit, offset)):
                with self.assertRaises(MemoryError):
                    operation()
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_sqlite_int64_offset_boundary_accepted(self):
        self.store.set('synthetic', 'keep')
        self.assertEqual(self.store.list(200, 2**63-1), [])
        self.assertEqual(self.store.search('synthetic', 200, 2**63-1), [])

    def test_get_and_backup_never_disclose_extra_schema_column(self):
        self.store.set('synthetic', 'keep')
        with sqlite3.connect(self.store.path) as db:
            db.execute('ALTER TABLE memories ADD COLUMN extra_private')
            db.execute("UPDATE memories SET extra_private='PRIVATE'")
        self.assertEqual(set(self.store.get('synthetic')), {'key', 'value', 'updated_at'})
        output = self.root / 'backup.json'
        backup_notes(self.store, output)
        note = json.loads(output.read_text())['notes'][0]
        self.assertEqual(set(note), {'key', 'value', 'updated_at'})

    def test_large_fields_capped_before_materialization_and_export_refused(self):
        for name, cap in (('key', 401), ('value', 16001), ('updated_at', 257)):
            values = {'key': 'synthetic', 'value': 'synthetic', 'stamp': STAMP}
            values['stamp' if name == 'updated_at' else name] = 'x' * 1000000
            store = self.flexible_fixture(name, **values)
            with store.connect() as db:
                row = db.execute(BACKUP_SQL, (1001,)).fetchone()
            self.assertEqual(len(row[name]), cap)
            self.assert_backup_refused(store)
            if name == 'value':
                with self.assertRaises(MemoryError):
                    store.get('synthetic')
            with self.assertRaises(MemoryError):
                store.search('synthetic')

    def test_unexpected_sqlite_storage_types_refused_without_coercion(self):
        for field in ('key', 'value', 'stamp'):
            for index, value in enumerate((None, 42, 1.5, b'synthetic')):
                store = self.flexible_fixture(field+str(index), **{field: value})
                self.assert_backup_refused(store)

    def test_nul_in_each_field_refused_instead_of_exporting_prefix(self):
        for field in ('key', 'value', 'stamp'):
            store = self.flexible_fixture(field, **{field: 'safe\x00PRIVATE'})
            self.assert_backup_refused(store)

    def test_invalid_utf8_is_controlled_and_never_exported(self):
        store = self.flexible_fixture('invalid-utf8')
        with sqlite3.connect(store.path) as db:
            db.execute("UPDATE memories SET value=CAST(x'ff' AS TEXT)")
        self.assert_backup_refused(store)
        with self.assertRaises(MemoryError):
            store.get('synthetic')

    def test_invalid_or_naive_timestamp_refused(self):
        for index, stamp in enumerate(('PRIVATE', '2026-10-20', STAMP+'\x00PRIVATE')):
            store = self.flexible_fixture('date'+str(index), stamp=stamp)
            self.assert_backup_refused(store)
            with self.assertRaises(MemoryError):
                store.list()

    def test_duplicate_key_get_and_backup_refused(self):
        store = self.flexible_fixture('duplicates')
        with sqlite3.connect(store.path) as db:
            db.execute('INSERT INTO memories VALUES (?,?,?)', ('synthetic', 'other', STAMP))
        self.assert_backup_refused(store)
        with self.assertRaises(MemoryError):
            store.get('synthetic')

    def test_invalid_last_row_cannot_create_partial_backup(self):
        self.store.set('a', 'safe')
        self.store.set('z', 'safe')
        with sqlite3.connect(self.store.path) as db:
            db.execute("UPDATE memories SET updated_at='PRIVATE' WHERE key='z'")
        self.assert_backup_refused(self.store)
        with self.assertRaises(MemoryError):
            self.store.list()

    def test_list_does_not_read_or_reveal_value(self):
        store = self.flexible_fixture('metadata')
        with sqlite3.connect(store.path) as db:
            db.execute("UPDATE memories SET value=CAST(x'ff' AS TEXT)")
        self.assertEqual(store.list(), [{'key': 'synthetic', 'updated_at': STAMP}])

    def test_unicode_limits_backup_restore_new_database_and_query(self):
        key, value = '👋' * 100, '👋' * 4000
        self.store.set(key, value)
        self.store.set('Redes', 'Português\nΔ e 中文\tDNS')
        notes = [self.store.get(k) for k in ('Redes', key)]
        source_before = self.store.path.read_bytes()
        output = self.root / 'backup.json'
        summary = backup_notes(self.store, output)
        target = MemoryStore(self.root / 'restored.sqlite3')
        result = restore_notes(target, output, approved=True)
        self.assertEqual(result['backup_sha256'], summary['sha256'])
        self.assertEqual(result['notes_count'], 2)
        self.assertEqual([target.get(k) for k in ('Redes', key)], notes)
        self.assertEqual(target.search('中文')[0]['value'], notes[0]['value'])
        self.assertEqual(self.store.path.read_bytes(), source_before)
        with sqlite3.connect(target.path) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone(), ('ok',))
        if os.name == 'posix':
            self.assertEqual(target.path.stat().st_mode & 0o777, 0o600)

    def test_concurrent_distinct_writes_persist_without_lost_records(self):
        self.store.set('initial', 'keep')
        def writer(worker):
            store = MemoryStore(self.store.path)
            for index in range(15):
                store.set(f'worker-{worker}-{index}', 'synthetic')
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(writer, range(4)))
        self.assertEqual(len(self.store.list(limit=200)), 61)
        with sqlite3.connect(self.store.path) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone(), ('ok',))

    def test_sql_error_rolls_back_entire_transaction(self):
        self.store.set('synthetic', 'keep')
        with self.assertRaises(MemoryError):
            with self.store.connect(write=True) as db:
                db.execute('UPDATE memories SET value=? WHERE key=?', ('changed', 'synthetic'))
                db.execute('INSERT INTO memories VALUES (?,?,?)', ('synthetic', 'duplicate', STAMP))
        self.assertEqual(self.store.get('synthetic')['value'], 'keep')

    def test_backup_refusal_cli_hides_payload_and_creates_no_file(self):
        store = self.flexible_fixture('cli', value='safe\x00PRIVATE')
        output = self.root / 'invalid.json'
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(['memory', '--db', str(store.path), 'backup', '--output', str(output)])
        self.assertEqual(code, 6)
        self.assertEqual(stdout.getvalue(), '')
        self.assertNotIn('PRIVATE', stderr.getvalue())
        self.assertNotIn('Traceback', stderr.getvalue())
        self.assertFalse(output.exists())
