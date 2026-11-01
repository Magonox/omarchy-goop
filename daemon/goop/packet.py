"""Assemble the context packet for a dropped-on window."""
import time

from . import classify, config, proc, screenshot
from .adapters import browser, folder, terminal

VERSION = 1


def window_summary(w):
    return {k: w.get(k) for k in ("address", "class", "title", "pid", "at", "size", "floating")} | {"workspace": w["workspace"]["id"]}


def build(window, snap=None, shots=True):
    pkt = {"version": VERSION, "ts": time.time(), "window": window_summary(window), "screenshot": None}
    if config.is_denied(window):
        return pkt | {"app_type": "denied", "adapter": None, "confidence": "high", "context": {},
                      "notes": ["window matches the privacy deny list; nothing was read or captured"]}
    kind = classify.app_type(window.get("class"))
    pkt["app_type"] = kind
    if kind == "terminal":
        ctx, conf = terminal.collect(window, snap or proc.snapshot())
    elif kind == "file_manager":
        ctx, conf = folder.collect(window)
    elif kind == "browser":
        ctx, conf = browser.collect(window)          # the page text from the Goop page reader, when it is installed
        if conf == "low" and shots:
            pkt["screenshot"] = screenshot.capture(window)
    else:
        # editors and others: no text adapter yet, so a screenshot is the context
        ctx, conf = {"notes": ["no text adapter for this app yet; screenshot only"]}, "low"
        if shots:
            pkt["screenshot"] = screenshot.capture(window)
    pkt.update(adapter=kind, confidence=conf, notes=ctx.pop("notes", []), context=ctx)
    return pkt
