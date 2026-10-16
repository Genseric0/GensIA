import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from gensia.memory import MemoryError, MemoryStore
from gensia.memory_backup import backup_notes
from gensia.memory_restore import restore_notes


class MemoryRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = MemoryStore(self.root / 'source.sqlite3')
        self.source.set('tema', 'Propagação — DNS')
        self.backup = self.root / 'notes.memory-backup.json'
        self.summary = backup_notes(self.source, self.backup)
        self.original = self.backup.read_bytes()
        self.document = json.loads(self.original)
        self.target = MemoryStore(self.root / 'restored.sqlite3')

    def save(self, document):
        self.backup.write_text(json.dumps(document, ensure_ascii=True), encoding='utf-8')

    def test_roundtrip_preserves_values_dates_and_source(self):
        result = restore_notes(self.target, self.backup, True)
        self.assertEqual(self.target.get('tema'), self.source.get('tema'))
        self.assertEqual(result['backup_sha256'], self.summary['sha256'])
        self.assertEqual(self.backup.read_bytes(), self.original)
        self.assertNotIn('DNS', json.dumps(result))

    def test_approval_required_before_read(self):
        with patch('gensia.memory_restore._load_backup') as load:
            with self.assertRaises(MemoryError):
                restore_notes(self.target, self.backup)
            load.assert_not_called()
        self.assertFalse(self.target.path.exists())

    def test_existing_destinations_preserved(self):
        for raw in (b'', b'keep'):
            self.target.path.write_bytes(raw)
            with self.assertRaises(MemoryError):
                restore_notes(self.target, self.backup, True)
            self.assertEqual(self.target.path.read_bytes(), raw)

    def test_symlink_destination_and_source_refused(self):
        outside = self.root / 'outside'
        try:
            self.target.path.symlink_to(outside)
        except OSError:
            self.skipTest('Symlinks unavailable')
        with self.assertRaises(MemoryError):
            restore_notes(self.target, self.backup, True)
        self.assertFalse(outside.exists())
        link = self.root / 'backup-link'
        link.symlink_to(self.backup)
        with self.assertRaises(MemoryError):
            restore_notes(MemoryStore(self.root / 'other.sqlite3'), link, True)
        self.assertFalse((self.root / 'other.sqlite3').exists())

    def test_empty_backup_creates_usable_empty_database(self):
        self.document['notes'] = []
        self.save(self.document)
        self.assertEqual(restore_notes(self.target, self.backup, True)['notes_count'], 0)
        self.assertEqual(self.target.list(), [])
        self.target.set('new', 'note')
        self.assertEqual(self.target.get('new')['value'], 'note')

    def test_invalid_contracts_refused_before_destination_creation(self):
        variants = []
        for key, value in (('schema_version', True), ('schema_version', 2),
                           ('kind', 'other'), ('exported_at', '2026-10-16'),
                           ('notes', {}), ('extra', 'PRIVATE')):
            item = copy.deepcopy(self.document)
            item[key] = value
            variants.append(item)
        for key, value in (('key', ''), ('value', 'x' * 4001),
                           ('updated_at', 'bad'), ('value', '\ud800'), ('extra', 'x')):
            item = copy.deepcopy(self.document)
            item['notes'][0][key] = value
            variants.append(item)
        for document in variants:
            self.save(document)
            with self.assertRaises(MemoryError):
                restore_notes(self.target, self.backup, True)
            self.assertFalse(self.target.path.exists())

    def test_duplicate_json_fields_and_note_keys_refused(self):
        self.backup.write_bytes(b'{"schema_version":1,"schema_version":2}')
        with self.assertRaises(MemoryError):
            restore_notes(self.target, self.backup, True)
        self.document['notes'] *= 2
        self.save(self.document)
        with self.assertRaises(MemoryError):
            restore_notes(self.target, self.backup, True)
        self.assertFalse(self.target.path.exists())

    def test_bad_json_encoding_and_numbers_are_controlled(self):
        for raw in (b'\xff', b'{', b'{"schema_version":NaN}',
                    b'{"schema_version":1.0}', b'[' * 2000 + b']' * 2000):
            self.backup.write_bytes(raw)
            with self.assertRaises(MemoryError):
                restore_notes(self.target, self.backup, True)
            self.assertFalse(self.target.path.exists())

    def test_byte_and_note_limits(self):
        with patch('gensia.memory_restore.MAX_BACKUP_BYTES', 1):
            with self.assertRaises(MemoryError):
                restore_notes(self.target, self.backup, True)
        with patch('gensia.memory_restore.MAX_NOTES', 0):
            with self.assertRaises(MemoryError):
                restore_notes(self.target, self.backup, True)
        self.assertFalse(self.target.path.exists())

    def test_sql_payloads_remain_data(self):
        note = self.document['notes'][0]
        note['key'] = "'); DROP TABLE memories; --"
        note['value'] = 'SELECT * FROM secrets'
        self.save(self.document)
        restore_notes(self.target, self.backup, True)
        self.assertEqual(self.target.get(note['key'])['value'], note['value'])

    def test_missing_parent_and_write_failure_preserve_backup(self):
        missing = MemoryStore(self.root / 'missing' / 'target.sqlite3')
        with self.assertRaises(MemoryError):
            restore_notes(missing, self.backup, True)
        self.assertFalse(missing.path.parent.exists())
        with patch('gensia.memory_restore.os.fsync', side_effect=OSError('PRIVATE')):
            with self.assertRaises(MemoryError) as error:
                restore_notes(self.target, self.backup, True)
        self.assertNotIn('PRIVATE', str(error.exception))
        self.assertIn('incompleta', str(error.exception))
        self.assertEqual(self.backup.read_bytes(), self.original)

    def test_real_cli_restore_and_second_attempt(self):
        command = [sys.executable, '-m', 'gensia', 'memory', '--db', str(self.target.path),
                   'restore', '--input', str(self.backup), '--approve']
        def run():
            return subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                                  capture_output=True, text=True, timeout=10)
        result = run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['restored'])
        self.assertEqual(self.target.get('tema'), self.source.get('tema'))
        before = self.target.path.read_bytes()
        self.assertEqual(run().returncode, 6)
        self.assertEqual(self.target.path.read_bytes(), before)
