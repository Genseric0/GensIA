"""Offline rollback recovery on a private copy; never opens the source in SQLite."""
from contextlib import closing
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
import time

from .memory import MemoryError, MemoryStore
from .memory_backup import backup_notes
from .memory_check import check_memory, MAX_CHECK_SECONDS, MAX_VM_STEPS, PROGRESS_INTERVAL
from .memory_restore import restore_notes, ensure_new_database
from .publication import publish_new

MAX_RECOVERY_BYTES = 64 * 1024 * 1024  # Per source file; never allocate it all at once.
JOURNAL_MAGIC = bytes.fromhex('d9d505f920a163d7')


def _exists(path):
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False


def _inventory(source):
    if any(_exists(Path(str(source) + suffix)) for suffix in ('-wal', '-shm')):
        raise MemoryError('Recuperação offline não suporta WAL/SHM; preservar todos os ficheiros.')
    journal = Path(str(source) + '-journal')
    return [source, journal] if _exists(journal) else [source]


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_nlink)


def _read_source(path, output=None):
    """Bounded byte copy/hash, with identity and mutation checks around the read."""
    descriptor = None
    try:
        if path.is_symlink():
            raise MemoryError('Origem exige ficheiros regulares sem links.')
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                             | getattr(os, 'O_NONBLOCK', 0))
        before = os.fstat(descriptor)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or before.st_size > MAX_RECOVERY_BYTES):
            raise MemoryError('Origem exige ficheiros regulares sem links, até 64 MiB cada.')
        digest = hashlib.sha256()
        count = 0
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            while True:
                chunk = stream.read(64 * 1024)
                if not chunk:
                    break
                count += len(chunk)
                if count > MAX_RECOVERY_BYTES:
                    raise MemoryError('Origem excedeu o limite durante a leitura.')
                digest.update(chunk)
                if output is not None:
                    output.write(chunk)
            after = os.fstat(stream.fileno())
        if (count != before.st_size or _signature(before) != _signature(after)
                or path.is_symlink() or _signature(path.lstat()) != _signature(before)):
            raise MemoryError('Origem alterada durante a leitura; recuperação recusada.')
        return {'signature': _signature(before), 'sha256': digest.hexdigest()}
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _verify_sources(source, snapshots):
    if _inventory(source) != list(snapshots):
        raise MemoryError('Conjunto de ficheiros da origem mudou; recuperação recusada.')
    for path, expected in snapshots.items():
        if _read_source(path) != expected:
            raise MemoryError('Origem alterada; cópia não será publicada.')


def _guard_copy(database):
    with database.open('rb') as stream:
        header = stream.read(100)
    if (len(header) != 100 or header[:16] != b'SQLite format 3\x00'
            or header[18:20] != b'\x01\x01'):
        raise MemoryError('Só são suportadas bases GensIA em modo rollback, sem WAL.')
    journal = Path(str(database) + '-journal')
    if journal.exists():
        with journal.open('rb') as stream:
            journal_header = stream.read(28)
            if journal.stat().st_size >= 8:
                stream.seek(-8, os.SEEK_END)
                tail = stream.read(8)
            else:
                tail = b''
            if tail == JOURNAL_MAGIC:
                # readSuperJournal in SQLite recognizes its pointer by this tail.
                # Never allow recovery to follow an external super-journal path.
                raise MemoryError('Journal multi-base/super-journal não suportado; preservar a origem.')
        if journal_header and any(journal_header):
            if len(journal_header) != 28 or journal_header[:8] != JOURNAL_MAGIC:
                raise MemoryError('Header do journal inválido; recuperação recusada.')
            original_pages = int.from_bytes(journal_header[16:20], 'big')
            sector = int.from_bytes(journal_header[20:24], 'big')
            page_size = int.from_bytes(journal_header[24:28], 'big')
            if page_size == 0:  # Legacy journals use the database page size.
                page_size = int.from_bytes(header[16:18], 'big')
                page_size = 65536 if page_size == 1 else page_size
            if (not 512 <= page_size <= 65536 or page_size & (page_size - 1)
                    or not 512 <= sector <= 65536 or sector & (sector - 1)
                    or original_pages * page_size > MAX_RECOVERY_BYTES):
                raise MemoryError('Journal excede os limites de tamanho/formato da recuperação.')


