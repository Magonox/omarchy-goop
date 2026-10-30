import http.server, json, os, sys, tempfile, threading, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop import tools
from goop.agent import openai_compat as oc, registry
from goop.agent.base import AgentRequest

KEY = "sk-test-SECRET-123"


class FakeServer:
    """A tiny /chat/completions server that replays scripted responses and records what it was sent."""

    def __init__(self):
        self.script, self.seen = [], []
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.seen.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
                status, payload = outer.script.pop(0) if outer.script else (500, {"error": {"message": "script exhausted"}})
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def reply(content=None, calls=None):
    msg = {"role": "assistant", "content": content}
    if calls:
        msg["tool_calls"] = [{"id": f"call{i}", "type": "function", "function": {"name": n, "arguments": a}} for i, (n, a) in enumerate(calls)]
    return 200, {"choices": [{"message": msg}]}


def request(**kw):
    return AgentRequest(command="hi", packet={}, window_address="0xabc", system="SYS", prompt="PROMPT", **kw)


class Base(unittest.TestCase):
    def setUp(self):
        self.srv = FakeServer()
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [mock.patch.object(oc, "SESSION_DIR", self.tmp.name), mock.patch.dict(os.environ, {"TEST_KEY": KEY}),
                        mock.patch("goop.config.load", return_value={})]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.srv.close()
        self.tmp.cleanup()

    def provider(self, **cfg):
        base = {"base_url": self.srv.url, "model": "test-model", "api_key_env": "TEST_KEY"}
        return oc.OpenAICompatProvider("test", {**base, **cfg})

    def run_events(self, provider, **kw):
        return list(provider.run(request(**kw)))


class Basics(Base):
    def test_plain_answer_and_request_shape(self):
        self.srv.script = [reply("Hello there.")]
        ev = self.run_events(self.provider())
        self.assertEqual([e["type"] for e in ev], ["thinking", "done"])
        self.assertEqual(ev[-1]["text"], "Hello there.")
        seen = self.srv.seen[0]
        self.assertEqual((seen["path"], seen["auth"]), ("/v1/chat/completions", "Bearer " + KEY))
        body = seen["body"]
        self.assertEqual(body["model"], "test-model")
        self.assertEqual([m["role"] for m in body["messages"]], ["system", "user"])
        names = {t["function"]["name"] for t in body["tools"]}
        self.assertTrue({"read_file", "type_in_terminal", "move_files", "screenshot"} <= names)

    def test_local_server_needs_no_key(self):
        self.srv.script = [reply("ok")]
        p = oc.OpenAICompatProvider("local", {"base_url": self.srv.url, "model": "m"})
        self.assertTrue(p.available())
        self.run_events(p)
        self.assertIsNone(self.srv.seen[0]["auth"])

    def test_key_from_file_and_missing_key(self):
        keyfile = os.path.join(self.tmp.name, "key")
        with open(keyfile, "w") as f:
            f.write("  file-key \n")
        p = oc.OpenAICompatProvider("f", {"base_url": self.srv.url, "model": "m", "api_key_file": keyfile})
        self.assertEqual(p.api_key(), "file-key")
        missing = oc.OpenAICompatProvider("x", {"base_url": self.srv.url, "model": "m", "api_key_env": "NOPE_NOT_SET"})
        self.assertFalse(missing.available())
        self.assertIn("NOPE_NOT_SET", missing.problem())
        self.assertEqual(self.run_events(missing)[0]["type"], "error")
        self.assertFalse(oc.OpenAICompatProvider("y", {"base_url": "", "model": ""}).available())


class ToolLoop(Base):
    def test_tool_call_result_goes_back_and_answer_follows(self):
        self.srv.script = [reply(None, [("read_context", "{}")]), reply("It is a folder.")]
        with mock.patch.object(tools, "call", return_value={"text": "CONTEXT"}) as call:
            ev = self.run_events(self.provider())
        self.assertEqual([e["type"] for e in ev], ["thinking", "tool_use", "thinking", "done"])
        self.assertEqual(ev[1]["name"], "read_context")
        call.assert_called_once_with("read_context", "0xabc", {})
        second = self.srv.seen[1]["body"]["messages"]
        self.assertEqual(second[-2]["tool_calls"][0]["function"]["name"], "read_context")
        self.assertEqual(second[-1], {"role": "tool", "tool_call_id": "call0", "content": "CONTEXT"})

    def test_tool_refusal_is_told_to_the_model_and_loop_continues(self):
        self.srv.script = [reply(None, [("read_file", '{"path": ".env"}')]), reply("I can't read that.")]
        with mock.patch.object(tools, "call", side_effect=tools.ToolError("looks like a secret")):
            ev = self.run_events(self.provider())
        self.assertEqual(ev[-1]["type"], "done")
        self.assertIn("Error: looks like a secret", self.srv.seen[1]["body"]["messages"][-1]["content"])

    def test_bad_arguments_json_becomes_empty_args(self):
        self.srv.script = [reply(None, [("window_info", "{not json")]), reply("done")]
        with mock.patch.object(tools, "call", return_value={"text": "x"}) as call:
            self.run_events(self.provider())
        call.assert_called_once_with("window_info", "0xabc", {})

    def test_narration_alongside_tool_call_is_shown(self):
        self.srv.script = [reply("Let me look.", [("window_info", "{}")]), reply("Done.")]
        with mock.patch.object(tools, "call", return_value={"text": "x"}):
            ev = self.run_events(self.provider())
        self.assertIn({"type": "text", "text": "Let me look."}, ev)

    def test_step_limit(self):
        self.srv.script = [reply(None, [("window_info", "{}")]) for _ in range(10)]
        with mock.patch.object(oc, "MAX_STEPS", 3), mock.patch.object(tools, "call", return_value={"text": "x"}):
            ev = self.run_events(self.provider())
        self.assertEqual(ev[-1]["type"], "error")
        self.assertEqual(len(self.srv.seen), 3)


