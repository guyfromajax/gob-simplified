#!/usr/bin/env python3
"""Batch universal-pool edits from player_attribute_changes.mc (2026-08-12).

Attribute digit rule (display 0–10 → raw 0–100):
    new = min(100, digit * 10 + (current % 10))
Example: SH 44 + direction 1 → 14.

Also: Omar Nola ↔ CJ Castleman full attributes+height+weight swap; Omar → junior.
HT/WT/year are absolute sets (not digit-mapped).

Targets: gob-staging.players and gob.players. Dry-run default.

Usage:
    .venv/bin/python scripts/batch_pool_edits_20260812.py
    .venv/bin/python scripts/batch_pool_edits_20260812.py --commit --confirm-db gob-staging
    .venv/bin/python scripts/batch_pool_edits_20260812.py --commit --confirm-db gob
    .venv/bin/python scripts/batch_pool_edits_20260812.py --commit --confirm-db both
"""

from __future__ import annotations

import argparse
import copy
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from pymongo import MongoClient
from pymongo.operations import UpdateOne

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.utils.position_ratings import compute_position_ratings  # noqa: E402

ATTR_KEYS = ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT")
YEAR_CANON = {
    "junior": "junior",
    "senior": "senior",
    "sophomore": "sophomore",
    "freshman": "freshman",
}

# (team, first, last) → edits
# attributes: display digits 0–10; height/weight/year absolute; swap_with for full swap partner
EDITS: list[dict[str, Any]] = [
    # Bentley-Truman — swap first (applied specially), then year on Omar
    {
        "team": "Bentley-Truman",
        "first_name": "Omar",
        "last_name": "Nola",
        "swap_with": ("CJ", "Castleman"),
        "year": "junior",
    },
    {
        "team": "Bentley-Truman",
        "first_name": "CJ",
        "last_name": "Castleman",
        # partner side of swap; no extra field sets
    },
    {
        "team": "Bentley-Truman",
        "first_name": "Kent",
        "last_name": "McManus",
        "attributes": {"SC": 1, "SH": 8, "ID": 1, "OD": 2, "FT": 9},
    },
    {
        "team": "Bentley-Truman",
        "first_name": "Ronnie",
        "last_name": "Rozier",
        "attributes": {"SC": 5},
    },
    {
        "team": "Bentley-Truman",
        "first_name": "Xenon",
        "last_name": "Fletcher",
        "attributes": {"ID": 2, "PS": 6, "BH": 5, "ST": 2, "AG": 6, "IQ": 6},
    },
    {
        "team": "Bentley-Truman",
        "first_name": "Pete",
        "last_name": "Del Fino",
        "attributes": {"BH": 2},
        "year": "senior",
    },
    # Lancaster
    {
        "team": "Lancaster",
        "first_name": "Roger",
        "last_name": "Henrich",
        "height": 84,
        "weight": 268,
        "attributes": {"SH": 1, "OD": 3},
    },
    {
        "team": "Lancaster",
        "first_name": "Benny",
        "last_name": "Pena",
        "attributes": {"SC": 2, "SH": 2, "ID": 8, "OD": 9, "PS": 4, "BH": 5},
    },
    # Four Corners
    {
        "team": "Four Corners",
        "first_name": "Jeffrey",
        "last_name": "Jackson",
        "attributes": {"SC": 8, "ID": 8, "OD": 7},
    },
    {
        "team": "Four Corners",
        "first_name": "Jay",
        "last_name": "Giancola",
        "attributes": {"ND": 10},
    },
    {
        "team": "Four Corners",
        "first_name": "Warren",
        "last_name": "Davis",
        "weight": 265,
        "attributes": {"SH": 1},
    },
    # Ocean City
    {
        "team": "Ocean City",
        "first_name": "Craig",
        "last_name": "James",
        "attributes": {"BH": 2},
    },
    {
        "team": "Ocean City",
        "first_name": "Booker",
        "last_name": "Preston",
        "attributes": {"BH": 3, "PS": 4, "ND": 2},
    },
    {
        "team": "Ocean City",
        "first_name": "Monroe",
        "last_name": "Quinto",
        "height": 77,
    },
    # Little York — DB spelling is Manual Roose
    {
        "team": "Little York",
        "first_name": "Manual",
        "last_name": "Roose",
        "attributes": {"RB": 3, "AG": 1, "ST": 2, "IQ": 2},
    },
    {
        "team": "Little York",
        "first_name": "AC",
        "last_name": "Buford",
        "attributes": {"IQ": 5},
    },
    # South Lancaster
    {
        "team": "South Lancaster",
        "first_name": "Sonny",
        "last_name": "Carrozza",
        "attributes": {"OD": 7, "BH": 3, "IQ": 2},
    },
]


