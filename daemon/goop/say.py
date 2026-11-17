"""Make a goop speak without putting the text on a command line.

`goopctl speak <addr> "text"` passes the text as an argument, which any local account can read in /proc/<pid>/cmdline while the
command runs. Lesson topics and narration are private, so they go through a 0600 file under ~/.cache/goop/run; only the file's
random name is on the command line. The shell reads the file and deletes it; a file it never read is removed after an hour.
"""
import os, subprocess, tempfile, time

from . import private

RUN = os.path.join(private.CACHE, "run")
CTL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bin", "goopctl")


def _prune(max_age=3600):
    """The shell deletes a file once it has read it; this removes one it never read (a shell that was not running)."""
    cutoff = time.time() - max_age
    try:
        for name in os.listdir(RUN):
            path = os.path.join(RUN, name)
            if name.startswith("say-") and os.path.getmtime(path) < cutoff:
                os.remove(path)
    except OSError:
        pass


def speak(address, text, timeout=10):
    """Ask the goop at `address` to say `text`. Returns True when the command ran."""
    private.makedirs(RUN)
    fd, path = tempfile.mkstemp(prefix="say-", suffix=".txt", dir=RUN)    # mkstemp creates the file 0600
    with os.fdopen(fd, "w") as f:
        f.write(text)
    try:
        subprocess.run([CTL, "speakfile", address, path], timeout=timeout, capture_output=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        _prune()
