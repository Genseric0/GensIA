"""Real loopback HTTP conversation; synthetic provider, never real inference."""
import http.client
import json
import time
import unittest

import test_api_socket


@unittest.skipUnless(not getattr(test_api_socket.RealHttpTests, '__unittest_skip__', False),
                     'Opt-in: GENSIA_TEST_REAL_HTTP=1 and API dependencies required')
class ChatHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import secrets
        import socket
        import threading
        import uvicorn
        from gensia.api import create_app

        class SyntheticProvider:
            calls = 0

            def ensure_local_model(self, model):
                return {'available': True, 'locality': 'confirmed_local'}

            def reply(self, model, prompt):
                self.calls += 1
                return '[TESTE SINTÉTICO] Olá, ação e engenharia.'

        cls.provider = SyntheticProvider()
        cls.token = secrets.token_hex(32)
        cls.sock = socket.socket()
        cls.addClassCleanup(cls.sock.close)
        cls.sock.bind(('127.0.0.1', 0))
        cls.sock.listen(16)
        cls.port = cls.sock.getsockname()[1]
        cls.server = uvicorn.Server(uvicorn.Config(
            create_app(cls.token, cls.port, 'synthetic', cls.provider),
            proxy_headers=False, access_log=False, server_header=False,
            log_level='critical', timeout_graceful_shutdown=2))
        cls.thread = threading.Thread(target=cls.server.run,
                                      kwargs={'sockets': [cls.sock]}, daemon=True)
        cls.addClassCleanup(cls.stop_server)
        cls.thread.start()
        deadline = time.monotonic() + 5
        while not cls.server.started and cls.thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.02)
        if not cls.server.started:
            raise RuntimeError('Synthetic chat HTTP server did not start')

    @classmethod
    def stop_server(cls):
        cls.server.should_exit = True
        cls.thread.join(5)
        if cls.thread.is_alive():
            raise RuntimeError('Synthetic chat HTTP server did not stop')

    def request(self, body, *, authorized=True, chunked=False):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        headers = {'Content-Type': 'application/json',
                   'Origin': f'http://127.0.0.1:{self.port}'}
        if authorized:
            headers['Authorization'] = 'Bearer ' + self.token
        try:
            payload = [body[:100], body[100:]] if chunked else body
            conn.request('POST', '/chat', payload, headers, encode_chunked=chunked)
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), json.loads(response.read())
        finally:
            conn.close()

    def test_unicode_reply_and_follow_up_over_real_socket(self):
        messages = [{'role': 'user', 'content': 'Explica ação e engenharia.'}]
        for _ in range(2):
            status, headers, data = self.request(json.dumps({'messages': messages}, ensure_ascii=False).encode())
            self.assertEqual(status, 200)
            self.assertIn('ação', data['reply'])
            self.assertFalse(data['actions_executed'])
            self.assertFalse(data['cloud_fallback'])
            self.assertEqual(headers['cache-control'], 'no-store')
            messages += [{'role': 'assistant', 'content': data['reply']},
                         {'role': 'user', 'content': 'Dá um exemplo.'}]

    def test_unauthorized_request_never_generates(self):
        before = self.provider.calls
        status, _, data = self.request(b'{"messages":[]}', authorized=False)
        self.assertEqual((status, data['error']), (401, 'unauthorized'))
        self.assertEqual(self.provider.calls, before)

    def test_chunked_body_limit_never_generates(self):
        before = self.provider.calls
        status, _, data = self.request(b' ' * 32769, chunked=True)
        self.assertEqual((status, data['error']), (413, 'request_too_large'))
        self.assertEqual(self.provider.calls, before)
