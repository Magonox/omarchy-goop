"""Members: tubes between named joints (goop/explainer/members.py, blueprint.resolve): tubes that share a joint meet by construction."""
import json, math, os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop.explainer import blueprint, build, members, planner


def story(**extra):
    s = {"version": 1, "title": "A small frame", "layout": {"template": "blueprint"},
         "joints": {"bb": [0, 1, 0], "seat": [-0.4, 2.4, 0], "head": [1.4, 2.6, 0], "axle": [-1.5, 0.8, 0]},
         "parts": [
             {"id": "seat_tube", "kind": "member", "label": "Seat tube", "from": "bb", "to": "seat", "radius": 0.08, "material": "red"},
             {"id": "top_tube", "kind": "member", "label": "Top tube", "from": "seat", "to": "head", "radius": 0.07},
             {"id": "stays", "kind": "member", "label": "Stays", "from": "bb", "to": "axle", "radius": 0.05, "z": [-0.2, 0.2]},
             {"id": "wheel", "kind": "code", "label": "Wheel", "brief": "a wheel with a tyre and thin spokes, standing on its edge", "size": [1.6, 1.6, 0.2], "at": ["axle"]}],
         "steps": [{"say": "A frame is made of tubes that meet at joints, like a real bicycle frame.", "do": [{"reveal": ["seat_tube", "top_tube", "stays", "wheel"]}, {"zoom": "all"}]},
                   {"say": "Each tube runs from one joint to the next, so they meet where they should.", "do": [{"label": ["top_tube"]}]}],
         "recap": "Tubes meet at shared joints.", "question": "What other machines have frames?"}
    s.update(extra)
    return s


def signed_volume(m):
    p, idx, v = m["p"], m["i"], 0
    for t in range(0, len(idx), 3):
        a, b, c = (p[idx[t + k] * 3:idx[t + k] * 3 + 3] for k in range(3))
        v += sum(a[k] * (b[(k + 1) % 3] * c[(k + 2) % 3] - b[(k + 2) % 3] * c[(k + 1) % 3]) for k in range(3)) / 6
    return v


class Tube(unittest.TestCase):
    def test_a_tube_is_a_closed_outward_facing_solid_of_about_the_right_volume(self):
        m = members.tube([0, 0, 0], [0, 2, 0], 0.1)
        self.assertGreater(signed_volume(m), 0)
        self.assertAlmostEqual(signed_volume(m), math.pi * 0.01 * 2 + 4 / 3 * math.pi * 0.001, delta=0.004)
        self.assertEqual(len(m["p"]), len(m["n"]))
        self.assertTrue(all(0 <= i < len(m["p"]) // 3 for i in m["i"]))

    def test_a_tube_runs_between_its_two_points_with_rounded_ends(self):
        m = members.tube([0, 0, 0], [3, 4, 0], 0.2)
        xs, ys = m["p"][0::3], m["p"][1::3]
        self.assertAlmostEqual(max(ys) - min(ys), 4 + 0.4, delta=0.1)
        self.assertAlmostEqual(max(xs) - min(xs), 3 + 0.4, delta=0.1)


class Resolve(unittest.TestCase):
    def test_members_become_boxes_with_meshes_at_their_joints(self):
        out, errs = blueprint.resolve(story())
        self.assertEqual(errs, [])
        tube = next(p for p in out["parts"] if p["id"] == "top_tube")
        self.assertEqual(tube["at"], [[0.5, 2.5, 0.0]])
        self.assertAlmostEqual(tube["size"][0], 1.8 + 0.14, places=3)
        self.assertTrue(tube["_meshes"])
        stays = next(p for p in out["parts"] if p["id"] == "stays")
        self.assertEqual([c[2] for c in stays["at"]], [-0.2, 0.2])
        wheel = next(p for p in out["parts"] if p["id"] == "wheel")
        self.assertEqual(wheel["at"], [[-1.5, 0.8, 0.0]])                        # a joint name in `at` becomes its point

    def test_tubes_that_share_a_joint_touch_in_the_built_scene(self):
        scene = build.build(story(), parts_dir="/nonexistent")
        parts = {p["id"]: p for p in scene["parts"]}
        seat, top = parts["seat_tube"], parts["top_tube"]
        # both pass through the seat joint (-0.4, 2.4, 0) in the machine frame; the scene is shifted, so compare the two tubes' offset from each other
        self.assertAlmostEqual(top["pos"][0] - seat["pos"][0], 0.5 - (-0.2), places=2)
        self.assertAlmostEqual(top["pos"][1] - seat["pos"][1], 2.5 - 1.7, places=2)

    def test_mistakes_are_explained_for_the_model(self):
        bad = story()
        bad["parts"][0]["to"] = "nowhere"
        self.assertIn("names of joints", "; ".join(blueprint.resolve(bad)[1]))
        bad = story(joints={"BB": [0, 1, 0]})
        self.assertTrue(blueprint.resolve(bad)[1])
        bad = story()
        bad["parts"][1]["radius"] = 9
        self.assertIn("radius", "; ".join(blueprint.resolve(bad)[1]))
        bad = story()
        bad["parts"][3]["at"] = ["nowhere"]
        self.assertIn("not in joints", "; ".join(blueprint.resolve(bad)[1]))

    def test_members_only_belong_in_a_blueprint(self):
        bad = story(layout={"template": "assembly"})
        with self.assertRaises(build.StoryboardError) as cm:
            build.build(bad, parts_dir="/nonexistent")
        self.assertIn("blueprint", str(cm.exception))

    def test_the_planner_skips_members_and_waits_only_for_code_parts(self):
        s = story()
        self.assertEqual(planner.first_parts(s), ["wheel"])
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            planner.write_pending(d, s)
            self.assertEqual(sorted(os.listdir(d)), ["wheel.json"])
        self.assertEqual(planner.full_story(s, {"wheel": {"code": "function build(M){}"}})["parts"][3]["code"], "function build(M){}")


if __name__ == "__main__":
    unittest.main()
