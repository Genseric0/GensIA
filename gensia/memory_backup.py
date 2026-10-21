"""Explicit, bounded logical export of local notes. No automatic scheduling."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from .memory import MemoryError, MemoryStore
from .publication import publish_new

MAX_NOTES = 1000
MAX_BACKUP_BYTES = 8 * 1024 * 1024
BACKUP_SQL = ('SELECT substr(CAST(key AS BLOB),1,401) AS key, typeof(key) AS key_type, '
              'substr(CAST(value AS BLOB),1,16001) AS value, typeof(value) AS value_type, '
              'substr(CAST(updated_at AS BLOB),1,257) AS updated_at, typeof(updated_at) AS updated_at_type '
              'FROM memories ORDER BY key LIMIT ?')


def backup_notes(store: MemoryStore, destination):
    # One SELECT, one read-only connection: values from the same SQLite read.
    # BLOB slicing preserves NUL for validation instead of truncating text at NUL.
    with store.connect() as db:
        rows = db.execute(BACKUP_SQL, (MAX_NOTES + 1,)).fetchall()
    if len(rows) > MAX_NOTES:
        raise MemoryError("Backup excede 1000 notas; nenhum ficheiro foi criado.")
    notes = [MemoryStore._read_record(row, True) for row in rows]
    if len({note['key'] for note in notes}) != len(notes):
        raise MemoryError('A memória contém chaves repetidas; backup recusado.')
    document = {'schema_version': 1, 'kind': 'gensia.memory_backup',
                'exported_at': datetime.now(timezone.utc).isoformat(), 'notes': notes}
    try:
        raw = (json.dumps(document, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    except UnicodeError as exc:
        raise MemoryError("A memória contém texto inválido; backup recusado.") from exc
    if len(raw) > MAX_BACKUP_BYTES:
        raise MemoryError("Backup excede 8 MiB; nenhum ficheiro foi criado.")
    try:
        path = Path(destination)
        if path.is_symlink():
            raise MemoryError('Destino do backup não pode ser link simbólico.')
        publication = publish_new(path, lambda output: output.write(raw))
    except FileExistsError as exc:
        raise MemoryError("Destino já existe; backup não substituiu ficheiros.") from exc
    except OSError as exc:
        raise MemoryError("Backup falhou antes da publicação; pode existir uma área temporária incompleta.") from exc
    return {'backup_created': True, 'notes_count': len(notes), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(), 'encrypted': False, **publication}
