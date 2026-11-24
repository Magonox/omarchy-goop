"""The in-app lesson builder (explain_run.py) and its router: a model sheet for objects, the outline method for everything else, and a fallback when a sheet cannot be made."""
import json, os, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explain_run
from goop import config, tools
from goop.explainer import planner
from test_sheet import stool


def sheet_reply():
    s = stool()
    del s["layout"]                                   # the builder sets the layout itself
    return json.dumps(s)


class Runner:
    """A fake model: answers the sheet prompt with `sheet`, counts the calls."""
    def __init__(self, sheet):
        self.sheet, self.calls = sheet, 0

    def __call__(self, system, prompt):
        self.calls += 1
        return self.sheet


def run_job(job, runner, deno=True):
    with tempfile.TemporaryDirectory() as d, \
            mock.patch.object(explain_run, "SCENES", d), mock.patch.object(explain_run, "LOG", os.path.join(d, "log")), \
            mock.patch.object(explain_run.planner, "claude_runner", return_value=runner), \
            mock.patch.object(explain_run, "say"), mock.patch.object(explain_run, "tell") as tell, \
            mock.patch.object(explain_run.play, "stop"), mock.patch.object(explain_run.play, "launch_scene") as launch, \
            mock.patch.object(explain_run.play, "save") as save, \
            mock.patch.object(explain_run.codegen, "available", return_value=deno), \
            mock.patch.object(explain_run.planner, "plan_outline", side_effect=planner.PlanError("outline tried")) as outline:
        path = os.path.join(d, "job.json")
        with open(path, "w") as f:
            json.dump(job, f)
        explain_run.main(path)
        scenes = [n for n in os.listdir(d) if n.endswith(".scene.json")]
        return {"tell": tell, "launch": launch, "save": save, "outline": outline, "scenes": scenes}


class Route(unittest.TestCase):
    def test_an_object_is_drawn_as_a_model_sheet_and_opens_complete(self):
        r = run_job({"topic": "how a stool holds you up", "address": "0xabc", "method": "auto"}, Runner(sheet_reply()))
        r["launch"].assert_called_once()
        self.assertEqual(r["launch"].call_args.args[1], "0xabc")
        self.assertEqual(len(r["scenes"]), 1)
        saved = r["save"].call_args.args[0]
        self.assertTrue(all(p["kind"] == "solid" for p in saved["parts"]))
        r["outline"].assert_not_called()
        r["tell"].assert_not_called()

    def test_something_that_is_not_an_object_goes_to_the_outline_method(self):
        runner = Runner(json.dumps({"route": "diagram", "why": "wifi is signals, not an object"}))
        r = run_job({"topic": "how wifi works", "address": "0xabc", "method": "auto"}, runner)
        self.assertEqual(runner.calls, 1)                                   # one small answer, no repairs
        r["outline"].assert_called_once()
        r["launch"].assert_not_called()

    def test_a_sheet_that_cannot_be_made_falls_back_to_the_outline_method(self):
        runner = Runner("this is not JSON at all")
        r = run_job({"topic": "how a toaster works", "address": "0xabc", "method": "auto"}, runner)
        self.assertEqual(runner.calls, planner.REPAIRS + 1)
        r["outline"].assert_called_once()

    def test_without_deno_a_topic_for_the_outline_method_is_explained_not_attempted(self):
        runner = Runner(json.dumps({"route": "diagram", "why": "wifi is signals"}))
        r = run_job({"topic": "how wifi works", "address": "0xabc", "method": "auto"}, runner, deno=False)
        r["outline"].assert_not_called()
        r["tell"].assert_called_once()
        self.assertIn("deno", r["tell"].call_args.args[1])

    def test_the_outline_method_never_draws_a_sheet(self):
        with mock.patch.object(explain_run.planner, "plan_sheet", side_effect=AssertionError("no sheet in outline mode")):
            for job in ({"topic": "how a toaster works", "address": "0xabc", "method": "outline"}, {"topic": "how a toaster works", "address": "0xabc"}):
                r = run_job(job, Runner(sheet_reply()))
                r["outline"].assert_called_once()

    def test_the_router_answer_is_recognised(self):
        with self.assertRaises(planner.NotAnObject):
            planner.plan_sheet("how digestion works", "", Runner(json.dumps({"route": "diagram", "why": "a process"})))

    def test_the_sheet_prompt_tells_the_model_when_not_to_draw(self):
        self.assertIn("WHEN NOT TO DRAW", planner.sheet_system())
        self.assertIn('"route":"diagram"', planner.sheet_system())


class Tool(unittest.TestCase):
    def spawned(self, cfg, deno=True):
        jobs = []
        with mock.patch.object(tools, "_window", return_value=({"title": "Page"}, None)), mock.patch.object(tools.access, "explainers", return_value="auto"), \
                mock.patch.object(tools.access, "level", return_value="ask"), mock.patch.object(config, "load", return_value=cfg), \
                mock.patch.object(tools.codegen, "available", return_value=deno), mock.patch.object(tools.shutil, "which", return_value="/usr/bin/claude"), \
                mock.patch.object(tools, "_builder_running", return_value=False), mock.patch.object(tools, "_spawn_builder", side_effect=jobs.append):
            tools.explain_in_3d("0xabc", {"topic": "how a watch works"})
        return jobs[0]

    def test_the_job_carries_the_method_from_the_settings(self):
        self.assertEqual(self.spawned({"explain_method": "auto"})["method"], "auto")
        self.assertEqual(self.spawned({"explain_method": "outline"})["method"], "outline")
        self.assertEqual(self.spawned({})["method"], "auto")                    # the default
        self.assertEqual(self.spawned({"explain_method": "weird"})["method"], "auto")

    def test_a_model_sheet_needs_no_deno(self):
        self.assertEqual(self.spawned({"explain_method": "auto"}, deno=False)["method"], "auto")
        with self.assertRaises(tools.ToolError):
            self.spawned({"explain_method": "outline"}, deno=False)


if __name__ == "__main__":
    unittest.main()
