#!/usr/bin/env python3
"""In-season training NET-EFFECT sim — new Player Attribute + Development systems.

Read-only. No Mongo, no writes. It:
  1. Generates a synthetic cohort with the REAL `generate_player` (new 6-tier attribute
     system: new RT formula, −2 height, tier anchors), one draw per year × position × tier.
  2. Runs the REAL `execute_training` for weeks 2-26 (the in-season path: per-year
     PRE_TRAINING_DECAY_BY_YEAR decay, then the per-position point-discounted gains, then
     floors) under the auto-train allocation.
  3. Reports the WITHIN-SEASON net effect on player attributes, by class year.

This is the trajectory a user sees on the training report / player card DURING the season.
(The level-only offseason then re-anchors RT onto the class-year ladder at season end — so
pure level loss is re-leveled next offseason; shape distortion and the in-season feel are not.)

It sweeps pre-training decay ×1.0 (current) / ×0.5 / ×0.0 to preview the "reduce the decay"
lever WITHOUT touching the per-position point discount.

    python scripts/in_season_training_net_effect.py --per-year 150 --seed 42
"""
import argparse
import copy
import logging
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logging.disable(logging.CRITICAL)  # silence the training logger's per-week spam

from BackEnd.utils.player_generation import generate_player, draw_position_intent, draw_tier  # noqa: E402
from BackEnd.utils.position_ratings import compute_position_ratings  # noqa: E402
from BackEnd.utils import player_development as dev  # noqa: E402  (reference_allocation)
import BackEnd.models.training_execution_v2 as te  # noqa: E402
import BackEnd.constants.training_shape as ts  # noqa: E402  (TRAINING_GAIN_PERCENTAGES)
from scripts.team_attr_season_dry_run import _auto_train_allocations  # noqa: E402

GAIN_BOOST_EXCLUDE = {"FT", "IQ", "ND"}  # universal 100% attrs — not boosted


def boosted_gain_table(pct: float) -> dict:
    """TRAINING_GAIN_PERCENTAGES with every non-(FT/IQ/ND) cell scaled by (1 + pct/100),
    rounded to int (uncapped — a cell may exceed 100 = amplified gain)."""
    mult = 1.0 + pct / 100.0
    return {pos: {a: (v if a in GAIN_BOOST_EXCLUDE else round(v * mult)) for a, v in row.items()}
            for pos, row in ts.TRAINING_GAIN_PERCENTAGES.items()}

YEARS = ["Freshman", "Sophomore", "Junior", "Senior"]
POSITIONS = ["PG", "SG", "SF", "PF", "C"]
CORE = te.TRAINABLE_PLAYER_ATTRS
DECAY_SCENARIOS = (1.0, 0.5, 0.0)

# growth attribute → drill-slider path (mirrors tests/test_in_season_invariants.py::_DRILL)
_DRILL = {
    "SC": ("offense", "inside"), "SH": ("offense", "outside"),
    "ID": ("defense", "inside"), "OD": ("defense", "outside"),
    "PS": ("technical", "passing"), "BH": ("technical", "ball_handling"),
    "RB": ("technical", "rebounding"), "ST": ("weight_room", "strength"),
    "AG": ("weight_room", "agility"),
    "ND": ("general", "conditioning"), "FT": ("general", "free_throws"),
    "IQ": ("general", "film_study"),
}


def _alloc_from_points(points: dict) -> dict:
    a = {"player_drills": {"offense": {"inside": 0, "outside": 0}, "defense": {"inside": 0, "outside": 0},
                           "technical": {"passing": 0, "ball_handling": 0, "rebounding": 0},
                           "weight_room": {"strength": 0, "agility": 0}},
         "general": {"conditioning": 0, "free_throws": 0, "film_study": 0, "breaks": 1},
         "team_drills": {}}
    for attr, p in points.items():
        grp, key = _DRILL.get(attr, (None, None))
        if grp is None:
            continue
        (a["general"] if grp == "general" else a["player_drills"][grp])[key] = int(p)
    return a


# The per-position REFERENCE allocation (coaching-quality baseline; Invariant 2 pins its
# RT net to ~flat), as a ready drill-slider dict per position.
REFERENCE_ALLOC_BY_POS = {pos: _alloc_from_points(dev.reference_allocation(pos)) for pos in POSITIONS}


def _rt_at(player) -> float:
    ratings = compute_position_ratings({"attributes": player["attributes"], "height": player["height"]})
    pos = player.get("training_position") or player.get("position_intent")
    return float(ratings.get(pos, max(ratings.values())))


def _total(player) -> int:
    return sum(int(player["attributes"][a]) for a in CORE)


def make_cohort(per_year: int, rng: random.Random) -> list[dict]:
    players, pid = [], 0
    for year in YEARS:
        for _ in range(per_year):
            intent = draw_position_intent(rng)
            tier = draw_tier(rng)
            gp = generate_player(intent, year, tier, rng)
            pid += 1
            players.append({
                "_id": str(pid), "first_name": "P", "last_name": str(pid),
                "year": year, "position_intent": intent, "training_position": intent,
                "attributes": gp["attributes"], "position_ratings": gp["position_ratings"],
                "height": gp["height"], "weight": gp["weight"], "tier": tier,
            })
    return players


