"""Descriptor-relative, bounded document reads on supporting POSIX systems."""
from contextlib import ExitStack
import os
from pathlib import Path
import stat

DESCRIPTOR_READS_SUPPORTED = (
    os.name == 'posix'
    and all(hasattr(os, flag) for flag in ('O_NOFOLLOW', 'O_DIRECTORY', 'O_NONBLOCK'))
    and os.open in os.supports_dir_fd and os.stat in os.supports_dir_fd
    and os.stat in os.supports_follow_symlinks)


class ConfinedReadError(RuntimeError):
    pass


def _identity(info):
    return (info.st_dev, info.st_ino)


def _snapshot(info):
    return (_identity(info), info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _regular(info):
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ConfinedReadError('Apenas ficheiros regulares sem hard links adicionais são aceites.')


def read_confined(workspace, relative_path, limit, workspace_identity):
    """Do not fall back to path-based opening if a descriptor operation fails."""
    root, relative = Path(workspace), Path(relative_path)
    if (not DESCRIPTOR_READS_SUPPORTED or not root.is_absolute()
            or relative.is_absolute() or not relative.parts or '..' in relative.parts
            or '\x00' in str(relative) or len(root.parts) + len(relative.parts) > 128):
        raise ConfinedReadError('Caminho ou leitura confinada indisponível.')
    if type(limit) is not int or limit < 1:
        raise ConfinedReadError('Limite de leitura inválido.')
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with ExitStack() as handles:
        def directory(name, parent=None):
            descriptor = os.open(name, directory_flags, dir_fd=parent)
            handles.callback(os.close, descriptor)
            return descriptor
        parent = directory(root.anchor)
        for component in root.parts[1:]:
            parent = directory(component, parent)
        if _identity(os.fstat(parent)) != tuple(workspace_identity):
            raise ConfinedReadError('A pasta-base foi substituída; leitura recusada.')
        for component in relative.parts[:-1]:
            parent = directory(component, parent)
        name = relative.parts[-1]
        expected = os.stat(name, dir_fd=parent, follow_symlinks=False)
        _regular(expected)
        descriptor = os.open(name, file_flags, dir_fd=parent)
        handles.callback(os.close, descriptor)
        before = os.fstat(descriptor)
        _regular(before)
        if _snapshot(expected) != _snapshot(before):
            raise ConfinedReadError('O documento foi substituído durante a abertura.')
        if before.st_size > limit:
            raise ConfinedReadError('O documento excede o limite configurado.')
        with os.fdopen(descriptor, 'rb', closefd=False) as stream:
            raw = stream.read(limit + 1)
        after = os.fstat(descriptor)
        if len(raw) > limit:
            raise ConfinedReadError('O documento mudou e excedeu o limite durante a leitura.')
        if _snapshot(before) != _snapshot(after) or len(raw) != before.st_size:
            raise ConfinedReadError('O documento foi alterado durante a leitura; tenta novamente.')
        return raw
