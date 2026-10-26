import array, math, os, sys, threading, time, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop.tts import engine, levels, server, speech_text

SR = 8000


def sine(seconds, amp=0.5):
    n = int(SR * seconds)
    return array.array("h", (int(amp * 32767 * math.sin(2 * math.pi * 220 * i / SR)) for i in range(n))).tobytes()


class FakeEngine(engine.Engine):
    name, sample_rate = "fake", SR

    def __init__(self, chunks=2, seconds=0.2, delay=0.0):
        self.chunks, self.seconds, self.delay, self.voices_seen = chunks, seconds, delay, []

    def available(self):
        return True

    def stream(self, text, voice):
        self.voices_seen.append(voice)
        for _ in range(self.chunks):
            time.sleep(self.delay)
            yield sine(self.seconds)


def sink(_rate):  # a real process that swallows the audio, so we exercise the pipe without making sound
    return ["sh", "-c", "cat > /dev/null"]


def make(eng, **kw):
    events = []
    srv = server.Server(eng, kw.pop("speakers", [3, 5, 8]), player_command=sink, emit=events.append, **kw)
    return srv, events


def wait_for(cond, timeout=4.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


class SpeechText(unittest.TestCase):
    def test_reads_naturally(self):
        t = speech_text.prepare("Ran `ls -la ~/Downloads`. **Six** items in /home/user/Downloads/blueferry, see https://x.io/a?b=1 \U0001F389")
        self.assertEqual(t, "Ran ls -la Downloads. Six items in blueferry, see a link")

    def test_code_blocks_and_bullets_dropped(self):
        self.assertEqual(speech_text.prepare("Do this:\n```\nrm -rf x\n```\n- one\n- two"), "Do this: one two")

    def test_home_and_dotdot(self):
        self.assertEqual(speech_text.prepare("cd ~ then ../up"), "cd home then up")

    def test_cut_at_sentence(self):
        t = "First sentence here. " * 40
        out = speech_text.prepare(t, 100)
        self.assertLessEqual(len(out), 100)
        self.assertTrue(out.endswith("."))

    def test_empty(self):
        self.assertEqual(speech_text.prepare("```x```"), "")


class Levels(unittest.TestCase):
    def test_silence_and_loud(self):
        quiet = levels.envelope(bytes(SR * 2), SR, 30)
        self.assertEqual(max(quiet), 0)
        loud = levels.envelope(sine(0.5, 0.9), SR, 30)
        self.assertAlmostEqual(len(loud), 15, delta=1)
        self.assertGreater(min(loud), 0.9)

    def test_always_in_range(self):
        self.assertTrue(all(0 <= v <= 1 for v in levels.envelope(sine(0.3, 1.0), SR)))


class Pace(unittest.TestCase):
    def test_length_scale(self):
        self.assertEqual(engine.length_scale(1.0), 1.0)
        self.assertAlmostEqual(engine.length_scale(0.88), 1.136, places=3)   # slower speech -> longer phonemes
        self.assertEqual(engine.length_scale(0.01), 2.0)                     # clamped: never absurdly slow
        self.assertAlmostEqual(engine.length_scale(99), 1 / 1.5)             # or absurdly fast

    def test_silence(self):
        self.assertEqual(len(engine.silence(250, 22050)), int(22050 * 0.25) * 2)
        self.assertEqual(set(engine.silence(10, 8000)), {0})


class Voices(unittest.TestCase):
    def test_pick_voice(self):
        self.assertEqual(server.pick_voice([3, 5, 8], 0), 3)
        self.assertEqual(server.pick_voice([3, 5, 8], 4), 5)
        self.assertEqual(server.pick_voice([], 99), 0)
        self.assertNotEqual(server.pick_voice([3, 5, 8], 1), server.pick_voice([3, 5, 8], 2))


class ServerFlow(unittest.TestCase):
    def test_speaks_with_start_levels_and_end(self):
        eng = FakeEngine()
        srv, events = make(eng)
        srv.speak("0xA", "Hello there. Second sentence.", seed=4)
        self.assertTrue(wait_for(lambda: any(e["type"] == "end" for e in events)))
        kinds = [e["type"] for e in events]
        self.assertEqual(kinds[0], "start")
        self.assertEqual(events[0]["id"], "0xA")
        self.assertGreater(events[0]["ttfa_ms"], -1)
        levels_seen = [e["v"] for e in events if e["type"] == "level"]
        self.assertTrue(any(v > 0.5 for v in levels_seen))            # the mouth moved
        self.assertEqual(levels_seen[-1], 0)                            # and closed again
        self.assertEqual(kinds[-1], "end")
        self.assertEqual(eng.voices_seen, [5])                          # seed 4 -> speakers[4 % 3]

    def test_muted_is_silent(self):
        srv, events = make(FakeEngine())
        srv.mute(True)
        srv.speak("0xA", "Hello.")
        time.sleep(0.4)
        self.assertEqual(events, [])

    def test_stop_cuts_speech_and_clears_queue(self):
        srv, events = make(FakeEngine(chunks=20, seconds=0.2, delay=0.05))
        srv.speak("0xA", "A long reply. With many parts.")
        srv.speak("0xB", "Queued behind it.")
        self.assertTrue(wait_for(lambda: any(e["type"] == "start" for e in events)))
        srv.stop()
        self.assertTrue(wait_for(lambda: any(e["type"] == "end" for e in events)))
        time.sleep(0.4)
        self.assertFalse(any(e.get("id") == "0xB" and e["type"] == "start" for e in events))   # queued job was dropped
        self.assertEqual([e for e in events if e["type"] == "level"][-1]["v"], 0)

    def test_back_to_back_utterances_queue_in_order(self):
        srv, events = make(FakeEngine(chunks=1, seconds=0.1))
        srv.speak("0xA", "One.")
        srv.speak("0xB", "Two.")
        self.assertTrue(wait_for(lambda: [e["id"] for e in events if e["type"] == "end"] == ["0xA", "0xB"]))
        starts = [e["id"] for e in events if e["type"] == "start"]
        self.assertEqual(starts, ["0xA", "0xB"])

    def test_engine_failure_does_not_kill_the_server(self):
        class Boom(FakeEngine):
            def stream(self, text, voice):
                raise RuntimeError("model exploded")
                yield b""
        srv, events = make(Boom())
        srv.speak("0xA", "Hi.")
        self.assertTrue(wait_for(lambda: any(e["type"] == "end" for e in events)))
        srv.engine = FakeEngine(chunks=1, seconds=0.1)                  # and it still works afterwards
        srv.speak("0xB", "Hi again.")
        self.assertTrue(wait_for(lambda: any(e["type"] == "start" and e["id"] == "0xB" for e in events)))

    def test_protocol_handles_garbage_and_commands(self):
        srv, events = make(FakeEngine(chunks=1, seconds=0.1))
        srv.serve(["not json\n", '{"cmd":"speak","id":"0xA","text":"Hello.","seed":1}\n', '{"cmd":"quit"}\n'])
        self.assertIsInstance(events, list)


if __name__ == "__main__":
    unittest.main()
