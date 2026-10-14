import importlib.util
import unittest
from unittest.mock import patch
from gensia.api import create_app, validate_settings, main


class ApiSettingsTests(unittest.TestCase):
    def test_invalid_token_and_port(self):
        for token in ("", "a" * 31, "é" * 32, "a b" * 20, "a" * 257):
            with self.assertRaises(ValueError):
                validate_settings(token, 8765)
        for port in (0, 1023, 65536, True):
            with self.assertRaises(ValueError):
                validate_settings("a" * 32, port)


@unittest.skipUnless(importlib.util.find_spec("fastapi") and importlib.util.find_spec("httpx"),
                     "API opcional: instalar requirements-api.txt e httpx")
class ApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        self.client = TestClient(create_app("a" * 64), base_url="http://127.0.0.1:8765",
                                 headers={"Authorization": "Bearer " + "a" * 64})
        self.addCleanup(self.client.close)

    def test_read_only_endpoints(self):
        for path in ("/health", "/status", "/diagnostics"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertNotIn("access-control-allow-origin", response.headers)
        self.assertFalse(self.client.get("/status").json()["actions_enabled"])

    def test_authentication_required(self):
        for token in ("", "Bearer wrong", "Bearer " + "a" * 63):
            self.assertEqual(self.client.get("/health", headers={"Authorization": token}).status_code, 401)

    def test_host_and_origin_rejected(self):
        for headers in ({"Host": "evil.example"}, {"Host": "localhost:8765"},
                        {"Origin": "https://evil.example"}, {"Origin": "null"}):
            self.assertIn(self.client.get("/status", headers=headers).status_code, (400, 403))

    def test_mutations_docs_queries_absent(self):
        for method in ("POST", "PUT", "DELETE", "PATCH", "OPTIONS"):
            self.assertEqual(self.client.request(method, "/status").status_code, 405)
        for path in ("/docs", "/openapi.json", "/memory", "/tools", "/status/"):
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.get("/status?token=secret").status_code, 400)

    def test_diagnostics_has_only_allowlisted_data(self):
        with patch.dict("os.environ", {"VIRUSTOTAL_API_KEY": "SECRET", "GENSIA_API_TOKEN": "PRIVATE"}):
            response = self.client.get("/diagnostics")
        self.assertEqual(set(response.json()), {"python", "packages", "model_connectivity_tested", "personal_data_accessed"})
        self.assertNotIn("SECRET", response.text)
        self.assertNotIn("PRIVATE", response.text)

    def test_launcher_loopback_and_no_proxy(self):
        with patch.dict("os.environ", {"GENSIA_API_TOKEN": "a" * 64}), patch("uvicorn.run") as run:
            self.assertEqual(main([]), 0)
        self.assertEqual(run.call_args.kwargs["host"], "127.0.0.1")
        self.assertFalse(run.call_args.kwargs["proxy_headers"])
        self.assertFalse(run.call_args.kwargs["access_log"])
