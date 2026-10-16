import importlib.util
import unittest
from unittest.mock import patch

from gensia.api import create_app
from gensia.panel import ASSETS, panel_asset


@unittest.skipUnless(importlib.util.find_spec('fastapi') and importlib.util.find_spec('httpx'),
                     'Optional API dependencies required')
class PanelTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        self.token = 'a' * 64
        self.client = TestClient(create_app(self.token), base_url='http://127.0.0.1:8765')
        self.addCleanup(self.client.close)
        self.auth = {'Authorization': 'Bearer ' + self.token}
        self.origin = 'http://127.0.0.1:8765'

    def test_only_static_shell_assets_are_public_and_no_token_is_embedded(self):
        for route in ASSETS:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.text, panel_asset(route)[0])
                self.assertNotIn(self.token, response.text)
                self.assertEqual(response.headers['cache-control'], 'no-store')
                self.assertEqual(response.headers['cross-origin-resource-policy'], 'same-origin')
                self.assertNotIn('set-cookie', response.headers)
                self.assertNotIn('unsafe-inline', response.headers['content-security-policy'])
                self.assertIn("connect-src 'self'", response.headers['content-security-policy'])
                self.assertNotIn('access-control-allow-origin', response.headers)
        self.assertEqual(self.client.get('/diagnostics').status_code, 401)
        self.assertEqual(self.client.get('/status').status_code, 401)

    def test_public_assets_keep_host_method_query_and_origin_guards(self):
        for route in ASSETS:
            self.assertEqual(self.client.get(route, headers={'Host': 'localhost:8765'}).status_code, 400)
            self.assertEqual(self.client.get(route + '?token=SECRET').status_code, 400)
            for method in ('POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'):
                self.assertEqual(self.client.request(method, route).status_code, 405)
            self.assertEqual(self.client.get(route, headers={'Origin': 'https://evil.example'}).status_code, 403)

    def test_exact_origin_exception_is_only_for_authenticated_get_diagnostics(self):
        headers = {**self.auth, 'Origin': self.origin}
        self.assertEqual(self.client.get('/diagnostics', headers=headers).status_code, 200)
        self.assertEqual(self.client.get('/diagnostics', headers={'Origin': self.origin}).status_code, 401)
        for origin in ('null', 'http://localhost:8765', 'http://127.0.0.1:8766', 'https://127.0.0.1:8765', self.origin + '/'):
            self.assertEqual(self.client.get('/diagnostics', headers={**self.auth, 'Origin': origin}).status_code, 403)
        for route in ('/health', '/status', '/agents', '/agents/report'):
            self.assertEqual(self.client.get(route, headers=headers).status_code, 403)
        duplicate = [('Authorization', self.auth['Authorization']), ('Origin', self.origin), ('Origin', self.origin)]
        self.assertEqual(self.client.get('/diagnostics', headers=duplicate).status_code, 403)

    def test_fetch_metadata_cross_site_and_same_site_are_refused(self):
        for route in ('/panel', '/panel.js', '/panel.css', '/diagnostics'):
            for site in ('cross-site', 'same-site', 'invalid'):
                self.assertEqual(self.client.get(route, headers={**self.auth, 'Sec-Fetch-Site': site}).status_code, 403)
        for site in ('same-origin', 'none'):
            self.assertEqual(self.client.get('/panel', headers={'Sec-Fetch-Site': site}).status_code, 200)

    def test_diagnostics_is_not_run_for_shell_or_unauthorized_requests(self):
        with patch('gensia.api.diagnostics', return_value={'sentinel': True}) as diagnose:
            for route in ASSETS:
                self.client.get(route)
            self.client.get('/diagnostics')
            self.client.get('/diagnostics', headers={**self.auth, 'Origin': 'null'})
            diagnose.assert_not_called()
            self.assertEqual(self.client.get('/diagnostics', headers=self.auth).json(), {'sentinel': True})
            diagnose.assert_called_once()

    def test_unknown_asset_paths_and_data_csp_remain_restricted(self):
        for route in ('/panel/', '/panel/secret', '/web/panel.html', '/panel.js/map'):
            self.assertEqual(self.client.get(route, headers=self.auth).status_code, 404)
        response = self.client.get('/diagnostics', headers={**self.auth, 'Origin': self.origin})
        self.assertEqual(response.headers['content-security-policy'], "default-src 'none'; frame-ancestors 'none'")
        self.assertNotIn('access-control-allow-origin', response.headers)
        self.assertNotIn('set-cookie', response.headers)
