"""Process-tree helpers over /proc."""
import os


def _stat(pid):
    try:
        with open(f"/proc/{pid}/stat") as f:
            raw = f.read()
    except OSError:
        return None
    head, _, rest = raw.rpartition(")")  # the name may contain spaces/parens
    fields = rest.split()
    return {"pid": int(pid), "name": head.split("(", 1)[1], "ppid": int(fields[1]), "start": int(fields[19])}


def snapshot():
    snap = {}
    for d in os.listdir("/proc"):
        if d.isdigit():
            s = _stat(d)
            if s:
                snap[s["pid"]] = s
    return snap


def children(snap, pid):
    return sorted((p for p in snap.values() if p["ppid"] == pid), key=lambda p: p["start"])


def descendants(snap, pid):
    """Breadth-first, oldest first within each level."""
    out, queue = [], [pid]
    while queue:
        nxt = []
        for q in queue:
            for c in children(snap, q):
                out.append(c)
                nxt.append(c["pid"])
        queue = nxt
    return out


def cwd(pid):
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        return None
