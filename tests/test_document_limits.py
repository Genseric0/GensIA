"""Bounded I/O regression tests; synthetic files and PDF parser fixture."""
import hashlib
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from gensia.documents import DocumentError, SafeTextDocuments, SafePdfDocuments


class BoundedDocumentTests(unittest.TestCase):
    def run_growth_case(self, pdf=False):
        limit = 1024 * 1024 if pdf else 1024
        stream = io.BytesIO(b'a' * (limit * 2))
        read_sizes = []
        original_read = stream.read
        def checked_read(size=-1):
            read_sizes.append(size)
            self.assertGreater(size, 0, 'Reading without a bound loads the whole file')
            self.assertLessEqual(size, limit + 1)
            return original_read(size)
        stream.read = checked_read
        # File was small at stat time; the stream represents subsequent growth.
        target = Mock()
        target.stat.return_value = SimpleNamespace(st_size=1)
        target.open.return_value = stream
        target.read_bytes.side_effect = AssertionError('Unbounded read_bytes is forbidden')
        audit = Mock()
        with tempfile.TemporaryDirectory() as temp:
            reader = (SafePdfDocuments if pdf else SafeTextDocuments)(temp, audit)
            with patch.object(reader, '_resolve', return_value=(target, 'fixture')):
                with patch('gensia.documents.importlib.import_module') as parser:
                    with self.assertRaisesRegex(DocumentError, 'durante a leitura'):
                        if pdf:
                            reader.read_pdf('fixture.pdf', max_mib=1)
                        else:
                            reader.read('fixture.txt', max_kib=1)
                    parser.assert_not_called()
        self.assertEqual(read_sizes, [limit + 1])
        self.assertTrue(stream.closed)
        audit.record.assert_called_once_with('read_pdf' if pdf else 'read_document', 'denied', 'fixture')

    def test_text_growth_is_bounded_and_denied(self):
        self.run_growth_case()

    def test_pdf_growth_is_bounded_before_parser(self):
        self.run_growth_case(pdf=True)

    def test_exact_text_limit_keeps_content_and_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            raw = ('á' * 512).encode('utf-8')
            (Path(temp) / 'exact.md').write_bytes(raw)
            result = SafeTextDocuments(temp, Mock()).read('exact.md', max_kib=1)
            self.assertEqual(result.bytes, 1024)
            self.assertEqual(result.content, 'á' * 512)
            self.assertEqual(result.sha256, hashlib.sha256(raw).hexdigest())

    def test_exact_pdf_limit_reaches_parser_with_complete_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            raw = b'%PDF-fixture' + b' ' * (1024 * 1024 - 12)
            (Path(temp) / 'exact.pdf').write_bytes(raw)
            factory = Mock(return_value=SimpleNamespace(is_encrypted=False,
                pages=[SimpleNamespace(extract_text=lambda: 'Synthetic text')]))
            with patch('gensia.documents.importlib.import_module',
                       return_value=SimpleNamespace(PdfReader=factory)):
                result = SafePdfDocuments(temp, Mock()).read_pdf('exact.pdf', max_mib=1)
            self.assertEqual(result.bytes, len(raw))
            self.assertEqual(factory.call_args.args[0].getvalue(), raw)

    def test_invalid_size_types_fail_before_path_access(self):
        with tempfile.TemporaryDirectory() as temp:
            for value in (True, 1.5, '1'):
                for reader, kwargs in ((SafeTextDocuments(temp, Mock()), {'max_kib': value}),
                                       (SafePdfDocuments(temp, Mock()), {'max_mib': value})):
                    with patch.object(reader, '_resolve') as resolve:
                        with self.assertRaises(DocumentError):
                            if isinstance(reader, SafePdfDocuments):
                                reader.read_pdf('unused.pdf', **kwargs)
                            else:
                                reader.read('unused.txt', **kwargs)
                        resolve.assert_not_called()

    def test_read_failure_closes_stream_and_records_error(self):
        with tempfile.TemporaryDirectory() as temp:
            stream = io.BytesIO(b'text')
            stream.read = Mock(side_effect=OSError('PRIVATE'))
            target = Mock()
            target.stat.return_value = SimpleNamespace(st_size=4)
            target.open.return_value = stream
            audit = Mock()
            reader = SafeTextDocuments(temp, audit)
            with patch.object(reader, '_resolve', return_value=(target, 'fixture.txt')):
                with self.assertRaises(DocumentError) as error:
                    reader.read('fixture.txt')
            self.assertTrue(stream.closed)
            self.assertNotIn('PRIVATE', str(error.exception))
            audit.record.assert_called_once_with('read_document', 'error', 'fixture.txt')
