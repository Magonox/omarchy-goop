"""The model sheet (docs/design/3d-model-sheet.md): features become meshes, a sheet's own claims are checked, components get a way out, hands turn at their real rates."""
import json, math, os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop.explainer import blueprint, build, solids


def volume(m):
    p, idx, v = m["p"], m["i"], 0
    for t in range(0, len(idx), 3):
        a, b, c = (p[idx[t + k] * 3:idx[t + k] * 3 + 3] for k in range(3))
        v += sum(a[k] * (b[(k + 1) % 3] * c[(k + 2) % 3] - b[(k + 2) % 3] * c[(k + 1) % 3]) for k in range(3)) / 6
    return v


class Features(unittest.TestCase):
    def test_every_solid_is_closed_and_faces_outward_with_the_right_volume(self):
        cases = {
            "box": (solids.box([1, 1, 1], [2, 3, 4], [30, 40, 50]), 24, 0.01),
            "beam": (solids.beam([0, 0, 0], [3, 4, 1], 0.5, 0.2, [1, 0, 0]), (9 + 16 + 1) ** 0.5 * 0.1, 0.01),
            "cylinder": (solids.cylinder([0, 0, 0], [0, 2, 0], 1.0), 2 * math.pi, 0.03),
            "ring": (solids.ring([0, 0, 0], [0, 1, 0], 2.0, 0.5), 2 * math.pi ** 2 * 2 * 0.25, 0.06),
            "revolve cone": (solids.revolve([0, 0, 0], [0, 1, 0], [[1, 0], [0, 2]]), math.pi * 2 / 3, 0.03),
            "sphere": (solids.sphere([0, 0, 0], 1.0), 4 / 3 * math.pi, 0.07),
            "hollow body": (solids.revolve_closed([0, 0, 0], [0, 1, 0], [[2, 0], [2, 1], [1.6, 1], [1.6, 0.2], [1.0, 0.2], [1.0, 0]]), math.pi * (4 - 2.56) + math.pi * (2.56 - 1) * 0.2, 0.03),
        }
        for name, (mesh, want, tol) in cases.items():
            with self.subTest(name):
                self.assertAlmostEqual(volume(mesh) / want, 1.0, delta=tol)

    def test_radial_copies_turn_about_the_axis(self):
        out = solids.compile_feature({"shape": "radial", "center": [0, 0, 0], "axis": "z", "count": 12, "item": {"shape": "box", "center": [0, 3, 0], "size": [0.1, 0.4, 0.05]}})
        self.assertEqual(len(out), 12)
        lo, hi = solids.bounds(out)
        self.assertAlmostEqual(hi[0], 3.2, delta=0.05)
        self.assertAlmostEqual(lo[1], -3.2, delta=0.05)

    def test_mistakes_are_explained(self):
        for bad, word in (({"shape": "cone"}, "shape"), ({"shape": "box", "center": [0, 0, 0], "size": [1, 1]}, "size"), ({"shape": "cylinder", "from": [0, 0, 0], "to": [0, 0, 0], "radius": 1}, "same point"),
                          ({"shape": "revolve", "base": [0, 0, 0], "axis": "y", "profile": [[1, 2], [1, 0]]}, "closed"), ({"shape": "radial", "center": [0, 0, 0], "count": 1, "item": {}}, "count"),
                          ({"shape": "box", "center": [0, 0, 0], "size": [1, 1, 1], "material": "mud"}, "material")):
            with self.assertRaises(ValueError) as cm:
                solids.compile_feature(bad)
            self.assertIn(word, str(cm.exception))


