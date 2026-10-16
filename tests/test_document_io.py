"""Deterministic filesystem races; no user documents or probabilistic threads."""
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from gensia.document_io import (ConfinedReadError, DESCRIPTOR_READS_SUPPORTED,
                                read_confined)
from gensia.documents import DocumentError, SafePdfDocuments, SafeTextDocuments
from gensia.pdf_process import _worker, extract_pdf_process


@unittest.skipUnless(DESCRIPTOR_READS_SUPPORTED, 'Descriptor-relative POSIX reads required')
class DocumentIoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'workspace'
        self.root.mkdir()
        self.outside = self.base / 'outside'
        self.outside.mkdir()
        self.path = self.root / 'safe.txt'
        self.path.write_text('public', encoding='utf-8')
        (self.outside / 'safe.txt').write_text('PRIVATE', encoding='utf-8')
        self.reader = SafeTextDocuments(self.root, Mock())

    def read(self, label='safe.txt', limit=1024):
        return read_confined(self.root, label, limit, self.reader._workspace_identity)

    def test_nested_utf8_document_and_compatibility_path(self):
        (self.root / 'nested').mkdir()
        (self.root / 'nested' / 'aula.md').write_text('Redes e segurança', encoding='utf-8')
        secure = self.reader.read('nested/aula.md')
        with patch('gensia.documents.DESCRIPTOR_READS_SUPPORTED', False):
            compatible = self.reader.read('nested/aula.md')
        self.assertEqual(secure.as_dict(), compatible.as_dict())

    def test_final_symlink_after_resolution_never_reaches_model(self):
        resolve = self.reader._resolve
        def changed(label):
            result = resolve(label)
            self.path.unlink()
            self.path.symlink_to(self.outside / 'safe.txt')
            return result
        provider = Mock()
        with patch.object(self.reader, '_resolve', side_effect=changed):
            with self.assertRaises(DocumentError) as error:
                self.reader.summarize('safe.txt', provider)
        provider.reply.assert_not_called()
        self.assertNotIn('PRIVATE', str(error.exception))

    def test_parent_swapped_to_symlink_before_open_is_refused(self):
        nested = self.root / 'nested'
        nested.mkdir()
        (nested / 'safe.txt').write_text('public', encoding='utf-8')
        resolve = self.reader._resolve
        def changed(label):
            result = resolve(label)
            nested.rename(self.root / 'original')
            nested.symlink_to(self.outside, target_is_directory=True)
            return result
        with patch.object(self.reader, '_resolve', side_effect=changed):
            with self.assertRaises(DocumentError):
                self.reader.read('nested/safe.txt')

    def test_parent_renamed_after_open_stays_anchored_to_original_directory(self):
        nested = self.root / 'nested'
        nested.mkdir()
        (nested / 'safe.txt').write_text('public', encoding='utf-8')
        original_open = os.open
        def raced_open(name, flags, **kwargs):
            descriptor = original_open(name, flags, **kwargs)
            if name == 'nested' and flags & os.O_DIRECTORY:
                nested.rename(self.root / 'original')
                nested.symlink_to(self.outside, target_is_directory=True)
            return descriptor
        with patch('gensia.document_io.os.open', side_effect=raced_open):
            result = self.read('nested/safe.txt')
        self.assertEqual(result, b'public')

    def test_regular_file_replaced_between_stat_and_open_is_refused(self):
        original_open = os.open
        def raced_open(name, flags, **kwargs):
            if name == 'safe.txt':
                self.path.rename(self.root / 'original.txt')
                self.path.write_text('REPLACED', encoding='utf-8')
            return original_open(name, flags, **kwargs)
        with patch('gensia.document_io.os.open', side_effect=raced_open):
            with self.assertRaisesRegex(ConfinedReadError, 'substituído'):
                self.read()

    def test_fifo_swap_after_stat_is_refused_without_reading(self):
        original_open = os.open
        def raced_open(name, flags, **kwargs):
            if name == 'safe.txt':
                self.path.unlink()
                os.mkfifo(self.path)
                self.assertTrue(flags & os.O_NONBLOCK)
            return original_open(name, flags, **kwargs)
        with patch('gensia.document_io.os.open', side_effect=raced_open):
            with patch('gensia.document_io.os.fdopen') as stream:
                with self.assertRaisesRegex(ConfinedReadError, 'regulares'):
                    self.read()
                stream.assert_not_called()

    def test_workspace_replaced_with_directory_or_symlink_is_refused(self):
        self.root.rename(self.base / 'old-workspace')
        self.root.mkdir()
        self.path.write_text('REPLACED', encoding='utf-8')
        with self.assertRaisesRegex(ConfinedReadError, 'pasta-base'):
            self.read()
        self.path.unlink()
        self.root.rmdir()
        self.root.symlink_to(self.outside, target_is_directory=True)
        with self.assertRaises(OSError):
            self.read()

    def test_hard_links_are_refused(self):
        os.link(self.path, self.root / 'alias.txt')
        with self.assertRaisesRegex(ConfinedReadError, 'hard links'):
            self.read()

    def test_in_place_mutation_during_read_is_refused(self):
        fdopen = os.fdopen
        @contextmanager
        def changed_stream(*args, **kwargs):
            with fdopen(*args, **kwargs) as actual:
                def read(size):
                    raw = actual.read(size)
                    self.path.write_text('mutate', encoding='utf-8')  # same byte count
                    info = self.path.stat()
                    os.utime(self.path, ns=(info.st_atime_ns, info.st_mtime_ns + 1000000))
                    return raw
                yield Mock(read=read)
        with patch('gensia.document_io.os.fdopen', side_effect=changed_stream):
            with self.assertRaisesRegex(ConfinedReadError, 'alterado durante'):
                self.read()

    def test_growth_read_is_bounded_and_closed(self):
        fdopen = os.fdopen
        sizes, streams = [], []
        @contextmanager
        def growing_stream(*args, **kwargs):
            with fdopen(*args, **kwargs) as actual:
                streams.append(actual)
                def read(size):
                    sizes.append(size)
                    self.path.write_bytes(b'x' * 2048)
                    return actual.read(size)
                yield Mock(read=read)
        with patch('gensia.document_io.os.fdopen', side_effect=growing_stream):
            with self.assertRaisesRegex(ConfinedReadError, 'durante a leitura'):
                self.read(limit=1024)
        self.assertEqual(sizes, [1025])
        self.assertTrue(all(stream.closed for stream in streams))

    def test_pdf_swap_is_refused_before_importing_parser(self):
        path = self.root / 'fixture.pdf'
        path.write_bytes(b'%PDF-fixture')
        reader = SafePdfDocuments(self.root, Mock())
        resolve = reader._resolve
        def changed(label):
            result = resolve(label)
            path.unlink()
            path.symlink_to(self.outside / 'safe.txt')
            return result
        with patch.object(reader, '_resolve', side_effect=changed):
            with patch('gensia.documents.importlib.import_module') as parser:
                with self.assertRaises(DocumentError):
                    reader.read_pdf('fixture.pdf')
                parser.assert_not_called()

    def test_worker_rejects_changed_workspace_before_pdf_read(self):
        request = {'workspace': str(self.root), 'path': 'fixture.pdf',
                   'workspace_identity': [-1, -1], 'max_mib': 1, 'max_pages': 1}
        with patch('gensia.pdf_process.apply_worker_limits', return_value={}):
            with patch('gensia.pdf_process.sys.stdin', Mock(buffer=io.BytesIO(json.dumps(request).encode()))):
                with patch.object(SafePdfDocuments, 'read_pdf') as parser:
                    self.assertEqual(_worker(), 8)
                    parser.assert_not_called()

    def test_parent_passes_initial_workspace_identity_to_worker(self):
        (self.root / 'fixture.pdf').write_bytes(b'%PDF-fixture')
        requests = []
        def refused_worker(command, **kwargs):
            requests.append(json.loads(kwargs['input']))
            return Mock(returncode=8)
        with self.assertRaises(DocumentError):
            extract_pdf_process(self.root, 'fixture.pdf', self.base / 'audit.jsonl', runner=refused_worker)
        self.assertEqual(requests[0]['workspace_identity'], list(self.reader._workspace_identity))

    @unittest.skipUnless(Path('/proc/self/fd').exists(), 'Linux fd inspection required')
    def test_no_descriptor_leak_after_success_or_failure(self):
        before = len(list(Path('/proc/self/fd').iterdir()))
        for _ in range(12):
            self.assertEqual(self.read(), b'public')
            with self.assertRaises(ConfinedReadError):
                self.read(limit=1)
        self.assertEqual(len(list(Path('/proc/self/fd').iterdir())), before)
