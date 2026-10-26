"""Hyprland queries and the drop hit-test."""
import json, re, subprocess


def hypr(*args):
    return json.loads(subprocess.check_output(["hyprctl", *args, "-j"], timeout=3))


def window_at(cx, cy, clients, active_workspaces):
    """Topmost visible window containing (cx, cy). Floating beats tiled, then focus order."""
    hits = [
        c for c in clients
        if c["mapped"] and not c["hidden"] and c["workspace"]["id"] in active_workspaces
        and c["at"][0] <= cx < c["at"][0] + c["size"][0]
        and c["at"][1] <= cy < c["at"][1] + c["size"][1]
    ]
    hits.sort(key=lambda c: (not c["floating"], c["focusHistoryID"]))
    return hits[0] if hits else None


def cursor():
    c = hypr("cursorpos")
    return c["x"], c["y"]


def snapshot():
    """(clients, active workspace ids) in one go."""
    clients = hypr("clients")
    ws = {m["activeWorkspace"]["id"] for m in hypr("monitors")}
    return clients, ws


def cursor_fast():
    """Cursor position straight from the Hyprland socket (no process spawn); falls back to hyprctl."""
    import os, socket
    path = f"{os.environ['XDG_RUNTIME_DIR']}/hypr/{os.environ['HYPRLAND_INSTANCE_SIGNATURE']}/.socket.sock"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect(path)
            s.sendall(b"j/cursorpos")
            buf = b""
            while chunk := s.recv(4096):
                buf += chunk
        c = json.loads(buf)
        return c["x"], c["y"]
    except (KeyError, OSError, ValueError):
        return cursor()


_ADDRESS = re.compile(r"^0x[0-9a-f]+$")


def focus_window(address):
    """Focus a window. Hyprland 0.56+ takes dispatches as Lua; older versions use the classic dispatcher, so try both.
    The address is validated first because it ends up inside a Lua string."""
    if not _ADDRESS.match(address):
        raise ValueError(f"bad window address {address!r}")
    attempts = (["hyprctl", "dispatch", f'hl.dsp.focus({{ window = "address:{address}" }})'],
                ["hyprctl", "dispatch", "focuswindow", f"address:{address}"])
    last = None
    for cmd in attempts:
        try:
            subprocess.run(cmd, check=True, timeout=3, capture_output=True)
            return
        except subprocess.CalledProcessError as e:
            last = e
    raise last
