"""The actions an agent may take, and the limits on each. Pure planning/validation lives here (testable);
tools.py adds the approval step and calls these. Nothing here deletes or overwrites anything."""
import json, os, re, shutil, time

UNDO_DIR = os.path.expanduser("~/.cache/goop/undo")
MAX_MOVES = 200
MAX_TYPED = 400


class ActionError(Exception):
    pass


def clean_line(text):
    """One line of text to type into a shell. No newlines or control characters: Enter is a separate flag."""
    if not isinstance(text, str) or not text.strip():
        raise ActionError("text must be a non-empty string")
    if len(text) > MAX_TYPED:
        raise ActionError(f"too long to type (max {MAX_TYPED} characters)")
    if any(ord(c) < 32 and c != "\t" or ord(c) == 127 for c in text):
        raise ActionError("send one single line with no newlines or control characters; use one call per command")
    return text


def _inside(root, path):
    return path == root or path.startswith(root + os.sep)


def _nearest_existing(path):
    while not os.path.lexists(path):
        path = os.path.dirname(path)
    return path


def plan_moves(root, moves):
    """Validate moves inside `root`. Returns (plan [(src, dst)], new_dirs). Raises ActionError on anything unsafe."""
    root = os.path.realpath(root)
    if not isinstance(moves, list) or not moves:
        raise ActionError("moves must be a non-empty list of {from, to}")
    if len(moves) > MAX_MOVES:
        raise ActionError(f"too many moves at once (max {MAX_MOVES})")
    plan, dsts, new_dirs = [], set(), []
    for m in moves:
        try:
            src_in, dst_in = m["from"], m["to"]
        except (TypeError, KeyError):
            raise ActionError("each move needs 'from' and 'to'")
        src, dst = os.path.normpath(os.path.join(root, src_in)), os.path.normpath(os.path.join(root, dst_in))
        for label, p in (("from", src), ("to", dst)):
            if not _inside(root, p) or p == root:
                raise ActionError(f"{label} path {p!r} is outside the folder")
            # a symlinked parent could point anywhere, so resolve the nearest real ancestor too
            anc = os.path.realpath(_nearest_existing(os.path.dirname(p)))
            if not _inside(root, anc):
                raise ActionError(f"{label} path {p!r} goes through a link that leaves the folder")
        if not os.path.lexists(src):
            raise ActionError(f"{src_in!r} does not exist")
        if os.path.lexists(dst) or dst in dsts:
            raise ActionError(f"{dst_in!r} already exists; I never overwrite")
        if os.path.isdir(src) and not os.path.islink(src) and _inside(src, dst):
            raise ActionError(f"cannot move {src_in!r} into itself")
        dsts.add(dst)
        d = os.path.dirname(dst)
        missing = []
        while not os.path.lexists(d) and d not in new_dirs:
            missing.append(d)
            d = os.path.dirname(d)
        new_dirs += reversed(missing)
        plan.append((src, dst))
    return plan, new_dirs


def apply_moves(plan, new_dirs, root):
    """Do the moves and save an undo log. Stops at the first failure and says what was already done."""
    done_dirs, done = [], []
    try:
        for d in new_dirs:
            os.makedirs(d, exist_ok=True)
            done_dirs.append(d)
        for src, dst in plan:
            shutil.move(src, dst)
            done.append([src, dst])
    except OSError as e:
        _save_undo(root, done, done_dirs)
        raise ActionError(f"stopped after {len(done)} of {len(plan)} moves: {e}")
    _save_undo(root, done, done_dirs)
    return len(done)


def _save_undo(root, moves, dirs):
    os.makedirs(UNDO_DIR, exist_ok=True)
    path = os.path.join(UNDO_DIR, f"{time.time():.3f}.json")
    with open(path, "w") as f:
        json.dump({"root": root, "moves": moves, "dirs": dirs}, f)


def last_undo(root=None):
    try:
        names = sorted(n for n in os.listdir(UNDO_DIR) if n.endswith(".json"))
    except OSError:
        return None, None
    for n in reversed(names):
        path = os.path.join(UNDO_DIR, n)
        with open(path) as f:
            log = json.load(f)
        if root is None or os.path.realpath(root) == log["root"]:
            return path, log
    return None, None


def undo(path, log):
    """Move everything back (never over an existing file) and remove the folders we created if they are empty."""
    restored = 0
    for src, dst in reversed(log["moves"]):
        if os.path.lexists(dst) and not os.path.lexists(src):
            shutil.move(dst, src)
            restored += 1
    for d in reversed(log["dirs"]):
        try:
            os.rmdir(d)
        except OSError:
            pass
    os.rename(path, path + ".undone")
    return restored


