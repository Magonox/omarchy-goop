"""The microphone side of goop: listens when asked, streams the words as they are heard, and says when the user has finished.

Protocol, newline-delimited JSON. In:  {"cmd":"listen","address":"0x..","context":"text on screen"}  {"cmd":"stop"} (finish now)  {"cmd":"cancel"}  {"cmd":"quit"}
Out: {"type":"listening"}  {"type":"level","v":0..1}  {"type":"partial","text"}  {"type":"final","text","reason":"silence|stopped|timeout|max"}  {"type":"idle"}  {"type":"error","why"}
The microphone is only open between listen and final/cancel. Nothing is recorded to disk or sent anywhere."""
import json, math, subprocess, sys, threading, time
from array import array

RATE, CHUNK = 16000, 1600                  # 100 ms of 16 kHz mono


class Endpointer:
    """Decides when a question is over. Speech is any chunk well above the background noise (which it keeps learning, so a humming fan is not speech); the question ends after
    `silence` seconds of quiet once something was heard. Nothing said for `no_speech` seconds, or `max_seconds` in total, ends it too."""

    def __init__(self, silence=1.0, no_speech=8.0, max_seconds=30.0):
        self.silence, self.no_speech, self.max_seconds = silence, no_speech, max_seconds
        self.t = self.last_voice = 0.0
        self.noise, self.spoke = 0.004, False

    def feed(self, rms, dt, has_text, text_changed=False):
        """-> None while listening, else the reason it ended: "silence", "timeout" or "max".
        New words from the model count as speech too, so a quiet speaker is not cut off mid-sentence."""
        self.t += dt
        if text_changed or rms > max(0.012, self.noise * 3.0):
            self.last_voice, self.spoke = self.t, True
        self.noise = min(rms, self.noise * 1.04 + 1e-5)       # follows quiet moments down at once, creeps up slowly: a steady fan or hum stops counting as speech
        if self.t >= self.max_seconds:
            return "max"
        if has_text and self.t - self.last_voice >= self.silence:
            return "silence"
        if not self.spoke and not has_text and self.t >= self.no_speech:
            return "timeout"
        return None


class ParecordMic:
    """The default microphone through PipeWire's PulseAudio layer (already on every Omarchy desktop), raw 16 kHz mono."""

    def __init__(self):
        self.proc = subprocess.Popen(["parecord", "--raw", "--rate=16000", "--channels=1", "--format=s16le", "--latency-msec=60"],
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def read(self):
        data = self.proc.stdout.read(CHUNK * 2)
        return data if data else None

    def close(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=2)
        except Exception:
            pass


class Server:
    def __init__(self, engine, settings, emit=None, mic=ParecordMic, context_for=None):
        self.engine, self.settings, self.mic_factory, self.context_for = engine, settings, mic, context_for
        self._emit, self._lock = emit or self._print, threading.Lock()
        self.thread, self.finish_req = None, None

    def _print(self, ev):
        with self._lock:
            sys.stdout.write(json.dumps(ev) + "\n")
            sys.stdout.flush()

    def emit(self, ev):
        self._emit(ev)

    # ---- one spoken question ----
    def _run(self, context, req):
        cfg = self.settings
        ep = Endpointer(cfg.get("silence_ms", 1000) / 1000, cfg.get("no_speech_seconds", 8), cfg.get("max_seconds", 30))
        try:
            mic = self.mic_factory()
        except OSError as e:
            return self.emit({"type": "error", "why": f"the microphone could not be opened: {e}"})
        session = self.engine.open(context)
        self.emit({"type": "listening"})
        last_text, last_level, reason = "", 0.0, None
        try:
            while reason is None:
                if req["cancel"]:
                    return self.emit({"type": "idle"})
                raw = mic.read()
                if raw is None:
                    reason = "stopped"
                    break
                pcm = array("h")
                pcm.frombytes(raw[:len(raw) // 2 * 2])
                samples = [x / 32768.0 for x in pcm]
                rms = math.sqrt(sum(x * x for x in samples) / len(samples)) if samples else 0.0
                now = time.monotonic()
                if now - last_level >= 0.08:
                    last_level = now
                    self.emit({"type": "level", "v": round(min(1.0, rms * 7), 3)})
                session.feed(samples)
                text = session.text()
                changed = text != last_text
                if changed:
                    last_text = text
                    self.emit({"type": "partial", "text": text})
                reason = "stopped" if req["finish"] else ep.feed(rms, len(samples) / RATE, bool(text), changed)
            mic.close()
            mic = None
            self.emit({"type": "final", "text": session.finish(), "reason": reason})
        except Exception as e:                       # a bug here must not leave the microphone open
            self.emit({"type": "error", "why": f"{type(e).__name__}: {e}"})
        finally:
            if mic:
                mic.close()
            session.close()
            self.emit({"type": "idle"})

    def listen(self, context=""):
        self.cancel()
        req = {"cancel": False, "finish": False}
        self.req = req
        self.thread = threading.Thread(target=self._run, args=(context, req), daemon=True)
        self.thread.start()

    def finish(self):
        if self.thread and self.thread.is_alive():
            self.req["finish"] = True

    def cancel(self):
        if self.thread and self.thread.is_alive():
            self.req["cancel"] = True
            self.thread.join(3)

    def serve(self, lines=None):
        for line in (lines if lines is not None else sys.stdin):
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            cmd = msg.get("cmd")
            if cmd == "listen":
                context = str(msg.get("context") or "")
                if not context and msg.get("address") and self.context_for:          # the words on screen help it get names right
                    try:
                        context = self.context_for(msg["address"]) or ""
                    except Exception:
                        context = ""
                self.listen(context[:4000])
            elif cmd == "stop":
                self.finish()
            elif cmd == "cancel":
                self.cancel()
            elif cmd == "quit":
                break
        self.cancel()
