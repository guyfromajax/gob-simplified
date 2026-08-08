#!/usr/bin/env python3
"""
Build a pre-built recruit SET — Phase 2 (data core) of the recruit image system.

Chain:
    generate_recruits_list(count)          [DB-free — names load from a JSON file]
      -> project each recruit to his MATURE build
           * attribute maturity scaling (ST/AG/RT) by per-year factor
           * height/weight growth via the game's training-camp model
      -> classify (frame + definition) + assign portrait genes
           [reuses the pure functions in classify_player_archetypes.py — no logic copied]
      -> emit  <set_id>.json           (game-facing set doc; loads into FRD)
               <set_id>.manifest.json   (sidecar: projected build + portrait genes)

Images (uniform kits) are a SEPARATE follow-up that consumes the manifest and
reuses the existing portrait pipeline. This script writes DATA only.

Run on your machine (no DB, no GEMINI key needed for this step):
    python3 scripts/recruit_sets/build_recruit_set.py --set-id set_0001
    python3 scripts/recruit_sets/build_recruit_set.py --set-id set_0001 --count 300 --seed 1

Validate the pipeline with synthetic recruits (no franchise_manager import):
    python3 scripts/recruit_sets/build_recruit_set.py --selftest

Contract: scripts/recruit_sets/SCHEMA.md
Design:   _documentation_master/00_Operations/Recruit_Image_System.md
"""
import os
import sys
import json
import uuid
import random
import argparse
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)                 # scripts/
ROOT = os.path.dirname(SCRIPTS)                 # repo root
sys.path.insert(0, SCRIPTS)                     # for classify_player_archetypes
sys.path.insert(0, ROOT)                        # for BackEnd.models.franchise_manager

import classify_player_archetypes as clf        # noqa: E402  (pure functions reused)
import player_ethnicity as pe                    # noqa: E402  (race mix balancing)

# --- projection: recruit -> mature-equivalent build ------------------------
# Attribute maturity scaling. Divide raw ST/AG/RT by the year factor to lift the
# recruit onto the player scale the classifier thresholds are calibrated for.
# Grounded in YEAR_TIER_RANGES (JH->Junior midpoint ratio ~0.54). See design doc.
ATTR_FACTOR = {"JH": 0.55, "Freshman": 0.65, "Sophomore": 0.80, "Junior": 1.00}

# Year advances one step at signing, so a recruit grows through these camps as a
# rostered player. Only freshman/sophomore grow (training_execution_v2.py).
CAMPS_BY_RECRUIT_YEAR = {
    "JH":        ["freshman", "sophomore"],
    "Freshman":  ["sophomore"],
    "Sophomore": [],
    "Junior":    [],
}


def _expected_height_delta(camp_year):
    # means of _roll_training_camp_height_delta() in training_execution_v2.py
    return {"freshman": 1.85, "sophomore": 0.5}.get(camp_year, 0.0)


def _expected_weight_delta(camp_year, height_after):
    # means of _roll_training_camp_weight_delta() (height-banded)
    if camp_year == "freshman":
        return 20.0 if height_after > 75 else (10.0 if height_after > 72 else 5.0)
    if camp_year == "sophomore":
        return 5.0 if height_after > 75 else 2.5
    return 0.0


def project_size(year, height, weight):
    """Project height/weight forward to a mature build using expected camp deltas."""
    h, w = float(height), float(weight)
    for camp_year in CAMPS_BY_RECRUIT_YEAR.get(year, []):
        h += _expected_height_delta(camp_year)
        w += _expected_weight_delta(camp_year, h)
    return int(round(h)), int(round(w))


def project_attr(value, year):
    """Scale a raw recruit attribute up onto the mature/player scale (cap 99)."""
    factor = ATTR_FACTOR.get(year, 1.0)
    return min(99, int(round(value / factor)))


# Recruits have no team, so accessories get neutral (black/white) colors rather
# than team colors. The kit bust is pre-uniform; team recolor happens at sign.
NEUTRAL_PRIMARY = "#141414"
NEUTRAL_SECONDARY = "#e8e8e8"


def _name_of(recruit):
    first, _, last = recruit["name"].partition(" ")
    return first, last


