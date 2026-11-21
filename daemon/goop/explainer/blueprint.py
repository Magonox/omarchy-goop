"""The blueprint layout: for a machine whose assembled shape matters (a truck, a rocket, a submarine), the outline gives every part a box in ONE shared frame, so the parts
fit together by construction, the way Teardown builds real machines in real dimensions in one coordinate space. The frame: x runs back to front with the FRONT at +x (the machine
drives and flies toward +x), y is up with the ground at y = 0, z is left to right. A part may appear several times ("at" lists one centre per copy: four wheels are one part with four
centres), and its code only draws ONE copy filling the box.

This module checks a blueprint the way an engineer would: parts that pass through each other and parts floating loose are errors with numbers in them, so the model can fix them."""
import copy, math, re

from . import members, solids

LIMITS = {"coord": 10.0, "size": (0.1, 10.0), "copies": (1, 8), "overlap": 0.35, "radius": (0.03, 0.6), "joints": 40}
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,23}$")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def is_box(p):
    """A blueprint part: its "size" is a [width, height, depth] box (elsewhere "size" is small/medium/large)."""
    return isinstance(p.get("size"), list)


AXES = {"x": [1, 0, 0], "y": [0, 1, 0], "z": [0, 0, 1]}


def spin_axis(p):
    """The axis a part turns about, in the machine frame: the part's own `spin_axis` if the outline named one, else guessed from its box. A disc or a rod has two equal sides and one odd one,
    and it turns about the odd one (a wheel 2.4 x 2.4 x 1.2 about z, its axle; a rotor 3 x 0.3 x 3 about y); anything else turns about the vertical."""
    if p.get("spin_axis") in AXES:
        return AXES[p["spin_axis"]]
    dims = p["size"]
    for i in range(3):
        a, b = (dims[j] for j in range(3) if j != i)
        if abs(a - b) <= 0.15 * max(a, b) and abs(dims[i] - a) > 0.15 * max(a, b):
            return [1 if k == i else 0 for k in range(3)]
    return AXES["y"]


def validate_part(p, pid):
    errs, lo, hi = [], *LIMITS["size"]
    size, at = p.get("size"), p.get("at")
    if not (isinstance(size, list) and len(size) == 3 and all(_num(v) and lo <= v <= hi for v in size)):
        errs.append(f"part {pid!r}: size must be [width, height, depth], each between {lo:g} and {hi:g} (x front-to-back, y up, z left-right)")
    clo, chi = LIMITS["copies"]
    ok = isinstance(at, list) and clo <= len(at) <= chi and all(isinstance(c, list) and len(c) == 3 and all(_num(v) and abs(v) <= LIMITS["coord"] for v in c) for c in at)
    if not ok:
        errs.append(f"part {pid!r}: at must be a list of {clo}-{chi} centres like [[x, y, z]], one per copy of the part, each coordinate within +-{LIMITS['coord']:g}")
    if p.get("spin_axis") is not None and p["spin_axis"] not in AXES:
        errs.append(f"part {pid!r}: spin_axis must be one of: x, y, z (the axis it turns about: a wheel turns about its axle)")
    return errs


def _point(c):
    return isinstance(c, list) and len(c) == 3 and all(_num(v) and abs(v) <= LIMITS["coord"] for v in c)


