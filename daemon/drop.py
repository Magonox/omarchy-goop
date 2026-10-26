#!/usr/bin/env python3
"""Hit-test the window under the cursor, build its context packet, print a summary.

  drop.py                      window under the cursor (what the shell calls on drop)
  drop.py --cursor X,Y         pretend the cursor is at X,Y
  drop.py --address 0xADDR     skip hit-testing, use this window
  drop.py --full               print the whole packet instead of a summary
The full packet is always written to ~/.cache/goop/last_packet.json.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop import hypr, packet  # noqa: E402

OUT = os.path.expanduser("~/.cache/goop/last_packet.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cursor")
    ap.add_argument("--address")
    ap.add_argument("--full", action="store_true")
    a = ap.parse_args()

    clients, ws = hypr.snapshot()
    if a.address:
        window = next((c for c in clients if c["address"] == a.address), None)
    else:
        cx, cy = map(float, a.cursor.split(",")) if a.cursor else hypr.cursor()
        window = hypr.window_at(cx, cy, clients, ws)

    if not window:
        pkt = {"version": packet.VERSION, "app_type": "none", "notes": ["no window under the cursor"]}
    else:
        pkt = packet.build(window)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(pkt, f, indent=2)

    if a.full:
        print(json.dumps(pkt, indent=2))
    else:
        w = pkt.get("window") or {}
        print(json.dumps({"app_type": pkt["app_type"], "address": w.get("address"), "class": w.get("class"), "title": w.get("title"),
                          "confidence": pkt.get("confidence"), "packet": OUT}))


if __name__ == "__main__":
    main()
