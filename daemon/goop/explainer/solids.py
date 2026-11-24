"""Features: the shapes a model sheet is built from (docs/design/3d-model-sheet.md).

A component of a sheet is a list of features in the shared frame of the whole object (x right, y up, z toward the viewer). Each feature is a small dictionary naming a shape and its real
dimensions; `compile_feature` turns it into meshes ({look, material, p, n, i}, triangles counter-clockwise seen from outside) in that same frame, and raises ValueError with a sentence the
model can repair from. Nothing here writes coordinates for the model: it gives shapes and where they are, the triangles are made here.

    box      {"shape":"box","center":[x,y,z],"size":[w,h,d],"rot":[rx,ry,rz]}          a block, optionally turned (degrees, about its own centre)
    beam     {"shape":"beam","from":[..],"to":[..],"width":w,"thickness":t,"normal":[..]}  a flat bar between two points; `normal` is the direction of its thin side (default z)
    cylinder {"shape":"cylinder","from":[..],"to":[..],"radius":r}                      a round bar or disc with flat ends
    tube     {"shape":"tube","from":[..],"to":[..],"radius":r}                          a round bar with rounded ends
    ring     {"shape":"ring","center":[..],"axis":"y","radius":R,"tube":r}              a torus
    revolve  {"shape":"revolve","base":[..],"axis":"y","profile":[[r,h],..],"closed":false}  a profile turned about an axis, bottom to top (bowls, bodies, shades, knobs); with
                "closed": true the profile is the outline of a hollow body's section, walked up the outside and down the inside (a watch case, a cup, a pipe)
    sphere   {"shape":"sphere","center":[..],"radius":r}
    band     {"shape":"band","points":[[..],..],"width":w,"thickness":t,"normal":[..]}  a flat strap through points (a watch strap, a belt)
    radial   {"shape":"radial","center":[..],"axis":"z","count":12,"item":{feature}}    copies of one feature turned about an axis through `center` (tick marks, bolts, spokes)
Every feature may carry "material": a name from vocab.MATERIALS (default: the component's)."""
import math

from . import members, vocab

AXES = {"x": [1.0, 0.0, 0.0], "y": [0.0, 1.0, 0.0], "z": [0.0, 0.0, 1.0]}
LIMITS = {"features": 80, "count": (2, 64), "profile": (2, 24), "points": (2, 24), "radius": (0.005, 12.0), "coord": 10.0, "vertices": 80000}
SHAPES = ("box", "beam", "cylinder", "tube", "ring", "revolve", "sphere", "band", "radial")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _vec(f, key, what):
    v = f.get(key)
    if not (isinstance(v, list) and len(v) == 3 and all(_num(x) and abs(x) <= LIMITS["coord"] for x in v)):
        raise ValueError(f"{what}: {key} must be a point [x, y, z] with each coordinate within +-{LIMITS['coord']:g}")
    return [float(x) for x in v]


def _pos(f, key, what, lo, hi):
    v = f.get(key)
    if not (_num(v) and lo <= v <= hi):
        raise ValueError(f"{what}: {key} must be a number between {lo:g} and {hi:g}")
    return float(v)


def _axis(f, what, default="y"):
    a = f.get("axis", default)
    if a not in AXES:
        raise ValueError(f"{what}: axis must be one of x, y, z")
    return AXES[a]


def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _add(a, b):
    return [a[i] + b[i] for i in range(3)]


