"""Members: the tubes, rods and bars of a frame, drawn between two named joints.

A bicycle frame drawn as separate shapes in separate boxes does not meet where it should (a model writing each tube alone cannot know where the next one starts). So a lesson names
its joints, points in the machine frame, and every tube is a member that runs from one joint to another: tubes meet because they share the joint, by construction.
`tube(a, b, r)` makes the mesh: a round bar from a to b with rounded ends, around its own midpoint, in the same {p, n, i} form every part's geometry has."""
import math


def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def tube(a, b, r, sides=14, cap_rings=3):
    """A round bar of radius r from point a to point b with hemispherical ends, as {"p", "n", "i"} around the midpoint of a and b (triangles counter-clockwise seen from outside)."""
    d = _sub(b, a)
    length = math.sqrt(sum(x * x for x in d))
    axis = _unit(d) if length > 1e-9 else [0.0, 1.0, 0.0]
    ref = [0.0, 1.0, 0.0] if abs(axis[1]) < 0.9 else [1.0, 0.0, 0.0]
    u = _unit(_cross(axis, ref))
    v = _cross(axis, u)
    half = length / 2
    rings = []                                         # (offset along the axis, ring radius, share of the axis in the normal)
    for k in range(cap_rings, 0, -1):
        phi = k / cap_rings * math.pi / 2
        rings.append((-half - r * math.sin(phi), r * math.cos(phi), -math.sin(phi)))
    rings += [(-half, r, 0.0), (half, r, 0.0)]
    for k in range(1, cap_rings + 1):
        phi = k / cap_rings * math.pi / 2
        rings.append((half + r * math.sin(phi), r * math.cos(phi), math.sin(phi)))
    p, n, idx, first = [], [], [], []
    for off, rad, ax in rings:
        first.append(len(p) // 3)
        count = 1 if rad < 1e-9 else sides              # a pole is one point
        for j in range(count):
            a_ = 2 * math.pi * j / sides
            radial = [math.cos(a_) * u[k] + math.sin(a_) * v[k] for k in range(3)]
            p += [rad * radial[k] + off * axis[k] for k in range(3)]
            norm = _unit([math.sqrt(max(0.0, 1 - ax * ax)) * radial[k] + ax * axis[k] for k in range(3)])
            n += norm
    for i in range(len(rings) - 1):
        a0, b0 = first[i], first[i + 1]
        ra, rb = rings[i][1] < 1e-9, rings[i + 1][1] < 1e-9
        for j in range(sides):
            j2 = (j + 1) % sides
            if ra:
                idx += [a0, b0 + j2, b0 + j]
            elif rb:
                idx += [a0 + j, a0 + j2, b0]
            else:
                idx += [a0 + j, a0 + j2, b0 + j2, a0 + j, b0 + j2, b0 + j]
    return {"p": [round(x, 4) for x in p], "n": [round(x, 3) for x in n], "i": idx}
