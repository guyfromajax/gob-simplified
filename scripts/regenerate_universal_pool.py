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

from pymongo import MongoClient
from pymongo.operations import UpdateOne

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.utils.position_ratings import compute_position_ratings  # noqa: E402
from BackEnd.utils.player_generation import (  # noqa: E402
    CLASS_YEARS,
    CORE_ATTRS,
    HEIGHT_IDEAL_IN,
    HEIGHT_MAX_IN,
    HEIGHT_MIN_IN,
    HEIGHT_SD_IN,
    POSITIONS,
    TIER_FREQUENCY,
    generate_core_attributes,
    position_profile,
    target_rt,
    weight_from_height,
)
import random as _random

DB_NAME = "gob-staging"
# Target position supply from tallest→shortest bands (design §11.3 step 1).
INTENT_BANDS = [("C", 0.20), ("PF", 0.20), ("SF", 0.20)]  # remainder = guards (PG+SG)
# Tier bands as cumulative rank thresholds (bottom→top), from §4.1 frequencies.
TIER_ORDER = ["Poor", "BelowAverage", "Average", "Good", "Great", "Elite"]

# ── Exact write contract (single source of truth for writes AND the manifest) ──
# Universal pool: regenerated attributes + physicals + stored RT. FPD/FRD: the
# stored-RT staleness fix ONLY — never their live attributes/height/weight.
# entry_tier + position_intent are stored TOP-LEVEL (not in a development subdoc):
# the remap CREATES the tier/intent assignment and then rewrites the attributes it
# was derived from, so this migration is the only place they can be captured
# losslessly — post-migration they could only be re-derived approximately from RT
# (boundary players would re-derive into the wrong tier / ~5% into the wrong intent).
UNIVERSAL_WRITE_FIELDS = ("attributes", "height", "weight", "year", "position_ratings",
                          "entry_tier", "position_intent")
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
    }


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        v = line.strip()
        if v and not v.startswith("#") and "=" in v:
            k, raw = v.split("=", 1)
            os.environ.setdefault(k.strip(), raw.strip().strip('"').strip("'"))


def _num(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _overall_rt(pr: dict) -> float:
    if not isinstance(pr, dict) or not pr:
        return 0.0
    return max(_num(v) for v in pr.values())


def assign_position_intent(players: list[dict]) -> None:
    """Assign ``_intent`` to each player by height band (§11.3 step 1)."""
    order = sorted(players, key=lambda p: _num(p.get("height")), reverse=True)
    n = len(order)
    idx = 0
    for pos, share in INTENT_BANDS:
        end = idx + round(share * n)
        for p in order[idx:end]:
            p["_intent"] = pos
        idx = end
    # Remaining tallest→shortest are guards; split by ball-handling+passing (PG)
    # vs shooting+perimeter-defence (SG), balanced within the guard band.
    guards = order[idx:]

    def guard_score(p):
        a = p.get("attributes") or {}
        pg_lean = _num(a.get("anchor_BH", a.get("BH"))) + _num(a.get("anchor_PS", a.get("PS")))
        sg_lean = _num(a.get("anchor_SH", a.get("SH"))) + _num(a.get("anchor_OD", a.get("OD")))
        return pg_lean - sg_lean

    guards_sorted = sorted(guards, key=guard_score, reverse=True)
    half = len(guards_sorted) // 2
    for p in guards_sorted[:half]:
        p["_intent"] = "PG"
    for p in guards_sorted[half:]:
        p["_intent"] = "SG"


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


def build_remap(players: list[dict], seed: int) -> None:
    rng = _random.Random(seed)
    assign_position_intent(players)
    assign_heights(players)
    assign_tiers(players)
    assign_years(players, rng)
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
    print(f"argmax matches intent: {_pct(sum(p['_argmax']==p['_intent'] for p in players), n)} (fitted 95.3%)")
    print("class p50 top1 RT: " + " / ".join(
        f"{y} {statistics.median([p['_top1'] for p in players if p['_year']==y]):.0f}"
        for y in CLASS_YEARS) + "   (designed 35/43/54/60)")
    print("class sizes: " + " / ".join(f"{y} {sum(p['_year']==y for p in players)}" for y in CLASS_YEARS))
    allh = [p["_height"] for p in players]
    print(f"league height mean {statistics.mean(allh):.1f} sd {statistics.pstdev(allh):.2f} (target ~78/3.6)")
    _core = ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "IQ", "FT", "ND")
    a100 = sum(any(p["_attributes"][a] >= 100 for a in _core) for p in players)
    print(f"any attr >=100: {_pct(a100, n)} (accepted 5.5%)")


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
    ap.add_argument("--db", default=DB_NAME)
    ap.add_argument("--seed", type=int, default=20260729)
    ap.add_argument("--commit", action="store_true", help="persist writes (default dry-run)")
    ap.add_argument("--i-have-a-backup", action="store_true",
                    help="required with --commit; confirms backup_gob_staging_players.py was run")
    args = ap.parse_args()

    for f in (ROOT / ".env.local", ROOT / ".env"):
        _load_env(f)
    uri = os.environ.get("MONGO_URI")
    if not uri:
        raise SystemExit("MONGO_URI not set")
    commit = args.commit
    if commit and not args.i_have_a_backup:
        raise SystemExit("Refusing to --commit without --i-have-a-backup (run backup_gob_staging_players.py first).")

    client = MongoClient(uri, serverSelectionTimeoutMS=20000)
    db = client[args.db]
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
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