def _mul(a, s):
    return [x * s for x in a]


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _len(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _len(a) or 1.0
    return [x / n for x in a]


def _perp_basis(axis):
    ref = [0.0, 1.0, 0.0] if abs(axis[1]) < 0.9 else [1.0, 0.0, 0.0]
    u = _unit(_cross(axis, ref))
    return u, _cross(axis, u)


class _Mesh:
    def __init__(self):
        self.p, self.n, self.i = [], [], []

    def vert(self, pt, nrm):
        self.p += [round(x, 4) for x in pt]
        self.n += [round(x, 3) for x in _unit(nrm)]
        return len(self.p) // 3 - 1

    def tri(self, a, b, c):
        self.i += [a, b, c]

    def quad(self, a, b, c, d):                   # counter-clockwise a, b, c, d
        self.i += [a, b, c, a, c, d]

    def done(self):
        return {"p": self.p, "n": self.n, "i": self.i}


def _basis_box(center, axes, half):
    """A block with the given orthonormal axes and half sizes."""
    m = _Mesh()
    for k in range(3):
        n = axes[k]
        u, v = axes[(k + 1) % 3], axes[(k + 2) % 3]
        hn, hu, hv = half[k], half[(k + 1) % 3], half[(k + 2) % 3]
        for sgn in (1, -1):
            nn = _mul(n, sgn)
            c = _add(center, _mul(nn, hn))
            uu, vv = (u, v) if sgn == 1 else (v, u)
            hh, hw = (hu, hv) if sgn == 1 else (hv, hu)
            corners = [_add(_add(c, _mul(uu, -hh)), _mul(vv, -hw)), _add(_add(c, _mul(uu, hh)), _mul(vv, -hw)),
                       _add(_add(c, _mul(uu, hh)), _mul(vv, hw)), _add(_add(c, _mul(uu, -hh)), _mul(vv, hw))]
            ids = [m.vert(pt, nn) for pt in corners]
            m.quad(*ids)
    return m.done()


def _matmul(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3)] for r in range(3)]


def _rot_matrix(rx, ry, rz):
    """Rotation by rx about x, then ry about y, then rz about z (degrees)."""
    rx, ry, rz = (math.radians(a) for a in (rx, ry, rz))
    mx = [[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]]
    my = [[math.cos(ry), 0, math.sin(ry)], [0, 1, 0], [-math.sin(ry), 0, math.cos(ry)]]
    mz = [[math.cos(rz), -math.sin(rz), 0], [math.sin(rz), math.cos(rz), 0], [0, 0, 1]]
    return _matmul(mz, _matmul(my, mx))


def box(center, size, rot=(0, 0, 0)):
    m = _rot_matrix(*rot)
    axes = [[m[r][c] for r in range(3)] for c in range(3)]
    return _basis_box(center, axes, [s / 2 for s in size])


def beam(a, b, width, thickness, normal=(0, 0, 1)):
    d = _sub(b, a)
    length = _len(d)
    if length < 1e-6:
        raise ValueError("beam: from and to are the same point")
    d = _unit(d)
    nrm = _sub(list(normal), _mul(d, _dot(list(normal), d)))
    if _len(nrm) < 1e-6:
        nrm = _perp_basis(d)[0]
    nrm = _unit(nrm)
    w = _cross(nrm, d)                              # (d, w, nrm) is right-handed, which the block builder needs for outward triangles
    return _basis_box([(a[k] + b[k]) / 2 for k in range(3)], [d, w, nrm], [length / 2, width / 2, thickness / 2])


def cylinder(a, b, radius, sides=28):
    d = _sub(b, a)
    length = _len(d)
    if length < 1e-6:
        raise ValueError("cylinder: from and to are the same point")
    axis = _unit(d)
    u, v = _perp_basis(axis)
    m = _Mesh()
    ring = [[math.cos(2 * math.pi * j / sides), math.sin(2 * math.pi * j / sides)] for j in range(sides)]
    side_a = [m.vert(_add(a, _mul(_add(_mul(u, c), _mul(v, s)), radius)), _add(_mul(u, c), _mul(v, s))) for c, s in ring]
    side_b = [m.vert(_add(b, _mul(_add(_mul(u, c), _mul(v, s)), radius)), _add(_mul(u, c), _mul(v, s))) for c, s in ring]
    for j in range(sides):
        j2 = (j + 1) % sides
        m.quad(side_a[j], side_a[j2], side_b[j2], side_b[j])
    for end, nrm, flip in ((a, _mul(axis, -1), True), (b, axis, False)):
        c = m.vert(end, nrm)
        rim = [m.vert(_add(end, _mul(_add(_mul(u, cc), _mul(v, ss)), radius)), nrm) for cc, ss in ring]
        for j in range(sides):
            j2 = (j + 1) % sides
            m.tri(c, rim[j2], rim[j]) if flip else m.tri(c, rim[j], rim[j2])
    return m.done()


