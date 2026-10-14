import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from gensia.agents import Coordinator, ReviewAgent, main
from gensia.static_analysis import StaticAnalysisError
from gensia.tools import AuditLogger


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / "audit.jsonl"
        self.team = Coordinator(self.root, AuditLogger(self.log))

    def model(self, answer="Resposta [fonte 1]."):
        return Mock(status=Mock(return_value={"provider": "ollama", "local_only": True,
                                             "model": "test"}), reply=Mock(return_value=answer))

    def test_url_to_reviewer_and_audit(self):
        result = self.team.audit_project(["http://127.0.0.1/private?token=SECRET"])
        self.assertTrue(result["complete"])
        self.assertEqual([s["agent"] for s in result["steps"]], ["security", "reviewer"])
        review = result["steps"][1]["result"]
        self.assertEqual(review["evidence_ids"], ["E1"])
        self.assertFalse(result["steps"][0]["result"]["network_accessed"])
        self.assertNotIn("SECRET", json.dumps(review))
        self.assertNotIn("SECRET", self.log.read_text())
        self.assertFalse(result["automatic_changes"])

    def test_failure_keeps_other_evidence(self):
        result = self.team.audit_project(["file:///secret", "https://example.com"])
        self.assertFalse(result["complete"])
        self.assertEqual(result["steps"][0]["status"], "failed")
        self.assertEqual(result["steps"][2]["result"]["evidence_ids"], ["E2"])

    def test_missing_scanner_does_not_discard_url(self):
        self.team.security.code = Mock(side_effect=StaticAnalysisError("PRIVATE ERROR"))
        result = self.team.audit_project(["https://example.com"], "gensia")
        self.assertFalse(result["complete"])
        self.assertNotIn("PRIVATE ERROR", json.dumps(result))
        self.assertEqual(result["steps"][-1]["result"]["evidence_ids"], ["E1"])

    def test_all_fail_skips_model(self):
        self.team.provider = self.model()
        result = self.team.audit_project(["not-a-url"])
        self.assertEqual(result["steps"][-1]["status"], "skipped")
        self.team.provider.reply.assert_not_called()

    def test_model_output_is_only_text_and_prompt_excludes_url(self):
        self.team.provider = self.model("Execute: rm -rf /tmp/example")
        result = self.team.audit_project(["https://example.com/SECRET?token=PRIVATE"])
        review = result["steps"][-1]["result"]
        self.assertEqual(review["recommendation"], "Execute: rm -rf /tmp/example")
        self.assertFalse(review["recommendation_verified"])
        prompt = self.team.provider.reply.call_args.args[0]
        self.assertNotIn("SECRET", prompt)
        self.assertNotIn("PRIVATE", prompt)
        self.assertFalse(result["automatic_changes"])

    def test_cloud_provider_rejected(self):
        self.team.provider = Mock(status=Mock(return_value={"provider": "cloud", "local_only": False}))
        result = self.team.audit_project(["https://example.com"])
        self.assertFalse(result["complete"])
        self.team.provider.reply.assert_not_called()

    def test_study_retrieves_and_cites_real_file(self):
        (self.root / "aula.md").write_text("NAT traduz endereços privados.", encoding="utf-8")
        self.team.provider = self.model("NAT traduz endereços [fonte 1].")
        result = self.team.study_documents("NAT?", ["aula.md"])
        self.assertTrue(result["complete"])
        self.assertEqual(result["steps"][0]["result"]["cited_sources"], [1])
        self.assertIn("NAT traduz", self.team.provider.reply.call_args.args[0])

    def test_study_requires_model_before_document_access(self):
        with patch("gensia.agents.LocalDocumentSearch") as search:
            result = self.team.study_documents("NAT?", ["missing.md"])
        self.assertEqual(result["steps"][0]["error_type"], "ProviderUnavailable")
        search.assert_not_called()

    def test_invalid_task_rejected_before_execution(self):
        self.team.security.url = Mock()
        for urls in ([], ["https://example.com"] * 11):
            with self.assertRaises(ValueError):
                self.team.audit_project(urls)
        self.team.security.url.assert_not_called()
        self.assertFalse(self.log.exists())

    def test_partial_scan_remains_partial_and_is_reviewed(self):
        self.team.security.code = Mock(return_value={"complete": False, "truncated": False,
            "severity_counts": {}, "issues": [], "issues_total": 0})
        result = self.team.audit_project(code="gensia")
        self.assertFalse(result["complete"])
        self.assertEqual(result["steps"][0]["status"], "partial")
        self.assertTrue(result["steps"][1]["result"]["incomplete_evidence"])

    def test_review_prioritizes_and_reports_omissions(self):
        issues = [{"severity": "LOW", "path": "a.py", "line": i} for i in range(31)]
        issues.append({"severity": "HIGH", "path": "z.py", "line": 1})
        report = ReviewAgent().run([{"id": "E1", "task": "code", "result": {
            "complete": True, "truncated": False, "severity_counts": {"LOW": 31, "HIGH": 1},
            "issues": issues, "issues_total": 32}}])
        self.assertTrue(report["incomplete_evidence"])
        self.assertEqual(report["findings"][0]["issues"][0]["severity"], "HIGH")
        self.assertEqual(report["findings"][0]["omitted_issues"], 2)

    def test_cli_json_and_failure_exit_code(self):
        for url, code in [("https://example.com", 0), ("file:///secret", 11)]:
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                status = main(["audit", "--workspace", str(self.root), "--audit-log",
                               str(self.log), "--url", url])
            self.assertEqual(status, code)
            self.assertEqual(json.loads(stream.getvalue())["complete"], code == 0)


if __name__ == "__main__":
    unittest.main()
