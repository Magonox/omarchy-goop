"""Approval handshake between an agent tool and the user. The tool writes a request file and blocks; the shell shows
it on a card; the user's click writes an answer file (answer.py). No answer in time means "no"."""
import json, os, re, time, uuid

DIR = os.path.expanduser("~/.cache/goop/approvals")
TTL = 90
_ID = re.compile(r"^[0-9a-f]{12}$")


def request(address, kind, summary, detail="", ttl=None, poll=0.2):
    """Block until the user answers. True only on an explicit yes."""
    ttl = ttl or TTL
    os.makedirs(DIR, exist_ok=True)
    rid = uuid.uuid4().hex[:12]
    req, ans = os.path.join(DIR, rid + ".json"), os.path.join(DIR, rid + ".answer")
    with open(req, "w") as f:
        json.dump({"id": rid, "address": address, "kind": kind, "summary": summary, "detail": detail,
                   "ts": time.time(), "ttl": ttl}, f)
    try:
        deadline = time.time() + ttl
        while time.time() < deadline:
            if os.path.exists(ans):
                with open(ans) as f:
                    return f.read().strip() == "yes"
            time.sleep(poll)
        return False
    finally:
        for p in (req, ans):
            try:
                os.remove(p)
            except OSError:
                pass


def pending():
    """Requests still waiting for an answer, oldest first (what the shell shows)."""
    out, now = [], time.time()
    try:
        names = os.listdir(DIR)
    except OSError:
        return out
    for n in names:
        if not n.endswith(".json"):
            continue
        try:
            with open(os.path.join(DIR, n)) as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        if now - d["ts"] < d["ttl"] and not os.path.exists(os.path.join(DIR, d["id"] + ".answer")):
            out.append(d)
    return sorted(out, key=lambda d: d["ts"])


def answer(rid, yes):
    if not _ID.match(rid):
        raise ValueError("bad approval id")
    os.makedirs(DIR, exist_ok=True)
    tmp = os.path.join(DIR, rid + ".tmp")
    with open(tmp, "w") as f:
        f.write("yes" if yes else "no")
    os.replace(tmp, os.path.join(DIR, rid + ".answer"))
