import os, sys, tempfile, threading, time, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop import actions, approvals, tools


def touch(path, text="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


class CleanLine(unittest.TestCase):
    def test_accepts_one_line(self):
        self.assertEqual(actions.clean_line("cd Downloads"), "cd Downloads")
        self.assertEqual(actions.clean_line("ls\t-la"), "ls\t-la")

    def test_rejects_multiline_control_empty_long(self):
        for bad in ("a\nb", "a\rb", "a\x1bb", "a\x03", "   ", "", None, 5, "x" * 401):
            with self.assertRaises(actions.ActionError, msg=repr(bad)):
                actions.clean_line(bad)


class SafeCommands(unittest.TestCase):
    def test_allowed(self):
        for ok in ("ls", "ls -la", "ls ~/Downloads", "ls -lh /home/user/Downloads", "cd ~/Downloads", "cd", "pwd",
                   "git status", "git log --oneline -5", "du -sh ~/Downloads", "df -h", "whoami"):
            self.assertTrue(actions.is_safe_command(ok), ok)

    def test_refused(self):
        for bad in ("rm -rf x", "ls; rm -rf x", "ls && id", "ls | sh", "ls > f", "ls $(id)", "ls `id`", "ls 'a b'", 'ls "x"',
                    "ls *", "ls ~/D?wn", "ls  -la", "ls\t-la", "cat ~/.ssh/id_rsa", "git push", "git branch -D x", "git log --output=f",
                    "git diff", "git", "cd ~ && ls", "echo hi", "sudo ls", "LS", "ls -", "ls --", "ls a=b", "tree -o f", ""):
            self.assertFalse(actions.is_safe_command(bad), repr(bad))


class PlanMoves(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        touch(os.path.join(self.root, "a.png"))
        touch(os.path.join(self.root, "b.txt"))
        touch(os.path.join(self.root, "sub", "c.txt"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_plan_creates_dirs(self):
        plan, dirs = actions.plan_moves(self.root, [{"from": "a.png", "to": "Images/2026/a.png"}])
        self.assertEqual(plan, [(f"{self.root}/a.png", f"{self.root}/Images/2026/a.png")])
        self.assertEqual(dirs, [f"{self.root}/Images", f"{self.root}/Images/2026"])

    def test_rejects_escapes_overwrite_missing_and_bad_shapes(self):
        bad = [
            [{"from": "a.png", "to": "../out.png"}],           # leaves the folder
            [{"from": "../x", "to": "x"}],                      # source outside
            [{"from": "a.png", "to": "/etc/a.png"}],            # absolute destination outside
            [{"from": "a.png", "to": "b.txt"}],                 # would overwrite
            [{"from": "nope", "to": "x"}],                      # missing source
            [{"from": "a.png", "to": "z"}, {"from": "b.txt", "to": "z"}],  # two onto one destination
            [{"from": "sub", "to": "sub/inner/sub"}],           # folder into itself
            [{"from": ".", "to": "x"}],                         # the folder itself
            [], None, "a.png", [{"from": "a.png"}],
        ]
        for moves in bad:
            with self.assertRaises(actions.ActionError, msg=str(moves)):
                actions.plan_moves(self.root, moves)

    def test_symlink_that_leaves_the_folder_is_refused(self):
        with tempfile.TemporaryDirectory() as outside:
            os.symlink(outside, os.path.join(self.root, "escape"))
            with self.assertRaises(actions.ActionError):
                actions.plan_moves(self.root, [{"from": "a.png", "to": "escape/a.png"}])

    def test_too_many(self):
        moves = [{"from": "a.png", "to": f"d/{i}.png"} for i in range(actions.MAX_MOVES + 1)]
        with self.assertRaises(actions.ActionError):
            actions.plan_moves(self.root, moves)

    def test_apply_and_undo_round_trip(self):
        with tempfile.TemporaryDirectory() as undo_dir, mock.patch.object(actions, "UNDO_DIR", undo_dir):
            plan, dirs = actions.plan_moves(self.root, [{"from": "a.png", "to": "Images/a.png"}, {"from": "b.txt", "to": "Docs/b.txt"}])
            self.assertEqual(actions.apply_moves(plan, dirs, self.root), 2)
            self.assertTrue(os.path.exists(f"{self.root}/Images/a.png"))
            self.assertFalse(os.path.exists(f"{self.root}/a.png"))
            path, log = actions.last_undo(self.root)
            self.assertEqual(actions.undo(path, log), 2)
            self.assertTrue(os.path.exists(f"{self.root}/a.png") and os.path.exists(f"{self.root}/b.txt"))
            self.assertFalse(os.path.exists(f"{self.root}/Images"))   # folders we created are cleaned up
            self.assertIsNone(actions.last_undo(self.root)[0])        # and the log is spent

    def test_undo_never_overwrites(self):
        with tempfile.TemporaryDirectory() as undo_dir, mock.patch.object(actions, "UNDO_DIR", undo_dir):
            plan, dirs = actions.plan_moves(self.root, [{"from": "a.png", "to": "Images/a.png"}])
            actions.apply_moves(plan, dirs, self.root)
            touch(f"{self.root}/a.png", "new file the user made since")
            path, log = actions.last_undo(self.root)
            self.assertEqual(actions.undo(path, log), 0)
            self.assertEqual(open(f"{self.root}/a.png").read(), "new file the user made since")


class Approvals(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(approvals, "DIR", self.tmp.name)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def ask_in_thread(self, **kw):
        out = {}
        t = threading.Thread(target=lambda: out.update(r=approvals.request("0x1", "type", "s", "d", poll=0.02, **kw)))
        t.start()
        for _ in range(100):
            if approvals.pending():
                break
            time.sleep(0.02)
        return t, out

    def test_yes_no_and_timeout(self):
        for reply, expected in (("yes", True), ("no", False)):
            t, out = self.ask_in_thread(ttl=5)
            req = approvals.pending()[0]
            self.assertEqual((req["address"], req["summary"], req["detail"]), ("0x1", "s", "d"))
            approvals.answer(req["id"], reply == "yes")
            t.join(2)
            self.assertIs(out["r"], expected)
            self.assertEqual(os.listdir(self.tmp.name), [])        # cleaned up
        t, out = self.ask_in_thread(ttl=0.3)
        t.join(3)
        self.assertIs(out["r"], False)                              # silence is "no"
        self.assertEqual(approvals.pending(), [])

    def test_bad_id_rejected(self):
        for bad in ("../../etc/passwd", "xyz", "0123456789abcde", ""):
            with self.assertRaises(ValueError):
                approvals.answer(bad, True)


class TypeInTerminal(unittest.TestCase):
    """Refusals happen BEFORE the user is ever asked, and nothing is typed."""
    WIN = {"address": "0x1", "class": "com.mitchellh.ghostty", "title": "~", "pid": 1, "mapped": True, "hidden": False,
           "workspace": {"id": 1}, "at": [0, 0], "size": [10, 10], "floating": False, "focusHistoryID": 0}

    def run_tool(self, collect_result, args):
        with mock.patch.object(tools, "_visible_window", return_value=self.WIN), \
             mock.patch.object(tools.proc, "snapshot", return_value={}), \
             mock.patch.object(tools.terminal_adapter, "collect", return_value=collect_result), \
             mock.patch.object(tools.approvals, "request", return_value=True) as ask, \
             mock.patch.object(tools.subprocess, "run") as run:
            try:
                tools.type_in_terminal("0x1", args)
                err = None
            except tools.ToolError as e:
                err = str(e)
            return err, ask.called, run.called

    def test_refuses_when_a_program_owns_the_terminal(self):
        err, asked, typed = self.run_tool(({"program": "claude", "project": {"cwd": "/"}}, "high"), {"text": "ls"})
        self.assertIn("claude", err)
        self.assertEqual((asked, typed), (False, False))

    def test_refuses_ambiguous_shell(self):
        err, asked, typed = self.run_tool(({"program": None, "project": {"cwd": "/"}}, "medium"), {"text": "ls"})
        self.assertIn("cannot tell which shell", err)
        self.assertEqual((asked, typed), (False, False))

    def test_refuses_multiline(self):
        err, asked, typed = self.run_tool(({"program": None, "project": {"cwd": "/"}}, "high"), {"text": "ls\nrm -rf x"})
        self.assertIn("single line", err)
        self.assertEqual((asked, typed), (False, False))

    def run_ok(self, text, auto=True):
        with mock.patch.object(tools, "_visible_window", return_value=self.WIN), \
             mock.patch.object(tools.proc, "snapshot", return_value={}), \
             mock.patch.object(tools.terminal_adapter, "collect", return_value=({"program": None, "project": {"cwd": "/home/x"}}, "high")), \
             mock.patch.object(tools.config, "load", return_value={"auto_approve_safe": auto}), \
             mock.patch.object(tools.hypr, "focus_window"), \
             mock.patch.object(tools.hypr, "hypr", return_value={"address": "0x1"}), \
             mock.patch.object(tools, "_audit"), \
             mock.patch.object(tools.approvals, "request", return_value=True) as ask, \
             mock.patch.object(tools.subprocess, "run") as run:
            tools.type_in_terminal("0x1", {"text": text})
            return ask.called, [c.args[0] for c in run.call_args_list]

    def test_safe_command_skips_card_and_clears_line_first(self):
        asked, calls = self.run_ok("ls ~/Downloads")
        self.assertFalse(asked)
        self.assertEqual(calls[0], ["wtype", "-M", "ctrl", "u", "-m", "ctrl"])   # clear the prompt line BEFORE typing
        self.assertEqual(calls[1], ["wtype", "--", "ls ~/Downloads"])
        self.assertEqual(calls[2], ["wtype", "-k", "Return"])

    def test_unsafe_command_still_asks_and_switch_disables_auto(self):
        self.assertTrue(self.run_ok("rm -r old")[0])
        self.assertTrue(self.run_ok("ls", auto=False)[0])

    def test_declined_types_nothing(self):
        with mock.patch.object(tools, "_visible_window", return_value=self.WIN), \
             mock.patch.object(tools.proc, "snapshot", return_value={}), \
             mock.patch.object(tools.terminal_adapter, "collect", return_value=({"program": None, "project": {"cwd": "/home/x"}}, "high")), \
             mock.patch.object(tools.approvals, "request", return_value=False), \
             mock.patch.object(tools.subprocess, "run") as run:
            with self.assertRaises(tools.ToolError) as cm:
                tools.type_in_terminal("0x1", {"text": "rm -r Downloads/old"})   # not on the safe list, so it asks
            self.assertIn("declined", str(cm.exception))
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class ReadRules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        touch(os.path.join(self.root, "notes.txt"), "hello world")
        touch(os.path.join(self.root, "sub", "deep.md"), "# deep")
        touch(os.path.join(self.root, ".env"), "KEY=1")
        touch(os.path.join(self.root, "id_rsa"), "x")
        touch(os.path.join(self.root, "my-api-token.txt"), "x")
        touch(os.path.join(self.root, ".ssh", "config"), "x")
        with open(os.path.join(self.root, "bin.dat"), "wb") as f:
            f.write(b"\x00\x01\x02" * 100)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reads_inside_and_relative_paths(self):
        self.assertEqual(actions.resolve_readable(self.root, "notes.txt"), f"{self.root}/notes.txt")
        self.assertEqual(actions.resolve_readable(self.root, "sub/deep.md"), f"{self.root}/sub/deep.md")
        self.assertEqual(actions.resolve_readable(self.root, f"{self.root}/notes.txt"), f"{self.root}/notes.txt")

    def test_refuses_outside_secrets_missing_and_non_files(self):
        for bad in ("../x", "/etc/passwd", "~/.bashrc", ".env", "id_rsa", "my-api-token.txt", ".ssh/config", "nope.txt", "sub", "", None, 5):
            with self.assertRaises(actions.ActionError, msg=repr(bad)):
                actions.resolve_readable(self.root, bad)

    def test_symlink_out_of_the_folder_is_refused(self):
        with tempfile.TemporaryDirectory() as outside:
            touch(os.path.join(outside, "private.txt"), "secret")
            os.symlink(os.path.join(outside, "private.txt"), os.path.join(self.root, "innocent.txt"))
            with self.assertRaises(actions.ActionError):
                actions.resolve_readable(self.root, "innocent.txt")

    def test_read_text_truncates_and_refuses_binary(self):
        text, size, cut = actions.read_text(f"{self.root}/notes.txt", 5)
        self.assertEqual((text, size, cut), ("hello", 11, True))
        with self.assertRaises(actions.ActionError):
            actions.read_text(f"{self.root}/bin.dat", 100)

    def test_list_dir_hides_hidden_and_secret_and_stays_inside(self):
        names = [e["name"] for e in actions.list_dir(self.root)[0]]
        self.assertEqual(sorted(names), ["bin.dat", "notes.txt", "sub"])
        self.assertEqual([e["name"] for e in actions.list_dir(self.root, "sub")[0]], ["deep.md"])
        for bad in ("..", "/etc", "notes.txt"):
            with self.assertRaises(actions.ActionError):
                actions.list_dir(self.root, bad)


class ReadFileTool(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        touch(os.path.join(self.root, "a.txt"), "alpha beta")

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, args, mode="folder", scope=None):
        with mock.patch.object(tools, "_scope", return_value=scope or self.root), \
             mock.patch.object(tools.config, "load", return_value={"read_files": mode}), \
             mock.patch.object(tools.approvals, "request", return_value=True) as ask:
            return tools.read_file("0x1", args), ask.called

    def test_reads_text_without_asking_in_folder_mode(self):
        out, asked = self.run_tool({"path": "a.txt"})
        self.assertIn("alpha beta", out["text"])
        self.assertIn("untrusted", out["text"])         # content is framed as data, not instructions
        self.assertFalse(asked)

    def test_ask_mode_shows_a_card_and_off_refuses(self):
        self.assertTrue(self.run_tool({"path": "a.txt"}, mode="ask")[1])
        with self.assertRaises(tools.ToolError):
            self.run_tool({"path": "a.txt"}, mode="off")

    def test_declined_card_reads_nothing(self):
        with mock.patch.object(tools, "_scope", return_value=self.root), \
             mock.patch.object(tools.config, "load", return_value={"read_files": "ask"}), \
             mock.patch.object(tools.approvals, "request", return_value=False):
            with self.assertRaises(tools.ToolError):
                tools.read_file("0x1", {"path": "a.txt"})

    def test_refusals_come_back_as_tool_errors(self):
        for bad in ({"path": "../x"}, {"path": ".env"}, {"path": "missing.txt"}):
            with self.assertRaises(tools.ToolError, msg=str(bad)):
                self.run_tool(bad)

    def test_pdf_goes_through_pdftotext_with_page_range(self):
        touch(os.path.join(self.root, "d.pdf"), "%PDF-fake")
        fake = mock.Mock(returncode=0, stdout="Page text here")
        with mock.patch.object(tools.subprocess, "run", return_value=fake) as run:
            out, _ = self.run_tool({"path": "d.pdf", "pages": "2-4"})
        self.assertEqual(run.call_args.args[0][:7], ["pdftotext", "-layout", "-f", "2", "-l", "4", f"{self.root}/d.pdf"])
        self.assertIn("Page text here", out["text"])

    def test_page_range_parsing(self):
        self.assertEqual(tools._page_range(None), (1, 10))
        self.assertEqual(tools._page_range("3"), (3, 3))
        self.assertEqual(tools._page_range("2-6"), (2, 6))
        self.assertEqual(tools._page_range("junk"), (1, 10))
        self.assertEqual(tools._page_range("1-9999"), (1, 50))     # bounded


class ReadScope(unittest.TestCase):
    def test_home_and_root_are_too_broad(self):
        win = {"class": "com.mitchellh.ghostty", "address": "0x1"}
        for cwd in (os.path.expanduser("~"), "/"):
            with mock.patch.object(tools, "_window", return_value=(win, set())), \
                 mock.patch.object(tools.proc, "snapshot", return_value={}), \
                 mock.patch.object(tools.terminal_adapter, "collect", return_value=({"project": {"cwd": cwd}}, "high")):
                with self.assertRaises(tools.ToolError):
                    tools._scope("0x1")

    def test_ambiguous_terminal_refused_and_downloads_allowed(self):
        win = {"class": "com.mitchellh.ghostty", "address": "0x1"}
        with mock.patch.object(tools, "_window", return_value=(win, set())), mock.patch.object(tools.proc, "snapshot", return_value={}):
            with mock.patch.object(tools.terminal_adapter, "collect", return_value=({"project": {"cwd": "/x"}}, "medium")):
                with self.assertRaises(tools.ToolError):
                    tools._scope("0x1")
            with mock.patch.object(tools.terminal_adapter, "collect", return_value=({"project": {"cwd": "/home/someone/Downloads"}}, "high")):
                self.assertEqual(tools._scope("0x1"), "/home/someone/Downloads")
