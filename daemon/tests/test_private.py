"""What Goop keeps under ~/.cache/goop is owner-only: folders 0700, files 0600 (questions, answers, sessions, screenshots)."""
import os, stat, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop import actions, approvals, private, tools
from goop.agent import openai_compat


def mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


class PrivateCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = os.path.join(self.tmp.name, ".cache", "goop")
        patcher = mock.patch.object(private, "CACHE", self.cache)
        patcher.start()
        self.addCleanup(patcher.stop)
        old = os.umask(0o022)                  # the usual default: new files would be 0644 and folders 0755
        self.addCleanup(os.umask, old)


class Makedirs(PrivateCase):
    def test_creates_every_level_owner_only(self):
        deep = os.path.join(self.cache, "sessions", "a")
        private.makedirs(deep)
        for p in (self.cache, os.path.join(self.cache, "sessions"), deep):
            self.assertEqual(mode(p), 0o700, p)

    def test_tightens_folders_an_older_version_made_open(self):
        sub = os.path.join(self.cache, "sessions")
        os.makedirs(sub, mode=0o755)
        os.chmod(self.cache, 0o755)
        os.chmod(sub, 0o755)
        private.makedirs(sub)
        self.assertEqual(mode(self.cache), 0o700)
        self.assertEqual(mode(sub), 0o700)

    def test_never_loosens_a_folder(self):
        os.makedirs(self.cache, mode=0o500)
        private.makedirs(self.cache)
        self.assertEqual(mode(self.cache), 0o500)
        os.chmod(self.cache, 0o700)

    def test_a_folder_outside_the_cache_is_created_private_but_an_existing_one_is_left_alone(self):
        shared = os.path.join(self.tmp.name, "shared")
        os.makedirs(shared, mode=0o755)
        os.chmod(shared, 0o755)
        private.makedirs(shared)
        self.assertEqual(mode(shared), 0o755)
        fresh = os.path.join(self.tmp.name, "fresh")
        private.makedirs(fresh)
        self.assertEqual(mode(fresh), 0o700)

    def test_the_cache_root_itself(self):
        private.makedirs(self.cache)
        self.assertEqual(mode(self.cache), 0o700)


class OpenFile(PrivateCase):
    def test_new_file_is_0600_even_with_a_permissive_umask(self):
        os.makedirs(self.cache)
        os.umask(0)
        path = os.path.join(self.cache, "a.json")
        with private.open_file(path) as f:
            f.write("x")
        self.assertEqual(mode(path), 0o600)

    def test_existing_open_file_is_tightened_and_truncated(self):
        os.makedirs(self.cache)
        path = os.path.join(self.cache, "a.json")
        with open(path, "w") as f:
            f.write("old content")
        os.chmod(path, 0o644)
        with private.open_file(path) as f:
            f.write("new")
        self.assertEqual(mode(path), 0o600)
        with open(path) as f:
            self.assertEqual(f.read(), "new")

    def test_append_keeps_earlier_lines(self):
        os.makedirs(self.cache)
        path = os.path.join(self.cache, "audit.log")
        for line in ("one\n", "two\n"):
            with private.open_file(path, "a") as f:
                f.write(line)
        with open(path) as f:
            self.assertEqual(f.read(), "one\ntwo\n")
        self.assertEqual(mode(path), 0o600)

    def test_only_write_and_append(self):
        with self.assertRaises(ValueError):
            private.open_file(os.path.join(self.cache, "x"), "r")


class WriteSites(PrivateCase):
    """The places that save a question, an answer or a log really go through the helper."""

    def test_openai_session_file(self):
        with mock.patch.object(openai_compat, "SESSION_DIR", os.path.join(self.cache, "sessions")):
            sid = openai_compat.save_session(None, [{"role": "user", "content": "a private question"}])
        path = os.path.join(self.cache, "sessions", sid + ".json")
        self.assertEqual(mode(path), 0o600)
        self.assertEqual(mode(os.path.dirname(path)), 0o700)
        self.assertEqual(mode(self.cache), 0o700)

    def test_audit_log(self):
        path = os.path.join(self.cache, "audit.log")
        with mock.patch.object(tools, "AUDIT", path):
            tools._audit("read_file", "0x1", True)
        self.assertEqual(mode(path), 0o600)
        self.assertEqual(mode(self.cache), 0o700)

    def test_undo_record(self):
        undo = os.path.join(self.cache, "undo")
        with mock.patch.object(actions, "UNDO_DIR", undo):
            actions._save_undo("/tmp/x", [["a", "b"]], [])
        (name,) = os.listdir(undo)
        self.assertEqual(mode(os.path.join(undo, name)), 0o600)
        self.assertEqual(mode(undo), 0o700)

    def test_approval_answer(self):
        with mock.patch.object(approvals, "DIR", os.path.join(self.cache, "approvals")):
            approvals.answer("abc123def456", True)
        path = os.path.join(self.cache, "approvals", "abc123def456.answer")
        self.assertEqual(mode(path), 0o600)
        self.assertEqual(mode(os.path.dirname(path)), 0o700)


if __name__ == "__main__":
    unittest.main()
