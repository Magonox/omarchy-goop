"""Turn steps into a timeline: when each action starts and stops, plus camera shots. Durations come from the narration length, so a step
lasts as long as the sentence takes to say (the voice is synced in a later step)."""
import math

from . import vocab

WORDS_PER_SECOND = 2.35
TEMPLATE_VIEW = {"axis": (-26, 16), "network": (-16, 42), "assembly": (-24, 13)}      # base yaw, pitch in degrees
MIN_WIDE = {"axis": 14.0, "network": 22.0, "assembly": 13.0}                           # never closer than this for the whole-model shot
MIN_FOCUS = {"axis": 9.0, "network": 13.0, "assembly": 13.0}                            # or this when focusing on one part


def duration(text):
    return max(5.0, round(len(text.split()) / WORDS_PER_SECOND + 1.4, 2))


def build(story, lay):
    placed, instances, bounds = lay["placed"], lay["instances"], lay["bounds"]
    template = story["layout"]["template"]
    yaw0, pitch = TEMPLATE_VIEW[template]
    movable = [i for i, p in placed.items() if not p["spanning"] and not p.get("context")]

    def expand(ids):
        out = []
        for r in (ids if isinstance(ids, list) else [ids]):
            out += instances.get(r, [])
        return out

    steps = list(story["steps"])
    if story.get("recap"):
        steps.append({"say": story["recap"], "do": [{"explode": []}, {"zoom": "all"}], "_recap": True})
    events, camera, timeline_steps = [], [], []
    revealed, flows, paths = set(), 0, {}
    t = 0.0
    for n, st in enumerate(steps):
        dur = duration(st["say"] + " " + (st.get("analogy") or ""))
        t0, t1 = t, t + dur
        timeline_steps.append({"t0": round(t0, 2), "t1": round(t1, 2), "say": st["say"], "analogy": st.get("analogy", "")})
        actions = st.get("do", []) or []
        mentioned = []
        for a in actions:
            name, arg = next(iter(a.items()))
            if name in ("reveal", "label", "highlight", "spin", "cutaway"):
                mentioned += expand(arg)
            elif name == "flow":
                mentioned += expand([arg["from"], arg["to"]])
            elif name == "pulse":
                mentioned += expand(arg)
        newly = [i for i in dict.fromkeys(mentioned) if i not in revealed and not placed[i].get("context")]
        if n == 0:   # the context (floor, casing, anything never mentioned yet) shows up with the first step
            newly = list(dict.fromkeys(newly + [i for i, p in placed.items() if p.get("context") or p["spanning"]]))
        if newly:
            events.append({"type": "reveal", "parts": newly, "t0": round(t0 + 0.35, 2)})
            revealed.update(newly)
        zoom_target = None
        for a in actions:
            name, arg = next(iter(a.items()))
            if name == "reveal":
                pass
            elif name == "label":
                events.append({"type": "label", "parts": [instances[r][0] for r in (arg if isinstance(arg, list) else [arg])], "t0": round(t0 + 0.7, 2), "t1": round(t1 - 0.2, 2)})
            elif name == "highlight":
                events.append({"type": "highlight", "parts": expand(arg), "t0": round(t0 + 1.0, 2), "t1": round(t1 - 0.3, 2)})
            elif name == "spin":
                events.append({"type": "spin", "parts": expand(arg), "rate": 140, "t0": round(t0 + 0.9, 2)})
            elif name == "cutaway":
                events.append({"type": "cutaway", "parts": expand(arg), "t0": round(t0 + 0.4, 2), "t1": round(t1 - 0.2, 2), "alpha": 0.18})
            elif name == "explode":
                ids = movable if arg == "all" else expand(arg)
                if ids:
                    events.append({"type": "explode", "parts": ids, "t0": round(t0 + 0.6, 2), "t1": round(t1 - 0.2, 2)})
            elif name == "pulse":
                events.append({"type": "pulse", "source": instances[arg][0], "t0": round(t0 + 0.6, 2)})
            elif name == "flow":
                a_, b_ = placed[instances[arg["from"]][0]], placed[instances[arg["to"]][0]]
                flows += 1
                pid = f"path{flows}"
                paths[pid] = [list(a_["pos"]), list(b_["pos"])]
                events.append({"type": "flow", "path": pid, "medium": arg.get("medium", "air"), "color": vocab.MEDIA[arg.get("medium", "air")], "t0": round(t0 + 0.8, 2), "t1": round(t1, 2)})
            elif name == "zoom":
                zoom_target = arg
        # the camera: an explicit zoom, else the parts this step introduced, else the whole thing
        if zoom_target and zoom_target != "all":
            focus = expand(zoom_target)
        elif zoom_target == "all" or st.get("_recap") or n == 0:
            focus = []
        else:
            focus = newly[:2] if 0 < len(newly) <= 2 else []
        if focus:
            ps = [placed[i] for i in focus]
            c = [sum(p["pos"][k] for p in ps) / len(ps) for k in range(3)]
            reach = max(p["radius"] for p in ps) + (max(math.dist(p["pos"], c) for p in ps) if len(ps) > 1 else 0)
            dist = max(MIN_FOCUS[template], reach * 6.0 + 3.0)
        else:
            c, dist = bounds["center"], max(MIN_WIDE[template], bounds["radius"] * 3.1)
        camera.append({"t": round(t0 + 0.2, 2), "target": [round(x, 3) for x in c], "dist": round(dist, 2), "yaw": round(yaw0 + 5 * n, 1), "pitch": pitch})
        t = t1
    end = t + 2.0
    camera.append({"t": round(end, 2), "target": bounds["center"], "dist": round(max(MIN_WIDE[template], bounds["radius"] * 3.1), 2), "yaw": round(yaw0 + 5 * len(steps), 1), "pitch": pitch})
    first = {}
    for e in events:
        if e["type"] == "reveal":
            for i in e["parts"]:
                first.setdefault(i, e["t0"])
    for i in placed:   # anything never mentioned appears with the last step so the lesson never hides a part forever
        if i not in first:
            events.append({"type": "reveal", "parts": [i], "t0": round(t - 1.0, 2)})
    return {"events": events, "camera": camera, "paths": paths, "steps": timeline_steps, "duration": round(end + 1.0, 2)}
