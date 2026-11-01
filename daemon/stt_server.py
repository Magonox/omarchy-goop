#!/usr/bin/env python3
"""goop's ears. Run with the project venv (it has moonshine-voice):  ~/.local/share/goop/venv/bin/python daemon/stt_server.py
Protocol is in goop/stt/server.py. Exits quietly if voice input is switched off or the engine is not installed."""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop import config  # noqa: E402
from goop.stt import engine as engines  # noqa: E402
from goop.stt.server import Server  # noqa: E402


def main():
    cfg = config.stt()
    if not cfg["enabled"]:
        return print(json.dumps({"type": "disabled"}), flush=True)
    eng = engines.get(cfg)
    if not eng.available():
        return print(json.dumps({"type": "unavailable", "why": "moonshine-voice is not installed (run setup.sh)"}), flush=True)
    t0 = time.monotonic()
    try:
        eng.load()
    except Exception as e:
        return print(json.dumps({"type": "unavailable", "why": f"the speech model could not be loaded: {str(e)[:120]}"}), flush=True)
    print(json.dumps({"type": "ready", "engine": eng.name, "model": cfg["model"], "load_s": round(time.monotonic() - t0, 2)}), flush=True)
    def title_of(address):
        """The words on screen: the window's title and, in a browser, the page's own text (when the page reader is installed)."""
        from goop import classify, hypr
        from goop.adapters import browser
        clients, _ = hypr.snapshot()
        w = next((c for c in clients if c["address"] == address), None)
        if not w:
            return ""
        words = f"{w.get('title', '')} {w.get('class', '')}".strip()
        if classify.app_type(w.get("class")) == "browser":
            r = browser.read(w.get("title") or "", 3000, timeout=0.8)
            if r.get("ok"):
                words += " " + " ".join([r.get("title", ""), " ".join(r.get("headings", [])), r.get("text", "")])
        return words
    Server(eng, cfg, context_for=title_of).serve()


if __name__ == "__main__":
    main()
