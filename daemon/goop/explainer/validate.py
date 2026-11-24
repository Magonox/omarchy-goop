"""Geometry checks on a built scene: do the parts really fit together the way the lesson says?

The model is poor at 3D placement, so instead of trusting it (or asking it to look again) the numbers are checked here, in plain Python, on the meshes
the scene already holds. Every finding is a sentence with numbers in it, so it can go straight back to the model as a repair request.

    check(scene) -> [Finding]       scene = the dict the renderer reads (build.load); a part's geometry is inline ("meshes") or in its "file"

What is checked (blueprint and assembly lessons, where the parts make up one thing):
  inside     a part the plan put "inside" another one whose box is not inside that part's box
  attach     a part the plan "attached" to another one that does not touch it
  people     a part that is a person, rider, driver, pilot, passenger, animal or character (lessons show the machine alone)
  overlap    two parts whose boxes cut deeply into each other although neither is declared to be inside the other
  floating   a part, or a group of parts, that touches nothing else
  size       a part that came out clearly bigger or smaller than the size the plan gave it
  ground     part of a blueprint machine below the ground (y < 0)

Boxes are axis-aligned boxes around each part's mesh (after the part's own scale, position and rotation), so the overlap test is a screening test
(a wheel inside a frame's box is reported, a wheel next to the frame is not), and "touching" means the nearest surface points are close. Both are
deliberately simple and fast (a few milliseconds per lesson); they find the faults a person sees at a glance."""
import json, math, os
from dataclasses import dataclass

PEOPLE = ("person", "people", "rider", "driver", "pilot", "passenger", "human", "man", "woman", "child", "boy", "girl", "character", "mascot", "animal", "cyclist", "astronaut")
SAMPLES = 400          # surface points kept per part for the distance test
CHECKED_TEMPLATES = ("blueprint", "assembly")


@dataclass
class Finding:
    kind: str          # people | overlap | floating | size | ground
    parts: tuple       # the part ids involved
    message: str       # plain sentence with numbers, written for the model that has to fix it

    def __str__(self):
        return f"[{self.kind}] {self.message}"


def _meshes(part):
    shape = part.get("shape") or {}
    if shape.get("meshes"):
        return shape["meshes"], shape.get("scale", 1) or 1
    path = shape.get("file")
    if path and os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        return data.get("meshes") or [], data.get("scale") or shape.get("scale", 1) or 1     # the part file's own scale is the one the renderer uses
    return [], 1


def _rotate(pt, rot):
    """Euler degrees applied x, then y, then z (the renderer's eulerRotation order is not verified, so a turned part is only approximate)."""
    x, y, z = pt
    rx, ry, rz = (math.radians(a) for a in rot)
    y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
    x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
    x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
    return x, y, z


def _surface(m):
    """Points on a mesh's surface: its vertices plus, for every triangle, the middles of its edges and its centre, so a big flat face is not represented by its corners alone."""
    p, ix = m.get("p") or [], m.get("i") or []
    v = [(p[i], p[i + 1], p[i + 2]) for i in range(0, len(p) - 2, 3)]
    pts = list(v)
    for t in range(0, len(ix) - 2, 3):
        try:
            a, b, c = v[ix[t]], v[ix[t + 1]], v[ix[t + 2]]
        except IndexError:
            continue
        pts.append(tuple((a[k] + b[k]) / 2 for k in range(3)))
        pts.append(tuple((b[k] + c[k]) / 2 for k in range(3)))
        pts.append(tuple((a[k] + c[k]) / 2 for k in range(3)))
        pts.append(tuple((a[k] + b[k] + c[k]) / 3 for k in range(3)))
    return pts


