"""Windows path policy with OS APIs and process creation simulated on Linux."""
import ctypes
import os
import unittest
from unittest.mock import Mock, patch

from gensia.tools import AppLauncher, ToolError, ToolPermissionError, _windows_directory


class WindowsLauncherTests(unittest.TestCase):
    def test_all_apps_use_explicit_os_paths_despite_environment(self):
        expected = {
            'calculator': ('GetSystemDirectoryW', r'D:\Windows\System32\calc.exe'),
            'notepad': ('GetSystemDirectoryW', r'D:\Windows\System32\notepad.exe'),
            'files': ('GetSystemWindowsDirectoryW', r'D:\Windows\explorer.exe'),
        }
        for app, (api, executable) in expected.items():
            audit, runner = Mock(), Mock()
            directory = r'D:\Windows' if app == 'files' else r'D:\Windows\System32'
            with patch('gensia.tools._windows_directory', return_value=directory) as query:
                with patch.dict(os.environ, {'PATH': 'untrusted', 'SystemRoot': 'untrusted', 'WINDIR': 'untrusted'}):
                    AppLauncher(audit, 'win32', runner).open(app, approved=True)
            query.assert_called_once_with(api)
            runner.assert_called_once_with([executable], executable=executable,
                                          cwd=directory, shell=False, close_fds=True)
            self.assertEqual([call.args for call in audit.record.call_args_list],
                             [('open_app', 'intent', app), ('open_app', 'success', app)])

    def test_denied_actions_do_not_resolve_or_launch(self):
        with patch('gensia.tools._windows_directory') as query:
            for app, approved in (('calculator', False), ('powershell', True)):
                runner = Mock()
                with self.assertRaises(ToolPermissionError):
                    AppLauncher(Mock(), 'win32', runner).open(app, approved)
                runner.assert_not_called()
            query.assert_not_called()

    def test_os_lookup_failure_has_no_path_fallback(self):
        audit, runner = Mock(), Mock()
        with patch('gensia.tools._windows_directory', side_effect=ToolError('lookup failed')):
            with self.assertRaises(ToolError):
                AppLauncher(audit, 'win32', runner).open('calculator', True)
        runner.assert_not_called()
        audit.record.assert_called_once_with('open_app', 'error', 'calculator')

    def test_invalid_system_paths_never_reach_runner(self):
        paths = ('Windows', r'C:Windows', r'\Windows', r'\\server\Windows',
                 r'C:\Windows\..\untrusted', r'C:\Windows:stream',
                 'C:\\Windows\n', r'"C:\Windows"', r'C:/Windows')
        for directory in paths:
            with self.subTest(directory=directory):
                runner = Mock()
                with patch('gensia.tools._windows_directory', return_value=directory):
                    with self.assertRaises(ToolError):
                        AppLauncher(Mock(), 'win32', runner).open('notepad', True)
                runner.assert_not_called()

    def test_missing_system_executable_is_error_without_retry(self):
        runner, audit = Mock(side_effect=FileNotFoundError('PRIVATE')), Mock()
        with patch('gensia.tools._windows_directory', return_value=r'C:\Windows\System32'):
            with self.assertRaises(ToolError) as error:
                AppLauncher(audit, 'win32', runner).open('notepad', True)
        self.assertNotIn('PRIVATE', str(error.exception))
        self.assertEqual(runner.call_count, 1)
        self.assertEqual([call.args for call in audit.record.call_args_list],
                         [('open_app', 'intent', 'notepad'), ('open_app', 'error', 'notepad')])

    def test_unicode_api_adapter_returns_buffer(self):
        function = Mock()
        def populate(buffer, size):
            buffer.value = r'C:\Windows\System32'
            return len(buffer.value)
        function.side_effect = populate
        kernel = Mock(GetSystemDirectoryW=function)
        with patch.object(ctypes, 'WinDLL', return_value=kernel, create=True):
            self.assertEqual(_windows_directory('GetSystemDirectoryW'), r'C:\Windows\System32')
        self.assertEqual(len(function.argtypes), 2)

    def test_unicode_api_adapter_zero_or_oversized_is_error(self):
        for result in (0, 32768, 40000):
            kernel = Mock(GetSystemDirectoryW=Mock(return_value=result))
            with patch.object(ctypes, 'WinDLL', return_value=kernel, create=True):
                with self.assertRaises(ToolError):
                    _windows_directory('GetSystemDirectoryW')
