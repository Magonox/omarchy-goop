"""TTS engines. An engine streams int16 mono PCM, one chunk per sentence, so playback can start after the first
sentence. Add an engine by subclassing Engine and listing it in ENGINES (the same idea as the LLM providers)."""
import os
from typing import Iterator, List

from . import pace

VOICE_DIR = os.path.expanduser("~/.local/share/goop/voices")


def length_scale(speed):
    """Piper stretches phonemes by length_scale (above 1 is slower), so speed 0.88 -> about 1.14. Clamped to stay intelligible."""
    return 1.0 / max(0.5, min(1.5, speed))


def silence(ms, sample_rate):
    return bytes(int(sample_rate * ms / 1000) * 2)   # int16 mono zeros


class Engine:
    name = ""
    sample_rate = 22050

    def available(self) -> bool:
        raise NotImplementedError

    def voices(self) -> List[int]:
        raise NotImplementedError

    def stream(self, text: str, voice: int) -> Iterator[bytes]:
        raise NotImplementedError


class PiperEngine(Engine):
    name = "piper"

    def __init__(self, model="en_US-libritts_r-medium", voice_dir=VOICE_DIR, speed=1.0, pause_ms=0, even_pace=True):
        self.path = os.path.join(voice_dir, model + ".onnx")
        self.speed, self.pause_ms, self.model = speed, pause_ms, model
        self.pace = pace.Pace(model) if even_pace else None       # per-speaker factors that even out how fast the characters talk
        self._voice = None

    def available(self):
        try:
            import piper  # noqa: F401
        except ImportError:
            return False
        return os.path.exists(self.path)

    def _load(self):
        if self._voice is None:
            from piper import PiperVoice
            self._voice = PiperVoice.load(self.path)
            self.sample_rate = self._voice.config.sample_rate
        return self._voice

    def voices(self):
        return list(range(self._load().config.num_speakers))

    def natural_pace(self, voice):
        """Characters per second this speaker talks at with no stretching (what daemon/calibrate_voices.py records)."""
        plain = PiperEngine(self.model, os.path.dirname(self.path), speed=1.0, pause_ms=0, even_pace=False)
        plain._voice = self._load()
        plain.sample_rate = self.sample_rate
        return pace.measure(plain, voice)

    def stream(self, text, voice):
        from piper.config import SynthesisConfig
        v = self._load()
        factor = self.pace.factor(voice, self.natural_pace) if self.pace else 1.0
        cfg = SynthesisConfig(speaker_id=voice, length_scale=length_scale(self.speed) * factor)
        gap = silence(self.pause_ms, v.config.sample_rate) if self.pause_ms else b""
        for chunk in v.synthesize(text, syn_config=cfg):
            yield chunk.audio_int16_bytes + gap          # the pause rides on the sentence, so streaming order is unchanged


ENGINES = {"piper": PiperEngine}


def get(settings):
    name = settings.get("engine", "piper")
    if name not in ENGINES:
        raise ValueError(f"unknown tts engine {name!r}; available: {', '.join(ENGINES)}")
    return ENGINES[name](model=settings.get("model", "en_US-libritts_r-medium"),
                         speed=settings.get("speed", 1.0), pause_ms=settings.get("pause_ms", 0))
