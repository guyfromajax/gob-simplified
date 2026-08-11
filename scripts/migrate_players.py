#!/usr/bin/env python3
"""Compatibility entry point for destructive universal-player JSON replacement.

Explicit files are required; the former implicit ``teams/*.json`` sweep could mix
production and staging variants of the same roster.
"""
import argparse
from datetime import datetime, timezone
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from BackEnd.script_db import connect_script_database
from scripts.maintain_universal_roster import replace_players
from scripts.publish_universal_data import _validate_backup_root, _write_backup

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    ap.add_argument("--file", action="append", type=Path, required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--confirm-db")
    ap.add_argument("--backup-dir", type=Path)
    args = ap.parse_args()
    conn = connect_script_database(
        target=args.db, access="write" if args.apply else "read",
        destructive=args.apply, confirm_db=args.confirm_db,
        pristine_env=dict(os.environ), repo_root=ROOT,
    )
    if args.apply:
        root = _validate_backup_root(args.backup_dir)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = root / f"{args.db}-before-player-replacement-{stamp}"
        run_dir.mkdir(mode=0o700)
        print(f"[BACKUP] {_write_backup(run_dir, 'players', list(conn.database['players'].find({})))}")
    print(replace_players(
        conn.database["players"], conn.database["teams"], args.file, apply=args.apply
    ))
    conn.close()
