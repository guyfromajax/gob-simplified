#!/usr/bin/env python3
"""Compatibility entry point for universal-player position-rating maintenance."""
import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target
from scripts.maintain_universal_roster import recalculate_ratings

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    conn = connect_migration_target(args.db, write=args.apply)
    print(recalculate_ratings(conn.database["players"], apply=args.apply))
    conn.close()
