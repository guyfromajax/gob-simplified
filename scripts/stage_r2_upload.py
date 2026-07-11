#!/usr/bin/env python3
"""
Copy ONLY the chosen teams' UUID masters into an isolated folder, so the R2
upload can't accidentally send anything else in assets_staging/players.

    python3 scripts/stage_r2_upload.py --team "Chapel Hill" --team "Durham"
    python3 scripts/upload_player_images_to_r2.py --source assets_staging/_r2_batch --dry-run
    python3 scripts/upload_player_images_to_r2.py --source assets_staging/_r2_batch

Reusable per conference later:  --team A --team B ...
"""
import os
import csv
import json
import shutil
import argparse

SRC = "assets_staging/players"
OUT = "assets_staging/_r2_batch"
MANIFEST = "tmp/team-logo-pipeline/team-logo-manifest.json"


def teams_for_conference(n):
    mani = json.load(open(MANIFEST))
    return [m["team"] for m in mani if str(m.get("conference")) == str(n)]


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--team", action="append", help="team name (repeatable)")
    g.add_argument("--conference", type=int, help="stage all teams in a conference")
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--clean", action="store_true",
                    help="empty the out dir first (recommended per conference)")
    args = ap.parse_args()

    want = set(args.team) if args.team else set(teams_for_conference(args.conference))
    if not want:
        raise SystemExit("no teams selected")
    rows = [r for r in csv.DictReader(open("scripts/players_archetypes.csv"))
            if r["team"] in want]
    if not rows:
        raise SystemExit(f"no players found for teams {sorted(want)}")

    if args.clean and os.path.isdir(args.out):
        shutil.rmtree(args.out)
    os.makedirs(args.out, exist_ok=True)

    copied, missing = 0, []
    for r in rows:
        s = os.path.join(args.src, r["_id"] + ".png")
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(args.out, r["_id"] + ".png"))
            copied += 1
        else:
            missing.append(f"{r['name']} ({r['team']})")

    print(f"[staged] {copied}/{len(rows)} masters -> {args.out}")
    if missing:
        print(f"[missing] {len(missing)} not found in {args.src}:")
        for m in missing:
            print(f"   - {m}")
        print("  (generate them first, then re-run)")
    else:
        print("  all present. Dry-run the upload next:")
        print(f"  python3 scripts/upload_player_images_to_r2.py --source {args.out} --dry-run")


if __name__ == "__main__":
    main()
