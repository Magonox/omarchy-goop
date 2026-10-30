import copy, json, os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop.explainer import build, layout, schema, timeline, vocab

LESSONS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "goop", "explainer", "lessons")


def lesson(name):
    with open(os.path.join(LESSONS, name + ".json")) as f:
        return json.load(f)


NAMES = ["jet_engine", "wifi", "spacecraft"]


class Validation(unittest.TestCase):
    def test_all_lessons_are_valid(self):
        for n in NAMES:
            self.assertEqual(schema.validate(lesson(n)), [], n)

    def errs(self, mutate, name="jet_engine"):
        s = copy.deepcopy(lesson(name))
        mutate(s)
        return schema.validate(s)

    def test_errors_name_the_valid_choices(self):
        e = self.errs(lambda s: s["parts"][2].update(kind="warp_drive"))
        self.assertTrue(any("warp_drive" in x and "fan" in x for x in e), e)       # lists the vocabulary so a model can repair itself
        e = self.errs(lambda s: s["layout"].update(template="spiral"))
        self.assertTrue(any("axis" in x for x in e))
        e = self.errs(lambda s: s["steps"][1]["do"].append({"explode_all": 1}))
        self.assertTrue(any("exactly one of" in x for x in e))

    def test_references_and_limits(self):
        self.assertTrue(self.errs(lambda s: s["steps"][1]["do"].append({"reveal": ["ghost"]})))
        self.assertTrue(self.errs(lambda s: s["parts"].append(dict(s["parts"][2]))))                      # duplicate id
        self.assertTrue(self.errs(lambda s: s["parts"].append({"id": "floor", "kind": "box", "label": "x"})))   # reserved
        self.assertTrue(self.errs(lambda s: s.update(parts=s["parts"][:1])))                              # too few parts
        self.assertTrue(self.errs(lambda s: s["steps"][0].update(say="short")))
        self.assertTrue(self.errs(lambda s: s["steps"][0]["do"].append({"flow": {"from": "fan", "to": "fan", "medium": "plasma"}})))
        self.assertTrue(self.errs(lambda s: s["parts"][0].update(spans=["fan"])))                         # casing needs two ends
        self.assertTrue(self.errs(lambda s: s["parts"][2].update(label="x" * 40)))

    def test_template_specific_rules(self):
        self.assertTrue(self.errs(lambda s: s["parts"][4].update(between=["router"]), "wifi"))
        self.assertTrue(self.errs(lambda s: s["parts"][1].update(distance="orbit"), "wifi"))
        self.assertTrue(self.errs(lambda s: s["parts"].pop(0), "wifi"))                                   # no router
        self.assertTrue(self.errs(lambda s: s["parts"][4].update(attach={"to": "module", "at": "inwards"}), "spacecraft"))
        self.assertTrue(self.errs(lambda s: s["parts"][3].update(inside="nowhere"), "spacecraft"))

    def test_not_an_object(self):
        self.assertEqual(schema.validate([]), ["the storyboard must be a JSON object"])
        self.assertEqual(schema.validate({}) != [], True)


class AxisLayout(unittest.TestCase):
    def setUp(self):
        self.lay = layout.layout(lesson("jet_engine"))
        self.p = self.lay["placed"]

    def test_parts_sit_in_order_without_overlapping(self):
        order = ["fan", "compressor", "chamber", "turbine", "nozzle"]
        xs = [self.p[i]["pos"][0] for i in order]
        self.assertEqual(xs, sorted(xs))
        for a, b in zip(order, order[1:]):
            gap = (self.p[b]["pos"][0] - self.p[b]["shape"]["h"] / 2) - (self.p[a]["pos"][0] + self.p[a]["shape"]["h"] / 2)
            self.assertGreater(gap, 0.1, (a, b))
        self.assertAlmostEqual(sum(xs) / len(xs), 0, delta=0.9)                                          # roughly centred

    def test_casing_and_shaft_span_their_parts(self):
        c, s = self.p["casing"], self.p["shaft"]
        self.assertTrue(c["spanning"] and c["shape"]["r"] > max(self.p[i]["radius"] for i in ("fan", "compressor", "chamber", "turbine", "nozzle")) * 0.99)
        lo, hi = c["pos"][0] - c["shape"]["h"] / 2, c["pos"][0] + c["shape"]["h"] / 2
        self.assertLess(lo, self.p["fan"]["pos"][0] - self.p["fan"]["shape"]["h"] / 2)
        self.assertGreater(hi, self.p["nozzle"]["pos"][0] + self.p["nozzle"]["shape"]["h"] / 2 - 0.01)
        self.assertLess(s["pos"][0] + s["shape"]["h"] / 2, hi)                                           # the shaft does not reach the nozzle

    def test_axial_parts_lie_on_their_side(self):
        self.assertEqual(self.p["fan"]["rot"], [0, 0, -90])


