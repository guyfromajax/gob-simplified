#!/usr/bin/env python3
"""
recalibrate_pool_physicals.py — targeted, idempotent HT/WT/RT recal of the universal pool.

WHY: franchise init draws 12 of 15 roster players from gob-staging.players, so ~80% of every
roster is still at the OLD height/weight scale and only walk-ons are fresh. This pulls the pool
onto the CURRENT physical scale so rosters can be evaluated — WITHOUT redoing the full migration
(attribute remap / tier / intent are correct and are NOT touched).

SCOPE (hard): gob-staging.players ONLY. Fields written: height, weight, position_ratings.
  Left alone: attributes, entry_tier, position_intent, potential_factor, year, names, portraits.
  Never touches franchise_players_data / franchise_recruits_data / recruit_sets / teams / gob.

METHOD (idempotent, re-runnable — the scale will be shifted again after roster review):
  height  rank-map each (position_intent, class-year) cohort onto that cohort's CURRENT target
          Normal(ideal − remaining·HT_gain, √(sd² + (remaining·HT_sd)²)) via inv_cdf. Rank-mapping
          onto a FIXED target is idempotent (re-run → same answer); "subtract N inches" is NOT
          (it compounds). Grow-into-frame survives because each class-year maps onto its own,
          lower-for-younger target.
  weight  recompute from the continuous line WEIGHT_AT_MEDIAN + slope·(h − median) + noise, where
          noise is derived DETERMINISTICALLY from player_id (sha256, same technique as
          potential_factor) so it does not jitter on re-run.
  ratings recompute position_ratings from (unchanged attributes, new height).

All targets are imported live from the generator constants, so when the height scale is shifted
again the edit lands in one place and this script re-maps onto the new target on the next run.

Usage:
    .venv/bin/python scripts/recalibrate_pool_physicals.py            # dry-run + manifest
    .venv/bin/python scripts/recalibrate_pool_physicals.py --commit   # backup + write
"""
from __future__ import annotations

import argparse
import hashlib
import os
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist

from pymongo.operations import UpdateOne

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.constants import LEAGUE_MEDIAN_HEIGHT_IN  # noqa: E402
from BackEnd.utils.player_generation import (  # noqa: E402
    HEIGHT_IDEAL_IN,
    HEIGHT_MAX_IN,
    HEIGHT_MIN_IN,
    HEIGHT_SD_IN,
    HT_REMAINING_SHARE_BY_YEAR,
    HT_TOTAL_MEAN,
    HT_TOTAL_SD,
    POSITIONS,
    WEIGHT_AT_MEDIAN,
    WEIGHT_LB_PER_INCH,
    WEIGHT_NOISE_LB,
    normalize_year,
)
from BackEnd.utils.position_ratings import compute_position_ratings  # noqa: E402
from BackEnd.script_db import STAGING_DB, connect_script_database  # noqa: E402

DB_NAME = STAGING_DB
COLLECTION = "players"
# The ONLY fields this script writes — asserted against the $set doc before every write.
WRITE_FIELDS = ("height", "weight", "position_ratings")


