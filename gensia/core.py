"""Encaminhamento independente da interface e do futuro motor de inferência."""
from dataclasses import dataclass
import importlib.util
import platform
from . import __version__
from .providers import ModelProvider, ProviderUnavailable


@dataclass(frozen=True)
class Result:
    ok: bool
    text: str
    code: int = 0


class Assistant:
    def __init__(self, provider: ModelProvider):
        self.provider = provider

    def status(self) -> dict:
        return {
            "version": __version__,
            "python": platform.python_version(),
            "system": platform.system(),
            **self.provider.status(),
            "persistent_memory": False,
            "memory_available": True,
            "memory_mode": "explicit_cli_only",
            "system_tools_enabled": True,
            "system_tools_mode": "explicit_cli_only",
            "voice_enabled": importlib.util.find_spec("whisper") is not None,
            "voice_available": True,
            "voice_mode": "explicit_audio_file_only",
            "tts_enabled": importlib.util.find_spec("piper") is not None,
            "tts_mode": "explicit_wav_file_only",
            "microphone_enabled": importlib.util.find_spec("sounddevice") is not None,
            "microphone_mode": "explicit_fixed_duration_only",
            "documents_available": True,
            "documents_mode": "explicit_local_text_only",
            "pdf_enabled": importlib.util.find_spec("pypdf") is not None,
            "pdf_mode": "explicit_local_embedded_text_only",
            "pdf_questions_available": True,
            "pdf_citations": "model_generated_page_markers_syntax_checked",
            "document_search_available": True,
            "document_search_mode": "local_ephemeral_lexical",
            "grounded_answers_available": True,
            "grounded_answers_mode": "retrieved_excerpts_to_local_provider_only",
            "passive_url_analysis_available": True,
            "passive_url_analysis_network": False,
            "url_reputation_available": True,
            "url_reputation_mode": "explicit_virustotal_lookup_only",
            "cisa_kev_available": True,
            "cisa_kev_mode": "explicit_update_local_lookup",
            "bandit_scan_available": True,
            "bandit_installed": importlib.util.find_spec("bandit") is not None,
            "bandit_scan_mode": "explicit_local_read_only",
        }

    def handle(self, text: str) -> Result:
        text = text.strip()
        if not text:
            return Result(False, "Escreve uma pergunta ou /ajuda.", 2)
        if len(text) > 16000:
            return Result(False, "Entrada demasiado longa (máximo: 16000 caracteres).", 2)
        if text == "/ajuda":
            return Result(True, "/ajuda — comandos; /estado — capacidades; /sair — terminar. "
                          "Texto livre usa o provider escolhido ao iniciar a sessão.")
        if text == "/estado":
            state = self.status()
            model = state.get("model") or "não configurado"
            return Result(True, f"GensIA {__version__}: terminal pronto; "
                          f"provider={state['provider']}; modelo={model}; "
                          "voz por ficheiro, memória e ferramentas disponíveis por comandos explícitos.")
        if text.startswith("/"):
            return Result(False, "Comando desconhecido. Usa /ajuda.", 2)
        try:
            return Result(True, self.provider.reply(text))
        except ProviderUnavailable as exc:
            return Result(False, str(exc), 3)
