"""Layout templates: turn named parts and relations into positions. Deterministic, so the model never has to place anything in 3D.
Every template returns {placed, instances, bounds}: `placed` maps an id to its pose, `instances` maps a storyboard part id to the placed ids
it became (a part attached "at sides" or in a "ring" becomes several)."""
import math

from . import vocab


def _shape(part):
    kind = vocab.KINDS[part["kind"]]
    f = vocab.SIZES[part.get("size", "medium")]
    shape = {k: (round(v * f, 3) if k in ("r", "h", "w", "d", "t", "r0", "r1") else v) for k, v in kind.items() if k != "material"}
    if part["kind"] == "device":
        shape["variant"] = part.get("variant", "laptop")
    return shape


def _radius(shape):
    return max(shape.get("r", 0), shape.get("h", 0) / 2, shape.get("w", 0) / 2, shape.get("r0", 0))


def _place(part, pid=None):
    shape = _shape(part)
    return {"id": pid or part["id"], "group": part["id"], "kind": part["kind"], "label": part["label"], "shape": shape,
            "material": part.get("material") or vocab.KINDS[part["kind"]]["material"],
            "pos": [0, 0, 0], "rot": [0, 0, 0], "explode": [0, 0, 0], "radius": round(_radius(shape), 3), "spanning": bool(vocab.KINDS[part["kind"]].get("spanning"))}


def _r3(v):
    return [round(x, 3) for x in v]


def axis(story):
    placed, parts = {}, story["parts"]
    for p in parts:
        placed[p["id"]] = _place(p)
    order = [p for p in parts if not placed[p["id"]]["spanning"]]
    gap = 0.3
    total = sum(placed[p["id"]]["shape"]["h"] for p in order) + gap * (len(order) - 1)
    x, n = -total / 2, len(order)
    for i, p in enumerate(order):
        pl = placed[p["id"]]
        ln = pl["shape"]["h"]
        pl["pos"] = _r3([x + ln / 2, 0, 0])
        x += ln + gap
        axial = vocab.KINDS[p["kind"]].get("axial")
        pl["rot"] = [0, 0, -90] if axial else [0, 0, 0]
        pl["explode"] = _r3([(i - (n - 1) / 2) * 1.1, 1.5 if i % 2 == 0 else -1.5, 0])
    for p in parts:
        pl = placed[p["id"]]
        if not pl["spanning"]:
            continue
        a, b = (placed[r] for r in p["spans"])
        lo = min(a["pos"][0] - a["shape"]["h"] / 2, b["pos"][0] - b["shape"]["h"] / 2)
        hi = max(a["pos"][0] + a["shape"]["h"] / 2, b["pos"][0] + b["shape"]["h"] / 2)
        inside = [q for q in order if lo - 1e-6 <= placed[q["id"]]["pos"][0] <= hi + 1e-6]
        widest = max((placed[q["id"]]["radius"] for q in inside), default=1.0)
        pl["rot"] = [0, 0, -90]
        pl["pos"] = _r3([(lo + hi) / 2, 0, 0])
        pl["shape"]["h"] = round(hi - lo + (0.4 if pl["kind"] == "casing" else 0.2), 3)
        if pl["kind"] == "casing":
            pl["shape"]["r"] = round(widest * 1.14, 3)
            pl["radius"] = pl["shape"]["r"]
    return placed, {p["id"]: [p["id"]] for p in parts}


def network(story):
    placed, parts = {}, story["parts"]
    for p in parts:
        placed[p["id"]] = _place(p)
    router = next(p for p in parts if p["kind"] == "router")
    rpos = [-4.6, placed[router["id"]]["shape"]["h"] / 2, 0.0]
    placed[router["id"]]["pos"] = _r3(rpos)
    devices = [p for p in parts if p["kind"] == "device"]
    n = len(devices)
    angles = [0.0] if n == 1 else [-38 + 76 * i / (n - 1) for i in range(n)]
    walls = [p for p in parts if p["kind"] == "wall"]
    for a, d in zip(angles, devices):
        pl = placed[d["id"]]
        dist = vocab.DISTANCES[d.get("distance", "medium")]
        ar = math.radians(a)
        pl["pos"] = _r3([rpos[0] + dist * math.cos(ar), pl["shape"]["h"] / 2, dist * math.sin(ar)])
        pl["rot"] = [0, round(-(a + 180) + 0, 3), 0]            # face the router
        crossing = sum(1 for w in walls if router["id"] in w["between"] and d["id"] in w["between"])
        steps = {"near": 0, "medium": 1, "far": 2}[d.get("distance", "medium")]
        pl["signal"] = max(1, 4 - steps - crossing)
        pl["distance"] = dist
    for w in walls:
        a, b = (placed[r] for r in w["between"])
        mid = [(a["pos"][0] + b["pos"][0]) / 2, 0, (a["pos"][2] + b["pos"][2]) / 2]
        theta = math.degrees(math.atan2(b["pos"][2] - a["pos"][2], b["pos"][0] - a["pos"][0]))
        pl = placed[w["id"]]
        pl["pos"] = _r3([mid[0] + 0.01, pl["shape"]["h"] / 2, mid[2]])
        pl["rot"] = [0, round(-(theta + 90), 3), 0]
    floor = {"id": "floor", "group": "floor", "kind": "box", "label": "Room", "shape": {"type": "floor", "w": 15.0, "h": 0.12, "d": 10.0, "r": 7.5},
             "material": "concrete", "pos": [0, -0.06, 0], "rot": [0, 0, 0], "explode": [0, 0, 0], "radius": 7.5, "spanning": False, "context": True}
    placed["floor"] = floor
    return placed, {p["id"]: [p["id"]] for p in parts}


