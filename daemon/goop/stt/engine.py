"""Speech-to-text engines. One interface, so another engine (Parakeet, Whisper) can be added later the same way the voice and the agents are.

    engine = get(settings)          engine.available()   engine.load()
    session = engine.open(context)  session.feed(list of floats at 16 kHz)  session.text()  session.finish() -> text  session.close()

A session is one spoken question. Audio is only ever held in memory while the session lives."""
import importlib.util

ARCHS = {"tiny": "TINY_STREAMING", "small": "SMALL_STREAMING", "medium": "MEDIUM_STREAMING"}
RATE = 16000


class Engine:
    name = ""

    def available(self) -> bool:
        raise NotImplementedError

    def load(self):
        """Open the model (downloads it the first time). Raises on failure."""

    def open(self, context=""):
        raise NotImplementedError


class MoonshineSession:
    def __init__(self, stream):
        from moonshine_voice.transcriber import TranscriptEventListener
        self.stream, self.lines = stream, {}               # line id -> text; dicts keep the order lines arrived in
        outer = self

        class Listener(TranscriptEventListener):
            def _take(self, event):
                outer.lines[event.line.line_id] = event.line.text
            on_line_started = on_line_updated = on_line_text_changed = on_line_completed = _take
        stream.add_listener(Listener())
        stream.start()

    def feed(self, samples):
        self.stream.add_audio(samples, RATE)

    def text(self):
        return " ".join(t.strip() for t in self.lines.values() if t and t.strip()).strip()

    def finish(self):
        try:
            result = self.stream.stop()                      # transcribes what is left in the buffer
            for line in getattr(result, "lines", None) or []:
                self.lines[line.line_id] = line.text
        except Exception:
            pass
        return self.text()

    def close(self):
        try:
            self.stream.close()
        except Exception:
            pass


class MoonshineEngine(Engine):
    """Moonshine streaming models: small (142 MB) by default, about 5x faster than real time on a 2018 laptop CPU, English, text appears while you speak."""
    name = "moonshine"

    def __init__(self, model="small", language="en"):
        self.model, self.language, self.transcriber = model if model in ARCHS else "small", language, None

    def available(self):
        return importlib.util.find_spec("moonshine_voice") is not None

    def load(self):
        import moonshine_voice as mv
        from moonshine_voice.transcriber import Transcriber
        path, arch = mv.get_model_for_language(self.language, mv.ModelArch[ARCHS[self.model]])
        self.transcriber = Transcriber(path, arch, update_interval=0.3)

    def open(self, context=""):
        try:
            self.transcriber.set_context(context or None, 8)    # bias towards the unusual words on screen (names, jargon)
        except Exception:
            pass
        return MoonshineSession(self.transcriber.create_stream(update_interval=0.3))


ENGINES = {"moonshine": MoonshineEngine}


def get(settings):
    cls = ENGINES.get(settings.get("engine"), MoonshineEngine)
    return cls(settings.get("model", "small"), settings.get("language", "en"))
