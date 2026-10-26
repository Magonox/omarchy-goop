"""File-manager windows. Nautilus only exposes the folder *name* in its title, so the path is resolved."""
import mimetypes, os, time
from collections import Counter

LIST_CAP = 200
SEARCH_DEPTH = 3
SEARCH_BUDGET = 3000  # directories visited
SKIP = {"node_modules", ".cache", ".git", ".local", ".cargo", ".rustup", ".npm", "target"}


def resolve(title, home=None):
    """(path, confidence, candidates) from a window title."""
    home = home or os.path.expanduser("~")
    t = (title or "").strip()
    if t == "Home":
        return home, "high", []
    if t.startswith(("/", "~")):
        p = os.path.expanduser(t)
        return (p, "high", []) if os.path.isdir(p) else (None, "low", [])
    found, visited = [], 0
    for root, dirs, _ in os.walk(home):
        depth = root[len(home):].count(os.sep)
        dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith(".")] if depth < SEARCH_DEPTH else []
        visited += 1
        if os.path.basename(root) == t and root != home:
            found.append(root)
        if visited > SEARCH_BUDGET:
            break
    found.sort(key=lambda p: p.count(os.sep))
    if not found:
        return None, "low", []
    return found[0], ("high" if len(found) == 1 else "medium"), found[1:]


def listing(path):
    entries, hidden = [], 0
    try:
        names = sorted(os.listdir(path), key=str.lower)
    except OSError as e:
        return {"error": str(e)}
    for n in names:
        if n.startswith("."):
            hidden += 1
            continue
        p = os.path.join(path, n)
        try:
            st = os.lstat(p)
        except OSError:
            continue
        kind = "dir" if os.path.isdir(p) and not os.path.islink(p) else ("link" if os.path.islink(p) else "file")
        entries.append({
            "name": n, "kind": kind, "size": st.st_size,
            "mtime": time.strftime("%Y-%m-%d", time.localtime(st.st_mtime)),
            "mime": mimetypes.guess_type(n)[0] if kind != "dir" else None,
        })
    entries.sort(key=lambda e: (e["kind"] != "dir", e["name"].lower()))
    ext = Counter(os.path.splitext(e["name"])[1].lower() or "(none)" for e in entries if e["kind"] != "dir")
    return {
        "total": len(entries), "hidden_skipped": hidden,
        "truncated": len(entries) > LIST_CAP,
        "extensions": dict(ext.most_common(15)),
        "entries": entries[:LIST_CAP],
    }


def collect(window, home=None):
    path, conf, others = resolve(window.get("title", ""), home)
    if not path:
        return {"notes": [f"could not resolve a folder for title {window.get('title')!r}"]}, "low"
    notes = ["path inferred from the window title"] if conf != "high" or others else []
    if others:
        notes.append("other folders share this name; picked the shallowest")
    return {"path": path, "alternatives": others, "listing": listing(path), "notes": notes}, conf
