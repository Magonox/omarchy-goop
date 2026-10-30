import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop.explainer import build, codegen, schema

GOOD = "function build(M){ return [{material:'gold', look:'solid', mesh: M.lathe([[0.2,-0.05],[1.5,-0.05],[1.5,0.05],[0.2,0.05],[0.2,-0.05]], 32)}]; }"
needs_deno = unittest.skipUnless(codegen.available(), "deno is not installed")


def story(code):
    return {"version": 1, "title": "T", "layout": {"template": "axis"},
            "parts": [{"id": "a", "kind": "code", "label": "A", "code": code}, {"id": "b", "kind": "cylinder", "label": "B"}],
            "steps": [{"say": "This is the first part, which does a job.", "do": [{"reveal": ["a", "b"]}]},
                      {"say": "And this is the second part, which does another job.", "do": [{"label": ["a"]}]}]}


class Checks(unittest.TestCase):
    def test_clean_rejects_bad_geometry(self):
        mesh = {"p": [0, 0, 0, 1, 0, 0, 0, 1, 0], "n": [0, 0, 1] * 3, "i": [0, 1, 2]}
        ok = [{"material": "gold", "look": "solid", "mesh": mesh}]
        meshes, dims = codegen._clean(ok, "part 'a'")
        self.assertEqual(len(meshes), 1)
        for bad in ([], "x", [{"material": "gold", "mesh": {"p": [0], "n": [0], "i": []}}],
                    [{"material": "unobtainium", "mesh": mesh}], [{"material": "gold", "look": "shiny", "mesh": mesh}],
                    [{"material": "gold", "mesh": {**mesh, "i": [0, 1, 9]}}],
                    [{"material": "gold", "mesh": {**mesh, "p": [0, 0, 0, 1e9, 0, 0, 0, 1, 0]}}],
                    [{"material": "gold", "mesh": {**mesh, "p": [0, 0, 0, 0.001, 0, 0, 0, 0.001, 0]}}]):
            with self.assertRaises(codegen.CodeError):
                codegen._clean(bad, "part 'a'")

    def test_code_length_is_validated(self):
        errs = schema.validate(story("x"))
        self.assertTrue(any("a code part needs code" in e for e in errs))


@needs_deno
class Sandbox(unittest.TestCase):
    def test_good_code_builds_and_lays_out(self):
        scene = build.build(story(GOOD))
        part = next(p for p in scene["parts"] if p["id"] == "a")
        self.assertEqual(part["shape"]["type"], "mesh")
        self.assertGreater(part["shape"]["r"], 1.0)
        self.assertIn("gold", part["palette"])

    def test_the_callers_storyboard_is_not_modified(self):
        s = story(GOOD)
        build.build(s)
        self.assertNotIn("_meshes", s["parts"][0])

    def test_runtime_errors_come_back_as_repairable_messages(self):
        with self.assertRaises(build.StoryboardError) as cm:
            build.build(story("function build(M){ return M.nothing.here(); }"))
        self.assertIn("your code threw an error", str(cm.exception))

    def test_hostile_code_is_contained(self):
        hostile = {
            "reads files": "function build(M){ Deno.readTextFileSync('/etc/passwd'); return []; }",
            "runs programs": "function build(M){ new Deno.Command('id').outputSync(); return []; }",
            "reads the environment": "function build(M){ Deno.env.get('HOME'); return []; }",
            "writes files": "function build(M){ Deno.writeTextFileSync('/tmp/goop-escape-test', 'x'); return []; }",
        }
        for name, code in hostile.items():
            with self.subTest(name):
                with self.assertRaises(build.StoryboardError):
                    build.build(story(code))
        self.assertFalse(os.path.exists("/tmp/goop-escape-test"))

    def test_endless_loops_are_stopped(self):
        old = codegen.LIMITS["seconds"]
        codegen.LIMITS["seconds"] = 2
        try:
            with self.assertRaises(build.StoryboardError) as cm:
                build.build(story("function build(M){ while (true) {} }"))
        finally:
            codegen.LIMITS["seconds"] = old
        self.assertIn("ran longer", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
