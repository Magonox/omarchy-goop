#!/usr/bin/env python3
"""Build and play one lesson, from the outline to the last part. Started detached by the explain_in_3d tool (the agent's own process ends as soon as it has
answered, so this cannot run inside it):   explain_run.py job.json    job = {"topic", "notes", "title", "address", "model"}

  1. outline   (one model call: the steps, the narration, every part's brief and size)
  2. parts     (one call per part, in parallel; each geometry file is written the moment it is ready)
  3. the lesson window opens as soon as the parts of the first step exist; the rest appear while it plays
Progress goes to ~/.cache/goop/explain_run.log; a failure is spoken by the goop and shown as a notification."""
import json, os, re, shutil, subprocess, sys, threading, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop import private  # noqa: E402
from goop.explainer import build, planner, play  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CTL = os.path.join(HERE, "..", "bin", "goopctl")
LOG = os.path.expanduser("~/.cache/goop/explain_run.log")
SCENES = os.path.expanduser("~/.cache/goop/scenes")
START_WAIT = 120          # seconds to wait for the first parts before opening the window anyway


def log(msg):
    private.makedirs(os.path.dirname(LOG))
    with private.open_file(LOG, "a") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")


def say(address, text):
    try:
        subprocess.run([CTL, "speak", address, text], timeout=10, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        pass


def tell(address, text):
    log(text)
    say(address, text)
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-a", "Goop", "3D lesson", text], capture_output=True)


def prune():
    """Keep the scenes folder small: drop lesson files older than a day."""
    cutoff = time.time() - 86400
    for name in os.listdir(SCENES) if os.path.isdir(SCENES) else []:
        path = os.path.join(SCENES, name)
        if name.count("-") and os.path.getmtime(path) < cutoff:
            shutil.rmtree(path, ignore_errors=True) if os.path.isdir(path) else os.remove(path)


def main(job_path):
    with open(job_path) as f:
        job = json.load(f)
    topic, address = job["topic"], job.get("address", "")
    model = job.get("model") or "opus"
    run = planner.claude_runner(model, job.get("outline_effort"))
    part_run = planner.claude_runner(model, job.get("part_effort"))
    t0 = time.time()
    say(address, f"Okay, let me build a model of {topic}. Give me a few seconds.")
    try:
        story = planner.plan_outline(topic, job.get("notes", ""), run, title=job.get("title", ""))
    except planner.PlanError as e:
        return tell(address, f"Sorry, I could not plan that lesson. {str(e)[:120]}")
    log(f"outline ready after {time.time() - t0:.0f}s: {len(story['parts'])} parts")

    private.makedirs(SCENES)
    prune()
    slug = re.sub(r"[^a-z0-9]+", "_", story["title"].lower()).strip("_")[:30] or "lesson"
    stem = f"{slug}-{int(time.time())}"
    parts_dir, scene_path = os.path.join(SCENES, stem + ".parts"), os.path.join(SCENES, stem + ".scene.json")
    planner.write_pending(parts_dir, story)
    scene = build.build(story, parts_dir=parts_dir)
    with private.open_file(scene_path) as f:
        json.dump(scene, f, separators=(",", ":"))

    need, done, first_ready = set(planner.first_parts(story)), set(), threading.Event()
    lock = threading.Lock()

    def on_part(pid, ok, seconds):
        log(f"part {pid} {'ready' if ok else 'FAILED, using a stand-in'} in {seconds}s")
        with lock:
            done.add(pid)
            if len(need & done) >= max(1, -(-len(need) * 3 // 5)):        # most of the opening parts are enough: the rest pop in while the lesson starts
                first_ready.set()
    results, worker = {}, None

    def produce():
        results.update(planner.produce(story, topic, part_run, parts_dir, on_part=on_part))
    worker = threading.Thread(target=produce, daemon=False)
    worker.start()
    first_ready.wait(START_WAIT)
    play.stop()
    play.launch_scene(scene_path, address)
    log(f"lesson window opened after {time.time() - t0:.0f}s")
    worker.join()
    log(f"all parts done after {time.time() - t0:.0f}s ({sum(1 for r in results.values() if not r['ok'])} stand-ins)")
    if results:
        play.save(planner.full_story(story, results))            # so the lesson can be replayed later without the model
    failed = [p["label"] for p in story["parts"] if not results.get(p["id"], {}).get("ok")]
    if failed:
        log("stand-ins used for: " + ", ".join(failed))


if __name__ == "__main__":
    try:
        main(sys.argv[1])
    except Exception as e:                       # never die silently: the user is waiting for a lesson
        log(f"crashed: {type(e).__name__}: {e}")
        try:
            tell(json.load(open(sys.argv[1])).get("address", ""), "Sorry, something went wrong while building that lesson.")
        except Exception:
            pass
        raise
