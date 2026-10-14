"""Ferramentas locais explícitas; não aceitam comandos livres do modelo."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


class ToolError(RuntimeError):
    pass


class ToolPermissionError(ToolError):
    pass


class AuditLogger:
    """Regista a ação sem guardar caminhos, argumentos ou conteúdo."""
    def __init__(self, path):
        self.path = Path(path)

    def record(self, action, outcome, target):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and self.path.is_symlink():
            raise ToolError("O ficheiro de auditoria não pode ser um link simbólico.")
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "outcome": outcome,
            "target_fingerprint": hashlib.sha256(target.encode("utf-8")).hexdigest()[:12],
        }
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
        descriptor = os.open(self.path, flags, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")


class SafeDirectoryTools:
    def __init__(self, workspace, audit):
        try:
            self.workspace = Path(workspace).expanduser().resolve(strict=True)
        except OSError as exc:
            raise ToolError("A pasta-base não existe ou não está acessível.") from exc
        if not self.workspace.is_dir():
            raise ToolError("A pasta-base deve ser um diretório.")
        self.audit = audit

    def list_directory(self, relative_path=".", limit=200):
        if not 1 <= limit <= 500:
            raise ToolError("O limite deve estar entre 1 e 500.")
        candidate = Path(relative_path)
        if candidate.is_absolute():
            self._audit("list_directory", "denied", str(candidate))
            raise ToolPermissionError("Usa um caminho relativo à pasta-base.")
        try:
            target = (self.workspace / candidate).resolve(strict=True)
        except OSError as exc:
            self._audit("list_directory", "error", str(candidate))
            raise ToolError("A pasta pedida não existe ou não está acessível.") from exc
        if not target.is_relative_to(self.workspace):
            self._audit("list_directory", "denied", str(candidate))
            raise ToolPermissionError("O caminho sai da pasta-base autorizada.")
        if not target.is_dir():
            self._audit("list_directory", "error", str(candidate))
            raise ToolError("O caminho pedido não é uma pasta.")
        entries = []
        try:
            selected = sorted(target.iterdir(), key=lambda item: item.name.casefold())[:limit + 1]
            truncated = len(selected) > limit
            children = selected[:limit]
            for child in children:
                stat = child.lstat()
                kind = "symlink" if child.is_symlink() else (
                    "directory" if child.is_dir() else "file" if child.is_file() else "other"
                )
                entries.append({"name": child.name, "type": kind,
                                "size": stat.st_size if kind == "file" else None})
        except OSError as exc:
            self._audit("list_directory", "error", str(candidate))
            raise ToolError("Não foi possível listar a pasta.") from exc
        self._audit("list_directory", "success", str(candidate))
        return {"path": str(candidate), "count": len(entries), "entries": entries,
                "truncated": truncated}

    def _audit(self, action, outcome, target):
        self.audit.record(action, outcome, target)


class AppLauncher:
    WINDOWS_APPS = {
        "calculator": ["calc.exe"],
        "notepad": ["notepad.exe"],
        "files": ["explorer.exe"],
    }

    def __init__(self, audit, platform_name=None, runner=None):
        self.audit = audit
        self.platform_name = platform_name or sys.platform
        self.runner = runner or subprocess.Popen

    def open(self, app, approved=False):
        if app not in self.WINDOWS_APPS:
            self.audit.record("open_app", "denied", app)
            raise ToolPermissionError("Aplicação não autorizada.")
        if not approved:
            self.audit.record("open_app", "denied", app)
            raise ToolPermissionError("A abertura exige confirmação explícita com --approve.")
        if self.platform_name != "win32":
            self.audit.record("open_app", "unsupported", app)
            raise ToolError("A abertura de aplicações está implementada apenas para Windows.")
        try:
            self.runner(self.WINDOWS_APPS[app], shell=False, close_fds=True)
        except OSError as exc:
            self.audit.record("open_app", "error", app)
            raise ToolError("O Windows não conseguiu abrir a aplicação.") from exc
        self.audit.record("open_app", "success", app)
        return {"opened": app, "approved": True}
