#!/usr/bin/env python3
"""
Update a curated list of universal players in gob.players and gob-staging.players
from teams/all_players_with_team_names.txt.

Safety:
- Only updates the explicitly named players below.
- Matches by first_name, last_name, and team.
- Does not delete or replace any collections or documents.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[1]
TXT_PATH = ROOT / "teams" / "all_players_with_team_names.txt"
TARGET_DBS = ("gob", "gob-staging")
TARGET_PLAYERS = (
    "Delmont Braggs",
)
ATTR_KEYS = ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT")
IDX = {
    "first_name": 0,
    "last_name": 1,
    "year": 2,
    "jersey": 3,
    "height": 4,
    "weight": 5,
    "SC": 6,
    "SH": 7,
    "ID": 8,
    "OD": 9,
    "PS": 10,
    "BH": 11,
    "RB": 12,
    "ST": 13,
    "AG": 14,
    "ND": 15,
    "IQ": 16,
    "FT": 17,
    "team": 18,
}


def _load_env(filepath: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not filepath.exists():
        return values
    for raw_line in filepath.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _load_mongo_uri() -> str:
    for env_file in (ROOT / ".env.local", ROOT / ".env"):
        for key, value in _load_env(env_file).items():
            os.environ.setdefault(key, value)
    uri = os.environ.get("MONGO_URI")
    if not uri:
        raise RuntimeError("MONGO_URI not found in environment, .env.local, or .env")
    return uri


def _int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_target_rows() -> dict[str, dict]:
    if not TXT_PATH.exists():
        raise FileNotFoundError(f"Source file not found: {TXT_PATH}")
    lines = TXT_PATH.read_text().splitlines()
    if len(lines) < 2:
        raise ValueError("Source file does not contain any player rows")

    rows: dict[str, dict] = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) <= IDX["team"]:
            continue
        full_name = f"{parts[IDX['first_name']].strip()} {parts[IDX['last_name']].strip()}".strip()
        if full_name not in TARGET_PLAYERS:
            continue
        attrs = {key: _int(parts[IDX[key]], 0) for key in ATTR_KEYS}
        rows[full_name] = {
            "first_name": parts[IDX["first_name"]].strip(),
            "last_name": parts[IDX["last_name"]].strip(),
            "team": parts[IDX["team"]].strip(),
            "year": parts[IDX["year"]].strip().lower(),
            "jersey": _int(parts[IDX["jersey"]], 0),
            "height": _int(parts[IDX["height"]], 0),
            "weight": _int(parts[IDX["weight"]], 0),
            "attributes": attrs,
        }

    missing = [name for name in TARGET_PLAYERS if name not in rows]
    if missing:
        raise ValueError(f"Missing target players in source file: {missing}")
    return rows


def _compute_position_ratings(player_row: dict) -> dict:
    sys.path.insert(0, str(ROOT))
    from BackEnd.utils.position_ratings import compute_position_ratings

    return compute_position_ratings(
        {
            "height": player_row["height"],
            "attributes": dict(player_row["attributes"]),
            "name": f"{player_row['first_name']} {player_row['last_name']}",
        }
    )


def main() -> int:
    uri = _load_mongo_uri()
    rows = _parse_target_rows()
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)

    print(f"[info] Loaded {len(rows)} target rows from {TXT_PATH}")
    total_modified = 0

    for db_name in TARGET_DBS:
        db = client[db_name]
        coll = db["players"]
        print(f"[info] Updating {db_name}.players")

        for full_name in TARGET_PLAYERS:
            row = rows[full_name]
            query = {
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "team": row["team"],
            }
            matches = list(coll.find(query, {"_id": 1}))
            if len(matches) != 1:
                raise RuntimeError(
                    f"{db_name}.players expected exactly 1 match for {full_name} ({row['team']}), found {len(matches)}"
                )

            position_ratings = _compute_position_ratings(row)
            set_doc = {
                "year": row["year"],
                "jersey": row["jersey"],
                "height": row["height"],
                "weight": row["weight"],
                "position_ratings": position_ratings,
            }
            for attr_key, attr_value in row["attributes"].items():
                set_doc[f"attributes.{attr_key}"] = attr_value

            result = coll.update_one({"_id": matches[0]["_id"]}, {"$set": set_doc})
            total_modified += result.modified_count
            print(
                f"  - {full_name} ({row['team']}): matched={result.matched_count} modified={result.modified_count}"
            )

    print(f"[done] Total modified documents across both DBs: {total_modified}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
