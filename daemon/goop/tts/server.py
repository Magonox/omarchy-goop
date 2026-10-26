"""Warm TTS process. One utterance at a time: synthesize sentence by sentence, stream to the speakers, and emit mouth
levels in time with playback.

stdin  (JSON lines):  {"cmd":"speak","id":ADDR,"text":...,"seed":N}   {"cmd":"stop"}   {"cmd":"mute","on":true}   {"cmd":"quit"}
stdout (JSON lines):  {"type":"ready"}  {"type":"start","id":ADDR,"ttfa_ms":N}  {"type":"level","id":ADDR,"v":0..1}  {"type":"end","id":ADDR}
"""
import json, queue, subprocess, sys, threading, time
from collections import deque

from . import levels, speech_text

OUT_LATENCY = 0.06      # rough delay between writing audio and hearing it
LEVEL_HZ = 30


def paplay_command(sample_rate):
    return ["paplay", "--raw", f"--rate={sample_rate}", "--format=s16le", "--channels=1", "--latency-msec=40"]


def pick_voice(speakers, seed):
    return speakers[seed % len(speakers)] if speakers else 0


class Server:
    def __init__(self, engine, speakers, max_chars=420, player_command=paplay_command, emit=None):
        self.engine, self.speakers, self.max_chars = engine, speakers, max_chars
        self.player_command = player_command
        self._emit_lock = threading.Lock()
        self.emit = emit or self._emit_stdout
        self.jobs = queue.Queue()
        self.muted = False
        self._gen = 0                    # bumped by stop(): anything from an older generation abandons its work
        self._player = None
        self._levels = deque()           # (monotonic time, id, level)
        self._levels_lock = threading.Lock()
        threading.Thread(target=self._worker, daemon=True).start()
        threading.Thread(target=self._level_emitter, daemon=True).start()

    def _emit_stdout(self, ev):
        with self._emit_lock:
            sys.stdout.write(json.dumps(ev) + "\n")
            sys.stdout.flush()

    # ---- commands ----
    def speak(self, id_, text, seed=0):
        if not self.muted:
            self.jobs.put((self._gen, id_, text, seed))

    def stop(self):
        self._gen += 1
        with self._levels_lock:
            self._levels.clear()
        p = self._player
        if p and p.poll() is None:
            p.kill()
        try:
            while True:
                self.jobs.get_nowait()
        except queue.Empty:
            pass

    def mute(self, on):
        self.muted = bool(on)
        if on:
            self.stop()

    def handle(self, msg):
        cmd = msg.get("cmd")
        if cmd == "speak":
            self.speak(msg.get("id", ""), str(msg.get("text", "")), int(msg.get("seed", 0)))
        elif cmd == "stop":
            self.stop()
        elif cmd == "mute":
            self.mute(msg.get("on", True))

    def serve(self, stream=sys.stdin):
        for line in stream:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("cmd") == "quit":
                break
            self.handle(msg)
        self.stop()

    # ---- playback ----
    def _worker(self):
        while True:
            gen, id_, text, seed = self.jobs.get()
            if gen != self._gen:
                continue
            try:
                self._play(gen, id_, text, seed)
            except Exception as e:  # a TTS failure must never take the process (or the goop) down
                sys.stderr.write(f"tts error: {e}\n")
            finally:
                self.emit({"type": "end", "id": id_})

    def _play(self, gen, id_, text, seed):
        text = speech_text.prepare(text, self.max_chars)
        if not text:
            return
        voice = pick_voice(self.speakers, seed)
        t_req = time.monotonic()
        player = subprocess.Popen(self.player_command(self.engine.sample_rate), stdin=subprocess.PIPE)
        self._player = player
        play_until, first = 0.0, True
        try:
            for pcm in self.engine.stream(text, voice):
                if gen != self._gen:
                    return
                now = time.monotonic()
                begin = max(play_until, now + OUT_LATENCY)
                if first:
                    first = False
                    self.emit({"type": "start", "id": id_, "ttfa_ms": round((now - t_req) * 1000)})
                frames = levels.envelope(pcm, self.engine.sample_rate, LEVEL_HZ)
                with self._levels_lock:
                    for i, v in enumerate(frames):
                        self._levels.append((begin + i / LEVEL_HZ, id_, v))
                play_until = begin + len(pcm) / 2 / self.engine.sample_rate
                player.stdin.write(pcm)
                player.stdin.flush()
            player.stdin.close()
            while player.poll() is None and gen == self._gen:    # let the last sentence finish
                time.sleep(0.02)
            while self._levels and gen == self._gen:
                time.sleep(0.02)
        finally:
            if player.poll() is None and gen != self._gen:
                player.kill()
            try:
                player.stdin.close()
            except (OSError, ValueError):
                pass
            self.emit({"type": "level", "id": id_, "v": 0})

    def _level_emitter(self):
        while True:
            time.sleep(1 / 100)
            while True:
                with self._levels_lock:
                    if not self._levels or self._levels[0][0] > time.monotonic():
                        break
                    _, id_, v = self._levels.popleft()
                self.emit({"type": "level", "id": id_, "v": round(v, 2)})
