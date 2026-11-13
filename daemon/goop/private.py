"""Owner-only storage for what Goop keeps under ~/.cache/goop.

Questions, answers, window text, screenshots, saved sessions and the tool-call log are private. Folders are created
mode 0700 and files 0600, so another local account cannot read them even when a parent folder (such as the home
folder) is traversable. Every folder from ~/.cache/goop down is tightened, including ones an older version created
with looser modes, so an upgrade fixes existing installs the next time Goop writes.

All code that writes under ~/.cache/goop uses makedirs() and open_file() from here. A plain os.makedirs could create
the root folder world-readable before anything else runs.
"""
import os

CACHE = os.path.expanduser("~/.cache/goop")


def _tighten(path):
    """Remove group and other access from a folder (never adds any)."""
    try:
        if os.stat(path).st_mode & 0o077:
            os.chmod(path, 0o700)
    except OSError:
        pass


def makedirs(path):
    """os.makedirs(path, exist_ok=True) with every Goop-owned folder owner-only (0700).

    Inside ~/.cache/goop each folder from the root down is created or tightened. Elsewhere only the new folder is
    created 0700; an existing folder outside the cache is left as it is."""
    path = os.path.abspath(os.path.expanduser(path))
    if path != CACHE and not path.startswith(CACHE + os.sep):
        os.makedirs(path, mode=0o700, exist_ok=True)
        return
    current = CACHE
    os.makedirs(current, mode=0o700, exist_ok=True)
    _tighten(current)
    for part in os.path.relpath(path, CACHE).split(os.sep):
        if part == os.curdir:
            continue
        current = os.path.join(current, part)
        os.makedirs(current, mode=0o700, exist_ok=True)
        _tighten(current)


def open_file(path, mode="w"):
    """open(path, mode) for "w" or "a", creating the file 0600 and tightening one that already exists."""
    if mode not in ("w", "a"):
        raise ValueError("private.open_file supports 'w' and 'a'")
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if mode == "a" else os.O_TRUNC)
    fd = os.open(path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
    except OSError:
        pass
    return os.fdopen(fd, mode)
