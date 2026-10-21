"""Memória explícita e local. Não importada pelo motor de conversação."""
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import stat


class MemoryError(RuntimeError):
    pass


class MemoryStore:
    READ_FIELDS = (('key', 100), ('value', 4000), ('updated_at', 64))
    GET_SQL = ('SELECT substr(CAST(key AS BLOB),1,401) AS key, typeof(key) AS key_type, '
               'substr(CAST(value AS BLOB),1,16001) AS value, typeof(value) AS value_type, '
               'substr(CAST(updated_at AS BLOB),1,257) AS updated_at, typeof(updated_at) AS updated_at_type '
               'FROM memories WHERE key = ? LIMIT 2')
    LIST_SQL = ('SELECT substr(CAST(key AS BLOB),1,401) AS key, typeof(key) AS key_type, '
                'substr(CAST(updated_at AS BLOB),1,257) AS updated_at, typeof(updated_at) AS updated_at_type '
                'FROM memories ORDER BY key LIMIT ? OFFSET ?')
    SEARCH_SQL = ('SELECT substr(CAST(key AS BLOB),1,401) AS key, typeof(key) AS key_type, '
                  'substr(CAST(value AS BLOB),1,16001) AS value, typeof(value) AS value_type, '
                  'substr(CAST(updated_at AS BLOB),1,257) AS updated_at, typeof(updated_at) AS updated_at_type '
                  'FROM memories WHERE instr(key, ?) > 0 OR instr(value, ?) > 0 '
                  'ORDER BY key LIMIT ? OFFSET ?')

    def __init__(self, path):
        self.path = Path(path).expanduser().absolute()

    @staticmethod
    def validate(value, limit, label):
        if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
            raise MemoryError(f"{label}: texto não vazio, até {limit} caracteres, sem NUL.")
        try:
            value.encode('utf-8', errors='strict')
        except UnicodeError:
            raise MemoryError(f"{label}: texto Unicode inválido.") from None
        return value

    @staticmethod
    def validate_pagination(limit, offset):
        # bool is an int subclass. SQLite binds integers only within signed int64.
        if (type(limit) is not int or type(offset) is not int
                or not 1 <= limit <= 200 or not 0 <= offset <= 9223372036854775807):
            raise MemoryError("Limite: inteiro 1–200; offset inteiro 0–9223372036854775807.")

    @classmethod
    def _read_record(cls, row, include_value):
        record = {}
        for name, limit in cls.READ_FIELDS:
            if name == 'value' and not include_value:
                continue
            raw = row[name]
            if row[name + '_type'] != 'text' or not isinstance(raw, bytes):
                raise MemoryError('A memória contém um registo inválido; leitura recusada.')
            try:
                text = raw.decode('utf-8', errors='strict')
                cls.validate(text, limit, 'Campo')
                if name == 'updated_at' and datetime.fromisoformat(text).utcoffset() is None:
                    raise ValueError('Timezone required')
            except (UnicodeError, ValueError, MemoryError):
                raise MemoryError('A memória contém um registo inválido; leitura recusada.') from None
            record[name] = text
        return record

    @contextmanager
    def connect(self, write=False):
        db = None
        try:
            if self.path.is_symlink():
                raise MemoryError("A base de memória não pode ser um link simbólico.")
            if write:
                self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                try:
                    descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                except FileExistsError:
                    pass
                else:
                    os.close(descriptor)
            info = self.path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise MemoryError('A memória exige ficheiro regular sem links simbólicos ou hard links adicionais.')
            mode = 'rw' if write else 'ro'
            db = sqlite3.connect(self.path.as_uri() + '?mode=' + mode, uri=True, timeout=5)
            db.execute('PRAGMA trusted_schema=OFF')
            if write:
                db.execute("CREATE TABLE IF NOT EXISTS memories (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)")
            db.row_factory = sqlite3.Row
            yield db
            if write:
                db.commit()
        except (sqlite3.Error, OSError, ValueError) as exc:
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
            rows = db.execute(self.GET_SQL, (key,)).fetchall()
            if len(rows) > 1:
                raise MemoryError('A memória contém chaves repetidas; leitura recusada.')
            return self._read_record(rows[0], True) if rows else None

    def list(self, limit=50, offset=0):
        self.validate_pagination(limit, offset)
        if not self.path.exists() and not self.path.is_symlink():
            return []
        with self.connect() as db:
            rows = db.execute(self.LIST_SQL, (limit, offset))
            return [self._read_record(row, False) for row in rows]

    def search(self, query, limit=20, offset=0):
        """Literal, case-sensitive substring search; values disclosed explicitly."""
        self.validate(query, 200, "Pesquisa")
        self.validate_pagination(limit, offset)
        if not self.path.exists() and not self.path.is_symlink():
            return []
        with self.connect() as db:
            rows = db.execute(self.SEARCH_SQL, (query, query, limit, offset))
            return [self._read_record(row, True) for row in rows]

    def delete(self, key, approved=False):
        if approved is not True:
            raise MemoryError("Apagar memória exige --approve.")
        self.validate(key, 100, "Chave")
        if not self.path.exists() and not self.path.is_symlink():
            return {"deleted": False}
        with self.connect(write=True) as db:
            count = db.execute("DELETE FROM memories WHERE key = ?", (key,)).rowcount
        return {"deleted": count == 1}
