#!/usr/bin/env python3
"""Export [EOG-BAND] rows from the `eog_band_log` collection to JSONL.

The Mongo sink is the production home for band instrumentation (Railway's filesystem is
ephemeral). Everything downstream — eog_band_report.py, eog_band_tuner.py — reads JSONL,
so this is the bridge.

usage:
  GOB_DB_ACCESS=read scripts/eog_band_export.py --list
  GOB_DB_ACCESS=read scripts/eog_band_export.py --franchise-id <id> -o out.jsonl
"""
from __future__ import annotations

import os as _os, sys as _sys, importlib.util as _ilu
_GOB_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _GOB_ROOT)
_spec = _ilu.spec_from_file_location(
    "_gob_repro", _os.path.join(_GOB_ROOT, "BackEnd", "utils", "repro.py"))
_repro = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_repro)
_repro.pin_hash_seed()

import argparse
import json
from collections import Counter


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="show franchises with logged rows")
    ap.add_argument("--franchise-id")
    ap.add_argument("-o", "--out", default="eog_band_export.jsonl")
    ap.add_argument("--min-weeks", type=int, default=1,
                    help="with --list, only show franchises having at least this many weeks")
    args = ap.parse_args()

    from BackEnd.db import db, eog_band_log_collection as C
    print(f"# source: {db.name}.eog_band_log")

    if args.list:
        rows = C.aggregate([
            {"$group": {"_id": "$franchise_id",
                        "rows": {"$sum": 1},
                        "weeks": {"$addToSet": "$week"},
                        "first": {"$min": "$created_at"},
                        "last": {"$max": "$created_at"},
                        "sha": {"$addToSet": "$git_sha"}}},
            {"$sort": {"rows": -1}},
        ])
        print(f"{'franchise_id':<28}{'rows':>9}{'weeks':>7}{'complete?':>11}  git_sha(s)")
        any_row = False
        for r in rows:
            wk = sorted(w for w in r["weeks"] if isinstance(w, int))
            if len(wk) < args.min_weeks:
                continue
            any_row = True
            complete = "YES" if (len(wk) == 26 and r["rows"] >= 36608) else f"{len(wk)}/26"
            print(f"{str(r['_id']):<28}{r['rows']:>9}{len(wk):>7}{complete:>11}  "
                  f"{','.join(str(s) for s in r['sha'][:2])}")
        if not any_row:
            print("  (nothing logged yet)")
        return 0

    if not args.franchise_id:
        ap.error("pass --franchise-id or --list")

    q = {"franchise_id": args.franchise_id}
    n = C.count_documents(q)
    if not n:
        print(f"no rows for franchise {args.franchise_id}")
        return 1
    weeks = Counter()
    with open(args.out, "w") as fh:
        # header first so the parser sees provenance, mirroring the file sink
        shas = C.distinct("git_sha", q)
        fh.write("[EOG-BAND-HEADER] " + json.dumps(
            {"record_type": "header", "source": "eog_band_log",
             "franchise_id": args.franchise_id, "git_sha": shas[0] if shas else "unknown",
             "git_sha_all": shas}) + "\n")
        for d in C.find(q).sort([("week", 1), ("_id", 1)]):
            d.pop("_id", None); d.pop("created_at", None)
            if isinstance(d.get("week"), int):
                weeks[d["week"]] += 1
            fh.write("[EOG-BAND] " + json.dumps(d, default=str) + "\n")
    print(f"wrote {n} rows -> {args.out}")
    print(f"  weeks {min(weeks)}-{max(weeks)} ({len(weeks)}/26)")
    odd = {w: c for w, c in sorted(weeks.items()) if c != 1408}
    print(f"  weeks off 1408 rows: {odd or 'none'}")
    print(f"\nnext: python scripts/eog_band_report.py {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
