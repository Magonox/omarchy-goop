"""Turn steps into a timeline: when each action starts and stops, plus camera shots. Durations come from the narration length, so a step
lasts as long as the sentence takes to say (the voice is synced in a later step)."""
import math

from . import vocab

WORDS_PER_SECOND = 2.35
TEMPLATE_VIEW = {"axis": (-26, 16), "network": (-16, 42), "assembly": (-24, 13), "blueprint": (-26, 14)}      # base yaw, pitch in degrees
MIN_WIDE = {"axis": 14.0, "network": 22.0, "assembly": 13.0, "blueprint": 12.0}                           # never closer than this for the whole-model shot
MIN_FOCUS = {"axis": 9.0, "network": 13.0, "assembly": 13.0, "blueprint": 9.0}                            # or this when focusing on one part


GO_AT = 5.4            # seconds into the finale step when the assembled thing sets off (parts spread, hold, then snap together)
PITCH_FOR = {"launch": 5, "drive": 9, "sink": 4, "fly": 9}


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
    fin = story.get("finale")
    fin_cfg = vocab.FINALES.get(fin["motion"]) if fin else None
    if fin:
        steps.append({"say": fin["say"], "do": [{"zoom": "all"}], "_finale": True})
    if story.get("recap"):
        steps.append({"say": story["recap"], "do": [{"explode": []}, {"zoom": "all"}], "_recap": True})
    teardown = template == "blueprint"       # the whole machine first, assembled; then taken apart while each part is explained; the finale puts it back together
    events, camera, timeline_steps, finale, step_t0 = [], [], [], None, []
    revealed, flows, paths = set(), 0, {}
    t = 0.0
    for n, st in enumerate(steps):
        dur = duration(st["say"] + " " + (st.get("analogy") or ""))
        if st.get("_finale"):
            dur = max(dur, GO_AT + fin_cfg["seconds"] + 0.6)
        t0, t1 = t, t + dur
        step_t0.append(t0)
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
            if teardown:          # a teardown starts with the finished machine: every part is there, assembled
                newly = list(dict.fromkeys(movable + newly))
        if newly:
            events.append({"type": "reveal", "parts": newly, "t0": round(t0 + 0.35, 2)})
            revealed.update(newly)
        zoom_target = None
        if st.get("_finale"):      # the parts fly apart (unless they already hang apart), hang for a moment, then snap together over two seconds
            if not teardown:
                events.append({"type": "explode", "parts": movable, "t0": round(t0 + 0.3, 2), "t1": round(t0 + GO_AT - 0.4, 2), "settle": 2.2})
            finale = {"motion": fin["motion"], "t0": round(t0, 2), "t_go": round(t0 + GO_AT, 2), "dur": fin_cfg["seconds"], "heading": fin_cfg["heading"], "env": fin_cfg["env"],
                      "effects": fin_cfg["effects"], "center": [round(x, 3) for x in bounds["center"]], "radius": round(bounds["radius"], 3),
                      "emitter": placed[instances[fin["emitter"]][0]]["pos"] if fin.get("emitter") else None}
            vert = [p["radius"] if p["rot"][2] else p["shape"]["h"] / 2 for p in (placed[i] for i in movable)]
            finale["bottom"] = round(min(placed[i]["pos"][1] - v for i, v in zip(movable, vert)), 3)
            finale["top"] = round(max(placed[i]["pos"][1] + v for i, v in zip(movable, vert)), 3)
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
        elif zoom_target == "all" or st.get("_recap") or st.get("_finale") or n == 0:
            focus = []
        else:
            focus = newly[:2] if 0 < len(newly) <= 2 else []
        if focus:
            ps = [placed[i] for i in focus]
            hang = teardown and n >= 1 and not st.get("_finale") and not st.get("_recap")       # the parts hang apart now, so aim where they really are
            c = [sum(p["pos"][k] + (p["explode"][k] if hang else 0) for p in ps) / len(ps) for k in range(3)]
            reach = max(p["radius"] for p in ps) + (max(math.dist([p["pos"][k] + (p["explode"][k] if hang else 0) for k in range(3)], c) for p in ps) if len(ps) > 1 else 0)
            dist = max(MIN_FOCUS[template], reach * 6.0 + 3.0)
        else:
            c, dist = bounds["center"], max(MIN_WIDE[template], bounds["radius"] * 3.1)
        camera.append({"t": round(t0 + 0.2, 2), "target": [round(x, 3) for x in c], "dist": round(dist, 2), "yaw": round(yaw0 + 5 * n, 1),
                       "pitch": PITCH_FOR[fin["motion"]] if st.get("_finale") else pitch})
        t = t1
    end = t + 2.0
    if teardown and len(step_t0) > 1:      # one long explode: out at the start of step 2, held through the explanations, back together as the finale (or the recap) begins
        fin_i = next((i for i, s in enumerate(steps) if s.get("_finale")), None)
        rec_i = next((i for i, s in enumerate(steps) if s.get("_recap")), None)
        if fin_i is not None:
            t_back, settle = step_t0[fin_i] + GO_AT - 0.4, 2.2
        else:
            t_back, settle = (step_t0[rec_i] + 0.2 if rec_i else t - 0.2), 1.6
        if t_back - (step_t0[1] + 0.4) > settle + 1.2:
            events.append({"type": "explode", "parts": movable, "t0": round(step_t0[1] + 0.4, 2), "t1": round(t_back, 2), "settle": settle})
    camera.append({"t": round(end, 2), "target": bounds["center"], "dist": round(max(MIN_WIDE[template], bounds["radius"] * 3.1), 2), "yaw": round(yaw0 + 5 * len(steps), 1), "pitch": pitch})
    first = {}
    for e in events:
        if e["type"] == "reveal":
            for i in e["parts"]:
                first.setdefault(i, e["t0"])
    for i in placed:   # anything never mentioned appears with the last step so the lesson never hides a part forever
        if i not in first:
            events.append({"type": "reveal", "parts": [i], "t0": round(t - 1.0, 2)})
    return {"events": events, "camera": camera, "paths": paths, "steps": timeline_steps, "duration": round(end + 1.0, 2), "finale": finale}
