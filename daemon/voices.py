#!/usr/bin/env python3
"""Audition Piper speakers. Run with the project venv:

  .venv/bin/python daemon/voices.py 0 112 233         play these speaker ids
  .venv/bin/python daemon/voices.py --random 12       12 random ones (prints their ids; seed with --seed)
  .venv/bin/python daemon/voices.py --current         the voices the goops use now (config "tts.speakers")

Then put the ids you like into ~/.config/goop/config.json:  {"tts": {"speakers": [0, 112, 233]}}
"""
import argparse, os, random, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop import config  # noqa: E402
from goop.tts import engine as engines  # noqa: E402
from goop.tts.server import paplay_command  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("ids", nargs="*", type=int)
ap.add_argument("--random", type=int, metavar="N")
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--current", action="store_true")
a = ap.parse_args()

cfg = config.tts()
eng = engines.get(cfg)
if not eng.available():
    sys.exit("piper-tts or the voice model is missing")
ids = a.ids
if a.current:
    ids = cfg["speakers"]
elif a.random:
    ids = random.Random(a.seed).sample(eng.voices(), a.random)
if not ids:
    ap.error("give speaker ids, --random N, or --current")

for sid in ids:
    print(f"speaker {sid}", flush=True)
    player = subprocess.Popen(paplay_command(eng.sample_rate), stdin=subprocess.PIPE)
    for pcm in eng.stream(f"Hi, I'm a goop. This is speaker {sid}.", sid):
        player.stdin.write(pcm)
    player.stdin.close()
    player.wait()
    time.sleep(0.5)
