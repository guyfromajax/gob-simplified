#!/usr/bin/env python3
"""Regenerate the universal players pool via the §11.3 rank-preserving remap and
recompute stored position_ratings everywhere (design §3.5 / §11.3).

DRY-RUN BY DEFAULT. It reads the pool, computes the remap in memory, prints the
§3.6.4 verification metrics on the regenerated population, and writes NOTHING.
Pass --commit (and --i-have-a-backup) to persist. It only ever *updates* existing
docs — no delete_many, no drops — per the staging-safety rule.

Remap (design §11.3, identity-preserving — names/portraits/player_id kept):
  1. Position intent  — sort pool by height; tallest ~20% → C, then PF, SF; the
     bottom ~40% guard band splits PG (ball-handling+passing) vs SG (shooting+
     perimeter D). Fills the centre shortage by construction.
  2. Height           — rank-map each player within his new cohort onto that
     position's target height distribution (80th pct stays 80th pct).
  3. Talent           — rank-map overall-RT percentile onto the §4.1 tier bands,
     so tier frequencies match the target exactly.
  4. Class year       — rebalanced to ~25% each (fixes the SR/SO skew; invisible
     to existing saves, which are new-franchises-only).
  5. Attributes       — redraw magnitudes preserving each player's relative
     attribute ordering ("a shooter stays a shooter"), scaled to hit the new
     tier's class-year ladder target. CH preserved (re-rolled at franchise init).

Then recompute stored position_ratings for the universal pool AND every FPD/FRD
doc under the new formula (the §3.5 fix — the cause was formula-drift staleness,
so recomputing corrects it wherever it lives).

Usage:
    ./.venv/bin/python scripts/regenerate_universal_pool.py            # dry-run + metrics
    ./.venv/bin/python scripts/regenerate_universal_pool.py --commit --i-have-a-backup
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
from collections import Counter
from pathlib import Path
from statistics import NormalDist

from pymongo.operations import UpdateOne

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.utils.position_ratings import (  # noqa: E402
    POSITION_WEIGHTS,
    compute_position_ratings,
    height_fitness,
)
from BackEnd.utils.player_generation import (  # noqa: E402
    CLASS_YEARS,
    CORE_ATTRS,
    HEIGHT_IDEAL_IN,
    HEIGHT_MAX_IN,
    HEIGHT_MIN_IN,
    HEIGHT_SD_IN,
    HT_REMAINING_SHARE_BY_YEAR,
    HT_TOTAL_MEAN,
    HT_TOTAL_SD,
    HT_TOTAL_MIN,
    HT_TOTAL_MAX,
    POSITIONS,
    TIER_FREQUENCY,
    draw_potential_factor,
    generate_core_attributes,
    position_profile,
    target_rt,
    weight_from_height,
)
from BackEnd.script_db import STAGING_DB, connect_script_database  # noqa: E402
import random as _random

DB_NAME = STAGING_DB
# Position intent: capacity-constrained fit assignment (not height banding).
# Soft per-bucket capacities 18-22% of the pool so a player is not bumped off his
# best fit purely because a bucket hit exactly 20%.
INTENT_LOWER_SHARE = 0.18
INTENT_UPPER_SHARE = 0.22
# League-wide new height aggregate (§11.2), used to break the height↔intent
# circularity for the fit score before cohort rank-mapping (§11.3 step 2).
LEAGUE_HEIGHT_MEAN = 78.0
LEAGUE_HEIGHT_SD = 3.6
# Tier bands as cumulative rank thresholds (bottom→top), from §4.1 frequencies.
TIER_ORDER = ["Poor", "BelowAverage", "Average", "Good", "Great", "Elite"]

# Populated by assign_position_intent, read by report_metrics.
_INTENT_STATS: dict = {}

# ── Exact write contract (single source of truth for writes AND the manifest) ──
# Universal pool: regenerated attributes + physicals + stored RT. FPD/FRD: the
# stored-RT staleness fix ONLY — never their live attributes/height/weight.
# entry_tier + position_intent are stored TOP-LEVEL (not in a development subdoc):
# the remap CREATES the tier/intent assignment and then rewrites the attributes it
# was derived from, so this migration is the only place they can be captured
# losslessly — post-migration they could only be re-derived approximately from RT
# (boundary players would re-derive into the wrong tier / ~5% into the wrong intent).
UNIVERSAL_WRITE_FIELDS = ("attributes", "height", "weight", "year", "position_ratings",
                          "entry_tier", "position_intent", "potential_factor")
STORED_RT_WRITE_FIELDS = ("position_ratings",)


def _universal_set_doc(p: dict) -> dict:
    return {
        "attributes": p["_attributes"],
        "height": p["_height"],
        "weight": p["_weight"],
        "year": p["_year_stored"],
        "position_ratings": p["_ratings"],
        "entry_tier": p["_tier"],
        "position_intent": p["_intent"],
        "potential_factor": p["_potential_factor"],
    }


def _num(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _overall_rt(pr: dict) -> float:
    if not isinstance(pr, dict) or not pr:
        return 0.0
    return max(_num(v) for v in pr.values())


def _skill_fit(attrs: dict, pos: str) -> float:
    """NEW position weight vector applied to the player's CURRENT attributes —
    attributes only, no height term. Deliberately NOT the stored position_ratings:
    those came from the old formula this migration replaces (PF height saturated
    at 76in so every athletic wing rated PF; PF/C shared four of five weighted
    attributes; SF was half AG+ST), so using stored RT as the identity signal
    would preserve the exact distortions we are removing."""
    return sum(POSITION_WEIGHTS[pos].get(a, 0.0) * _num(attrs.get(a)) for a in POSITION_WEIGHTS[pos])


def _league_mapped_heights(players: list[dict]) -> None:
    """Rank-map each player's height onto the LEAGUE-WIDE new distribution and
    store on ``_h_league`` (breaks the height↔intent circularity for the fit
    score; cohort rank-mapping per §11.3 step 2 still happens after intent)."""
    nd = NormalDist(LEAGUE_HEIGHT_MEAN, LEAGUE_HEIGHT_SD)
    order = sorted(players, key=lambda p: _num(p.get("height")))
    n = len(order)
    for rank, p in enumerate(order):
        p["_h_league"] = nd.inv_cdf((rank + 0.5) / n)


def assign_position_intent(players: list[dict]) -> None:
    """Capacity-constrained fit assignment (replaces height-band assignment).

    Fit(player, pos) = the player's PERCENTILE of attribute-only skill fit at pos
    (percentiles make positions comparable — different vectors load on attributes
    with different league means), MODULATED (not gated) by height_fitness at his
    league-mapped height. Maximize total fit subject to soft per-bucket capacities
    (18-22%). Method: greedy in descending fit margin (most certain placed first),
    then a lower-bound repair that pulls the highest-fit movers out of buckets with
    slack into any under-filled bucket."""
    n = len(players)
    _league_mapped_heights(players)

    # 1. attribute-only raw skill fit per position → 2. percentile per position
    #    (rank/(n-1)) → 3. modulate by height fitness at the league-mapped height.
    for pos in POSITIONS:
        raw = [(i, _skill_fit(p.get("attributes") or {}, pos)) for i, p in enumerate(players)]
        raw.sort(key=lambda t: t[1])
        for rank, (i, _v) in enumerate(raw):
            pct = rank / (n - 1) if n > 1 else 1.0
            players[i].setdefault("_fit", {})[pos] = pct * height_fitness(pos, players[i]["_h_league"])
    for p in players:
        p["_fit_rank"] = sorted(POSITIONS, key=lambda pos: -p["_fit"][pos])

    lower = round(INTENT_LOWER_SHARE * n)
    upper = round(INTENT_UPPER_SHARE * n)
    counts = {pos: 0 for pos in POSITIONS}

    def margin(p):
        f = sorted(p["_fit"].values(), reverse=True)
        return f[0] - f[1]

    for p in sorted(players, key=margin, reverse=True):
        for pos in p["_fit_rank"]:
            if counts[pos] < upper:
                p["_intent"] = pos
                counts[pos] += 1
                break

    _repair_lower_bounds(players, counts, lower)

    # Displacement rank (1 = best-fit position, 2 = second, …) and objective.
    for p in players:
        p["_disp"] = p["_fit_rank"].index(p["_intent"]) + 1
    objective = sum(p["_fit"][p["_intent"]] for p in players)
    unconstrained = sum(max(p["_fit"].values()) for p in players)
    _INTENT_STATS.clear()
    _INTENT_STATS.update(method="greedy(desc fit margin)+lower-bound repair",
                         objective=objective, unconstrained_best=unconstrained,
                         counts=dict(counts), lower=lower, upper=upper)


def _repair_lower_bounds(players: list[dict], counts: dict, lower: int) -> None:
    """Fill any bucket below ``lower`` by moving the highest-fit-to-that-bucket
    player out of a bucket that still has slack above ``lower``."""
    for _ in range(len(players)):  # bounded; each iteration fills ≥1 seat
        under = [b for b in POSITIONS if counts[b] < lower]
        if not under:
            return
        b = min(under, key=lambda x: counts[x])
        movers = [p for p in players if p["_intent"] != b and counts[p["_intent"]] > lower]
        if not movers:
            return
        best = max(movers, key=lambda p: p["_fit"][b])
        counts[best["_intent"]] -= 1
        best["_intent"] = b
        counts[b] += 1


def assign_heights(players: list[dict]) -> None:
    """Rank-map each player within his cohort onto the position height dist."""
    by_pos: dict[str, list[dict]] = {pos: [] for pos in POSITIONS}
    for p in players:
        by_pos[p["_intent"]].append(p)
    for pos, cohort in by_pos.items():
        nd = NormalDist(HEIGHT_IDEAL_IN[pos], HEIGHT_SD_IN)
        cohort_sorted = sorted(cohort, key=lambda p: _num(p.get("height")))
        n = len(cohort_sorted)
        for rank, p in enumerate(cohort_sorted):
            q = (rank + 0.5) / n  # midpoint rank → quantile (avoids the 0/1 tails)
            h = round(nd.inv_cdf(q))
            p["_height"] = max(HEIGHT_MIN_IN, min(HEIGHT_MAX_IN, h))


def assign_tiers(players: list[dict]) -> None:
    """Rank-map overall-RT percentile onto §4.1 tier bands (exact frequencies)."""
    order = sorted(players, key=lambda p: _overall_rt(p.get("position_ratings") or {}))
    n = len(order)
    idx = 0
    for i, tier in enumerate(TIER_ORDER):
        if i == len(TIER_ORDER) - 1:
            end = n
        else:
            end = idx + round(TIER_FREQUENCY[tier] * n)
        for p in order[idx:end]:
            p["_tier"] = tier
        idx = end


def assign_years(players: list[dict], rng: _random.Random) -> None:
    """Rebalance class years to ~25% each (design §11 class-size balance)."""
    order = list(players)
    rng.shuffle(order)
    n = len(order)
    per = n // len(CLASS_YEARS)
    years = [y for y in CLASS_YEARS for _ in range(per)]
    years += [rng.choice(CLASS_YEARS) for _ in range(n - len(years))]
    _YEAR_TO_STORED = {"FR": "freshman", "SO": "sophomore", "JR": "junior", "SR": "senior"}
    for p, y in zip(order, years):
        p["_year"] = y
        p["_year_stored"] = _YEAR_TO_STORED[y]


# How strongly a player's OLD attribute shape modulates the new position
# profile. 0 → identical to fresh generation (no identity); 1 → full old shape
# (explodes RT when height-assigned intent ≠ old attribute shape). A modest value
# keeps the intent profile dominant — so argmax follows intent and centre supply
# actually fills — while a shooter still reads relatively higher on SH than his
# new positional peers (design §11.3 step 4, "a shooter stays a shooter").
IDENTITY_STRENGTH = 0.15


def _blended_profile(intent: str, old: dict) -> dict | None:
    """Intent's position profile nudged toward the player's old relative shape."""
    clean = position_profile(intent)
    shape = {a: _num(old.get(f"anchor_{a}", old.get(a))) for a in CORE_ATTRS}
    mean_shape = statistics.mean(shape.values()) if any(shape.values()) else 0.0
    if mean_shape <= 0:
        return None  # no usable old shape → fall back to clean position profile
    blended = {}
    for a in CORE_ATTRS:
        rel = shape[a] / mean_shape  # 1.0 = at the player's own average
        blended[a] = max(0.05, clean[a] * (1.0 + IDENTITY_STRENGTH * (rel - 1.0)))
    return blended


def remap_attributes(players: list[dict], rng: _random.Random) -> None:
    """Redraw attribute magnitudes preserving relative ordering, hitting target."""
    for p in players:
        old = p.get("attributes") or {}
        rel = _blended_profile(p["_intent"], old)
        target = target_rt(p["_tier"], p["_year"])
        core = generate_core_attributes(p["_intent"], p["_height"], target, rng, relative_order=rel)
        attrs: dict = dict(core)
        for a in CORE_ATTRS:
            attrs[f"anchor_{a}"] = attrs[a]
        ch = int(_num(old.get("CH", old.get("anchor_CH", rng.randint(1, 100))))) or rng.randint(1, 100)
        attrs["CH"] = ch
        attrs["anchor_CH"] = ch
        attrs["EM"] = rng.randint(1, 100)
        attrs["anchor_EM"] = attrs["EM"]
        attrs["MO"] = 0
        attrs["anchor_MO"] = 0
        attrs["NG"] = 1.0
        attrs["anchor_NG"] = 1.0
        p["_attributes"] = attrs
        p["_weight"] = weight_from_height(p["_height"], rng)
        p["_ratings"] = compute_position_ratings({"attributes": attrs, "height": p["_height"]})
        p["_potential_factor"] = draw_potential_factor(rng)   # Phase 1 (behaviour-neutral until re-run)


def apply_class_year_stagger(players: list[dict], rng: _random.Random) -> None:
    """§11.3 grow-into-frame. assign_heights maps each player onto his position's ADULT
    height distribution (the fitness peak); stagger it DOWN by the remaining share of a
    drawn career HT gain for his class year (§16.3 curve, via HT_REMAINING_SHARE_BY_YEAR),
    so the migrated pool has a real height gradient — FR below frame, SR at it — instead of
    the flat ~0.34in it carried. Mirrors generation's draw_height() grow-into-frame, so a
    pool player and a freshly generated recruit of the same year/position are comparable.
    Runs AFTER assign_years and BEFORE remap_attributes, so attributes (and weight) are
    generated at the staggered height — a shorter FR gets the fitness-appropriate attribute
    mass, exactly as fresh generation does."""
    for p in players:
        remaining = HT_REMAINING_SHARE_BY_YEAR.get(p["_year"], 0.0)
        if remaining:
            gain = max(HT_TOTAL_MIN, min(HT_TOTAL_MAX, rng.gauss(HT_TOTAL_MEAN, HT_TOTAL_SD)))
            p["_height"] = max(HEIGHT_MIN_IN, round(p["_height"] - remaining * gain))


def build_remap(players: list[dict], seed: int) -> None:
    rng = _random.Random(seed)
    assign_position_intent(players)
    assign_heights(players)
    assign_tiers(players)
    assign_years(players, rng)
    apply_class_year_stagger(players, rng)
    remap_attributes(players, rng)


# ── verification (mirrors design §3.6.4) ─────────────────────────────────────

def _pct(x, d):
    return f"{100 * x / d:.1f}%" if d else "n/a"


def report_metrics(players: list[dict]) -> None:
    n = len(players)
    for p in players:
        rt = p["_ratings"]
        ranked = sorted(POSITIONS, key=lambda pos: (-rt[pos], POSITIONS.index(pos)))
        p["_argmax"] = ranked[0]
        p["_top1"] = rt[ranked[0]]
        p["_margin"] = rt[ranked[0]] - rt[ranked[1]]
    amc = Counter(p["_argmax"] for p in players)
    print("\n== §3.6.4 metrics on regenerated pool (n=%d) ==" % n)
    print("argmax:      " + " / ".join(f"{pos} {_pct(amc[pos], n)}" for pos in POSITIONS)
          + "   (target ~20 each, fitted 19.9/21.9/18.2/18.6/21.5)")
    print("median ht by argmax: " + " / ".join(
        f"{pos} {statistics.median([p['_height'] for p in players if p['_argmax']==pos]):.0f}"
        for pos in POSITIONS) + "   (fitted 73/76/79/80/83, monotonic)")
    margins = [p["_margin"] for p in players]
    print(f"margin<3: {_pct(sum(m<3 for m in margins), n)}  (fitted 11.2%)  "
          f"margin<5: {_pct(sum(m<5 for m in margins), n)}  ties: {_pct(sum(m==0 for m in margins), n)} (fitted 2.5%)")
    print("class p50 top1 RT: " + " / ".join(
        f"{y} {statistics.median([p['_top1'] for p in players if p['_year']==y]):.0f}"
        for y in CLASS_YEARS) + "   (designed 35/43/54/60)")
    print("class sizes: " + " / ".join(f"{y} {sum(p['_year']==y for p in players)}" for y in CLASS_YEARS))
    print("height p50 by class year: " + " / ".join(
        f"{y} {statistics.median([p['_height'] for p in players if p['_year']==y]):.1f}"
        for y in CLASS_YEARS) + "   (§11.3 stagger: FR below frame → SR at it; was flat ~0.34in)")
    allh = [p["_height"] for p in players]
    print(f"league height mean {statistics.mean(allh):.1f} sd {statistics.pstdev(allh):.2f} (target ~78/3.6)")
    _core = ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "IQ", "FT", "ND")
    a100 = sum(any(p["_attributes"][a] >= 100 for a in _core) for p in players)
    print(f"any attr >=100: {_pct(a100, n)} (accepted 5.5%)")

    # ── remap intent assignment (§11.3 capacity-constrained fit) ──
    print("\n== position intent assignment (capacity-constrained fit) ==")
    st = _INTENT_STATS
    print(f"method: {st.get('method')}   soft caps [{st.get('lower')},{st.get('upper')}] "
          f"({100*st.get('lower',0)/n:.0f}-{100*st.get('upper',0)/n:.0f}%)")
    print(f"objective (Σ assigned fit): {st.get('objective',0):.1f}  vs unconstrained-best "
          f"{st.get('unconstrained_best',0):.1f}  ({100*st.get('objective',0)/max(1e-9,st.get('unconstrained_best',1)):.1f}% of ceiling)")
    supply = Counter(p["_intent"] for p in players)
    print("intent supply: " + " / ".join(f"{pos} {supply[pos]} ({_pct(supply[pos], n)})" for pos in POSITIONS))
    # DISPLACEMENT — the identity-preservation metric for the remap (argmax=intent
    # is high by construction now that intent is derived from attributes).
    disp = Counter(p["_disp"] for p in players)
    print("displacement (assigned = which fit rank): "
          + "  ".join(f"{'best' if k==1 else '2nd' if k==2 else '3rd' if k==3 else f'{k}th'} {_pct(disp[k], n)}"
                      for k in sorted(disp)))
    print("(argmax matches intent, high by construction for the remap: "
          f"{_pct(sum(p['_argmax']==p['_intent'] for p in players), n)})")
    # HEIGHT by assigned intent — confirm tall players land at PF/C, not SF.
    def _p(vals, q):
        v = sorted(vals); i = (len(v)-1)*q/100; lo=int(i); hi=min(lo+1,len(v)-1)
        return v[lo] + (v[hi]-v[lo])*(i-lo)
    print("height by assigned intent (p10 / median / p90):")
    for pos in POSITIONS:
        hs = [p["_height"] for p in players if p["_intent"] == pos]
        print(f"   {pos}: {_p(hs,10):.0f} / {statistics.median(hs):.0f} / {_p(hs,90):.0f}  (n={len(hs)})")


def recompute_stored_rt(coll, franchise=False, dry=True):
    """Recompute stored position_ratings for FPD/FRD under the new formula."""
    ops, changed, total, example = [], 0, 0, None
    fields = {"attributes": 1, "position_ratings": 1}
    if franchise:
        fields.update({"meta": 1, "player_id": 1, "franchise_id": 1})
    else:
        fields.update({"height": 1, "recruit_id": 1, "franchise_id": 1})
    for d in coll.find({}, fields):
        total += 1
        a = d.get("attributes") or {}
        if franchise:
            meta = d.get("meta") or {}
            h = meta.get("height", a.get("height"))
        else:
            h = d.get("height", a.get("height"))
        new = compute_position_ratings({"attributes": a, "height": h})
        if new != d.get("position_ratings"):
            changed += 1
            if example is None:
                example = {"_id": d["_id"], "old": d.get("position_ratings"), "new": new}
            if not dry:
                ops.append(UpdateOne({"_id": d["_id"]}, {"$set": {"position_ratings": new}}))
    if ops and not dry:
        for i in range(0, len(ops), 500):
            coll.bulk_write(ops[i:i + 500], ordered=False)
    return changed, total, example


def _fmt_doc(d: dict, keys) -> str:
    import json
    return json.dumps({k: d.get(k) for k in keys}, default=str, sort_keys=True)


def print_field_manifest(db_name, players, fpd_ex, fpd_changed, fpd_total,
                         frd_ex, frd_changed, frd_total) -> None:
    """Field-level pre-flight: exactly what each collection would be written."""
    print("\n" + "=" * 72)
    print("FIELD-LEVEL WRITE MANIFEST (dry-run — nothing written)")
    print("=" * 72)
    print(f"Database: {db_name}   (only)")
    print("Write operator: $set only. No delete_one/delete_many/drop, no")
    print("replace_one — existing docs are updated in place, identity fields")
    print("(_id, player_id, first_name, last_name, photo, team, jersey,")
    print("scouting_report, stats) are never in any $set and are untouched.")

    # ── universal players ──
    ex = players[0]
    attr_keys = sorted(ex["_attributes"].keys())
    print("\n--- collection: players (universal pool) ---")
    print(f"  docs written: {len(players)}")
    print(f"  $set field paths: {', '.join(UNIVERSAL_WRITE_FIELDS)}")
    print(f"    · attributes  → whole subdoc replaced, {len(attr_keys)} keys: {attr_keys}")
    print(f"      (includes anchor_* mirrors: {sum(k.startswith('anchor_') for k in attr_keys)} keys)")
    print("    · height, weight, year (class year), position_ratings → top-level")
    print("    · entry_tier, position_intent → top-level (captured here — the remap")
    print("      destroys the evidence they were derived from; not reconstructible later)")
    print("  NOT written: the rest of the development subdoc (peak_count, family_timing,")
    print("    ch_seed, training_position, focus_accumulator) — OUT OF SCOPE this pass.")
    before = {k: ex.get(k) for k in ("height", "weight", "year")}
    before["position_ratings"] = ex.get("position_ratings")
    before["attributes(SC,SH,ID,RB,ST,anchor_SC)"] = {
        k: (ex.get("attributes") or {}).get(k) for k in ("SC", "SH", "ID", "RB", "ST", "anchor_SC")}
    after = {"height": ex["_height"], "weight": ex["_weight"], "year": ex["_year_stored"],
             "position_ratings": ex["_ratings"],
             "entry_tier": ex["_tier"], "position_intent": ex["_intent"],
             "attributes(SC,SH,ID,RB,ST,anchor_SC)": {
                 k: ex["_attributes"].get(k) for k in ("SC", "SH", "ID", "RB", "ST", "anchor_SC")}}
    print(f"  example _id={ex.get('_id')}  name={ex.get('first_name')} {ex.get('last_name')}")
    print(f"    BEFORE: {before}")
    print(f"    AFTER : {after}")

    # ── FPD / FRD ──
    for label, coll, ex_rt, changed, total in (
        ("franchise_players_data (FPD)", "franchise_players_data", fpd_ex, fpd_changed, fpd_total),
        ("franchise_recruits_data (FRD)", "franchise_recruits_data", frd_ex, frd_changed, frd_total),
    ):
        print(f"\n--- collection: {label} ---")
        print(f"  docs written: {changed} of {total} (only those whose stored RT differs)")
        print(f"  $set field paths: {', '.join(STORED_RT_WRITE_FIELDS)}   ← position_ratings ONLY")
        assert set(STORED_RT_WRITE_FIELDS) == {"position_ratings"}, "RED FLAG: FPD/FRD write set changed"
        assert not any(f in STORED_RT_WRITE_FIELDS for f in ("attributes", "height", "weight", "meta")), \
            "RED FLAG: FPD/FRD would write live roster data"
        if ex_rt:
            print(f"  example _id={ex_rt['_id']}")
            print(f"    BEFORE position_ratings: {ex_rt['old']}")
            print(f"    AFTER  position_ratings: {ex_rt['new']}")
        else:
            print("  (no changed doc found to sample)")
    print("\nRED-FLAG CHECK: no attribute/height/weight/meta field appears in the")
    print("FPD or FRD write set — live franchise rosters are NOT rewritten. PASS.")
    print("=" * 72)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", choices=[DB_NAME], default=DB_NAME)
    ap.add_argument("--seed", type=int, default=20260729)
    ap.add_argument("--commit", action="store_true", help="persist writes (default dry-run)")
    ap.add_argument("--i-have-a-backup", action="store_true",
                    help="required with --commit; confirms backup_gob_staging_players.py was run")
    args = ap.parse_args()

    commit = args.commit
    if commit and not args.i_have_a_backup:
        raise SystemExit("Refusing to --commit without --i-have-a-backup (run backup_gob_staging_players.py first).")

    connection = connect_script_database(
        target=args.db,
        access="write" if commit else "read",
        pristine_env=dict(os.environ),
        repo_root=ROOT,
    )
    db = connection.database
    players = list(db["players"].find({}))
    print(f"loaded {len(players)} universal players from {args.db}.players")

    build_remap(players, args.seed)
    report_metrics(players)

    # Dry pass over FPD/FRD to count changes and capture before/after examples.
    fpd_changed, fpd_total, fpd_ex = recompute_stored_rt(db["franchise_players_data"], franchise=True, dry=True)
    frd_changed, frd_total, frd_ex = recompute_stored_rt(db["franchise_recruits_data"], franchise=False, dry=True)

    print_field_manifest(args.db, players, fpd_ex, fpd_changed, fpd_total, frd_ex, frd_changed, frd_total)

    print(f"\nMODE: {'COMMIT' if commit else 'DRY-RUN (no writes)'}")
    if commit:
        ops = [UpdateOne({"_id": p["_id"]}, {"$set": _universal_set_doc(p)}) for p in players]
        for i in range(0, len(ops), 500):
            db["players"].bulk_write(ops[i:i + 500], ordered=False)
        print(f"  universal pool: updated {len(ops)} docs")
        fpd_changed, fpd_total, _ = recompute_stored_rt(db["franchise_players_data"], franchise=True, dry=False)
        frd_changed, frd_total, _ = recompute_stored_rt(db["franchise_recruits_data"], franchise=False, dry=False)

    verb = "would recompute" if not commit else "recomputed"
    print(f"  FPD stored RT: {verb} {fpd_changed}/{fpd_total}")
    print(f"  FRD stored RT: {verb} {frd_changed}/{frd_total}")
    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
