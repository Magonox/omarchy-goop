import json, os, sys, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop import access, settings, tools
from goop.agent import prompt
from goop.explainer import codegen, planner

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
needs_deno = unittest.skipUnless(codegen.available(), "deno is not installed")


def lesson(name="blu_ray_code"):
    """A lesson whose every part is model-written code (a real planner answer, kept as a fixture)."""
    with open(os.path.join(FIXTURES, name + ".json")) as f:
        return json.load(f)


def runner(*replies):
    seen = []

    def run(system, prompt_):
        seen.append(prompt_)
        return replies[min(len(seen), len(replies)) - 1]
    run.seen = seen
    return run


class Extract(unittest.TestCase):
    def test_plain_fenced_and_chatty(self):
        for text in ('{"a": 1}', '```json\n{"a": 1}\n```', 'Sure! Here you go:\n{"a": 1}\nHope that helps.'):
            self.assertEqual(planner.extract_json(text), {"a": 1})

    def test_no_json_is_an_error(self):
        with self.assertRaises(ValueError):
            planner.extract_json("I cannot do that")


@needs_deno
class Plan(unittest.TestCase):
    def test_valid_first_try(self):
        run = runner(json.dumps(lesson()))
        story, scene = planner.plan("how antennas work", "notes", run, title="Antenna article")
        self.assertEqual(story["title"], scene["title"])
        self.assertEqual(len(run.seen), 1)
        self.assertIn("how antennas work", run.seen[0])
        self.assertIn("Antenna article", run.seen[0])

    def test_errors_are_sent_back_and_repaired(self):
        bad = lesson()
        bad["parts"][0]["code"] = "function build(M) { return M.nothing.here(); }"
        run = runner(json.dumps(bad), json.dumps(lesson()))
        story, scene = planner.plan("antennas", "", run)
        self.assertEqual(len(run.seen), 2)
        self.assertIn("your code threw an error", run.seen[1])     # the sandbox's message reaches the model
        self.assertTrue(scene["duration"] > 0)

    def test_bad_json_is_repaired_too(self):
        run = runner("sorry, no", json.dumps(lesson()))
        planner.plan("antennas", "", run)
        self.assertIn("no JSON object", run.seen[1])

    def test_gives_up_after_the_repairs(self):
        run = runner("nope")
        with self.assertRaises(planner.PlanError):
            planner.plan("antennas", "", run)
        self.assertEqual(len(run.seen), planner.REPAIRS + 1)

    def test_a_ready_made_part_is_refused(self):
        bad = lesson()
        bad["parts"][0] = {"id": "p1", "kind": "cylinder", "label": "Plain"}
        run = runner(json.dumps(bad), json.dumps(lesson()))
        planner.plan("antennas", "", run)
        self.assertIn("every part must be kind", run.seen[1])

    def test_system_prompt_teaches_code_parts_only(self):
        sp = planner.system_prompt()
        for word in ("assembly", "network", "axis", "flow", "recap", "M.lathe", "M.extrude", "sender"):
            self.assertIn(word, sp)
        self.assertNotIn("READY-MADE", sp)
        self.assertNotIn("custom", sp)


@needs_deno
class Tool(unittest.TestCase):
    def setUp(self):
        self.window = mock.patch.object(tools, "_window", return_value=({"title": "Antenna article", "class": "chromium"}, set()))
        self.play = mock.patch.object(tools, "play")
        self.runner = mock.patch.object(tools, "_lesson_runner", return_value=runner(json.dumps(lesson())))
        self.audit = mock.patch.object(tools, "_audit")
        self.window.start(); self.audit.start(); self.runner.start()
        self.play_mock = self.play.start()
        self.play_mock.save.return_value = "/tmp/x.json"
        self.addCleanup(mock.patch.stopall)

    def cfg(self, **kw):
        return mock.patch.object(access.config, "load", return_value=kw)

    def call(self, args=None, **cfg):
        with self.cfg(**cfg), mock.patch.object(tools, "_approve") as ap:
            r = tools.call("explain_in_3d", "0xabc", {"topic": "how digital TV antennas work", "notes": "a tower sends waves"} if args is None else args)
        return r, ap

    def test_offer_mode_asks_first_then_plays(self):
        r, ap = self.call()
        ap.assert_called_once()
        self.assertEqual(ap.call_args[0][1], "lesson")
        self.assertIn("digital TV antennas", ap.call_args[0][2])
        self.play_mock.launch.assert_called_once_with("/tmp/x.json", "0xabc")
        self.assertIn("narrated lesson", r["text"])

    def test_declined_card_builds_nothing(self):
        with self.cfg(explainers="offer"), mock.patch.object(tools, "_approve", side_effect=tools.ToolError("the user declined")):
            with self.assertRaises(tools.ToolError):
                tools.call("explain_in_3d", "0xabc", {"topic": "how antennas work"})
        self.play_mock.launch.assert_not_called()

    def test_auto_skips_the_card_unless_ask_all(self):
        _, ap = self.call(explainers="auto")
        ap.assert_not_called()
        _, ap = self.call(explainers="auto", access="ask_all")
        ap.assert_called_once()

    def test_never_refuses(self):
        with self.cfg(explainers="never"):
            with self.assertRaises(tools.ToolError):
                tools.call("explain_in_3d", "0xabc", {"topic": "how antennas work"})
        self.play_mock.launch.assert_not_called()

    def test_topic_is_checked(self):
        for topic in ("", "hi", "x" * 200):
            with self.cfg(), mock.patch.object(tools, "_approve"):
                with self.assertRaises(tools.ToolError):
                    tools.call("explain_in_3d", "0xabc", {"topic": topic})

    def test_planner_failure_reaches_the_agent(self):
        with self.cfg(explainers="auto"), mock.patch.object(tools, "_lesson_runner", return_value=runner("nope")):
            with self.assertRaises(tools.ToolError) as cm:
                tools.call("explain_in_3d", "0xabc", {"topic": "how antennas work"})
        self.assertIn("could not be built", str(cm.exception))
        self.play_mock.launch.assert_not_called()

    def test_look_only_still_allows_lessons(self):
        _, ap = self.call(access="look")
        self.play_mock.launch.assert_called_once()


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
