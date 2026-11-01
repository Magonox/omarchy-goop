import copy, os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop.explainer import blueprint, build, codegen, layout, planner, schema, timeline


def part(pid, label, size, at, **kw):
    return {"id": pid, "kind": "code", "label": label, "brief": f"A realistic {label} with its main shapes and a few small details.", "size": size, "at": at, **kw}


def truck():
    return {
        "version": 1, "title": "How a monster truck works", "layout": {"template": "blueprint"},
        "parts": [
            part("frame", "Frame", [5.4, 0.5, 2.0], [[0, 1.25, 0]]),
            part("body", "Body", [4.2, 1.6, 2.2], [[-0.3, 2.3, 0]]),
            part("engine", "Engine", [1.4, 1.2, 1.4], [[2.35, 2.1, 0]]),
            part("tires", "Tires", [1.6, 1.6, 0.9], [[1.9, 0.8, 1.45], [1.9, 0.8, -1.45], [-1.9, 0.8, 1.45], [-1.9, 0.8, -1.45]]),
        ],
        "steps": [
            {"say": "This is a monster truck, and it is built from a few big parts that all work together.", "do": [{"zoom": "all"}]},
            {"say": "Let's take it apart. The frame is the strong steel skeleton that everything else bolts onto.", "do": [{"label": ["frame"]}, {"highlight": ["frame"]}, {"zoom": "frame"}]},
            {"say": "The four giant tires are taller than a grown-up, and they roll over cars as if they were speed bumps.", "do": [{"label": ["tires"]}, {"highlight": ["tires"]}]},
            {"say": "Up front is the engine. It makes the power that turns the tires round and round.", "do": [{"label": ["engine"]}, {"zoom": "engine"}]},
        ],
        "finale": {"say": "Now watch every part come back together into one monster truck, and off it goes!", "motion": "drive", "emitter": "tires"},
        "recap": "Remember: a frame, big tires and an engine, all working together.",
    }


def scene(story=None):
    return build.build(story or truck(), parts_dir="/tmp/bp.parts")


class Checks(unittest.TestCase):
    def test_a_sound_blueprint_passes(self):
        self.assertEqual(schema.validate(truck(), outline=True), [])

    def test_parts_passing_through_each_other_are_named_with_numbers(self):
        s = truck()
        s["parts"][1]["at"] = [[-0.3, 1.6, 0]]               # the body sunk into the frame
        errs = schema.validate(s, outline=True)
        self.assertTrue(any("pass through each other" in e and "'body'" in e and "'frame'" in e and "%" in e for e in errs), errs)

    def test_a_floating_part_is_called_out(self):
        s = truck()
        s["parts"][2]["at"] = [[2.35, 7.0, 0]]
        errs = schema.validate(s, outline=True)
        self.assertTrue(any("'engine' floats away" in e for e in errs), errs)

    def test_a_part_declared_inside_another_may_sit_within_it(self):
        s = truck()
        s["parts"][2]["at"] = [[-0.3, 2.3, 0]]
        s["parts"][2]["inside"] = "body"
        self.assertEqual(schema.validate(s, outline=True), [])
        del s["parts"][2]["inside"]
        self.assertTrue(schema.validate(s, outline=True))

    def test_copies_of_one_part_must_not_collide_with_each_other(self):
        s = truck()
        s["parts"][3]["at"] = [[1.9, 0.8, 1.45], [1.9, 0.8, 1.5]]
        self.assertTrue(any("'tires' and 'tires#2' pass through" in e for e in schema.validate(s, outline=True)))

    def test_bad_sizes_and_centres_name_the_format(self):
        s = truck()
        s["parts"][0]["size"] = [0, 1, 1]
        s["parts"][1]["at"] = [[1, 2]]
        errs = schema.validate(s, outline=True)
        self.assertTrue(any("size must be [width, height, depth]" in e for e in errs))
        self.assertTrue(any("at must be a list" in e for e in errs))

    def test_a_blueprint_part_needs_no_width_or_height(self):
        self.assertFalse(any("width" in e for e in schema.validate(truck(), outline=True)))


class Layout(unittest.TestCase):
    def test_copies_become_instances_and_the_machine_stands_on_the_ground(self):
        sc = scene()
        ids = [p["id"] for p in sc["parts"]]
        self.assertEqual([i for i in ids if i.startswith("tires")], ["tires", "tires#2", "tires#3", "tires#4"])
        low = min(p["pos"][1] - p["shape"]["h"] / 2 for p in sc["parts"])
        self.assertAlmostEqual(low, 0.0, places=2)                          # the tires touch y = 0
        xs = [p["pos"][0] for p in sc["parts"]]
        self.assertAlmostEqual((min(xs) + max(xs)) / 2, 0.0, delta=1.0)    # centred left-right

    def test_every_part_is_exactly_where_its_box_says(self):
        sc = scene()
        by = {p["id"]: p for p in sc["parts"]}
        self.assertLess(abs(by["body"]["pos"][1] - by["frame"]["pos"][1] - 1.05), 0.01)      # the body sits right on the frame (2.3 - 1.25)
        self.assertEqual(by["tires"]["shape"]["h"], 1.6)
        self.assertEqual(by["tires"]["shape"]["r"], 0.8)

    def test_parts_fly_apart_away_from_the_middle_and_the_scene_carries_the_ground_for_the_finale(self):
        sc = scene()
        mid = [sum(p["pos"][k] for p in sc["parts"]) / len(sc["parts"]) for k in range(3)]
        for p in sc["parts"]:
            away = sum(p["explode"][k] * (p["pos"][k] - mid[k]) for k in range(3))
            self.assertGreater(away, 0, p["id"])
        self.assertAlmostEqual(sc["finale"]["bottom"], 0.0, places=2)
        self.assertEqual(sc["finale"]["heading"], [1, 0, 0])


