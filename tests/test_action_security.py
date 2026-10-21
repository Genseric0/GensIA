import json
from contextlib import redirect_stderr
from io import StringIO
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from gensia.kev import CisaKevCatalog, KevError
from gensia.cli import main
from gensia.security import VirusTotalUrlReputation, SecurityError
from gensia.tools import AppLauncher, AuditLogger, ToolError, ToolPermissionError


class ActionSecurityTests(unittest.TestCase):
    def test_only_exact_true_authorizes_sensitive_methods(self):
        for approved in (False, None, 0, 1, 'false', 'true', [], {}, [True]):
            runner, opener = Mock(), Mock()
            with patch.object(AppLauncher, '_resolve_executable') as resolve:
                with self.assertRaises(ToolPermissionError):
                    AppLauncher(Mock(), 'win32', runner).open('calculator', approved)
            runner.assert_not_called()
            resolve.assert_not_called()
            with self.assertRaises(SecurityError):
                VirusTotalUrlReputation(Mock(), 'synthetic', opener=opener).lookup('https://example.com/', approved)
            with self.assertRaises(KevError):
                CisaKevCatalog(Mock(), opener=opener).update('synthetic.json', approved)
            opener.assert_not_called()

    def test_intent_recorded_before_process_and_final_record_after(self):
        events = []
        audit = Mock()
        audit.record.side_effect = lambda action,outcome,target: events.append(outcome)
        runner = lambda *args, **kwargs: events.append('process')
        with patch.object(AppLauncher, '_resolve_executable', return_value=('calc.exe', 'system')):
            result = AppLauncher(audit, 'win32', runner).open('calculator', True)
        self.assertEqual(events, ['intent','process','success'])
        self.assertTrue(result['audit_completed'])

    def test_failed_intent_blocks_process_and_sanitizes_error(self):
        runner = Mock()
        audit = Mock(record=Mock(side_effect=OSError('PRIVATE')))
        with patch.object(AppLauncher, '_resolve_executable', return_value=('calc.exe','system')):
            with self.assertRaises(ToolError) as error:
                AppLauncher(audit,'win32',runner).open('calculator',True)
        runner.assert_not_called()
        self.assertNotIn('PRIVATE',str(error.exception))

    def test_failed_final_audit_reports_effect_and_no_retry(self):
        runner,audit = Mock(),Mock()
        audit.record.side_effect = [None, OSError('PRIVATE')]
        with patch.object(AppLauncher, '_resolve_executable', return_value=('calc.exe','system')):
            result = AppLauncher(audit,'win32',runner).open('calculator',True)
        runner.assert_called_once()
        self.assertEqual(result['opened'],'calculator')
        self.assertFalse(result['audit_completed'])
        self.assertEqual(result['warning'],'app_opened_final_audit_failed_do_not_retry')
        self.assertNotIn('PRIVATE',json.dumps(result))

    def test_real_audit_flush_fsync_before_return_and_failure_is_controlled(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'audit.jsonl'
            original = os.fsync
            with patch('gensia.tools.os.fsync', wraps=original) as fsync:
                AuditLogger(path).record('open_app','intent','synthetic')
            fsync.assert_called_once()
            self.assertEqual(json.loads(path.read_text())['outcome'],'intent')
            with patch('gensia.tools.os.fsync', side_effect=OSError('PRIVATE')):
                with self.assertRaises(ToolError) as error:
                    AuditLogger(path).record('open_app','intent','synthetic')
            self.assertNotIn('PRIVATE',str(error.exception))

    def test_external_request_requires_available_intent_audit(self):
        def fail_intent(action,outcome,target):
            if outcome == 'intent':
                raise ToolError('synthetic failure')
        opener,audit = Mock(),Mock(record=Mock(side_effect=fail_intent))
        with self.assertRaises(ToolError):
            VirusTotalUrlReputation(audit,'synthetic',opener=opener).lookup('https://example.com/',True)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ToolError):
                CisaKevCatalog(audit,opener=opener).update(Path(directory)/'new.json',True)
            self.assertFalse((Path(directory)/'new.json').exists())
        opener.assert_not_called()

    def test_cli_security_audit_failure_has_controlled_exit(self):
        stderr = StringIO()
        with patch('gensia.cli.AuditLogger', side_effect=ToolError('Audit indisponível.')):
            with redirect_stderr(stderr):
                code = main(['security', 'url', 'https://example.com/'])
        self.assertEqual(code, 9)
        self.assertEqual(stderr.getvalue().strip(), 'Audit indisponível.')

    def test_completed_external_effect_is_reported_when_final_audit_fails(self):
        from tests.test_kev import FakeResponse, catalog_bytes

        def fail_final(action, outcome, target):
            if action in ('lookup_url_reputation', 'update_cisa_kev') and outcome in ('success', 'not_found'):
                raise ToolError('PRIVATE')

        audit = Mock(record=Mock(side_effect=fail_final))
        report = {'data': {'attributes': {'last_analysis_stats': {}}}}
        opener = Mock(return_value=FakeResponse(json.dumps(report).encode()))
        result = VirusTotalUrlReputation(audit, 'synthetic', opener=opener).lookup('https://example.com/', True)
        opener.assert_called_once()
        self.assertTrue(result['external_request_performed'])
        self.assertFalse(result['audit_completed'])
        self.assertIn('do_not_retry', result['warning'])
        self.assertNotIn('PRIVATE', json.dumps(result))
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)/'new.json'
            opener = Mock(return_value=FakeResponse(catalog_bytes()))
            result = CisaKevCatalog(audit, opener=opener).update(cache, True)
            opener.assert_called_once()
            self.assertTrue(cache.is_file())
            self.assertTrue(result['cache_changed'])
            self.assertFalse(result['audit_completed'])
            self.assertIn('do_not_retry', result['warning'])
            self.assertNotIn('PRIVATE', json.dumps(result))
