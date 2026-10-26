#!/usr/bin/env python3
"""answer.py <approval-id> yes|no   (called by the shell when you click Approve or Deny)"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop import approvals  # noqa: E402

approvals.answer(sys.argv[1], sys.argv[2] == "yes")
