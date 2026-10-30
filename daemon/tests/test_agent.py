import json, os, subprocess, sys, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from goop.agent import claude, events, prompt, registry
from goop.agent.base import AgentRequest


class ParseStream(unittest.TestCase):
    def test_real_sample(self):
        state, out = {}, []
        with open(os.path.join(HERE, "fixtures", "claude_stream.jsonl")) as f:
            for line in f:
                out += claude.parse_line(line, state)
        kinds = [e["type"] for e in out]
        self.assertEqual(kinds[0], "thinking")
        self.assertIn("text", kinds)
        self.assertEqual(kinds[-1], "done")
        self.assertEqual(out[-1]["text"], "Hi there, friend!")
        self.assertTrue(out[-1]["session"])

    def test_tool_use_strips_prefix(self):
        line = json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "mcp__goop__screenshot"}]}})
        self.assertEqual(claude.parse_line(line, {}), [events.tool_use("screenshot")])

    def test_internal_tools_are_not_shown(self):
        line = json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "ToolSearch"}]}})
        self.assertEqual(claude.parse_line(line, {}), [events.thinking()])

    def test_error_result_and_nothing_after_finish(self):
        state = {}
        out = claude.parse_line(json.dumps({"type": "result", "is_error": True, "result": "rate limited"}), state)
        self.assertEqual(out, [events.error("rate limited")])
        self.assertEqual(claude.parse_line(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "x"}]}}), state), [])

    def test_garbage_ignored(self):
        self.assertEqual(claude.parse_line("not json", {}), [])


class Command(unittest.TestCase):
    def setUp(self):
        p = mock.patch("goop.config.load", return_value={})     # not the developer's own config
        p.start()
        self.addCleanup(p.stop)

    def req(self, **kw):
        return AgentRequest(command="c", packet={}, window_address="0x1", system="SYS", prompt="SECRET WINDOW TEXT", **kw)

    def test_read_only_and_prompt_off_argv(self):
        cmd = claude.ClaudeProvider().command(self.req(mcp_config="/m.json", model="haiku"))
        self.assertIn("--strict-mcp-config", cmd)
        for denied in ("Bash", "Edit", "Write"):
            self.assertIn(denied, cmd[cmd.index("--disallowedTools"):])
        self.assertNotIn("Read", cmd[cmd.index("--allowedTools"):cmd.index("--disallowedTools")])
        self.assertNotIn("SECRET WINDOW TEXT", " ".join(cmd))

    def test_project_gets_read_tools_and_resume(self):
        cmd = claude.ClaudeProvider().command(self.req(read_paths=True, session="abc"))
        self.assertIn("Grep", cmd[cmd.index("--allowedTools"):cmd.index("--disallowedTools")])
        self.assertEqual(cmd[cmd.index("--resume") + 1], "abc")


class Prompt(unittest.TestCase):
    def test_untrusted_data_framing(self):
        self.assertIn("DATA", prompt.SYSTEM)
        p = prompt.user_prompt({"app_type": "browser"}, "summarize")
        self.assertTrue(p.rstrip().endswith("USER REQUEST: summarize"))

    def test_big_packet_trimmed(self):
        pkt = {"context": {"listing": {"entries": [{"name": "f%d" % i, "pad": "x" * 200} for i in range(500)]},
                           "terminal_text": "t" * 90000}}
        self.assertLessEqual(len(prompt.trim(pkt)), prompt.PACKET_CAP + 20)


class Registry(unittest.TestCase):
    def test_lookup(self):
        self.assertEqual(registry.get("claude").name, "claude")
        with self.assertRaises(ValueError):
            registry.get("nope")


class McpServer(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.home = tempfile.TemporaryDirectory()         # an empty HOME: the default access level, not the developer's config
        self.addCleanup(self.home.cleanup)

    def rpc(self, *msgs):
        p = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "mcp_server.py")], input="\n".join(map(json.dumps, msgs)) + "\n",
                           capture_output=True, text=True, env={**os.environ, "GOOP_WINDOW": "0xdead", "HOME": self.home.name}, timeout=10)
        return [json.loads(l) for l in p.stdout.splitlines()]

    def test_protocol(self):
        r = self.rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                     {"jsonrpc": "2.0", "method": "notifications/initialized"},
                     {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                     {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "nope"}},
                     {"jsonrpc": "2.0", "id": 4, "method": "bogus"})
        self.assertEqual([m["id"] for m in r], [1, 2, 3, 4])  # the notification got no reply
        self.assertEqual({t["name"] for t in r[1]["result"]["tools"]}, {"screenshot", "window_info", "read_context", "read_file", "list_files", "type_in_terminal", "move_files", "undo_last_move", "explain_in_3d"})
        schemas = {t["name"]: t["inputSchema"] for t in r[1]["result"]["tools"]}
        self.assertEqual(schemas["move_files"]["required"], ["moves"])
        self.assertEqual(schemas["type_in_terminal"]["required"], ["text"])
        self.assertTrue(r[2]["result"]["isError"])
        self.assertEqual(r[3]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
