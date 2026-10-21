"""Análise estática local e limitada de código Python com Bandit opcional."""
from collections import Counter
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .tools import AuditLogger


class StaticAnalysisError(RuntimeError):
    pass


class BanditScanner:
    MAX_FILES = 5000
    MAX_SOURCE_BYTES = 100 * 1024 * 1024
    MAX_REPORT_BYTES = 5 * 1024 * 1024
    MAX_RETURNED_ISSUES = 500
    LEVELS = {"all", "low", "medium", "high"}
    EXCLUDED_DIRECTORIES = {
        ".git", ".hg", ".svn", ".mypy_cache", ".nox", ".pytest_cache",
        ".tox", ".venv", "__pycache__", "build", "dist", "env",
        "node_modules", "venv",
    }

    def __init__(self, workspace, audit: AuditLogger, runner=None, module_finder=None):
        try:
            self.workspace = Path(workspace).expanduser().resolve(strict=True)
        except OSError as exc:
            raise StaticAnalysisError("A pasta-base não existe ou não está acessível.") from exc
        if not self.workspace.is_dir():
            raise StaticAnalysisError("A pasta-base deve ser um diretório.")
        self.audit = audit
        self.runner = runner or subprocess.run
        self.module_finder = module_finder or importlib.util.find_spec

    def scan(self, relative_path=".", severity="low", confidence="low", timeout=120.0) -> dict:
        if severity not in self.LEVELS or confidence not in self.LEVELS:
            raise StaticAnalysisError("Severidade e confiança devem ser all, low, medium ou high.")
        if not 5 <= timeout <= 300:
            raise StaticAnalysisError("O timeout deve estar entre 5 e 300 segundos.")
        target, target_label = self._resolve_target(relative_path)
        file_count, source_bytes, excluded = self._preflight(target)
        if not file_count:
            self.audit.record("scan_python_bandit", "denied", target_label)
            raise StaticAnalysisError("O alvo não contém ficheiros Python para analisar.")
        if self.module_finder("bandit") is None:
            self.audit.record("scan_python_bandit", "unavailable", target_label)
            raise StaticAnalysisError(
                "Bandit não está instalado. Executa: py -3 -m pip install bandit==1.9.4"
            )

        with tempfile.TemporaryDirectory(prefix="gensia-bandit-") as temp_directory:
            report = Path(temp_directory) / "report.json"
            ini = Path(temp_directory) / "controlled.ini"
            config = Path(temp_directory) / "controlled.yaml"
            ini.write_text("[bandit]\n", encoding="utf-8")
            config.write_text("{}\n", encoding="utf-8")
            command = [
                sys.executable, "-I", "-B", "-m", "bandit", "-f", "json", "-o", str(report),
                "--ini", str(ini), "-c", str(config), "--ignore-nosec",
                "--severity-level", severity, "--confidence-level", confidence,
                "--exit-zero",
            ]
            if target.is_dir():
                command.append("-r")
            if excluded:
                command.extend(["-x", ",".join(str(path) for path in excluded)])
            command.append(str(target))
            environment = os.environ.copy()
            environment.pop("PYTHONPATH", None)
            environment.pop("PYTHONHOME", None)
            try:
                completed = self.runner(
                    command,
                    cwd=temp_directory,
                    env=environment,
                    shell=False,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                self.audit.record("scan_python_bandit", "timeout", target_label)
                raise StaticAnalysisError("A análise Bandit excedeu o timeout.") from exc
            except OSError as exc:
                self.audit.record("scan_python_bandit", "error", target_label)
                raise StaticAnalysisError("Não foi possível iniciar o Bandit.") from exc
            if completed.returncode != 0:
                self.audit.record("scan_python_bandit", "error", target_label)
                raise StaticAnalysisError(f"O Bandit falhou com código {completed.returncode}.")
            try:
                if not report.is_file() or report.stat().st_size > self.MAX_REPORT_BYTES:
                    raise StaticAnalysisError("O relatório Bandit está ausente ou excedeu 5 MiB.")
                document = json.loads(report.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self.audit.record("scan_python_bandit", "error", target_label)
                raise StaticAnalysisError("O Bandit produziu um relatório JSON inválido.") from exc

        try:
            output = self._normalize_report(document)
        except StaticAnalysisError:
            self.audit.record("scan_python_bandit", "error", target_label)
            raise
        self.audit.record("scan_python_bandit", "success", target_label)
        return {
            "engine": "bandit",
            "engine_version": self._version(),
            "target": target_label,
            "files_considered": file_count,
            "source_bytes": source_bytes,
            "severity_threshold": severity,
            "confidence_threshold": confidence,
            "issues_total": output["issues_total"],
            "issues_returned": len(output["issues"]),
            "truncated": output["issues_total"] > len(output["issues"]),
            "severity_counts": output["severity_counts"],
            "confidence_counts": output["confidence_counts"],
            "scanner_errors_count": output["scanner_errors_count"],
            "complete": output["scanner_errors_count"] == 0,
            "issues": output["issues"],
            "local_only": True,
            "network_accessed": None,
            "files_modified": None,
            "isolation": "python_isolated_mode_not_os_sandbox",
            "project_configuration_used": False,
            "limitations": (
                "Análise estática heurística: pode ter falsos positivos e falsos negativos; "
                "não executa intencionalmente o projeto nem substitui revisão humana. "
                "Não é uma sandbox do SO: plugins instalados são código confiável; "
                "rede e alterações não são monitorizadas. Não analisar árvores que mudem em simultâneo."
            ),
        }

    def _resolve_target(self, value):
        candidate = Path(value)
        if candidate.is_absolute():
            raise StaticAnalysisError("Usa um caminho relativo à pasta-base.")
        lexical = self.workspace
        for component in candidate.parts:
            lexical = lexical / component
            if lexical.is_symlink():
                raise StaticAnalysisError("O alvo não pode atravessar links simbólicos.")
        try:
            target = (self.workspace / candidate).resolve(strict=True)
        except OSError as exc:
            raise StaticAnalysisError("O alvo não existe ou não está acessível.") from exc
        if not target.is_relative_to(self.workspace):
            raise StaticAnalysisError("O caminho sai da pasta-base autorizada.")
        if not target.is_dir() and not (target.is_file() and target.suffix.casefold() == ".py"):
            raise StaticAnalysisError("O alvo deve ser uma pasta ou um ficheiro .py.")
        return target, target.relative_to(self.workspace).as_posix() or "."

    def _preflight(self, target):
        files = []
        excluded = []
        if target.is_file():
            files = [target]
        else:
            for root, directories, names in os.walk(target, topdown=True, followlinks=False):
                root_path = Path(root)
                kept = []
                for name in directories:
                    child = root_path / name
                    if name in self.EXCLUDED_DIRECTORIES:
                        excluded.append(child)
                    elif child.is_symlink():
                        raise StaticAnalysisError("A árvore contém um link simbólico não autorizado.")
                    else:
                        kept.append(name)
                directories[:] = kept
                for name in names:
                    child = root_path / name
                    if child.is_symlink():
                        raise StaticAnalysisError("A árvore contém um link simbólico não autorizado.")
                    if child.suffix.casefold() == ".py":
                        files.append(child)
                        if len(files) > self.MAX_FILES:
                            raise StaticAnalysisError("O alvo excede 5000 ficheiros Python.")
        total = 0
        try:
            for path in files:
                total += path.stat().st_size
                if total > self.MAX_SOURCE_BYTES:
                    raise StaticAnalysisError("O código Python excede 100 MiB.")
        except OSError as exc:
            raise StaticAnalysisError("Não foi possível inspecionar os ficheiros Python.") from exc
        return len(files), total, excluded

    def _normalize_report(self, document):
        if not isinstance(document, dict) or not isinstance(document.get("results"), list):
            raise StaticAnalysisError("O relatório Bandit tem uma estrutura inválida.")
        results = document["results"]
        severity_counts = Counter()
        confidence_counts = Counter()
        issues = []
        for index, item in enumerate(results):
            if not isinstance(item, dict):
                raise StaticAnalysisError(f"O resultado Bandit {index} é inválido.")
            severity = self._bounded_text(item.get("issue_severity"), 20).upper()
            confidence = self._bounded_text(item.get("issue_confidence"), 20).upper()
            severity_counts[severity] += 1
            confidence_counts[confidence] += 1
            if len(issues) < self.MAX_RETURNED_ISSUES:
                issues.append({
                    "path": self._relative_report_path(item.get("filename")),
                    "line": self._positive_integer(item.get("line_number")),
                    "test_id": self._bounded_text(item.get("test_id"), 40),
                    "test_name": self._bounded_text(item.get("test_name"), 120),
                    "severity": severity,
                    "confidence": confidence,
                    "message": self._bounded_text(item.get("issue_text"), 1000),
                    "more_info": self._bounded_text(item.get("more_info"), 1000, allow_empty=True),
                })
        errors = document.get("errors", [])
        if not isinstance(errors, list):
            raise StaticAnalysisError("A lista de erros Bandit é inválida.")
        return {
            "issues_total": len(results),
            "severity_counts": dict(sorted(severity_counts.items())),
            "confidence_counts": dict(sorted(confidence_counts.items())),
            "scanner_errors_count": len(errors),
            "issues": issues,
        }

    def _relative_report_path(self, value):
        text = self._bounded_text(value, 4096)
        candidate = Path(text)
        if not candidate.is_absolute():
            candidate = self.workspace / candidate
        try:
            return candidate.resolve(strict=False).relative_to(self.workspace).as_posix()
        except ValueError:
            return "<fora-da-pasta-base>"

    @staticmethod
    def _positive_integer(value):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise StaticAnalysisError("O relatório Bandit contém uma linha inválida.")
        return value

    @staticmethod
    def _bounded_text(value, limit, allow_empty=False):
        if not isinstance(value, str) or (not allow_empty and not value) or len(value) > limit:
            raise StaticAnalysisError("O relatório Bandit contém texto inválido.")
        return value

    @staticmethod
    def _version():
        try:
            return importlib.metadata.version("bandit")
        except importlib.metadata.PackageNotFoundError:
            return "unknown"
