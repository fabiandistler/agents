"""Export the day's orders as CSV."""

import csv
from pathlib import Path


def export_orders(orders: list[dict], target: Path) -> None:
    with target.open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=["id", "total"])
        writer.writeheader()
        writer.writerows(orders)