def bounded_race_weights(recruits, seed, cap_pp=8):
    """Roll a per-set race target within +/-cap_pp of the league base (60/30/10),
    then return residual weights for the RANDOM (unmatched) pool so the set lands
    near that rolled target. Name-signalled recruits (a 'Garcia' -> Hispanic)
    count toward the target and are never overridden — so a race can't be rolled
    BELOW its name-locked floor (else the impossible deficit would spill onto
    another race and blow the cap). Gives organic set-to-set variation with the
    drift bounded, instead of a rigid exact 60/30/10. Returns (weights, target_pct)."""
    rng = random.Random(f"ethmix|{seed}")
    base = dict(pe.RACE_WEIGHTS)                       # {"black":60,"white":30,"other":10}
    n = len(recruits)

    matched = {"black": 0, "white": 0, "other": 0}
    for r in recruits:
        race, _, _ = pe.name_signal(*_name_of(r))
        if race:
            matched[race] += 1
    floor = {k: 100.0 * matched[k] / n for k in matched}      # name-locked minimum share

    # Per-race feasible band: within +/-cap of base, but never below the name floor.
    # Shrink the ROLL band by `headroom` so residual sampling noise (~2-3pp over the
    # ~230 unmatched recruits) keeps the ACTUAL result inside the +/-cap band.
    headroom = min(2.0, cap_pp / 3.0)
    lo = {k: min(max(base[k] - cap_pp + headroom, floor[k]), base[k] + cap_pp) for k in base}
    hi = {k: max(base[k] + cap_pp - headroom, lo[k]) for k in base}

    # Roll 'other' in its band, then 'white' in the sub-band that also keeps 'black'
    # in its band; 'black' is the remainder. Deterministic, always feasible.
    to = rng.uniform(lo["other"], hi["other"])
    w_lo = max(lo["white"], (100.0 - to) - hi["black"])
    w_hi = min(hi["white"], (100.0 - to) - lo["black"])
    tw = rng.uniform(w_lo, w_hi) if w_lo <= w_hi else base["white"]
    tb = 100.0 - to - tw
    target = {"black": tb, "white": tw, "other": to}

    residual = {k: max(0.0, target[k] / 100.0 * n - matched[k]) for k in target}
    weights = [(k, max(0, round(residual[k]))) for k in ("black", "white", "other")]
    return weights, target


def build_one(recruit, random_weights=None):
    """One recruit -> (set record, manifest entry). recruit is a generate_recruits_list dict.
    random_weights balances the pool's race mix to the league target (compute_random_weights).

    Keeps an existing recruit_id when the input already has one (rebuilding the baking
    manifest for an already-minted recruit — genes are seeded by rid, so this reproduces
    that recruit's face while recomputing the build frame from his current physicals);
    mints a fresh uuid only for brand-new recruits."""
    rid = recruit.get("recruit_id") or str(uuid.uuid4())
    name = recruit["name"]
    year = recruit.get("year", "JH")
    attrs = recruit["attributes"]
    pratings = recruit.get("position_ratings") or {}
    height, weight = recruit["height"], recruit["weight"]

    # --- projection -> classifier inputs
    st_p = project_attr(attrs.get("ST", 0), year)
    ag_p = project_attr(attrs.get("AG", 0), year)
    rt_raw = max(pratings.values()) if pratings else 0     # best position = the recruit's RT
    rt_p = project_attr(rt_raw, year)
    h_p, w_p = project_size(year, height, weight)
    bmi = 703 * w_p / (h_p ** 2)

    # --- build (reuses the exact 127-team classifier functions)
    defi = clf.definition(st_p, ag_p, rt_p)
    frame = clf.frame_of(h_p, w_p, bmi, defi, st_p)
    if frame == "Doughy":
        defi = "Soft"                                       # terminal type, pinned
    else:
        defi = clf.reroll_definition(defi, rid)

    # --- portrait genes (seeded by recruit_id, exactly like league players)
    first, _, last = name.partition(" ")
    eth = clf.assign_ethnicity(first, last, rid, random_weights=random_weights)
    portrait = {
        "race": eth["race"],
        "skin": eth["skin"],
        "skin_prompt": eth["skin_prompt"],
        "hair": clf.pick_hair(rid, eth["race"], eth["skin"]),
        "face_prompt": clf.pick_face(rid, eth["race"], eth["skin"]),
        "expression": clf.pick_expression(rid),
        "accessories": clf.pick_accessories(rid, year, NEUTRAL_PRIMARY, NEUTRAL_SECONDARY),
    }

    record = {
        "recruit_id": rid,
        "name": name,
        "year": year,
        "archetype": recruit.get("archetype"),
        "height": height,                                   # AS GENERATED (not projected)
        "weight": weight,
        "attributes": attrs,                                # verbatim -> FRD
        "position_ratings": pratings,
        # Stable home region (identity, not franchise-layered): baked once here so
        # the recruit lands in the same region in every franchise. Seeded by rid so
        # a rebuild reproduces it. The loader reads this; Lean still derives from it
        # with its own randomness. Region keys mirror _build_region_team_map (A–H).
        "Home Region": random.Random(f"region|{rid}").choice(list("ABCDEFGH")),
    }
    manifest = {
        "recruit_id": rid,
        "projected": {"height": h_p, "weight": w_p, "ST": st_p, "AG": ag_p, "RT": rt_p},
        "build": {"frame": frame, "definition": defi or "Toned"},
        "portrait": portrait,
    }
    return record, manifest


def generate_recruits(count, seed=None):
    """Real recruit generation (DB-free). Lazy import so the sandbox/self-test path
    never needs BackEnd.models.franchise_manager (which pulls DB modules)."""
    if seed is not None:
        random.seed(seed)
    from BackEnd.models.franchise_manager import RecruitManager
    return RecruitManager(None).generate_recruits_list(count=count)


# --- self-test: synthetic recruits, no franchise_manager import ------------
_ATTR_CODES = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]
_SYNTH_YEARS = ["JH"] * 40 + ["Freshman"] * 12 + ["Sophomore"] * 4 + ["Junior"] * 4