def _recover_private(database):
    deadline = time.monotonic() + MAX_CHECK_SECONDS
    steps = 0
    def over_budget():
        nonlocal steps
        steps += PROGRESS_INTERVAL
        return int(steps >= MAX_VM_STEPS or time.monotonic() >= deadline)
    with closing(sqlite3.connect(database.as_uri() + '?mode=rw', uri=True, timeout=2)) as db:
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1024 * 1024)
        db.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 65536)
        db.setlimit(sqlite3.SQLITE_LIMIT_EXPR_DEPTH, 50)
        db.set_progress_handler(over_budget, PROGRESS_INTERVAL)
        db.execute('PRAGMA trusted_schema=OFF')
        # This read can roll back the private journal. No source SQLite handle.
        db.execute('PRAGMA schema_version').fetchone()
        objects = set(db.execute('SELECT type,name,tbl_name FROM sqlite_schema LIMIT 3'))
        if objects != {('table', 'memories', 'memories'),
                       ('index', 'sqlite_autoindex_memories_1', 'memories')}:
            raise MemoryError('Esquema de memória personalizado não suportado na recuperação.')
        if time.monotonic() >= deadline:
            raise MemoryError('Recuperação da cópia excedeu o orçamento cooperativo.')


def recover_copy(store: MemoryStore, destination, approved=False, source_stopped=False):
    if approved is not True or source_stopped is not True:
        raise MemoryError('Recuperação exige --approve e --source-stopped após parar todos os acessos à origem.')
    if not hasattr(sqlite3.Connection, 'setlimit'):
        raise MemoryError('Recuperação requer Python 3.11 ou superior.')
    publication = None
    try:
        target = Path(destination).expanduser().absolute()
        ensure_new_database(target)
        sources = _inventory(store.path)
        snapshots = {}
        with tempfile.TemporaryDirectory(prefix='.gensia-recovery-', dir=target.parent) as temporary:
            root = Path(temporary)
            database = root / 'snapshot.sqlite3'
            for source in sources:
                copy = database if source == store.path else Path(str(database) + '-journal')
                # Temporary directory is private; descriptors are exclusive and 0600.
                descriptor = os.open(copy, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, 'wb') as output:
                    snapshots[source] = _read_source(source, output)
                with copy.open('rb') as copied:
                    if hashlib.file_digest(copied, 'sha256').hexdigest() != snapshots[source]['sha256']:
                        raise MemoryError('Hash da cópia não corresponde à origem.')
            _verify_sources(store.path, snapshots)
            _guard_copy(database)
            _recover_private(database)
            check_memory(MemoryStore(database))
            # Normalize notes into a fresh schema; never publish arbitrary schema.
            logical = root / 'notes.json'
            backup = backup_notes(MemoryStore(database), logical)
            normalized = root / 'normalized.sqlite3'
            restored = restore_notes(MemoryStore(normalized), logical, approved=True)
            if backup['warnings'] or restored['warnings'] or not restored['restored']:
                raise MemoryError('Preparação da cópia não confirmada; destino não publicado.')
            checked = check_memory(MemoryStore(normalized))
            _verify_sources(store.path, snapshots)
            ensure_new_database(target)
            def writer(output):
                with normalized.open('rb') as input_stream:
                    shutil.copyfileobj(input_stream, output, length=64 * 1024)
            publication = publish_new(target, writer)
    except (OSError, sqlite3.Error) as exc:
        if publication is None:
            raise MemoryError('Recuperação não publicada; preservar origem e auxiliares. Pode existir área temporária incompleta.') from exc
        publication['staging_cleaned'] = False
        publication['warnings'].append('recovery_cleanup_failed')
        publication['do_not_retry'] = True
    return {'recovered': publication['staging_cleaned'],
            'notes_checked': checked['notes_checked'], 'normalized_schema': True,
            'source_files_checked': len(snapshots), 'source_hashes_verified': True,
            'source_sqlite_opened': False, 'source_mutations_requested': False,
            'source_stopped_asserted': True, 'source_quiescence_enforced': False,
            'note_contents_returned': False, 'encrypted': False, **publication}
