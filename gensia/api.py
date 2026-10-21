"""Optional loopback API: diagnostics and bounded, opt-in local conversation."""
import argparse
import importlib.metadata
import os
import platform
import secrets
import sys
import threading

from . import __version__
from .agent_catalog import CatalogSnapshot, catalog_snapshot
from .catalog_report import render_report
from .protections import protection_report
from .panel import ASSETS, panel_asset
from .chat import ChatError, MAX_BODY_BYTES, conversation, prompt_for, checked_reply, model_name
from .api_listener import run_local


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
            "model_connectivity_tested": False, "personal_data_accessed": False,
            "document_protections": protection_report()}


def create_app(token, port=8765, chat_model=None, provider=None):
    validate_settings(token, port)
    if chat_model is not None:
        model_name(chat_model)
    from fastapi import FastAPI
    from .providers import OllamaProvider, ProviderUnavailable
    from starlette.responses import JSONResponse, HTMLResponse, Response
    from starlette.concurrency import run_in_threadpool
    from starlette.requests import Request

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None,
                  redirect_slashes=False)
    expected_host = f"127.0.0.1:{port}"
    expected_origin = f"http://{expected_host}"
    model = provider if provider is not None else OllamaProvider(model=chat_model, timeout=90)
    model_lock = threading.Lock()

    @app.middleware("http")
    async def guard(request, call_next):
        headers = request.headers
        if headers.getlist("host") != [expected_host]:
            response = JSONResponse({"error": "host_not_allowed"}, status_code=400)
        elif "origin" in headers and not (
            ((request.url.path in ('/diagnostics', '/model') and request.method == 'GET')
             or (request.url.path == '/chat' and request.method == 'POST'))
            and headers.getlist('origin') == [expected_origin]
        ):
            response = JSONResponse({"error": "browser_origin_not_allowed"}, status_code=403)
        elif 'sec-fetch-site' in headers and headers.getlist('sec-fetch-site') not in (
            ['same-origin'], ['none']
        ):
            response = JSONResponse({'error': 'fetch_site_not_allowed'}, status_code=403)
        elif request.url.path in ASSETS:
            if request.method != 'GET':
                response = JSONResponse({'error': 'read_only'}, status_code=405)
            elif request.url.query:
                response = JSONResponse({'error': 'query_not_allowed'}, status_code=400)
            else:
                response = await call_next(request)
        elif len(headers.getlist("authorization")) != 1 or not secrets.compare_digest(
            headers.get("authorization", "").encode(), ("Bearer " + token).encode()
        ):
            response = JSONResponse({"error": "unauthorized"}, status_code=401)
        elif request.method != "GET" and not (request.url.path == '/chat' and request.method == 'POST'):
            response = JSONResponse({"error": "read_only"}, status_code=405)
        elif request.url.query:
            response = JSONResponse({"error": "query_not_allowed"}, status_code=400)
        else:
            response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if request.url.path in ASSETS and response.status_code == 200:
            response.headers['Content-Security-Policy'] = (
                "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src data:; "
                "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
            )
            response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
        if request.url.path == "/agents/report" and response.status_code == 200:
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; "
                "form-action 'none'; frame-ancestors 'none'"
            )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        return response

    def asset(route):
        content, media_type = panel_asset(route)
        return Response(content, media_type=media_type)

    @app.get('/panel')
    async def panel():
        return asset('/panel')

    @app.get('/panel.js')
    async def panel_js():
        return asset('/panel.js')

    @app.get('/panel.css')
    async def panel_css():
        return asset('/panel.css')

    @app.get('/app')
    async def chat_page():
        return asset('/app')

    @app.get('/app.js')
    async def chat_js():
        return asset('/app.js')

    @app.get('/app.css')
    async def chat_css():
        return asset('/app.css')

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/status")
    async def status():
        return {"version": __version__, "mode": "local_read_only",
                "actions_enabled": False, "cloud_fallback": False,
                "chat_configured": chat_model is not None}

    def provider_failure(error):
        code = getattr(error, 'code', 'upstream_error')
        allowed = {'model_required', 'invalid_input', 'cloud_model_blocked', 'locality_unconfirmed',
                   'connection_failed', 'model_not_found', 'upstream_error', 'invalid_response',
                   'response_too_large', 'unsafe_text'}
        return JSONResponse({'error': code if code in allowed else 'upstream_error'}, status_code=503)

    @app.get('/model')
    def model_status():
        if chat_model is None:
            return {'configured': False, 'available': False, 'locality': 'not_checked',
                    'inference_tested': False}
        if not model_lock.acquire(blocking=False):
            return JSONResponse({'error': 'model_busy'}, status_code=429)
        try:
            info = model.ensure_local_model(chat_model)
            if info.get('available') is not True or info.get('locality') != 'confirmed_local':
                return JSONResponse({'error': 'locality_unconfirmed'}, status_code=503)
            return {'configured': True, 'available': True, 'locality': 'confirmed_local',
                    'inference_tested': False}
        except ProviderUnavailable as error:
            return provider_failure(error)
        except Exception:
            return JSONResponse({'error': 'model_check_failed'}, status_code=503)
        finally:
            model_lock.release()

    def generate(messages):
        # Lock stays with the worker until actual completion, even if the client leaves.
        if not model_lock.acquire(blocking=False):
            return JSONResponse({'error': 'model_busy'}, status_code=429)
        try:
            text = checked_reply(model.reply(chat_model, prompt_for(messages)))
            return {'reply': text, 'actions_executed': False, 'cloud_fallback': False}
        except ProviderUnavailable as error:
            return provider_failure(error)
        except ChatError:
            return JSONResponse({'error': 'invalid_model_response'}, status_code=502)
        except Exception:
            return JSONResponse({'error': 'generation_failed'}, status_code=503)
        finally:
            model_lock.release()

    async def chat_endpoint(request):
        if chat_model is None:
            return JSONResponse({'error': 'chat_not_configured'}, status_code=503)
        if request.headers.getlist('content-type') != ['application/json']:
            return JSONResponse({'error': 'json_required'}, status_code=415)
        lengths = request.headers.getlist('content-length')
        if lengths and (len(lengths) != 1 or not lengths[0].isdigit()
                        or len(lengths[0]) > 10 or int(lengths[0]) > MAX_BODY_BYTES):
            return JSONResponse({'error': 'request_too_large'}, status_code=413)
        chunks, size = [], 0
        try:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_BODY_BYTES:
                    return JSONResponse({'error': 'request_too_large'}, status_code=413)
                chunks.append(chunk)
            messages = conversation(b''.join(chunks))
        except ChatError as error:
            return JSONResponse({'error': error.code}, status_code=400)
        except Exception:
            return JSONResponse({'error': 'invalid_request'}, status_code=400)
        return await run_in_threadpool(generate, messages)

    # FastAPI must see the concrete Request annotation when optional imports are local.
    chat_endpoint.__annotations__['request'] = Request
    app.add_api_route('/chat', chat_endpoint, methods=['POST'])

    @app.get("/diagnostics")
    async def diagnostic_endpoint():
        return diagnostics()

    @app.get("/agents", response_model=CatalogSnapshot)
    async def agent_catalog_endpoint():
        return catalog_snapshot()

    @app.get("/agents/report", response_class=HTMLResponse)
    async def agent_report_endpoint():
        return HTMLResponse(render_report(), headers={
            "Content-Disposition": 'attachment; filename="gensia-agents.html"',
        })

    return app


def main(argv=None):
    parser = argparse.ArgumentParser(description="GensIA: API local e conversa opcional (Ctrl+C termina)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument('--chat-model', help='Modelo Ollama local previamente instalado')
    parser.add_argument('--ephemeral-token', action='store_true', help='Gerar e apresentar token só para esta execução')
    args = parser.parse_args(argv)
    token = secrets.token_hex(32) if args.ephemeral_token else os.environ.get("GENSIA_API_TOKEN", "")
    try:
        validate_settings(token, args.port)
        import uvicorn
        app = create_app(token, args.port, chat_model=args.chat_model)
    except (ValueError, ImportError) as exc:
        message = str(exc) if isinstance(exc, ValueError) else "Instala requirements-api.txt no ambiente virtual."
        print(message, file=sys.stderr)
        return 10
    return run_local(app, args.port, token=token, display_token=args.ephemeral_token)


if __name__ == "__main__":
    raise SystemExit(main())
