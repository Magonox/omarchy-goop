#!/usr/bin/env python3
"""Stream the cursor position as 'x y' lines (only when it moves) so goops can look at it."""
import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop import hypr  # noqa: E402

last = None
try:
    while True:
        pos = hypr.cursor_fast()
        if pos != last:
            print(f"{pos[0]:.0f} {pos[1]:.0f}", flush=True)
            last = pos
        time.sleep(1 / 15)
except (BrokenPipeError, KeyboardInterrupt):
    pass
