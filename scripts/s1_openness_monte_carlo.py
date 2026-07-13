#!/usr/bin/env python3
"""S1 Openness — Monte-Carlo tuner (Dynamic_MM_Brief §7, Stage 1).

Measures how the S1 "beaten defender opens space → graded shot contest" chain moves FG%, and how
sensitive that is to the tunable constants. Reuses the REAL S1 functions so a sweep truly exercises
the shipped logic (not a re-implementation):

  A  `_roll_defender_reads_graded`  (phase_resolution)  — the read roll → {follows, margin}
  B  `_defender_lag_fraction` + OPENNESS_LAG_*  (animator) — margin → how far the beaten defender lags
  C  `_proximity_contest_factor` + PROXIMITY_*  (shot_manager) — defender distance → defensive weight

The shot make math is replicated verbatim from `ShotManager.calculate_shot_score`
(offense = Σ attr·w/10 · d6 + dribble bonus; defense by shot type · d6 · proximity_factor; make =
shot_score ≥ threshold) — kept in sync by citation, not imported, so no game/DB is needed.

MODEL ASSUMPTIONS (documented, adjustable — the geometry the real animator draws, first-order):
  • A tracking defender sits BASE_CUSHION grid off his man (≈ today's normal contest, factor≈1.0).
  • On a positional step the guarded man moves with prob P_MAN_MOVES, travelling U[MOVE_LO, MOVE_HI].
  • A beaten defender closes only `frac` of that move → gap ≈ BASE_CUSHION + (1−frac)·move. Part C
    reads that gap. (Radial approximation; the sign of the move is folded into the magnitude.)
The absolute FG% is calibrated (threshold auto-solved to BASELINE_FG), so read the S1 *delta* and the
factor/gap distributions — those are robust to the calibration; the absolute number is not.

Run:  MONGO_URI="" MONGO_DB_NAME="gob-test" python3 scripts/s1_openness_monte_carlo.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from BackEnd.engine.phase_resolution import _roll_defender_reads_graded
import BackEnd.models.animator as animator
import BackEnd.models.shot_manager as shot_manager
from BackEnd.models.animator import _defender_lag_fraction
from BackEnd.models.shot_manager import _proximity_contest_factor

SEED = 20260713
N = 40_000                       # possessions per cell
BASELINE_FG = 0.47               # threshold auto-solved so flag-off FG% hits this
DEF_EFF = 2                      # team defensive_efficiency added to the read roll
# Geometry model (see header)
BASE_CUSHION = 2.5
P_MAN_MOVES = 0.55
MOVE_LO, MOVE_HI = 3.0, 8.0
# Shot-type mix (representative HCO) → (label, is_three, is_paint, offense weights, defense fn key)
SHOT_MIX = [("three", 0.45), ("mid", 0.35), ("inside", 0.20)]

_OFF_WEIGHTS = {  # from PLAYCALL_ATTRIBUTE_WEIGHTS (Outside/Attack-mid/Inside)
    "three":  {"SH": 8, "IQ": 1, "CH": 1},
    "mid":    {"SC": 5, "AG": 2, "ST": 1, "IQ": 1, "CH": 1},
    "inside": {"SC": 6, "ST": 2, "IQ": 1, "CH": 1},
}


class _P:
    __slots__ = ("attributes",)
    def __init__(self, attrs):
        self.attributes = attrs


def _rand_attrs(rng, mu=55, sd=15):
    """A player's attribute row — each stat ~ N(mu, sd) clamped [20, 99]."""
    keys = ("SC", "SH", "BH", "AG", "ST", "OD", "ID", "IQ", "CH")
    return {k: max(20, min(99, int(rng.gauss(mu, sd)))) for k in keys}


def _offense_score(attrs, wkey, rng):
    """Replicates calculate_shot_score offense: Σ attr·(w/10)·d6  +  dribble bonus."""
    w = _OFF_WEIGHTS[wkey]
    base = sum(attrs[a] * (wt / 10) for a, wt in w.items()) * rng.randint(1, 6)
    dribble = (attrs["AG"] * 0.8 + attrs["IQ"] * 0.2) * rng.randint(1, 6) * 0.2
    return base + dribble


