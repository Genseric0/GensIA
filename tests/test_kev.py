import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError, URLError

from gensia.kev import CisaKevCatalog, KevError
from gensia.tools import AuditLogger


def catalog_bytes(cve="CVE-2021-44228"):
    return json.dumps({
        "title": "CISA Catalog of Known Exploited Vulnerabilities",
        "catalogVersion": "2026.10.14",
        "dateReleased": "2026-10-14T00:00:00Z",
        "count": 1,
        "vulnerabilities": [{
            "cveID": cve,
            "vendorProject": "Apache",
            "product": "Log4j2",
            "vulnerabilityName": "Apache Log4j2 Remote Code Execution Vulnerability",
            "dateAdded": "2021-12-10",
            "shortDescription": "A crafted request can lead to remote code execution.",
            "requiredAction": "Apply mitigations per vendor instructions.",
            "dueDate": "2021-12-24",
            "knownRansomwareCampaignUse": "Known",
            "notes": "https://www.cisa.gov/",
        }],
    }).encode("utf-8")


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit):
        return self.payload


class KevTests(unittest.TestCase):
    def service(self, directory, opener=None):
        return CisaKevCatalog(
            AuditLogger(Path(directory) / "audit.jsonl"), opener=opener
        )

    def test_update_requires_approval_before_network_or_cache_creation(self):
        called = []
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "data" / "kev.json"
            service = self.service(directory, lambda *args, **kwargs: called.append(args))
            with self.assertRaisesRegex(KevError, "approve-external"):
                service.update(cache)
            self.assertFalse(cache.exists())
        self.assertEqual(called, [])

    def test_update_uses_fixed_official_get_and_lookup_is_local(self):
        observed = {}

        def opener(request, timeout):
            observed["url"] = request.full_url
            observed["method"] = request.get_method()
            observed["timeout"] = timeout
            return FakeResponse(catalog_bytes())

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "kev.json"
            service = self.service(directory, opener)
            update = service.update(cache, approved=True, timeout=12)
            result = service.check("cve-2021-44228", cache)
            audit = Path(directory, "audit.jsonl").read_text(encoding="utf-8")
        self.assertEqual(observed["url"], CisaKevCatalog.FEED_URL)
        self.assertEqual(observed["method"], "GET")
        self.assertEqual(observed["timeout"], 12)
        self.assertEqual(update["entries"], 1)
        self.assertTrue(result["in_kev"])
        self.assertFalse(result["network_accessed"])
        self.assertEqual(result["entry"]["vendorProject"], "Apache")
        self.assertNotIn("CVE-2021-44228", audit)

    def test_identical_catalog_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "kev.json"
            service = self.service(directory, lambda *args, **kwargs: FakeResponse(catalog_bytes()))
            self.assertTrue(service.update(cache, approved=True)["cache_changed"])
            self.assertFalse(service.update(cache, approved=True)["cache_changed"])

    def test_invalid_download_preserves_previous_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "kev.json"
            cache.write_bytes(catalog_bytes())
            before = cache.read_bytes()
            service = self.service(directory, lambda *args, **kwargs: FakeResponse(b"not-json"))
            with self.assertRaises(KevError):
                service.update(cache, approved=True)
            self.assertEqual(cache.read_bytes(), before)

    def test_count_mismatch_and_duplicate_cves_are_rejected(self):
        mismatch = json.loads(catalog_bytes())
        mismatch["count"] = 2
        duplicate = json.loads(catalog_bytes())
        duplicate["vulnerabilities"].append(dict(duplicate["vulnerabilities"][0]))
        duplicate["count"] = 2
        with tempfile.TemporaryDirectory() as directory:
            for document in (mismatch, duplicate):
                with self.subTest(document=document):
                    payload = json.dumps(document).encode()
                    service = self.service(directory, lambda *args, p=payload, **kwargs: FakeResponse(p))
                    with self.assertRaises(KevError):
                        service.update(Path(directory) / "new.json", approved=True)

    def test_invalid_cve_and_missing_cache_fail_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self.service(directory, lambda *_args, **_kwargs: self.fail("network used"))
            with self.assertRaises(KevError):
                service.check("2021-44228", Path(directory) / "missing.json")
            with self.assertRaisesRegex(KevError, "kev-update"):
                service.check("CVE-2021-44228", Path(directory) / "missing.json")

    def test_cache_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / "real.json"
            real.write_bytes(catalog_bytes())
            link = root / "link.json"
            link.symlink_to(real)
            with self.assertRaisesRegex(KevError, "link simbólico"):
                self.service(directory).check("CVE-2021-44228", link)

    def test_large_network_and_http_failures_are_sanitized(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "kev.json"
            openers = (
                lambda *args, **kwargs: FakeResponse(b"x" * (CisaKevCatalog.MAX_BYTES + 1)),
                lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("secret")),
                lambda request, **_kwargs: (_ for _ in ()).throw(
                    HTTPError(request.full_url, 503, "secret", {}, None)
                ),
            )
            for opener in openers:
                with self.subTest(opener=opener):
                    with self.assertRaises(KevError) as caught:
                        self.service(directory, opener).update(cache, approved=True)
                    self.assertNotIn("secret", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
