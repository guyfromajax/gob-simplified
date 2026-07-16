#!/usr/bin/env python3
"""
Sign-time recolor: turn signed recruits' white kits into their new team's uniform.

When recruits sign (week 35), each one's stored kit is recolored into the team he
signed with and finished into players/master/<recruit_id>.png — the object key the
game already resolves. This is the batch step that produces those uniformed
masters; upload them afterward with upload_recruit_images_to_r2.py --stage signed.

No u2net here (the kit mask is precomputed); just the portable recolor + finish.

    # explicit pairs (recruit_id + teams_uniforms key):
    python3 scripts/recruit_sets/sign_recruits.py --pair <recruit_id> DURHAM --pair <recruit_id> SWOOSH

    # everyone who signed in a franchise's week-35 results (resolves team keys for you):
    python3 scripts/recruit_sets/sign_recruits.py --from-franchise <franchise_id>

Then upload:
    python3 scripts/recruit_sets/upload_recruit_images_to_r2.py --stage signed

Intended to run after week-35 signings (manually, via cron, or triggered by the
backend). Kits are read from assets_staging/recruits/kit/ by default. See
_documentation_master/00_Operations/Recruit_Image_System.md.
"""
import os
import re
import sys
import json
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import apply_recruit_uniform as aru        # noqa: E402  (apply_recruit_uniform, team_recipe)

RECIPES = os.path.join(ROOT, "teams", "teams_uniforms.json")


def slug(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def team_key_by_name():
    """Map slugified team name -> teams_uniforms key (e.g. 'durham' -> 'DURHAM')."""
    m = json.load(open(RECIPES))
    return {slug(v.get("team")): k for k, v in m.items()}


def pairs_from_franchise(fid):
    """(recruit_id, team_key) for every real recruit who signed (skips walk-ons)."""
    from BackEnd.db import db
    from BackEnd.api.franchise_routes import WEEK_35_RECRUITING_RESULTS_FIELD
    query_ids = [fid]
    try:
        from bson import ObjectId
        query_ids.append(ObjectId(fid))
    except Exception:
        pass
    doc = None
    for qid in query_ids:
        doc = db.franchises.find_one({"_id": qid}, {WEEK_35_RECRUITING_RESULTS_FIELD: 1})
        if doc:
            break
    if not doc:
        sys.exit(f"franchise not found: {fid}")
    signed = (doc.get(WEEK_35_RECRUITING_RESULTS_FIELD) or {}).get("signed_players") or []
    keymap = team_key_by_name()
    pairs, skipped_walkon, unresolved = [], 0, []
    for s in signed:
        rid = s.get("recruit_id")
        if not rid:                       # walk-on: no pre-generated portrait
            skipped_walkon += 1
            continue
        key = keymap.get(slug(s.get("team_name")))
        if not key:
            unresolved.append(s.get("team_name"))
            continue
        pairs.append((rid, key))
    if skipped_walkon:
        print(f"[info] skipped {skipped_walkon} walk-on(s) (no portrait)")
    if unresolved:
        print(f"[warn] could not resolve uniform for team(s): {sorted(set(unresolved))}")
    return pairs


def main():
    ap = argparse.ArgumentParser(description="Recolor signed recruits into their team uniforms.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pair", nargs=2, action="append", metavar=("RECRUIT_ID", "TEAM_ID"),
                   help="recruit uuid + teams_uniforms key (repeatable)")
    g.add_argument("--from-franchise", help="franchise _id — recolor everyone who signed")
    ap.add_argument("--kit-dir", default=aru.KIT_DIR)
    ap.add_argument("--out-dir", default=aru.OUT_DIR)
    args = ap.parse_args()

    if not os.path.exists(RECIPES):
        sys.exit(f"recipe manifest not found: {RECIPES} (run build_teams_uniforms.py)")
    recipes = json.load(open(RECIPES))

    pairs = args.pair if args.pair else pairs_from_franchise(args.from_franchise)
    if not pairs:
        print("[done] nothing to recolor")
        return

    ok = fail = 0
    for rid, team_id in pairs:
        try:
            out = aru.apply_recruit_uniform(rid, team_id, args.kit_dir, args.out_dir, recipes)
            print(f"[ok] {rid} -> {team_id.upper()}  {out}")
            ok += 1
        except Exception as e:
            print(f"[fail] {rid} ({team_id}): {type(e).__name__}: {str(e)[:140]}")
            fail += 1

    print(f"\n[done] {ok} uniformed, {fail} failed -> {args.out_dir}")
    if ok:
        print("Next: python3 scripts/recruit_sets/upload_recruit_images_to_r2.py --stage signed")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