def resolve(story):
    """(story, errors): a copy of a blueprint storyboard with its joints resolved. A part's `at` may name a joint instead of giving a point, and a `member` part (a tube from one
    joint to another) becomes an ordinary box in the machine frame with its mesh attached, so the rest of the pipeline treats it like any other part. Errors are written for the model."""
    out, errs = copy.deepcopy(story), []
    joints = out.get("joints")
    clean = {}
    if joints is not None:
        if not isinstance(joints, dict) or len(joints) > LIMITS["joints"]:
            errs.append(f"joints must be an object of up to {LIMITS['joints']} named points like {{\"bottom_bracket\": [0, 1, 0]}}")
        else:
            for name, c in joints.items():
                if not _NAME.match(str(name)) or not _point(c):
                    errs.append(f"joint {name!r}: the name must be lowercase letters, digits or _ and the point [x, y, z] with each coordinate within +-{LIMITS['coord']:g}")
                else:
                    clean[name] = [float(v) for v in c]
    for p in out.get("parts", []) if isinstance(out.get("parts"), list) else []:
        if not isinstance(p, dict):
            continue
        pid = p.get("id")
        if isinstance(p.get("at"), list):
            new = []
            for c in p["at"]:
                if isinstance(c, str):
                    if c in clean:
                        new.append(list(clean[c]))
                    else:
                        errs.append(f"part {pid!r}: at names a joint {c!r} that is not in joints")
                        new.append([0, 0, 0])
                else:
                    new.append(c)
            p["at"] = new
        if p.get("kind") == "solid":
            errs += _solid(p)
            continue
        if p.get("kind") != "member":
            continue
        a, b, r = clean.get(p.get("from")), clean.get(p.get("to")), p.get("radius", 0.08)
        zs = p.get("z", [0])
        bad = []
        if a is None or b is None:
            bad.append(f"from and to must be names of joints (known: {', '.join(clean) or 'none'})")
        elif a == b:
            bad.append("from and to are the same joint")
        if not (_num(r) and LIMITS["radius"][0] <= r <= LIMITS["radius"][1]):
            bad.append(f"radius must be a number between {LIMITS['radius'][0]:g} and {LIMITS['radius'][1]:g}")
        if not (isinstance(zs, list) and 1 <= len(zs) <= 4 and all(_num(v) and abs(v) <= LIMITS["coord"] for v in zs)):
            bad.append("z must be a list of up to 4 offsets across the machine, like [-0.2, 0.2], for a copy on each side")
        if bad:
            errs.append(f"member {pid!r}: " + "; ".join(bad))
            continue
        mid = [round((a[k] + b[k]) / 2, 4) for k in range(3)]
        mesh = members.tube([a[k] - mid[k] for k in range(3)], [b[k] - mid[k] for k in range(3)], r)
        p["_meshes"] = [{"look": "solid", "material": p.get("material", "steel"), **mesh}]
        p["size"] = [round(max(LIMITS["size"][0], abs(a[k] - b[k]) + 2 * r), 4) for k in range(3)]
        p["at"] = [[mid[0], mid[1], mid[2] + z] for z in zs]
    errs += _connections(out)
    return out, errs


VIEW_AXES = {"front": (0, 1), "side": (2, 1), "top": (0, 2)}       # which two axes of the shared frame each view shows: x and y, z and y, x and z


def _solid(p):
    """Build a sheet component from its features: its meshes (around its own centre), its box and place, its spin; and check what the sheet claims about it. Returns error sentences."""
    pid, errs = p.get("id"), []
    try:
        meshes = solids.compile_component(p.get("features"), p.get("material", "steel"))
    except ValueError as e:
        return [f"component {pid!r}: {e}"]
    lo, hi = solids.bounds(meshes)
    mid = [(lo[k] + hi[k]) / 2 for k in range(3)]
    for m in meshes:
        for k in range(len(m["p"])):
            m["p"][k] = round(m["p"][k] - mid[k % 3], 4)
    p["_meshes"] = meshes
    p["size"] = [round(max(LIMITS["size"][0], hi[k] - lo[k]), 4) for k in range(3)]
    p["at"] = [[round(x, 4) for x in mid]]
    p["_span"] = [lo, hi]
    extent = max(hi[k] - lo[k] for k in range(3))
    views = p.get("views")
    if views is not None:
        if not isinstance(views, dict) or any(k not in VIEW_AXES for k in views):
            errs.append(f"component {pid!r}: views may hold front [x0, x1, y0, y1], side [z0, z1, y0, y1] and top [x0, x1, z0, z1] only")
        else:
            for name, v in views.items():
                if not (isinstance(v, list) and len(v) == 4 and all(_num(x) for x in v)):
                    errs.append(f"component {pid!r}: the {name} view must be four numbers {VIEW_AXES_TEXT[name]}")
                    continue
                for axis, (want_lo, want_hi) in zip(VIEW_AXES[name], ((v[0], v[1]), (v[2], v[3]))):
                    tol = max(0.12, 0.08 * extent)
                    if abs(lo[axis] - want_lo) > tol or abs(hi[axis] - want_hi) > tol:
                        errs.append(f"component {pid!r}: your {name} view says it spans {'xyz'[axis]} {want_lo:g} to {want_hi:g}, but its features span {'xyz'[axis]} {lo[axis]:.2f} to {hi[axis]:.2f}: "
                                    f"fix the features or the view so they agree")
    out = p.get("out")
    if out is not None:                 # the way this component is taken out of the assembly, stated by the sheet (a dial leaves a watch through the front, not through the case wall)
        if out not in OUT:
            errs.append(f"component {pid!r}: out must be one of {', '.join(OUT)} (the direction it is taken out of the assembly; none for the body everything else comes out of)")
        else:
            p["_out"] = OUT[out]
    spin = p.get("spin")
    if spin is not None:
        axis, per = (spin or {}).get("axis", "z") if isinstance(spin, dict) else None, (spin or {}).get("period_s") if isinstance(spin, dict) else None
        piv = (spin or {}).get("pivot", mid) if isinstance(spin, dict) else None
        if not (isinstance(spin, dict) and axis in AXES and _num(per) and per > 0 and _point(piv) and spin.get("dir", "cw") in ("cw", "ccw")):
            errs.append(f"component {pid!r}: spin must be {{\"axis\": \"x|y|z\", \"pivot\": [x, y, z], \"period_s\": seconds for one turn, \"dir\": \"cw\" or \"ccw\"}}")
        else:
            p["spin_axis"] = axis
            p["_spin"] = {"pivot": [float(x) for x in piv], "period_s": float(per), "dir": spin.get("dir", "cw")}
    return errs


