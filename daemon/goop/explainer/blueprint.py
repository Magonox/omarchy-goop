"""The blueprint layout: for a machine whose assembled shape matters (a truck, a rocket, a submarine), the outline gives every part a box in ONE shared frame, so the parts
fit together by construction, the way Teardown builds real machines in real dimensions in one coordinate space. The frame: x runs back to front with the FRONT at +x (the machine
drives and flies toward +x), y is up with the ground at y = 0, z is left to right. A part may appear several times ("at" lists one centre per copy: four wheels are one part with four
centres), and its code only draws ONE copy filling the box.

This module checks a blueprint the way an engineer would: parts that pass through each other and parts floating loose are errors with numbers in them, so the model can fix them."""
import math

LIMITS = {"coord": 10.0, "size": (0.1, 10.0), "copies": (1, 8), "overlap": 0.35}


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
            if i < j:
                f = _overlap(a, b)
                key = tuple(sorted((pa, pb)))
                if f > LIMITS["overlap"] and key not in seen:
                    seen.add(key)
                    errs.append(f"parts {pa!r} and {pb!r} pass through each other (the smaller is {f:.0%} inside the other); move or resize their boxes so they touch without overlapping "
                                f"(or give one \"inside\": the other part's id if it really sits within it)")
        if not near and len(items) > 1:
            errs.append(f"part {pa!r} floats away from the rest of the machine; move its box so it touches the part it attaches to")
    return errs[:8]


def place(parts):
    """-> [(storyboard part, instance id, centre, size)] shifted so the machine is centred left-right and front-back and stands on y = 0."""
    items = [(p, pid, c, s) for p in parts for pid, c, s in instances(p)]
    lo = [min(c[i] - s[i] / 2 for _, _, c, s in items) for i in range(3)]
    hi = [max(c[i] + s[i] / 2 for _, _, c, s in items) for i in range(3)]
    shift = [-(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2]
    return [(p, pid, [c[i] + shift[i] for i in range(3)], s) for p, pid, c, s in items]
