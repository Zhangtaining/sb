#!/usr/bin/env python3
"""Run Alembic migrations to initialise / upgrade the database schema.

Usage:
    python scripts/setup_db.py          # upgrades to head
    python scripts/setup_db.py --check  # prints current revision
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up the gym database schema")
    parser.add_argument(
        "--check", action="store_true", help="Print current Alembic revision and exit"
    )
    args = parser.parse_args()

    if args.check:
        result = subprocess.run(
            ["uv", "run", "alembic", "current"], capture_output=True, text=True
        )
        print(result.stdout or result.stderr)
        sys.exit(result.returncode)

    print("Running Alembic migrations…")
    result = subprocess.run(["uv", "run", "alembic", "upgrade", "head"], check=False)
    if result.returncode != 0:
        print("Migration failed. Is the database running? (make dev-up)", file=sys.stderr)
        sys.exit(1)
    print("Database schema is up to date.")


if __name__ == "__main__":
    main()
