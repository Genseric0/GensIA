from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, redirect_stderr, redirect_stdout
import errno
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from gensia.cli import main
from gensia.memory import MemoryError, MemoryStore
from gensia.memory_backup import backup_notes
from gensia.memory_restore import restore_notes
from gensia.memory_recovery import recover_copy, JOURNAL_MAGIC, _read_source


class MemoryRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = MemoryStore(self.root / 'original.sqlite3')
        self.source.set('private-key', 'conteúdo privado 👋')
        self.target = self.root / 'recovered.sqlite3'
        self.journal = Path(str(self.source.path) + '-journal')

    def recover(self):
        return recover_copy(self.source, self.target, approved=True, source_stopped=True)

    def digest(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def make_hot_journal(self):
        with self.source.connect(write=True) as db:
            db.executemany('INSERT INTO memories VALUES (?, ?, ?)',
                           [(f'n{i}', 'a' * 4000, '2026-10-21T00:00:00+00:00') for i in range(100)])
        script = '''
import sys
from gensia.memory import MemoryStore
with MemoryStore(sys.argv[1]).connect(write=True) as db:
    db.execute('PRAGMA cache_size=1')
    db.execute("UPDATE memories SET value=replace(value, 'a', 'b')")
    print('READY', flush=True)
    sys.stdin.read()
'''
        child = subprocess.Popen([sys.executable, '-u', '-c', script, str(self.source.path)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                readiness = pool.submit(child.stdout.readline)
                try:
                    line = readiness.result(timeout=10)
                finally:
                    child.kill()
                    child.wait(timeout=10)
            _, errors = child.communicate(timeout=10)
            self.assertEqual(line.strip(), 'READY', errors)
        finally:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=10)
        self.assertTrue(self.journal.exists())
        with self.assertRaises(MemoryError):
            self.source.get('n0')

    def test_exact_approvals_before_any_io(self):
        with patch('gensia.memory_recovery._inventory') as inventory:
            for approve, stopped in ((False, True), (True, False), (1, True), (True, 1)):
                with self.subTest(approve=approve, stopped=stopped), self.assertRaises(MemoryError):
                    recover_copy(self.source, self.target, approve, stopped)
            inventory.assert_not_called()
        self.assertFalse(self.target.exists())

    @staticmethod
    def changed_ctime(info):
        values = {name: getattr(info, name) for name in
                  ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns',
                   'st_nlink', 'st_mode')}
        values['st_ctime_ns'] += 1000000000
        return SimpleNamespace(**values)

    def test_path_and_descriptor_ctime_differences_do_not_reject_unchanged_bytes(self):
        lstat = Path.lstat
        def different_api_ctime(path, *args, **kwargs):
            info = lstat(path, *args, **kwargs)
            return self.changed_ctime(info) if path == self.source.path else info
        with patch('gensia.memory_recovery.Path.lstat', different_api_ctime):
            snapshot = _read_source(self.source.path)
        self.assertEqual(snapshot['sha256'], self.digest(self.source.path))

    def test_descriptor_ctime_change_during_read_is_still_rejected(self):
        info = self.source.path.stat()
        with patch('gensia.memory_recovery.os.fstat', side_effect=[info, self.changed_ctime(info)]):
            with self.assertRaises(MemoryError):
                _read_source(self.source.path)

    def test_clean_source_preserved_and_output_does_not_return_contents(self):
        before = self.digest(self.source.path)
        connect = sqlite3.connect
        with patch('gensia.memory_recovery.sqlite3.connect', wraps=connect) as calls:
            result = self.recover()
        self.assertTrue(result['recovered'])
        self.assertFalse(result['source_sqlite_opened'])
        self.assertFalse(result['source_quiescence_enforced'])
        self.assertTrue(result['source_hashes_verified'])
        self.assertNotIn('private', json.dumps(result))
        self.assertFalse(any(self.source.path.as_uri() in str(call) for call in calls.call_args_list))
        self.assertEqual(before, self.digest(self.source.path))
        self.assertEqual(MemoryStore(self.target).get('private-key'), self.source.get('private-key'))
        self.assertCountEqual(self.root.iterdir(), [self.source.path, self.target])

    def test_real_hot_journal_recovers_only_copy_and_preserves_both_original_files(self):
        self.make_hot_journal()
        before = {path: self.digest(path) for path in (self.source.path, self.journal)}
        result = self.recover()
        self.assertTrue(result['recovered'])
        self.assertEqual(result['source_files_checked'], 2)
        self.assertEqual(result['notes_checked'], 101)
        self.assertEqual(MemoryStore(self.target).get('n0')['value'], 'a' * 4000)
        self.assertEqual(before, {path: self.digest(path) for path in before})
        with self.assertRaises(MemoryError):
            self.source.get('n0')

    def test_existing_destination_and_each_auxiliary_are_preserved_in_both_commands(self):
        logical = self.root / 'notes.json'
        backup_notes(self.source, logical)
        for suffix in ('', '-journal', '-wal', '-shm'):
            with self.subTest(suffix=suffix):
                occupied = Path(str(self.target) + suffix)
                occupied.write_bytes(b'preserve')
                for action in (self.recover, lambda: restore_notes(MemoryStore(self.target), logical, True)):
                    with self.assertRaises(MemoryError):
                        action()
                    self.assertEqual(occupied.read_bytes(), b'preserve')
                occupied.unlink()
        self.assertFalse(self.target.exists())

    def test_destination_sidecar_created_during_recovery_blocks_publication(self):
        from gensia.memory_recovery import _recover_private
        sidecar = Path(str(self.target) + '-journal')
        def competing(database):
            _recover_private(database)
            sidecar.write_bytes(b'competitor')
        with patch('gensia.memory_recovery._recover_private', side_effect=competing):
            with self.assertRaises(MemoryError):
                self.recover()
        self.assertFalse(self.target.exists())
        self.assertEqual(sidecar.read_bytes(), b'competitor')

    @unittest.skipUnless(os.name == 'posix', 'POSIX symbolic link fixture')
    def test_dangling_links_in_source_and_destination_auxiliaries_are_rejected(self):
        for path in (self.journal, Path(str(self.target) + '-wal')):
            with self.subTest(path=path.name):
                path.symlink_to(self.root / 'missing')
                with self.assertRaises(MemoryError):
                    self.recover()
                self.assertTrue(path.is_symlink())
                path.unlink()

    def test_source_hard_link_and_nonregular_journal_are_rejected(self):
        alias = self.root / 'alias'
        os.link(self.source.path, alias)
        with self.assertRaises(MemoryError):
            self.recover()
        alias.unlink()
        self.journal.mkdir()
        with self.assertRaises(MemoryError):
            self.recover()
        self.assertTrue(self.journal.is_dir())

    def test_wal_header_without_auxiliaries_is_rejected_before_sqlite(self):
        with closing(sqlite3.connect(self.source.path)) as db:
            self.assertEqual(db.execute('PRAGMA journal_mode=WAL').fetchone()[0], 'wal')
        self.assertFalse(Path(str(self.source.path) + '-wal').exists())
        with patch('gensia.memory_recovery.sqlite3.connect') as connect:
            with self.assertRaises(MemoryError):
                self.recover()
            connect.assert_not_called()

    def test_wal_and_shm_source_files_are_never_ignored(self):
        for suffix in ('-wal', '-shm'):
            with self.subTest(suffix=suffix):
                sidecar = Path(str(self.source.path) + suffix)
                sidecar.write_bytes(b'preserve')
                with self.assertRaises(MemoryError):
                    self.recover()
                self.assertEqual(sidecar.read_bytes(), b'preserve')
                sidecar.unlink()

    def test_superjournal_pointer_is_rejected_without_opening_sqlite_or_touching_external_file(self):
        # Valid modern SQLite super-journal suffix: -mj + 9 hex digits, with 9 at -3.
        sentinel = self.root / 'external-mj1234569ab'
        sentinel.write_bytes(b'do not modify')
        name = os.fsencode(sentinel)
        trailer = name + len(name).to_bytes(4, 'big') + sum(name).to_bytes(4, 'big') + JOURNAL_MAGIC
        page_size = 4096
        pages = self.source.path.stat().st_size // page_size
        header = JOURNAL_MAGIC + b'\x00' * 8 + pages.to_bytes(4, 'big')
        header += (512).to_bytes(4, 'big') + page_size.to_bytes(4, 'big')
        pseudo_page = (0x40000000 // page_size + 1).to_bytes(4, 'big')
        self.journal.write_bytes(header.ljust(512, b'\x00') + pseudo_page + trailer)
        before = self.digest(self.journal)
        with patch('gensia.memory_recovery.sqlite3.connect') as connect:
            with self.assertRaises(MemoryError):
                self.recover()
            connect.assert_not_called()
        self.assertEqual(sentinel.read_bytes(), b'do not modify')
        self.assertEqual(before, self.digest(self.journal))

    def test_huge_rollback_size_refused_before_sqlite(self):
        header = JOURNAL_MAGIC + b'\x00' * 8 + (0xffffffff).to_bytes(4, 'big')
        self.journal.write_bytes(header + (512).to_bytes(4, 'big') + (4096).to_bytes(4, 'big'))
        with patch('gensia.memory_recovery.sqlite3.connect') as connect:
            with self.assertRaises(MemoryError):
                self.recover()
            connect.assert_not_called()

    def test_source_mutation_detected_before_publication(self):
        from gensia.memory_recovery import _recover_private
        def mutate(database):
            _recover_private(database)
            self.source.set('changed', 'later')
        with patch('gensia.memory_recovery._recover_private', side_effect=mutate):
            with self.assertRaises(MemoryError):
                self.recover()
        self.assertFalse(self.target.exists())
        self.assertEqual(self.source.get('changed')['value'], 'later')

    def test_new_source_journal_detected_before_publication(self):
        from gensia.memory_recovery import _recover_private
        def mutate(database):
            _recover_private(database)
            self.journal.write_bytes(b'\x00' * 28)
        with patch('gensia.memory_recovery._recover_private', side_effect=mutate):
            with self.assertRaises(MemoryError):
                self.recover()
        self.assertFalse(self.target.exists())
        self.assertTrue(self.journal.exists())

    def test_oversized_source_missing_source_and_invalid_schema_fail_closed(self):
        with patch('gensia.memory_recovery.MAX_RECOVERY_BYTES', 10):
            with self.assertRaises(MemoryError):
                self.recover()
        with self.source.connect(write=True) as db:
            db.execute('CREATE TABLE unrelated (secret TEXT)')
        with self.assertRaises(MemoryError):
            self.recover()
        self.source.path.unlink()
        with self.assertRaises(MemoryError):
            self.recover()
        self.assertFalse(self.target.exists())

    def test_failed_validation_and_enospc_never_publish_destination(self):
        before = self.digest(self.source.path)
        for failure in (MemoryError('synthetic validation failure'), OSError(errno.ENOSPC, 'full')):
            with self.subTest(failure=type(failure).__name__):
                with patch('gensia.memory_recovery.check_memory', side_effect=failure):
                    with self.assertRaises(MemoryError):
                        self.recover()
                self.assertFalse(self.target.exists())
                self.assertEqual(before, self.digest(self.source.path))

    def test_external_cleanup_failure_reports_already_published_destination(self):
        class CleanupFailure(tempfile.TemporaryDirectory):
            def __init__(self, *args, **kwargs):
                self.fail = kwargs.get('prefix') == '.gensia-recovery-'
                super().__init__(*args, **kwargs)
            def cleanup(self):
                super().cleanup()
                if self.fail:
                    raise OSError('synthetic cleanup failure')
        with patch('gensia.memory_recovery.tempfile.TemporaryDirectory', CleanupFailure):
            result = self.recover()
        self.assertFalse(result['recovered'])
        self.assertTrue(result['destination_published'])
        self.assertTrue(result['do_not_retry'])
        self.assertIn('recovery_cleanup_failed', result['warnings'])
        self.assertIsNotNone(MemoryStore(self.target).get('private-key'))

    def test_cli_requires_flags_and_returns_metadata_only(self):
        args = ['memory', '--db', str(self.source.path), 'recover-copy', '--output', str(self.target)]
        with redirect_stderr(StringIO()) as errors:
            self.assertEqual(main(args), 6)
        self.assertNotIn('conteúdo', errors.getvalue())
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(main(args + ['--approve', '--source-stopped']), 0)
        result = json.loads(output.getvalue())
        self.assertTrue(result['recovered'])
        self.assertNotIn('private-key', output.getvalue())
        self.assertNotIn('conteúdo', output.getvalue())