def stool():
    return {"version": 1, "title": "A stool", "layout": {"template": "blueprint", "explode": "free"},
            "parts": [
                {"id": "seat", "kind": "solid", "label": "Seat", "material": "wood", "features": [{"shape": "cylinder", "from": [0, 4, 0], "to": [0, 4.4, 0], "radius": 1.5}],
                 "views": {"front": [-1.5, 1.5, 4, 4.4], "top": [-1.5, 1.5, -1.5, 1.5]}},
                {"id": "leg_a", "kind": "solid", "label": "Leg A", "material": "dark_wood", "features": [{"shape": "beam", "from": [-1, 0, 0], "to": [-1, 4, 0], "width": 0.3, "thickness": 0.3}]},
                {"id": "leg_b", "kind": "solid", "label": "Leg B", "material": "dark_wood", "features": [{"shape": "beam", "from": [1, 0, 0], "to": [1, 4, 0], "width": 0.3, "thickness": 0.3}]}],
            "connections": [{"a": "seat", "b": "leg_a", "at": [-1, 4, 0]}, {"a": "seat", "b": "leg_b", "at": [1, 4, 0]}],
            "steps": [{"say": "This is a small stool, with a round seat held up by two legs, like a real one.", "do": [{"reveal": ["seat", "leg_a", "leg_b"]}, {"zoom": "all"}]},
                      {"say": "Each leg meets the seat at one point, so the legs carry the seat's weight down to the floor.", "do": [{"label": ["seat"]}]}],
            "recap": "Legs carry the seat.", "question": "What other furniture has legs?"}


class Sheet(unittest.TestCase):
    def test_a_good_sheet_builds_with_components_in_place(self):
        scene = build.build(stool())
        parts = {p["id"]: p for p in scene["parts"]}
        self.assertEqual(sorted(parts), ["leg_a", "leg_b", "seat"])
        self.assertGreater(parts["seat"]["pos"][1], parts["leg_a"]["pos"][1])           # the seat is above the legs' middle
        self.assertAlmostEqual(parts["leg_a"]["pos"][0], -parts["leg_b"]["pos"][0], places=2)

    def test_a_view_that_disagrees_with_the_features_is_sent_back_with_numbers(self):
        s = stool()
        s["parts"][0]["views"]["front"] = [-1.5, 1.5, 4, 6]
        with self.assertRaises(build.StoryboardError) as cm:
            build.build(s)
        self.assertIn("front view says it spans y 4 to 6", str(cm.exception))
        self.assertIn("4.00 to 4.40", str(cm.exception))

    def test_a_connection_point_must_lie_on_both_components(self):
        s = stool()
        s["connections"][0]["at"] = [-1, 9, 0]
        with self.assertRaises(build.StoryboardError) as cm:
            build.build(s)
        self.assertIn("do not meet there", str(cm.exception))

    def test_components_get_the_way_out_with_fewest_others_in_the_path(self):
        scene = build.build(stool())
        parts = {p["id"]: p for p in scene["parts"]}
        self.assertGreater(parts["seat"]["explode"][1], 0)                              # the seat lifts off
        self.assertLess(parts["leg_a"]["explode"][0], 0)                                # the legs go out to their own sides
        self.assertGreater(parts["leg_b"]["explode"][0], 0)

    def test_a_part_with_a_real_period_turns_about_its_own_pivot_at_its_own_rate(self):
        s = stool()
        s["timelapse"] = 10
        s["parts"].append({"id": "hand", "kind": "solid", "label": "Hand", "material": "black", "features": [{"shape": "beam", "from": [0, 4.45, 0], "to": [1.2, 4.45, 0], "width": 0.1, "thickness": 0.05, "normal": [0, 1, 0]}],
                           "spin": {"axis": "y", "pivot": [0, 4.45, 0], "period_s": 60, "dir": "cw"}})
        s["connections"].append({"a": "hand", "b": "seat", "at": [0.1, 4.4, 0]})
        s["steps"][1]["do"].append({"spin": ["hand"]})
        scene = build.build(s)
        hand = next(p for p in scene["parts"] if p["id"] == "hand")
        self.assertAlmostEqual(hand["spin_rate"], -60.0, places=2)                       # 360 degrees per 60 s, times 10, clockwise is negative about +y
        self.assertEqual(hand["spin_axis"], [0, 1, 0])
        self.assertTrue(any(abs(v) > 0.01 for v in hand["spin_pivot"]))                  # the pivot is the end of the hand, not its middle
        ev = next(e for e in scene["events"] if e["type"] == "spin")
        self.assertEqual(ev["rates"], {"hand": hand["spin_rate"]})

    def test_a_sheet_is_not_judged_by_the_old_box_overlap_rule(self):
        s = stool()
        s["parts"].append({"id": "pad", "kind": "solid", "label": "Pad", "material": "leather", "features": [{"shape": "cylinder", "from": [0, 4.3, 0], "to": [0, 4.6, 0], "radius": 1.2}]})
        s["connections"].append({"a": "pad", "b": "seat", "at": [0, 4.4, 0]})
        build.build(s)                                                                  # the pad sits partly inside the seat's box: allowed

    def test_the_saved_chair_and_watch_are_valid_sheets(self):
        here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "lessons")
        for name, hands in (("chair-sheet.json", False), ("watch-sheet.json", True)):
            with self.subTest(name):
                story = json.load(open(os.path.join(here, name)))
                scene = build.build(story)
                self.assertGreaterEqual(len(scene["parts"]), 10)
                if hands:
                    rates = {p["id"]: p["spin_rate"] for p in scene["parts"] if p.get("spin_rate")}
                    self.assertAlmostEqual(rates["minute_hand"] / rates["hour_hand"], 12, places=1)
                    self.assertAlmostEqual(rates["second_hand"] / rates["minute_hand"], 60, places=1)
                    self.assertTrue(all(r < 0 for r in rates.values()))                 # clockwise


