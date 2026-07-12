#!/usr/bin/env python3
"""
Generate teams_uniforms.json — the 128-team uniform RECIPE manifest.

A uniform is data, not an image: {body, trim, wordmark} per team. This is the
single source of truth the sign-time recolor (and the future downloadable build)
reads to paint a recruit's white tank into his new team's jersey. Variant-shaped
from day one so special jerseys (black/white/color-rush) slot in as extra
`variants[]` rows with no schema change.

Parses teams/128_teams.txt with the same tolerant tokenizer as
apply_team_uniforms.team_info (collects all hex tokens, so it handles rows where
both colors are crammed into one field, e.g. Ocean City). base = primary for all
128 (matches what shipped). wordmark = mascot uppercased (the league default).

    python3 scripts/recruit_sets/build_teams_uniforms.py
    -> writes teams/teams_uniforms.json

See _documentation_master/00_Operations/Recruit_Image_System.md.
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCRIPTS = os.path.dirname(HERE)
MANIFEST = os.path.join(ROOT, "tmp", "team-logo-pipeline", "team-logo-manifest.json")
OUT = os.path.join(ROOT, "teams", "teams_uniforms.json")

def main():
    if not os.path.exists(MANIFEST):
        sys.exit(f"not found: {MANIFEST}")
    # The logo manifest is the canonical team config (team_id + colors + mascot,
    # all 128) — used to build every team's logo/banner. 128_teams.txt has messy
    # mixed-format duplicate rows, so we read straight from the manifest.
    rows = json.load(open(MANIFEST))
    manifest, missing = {}, []
    for m in rows:
        # normalize team_id to uppercase — the manifest has a few lowercase anomalies
        # (queens_guard, rivers_edge, ...); the sign-time recolor also .upper()s its
        # lookup key, so team_id case can never break the recipe lookup.
        team_id = (m.get("team_id") or "").upper() or None
        primary = m.get("primary_color")
        secondary = m.get("secondary_color") or "#ffffff"
        if not team_id or not primary:
            missing.append(m.get("team"))
            continue
        manifest[team_id] = {
            "team": m.get("team"),
            "base": "primary",           # shirt body = primary for all 128 (as shipped)
            "zones": [],                 # solid jerseys; patterned DLC adds zones later
            "variants": [
                {"id": "home", "body": primary, "trim": secondary,
                 "wordmark": (m.get("mascot") or m.get("team") or "").upper()},
            ],
        }
    with open(OUT, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"[ok] wrote {OUT}  ({len(manifest)} teams)")
    if missing:
        print(f"[warn] no colors found for: {missing}")
    if len(manifest) != 128:
        print(f"[warn] expected 128 teams, got {len(manifest)}")
    for tid in ("BENTLEY_TRUMAN", "OCEAN_CITY", "MORRISTOWN", "DURHAM"):
        v = manifest.get(tid, {}).get("variants", [{}])[0]
        print(f"  {tid:16} body={v.get('body')} trim={v.get('trim')} wordmark={v.get('wordmark')!r}")


if __name__ == "__main__":
    main()
