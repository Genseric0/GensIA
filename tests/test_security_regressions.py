"""Regression cases from the commercial-readiness source review."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from gensia.providers import OllamaProvider, ProviderUnavailable
from gensia.tools import AuditLogger, ToolError


class AuditRegressionTests(unittest.TestCase):
    def test_regular_log_appends_without_plaintext_target(self):
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / 'private' / 'audit.jsonl'
            audit = AuditLogger(log)
            audit.record('read', 'success', 'PRIVATE document')
            audit.record('read', 'denied', 'PRIVATE document')
            content = log.read_text(encoding='utf-8')
            self.assertEqual([json.loads(line)['outcome'] for line in content.splitlines()],
                             ['success', 'denied'])
            self.assertNotIn('PRIVATE document', content)
            if os.name == 'posix':
                self.assertEqual(log.stat().st_mode & 0o777, 0o600)

    @unittest.skipUnless(hasattr(os, 'O_NOFOLLOW'), 'Requires O_NOFOLLOW')
    def test_swap_to_symlink_between_check_and_open(self):
        with tempfile.TemporaryDirectory() as temp:
            log, target = Path(temp) / 'audit', Path(temp) / 'outside'
            target.write_bytes(b'keep')
            original_open = os.open
            def swapped_open(path, flags, mode):
                Path(path).symlink_to(target)
                return original_open(path, flags, mode)
            with patch('gensia.tools.os.open', side_effect=swapped_open):
                with self.assertRaises(ToolError):
                    AuditLogger(log).record('read', 'success', 'document')
            self.assertEqual(target.read_bytes(), b'keep')

    def test_hardlink_is_not_appended(self):
        with tempfile.TemporaryDirectory() as temp:
            target, log = Path(temp) / 'outside', Path(temp) / 'audit'
            target.write_bytes(b'keep')
            try:
                os.link(target, log)
            except OSError:
                self.skipTest('Hard links unavailable')
            with self.assertRaises(ToolError):
                AuditLogger(log).record('read', 'success', 'document')
            self.assertEqual(target.read_bytes(), b'keep')

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'Requires POSIX FIFO')
    def test_fifo_is_refused_without_waiting_for_reader(self):
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / 'audit'
            os.mkfifo(log)
            with self.assertRaises(ToolError):
                AuditLogger(log).record('read', 'success', 'document')

    def test_dangling_symlink_cannot_create_outside_log(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, log = root / 'outside', root / 'audit'
            try:
                log.symlink_to(target)
            except OSError:
                self.skipTest('Symlinks unavailable')
            with self.assertRaises(ToolError):
                AuditLogger(log).record('read', 'success', 'document')
            self.assertFalse(target.exists())

    def test_os_failure_is_a_domain_error(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch('gensia.tools.os.open', side_effect=PermissionError('PRIVATE PATH')):
                with self.assertRaises(ToolError) as error:
                    AuditLogger(Path(temp) / 'audit').record('read', 'error', 'document')
            self.assertNotIn('PRIVATE PATH', str(error.exception))


class ProviderRegressionTests(unittest.TestCase):
    def test_error_in_success_response_is_sanitized_for_all_types(self):
        from unittest.mock import MagicMock
        for value in ('SECRET\x1b[2J', {'private': 'SECRET'}, None):
            response = MagicMock()
            response.__enter__.return_value.read.return_value = json.dumps({'error': value}).encode()
            with patch('gensia.providers._LOCAL_OPENER.open', return_value=response):
                with self.assertRaises(ProviderUnavailable) as error:
                    OllamaProvider('test').reply('synthetic')
            self.assertNotIn('SECRET', str(error.exception))

    def test_truncated_http_response_becomes_controlled_error(self):
        from http.client import IncompleteRead
        with patch('gensia.providers._LOCAL_OPENER.open', side_effect=IncompleteRead(b'secret', 100)):
            with self.assertRaises(ProviderUnavailable) as error:
                OllamaProvider('test').reply('synthetic')
        self.assertNotIn('secret', str(error.exception))

    def test_http_error_body_is_not_disclosed_or_read(self):
        from unittest.mock import Mock
        body = Mock(wraps=io.BytesIO(b'{"error": "SECRET\\u001b[2J"}'))
        with patch('gensia.providers._LOCAL_OPENER.open', side_effect=HTTPError(
                'http://127.0.0.1', 500, 'server error', {}, body)):
            with self.assertRaises(ProviderUnavailable) as error:
                OllamaProvider('test').reply('synthetic prompt')
        self.assertNotIn('SECRET', str(error.exception))
        body.read.assert_not_called()
        body.close.assert_called_once()

    def test_structured_http_error_cannot_crash_handler(self):
        for payload in ({'error': {'detail': 'secret'}}, {'error': ['secret']}):
            body = io.BytesIO(json.dumps(payload).encode())
            with patch('gensia.providers._LOCAL_OPENER.open', side_effect=HTTPError(
                    'http://127.0.0.1', 500, 'error', {}, body)):
                with self.assertRaises(ProviderUnavailable):
                    OllamaProvider('test').reply('synthetic')

    def test_invalid_port_and_url_path_are_rejected_at_setup(self):
        for url in ('http://127.0.0.1:bad', 'http://127.0.0.1:65536',
                    'http://127.0.0.1:0', 'http://127.0.0.1/private',
                    'http://127.0.0.1/\n', 'http://localhost/#'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                OllamaProvider('test', url)
