import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from gensia.documents import DocumentError
from gensia.pdf_process import extract_pdf_process
from gensia.pdf_limits import ADDRESS_SPACE_BYTES, CPU_SECONDS, FILE_BYTES


def limit_report():
    if not sys.platform.startswith('linux'):
        return {'applied': False, 'platform': sys.platform}
    return {'applied': True, 'platform': sys.platform, 'address_space_bytes': ADDRESS_SPACE_BYTES,
            'cpu_seconds': CPU_SECONDS, 'file_bytes': FILE_BYTES, 'core_bytes': 0}


class PdfProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'fixture.pdf'
        self.path.write_bytes(b'%PDF-fixture')
        self.audit = self.root / 'audit.jsonl'

    def extract(self, **kwargs):
        return extract_pdf_process(self.root, 'fixture.pdf', self.audit, **kwargs)

    def result(self):
        return {'path': 'fixture.pdf', 'bytes': 12, 'characters': 4,
                'sha256': 'a' * 64, 'pages': 1, 'content': 'text'}

    def runner_for(self, raw, code=0):
        try:
            raw = json.dumps({'document': json.loads(raw), 'resource_limits': limit_report()}).encode()
        except (ValueError, UnicodeError):
            pass
        def run(command, **kwargs):
            kwargs['stdout'].write(raw)
            return SimpleNamespace(returncode=code)
        return Mock(side_effect=run)

    def test_process_contract_and_valid_result(self):
        runner = self.runner_for(json.dumps(self.result()).encode())
        output = self.extract(runner=runner)
        self.assertTrue(output['supervision']['separate_process'])
        self.assertFalse(output['supervision']['os_sandbox'])
        args, options = runner.call_args.args[0], runner.call_args.kwargs
        self.assertEqual(args[:3], [sys.executable, '-I', '-B'])
        self.assertFalse(options['shell'])
        self.assertNotIn('PYTHONPATH', options['env'])
        self.assertNotIn('PYTHONHOME', options['env'])
        self.assertFalse(Path(options['cwd']).exists())
        self.assertTrue(options['stdout'].closed)

    def test_limits_rejected_without_process(self):
        for kwargs in ({'timeout': 0}, {'timeout': float('nan')}, {'timeout': True},
                       {'max_mib': 0}, {'max_pages': True}):
            runner = Mock()
            with self.assertRaises(DocumentError):
                self.extract(runner=runner, **kwargs)
            runner.assert_not_called()

    def test_traversal_refused_without_process(self):
        runner = Mock()
        with self.assertRaises(DocumentError):
            extract_pdf_process(self.root, '../outside.pdf', self.audit, runner=runner)
        runner.assert_not_called()

    def test_invalid_or_oversized_output_is_refused(self):
        for raw in (b'not JSON SECRET', b'{}', b'x' * (2 * 1024 * 1024 + 1)):
            with self.assertRaises(DocumentError) as error:
                self.extract(runner=self.runner_for(raw))
            self.assertNotIn('SECRET', str(error.exception))

    def test_invalid_metadata_is_refused(self):
        for key, value in (('path', 'outside.pdf'), ('pages', 101), ('bytes', -1),
                           ('characters', 999), ('sha256', 'x' * 64)):
            result = self.result()
            result[key] = value
            with self.assertRaises(DocumentError):
                self.extract(runner=self.runner_for(json.dumps(result).encode()))

    def test_failed_worker_does_not_disclose_output(self):
        with self.assertRaises(DocumentError) as error:
            self.extract(runner=self.runner_for(b'SECRET', code=8))
        self.assertNotIn('SECRET', str(error.exception))

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux process existence check')
    def test_real_timeout_kills_and_reaps_direct_child(self):
        children = []
        real_popen = subprocess.Popen
        def record_child(*args, **kwargs):
            child = real_popen(*args, **kwargs)
            children.append(child)
            return child
        def slow_worker(command, **kwargs):
            return subprocess.run([sys.executable, '-I', '-c', 'import time; time.sleep(20)'], **kwargs)
        with patch('subprocess.Popen', side_effect=record_child):
            with self.assertRaisesRegex(DocumentError, 'processo foi encerrado'):
                self.extract(runner=slow_worker, timeout=1)
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].returncode, -signal.SIGKILL)
        # Verify reaping directly, without a startup marker or /proc PID reuse race.
        with self.assertRaises(ChildProcessError):
            os.waitpid(children[0].pid, os.WNOHANG)
        self.assertEqual(json.loads(self.audit.read_text().splitlines()[-1])['outcome'], 'timeout')

    @unittest.skipUnless(importlib.util.find_spec('pypdf'), 'Optional pypdf required')
    def test_real_worker_rejects_malformed_pdf(self):
        with self.assertRaises(DocumentError):
            self.extract()

    @unittest.skipUnless(importlib.util.find_spec('pypdf'), 'Optional pypdf required')
    def test_real_cli_extracts_text_with_pypdf(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        writer = PdfWriter()
        page = writer.add_blank_page(width=200, height=200)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
            DictionaryObject({NameObject('/F1'): font})})
        stream = DecodedStreamObject()
        stream.set_data(b'BT /F1 12 Tf 20 40 Td (GensIA fixture) Tj ET')
        page[NameObject('/Contents')] = writer._add_object(stream)
        writer.write(self.path)
        result = subprocess.run([sys.executable, '-m', 'gensia', 'document',
                                 '--workspace', str(self.root), '--audit', str(self.audit),
                                 'pdf-read-supervised', 'fixture.pdf'],
                                cwd=Path(__file__).resolve().parents[1], timeout=15,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertIn('GensIA fixture', output['content'])
        self.assertTrue(output['supervision']['separate_process'])
        self.assertEqual(output['pages'], 1)
