"""Invariants of a built 3D lesson: things that must be true for the lesson to look and behave like the real thing, checked by numbers.

A lesson is a scene (build.load / build.build) that the renderer (shell/explainer3d/lesson.js) plays. This module runs the renderer's own `state(t)` in node, with no GPU,
at many moments, and checks what a viewer would see against the real geometry of the parts:

  connections          parts the plan joins really touch; nothing floats; parts inside their container are inside it (validate.py)
  people               no person, rider or animal as a part
  sizes_match_plan     a part came out the size the plan gave it
  mesh_integrity       every part's mesh is clean: finite numbers, valid triangle indexes, few degenerate triangles, unit normals
  labels_on_parts      a label sits on its part, wherever the part is (also when it has been pulled apart)
  flows_touch_parts    a stream starts and ends on the parts it joins, at the moment it plays
  explode_proportional parts pulled apart stay near home (a fraction of the model's size), not a fixed distance
  camera_frames_subject  the opening shot holds every part, and the finale keeps the moving body in the picture while it is visible
  effects_scale        bubbles, smoke and drops are small against the model, and bubbles stay inside the water
  rolling_is_physical  a rolling wheel turns once per circumference travelled, in the direction that rolls, at the wheel's real radius
  spin_axis_matches_geometry  a disc (wheel, plate, rotor) turns about its own axle, the thin axis
  coupled_motion       parts that drive each other turn at the ratio and in the direction their link demands (meshing gears opposite, chain or belt the same)

Each check returns a list of Violation, an empty list when it holds. `check_all` runs them all. The thresholds are a starting point, tuned by eye with the owner; they live
as named constants below so they can be changed in one place."""
import json, math, os, shutil, statistics, subprocess, tempfile
from dataclasses import dataclass

from . import validate

LESSON_JS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "shell", "explainer3d", "lesson.js")

LABEL_TOLERANCE = (0.35, 0.25)        # a label may be this far (units) or this share of the part's size from the part
FLOW_TOLERANCE = (0.3, 0.3)           # same for the ends of a stream
EXPLODE_SHARE = 0.25                  # the median part moves at most this share of the model's radius when pulled apart
EFFECT_SHARE = 0.15                   # an effect particle is at most this share of the model's radius wide
DROP_SHARE = 0.25                     # a flow drop is at most this share of the smallest part it joins
ROLL_TOLERANCE = 0.08                 # rolling: distance travelled and wheel turned may disagree by this share
COUPLING_TOLERANCE = 0.10
DEGENERATE_SHARE = 0.25                # lathes and caps always make a few zero-area triangles at their poles; only a mostly-collapsed mesh is a fault
FOV = 34.0                            # degrees, vertical (Lesson3D.qml)
ASPECT = 16 / 9
FRAME = 1.0                           # a point is in the picture inside +-FRAME in normalised screen units


@dataclass
class Violation:
    invariant: str
    message: str
    t: float = None

    def __str__(self):
        return f"{self.invariant}" + (f" at {self.t:.1f}s" if self.t is not None else "") + f": {self.message}"


# ---- geometry helpers ----

def local_box(part):
    """The part's own box (lo, hi) after its scale, around its own origin, or None while it has no geometry."""
    meshes, k = validate._meshes(part)
    pts = [m.get("p") or [] for m in meshes]
    pts = [p for p in pts if p]
    if not pts:
        sh = part.get("shape") or {}              # a ready-made shape (the built-in lessons): a box from its dimensions
        if not (sh.get("h") or sh.get("r") or sh.get("w")):
            return None
        half_w = max(sh.get("r", 0), sh.get("r0", 0), sh.get("w", 0) / 2)
        half_d = max(sh.get("r", 0), sh.get("r0", 0), sh.get("d", 0) / 2)
        h = sh.get("h") or 2 * half_w
        return [-half_w, -h / 2, -half_d], [half_w, h / 2, half_d]
    lo = [min(min(p[a::3]) for p in pts) * k for a in range(3)]
    hi = [max(max(p[a::3]) for p in pts) * k for a in range(3)]
    return lo, hi


def extent(box):
    return [box[1][a] - box[0][a] for a in range(3)]


def point_box_distance(pt, lo, hi):
    return math.sqrt(sum(max(lo[a] - pt[a], 0.0, pt[a] - hi[a]) ** 2 for a in range(3)))


