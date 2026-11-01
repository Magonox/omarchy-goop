"""What goop needs and what is missing, for the settings panel's setup checklist (and `doctor.py` on the command line)."""
import os, shutil

VENV_PYTHON = os.path.expanduser("~/.local/share/goop/venv/bin/python")
STT_PACKAGE = "moonshine_voice"
VOICE_MODEL = os.path.expanduser("~/.local/share/goop/voices/en_US-libritts_r-medium.onnx")
QUICK3D_PLUGIN = "/usr/lib/qt6/qml/QtQuick3D/libqquick3dplugin.so"


def checks(provider_name="claude", provider_problem=None, which=shutil.which, exists=os.path.exists, has_module=None):
    """[{id, label, ok, required, hint}]. `provider_problem` is None when the active agent is ready, else why not."""
    def tool(id_, label, cmd, required, hint):
        return {"id": id_, "label": label, "ok": bool(which(cmd)), "required": required, "hint": hint}

    agent_ok = provider_problem is None
    agent_hint = provider_problem or ""
    if provider_name == "claude" and not which("claude"):
        agent_ok, agent_hint = False, "Install Claude Code and run `claude` once to sign in"
    voice_ok = exists(VENV_PYTHON) and exists(VOICE_MODEL)
    if has_module is None:
        def has_module(name):
            site = os.path.join(os.path.dirname(os.path.dirname(VENV_PYTHON)), "lib")
            return any(exists(os.path.join(site, v, "site-packages", name)) for v in (os.listdir(site) if exists(site) else []))
    return [
        {"id": "agent", "label": f"Agent ({provider_name})", "ok": agent_ok, "required": True, "hint": agent_hint},
        tool("hyprctl", "Hyprland (hyprctl)", "hyprctl", True, "Goop needs Hyprland"),
        tool("screenshots", "Screenshots (grim)", "grim", True, "Install grim so goops can see windows"),
        {"id": "voice", "label": "On-device voice", "ok": voice_ok, "required": False,
         "hint": "Run setup.sh to install the voice (about 275 MB)"},
        {"id": "listen", "label": "Talk to goops (microphone input)", "ok": has_module(STT_PACKAGE) and bool(which("parecord")), "required": False,
         "hint": "Run setup.sh to install voice input (about 160 MB, on-device)"},
        tool("audio", "Audio playback (paplay)", "paplay", False, "Install pipewire-pulse so goops can speak"),
        tool("typing", "Typing into terminals (wtype)", "wtype", False, "Install wtype so goops can type commands"),
        tool("pdf", "Reading PDFs (pdftotext)", "pdftotext", False, "Install poppler so goops can read PDFs"),
        {"id": "quick3d", "label": "3D explainers (qt6-quick3d)", "ok": exists(QUICK3D_PLUGIN), "required": False,
         "hint": "Run: sudo pacman -S qt6-quick3d (about 10 MB)"},
        tool("sandbox", "3D lesson shapes (deno sandbox)", "deno", False, "Run: sudo pacman -S deno. 3D lessons need it to run the model's shape code safely"),
        tool("lessons", "3D lesson planner (claude CLI)", "claude", False, "3D lessons are planned with the claude CLI for now; install Claude Code to use them"),
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
