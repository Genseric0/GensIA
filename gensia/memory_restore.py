"""Validate JSON notes and restore to a new SQLite file exclusively."""
from contextlib import closing
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile

from .memory import MemoryError, MemoryStore
from .memory_backup import MAX_BACKUP_BYTES, MAX_NOTES


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise MemoryError('Backup contém campos JSON duplicados.')
        result[key] = value
    return result


def _reject_number(value):
    raise ValueError('Unsupported number')


def _small_integer(value):
    if len(value) > 10:
        raise ValueError('Integer too long')
    return int(value)


def _date(value):
    MemoryStore.validate(value, 64, 'Data')
    if datetime.fromisoformat(value).utcoffset() is None:
        raise ValueError('Timezone missing')


def _load_backup(source):
    descriptor = None
    try:
        path = Path(source)
        if path.is_symlink():
            raise MemoryError('Backup não pode ser link simbólico.')
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                             | getattr(os, 'O_NONBLOCK', 0))
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BACKUP_BYTES:
            raise MemoryError('Backup deve ser um ficheiro regular de até 8 MiB.')
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            raw = stream.read(MAX_BACKUP_BYTES + 1)
        if len(raw) > MAX_BACKUP_BYTES:
            raise MemoryError('Backup excedeu 8 MiB durante a leitura.')
        document = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                              parse_int=_small_integer, parse_float=_reject_number,
                              parse_constant=_reject_number)
        if (not isinstance(document, dict)
                or set(document) != {'schema_version', 'kind', 'exported_at', 'notes'}
                or type(document['schema_version']) is not int
                or document['schema_version'] != 1
                or document['kind'] != 'gensia.memory_backup'):
            raise MemoryError('Formato ou versão do backup inválidos.')
        _date(document['exported_at'])
        notes = document['notes']
        if not isinstance(notes, list) or len(notes) > MAX_NOTES:
            raise MemoryError('Backup deve conter até 1000 notas.')
        keys = set()
        for note in notes:
            if not isinstance(note, dict) or set(note) != {'key', 'value', 'updated_at'}:
                raise MemoryError('Estrutura de nota inválida.')
            MemoryStore.validate(note['key'], 100, 'Chave')
            MemoryStore.validate(note['value'], 4000, 'Valor')
            _date(note['updated_at'])
            for value in note.values():
                value.encode('utf-8')  # Reject isolated surrogate escapes.
            if note['key'] in keys:
                raise MemoryError('Backup contém chaves de notas duplicadas.')
            keys.add(note['key'])
        return notes, hashlib.sha256(raw).hexdigest()
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        raise MemoryError('Não foi possível ler ou validar o backup local.') from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def restore_notes(store: MemoryStore, source, approved=False):
    if approved is not True:
        raise MemoryError('Restauro exige --approve e uma base de destino nova.')
    notes, source_hash = _load_backup(source)
    descriptor = None
    try:
        # Build a fresh schema privately. Never open the destination through
        # SQLite: copy the completed database to our exclusively owned handle.
        with tempfile.TemporaryDirectory(prefix='gensia-restore-') as temp:
            staged = Path(temp) / 'memory.sqlite3'
            with closing(sqlite3.connect(staged)) as db:
                with db:
                    db.execute('CREATE TABLE memories (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)')
                    db.executemany('INSERT INTO memories VALUES (?, ?, ?)',
                                   [(n['key'], n['value'], n['updated_at']) for n in notes])
                if db.execute('PRAGMA integrity_check').fetchone() != ('ok',):
                    raise MemoryError('A base temporária não passou a verificação de integridade.')
            descriptor = os.open(store.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as output:
                descriptor = None
                with staged.open('rb') as input_stream:
                    shutil.copyfileobj(input_stream, output, length=64 * 1024)
                output.flush()
                os.fsync(output.fileno())
    except FileExistsError as exc:
        raise MemoryError('Destino já existe; nenhuma base foi substituída.') from exc
    except (OSError, sqlite3.Error) as exc:
        raise MemoryError('Restauro falhou. Pode ter ficado uma nova base incompleta; a origem foi preservada.') from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return {'restored': True, 'notes_count': len(notes), 'backup_sha256': source_hash,
            'encrypted': False}
