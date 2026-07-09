#!/usr/bin/env python3
"""Dynamic Defense (Dynamic_MM_Brief §5C) — TWO-GATE intercept prototype.

Reproducible (seeded) Monte-Carlo over the redesigned interception model, no DB / server:

  Gate 1 — GEOMETRY (dynamic, posture-INDEPENDENT):  when a pass is thrown, any defender within
           lane range of it (perpendicular distance ≤ LANE_RANGE, projection in the lane) has an
           interception OPPORTUNITY. Posture affects this only *indirectly*, by where it places
           the defenders (proof geometry) — tight/deny sits in his man's lane; loose/help sags to
           the middle and lands in OTHER players' lanes.
  Gate 2 — AGGRESSION:  an in-lane defender attempts the pick with P by `aggression_call`
           (aggressive 50% / normal 25% / passive 0%).
  Then   — ATTRIBUTE contest (placeholder success here; live = resolve_pass_contest). First pick
           ends the possession. A MISSED attempt = the gambled-at man is open (Goal 2 fuel).

The purpose is to see how posture (via placement) reshapes WHO gets interception chances and how
often — split into "on-man deny" (receiver's own defender jumping the entry) vs "help-lane"
(a sagging defender in someone else's lane). Reuses the placement geometry from
scripts/defense_posture_proof.py so the numbers match the visual proof.

Run:  MONGO_URI="" MONGO_DB_NAME="gob-test" python3 dynamic_defense_prototype.py
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))

from scripts.defense_posture_proof import OFFENSE, _coords, defender_positions
from BackEnd.engine.motion_read_map import is_inside_location

SEED = 20260709
N_TURNS = 20000
PASSES_PER_TURN = 4          # ball-movement passes in a typical HCO possession

# ── GATE KNOBS (tune here) ─────────────────────────────────────────────────
# Gate 1 — lane geometry. LANE_RANGE = perpendicular grid distance a defender can be from the
# pass line and still have a play (≈ HCO_PASS_LANE_DIST, 5–6 in the live system).
LANE_RANGE = 5.5
LANE_T_MIN = 0.10            # ignore defenders hugging the passer (t below this)
LANE_T_MAX = 1.00           # include the receiver's own man jumping the entry (t up to 1.0)
# Gate 2 — attempt probability by aggression_call.
INTERCEPT_ATTEMPT_PCT_BY_CALL = {"aggressive": 50, "normal": 25, "passive": 0}
# Placeholder for the live resolve_pass_contest attribute roll (share of attempts that complete).
# Set to a realistic ~6% — live this is resolve_pass_contest (attribute-gated); most passes complete.
INTERCEPT_SUCCESS_RATE = 0.06
# ───────────────────────────────────────────────────────────────────────────

OFF_POSITIONS = list(OFFENSE.keys())


def _lane_presence(defender_xy, passer_xy, receiver_xy):
    """(in_lane, t) — perpendicular distance test of a defender against the pass segment."""
    ax, ay = passer_xy
    bx, by = receiver_xy
    px, py = defender_xy
    abx, aby = bx - ax, by - ay
    denom = abx * abx + aby * aby
    if denom == 0:
        return (False, 0.0)
    t = ((px - ax) * abx + (py - ay) * aby) / denom
    perp = math.hypot((ax + t * abx) - px, (ay + t * aby) - py)
    return (LANE_T_MIN < t <= LANE_T_MAX and perp <= LANE_RANGE, t)


def _simulate(posture, call, rng):
    """One (posture, call) cell → dict of tallies over N_TURNS."""
    attempt_pct = INTERCEPT_ATTEMPT_PCT_BY_CALL[call]
    opp_defenders = 0        # in-lane opportunities (defender-passes)
    attempts = 0
    picks_turn = 0
    on_man_opps = 0          # opportunity where the in-lane defender guards the RECEIVER
    help_opps = 0            # opportunity where he guards someone else (help-lane)
    total_passes = 0

    for _ in range(N_TURNS):
        holder = "PG"
        picked = False
        for _p in range(PASSES_PER_TURN):
            receiver = rng.choice([p for p in OFF_POSITIONS if p != holder])
            defs = defender_positions(holder, posture)
            passer_xy = _coords(OFFENSE[holder])
            receiver_xy = _coords(OFFENSE[receiver])
            total_passes += 1
            for dpos, dxy in defs.items():
                if dpos == holder:
                    continue  # the passer's own defender is behind the ball
                in_lane, _t = _lane_presence(dxy, passer_xy, receiver_xy)
                if not in_lane:
                    continue
                opp_defenders += 1
                if dpos == receiver:
                    on_man_opps += 1
                else:
                    help_opps += 1
                # Gate 2
                if rng.randint(1, 100) <= attempt_pct:
                    attempts += 1
                    if not picked and rng.random() < INTERCEPT_SUCCESS_RATE:
                        picked = True
            holder = receiver
        if picked:
            picks_turn += 1

    return {
        "opp_per_pass": opp_defenders / total_passes,
        "on_man_share": (100.0 * on_man_opps / opp_defenders) if opp_defenders else 0.0,
        "help_share": (100.0 * help_opps / opp_defenders) if opp_defenders else 0.0,
        "attempts_per_turn": attempts / N_TURNS,
        "picks_pct_turn": 100.0 * picks_turn / N_TURNS,
    }


def run():
    rng = random.Random(SEED)
    inside = [p for p, s in OFFENSE.items() if is_inside_location(s)]
    print(f"Two-gate intercept prototype — seed={SEED}, {N_TURNS} turns/cell, "
          f"{PASSES_PER_TURN} passes/turn")
    print(f"offense: {OFFENSE}   (inside-man → locked normal: {inside})")
    print(f"LANE_RANGE={LANE_RANGE}  attempt%={INTERCEPT_ATTEMPT_PCT_BY_CALL}  "
          f"success(placeholder)={INTERCEPT_SUCCESS_RATE:.0%}\n")

    hdr = (f"{'posture':>8} {'call':>10} | {'opps/pass':>9} | "
           f"{'on-man%':>7} {'help%':>6} | {'attempts/turn':>13} | {'picks%/turn':>11}")
    print(hdr)
    print("-" * len(hdr))
    for posture in ("tight", "normal", "loose"):
        for call in ("aggressive", "normal", "passive"):
            r = _simulate(posture, call, rng)
            print(f"{posture:>8} {call:>10} | {r['opp_per_pass']:>9.2f} | "
                  f"{r['on_man_share']:>6.0f}% {r['help_share']:>5.0f}% | "
                  f"{r['attempts_per_turn']:>13.2f} | {r['picks_pct_turn']:>10.1f}%")
        print()

    print("Reading the table (Gate 1 geometry is identical across calls — only Gate 2 attempt% differs):")
    print("  • opps/pass = avg defenders in a pass lane (Gate 1). Driven by POSTURE placement only.")
    print("  • on-man% vs help%  = character of the opportunities: tight should skew ON-MAN (deny the")
    print("    entry to his guy); loose should skew HELP (sitting in other players' lanes). This is the")
    print("    'tight guards his man / loose plays other lanes' behavior you described.")
    print("  • attempts/turn & picks%/turn scale with aggression_call (passive=0 → no attempts).")
    print("  • picks% uses the placeholder success; live it's resolve_pass_contest (attribute-gated).")
    print("  • tune LANE_RANGE / INTERCEPT_ATTEMPT_PCT_BY_CALL / INTERCEPT_SUCCESS_RATE and re-run.")


if __name__ == "__main__":
    run()