class Vision(Base):
    def shot(self):
        path = os.path.join(self.tmp.name, "s.png")
        with open(path, "wb") as f:
            f.write(b"\x89PNG fake")
        return path

    def test_screenshot_attached_when_model_has_vision(self):
        self.srv.script = [reply(None, [("screenshot", "{}")]), reply("A window.")]
        with mock.patch.object(tools, "call", return_value={"image": self.shot()}):
            self.run_events(self.provider(vision=True))
        last = self.srv.seen[1]["body"]["messages"][-1]
        self.assertEqual(last["role"], "user")
        self.assertTrue(last["content"][1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_text_only_model_is_told_and_gets_no_image(self):
        self.srv.script = [reply(None, [("screenshot", "{}")]), reply("I can't see it.")]
        with mock.patch.object(tools, "call", return_value={"image": self.shot()}):
            self.run_events(self.provider(vision=False))
        msgs = self.srv.seen[1]["body"]["messages"]
        self.assertIn("cannot look at images", msgs[-1]["content"])
        self.assertTrue(all(isinstance(m["content"], (str, type(None))) for m in msgs))


class Sessions(Base):
    def test_follow_up_carries_the_conversation(self):
        self.srv.script = [reply("First answer. Want more?"), reply("More.")]
        first = self.run_events(self.provider())[-1]
        sid = first["session"]
        self.assertRegex(sid, r"^[0-9a-f]{32}$")
        self.run_events(self.provider(), session=sid)
        msgs = self.srv.seen[1]["body"]["messages"]
        self.assertEqual([m["role"] for m in msgs], ["system", "user", "assistant", "user"])
        self.assertEqual(msgs[2]["content"], "First answer. Want more?")

    def test_trim_starts_at_a_user_turn_and_bad_ids_are_ignored(self):
        msgs = [{"role": "tool", "content": "orphan"}, {"role": "assistant", "content": "a"}, {"role": "user", "content": "u"}, {"role": "assistant", "content": "b"}]
        self.assertEqual([m["role"] for m in oc.trim(msgs)], ["user", "assistant"])
        self.assertEqual(oc.load_session("../../etc/passwd"), [])
        self.assertEqual(oc.load_session(None), [])

    def test_history_is_bounded(self):
        sid = None
        for i in range(30):
            sid = oc.save_session(sid, oc.load_session(sid) + [{"role": "user", "content": str(i)}, {"role": "assistant", "content": "x"}])
        self.assertLessEqual(len(oc.load_session(sid)), oc.HISTORY_MESSAGES)


class Errors(Base):
    def test_http_errors_are_readable_and_never_leak_the_key(self):
        for code, needle in ((401, "key was rejected"), (404, "not found"), (429, "rate limited"), (500, "HTTP 500")):
            self.srv.script = [(code, {"error": {"message": "nope"}})]
            ev = self.run_events(self.provider())
            self.assertEqual(ev[-1]["type"], "error")
            self.assertIn(needle, ev[-1]["message"])
            self.assertNotIn(KEY, json.dumps(ev))

    def test_unreachable_server(self):
        self.srv.close()
        ev = self.run_events(self.provider())
        self.assertIn("cannot reach", ev[-1]["message"])

    def test_malformed_response(self):
        self.srv.script = [(200, {"unexpected": True})]
        self.assertIn("not in the expected format", self.run_events(self.provider())[-1]["message"])


class Registry(unittest.TestCase):
    def test_lookup(self):
        cfg = {"provider": "grok", "providers": {"grok": {"base_url": "https://x/v1", "model": "m", "api_key_env": "K"}}}
        with mock.patch.object(registry.config, "load", return_value=cfg):
            self.assertEqual(registry.get().name, "grok")
            self.assertEqual(registry.get("claude").name, "claude")
            self.assertEqual(registry.names(), ["claude", "grok"])
            with self.assertRaises(ValueError):
                registry.get("nope")
        with mock.patch.object(registry.config, "load", return_value={"providers": {"w": {"type": "weird"}}}):
            with self.assertRaises(ValueError):
                registry.get("w")


if __name__ == "__main__":
    unittest.main()
