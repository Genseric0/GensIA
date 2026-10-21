from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import threading
import unittest
from unittest.mock import patch

from gensia.model_probe import PROBE_PROMPT, main, probe
from gensia.providers import ProviderError, ProviderUnavailable


class ModelProbeTests(unittest.TestCase):
    def test_approval_and_limits_precede_provider_creation(self):
        cases = [{}, {"approve": 1}, {"approve": True, "repeats": True},
                 {"approve": True, "repeats": 0}, {"approve": True, "repeats": 4},
                 {"approve": True, "timeout": float('nan')},
                 {"approve": True, "timeout": float('inf')},
                 {"approve": True, "timeout": True},
                 {"approve": True, "timeout": 0}, {"approve": True, "timeout": 121}]
        with patch('gensia.model_probe.OllamaProvider') as provider:
            for case in cases:
                with self.subTest(case=case), self.assertRaises(ValueError):
                    probe('test:small', **case)
            provider.assert_not_called()

    def test_invalid_endpoint_or_model_has_no_network(self):
        with patch('gensia.providers._LOCAL_OPENER.open') as transport:
            for model, endpoint in [('test', 'https://example.com'), ('test', 'http://localhost/a'),
                                    (None, 'http://localhost'), ('a b', 'http://localhost')]:
                with self.subTest(model=model), self.assertRaises((ValueError, ProviderError)):
                    probe(model, endpoint, approve=True)
            transport.assert_not_called()

    def test_repeat_timings_and_no_content_disclosure(self):
        with patch('gensia.model_probe.OllamaProvider.reply', return_value='PRIVATE_RESPONSE'), patch(
                'gensia.model_probe.perf_counter', side_effect=[1, 1.125, 2, 2.25, 3, 3.5]):
            report = probe('PRIVATE_MODEL', approve=True, repeats=3)
        self.assertTrue(report['passed'])
        self.assertEqual([s['elapsed_ms'] for s in report['samples']], [125, 250, 500])
        self.assertNotIn('PRIVATE', json.dumps(report))
        self.assertFalse(report['quality_validated'])
        self.assertFalse(report['hardware_memory_measured'])

    def test_partial_failure_stops_without_retry_or_false_pass(self):
        with patch('gensia.model_probe.OllamaProvider.reply', side_effect=[
                'ok', ProviderError('connection_failed'), 'never']) as reply:
            report = probe('test', approve=True, repeats=3)
        self.assertFalse(report['passed'])
        self.assertEqual(len(report['samples']), 1)
        self.assertEqual(report['attempts'], 2)
        self.assertEqual(reply.call_count, 2)
        self.assertEqual(report['error'], 'connection_failed')

    def test_untrusted_error_is_not_reflected(self):
        for exc in [ProviderUnavailable('SECRET'), OSError('SECRET'), ValueError('SECRET')]:
            with self.subTest(exc=type(exc)), patch('gensia.model_probe.OllamaProvider.reply', side_effect=exc):
                report = probe('test', approve=True)
            self.assertFalse(report['passed'])
            self.assertNotIn('SECRET', json.dumps(report))

    def test_interruption_is_partial_and_sanitized(self):
        with patch('gensia.model_probe.OllamaProvider.reply', side_effect=KeyboardInterrupt):
            report = probe('test', approve=True)
        self.assertTrue(report['interrupted'])
        self.assertFalse(report['passed'])
        self.assertEqual(report['samples'], [])

    def test_cli_without_approval_never_contacts_daemon(self):
        output = io.StringIO()
        with redirect_stdout(output), patch('gensia.model_probe.OllamaProvider') as provider:
            code = main(['--model', 'test'])
        self.assertEqual(code, 2)
        provider.assert_not_called()
        self.assertFalse(json.loads(output.getvalue())['passed'])

    def test_invalid_reply_or_clock_never_passes(self):
        for response, elapsed in [('', 1), (None, 1), ('ok', -1), ('ok', float('nan'))]:
            with self.subTest(response=response, elapsed=elapsed), patch(
                    'gensia.model_probe.OllamaProvider.reply', return_value=response), patch(
                    'gensia.model_probe.perf_counter', side_effect=[0, elapsed]):
                report = probe('test', approve=True)
            self.assertFalse(report['passed'])
            self.assertEqual(report['samples'], [])
            self.assertEqual(report['error'], 'invalid_response')

    def test_cli_success_failure_and_interrupt_exit_codes(self):
        for effect, expected in [('ok', 0), (ProviderError('cloud_model_blocked'), 12), (KeyboardInterrupt(), 130)]:
            output = io.StringIO()
            with redirect_stdout(output), patch('gensia.model_probe.OllamaProvider.reply') as reply:
                if isinstance(effect, BaseException):
                    reply.side_effect = effect
                else:
                    reply.return_value = effect
                code = main(['--model', 'test', '--approve'])
            self.assertEqual(code, expected)
            self.assertEqual(json.loads(output.getvalue())['passed'], expected == 0)

    def test_real_http_uses_only_show_and_fixed_chat_and_blocks_cloud(self):
        requests = []
        cloud = [False]

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append((self.path, body))
                data = ({'details': {'format': 'gguf'}, 'model_info': {'general.architecture': 'test'}}
                        if self.path == '/api/show' else {'done': True, 'message': {'content': 'SECRET_REPLY'}})
                if cloud[0]:
                    data['remote_host'] = 'https://cloud.example'
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            endpoint = f'http://127.0.0.1:{server.server_port}'
            report = probe('test', endpoint, approve=True)
            self.assertTrue(report['passed'])
            self.assertNotIn('SECRET_REPLY', json.dumps(report))
            self.assertEqual([p for p, b in requests], ['/api/show', '/api/chat'])
            self.assertEqual(requests[1][1]['messages'], [{'role': 'user', 'content': PROBE_PROMPT}])
            requests.clear()
            cloud[0] = True
            report = probe('test', endpoint, approve=True, repeats=3)
            self.assertFalse(report['passed'])
            self.assertEqual(report['error'], 'cloud_model_blocked')
            self.assertEqual([p for p, b in requests], ['/api/show'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