def world_box(part, box, state, root=None):
    """Where the part's box is at this moment: its place, plus how far it is pulled apart, plus the finale's move of the whole body."""
    d = [(part.get("pos") or [0, 0, 0])[a] + [state["dx"], state["dy"], state["dz"]][a] for a in range(3)]
    if root:
        d = [d[a] + root["pos"][a] - root["pivot"][a] for a in range(3)]
    return [box[0][a] + d[a] for a in range(3)], [box[1][a] + d[a] for a in range(3)]


def project(cam, pt):
    """(x, y, depth) of a world point in the picture, x and y in normalised screen units (+-1 is the edge), for the camera that orbits `target` at `dist`
    with `yaw` about the vertical and `pitch` above the horizon (the Node in Lesson3D.qml; the order of the two rotations is the usual orbit camera)."""
    yaw, pitch = math.radians(cam["yaw"]), math.radians(-cam["pitch"])
    v = [pt[a] - cam["target"][a] for a in range(3)]
    x1, z1 = v[0] * math.cos(yaw) - v[2] * math.sin(yaw), v[0] * math.sin(yaw) + v[2] * math.cos(yaw)         # undo yaw about y
    y2, z2 = v[1] * math.cos(pitch) + z1 * math.sin(pitch), -v[1] * math.sin(pitch) + z1 * math.cos(pitch)      # undo pitch about x
    depth = cam["dist"] - z2
    if depth <= 1e-6:
        return None
    t = math.tan(math.radians(FOV) / 2)
    return x1 / depth / (t * ASPECT), y2 / depth / t, depth


# ---- running the renderer ----

HARNESS = r"""
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8").replace(".pragma library", "") + "\nmodule.exports = {prepare, state};";
const m = { exports: {} }; new Function("module", src)(m);
const scene = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const C = m.exports.prepare(scene);
const times = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));
const out = times.map(t => { const st = m.exports.state(C, t);
  return { t, parts: st.parts.map(p => ({ vis: p.vis, dx: p.dx, dy: p.dy, dz: p.dz, spin: p.spin, k: p.k, alpha: p.alpha })),
           labels: st.labels, drops: st.drops, fx: st.fx, root: st.root, env: st.env, cam: st.cam }; });
fs.writeFileSync(process.argv[5], JSON.stringify(out));
"""


def available():
    return shutil.which("node") is not None


def sample_times(scene, step=1.0):
    """Regular moments plus the ones that matter: the middle of every stream, and the finale second by second."""
    ts = {round(i * step, 2) for i in range(int(scene["duration"] / step) + 1)}
    for e in scene.get("events", []):
        if e["type"] == "flow":
            ts.add(round((e["t0"] + e["t1"]) / 2, 2))
    fin = scene.get("finale")
    if fin:
        ts |= {round(fin["t_go"] + 0.5 * i, 2) for i in range(int(fin["dur"] / 0.5) + 2)}
    return sorted(t for t in ts if 0 <= t <= scene["duration"])


def run_states(scene, times):
    """The renderer's state at each time (a list of dicts), by running lesson.js in node."""
    with tempfile.TemporaryDirectory() as d:
        paths = [os.path.join(d, n) for n in ("h.js", "scene.json", "times.json", "out.json")]
        for p, text in zip(paths[:3], (HARNESS, json.dumps(scene), json.dumps(times))):
            with open(p, "w") as f:
                f.write(text)
        subprocess.run(["node", paths[0], LESSON_JS, paths[1], paths[2], paths[3]], check=True, capture_output=True, timeout=120)
        with open(paths[3]) as f:
            return json.load(f)


# ---- the checks ----

def _boxes(scene):
    return {p["id"]: (p, local_box(p)) for p in scene["parts"]}


def _by_kind(findings, name, kinds):
    return [Violation(name, f.message) for f in findings if f.kind in kinds]


def connections(scene, story=None, findings=None):
    return _by_kind(validate.check(scene, story) if findings is None else findings, "connections", ("floating", "attach", "inside", "overlap", "ground"))


def people(scene, story=None, findings=None):
    return _by_kind(validate.check(scene, story) if findings is None else findings, "people", ("people",))


