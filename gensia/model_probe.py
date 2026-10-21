"""Explicit operational probe, with fixed synthetic input and no saved content."""
import argparse
import json
import math
from time import perf_counter

from . import __version__
from .providers import OllamaProvider, ProviderError, ProviderUnavailable


PROBE_PROMPT = "Teste sintético de ligação. Responde apenas com: GENSIA_OK"


def probe(model, endpoint="http://127.0.0.1:11434", *, approve=False,
          repeats=1, timeout=60.0):
    """Measure complete reply calls, including local metadata verification.

    Approval precedes provider creation. No files, history or custom prompt are
    accepted. Model content, model names, endpoints and raw errors are omitted.
    The daemon must be trusted; metadata cannot prove its network behavior.
    """
    if approve is not True:
        raise ValueError("A geração exige --approve.")
    if type(repeats) is not int or not 1 <= repeats <= 3:
        raise ValueError("Repetições devem estar entre 1 e 3.")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 1 <= timeout <= 120:
        raise ValueError("Timeout deve estar entre 1 e 120 segundos por pedido HTTP.")
    # Constructor validates the loopback endpoint and model before any I/O.
    provider = OllamaProvider(model, endpoint, timeout=timeout)
    provider._model_name(model)
    samples = []
    error = None
    attempts = 0
    interrupted = False
    for _ in range(repeats):
        attempts += 1
        started = perf_counter()
        try:
            response = provider.reply(PROBE_PROMPT)
        except ProviderError as exc:
            error = exc.code if exc.code in ProviderError.MESSAGES else "invalid_response"
            break
        except (ProviderUnavailable, OSError, ValueError):
            error = "probe_failed"
            break
        except KeyboardInterrupt:
            error = "interrupted"
            interrupted = True
            break
        elapsed = perf_counter() - started
        if not isinstance(response, str) or not response.strip() or not math.isfinite(elapsed) or elapsed < 0:
            error = "invalid_response"
            break
        samples.append({"reply_received": True, "elapsed_ms": round(elapsed * 1000, 3)})
    return {
        "kind": "gensia.model_probe", "gensia_version": __version__,
        "passed": len(samples) == repeats, "requested_samples": repeats,
        "attempts": attempts, "samples": samples, "error": error,
        "interrupted": interrupted, "input_kind": "fixed_synthetic_prompt",
        "content_included": False, "files_read": False,
        "cloud_fallback": False, "quality_validated": False,
        "hardware_memory_measured": False,
        "limitations": "Tempos de chamadas completas, incluindo metadados; não são tokens/s "
        "nem benchmark geral. Cache/carga do daemon podem alterar resultados. "
        "Resposta recebida não valida qualidade, RAM/GPU ou segurança. "
        "Usar daemon confiável com cloud desativada. Timeout aplica-se a cada "
        "pedido HTTP, não é prazo global; cancelar não garante parar a geração no daemon.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Etiqueta exata de pesos locais já instalados")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--approve", action="store_true", help="Autorizar geração com frase sintética fixa")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args(argv)
    try:
        report = probe(args.model, args.endpoint, approve=args.approve,
                       repeats=args.repeats, timeout=args.timeout)
    except ValueError:
        print(json.dumps({"kind": "gensia.model_probe", "passed": False,
                          "error": "invalid_arguments_or_approval_required"}))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 130 if report["interrupted"] else (0 if report["passed"] else 12)


if __name__ == "__main__":
    raise SystemExit(main())
