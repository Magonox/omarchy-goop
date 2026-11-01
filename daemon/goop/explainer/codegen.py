"""Code parts: the model writes the geometry of a part as a small JavaScript function, and we run it in a sandbox.
This is the most open-ended way to make a shape, so it is also the one that must be locked down: the text on a web page reaches the model, so the model's
code is treated as untrusted. It runs in Deno started with NO permissions (no files, no network, no environment, no subprocesses), a memory cap, a
time limit and a size limit on its output, and all it can do is return numbers: meshes made of positions, normals and triangle indexes.
The helpers (box, cylinder, lathe, extrude...) are the renderer's own mesh builders (shell/explainer3d/meshes.js), so the same code runs in both places."""
import hashlib, json, math, os, shutil, subprocess

from . import vocab

HERE = os.path.dirname(os.path.abspath(__file__))
MESHES_JS = os.path.join(HERE, "..", "..", "..", "shell", "explainer3d", "meshes.js")
LIMITS = {"code": (30, 7000), "seconds": 6, "memory_mb": 256, "vertices": 40000, "meshes": 24, "extent": 8.0, "stdout": 12_000_000}
LOOKS = ("solid", "glass", "glow", "screen", "led")

HARNESS_TAIL = r"""
;(function () {
  const M = {box, cyl, prism, pipe, torus, terrain, skirt, T, merge, frustum, sphere, tube, lathe, extrude, mesh, vert, quad};
  let out;
  try { out = build(M); } catch (e) { console.log(JSON.stringify({error: String(e && e.message || e)})); return; }
  console.log(JSON.stringify({result: out}));
})();
"""


class CodeError(ValueError):
    pass


def available():
    return shutil.which("deno") is not None


def _harness(code):
    with open(MESHES_JS) as f:
        meshes = f.read().replace(".pragma library", "")
    return "const Qt = {vector3d: (x, y, z) => ({x, y, z})};\n" + meshes + "\n" + code + "\n" + HARNESS_TAIL


def _run(code):
    """Execute `code` (which defines build(M)) in the sandbox; returns the decoded {"result": ...}."""
    if not available():
        raise CodeError("the deno runtime is needed to run code parts (sudo pacman -S deno)")
    cmd = ["deno", "run", "--quiet", "--no-prompt", "--no-config", "--no-lock", "--no-remote", f"--v8-flags=--max-old-space-size={LIMITS['memory_mb']}", "-"]
    try:
        r = subprocess.run(cmd, input=_harness(code), capture_output=True, text=True, timeout=LIMITS["seconds"],
                           env={"PATH": os.environ.get("PATH", ""), "HOME": "/nonexistent", "DENO_NO_UPDATE_CHECK": "1"}, cwd="/")
    except subprocess.TimeoutExpired:
        raise CodeError(f"the code ran longer than {LIMITS['seconds']} seconds (an endless loop, or far too many shapes)")
    if len(r.stdout) > LIMITS["stdout"]:
        raise CodeError("the code produced far too much geometry")
    line = (r.stdout.strip().splitlines() or [""])[-1]
    try:
        return json.loads(line)
    except ValueError:
        tail = (r.stderr or "").strip().splitlines()
        raise CodeError("the code failed to run: " + (tail[-1][:200] if tail else "no output"))


