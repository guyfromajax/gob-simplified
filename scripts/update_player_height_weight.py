#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection


def load_team_players(teams_dir: Path) -> list[Dict[str, Any]]:
    """Read all team JSON files and return a flat list of player dicts with team name attached."""
    players: list[Dict[str, Any]] = []
    for path in sorted(teams_dir.glob("*.json")):
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        team_name = data.get("name")
        roster = data.get("players", [])
        if not team_name or not isinstance(roster, list):
            continue

        for p in roster:
            # Normalize & keep only what we need
            rec = {
                "team": team_name,
                "first_name": p.get("first_name"),
                "last_name": p.get("last_name"),
                "jersey": p.get("jersey"),
                "height": p.get("height"),
                "weight": p.get("weight"),
            }
            players.append(rec)
    return players


def build_filters(p: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Primary filter by team+first_name+last_name; fallback filter by team+jersey."""
    primary = None
    fallback = None

    if p.get("team") and p.get("first_name") and p.get("last_name"):
        primary = {
            "team": p["team"],
            "first_name": p["first_name"],
            "last_name": p["last_name"],
        }
    if p.get("team") and p.get("jersey") is not None:
        fallback = {
            "team": p["team"],
            "jersey": p["jersey"],
        }
    return primary, fallback


def coerce_int(val) -> Optional[int]:
    try:
        if val is None:
            return None
        return int(val)
    except Exception:
        return None


def plan_updates(players: list[Dict[str, Any]], coll: Collection, dry_run: bool) -> Tuple[int, int, int]:
    matched = 0
    updated = 0
    missing = 0

    bulk_ops: list[UpdateOne] = []

    for p in players:
        h = coerce_int(p.get("height"))
        w = coerce_int(p.get("weight"))
        if h is None and w is None:
            # Nothing to set for this player
            continue

        filt1, filt2 = build_filters(p)
        doc = None
        if filt1:
            doc = coll.find_one({**filt1, "first_name": {"$exists": True}, "last_name": {"$exists": True}})
        if doc is None and filt2:
            doc = coll.find_one({**filt2, "first_name": {"$exists": True}, "last_name": {"$exists": True}})

        if not doc:
            missing += 1
            print(f"MISS: {p['team']} — {p.get('first_name','?')} {p.get('last_name','?')} "
                  f"(jersey {p.get('jersey')}) not found")
            continue

        matched += 1

        to_set = {}
        if h is not None:
            to_set["height"] = h
        if w is not None:
            to_set["weight"] = w

        # Idempotent: only $set the fields
        bulk_ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": to_set}))

        # Helpful log for dry-run
        if dry_run:
            print(f"PLAN: {_name_line(doc)}  ->  set {to_set}")

    if not dry_run and bulk_ops:
        res = coll.bulk_write(bulk_ops, ordered=False)
        updated = res.modified_count

    return matched, updated, missing


def _name_line(doc: Dict[str, Any]) -> str:
    return f"{doc.get('team')} — {doc.get('first_name','?')} {doc.get('last_name','?')} (jersey {doc.get('jersey')})"


def main():
    ap = argparse.ArgumentParser(description="Sync height/weight from BackEnd/teams JSON into Mongo players.")
    ap.add_argument("--mongo", default="mongodb://localhost:27017", help="Mongo URI")
    ap.add_argument("--db", default="gob", help="Database name")
    ap.add_argument("--collection", default="players", help="Players collection name")
    ap.add_argument("--teams-dir", default="teams", help="Path to teams JSON directory")
    ap.add_argument("--dry-run", action="store_true", help="Do not write; just print planned changes")
    args = ap.parse_args()

    teams_dir = Path(args.teams_dir).resolve()
    if not teams_dir.exists():
        raise SystemExit(f"Teams directory not found: {teams_dir}")

    client = MongoClient(args.mongo)
    coll = client[args.db][args.collection]

    players = load_team_players(teams_dir)
    print(f"Loaded {len(players)} roster entries from {teams_dir}")

    matched, updated, missing = plan_updates(players, coll, args.dry_run)

    print("\n--- Summary ---")
    print(f"Matched docs: {matched}")
    if args.dry_run:
        print(f"Would update: {matched - missing} (dry-run; no writes performed)")
    else:
        print(f"Updated docs: {updated}")
    print(f"Not found:    {missing}")


if __name__ == "__main__":
    main()

