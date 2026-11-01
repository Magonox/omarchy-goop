import json, os, struct, subprocess, sys, tempfile, threading, time, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop import access, doctor, tools
from goop.adapters import browser
import pagereader_install as installer

HOST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pagereader_host.py")


class FakeExtension:
    """Plays the browser's side of the native-messaging pipe: reads framed requests from the host's stdout and answers them."""
    def __init__(self, proc, answer):
        self.proc, self.answer, self.seen = proc, answer, []
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        while True:
            head = self.proc.stdout.read(4)
            if len(head) < 4:
                return
            msg = json.loads(self.proc.stdout.read(struct.unpack("=I", head)[0]))
            self.seen.append(msg)
            data = json.dumps({"id": msg["id"], **self.answer(msg)}).encode()
            self.proc.stdin.write(struct.pack("=I", len(data)) + data)
            self.proc.stdin.flush()


class Host(unittest.TestCase):
    def start(self, answer):
        self.dir = tempfile.mkdtemp()
        env = dict(os.environ, HOME=self.dir)
        self.proc = subprocess.Popen([sys.executable, HOST], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env)
        self.sock = os.path.join(self.dir, ".cache", "goop", "page.sock")
        for _ in range(100):
            if os.path.exists(self.sock):
                break
            time.sleep(0.05)
        self.addCleanup(self.proc.kill)
        return FakeExtension(self.proc, answer)

    def test_a_read_goes_to_the_extension_and_the_page_text_comes_back(self):
        ext = self.start(lambda m: {"ok": True, "title": "A Page", "text": "hello from the page", "url": "http://x/"} if m["cmd"] == "read" else {"ok": True})
        r = browser.read("A Page - Chromium", 5000, sock=self.sock)
        self.assertEqual((r["ok"], r["text"], r["url"]), (True, "hello from the page", "http://x/"))
        self.assertEqual(ext.seen[0]["title"], "A Page")                      # the browser's own " - Chromium" suffix is dropped
        self.assertEqual(ext.seen[0]["max_chars"], 5000)
        self.assertTrue(browser.available(sock=self.sock))

    def test_the_socket_is_private_to_the_user(self):
        self.start(lambda m: {"ok": True})
        self.assertEqual(os.stat(self.sock).st_mode & 0o777, 0o600)

    def test_several_requests_get_their_own_answers(self):
        self.start(lambda m: {"ok": True, "text": f"page for {m['title']}"})
        out = {}

        def one(name):
            out[name] = browser.read(name, 100, sock=self.sock)["text"]
        ts = [threading.Thread(target=one, args=(n,)) for n in ("alpha", "beta", "gamma")]
        [t.start() for t in ts]
        [t.join(10) for t in ts]
        self.assertEqual(out, {"alpha": "page for alpha", "beta": "page for beta", "gamma": "page for gamma"})

    def test_unknown_commands_are_refused(self):
        self.start(lambda m: {"ok": True})
        self.assertFalse(browser.request({"cmd": "delete_everything"}, sock=self.sock)["ok"])

    def test_the_socket_goes_away_when_the_browser_does(self):
        self.start(lambda m: {"ok": True})
        self.proc.stdin.close()
        self.proc.wait(5)
        self.assertFalse(os.path.exists(self.sock))


class Client(unittest.TestCase):
    def test_no_browser_means_a_helpful_error_not_a_crash(self):
        r = browser.read("x", sock="/nonexistent/page.sock")
        self.assertFalse(r["ok"])
        self.assertIn("goop-install-pagereader", r["error"])
        self.assertFalse(browser.available(sock="/nonexistent/page.sock"))

    def test_the_packet_context_falls_back_to_a_screenshot_note(self):
        with mock.patch.object(browser, "read", return_value={"ok": False, "error": "no reader"}):
            ctx, conf = browser.collect({"title": "T"})
        self.assertEqual(conf, "low")
        self.assertIn("screenshot only", ctx["notes"][0])
        with mock.patch.object(browser, "read", return_value={"ok": True, "title": "T", "url": "http://x", "text": "body", "headings": ["H"]}):
            ctx, conf = browser.collect({"title": "T"})
        self.assertEqual((conf, ctx["page"]["text"], ctx["page"]["headings"]), ("high", "body", ["H"]))

    def test_the_page_renders_as_readable_text(self):
        text = browser.render({"title": "Lighthouses", "url": "http://x/l", "description": "About lights", "selection": "Fresnel lens", "headings": ["A", "B"],
                               "text": "Body text.", "truncated": True, "chars": 99999})
        for part in ("PAGE: Lighthouses", "URL: http://x/l", "DESCRIPTION: About lights", "SELECTED THIS TEXT: Fresnel lens", "HEADINGS: A | B", "Body text.", "cut after"):
            self.assertIn(part, text)


