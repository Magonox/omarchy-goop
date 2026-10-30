#!/usr/bin/env python3
"""Print what goop needs and what is missing, as JSON: {"checks": [...], "providers": [...]}."""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop import config, doctor  # noqa: E402
from goop.agent import registry  # noqa: E402

active = config.load().get("provider", "claude")
provs = doctor.providers(registry, active)
current = next((p for p in provs if p["active"]), None)
problem = None if (current and current["ready"]) else (current["problem"] if current else f"unknown agent {active!r}")
print(json.dumps({"checks": doctor.checks(active, problem), "providers": provs, "active": active}))
