"""Read-only prerequisite checks; never install, pull, generate, or start services."""
import argparse
import importlib.metadata
import importlib.util
import json
import math
from urllib.parse import urlparse

from . import __version__
from .providers import OllamaProvider, ProviderUnavailable
from .protections import protection_report


def _bandit_check():
    try:
        version = importlib.metadata.version("bandit")
        present = importlib.util.find_spec("bandit") is not None
    except importlib.metadata.PackageNotFoundError:
        return {"state": "missing", "version": None, "execution_validated": False}
    except (ImportError, ValueError, OSError):
        return {"state": "unavailable", "version": None, "execution_validated": False}
    return {"state": "available" if present else "unavailable", "version": version,
            "execution_validated": False}


def diagnose(model=None, endpoint="http://127.0.0.1:11434", timeout=2.0):
    """Probe only /api/tags via the protected local transport, without prompts.

    A listed model is not proof of working inference or local-only model execution.
    Exact model tags are required; no alias guessing or automatic selection.
    """
    if model is not None and (not isinstance(model, str) or not model or
                              len(model) > 200 or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in model)):
        raise ValueError("Indica uma etiqueta de modelo válida, sem espaços, até 200 caracteres.")
    if not math.isfinite(timeout) or not 0.1 <= timeout <= 10:
        raise ValueError("Timeout deve estar entre 0.1 e 10 segundos.")
    provider = OllamaProvider(model, endpoint, timeout=timeout)
    parsed = urlparse(provider.base_url)
    if parsed.path not in ("", "/") or (parsed.port is not None and not 1 <= parsed.port <= 65535):
        raise ValueError("Usa a origem local do Ollama, sem caminho adicional.")

    bandit = _bandit_check()
    selected = {"state": "not_selected" if model is None else "not_checked",
                "requested": model, "inference_validated": False}
    ollama = {"state": "unavailable_or_invalid"}
    actions = []
    if bandit["state"] != "available":
        actions.append("Preparar Bandit no mesmo ambiente Python; consultar docs/DOCTOR.md.")
    try:
        names = provider.list_models()
        ollama = {"state": "reachable", "models_count": len(names)}
        if model is not None:
            selected["state"] = "listed" if model in names else "missing"
    except (ProviderUnavailable, OSError, ValueError):
        # Do not expose HTTP error bodies or inventory returned by a local service.
        actions.append("Confirmar o serviço Ollama e o endpoint local; a resposta pode estar inválida.")
    if model is None:
        actions.append("Repetir com --model e a etiqueta exata de um modelo local escolhido por ti.")
    elif selected["state"] == "missing":
        actions.append("Modelo não listado. Verificar a etiqueta e instalar os pesos manualmente se necessário.")

    passed = bandit["state"] == "available" and selected["state"] == "listed"
    if passed:
        actions.append("Executar scripts/validate_agents_real.py para validar geração e análise reais.")
    return {
        "gensia_version": __version__, "preflight_passed": passed,
        "checks": {"bandit": bandit, "ollama": ollama, "model": selected,
                   "document_protections": protection_report()},
        "next_actions": actions, "prompts_sent": False, "downloads_started": False,
        "services_started": False, "cloud_fallback": False,
        "limitations": "Verifica metadados e listagem, não executa Bandit nem inferência. "
                       "Modelo listado não comprova pesos utilizáveis, qualidade ou execução sem cloud. "
                       "Usar pesos locais e desativar cloud no servidor Ollama. "
                       "preflight_passed refere-se apenas a Bandit/modelo, não aprova segurança; "
                       "capacidades de documentos não são testes de aplicação das proteções.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="GensIA: diagnóstico local sem prompts ou downloads")
    parser.add_argument("--model", help="etiqueta exata, por exemplo qwen2.5:0.5b")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args(argv)
    try:
        report = diagnose(args.model, args.endpoint, args.timeout)
    except ValueError:
        print(json.dumps({"preflight_passed": False, "error": "invalid_arguments"}))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["preflight_passed"] else 12


if __name__ == "__main__":
    raise SystemExit(main())
