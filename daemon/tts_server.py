#!/usr/bin/env python3
"""The goops' voice. Run with the project venv (it has piper-tts):  .venv/bin/python daemon/tts_server.py
Protocol is in goop/tts/server.py. Exits quietly if TTS is disabled in config or the engine is not installed."""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop import config  # noqa: E402
from goop.tts import engine as engines  # noqa: E402
from goop.tts.server import Server  # noqa: E402


def main():
    cfg = config.tts()
    if not cfg["enabled"]:
        return print(json.dumps({"type": "disabled"}), flush=True)
    eng = engines.get(cfg)
    if not eng.available():
        return print(json.dumps({"type": "unavailable", "why": "piper-tts or the voice model is missing"}), flush=True)
    t0 = time.monotonic()
    for _ in eng.stream("Ready.", cfg["speakers"][0] if cfg["speakers"] else 0):   # load the model and pay first-call costs now
        pass
    print(json.dumps({"type": "ready", "engine": eng.name, "load_s": round(time.monotonic() - t0, 2)}), flush=True)
    Server(eng, cfg["speakers"], cfg["max_chars"]).serve()


if __name__ == "__main__":
    main()
