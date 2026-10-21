import errno
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gensia.publication import publish_new


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / 'completed'

    def test_complete_private_file_and_cleanup(self):
        result = publish_new(self.target, lambda output: output.write(b'complete'))
        self.assertEqual(self.target.read_bytes(), b'complete')
        self.assertEqual(list(self.root.iterdir()), [self.target])
        self.assertEqual(self.target.stat().st_nlink, 1)
        self.assertTrue(result['file_synced'])
        self.assertTrue(result['destination_published'])
        self.assertTrue(result['staging_cleaned'])
        self.assertFalse(result['do_not_retry'])
        if os.name == 'posix':
            self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)
            self.assertTrue(result['directory_synced'])
        else:
            self.assertIsNone(result['directory_synced'])

    def test_partial_write_enospc_never_publishes(self):
        def writer(output):
            output.write(b'partial')
            raise OSError(errno.ENOSPC, 'synthetic disk full')
        with self.assertRaises(OSError):
            publish_new(self.target, writer)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_fsync_enospc_never_publishes(self):
        with patch('gensia.publication.os.fsync', side_effect=OSError(errno.ENOSPC, 'full')):
            with self.assertRaises(OSError):
                publish_new(self.target, lambda output: output.write(b'complete'))
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_destination_is_untouched(self):
        self.target.write_bytes(b'existing')
        with self.assertRaises(FileExistsError):
            publish_new(self.target, lambda output: self.fail('must not write'))
        self.assertEqual(self.target.read_bytes(), b'existing')

    def test_competing_destination_is_never_overwritten(self):
        def writer(output):
            output.write(b'ours')
            self.target.write_bytes(b'competitor')
        with self.assertRaises(FileExistsError):
            publish_new(self.target, writer)
        self.assertEqual(self.target.read_bytes(), b'competitor')
        self.assertEqual(list(self.root.iterdir()), [self.target])

    def test_unsupported_publication_fails_closed(self):
        with patch('gensia.publication._publish', side_effect=OSError(errno.ENOTSUP, 'unsupported')):
            with self.assertRaises(OSError):
                publish_new(self.target, lambda output: output.write(b'complete'))
        self.assertFalse(self.target.exists())

    def test_directory_sync_failure_reports_existing_completed_destination(self):
        with patch('gensia.publication._sync_parent', return_value=False):
            result = publish_new(self.target, lambda output: output.write(b'complete'))
        self.assertEqual(self.target.read_bytes(), b'complete')
        self.assertEqual(result['warnings'], ['directory_sync_failed'])
        self.assertTrue(result['do_not_retry'])
        self.assertTrue(result['destination_published'])

    def test_cleanup_failure_after_publication_is_not_a_retryable_absence(self):
        cleanup = tempfile.TemporaryDirectory.cleanup
        def failed_cleanup(directory):
            cleanup(directory)
            raise OSError('synthetic cleanup failure')
        with patch('gensia.publication.tempfile.TemporaryDirectory.cleanup', failed_cleanup):
            result = publish_new(self.target, lambda output: output.write(b'complete'))
        self.assertEqual(self.target.read_bytes(), b'complete')
        self.assertFalse(result['staging_cleaned'])
        self.assertTrue(result['destination_published'])
        self.assertEqual(result['warnings'], ['staging_cleanup_failed'])
        self.assertTrue(result['do_not_retry'])
