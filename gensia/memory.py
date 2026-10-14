"""Memória explícita e local. Não importada pelo motor de conversação."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


class MemoryError(RuntimeError):
    pass


class MemoryStore:
    def __init__(self, path):
        self.path = Path(path).expanduser().absolute()

    @staticmethod
    def validate(value, limit, label):
        if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
            raise MemoryError(f"{label}: texto não vazio, até {limit} caracteres, sem NUL.")
        return value

    @contextmanager
    def connect(self, write=False):
        db = None
        try:
            if self.path.is_symlink():
                raise MemoryError("A base de memória não pode ser um link simbólico.")
            if write:
                self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                db = sqlite3.connect(self.path, timeout=5)
                db.execute("CREATE TABLE IF NOT EXISTS memories (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)")
            else:
                db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=5)
            db.row_factory = sqlite3.Row
            yield db
            if write:
                db.commit()
        except (sqlite3.Error, OSError) as exc:
            if db is not None:
                db.rollback()
            raise MemoryError("Não foi possível aceder à memória local; verifica o ficheiro e as permissões.") from exc
        finally:
            if db is not None:
                db.close()

    def set(self, key, value):
        self.validate(key, 100, "Chave")
        self.validate(value, 4000, "Valor")
        now = datetime.now(timezone.utc).isoformat()
        with self.connect(write=True) as db:
            db.execute(
                "INSERT INTO memories VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, value, now),
            )
        return {"saved": key}

    def get(self, key):
        self.validate(key, 100, "Chave")
        if not self.path.exists() and not self.path.is_symlink():
            return None
        with self.connect() as db:
            row = db.execute("SELECT * FROM memories WHERE key = ?", (key,)).fetchone()
            return dict(row) if row else None

    def list(self, limit=50, offset=0):
        if not 1 <= limit <= 200 or offset < 0:
            raise MemoryError("Limite: 1–200; offset não negativo.")
        if not self.path.exists() and not self.path.is_symlink():
            return []
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT key, updated_at FROM memories ORDER BY key LIMIT ? OFFSET ?", (limit, offset)
            )]

    def delete(self, key, approved=False):
        if not approved:
            raise MemoryError("Apagar memória exige --approve.")
        self.validate(key, 100, "Chave")
        if not self.path.exists() and not self.path.is_symlink():
            return {"deleted": False}
        with self.connect(write=True) as db:
            count = db.execute("DELETE FROM memories WHERE key = ?", (key,)).rowcount
        return {"deleted": count == 1}
