#!/usr/bin/env python3
"""Measure how fast each Piper speaker talks and write the pace table Goop uses to even them out.
  .venv/bin/python daemon/calibrate_voices.py --all       every speaker's natural pace, with the stretch predicted for each (several minutes); writes goop/tts/pace_<model>.json
  .venv/bin/python daemon/calibrate_voices.py --refine    runs each speaker at its predicted stretch and corrects it once from its own response (several more minutes)
  .venv/bin/python daemon/calibrate_voices.py 0 112 233   just these: prints natural pace and where the table would put them"""
import argparse, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop import config  # noqa: E402
from goop.tts import engine as engines, pace  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("ids", nargs="*", type=int)
ap.add_argument("--all", action="store_true")
ap.add_argument("--refine", action="store_true")
a = ap.parse_args()
cfg = config.tts()
eng = engines.PiperEngine(cfg["model"], speed=1.0, pause_ms=0, even_pace=False)
if not eng.available():
    sys.exit("piper-tts or the voice model is missing")
path = pace.shipped_path(cfg["model"])


def progress(n, total, t0):
    if n % 50 == 0:
        print(f"  {n}/{total} speakers, {time.time() - t0:.0f}s", file=sys.stderr, flush=True)


def save(table):
    with open(path, "w") as f:
        json.dump(table, f, separators=(",", ":"))


if a.refine:
    table = json.load(open(path))
    target, cps = table["target"], {int(k): v for k, v in table["cps"].items()}
    factors, t0 = {}, time.time()
    for n, sid in enumerate(sorted(cps), 1):
        f0 = pace.predicted_factor(cps[sid], target)
        factors[sid] = pace.refined_factor(cps[sid], target, f0, pace.measure(eng, sid, f0)) if abs(f0 - 1) > 0.04 else f0
        progress(n, len(cps), t0)
    save(pace.build_table(cps, factors) | {"target": target})
    print(f"refined {len(factors)} speakers -> {path}")
elif a.all:
    ids, rates, t0 = eng.voices(), {}, time.time()
    for n, sid in enumerate(ids, 1):
        rates[sid] = pace.measure(eng, sid)
        progress(n, len(ids), t0)
    save(pace.build_table(rates))
    print(f"wrote {path}: {len(rates)} speakers, target {pace.build_table(rates)['target']} characters per second")
else:
    ids = a.ids or cfg["speakers"]
    rates = {sid: pace.measure(eng, sid) for sid in ids}
    target = json.load(open(path))["target"] if os.path.exists(path) else sorted(rates.values())[len(rates) // 2]
    for sid, cps in rates.items():
        f = pace.predicted_factor(cps, target)
        print(f"speaker {sid:4}  natural {cps:5.1f} chars/s   predicted stretch {f:.2f}   -> about {cps * f ** -pace.ELASTICITY:5.1f}")
