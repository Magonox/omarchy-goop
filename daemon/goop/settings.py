"""Read and change the user's goop config (~/.config/goop/config.json) from the command line. The shell watches the file, so a change
takes effect immediately. Values for dotted keys like tts.speed are parsed as JSON when they can be."""
import json, os

from . import config

CHOICES = {"animations": ("full", "reduced", "off"), "access": ("look", "ask", "ask_all"), "read_files": ("folder", "ask", "off"),
           "explainers": ("offer", "auto", "never")}


def _read(path):
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def parse(key, raw):
    if key == "provider":
        from .agent import registry
        if raw not in registry.names():
            raise ValueError(f"unknown agent {raw!r}; configured: {', '.join(registry.names())}")
        return raw
    if key in CHOICES:
        if raw not in CHOICES[key]:
            raise ValueError(f"{key} must be one of: {', '.join(CHOICES[key])}")
        return raw
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def set_value(key, raw, path=None):
    path = path or config.PATH
    value = parse(key, raw)
    data = _read(path)
    node = data
    *parents, leaf = key.split(".")
    for part in parents:
        if not isinstance(node.get(part), dict):
            node[part] = {}
        node = node[part]
    node[leaf] = value
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)            # atomic, so the shell never reads half a file
    return value


def migrate_file(path=None):
    """Bring the saved config up to the current version and write it (after a backup). Returns the notes of what changed; nothing is written when there is nothing to do."""
    from . import migrate
    path = path or config.PATH
    data = _read(path)
    if not data:
        return []                                    # no config file: nothing of the user's to migrate
    new, notes = migrate.migrate(data)
    if new != data:
        import shutil, time
        shutil.copy2(path, f"{path}.bak.{time.strftime('%Y%m%d%H%M%S')}")
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(new, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    return notes


def get_value(key, path=None):
    node = config.load() if path is None else {**config.DEFAULTS, **_read(path)}
    for part in key.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    return node