def _defense_score_raw(attrs, wkey, rng):
    """Replicates calculate_shot_score defense (pre-proximity), by shot type."""
    if wkey == "inside":   # is_paint
        s = attrs["ID"] * 0.6 + attrs["ST"] * 0.2 + attrs["IQ"] * 0.1 + attrs["CH"] * 0.1
    elif wkey == "three":  # is_three
        s = attrs["OD"] * 0.8 + attrs["IQ"] * 0.1 + attrs["CH"] * 0.1
    else:                  # mid
        s = (attrs["OD"] * 0.3 + attrs["ID"] * 0.3 + attrs["AG"] * 0.1
             + attrs["ST"] * 0.1 + attrs["IQ"] * 0.1 + attrs["CH"] * 0.1)
    return s * rng.randint(1, 6)


def _pick_shot(rng):
    r = rng.random()
    c = 0.0
    for label, p in SHOT_MIX:
        c += p
        if r <= c:
            return label
    return SHOT_MIX[-1][0]


def _simulate(rng):
    """One cell: returns per-possession records (offense/defense scores, proximity factor, beaten)."""
    recs = []
    for _ in range(N):
        wkey = _pick_shot(rng)
        shooter = _P(_rand_attrs(rng))
        defender = _P(_rand_attrs(rng))
        off = _offense_score(shooter.attributes, wkey, rng)
        dfn = _defense_score_raw(defender.attributes, wkey, rng)

        # A: real read roll (single defender 'D').
        reads = _roll_defender_reads_graded({"D": defender}, DEF_EFF, rng)
        moved = rng.random() < P_MAN_MOVES
        move = rng.uniform(MOVE_LO, MOVE_HI) if moved else 0.0
        # B: real lag fraction.
        frac = _defender_lag_fraction({"_defender_reads": reads}, "D", "O", moved)
        beaten = frac < 1.0
        gap = BASE_CUSHION + (1.0 - frac) * move
        # C: real proximity factor (defender beyond radius → no contest, factor 0).
        from BackEnd.constants import CONTEST_EUCLIDEAN_RADIUS
        pf = 0.0 if gap > CONTEST_EUCLIDEAN_RADIUS else _proximity_contest_factor(gap)
        recs.append((off, dfn, pf, beaten, gap, wkey))
    return recs


def _solve_threshold(recs, target):
    """Binary-search the make threshold so BASELINE (proximity=1.0) FG% == target."""
    lo, hi = -200.0, 400.0
    for _ in range(40):
        mid = (lo + hi) / 2
        fg = sum(1 for off, dfn, *_ in recs if (off - dfn * 1.0) >= mid) / len(recs)
        if fg > target:
            lo = mid  # too many makes → raise bar
        else:
            hi = mid
    return (lo + hi) / 2


def _fg(recs, thr, s1):
    """FG% under baseline (s1=False, proximity=1.0) or S1 (s1=True, graded proximity)."""
    made = tot = 0
    for off, dfn, pf, *_ in recs:
        pfx = pf if s1 else 1.0
        made += 1 if (off - dfn * pfx) >= thr else 0
        tot += 1
    return 100.0 * made / tot


def _fg_by_type(recs, thr, s1):
    out = {}
    for label, _ in SHOT_MIX:
        sub = [r for r in recs if r[5] == label]
        out[label] = _fg(sub, thr, s1) if sub else 0.0
    return out