def assembly(story):
    placed, instances, parts = {}, {}, story["parts"]
    for p in parts:
        placed[p["id"]] = _place(p)
        instances[p["id"]] = [p["id"]]
    by_id = {p["id"]: p for p in parts}
    spine = [p for p in parts if not p.get("attach") and not p.get("inside")]
    gap, y = 0.14, 0.0
    n = len(spine)
    for i, p in enumerate(spine):
        pl = placed[p["id"]]
        pl["pos"] = _r3([0, y + pl["shape"]["h"] / 2, 0])
        y += pl["shape"]["h"] + gap
        pl["explode"] = _r3([0, (i - (n - 1) / 2) * 1.25, 0])
    shift = (y - gap) / 2
    for p in spine:
        placed[p["id"]]["pos"][1] = round(placed[p["id"]]["pos"][1] - shift, 3)
    for p in parts:
        if p.get("inside"):
            par = placed[p["inside"]]
            placed[p["id"]]["pos"] = list(par["pos"])
            placed[p["id"]]["explode"] = [0, 0, 2.8]
    for p in parts:
        att = p.get("attach")
        if not att:
            continue
        par = placed[att["to"]]
        pr, ph, pp = par["shape"].get("r", 1.0), par["shape"].get("h", 1.0), par["pos"]
        base = placed.pop(p["id"])
        shp = base["shape"]
        half_w = shp.get("w", 2 * shp.get("r", 0.5)) / 2
        at, count = att["at"], att.get("count", 1)
        spots = []   # (pos, rot, explode)
        if at in ("left", "right", "sides"):
            for sgn in ([-1, 1] if at == "sides" else [-1 if at == "left" else 1]):
                spots.append(([pp[0] + sgn * (pr + 0.12 + half_w), pp[1], pp[2]], [0, 0, 0], [sgn * 2.6, 0, 0]))
        elif at == "top":
            spots.append(([pp[0], pp[1] + ph / 2 + shp.get("h", 0.5) / 2 + 0.05, pp[2]], [0, 0, 0], [0, 2.4, 0]))
        elif at == "bottom":
            spots.append(([pp[0], pp[1] - ph / 2 - shp.get("h", 0.5) / 2 - 0.05, pp[2]], [0, 0, 0], [0, -2.4, 0]))
        elif at in ("front", "back"):
            sgn = 1 if at == "front" else -1
            spots.append(([pp[0], pp[1], pp[2] + sgn * (pr + shp.get("r", 0.5) * 0.8)], [-55 * sgn if p["kind"] == "dish" else 0, 0, 0], [0, 0, sgn * 2.6]))
        else:   # ring around the parent, pointing outward
            for k in range(count):
                a = 2 * math.pi * k / count
                spots.append(([pp[0] + (pr + 0.05) * math.cos(a), pp[1] - ph * 0.28, pp[2] + (pr + 0.05) * math.sin(a)],
                              [0, round(-math.degrees(a), 3), 0], [math.cos(a) * 2.2, 0, math.sin(a) * 2.2]))
        instances[p["id"]] = []
        for k, (pos, rot, exp) in enumerate(spots):
            pid = p["id"] if k == 0 else f"{p['id']}_{k + 1}"
            pl = dict(base, id=pid, pos=_r3(pos), rot=rot, explode=_r3(exp))
            placed[pid] = pl
            instances[p["id"]].append(pid)
    return placed, instances


TEMPLATES = {"axis": axis, "network": network, "assembly": assembly}


def layout(story):
    out = TEMPLATES[story["layout"]["template"]](story)
    placed, instances = out
    lo, hi = [1e9] * 3, [-1e9] * 3
    for pl in placed.values():
        for k in range(3):
            reach = pl["radius"] + (abs(pl["explode"][k]) * 0.6)
            lo[k], hi[k] = min(lo[k], pl["pos"][k] - reach), max(hi[k], pl["pos"][k] + reach)
    center = [(a + b) / 2 for a, b in zip(lo, hi)]
    radius = max(b - a for a, b in zip(lo, hi)) / 2
    return {"placed": placed, "instances": instances, "bounds": {"center": _r3(center), "radius": round(radius, 3)}}
