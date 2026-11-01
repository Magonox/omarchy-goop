import json, os, sys, tempfile, threading, time, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from goop import access, settings, tools
from goop.agent import prompt
from goop.explainer import build, codegen, planner

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
needs_deno = unittest.skipUnless(codegen.available(), "deno is not installed")


def fixture():
    """A real planner answer (every part is code), kept so the tests need no model."""
    with open(os.path.join(FIXTURES, "blu_ray_code.json")) as f:
        return json.load(f)


def outline(story=None):
    """The same lesson as the planner's first answer: no code, a brief and a size for every part."""
    s = json.loads(json.dumps(story or fixture()))
    for p in s["parts"]:
        p.pop("code", None)
        p.pop("size", None)
        p["brief"] = f"A detailed model of the {p['label']} with its main shape and several small details."
        p["width"], p["height"] = 2.0, 1.0
    return s


class FakeModel:
    """Answers outline calls with the outline JSON and part calls with that part's code from the fixture; records what it was asked."""
    def __init__(self, outlines=None, delay=0.0, codes=None, slow=(), gate=None):
        self.outlines = list(outlines) if outlines is not None else [json.dumps(outline())]
        self.codes = codes or {p["id"]: p["code"] for p in fixture()["parts"]}
        self.gate = gate
        self.delay, self.slow, self.calls, self.active, self.peak, self.lock = delay, set(slow), [], 0, 0, threading.Lock()

    def __call__(self, system, prompt_):
        with self.lock:
            self.calls.append((system[:12], prompt_))
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            if system.startswith("You plan"):
                return self.outlines.pop(0) if len(self.outlines) > 1 else self.outlines[0]
            label = prompt_.split("Write the shape of this part: ")[1].split("\n")[0]
            pid = next(p["id"] for p in fixture()["parts"] if p["label"] == label)
            time.sleep(self.delay)
            if pid in self.slow and self.gate:
                self.gate.wait(30)                       # a slow part stays unfinished until the test opens the gate (the window launching)
            code = self.codes[pid]
            return code[0] if isinstance(code, list) and len(self.calls) % 2 else (code[-1] if isinstance(code, list) else code)
        finally:
            with self.lock:
                self.active -= 1


class Reading(unittest.TestCase):
    def test_json_plain_fenced_and_chatty(self):
        for text in ('{"a": 1}', '```json\n{"a": 1}\n```', 'Sure! Here you go:\n{"a": 1}\nHope that helps.'):
            self.assertEqual(planner.extract_json(text), {"a": 1})
        with self.assertRaises(ValueError):
            planner.extract_json("I cannot do that")

    def test_code_plain_fenced_and_chatty(self):
        for text in ("function build(M){return 1}", "```js\nfunction build(M){return 1}\n```", "Here:\nfunction build(M){return 1}"):
            self.assertEqual(planner.extract_code(text), "function build(M){return 1}")


class Outline(unittest.TestCase):
    def test_valid_outline_comes_back(self):
        model = FakeModel()
        story = planner.plan_outline("how Blu-ray works", "notes", model, title="Article")
        self.assertEqual(len(model.calls), 1)
        self.assertIn("Article", model.calls[0][1])
        self.assertNotIn("code", story["parts"][0])

    def test_problems_are_sent_back_and_repaired(self):
        bad = outline()
        del bad["parts"][0]["width"]
        model = FakeModel(outlines=[json.dumps(bad), json.dumps(outline())])
        planner.plan_outline("t", "", model)
        self.assertEqual(len(model.calls), 2)
        self.assertIn("width must be a number", model.calls[1][1])

    def test_ready_made_kinds_are_refused(self):
        bad = outline()
        bad["parts"][0]["kind"] = "cylinder"
        model = FakeModel(outlines=[json.dumps(bad), json.dumps(outline())])
        planner.plan_outline("t", "", model)
        self.assertIn("every part must be kind", model.calls[1][1])

    def test_gives_up_after_the_repairs(self):
        model = FakeModel(outlines=["nope"])
        with self.assertRaises(planner.PlanError):
            planner.plan_outline("t", "", model)
        self.assertEqual(len(model.calls), planner.REPAIRS + 1)

    def test_prompts_teach_the_staged_format(self):
        sp = planner.outline_system()
        for word in ("brief", "width", "sender", "first step should reveal only"):
            self.assertIn(word, sp)
        self.assertNotIn("function build", sp)
        ps = planner.part_system()
        for word in ("M.lathe", "M.extrude", "fits the width and height"):
            self.assertIn(word, ps)

    def test_the_scene_is_laid_out_before_any_code_exists(self):
        scene = build.build(outline(), parts_dir="/tmp/x.parts")
        for p in scene["parts"]:
            self.assertTrue(p["shape"]["file"].startswith("/tmp/x.parts/"))
            self.assertNotIn("meshes", p["shape"])
            self.assertEqual(p["shape"]["r"], 1.0)               # half the outline's width
            self.assertEqual(p["shape"]["h"], 1.0)
        self.assertGreater(scene["duration"], 20)

    def test_first_parts_come_from_the_first_step(self):
        s = outline()
        s["steps"][0]["do"] = [{"reveal": ["disc", "laser"]}]
        s["parts"] = s["parts"] + []
        ids = planner.first_parts(s)
        self.assertEqual(ids, [i for i in ("disc", "laser") if i in [p["id"] for p in s["parts"]]] or ids)
        s["steps"][0]["do"] = [{"label": ["disc"]}]
        self.assertEqual(planner.first_parts(s), [s["parts"][0]["id"]])


