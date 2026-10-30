"""What goop needs and what is missing, for the settings panel's setup checklist (and `doctor.py` on the command line)."""
import os, shutil

VENV_PYTHON = os.path.expanduser("~/.local/share/goop/venv/bin/python")
VOICE_MODEL = os.path.expanduser("~/.local/share/goop/voices/en_US-libritts_r-medium.onnx")


def checks(provider_name="claude", provider_problem=None, which=shutil.which, exists=os.path.exists):
    """[{id, label, ok, required, hint}]. `provider_problem` is None when the active agent is ready, else why not."""
    def tool(id_, label, cmd, required, hint):
        return {"id": id_, "label": label, "ok": bool(which(cmd)), "required": required, "hint": hint}

    agent_ok = provider_problem is None
    agent_hint = provider_problem or ""
    if provider_name == "claude" and not which("claude"):
        agent_ok, agent_hint = False, "Install Claude Code and run `claude` once to sign in"
    voice_ok = exists(VENV_PYTHON) and exists(VOICE_MODEL)
    return [
        {"id": "agent", "label": f"Agent ({provider_name})", "ok": agent_ok, "required": True, "hint": agent_hint},
        tool("hyprctl", "Hyprland (hyprctl)", "hyprctl", True, "Goop needs Hyprland"),
        tool("screenshots", "Screenshots (grim)", "grim", True, "Install grim so goops can see windows"),
        {"id": "voice", "label": "On-device voice", "ok": voice_ok, "required": False,
         "hint": "Run setup.sh to install the voice (about 275 MB)"},
        tool("audio", "Audio playback (paplay)", "paplay", False, "Install pipewire-pulse so goops can speak"),
        tool("typing", "Typing into terminals (wtype)", "wtype", False, "Install wtype so goops can type commands"),
        tool("pdf", "Reading PDFs (pdftotext)", "pdftotext", False, "Install poppler so goops can read PDFs"),
    ]


def providers(registry, active):
    """[{name, ready, active, problem}] for every configured agent."""
    out = []
    for name in registry.names():
        p = registry.get(name)
        problem = getattr(p, "problem", lambda: None)()
        if name == "claude" and not p.available():
            problem = "the claude CLI was not found"
        out.append({"name": name, "ready": p.available(), "active": name == active, "problem": problem or ""})
    return out