def sizes_match_plan(scene, story=None, findings=None):
    return _by_kind(validate.check(scene, story) if findings is None else findings, "sizes_match_plan", ("size",))


def mesh_integrity(scene):
    out = []
    for p in scene["parts"]:
        meshes, _ = validate._meshes(p)
        for n, m in enumerate(meshes):
            pts, nrm, idx = m.get("p") or [], m.get("n") or [], m.get("i") or []
            if len(pts) % 3 or len(idx) % 3 or any(not math.isfinite(v) for v in pts + nrm):
                out.append(Violation("mesh_integrity", f"'{p['id']}' mesh {n}: positions or indexes are not whole triples, or contain a value that is not finite"))
                continue
            count = len(pts) // 3
            if any(i < 0 or i >= count for i in idx):
                out.append(Violation("mesh_integrity", f"'{p['id']}' mesh {n}: a triangle points at a vertex that does not exist"))
                continue
            size = max(max(pts[a::3]) - min(pts[a::3]) for a in range(3)) if pts else 0
            bad = 0
            for t in range(0, len(idx), 3):
                a, b, c = (pts[idx[t + k] * 3:idx[t + k] * 3 + 3] for k in range(3))
                u, v = [b[k] - a[k] for k in range(3)], [c[k] - a[k] for k in range(3)]
                cross = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
                if math.sqrt(sum(x * x for x in cross)) / 2 < 1e-9 * max(size, 1e-9) ** 2:
                    bad += 1
            tris = max(1, len(idx) // 3)
            if bad / tris > DEGENERATE_SHARE:
                out.append(Violation("mesh_integrity", f"'{p['id']}' mesh {n}: {bad} of {tris} triangles have no area"))
            if nrm:
                off = sum(1 for k in range(0, len(nrm) - 2, 3) if not 0.8 <= math.sqrt(nrm[k] ** 2 + nrm[k + 1] ** 2 + nrm[k + 2] ** 2) <= 1.2)
                if off / max(1, len(nrm) // 3) > 0.05:
                    out.append(Violation("mesh_integrity", f"'{p['id']}' mesh {n}: {off} normals are not unit length"))
    return out


def labels_on_parts(scene, states):
    boxes, out = _boxes(scene), []
    by_label = {}
    for pid, (p, box) in boxes.items():
        if box:
            by_label.setdefault(p.get("label"), []).append(pid)
    for st in states:
        for lb in st["labels"]:
            best = None
            for pid in by_label.get(lb["text"], []):
                p, box = boxes[pid]
                i = scene["parts"].index(p)
                lo, hi = world_box(p, box, st["parts"][i], st["root"])
                size = max(extent(box))
                d = point_box_distance(lb["at"], lo, hi)
                allowed = max(LABEL_TOLERANCE[0], LABEL_TOLERANCE[1] * size)
                if best is None or d - allowed < best[0]:
                    best = (d - allowed, d, allowed)
            if best and best[0] > 0:
                out.append(Violation("labels_on_parts", f"the label '{lb['text']}' is {best[1]:.2f} units from its part (at most {best[2]:.2f})", st["t"]))
                break
    return _first_per_message(out)


def flows_touch_parts(scene, states):
    boxes, out, at = _boxes(scene), [], {round(s["t"], 2): s for s in states}
    for e in scene.get("events", []):
        if e["type"] != "flow":
            continue
        st = at.get(round((e["t0"] + e["t1"]) / 2, 2))
        if not st:
            continue
        for end, pt in enumerate(scene["paths"][e["path"]]):
            pid = min((q for q in scene["parts"] if boxes[q["id"]][1]), key=lambda q: math.dist(q["pos"], pt))["id"]
            p, box = boxes[pid]
            lo, hi = world_box(p, box, st["parts"][scene["parts"].index(p)], st["root"])
            d, allowed = point_box_distance(pt, lo, hi), max(FLOW_TOLERANCE[0], FLOW_TOLERANCE[1] * max(extent(box)))
            if d > allowed:
                out.append(Violation("flows_touch_parts", f"the {e['medium']} stream {'starts' if end == 0 else 'ends'} {d:.2f} units from '{pid}' (at most {allowed:.2f})", st["t"]))
    return out


def explode_proportional(scene):
    R = scene["bounds"]["radius"]
    moves = [math.dist([0, 0, 0], p["explode"]) for p in scene["parts"] if any(p["explode"])]
    if not moves:
        return []
    med = statistics.median(moves)
    if med > EXPLODE_SHARE * R:
        return [Violation("explode_proportional", f"parts are pulled apart by {med:.2f} units on average, {med / R * 100:.0f}% of the model's radius {R:.2f} (at most {EXPLODE_SHARE * 100:.0f}%)")]
    return []


def camera_frames_subject(scene, states):
    out, boxes = [], _boxes(scene)
    first = min(states, key=lambda s: abs(s["t"] - 2.0))
    for p, box in boxes.values():
        i = scene["parts"].index(p)
        if not box or not first["parts"][i]["vis"]:
            continue
        lo, hi = world_box(p, box, first["parts"][i], first["root"])
        c = project(first["cam"], [(lo[a] + hi[a]) / 2 for a in range(3)])
        if c is None or abs(c[0]) > FRAME or abs(c[1]) > FRAME:
            out.append(Violation("camera_frames_subject", f"in the opening shot '{p['id']}' is outside the picture", first["t"]))
    fin = scene.get("finale")
    if fin:
        for st in states:
            if not (fin["t_go"] <= st["t"] <= fin["t_go"] + fin["dur"]) or not any(q["vis"] for q in st["parts"]) or min(q["alpha"] for q in st["parts"]) < 0.1:
                continue
            c = project(st["cam"], st["root"]["pos"])
            if c is None or abs(c[0]) > FRAME or abs(c[1]) > FRAME:
                out.append(Violation("camera_frames_subject", f"in the finale ({fin['motion']}) the body has left the picture while it is still visible (screen position {0 if c is None else c[0]:.1f}, {0 if c is None else c[1]:.1f})", st["t"]))
                break
    return out


def effects_scale(scene, states):
    out, fin = [], scene.get("finale")
    R = fin["radius"] if fin else scene["bounds"]["radius"]
    if fin:
        widest = max((q["s"] * 100 for st in states for q in st["fx"]), default=0)
        if widest > EFFECT_SHARE * R:
            out.append(Violation("effects_scale", f"effect particles are up to {widest:.2f} units wide, {widest / R * 100:.0f}% of the model's radius {R:.2f} (at most {EFFECT_SHARE * 100:.0f}%)"))
        if fin.get("env") == "water":
            for st in states:
                if st["env"] and any(q["y"] > st["env"]["pos"][1] + 0.1 for q in st["fx"]):
                    out.append(Violation("effects_scale", "bubbles rise above the water surface", st["t"]))
                    break
    boxes = _boxes(scene)
    for e in scene.get("events", []):
        if e["type"] != "flow":
            continue
        sizes = []
        for pt in scene["paths"][e["path"]]:
            pid = min((q for q in scene["parts"] if boxes[q["id"]][1]), key=lambda q: math.dist(q["pos"], pt))["id"]
            sizes.append(min(extent(boxes[pid][1])))
        drop = 0.0024 * 100                                                         # lesson.js: the size of a flow drop, as drawn
        if drop > DROP_SHARE * min(sizes):
            out.append(Violation("effects_scale", f"a {e['medium']} flow drop is {drop:.2f} units wide against a part {min(sizes):.2f} across (at most {DROP_SHARE * 100:.0f}%)"))
    return out


def rolling_is_physical(scene, states):
    fin = scene.get("finale")
    if not fin or not fin.get("rollers"):
        return []
    boxes = _boxes(scene)
    a, b = (min(states, key=lambda s: abs(s["t"] - (fin["t_go"] + x))) for x in (1.5, 4.0))
    dx = b["root"]["pos"][0] - a["root"]["pos"][0]
    out = []
    for rid in fin["rollers"]:
        i = next(n for n, p in enumerate(scene["parts"]) if p["id"] == rid)
        box = boxes[rid][1]
        radius = max(extent(box)[0], extent(box)[1]) / 2
        turned = math.radians(b["parts"][i]["spin"] - a["parts"][i]["spin"])
        if dx > 0 and turned >= 0:
            out.append(Violation("rolling_is_physical", f"'{rid}' turns the wrong way for the body to roll forward"))
        rolled = -turned * radius
        if abs(dx) > 1e-6 and abs(rolled - dx) > ROLL_TOLERANCE * abs(dx):
            out.append(Violation("rolling_is_physical", f"'{rid}' (radius {radius:.2f}) would roll {rolled:.2f} units but the body moves {dx:.2f}: the wheel slips"))
    return out


def spin_axis_matches_geometry(scene):
    out, boxes = [], _boxes(scene)
    spinners = {pid for e in scene.get("events", []) if e["type"] == "spin" for pid in e["parts"]}
    for pid in sorted(spinners):
        p, box = boxes[pid]
        if not box:
            continue
        ext = extent(box)
        order = sorted(range(3), key=lambda a: ext[a])
        thin, mid, wide = order
        if ext[wide] > 0 and ext[mid] >= 0.75 * ext[wide] and ext[thin] < 0.6 * ext[wide]:        # a disc: two long sides alike, one short
            axis = p.get("spin_axis") or [0, 1, 0]
            if axis[thin] != 1:
                out.append(Violation("spin_axis_matches_geometry", f"'{pid}' is a disc ({ext[0]:.2f} x {ext[1]:.2f} x {ext[2]:.2f}) but turns about axis {axis}, not its thin axis"))
    return out


def coupling_violations(kind, a_turn, b_turn, ratio):
    """Do two parts turn as their link demands? `a_turn` and `b_turn` are the degrees each turned over the same time; `ratio` is how many times faster b turns than a
    (gear teeth of a over teeth of b, sprocket sizes for a chain). Meshing gears turn opposite ways; a chain, belt or shaft the same way."""
    sign = -1 if kind == "mesh" else 1
    if abs(a_turn) < 1e-9:
        return [] if abs(b_turn) < 1e-9 else [f"the driven part turns {b_turn:.0f} degrees while the driver does not move"]
    want = sign * ratio * a_turn
    if abs(b_turn - want) > COUPLING_TOLERANCE * abs(want):
        return [f"the driver turns {a_turn:.0f} degrees so the driven part should turn {want:.0f} ({'opposite' if sign < 0 else 'the same way'}, ratio {ratio:g}), but it turns {b_turn:.0f}"]
    return []


def coupled_motion(scene, states, couplings):
    """`couplings` is a list of {"a", "b", "kind": mesh|chain|belt|shaft, "ratio"}: the plan's links between turning parts (a storyboard field planned in F4)."""
    out, ids = [], [p["id"] for p in scene["parts"]]
    for c in couplings or []:
        ia, ib = ids.index(c["a"]), ids.index(c["b"])
        best = max(((s["parts"][ia]["spin"], s["parts"][ib]["spin"], s["t"]) for s in states), key=lambda r: abs(r[0]))
        for msg in coupling_violations(c["kind"], best[0], best[1], c["ratio"]):
            out.append(Violation("coupled_motion", f"{c['a']} drives {c['b']} by a {c['kind']}: {msg}", best[2]))
    return out


def _first_per_message(items):
    seen, out = set(), []
    for v in items:
        key = v.message.split(" is ")[0]
        if key not in seen:
            seen.add(key)
            out.append(v)
    return out


NAMES = ("connections", "people", "sizes_match_plan", "mesh_integrity", "labels_on_parts", "flows_touch_parts", "explode_proportional", "camera_frames_subject",
         "effects_scale", "rolling_is_physical", "spin_axis_matches_geometry", "coupled_motion")


def check_all(scene, story=None, couplings=None, step=1.0):
    """{invariant name: [Violation]} for a built scene. Needs node (the renderer's state() is run in it)."""
    states = run_states(scene, sample_times(scene, step))
    found = validate.check(scene, story)                         # once: the geometry checks are the slow part
    return {
        "connections": connections(scene, story, found), "people": people(scene, story, found), "sizes_match_plan": sizes_match_plan(scene, story, found),
        "mesh_integrity": mesh_integrity(scene), "labels_on_parts": labels_on_parts(scene, states), "flows_touch_parts": flows_touch_parts(scene, states),
        "explode_proportional": explode_proportional(scene), "camera_frames_subject": camera_frames_subject(scene, states),
        "effects_scale": effects_scale(scene, states), "rolling_is_physical": rolling_is_physical(scene, states),
        "spin_axis_matches_geometry": spin_axis_matches_geometry(scene), "coupled_motion": coupled_motion(scene, states, couplings),
    }
