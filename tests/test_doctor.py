from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.metadata
import io
import json
import threading
import unittest
from unittest.mock import patch

from gensia.doctor import _bandit_check, diagnose, main
from gensia.providers import ProviderUnavailable


AVAILABLE = {"state": "available", "version": "1.9.4", "execution_validated": False}


class DoctorTests(unittest.TestCase):
    def test_dependencies_present_are_not_claimed_as_executed(self):
        with patch("gensia.doctor._bandit_check", return_value=AVAILABLE), patch(
                "gensia.doctor.OllamaProvider.list_models", return_value=["test:small"]):
            report = diagnose("test:small")
        self.assertTrue(report["preflight_passed"])
        self.assertFalse(report["checks"]["model"]["inference_validated"])
        self.assertFalse(report["checks"]["bandit"]["execution_validated"])

    def test_missing_model_and_no_inventory_disclosure(self):
        with patch("gensia.doctor._bandit_check", return_value=AVAILABLE), patch(
                "gensia.doctor.OllamaProvider.list_models", return_value=["PRIVATE_MODEL:latest"]):
            report = diagnose("absent:latest")
        self.assertFalse(report["preflight_passed"])
        self.assertEqual(report["checks"]["model"]["state"], "missing")
        self.assertNotIn("PRIVATE_MODEL", json.dumps(report))

    def test_no_implicit_model_choice(self):
        with patch("gensia.doctor.OllamaProvider.list_models", return_value=["test:small"]):
            report = diagnose()
        self.assertEqual(report["checks"]["model"]["state"], "not_selected")
        self.assertFalse(report["preflight_passed"])

    def test_service_error_is_sanitized_and_model_not_misreported_missing(self):
        with patch("gensia.doctor.OllamaProvider.list_models", side_effect=ProviderUnavailable("SECRET")):
            report = diagnose("test:small")
        self.assertEqual(report["checks"]["ollama"]["state"], "unavailable_or_invalid")
        self.assertEqual(report["checks"]["model"]["state"], "not_checked")
        self.assertNotIn("SECRET", json.dumps(report))

    def test_missing_bandit_does_not_prevent_ollama_check(self):
        with patch("gensia.doctor._bandit_check", return_value={"state": "missing"}), patch(
                "gensia.doctor.OllamaProvider.list_models", return_value=["test:small"]):
            report = diagnose("test:small")
        self.assertFalse(report["preflight_passed"])
        self.assertEqual(report["checks"]["model"]["state"], "listed")

    def test_bandit_metadata_and_module_are_both_checked(self):
        with patch("gensia.doctor.importlib.metadata.version", return_value="1.9.4"), patch(
                "gensia.doctor.importlib.util.find_spec", return_value=None):
            self.assertEqual(_bandit_check()["state"], "unavailable")
        with patch("gensia.doctor.importlib.metadata.version", side_effect=importlib.metadata.PackageNotFoundError):
            self.assertEqual(_bandit_check()["state"], "missing")

    def test_invalid_arguments_fail_before_any_probe(self):
        cases = [{"model": ""}, {"model": "a\nb"}, {"model": "a" * 201},
                 {"timeout": float("nan")}, {"timeout": float("inf")}, {"timeout": 0},
                 {"endpoint": "https://example.com"}, {"endpoint": "http://127.0.0.1/other"},
                 {"endpoint": "http://127.0.0.1:0"}, {"endpoint": "http://127.0.0.1:99999"}]
        with patch("gensia.doctor._bandit_check") as bandit, patch(
                "gensia.doctor.OllamaProvider.list_models") as models:
            for case in cases:
                with self.subTest(case=case), self.assertRaises(ValueError):
                    diagnose(**case)
        bandit.assert_not_called()
        models.assert_not_called()

    def test_exact_tag_matching(self):
        with patch("gensia.doctor.OllamaProvider.list_models", return_value=["test:latest"]):
            report = diagnose("test")
        self.assertEqual(report["checks"]["model"]["state"], "missing")

    def test_cli_exit_codes(self):
        for model, names, expected in [("test:small", ["test:small"], 0), ("test:small", [], 12), ("", [], 2)]:
            output = io.StringIO()
            with patch("gensia.doctor._bandit_check", return_value=AVAILABLE), patch(
                    "gensia.doctor.OllamaProvider.list_models", return_value=names), redirect_stdout(output):
                code = main(["--model", model])
            self.assertEqual(code, expected)
            self.assertEqual(json.loads(output.getvalue())["preflight_passed"], expected == 0)

    def test_real_http_only_get_tags_without_body(self):
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append((self.command, self.path, self.headers.get("Content-Length")))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"models":[{"name":"test:small"}]}')

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch("gensia.doctor._bandit_check", return_value=AVAILABLE):
                report = diagnose("test:small", f"http://127.0.0.1:{server.server_port}")
            self.assertTrue(report["preflight_passed"])
            self.assertEqual(received, [("GET", "/api/tags", None)])
            self.assertFalse(report["prompts_sent"])
            self.assertFalse(report["downloads_started"])
            self.assertFalse(report["services_started"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