def gear(pid, center, axis, radius, thick=0.1, period=None, direction="cw"):
    c = list(center)
    k = {"x": 0, "y": 1, "z": 2}[axis]
    a, b = list(c), list(c)
    a[k] -= thick / 2
    b[k] += thick / 2
    spin = {"axis": axis, "pivot": c}
    if period:
        spin.update(period_s=period, dir=direction)
    return {"id": pid, "kind": "solid", "label": pid.replace("_", " ").title(), "material": "steel",
            "features": [{"shape": "cylinder", "from": a, "to": b, "radius": radius}], "spin": spin}


def train(parts, links, connections):
    s = stool()
    s["parts"] += parts
    s["links"] = links
    s["connections"] += connections
    s["steps"][1]["do"].append({"spin": [parts[0]["id"]]})
    return build.build(s)


def rates(scene):
    return {p["id"]: p.get("spin_rate") for p in scene["parts"] if p.get("spin_rate") is not None}


class SavedEggBeater(unittest.TestCase):
    def test_the_two_whisks_turn_opposite_ways_and_the_whole_train_turns_together(self):
        here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "lessons", "egg-beater-sheet.json")
        scene = build.build(json.load(open(here)))
        r = {p["id"]: p["spin_rate"] for p in scene["parts"] if p.get("spin_rate")}
        self.assertLess(r["beater_left"] * r["beater_right"], 0)
        self.assertGreater(abs(r["beater_left"]), abs(r["crank_wheel"]))            # the small gears turn faster than the big one
        ev = next(e for e in scene["events"] if e["type"] == "spin")
        self.assertTrue({"crank_wheel", "pinion_left", "pinion_right", "beater_left", "beater_right"} <= set(ev["parts"]))


