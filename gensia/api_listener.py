"""Reserve the loopback listener before revealing an ephemeral access token."""
import socket
import sys


def run_local(app, port, token=None, display_token=False):
    import uvicorn

    listener = None
    try:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(('127.0.0.1', port))
        listener.listen(128)
        listener.setblocking(False)
    except OSError:
        if listener is not None:
            listener.close()
        print('Não foi possível reservar a porta local. Nenhum token foi apresentado.', file=sys.stderr)
        return 10
    try:
        config = uvicorn.Config(app, host='127.0.0.1', port=port, proxy_headers=False,
                                access_log=False, server_header=False, workers=1,
                                limit_concurrency=16, timeout_keep_alive=5)
        server = uvicorn.Server(config)
        print(f'GensIA: http://127.0.0.1:{port}/app', flush=True)
        if display_token is True:
            print(f'Token temporário: {token}', flush=True)
        server.run(sockets=[listener])
        return 0
    finally:
        listener.close()
