"""Custom parts: a part the model describes as a recipe of basic pieces (kind "custom"), for anything the ready-made shapes do not cover.
A piece is data only: a form, its dimensions, where it sits and how it is turned, in the part's own relative units. The engine measures and
places the whole part, so the model never positions anything in the scene. Free-form shapes are still plain numbers: `lathe` revolves a
profile (bottles, bowls, discs, vases, bulbs) and `extrude` gives a flat outline some height (gears, brackets, wings, logos).
All limits are enforced here; the renderer (shell/explainer3d/shapes.js, `custom`) builds exactly what passes this check."""
import math

from . import vocab

FORMS = {   # form -> the dimensions it needs (all in relative units)
    "box": ("w", "h", "d"),
    "cylinder": ("r", "h"),
    "cone": ("r", "h"),                 # optional "top" radius makes a frustum
    "sphere": ("r",),
    "ring": ("r", "t"),                 # a doughnut: major radius r, tube radius t
    "disc": ("r", "h"),                 # optional "hole" radius makes a CD / washer
    "lathe": ("profile",),              # [[radius, height], ...] revolved around the vertical axis
    "extrude": ("outline", "h"),        # [[x, z], ...] outline pushed up by h
}
LOOKS = ("solid", "glass", "glow", "screen", "led")
LIMITS = {"pieces": (1, 24), "points": (2, 24), "repeat": (2, 24), "dim": (0.005, 4.0), "at": 3.0, "total": 120}
AXES = {"x": 0, "y": 1, "z": 2}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _vec(v, n, lim):
    return isinstance(v, list) and len(v) == n and all(_num(x) and abs(x) <= lim for x in v)


def validate(pieces, where):
    """Error strings for a custom part's `pieces`; each names the valid choices so a model can repair its own answer."""
    errs, lo, hi = [], *LIMITS["pieces"]
    if not isinstance(pieces, list) or not lo <= len(pieces) <= hi:
        return [f"{where}: a custom part needs pieces: a list of {lo}-{hi} pieces, each like {{\"form\":\"cylinder\",\"r\":0.5,\"h\":0.2,\"at\":[0,0,0]}}"]
    total = 0
    for n, pc in enumerate(pieces, 1):
        w = f"{where} piece {n}"
        if not isinstance(pc, dict) or pc.get("form") not in FORMS:
            errs.append(f"{w}: form must be one of: {', '.join(FORMS)}")
            continue
        form = pc["form"]
        dlo, dhi = LIMITS["dim"]
        for key in FORMS[form]:
            val = pc.get(key)
            if key in ("profile", "outline"):
                pl, ph = LIMITS["points"]
                ok = isinstance(val, list) and (3 if key == "outline" else pl) <= len(val) <= ph and all(
                    _vec(p, 2, LIMITS["at"]) and (key != "profile" or p[0] >= 0) for p in val)
                if not ok:
                    errs.append(f"{w}: {form} needs {key}: {'3' if key == 'outline' else '2'}-{ph} points like [[x, y]], numbers within +-{LIMITS['at']:g}"
                                + (" (radius first, never negative)" if key == "profile" else ""))
            elif not (_num(val) and dlo <= val <= dhi):
                errs.append(f"{w}: {form} needs {key} between {dlo:g} and {dhi:g}")
        for key in ("top", "hole"):
            if key in pc and not (_num(pc[key]) and 0 <= pc[key] <= dhi):
                errs.append(f"{w}: {key} must be a number between 0 and {dhi:g}")
        if "at" in pc and not _vec(pc["at"], 3, LIMITS["at"]):
            errs.append(f"{w}: at must be [x, y, z] within +-{LIMITS['at']:g}")
        if "turn" in pc and not _vec(pc["turn"], 3, 360):
            errs.append(f"{w}: turn must be [rx, ry, rz] in degrees")
        if pc.get("material", "steel") not in vocab.MATERIALS:
            errs.append(f"{w}: material must be one of: {', '.join(vocab.MATERIALS)}")
        if pc.get("look", "solid") not in LOOKS:
            errs.append(f"{w}: look must be one of: {', '.join(LOOKS)}")
        count = 1
        rep = pc.get("repeat")
        if rep is not None:
            rlo, rhi = LIMITS["repeat"]
            if not (isinstance(rep, dict) and isinstance(rep.get("count"), int) and rlo <= rep["count"] <= rhi
                    and (rep.get("around") in AXES or _vec(rep.get("along"), 3, LIMITS["at"]))):
                errs.append(f"{w}: repeat needs count {rlo}-{rhi} and either around (x, y or z: copies spin around the part's centre) "
                            f"or along ([dx, dy, dz]: copies step along a line)")
            else:
                count = rep["count"]
        total += count
    if not errs and total > LIMITS["total"]:
        errs.append(f"{where}: {total} pieces after repeats; keep it under {LIMITS['total']}")
    return errs


