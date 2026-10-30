import json, os, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop import access, tools
from goop.agent import claude, openai_compat, prompt
from goop.agent.base import AgentRequest

ACTING = {"type_in_terminal", "move_files", "undo_last_move"}


def cfg(**kw):
    return mock.patch.object(access.config, "load", return_value=kw)


class Policy(unittest.TestCase):
    def test_levels_table(self):
        self.assertEqual(access.policy({"access": "look"}), {"level": "look", "act": False, "auto_safe": False, "read": "folder", "screenshot": "auto"})
        self.assertEqual(access.policy({"access": "ask"}), {"level": "ask", "act": True, "auto_safe": True, "read": "folder", "screenshot": "auto"})
        self.assertEqual(access.policy({"access": "ask_all"}), {"level": "ask_all", "act": True, "auto_safe": False, "read": "ask", "screenshot": "ask"})

    def test_default_is_ask_first_and_junk_falls_back(self):
        for value in (None, "", "everything", 5, ["look"]):
            self.assertEqual(access.level({"access": value}), "ask")
        self.assertEqual(access.level({}), "ask")

    def test_explicit_overrides_still_work(self):
        self.assertEqual(access.policy({"access": "ask", "read_files": "off"})["read"], "off")
        self.assertFalse(access.policy({"access": "ask", "auto_approve_safe": False})["auto_safe"])
        self.assertEqual(access.policy({"access": "ask_all", "read_files": "folder"})["read"], "folder")
        self.assertFalse(access.policy({"access": "look", "auto_approve_safe": True})["auto_safe"])   # an override cannot grant acting
        self.assertEqual(access.policy({"read_files": "bogus"})["read"], "folder")                    # invalid override ignored

    def test_allowed_tools(self):
        names = ["screenshot", "read_file", "type_in_terminal", "move_files", "undo_last_move", "list_files"]
        self.assertEqual(access.allowed(names, {"access": "look"}), ["screenshot", "read_file", "list_files"])
        self.assertEqual(access.allowed(names, {"access": "ask"}), names)
        self.assertEqual(access.allowed(names, {"access": "ask_all"}), names)

    def test_labels_cover_every_level(self):
        for lv in access.LEVELS:
            self.assertTrue(access.LABELS[lv] and access.DESCRIPTIONS[lv])


class Enforcement(unittest.TestCase):
    def fake_tools(self):
        calls = []
        fake = {n: ((lambda a, args, n=n: calls.append(n) or {"text": "ok"}), "d", {}) for n in list(tools.TOOLS)}
        return calls, mock.patch.dict(tools.TOOLS, fake)

    def test_look_only_refuses_acting_tools_but_not_reading_ones(self):
        calls, patched = self.fake_tools()
        with patched, cfg(access="look"), mock.patch.object(tools, "_audit"):
            for name in ACTING:
                with self.assertRaises(tools.ToolError) as cm:
                    tools.call(name, "0x1", {})
                self.assertIn("Look only", str(cm.exception))
            self.assertEqual(calls, [])                                       # nothing ran
            for name in ("read_file", "list_files", "window_info", "read_context"):
                self.assertEqual(tools.call(name, "0x1", {}), {"text": "ok"})
            self.assertEqual(calls, ["read_file", "list_files", "window_info", "read_context"])

    def test_ask_levels_allow_acting_tools(self):
        for level in ("ask", "ask_all"):
            calls, patched = self.fake_tools()
            with patched, cfg(access=level), mock.patch.object(tools, "_audit"):
                tools.call("move_files", "0x1", {})
            self.assertEqual(calls, ["move_files"], level)

    def test_screenshot_card_only_at_ask_for_everything(self):
        win = {"address": "0x1", "title": "Docs", "class": "x", "at": [0, 0], "size": [5, 5], "pid": 1}
        for level, asks in (("look", False), ("ask", False), ("ask_all", True)):
            with cfg(access=level), mock.patch.object(tools, "_visible_window", return_value=win), \
                 mock.patch.object(tools.screenshot, "capture", return_value="/tmp/x.png"), \
                 mock.patch.object(tools.approvals, "request", return_value=True) as ask:
                self.assertEqual(tools.take_screenshot("0x1"), {"image": "/tmp/x.png"})
                self.assertEqual(ask.called, asks, level)
        with cfg(access="ask_all"), mock.patch.object(tools, "_visible_window", return_value=win), \
             mock.patch.object(tools.screenshot, "capture") as cap, mock.patch.object(tools.approvals, "request", return_value=False):
            with self.assertRaises(tools.ToolError):
                tools.take_screenshot("0x1")
            cap.assert_not_called()                                           # declined: no capture happened

    def test_safe_commands_run_without_a_card_only_at_ask_first(self):
        win = {"address": "0x1", "class": "com.mitchellh.ghostty", "title": "~", "pid": 1, "workspace": {"id": 1}}
        for level, asks in (("ask", False), ("ask_all", True)):
            with cfg(access=level), mock.patch.object(tools, "_visible_window", return_value=win), \
                 mock.patch.object(tools.proc, "snapshot", return_value={}), mock.patch.object(tools, "_audit"), \
                 mock.patch.object(tools.terminal_adapter, "collect", return_value=({"program": None, "project": {"cwd": "/home/u"}}, "high")), \
                 mock.patch.object(tools.hypr, "focus_window"), mock.patch.object(tools.hypr, "hypr", return_value={"address": "0x1"}), \
                 mock.patch.object(tools.approvals, "request", return_value=True) as ask, mock.patch.object(tools.subprocess, "run"):
                tools.type_in_terminal("0x1", {"text": "ls"})
                self.assertEqual(ask.called, asks, level)

    def test_file_reads_ask_only_at_ask_for_everything(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "a.txt"), "w") as f:
                f.write("hi")
            for level, asks in (("look", False), ("ask", False), ("ask_all", True)):
                with cfg(access=level), mock.patch.object(tools, "_scope", return_value=d), \
                     mock.patch.object(tools.approvals, "request", return_value=True) as ask:
                    self.assertIn("hi", tools.read_file("0x1", {"path": "a.txt"})["text"])
                    self.assertEqual(ask.called, asks, level)


