import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop.tts import engine as engines, pace


class FakeEngine:
    """Speaks the calibration text at a natural pace of its own per speaker (characters per second), stretching it the way Piper does: the pace changes as length_scale ** -0.45."""
    sample_rate = 22050

    def __init__(self, cps):
        self.cps = cps
        self.speed = 1.0

    def stream(self, text, voice):
        seconds = len(text) / self.cps[voice] * (1.0 / self.speed) ** pace.ELASTICITY
        yield bytes(int(seconds * self.sample_rate) * 2)


class Measuring(unittest.TestCase):
    def test_measure_returns_characters_per_second_of_speech(self):
        eng = FakeEngine({1: 20.0, 2: 30.0})
        self.assertAlmostEqual(pace.measure(eng, 1), 20.0, delta=0.05)
        self.assertAlmostEqual(pace.measure(eng, 2), 30.0, delta=0.05)

    def test_measuring_with_a_stretch_follows_the_response_curve_and_restores_the_speed(self):
        eng = FakeEngine({1: 20.0})
        self.assertAlmostEqual(pace.measure(eng, 1, factor=1.5), 20.0 * 1.5 ** -0.45, delta=0.05)
        self.assertEqual(eng.speed, 1.0)

    def test_the_table_targets_the_median_so_typical_voices_stay_put(self):
        table = pace.build_table({0: 25.0, 1: 22.0, 2: 20.0, 3: 28.0, 4: 22.5})
        self.assertEqual(table["target"], 22.5)
        self.assertEqual(table["cps"]["3"], 28.0)
        self.assertAlmostEqual(table["factor"]["4"], 1.0, places=2)
        self.assertGreater(table["factor"]["3"], 1.0)
        self.assertLess(table["factor"]["2"], 1.0)


class Factors(unittest.TestCase):
    def make(self, cps=None, target=22.5):
        d = tempfile.mkdtemp()
        shipped = os.path.join(d, "shipped.json")
        json.dump({"target": target, "cps": cps or {}}, open(shipped, "w"))
        return pace.Pace("m", cache=os.path.join(d, "cache.json"), shipped=shipped), d

    def test_a_fast_talker_is_slowed_a_slow_talker_is_sped_up_and_a_typical_one_is_left_alone(self):
        p, _ = self.make({"1": 28.5, "2": 20.0, "3": 22.5})
        self.assertAlmostEqual(p.factor(1), (28.5 / 22.5) ** (1 / pace.ELASTICITY))   # more than 1: stretched, so it sounds slower
        self.assertGreater(p.factor(1), 1.3)                                           # a weak lever needs a big stretch
        self.assertLess(p.factor(2), 1.0)
        self.assertAlmostEqual(p.factor(3), 1.0)

    def test_the_stretch_really_lands_on_the_target_pace_with_the_assumed_curve(self):
        for cps in (20.0, 22.0, 26.0, 29.0):          # inside the clamp; a voice slower than the clamp allows cannot reach the target
            got = cps * pace.predicted_factor(cps, 23.5) ** -pace.ELASTICITY
            self.assertAlmostEqual(got, 23.5, delta=0.1, msg=cps)

    def test_a_solved_stretch_in_the_table_wins_over_the_prediction(self):
        d = tempfile.mkdtemp()
        shipped = os.path.join(d, "s.json")
        json.dump({"target": 22.5, "cps": {"1": 28.5}, "factor": {"1": 1.33}}, open(shipped, "w"))
        self.assertEqual(pace.Pace("m", cache=os.path.join(d, "c.json"), shipped=shipped).factor(1), 1.33)

    def test_one_correction_step_moves_the_stretch_the_right_way(self):
        # a voice whose own curve is steeper than average: the first guess overshoots slow, so the stretch comes back down
        tried = pace.predicted_factor(28.0, 23.0)
        got = 28.0 * tried ** -0.7                                                      # this voice responds more strongly than the average
        better = pace.refined_factor(28.0, 23.0, tried, got)
        self.assertLess(better, tried)
        self.assertAlmostEqual(28.0 * better ** -0.7, 23.0, delta=0.3)
        got_weak = 28.0 * tried ** -0.25                                                # a stubborn voice needs more
        self.assertGreater(pace.refined_factor(28.0, 23.0, tried, got_weak), tried)

    def test_the_stretch_is_clamped(self):
        p, _ = self.make({"1": 60.0, "2": 5.0})
        self.assertEqual(p.factor(1), pace.CLAMP[1])
        self.assertEqual(p.factor(2), pace.CLAMP[0])
        self.assertEqual(pace.refined_factor(60.0, 22.5, 1.5, 40.0), pace.CLAMP[1])

    def test_an_unknown_speaker_is_left_alone_unless_it_can_be_measured(self):
        p, _ = self.make({})
        self.assertEqual(p.factor(9), 1.0)
        self.assertAlmostEqual(p.factor(9, lambda v: 27.0), pace.predicted_factor(27.0, 22.5))

    def test_a_measured_speaker_is_remembered_for_next_time(self):
        p, d = self.make({})
        p.factor(9, lambda v: 27.0)
        again = pace.Pace("m", cache=os.path.join(d, "cache.json"), shipped=os.path.join(d, "shipped.json"))
        self.assertAlmostEqual(again.factor(9), pace.predicted_factor(27.0, 22.5))

    def test_no_table_at_all_changes_nothing(self):
        p = pace.Pace("no-such-model", cache="/nonexistent/c.json", shipped="/nonexistent/s.json")
        self.assertEqual(p.factor(0), 1.0)


class InTheEngine(unittest.TestCase):
    def test_the_piper_engine_multiplies_the_speed_setting_by_the_speaker_factor(self):
        eng = engines.PiperEngine(speed=0.94, even_pace=True)
        eng.pace = type("P", (), {"factor": lambda self, voice, fn=None: {1: 1.25, 2: 0.9}[voice]})()
        seen = []

        class Chunk:
            audio_int16_bytes = b"\x00\x00"

        class Voice:
            class config:
                sample_rate = 22050
            def synthesize(self, text, syn_config):
                seen.append(syn_config.length_scale)
                yield Chunk()
        eng._voice = Voice()
        try:
            import piper  # noqa: F401
        except ImportError:
            self.skipTest("piper is not installed in this Python")
        list(eng.stream("hi", 1)); list(eng.stream("hi", 2))
        base = engines.length_scale(0.94)
        self.assertAlmostEqual(seen[0], base * 1.25)
        self.assertAlmostEqual(seen[1], base * 0.9)

    def test_even_pace_can_be_switched_off(self):
        self.assertIsNone(engines.PiperEngine(even_pace=False).pace)

    def test_the_shipped_table_covers_the_configured_speakers_when_it_exists(self):
        path = pace.shipped_path("en_US-libritts_r-medium")
        if not os.path.exists(path):
            self.skipTest("the pace table has not been generated yet")
        table = json.load(open(path))
        self.assertGreater(table["target"], 10)
        for sid in (0, 112, 233, 358, 471, 590, 702, 815):
            self.assertIn(str(sid), table["cps"])
            self.assertIn(str(sid), table["factor"])


if __name__ == "__main__":
    unittest.main()
