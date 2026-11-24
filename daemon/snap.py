#!/usr/bin/env python3
"""Render a 3D lesson to pictures without touching the owner's screen, so a person (or Claude, which can read images) can look at what the viewer would see.

    snap.py <storyboard.json> [--times auto|5,20,45] [--out DIR] [--size 1280x800]

The real lesson window (shell/explainer3d) is started on a throwaway virtual monitor that Hyprland makes for the purpose (`hyprctl output create headless`), the lesson clock
is stepped through GOOP_CLOCK_FILE, and `grim -o` captures only that monitor. Nothing is drawn on a real monitor and no real window is captured. The virtual monitor is removed
at the end, even after an error. Prints the pictures and a contact sheet (`sheet.png`, each tile labelled with its time).

`--times auto` takes the middle of every step, plus the finale second by second: the moments a viewer would judge the lesson by.
Needs: hyprctl and grim (Hyprland), quickshell, qt6-quick3d, ImageMagick (for the sheet), deno (to run the parts' code)."""
import argparse, json, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from goop.explainer import build  # noqa: E402


def sh(*cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def monitors():
    return {m["name"]: m for m in json.loads(sh("hyprctl", "-j", "monitors", "all").stdout or "[]")}


def auto_times(scene):
    ts = [round(s["t0"] + min(3.0, (s["t1"] - s["t0"]) / 2), 1) for s in scene["steps"]]
    fin = scene.get("finale")
    if fin:
        ts += [round(fin["t_go"] + x, 1) for x in (0.0, 1.5, 3.0, 4.5, fin["dur"] - 0.5)]
    return sorted({t for t in ts if 0 <= t < scene["duration"]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story")
    ap.add_argument("--times", default="auto")
    ap.add_argument("--out", default=None)
    ap.add_argument("--size", default="1280x800")
    a = ap.parse_args()
    for tool in ("hyprctl", "grim", "quickshell"):
        if not shutil.which(tool):
            sys.exit(f"snap: {tool} is needed")
    scene = build.load(a.story)
    times = auto_times(scene) if a.times == "auto" else [float(x) for x in a.times.split(",")]
    out = os.path.abspath(a.out or tempfile.mkdtemp(prefix="goop-snap-"))
    os.makedirs(out, exist_ok=True)
    work = tempfile.mkdtemp(prefix="goop-snap-work-")
    scene_path, clock = os.path.join(work, "scene.json"), os.path.join(work, "clock")
    with open(scene_path, "w") as f:
        json.dump(scene, f, separators=(",", ":"))
    with open(clock, "w") as f:
        f.write("0")

    before = set(monitors())
    focus_before = next((n for n, m in monitors().items() if m.get("focused")), None)
    name, proc = None, None
    try:
        sh("hyprctl", "output", "create", "headless")
        new = set(monitors()) - before
        if not new:
            sys.exit("snap: Hyprland did not make a virtual monitor")
        name = sorted(new)[0]
        sh("hyprctl", "keyword", "monitor", f"{name},{a.size}@60,0x3000,1")           # far below the real monitors, so nothing real overlaps it
        if focus_before:
            sh("hyprctl", "dispatch", "focusmonitor", focus_before)                  # the owner's focus stays where it was
        env = dict(os.environ, GOOP_SCENE=scene_path, GOOP_CLOCK_FILE=clock, GOOP_OUTPUT=name, GOOP_QUIET="1")
        proc = subprocess.Popen(["quickshell", "-n", "-p", os.path.join(ROOT, "shell", "explainer3d")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(4.0)                                                            # the window opens and the parts load
        shots = []
        for t in times:
            with open(clock, "w") as f:
                f.write(f"{t}")
            time.sleep(0.9)
            path = os.path.join(out, f"t{t:06.1f}.png")
            r = sh("grim", "-o", name, path)
            if r.returncode != 0:
                sys.exit(f"snap: grim failed: {r.stderr.strip()}")
            shots.append((t, path))
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if name:
            sh("hyprctl", "output", "remove", name)
        if focus_before:
            sh("hyprctl", "dispatch", "focusmonitor", focus_before)
        shutil.rmtree(work, ignore_errors=True)
    if shutil.which("magick"):
        tiles = []
        for t, path in shots:
            tile = path.replace(".png", "_tile.png")
            sh("magick", path, "-resize", "640x", "-gravity", "NorthWest", "-fill", "white", "-undercolor", "#00000099", "-pointsize", "18", "-annotate", "+6+6", f" t={t:g}s ", tile)
            tiles.append(tile)
        sheet = os.path.join(out, "sheet.png")
        sh("magick", "montage", *tiles, "-tile", "3x", "-geometry", "+4+4", "-background", "#111118", sheet)
        for tile in tiles:
            os.remove(tile)
        print(sheet)
    for t, path in shots:
        print(path)


if __name__ == "__main__":
    main()
