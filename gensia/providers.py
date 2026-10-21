"""Providers de modelos; o Ollama só aceita um endpoint local explícito."""
import json
from http.client import HTTPException
import math
import re
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


class ProviderError(ProviderUnavailable):
    """Fixed public codes/messages; never reflect model, prompt or server data."""
    MESSAGES = {
        'model_required': 'Escolhe um modelo local com --model NOME.',
        'invalid_input': 'Pedido ao modelo inválido ou demasiado longo.',
        'cloud_model_blocked': 'Modelo remoto recusado; configura um modelo local.',
        'locality_unconfirmed': 'Não foi possível confirmar metadados de um modelo local.',
        'connection_failed': 'Não foi possível contactar o Ollama local.',
        'model_not_found': 'O modelo local não foi encontrado.',
        'upstream_error': 'O Ollama comunicou um erro; verifica o serviço local.',
        'invalid_response': 'O Ollama devolveu uma resposta inválida.',
        'response_too_large': 'A resposta do Ollama excedeu o limite permitido.',
        'unsafe_text': 'O Ollama devolveu texto inválido ou controlos de terminal.',
    }

    def __init__(self, code):
        self.code = code if code in self.MESSAGES else 'invalid_response'
        super().__init__(self.MESSAGES[self.code])


def _safe_text(value, limit, *, input_text=False):
    code = 'invalid_input' if input_text else 'unsafe_text'
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ProviderError(code)
    # CRLF is a normal line ending; a bare CR can overwrite terminal output.
    value = value.replace('\r\n', '\n')
    if any((ord(c) < 32 and c not in '\t\n') or 127 <= ord(c) <= 159 for c in value):
        raise ProviderError(code)
    try:
        value.encode('utf-8', errors='strict')
    except UnicodeError:
        raise ProviderError(code) from None
    return value


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError('nonfinite number')


def _strict_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('nonfinite number')
    return number


def _bounded_depth(document):
    # Independent of interpreter JSON recursion behavior; bounded iterator stack.
    stack = [(iter((document,)), 0)]
    while stack:
        iterator, depth = stack[-1]
        try:
            value = next(iterator)
        except StopIteration:
            stack.pop()
            continue
        if isinstance(value, (dict, list)):
            if depth >= 64:
                raise ProviderError('invalid_response')
            stack.append((iter(value.values() if isinstance(value, dict) else value), depth + 1))


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
    MAX_RESPONSE_BYTES = 10 * 1024 * 1024
    MAX_INPUT_CHARACTERS = 96000
    MAX_OUTPUT_CHARACTERS = 1024 * 1024

    def __init__(self, model=None, base_url="http://127.0.0.1:11434", timeout=120.0):
        self.model = model
        self.base_url = self._validate_base_url(base_url)
        if type(timeout) not in (int, float) or not 0.1 <= timeout <= 600 or not math.isfinite(timeout):
            raise ValueError("Timeout deve estar entre 0.1 e 600 segundos.")
        if model is not None:
            try:
                self._model_name(model)
            except ProviderError:
                raise ValueError('Nome do modelo inválido.') from None
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
                "network_enabled": True, "endpoint": self.base_url,
                "endpoint_loopback": True, "locality_verified": False,
                "inference_verified": False}

    @staticmethod
    def _model_name(model):
        if model is None or model == '':
            raise ProviderError('model_required')
        if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}', model):
            raise ProviderError('invalid_input')
        return model

    @staticmethod
    def _reject_remote(data):
        for field in ('remote_model', 'remote_host'):
            if field in data:
                value = data[field]
                if not isinstance(value, str):
                    raise ProviderError('invalid_response')
                if value:
                    raise ProviderError('cloud_model_blocked')

    def ensure_local_model(self, model=None):
        selected = self._model_name(self.model if model is None else model)
        if selected.casefold().endswith((':cloud', '-cloud')):
            raise ProviderError('cloud_model_blocked')
        data = self._request('/api/show', payload={'model': selected})
        self._reject_remote(data)
        details, information = data.get('details'), data.get('model_info')
        if not isinstance(details, dict) or not isinstance(information, dict):
            raise ProviderError('locality_unconfirmed')
        architecture = information.get('general.architecture')
        if details.get('format') != 'gguf' or not isinstance(architecture, str) or not architecture.strip():
            raise ProviderError('locality_unconfirmed')
        _safe_text(architecture, 200)
        return {'available': True, 'locality': 'confirmed_local', 'inference_tested': False}

    def list_models(self):
        data = self._request("/api/tags", method="GET")
        models = data.get("models")
        if not isinstance(models, list):
            raise ProviderUnavailable("Resposta inválida do Ollama: campo models ausente.")
        names = []
        for item in models:
            if not isinstance(item, dict) or not isinstance(item.get('name'), str):
                raise ProviderError('invalid_response')
            self._model_name(item['name'])
            names.append(item['name'])
        return names

    def reply(self, text: str, prompt=None) -> str:
        # Legacy reply(text), or explicit reply(model, prompt), without mutating
        # provider configuration shared by concurrent requests.
        selected = self._model_name(self.model if prompt is None else text)
        text = _safe_text(text if prompt is None else prompt, self.MAX_INPUT_CHARACTERS, input_text=True)
        self.ensure_local_model(selected)
        data = self._request("/api/chat", payload={
            "model": selected,
            "messages": [{"role": "user", "content": text}],
            "stream": False,
        })
        self._reject_remote(data)
        if 'done' in data and data['done'] is not True:
            raise ProviderError('invalid_response')
        message = data.get("message")
        if isinstance(message, dict) and message.get('role', 'assistant') != 'assistant':
            raise ProviderError('invalid_response')
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ProviderError('invalid_response')
        return _safe_text(content, self.MAX_OUTPUT_CHARACTERS).strip()

    def _request(self, path, payload=None, method="POST"):
        body = None if payload is None else json.dumps(payload, allow_nan=False).encode("utf-8")
        request = Request(self.base_url + path, data=body, method=method,
                          headers={"Content-Type": "application/json"})
        try:
            with _LOCAL_OPENER.open(request, timeout=self.timeout) as response:
                raw = response.read(self.MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            # Untrusted error bodies may be unbounded, malformed or contain
            # sensitive prompt content and terminal control sequences.
            exc.close()
            raise ProviderError('model_not_found' if exc.code == 404 else 'upstream_error') from None
        except (URLError, socket.timeout, TimeoutError, HTTPException, OSError) as exc:
            raise ProviderError('connection_failed') from None
        if not isinstance(raw, bytes):
            raise ProviderError('invalid_response')
        if len(raw) > self.MAX_RESPONSE_BYTES:
            raise ProviderError('response_too_large')
        try:
            data = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_object,
                              parse_constant=_reject_constant, parse_float=_strict_float)
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise ProviderError('invalid_response') from None
        if not isinstance(data, dict):
            raise ProviderError('invalid_response')
        _bounded_depth(data)
        if "error" in data:
            raise ProviderError('upstream_error')
        return data
