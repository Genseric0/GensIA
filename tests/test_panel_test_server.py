import http.client
import importlib.util
import json
import os
from pathlib import Path
import secrets
import selectors
import subprocess
import sys
import time
import unittest

HELPER = str(Path(__file__).resolve().parents[1] / 'scripts' / 'panel_test_server.py')


class PanelTestServerTests(unittest.TestCase):
    def test_invalid_configuration_does_not_echo_credentials(self):
        for token in ('', 'PRIVATE_SECRET'):
            result = subprocess.run([sys.executable, '-I', '-B', HELPER],
                env={**os.environ, 'GENSIA_API_TOKEN': token}, capture_output=True,
                text=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout),
                             {'event': 'error', 'reason': 'invalid_test_configuration'})
            self.assertNotIn('PRIVATE_SECRET', result.stdout + result.stderr)

    @unittest.skipUnless(os.name == 'posix' and importlib.util.find_spec('uvicorn')
                         and importlib.util.find_spec('fastapi'), 'POSIX API development helper test')
    def test_real_ephemeral_api_authentication_and_shutdown(self):
        token = secrets.token_hex(32)
        child = subprocess.Popen([sys.executable, '-I', '-B', HELPER],
            env={**os.environ, 'GENSIA_API_TOKEN': token}, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True)
        self.addCleanup(lambda: child.stdout.close())
        def stop():
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill(); child.wait(timeout=3)
        self.addCleanup(stop)
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            self.assertTrue(selector.select(timeout=5), 'No readiness metadata within deadline')
            line = child.stdout.readline(4097)
        self.assertNotIn(token, line)
        ready = json.loads(line)
        self.assertEqual(ready['event'], 'listening')
        self.assertEqual(set(ready), {'event', 'port', 'python'})
        self.assertGreaterEqual(ready['port'], 1024)
        def request(route, authorized=False):
            client = http.client.HTTPConnection('127.0.0.1', ready['port'], timeout=1)
            try:
                client.request('GET', route, headers={'Authorization': 'Bearer ' + token} if authorized else {})
                response = client.getresponse()
                return response.status, response.read()
            finally:
                client.close()
        deadline = time.monotonic() + 5
        while True:
            try:
                if request('/health', True)[0] == 200:
                    break
            except OSError:
                pass
            self.assertLess(time.monotonic(), deadline, 'Temporary API not ready')
            time.sleep(0.03)
        self.assertEqual(request('/panel')[0], 200)
        self.assertEqual(request('/diagnostics')[0], 401)
        status, body = request('/diagnostics', True)
        self.assertEqual(status, 200)
        self.assertNotIn(token.encode(), body)
        stop()
        self.assertIsNotNone(child.returncode)