OUT = {"+x": [1.0, 0.0, 0.0], "-x": [-1.0, 0.0, 0.0], "+y": [0.0, 1.0, 0.0], "-y": [0.0, -1.0, 0.0], "+z": [0.0, 0.0, 1.0], "-z": [0.0, 0.0, -1.0], "none": [0.0, 0.0, 0.0]}
VIEW_AXES_TEXT = {"front": "[x0, x1, y0, y1]", "side": "[z0, z1, y0, y1]", "top": "[x0, x1, z0, z1]"}


def _span_of(p):
    """(lo, hi) of a part in the shared frame (all its copies), or None."""
    if p.get("_span"):
        return p["_span"]
    if isinstance(p.get("size"), list) and isinstance(p.get("at"), list) and p["at"]:
        lo = [min(c[k] - p["size"][k] / 2 for c in p["at"]) for k in range(3)]
        hi = [max(c[k] + p["size"][k] / 2 for c in p["at"]) for k in range(3)]
        return lo, hi
    return None


def _connections(story):
    """Errors for a sheet's `connections`: [{"a": id, "b": id, "at": [x, y, z]}]. Each point must lie on both components (within a small margin)."""
    conns = story.get("connections")
    if conns is None:
        return []
    errs, parts = [], {p.get("id"): p for p in story.get("parts", []) if isinstance(p, dict)}
    if not isinstance(conns, list) or len(conns) > 80:
        return ["connections must be a list of up to 80 items like {\"a\": \"seat\", \"b\": \"leg\", \"at\": [x, y, z]}"]
    for n, c in enumerate(conns, 1):
        if not (isinstance(c, dict) and c.get("a") in parts and c.get("b") in parts and _point(c.get("at"))):
            errs.append(f"connection {n}: needs a and b (ids of components) and at (the point [x, y, z] where they meet)")
            continue
        for who in (c["a"], c["b"]):
            span = _span_of(parts[who])
            if not span:
                continue
            extent = max(span[1][k] - span[0][k] for k in range(3))
            tol = max(0.12, 0.05 * extent)
            d = math.sqrt(sum(max(span[0][k] - c["at"][k], 0, c["at"][k] - span[1][k]) ** 2 for k in range(3)))
            if d > tol:
                errs.append(f"connection {c['a']!r} to {c['b']!r}: the point {c['at']} is {d:.2f} units from {who!r}, so they do not meet there; move the point or the component")
    return errs


def instances(p):
    """[(id, centre, size)] for every copy of a part; the first keeps the part's id, the others get id#2, id#3..."""
    return [(p["id"] if k == 0 else f"{p['id']}#{k + 1}", c, p["size"]) for k, c in enumerate(p["at"])]


def _span(c, s):
    return [(c[i] - s[i] / 2, c[i] + s[i] / 2) for i in range(3)]


def _overlap(a, b):
    """The fraction of the smaller box that the other one covers (0 = apart or touching, 1 = one is entirely inside the other)."""
    vol, small = 1.0, min(a[1][0] * a[1][1] * a[1][2], b[1][0] * b[1][1] * b[1][2])
    for (a0, a1), (b0, b1) in zip(_span(*a), _span(*b)):
        d = min(a1, b1) - max(a0, b0)
        if d <= 0:
            return 0.0
        vol *= d
    return vol / small if small > 0 else 0.0


def _gap(a, b):
    """The distance between two boxes (0 when they touch or overlap)."""
    return math.sqrt(sum(max(0.0, max(a0 - b1, b0 - a1)) ** 2 for (a0, a1), (b0, b1) in zip(_span(*a), _span(*b))))


