#!/usr/bin/env python3
"""Install or remove the Goop page reader for Chromium-based browsers:   pagereader_install.py [--uninstall] [--flags FILE] [--hosts-dir DIR]...
 1. writes the native-messaging host file, which tells the browser how to start daemon/pagereader_host.py and which extension may talk to it;
 2. adds browser/pagereader to the --load-extension list in ~/.config/chromium-flags.conf (Omarchy loads its own extensions the same way), after backing the file up.
Safe to run again. The browser must be restarted to load the extension; this script never touches a running browser."""
import argparse, json, os, shutil, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
EXT_DIR = os.path.join(ROOT, "browser", "pagereader")
HOST_PATH = os.path.join(HERE, "pagereader_host.py")
HOST_NAME = "io.github.magonox.goop.pagereader"
FLAGS = os.path.expanduser("~/.config/chromium-flags.conf")
HOST_DIRS = [os.path.expanduser("~/.config/chromium/NativeMessagingHosts")]      # Chromium only; pass --hosts-dir for another Chromium-based browser


def extension_id():
    with open(os.path.join(EXT_DIR, "EXTENSION_ID")) as f:
        return f.read().strip()


def host_manifest():
    return {"name": HOST_NAME, "description": "Goop page reader host", "path": HOST_PATH, "type": "stdio",
            "allowed_origins": [f"chrome-extension://{extension_id()}/"]}


def merge_flags(text, ext_path, remove=False):
    """The flags file with ext_path added to (or removed from) its --load-extension list. Other lines are kept exactly."""
    lines, found = text.split("\n"), False
    for i, line in enumerate(lines):
        if line.startswith("--load-extension="):
            found = True
            items = [p for p in line[len("--load-extension="):].split(",") if p and p != ext_path]
            if not remove:
                items.append(ext_path)
            lines[i] = "--load-extension=" + ",".join(items) if items else None
    lines = [l for l in lines if l is not None]
    if not found and not remove:
        if lines and lines[-1] == "":
            lines.pop()
        lines += [f"--load-extension={ext_path}", ""]
    return "\n".join(lines)


def run(remove=False, flags=FLAGS, host_dirs=None, ext_path=EXT_DIR, out=print):
    host_dirs = HOST_DIRS if host_dirs is None else host_dirs
    for d in host_dirs:
        target = os.path.join(d, HOST_NAME + ".json")
        if remove:
            if os.path.exists(target):
                os.remove(target)
                out(f"removed {target}")
        elif os.path.isdir(os.path.dirname(d)) or os.path.isdir(d):        # only for browsers that are set up on this machine
            os.makedirs(d, exist_ok=True)
            with open(target, "w") as f:
                json.dump(host_manifest(), f, indent=2)
                f.write("\n")
            out(f"wrote {target}")
    old = open(flags).read() if os.path.exists(flags) else ""
    new = merge_flags(old, ext_path, remove)
    if new != old:
        if os.path.exists(flags):
            backup = f"{flags}.bak.{time.strftime('%Y%m%d%H%M%S')}"
            shutil.copy2(flags, backup)
            out(f"backed up {flags} to {backup}")
        os.makedirs(os.path.dirname(flags), exist_ok=True)
        with open(flags, "w") as f:
            f.write(new)
        out(f"{'removed from' if remove else 'added to'} {flags}: {ext_path}")
    else:
        out(f"{flags} already {'has no' if remove else 'lists the'} Goop page reader")
    if not remove:
        out("Restart Chromium (close all its windows and open it again) to load the extension.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--flags", default=FLAGS)
    ap.add_argument("--hosts-dir", action="append")
    a = ap.parse_args()
    run(a.uninstall, a.flags, a.hosts_dir)
