#!/usr/bin/env python3
"""Plan a lesson from the command line (for trying the planner without the goop):
    plan_lesson.py "how a Blu-ray disc works" --notes "facts..." [--mode pieces|code] [--model opus] [--out file.json]
Prints the path of the saved storyboard; play it with bin/goop-explain <path>."""
import argparse, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop.explainer import planner, play  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("topic")
    ap.add_argument("--notes", default="")
    ap.add_argument("--notes-file")
    ap.add_argument("--mode", default="pieces", choices=("pieces", "code"))
    ap.add_argument("--model", default="opus")
    ap.add_argument("--out")
    a = ap.parse_args()
    notes = open(a.notes_file).read() if a.notes_file else a.notes
    base, calls = planner.claude_runner(a.model), []

    def run(system, prompt):
        t = time.time()
        reply = base(system, prompt)
        calls.append(round(time.time() - t, 1))
        print(f"model call {len(calls)}: {calls[-1]}s, {len(reply)} characters" + (" (a repair pass)" if len(calls) > 1 else ""), file=sys.stderr)
        return reply
    try:
        story, scene = planner.plan(a.topic, notes, run, mode=a.mode)
    except planner.PlanError as e:
        sys.exit(f"failed: {e}")
    path = a.out or play.save(story)
    if a.out:
        with open(path, "w") as f:
            json.dump(story, f, indent=2)
    print(path)
    print(f"{len(story['parts'])} parts, {scene['duration']:.0f}s, template {story['layout']['template']}, {len(calls)} model call(s) {calls}", file=sys.stderr)


if __name__ == "__main__":
    main()