def check(parts):
    """Errors for parts that pass through each other or float away from the rest. A part declared `inside` another may sit within it."""
    items = [(p["id"], pid, (c, s)) for p in parts for pid, c, s in instances(p)]
    inside = {p["id"]: p.get("inside") for p in parts}
    members_involved = {p["id"]: True for p in parts if p.get("kind") == "member"}       # tubes meet at joints, so their boxes always overlap: not an error
    lo = [min(_span(*box)[i][0] for _, _, box in items) for i in range(3)]
    hi = [max(_span(*box)[i][1] for _, _, box in items) for i in range(3)]
    extent = max(h - l for h, l in zip(hi, lo))
    errs, seen = [], set()
    for i, (ida, pa, a) in enumerate(items):
        near = False
        for j, (idb, pb, b) in enumerate(items):
            if i == j:
                continue
            if ida != idb and (inside.get(ida) == idb or inside.get(idb) == ida):     # a part inside another is allowed to sit within it
                near = True
                continue
            if _gap(a, b) <= max(0.35, 0.06 * extent):
                near = True
            if i < j and members_involved.get(ida) is None and members_involved.get(idb) is None:
                f = _overlap(a, b)
                key = tuple(sorted((pa, pb)))
                if f > LIMITS["overlap"] and key not in seen:
                    seen.add(key)
                    errs.append(f"parts {pa!r} and {pb!r} pass through each other (the smaller is {f:.0%} inside the other); move or resize their boxes so they touch without overlapping "
                                f"(or give one \"inside\": the other part's id if it really sits within it)")
        if not near and len(items) > 1:
            errs.append(f"part {pa!r} floats away from the rest of the machine; move its box so it touches the part it attaches to")
    return errs[:8]


def shift(parts):
    """The shift `place` applies to every part (centres the machine left-right and front-back and stands it on y = 0)."""
    items = [(p, pid, c, s) for p in parts for pid, c, s in instances(p)]
    lo = [min(c[i] - s[i] / 2 for _, _, c, s in items) for i in range(3)]
    hi = [max(c[i] + s[i] / 2 for _, _, c, s in items) for i in range(3)]
    return [-(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2]


_DIRS = ([0, 1, 0], [0, -1, 0], [1, 0, 0], [-1, 0, 0], [0, 0, 1], [0, 0, -1])


def free_directions(items):
    """{instance id: unit direction}: for every component, the way it can be pulled out of the assembly with the fewest others in its path. Its box is slid along each of the six axis
    directions (by its own length along that axis) and the other boxes it would pass through are counted (boxes are shrunk a little, since joined components touch). Ties go to the direction
    pointing away from the middle of the whole, then to up."""
    boxes = [(pid, c, s) for _, pid, c, s in items]
    mid = [sum(c[i] for _, c, _ in boxes) / len(boxes) for i in range(3)]
    stated = {pid: p["_out"] for p, pid, _, _ in items if p.get("_out") is not None}
    out = {}
    for pid, c, s in boxes:
        if pid in stated:               # the sheet said which way it comes out
            out[pid] = list(stated[pid])
            continue
        best = None
        for rank, d in enumerate(_DIRS):
            axis = next(k for k in range(3) if d[k])
            lo = [c[k] - s[k] / 2 for k in range(3)]
            hi = [c[k] + s[k] / 2 for k in range(3)]
            if d[axis] > 0:
                hi[axis] += s[axis] * 1.2
            else:
                lo[axis] -= s[axis] * 1.2
            blocked = 0
            for qid, qc, qs in boxes:
                if qid == pid:
                    continue
                if all(min(hi[k], qc[k] + qs[k] * 0.45) > max(lo[k], qc[k] - qs[k] * 0.45) for k in range(3)):
                    blocked += 1
            away = sum((c[k] - mid[k]) * d[k] for k in range(3))
            key = (blocked, -away, rank)
            if best is None or key < best[0]:
                best = (key, d)
        out[pid] = [float(x) for x in best[1]]
    return out


def place(parts):
    """-> [(storyboard part, instance id, centre, size)] shifted so the machine is centred left-right and front-back and stands on y = 0."""
    items = [(p, pid, c, s) for p in parts for pid, c, s in instances(p)]
    lo = [min(c[i] - s[i] / 2 for _, _, c, s in items) for i in range(3)]
    hi = [max(c[i] + s[i] / 2 for _, _, c, s in items) for i in range(3)]
    shift = [-(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2]
    return [(p, pid, [c[i] + shift[i] for i in range(3)], s) for p, pid, c, s in items]
