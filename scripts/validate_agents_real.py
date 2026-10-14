"""Opt-in integration checks with real Bandit and an already running Ollama.

Run from the repository root: python scripts/validate_agents_real.py --model NAME
Does not install dependencies, pull models, execute fixtures, or start services.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gensia import __version__
from gensia.agents import Coordinator
from gensia.providers import OllamaProvider
from gensia.tools import AuditLogger


def validate(model, endpoint):
    provider = OllamaProvider(model, endpoint, timeout=180)
    models = provider._request("/api/tags", method="GET")["models"]
    installed = next((m for m in models if m.get("name") == model), None)
    if installed is None:
        raise RuntimeError("O modelo indicado não está instalado neste Ollama.")
    with tempfile.TemporaryDirectory(prefix="gensia-real-") as directory:
        root = Path(directory)
        # This file is only parsed by Bandit; never imported or executed.
        fixture = root / "unsafe_example.py"
        fixture.write_text("import subprocess\ndef unsafe(command):\n    subprocess.run(command, shell=True)\n", encoding="utf-8")
        before = hashlib.sha256(fixture.read_bytes()).hexdigest()
        (root / "redes.md").write_text(
            "NAT traduz endereços IP privados em endereços públicos. "
            "PAT distingue várias ligações através de números de porta.\n", encoding="utf-8")
        team = Coordinator(root, AuditLogger(root / "audit.jsonl"), provider)
        audit = team.audit_project(code="unsafe_example.py")
        study = team.study_documents("O que faz NAT? Responde numa frase com a referência.", ["redes.md"])
        scan = audit["steps"][0].get("result", {})
        review = audit["steps"][-1].get("result", {})
        answer = study["steps"][0].get("result", {})
        checks = {
            "bandit_real_complete": scan.get("complete") is True,
            "bandit_detects_shell_true": any(i["test_id"] == "B602" for i in scan.get("issues", [])),
            "fixture_unchanged": before == hashlib.sha256(fixture.read_bytes()).hexdigest(),
            "reviewer_real_response": bool(review.get("model_used") and review.get("recommendation")),
            "study_real_response": bool(study["complete"] and answer.get("answer")),
            "study_valid_citation": answer.get("citation_status") == "present",
        }
        return {
            "gensia_version": __version__, "python": platform.python_version(),
            "platform": platform.system(), "bandit_version": scan.get("engine_version"),
            "ollama_version": provider._request("/api/version", method="GET").get("version"),
            "model": model, "model_digest": installed.get("digest"), "checks": checks,
            "passed": all(checks.values()), "audit": audit, "study": study,
            "limits": "Teste de integração com dados sintéticos; não mede qualidade geral nem garante segurança.",
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    try:
        report = validate(args.model, args.endpoint)
    except Exception as exc:
        # Avoid publishing exception messages containing provider/source details.
        print(json.dumps({"passed": False, "error_type": type(exc).__name__}))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
