"""Fault injection and actual process termination, with synthetic data only."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from gensia.memory import MemoryError, MemoryStore
from gensia.memory_backup import backup_notes
from gensia.memory_restore import restore_notes
from unittest.mock import patch


class MemoryFailureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'notes.sqlite3'
        self.store = MemoryStore(self.path)
        self.store.set('confirmed', 'original')

    def kill_at_checkpoint(self, script, *args):
        child = subprocess.Popen([sys.executable, '-u', '-c', script, *map(str, args)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        try:
            # communicate has a timeout even when a child fails before readiness.
            # A separate marker line is read by a bounded reader thread.
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(child.stdout.readline)
                try:
                    line = future.result(timeout=10)
                finally:
                    child.kill()
                    child.wait(timeout=10)
            _, errors = child.communicate(timeout=10)
            self.assertEqual(line.strip(), 'READY', errors)
        finally:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=10)

    def test_killed_backup_before_publish_leaves_no_destination(self):
        target = self.root / 'backup.json'
        self.kill_at_checkpoint('''
import sys
from gensia.memory import MemoryStore
from gensia.memory_backup import backup_notes
import gensia.publication as publication
def pause(fd):
    print('READY', flush=True)
    sys.stdin.read()
publication.os.fsync = pause
backup_notes(MemoryStore(sys.argv[1]), sys.argv[2])
''', self.path, target)
        self.assertFalse(target.exists())
        self.assertTrue(list(self.root.glob('.gensia-publish-*')))
        self.assertEqual(self.store.get('confirmed')['value'], 'original')

    def test_killed_process_after_backup_completion_keeps_valid_destination(self):
        target = self.root / 'backup.json'
        self.kill_at_checkpoint('''
import sys
from gensia.memory import MemoryStore
from gensia.memory_backup import backup_notes
backup_notes(MemoryStore(sys.argv[1]), sys.argv[2])
print('READY', flush=True)
sys.stdin.read()
''', self.path, target)
        self.assertEqual(json.loads(target.read_text())['notes'][0]['value'], 'original')
        self.assertEqual(target.stat().st_nlink, 1)

    def test_killed_restore_before_publish_preserves_backup_and_absent_destination(self):
        backup = self.root / 'source.json'
        backup_notes(self.store, backup)
        original = backup.read_bytes()
        target = self.root / 'restored.sqlite3'
        self.kill_at_checkpoint('''
import sys
from gensia.memory import MemoryStore
from gensia.memory_restore import restore_notes
import gensia.publication as publication
def pause(fd):
    print('READY', flush=True)
    sys.stdin.read()
publication.os.fsync = pause
restore_notes(MemoryStore(sys.argv[1]), sys.argv[2], approved=True)
''', target, backup)
        self.assertFalse(target.exists())
        self.assertEqual(backup.read_bytes(), original)
        self.assertEqual(self.store.get('confirmed')['value'], 'original')

    def test_restore_reports_postpublication_warning_without_retry(self):
        backup = self.root / 'source.json'
        backup_notes(self.store, backup)
        target = MemoryStore(self.root / 'restored.sqlite3')
        with patch('gensia.publication._sync_parent', return_value=False):
            result = restore_notes(target, backup, approved=True)
        self.assertTrue(result['restored'])
        self.assertTrue(result['destination_published'])
        self.assertTrue(result['do_not_retry'])
        self.assertEqual(result['warnings'], ['directory_sync_failed'])
        self.assertEqual(target.get('confirmed')['value'], 'original')

    def test_build_cleanup_file_exists_error_does_not_misreport_published_restore(self):
        backup = self.root / 'source.json'
        backup_notes(self.store, backup)
        target = MemoryStore(self.root / 'restored.sqlite3')
        class CleanupFailure(tempfile.TemporaryDirectory):
            def __init__(self, *args, **kwargs):
                self.fail = kwargs.get('prefix') == 'gensia-restore-'
                super().__init__(*args, **kwargs)
            def cleanup(self):
                super().cleanup()
                if self.fail:
                    raise FileExistsError('synthetic cleanup error')
        with patch('gensia.memory_restore.tempfile.TemporaryDirectory', CleanupFailure):
            result = restore_notes(target, backup, approved=True)
        self.assertFalse(result['restored'])
        self.assertTrue(result['destination_published'])
        self.assertTrue(result['do_not_retry'])
        self.assertEqual(result['warnings'], ['build_cleanup_failed'])
        self.assertEqual(target.get('confirmed')['value'], 'original')

    @unittest.skipUnless(os.name == 'posix', 'POSIX hard-link publication window')
    def test_killed_after_restore_publish_leaves_complete_but_guarded_hard_link(self):
        backup = self.root / 'source.json'
        backup_notes(self.store, backup)
        target = self.root / 'restored.sqlite3'
        self.kill_at_checkpoint('''
import sys
from gensia.memory import MemoryStore
from gensia.memory_restore import restore_notes
import gensia.publication as publication
original = publication._publish
def pause(stage, destination):
    original(stage, destination)
    print('READY', flush=True)
    sys.stdin.read()
publication._publish = pause
restore_notes(MemoryStore(sys.argv[1]), sys.argv[2], approved=True)
''', target, backup)
        self.assertEqual(target.stat().st_nlink, 2)
        with self.assertRaises(MemoryError):
            MemoryStore(target).get('confirmed')
        # Verify completed bytes independently, without weakening MemoryStore.
        with closing(sqlite3.connect(target.as_uri() + '?mode=ro', uri=True)) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone(), ('ok',))
            self.assertEqual(db.execute("SELECT value FROM memories WHERE key='confirmed'").fetchone(), ('original',))

    def test_sqlite_full_rolls_back_without_losing_committed_note(self):
        with self.assertRaises(MemoryError) as caught:
            with self.store.connect(write=True) as db:
                pages = db.execute('PRAGMA page_count').fetchone()[0]
                self.assertEqual(db.execute(f'PRAGMA max_page_count={pages}').fetchone()[0], pages)
                db.execute("UPDATE memories SET value='uncommitted' WHERE key='confirmed'")
                db.execute('INSERT INTO memories VALUES (?, ?, ?)',
                           ('oversized-test', 'x' * 100000, '2026-10-21T00:00:00+00:00'))
        self.assertEqual(caught.exception.__cause__.sqlite_errorcode, sqlite3.SQLITE_FULL)
        self.assertEqual(self.store.get('confirmed')['value'], 'original')
        self.assertIsNone(self.store.get('oversized-test'))

    def test_killed_uncommitted_transaction_in_delete_and_wal_modes(self):
        for journal in ('DELETE', 'WAL'):
            with self.subTest(journal=journal):
                with self.store.connect(write=True) as db:
                    self.assertEqual(db.execute('PRAGMA journal_mode=' + journal).fetchone()[0].upper(), journal)
                self.kill_at_checkpoint('''
import sys
from gensia.memory import MemoryStore
with MemoryStore(sys.argv[1]).connect(write=True) as db:
    db.execute("UPDATE memories SET value='uncommitted' WHERE key='confirmed'")
    print('READY', flush=True)
    sys.stdin.read()
''', self.path)
                self.assertEqual(self.store.get('confirmed')['value'], 'original')

    def test_hot_rollback_journal_requires_explicit_writable_recovery(self):
        with self.store.connect(write=True) as db:
            db.executemany('INSERT INTO memories VALUES (?, ?, ?)',
                           [(f'n{i}', 'a' * 4000, '2026-10-21T00:00:00+00:00') for i in range(100)])
        self.kill_at_checkpoint('''
import sys
from gensia.memory import MemoryStore
with MemoryStore(sys.argv[1]).connect(write=True) as db:
    db.execute('PRAGMA cache_size=1')
    db.execute("UPDATE memories SET value=replace(value, 'a', 'b')")
    print('READY', flush=True)
    sys.stdin.read()
''', self.path)
        self.assertTrue(Path(str(self.path) + '-journal').exists())
        with self.assertRaises(MemoryError):
            self.store.get('confirmed')  # Read-only paths must not silently repair.
        # Explicit writable recovery only on this disposable synthetic fixture.
        with closing(sqlite3.connect(self.path)) as recovery:
            self.assertEqual(recovery.execute('PRAGMA integrity_check').fetchone(), ('ok',))
        self.assertEqual(self.store.get('n0')['value'], 'a' * 4000)
        self.assertEqual(self.store.get('confirmed')['value'], 'original')
