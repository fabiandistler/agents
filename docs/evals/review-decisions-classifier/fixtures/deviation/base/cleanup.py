"""Delete export files older than the retention period."""

import argparse
import time
from pathlib import Path

RETENTION_DAYS = 30


def old_files(folder: Path, days: int) -> list[Path]:
    cutoff = time.time() - days * 86400
    return [path for path in folder.glob("*.csv") if path.stat().st_mtime < cutoff]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--days", type=int, default=RETENTION_DAYS)
    args = parser.parse_args()
    for path in old_files(args.folder, args.days):
        path.unlink()


if __name__ == "__main__":
    main()