class Tool(unittest.TestCase):
    def setUp(self):
        self.win = {"title": "Lighthouses - Chromium", "class": "chromium"}
        for p in (mock.patch.object(tools, "_window", side_effect=lambda a: (self.win, set())), mock.patch.object(tools, "_audit")):
            p.start()
        self.addCleanup(mock.patch.stopall)

    def call(self, args=None, reply=None, **cfg):
        reply = reply or {"ok": True, "title": "Lighthouses", "url": "https://sea.example/lighthouses", "text": "Fresnel lenses bend light.", "headings": ["Lenses"]}
        with mock.patch.object(access.config, "load", return_value={**access.config.DEFAULTS, **cfg}), mock.patch.object(tools.browser_adapter, "read", return_value=reply) as rd, \
                mock.patch.object(tools, "_approve") as ap:
            r = tools.call("read_page", "0xabc", args or {})
        return r, rd, ap

    def test_it_returns_the_page_marked_as_untrusted_data(self):
        r, rd, ap = self.call()
        self.assertIn("untrusted", r["text"])
        self.assertIn("Fresnel lenses bend light.", r["text"])
        ap.assert_not_called()
        self.assertEqual(rd.call_args[0][0], "Lighthouses - Chromium")

    def test_the_length_cap_is_clamped(self):
        self.assertEqual(self.call({"max_chars": 999999})[1].call_args[0][1], 40000)
        self.assertEqual(self.call({"max_chars": 3})[1].call_args[0][1], 500)
        self.assertEqual(self.call({"max_chars": "lots"})[1].call_args[0][1], 12000)

    def test_only_browsers_are_read(self):
        self.win["class"] = "com.mitchellh.ghostty"
        with self.assertRaises(tools.ToolError):
            self.call()

    def test_a_page_on_the_privacy_list_is_not_handed_over(self):
        with self.assertRaises(tools.ToolError) as cm:
            self.call(reply={"ok": True, "title": "My Bank - Account", "url": "https://x/", "text": "balance 1234"})
        self.assertIn("privacy", str(cm.exception))
        with self.assertRaises(tools.ToolError):
            self.call(reply={"ok": True, "title": "Home", "url": "https://paypal.example/me", "text": "secret"})

    def test_ask_for_everything_shows_a_card_first(self):
        _, _, ap = self.call(access="ask_all")
        ap.assert_called_once()
        self.assertEqual(ap.call_args[0][1], "read_page")

    def test_reader_errors_reach_the_agent(self):
        with self.assertRaises(tools.ToolError) as cm:
            self.call(reply={"ok": False, "error": "this kind of page cannot be read (chrome)"})
        self.assertIn("cannot be read", str(cm.exception))

    def test_look_only_still_reads(self):
        self.assertIn("Fresnel", self.call(access="look")[0]["text"])

    def test_it_is_offered_to_the_model(self):
        self.assertIn("read_page", tools.TOOLS)
        self.assertIn("read_page", access.allowed(list(tools.TOOLS), {"access": "look"}))


class Installer(unittest.TestCase):
    FLAGS = "--ozone-platform=wayland\n--load-extension=/usr/a,/usr/b\n--no-default-browser-check\n"

    def test_it_adds_to_the_existing_list_and_is_safe_to_repeat(self):
        once = installer.merge_flags(self.FLAGS, "/g/pagereader")
        self.assertIn("--load-extension=/usr/a,/usr/b,/g/pagereader\n", once)
        self.assertEqual(installer.merge_flags(once, "/g/pagereader"), once)
        self.assertEqual(once.count("--load-extension="), 1)                  # a second flag would replace the first and drop Omarchy's own extensions
        self.assertIn("--ozone-platform=wayland", once)

    def test_it_creates_the_flag_when_there_is_none_and_removes_cleanly(self):
        added = installer.merge_flags("--ozone-platform=wayland\n", "/g/pagereader")
        self.assertEqual(added, "--ozone-platform=wayland\n--load-extension=/g/pagereader\n")
        self.assertEqual(installer.merge_flags(added, "/g/pagereader", remove=True), "--ozone-platform=wayland\n")
        self.assertEqual(installer.merge_flags(installer.merge_flags(self.FLAGS, "/g/p"), "/g/p", remove=True), self.FLAGS)

    def test_a_real_run_backs_the_file_up_and_writes_the_host_manifest(self):
        d = tempfile.mkdtemp()
        flags, hosts = os.path.join(d, "flags.conf"), os.path.join(d, "NativeMessagingHosts")
        open(flags, "w").write(self.FLAGS)
        installer.run(False, flags, [hosts], "/g/pagereader", lambda m: None)
        self.assertTrue(any(n.startswith("flags.conf.bak.") for n in os.listdir(d)))
        manifest = json.load(open(os.path.join(hosts, installer.HOST_NAME + ".json")))
        self.assertEqual(manifest["type"], "stdio")
        self.assertEqual(manifest["path"], installer.HOST_PATH)
        self.assertEqual(manifest["allowed_origins"], [f"chrome-extension://{installer.extension_id()}/"])
        installer.run(True, flags, [hosts], "/g/pagereader", lambda m: None)
        self.assertEqual(open(flags).read(), self.FLAGS)
        self.assertFalse(os.path.exists(os.path.join(hosts, installer.HOST_NAME + ".json")))

    def test_the_extension_id_matches_the_pinned_key(self):
        import base64, hashlib
        key = json.load(open(os.path.join(installer.EXT_DIR, "manifest.json")))["key"]
        h = hashlib.sha256(base64.b64decode(key)).hexdigest()[:32]
        self.assertEqual("".join(chr(ord("a") + int(c, 16)) for c in h), installer.extension_id())


class Doctor(unittest.TestCase):
    def test_the_page_reader_is_an_optional_check_with_a_hint(self):
        with mock.patch.object(doctor, "browser_ready", return_value=False):
            c = next(c for c in doctor.checks(which=lambda x: x, exists=lambda p: True, has_module=lambda n: True) if c["id"] == "pagereader")
        self.assertFalse(c["ok"])
        self.assertFalse(c["required"])
        self.assertIn("goop-install-pagereader", c["hint"])


if __name__ == "__main__":
    unittest.main()
