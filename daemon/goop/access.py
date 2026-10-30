"""The access level: one switch for how much goop may do. Everything that decides "may I?" asks this module.

  look      see and read, never act. Typing into terminals and moving files are refused (and not even offered to the model).
  ask       the default. Actions need an approval card; plain read-only terminal commands run at once; files inside the folder the
            window shows are read at once.
  ask_all   a card for everything that leaves the window's own context: every screenshot, every file read, every command and move.

`read_files` and `auto_approve_safe` in the user's config still work as explicit overrides of the level (they are no longer defaults).
"""
from . import config

LEVELS = ("look", "ask", "ask_all")
DEFAULT = "ask"
LABELS = {"look": "Look only", "ask": "Ask first", "ask_all": "Ask for everything"}
DESCRIPTIONS = {
    "look": "Goop can see and read, but never change anything.",
    "ask": "Goop asks before it acts. Plain read-only commands (ls, cd, pwd) run at once.",
    "ask_all": "Goop asks before every action, file read and screenshot.",
}
ACTING = frozenset({"type_in_terminal", "move_files", "undo_last_move"})


def level(cfg=None):
    cfg = config.load() if cfg is None else cfg
    value = cfg.get("access")
    return value if value in LEVELS else DEFAULT


def policy(cfg=None):
    cfg = config.load() if cfg is None else cfg
    lv = level(cfg)
    p = {
        "level": lv,
        "act": lv != "look",                              # may it use the acting tools at all
        "auto_safe": lv == "ask",                         # run plain read-only terminal commands without a card
        "read": "ask" if lv == "ask_all" else "folder",   # "folder": inside the window's folder | "ask": a card per file | "off"
        "screenshot": "ask" if lv == "ask_all" else "auto",
    }
    if cfg.get("read_files") in ("folder", "ask", "off"):
        p["read"] = cfg["read_files"]
    if isinstance(cfg.get("auto_approve_safe"), bool) and p["act"]:
        p["auto_safe"] = cfg["auto_approve_safe"]
    return p


def allowed(names, cfg=None):
    """The tool names a model may be offered at the current level."""
    act = policy(cfg)["act"]
    return [n for n in names if act or n not in ACTING]


LOOK_ONLY_MESSAGE = ("Goop is set to Look only, so it cannot change anything. "
                     "The user can change the access level in the Goop settings (the ghost icon in the bar).")