class GearLinks(unittest.TestCase):
    """Only the driver has a speed; the others follow from how they are linked, worked out from where the gears touch."""

    def test_gears_side_by_side_turn_opposite_ways_at_the_ratio_of_their_sizes(self):
        sc = train([gear("big", [0, 6, 0], "z", 1.0, period=6), gear("small", [1.5, 6, 0], "z", 0.5)],
                   [{"a": "big", "b": "small", "kind": "mesh"}], [{"a": "big", "b": "small", "at": [1.0, 6, 0]}])
        r = rates(sc)
        self.assertAlmostEqual(r["big"], -60.0, places=2)                 # 360 degrees in 6 s, clockwise
        self.assertAlmostEqual(r["small"], 120.0, places=1)               # half the size: twice as fast, the other way

    def test_gears_at_right_angles_turn_the_way_their_contact_points_say(self):
        # an egg beater: a crown wheel facing +z drives two pinions with upright axes, one caught at its front, one at its back
        wheel = gear("wheel", [0, 6, 0.3], "z", 1.2, period=2)
        left, right = gear("left", [-0.6, 4.8, 0.0], "y", 0.3), gear("right", [0.6, 4.8, 0.6], "y", 0.3)
        sc = train([wheel, left, right], [{"a": "wheel", "b": "left", "kind": "mesh"}, {"a": "wheel", "b": "right", "kind": "mesh"}],
                   [{"a": "wheel", "b": "left", "at": [-0.6, 4.8, 0.3]}, {"a": "wheel", "b": "right", "at": [0.6, 4.8, 0.3]}])
        r = rates(sc)
        self.assertLess(r["left"] * r["right"], 0)                         # opposite ways
        self.assertAlmostEqual(abs(r["left"]), abs(r["right"]), places=1)   # the same speed

    def test_a_chain_turns_the_same_way_at_its_ratio_and_a_shaft_turns_as_one(self):
        sc = train([gear("pedals", [0, 6, 0], "z", 1.0, period=4), gear("sprocket", [3, 6, 0], "z", 0.4), gear("wheel", [3, 6, 0.3], "z", 1.5)],
                   [{"a": "pedals", "b": "sprocket", "kind": "chain", "ratio": 2.5}, {"a": "sprocket", "b": "wheel", "kind": "shaft"}],
                   [{"a": "sprocket", "b": "wheel", "at": [3, 6, 0.1]}])
        r = rates(sc)
        self.assertAlmostEqual(r["sprocket"], r["pedals"] * 2.5, places=2)
        self.assertAlmostEqual(r["wheel"], r["sprocket"], places=2)

    def test_turning_one_part_of_a_train_turns_all_of_it(self):
        sc = train([gear("big", [0, 6, 0], "z", 1.0, period=6), gear("small", [1.5, 6, 0], "z", 0.5)],
                   [{"a": "big", "b": "small", "kind": "mesh"}], [{"a": "big", "b": "small", "at": [1.0, 6, 0]}])
        ev = next(e for e in sc["events"] if e["type"] == "spin")
        self.assertEqual(sorted(ev["parts"]), ["big", "small"])
        self.assertEqual(set(ev["rates"]), {"big", "small"})

    def test_mistakes_in_a_train_are_explained(self):
        cases = [
            ([gear("big", [0, 6, 0], "z", 1.0, period=6), gear("small", [1.5, 6, 0], "z", 0.5)], [{"a": "big", "b": "small", "kind": "mesh"}], [], "point where their teeth meet"),
            ([gear("big", [0, 6, 0], "z", 1.0, period=6), gear("small", [1.5, 6, 0], "z", 0.5)], [], [], "nothing drives it"),
            ([gear("big", [0, 6, 0], "z", 1.0, period=6), gear("small", [1.5, 6, 0], "z", 0.5, period=1)], [{"a": "big", "b": "small", "kind": "mesh"}],
             [{"a": "big", "b": "small", "at": [1.0, 6, 0]}], "only to the part that drives"),
            ([gear("big", [0, 6, 0], "z", 1.0, period=6), gear("small", [1.5, 6, 0], "z", 0.5)], [{"a": "big", "b": "small", "kind": "chain"}], [], "needs ratio"),
        ]
        for parts, links, conns, words in cases:
            with self.subTest(words):
                with self.assertRaises(build.StoryboardError) as cm:
                    train(parts, links, conns)
                self.assertIn(words, str(cm.exception))


if __name__ == "__main__":
    unittest.main()