def _num(v, d=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _quantile(xs: list[float], p: float) -> float:
    """Linear-interpolated quantile (p in [0,1])."""
    if not xs:
        return 0.0
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    idx = p * (len(s) - 1)
    lo = int(idx)
    frac = idx - lo
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * frac


def _argmax_pos(pr: dict) -> str | None:
    if not isinstance(pr, dict) or not pr:
        return None
    return max(pr.items(), key=lambda kv: _num(kv[1]))[0]


# ── Recal steps ───────────────────────────────────────────────────────────────

def _cohort_target(pos: str, norm_year: str) -> tuple[float, float]:
    """Target (mean, sd) height for a (position_intent, class-year) cohort — the marginal
    the generator produces: adult frame Normal(ideal, HEIGHT_SD) shifted down by the REMAINING
    share of the career HT gain (grow-into-frame), variances adding."""
    remaining = HT_REMAINING_SHARE_BY_YEAR.get(norm_year, 0.0)
    mean = HEIGHT_IDEAL_IN[pos] - remaining * HT_TOTAL_MEAN
    sd = (HEIGHT_SD_IN ** 2 + (remaining * HT_TOTAL_SD) ** 2) ** 0.5
    return mean, sd


def recal_height(players: list[dict]) -> None:
    """Rank-map each (intent, class-year) cohort onto its target Normal. Stable tie-break by
    player_id so the rank order — and thus every assigned height — is deterministic and a fixed
    point under re-run."""
    cohorts: dict[tuple[str, str], list[dict]] = {}
    for p in players:
        pos = str(p.get("position_intent"))
        if pos not in HEIGHT_IDEAL_IN:
            raise SystemExit(f"player {p.get('player_id')}: intent {pos!r} not a real position")
        ny = normalize_year(p.get("year"))
        cohorts.setdefault((pos, ny), []).append(p)

    for (pos, ny), cohort in cohorts.items():
        mean, sd = _cohort_target(pos, ny)
        nd = NormalDist(mean, sd)
        # ascending by (current height, player_id) → shortest keeps the lowest quantile
        cohort.sort(key=lambda p: (_num(p.get("height")), str(p.get("player_id"))))
        n = len(cohort)
        for rank, p in enumerate(cohort):
            h = nd.inv_cdf((rank + 0.5) / n)
            p["_height"] = max(HEIGHT_MIN_IN, min(HEIGHT_MAX_IN, round(h)))


def _weight_noise(player_id) -> float:
    """Uniform noise in [−WEIGHT_NOISE_LB, +WEIGHT_NOISE_LB], deterministic in player_id (salted
    so it does not correlate with the potential_factor hash)."""
    h = int(hashlib.sha256(f"weight:{player_id}".encode("utf-8")).hexdigest()[:12], 16)
    u = h / float(16 ** 12)  # deterministic uniform in [0,1)
    return -WEIGHT_NOISE_LB + u * 2.0 * WEIGHT_NOISE_LB


def recal_weight(players: list[dict]) -> None:
    """Continuous line from the NEW height + deterministic per-player noise. No compounding."""
    for p in players:
        base = WEIGHT_AT_MEDIAN + WEIGHT_LB_PER_INCH * (p["_height"] - LEAGUE_MEDIAN_HEIGHT_IN)
        p["_weight"] = max(1, round(base + _weight_noise(p.get("player_id"))))


def recal_ratings(players: list[dict]) -> None:
    for p in players:
        p["_ratings"] = compute_position_ratings(
            {"attributes": p.get("attributes") or {}, "height": p["_height"]}
        )


def build(players: list[dict]) -> None:
    recal_height(players)   # sets _height
    recal_weight(players)   # reads _height → _weight
    recal_ratings(players)  # reads _height → _ratings


def _set_doc(p: dict) -> dict:
    doc = {"height": p["_height"], "weight": p["_weight"], "position_ratings": p["_ratings"]}
    assert set(doc) == set(WRITE_FIELDS), "RED FLAG: write set drifted from the height/weight/RT contract"
    return doc


# ── Report ─────────────────────────────────────────────────────────────────────

def _pct_line(label: str, before: list[float], after: list[float]) -> str:
    b = (_quantile(before, .1), _quantile(before, .5), _quantile(before, .9))
    a = (_quantile(after, .1), _quantile(after, .5), _quantile(after, .9))
    return (f"  {label:6} before {b[0]:5.0f}/{b[1]:5.0f}/{b[2]:5.0f}   "
            f"after {a[0]:5.0f}/{a[1]:5.0f}/{a[2]:5.0f}")


def report(db_name: str, players: list[dict]) -> None:
    print("=" * 78)
    print("POOL PHYSICAL RECAL — DRY-RUN MANIFEST")
    print("=" * 78)
    print(f"TARGET   database={db_name!r}  collection={COLLECTION!r}")
    print(f"WRITES   field paths: {', '.join(WRITE_FIELDS)}   (nothing else)")
    print(f"DOCS     {len(players)}")

    # 1. HT/WT p10/p50/p90 by position (intent), before vs after
    print("\nHEIGHT  p10/p50/p90 (in), by position_intent")
    for pos in POSITIONS:
        cp = [p for p in players if str(p.get("position_intent")) == pos]
        print(_pct_line(pos, [_num(p.get("height")) for p in cp], [p["_height"] for p in cp]))
    print(_pct_line("ALL", [_num(p.get("height")) for p in players], [p["_height"] for p in players]))

    print("\nWEIGHT  p10/p50/p90 (lb), by position_intent")
    for pos in POSITIONS:
        cp = [p for p in players if str(p.get("position_intent")) == pos]
        print(_pct_line(pos, [_num(p.get("weight")) for p in cp], [p["_weight"] for p in cp]))
    print(_pct_line("ALL", [_num(p.get("weight")) for p in players], [p["_weight"] for p in players]))

    # 2. class-year height gradient (grow-into-frame must remain monotone FR<SO<JR<SR)
    print("\nCLASS-YEAR HEIGHT GRADIENT  mean height by class-year (grow-into-frame)")
    order = ["JH", "FR", "SO", "JR", "SR"]
    years_present = [y for y in order if any(normalize_year(p.get("year")) == y for p in players)]
    print("  year   before   after")
    prev = None
    monotone = True
    for y in years_present:
        cp = [p for p in players if normalize_year(p.get("year")) == y]
        mb = statistics.mean(_num(p.get("height")) for p in cp)
        ma = statistics.mean(p["_height"] for p in cp)
        if prev is not None and ma < prev:
            monotone = False
        prev = ma
        print(f"  {y:5}  {mb:6.2f}  {ma:6.2f}   (n={len(cp)})")
    print(f"  → after-gradient monotone increasing (younger shorter): {'YES ✓' if monotone else 'NO ✗'}")

    # 3. position supply / argmax change (should barely move — attributes untouched)
    before_arg = Counter(_argmax_pos(p.get("position_ratings") or {}) for p in players)
    after_arg = Counter(_argmax_pos(p["_ratings"]) for p in players)
    moved = sum(1 for p in players
                if _argmax_pos(p.get("position_ratings") or {}) != _argmax_pos(p["_ratings"]))
    print("\nPOSITION SUPPLY (argmax of position_ratings)  before → after")
    for pos in POSITIONS:
        print(f"  {pos:3}  {before_arg.get(pos, 0):4d} → {after_arg.get(pos, 0):4d}")
    print(f"  argmax moved for {moved}/{len(players)} players "
          f"({100.0*moved/len(players):.1f}%) — expect small; large ⇒ something over-reached")

    # 4. examples
    print("\nEXAMPLES  (name · intent · year : height, weight  before → after)")
    for p in players[:6]:
        nm = f"{p.get('first_name','?')} {p.get('last_name','?')}"[:22]
        print(f"  {nm:22} {str(p.get('position_intent')):3} {normalize_year(p.get('year')):3} : "
              f"{_num(p.get('height')):.0f}in,{_num(p.get('weight')):.0f}lb → "
              f"{p['_height']}in,{p['_weight']}lb")

    # 5. idempotency self-check: re-run on the post-update state, expect zero drift
    shadow = [{"player_id": p.get("player_id"), "position_intent": p.get("position_intent"),
               "year": p.get("year"), "attributes": p.get("attributes"),
               "height": p["_height"], "weight": p["_weight"]} for p in players]
    build(shadow)
    dh = sum(1 for p, s in zip(players, shadow) if p["_height"] != s["_height"])
    dw = sum(1 for p, s in zip(players, shadow) if p["_weight"] != s["_weight"])
    dr = sum(1 for p, s in zip(players, shadow) if p["_ratings"] != s["_ratings"])
    print(f"\nIDEMPOTENCY  re-run on post-update state changes: "
          f"height {dh}, weight {dw}, ratings {dr}  (all 0 ⇒ safe to re-run) "
          f"{'✓' if (dh == dw == dr == 0) else '✗ NOT IDEMPOTENT'}")
    print("=" * 78)


# ── Backup + main ────────────────────────────────────────────────────────────────

def _backup(db, db_name: str) -> str:
    """Server-side copy of players → a fresh timestamped collection. Never overwrites."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    name = f"players_backup_htwt_recal_{ts}"
    src_n = db[COLLECTION].count_documents({})
    db[COLLECTION].aggregate([{"$match": {}}, {"$out": name}])
    dst_n = db[name].count_documents({})
    if dst_n != src_n:
        raise SystemExit(f"backup count mismatch: src={src_n} dst={dst_n}")
    print(f"BACKUP   {db_name}.{COLLECTION} ({src_n}) → {db_name}.{name}")
    return name


def main() -> int:
    ap = argparse.ArgumentParser(description="Idempotent HT/WT/RT recal of gob-staging.players")
    ap.add_argument("--db", choices=[DB_NAME], default=DB_NAME)
    ap.add_argument("--commit", action="store_true", help="back up then persist writes (default dry-run)")
    args = ap.parse_args()

    connection = connect_script_database(
        target=args.db,
        access="write" if args.commit else "read",
        pristine_env=dict(os.environ),
        repo_root=ROOT,
    )
    db = connection.database

    # HARD GUARD: never write anywhere but gob-staging.
    if db.name != DB_NAME:
        raise SystemExit(f"Refusing: target DB is {db.name!r}, expected {DB_NAME!r}. No writes performed.")

    players = list(db[COLLECTION].find({}))
    print(f"loaded {len(players)} pool players from {db.name}.{COLLECTION}\n")

    build(players)
    report(db.name, players)

    print(f"\nMODE: {'COMMIT' if args.commit else 'DRY-RUN (no writes)'}")
    if args.commit:
        assert db.name == DB_NAME, "guard bypassed"  # belt-and-braces before any write
        _backup(db, db.name)
        ops = [UpdateOne({"_id": p["_id"]}, {"$set": _set_doc(p)}) for p in players]
        for i in range(0, len(ops), 500):
            db[COLLECTION].bulk_write(ops[i:i + 500], ordered=False)
        print(f"  {db.name}.{COLLECTION}: updated {len(ops)} docs (height, weight, position_ratings)")
    else:
        print("  (no writes — re-run with --commit to back up and persist)")

    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
