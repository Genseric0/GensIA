from pathlib import Path
import tempfile
import unittest

from gensia.documents import DocumentError, DocumentPermissionError
from gensia.search import LocalDocumentSearch, _tokens
from gensia.tools import AuditLogger


class RecordingProvider:
    def __init__(self, answer="Resposta [fonte 1]."):
        self.answer = answer
        self.prompt = None
        self.calls = 0

    def reply(self, prompt):
        self.prompt = prompt
        self.calls += 1
        return self.answer

    def status(self):
        return {"provider": "test-local", "local_only": True}


class SearchTests(unittest.TestCase):
    def searcher(self, root):
        return LocalDocumentSearch(root, AuditLogger(Path(root) / "audit.jsonl"))

    def test_tokenization_is_case_and_accent_insensitive(self):
        self.assertEqual(_tokens("Endereços ENDERECOS"), ["enderecos", "enderecos"])

    def test_ranks_relevant_chunks_across_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nat.md").write_text("NAT traduz endereços privados para públicos.", encoding="utf-8")
            (root / "sql.txt").write_text("SELECT consulta dados numa tabela SQL.", encoding="utf-8")
            result = self.searcher(root).search("enderecos NAT", ["sql.txt", "nat.md"])
            self.assertEqual(result["results"][0]["path"], "nat.md")
            self.assertEqual(result["files_scanned"], 2)
            self.assertTrue(result["local_only"])

    def test_returns_line_ranges_and_no_results_without_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "aula.txt").write_text("linha um\nlinha dois", encoding="utf-8")
            found = self.searcher(root).search("dois", ["aula.txt"])
            self.assertEqual(found["results"][0]["location"], {"lines": [1, 2]})
            missing = self.searcher(root).search("roteamento", ["aula.txt"])
            self.assertEqual(missing["results"], [])

    def test_query_file_and_result_limits_are_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            search = self.searcher(directory)
            with self.assertRaisesRegex(DocumentError, "vazia"):
                search.search(" ", ["x.txt"])
            with self.assertRaisesRegex(DocumentError, "500"):
                search.search("x" * 501, ["x.txt"])
            with self.assertRaisesRegex(DocumentError, "1 e 10"):
                search.search("nat", [])
            with self.assertRaisesRegex(DocumentError, "top-k"):
                search.search("nat", ["x.txt"], top_k=21)

    def test_path_confinement_is_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(DocumentPermissionError):
                self.searcher(directory).search("segredo", ["../segredo.txt"])

    def test_answer_sends_only_retrieved_evidence_and_maps_citation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "redes.txt").write_text("NAT traduz endereços privados.", encoding="utf-8")
            (root / "outro.txt").write_text("SEGREDO-IRRELEVANTE sobre culinária.", encoding="utf-8")
            provider = RecordingProvider("NAT traduz endereços [fonte 1].")
            result = self.searcher(root).answer(
                "O que faz NAT?", ["redes.txt", "outro.txt"], provider, top_k=1
            )
            self.assertIn("NAT traduz", provider.prompt)
            self.assertNotIn("SEGREDO-IRRELEVANTE", provider.prompt)
            self.assertEqual(result["cited_sources"], [1])
            self.assertEqual(result["citation_status"], "present")

    def test_answer_flags_missing_and_invalid_source_references(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "aula.txt").write_text("NAT traduz endereços.", encoding="utf-8")
            missing = self.searcher(root).answer(
                "NAT?", ["aula.txt"], RecordingProvider("Traduz endereços."), top_k=1
            )
            self.assertEqual(missing["citation_status"], "missing")
            invalid = self.searcher(root).answer(
                "NAT?", ["aula.txt"], RecordingProvider("Resposta [fonte 9]."), top_k=1
            )
            self.assertEqual(invalid["citation_status"], "invalid")

    def test_answer_skips_provider_when_retrieval_has_no_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "aula.txt").write_text("SQL consulta tabelas.", encoding="utf-8")
            provider = RecordingProvider()
            result = self.searcher(root).answer("roteamento", ["aula.txt"], provider)
            self.assertEqual(provider.calls, 0)
            self.assertEqual(result["answer"], "NÃO ENCONTRADO NOS DOCUMENTOS.")
            self.assertEqual(result["citation_status"], "not_applicable")


if __name__ == "__main__":
    unittest.main()
