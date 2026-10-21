"""Synthetic loopback-only chat server used exclusively by the browser QA runner."""
import json
import os
from pathlib import Path
import socket
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class SyntheticProvider:
    def ensure_local_model(self, model=None):
        return {'available': True, 'locality': 'confirmed_local', 'inference_tested': False}

    def reply(self, model, prompt):
        from gensia.providers import ProviderError
        messages = json.loads(prompt.split('\n', 1)[1])
        last = messages[-1]['content']
        if last == 'SIMULATE_ERROR':
            raise ProviderError('cloud_model_blocked')
        if last == 'SIMULATE_SLOW':
            time.sleep(1.2)
        if last == 'SIMULATE_HTML':
            return '[TESTE SINTÉTICO] <img src=x onerror="window.__injected=1">'
        return f'[TESTE SINTÉTICO] Contexto: {len(messages)} mensagens. Exemplo demonstrativo de resposta local.'


def main():
    token = os.environ.get('GENSIA_API_TOKEN', '')
    if len(token) != 64 or not token.isascii() or not token.isalnum():
        return 2
    import uvicorn
    from gensia.api import create_app
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(16)
        port = listener.getsockname()[1]
        app = create_app(token, port, chat_model='synthetic-qa-only', provider=SyntheticProvider())
        config = uvicorn.Config(app, host='127.0.0.1', port=port, proxy_headers=False,
                                access_log=False, server_header=False, log_level='critical',
                                timeout_graceful_shutdown=2)
        print(json.dumps({'event':'listening','port':port}), flush=True)
        uvicorn.Server(config).run(sockets=[listener])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