def synthetic_recruits(n, seed=7):
    r = random.Random(seed)
    # rough attribute band by year, mirroring YEAR_TIER_RANGES spread
    band = {"JH": (10, 70), "Freshman": (15, 72), "Sophomore": (20, 78), "Junior": (30, 85)}
    out = []
    for i in range(n):
        year = _SYNTH_YEARS[i % len(_SYNTH_YEARS)]
        lo, hi = band[year]
        height = r.randint(66, 82)
        weight = r.randint(160, 245)
        attrs = {c: r.randint(lo, hi) for c in _ATTR_CODES}
        attrs["CH"] = r.randint(1, 90)
        pr = {p: r.randint(lo, hi) for p in ("PG", "SG", "SF", "PF", "C")}
        out.append({
            "name": f"Recruit{i:03d} Prospect",
            "year": year, "archetype": "Athlete",
            "height": height, "weight": weight,
            "attributes": attrs, "position_ratings": pr,
        })
    return out


def validate(set_doc):
    recs = set_doc["recruits"]
    assert len(recs) == set_doc["recruit_count"], "recruit_count mismatch"
    ids = [r["recruit_id"] for r in recs]
    assert len(set(ids)) == len(ids), "duplicate recruit_id in set"
    for r in recs:
        assert r["year"] in ATTR_FACTOR, f"bad year {r['year']}"
        assert all(c in r["attributes"] for c in _ATTR_CODES), "missing core attributes"


def print_summary(records, manifests, is_selftest, eth_target=None):
    n = len(records)
    yr = Counter(r["year"] for r in records)
    fr = Counter(m["build"]["frame"] for m in manifests)
    de = Counter(m["build"]["definition"] for m in manifests)
    ra = Counter(m["portrait"]["race"] for m in manifests)
    order_fr = ["Slight", "Lean", "Normal", "Broad", "Doughy"]

    def line(title, counter, order=None):
        keys = order or sorted(counter, key=lambda k: -counter[k])
        parts = [f"{k} {counter.get(k, 0)} ({100*counter.get(k,0)/n:.0f}%)" for k in keys if counter.get(k, 0) or order]
        print(f"  {title:<12} " + " | ".join(parts))

    print(f"\n[summary] {n} recruits{'  (SELF-TEST synthetic)' if is_selftest else ''}")
    line("year", yr, ["JH", "Freshman", "Sophomore", "Junior"])
    line("frame", fr, order_fr)
    line("definition", de, ["Cut", "Toned", "Soft"])
    line("race", ra, ["black", "white", "other"])
    if eth_target:
        print("  " + " " * 12 + " target rolled: "
              + " | ".join(f"{k} {eth_target[k]:.0f}%" for k in ("black", "white", "other")))
    missing = [f for f in order_fr if not fr.get(f)]
    if missing:
        print(f"  [warn] frames with zero coverage: {', '.join(missing)} "
              f"(a full 300-set should span all five)")


def main():
    ap = argparse.ArgumentParser(description="Build a pre-built recruit set (data core).")
    ap.add_argument("--set-id", default="set_0001", help="human-readable set id (set_NNNN)")
    ap.add_argument("--count", type=int, default=300)
    ap.add_argument("--seed", type=int, help="seed generation for a reproducible set")
    ap.add_argument("--out-dir", default=HERE)
    ap.add_argument("--eth-cap-pp", type=float, default=8.0,
                    help="max drift (percentage points) of each race from the 60/30/10 base")
    ap.add_argument("--selftest", action="store_true",
                    help="build from synthetic recruits (validates proj/classify, writes nothing)")
    args = ap.parse_args()

    if args.selftest:
        recruits = synthetic_recruits(max(args.count, 60) if args.count != 300 else 60)
    else:
        recruits = generate_recruits(args.count, args.seed)

    # Balance the race mix toward a per-set target rolled within +/-cap of the
    # league base (60/30/10), so sets vary organically without extreme drift.
    eth_seed = args.seed if args.seed is not None else args.set_id
    random_weights, eth_target = bounded_race_weights(recruits, eth_seed, args.eth_cap_pp)

    records, manifests = [], []
    for rc in recruits:
        rec, man = build_one(rc, random_weights=random_weights)
        records.append(rec)
        manifests.append(man)

    set_doc = {"set_id": args.set_id, "version": 1,
               "recruit_count": len(records), "recruits": records}
    manifest_doc = {"set_id": args.set_id, "entries": manifests}
    validate(set_doc)

    if not args.selftest:
        os.makedirs(args.out_dir, exist_ok=True)
        set_path = os.path.join(args.out_dir, f"{args.set_id}.json")
        man_path = os.path.join(args.out_dir, f"{args.set_id}.manifest.json")
        json.dump(set_doc, open(set_path, "w"), indent=2)
        json.dump(manifest_doc, open(man_path, "w"), indent=2)
        print(f"[ok] wrote {set_path}")
        print(f"[ok] wrote {man_path}")

    print_summary(records, manifests, args.selftest, eth_target)


if __name__ == "__main__":
    main()
