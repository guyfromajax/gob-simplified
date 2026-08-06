#!/usr/bin/env python3
"""Provision / tear down the §11 league-convergence scratch database.

Creates ``gob-s11-league-convergence`` on the same Atlas cluster as MONGO_URI,
cloning reference collections from ``gob``. Does NOT touch gob or gob-staging
franchise data.

Usage:
    .venv/bin/python scripts/s11_provision_convergence_scratch.py
    .venv/bin/python scripts/s11_provision_convergence_scratch.py --drop   # wipe scratch DB
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

for _env in (".env", ".env.local"):
    p = _REPO / _env
    if not p.exists():
        continue
    for line in p.read_text().splitlines():
        if not line.strip() or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from pymongo import MongoClient  # noqa: E402

SCRATCH_DB = "gob-s11-league-convergence"
SOURCE_DB = "gob"
REFERENCE = [
    "players",
    "teams",
    "plays",
    "defenses",
    "fcp_skeletons",
    "hct_skeletons",
    "recruit_sets",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", action="store_true", help="Drop the scratch DB entirely")
    ap.add_argument("--force-reclone", action="store_true")
    args = ap.parse_args()

    uri = os.environ.get("MONGO_URI")
    if not uri:
        sys.exit("MONGO_URI not set")
    client = MongoClient(uri, serverSelectionTimeoutMS=30000)

    if args.drop:
        client.drop_database(SCRATCH_DB)
        print(f"Dropped {SCRATCH_DB}")
        return

    src = client[SOURCE_DB]
    dst = client[SCRATCH_DB]
    for col in REFERENCE:
        n_src = src[col].count_documents({})
        n_dst = dst[col].count_documents({})
        if n_dst > 0 and not args.force_reclone:
            print(f"skip {col}: scratch already has {n_dst} (src {n_src})")
            continue
        print(f"cloning {col}: {n_src} docs…")
        if n_dst:
            dst[col].delete_many({})
        batch = []
        for doc in src[col].find():
            batch.append(doc)
            if len(batch) >= 500:
                dst[col].insert_many(batch)
                batch = []
        if batch:
            dst[col].insert_many(batch)
        print(f"  → {dst[col].count_documents({})}")
    print(f"Ready: {SCRATCH_DB}")


if __name__ == "__main__":
    main()
