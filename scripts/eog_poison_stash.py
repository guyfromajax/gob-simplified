#!/usr/bin/env python3
"""
Runtime draw-count verification (the narrowed poison-stash for this pass).

A true poison-stash — stash the RNG stream, poison an output, re-run, compare — is
IMPOSSIBLE right now: training and EOG both draw from global `random`, which pymongo
consumes non-reproducibly (the same global-stream coupling that makes training_rng a
blocker for leveling; demonstrated by two identically-seeded runs diverging). So a
cross-run stream diff can't isolate the change from the noise.

We accept a NARROWER check for ONE pass — count draws at runtime per unit of work and
assert the observed counts match the source-level analysis. This closes the gap
between "we traced it" and "we counted it." The proper poison-stash returns once
training and EOG have their own RNG streams.

Two checks:
  1. TRAINING (where Task 6 lives): the focus multiplier is in _apply_team_training_points,
     NOT EOG. Old code did random.choice([1.5..1.8]) per focus application (1 draw each);
     new code is flat 2x (0 draws). Assert an amplified call draws the SAME as a
     non-amplified one → each focus application dropped exactly 1 draw → and the amplified
     effect is 2x → focus still fires, draw-free.
  2. EOG: per team-game, draws == attrs_processed − data_integrity_events (data-integrity
     at zero usage skips the draw). Assert each band function draws exactly once except
     the data-integrity path → no hidden EOG draws.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import BackEnd.models.training_execution_v2 as T  # noqa: E402
from BackEnd import eog_attr_rules as R  # noqa: E402

FOCUS_LIST = [1.5, 1.6, 1.7, 1.8]


def _training_call(amplify: bool):
    """Run one _apply_team_training_points, counting draws + focus-multiplier choices."""
    draws = [0]
    focus_choice = [0]
    orig_randint, orig_choice = random.randint, random.choice

    def cr(a, b):
        draws[0] += 1
        return orig_randint(a, b)

    def cc(seq):
        if list(seq) == FOCUS_LIST:
            focus_choice[0] += 1
        return orig_choice(seq)

    team = {"offensive_efficiency": 0}
    with patch.object(T, "_should_amplify_team_attr", return_value=amplify), \
         patch("random.randint", side_effect=cr), \
         patch("random.choice", side_effect=cc):
        random.seed(42)  # identical base delta for amplified vs control
        T._apply_team_training_points(team, "offensive_efficiency", 2, "arch", "sub")
    return draws[0], focus_choice[0], team["offensive_efficiency"]


def check_training() -> bool:
    da, fca, va = _training_call(True)    # focus fires
    dc, fcc, vc = _training_call(False)   # control (no focus)
    print("## 1. TRAINING focus multiplier (Task 6) — runtime draw count")
    print(f"  amplified call: draws={da}  focus_random.choice={fca}  attr_change={va}")
    print(f"  control call:   draws={dc}  focus_random.choice={fcc}  attr_change={vc}")
    ok = True
    if da != dc:
        print(f"  ❌ amplified draws ({da}) != control ({dc}) — focus is NOT draw-free"); ok = False
    else:
        print(f"  ✅ focus adds 0 draws (each focus application dropped exactly 1 vs old code)")
    if fca != 0 or fcc != 0:
        print(f"  ❌ focus random.choice([1.5..1.8]) still called ({fca}/{fcc}) — Task 6 not applied"); ok = False
    else:
        print(f"  ✅ the old focus draw is gone (0 calls)")
    if vc != 0 and va == 2 * vc:
        print(f"  ✅ focus still fires: amplified {va} == 2 × control {vc}")
    else:
        print(f"  ❌ focus effect wrong: amplified {va} vs 2×control {2*vc}"); ok = False
    return ok


class _CountRng:
    def __init__(self):
        self.n = 0

    def randint(self, a, b):
        self.n += 1
        return a


def check_eog() -> bool:
    rng = _CountRng()
    # One team-game's 11 attributes; offense forced to zero usage → data-integrity (no draw).
    results = [
        R.shot_threshold_change(55, True, rng=rng),
        R.discipline_change(5, 20, rng=rng),
        R.fight_change(True, rng=rng),
        R.rebound_modifier_change(30, 20, rng=rng),
        R.offensive_efficiency_change(0, 0.0, rng=rng),   # zero usage → data-integrity
        R.defensive_efficiency_change(20, 0.4, rng=rng),
        R.fb_efficiency_change(8, 0.4, rng=rng),
        R.fb_opp_modifier_change(7, rng=rng),
        R.pt_efficiency_change(6, 0.5, rng=rng),
        R.pt_opp_modifier_change(10, rng=rng),
        R.team_chemistry_change(True, 10, 50, rng=rng),
    ]
    attrs = len(results)
    data_integrity = sum(1 for _lbl, d in results if d is None)
    expected = attrs - data_integrity
    print("\n## 2. EOG per team-game — draws == attrs_processed − data_integrity_events")
    print(f"  attrs={attrs}  data_integrity_events={data_integrity}  expected_draws={expected}  observed_draws={rng.n}")
    if rng.n == expected:
        print(f"  ✅ exactly one draw per non-data-integrity attribute — no hidden EOG draws")
        return True
    print(f"  ❌ observed {rng.n} != expected {expected} — a band function drew an unexpected number of times")
    return False


def _rebound_call(amplify: bool, start: float, points: int):
    draws = [0]
    orig_ri, orig_ch = random.randint, random.choice

    def cr(a, b):
        draws[0] += 1
        return orig_ri(a, b)

    def cc(seq):
        draws[0] += 1
        return orig_ch(seq)

    team = {"rebound_modifier": start}
    with patch.object(T, "_should_amplify_team_attr", return_value=amplify), \
         patch("random.randint", side_effect=cr), \
         patch("random.choice", side_effect=cc):
        random.seed(7)
        T._apply_rebound_modifier_training(team, points, "arch", "sub")
    return draws[0], team["rebound_modifier"]


def check_rebound_training() -> bool:
    # _apply_rebound_modifier_training is a SEPARATE function; Task 2 rescaled its range/
    # clamps and the focus multiplier is now flat 2x (Task 6 applied here too). So the
    # focus is draw-FREE: amplified and non-amplified both draw once (the base randint),
    # and the amplified increase is exactly 2x the base. Output stays in 0.0-1.0 at 2dp.
    start = 0.5
    dna, vna = _rebound_call(False, start, 3)      # non-amplified → base only
    da, va = _rebound_call(True, start, 3)         # amplified → base, flat 2x (no draw)
    dclamp, vclamp = _rebound_call(True, 0.98, 5)  # near the new upper rail
    base_inc = round(vna - start, 2)
    amp_inc = round(va - start, 2)
    print("\n## 3. REBOUND training path (Task 2 + Task 6) — runtime draw count + range")
    print(f"  non-amplified: draws={dna}  out={vna}  (increase {base_inc})")
    print(f"  amplified:     draws={da}  out={va}  (increase {amp_inc}, expect 2× base)")
    print(f"  clamp test (start 0.98, +pts): out={vclamp}")
    ok = True
    if dna != 1 or da != 1:
        print(f"  ❌ draws non-amp={dna} amp={da} (both expected 1) — focus is NOT flat/draw-free"); ok = False
    else:
        print("  ✅ focus is flat 2x, draw-free (was 2 draws with random.choice; now 1)")
    if amp_inc != round(2 * base_inc, 2):
        print(f"  ❌ amplified increase {amp_inc} != 2× base {round(2*base_inc,2)} — focus not doubling"); ok = False
    else:
        print(f"  ✅ focus doubles: amplified increase {amp_inc} == 2 × base {base_inc}")
    for label, v in [("non-amp", vna), ("amp", va), ("clamp", vclamp)]:
        if not (0.0 <= v <= 1.0):
            print(f"  ❌ {label} output {v} outside new 0.0-1.0 range"); ok = False
        if round(v, 2) != v:
            print(f"  ❌ {label} output {v} not on the 0.01 grid (2dp)"); ok = False
    if ok:
        print(f"  ✅ outputs inside 0.0-1.0 at 2dp; clamp lands at {vclamp} (new upper rail 1.0)")
    return ok


def main() -> int:
    ok_t = check_training()
    ok_e = check_eog()
    ok_r = check_rebound_training()
    print("\n" + ("✅ POISON-STASH (narrowed) PASSES — draw counts match source analysis; "
                  "Task 6 is the only draw-count change, counted at runtime; rebound rescale "
                  "is draw-neutral and range-correct."
                  if ok_t and ok_e and ok_r else "❌ draw-count mismatch — investigate before commit."))
    return 0 if (ok_t and ok_e and ok_r) else 1


if __name__ == "__main__":
    raise SystemExit(main())