def tube(a, b, radius):
    mid = [(a[k] + b[k]) / 2 for k in range(3)]
    t = members.tube(_sub(a, mid), _sub(b, mid), radius)
    return _translate(t, mid)


def ring(center, axis, radius, tube_r, segs=40, sides=14):
    u, v = _perp_basis(axis)
    m = _Mesh()
    grid = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        radial = _add(_mul(u, math.cos(a)), _mul(v, math.sin(a)))
        c = _add(center, _mul(radial, radius))
        row = []
        for j in range(sides):
            f = 2 * math.pi * j / sides
            nrm = _add(_mul(radial, math.cos(f)), _mul(axis, math.sin(f)))
            row.append(m.vert(_add(c, _mul(nrm, tube_r)), nrm))
        grid.append(row)
    for i in range(segs):
        for j in range(sides):
            i2, j2 = (i + 1) % segs, (j + 1) % sides
            m.quad(grid[i][j], grid[i2][j], grid[i2][j2], grid[i][j2])
    return m.done()


def revolve(base, axis, profile, sides=40):
    u, v = _perp_basis(axis)
    m = _Mesh()
    rows = []
    for k, (r, h) in enumerate(profile):
        if k == 0:
            t = [profile[1][0] - r, profile[1][1] - h]
        elif k == len(profile) - 1:
            t = [r - profile[k - 1][0], h - profile[k - 1][1]]
        else:
            t = [profile[k + 1][0] - profile[k - 1][0], profile[k + 1][1] - profile[k - 1][1]]
        tl = math.hypot(*t) or 1.0
        nr, nh = t[1] / tl, -t[0] / tl                      # outward in the (radius, height) plane for a profile that runs bottom to top
        row = []
        for j in range(sides):
            a = 2 * math.pi * j / sides
            radial = _add(_mul(u, math.cos(a)), _mul(v, math.sin(a)))
            row.append(m.vert(_add(_add(base, _mul(axis, h)), _mul(radial, r)), _add(_mul(radial, nr), _mul(axis, nh))))
        rows.append(row)
    for k in range(len(profile) - 1):
        for j in range(sides):
            j2 = (j + 1) % sides
            m.quad(rows[k][j], rows[k][j2], rows[k + 1][j2], rows[k + 1][j])
    for k, flip in ((0, True), (len(profile) - 1, False)):
        r, h = profile[k]
        if r > 1e-6:
            nrm = _mul(axis, -1 if flip else 1)
            c = m.vert(_add(base, _mul(axis, h)), nrm)
            rim = [m.vert(_add(_add(base, _mul(axis, h)), _mul(_add(_mul(u, math.cos(2 * math.pi * j / sides)), _mul(v, math.sin(2 * math.pi * j / sides))), r)), nrm) for j in range(sides)]
            for j in range(sides):
                j2 = (j + 1) % sides
                m.tri(c, rim[j2], rim[j]) if flip else m.tri(c, rim[j], rim[j2])
    return m.done()