@needs_deno
class Parts(unittest.TestCase):
    def test_a_part_with_a_code_error_is_repaired(self):
        story = outline()
        part = story["parts"][0]
        codes = {p["id"]: p["code"] for p in fixture()["parts"]}
        broken = "function build(M) { return M.nothing.here(); }"
        calls = iter([broken, codes[part["id"]]])
        model = lambda system, prompt_: next(calls) if "Write the shape" in prompt_ or True else ""
        data = planner.make_part(story, part, "t", model)
        self.assertGreater(len(data["meshes"]), 0)
        self.assertGreater(data["scale"], 0)

    def test_a_part_that_never_works_becomes_a_stand_in(self):
        story = outline()
        model = FakeModel(codes={p["id"]: "function build(M){ throw new Error('no'); }" for p in fixture()["parts"]})
        with tempfile.TemporaryDirectory() as d:
            results = planner.produce(story, "t", model, d)
            self.assertTrue(all(not r["ok"] for r in results.values()))
            for p in story["parts"]:                                  # still a drawable file, so the lesson plays
                data = json.load(open(os.path.join(d, p["id"] + ".json")))
                self.assertGreater(len(data["meshes"]), 0)

    def test_parts_are_made_at_the_same_time_and_files_appear_as_they_finish(self):
        story = outline()
        model = FakeModel(delay=0.25)
        seen = []
        with tempfile.TemporaryDirectory() as d:
            planner.write_pending(d, story)
            results = planner.produce(story, "t", model, d, on_part=lambda pid, ok, s: seen.append((pid, ok)))
            self.assertEqual(len(results), len(story["parts"]))
            self.assertEqual(len(seen), len(story["parts"]))
            self.assertGreater(model.peak, 2)                          # several calls were in flight together
            for p in story["parts"]:
                self.assertGreater(len(json.load(open(os.path.join(d, p["id"] + ".json")))["meshes"]), 0)

    def test_a_finished_story_replays_without_the_model(self):
        story = outline()
        with tempfile.TemporaryDirectory() as d:
            results = planner.produce(story, "t", FakeModel(), d)
        full = planner.full_story(story, results)
        scene = build.build(full)                                       # code embedded, run in the sandbox
        self.assertTrue(all("meshes" in p["shape"] for p in scene["parts"]))


@needs_deno
class Runner(unittest.TestCase):
    """The whole detached pipeline with a fake model: the window opens when the first step's parts exist, before the slowest part."""
    def test_window_opens_before_the_last_part_and_everything_is_saved(self):
        import explain_run
        story = outline()
        first = planner.first_parts(story)
        later = [p["id"] for p in story["parts"] if p["id"] not in first][-1]       # a part the first step does not need, made slow
        gate = threading.Event()
        model = FakeModel(delay=0.05, slow=[later], gate=gate)
        launched = {}

        def launch(scene_path, address=""):
            launched["scene"], launched["address"] = scene_path, address
            parts = json.load(open(scene_path))["parts"]
            launched["state"] = {}
            for p in parts:
                with open(p["shape"]["file"]) as f:
                    launched["state"][p["id"]] = len(json.load(f)["meshes"])
            gate.set()                                   # now let the slow part finish

        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(explain_run, "SCENES", d), mock.patch.object(explain_run, "LOG", os.path.join(d, "log")), \
                mock.patch.object(explain_run.planner, "claude_runner", return_value=model), \
                mock.patch.object(explain_run, "say"), mock.patch.object(explain_run, "tell"), \
                mock.patch.object(explain_run.play, "stop") as stop, mock.patch.object(explain_run.play, "launch_scene", side_effect=launch), \
                mock.patch.object(explain_run.play, "save") as save:
            job = os.path.join(d, "job.json")
            json.dump({"topic": "how Blu-ray works", "notes": "n", "title": "T", "address": "0xabc", "model": "opus"}, open(job, "w"))
            explain_run.main(job)
        stop.assert_called_once()
        self.assertEqual(launched["address"], "0xabc")
        for pid in first:
            self.assertGreater(launched["state"][pid], 0, "the first step's parts were drawn before the window opened")
        self.assertEqual(launched["state"][later], 0, "the slow part was still being drawn when the window opened")
        save.assert_called_once()
        saved = save.call_args[0][0]
        self.assertTrue(all("code" in p for p in saved["parts"]))

    def test_an_outline_failure_is_told_to_the_user_and_nothing_opens(self):
        import explain_run
        model = FakeModel(outlines=["nope"])
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(explain_run, "SCENES", d), mock.patch.object(explain_run, "LOG", os.path.join(d, "log")), \
                mock.patch.object(explain_run.planner, "claude_runner", return_value=model), \
                mock.patch.object(explain_run, "say"), mock.patch.object(explain_run, "tell") as tell, \
                mock.patch.object(explain_run.play, "launch_scene") as launch:
            job = os.path.join(d, "job.json")
            json.dump({"topic": "x y z", "address": "0xabc"}, open(job, "w"))
            explain_run.main(job)
        tell.assert_called_once()
        launch.assert_not_called()


