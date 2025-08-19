#!/usr/bin/env python3
"""Backfill legacy franchise documents to the new player_stats schema."""

import argparse
import os
import sys

# Ensure BackEnd package is importable when running as a script
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from BackEnd.db import db
from BackEnd.utils.stat_updater import backfill_franchise_player_stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate franchise documents to the new player_stats schema",
    )
    parser.add_argument(
        "--franchise-id",
        help="Optional specific franchise _id to migrate. If omitted, all franchises are processed.",
    )
    args = parser.parse_args()

    if args.franchise_id:
        backfill_franchise_player_stats(args.franchise_id)
        print(f"Updated franchise {args.franchise_id}")
    else:
        for doc in db["franchises"].find({}):
            fid = doc.get("_id")
            backfill_franchise_player_stats(fid)
            print(f"Updated franchise {fid}")
    print("Backfill complete")


if __name__ == "__main__":
    main()
