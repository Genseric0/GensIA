"""Development helper: isolated loopback API on a reserved ephemeral socket."""
import argparse
import json
import os
from pathlib import Path
import socket
import sys

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    token = os.environ.get('GENSIA_API_TOKEN', '')
    if not (len(token) == 64 and token.isascii() and token.isalnum()):
        print(json.dumps({'event': 'error', 'reason': 'invalid_test_configuration'}), flush=True)
        return 2
    try:
        import uvicorn
        from gensia.api import create_app
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(16)
            port = listener.getsockname()[1]
            app = create_app(token, port)
            config = uvicorn.Config(app, host='127.0.0.1', port=port, proxy_headers=False,
                                    access_log=False, server_header=False, log_level='critical',
                                    timeout_graceful_shutdown=2, workers=1)
            # Socket is reserved before announcing; runner still waits for /health.
            print(json.dumps({'event': 'listening', 'port': port,
                              'python': '.'.join(map(str, sys.version_info[:3]))}), flush=True)
            uvicorn.Server(config).run(sockets=[listener])
        return 0
    except Exception:
        print(json.dumps({'event': 'error', 'reason': 'test_server_unavailable'}), flush=True)
        return 10


if __name__ == '__main__':
    raise SystemExit(main())
