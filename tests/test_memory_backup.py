import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from gensia.memory import MemoryStore, MemoryError
from gensia.memory_backup import backup_notes


class MemoryBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = MemoryStore(self.root / 'memory.sqlite3')
        self.output = self.root / 'notes.memory-backup.json'

    def test_values_timestamps_hash_and_source_preserved(self):
        self.store.set('tema', 'Propagação — DNS')
        note = self.store.get('tema')
        original = self.store.path.read_bytes()
        result = backup_notes(self.store, self.output)
        raw = self.output.read_bytes()
        document = json.loads(raw.decode('utf-8'))
        self.assertEqual(document['kind'], 'gensia.memory_backup')
        self.assertEqual(document['schema_version'], 1)
        self.assertEqual(document['notes'], [note])
        self.assertEqual(result['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result['bytes'], len(raw))
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertNotIn('Propagação', json.dumps(result))
        if os.name == 'posix':
            self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)

    def test_missing_source_does_not_create_source_or_output(self):
        with self.assertRaises(MemoryError):
            backup_notes(self.store, self.output)
        self.assertFalse(self.store.path.exists())
        self.assertFalse(self.output.exists())

    def test_existing_file_preserved(self):
        self.store.set('a', 'value')
        for content in (b'', b'keep'):
            self.output.write_bytes(content)
            with self.assertRaises(MemoryError):
                backup_notes(self.store, self.output)
            self.assertEqual(self.output.read_bytes(), content)

    def test_symlink_destinations_refused(self):
        self.store.set('a', 'value')
        for exists in (False, True):
            target = self.root / ('existing' if exists else 'missing')
            if exists:
                target.write_bytes(b'keep')
            link = self.root / ('link-existing' if exists else 'link-missing')
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest('Symlinks unavailable')
            with self.assertRaises(MemoryError):
                backup_notes(self.store, link)
            self.assertEqual(target.read_bytes() if exists else target.exists(), b'keep' if exists else False)

    def test_limits_never_create_truncated_backup(self):
        self.store.set('a', 'value')
        self.store.set('b', 'value')
        for setting in ('MAX_NOTES', 'MAX_BACKUP_BYTES'):
            with patch('gensia.memory_backup.' + setting, 1):
                with self.assertRaises(MemoryError):
                    backup_notes(self.store, self.output)
            self.assertFalse(self.output.exists())

    def test_invalid_source_rows_refused(self):
        self.store.set('a', 'value')
        for field, value in (('updated_at', 'invalid'), ('updated_at', '2026-10-16'),
                             ('value', 'x' * 4001)):
            self.store.set('a', 'value')
            with sqlite3.connect(self.store.path) as db:
                # Field is a fixed fixture identifier; values remain parameters.
                if field == 'updated_at':
                    db.execute('UPDATE memories SET updated_at=?', (value,))
                else:
                    db.execute('UPDATE memories SET value=?', (value,))
            with self.assertRaises(MemoryError):
                backup_notes(self.store, self.output)
            self.assertFalse(self.output.exists())

    def test_wal_committed_values_included_without_checkpoint_copy(self):
        self.store.set('a', 'old')
        with sqlite3.connect(self.store.path) as writer:
            writer.execute('PRAGMA journal_mode=WAL')
            writer.execute('UPDATE memories SET value=?', ('new',))
            writer.commit()
            backup_notes(self.store, self.output)
        self.assertEqual(json.loads(self.output.read_text())['notes'][0]['value'], 'new')

    def test_write_failure_is_controlled_and_may_leave_partial_file(self):
        self.store.set('a', 'value')
        with patch('gensia.memory_backup.os.fsync', side_effect=OSError('PRIVATE')):
            with self.assertRaises(MemoryError) as error:
                backup_notes(self.store, self.output)
        self.assertNotIn('PRIVATE', str(error.exception))
        self.assertIn('incompleto', str(error.exception))
        self.assertTrue(self.output.exists())

    def test_real_cli_summary_hides_notes_and_refuses_second_backup(self):
        self.store.set('private-key', 'PRIVATE-VALUE')
        command = [sys.executable, '-m', 'gensia', 'memory', '--db', str(self.store.path),
                   'backup', '--output', str(self.output)]
        def run():
            return subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                                  capture_output=True, text=True, timeout=10)
        result = run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['backup_created'])
        self.assertNotIn('PRIVATE', result.stdout)
        content = self.output.read_bytes()
        self.assertEqual(run().returncode, 6)
        self.assertEqual(self.output.read_bytes(), content)