def scaled_decay(orig: dict, scale: float) -> dict:
    return {k: (round(lo * scale), round(hi * scale)) for k, (lo, hi) in orig.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-year", type=int, default=150)
    ap.add_argument("--weeks", type=int, default=25, help="in-season weeks (2..2+weeks-1)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--gain-pct-boost", type=float, default=0.0,
                    help="if set, boost every TRAINING_GAIN_PERCENTAGES cell (except FT/IQ/ND) by this %% "
                         "and compare baseline vs boosted at current decay (instead of the decay sweep)")
    args = ap.parse_args()

    orig_decay = dict(te.PRE_TRAINING_DECAY_BY_YEAR)

    cohort0 = make_cohort(args.per_year, random.Random(args.seed))
    start = {p["_id"]: (_rt_at(p), _total(p)) for p in cohort0}

    def season(players, alloc_mode, alloc_rng):
        """Train `players` in place for the in-season weeks under `alloc_mode`."""
        if alloc_mode == "reference":
            by_pos = {pos: [p for p in players if p["training_position"] == pos] for pos in POSITIONS}
            for pos, group in by_pos.items():
                if not group:
                    continue
                team = {}
                for _wk in range(args.weeks):
                    group, team, *_ = te.execute_training(
                        group, team, REFERENCE_ALLOC_BY_POS[pos], skip_pre_training_depreciation=False)
        else:  # auto-train
            team = {}
            for _wk in range(args.weeks):
                players, team, *_ = te.execute_training(
                    players, team, _auto_train_allocations(24, alloc_rng), skip_pre_training_depreciation=False)

    orig_gain = {p: dict(r) for p, r in ts.TRAINING_GAIN_PERCENTAGES.items()}

    def run(alloc_mode, scale, gain_table=None):
        te.PRE_TRAINING_DECAY_BY_YEAR.clear()
        te.PRE_TRAINING_DECAY_BY_YEAR.update(scaled_decay(orig_decay, scale))
        ts.TRAINING_GAIN_PERCENTAGES.clear()
        ts.TRAINING_GAIN_PERCENTAGES.update(gain_table or orig_gain)
        te.random.seed(args.seed)                      # execute_training draws from module `random`
        players = copy.deepcopy(cohort0)
        season(players, alloc_mode, random.Random(args.seed + 1))
        out = {y: [] for y in YEARS}
        for p in players:
            out[p["year"]].append(_rt_at(p) - start[p["_id"]][0])
        return {y: statistics.mean(v) for y, v in out.items()}

    print(f"cohort: {len(cohort0)} players ({args.per_year}/yr, real generate_player) | "
          f"in-season weeks 2-{1 + args.weeks} | seed {args.seed}")
    print("cells = mean ΔRT per player over the season (within-season, pre-offseason re-level)\n")

    if args.gain_pct_boost:
        boosted = boosted_gain_table(args.gain_pct_boost)
        print(f"GAIN-TABLE experiment: +{args.gain_pct_boost:.0f}% on all cells except {sorted(GAIN_BOOST_EXCLUDE)} | "
              f"decay at ×1.0 (current)\n")
        for mode in ("reference", "auto"):
            base = run(mode, 1.0, gain_table=orig_gain)
            boost = run(mode, 1.0, gain_table=boosted)
            note = "calibration baseline — Invariant 2 band (−5,+6)" if mode == "reference" else "typical/CPU spread"
            print(f"── {mode.upper()} allocation  ({note}) ──")
            print(f"{'year':<11}{'baseline':>10}{'+' + str(int(args.gain_pct_boost)) + '% gains':>12}{'Δ':>7}")
            for y in YEARS:
                print(f"{y:<11}{base[y]:>+10.1f}{boost[y]:>+12.1f}{boost[y] - base[y]:>+7.1f}")
            print()
    else:
        header = "".join(f"×{s:<5}" for s in DECAY_SCENARIOS)
        for mode in ("reference", "auto"):
            results = {scale: run(mode, scale) for scale in DECAY_SCENARIOS}
            note = "calibration baseline — Invariant 2 expects ≈flat" if mode == "reference" else "typical/CPU spread"
            print(f"── {mode.upper()} allocation  ({note}) ──   decay scale →")
            print(f"{'year':<11}{header}")
            for y in YEARS:
                print(f"{y:<11}" + "".join(f"{results[s][y]:>+6.1f}" for s in DECAY_SCENARIOS))
            print()
        print("decay ranges (per attr/week):  " + " | ".join(
            f"×{s}: FR/SO {scaled_decay(orig_decay, s)['freshman']}, JR/SR {scaled_decay(orig_decay, s)['junior']}"
            for s in DECAY_SCENARIOS))

    te.PRE_TRAINING_DECAY_BY_YEAR.clear()
    te.PRE_TRAINING_DECAY_BY_YEAR.update(orig_decay)
    ts.TRAINING_GAIN_PERCENTAGES.clear()
    ts.TRAINING_GAIN_PERCENTAGES.update(orig_gain)


if __name__ == "__main__":
    main()
