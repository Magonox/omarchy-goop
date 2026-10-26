"""Terminal windows: find the shell/program behind the window, then describe its cwd as a project."""
import os, subprocess

from .. import proc, project

FOREGROUND = {"claude", "nvim", "vim", "tmux", "ssh", "htop", "btop"}


def candidates(snap, root_pid):
    """One entry per shell under the terminal process (terminals like ghostty share one pid)."""
    out = []
    for shell in proc.children(snap, root_pid):
        prog = next((d for d in proc.descendants(snap, shell["pid"]) if d["name"] in FOREGROUND), None)
        target = prog or shell
        out.append({
            "shell_pid": shell["pid"],
            "program": prog["name"] if prog else None,
            "program_pid": prog["pid"] if prog else None,
            "cwd": proc.cwd(target["pid"]) or proc.cwd(shell["pid"]),
            "start": shell["start"],
        })
    return [c for c in out if c["cwd"]]


SPINNERS = "✳✻✽✶✢·◐◓◑◒⠂⠐⠠⠄⠁⠈"   # Claude Code puts a spinner glyph at the start of its terminal title


def score(cand, title, home=None):
    """How well a title says "this window is that shell". Higher is better."""
    home = home or os.path.expanduser("~")
    t, cwd, prog = title.strip(), cand["cwd"], cand["program"]
    sc = 0
    if os.path.basename(cwd).lower() in title.lower() and cwd != home:
        sc += 2
    if cwd in t or (t in ("~", "") and cwd == home) or (t.startswith("~") and os.path.expanduser(t) == cwd):
        sc += 2
    claude_title = bool(t) and t[0] in SPINNERS
    if claude_title:
        sc += 3 if prog == "claude" else -2
    elif prog == "claude":
        sc -= 1  # a plain-looking title is more likely an idle shell
    if prog in ("nvim", "vim") and prog in t.lower():
        sc += 3
    return sc


def pick(cands, title):
    """Best candidate for a window title. Returns (candidate, confident)."""
    if not cands:
        return None, False
    if len(cands) == 1:
        return cands[0], True
    ranked = sorted(cands, key=lambda c: (score(c, title), c["start"]), reverse=True)
    top, second = score(ranked[0], title), score(ranked[1], title)
    return ranked[0], top > second


def _tmux_text(snap, shell_pid):
    """Visible text of the tmux pane attached under this shell, if any."""
    try:
        out = subprocess.run(["tmux", "list-clients", "-F", "#{client_pid} #{session_name}"],
                             capture_output=True, text=True, timeout=2).stdout.split("\n")
        mine = {d["pid"] for d in proc.descendants(snap, shell_pid)}
        for line in out:
            pid, _, session = line.partition(" ")
            if pid.isdigit() and int(pid) in mine:
                cap = subprocess.run(["tmux", "capture-pane", "-p", "-t", session],
                                     capture_output=True, text=True, timeout=2)
                return "\n".join(cap.stdout.splitlines()[-80:])
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def collect(window, snap):
    cands = candidates(snap, window["pid"])
    chosen, confident = pick(cands, window.get("title", ""))
    if not chosen:
        return {"notes": ["no shell found under the terminal process"]}, "low"
    ctx = {
        "program": chosen["program"],
        "claude_running": chosen["program"] == "claude",
        "project": project.describe(chosen["cwd"]),
        "other_terminals": [c["cwd"] for c in cands if c is not chosen],
    }
    notes = []
    if chosen["program"] == "claude" and ctx["project"].get("claude_session"):
        ctx["resume"] = {"cwd": chosen["cwd"], "command": ["claude", "--resume", ctx["project"]["claude_session"]["id"]]}
    if chosen["program"] == "tmux":
        text = _tmux_text(snap, chosen["shell_pid"])
        if text:
            ctx["terminal_text"] = text
    if not confident:
        notes.append("several terminals share this process; picked by title match, may be the wrong one")
    ctx_notes = notes
    return {**ctx, "notes": ctx_notes}, "high" if confident else "medium"