class Tool(unittest.TestCase):
    def setUp(self):
        for p in (mock.patch.object(tools, "_window", return_value=({"title": "Antenna article", "class": "chromium"}, set())),
                  mock.patch.object(tools, "_audit"), mock.patch.object(tools.codegen, "available", return_value=True),
                  mock.patch.object(tools.shutil, "which", return_value="/usr/bin/claude"),
                  mock.patch.object(tools, "_builder_running", return_value=False)):
            p.start()
        self.spawn = mock.patch.object(tools, "_spawn_builder").start()
        self.addCleanup(mock.patch.stopall)

    def cfg(self, **kw):
        return mock.patch.object(access.config, "load", return_value=kw)

    def call(self, args=None, **cfg):
        with self.cfg(**cfg), mock.patch.object(tools, "_approve") as ap:
            r = tools.call("explain_in_3d", "0xabc", {"topic": "how digital TV antennas work", "notes": "a tower sends waves"} if args is None else args)
        return r, ap

    def test_offer_mode_asks_first_then_starts_the_builder_and_returns_at_once(self):
        r, ap = self.call()
        ap.assert_called_once()
        self.assertEqual(ap.call_args[0][1], "lesson")
        self.assertIn("digital TV antennas", ap.call_args[0][2])
        job = self.spawn.call_args[0][0]
        self.assertEqual((job["topic"], job["address"], job["title"]), ("how digital TV antennas work", "0xabc", "Antenna article"))
        self.assertIn("being built", r["text"])

    def test_declined_card_builds_nothing(self):
        with self.cfg(explainers="offer"), mock.patch.object(tools, "_approve", side_effect=tools.ToolError("the user declined")):
            with self.assertRaises(tools.ToolError):
                tools.call("explain_in_3d", "0xabc", {"topic": "how antennas work"})
        self.spawn.assert_not_called()

    def test_auto_skips_the_card_unless_ask_all(self):
        _, ap = self.call(explainers="auto")
        ap.assert_not_called()
        _, ap = self.call(explainers="auto", access="ask_all")
        ap.assert_called_once()

    def test_never_refuses(self):
        with self.cfg(explainers="never"):
            with self.assertRaises(tools.ToolError):
                tools.call("explain_in_3d", "0xabc", {"topic": "how antennas work"})
        self.spawn.assert_not_called()

    def test_topic_is_checked(self):
        for topic in ("", "hi", "x" * 200):
            with self.cfg(), mock.patch.object(tools, "_approve"):
                with self.assertRaises(tools.ToolError):
                    tools.call("explain_in_3d", "0xabc", {"topic": topic})

    def test_missing_sandbox_or_a_lesson_already_building_is_explained(self):
        with mock.patch.object(tools.codegen, "available", return_value=False):
            with self.assertRaises(tools.ToolError) as cm:
                self.call(explainers="auto")
        self.assertIn("deno", str(cm.exception))
        with mock.patch.object(tools, "_builder_running", return_value=True):
            with self.assertRaises(tools.ToolError) as cm:
                self.call(explainers="auto")
        self.assertIn("already being built", str(cm.exception))
        self.spawn.assert_not_called()

    def test_look_only_still_allows_lessons(self):
        self.call(access="look")
        self.spawn.assert_called_once()


class Switches(unittest.TestCase):
    def test_never_withholds_the_tool_from_models(self):
        names = ["screenshot", "explain_in_3d"]
        self.assertEqual(access.allowed(names, {"explainers": "never"}), ["screenshot"])
        self.assertEqual(access.allowed(names, {"explainers": "offer"}), names)
        self.assertEqual(access.allowed(names, {}), names)
        self.assertEqual(access.allowed(names, {"explainers": "junk"}), names)

    def test_setting_validates(self):
        self.assertEqual(settings.parse("explainers", "auto"), "auto")
        with self.assertRaises(ValueError):
            settings.parse("explainers", "sometimes")

    def test_prompt_mentions_lessons_and_can_switch_them_off(self):
        self.assertIn("explain_in_3d", prompt.system_for("ask"))
        self.assertIn("switched off", prompt.system_for("ask", lessons=False))


if __name__ == "__main__":
    unittest.main()
