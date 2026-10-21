"""Explicit, read-only memory validation; never repairs or exports note content."""
import sqlite3
import time

from .memory import MemoryError, MemoryStore
from .memory_backup import BACKUP_SQL, MAX_NOTES

MAX_CHECK_SECONDS = 2.0
MAX_VM_STEPS = 2_000_000
PROGRESS_INTERVAL = 1000


def check_memory(store: MemoryStore):
    deadline = time.monotonic() + MAX_CHECK_SECONDS
    steps = 0

    def stop_if_over_budget():
        nonlocal steps
        steps += PROGRESS_INTERVAL
        return int(steps >= MAX_VM_STEPS or time.monotonic() >= deadline)

    try:
        with store.connect() as db:
            if not hasattr(db, 'setlimit'):
                raise MemoryError('Verificação requer Python 3.11 ou superior para limitar o SQLite.')
            # Integrity checks may evaluate schema CHECK expressions. Bound SQL,
            # rows/strings/blobs and expression nesting before reading the schema.
            db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1024 * 1024)
            db.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 65536)
            db.setlimit(sqlite3.SQLITE_LIMIT_EXPR_DEPTH, 50)
            db.set_progress_handler(stop_if_over_budget, PROGRESS_INTERVAL)
            try:
                # One snapshot, including WAL commits. No checkpoints or repair.
                db.execute('PRAGMA query_only=ON')
                db.execute('BEGIN')
                ordinary = db.execute(
                    "SELECT 1 FROM sqlite_schema WHERE name='memories' "
                    "AND type='table' AND rootpage>0 LIMIT 1"
                ).fetchone()
                if ordinary is None:
                    raise MemoryError('Verificação recusada: tabela de memória incompatível.')
                seen = set()
                for row in db.execute(BACKUP_SQL, (MAX_NOTES + 1,)):
                    if len(seen) >= MAX_NOTES:
                        raise MemoryError('Verificação incompleta: limite de 1000 notas excedido.')
                    note = MemoryStore._read_record(row, True)
                    if note['key'] in seen:
                        raise MemoryError('Verificação falhou: existem chaves de memória repetidas.')
                    seen.add(note['key'])
                # Full SQLite check also covers index consistency and UNIQUE.
                result = db.execute('PRAGMA integrity_check(1)').fetchmany(2)
                if len(result) != 1 or result[0][0] != 'ok':
                    raise MemoryError('Verificação falhou: integridade SQLite não confirmada.')
                if time.monotonic() >= deadline:
                    raise MemoryError('Verificação incompleta: prazo de processamento excedido.')
            finally:
                db.set_progress_handler(None, 0)
    except sqlite3.Error:
        raise MemoryError('Verificação não concluída: SQLite indisponível, inválido ou orçamento excedido.') from None
    return {'ok': True, 'sqlite_integrity': 'ok', 'notes_checked': len(seen),
            'snapshot': 'single_read_transaction', 'mutations_requested': False,
            'note_contents_returned': False, 'foreign_keys_checked': False,
            'recovery_tested': False}
