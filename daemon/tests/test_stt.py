import math, os, sys, threading, time, unittest
from array import array

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop import config
from goop.stt import engine as engines
from goop.stt.server import CHUNK, Endpointer, Server

LOUD, QUIET = 0.2, 0.0005


def chunk(level):
    """100 ms of audio at the given loudness, as the microphone delivers it (16-bit mono)."""
    return array("h", [int(math.sin(2 * math.pi * 220 * i / 16000) * level * 32767 * 1.414) for i in range(CHUNK)]).tobytes()


class FakeMic:
    """Plays a script of loudness values, one per 100 ms chunk, then ends (None) like a closed stream."""
    def __init__(self, script, block=False):
        self.script, self.closed, self.block = list(script), False, block

    def read(self):
        if self.block and not self.script:
            time.sleep(0.01)
            return chunk(LOUD)                                   # keeps "talking" so only stop/cancel can end it
        return chunk(self.script.pop(0)) if self.script else None

    def close(self):
        self.closed = True


class FakeSession:
    """Hears one more word for every 3 loud chunks."""
    def __init__(self, words):
        self.words, self.loud, self.closed = words, 0, False

    def feed(self, samples):
        if math.sqrt(sum(x * x for x in samples) / len(samples)) > 0.05:
            self.loud += 1

    def text(self):
        return " ".join(self.words[:self.loud // 3])

    def finish(self):
        return " ".join(self.words)

    def close(self):
        self.closed = True


class FakeEngine:
    def __init__(self, words=("how", "does", "a", "blu-ray", "disc", "work")):
        self.words, self.contexts, self.sessions = words, [], []

    def open(self, context=""):
        self.contexts.append(context)
        self.sessions.append(FakeSession(self.words))
        return self.sessions[-1]


def run(script, settings=None, block=False, engine=None, context=""):
    events, mic = [], FakeMic(script, block)
    eng = engine or FakeEngine()
    server = Server(eng, {"silence_ms": 1000, "no_speech_seconds": 3, "max_seconds": 30, **(settings or {})}, emit=events.append, mic=lambda: mic)
    server.listen(context)
    server.thread.join(10)
    return events, mic, eng, server


class Endpointing(unittest.TestCase):
    def test_a_pause_after_speech_ends_the_question(self):
        ep = Endpointer(silence=1.0)
        out = [ep.feed(0.2, 0.1, True) for _ in range(10)] + [ep.feed(0.0005, 0.1, True) for _ in range(9)]
        self.assertTrue(all(o is None for o in out))                 # 0.9 s of quiet is not yet the end
        self.assertEqual(ep.feed(0.0005, 0.1, True), "silence")

    def test_nothing_said_times_out(self):
        ep = Endpointer(no_speech=3.0)
        out = [ep.feed(0.0005, 0.1, False) for _ in range(40)]
        self.assertEqual(next(o for o in out if o), "timeout")

    def test_a_long_question_is_cut_at_the_maximum(self):
        ep = Endpointer(max_seconds=5.0)
        self.assertEqual(next(o for o in (ep.feed(0.2, 0.1, True) for _ in range(80)) if o), "max")

    def test_new_words_count_as_speech_so_quiet_voices_are_not_cut_off(self):
        ep = Endpointer(silence=1.0)
        for _ in range(30):                                          # very quiet speech: below the loudness bar but the model keeps hearing words
            self.assertIsNone(ep.feed(0.004, 0.1, True, text_changed=True))
        self.assertIsNone(ep.feed(0.004, 0.1, True))

    def test_it_adapts_to_a_noisy_room(self):
        ep = Endpointer(silence=1.0)
        out = [ep.feed(0.02, 0.1, True) for _ in range(60)]         # a steady hum with some words heard: the hum must not count as speech forever
        self.assertIn("silence", out)
        self.assertLess(ep.last_voice, 3.0)


class Session(unittest.TestCase):
    def test_a_spoken_question_streams_words_then_finishes_on_the_pause(self):
        events, mic, eng, _ = run([LOUD] * 20 + [QUIET] * 15)
        types = [e["type"] for e in events]
        self.assertEqual(types[0], "listening")
        self.assertIn("level", types)
        partials = [e["text"] for e in events if e["type"] == "partial"]
        self.assertEqual(partials[0], "how")                          # words appear as they are heard
        self.assertEqual(partials, sorted(partials, key=len))
        final = next(e for e in events if e["type"] == "final")
        self.assertEqual((final["text"], final["reason"]), ("how does a blu-ray disc work", "silence"))
        self.assertEqual(types[-1], "idle")
        self.assertTrue(mic.closed)
        self.assertTrue(eng.sessions[0].closed)

    def test_silence_only_ends_with_an_empty_final(self):
        events, mic, *_ = run([QUIET] * 50)
        final = next(e for e in events if e["type"] == "final")
        self.assertEqual((final["text"], final["reason"]), ("how does a blu-ray disc work", "timeout"))   # the fake engine always finishes with its words
        self.assertTrue(mic.closed)

    def test_stop_finishes_now(self):
        events, mic, eng, server = [], FakeMic([LOUD] * 5, block=True), FakeEngine(), None
        server = Server(eng, {"silence_ms": 1000, "no_speech_seconds": 30, "max_seconds": 30}, emit=events.append, mic=lambda: mic)
        server.listen()
        time.sleep(0.3)
        server.finish()
        server.thread.join(5)
        self.assertEqual(next(e for e in events if e["type"] == "final")["reason"], "stopped")
        self.assertTrue(mic.closed)

    def test_cancel_sends_no_final_and_closes_the_microphone(self):
        events, mic, eng = [], FakeMic([LOUD] * 5, block=True), FakeEngine()
        server = Server(eng, {"silence_ms": 1000, "no_speech_seconds": 30, "max_seconds": 30}, emit=events.append, mic=lambda: mic)
        server.listen()
        time.sleep(0.3)
        server.cancel()
        self.assertFalse(any(e["type"] == "final" for e in events))
        self.assertEqual(events[-1]["type"], "idle")
        self.assertTrue(mic.closed)

    def test_the_screen_context_reaches_the_engine(self):
        _, _, eng, _ = run([LOUD] * 6 + [QUIET] * 12, context="Hyprland Omarchy")
        self.assertEqual(eng.contexts, ["Hyprland Omarchy"])

    def test_a_missing_microphone_is_reported_not_raised(self):
        events = []
        server = Server(FakeEngine(), {}, emit=events.append, mic=lambda: (_ for _ in ()).throw(OSError("no such device")))
        server.listen()
        server.thread.join(5)
        self.assertEqual(events[0]["type"], "error")
        self.assertIn("microphone", events[0]["why"])

    def test_a_crash_inside_still_closes_the_microphone(self):
        class Boom(FakeEngine):
            def open(self, context=""):
                s = super().open(context)
                s.feed = lambda samples: (_ for _ in ()).throw(RuntimeError("boom"))
                return s
        events, mic, *_ = run([LOUD] * 5, engine=Boom())
        self.assertTrue(any(e["type"] == "error" for e in events))
        self.assertTrue(mic.closed)

    def test_the_protocol_over_stdin(self):
        events, mic = [], FakeMic([LOUD] * 20 + [QUIET] * 15)
        server = Server(FakeEngine(), {"silence_ms": 1000, "no_speech_seconds": 3, "max_seconds": 30}, emit=events.append, mic=lambda: mic)
        def lines():
            yield '{"cmd":"listen","context":"x"}\n'
            yield "not json\n"
            for _ in range(400):                                    # stdin stays open until the question is over
                if any(e["type"] == "final" for e in events):
                    break
                time.sleep(0.02)
        server.serve(lines())
        self.assertTrue(any(e["type"] == "final" for e in events))


class Engines(unittest.TestCase):
    def test_model_names_map_to_sizes_and_junk_falls_back(self):
        self.assertEqual(engines.get({"model": "tiny"}).model, "tiny")
        self.assertEqual(engines.get({"model": "medium"}).model, "medium")
        self.assertEqual(engines.get({"model": "huge"}).model, "small")
        self.assertIsInstance(engines.get({"engine": "nope"}), engines.MoonshineEngine)

    def test_defaults_are_the_recommended_ones(self):
        d = config.DEFAULTS["stt"]
        self.assertEqual((d["engine"], d["model"], d["silence_ms"], d["auto_send_ms"]), ("moonshine", "small", 1000, 1500))


@unittest.skipUnless(engines.MoonshineEngine().available(), "moonshine-voice is not installed in this Python")
class Real(unittest.TestCase):
    def test_the_real_model_hears_a_spoken_sentence(self):
        eng = engines.MoonshineEngine("tiny")
        eng.load()
        sess = eng.open("")
        from goop.tts import engine as tts_engines
        cfg = config.tts()
        pcm = b"".join(tts_engines.get(cfg).stream("How does a blue laser read a disc?", cfg["speakers"][0]))
        a = array("h")
        a.frombytes(pcm)
        a16 = [a[min(len(a) - 1, int(i * 22050 / 16000))] / 32768.0 for i in range(int(len(a) * 16000 / 22050))]     # 22.05 kHz voice -> 16 kHz
        for i in range(0, len(a16), CHUNK):
            sess.feed(a16[i:i + CHUNK])
        text = sess.finish().lower()
        sess.close()
        self.assertIn("laser", text)
        self.assertIn("disc", text)


if __name__ == "__main__":
    unittest.main()


class Doctor(unittest.TestCase):
    def test_voice_input_is_an_optional_check_with_a_hint(self):
        from goop import doctor
        def check(has, which):
            return next(c for c in doctor.checks(which=lambda c: c if which else None, exists=lambda p: True, has_module=lambda n: has) if c["id"] == "listen")
        self.assertTrue(check(True, True)["ok"])
        bad = check(False, True)
        self.assertFalse(bad["ok"])
        self.assertFalse(bad["required"])
        self.assertIn("setup.sh", bad["hint"])
        self.assertFalse(check(True, False)["ok"])                      # no parecord, no microphone
