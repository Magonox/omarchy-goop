"""Window screenshots via grim, kept in a cache dir and pruned after an hour."""
import os, subprocess, time

from . import private

DIR = os.path.expanduser("~/.cache/goop/shots")
MAX_AGE = 3600


def prune():
    now = time.time()
    for f in os.listdir(DIR):
        p = os.path.join(DIR, f)
        if now - os.path.getmtime(p) > MAX_AGE:
            os.remove(p)


def capture(window):
    private.makedirs(DIR)
    prune()
    (x, y), (w, h) = window["at"], window["size"]
    path = os.path.join(DIR, f"{int(time.time())}-{window['pid']}.png")
    try:
        # -s 1: logical resolution, keeps images (and tokens) small on a 2x display
        subprocess.run(["grim", "-s", "1", "-g", f"{x},{y} {w}x{h}", path], check=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        os.chmod(path, 0o600)            # grim writes it with the default mode
    except OSError:
        pass
    return path
