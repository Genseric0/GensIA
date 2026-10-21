import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from gensia.static_analysis import BanditScanner, StaticAnalysisError
from gensia.tools import AuditLogger


class Completed:
    def __init__(self, returncode=0):
        self.returncode = returncode
        self.stderr = b""


class BanditScannerTests(unittest.TestCase):
    def scanner(self, root, runner, available=True):
        return BanditScanner(
            root,
            AuditLogger(Path(root) / "audit.jsonl"),
            runner=runner,
            module_finder=lambda _name: object() if available else None,
        )

    @staticmethod
    def result(filename, count=1):
        issue = {
            "filename": str(filename),
            "line_number": 2,
            "test_id": "B602",
            "test_name": "subprocess_popen_with_shell_equals_true",
            "issue_severity": "HIGH",
            "issue_confidence": "HIGH",
            "issue_text": "subprocess call with shell=True identified",
            "more_info": "https://bandit.readthedocs.io/",
            "code": "SECRET_SOURCE_CODE",
        }
        return {"results": [dict(issue) for _ in range(count)], "errors": []}

    def writing_runner(self, document, observed=None, returncode=0):
        def runner(command, **kwargs):
            if observed is not None:
                observed["command"] = command
                observed["kwargs"] = kwargs
            report = Path(command[command.index("-o") + 1])
            report.write_text(json.dumps(document), encoding="utf-8")
            return Completed(returncode)
        return runner

    def test_runs_with_argument_list_and_normalizes_read_only_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "project;echo hacked"
            target.mkdir()
            source = target / "app.py"
            source.write_text("import subprocess\nsubprocess.run('x', shell=True)\n", encoding="utf-8")
            before = source.read_bytes()
            observed = {}
            scanner = self.scanner(
                root, self.writing_runner(self.result(source), observed)
            )
            output = scanner.scan("project;echo hacked", "high", "medium", 30)
            audit = (root / "audit.jsonl").read_text(encoding="utf-8")
            after = source.read_bytes()
        self.assertFalse(observed["kwargs"]["shell"])
        self.assertIn(str(target), observed["command"])
        self.assertEqual(observed["kwargs"]["stdin"], subprocess.DEVNULL)
        self.assertNotIn("PYTHONPATH", observed["kwargs"]["env"])
        self.assertEqual(output["issues_total"], 1)
        self.assertEqual(output["issues"][0]["path"], "project;echo hacked/app.py")
        self.assertNotIn("code", output["issues"][0])
        self.assertEqual(before, after)
        self.assertIsNone(output["network_accessed"])
        self.assertIsNone(output["files_modified"])
        self.assertNotIn(str(target), audit)

    def test_controlled_configuration_and_private_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "app.py").write_text("assert False # nosec\n")
            (root / ".bandit").write_text("[bandit]\nskips=B101\n")
            def runner(command, **kwargs):
                self.assertEqual(command[1:5], ["-I", "-B", "-m", "bandit"])
                self.assertNotEqual(Path(kwargs["cwd"]), root)
                self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
                self.assertIn("--ignore-nosec", command)
                ini = Path(command[command.index("--ini") + 1])
                config = Path(command[command.index("-c") + 1])
                self.assertEqual(ini.read_text(), "[bandit]\n")
                self.assertEqual(config.read_text(), "{}\n")
                self.assertEqual(ini.parent, Path(kwargs["cwd"]))
                return self.writing_runner({"results": [], "errors": []})(command)
            result = self.scanner(root, runner).scan()
            self.assertFalse(result["project_configuration_used"])

    def test_real_interpreter_excludes_project_shadow_module(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            marker = root / "executed.txt"
            (root / "bandit.py").write_text(
                "from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n"
            )
            def runner(command, **kwargs):
                # Exercise the exact interpreter flags, without requiring Bandit.
                probe = (
                    "import sys,importlib.util; "
                    "s=importlib.util.find_spec('bandit'); "
                    "assert not s or s.origin != sys.argv[1]"
                )
                completed = subprocess.run(
                    command[:3] + ["-c", probe, str(root / "bandit.py")],
                    cwd=root, env={"PYTHONPATH": str(root)},
                    capture_output=True, timeout=10,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                return self.writing_runner({"results": [], "errors": []})(command)
            self.scanner(root, runner).scan()
            self.assertFalse(marker.exists())

    def test_rejects_absolute_traversal_and_non_python_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "note.txt").write_text("text", encoding="utf-8")
            scanner = self.scanner(root, self.fail)
            for path in (str(root / "note.txt"), "..", "note.txt"):
                with self.subTest(path=path), self.assertRaises(StaticAnalysisError):
                    scanner.scan(path)

    def test_rejects_symlink_target_and_unapproved_symlink_in_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            project = root / "project"
            project.mkdir()
            (project / "app.py").write_text("print('ok')", encoding="utf-8")
            (root / "alias").symlink_to(project, target_is_directory=True)
            (project / "linked.py").symlink_to(project / "app.py")
            scanner = self.scanner(root, self.fail)
            with self.assertRaisesRegex(StaticAnalysisError, "simbólic"):
                scanner.scan("alias")
            with self.assertRaisesRegex(StaticAnalysisError, "simbólic"):
                scanner.scan("project")

    def test_reports_missing_optional_dependency_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "app.py"
            source.write_text("print('ok')", encoding="utf-8")
            with self.assertRaisesRegex(StaticAnalysisError, "bandit==1.9.4"):
                self.scanner(directory, self.fail, available=False).scan("app.py")

    def test_excludes_common_generated_directories_from_preflight_and_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "app.py").write_text("print('ok')", encoding="utf-8")
            (root / ".venv").mkdir()
            (root / ".venv" / "large.py").write_text("x" * 1000, encoding="utf-8")
            observed = {}
            output = self.scanner(
                root, self.writing_runner(self.result(root / "app.py", 0), observed)
            ).scan(".")
        self.assertEqual(output["files_considered"], 1)
        self.assertIn("-x", observed["command"])
        self.assertIn(str(root / ".venv"), observed["command"])

    def test_timeout_and_nonzero_exit_are_sanitized(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "app.py").write_text("print('ok')", encoding="utf-8")
            def timeout_runner(*_args, **_kwargs):
                raise subprocess.TimeoutExpired(["bandit"], 5, stderr=b"secret")
            for runner, expected in (
                (timeout_runner, "timeout"),
                (lambda *_args, **_kwargs: Completed(7), "código 7"),
            ):
                with self.subTest(expected=expected), self.assertRaises(StaticAnalysisError) as caught:
                    self.scanner(directory, runner).scan("app.py", timeout=5)
                self.assertIn(expected, str(caught.exception))
                self.assertNotIn("secret", str(caught.exception))

    def test_invalid_or_oversized_report_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "app.py").write_text("print('ok')", encoding="utf-8")
            documents = ({}, {"results": "bad", "errors": []})
            for document in documents:
                with self.subTest(document=document):
                    runner = self.writing_runner(document)
                    with self.assertRaises(StaticAnalysisError):
                        self.scanner(root, runner).scan("app.py")
            def oversized(command, **_kwargs):
                report = Path(command[command.index("-o") + 1])
                report.write_bytes(b"x" * (BanditScanner.MAX_REPORT_BYTES + 1))
                return Completed()
            with self.assertRaisesRegex(StaticAnalysisError, "5 MiB"):
                self.scanner(root, oversized).scan("app.py")

    def test_limits_returned_issues_and_redacts_outside_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "app.py"
            source.write_text("print('ok')", encoding="utf-8")
            document = self.result("/outside/secret.py", 501)
            output = self.scanner(root, self.writing_runner(document)).scan("app.py")
        self.assertEqual(output["issues_total"], 501)
        self.assertEqual(output["issues_returned"], 500)
        self.assertTrue(output["truncated"])
        self.assertEqual(output["issues"][0]["path"], "<fora-da-pasta-base>")


if __name__ == "__main__":
    unittest.main()
