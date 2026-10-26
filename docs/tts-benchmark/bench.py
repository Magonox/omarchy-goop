#!/usr/bin/env python3
"""CPU benchmark of small on-device TTS engines, using goop-style sentences.

  python bench.py                 run every engine (each in its own process) and print a table
  python bench.py --engine NAME   run one engine, print JSON (used internally)

Per engine: load time, then for each sentence: median synth time over 3 timed runs (after 1 warm-up), audio length,
real-time factor (synth time / audio time; below 1.0 means faster than real time), and peak RSS. WAVs go to out/.
"""
import argparse, json, os, resource, statistics, subprocess, sys, time

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

SENTENCES = {
    "short": "Done! I found six files.",
    "first": "I ran the command in your terminal.",   # what time-to-first-audio is measured on when streaming by sentence
    "long": ("This is your Pictures folder. It holds thirteen screenshots named by date and time, from October ninth to the "
             "twenty sixth. The biggest one is about three megabytes, and nothing looks out of place."),
}
RUNS = 3


def load(name):
    """-> synth(text) -> (float32 mono array, sample rate)"""
    if name.startswith("piper-"):
        from piper import PiperVoice
        voice = PiperVoice.load(os.path.join(HERE, "models/piper", name.removeprefix("piper-") + ".onnx"))
        def synth(text):
            chunks = list(voice.synthesize(text))
            return np.concatenate([c.audio_float_array for c in chunks]), chunks[0].sample_rate
        return synth
    if name == "kokoro-int8":
        from kokoro_onnx import Kokoro
        k = Kokoro(os.path.join(HERE, "models/kokoro/kokoro-v1.0.int8.onnx"), os.path.join(HERE, "models/kokoro/voices-v1.0.bin"))
        return lambda text: k.create(text, voice="af_heart", speed=1.0, lang="en-us")
    if name.startswith("supertonic-"):
        from supertonic import TTS
        steps = int(name.split("-")[1].removeprefix("s"))
        tts = TTS(auto_download=False)
        style = tts.get_voice_style("M1")
        def synth(text):
            wav, _ = tts.synthesize(text, voice_style=style, total_steps=steps, lang="en")
            return np.asarray(wav, dtype=np.float32).reshape(-1), tts.sample_rate
        return synth
    if name == "kitten-nano":
        # kitten's phonemizer wants a system espeak-ng; reuse the copy bundled with kokoro-onnx instead of installing one
        import espeakng_loader
        os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = espeakng_loader.get_library_path()
        os.environ["ESPEAK_DATA_PATH"] = espeakng_loader.get_data_path()
        from kittentts import KittenTTS
        m = KittenTTS()
        return lambda text: (np.asarray(m.generate(text, voice="expr-voice-2-m"), dtype=np.float32).reshape(-1), 24000)
    raise SystemExit(f"unknown engine {name}")


def run_one(name):
    t0 = time.perf_counter()
    synth = load(name)
    result = {"engine": name, "load_s": round(time.perf_counter() - t0, 2), "sentences": {}}
    os.makedirs(OUT, exist_ok=True)
    for key, text in SENTENCES.items():
        synth(text)                                   # warm-up (first call pays one-time costs)
        times = []
        for _ in range(RUNS):
            t = time.perf_counter()
            audio, sr = synth(text)
            times.append(time.perf_counter() - t)
        secs = len(audio) / sr
        med = statistics.median(times)
        result["sentences"][key] = {"synth_s": round(med, 3), "audio_s": round(secs, 2), "rtf": round(med / secs, 3)}
        sf.write(os.path.join(OUT, f"{name}-{key}.wav"), audio, sr)
    result["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
    print(json.dumps(result))


ENGINES = ["piper-en_US-lessac-low", "piper-en_US-lessac-medium", "piper-en_US-libritts_r-medium", "kokoro-int8",
           "supertonic-s2", "supertonic-s5", "supertonic-s8", "kitten-nano"]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine")
    a = ap.parse_args()
    if a.engine:
        run_one(a.engine)
        sys.exit()
    rows = []
    for e in ENGINES:
        print(f"... {e}", file=sys.stderr, flush=True)
        p = subprocess.run([sys.executable, __file__, "--engine", e], capture_output=True, text=True, timeout=900)
        line = next((l for l in p.stdout.splitlines() if l.startswith("{")), None)
        if not line:
            print(f"!!! {e} failed: {(p.stderr or p.stdout).strip().splitlines()[-1:]}", file=sys.stderr)
            continue
        rows.append(json.loads(line))
    json.dump(rows, open(os.path.join(HERE, "results.json"), "w"), indent=2)
    print(f"{'engine':32} {'load':>6} {'first-sentence':>15} {'short rtf':>10} {'long rtf':>9} {'RAM MB':>7}")
    for r in rows:
        s = r["sentences"]
        print(f"{r['engine']:32} {r['load_s']:>5}s {s['first']['synth_s']:>14}s {s['short']['rtf']:>10} {s['long']['rtf']:>9} {r['peak_rss_mb']:>7}")
