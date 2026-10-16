from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from gensia.pdf_limits import ADDRESS_SPACE_BYTES, CPU_SECONDS, FILE_BYTES
from gensia.protections import _worker_capabilities, main, protection_report


class ProtectionTests(unittest.TestCase):
    def resource(self):
        api = SimpleNamespace(RLIMIT_AS=1, RLIMIT_CPU=2, RLIMIT_FSIZE=3,
                              RLIMIT_CORE=4, RLIM_INFINITY=-1)
        api.getrlimit = Mock(side_effect=lambda kind: (100, 200) if kind == 1 else (-1, -1))
        api.setrlimit = Mock(side_effect=AssertionError('Must never change limits'))
        return api

    def test_linux_planned_limits_preserve_lower_inherited_caps(self):
        api = self.resource()
        with patch('gensia.protections.sys.platform', 'linux'), patch(
                'gensia.protections.importlib.import_module', return_value=api):
            report = _worker_capabilities()
        self.assertEqual(report['state'], 'available_unverified')
        self.assertEqual(report['configured_caps']['address_space_bytes'], ADDRESS_SPACE_BYTES)
        self.assertEqual(report['planned_caps'], {'address_space_bytes': 100,
                         'cpu_seconds': CPU_SECONDS, 'file_bytes': FILE_BYTES, 'core_bytes': 0})
        self.assertFalse(report['enforcement_validated'])
        self.assertFalse(report['limits_changed'])
        api.setrlimit.assert_not_called()

    def test_non_linux_never_imports_resource_or_claims_quotas(self):
        for platform in ('win32', 'darwin'):
            with patch('gensia.protections.sys.platform', platform), patch(
                    'gensia.protections.importlib.import_module') as load:
                report = _worker_capabilities()
            self.assertEqual(report['state'], 'unsupported')
            self.assertIsNone(report['planned_caps'])
            load.assert_not_called()

    def test_missing_or_broken_resource_is_sanitized_and_not_partially_reported(self):
        for error in (ImportError('SECRET'), OSError('PRIVATE'), AttributeError('PATH'), ValueError('ENV')):
            api = self.resource()
            api.getrlimit.side_effect = [(-1, -1), error]
            with patch('gensia.protections.sys.platform', 'linux'), patch(
                    'gensia.protections.importlib.import_module', return_value=api):
                report = _worker_capabilities()
            self.assertEqual(report['state'], 'unavailable')
            self.assertIsNone(report['planned_caps'])
            self.assertNotIn(str(error), json.dumps(report))
        with patch('gensia.protections.sys.platform', 'linux'), patch(
                'gensia.protections.importlib.import_module', side_effect=ImportError('SECRET')):
            self.assertEqual(_worker_capabilities()['state'], 'unavailable')

    def test_compatibility_read_mode_is_explicit_and_not_approved(self):
        with patch('gensia.protections.sys.platform', 'win32'), patch(
                'gensia.protections.document_io.DESCRIPTOR_READS_SUPPORTED', False):
            report = protection_report()
        self.assertEqual(report['document_reads']['mode'], 'path_compatibility')
        self.assertFalse(report['document_reads']['capability_available'])
        self.assertFalse(report['os_sandbox'])
        self.assertFalse(report['commercial_approval'])
        self.assertEqual(len(report['warnings']), 3)

    def test_report_does_not_open_personal_files_network_processes_or_change_limits(self):
        api = self.resource()
        with patch('gensia.protections.sys.platform', 'linux'), patch(
                'os.open', side_effect=AssertionError('No files')), patch(
                'pathlib.Path.read_bytes', side_effect=AssertionError('No documents')), patch(
                'socket.socket', side_effect=AssertionError('No network')), patch(
                'subprocess.Popen', side_effect=AssertionError('No process')), patch(
                'gensia.pdf_limits.apply_worker_limits', side_effect=AssertionError('No enforcement')), patch.dict(
                'os.environ', {'GENSIA_API_TOKEN': 'PRIVATE_TOKEN', 'PRIVATE_PATH': '/SECRET_HOME'}), patch(
                'gensia.protections.importlib.import_module', return_value=api):
            report = protection_report()
        for name in ('limits_changed', 'processes_started', 'network_requests', 'personal_data_accessed'):
            self.assertFalse(report[name])
        self.assertNotIn('PRIVATE_TOKEN', json.dumps(report))
        self.assertNotIn('SECRET_HOME', json.dumps(report))
        api.setrlimit.assert_not_called()

    def test_reports_do_not_share_mutable_caps_or_warnings(self):
        with patch('gensia.protections.sys.platform', 'win32'):
            report = protection_report()
            report['warnings'].clear()
            report['pdf_worker']['resource_limits']['configured_caps']['core_bytes'] = 100
            again = protection_report()
        self.assertTrue(again['warnings'])
        self.assertEqual(again['pdf_worker']['resource_limits']['configured_caps']['core_bytes'], 0)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux current limits required')
    def test_real_capability_probe_does_not_change_parent_limits(self):
        import resource
        kinds = (resource.RLIMIT_AS, resource.RLIMIT_CPU, resource.RLIMIT_FSIZE, resource.RLIMIT_CORE)
        before = [resource.getrlimit(kind) for kind in kinds]
        report = protection_report()
        self.assertEqual(report['pdf_worker']['resource_limits']['state'], 'available_unverified')
        self.assertEqual([resource.getrlimit(kind) for kind in kinds], before)
        self.assertFalse(report['document_reads']['execution_validated'])

    def test_cli_real_json_and_zero_means_report_not_approval(self):
        result = subprocess.run([sys.executable, '-B', '-m', 'gensia.protections'],
                                cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['schema_version'], 1)
        self.assertFalse(report['commercial_approval'])
        self.assertFalse(report['network_requests'])

    def test_cli_unknown_arguments_fail_before_probe(self):
        with patch('gensia.protections.protection_report') as probe, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                main(['--unknown'])
        self.assertEqual(error.exception.code, 2)
        probe.assert_not_called()