class NetworkLayout(unittest.TestCase):
    def setUp(self):
        self.p = layout.layout(lesson("wifi"))["placed"]

    def test_signal_depends_on_distance_and_walls(self):
        self.assertEqual((self.p["laptop"]["signal"], self.p["phone"]["signal"], self.p["tv"]["signal"]), (4, 2, 1))

    def test_devices_get_farther_and_walls_sit_between(self):
        r = self.p["router"]["pos"]
        d = {k: ((self.p[k]["pos"][0] - r[0]) ** 2 + (self.p[k]["pos"][2] - r[2]) ** 2) ** 0.5 for k in ("laptop", "phone", "tv")}
        self.assertLess(d["laptop"], d["phone"])
        self.assertLess(d["phone"], d["tv"])
        for w, dev in (("wall1", "phone"), ("wall2", "tv")):
            wp = self.p[w]["pos"]
            dw = ((wp[0] - r[0]) ** 2 + (wp[2] - r[2]) ** 2) ** 0.5
            self.assertAlmostEqual(dw, d[dev] / 2, delta=0.2)

    def test_there_is_a_floor(self):
        self.assertTrue(self.p["floor"]["context"])


class AssemblyLayout(unittest.TestCase):
    def setUp(self):
        self.lay = layout.layout(lesson("spacecraft"))
        self.p, self.inst = self.lay["placed"], self.lay["instances"]

    def test_spine_stacks_bottom_to_top(self):
        ys = [self.p[i]["pos"][1] for i in ("engine", "module", "capsule")]
        self.assertEqual(ys, sorted(ys))

    def test_attached_parts_become_instances(self):
        self.assertEqual(len(self.inst["panels"]), 2)
        a, b = (self.p[i]["pos"][0] for i in self.inst["panels"])
        self.assertAlmostEqual(a, -b, places=2)                                                           # one on each side
        self.assertEqual(len(self.inst["thrusters"]), 4)
        self.assertEqual(len({tuple(self.p[i]["pos"]) for i in self.inst["thrusters"]}), 4)

    def test_inside_parts_share_the_parents_centre(self):
        self.assertEqual(self.p["tank"]["pos"], self.p["module"]["pos"])


class Timeline(unittest.TestCase):
    def test_every_lesson_builds_and_is_consistent(self):
        for n in NAMES:
            scene = build.build(lesson(n))
            steps = scene["steps"]
            self.assertTrue(all(a["t1"] <= b["t0"] + 1e-6 for a, b in zip(steps, steps[1:])), n)
            self.assertTrue(all(s["t1"] - s["t0"] >= 5 for s in steps), n)
            cam = [c["t"] for c in scene["camera"]]
            self.assertEqual(cam, sorted(cam), n)
            revealed = {i for e in scene["events"] if e["type"] == "reveal" for i in e["parts"]}
            self.assertEqual(revealed, {p["id"] for p in scene["parts"]}, n)                              # nothing stays hidden forever
            self.assertLess(scene["duration"], vocab.LIMITS["duration"], n)
            self.assertTrue(scene["question"], n)
            json.dumps(scene)                                                                              # serialisable

    def test_build_is_deterministic(self):
        for n in NAMES:
            self.assertEqual(build.build(lesson(n)), build.build(lesson(n)))

    def test_recap_step_is_appended(self):
        s = lesson("jet_engine")
        self.assertEqual(len(build.build(s)["steps"]), len(s["steps"]) + 1)

    def test_invalid_storyboard_raises_with_messages(self):
        s = lesson("wifi")
        s["parts"][0]["kind"] = "nope"
        with self.assertRaises(build.StoryboardError) as cm:
            build.build(s)
        self.assertTrue(cm.exception.errors)

    def test_duration_cap(self):
        s = lesson("jet_engine")
        s["steps"] = s["steps"] * 2
        s["steps"] = s["steps"][:12]
        for st in s["steps"]:
            st["say"] = "word " * 60
        with self.assertRaises(build.StoryboardError):
            build.build(s)

    def test_explode_and_flow_events(self):
        scene = build.build(lesson("jet_engine"))
        types = {e["type"] for e in scene["events"]}
        self.assertTrue({"reveal", "label", "highlight", "flow", "spin", "explode"} <= types)
        flow = next(e for e in scene["events"] if e["type"] == "flow")
        self.assertIn(flow["path"], scene["paths"])
        self.assertEqual(len(scene["paths"][flow["path"]]), 2)

    def test_narration_length_sets_duration(self):
        self.assertEqual(timeline.duration("one two three"), 5.0)
        self.assertGreater(timeline.duration("word " * 40), 15)


if __name__ == "__main__":
    unittest.main()
