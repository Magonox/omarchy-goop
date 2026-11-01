#!/usr/bin/env python3
"""Plan a whole lesson from the command line, with timings (for trying the planner without the goop):
    plan_lesson.py "how a Blu-ray disc works" --notes "facts..." [--model opus] [--workers 6] [--out file.json]
Prints the path of the saved storyboard (with every part's code); play it with bin/goop-explain <path>."""
import argparse, json, os, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop.explainer import planner, play  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("topic")
    ap.add_argument("--notes", default="")
    ap.add_argument("--notes-file")
    ap.add_argument("--model", default="opus")
    ap.add_argument("--outline-effort", default="medium")
    ap.add_argument("--part-effort", default="low")
    ap.add_argument("--workers", type=int, default=planner.WORKERS)
    ap.add_argument("--out")
    a = ap.parse_args()
    notes = open(a.notes_file).read() if a.notes_file else a.notes
    run, part_run, t0 = planner.claude_runner(a.model, a.outline_effort), planner.claude_runner(a.model, a.part_effort), time.time()
    try:
        story = planner.plan_outline(a.topic, notes, run)
        print(f"outline: {time.time() - t0:.0f}s, {len(story['parts'])} parts", file=sys.stderr)
        with tempfile.TemporaryDirectory() as parts_dir:
            results = planner.produce(story, a.topic, part_run, parts_dir, workers=a.workers,
                                      on_part=lambda pid, ok, s: print(f"  part {pid}: {'ok' if ok else 'FAILED'} in {s}s (at {time.time() - t0:.0f}s)", file=sys.stderr))
    except planner.PlanError as e:
        sys.exit(f"failed: {e}")
    full = planner.full_story(story, results)
    path = a.out or play.save(full)
    if a.out:
        with open(path, "w") as f:
            json.dump(full, f, indent=2)
    print(path)
    print(f"total {time.time() - t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