def _digit_map(current: int, digit: int) -> int:
    if not isinstance(digit, int) or digit < 0 or digit > 10:
        raise ValueError(f"display digit out of range 0–10: {digit!r}")
    if not isinstance(current, (int, float)):
        raise ValueError(f"current attr not numeric: {current!r}")
    cur = int(current)
    return min(100, digit * 10 + (cur % 10))


def _find(db, team: str, first: str, last: str) -> dict[str, Any]:
    docs = list(
        db.players.find(
            {"team": team, "first_name": first, "last_name": last},
        )
    )
    if len(docs) != 1:
        raise SystemExit(
            f"Expected 1 player for {first} {last} @ {team} in {db.name}, found {len(docs)}"
        )
    return docs[0]


def _apply_attr_digits(
    attrs: dict[str, Any], digits: dict[str, int]
) -> tuple[list[tuple[str, int, int]], dict[str, Any]]:
    changes: list[tuple[str, int, int]] = []
    out = dict(attrs)
    for key, digit in digits.items():
        if key not in ATTR_KEYS:
            raise SystemExit(f"Unknown attribute key {key!r}")
        old = int(out.get(key) or 0)
        new = _digit_map(old, digit)
        out[key] = new
        anchor = f"anchor_{key}"
        if anchor in out:
            out[anchor] = new
        changes.append((key, old, new))
    return changes, out


def _plan_db(db) -> list[dict[str, Any]]:
    """Build per-player $set plans for one database. Swap handled once for the pair."""
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for spec in EDITS:
        key = (spec["team"], spec["first_name"], spec["last_name"])
        by_key[key] = spec

    plans: dict[str, dict[str, Any]] = {}  # player _id → plan

    # 1) Swap Omar ↔ CJ (full attributes + height + weight)
    omar = _find(db, "Bentley-Truman", "Omar", "Nola")
    cj = _find(db, "Bentley-Truman", "CJ", "Castleman")
    omar_id, cj_id = str(omar["_id"]), str(cj["_id"])

    omar_new_attrs = copy.deepcopy(cj.get("attributes") or {})
    cj_new_attrs = copy.deepcopy(omar.get("attributes") or {})
    omar_ht, omar_wt = cj.get("height"), cj.get("weight")
    cj_ht, cj_wt = omar.get("height"), omar.get("weight")

    plans[omar_id] = {
        "name": "Omar Nola",
        "team": "Bentley-Truman",
        "doc": omar,
        "set": {
            "attributes": omar_new_attrs,
            "height": omar_ht,
            "weight": omar_wt,
            "year": "junior",
            "position_ratings": compute_position_ratings(
                {"attributes": omar_new_attrs, "height": omar_ht}
            ),
        },
        "notes": [
            f"SWAP attrs/HT/WT with CJ Castleman; year {omar.get('year')} → junior",
            f"height {omar.get('height')} → {omar_ht}, weight {omar.get('weight')} → {omar_wt}",
        ],
        "attr_changes": sorted(
            (k, (omar.get("attributes") or {}).get(k), omar_new_attrs.get(k))
            for k in ATTR_KEYS
            if (omar.get("attributes") or {}).get(k) != omar_new_attrs.get(k)
        ),
    }
    plans[cj_id] = {
        "name": "CJ Castleman",
        "team": "Bentley-Truman",
        "doc": cj,
        "set": {
            "attributes": cj_new_attrs,
            "height": cj_ht,
            "weight": cj_wt,
            "position_ratings": compute_position_ratings(
                {"attributes": cj_new_attrs, "height": cj_ht}
            ),
        },
        "notes": [
            "SWAP attrs/HT/WT with Omar Nola (year unchanged)",
            f"height {cj.get('height')} → {cj_ht}, weight {cj.get('weight')} → {cj_wt}",
        ],
        "attr_changes": sorted(
            (k, (cj.get("attributes") or {}).get(k), cj_new_attrs.get(k))
            for k in ATTR_KEYS
            if (cj.get("attributes") or {}).get(k) != cj_new_attrs.get(k)
        ),
    }

    # 2) Everyone else (and skip Omar/CJ attribute specs — already swapped)
    for spec in EDITS:
        first, last, team = spec["first_name"], spec["last_name"], spec["team"]
        if (first, last) in {("Omar", "Nola"), ("CJ", "Castleman")}:
            continue
        doc = _find(db, team, first, last)
        pid = str(doc["_id"])
        attrs = copy.deepcopy(doc.get("attributes") or {})
        set_doc: dict[str, Any] = {}
        notes: list[str] = []
        attr_changes: list[tuple[str, int, int]] = []

        if spec.get("attributes"):
            attr_changes, attrs = _apply_attr_digits(attrs, spec["attributes"])
            set_doc["attributes"] = attrs

        height = doc.get("height")
        if "height" in spec:
            notes.append(f"height {height} → {spec['height']}")
            height = spec["height"]
            set_doc["height"] = height
        if "weight" in spec:
            notes.append(f"weight {doc.get('weight')} → {spec['weight']}")
            set_doc["weight"] = spec["weight"]
        if "year" in spec:
            year = YEAR_CANON[spec["year"]]
            notes.append(f"year {doc.get('year')} → {year}")
            set_doc["year"] = year

        if "attributes" in set_doc or "height" in set_doc:
            set_doc["position_ratings"] = compute_position_ratings(
                {"attributes": attrs, "height": height}
            )

        if not set_doc:
            raise SystemExit(f"No-op edit for {first} {last}")

        plans[pid] = {
            "name": f"{first} {last}",
            "team": team,
            "doc": doc,
            "set": set_doc,
            "notes": notes,
            "attr_changes": attr_changes,
        }

    return list(plans.values())


