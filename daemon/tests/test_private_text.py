"""Private text must not leak through the process list (speech), the reply bubble (images) or native file tools (access setting)."""
import os, re, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agent
from goop import say

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as f:
        return f.read()


class NativeReads(unittest.TestCase):
    def test_follows_the_access_setting(self):
        cwd = "/home/x/project"
        for cfg, want in [({}, True), ({"access": "look"}, True), ({"access": "ask_all"}, False),
                          ({"read_files": "off"}, False), ({"read_files": "ask"}, False), ({"read_files": "folder", "access": "ask_all"}, True)]:
            with self.subTest(cfg=cfg):
                self.assertEqual(agent.native_reads_allowed(cwd, cfg), want)

    def test_never_outside_a_project(self):
        self.assertFalse(agent.native_reads_allowed(None, {}))

    def test_agent_uses_it(self):
        self.assertIn("read_paths=native_reads", read("daemon", "agent.py"))
        self.assertNotIn("read_paths=bool(project_cwd)", read("daemon", "agent.py"))


class Speak(unittest.TestCase):
    def test_text_goes_through_a_private_file_not_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            seen = {}

            def fake_run(cmd, **kw):
                seen["cmd"] = cmd
                seen["mode"] = os.stat(cmd[-1]).st_mode & 0o777
                seen["text"] = open(cmd[-1]).read()

            with mock.patch.object(say, "RUN", tmp), mock.patch.object(say.subprocess, "run", side_effect=fake_run):
                self.assertTrue(say.speak("0xabc", "my private topic"))
        self.assertEqual(seen["text"], "my private topic")
        self.assertEqual(seen["mode"], 0o600)
        self.assertEqual(seen["cmd"][1:3], ["speakfile", "0xabc"])
        self.assertNotIn("my private topic", " ".join(seen["cmd"]))

    def test_old_unread_files_are_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            old, new = os.path.join(tmp, "say-old.txt"), os.path.join(tmp, "say-new.txt")
            for p in (old, new):
                open(p, "w").close()
            os.utime(old, (1, 1))
            with mock.patch.object(say, "RUN", tmp):
                say._prune()
            self.assertFalse(os.path.exists(old))
            self.assertTrue(os.path.exists(new))

    def test_nothing_passes_text_to_goopctl_speak_or_notify_send(self):
        for f in ("explain_run.py", "narrate.py"):
            src = read("daemon", f)
            self.assertNotRegex(src, r'\[CTL,\s*"speak"', f)
        self.assertNotRegex(read("daemon", "explain_run.py"), r'"notify-send"[^\n]*\btext\b')


class Bubble(unittest.TestCase):
    def test_images_never_reach_the_markdown_text(self):
        qml = read("shell", "Goop.qml")
        self.assertIn("function noImages", qml)
        for m in re.finditer(r"textFormat:\s*Text\.MarkdownText", qml):
            line_start = qml.rfind("\n", 0, m.start())
            block = qml[max(0, qml.rfind("Text {", 0, m.start())):m.end()]
            self.assertIn("noImages(gp.bubble)", block)


if __name__ == "__main__":
    unittest.main()
