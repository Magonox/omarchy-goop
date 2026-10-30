"""Privacy deny list. A denied window gets no context and no screenshot."""
import json, os, re

DEFAULTS = {
    "deny_classes": ["1password", "bitwarden", "keepassxc", "seahorse", "gnome-keyring"],
    "deny_title_regex": ["password", "bank", "paypal", "1password", "bitwarden"],
    "auto_approve_safe": True,  # run plain read-only terminal commands (ls, pwd, cd, git status/log) without a card
    "tts": {                    # a goop's spoken voice; all on-device, nothing leaves the machine
        "enabled": True,
        "engine": "piper",
        "model": "en_US-libritts_r-medium",
        "speakers": [0, 112, 233, 358, 471, 590, 702, 815],   # Piper speaker ids; each goop's personality seed picks one
        "speed": 0.94,          # 1.0 = Piper's natural pace; lower is slower
        "pause_ms": 220,        # silence between sentences
        "max_chars": 420,       # longer replies are cut at a sentence boundary
    },
    "read_files": "folder",     # who may read files: "folder" = files inside the window's own folder, "ask" = a card per file, "off"
    "providers": {},            # extra OpenAI-compatible endpoints by name; see agent/registry.py
    "provider": "claude",       # which agent the goops are
    "model": "haiku",           # provider-specific model name; quick replies suit a small, fast model
}
PATH = os.path.expanduser("~/.config/goop/config.json")


def load():
    cfg = dict(DEFAULTS)
    try:
        with open(PATH) as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def is_denied(window, cfg=None):
    cfg = cfg or load()
    cls = (window.get("class") or "").lower()
    title = window.get("title") or ""
    if any(d in cls for d in cfg["deny_classes"]):
        return True
    return any(re.search(p, title, re.I) for p in cfg["deny_title_regex"])


def tts():
    """TTS settings with defaults filled in (a user config may override only some keys)."""
    return {**DEFAULTS["tts"], **load().get("tts", {})}