# ---- commands safe enough to run without asking ----
# Read-only display commands only. Arguments are plain words: no quotes, $, backticks, ; & | < > ( ) { } * ? ! = or
# newlines, so nothing can chain, redirect, expand or substitute. No cat/less (they could dump secrets onto a screenshot).
_FLAG = re.compile(r"^-{1,2}[A-Za-z0-9][A-Za-z0-9-]*$")
_WORD = re.compile(r"^[A-Za-z0-9_./~@%+:,][A-Za-z0-9_./~@%+:,-]*$")   # a path, never something starting with "-"
_PLAIN = {"ls": "paths", "cd": "paths", "du": "paths", "df": "paths",
          "pwd": "flags", "whoami": "flags", "uname": "flags", "uptime": "flags", "free": "flags"}
_GIT_SUB = {"status", "log"}


def is_safe_command(line):
    parts = line.split()
    if not parts or line != " ".join(parts):      # odd spacing or tabs: not worth reasoning about
        return False
    cmd, args = parts[0], parts[1:]
    if cmd == "git":
        return (len(args) >= 1 and args[0] in _GIT_SUB
                and all(_FLAG.match(a) and "output" not in a for a in args[1:]))
    kind = _PLAIN.get(cmd)
    if kind is None:
        return False
    return all(_FLAG.match(a) or (kind == "paths" and _WORD.match(a)) for a in args)


# ---- reading files: only inside the folder the window shows, never secrets ----
READ_TEXT_BYTES = 400_000
SECRET_DIRS = {".ssh", ".gnupg", ".aws", ".kube", ".docker", ".password-store"}
_SECRET_FILE = re.compile(r"(^\.env($|\.)|\.(pem|key|p12|pfx|kdbx|gpg|asc)$|^id_(rsa|dsa|ecdsa|ed25519)|credential|^\.netrc$|^\.npmrc$|^\.pypirc$|secret|token)", re.I)
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
MAX_IMAGE_BYTES = 5_000_000
MAX_PDF_BYTES = 30_000_000


def resolve_readable(root, path):
    """The real path of `path` if it is a file inside `root` that is safe to hand to a model. Raises ActionError otherwise."""
    if not isinstance(path, str) or not path.strip():
        raise ActionError("path must be a non-empty string")
    root = os.path.realpath(root)
    asked = os.path.normpath(os.path.join(root, os.path.expanduser(path.strip())))
    real = os.path.realpath(asked)
    if not _inside(root, real):
        raise ActionError("that file is outside the folder this window shows, so I will not read it")
    parts = os.path.relpath(real, root).split(os.sep)
    if any(p in SECRET_DIRS for p in parts) or _SECRET_FILE.search(os.path.basename(real)) or _SECRET_FILE.search(os.path.basename(asked)):
        raise ActionError("that looks like a secret or credential file, so I will not read it")
    if not os.path.isfile(real):
        raise ActionError("that is not a regular file" if os.path.exists(real) else "that file does not exist")
    return real


def read_text(real, max_chars):
    """(text, total_bytes, truncated). Refuses binary files."""
    size = os.path.getsize(real)
    with open(real, "rb") as f:
        raw = f.read(READ_TEXT_BYTES)
    if b"\0" in raw[:4096]:
        raise ActionError("that is a binary file, not text")
    text = raw.decode("utf-8", errors="replace")
    return text[:max_chars], size, len(text) > max_chars or size > READ_TEXT_BYTES


def list_dir(root, path=".", cap=300):
    """Names in a folder inside `root`: [{name, kind, size}], plus how many were left out. Hidden and secret entries are skipped."""
    root = os.path.realpath(root)
    target = os.path.realpath(os.path.normpath(os.path.join(root, os.path.expanduser(path or "."))))
    if not _inside(root, target):
        raise ActionError("that folder is outside the one this window shows")
    if not os.path.isdir(target):
        raise ActionError("that is not a folder")
    out = []
    for n in sorted(os.listdir(target), key=str.lower):
        if n.startswith(".") or n in SECRET_DIRS or _SECRET_FILE.search(n):
            continue
        full = os.path.join(target, n)
        try:
            st = os.lstat(full)
        except OSError:
            continue
        out.append({"name": n, "kind": "dir" if os.path.isdir(full) and not os.path.islink(full) else "file", "size": st.st_size})
    return out[:cap], max(0, len(out) - cap)
