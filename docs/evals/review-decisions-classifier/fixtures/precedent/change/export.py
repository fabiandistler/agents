"""Export the day's orders as CSV."""

import csv
import datetime
import json
import sys
from pathlib import Path


def _log(message: str, **fields: object) -> None:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record = {"time": now, "msg": message, **fields}
    print(json.dumps(record), file=sys.stdout)


def export_orders(orders: list[dict], target: Path) -> None:
    try:
        with target.open("w", newline="") as out:
            writer = csv.DictWriter(out, fieldnames=["id", "total"])
            writer.writeheader()
            writer.writerows(orders)
    except OSError as err:
        _log("export failed", target=str(target), error=type(err).__name__)
        raise
    _log("export done", rows=len(orders))