def revolve_closed(base, axis, profile, sides=40):
    """A hollow body: `profile` is the outline of its cross-section (points [radius, height]) walked clockwise: up the outside, over the rim, down the inside, back along the bottom. The last point
    joins the first. Every segment is flat shaded (crisp edges), and there are no end caps because the outline itself closes the solid."""
    u, v = _perp_basis(axis)
    m = _Mesh()
    n = len(profile)
    for k in range(n):
        (r0, h0), (r1, h1) = profile[k], profile[(k + 1) % n]
        dr, dh = r1 - r0, h1 - h0
        tl = math.hypot(dr, dh)
        if tl < 1e-9:
            continue
        nr, nh = dh / tl, -dr / tl
        rows = []
        for r, h in ((r0, h0), (r1, h1)):
            row = []
            for j in range(1 if r < 1e-9 else sides):                       # a point on the axis is one vertex
                a = 2 * math.pi * j / sides
                radial = _add(_mul(u, math.cos(a)), _mul(v, math.sin(a)))
                row.append(m.vert(_add(_add(base, _mul(axis, h)), _mul(radial, r)), _add(_mul(radial, nr), _mul(axis, nh))))
            rows.append(row)
        if len(rows[0]) == 1 and len(rows[1]) == 1:                         # a segment along the axis has no surface
            continue
        for j in range(sides):
            j2 = (j + 1) % sides
            if len(rows[0]) == 1:
                m.tri(rows[0][0], rows[1][j2], rows[1][j])
            elif len(rows[1]) == 1:
                m.tri(rows[0][j], rows[0][j2], rows[1][0])
            else:
                m.quad(rows[0][j], rows[0][j2], rows[1][j2], rows[1][j])
    return m.done()


def sphere(center, radius, steps=12):
    profile = [[radius * math.sin(math.pi * k / steps), -radius * math.cos(math.pi * k / steps)] for k in range(steps + 1)]
    profile[0][0] = profile[-1][0] = 0.0
    return revolve(center, [0.0, 1.0, 0.0], profile, 24)


def _translate(mesh, off):
    p = mesh["p"]
    return {"p": [round(p[k] + off[k % 3], 4) for k in range(len(p))], "n": mesh["n"], "i": mesh["i"]}


def rotate_about(mesh, center, axis, degrees):
    """The mesh turned `degrees` about the line through `center` along `axis` (Rodrigues)."""
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)

    def rot(v):
        k = _cross(axis, v)
        d = _dot(axis, v)
        return [v[i] * c + k[i] * s + axis[i] * d * (1 - c) for i in range(3)]
    p, n = mesh["p"], mesh["n"]
    out_p, out_n = [], []
    for t in range(0, len(p), 3):
        q = rot([p[t] - center[0], p[t + 1] - center[1], p[t + 2] - center[2]])
        out_p += [round(q[k] + center[k], 4) for k in range(3)]
        out_n += [round(x, 3) for x in rot(n[t:t + 3])]
    return {"p": out_p, "n": out_n, "i": mesh["i"]}


def _look(material):
    return "glass" if material == "glass" else "glow" if material == "flame" else "solid"


