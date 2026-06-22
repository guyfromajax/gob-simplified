"""Read-only: pull Zone defenses from gob-staging and dump their zone areas.

Inspects the structure of `defenses` docs where defense_type == "Zone" so we can
map each zone defender to the spots/areas it covers (incl. triggered shifts) for
the Dynamic HCO Motion brief (Step 1 zone mismatch scoring).

Staging only. Read-only — no writes/deletes.
"""
import os
import sys
import json
from pathlib import Path

from dotenv import dotenv_values
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
env = dotenv_values(ROOT / ".env.local")
uri = env.get("MONGO_URI")
if not uri or "gob-staging" not in uri:
    sys.exit(f"Refusing to run: .env.local MONGO_URI is not gob-staging (got: {uri!r})")

client = MongoClient(uri)
db = client["gob-staging"]
coll = db["defenses"]

zones = list(coll.find({"defense_type": "Zone"}))
print(f"Found {len(zones)} Zone defense docs in gob-staging.defenses\n")

for doc in zones:
    name = doc.get("name") or doc.get("defense_name") or doc.get("_id")
    print("=" * 70)
    print(f"NAME: {name}")
    print(f"TOP-LEVEL KEYS: {sorted(doc.keys())}")
    # Dump the full doc (minus large/noise fields) so we can see zone-area shape
    doc.pop("_id", None)
    print(json.dumps(doc, indent=2, default=str)[:6000])
    print()