class WhatModelsAreOffered(unittest.TestCase):
    def test_openai_compat_tool_list(self):
        with cfg(access="look"):
            names = {t["function"]["name"] for t in openai_compat.tool_definitions()}
        self.assertFalse(names & ACTING)
        self.assertTrue({"read_file", "screenshot", "list_files"} <= names)
        with cfg(access="ask"):
            self.assertTrue(ACTING <= {t["function"]["name"] for t in openai_compat.tool_definitions()})

    def test_claude_command_withholds_and_denies_acting_tools(self):
        req = AgentRequest(command="c", packet={}, window_address="0x1", system="S", prompt="P")
        with cfg(access="look"):
            cmd = claude.ClaudeProvider().command(req)
        allowed = cmd[cmd.index("--allowedTools"):cmd.index("--disallowedTools")]
        denied = cmd[cmd.index("--disallowedTools"):]
        for name in ACTING:
            self.assertNotIn("mcp__goop__" + name, allowed)
            self.assertIn("mcp__goop__" + name, denied)
        self.assertIn("mcp__goop__read_file", allowed)
        with cfg(access="ask"):
            cmd = claude.ClaudeProvider().command(req)
        self.assertIn("mcp__goop__move_files", cmd[cmd.index("--allowedTools"):cmd.index("--disallowedTools")])

    def test_prompt_states_the_limits(self):
        self.assertIn("LOOK ONLY", prompt.system_for("look"))
        self.assertIn("approval card", prompt.system_for("ask_all"))
        self.assertEqual(prompt.system_for("ask"), prompt.SYSTEM)
        self.assertEqual(prompt.system_for("nonsense"), prompt.SYSTEM)

    def test_mcp_server_lists_only_offered_tools(self):
        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, ".config", "goop"))
            with open(os.path.join(home, ".config", "goop", "config.json"), "w") as f:
                json.dump({"access": "look"}, f)
            import subprocess
            p = subprocess.run([sys.executable, "-I", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_server.py")],
                               input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n", capture_output=True, text=True,
                               env={**os.environ, "HOME": home, "GOOP_WINDOW": "0x0"}, timeout=10)
        names = {t["name"] for t in json.loads(p.stdout)["result"]["tools"]}
        self.assertFalse(names & ACTING)
        self.assertIn("read_file", names)


if __name__ == "__main__":
    unittest.main()