def compile_feature(f, material="steel", depth=0):
    """[mesh] for one feature (its meshes carry `look` and `material`), or ValueError."""
    if not isinstance(f, dict) or f.get("shape") not in SHAPES:
        raise ValueError(f"a feature must be an object with a shape, one of: {', '.join(SHAPES)}")
    kind = f["shape"]
    what = f"feature {kind!r}"
    mat = f.get("material", material)
    if mat not in vocab.MATERIALS:
        raise ValueError(f"{what}: material {mat!r} is not one of: {', '.join(vocab.MATERIALS)}")
    rlo, rhi = LIMITS["radius"]
    if kind == "box":
        size = f.get("size")
        if not (isinstance(size, list) and len(size) == 3 and all(_num(s) and 0.005 <= s <= 20 for s in size)):
            raise ValueError(f"{what}: size must be [width, height, depth], each between 0.005 and 20")
        rot = f.get("rot", [0, 0, 0])
        if not (isinstance(rot, list) and len(rot) == 3 and all(_num(a) for a in rot)):
            raise ValueError(f"{what}: rot must be three angles in degrees [rx, ry, rz]")
        mesh = box(_vec(f, "center", what), size, rot)
    elif kind == "beam":
        mesh = beam(_vec(f, "from", what), _vec(f, "to", what), _pos(f, "width", what, 0.005, 20), _pos(f, "thickness", what, 0.005, 20), f.get("normal") or [0, 0, 1])
    elif kind == "cylinder":
        mesh = cylinder(_vec(f, "from", what), _vec(f, "to", what), _pos(f, "radius", what, rlo, rhi))
    elif kind == "tube":
        mesh = tube(_vec(f, "from", what), _vec(f, "to", what), _pos(f, "radius", what, rlo, rhi))
    elif kind == "ring":
        r, tr = _pos(f, "radius", what, rlo, rhi), _pos(f, "tube", what, rlo, rhi)
        mesh = ring(_vec(f, "center", what), _axis(f, what), r, tr)
    elif kind == "sphere":
        mesh = sphere(_vec(f, "center", what), _pos(f, "radius", what, rlo, rhi))
    elif kind == "revolve":
        prof = f.get("profile")
        lo, hi = LIMITS["profile"]
        if not (isinstance(prof, list) and lo <= len(prof) <= hi and all(isinstance(q, list) and len(q) == 2 and all(_num(x) for x in q) and q[0] >= 0 for q in prof)):
            raise ValueError(f"{what}: profile must be {lo}-{hi} points [radius, height] with radius >= 0, running from the bottom to the top")
        if f.get("closed"):
            if len(prof) < 3:
                raise ValueError(f"{what}: a closed profile needs at least 3 points")
            mesh = revolve_closed(_vec(f, "base", what), _axis(f, what), prof)
        else:
            if any(prof[k + 1][1] < prof[k][1] - 1e-9 for k in range(len(prof) - 1)):
                raise ValueError(f"{what}: profile heights must not go down (list the points from the bottom to the top; for a hollow body set \"closed\": true and walk its section outline)")
            mesh = revolve(_vec(f, "base", what), _axis(f, what), prof)
    elif kind == "band":
        pts = f.get("points")
        lo, hi = LIMITS["points"]
        if not (isinstance(pts, list) and lo <= len(pts) <= hi and all(isinstance(q, list) and len(q) == 3 and all(_num(x) and abs(x) <= LIMITS["coord"] for x in q) for q in pts)):
            raise ValueError(f"{what}: points must be {lo}-{hi} points [x, y, z]")
        w, t = _pos(f, "width", what, 0.005, 20), _pos(f, "thickness", what, 0.005, 20)
        parts = [beam(pts[k], pts[k + 1], w, t, f.get("normal") or [0, 0, 1]) for k in range(len(pts) - 1)]
        return [{"look": _look(mat), "material": mat, **g} for g in parts]
    else:                                                          # radial
        if depth:
            raise ValueError(f"{what}: a radial cannot hold another radial")
        lo, hi = LIMITS["count"]
        n = f.get("count")
        if not (isinstance(n, int) and lo <= n <= hi):
            raise ValueError(f"{what}: count must be a whole number between {lo} and {hi}")
        centre, axis = _vec(f, "center", what), _axis(f, what, "z")
        base = compile_feature(f.get("item"), mat, depth + 1)
        out = []
        for k in range(n):
            for g in base:
                out.append({**g, **rotate_about(g, centre, axis, 360.0 * k / n)} if k else g)
        return out
    return [{"look": _look(mat), "material": mat, **mesh}]


def compile_component(features, material="steel"):
    """All meshes of a component, in the shared frame. ValueError with a sentence if a feature is wrong."""
    if not (isinstance(features, list) and 1 <= len(features) <= LIMITS["features"]):
        raise ValueError(f"features must be a list of 1-{LIMITS['features']} features")
    out = []
    for n, f in enumerate(features, 1):
        try:
            out += compile_feature(f, material)
        except ValueError as e:
            raise ValueError(f"feature {n}: {e}")
    if sum(len(m["p"]) // 3 for m in out) > LIMITS["vertices"]:
        raise ValueError("too many triangles: use fewer or simpler features")
    return out


def bounds(meshes):
    """(lo, hi) of all points of the meshes."""
    pts = [m["p"] for m in meshes]
    lo = [min(min(p[a::3]) for p in pts) for a in range(3)]
    hi = [max(max(p[a::3]) for p in pts) for a in range(3)]
    return lo, hi
