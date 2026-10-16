"""Providers de modelos; o Ollama só aceita um endpoint local explícito."""
import json
from http.client import HTTPException
import socket
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "Redirecionamento Ollama recusado", headers, None)


# Never delegate local prompts to a proxy or redirected endpoint.
_LOCAL_OPENER = build_opener(ProxyHandler({}), _NoRedirect())


class ProviderUnavailable(RuntimeError):
    pass


class ModelProvider(Protocol):
    def reply(self, text: str) -> str: ...
    def status(self) -> dict: ...


class UnconfiguredProvider:
    def reply(self, text: str) -> str:
        raise ProviderUnavailable(
            "Modelo não configurado. Usa --provider ollama --model NOME. "
            "Nenhuma tarefa foi executada."
        )

    def status(self) -> dict:
        return {"provider": "not_configured", "model": None, "local_only": True,
                "network_enabled": False}


class OllamaProvider:
    def __init__(self, model=None, base_url="http://127.0.0.1:11434", timeout=120.0):
        self.model = model
        self.base_url = self._validate_base_url(base_url)
        if not 0.1 <= timeout <= 600:
            raise ValueError("Timeout deve estar entre 0.1 e 600 segundos.")
        self.timeout = timeout

    @staticmethod
    def _validate_base_url(value):
        if not isinstance(value, str) or any(ord(char) <= 32 or ord(char) == 127 for char in value):
            raise ValueError("Endpoint Ollama inválido.")
        parsed = urlparse(value)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("O endpoint Ollama deve usar HTTP em localhost.")
        # Accessing .port also validates nonnumeric and out-of-range ports.
        port = parsed.port
        if (parsed.username or parsed.password or '?' in value or '#' in value
                or parsed.path not in ('', '/') or parsed.params
                or parsed.netloc.endswith(':') or port == 0):
            raise ValueError("Endpoint Ollama inválido.")
        return value.rstrip("/")

    def status(self) -> dict:
        return {"provider": "ollama", "model": self.model, "local_only": True,
                "network_enabled": True, "endpoint": self.base_url}

    def list_models(self):
        data = self._request("/api/tags", method="GET")
        models = data.get("models")
        if not isinstance(models, list):
            raise ProviderUnavailable("Resposta inválida do Ollama: campo models ausente.")
        return [item.get("name") for item in models
                if isinstance(item, dict) and isinstance(item.get("name"), str)]

    def reply(self, text: str) -> str:
        if not self.model or len(self.model) > 200:
            raise ProviderUnavailable("Escolhe um modelo com --model NOME.")
        data = self._request("/api/chat", payload={
            "model": self.model,
            "messages": [{"role": "user", "content": text}],
            "stream": False,
        })
        message = data.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ProviderUnavailable("Ollama devolveu uma resposta vazia ou inválida.")
        return content.strip()

    def _request(self, path, payload=None, method="POST"):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(self.base_url + path, data=body, method=method,
                          headers={"Content-Type": "application/json"})
        try:
            with _LOCAL_OPENER.open(request, timeout=self.timeout) as response:
                raw = response.read(10 * 1024 * 1024 + 1)
        except HTTPError as exc:
            # Untrusted error bodies may be unbounded, malformed or contain
            # sensitive prompt content and terminal control sequences.
            exc.close()
            raise ProviderUnavailable(f"Ollama respondeu HTTP {exc.code}. Verifica o serviço e o modelo local.") from exc
        except (URLError, socket.timeout, TimeoutError, HTTPException, OSError) as exc:
            raise ProviderUnavailable(
                "Não foi possível contactar o Ollama local. Confirma se o serviço está ativo."
            ) from exc
        if len(raw) > 10 * 1024 * 1024:
            raise ProviderUnavailable("Resposta do Ollama excedeu o limite de 10 MiB.")
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ProviderUnavailable("Ollama devolveu JSON inválido.") from exc
        if not isinstance(data, dict):
            raise ProviderUnavailable("Ollama devolveu uma resposta inválida.")
        if "error" in data:
            raise ProviderUnavailable("Ollama comunicou um erro. Verifica o serviço e o modelo local.")
        return data