def run():
    print(f"S1 Openness Monte-Carlo — seed={SEED}, N={N:,}/cell, baseline FG target={BASELINE_FG:.0%}")
    print(f"model: cushion={BASE_CUSHION} p_move={P_MAN_MOVES} move~U[{MOVE_LO},{MOVE_HI}] "
          f"def_eff={DEF_EFF} mix={{{', '.join(f'{l}:{p:.0%}' for l,p in SHOT_MIX)}}}")
    print("Sweeping OPENNESS_LAG_MAX (Part B, how far a beaten defender lags). "
          "PROXIMITY floor/near/open at shipped defaults.\n")

    hdr = (f"{'LAG_MAX':>8} | {'beat%':>6} {'pf|beat':>8} {'gap|beat':>8} | "
           f"{'FG base':>8} {'FG S1':>7} {'Δ':>6} | {'3PT Δ':>6} {'mid Δ':>6} {'in Δ':>6}")
    print(hdr)
    print("-" * len(hdr))

    for lag_max in (0.50, 0.65, 0.80, 0.95):
        animator.OPENNESS_LAG_MAX = lag_max            # override the REAL constant
        rng = random.Random(SEED)                      # same stream every cell → paired comparison
        recs = _simulate(rng)
        thr = _solve_threshold(recs, BASELINE_FG)
        beaten = [r for r in recs if r[3]]
        beat_pct = 100.0 * len(beaten) / len(recs)
        pf_beat = (sum(r[2] for r in beaten) / len(beaten)) if beaten else 1.0
        gap_beat = (sum(r[4] for r in beaten) / len(beaten)) if beaten else BASE_CUSHION
        fg_b, fg_s1 = _fg(recs, thr, False), _fg(recs, thr, True)
        t_b, t_s1 = _fg_by_type(recs, thr, False), _fg_by_type(recs, thr, True)
        print(f"{lag_max:>8.2f} | {beat_pct:>5.0f}% {pf_beat:>8.2f} {gap_beat:>8.1f} | "
              f"{fg_b:>7.1f}% {fg_s1:>6.1f}% {fg_s1-fg_b:>+5.1f} | "
              f"{t_s1['three']-t_b['three']:>+5.1f} {t_s1['mid']-t_b['mid']:>+5.1f} "
              f"{t_s1['inside']-t_b['inside']:>+5.1f}")

    # Secondary sweep — the Part C proximity ramp (open-distance) at fixed LAG_MAX, so both dials show.
    animator.OPENNESS_LAG_MAX = 0.80
    print(f"\nPROXIMITY ramp sweep (Part C, OPEN_DIST = grid at which the shot is ~open) @ LAG_MAX=0.80, "
          f"NEAR={shot_manager.PROXIMITY_CONTEST_NEAR_DIST} FLOOR={shot_manager.PROXIMITY_CONTEST_OPEN_FLOOR}")
    h2 = f"{'OPEN_DIST':>9} | {'pf|beat':>8} | {'FG base':>8} {'FG S1':>7} {'Δ':>6}"
    print(h2)
    print("-" * len(h2))
    _open_default = shot_manager.PROXIMITY_CONTEST_OPEN_DIST
    for open_d in (7.0, 9.0, 11.0):
        shot_manager.PROXIMITY_CONTEST_OPEN_DIST = open_d
        rng = random.Random(SEED)
        recs = _simulate(rng)
        thr = _solve_threshold(recs, BASELINE_FG)
        beaten = [r for r in recs if r[3]]
        pf_beat = (sum(r[2] for r in beaten) / len(beaten)) if beaten else 1.0
        fg_b, fg_s1 = _fg(recs, thr, False), _fg(recs, thr, True)
        print(f"{open_d:>9.1f} | {pf_beat:>8.2f} | {fg_b:>7.1f}% {fg_s1:>6.1f}% {fg_s1-fg_b:>+5.1f}")
    shot_manager.PROXIMITY_CONTEST_OPEN_DIST = _open_default

    print("\nReading the tables:")
    print("  • beat% = share of possessions the defender is beaten (man moved + failed read). Driven")
    print("    by defender IQ/CH + DEF_EFF vs the 110 bar + P_MAN_MOVES — NOT by LAG_MAX (~flat).")
    print("  • pf|beat / gap|beat = mean proximity factor & defender gap ON beaten possessions. Higher")
    print("    LAG_MAX (or lower OPEN_DIST) → lower factor → the beaten man's shot is more open.")
    print("  • FG Δ = the whole S1 effect on FG% (only beaten possessions shift). It is BOTTLENECKED")
    print("    by beat% (~14%) far more than by LAG_MAX: to move FG more, more defenders must get beaten")
    print("    (read bar / P_MAN_MOVES), not just lag harder. Confirm beat-frequency + baseline in-app.")
    print("  • Absolute FG is calibrated to the target; trust the Δ and the pf/gap columns, not the level.")


if __name__ == "__main__":
    run()
