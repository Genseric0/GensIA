from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest
from unittest.mock import patch
from gensia.providers import OllamaProvider, ProviderUnavailable


class TransportTests(unittest.TestCase):
    def server(self, redirect_code=None):
        visits = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                visits.append(self.path)
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                if redirect_code and self.path != "/escaped":
                    self.send_response(redirect_code)
                    self.send_header("Location", "/escaped")
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"details":{"format":"gguf"},"model_info":{"general.architecture":"llama"}}'
                                     if self.path == '/api/show' else b'{"message":{"content":"local"}}')

            def do_GET(self):
                visits.append(self.path)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"message":{"content":"redirected"}}')

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.addCleanup(cleanup)
        return f"http://127.0.0.1:{server.server_port}", visits

    def test_http_redirects_are_not_followed(self):
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code):
                endpoint, visits = self.server(code)
                with self.assertRaises(ProviderUnavailable):
                    OllamaProvider("fixture", endpoint).reply("test prompt")
                self.assertEqual(visits, ["/api/show"])

    def test_environment_proxy_cannot_receive_prompt(self):
        endpoint, visits = self.server()
        proxy, proxy_visits = self.server()
        with patch.dict("os.environ", {"http_proxy": proxy, "HTTP_PROXY": proxy,
                                      "no_proxy": "", "NO_PROXY": ""}):
            self.assertEqual(OllamaProvider("fixture", endpoint).reply("test prompt"), "local")
        self.assertEqual(visits, ["/api/show", "/api/chat"])
        self.assertEqual(proxy_visits, [])
