#!/usr/bin/env python3
"""S2 3-Tier Drive — Monte-Carlo tuner (Dynamic_MM_Brief §S2).

Measures the HCO drive-contest OUTCOME DISTRIBUTION and how the S2 knobs move it. Like the S1 tuner,
it reuses the REAL shipped functions so a sweep truly exercises the live logic (not a re-implementation):

  spine  `_resolve_hco_drive_contest`  (attack_drive_clearance) → `_resolve_moment` (dynamic_hct)
         one D8 roll → (tier, stop_fraction, contact). tier ∈ {A blow-by, B neutral, C clean stop};
         contact ∈ {D_FOUL, O_FOUL, DEAD BALL}. Team quality enters as off_eff/def_eff × d6.
  S2c    `_resolve_hco_help_cutoff` (attack_drive_clearance) → `best_cutoff_on_drive` (cutoff geometry)
         + `resolve_cutoff_contest`. On a blow-by, a help defender may race to the drive line and demote it.

No game/DB is needed: the contest reads only player `.attributes` + team `.team_attributes` /
`.strategy_calls`, all of which are mocked here. The absolute rates depend on the mock attribute
distribution (documented below) — read the SHAPE and the SWEEP deltas, which are robust, not the exact %.

Sweeps (override the REAL module constant, so the swept value is what the shipped function uses):
  1. `DRIVE_NEUTRAL_BAND` — the win/lose gate width → how much of the field lands in Tier B.
  2. matchup lean (off_eff/def_eff + attribute means) at the shipped band → A/B/C shift with team quality.
  3. `HCO_CUTOFF_PATH_CORRIDOR` × aggression — S2c blow-by demotion rate under a fixed help layout.

Run:  MONGO_URI="" MONGO_DB_NAME="gob-test" python3 scripts/s2_drive_monte_carlo.py
"""
import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import BackEnd.engine.attack_drive_clearance as adc
from BackEnd.engine.attack_drive_clearance import (
    _resolve_hco_drive_contest,
    _resolve_hco_help_cutoff,
)

SEED = 20260714
N = 60_000                        # drives per cell
ATTR_MU, ATTR_SD = 55, 15         # mock attribute row ~ N(mu, sd) clamped [20, 99]
_OUTCOMES = ("A", "B", "C", "D_FOUL", "O_FOUL", "DEAD BALL")


class _P:
    __slots__ = ("attributes",)
    def __init__(self, attrs):
        self.attributes = attrs


class _T:
    __slots__ = ("team_attributes", "strategy_calls")
    def __init__(self, team_attributes, aggression="normal"):
        self.team_attributes = team_attributes
        self.strategy_calls = {"aggression_call": aggression}


def _attrs(rng, mu=ATTR_MU, sd=ATTR_SD):
    keys = ("SC", "SH", "BH", "AG", "ST", "OD", "ID", "IQ", "CH")
    return {k: max(20, min(99, int(rng.gauss(mu, sd)))) for k in keys}


def _teams(off_eff, def_eff, aggression="normal"):
    off = _T({"offensive_efficiency": off_eff, "team_chemistry": 40, "fight": 10}, "normal")
    dfn = _T({"defensive_efficiency": def_eff, "team_chemistry": 40, "discipline": 10}, aggression)
    return off, dfn


def _drive_dist(rng, off_team, def_team, off_mu=ATTR_MU, def_mu=ATTR_MU, n=N):
    """Tally the tier/contact outcome over `n` random matchups (contact overrides tier as the label)."""
    c = Counter()
    for _ in range(n):
        driver = _P(_attrs(rng, off_mu))
        primary = _P(_attrs(rng, def_mu))
        tier, _frac, contact = _resolve_hco_drive_contest(driver, primary, off_team, def_team)
        c[contact or tier] += 1
    return c


def _fmt(c, n=N):
    return "  ".join(f"{k}:{100*c[k]/n:4.1f}%" for k in _OUTCOMES)


def sweep_neutral_band():
    print("=" * 96)
    print("1. DRIVE_NEUTRAL_BAND sweep — even matchup (off_eff=def_eff=3, attrs μ=55). Wider band → more B.")
    print("=" * 96)
    off_team, def_team = _teams(3, 3)
    _orig = adc.DRIVE_NEUTRAL_BAND
    print(f"{'BAND':>6} | " + "  ".join(f"{k:>10}" for k in _OUTCOMES))
    print("-" * 96)
    for band in (25.0, 50.0, 100.0, 150.0, 200.0):
        adc.DRIVE_NEUTRAL_BAND = band
        rng = random.Random(SEED)
        c = _drive_dist(rng, off_team, def_team)
        tag = "  ← shipped" if band == 100.0 else ""
        print(f"{band:>6.0f} | " + "  ".join(f"{100*c[k]/N:9.1f}%" for k in _OUTCOMES) + tag)
    adc.DRIVE_NEUTRAL_BAND = _orig


