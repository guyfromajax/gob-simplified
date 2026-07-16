#!/usr/bin/env python3
"""
Export the universal_players collection for the portrait-generation pipeline.

Run this WHERE MONGO_URI IS SET (your local machine, a Cursor agent, or any
environment with DB access) — the Claude Code web session is network-restricted
and cannot reach the database.

    export MONGO_URI="mongodb+srv://.../gob-staging?..."   # if not already set
    python3 scripts/export_players_for_portraits.py

Outputs (written next to this script, under scripts/):
    players_export.json   full normalized rows
    players_export.csv    same, flat CSV
It also prints a sample document's keys (so we can confirm the real schema)
and a quick height/weight distribution + provisional build tertiles.

No secrets are printed.
"""
import os
import sys
import csv
import json
import re

DB_NAME = os.environ.get("MONGO_DB_NAME", "gob-staging")
COLLECTION = os.environ.get("PLAYERS_COLLECTION", "universal_players")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

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


def load_env_file(path=".env"):
    """Read KEY=VALUE lines from a local .env into os.environ (no printing).

    Only sets vars that aren't already in the environment, so an explicitly
    exported value still wins. Secrets never touch the terminal.
    """
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


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
    load_env_file()   # auto-load MONGO_URI from .env — never printed
    uri = os.environ.get("MONGO_URI")
    if not uri:
        sys.exit("MONGO_URI not set (checked environment and .env). "
                 "Run where the DB is reachable, or set MONGO_URI.")
    try:
        from pymongo import MongoClient
    except ImportError:
        sys.exit("pymongo not installed. Run:  pip install pymongo")

    client = MongoClient(uri)
    db = client.get_database(DB_NAME)
    colls = db.list_collection_names()

    # Pick the players collection: env override, else the configured name,
    # else auto-detect from common candidates by which actually has docs.
    candidates = [COLLECTION, "universal_players", "players", "universalPlayers",
                  "player", "Players"]
    chosen = None
    for c in candidates:
        if c in colls and db[c].estimated_document_count() > 0:
            chosen = c
            break
    if not chosen:
        print(f"[diag] databases on this cluster: {client.list_database_names()}")
        print(f"[diag] collections in '{DB_NAME}': {colls}")
        sys.exit(f"No non-empty players collection found in '{DB_NAME}'. "
                 "Set MONGO_DB_NAME / PLAYERS_COLLECTION to one of the above.")

    coll = db[chosen]
    print(f"[collection] using {DB_NAME}.{chosen} "
          f"({coll.estimated_document_count()} docs)")

    sample = coll.find_one({})
    if sample:
        print(f"[schema] top-level keys: {', '.join(sorted(sample.keys()))}\n")

    proj = {f: 1 for f in PROJECTION_FIELDS}
    rows = [normalize(d) for d in coll.find({}, proj)]
    print(f"[export] {len(rows)} players from {DB_NAME}.{chosen}")
    if not rows:
        sys.exit("Collection returned 0 documents — nothing to export.")

    json.dump(rows, open(os.path.join(OUT_DIR, "players_export.json"), "w"),
              indent=2, default=str)
    with open(os.path.join(OUT_DIR, "players_export.csv"), "w", newline="") as f:
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

    print("\n[done] wrote players_export.json and players_export.csv")


if __name__ == "__main__":
    main()
