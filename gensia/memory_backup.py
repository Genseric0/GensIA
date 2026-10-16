"""Explicit, bounded logical export of local notes. No automatic scheduling."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from .memory import MemoryError, MemoryStore

MAX_NOTES = 1000
MAX_BACKUP_BYTES = 8 * 1024 * 1024


def backup_notes(store: MemoryStore, destination):
    # One SELECT, one read-only connection: values from the same SQLite read.
    # Substrings bound data materialized into Python even for malformed rows.
    with store.connect() as db:
        rows = db.execute(
            "SELECT substr(key, 1, 101) AS key, substr(value, 1, 4001) AS value, "
            "substr(updated_at, 1, 65) AS updated_at FROM memories ORDER BY key LIMIT ?",
            (MAX_NOTES + 1,),
        ).fetchall()
    if len(rows) > MAX_NOTES:
        raise MemoryError("Backup excede 1000 notas; nenhum ficheiro foi criado.")
    notes = []
    for row in rows:
        note = dict(row)
        MemoryStore.validate(note['key'], 100, 'Chave')
        MemoryStore.validate(note['value'], 4000, 'Valor')
        MemoryStore.validate(note['updated_at'], 64, 'Data')
        try:
            timestamp = datetime.fromisoformat(note['updated_at'])
            if timestamp.utcoffset() is None:
                raise ValueError('Missing timezone')
        except ValueError as exc:
            raise MemoryError("A memória contém uma data inválida; backup recusado.") from exc
        notes.append(note)
    document = {'schema_version': 1, 'kind': 'gensia.memory_backup',
                'exported_at': datetime.now(timezone.utc).isoformat(), 'notes': notes}
    try:
        raw = (json.dumps(document, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    except UnicodeError as exc:
        raise MemoryError("A memória contém texto inválido; backup recusado.") from exc
    if len(raw) > MAX_BACKUP_BYTES:
        raise MemoryError("Backup excede 8 MiB; nenhum ficheiro foi criado.")
    descriptor = None
    try:
        # Exclusive creation also refuses existing and dangling symlinks.
        descriptor = os.open(Path(destination), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as output:
            descriptor = None
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
    except FileExistsError as exc:
        raise MemoryError("Destino já existe; backup não substituiu ficheiros.") from exc
    except OSError as exc:
        raise MemoryError("Não foi possível gravar o backup. Pode ter ficado um novo ficheiro incompleto.") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return {'backup_created': True, 'notes_count': len(notes), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(), 'encrypted': False}
