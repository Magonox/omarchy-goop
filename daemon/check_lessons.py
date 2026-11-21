#!/usr/bin/env python3
"""Run the invariants (goop/explainer/invariants.py) on lessons and print what fails:
    check_lessons.py [lesson.json ...]        default: the fixtures in tests/fixtures/lessons and the built-in lessons
    check_lessons.py -v                       list every violation, not just counts
Needs deno (to run the parts' code) and node (to run the renderer's state())."""
import glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from goop.explainer import build, invariants  # noqa: E402

COUPLINGS = {"watch-sheet": [{"a": "hour_hand", "b": "minute_hand", "kind": "chain", "ratio": 12}, {"a": "minute_hand", "b": "second_hand", "kind": "chain", "ratio": 60}],
             "bicycle-v2": [{"a": "crank", "b": "rear_wheel", "kind": "chain", "ratio": 2.75}]}      # the plan has no links yet (F4): the bicycle's chain, by hand


def lessons():
    found = sorted(glob.glob(os.path.join(HERE, "tests", "fixtures", "lessons", "*.json")))
    found += sorted(glob.glob(os.path.join(HERE, "goop", "explainer", "lessons", "*.json")))
    return found


def run(path):
    name = os.path.basename(path)[:-5]
    story = json.load(open(path))
    scene = build.load(path)
    return name, invariants.check_all(scene, story, COUPLINGS.get(name))


def main():
    verbose = "-v" in sys.argv
    paths = [a for a in sys.argv[1:] if a != "-v"] or lessons()
    rows = [run(p) for p in paths]
    width = max(len(n) for n, _ in rows)
    print(f"{'':{width}}  " + " ".join(f"{i[:6]:>6}" for i in invariants.NAMES))
    for name, res in rows:
        print(f"{name:{width}}  " + " ".join(f"{len(res[i]) or '.':>6}" for i in invariants.NAMES))
    if verbose:
        for name, res in rows:
            for i in invariants.NAMES:
                for v in res[i]:
                    print(f"{name}: {v}")


if __name__ == "__main__":
    main()
