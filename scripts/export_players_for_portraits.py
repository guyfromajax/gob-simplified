#!/usr/bin/env python3
"""
Export the universal_players collection for the portrait-generation pipeline.

Run with an explicit database target:

    python3 scripts/export_players_for_portraits.py --db gob-staging

Outputs (written next to this script, under scripts/):
    players_export.json   full normalized rows
    players_export.csv    same, flat CSV
It also prints a sample document's keys (so we can confirm the real schema)
and a quick height/weight distribution + provisional build tertiles.

No secrets are printed.
"""
import argparse
import sys
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target

OUT_DIR = Path(__file__).resolve().parent

# Candidate field names — Mongo silently ignores ones that don't exist, so we
# cast a wide net and normalize below. Adjust after seeing the printed keys.
PROJECTION_FIELDS = [
    "_id", "first_name", "last_name", "name", "full_name",
    "team", "team_name", "team_id", "teamId",
    "jersey_number", "jersey", "number",
    "height", "height_in", "height_inches", "heightInInches",
    "weight", "weight_lb", "weight_lbs",
    "year", "class", "class_year",
    "attributes", "position_ratings",   # ST/AG for build, RT = max position rating
]


def _to_inches(v):
    """Normalize a height value to integer inches, or None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        n = float(v)
        if n < 100:            # already inches (e.g. 73)
            return int(round(n))
        if 140 <= n <= 240:    # centimeters
            return int(round(n / 2.54))
        return int(round(n))
    if isinstance(v, str):
        m = re.match(r"\s*(\d+)\s*['’\-]\s*(\d+)", v)  # 6'1"  6-1  6’1
        if m:
            return int(m.group(1)) * 12 + int(m.group(2))
        m = re.match(r"\s*(\d+(?:\.\d+)?)\s*$", v)
        if m:
            return _to_inches(float(m.group(1)))
    return None


def _to_lb(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        n = float(v)
        return int(round(n if n > 90 else n * 2.2046))  # assume kg if <=90
    if isinstance(v, str):
        m = re.match(r"\s*(\d+(?:\.\d+)?)", v)
        if m:
            return _to_lb(float(m.group(1)))
    return None


def _first(doc, *keys):
    for k in keys:
        if doc.get(k) not in (None, ""):
            return doc[k]
    return None


def normalize(doc):
    fn, ln = doc.get("first_name"), doc.get("last_name")
    name = _first(doc, "name", "full_name") or " ".join(x for x in (fn, ln) if x)
    attrs = doc.get("attributes") or {}
    ratings = doc.get("position_ratings") or {}
    rt = max(ratings.values()) if ratings else None   # highest position rating
    return {
        "_id": str(doc.get("_id")),
        "name": name,
        "first_name": fn,
        "last_name": ln,
        "team": _first(doc, "team", "team_name"),
        "team_id": _first(doc, "team_id", "teamId"),
        "jersey": _first(doc, "jersey_number", "jersey", "number"),
        "height_in": _to_inches(_first(doc, "height_in", "height_inches",
                                        "heightInInches", "height")),
        "weight_lb": _to_lb(_first(doc, "weight_lb", "weight_lbs", "weight")),
        "year": _first(doc, "year", "class_year", "class"),
        "st": attrs.get("ST"),   # strength  -> muscle
        "ag": attrs.get("AG"),   # agility   -> leanness
        "rt": rt,                # overall quality -> in-shape vs out-of-shape
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    parser.add_argument("--collection", default="players")
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    connection = connect_migration_target(args.db, write=False)
    db = connection.database
    colls = db.list_collection_names()

    # Pick the players collection: env override, else the configured name,
    # else auto-detect from common candidates by which actually has docs.
    candidates = [args.collection, "universal_players", "players", "universalPlayers",
                  "player", "Players"]
    chosen = None
    for c in candidates:
        if c in colls and db[c].estimated_document_count() > 0:
            chosen = c
            break
    if not chosen:
        print(f"[diag] collections in '{args.db}': {colls}")
        sys.exit(f"No non-empty players collection found in '{args.db}'. "
                 "Set --collection to one of the above.")

    coll = db[chosen]
    print(f"[collection] using {args.db}.{chosen} "
          f"({coll.estimated_document_count()} docs)")

    sample = coll.find_one({})
    if sample:
        print(f"[schema] top-level keys: {', '.join(sorted(sample.keys()))}\n")

    proj = {f: 1 for f in PROJECTION_FIELDS}
    rows = [normalize(d) for d in coll.find({}, proj)]
    print(f"[export] {len(rows)} players from {args.db}.{chosen}")
    if not rows:
        sys.exit("Collection returned 0 documents — nothing to export.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "players_export.json").open("w", encoding="utf-8") as json_file:
        json.dump(rows, json_file, indent=2, default=str)
    with (args.output_dir / "players_export.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # --- quick distribution + provisional build tertiles ---------------------
    complete = [r for r in rows if r["height_in"] and r["weight_lb"]]
    missing = len(rows) - len(complete)
    if missing:
        print(f"[warn] {missing} players missing height/weight — check field names above")
    if complete:
        bmis = sorted(703 * r["weight_lb"] / (r["height_in"] ** 2) for r in complete)
        n = len(bmis)
        t1, t2 = bmis[n // 3], bmis[2 * n // 3]
        heights = sorted(r["height_in"] for r in complete)
        print()
        print(f"[dist] height  min/median/max = "
              f"{heights[0]}\" / {heights[n//2]}\" / {heights[-1]}\"")
        print(f"[dist] BMI build tertiles (height-adjusted):")
        print(f"         lean   : BMI <  {t1:.1f}")
        print(f"         normal : {t1:.1f} <= BMI < {t2:.1f}")
        print(f"         strong : BMI >= {t2:.1f}")
        print(f"       -> paste these cutoffs into classify_player_archetypes.py")

    connection.close()
    print(f"\n[done] wrote players_export.json and players_export.csv to {args.output_dir}")


if __name__ == "__main__":
    main()
