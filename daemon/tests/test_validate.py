"""The geometry validator: finds parts that float, cut into each other, sit outside what they were declared inside, or are people."""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop.explainer import validate


def box(w, h, d):
    x, y, z = w / 2, h / 2, d / 2
    corners = [(sx * x, sy * y, sz * z) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    idx = [i for a, b, c, d in faces for i in (a, b, c, a, c, d)]
    return {"p": [v for c in corners for v in c], "n": [], "i": idx}


def part(pid, size, pos, **kw):
    w, h, d = size
    return {"id": pid, "label": pid.replace("_", " ").title(), "pos": list(pos), "rot": [0, 0, 0], "shape": {"scale": 1, "h": kw.pop("plan_h", h), "meshes": [box(w, h, d)]}, **kw}


def scene(parts, template="assembly"):
    return {"template": template, "parts": parts}


def kinds(findings):
    return sorted(f.kind for f in findings)


class Validate(unittest.TestCase):
    def test_parts_that_touch_are_fine(self):
        s = scene([part("base", (2, 1, 2), (0, 0.5, 0)), part("mast", (0.4, 3, 0.4), (0, 2.5, 0)), part("flag", (1, 0.5, 0.1), (0.7, 3.75, 0))])
        self.assertEqual(validate.check(s), [])

    def test_a_floating_part_is_reported_with_the_gap(self):
        s = scene([part("base", (2, 1, 2), (0, 0.5, 0)), part("mast", (0.4, 3, 0.4), (0, 2.5, 0)), part("lamp", (0.5, 0.5, 0.5), (0, 6, 0))])
        f = validate.check(s)
        self.assertEqual(kinds(f), ["floating"])
        self.assertIn("'Mast'", f[0].message)
        self.assertRegex(f[0].message, r"\d\.\d\d units away")
        self.assertEqual(len(f), 1)

    def test_a_part_nested_inside_another_is_not_a_collision(self):
        s = scene([part("cylinder", (2, 3, 2), (0, 1.5, 0)), part("piston", (1.4, 1, 1.4), (0, 1.5, 0))])
        self.assertEqual(validate.check(s), [])

    def test_two_parts_cutting_into_each_other_are_reported(self):
        s = scene([part("a", (2, 2, 2), (0, 1, 0)), part("b", (2, 2, 2), (1.2, 1, 0))])
        self.assertEqual(kinds(validate.check(s)), ["overlap"])

    def test_declared_inside_must_really_be_inside(self):
        s = scene([part("envelope", (4, 6, 4), (0, 6, 0)), part("hot_air", (3, 5, 3), (0, 0, 0)), part("basket", (1, 1, 1), (0, 0.5, 0))])
        story = {"parts": [{"id": "hot_air", "inside": "envelope"}]}
        self.assertIn("inside", kinds(validate.check(s, story)))
        s["parts"][1]["pos"] = [0, 6, 0]
        self.assertNotIn("inside", kinds(validate.check(s, story)))

    def test_attached_parts_must_touch(self):
        s = scene([part("basket", (1, 1, 1), (0, 0.5, 0)), part("burner", (1, 0.5, 1), (0, 2, 0))])
        story = {"parts": [{"id": "burner", "attach": {"to": "basket", "at": "top"}}]}
        f = [x for x in validate.check(s, story) if x.kind == "attach"]
        self.assertEqual(len(f), 1)
        self.assertIn("gap", f[0].message)

    def test_people_are_reported_even_in_templates_that_are_not_checked(self):
        s = scene([part("seat", (1, 0.2, 1), (0, 1, 0)), part("rider", (1, 2, 1), (0, 2, 0), label="Rider's Weight")], template="network")
        self.assertEqual(kinds(validate.check(s)), ["people"])

    def test_a_part_that_came_out_the_wrong_size_is_reported(self):
        s = scene([part("a", (2, 1, 2), (0, 0.5, 0)), part("b", (2, 1, 2), (0, 1.5, 0), plan_h=2)])
        self.assertEqual(kinds(validate.check(s)), ["size"])

    def test_a_blueprint_machine_below_ground_is_reported(self):
        s = scene([part("body", (4, 1, 2), (0, 0.5, 0)), part("wheel", (1, 1, 1), (1, -1.2, 0))], template="blueprint")
        self.assertIn("ground", kinds(validate.check(s)))

    def test_findings_read_as_sentences_with_numbers(self):
        s = scene([part("a", (1, 1, 1), (0, 0.5, 0)), part("b", (1, 1, 1), (0, 5, 0))])
        self.assertRegex(str(validate.check(s)[0]), r"^\[floating\] .*\d")


if __name__ == "__main__":
    unittest.main()
