#!/usr/bin/env python3
"""Plan a whole lesson from the command line, with timings (for trying the planner without the goop):
    plan_lesson.py "how a Blu-ray disc works" --notes "facts..." [--model opus] [--workers 6] [--out file.json]
Prints the path of the saved storyboard (with every part's code); play it with bin/goop-explain <path>."""
import argparse, json, os, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop.explainer import build, planner, play, validate  # noqa: E402


def report(label, findings):
    print(f"validator, {label}: {len(findings)} finding(s)", file=sys.stderr)
    for f in findings:
        print(f"    {f}", file=sys.stderr)


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
    ap.add_argument("--sheet", action="store_true", help="draw a model sheet (one call, no per-part shape code) instead of an outline and parts")
    ap.add_argument("--no-refit", action="store_true", help="skip laying the lesson out again with the sizes the parts really came out at")
    a = ap.parse_args()
    notes = open(a.notes_file).read() if a.notes_file else a.notes
    run, part_run, t0 = planner.claude_runner(a.model, a.outline_effort, timeout=planner.SHEET_TIMEOUT if a.sheet else None), planner.claude_runner(a.model, a.part_effort), time.time()
    if a.sheet:
        try:
            story = planner.plan_sheet(a.topic, notes, run)
        except planner.PlanError as e:
            sys.exit(f"failed: {e}")
        print(f"sheet: {time.time() - t0:.0f}s, {len(story['parts'])} components", file=sys.stderr)
        scene = build.build(story)
        report("model sheet", validate.check(scene, story))
        path = a.out or play.save(story)
        if a.out:
            with open(path, "w") as f:
                json.dump(story, f, indent=2)
        print(path)
        print(f"total {time.time() - t0:.0f}s", file=sys.stderr)
        return
    try:
        story = planner.plan_outline(a.topic, notes, run)
        print(f"outline: {time.time() - t0:.0f}s, {len(story['parts'])} parts", file=sys.stderr)
        with tempfile.TemporaryDirectory() as parts_dir:
            results = planner.produce(story, a.topic, part_run, parts_dir, workers=a.workers,
                                      on_part=lambda pid, ok, s: print(f"  part {pid}: {'ok' if ok else 'FAILED'} in {s}s (at {time.time() - t0:.0f}s)", file=sys.stderr))
            t1 = time.time()
            before = validate.check(build.build(story, parts_dir=parts_dir), story)
            report("as laid out from the outline", before)
            if not a.no_refit:
                story = planner.refit(story, parts_dir)
                after = validate.check(build.build(story, parts_dir=parts_dir), story)
                report("after laying out again with the real sizes", after)
            print(f"checks took {time.time() - t1:.1f}s", file=sys.stderr)
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