def _print_manifest(db_name: str, plans: list[dict[str, Any]]) -> None:
    print("=" * 78)
    print(f"BATCH POOL EDITS — {db_name}  ({len(plans)} players)")
    print("=" * 78)
    for plan in sorted(plans, key=lambda p: (p["team"], p["name"])):
        print(f"● {plan['name']}  ({plan['team']})  id={plan['doc']['_id']}")
        for note in plan["notes"]:
            print(f"    {note}")
        for key, old, new in plan["attr_changes"]:
            print(f"    {key}: {old} → {new}")
        if "year" in plan["set"] and not any(n.startswith("year ") for n in plan["notes"]):
            print(f"    year → {plan['set']['year']}")
    print("=" * 78)


def _backup(db) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    name = f"players_backup_batch_edit_{ts}"
    src = db.players.count_documents({})
    db.players.aggregate([{"$match": {}}, {"$out": name}])
    dst = db[name].count_documents({})
    if dst != src:
        raise SystemExit(f"backup count mismatch {db.name}: {src} vs {dst}")
    print(f"BACKUP  {db.name}.players ({src}) → {db.name}.{name}")
    return name


def _commit(db, plans: list[dict[str, Any]]) -> None:
    ops = [UpdateOne({"_id": p["doc"]["_id"]}, {"$set": p["set"]}) for p in plans]
    result = db.players.bulk_write(ops, ordered=False)
    print(f"WROTE   {db.name}.players modified={result.modified_count} matched={result.matched_count}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", action="store_true")
    ap.add_argument(
        "--confirm-db",
        choices=("gob-staging", "gob", "both"),
        help="Required with --commit: which database(s) to write.",
    )
    args = ap.parse_args()

    if args.commit and not args.confirm_db:
        print("Refusing --commit without --confirm-db gob-staging|gob|both", file=sys.stderr)
        return 2

    uri = str(dotenv_values(ROOT / ".env.local").get("MONGO_URI") or "").strip()
    if not uri:
        raise SystemExit("Missing MONGO_URI in .env.local")

    targets = ["gob-staging", "gob"]
    if args.commit:
        if args.confirm_db == "both":
            targets = ["gob-staging", "gob"]
        else:
            targets = [args.confirm_db]

    client = MongoClient(uri, serverSelectionTimeoutMS=20000)
    try:
        for db_name in ["gob-staging", "gob"] if not args.commit else targets:
            # Always plan both on dry-run; on commit only confirmed targets.
            if args.commit and db_name not in targets:
                continue
            db = client[db_name]
            plans = _plan_db(db)
            _print_manifest(db_name, plans)
            if args.commit:
                _backup(db)
                _commit(db, plans)
            else:
                print(f"DRY-RUN {db_name}: no writes\n")

        if not args.commit:
            print("Re-run with: --commit --confirm-db both")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