def world_points(part):
    """The part's surface points in the scene (thinned to about SAMPLES for the distance test) plus its box (lo, hi)."""
    meshes, k = _meshes(part)
    pos, rot = part.get("pos") or [0, 0, 0], part.get("rot") or [0, 0, 0]
    pts = []
    for m in meshes:
        pts.extend((q[0] * k, q[1] * k, q[2] * k) for q in _surface(m))
    if not pts:
        return [], None
    if any(rot):
        pts = [_rotate(q, rot) for q in pts]
    pts = [(q[0] + pos[0], q[1] + pos[1], q[2] + pos[2]) for q in pts]
    lo = tuple(min(q[a] for q in pts) for a in range(3))
    hi = tuple(max(q[a] for q in pts) for a in range(3))
    step = max(1, len(pts) // SAMPLES)
    return pts[::step], (lo, hi)


def _box_gap(ba, bb):
    """Distance between two boxes (0 when they touch or overlap): a lower bound for the distance between the parts inside them."""
    return math.sqrt(sum(max(0.0, max(ba[0][i] - bb[1][i], bb[0][i] - ba[1][i])) ** 2 for i in range(3)))


def _gap(a, b, stop=0.0):
    """Smallest distance between two point clouds (brute force on the thinned samples). With `stop`, gives up as soon as a pair closer than that is found (the exact value
    does not matter once two parts are known to touch)."""
    best, limit = math.inf, stop * stop
    for p in a:
        for q in b:
            d = (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2
            if d < best:
                best = d
                if best <= limit:
                    return math.sqrt(best)
    return math.sqrt(best)


def _overlap(ba, bb):
    """(depth, fraction): how deep two boxes cut into each other (the smallest overlap along any axis) and what share of the smaller box that is, or None."""
    ext = [min(ba[1][i], bb[1][i]) - max(ba[0][i], bb[0][i]) for i in range(3)]
    if min(ext) <= 0:
        return None
    vol = ext[0] * ext[1] * ext[2]
    va = math.prod(ba[1][i] - ba[0][i] for i in range(3))
    vb = math.prod(bb[1][i] - bb[0][i] for i in range(3))
    return min(ext), vol / max(min(va, vb), 1e-9)


def _contains(outer, inner, slack):
    """Does the outer box hold the inner one completely (a piston in its cylinder, a valve in its head)? That is nesting, not a collision."""
    return all(outer[0][i] - slack <= inner[0][i] and inner[1][i] <= outer[1][i] + slack for i in range(3))


def _inside(part, other):
    """Is the part declared to be inside (or part of) the other one?"""
    ctx = part.get("context")
    return any(part.get(k) == other.get("id") or other.get(k) == part.get("id") for k in ("inside", "attach_to", "parent")) or ctx is True


def check(scene, story=None, gap_tolerance=0.04, overlap_limit=0.35):
    """All findings for a scene (an empty list means nothing was wrong). `gap_tolerance` is the share of the model's size that still counts as touching.
    `story` is the outline the scene was built from: with it the relations the plan declared ("inside", "attach") are checked against the real geometry."""
    findings = []
    parts = scene.get("parts") or []
    for p in parts:
        words = f"{p.get('id', '')} {p.get('label', '')}".lower().replace("_", " ").split()
        hit = next((w for w in PEOPLE if w in words), None)
        if hit:
            findings.append(Finding("people", (p["id"],), f"'{p.get('label') or p['id']}' is a {hit}: remove it, lessons show the machine alone"))
    if scene.get("template") not in CHECKED_TEMPLATES:
        return findings
    data = {}
    for p in parts:
        pts, box = world_points(p)
        if box:
            data[p["id"]] = (p, pts, box)
    if len(data) < 2:
        return findings
    lo = [min(b[2][0][a] for b in data.values()) for a in range(3)]
    hi = [max(b[2][1][a] for b in data.values()) for a in range(3)]
    size = max(hi[a] - lo[a] for a in range(3)) or 1.0
    tol = gap_tolerance * size

    ids = list(data)
    # components the plan joins may reach into each other (a crown's stem in the case, a tenon in its mortise): that is a joint, not a collision
    joined = {frozenset((c.get("a"), c.get("b"))) for c in (story or {}).get("connections") or [] if isinstance(c, dict)}
    touching = {i: set() for i in ids}
    for ai in range(len(ids)):
        for bi in range(ai + 1, len(ids)):
            a, b = data[ids[ai]], data[ids[bi]]
            ov = _overlap(a[2], b[2])
            if ov and not _inside(a[0], b[0]) and frozenset((ids[ai], ids[bi])) not in joined and ov[1] > overlap_limit and ov[0] > tol and not (_contains(a[2], b[2], tol) or _contains(b[2], a[2], tol)):
                findings.append(Finding("overlap", (ids[ai], ids[bi]),
                                        f"'{a[0].get('label') or ids[ai]}' and '{b[0].get('label') or ids[bi]}' cut into each other by {ov[0]:.2f} units "
                                        f"({ov[1] * 100:.0f}% of the smaller part's box): move one by about that much"))
            if ov or (_box_gap(a[2], b[2]) <= tol and _gap(a[1], b[1], tol) <= tol):
                touching[ids[ai]].add(ids[bi])
                touching[ids[bi]].add(ids[ai])

    seen, groups = set(), []
    for i in ids:
        if i in seen:
            continue
        stack, comp = [i], []
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            comp.append(n)
            stack.extend(touching[n] - seen)
        groups.append(comp)
    if len(groups) > 1:
        groups.sort(key=len, reverse=True)
        main = groups[0]
        for comp in groups[1:]:
            names = ", ".join(f"'{data[c][0].get('label') or c}'" for c in comp)
            nearest = min(((_box_gap(data[c][2], data[m][2]), c, m) for c in comp for m in main), key=lambda t: t[0])
            nearest = (_gap(data[nearest[1]][1], data[nearest[2]][1]), nearest[1], nearest[2])      # the surfaces, not just the boxes (a wheel's box can overlap a frame it never touches)
            findings.append(Finding("floating", tuple(comp), f"{names} touch{'es' if len(comp) == 1 else ''} nothing else: the nearest part is "
                                    f"'{data[nearest[2]][0].get('label') or nearest[2]}', {nearest[0]:.2f} units away; place it so it meets that part"))

    for q in (story or {}).get("parts", []):
        pid = q.get("id")
        if pid not in data:
            continue
        label = data[pid][0].get("label") or pid
        if q.get("inside") in data:                      # declared inside another part: its box must sit within the container's box
            cont = data[q["inside"]]
            if not _contains(cont[2], data[pid][2], tol):
                far = math.dist([(data[pid][2][0][a] + data[pid][2][1][a]) / 2 for a in range(3)], [(cont[2][0][a] + cont[2][1][a]) / 2 for a in range(3)])
                findings.append(Finding("inside", (pid, q["inside"]), f"'{label}' is declared inside '{cont[0].get('label') or q['inside']}' but its centre is {far:.2f} units "
                                        f"from that part's centre and it sticks out of its box: put it inside"))
        att = q.get("attach")
        if isinstance(att, dict) and att.get("to") in data:   # attached to another part: the two must touch
            other = data[att["to"]]
            gap = 0.0 if _overlap(data[pid][2], other[2]) else (_box_gap(data[pid][2], other[2]) and _gap(data[pid][1], other[1], tol))
            if gap > tol:
                findings.append(Finding("attach", (pid, att["to"]), f"'{label}' is attached to '{other[0].get('label') or att['to']}' ({att.get('at', 'somewhere')}) "
                                        f"but there is a {gap:.2f} unit gap between them"))

    for i in ids:
        p, _, (blo, bhi) = data[i]
        sh = p.get("shape") or {}
        if sh.get("h") and (bhi[1] - blo[1]) > 0:
            ratio = (bhi[1] - blo[1]) / sh["h"]
            if ratio < 0.75 or ratio > 1.3:
                findings.append(Finding("size", (i,), f"'{p.get('label') or i}' came out {bhi[1] - blo[1]:.2f} tall but the plan gave {sh['h']:.2f}"))
    if scene.get("template") == "blueprint":
        low = min(b[2][0][1] for b in data.values())
        if low < -0.05 * size:
            findings.append(Finding("ground", (), f"part of the machine is {-low:.2f} units below the ground"))
    return findings
