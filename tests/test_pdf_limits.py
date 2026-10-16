import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from gensia.documents import DocumentError
from gensia.pdf_limits import (ADDRESS_SPACE_BYTES, CPU_SECONDS, FILE_BYTES,
                               apply_worker_limits, validate_worker_limits)
from gensia.pdf_process import _worker, extract_pdf_process

ROOT = Path(__file__).resolve().parents[1]
LINUX = sys.platform.startswith('linux')


class PdfLimitsTests(unittest.TestCase):
    def fake_resource(self):
        states = {0: (-1, -1), 1: (100, 200), 2: (-1, -1), 3: (-1, -1)}
        api = SimpleNamespace(RLIMIT_CORE=0, RLIMIT_AS=1, RLIMIT_CPU=2,
                              RLIMIT_FSIZE=3, RLIM_INFINITY=-1)
        api.getrlimit = Mock(side_effect=lambda kind: states[kind])
        api.setrlimit = Mock(side_effect=lambda kind, caps: states.__setitem__(kind, caps))
        return api

    def test_never_raises_inherited_limits_and_verifies_caps(self):
        api = self.fake_resource()
        with patch('gensia.pdf_limits.sys.platform', 'linux'), patch.dict(sys.modules, resource=api):
            report = apply_worker_limits()
            self.assertTrue(validate_worker_limits(report))
        self.assertEqual(report['address_space_bytes'], 100)
        self.assertEqual(report['cpu_seconds'], CPU_SECONDS)
        self.assertEqual(report['file_bytes'], FILE_BYTES)
        self.assertEqual(report['core_bytes'], 0)
        self.assertEqual(api.setrlimit.call_count, 4)

    def test_unsupported_platform_does_not_claim_quotas(self):
        with patch('gensia.pdf_limits.sys.platform', 'win32'):
            self.assertEqual(apply_worker_limits(), {'applied': False, 'platform': 'win32'})
            self.assertTrue(validate_worker_limits(apply_worker_limits()))
            self.assertFalse(validate_worker_limits({'applied': True, 'platform': 'win32'}))

    def test_linux_rejects_missing_false_or_excessive_reports(self):
        good = {'applied': True, 'platform': 'linux', 'core_bytes': 0,
                'address_space_bytes': ADDRESS_SPACE_BYTES, 'cpu_seconds': CPU_SECONDS,
                'file_bytes': FILE_BYTES}
        invalid = [None, {}, {'applied': False, 'platform': 'linux'},
                   dict(good, core_bytes=True), dict(good, file_bytes=FILE_BYTES + 1),
                   dict(good, cpu_seconds=-1), dict(good, platform='win32')]
        with patch('gensia.pdf_limits.sys.platform', 'linux'):
            self.assertTrue(validate_worker_limits(good))
            for report in invalid:
                self.assertFalse(validate_worker_limits(report))

    def test_limit_setup_failure_stops_before_stdin_or_parser(self):
        stdin = Mock()
        with patch('gensia.pdf_process.apply_worker_limits', side_effect=OSError('SECRET')):
            with patch('gensia.pdf_process.sys.stdin', stdin):
                with patch('gensia.pdf_process.SafePdfDocuments') as parser:
                    self.assertEqual(_worker(), 8)
                    parser.assert_not_called()
        stdin.buffer.read.assert_not_called()

    def test_unconfirmed_kernel_limit_is_failure(self):
        api = self.fake_resource()
        api.setrlimit.side_effect = None
        with patch('gensia.pdf_limits.sys.platform', 'linux'), patch.dict(sys.modules, resource=api):
            with self.assertRaises(RuntimeError):
                apply_worker_limits()

    @unittest.skipUnless(LINUX, 'Linux requires a positive limits report')
    def test_parent_refuses_worker_without_confirmed_limits(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'test.pdf').write_bytes(b'%PDF-fixture')
            def unconfirmed_worker(command, **kwargs):
                kwargs['stdout'].write(json.dumps({'document': {}, 'resource_limits':
                    {'applied': False, 'platform': sys.platform}}).encode())
                return SimpleNamespace(returncode=0)
            with self.assertRaisesRegex(DocumentError, 'worker PDF inválidos'):
                extract_pdf_process(root, 'test.pdf', root / 'audit.jsonl',
                                    runner=unconfirmed_worker)

    @unittest.skipUnless(LINUX, 'Linux resource limits required')
    def test_real_address_space_file_and_core_limits_only_in_child(self):
        import resource
        before = {kind: resource.getrlimit(kind) for kind in
                  (resource.RLIMIT_AS, resource.RLIMIT_CPU, resource.RLIMIT_FSIZE, resource.RLIMIT_CORE)}
        with tempfile.TemporaryDirectory() as temp:
            code = (f'import sys; sys.path.insert(0, {str(ROOT)!r}); '
                    'from gensia.pdf_limits import apply_worker_limits; '
                    'import json, os, resource\n'
                    'report=apply_worker_limits()\n'
                    'try:\n bytearray(1024*1024*1024)\n'
                    'except MemoryError:\n report["allocation_refused"]=True\n'
                    'try:\n'
                    ' with open("large", "wb", buffering=0) as out:\n'
                    '  for i in range(257): out.write(b"x"*16384)\n'
                    'except OSError:\n report["file_refused"]=True\n'
                    'report["size"]=os.stat("large").st_size\n'
                    'report["kernel_as"]=resource.getrlimit(resource.RLIMIT_AS)[1]\n'
                    'report["kernel_core"]=resource.getrlimit(resource.RLIMIT_CORE)[1]\n'
                    'print(json.dumps(report))')
            result = subprocess.run([sys.executable, '-I', '-B', '-c', code], cwd=temp,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report['allocation_refused'])
            self.assertTrue(report['file_refused'])
            self.assertLessEqual(report['size'], FILE_BYTES)
            self.assertEqual(report['kernel_as'], report['address_space_bytes'])
            self.assertEqual(report['kernel_core'], 0)
        self.assertEqual(before, {kind: resource.getrlimit(kind) for kind in before})

    @unittest.skipUnless(LINUX, 'Linux CPU signal required')
    def test_real_cpu_hard_limit_terminates_child(self):
        # Same implementation, reduced to one CPU second only inside this test child.
        code = (f'import sys; sys.path.insert(0, {str(ROOT)!r}); '
                'import gensia.pdf_limits as limits; limits.CPU_SECONDS=1; '
                'limits.apply_worker_limits()\nwhile True: pass')
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable, '-I', '-B', '-c', code], cwd=temp,
                                    capture_output=True, timeout=15)
        self.assertEqual(result.returncode, -signal.SIGKILL)

    @unittest.skipUnless(LINUX and importlib.util.find_spec('pypdf'), 'Linux and pypdf required')
    def test_real_resource_failure_then_pdf_success_and_large_parent_audit(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            writer = PdfWriter()
            page = writer.add_blank_page(width=200, height=200)
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                     NameObject('/Subtype'): NameObject('/Type1'),
                                     NameObject('/BaseFont'): NameObject('/Helvetica')})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
                DictionaryObject({NameObject('/F1'): font})})
            stream = DecodedStreamObject()
            stream.set_data(b'BT /F1 12 Tf 20 40 Td (Recovered) Tj ET')
            page[NameObject('/Contents')] = writer._add_object(stream)
            writer.write(root / 'good.pdf')
            audit = root / 'audit.jsonl'
            # Parent audit is intentionally larger than the worker's per-file cap.
            with audit.open('wb') as out:
                out.seek(FILE_BYTES + 1)
                out.write(b'\n')
            failing_code = (f'import sys; sys.path.insert(0, {str(ROOT)!r}); '
                            'from gensia.pdf_limits import apply_worker_limits; apply_worker_limits(); '
                            'bytearray(1024*1024*1024)')
            def failing_runner(command, **kwargs):
                return subprocess.run([sys.executable, '-I', '-B', '-c', failing_code], **kwargs)
            with self.assertRaisesRegex(DocumentError, 'limite de recursos'):
                extract_pdf_process(root, 'good.pdf', audit, runner=failing_runner)
            result = extract_pdf_process(root, 'good.pdf', audit)
            self.assertIn('Recovered', result['content'])
            self.assertTrue(result['supervision']['resource_limits']['applied'])
            self.assertFalse((root / 'worker-audit.jsonl').exists())
            events = audit.read_text().splitlines()[-2:]
            self.assertEqual([json.loads(line)['outcome'] for line in events], ['error', 'success'])
