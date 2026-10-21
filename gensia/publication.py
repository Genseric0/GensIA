"""Publish a complete new file without replacing a competing destination."""
import os
from pathlib import Path
import tempfile


def _publish(stage, destination):
    if os.name == 'nt':
        # Windows rename fails if the destination already exists.
        os.rename(stage, destination)
    else:
        # POSIX rename can replace a destination; link creates it exclusively.
        os.link(stage, destination, follow_symlinks=False)


def _sync_parent(parent):
    if os.name != 'posix':
        return None  # No portable directory fsync on Windows.
    descriptor = None
    try:
        descriptor = os.open(parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        os.fsync(descriptor)
        return True
    except OSError:
        return False
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                return False  # Report a warning; publication already completed.


def publish_new(destination, writer):
    """writer receives a private binary stream; only a flushed file is published.

    Parent directories must be trusted. This is not protection from a hostile
    process with the same privileges or a promise about storage hardware.
    """
    path = Path(destination)
    if path.is_symlink() or path.exists():
        raise FileExistsError('Destination already exists')
    published = False
    cleaned = True
    try:
        with tempfile.TemporaryDirectory(prefix='.gensia-publish-', dir=path.parent) as temporary:
            stage = Path(temporary) / 'content'
            descriptor = os.open(stage, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(descriptor, 'wb') as output:
                    descriptor = None
                    writer(output)
                    output.flush()
                    os.fsync(output.fileno())
            finally:
                if descriptor is not None:
                    os.close(descriptor)
            _publish(stage, path)
            published = True
        # Cleanup also removes the private hard link on POSIX before return.
    except OSError:
        if not published:
            raise
        cleaned = False
    directory_synced = _sync_parent(path.parent)
    warnings = []
    if not cleaned:
        warnings.append('staging_cleanup_failed')
    if directory_synced is False:
        warnings.append('directory_sync_failed')
    return {'destination_published': True, 'file_synced': True,
            'directory_synced': directory_synced, 'staging_cleaned': cleaned,
            'warnings': warnings, 'do_not_retry': bool(warnings)}
