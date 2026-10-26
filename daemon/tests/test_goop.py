import os, subprocess, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop import classify, config, hypr, project
from goop.adapters import folder, terminal


def win(addr, at, size, floating=False, focus=0, ws=1, mapped=True, hidden=False):
    return {"address": addr, "at": at, "size": size, "floating": floating, "focusHistoryID": focus,
            "workspace": {"id": ws}, "mapped": mapped, "hidden": hidden}


class HitTest(unittest.TestCase):
    def test_floating_beats_tiled(self):
        cs = [win("tiled", [0, 0], [100, 100]), win("float", [10, 10], [20, 20], floating=True, focus=5)]
        self.assertEqual(hypr.window_at(15, 15, cs, {1})["address"], "float")

    def test_focus_breaks_ties(self):
        cs = [win("a", [0, 0], [100, 100], focus=3), win("b", [0, 0], [100, 100], focus=1)]
        self.assertEqual(hypr.window_at(5, 5, cs, {1})["address"], "b")

    def test_ignores_other_workspace_hidden_and_misses(self):
        cs = [win("w2", [0, 0], [100, 100], ws=2), win("h", [0, 0], [100, 100], hidden=True)]
        self.assertIsNone(hypr.window_at(5, 5, cs, {1}))
        self.assertIsNone(hypr.window_at(500, 5, [win("a", [0, 0], [100, 100])], {1}))


class FocusWindow(unittest.TestCase):
    def test_lua_first_then_classic_fallback_and_validation(self):
        import subprocess as sp
        calls = []

        def fake(cmd, **kw):
            calls.append(cmd)
            if len(calls) == 1:       # an older Hyprland rejects the Lua form
                raise sp.CalledProcessError(7, cmd)

        with mock.patch.object(hypr.subprocess, "run", side_effect=fake):
            hypr.focus_window("0xabc123")
        self.assertIn("hl.dsp.focus", calls[0][2])
        self.assertEqual(calls[1], ["hyprctl", "dispatch", "focuswindow", "address:0xabc123"])
        for bad in ('0x1" }) os.execute("x', "abc", "0x", ""):
            with self.assertRaises(ValueError):
                hypr.focus_window(bad)


class Classify(unittest.TestCase):
    def test_classes(self):
        for cls, kind in [("com.mitchellh.ghostty", "terminal"), ("org.gnome.Nautilus", "file_manager"),
                          ("chromium", "browser"), ("chrome-x.com__-Default", "browser"), ("mpv", "other"), (None, "other")]:
            self.assertEqual(classify.app_type(cls), kind, cls)


class Deny(unittest.TestCase):
    def test_deny(self):
        cfg = config.DEFAULTS
        self.assertTrue(config.is_denied({"class": "KeePassXC", "title": "x"}, cfg))
        self.assertTrue(config.is_denied({"class": "chromium", "title": "My Bank - Chromium"}, cfg))
        self.assertFalse(config.is_denied({"class": "chromium", "title": "New Tab"}, cfg))


class Project(unittest.TestCase):
    def test_claude_project_and_home_exclusion(self):
        with tempfile.TemporaryDirectory() as home:
            proj = os.path.join(home, "app")
            os.makedirs(proj)
            open(os.path.join(proj, "CLAUDE.md"), "w").write("# rules")
            info = project.describe(proj, home=home, projects_dir=home)
            self.assertTrue(info["is_claude_project"])
            self.assertEqual(info["claude_md"], "# rules")
            os.makedirs(os.path.join(home, ".claude"))
            self.assertFalse(project.describe(home, home=home, projects_dir=home)["is_project"])

    def test_git_and_session_lookup(self):
        with tempfile.TemporaryDirectory() as home:
            proj = os.path.join(home, "p.x")
            os.makedirs(proj)
            subprocess.run(["git", "-C", proj, "init", "-q"], check=True)
            open(os.path.join(proj, "f.txt"), "w").write("hi")
            self.assertEqual(project.describe(proj, home=home, projects_dir=home)["git"]["status"], ["?? f.txt"])
            sdir = os.path.join(home, project.encode_cwd(proj))
            os.makedirs(sdir)
            open(os.path.join(sdir, "abc.jsonl"), "w").write("{}")
            self.assertEqual(project.latest_session(proj, home)["id"], "abc")

    def test_encode(self):
        self.assertEqual(project.encode_cwd("/home/user"), "-home-user")
        self.assertEqual(project.encode_cwd("/a/b.c"), "-a-b-c")


class TerminalPick(unittest.TestCase):
    def test_title_match_and_ambiguity(self):
        a = {"cwd": "/w/alpha", "start": 1, "program": None}
        b = {"cwd": "/w/beta", "start": 2, "program": None}
        self.assertEqual(terminal.pick([a, b], "editing alpha"), (a, True))
        self.assertEqual(terminal.pick([a, b], "no match"), (b, False))  # newest, but not confident
        self.assertEqual(terminal.pick([a], "x"), (a, True))
        self.assertEqual(terminal.pick([], "x"), (None, False))

    def test_claude_spinner_title_picks_claude_shell_in_same_cwd(self):
        # two ghostty windows, both started in $HOME: one runs claude, one is idle (the real failure we hit)
        home = os.path.expanduser("~")
        claude = {"cwd": home, "start": 1, "program": "claude"}
        idle = {"cwd": home, "start": 2, "program": None}  # newer, so the old tie-break picked this
        self.assertEqual(terminal.pick([claude, idle], "\u25d0 goop-window-context-backend"), (claude, True))
        self.assertEqual(terminal.pick([claude, idle], "~"), (idle, True))


class Folder(unittest.TestCase):
    def test_resolve_and_listing(self):
        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, "Pictures"))
            os.makedirs(os.path.join(home, "Work", "Pictures"))
            open(os.path.join(home, "Pictures", "a.png"), "w").write("x")
            open(os.path.join(home, "Pictures", ".hid"), "w").write("x")
            self.assertEqual(folder.resolve("Home", home)[0], home)
            path, conf, others = folder.resolve("Pictures", home)
            self.assertEqual((path, conf), (os.path.join(home, "Pictures"), "medium"))  # ambiguous name
            self.assertEqual(others, [os.path.join(home, "Work", "Pictures")])
            self.assertEqual(folder.resolve("Nope", home)[1], "low")
            lst = folder.listing(path)
            self.assertEqual((lst["total"], lst["hidden_skipped"]), (1, 1))
            self.assertEqual(lst["extensions"], {".png": 1})


if __name__ == "__main__":
    unittest.main()
