"""API opcional, local e apenas de diagnóstico. Não importa ferramentas pessoais."""
import argparse
import importlib.metadata
import os
import platform
import secrets
import sys

from . import __version__
from .agent_catalog import CatalogSnapshot, catalog_snapshot


def validate_settings(token, port):
    if not isinstance(token, str) or not 32 <= len(token) <= 256 or not token.isascii() or not token.isalnum():
        raise ValueError("GENSIA_API_TOKEN deve ter 32–256 caracteres ASCII alfanuméricos aleatórios.")
    if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
        raise ValueError("A porta deve estar entre 1024 e 65535.")


def diagnostics():
    versions = {}
    for name in ("fastapi", "uvicorn", "starlette", "pydantic"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {"python": platform.python_version(), "packages": versions,
            "model_connectivity_tested": False, "personal_data_accessed": False}


def create_app(token, port=8765):
    validate_settings(token, port)
    from fastapi import FastAPI
    from starlette.responses import JSONResponse

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None,
                  redirect_slashes=False)
    expected_host = f"127.0.0.1:{port}"

    @app.middleware("http")
    async def guard(request, call_next):
        headers = request.headers
        if headers.getlist("host") != [expected_host]:
            response = JSONResponse({"error": "host_not_allowed"}, status_code=400)
        elif "origin" in headers:
            response = JSONResponse({"error": "browser_origin_not_allowed"}, status_code=403)
        elif len(headers.getlist("authorization")) != 1 or not secrets.compare_digest(
            headers.get("authorization", "").encode(), ("Bearer " + token).encode()
        ):
            response = JSONResponse({"error": "unauthorized"}, status_code=401)
        elif request.method != "GET":
            response = JSONResponse({"error": "read_only"}, status_code=405)
        elif request.url.query:
            response = JSONResponse({"error": "query_not_allowed"}, status_code=400)
        else:
            response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/status")
    async def status():
        return {"version": __version__, "mode": "local_read_only",
                "actions_enabled": False, "cloud_fallback": False}

    @app.get("/diagnostics")
    async def diagnostic_endpoint():
        return diagnostics()

    @app.get("/agents", response_model=CatalogSnapshot)
    async def agent_catalog_endpoint():
        return catalog_snapshot()

    return app


def main(argv=None):
    parser = argparse.ArgumentParser(description="GensIA: API local read-only (Ctrl+C termina)")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    token = os.environ.get("GENSIA_API_TOKEN", "")
    try:
        validate_settings(token, args.port)
        import uvicorn
        app = create_app(token, args.port)
    except (ValueError, ImportError) as exc:
        message = str(exc) if isinstance(exc, ValueError) else "Instala requirements-api.txt no ambiente virtual."
        print(message, file=sys.stderr)
        return 10
    uvicorn.run(app, host="127.0.0.1", port=args.port, proxy_headers=False,
                access_log=False, server_header=False, workers=1,
                limit_concurrency=16, timeout_keep_alive=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
