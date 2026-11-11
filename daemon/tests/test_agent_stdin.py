"""The user's question must reach agent.py over stdin, not on the command line (argv is world-readable in /proc)."""
import contextlib, io, json, os, re, sys, unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agent
from goop import config

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def ns(command=None):
    return SimpleNamespace(command=command, stdin=command is None)


class ReadCommand(unittest.TestCase):
    def test_command_flag_wins(self):
        self.assertEqual(agent.read_command(ns("hi"), io.StringIO("")), "hi")

    def test_reads_one_json_line_from_stdin(self):
        line = json.dumps({"command": "what is this?\nand \"this\"; $(rm -rf ~)"}) + "\n"
        self.assertEqual(agent.read_command(ns(), io.StringIO(line)), 'what is this?\nand "this"; $(rm -rf ~)')

    def test_only_the_first_line_is_read(self):
        stdin = io.StringIO(json.dumps({"command": "one"}) + "\n" + json.dumps({"command": "two"}) + "\n")
        self.assertEqual(agent.read_command(ns(), stdin), "one")

    def test_bad_input_is_a_readable_error(self):
        for bad in ("", "\n", "not json\n", "[]\n", "{}\n", '{"command": 5}\n', '{"command": "  "}\n', "null\n"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                agent.read_command(ns(), io.StringIO(bad))


class Main(unittest.TestCase):
    def run_main(self, argv, stdin_text):
        out = io.StringIO()
        with mock.patch.object(config, "load", return_value={"enabled": True}), \
             mock.patch.object(sys, "argv", ["agent.py"] + argv), \
             mock.patch.object(sys, "stdin", io.StringIO(stdin_text)), \
             contextlib.redirect_stdout(out):
            agent.main()
        return [json.loads(l) for l in out.getvalue().splitlines()]

    def test_bad_stdin_emits_an_error_event(self):
        evs = self.run_main(["--address", "0x1", "--stdin"], "garbage\n")
        self.assertEqual([e["type"] for e in evs], ["error"])
        self.assertIn("stdin", evs[0]["message"])

    def test_needs_exactly_one_source(self):
        for argv in (["--address", "0x1"], ["--address", "0x1", "--stdin", "--command", "x"]):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.run_main(argv, "")


class ShellDoesNotLeak(unittest.TestCase):
    """Guard against putting the question back on a command line."""

    def test_goop_qml_uses_stdin_not_command(self):
        with open(os.path.join(ROOT, "shell", "Goop.qml"), encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn('"--command"', src)
        self.assertIn('"--stdin"', src)
        self.assertTrue(re.search(r"stdinEnabled:\s*true", src[src.index("id: agent"):][:400]))


if __name__ == "__main__":
    unittest.main()
