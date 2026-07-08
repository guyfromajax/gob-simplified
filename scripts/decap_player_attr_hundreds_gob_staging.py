#!/usr/bin/env python3
"""
Replace capped attribute values of exactly 100 with random 88–104 on gob-staging.

Targets conferences 2–16 only (conference 1 excluded). Updates profile attrs,
CH, and matching anchor_* fields in sync. Recomputes position_ratings.

Run from repo root:
  .venv/bin/python scripts/decap_player_attr_hundreds_gob_staging.py --dry-run
  .venv/bin/python scripts/decap_player_attr_hundreds_gob_staging.py --yes
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def _load_env(filepath: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if filepath.exists():
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


for p in [ROOT / ".env.local", ROOT / ".env"]:
    for k, v in _load_env(p).items():
        os.environ.setdefault(k, v)

import random

from pymongo import MongoClient, UpdateOne

from BackEnd.utils.position_ratings import compute_position_ratings

DB_NAME = "gob-staging"
RANDOM_SEED = 42
PROFILE_ATTRS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]
SYNC_KEYS = PROFILE_ATTRS + ["CH"]


def _random_decap_value() -> int:
    """Random 88–104, excluding 100 to break cap clustering."""
    choices = [v for v in range(88, 105) if v != 100]
    return random.choice(choices)


def _count_hundreds(attrs: dict) -> int:
    total = 0
    for key, value in attrs.items():
        if isinstance(value, (int, float)) and int(value) == 100:
            total += 1
    return total


def _decap_attributes(attrs: dict) -> tuple[dict, int]:
    """Return updated attrs and number of profile/anchor pairs adjusted."""
    updated = dict(attrs)
    replacements = 0

    for key in SYNC_KEYS:
        anchor_key = f"anchor_{key}"
        current = updated.get(key)
        anchor = updated.get(anchor_key)
        hit = (
            isinstance(current, (int, float)) and int(current) == 100
        ) or (
            isinstance(anchor, (int, float)) and int(anchor) == 100
        )
        if not hit:
            continue
        new_val = _random_decap_value()
        updated[key] = new_val
        updated[anchor_key] = new_val
        replacements += 1

    for key, value in list(updated.items()):
        if key in SYNC_KEYS or key.startswith("anchor_"):
            continue
        if isinstance(value, (int, float)) and int(value) == 100:
            updated[key] = _random_decap_value()
            replacements += 1

    return updated, replacements


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replace attribute values of 100 with random 88–104 (conf 2–16)"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.yes:
        print("Pass --yes to write, or --dry-run to preview.", file=sys.stderr)
        return 1

    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("MONGO_URI not set", file=sys.stderr)
        return 1

    random.seed(RANDOM_SEED)

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[DB_NAME]

    conf1_names = {
        t["name"] for t in db.teams.find({"conference": 1}, {"name": 1})
    }
    players = list(
        db.players.find(
            {"team": {"$nin": list(conf1_names)}},
            {"attributes": 1, "height": 1, "team": 1},
        )
    )

    before_hundreds = sum(_count_hundreds(p.get("attributes") or {}) for p in players)
    key_counter: Counter[str] = Counter()
    ops: list[UpdateOne] = []
    players_changed = 0
    pairs_adjusted = 0
    after_hundreds = 0

    for player in players:
        attrs = player.get("attributes") or {}
        if _count_hundreds(attrs) == 0:
            after_hundreds += _count_hundreds(attrs)
            continue

        new_attrs, adjusted = _decap_attributes(attrs)
        after_hundreds += _count_hundreds(new_attrs)
        if adjusted == 0:
            continue

        for key in SYNC_KEYS:
            if isinstance(attrs.get(key), (int, float)) and int(attrs[key]) == 100:
                key_counter[key] += 1

        height = player.get("height")
        ratings = compute_position_ratings(
            {"height": height, "attributes": new_attrs},
            profile="player",
        )

        players_changed += 1
        pairs_adjusted += adjusted
        ops.append(
            UpdateOne(
                {"_id": player["_id"]},
                {"$set": {"attributes": new_attrs, "position_ratings": ratings}},
            )
        )

    print(f"Rewrite pool: {len(players)} players (conf 2–16)")
    print(f"Values exactly 100 before: {before_hundreds}")
    print(f"Players to update: {players_changed}")
    print(f"Synced profile/CH pairs adjusted: {pairs_adjusted}")
    print("Top capped attrs replaced:")
    for key, count in key_counter.most_common(10):
        print(f"  {key}: {count}")
    print(f"Values exactly 100 after: {after_hundreds}")

    if args.dry_run:
        print(f"Dry run OK — would write {len(ops)} updates.")
        return 0

    if not ops:
        print("Nothing to update.")
        return 0

    result = db.players.bulk_write(ops, ordered=False)
    meta = {
        "_id": "latest",
        "script": "decap_player_attr_hundreds_gob_staging.py",
        "random_seed": RANDOM_SEED,
        "players_updated": players_changed,
        "pairs_adjusted": pairs_adjusted,
        "hundreds_before": before_hundreds,
        "completed_at": datetime.now(timezone.utc),
    }
    db.players_decap_meta.replace_one({"_id": "latest"}, meta, upsert=True)

    print(f"Modified {result.modified_count} player documents.")
    print("Metadata written to players_decap_meta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
