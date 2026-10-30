"""Start and stop a lesson window (bin/goop-explain). One lesson plays at a time."""
import json, os, re, signal, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(HERE, "..", "..", "..", "bin", "goop-explain")
LESSON_DIR = os.path.expanduser("~/.cache/goop/lessons")


def running():
    """pids of lesson windows (a quickshell started with the explainer3d program), found by exact command line."""
    out = []
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                argv = f.read().split(b"\0")
        except OSError:
            continue
        if argv and os.path.basename(argv[0].decode(errors="replace")) == "quickshell" and any(a.endswith(b"shell/explainer3d") for a in argv):
            out.append(int(pid))
    return out


def stop():
    for pid in running():
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def save(story):
    os.makedirs(LESSON_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", story.get("title", "lesson").lower()).strip("_")[:40] or "lesson"
    path = os.path.join(LESSON_DIR, slug + ".json")
    with open(path, "w") as f:
        json.dump(story, f, indent=2)
    return path


def launch(story_path, address=""):
    """Play a saved storyboard, narrated by the goop at `address`. Returns right away."""
    env = dict(os.environ, GOOP_ADDR=address or "")
    subprocess.Popen([BIN, story_path], env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
