#!/usr/bin/env python3
"""build_scene.py <lesson-name | storyboard.json> [-o scene.json]   storyboard -> resolved scene for the 3D renderer; prints errors if invalid."""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop.explainer import build  # noqa: E402

LESSONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "goop", "explainer", "lessons")

ap = argparse.ArgumentParser()
ap.add_argument("source")
ap.add_argument("-o", "--out")
a = ap.parse_args()
path = a.source if os.path.exists(a.source) else os.path.join(LESSONS, a.source + ".json")
try:
    scene = build.load(path)
except FileNotFoundError:
    sys.exit(f"no such lesson: {a.source} (lessons: {', '.join(sorted(f[:-5] for f in os.listdir(LESSONS)))})")
except build.StoryboardError as e:
    sys.exit("storyboard problems:\n  - " + "\n  - ".join(e.errors))
text = json.dumps(scene, separators=(",", ":"))
if a.out:
    with open(a.out, "w") as f:
        f.write(text)
else:
    print(text)
