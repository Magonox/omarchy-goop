"""Describe a directory as a project: markers, CLAUDE.md, git state, Claude sessions."""
import os, subprocess

MARKERS = ["CLAUDE.md", ".claude", ".git", "package.json", "pyproject.toml", "Cargo.toml", "go.mod", "Makefile"]
CLAUDE_MD_CAP = 4000
LIST_CAP = 100


def encode_cwd(path):
    """Claude Code names a project's session dir after its cwd: '/' and '.' become '-'."""
    return path.replace("/", "-").replace(".", "-")


def latest_session(cwd, projects_dir=None):
    d = os.path.join(projects_dir or os.path.expanduser("~/.claude/projects"), encode_cwd(cwd))
    try:
        files = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".jsonl")]
    except OSError:
        return None
    if not files:
        return None
    newest = max(files, key=os.path.getmtime)
    return {"id": os.path.basename(newest)[:-6], "path": newest, "mtime": os.path.getmtime(newest)}


def _git(cwd, *args):
    try:
        r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=3,
                           env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def describe(cwd, home=None, projects_dir=None):
    home = home or os.path.expanduser("~")
    markers = [m for m in MARKERS if os.path.exists(os.path.join(cwd, m))]
    info = {"cwd": cwd, "markers": markers}
    # $HOME is where terminals start; it is not a project even if it has a stray marker
    info["is_project"] = bool(markers) and os.path.realpath(cwd) != os.path.realpath(home)
    info["is_claude_project"] = info["is_project"] and ("CLAUDE.md" in markers or ".claude" in markers)
    try:
        with open(os.path.join(cwd, "CLAUDE.md")) as f:
            info["claude_md"] = f.read(CLAUDE_MD_CAP)
    except OSError:
        pass
    try:
        names = sorted(n for n in os.listdir(cwd) if not n.startswith("."))
    except OSError:
        names = []
    info["files"] = names[:LIST_CAP]
    info["files_truncated"] = len(names) > LIST_CAP
    if ".git" in markers:
        status = _git(cwd, "status", "--porcelain")
        info["git"] = {
            "branch": _git(cwd, "rev-parse", "--abbrev-ref", "HEAD"),
            "status": (status or "").splitlines()[:50],
            "recent": (_git(cwd, "log", "--oneline", "-5") or "").splitlines(),
        }
    sess = latest_session(cwd, projects_dir)
    if sess:
        info["claude_session"] = sess
    return info
