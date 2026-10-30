#!/usr/bin/env python3
"""Read a built scene aloud, one step at a time, through the running goop's voice (so its mouth moves).
    narrate.py scene.json [--addr 0x..] [--offset 1.5]
Stops when the scene's duration is over, or when asked to (SIGTERM)."""
import argparse, json, os, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
CTL = os.path.join(HERE, "..", "bin", "goopctl")


def goop_addr():
    """The goop on the focused window, else the first one that exists."""
    try:
        addrs = subprocess.run([CTL, "list"], capture_output=True, text=True, timeout=5).stdout.split()
        active = json.loads(subprocess.run(["hyprctl", "activewindow", "-j"], capture_output=True, text=True, timeout=5).stdout or "{}").get("address")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return active if active in addrs else (addrs[0] if addrs else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--addr")
    ap.add_argument("--offset", type=float, default=1.5)       # the renderer takes a moment to load the scene
    ap.add_argument("--speed", type=float, default=float(os.environ.get("GOOP_SPEED", "1")))
    a = ap.parse_args()
    scene = json.load(open(a.scene))
    addr = a.addr or goop_addr()
    if not addr:
        return print("narrate: no goop to speak with", file=sys.stderr)
    signal.signal(signal.SIGTERM, lambda *_: (subprocess.run([CTL, "hush"]), sys.exit(0)))
    start = time.monotonic() + a.offset
    for st in scene["steps"]:
        wait = start + st["t0"] / a.speed - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        subprocess.run([CTL, "speak", addr, st["say"]], timeout=10)
    if scene.get("question"):
        pass            # the closing question is shown by the renderer; asking it aloud comes with teacher mode


if __name__ == "__main__":
    main()
