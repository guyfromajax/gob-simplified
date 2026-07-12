#!/usr/bin/env python3
"""
Apply a team uniform to a recruit's white kit — the SIGN-TIME recolor (Phase 2c).

When a recruit signs (week 35), his stored kit (pre-finish white RGBA bust +
precomputed tank mask) is recolored into his new team's jersey and finished into
the canonical master at players/master/<recruit_id>.png — the same object key the
game already resolves. NO u2net here: the mask was baked at generation time, so
this step is pure masked-recolor + wordmark (the portable core the downloadable
build reimplements).

Recipe source: teams/teams_uniforms.json (built by build_teams_uniforms.py).

Importable (what the backend calls on signing):
    from apply_recruit_uniform import apply_recruit_uniform
    apply_recruit_uniform(recruit_id, team_id, kit_dir, out_dir)

CLI (proof / batch visualization — recolor kits against a team):
    # one recruit onto one team
    python3 scripts/recruit_sets/apply_recruit_uniform.py --recruit-id <uuid> --team-id DURHAM
    # visualize a whole proof: recolor every kit onto a given team
    python3 scripts/recruit_sets/apply_recruit_uniform.py --all --team-id SWOOSH

See _documentation_master/00_Operations/Recruit_Image_System.md.
"""
import os
import sys
import json
import glob
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

import apply_team_uniforms as uni       # noqa: E402  (recolor_and_stamp, hex2rgb)
import finish_portraits as fin          # noqa: E402  (finish -> crop to canvas)

RECIPES = os.path.join(ROOT, "teams", "teams_uniforms.json")
KIT_DIR = "assets_staging/recruits/kit"
OUT_DIR = "assets_staging/players"       # players/master/<recruit_id>.png -> upload target


def _recipes():
    if not os.path.exists(RECIPES):
        sys.exit(f"recipe manifest not found: {RECIPES} (run build_teams_uniforms.py)")
    return json.load(open(RECIPES))


def team_recipe(team_id, recipes=None, variant="home"):
    """(primary_hex, secondary_hex, wordmark) for a team_id, case-insensitive."""
    recipes = recipes or _recipes()
    entry = recipes.get((team_id or "").upper())
    if not entry:
        raise KeyError(f"team_id {team_id!r} not in teams_uniforms.json")
    v = next((x for x in entry["variants"] if x["id"] == variant), entry["variants"][0])
    return v["body"], v["trim"], v["wordmark"]


def apply_recruit_uniform(recruit_id, team_id, kit_dir=KIT_DIR, out_dir=OUT_DIR,
                          recipes=None, variant="home"):
    """Recolor a recruit's kit into team_id's uniform -> players/master/<recruit_id>.png."""
    import numpy as np
    from PIL import Image

    bust_p = os.path.join(kit_dir, f"{recruit_id}.png")
    mask_p = os.path.join(kit_dir, f"{recruit_id}.mask.png")
    if not (os.path.exists(bust_p) and os.path.exists(mask_p)):
        raise FileNotFoundError(f"kit missing for {recruit_id} in {kit_dir}")

    primary, secondary, wordmark = team_recipe(team_id, recipes, variant)

    arr = np.asarray(Image.open(bust_p).convert("RGBA"))
    a = arr[..., :3].astype(np.float32)
    alpha = arr[..., 3]
    tank = np.asarray(Image.open(mask_p).convert("L")) > 128

    rgba = uni.recolor_and_stamp(a, alpha, tank,
                                 uni.hex2rgb(primary), uni.hex2rgb(secondary), wordmark)

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{recruit_id}.png")
    tmp = out_path + ".prefinish.png"
    Image.fromarray(rgba, "RGBA").save(tmp)
    fin.finish(tmp, out_path)            # crop/resize to the 3530x3412 canvas
    os.remove(tmp)
    return out_path


def main():
    ap = argparse.ArgumentParser(description="Sign-time recruit uniform recolor.")
    ap.add_argument("--team-id", required=True, help="team_id from teams_uniforms.json (any case)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--recruit-id", help="one recruit uuid (its kit must exist)")
    g.add_argument("--all", action="store_true", help="recolor every kit in --kit-dir (proof viz)")
    ap.add_argument("--kit-dir", default=KIT_DIR)
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--variant", default="home")
    args = ap.parse_args()

    recipes = _recipes()
    try:
        team_recipe(args.team_id, recipes, args.variant)   # fail fast on bad team
    except KeyError as e:
        sys.exit(str(e))

    if args.recruit_id:
        ids = [args.recruit_id]
    else:
        ids = [os.path.splitext(os.path.basename(p))[0]
               for p in glob.glob(os.path.join(args.kit_dir, "*.png"))
               if not p.endswith(".mask.png")]
    ok = fail = 0
    for rid in ids:
        try:
            out = apply_recruit_uniform(rid, args.team_id, args.kit_dir, args.out_dir,
                                        recipes, args.variant)
            print(f"[ok] {rid} -> {out}")
            ok += 1
        except Exception as e:
            print(f"[fail] {rid}: {type(e).__name__}: {str(e)[:140]}")
            fail += 1
    print(f"\n[done] {ok} uniformed onto {args.team_id.upper()}, {fail} failed -> {args.out_dir}")


if __name__ == "__main__":
    main()
