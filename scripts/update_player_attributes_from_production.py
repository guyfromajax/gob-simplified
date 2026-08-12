#!/usr/bin/env python3
"""Compatibility entry point for the historical production attribute profile."""
import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target
from scripts.maintain_universal_roster import TEAMS_DIR, sync_attribute_profile

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--teams-dir", type=Path, default=TEAMS_DIR)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    conn = connect_migration_target("gob", write=args.apply)
    print(sync_attribute_profile(conn.database["players"], "production", args.teams_dir, apply=args.apply))
    conn.close()
