#!/usr/bin/env python3
"""Window geometry for the shell: which windows exist, where, and whether they are on screen."""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop import approvals, hypr  # noqa: E402

clients, ws = hypr.snapshot()
wins = [
    {"address": c["address"], "x": c["at"][0], "y": c["at"][1], "w": c["size"][0], "h": c["size"][1],
     "visible": c["workspace"]["id"] in ws, "monitor": c.get("monitor", 0)}
    for c in clients if c["mapped"] and not c["hidden"]
]
monitors = [hypr.monitor_summary(m) for m in hypr.hypr("monitors")]
try:
    active = hypr.hypr("activewindow").get("address")
except Exception:
    active = None
print(json.dumps({"active": active, "windows": wins, "monitors": monitors, "approvals": approvals.pending()}))