def _clean(out, where):
    """Check what the sandbox returned and turn it into meshes the renderer can draw: [{look, material, p, n, i}], plus the bounds."""
    if not isinstance(out, list) or not 1 <= len(out) <= LIMITS["meshes"]:
        raise CodeError(f"{where}: build(M) must return an array of 1-{LIMITS['meshes']} items like {{material, look, mesh}}")
    meshes, total = [], 0
    for k, item in enumerate(out, 1):
        w = f"{where} item {k}"
        if not isinstance(item, dict) or not isinstance(item.get("mesh"), dict):
            raise CodeError(f"{w}: each item must be {{material: name, look: one of {', '.join(LOOKS)}, mesh: a mesh from M}}")
        mat, look, m = item.get("material", "steel"), item.get("look", "solid"), item["mesh"]
        if mat not in vocab.MATERIALS:
            raise CodeError(f"{w}: material must be one of: {', '.join(vocab.MATERIALS)}")
        if look not in LOOKS:
            raise CodeError(f"{w}: look must be one of: {', '.join(LOOKS)}")
        p, n, ix = m.get("p"), m.get("n"), m.get("i")
        if not (isinstance(p, list) and isinstance(n, list) and isinstance(ix, list)) or len(p) != len(n) or len(p) % 3 or len(ix) % 3 or not p or not ix:
            raise CodeError(f"{w}: the mesh needs p and n (x,y,z lists of equal length) and i (triangle indexes, three per triangle)")
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in p + n):
            raise CodeError(f"{w}: the mesh contains a value that is not a finite number")
        count = len(p) // 3
        if not all(isinstance(v, int) and 0 <= v < count for v in ix):
            raise CodeError(f"{w}: a triangle index points outside the mesh's {count} vertices")
        total += count
        if total > LIMITS["vertices"]:
            raise CodeError(f"{where}: too many vertices ({total}); use fewer segments or fewer repeated shapes (limit {LIMITS['vertices']})")
        meshes.append({"look": look, "material": mat, "p": p, "n": n, "i": ix})
    pts = [(m["p"][k], m["p"][k + 1], m["p"][k + 2]) for m in meshes for k in range(0, len(m["p"]), 3)]
    lo, hi = [min(p[a] for p in pts) for a in range(3)], [max(p[a] for p in pts) for a in range(3)]
    if max(hi[a] - lo[a] for a in range(3)) > LIMITS["extent"] * 2 or max(abs(v) for v in lo + hi) > LIMITS["extent"] * 4:
        raise CodeError(f"{where}: the shape is far too big; keep it within about +-{LIMITS['extent']:g} units (a hand-sized object is about 1)")
    if max(hi[a] - lo[a] for a in range(3)) < 0.02:
        raise CodeError(f"{where}: the shape is almost invisible; make it about 0.5-3 units across")
    center = [(lo[a] + hi[a]) / 2 for a in range(3)]
    for m in meshes:                            # centre on the origin, like every other shape, and round to keep the scene file small
        m["p"] = [round(m["p"][k] - center[k % 3], 4) for k in range(len(m["p"]))]
        m["n"] = [round(v, 3) for v in m["n"]]
    r = max(math.hypot(p[0] - center[0], p[2] - center[2]) for p in pts)
    return meshes, {"r": r, "h": hi[1] - lo[1]}


def compile_part(code, where):
    """Run one part's code and return its checked meshes and size: ([mesh...], {"r", "h"}). Raises CodeError with a message a model can repair from."""
    lo, hi = LIMITS["code"]
    if not isinstance(code, str) or not lo <= len(code) <= hi:
        raise CodeError(f"{where}: the code must be {lo}-{hi} characters defining function build(M)")
    res = _run(code)
    if "error" in res:
        raise CodeError(f"{where}: your code threw an error: {res['error']}")
    return _clean(res.get("result"), where)


def fit_scale(dims, width, height):
    """How much to scale a part's mesh so it fits inside the box the outline gave it (width across, height tall)."""
    return min((width / 2) / max(dims["r"], 1e-6), height / max(dims["h"], 1e-6))


_cache = {}


def resolve(story):
    """Run every code part's code (in the sandbox) and store the checked meshes on the part; raises CodeError with a message a model can repair from."""
    for p in story.get("parts", []):
        if p.get("kind") != "code":
            continue
        code = p["code"]
        key = hashlib.sha1(code.encode()).hexdigest()
        if key not in _cache:
            _cache[key] = compile_part(code, f"part {p['id']!r}")
        p["_meshes"], p["_dims"] = _cache[key]
        if "width" in p:
            p["_scale"] = fit_scale(p["_dims"], p["width"], p["height"])
