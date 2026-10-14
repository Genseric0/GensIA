from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError, URLError

from gensia.security import PassiveUrlAnalyzer, SecurityError, VirusTotalUrlReputation
from gensia.tools import AuditLogger


class UrlSecurityTests(unittest.TestCase):
    def analyzer(self, root):
        return PassiveUrlAnalyzer(AuditLogger(Path(root) / "audit.jsonl"))

    def test_normalizes_https_without_claiming_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.analyzer(directory).analyze("HTTPS://Example.COM/a?q=1")
            self.assertEqual(result["canonical_url"], "https://example.com/a?q=1")
            self.assertEqual(result["risk_level"], "low")
            self.assertEqual(result["verdict"], "heuristic_review_required")
            self.assertFalse(result["network_accessed"])

    def test_http_userinfo_and_non_default_port_are_flagged_and_credentials_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            url = "http://trusted.example@evil.example:8080/login"
            result = self.analyzer(directory).analyze(url)
            codes = {item["code"] for item in result["findings"]}
            self.assertTrue({"userinfo_present", "unencrypted_http", "non_default_port"} <= codes)
            self.assertEqual(result["risk_level"], "high")
            self.assertNotIn("trusted.example@", result["canonical_url"])
            self.assertNotIn(url, Path(directory, "audit.jsonl").read_text(encoding="utf-8"))

    def test_private_ipv4_and_ipv6_are_high_risk(self):
        with tempfile.TemporaryDirectory() as directory:
            ipv4 = self.analyzer(directory).analyze("http://127.0.0.1/admin")
            self.assertIn("non_public_ip", {item["code"] for item in ipv4["findings"]})
            ipv6 = self.analyzer(directory).analyze("http://[::1]/")
            self.assertEqual(ipv6["canonical_url"], "http://[::1]/")
            self.assertEqual(ipv6["risk_level"], "high")

    def test_punycode_is_visible_and_flagged(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.analyzer(directory).analyze("https://xn--exmple-cua.com/")
            self.assertIn("punycode", {item["code"] for item in result["findings"]})
            self.assertEqual(result["hostname"], "xn--exmple-cua.com")

    def test_rejects_non_http_controls_bad_port_and_bad_hostname(self):
        with tempfile.TemporaryDirectory() as directory:
            analyzer = self.analyzer(directory)
            for url in (
                "file:///etc/passwd", "javascript:alert(1)",
                "https://example.com/%0aX", "https://example.com:99999/",
                "https://bad_host.example/", "https://example.com/%zz",
            ):
                with self.subTest(url=url), self.assertRaises(SecurityError):
                    analyzer.analyze(url)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit):
        return self.payload


class VirusTotalReputationTests(unittest.TestCase):
    def service(self, root, opener, key="test-api-key"):
        return VirusTotalUrlReputation(
            AuditLogger(Path(root) / "audit.jsonl"), key, opener=opener
        )

    def test_requires_explicit_approval_before_network(self):
        called = []
        with tempfile.TemporaryDirectory() as directory:
            service = self.service(directory, lambda *args, **kwargs: called.append(args))
            with self.assertRaisesRegex(SecurityError, "approve-external"):
                service.lookup("https://example.com/path")
        self.assertEqual(called, [])

    def test_requires_environment_key_before_network(self):
        called = []
        with tempfile.TemporaryDirectory() as directory:
            service = self.service(directory, lambda *args, **kwargs: called.append(args), key="")
            with self.assertRaisesRegex(SecurityError, "VIRUSTOTAL_API_KEY"):
                service.lookup("https://example.com/path", approved=True)
        self.assertEqual(called, [])

    def test_refuses_private_local_ambiguous_and_userinfo_urls(self):
        called = []
        with tempfile.TemporaryDirectory() as directory:
            service = self.service(directory, lambda *args, **kwargs: called.append(args))
            values = (
                "http://127.0.0.1/admin",
                "https://printer.local/",
                "https://intranet/",
                "https://name@example.com/",
                "https://127.1/",
            )
            for value in values:
                with self.subTest(value=value), self.assertRaises(SecurityError):
                    service.lookup(value, approved=True)
        self.assertEqual(called, [])

    def test_gets_existing_report_with_unpadded_urlsafe_identifier(self):
        observed = {}
        payload = (
            b'{"data":{"attributes":{"last_analysis_date":0,'
            b'"last_analysis_stats":{"harmless":70,"malicious":2,'
            b'"suspicious":1,"undetected":4,"timeout":0}}}}'
        )

        def opener(request, timeout):
            observed["url"] = request.full_url
            observed["method"] = request.get_method()
            observed["key"] = request.get_header("X-apikey")
            observed["timeout"] = timeout
            return FakeResponse(payload)

        with tempfile.TemporaryDirectory() as directory:
            result = self.service(directory, opener).lookup(
                "HTTPS://Example.COM/path?q=1", approved=True
            )
            audit = Path(directory, "audit.jsonl").read_text(encoding="utf-8")
        self.assertEqual(observed["method"], "GET")
        self.assertEqual(observed["key"], "test-api-key")
        self.assertEqual(observed["timeout"], 15.0)
        self.assertTrue(observed["url"].startswith(
            "https://www.virustotal.com/api/v3/urls/aHR0cHM6Ly9leGFtcGxlLmNvbS9wYXRoP3E9MQ"
        ))
        self.assertNotIn("=", observed["url"].rsplit("/", 1)[1])
        self.assertTrue(result["found"])
        self.assertEqual(result["stats"]["malicious"], 2)
        self.assertEqual(result["interpretation"], "malicious_engines_flagged")
        self.assertEqual(result["last_analysis_at"], "1970-01-01T00:00:00+00:00")
        self.assertFalse(result["submitted_for_analysis"])
        self.assertNotIn("test-api-key", audit)
        self.assertNotIn("example.com", audit)

    def test_404_is_not_found_and_does_not_submit(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 404, "not found", {}, None)

        with tempfile.TemporaryDirectory() as directory:
            result = self.service(directory, opener).lookup(
                "https://example.com/new", approved=True
            )
        self.assertFalse(result["found"])
        self.assertFalse(result["submitted_for_analysis"])
        self.assertIn("não significa", result["interpretation"])

    def test_rejects_invalid_and_oversized_responses(self):
        with tempfile.TemporaryDirectory() as directory:
            for payload in (b"not-json", b"{}", b"x" * (1024 * 1024 + 1)):
                with self.subTest(length=len(payload)):
                    service = self.service(directory, lambda *args, p=payload, **kwargs: FakeResponse(p))
                    with self.assertRaises(SecurityError):
                        service.lookup("https://example.com/", approved=True)

    def test_sanitizes_network_and_http_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            failures = (
                lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("secret endpoint")),
                lambda request, **_kwargs: (_ for _ in ()).throw(
                    HTTPError(request.full_url, 429, "secret body", {}, None)
                ),
            )
            for opener in failures:
                with self.subTest(opener=opener):
                    with self.assertRaises(SecurityError) as caught:
                        self.service(directory, opener).lookup(
                            "https://example.com/", approved=True
                        )
                    self.assertNotIn("secret", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