class Teardown(unittest.TestCase):
    def test_step_one_shows_the_whole_machine_assembled(self):
        sc = scene()
        first = min(e["t0"] for e in sc["events"] if e["type"] == "reveal")
        revealed = {i for e in sc["events"] if e["type"] == "reveal" and e["t0"] <= first + 0.01 for i in e["parts"]}
        self.assertEqual(revealed, {p["id"] for p in sc["parts"]})
        explodes = [e for e in sc["events"] if e["type"] == "explode"]
        self.assertGreater(min(e["t0"] for e in explodes), sc["steps"][1]["t0"])            # nothing is apart during the first step

    def test_it_stays_apart_through_the_explanations_and_comes_back_for_the_finale(self):
        sc = scene()
        explodes = [e for e in sc["events"] if e["type"] == "explode"]
        self.assertEqual(len(explodes), 1)
        e, fin = explodes[0], sc["finale"]
        self.assertAlmostEqual(e["t0"], sc["steps"][1]["t0"] + 0.4, places=1)
        self.assertAlmostEqual(e["t1"], fin["t_go"] - 0.4, places=1)                         # back together just before it sets off
        self.assertEqual(e["settle"], 2.2)
        self.assertEqual(sorted(e["parts"]), sorted(p["id"] for p in sc["parts"]))

    def test_without_a_finale_it_comes_back_together_for_the_recap(self):
        s = truck()
        del s["finale"]
        sc = scene(s)
        e = next(e for e in sc["events"] if e["type"] == "explode")
        recap = sc["steps"][-1]
        self.assertAlmostEqual(e["t1"], recap["t0"] + 0.2, places=1)

    def test_the_camera_aims_at_where_a_part_really_hangs(self):
        sc = scene()
        by = {p["id"]: p for p in sc["parts"]}
        frame_step = sc["steps"][1]
        cam = min((c for c in sc["camera"] if c["t"] >= frame_step["t0"]), key=lambda c: c["t"])
        want = [by["frame"]["pos"][k] + by["frame"]["explode"][k] for k in range(3)]
        self.assertTrue(all(abs(cam["target"][k] - want[k]) < 0.01 for k in range(3)), (cam["target"], want))

    def test_other_templates_are_unchanged(self):
        s = {"version": 1, "title": "T", "layout": {"template": "axis"},
             "parts": [{"id": "a", "kind": "cylinder", "label": "A"}, {"id": "b", "kind": "cylinder", "label": "B"}],
             "steps": [{"say": "This is the first part, which does a job.", "do": [{"reveal": ["a"]}]}, {"say": "And this is the second part, which does another job.", "do": [{"reveal": ["b"]}]}]}
        sc = build.build(s)
        first = min(e["t0"] for e in sc["events"] if e["type"] == "reveal")
        revealed = {i for e in sc["events"] if e["type"] == "reveal" and e["t0"] <= first + 0.01 for i in e["parts"]}
        self.assertEqual(revealed, {"a"})

    def test_the_window_waits_for_all_parts_of_a_blueprint_lesson(self):
        self.assertEqual(sorted(planner.first_parts(truck())), sorted(p["id"] for p in truck()["parts"]))


class Fitting(unittest.TestCase):
    DIMS = {"r": 1.0, "h": 2.0, "ex": 4.0, "ey": 2.0, "ez": 1.0}

    def test_a_mesh_fills_its_box_without_changing_proportions(self):
        self.assertAlmostEqual(codegen.fit_box(self.DIMS, [8, 4, 2]), 2.0)               # doubled in every direction
        self.assertAlmostEqual(codegen.fit_box(self.DIMS, [8, 4, 1]), 1.0)               # the tightest side wins
        self.assertAlmostEqual(codegen.part_scale({"size": [2, 1, 0.5]}, self.DIMS), 0.5)
        self.assertAlmostEqual(codegen.part_scale({"width": 4, "height": 4}, self.DIMS), 2.0)    # the older width/height rule still works

    def test_the_part_prompt_gives_the_box_and_says_when_it_repeats(self):
        s = truck()
        text = planner.part_user(s, s["parts"][3], "monster trucks")
        self.assertIn("1.6 long", text)
        self.assertIn("0.9 wide", text)
        self.assertIn("appears 4 times", text)
        self.assertIn("+x", text)
        self.assertNotIn("appears", planner.part_user(s, s["parts"][0], "monster trucks"))

    def test_the_outline_prompt_teaches_blueprints_and_the_teardown_order(self):
        sp = planner.outline_system()
        for word in ('"blueprint"', "FRONT at +x", "ground at y=0", "taken apart", "step 1 introduces the whole finished machine"):
            self.assertIn(word, sp)


if __name__ == "__main__":
    unittest.main()
