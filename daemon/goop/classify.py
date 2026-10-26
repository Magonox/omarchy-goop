"""Window class -> app type. Order matters: first match wins."""

RULES = [
    ("file_manager", ["nautilus", "thunar", "dolphin", "nemo", "pcmanfm", "yazi"]),
    ("terminal", ["ghostty", "kitty", "alacritty", "foot", "wezterm", "xterm", "konsole"]),
    ("browser", ["chromium", "chrome", "brave", "firefox", "zen", "vivaldi"]),
    ("editor", ["code", "zed", "jetbrains", "sublime", "kate", "gedit"]),
]


def app_type(window_class):
    cls = (window_class or "").lower()
    for kind, needles in RULES:
        if any(n in cls for n in needles):
            return kind
    return "other"