def sweep_matchup_lean():
    print("\n" + "=" * 96)
    print(f"2. Matchup lean @ shipped BAND={adc.DRIVE_NEUTRAL_BAND:.0f} — team eff + attr means shifted ±.")
    print("=" * 96)
    print(f"{'LEAN':>16} | " + "  ".join(f"{k:>10}" for k in _OUTCOMES))
    print("-" * 96)
    # (label, off_eff, def_eff, off_mu, def_mu)
    cells = [
        ("offense-favored", 6, 1, 62, 48),
        ("even",            3, 3, 55, 55),
        ("defense-favored", 1, 6, 48, 62),
    ]
    for label, oe, de, omu, dmu in cells:
        off_team, def_team = _teams(oe, de)
        rng = random.Random(SEED)
        c = _drive_dist(rng, off_team, def_team, omu, dmu)
        print(f"{label:>16} | " + "  ".join(f"{100*c[k]/N:9.1f}%" for k in _OUTCOMES))


# ---- S2c help-cutoff selectivity -------------------------------------------------------------------
# Fixed representative half-court layout (home orientation, grid ~100×50, rim ≈ (88, 25)). The BH blows
# by from the right wing to the rim; 4 help defenders sit at canonical help spots (the beaten primary is
# NOT a candidate). This is a MODEL layout — the absolute demotion rate is layout-dependent; read the
# SWEEP delta (how corridor / aggression change it), which is what the knobs control.
_DRIVE_START = {"x": 74, "y": 13}
_DRIVE_END = {"x": 88, "y": 25}
_HELP_LAYOUT = {           # def_pos → (x, y): perp-distance to the drive line varies by design
    "C":  {"x": 85, "y": 26},   # rim protector — squarely in the lane, cuts off often
    "PF": {"x": 80, "y": 22},   # nail help — near the path
    "SF": {"x": 74, "y": 33},   # weak-side wing — off the path (usually outside the corridor)
    "SG": {"x": 68, "y": 24},   # top/trail — behind, rarely wins the race
}


def sweep_help_cutoff():
    print("\n" + "=" * 96)
    print("3. S2c help-cutoff — % of blow-bys DEMOTED by a rotating help defender (fixed model layout).")
    print(f"   corridor × aggression; shipped corridor={adc.HCO_CUTOFF_PATH_CORRIDOR:.0f}. "
          "Demote = a help defender wins the race and the contest is not POS_O.")
    print("=" * 96)
    off_team, def_team = _teams(3, 3)
    def_lineup = {p: _P({"AG": 60, "OD": 55, "IQ": 55, "CH": 55, "BH": 40, "ST": 55, "ID": 55,
                         "SC": 50, "SH": 50}) for p in _HELP_LAYOUT}
    _orig_corr = adc.HCO_CUTOFF_PATH_CORRIDOR
    print(f"{'CORRIDOR':>9} | {'aggression':>11} | {'demoted':>8} | "
          + "  ".join(f"{k:>8}" for k in ("→B", "→C", "→D_FOUL", "→O_FOUL", "→DEAD")))
    print("-" * 96)
    for corridor in (7.0, 11.0, 14.0):
        adc.HCO_CUTOFF_PATH_CORRIDOR = corridor
        for agg in ("passive", "normal", "aggressive"):
            off_team, def_team = _teams(3, 3, agg)
            rng = random.Random(SEED)
            random.seed(SEED)  # _resolve_hco_help_cutoff draws from the global stream (race + contest)
            demoted = 0
            mix = Counter()
            for _ in range(N):
                driver = _P(_attrs(rng))
                cut_pos, tier, _frac, contact, _meet = _resolve_hco_help_cutoff(
                    _DRIVE_START, _DRIVE_END, driver, "BH_DEF",
                    _HELP_LAYOUT, def_lineup, off_team, def_team, agg)
                if cut_pos:
                    demoted += 1
                    mix[contact or tier] += 1
            tag = "  ← shipped" if corridor == 11.0 and agg == "normal" else ""
            print(f"{corridor:>9.0f} | {agg:>11} | {100*demoted/N:>7.1f}% | "
                  f"{100*mix['B']/N:>7.1f}% {100*mix['C']/N:>7.1f}% {100*mix['D_FOUL']/N:>7.1f}% "
                  f"{100*mix['O_FOUL']/N:>7.1f}% {100*mix['DEAD BALL']/N:>7.1f}%" + tag)
    adc.HCO_CUTOFF_PATH_CORRIDOR = _orig_corr


def run():
    print(f"S2 3-Tier Drive Monte-Carlo — seed={SEED}, N={N:,}/cell, attrs ~N({ATTR_MU},{ATTR_SD})")
    print("Reuses the REAL _resolve_hco_drive_contest / _resolve_hco_help_cutoff (mock players+teams).\n")
    sweep_neutral_band()
    sweep_matchup_lean()
    sweep_help_cutoff()
    print("\nReading the tables:")
    print("  1. BAND is the primary tier dial: the chem+eff default (~few pts) makes B vanish; ~100 gives")
    print("     B a real plurality at even matchups. ↑BAND squeezes A+C into B (more contested pull-ups,")
    print("     fewer clean blow-bys AND fewer clean stops); ↓BAND → near-binary A-vs-C.")
    print("  2. Team quality lives in the SCORES (off/def_eff × d6), so lean shifts A↔C as expected while")
    print("     B stays broad — the neutral tier is matchup-robust by design.")
    print("  3. Help-cutoff demotion scales with corridor (net width) and aggression (stop_attempt_prob:")
    print("     passive 0 → never rotates; aggressive 1 → every near help defender attempts). Absolute % is")
    print("     layout-dependent; the corridor/aggression DELTA is the tunable signal. Confirm vs in-app.")


if __name__ == "__main__":
    run()
