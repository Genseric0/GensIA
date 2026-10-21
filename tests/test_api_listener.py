from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import socket
import sys
import types
import unittest
from unittest.mock import Mock, patch

from gensia.api_listener import run_local


class ListenerTests(unittest.TestCase):
    def test_occupied_port_does_not_reveal_token_or_invoke_server(self):
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0))
            occupied.listen(1)
            port = occupied.getsockname()[1]
            fake = types.SimpleNamespace(Config=Mock(), Server=Mock())
            output, errors = StringIO(), StringIO()
            with patch.dict(sys.modules, {'uvicorn': fake}), redirect_stdout(output), redirect_stderr(errors):
                code = run_local(object(), port, 'PRIVATE', True)
        self.assertEqual(code, 10)
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('PRIVATE', errors.getvalue())
        fake.Server.assert_not_called()

    def test_reserved_socket_passed_to_server_and_closed_on_exit(self):
        saved = []
        def run(*, sockets):
            saved.extend(sockets)
            self.assertEqual(sockets[0].getsockname()[0], '127.0.0.1')
            self.assertGreater(sockets[0].getsockname()[1], 0)
            self.assertNotIn('PRIVATE', output.getvalue())
        fake = types.SimpleNamespace(Config=Mock(), Server=Mock(return_value=types.SimpleNamespace(run=run)))
        output = StringIO()
        with patch.dict(sys.modules, {'uvicorn': fake}), redirect_stdout(output):
            self.assertEqual(run_local(object(), 0, 'PRIVATE', False), 0)
        self.assertEqual(saved[0].fileno(), -1)

    def test_token_is_shown_only_after_bind_and_on_explicit_option(self):
        output = StringIO()
        def run(*, sockets):
            self.assertGreater(sockets[0].getsockname()[1], 0)
            self.assertIn('Token temporário: PRIVATE', output.getvalue())
        fake = types.SimpleNamespace(Config=Mock(), Server=Mock(return_value=types.SimpleNamespace(run=run)))
        with patch.dict(sys.modules, {'uvicorn': fake}), redirect_stdout(output):
            self.assertEqual(run_local(object(), 0, 'PRIVATE', True), 0)
