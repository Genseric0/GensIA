import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from gensia.core import Assistant
from gensia.providers import OllamaProvider, ProviderUnavailable
from gensia.tools import AppLauncher, AuditLogger, SafeDirectoryTools, ToolError, ToolPermissionError

ROOT = Path(__file__).resolve().parents[1]


def run(*args, input=None):
    return subprocess.run([sys.executable, "-m", "gensia", *args], cwd=ROOT,
                          input=input, text=True, capture_output=True, timeout=5)


class CliTests(unittest.TestCase):
    def test_status_is_honest(self):
        p = run("status")
        self.assertEqual(p.returncode, 0)
        data = json.loads(p.stdout)
        for key in ("network_enabled", "persistent_memory", "voice_enabled"):
            self.assertFalse(data[key])
        self.assertTrue(data["system_tools_enabled"])
        self.assertEqual(data["system_tools_mode"], "explicit_cli_only")
        self.assertIn("tts_enabled", data)
        self.assertEqual(data["tts_mode"], "explicit_wav_file_only")
        self.assertIn("microphone_enabled", data)
        self.assertEqual(data["microphone_mode"], "explicit_fixed_duration_only")
        self.assertTrue(data["documents_available"])
        self.assertEqual(data["documents_mode"], "explicit_local_text_only")
        self.assertTrue(data["url_reputation_available"])
        self.assertEqual(data["url_reputation_mode"], "explicit_virustotal_lookup_only")
        self.assertTrue(data["cisa_kev_available"])
        self.assertEqual(data["cisa_kev_mode"], "explicit_update_local_lookup")
        self.assertTrue(data["bandit_scan_available"])
        self.assertEqual(data["bandit_scan_mode"], "explicit_local_read_only")
        self.assertIsNone(data["model"])
        self.assertEqual(data["provider"], "not_configured")

    def test_question_reports_missing_provider(self):
        p = run("ask", "Explica NAT")
        self.assertEqual(p.returncode, 3)
        self.assertIn("Nenhuma tarefa foi executada", p.stderr)

    def test_interactive_help_and_exit(self):
        p = run("chat", input="/ajuda\n/estado\n/sair\n")
        self.assertEqual(p.returncode, 0)
        self.assertIn("terminal pronto", p.stdout)
        self.assertIn("Até breve", p.stdout)

    def test_eof_exits_cleanly(self):
        self.assertEqual(run("chat", input="").returncode, 0)

    def test_bad_command(self):
        self.assertEqual(run("ask", "/nao-existe").returncode, 2)

    def test_blank_input(self):
        self.assertEqual(run("ask", "   ").returncode, 2)

    def test_large_input(self):
        self.assertEqual(run("ask", "a" * 16001).returncode, 2)

    def test_doctor(self):
        self.assertTrue(json.loads(run("doctor").stdout)["python_supported"])

    def test_provider_receives_text_without_shell_interpretation(self):
        class RecordingProvider:
            def reply(self, text):
                self.received = text
                return "resposta de teste"
            def status(self):
                return {"provider": "test", "model": "test", "local_only": True}
        provider = RecordingProvider()
        assistant = Assistant(provider)
        payload = "echo teste; $(whoami)"
        self.assertEqual(assistant.handle(payload).text, "resposta de teste")
        self.assertEqual(provider.received, payload)

    def test_remote_ollama_endpoint_is_rejected(self):
        with self.assertRaises(ValueError):
            OllamaProvider("modelo", "https://example.com")

    @patch("gensia.providers._LOCAL_OPENER.open")
    def test_ollama_chat_payload_and_response(self, mocked):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return b'{"message":{"content":" Ola local "}}'
        mocked.return_value = Response()
        provider = OllamaProvider("llama-teste")
        self.assertEqual(provider.reply("Explica NAT"), "Ola local")
        request = mocked.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(body["model"], "llama-teste")
        self.assertFalse(body["stream"])
        self.assertEqual(body["messages"][0]["content"], "Explica NAT")

    @patch("gensia.providers._LOCAL_OPENER.open")
    def test_list_installed_models(self, mocked):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return b'{"models":[{"name":"a"},{"name":"b"}]}'
        mocked.return_value = Response()
        self.assertEqual(OllamaProvider().list_models(), ["a", "b"])

    @patch("gensia.providers._LOCAL_OPENER.open")
    def test_invalid_json_is_reported(self, mocked):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return b'not-json'
        mocked.return_value = Response()
        with self.assertRaises(ProviderUnavailable):
            OllamaProvider("modelo").reply("ola")

    def test_ollama_chat_requires_model(self):
        with self.assertRaises(ProviderUnavailable):
            OllamaProvider().reply("ola")

    def test_cli_ollama_requires_model(self):
        p = run("--provider", "ollama", "ask", "ola")
        self.assertEqual(p.returncode, 2)
        self.assertIn("--model", p.stderr)

    def test_directory_listing_stays_in_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.txt").write_text("abc", encoding="utf-8")
            (root / "pasta").mkdir()
            audit = AuditLogger(root / "audit.jsonl")
            result = SafeDirectoryTools(root, audit).list_directory(".")
            names = {entry["name"] for entry in result["entries"]}
            self.assertIn("a.txt", names)
            self.assertIn("pasta", names)

    def test_directory_traversal_is_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = SafeDirectoryTools(root, AuditLogger(root / "audit.jsonl"))
            with self.assertRaises(ToolPermissionError):
                tools.list_directory("..")

    def test_truncated_flag_only_when_items_are_omitted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.txt").write_text("a", encoding="utf-8")
            audit = AuditLogger(root / "audit.jsonl")
            tools = SafeDirectoryTools(root, audit)
            self.assertFalse(tools.list_directory(".", limit=1)["truncated"])
            (root / "b.txt").write_text("b", encoding="utf-8")
            self.assertTrue(tools.list_directory(".", limit=1)["truncated"])

    def test_audit_does_not_store_path(self):
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "audit.jsonl"
            secret_path = "Documentos/cliente-secreto"
            AuditLogger(audit_path).record("list_directory", "success", secret_path)
            content = audit_path.read_text(encoding="utf-8")
            self.assertNotIn(secret_path, content)
            self.assertIn("target_fingerprint", content)

    def test_app_requires_explicit_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            launcher = AppLauncher(AuditLogger(Path(directory) / "audit.jsonl"), "win32")
            with self.assertRaises(ToolPermissionError):
                launcher.open("calculator", approved=False)

    def test_allowed_app_uses_argument_list_without_shell(self):
        calls = []
        def runner(command, **kwargs):
            calls.append((command, kwargs))
        with tempfile.TemporaryDirectory() as directory:
            launcher = AppLauncher(AuditLogger(Path(directory) / "audit.jsonl"), "win32", runner)
            with patch('gensia.tools._windows_directory', return_value=r'C:\Windows\System32'):
                launcher.open("notepad", approved=True)
        self.assertEqual(calls[0][0], [r"C:\Windows\System32\notepad.exe"])
        self.assertFalse(calls[0][1]["shell"])

    def test_unknown_app_is_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            launcher = AppLauncher(AuditLogger(Path(directory) / "audit.jsonl"), "win32")
            with self.assertRaises(ToolPermissionError):
                launcher.open("powershell", approved=True)

    def test_cli_lists_authorized_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "teste.txt").write_text("ok", encoding="utf-8")
            audit = root / "events.jsonl"
            p = run("tool", "--audit", str(audit), "list", "--workspace", str(root), ".")
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(json.loads(p.stdout)["entries"][0]["name"], "teste.txt")

    def test_cli_tts_reports_missing_voice(self):
        p = run(
            "voice", "synthesize", "Olá",
            "--voice", "nao-existe.onnx", "--output", "fala.wav",
        )
        self.assertEqual(p.returncode, 7)
        self.assertIn(".onnx", p.stderr)

    def test_cli_microphone_rejects_unbounded_duration(self):
        p = run("voice", "record", "--output", "fala.wav", "--duration", "61")
        self.assertEqual(p.returncode, 7)
        self.assertIn("60 segundos", p.stderr)

    def test_cli_reads_authorized_text_document(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "aula.md").write_text("# Redes\nNAT traduz endereços.", encoding="utf-8")
            p = run(
                "document", "--workspace", str(root), "--audit", str(root / "audit.jsonl"),
                "read", "aula.md",
            )
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("NAT traduz", json.loads(p.stdout)["content"])

    def test_cli_document_summary_requires_local_model(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "aula.txt").write_text("conteúdo", encoding="utf-8")
            audit = Path(directory) / "audit.jsonl"
            p = run(
                "document", "--workspace", directory,
                "--audit", str(audit),
                "summarize", "aula.txt",
            )
            self.assertEqual(p.returncode, 3)
            self.assertIn("Modelo não configurado", p.stderr)
            self.assertFalse(audit.exists())

    def test_cli_pdf_question_requires_local_model_before_reading(self):
        with tempfile.TemporaryDirectory() as directory:
            audit = Path(directory) / "audit.jsonl"
            p = run(
                "document", "--workspace", directory, "--audit", str(audit),
                "pdf-ask", "nao-existe.pdf", "O que é NAT?",
            )
            self.assertEqual(p.returncode, 3)
            self.assertIn("Modelo não configurado", p.stderr)
            self.assertFalse(audit.exists())

    def test_cli_searches_multiple_text_documents_without_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "redes.md").write_text("NAT traduz endereços privados.", encoding="utf-8")
            (root / "sql.txt").write_text("SELECT lê linhas da base de dados.", encoding="utf-8")
            p = run(
                "document", "--workspace", directory, "--audit", str(root / "audit.jsonl"),
                "search", "enderecos NAT", "sql.txt", "redes.md", "--top-k", "1",
            )
            self.assertEqual(p.returncode, 0, p.stderr)
            data = json.loads(p.stdout)
            self.assertEqual(data["results"][0]["path"], "redes.md")
            self.assertTrue(data["local_only"])

    def test_cli_grounded_answer_requires_model_before_reading(self):
        with tempfile.TemporaryDirectory() as directory:
            audit = Path(directory) / "audit.jsonl"
            p = run(
                "document", "--workspace", directory, "--audit", str(audit),
                "ask-search", "O que é NAT?", "nao-existe.txt",
            )
            self.assertEqual(p.returncode, 3)
            self.assertIn("Modelo não configurado", p.stderr)
            self.assertFalse(audit.exists())

    def test_cli_analyzes_url_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            audit = Path(directory) / "audit.jsonl"
            p = run("security", "--audit", str(audit), "url", "https://example.com/login")
            self.assertEqual(p.returncode, 0, p.stderr)
            data = json.loads(p.stdout)
            self.assertFalse(data["network_accessed"])
            self.assertEqual(data["hostname"], "example.com")

    def test_cli_reputation_requires_explicit_external_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            audit = Path(directory) / "audit.jsonl"
            p = run(
                "security", "--audit", str(audit), "url-reputation",
                "https://example.com/login",
            )
            self.assertEqual(p.returncode, 9)
            self.assertIn("approve-external", p.stderr)

    def test_cli_kev_update_requires_explicit_external_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "kev.json"
            p = run(
                "security", "--audit", str(Path(directory) / "audit.jsonl"),
                "kev-update", "--cache", str(cache),
            )
            self.assertEqual(p.returncode, 9)
            self.assertIn("approve-external", p.stderr)
            self.assertFalse(cache.exists())


if __name__ == "__main__":
    unittest.main()
