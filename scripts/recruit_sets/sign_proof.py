#!/usr/bin/env python3
"""
Sign-time recolor PROOF — 15 recruits onto 15 different teams.

Visual sanity check for the sign-time recolor before going live: assigns each of
your baked kits a DIFFERENT team's uniform so you can eyeball the tool across many
recipes at once. By design it covers all 8 Conference-1 teams (the nuanced
designs) one-each, then fills the remaining kits with random non-conf1 teams.

    python3 scripts/recruit_sets/sign_proof.py
    python3 scripts/recruit_sets/sign_proof.py --seed 7          # different random 7
    python3 scripts/recruit_sets/sign_proof.py --kit-dir assets_staging/recruits/kit/set_0001

Output -> assets_staging/recruits/signed/<recruit_id>.png (one per recruit, each a
different team). The printed table tells you which recruit got which uniform.
Nothing here is uploaded; it's a local eyeball step. See sign_recruits.py for the
real signing hook.
"""
import os
import re
import sys
import glob
import json
import random
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)

import apply_recruit_uniform as aru        # noqa: E402  (apply_recruit_uniform, team_recipe)

RECIPES = os.path.join(ROOT, "teams", "teams_uniforms.json")
# The 8 Conference-1 teams (nuanced designs) — same set used by the attr scripts.
CONF1_NAMES = [
    "Bentley-Truman", "Morristown", "Four Corners", "South Lancaster",
    "Lancaster", "Xavien", "Little York", "Ocean City",
]


def slug(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def resolve_keys(recipes):
    """(conf1_keys, non_conf1_keys) resolved from team names -> teams_uniforms keys."""
    by_name = {slug(v.get("team")): k for k, v in recipes.items()}
    conf1 = []
    for n in CONF1_NAMES:
        k = by_name.get(slug(n))
        if not k:
            sys.exit(f"conf1 team not found in teams_uniforms.json: {n}")
        conf1.append(k)
    conf1_set = set(conf1)
    non_conf1 = sorted(k for k in recipes if k not in conf1_set)
    return conf1, non_conf1


def kit_ids(kit_dir, set_path):
    """recruit_ids that have a bust in kit_dir (optionally restricted to a set)."""
    ids = sorted(
        os.path.basename(p)[:-4]                       # strip '.png'
        for p in glob.glob(os.path.join(kit_dir, "*.png"))
        if not p.endswith(".mask.png")
    )
    if set_path and os.path.exists(set_path):
        keep = {r["recruit_id"] for r in json.load(open(set_path))["recruits"]}
        before = len(ids)
        ids = [i for i in ids if i in keep]
        if before != len(ids):
            print(f"[info] {before - len(ids)} kit(s) not in {os.path.basename(set_path)} — ignored")
    return ids


def main():
    ap = argparse.ArgumentParser(description="Recolor N recruits onto N different teams (proof).")
    ap.add_argument("--kit-dir", default=aru.KIT_DIR)
    ap.add_argument("--out-dir", default=aru.OUT_DIR)
    ap.add_argument("--set", default=os.path.join(HERE, "set_0001.json"),
                    help="restrict to this set's recruit_ids (default set_0001.json; '' to disable)")
    ap.add_argument("--seed", type=int, default=1, help="seed for the random non-conf1 picks")
    args = ap.parse_args()

    if not os.path.exists(RECIPES):
        sys.exit(f"recipe manifest not found: {RECIPES} (run build_teams_uniforms.py)")
    recipes = json.load(open(RECIPES))
    conf1, non_conf1 = resolve_keys(recipes)

    ids = kit_ids(args.kit_dir, args.set or None)
    if not ids:
        sys.exit(f"no kits found in {args.kit_dir} (bake kits first with build_recruit_images.py)")

    # team plan: all 8 conf1 first (so they're always covered), then random non-conf1
    rng = random.Random(args.seed)
    n = len(ids)
    if n <= len(conf1):
        teams = conf1[:n]
    else:
        extra = rng.sample(non_conf1, min(n - len(conf1), len(non_conf1)))
        teams = conf1 + extra
    pairs = list(zip(ids, teams))

    print(f"Recoloring {len(pairs)} recruit(s), each onto a different team "
          f"({sum(1 for _, t in pairs if t in set(conf1))} conf1 + "
          f"{sum(1 for _, t in pairs if t not in set(conf1))} non-conf1):\n")
    ok = fail = 0
    conf1_set = set(conf1)
    for rid, team in pairs:
        tag = "conf1" if team in conf1_set else "     "
        try:
            aru.apply_recruit_uniform(rid, team, args.kit_dir, args.out_dir, recipes)
            print(f"  [{tag}] {rid}  ->  {team}")
            ok += 1
        except Exception as e:
            print(f"  [FAIL ] {rid}  ->  {team}: {type(e).__name__}: {str(e)[:120]}")
            fail += 1

    print(f"\n[done] {ok} recolored, {fail} failed -> {args.out_dir}")
    print("Open them side by side; each recruit wears a different team's uniform.")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