def _local_box(pc):
    """Half-extent corners of one piece around its own origin, as ((x0, y0, z0), (x1, y1, z1))."""
    f = pc["form"]
    if f == "box":
        hx, hy, hz = pc["w"] / 2, pc["h"] / 2, pc["d"] / 2
        return (-hx, -hy, -hz), (hx, hy, hz)
    if f in ("cylinder", "cone", "disc"):
        r = max(pc["r"], pc.get("top", 0))
        return (-r, -pc["h"] / 2, -r), (r, pc["h"] / 2, r)
    if f == "sphere":
        return (-pc["r"],) * 3, (pc["r"],) * 3
    if f == "ring":
        e = pc["r"] + pc["t"]
        return (-e, -pc["t"], -e), (e, pc["t"], e)
    if f == "lathe":
        r = max(p[0] for p in pc["profile"])
        return (-r, min(p[1] for p in pc["profile"]), -r), (r, max(p[1] for p in pc["profile"]), r)
    xs, zs = [p[0] for p in pc["outline"]], [p[1] for p in pc["outline"]]
    return (min(xs), -pc["h"] / 2, min(zs)), (max(xs), pc["h"] / 2, max(zs))


def _rot(v, rx, ry, rz):
    """Same order as the renderer's transform: x, then y, then z, in degrees."""
    d = math.pi / 180
    x, y, z = v
    a = y * math.cos(rx * d) - z * math.sin(rx * d); b = y * math.sin(rx * d) + z * math.cos(rx * d)
    y, z = a, b
    a = x * math.cos(ry * d) + z * math.sin(ry * d); b = -x * math.sin(ry * d) + z * math.cos(ry * d)
    x, z = a, b
    a = x * math.cos(rz * d) - y * math.sin(rz * d); b = x * math.sin(rz * d) + y * math.cos(rz * d)
    return [a, b, z]


def corners(pieces):
    """Every corner of every (repeated, turned) piece, in the part's relative units."""
    pts = []
    for pc in pieces:
        (x0, y0, z0), (x1, y1, z1) = _local_box(pc)
        tx, ty, tz = pc.get("turn", [0, 0, 0])
        at = pc.get("at", [0, 0, 0])
        base = [[a + b for a, b in zip(_rot([x, y, z], tx, ty, tz), at)] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
        rep = pc.get("repeat")
        if not rep:
            pts += base
        elif "around" in rep:
            for k in range(rep["count"]):
                ang = 360.0 * k / rep["count"]
                pts += [_rot(p, ang if rep["around"] == "x" else 0, ang if rep["around"] == "y" else 0, ang if rep["around"] == "z" else 0) for p in base]
        else:
            pts += [[p[i] + k * rep["along"][i] for i in range(3)] for k in range(rep["count"]) for p in base]
    return pts


def measure(pieces, scale):
    """{"r": widest reach sideways, "h": height, "center": [x, y, z]} of the whole part in scene units (the renderer centres it on the origin)."""
    pts = corners(pieces)
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    center = [(lo[i] + hi[i]) / 2 for i in range(3)]
    r = max(math.hypot(p[0] - center[0], p[2] - center[2]) for p in pts)
    return {"r": round(r * scale, 3), "h": round((hi[1] - lo[1]) * scale, 3), "center": [round(c * scale, 4) for c in center]}
