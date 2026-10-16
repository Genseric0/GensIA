"""Opt-in real loopback HTTP checks; no personal data or external requests."""
import http.client
import importlib.util
import os
import secrets
import socket
import threading
import time
import unittest


@unittest.skipUnless(
    os.environ.get('GENSIA_TEST_REAL_HTTP') == '1'
    and importlib.util.find_spec('uvicorn')
    and importlib.util.find_spec('fastapi'),
    'Opt-in: GENSIA_TEST_REAL_HTTP=1 and API dependencies required',
)
class RealHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import uvicorn
        from gensia.api import create_app
        cls.token = secrets.token_hex(32)
        cls.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cls.addClassCleanup(cls.sock.close)
        cls.sock.bind(('127.0.0.1', 0))
        cls.sock.listen(16)
        cls.port = cls.sock.getsockname()[1]
        config = uvicorn.Config(create_app(cls.token, cls.port),
                                host='127.0.0.1', port=cls.port,
                                proxy_headers=False, access_log=False,
                                server_header=False, log_level='critical',
                                timeout_graceful_shutdown=2)
        cls.server = uvicorn.Server(config)
        cls.thread = threading.Thread(target=cls.server.run,
                                      kwargs={'sockets': [cls.sock]}, daemon=True)
        cls.addClassCleanup(cls.stop_server)
        cls.thread.start()
        deadline = time.monotonic() + 5
        while not cls.server.started and cls.thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.02)
        if not cls.server.started:
            raise RuntimeError('Loopback test server did not start within 5 seconds')

    @classmethod
    def stop_server(cls):
        cls.server.should_exit = True
        cls.thread.join(timeout=5)
        if cls.thread.is_alive():
            raise RuntimeError('Loopback test server did not stop within 5 seconds')

    def request(self, path='/agents/report', method='GET', headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        try:
            # Explicit headers permit duplicate-header regression cases.
            connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            for name, value in (headers if headers is not None else self.headers()):
                connection.putheader(name, value)
            connection.endheaders()
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode('utf-8')
        finally:
            connection.close()

    def headers(self):
        return [('Host', f'127.0.0.1:{self.port}'), ('Authorization', f'Bearer {self.token}')]

    def test_real_html_export(self):
        from gensia.catalog_report import render_report
        status, headers, body = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(body, render_report())
        headers = {key.lower(): value for key, value in headers.items()}
        self.assertEqual(headers['cache-control'], 'no-store')
        self.assertIn('attachment;', headers['content-disposition'])
        self.assertIn("frame-ancestors 'none'", headers['content-security-policy'])
        self.assertNotIn(self.token, body)

    def test_real_diagnostics_protection_report(self):
        import json
        status, headers, body = self.request('/diagnostics')
        self.assertEqual(status, 200)
        report = json.loads(body)['document_protections']
        self.assertEqual(report['schema_version'], 1)
        self.assertFalse(report['commercial_approval'])
        self.assertFalse(report['limits_changed'])
        self.assertNotIn(self.token, body)
        self.assertEqual(self.request('/diagnostics', headers=self.headers()[:1])[0], 401)

    def test_real_public_panel_assets_without_credential_or_data(self):
        from gensia.panel import ASSETS, panel_asset
        for route in ASSETS:
            status, headers, body = self.request(route, headers=self.headers()[:1])
            self.assertEqual(status, 200)
            self.assertEqual(body, panel_asset(route)[0])
            self.assertNotIn(self.token, body)
            self.assertNotIn('Set-Cookie', headers)
        self.assertEqual(self.request('/panel?token=PRIVATE', headers=self.headers()[:1])[0], 400)

    def test_real_panel_origin_exception_and_duplicate_fetch_metadata(self):
        origin = ('Origin', f'http://127.0.0.1:{self.port}')
        self.assertEqual(self.request('/diagnostics', headers=self.headers() + [origin])[0], 200)
        self.assertEqual(self.request('/diagnostics', headers=self.headers()[:1] + [origin])[0], 401)
        self.assertEqual(self.request('/diagnostics', headers=self.headers() + [origin, origin])[0], 403)
        self.assertEqual(self.request('/status', headers=self.headers() + [origin])[0], 403)
        duplicate = [('Sec-Fetch-Site', 'same-origin'), ('Sec-Fetch-Site', 'same-origin')]
        self.assertEqual(self.request('/panel', headers=self.headers()[:1] + duplicate)[0], 403)

    def test_missing_and_duplicate_authorization(self):
        self.assertEqual(self.request(headers=self.headers()[:1])[0], 401)
        self.assertEqual(self.request(headers=self.headers() + self.headers()[1:])[0], 401)

    def test_host_and_origin(self):
        wrong_host = [('Host', 'localhost:' + str(self.port)), self.headers()[1]]
        self.assertEqual(self.request(headers=wrong_host)[0], 400)
        # Uvicorn may itself reject duplicate Host before the application guard.
        self.assertEqual(self.request(headers=self.headers() + self.headers()[:1])[0], 400)
        self.assertEqual(self.request(headers=self.headers() + [('Origin', 'null')])[0], 403)

    def test_read_only_and_query_rejection(self):
        self.assertEqual(self.request(method='POST')[0], 405)
        self.assertEqual(self.request(path='/agents/report?token=not-a-secret')[0], 400)
        self.assertEqual(self.request(path='/agents/run')[0], 404)
