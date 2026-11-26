"""Structured logging shared by every job."""

import json
import sys
import time


def log_event(event: str, **fields: object) -> None:
    """Write one JSON line to stderr: ts in epoch seconds, event, then fields."""
    record = {"ts": time.time(), "event": event, **fields}
    sys.stderr.write(json.dumps(record) + "\n")
