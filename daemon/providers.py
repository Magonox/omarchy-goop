#!/usr/bin/env python3
"""List the configured agents and check that they work.

  providers.py              which providers exist and whether each is ready (key present, etc.)
  providers.py --test NAME  send a tiny request to NAME and report what came back (checks URL, model and key)
"""
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop import config  # noqa: E402
from goop.agent import registry  # noqa: E402
from goop.agent.base import AgentRequest  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--test")
a = ap.parse_args()
active = config.load().get("provider", "claude")

if not a.test:
    for n in registry.names():
        p = registry.get(n)
        why = "" if p.available() else "  <- " + (getattr(p, "problem", lambda: "claude CLI not found")() or "not available")
        print(f"{'*' if n == active else ' '} {n:12} {'ready' if p.available() else 'NOT READY'}{why}")
    sys.exit()

p = registry.get(a.test)
req = AgentRequest(command="hi", packet={}, window_address="0x0", system="Reply with one short sentence.", prompt="Say hello.", model=config.load().get("model"))
for ev in p.run(req):
    if ev["type"] in ("done", "error"):
        print(ev["type"].upper() + ":", ev.get("text") or ev.get("message"))
