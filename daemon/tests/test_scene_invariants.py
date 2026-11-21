"""Invariants of built 3D lessons (goop/explainer/invariants.py), checked on saved lessons and, with synthetic scenes, on the checks themselves.

Part 1 tests each check on tiny scenes made here, so a check that stops detecting its fault fails. Part 2 builds every saved lesson in tests/fixtures/lessons (and the
built-in ones), plays the renderer's own state() in node over each, and checks every invariant. KNOWN lists what is wrong today: a lesson and invariant in that list must
still fail (so the list cannot go stale), and every other pair must pass. When a fix lands, delete its entry. Run `python3 daemon/check_lessons.py -v` to read the findings."""
import json, os, shutil, sys, unittest
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop.explainer import build, codegen, invariants as inv

HERE = os.path.dirname(os.path.abspath(__file__))


def box_mesh(w, h, d):
    x, y, z = w / 2, h / 2, d / 2
    corners = [(sx * x, sy * y, sz * z) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return {"p": [v for c in corners for v in c], "n": [], "i": [i for a, b, c, d in faces for i in (a, b, c, a, c, d)]}


def part(pid, size, pos=(0, 0, 0), **kw):
    return {"id": pid, "label": pid.title(), "pos": list(pos), "rot": [0, 0, 0], "explode": kw.pop("explode", [0, 0, 0]), "radius": 1,
            "shape": {"scale": 1, "h": size[1], "meshes": [box_mesh(*size)]}, **kw}


class Relative(unittest.TestCase):
    """Explode distance follows the size of the model and of the part (layout._scale_explode), not a fixed number of units."""
    def test_small_models_and_small_parts_are_pulled_apart_less(self):
        from goop.explainer import layout

        def placed(scale):
            return {"big": {"pos": [0, 0, 0], "radius": 3 * scale, "explode": [2.4, 0, 0]}, "small": {"pos": [5 * scale, 0, 0], "radius": 0.2 * scale, "explode": [0, 2.4, 0]}}
        a, b = placed(1), placed(0.2)
        layout._scale_explode(a)
        layout._scale_explode(b)
        small_a, small_b = a["small"]["explode"][1], b["small"]["explode"][1]
        self.assertLess(a["small"]["explode"][1], 2.4)                         # a small part no longer moves as far as a big one
        self.assertAlmostEqual(small_b / small_a, 0.2, delta=0.02)             # the same lesson at a fifth of the size moves a fifth as far
        self.assertEqual(a["big"]["explode"][1:], [0, 0])                      # directions are kept


class Helpers(unittest.TestCase):
    def test_point_to_box_distance(self):
        self.assertAlmostEqual(inv.point_box_distance((0, 0, 0), (-1, -1, -1), (1, 1, 1)), 0)
        self.assertAlmostEqual(inv.point_box_distance((3, 0, 0), (-1, -1, -1), (1, 1, 1)), 2)
        self.assertAlmostEqual(inv.point_box_distance((2, 2, 1), (-1, -1, -1), (1, 1, 1)), 2 ** 0.5)

    def test_the_target_is_in_the_middle_of_the_picture_and_far_things_are_smaller(self):
        cam = {"target": [1, 2, 3], "dist": 10, "yaw": 30, "pitch": 15}
        x, y, depth = inv.project(cam, [1, 2, 3])
        self.assertAlmostEqual(x, 0), self.assertAlmostEqual(y, 0), self.assertAlmostEqual(depth, 10)
        near = inv.project({**cam, "dist": 10}, [1, 3, 3])
        far = inv.project({**cam, "dist": 30}, [1, 3, 3])
        self.assertGreater(abs(near[1]), abs(far[1]))

    def test_points_behind_the_camera_are_not_in_the_picture(self):
        self.assertIsNone(inv.project({"target": [0, 0, 0], "dist": 5, "yaw": 0, "pitch": 0}, [0, 0, 20]))

    def test_coupled_parts(self):
        self.assertEqual(inv.coupling_violations("mesh", 100, -50, 0.5), [])            # meshing gears turn opposite ways, at the teeth ratio
        self.assertEqual(inv.coupling_violations("chain", 100, 275, 2.75), [])          # a chain: the same way
        self.assertTrue(inv.coupling_violations("mesh", 100, 50, 0.5))                  # same way: wrong
        self.assertTrue(inv.coupling_violations("chain", 100, 145, 2.75))               # right way, wrong ratio
        self.assertTrue(inv.coupling_violations("chain", 0, 40, 2))                     # the driven part moves alone

    def test_mesh_integrity(self):
        ok = {"id": "a", "shape": {"scale": 1, "meshes": [box_mesh(1, 1, 1)]}}
        self.assertEqual(inv.mesh_integrity({"parts": [ok]}), [])
        nan = {"id": "n", "shape": {"scale": 1, "meshes": [{"p": [0, 0, float("nan")] + [1, 0, 0, 0, 1, 0], "n": [], "i": [0, 1, 2]}]}}
        bad_index = {"id": "i", "shape": {"scale": 1, "meshes": [{"p": [0, 0, 0, 1, 0, 0, 0, 1, 0], "n": [], "i": [0, 1, 7]}]}}
        flat = {"id": "f", "shape": {"scale": 1, "meshes": [{"p": [0, 0, 0, 1, 0, 0, 2, 0, 0], "n": [], "i": [0, 1, 2]}]}}
        for p in (nan, bad_index, flat):
            self.assertEqual(len(inv.mesh_integrity({"parts": [p]})), 1, p["id"])

    def test_a_disc_must_turn_about_its_thin_axis(self):
        def scene(axis):
            return {"parts": [part("wheel", (1, 1, 0.1), spin_axis=axis)], "events": [{"type": "spin", "parts": ["wheel"]}]}
        self.assertEqual(inv.spin_axis_matches_geometry(scene([0, 0, 1])), [])
        self.assertEqual(len(inv.spin_axis_matches_geometry(scene([0, 1, 0]))), 1)

    def test_parts_pulled_apart_by_a_fixed_distance_are_reported(self):
        near = {"bounds": {"radius": 10}, "parts": [part("a", (1, 1, 1), explode=[1, 0, 0]), part("b", (1, 1, 1), explode=[0, 2, 0])]}
        far = {"bounds": {"radius": 10}, "parts": [part("a", (1, 1, 1), explode=[4, 0, 0]), part("b", (1, 1, 1), explode=[0, 5, 0])]}
        self.assertEqual(inv.explode_proportional(near), [])
        self.assertEqual(len(inv.explode_proportional(far)), 1)

    def test_a_rolling_wheel_turns_once_per_circumference_the_right_way(self):
        scene = {"parts": [part("w", (1, 1, 0.2), spin_axis=[0, 0, 1])], "finale": {"rollers": ["w"], "t_go": 0, "dur": 6}}

        def states(turn):
            return [{"t": 1.5, "root": {"pos": [0, 0, 0]}, "parts": [{"spin": 0}]}, {"t": 4.0, "root": {"pos": [5, 0, 0]}, "parts": [{"spin": turn}]}]
        right = -5 / 0.5 * 180 / 3.141592653589793                                    # radius 0.5, 5 units: 10 radians, clockwise about +z
        self.assertEqual(inv.rolling_is_physical(scene, states(right)), [])
        self.assertTrue(inv.rolling_is_physical(scene, states(right * 0.5)))          # slips
        self.assertTrue(inv.rolling_is_physical(scene, states(-right)))               # rolls backwards

    def test_a_flow_that_ends_far_from_its_part_is_reported(self):
        scene = {"parts": [part("a", (1, 1, 1), (0, 0, 0)), part("b", (1, 1, 1), (4, 0, 0))],
                 "events": [{"type": "flow", "path": "p", "medium": "air", "t0": 0, "t1": 2}], "paths": {"p": [[0, 0, 0], [4, 0, 0]]}}
        home = {"t": 1.0, "root": {"pos": [0, 0, 0], "pivot": [0, 0, 0]}, "parts": [dict(dx=0, dy=0, dz=0)] * 2}
        away = {"t": 1.0, "root": {"pos": [0, 0, 0], "pivot": [0, 0, 0]}, "parts": [dict(dx=0, dy=3, dz=0)] * 2}
        self.assertEqual(inv.flows_touch_parts(scene, [home]), [])
        self.assertEqual(len(inv.flows_touch_parts(scene, [away])), 2)


import math  # noqa: E402  (used by the helper test above)

# What is wrong today, by lesson. Every entry must still fail (the list cannot go stale); every other lesson and invariant must pass.
KNOWN = {
    "balloon-base": ["connections", "sizes_match_plan", "camera_frames_subject", "effects_scale"],
    "balloon-v2": ["connections", "sizes_match_plan", "mesh_integrity", "camera_frames_subject", "effects_scale"],
    "bicycle-v2": ["connections", "sizes_match_plan", "coupled_motion"],
    "engine-base": ["sizes_match_plan"],
    "engine-new": ["sizes_match_plan"],
    "submarine-v2": ["connections", "sizes_match_plan", "mesh_integrity"],
    "antenna": [],
    "jet_engine": [],
    "spacecraft": ["camera_frames_subject", "effects_scale"],
    "wifi": [],
}
COUPLINGS = {"bicycle-v2": [{"a": "crank", "b": "rear_wheel", "kind": "chain", "ratio": 2.75}]}      # the plan has no links yet (F4): the bicycle's chain, by hand


def lesson_paths():
    root = os.path.join(HERE, "..", "goop", "explainer", "lessons")
    return sorted(os.path.join(HERE, "fixtures", "lessons", f) for f in os.listdir(os.path.join(HERE, "fixtures", "lessons")) if f.endswith(".json")) + \
        sorted(os.path.join(root, f) for f in os.listdir(root) if f.endswith(".json"))


@unittest.skipUnless(inv.available() and codegen.available(), "node and deno are needed to play the saved lessons")
class SavedLessons(unittest.TestCase):
    results = {}

    @classmethod
    def setUpClass(cls):
        def one(path):
            name = os.path.basename(path)[:-5]
            with open(path) as f:
                story = json.load(f)
            return name, inv.check_all(build.load(path), story, COUPLINGS.get(name))
        with ThreadPoolExecutor(max_workers=4) as pool:
            cls.results = dict(pool.map(one, lesson_paths()))

    def test_every_saved_lesson_is_known(self):
        self.assertEqual(sorted(self.results), sorted(KNOWN), "add the new lesson to KNOWN (empty list if it is clean)")

    def test_invariants_hold_except_where_known_to_fail(self):
        for name, res in self.results.items():
            for invariant in inv.NAMES:
                with self.subTest(lesson=name, invariant=invariant):
                    found = res[invariant]
                    if invariant in KNOWN.get(name, []):
                        self.assertTrue(found, f"{name}: {invariant} now holds: remove it from KNOWN")
                    else:
                        self.assertEqual(found, [], f"{name}: " + "; ".join(str(v) for v in found[:3]))


if __name__ == "__main__":
    unittest.main()
