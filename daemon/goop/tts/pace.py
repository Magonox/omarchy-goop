"""Voice pace. Piper's speakers each talk at their own natural speed, so one global speed makes some characters sound rushed. Here every speaker's natural pace is measured once
(characters of speech per second on a fixed paragraph, pauses excluded) and the engine slows the fast ones and speeds up the slow ones to a common pace; the user's `tts.speed`
still scales that common pace. Piper's length_scale is a weak lever (the pace changes roughly as length_scale ** -0.45, so doubling it speeds a voice down by only about a quarter), so the
stretch each speaker needs is solved from measurements, not assumed linear. A table for every speaker of the default voice ships with Goop (pace_<model>.json, made by daemon/calibrate_voices.py); for any other model a
speaker is measured the first time it speaks and remembered in ~/.cache/goop/voice_pace.json."""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.expanduser("~/.cache/goop/voice_pace.json")
ELASTICITY = 0.45          # measured on the libritts_r voices: pace ~ length_scale ** -0.45
CLAMP = (0.6, 1.8)          # never stretch a voice by more than this, whatever the measurement says
TEXT = ("Hello, I am a goop. I look at what is on your screen and I can explain how things work. "
        "A rocket engine pushes hot gas out of the back, and the rocket goes up. Would you like me to show you a model of it?")


def clamp(f):
    return max(CLAMP[0], min(CLAMP[1], f))


def predicted_factor(cps, target):
    """The stretch that should bring a voice with natural pace `cps` to `target`, from the average response curve."""
    return clamp((cps / target) ** (1 / ELASTICITY)) if cps and target else 1.0


def refined_factor(cps, target, tried, got):
    """One correction step: the voice was run with stretch `tried` and came out at pace `got`; solve its own response curve for the target."""
    if abs(math.log(tried)) < 0.04 or got <= 0 or cps <= got:
        return clamp(tried * (got / target) ** (1 / ELASTICITY)) if got > 0 and abs(math.log(tried)) >= 0.04 else tried
    e = max(0.15, min(1.2, math.log(cps / got) / math.log(tried)))
    return clamp(tried * (got / target) ** (1 / e))


def measure(engine, voice, factor=1.0):
    """Characters of speech per second with the voice stretched by `factor` (1.0 = its natural pace). The engine must have no pauses and no pace table of its own."""
    old = engine.speed
    engine.speed = 1.0 / factor
    try:
        seconds = sum(len(pcm) / 2 / engine.sample_rate for pcm in engine.stream(TEXT, voice))
    finally:
        engine.speed = old
    return len(TEXT) / seconds if seconds else 0.0


def shipped_path(model):
    return os.path.join(HERE, f"pace_{model}.json")


def _read(path):
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


class Pace:
    """Per-speaker length factors for one model."""

    def __init__(self, model, cache=CACHE, shipped=None):
        self.model, self.cache_path = model, cache
        table = _read(shipped or shipped_path(model))
        self.target = table.get("target")
        self.cps = {int(k): v for k, v in table.get("cps", {}).items()}
        self.factors = {int(k): v for k, v in table.get("factor", {}).items()}       # solved stretches, when the table was refined
        user = _read(cache).get(model, {})
        for k, v in user.get("cps", {}).items():
            self.cps.setdefault(int(k), v)
        self.target = self.target or user.get("target")

    def factor(self, voice, measure_fn=None):
        """What to multiply the length scale by for this speaker: above 1 slows a fast talker down. 1.0 when nothing is known."""
        if voice not in self.cps and measure_fn:
            self.cps[voice] = round(measure_fn(voice), 3)
            self._remember()
        if voice in self.factors:
            return clamp(self.factors[voice])
        return predicted_factor(self.cps.get(voice), self.target)

    def _remember(self):
        try:
            data = _read(self.cache_path)
            data[self.model] = {"target": self.target, "cps": {str(k): v for k, v in self.cps.items()}}
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w") as f:
                json.dump(data, f)
        except OSError:
            pass


def build_table(rates, factors=None):
    """{"target", "cps", "factor"} from measured natural paces (and solved stretches once refined). The target is the median pace, so typical voices stay put and the outliers move toward them."""
    values = sorted(rates.values())
    table = {"target": round(values[len(values) // 2], 3), "cps": {str(k): round(v, 3) for k, v in sorted(rates.items())}}
    table["factor"] = {str(k): round(v, 3) for k, v in sorted((factors or {k: predicted_factor(c, table["target"]) for k, c in rates.items()}).items())}
    return table
