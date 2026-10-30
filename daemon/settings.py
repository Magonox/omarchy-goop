#!/usr/bin/env python3
"""settings.py get [key]  |  settings.py set <key> <value>      (e.g. set animations off, set tts.speed 0.9)"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop import config, settings  # noqa: E402

args = sys.argv[1:]
try:
    if args[:1] == ["get"]:
        print(json.dumps(settings.get_value(args[1]) if len(args) > 1 else config.load(), indent=2))
    elif args[:1] == ["set"] and len(args) == 3:
        print(json.dumps(settings.set_value(args[1], args[2])))
    else:
        sys.exit(__doc__)
except ValueError as e:
    sys.exit(f"error: {e}")
