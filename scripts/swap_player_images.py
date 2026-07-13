#!/usr/bin/env python3
"""
Swap two players' FULL master images (body, face, hair, uniform — everything).
The game resolves a player's portrait by their UUID, so we exchange the contents
of the two <uuid>.png files. Use for personality/name fit, not re-generation.

    python3 scripts/swap_player_images.py \
        --pair "Hog Dempsey" "Sonny Johnson" \
        --pair "Gerald Lamar" "Coby Cantu"

Operates on assets_staging/players/<uuid>.png by default. If a pair's masters are
already uploaded to R2, re-stage + re-upload those UUIDs afterward.
"""
import os
import csv
import sys
import argparse

MASTERS = "assets_staging/players"


def load_uuid_map():
    m = {}
    for r in csv.DictReader(open("scripts/players_archetypes.csv")):
        m[r["name"].strip().lower()] = r["_id"]
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", nargs=2, action="append", metavar=("A", "B"),
                    required=True, help="two player names to swap (repeatable)")
    ap.add_argument("--dir", default=MASTERS)
    args = ap.parse_args()

    names = load_uuid_map()
    ok = 0
    for a, b in args.pair:
        ua, ub = names.get(a.strip().lower()), names.get(b.strip().lower())
        if not ua or not ub:
            print(f"[skip] {a} <-> {b}: name not found ({a if not ua else b})")
            continue
        pa = os.path.join(args.dir, ua + ".png")
        pb = os.path.join(args.dir, ub + ".png")
        if not (os.path.exists(pa) and os.path.exists(pb)):
            print(f"[skip] {a} <-> {b}: master file missing")
            continue
        tmp = pa + ".swaptmp"
        os.replace(pa, tmp)
        os.replace(pb, pa)
        os.replace(tmp, pb)
        print(f"[ok] swapped  {a} ({ua})  <->  {b} ({ub})")
        ok += 1
    print(f"\n[done] {ok}/{len(args.pair)} pairs swapped in {args.dir}")


if __name__ == "__main__":
    main()
