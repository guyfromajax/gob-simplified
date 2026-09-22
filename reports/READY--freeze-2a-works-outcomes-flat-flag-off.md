# Stage 2a: the freeze works. Outcomes don't move detectably. Flag still OFF.

IT WORKED. Flag on, a stored defender row never changes once written: 0 overwrites vs 11,181 flag-off
(8 games). Same-step same-offense rows identical 99.67% (was 61.62%), p90 0.00 (was 3.00).
Freeze-miss 2.25/game at SD=1, 0.33 at SD=0 -- acceptance test passes; 89% of the residual is the
shot-contest selection hitting a step whose stamp produced an EMPTY row (pre-existing, surfaced).

OUTCOMES: nothing resolvable at n=40. Interceptions +0.40 +/- 0.73/game, pts -0.78 +/- 3.19, FG%
-0.83 +/- 2.20. Population at risk is ~0.6 interceptions/game, below n=40's power. Nothing large or
unexpected happened.

:7683 PRE-SEED -- JAMIE'S AND MY LEAN (DELETE) WAS WRONG; THE PRE-REGISTERED RULE KEPT IT. Only 78-84%
of those beats are ever reached by a stamp, AND the pre-seed is read back on the very next line
(:7687) inside the same block, so no stamp could cover it anyway. Design refined to: one draw per
step, written once by whoever creates the step, never redrawn. announce_blocked_write names every
first writer.

SEAM B (DRIVE) IS NOT CLOSED BY STAGE 2 -- the scope report was wrong. attack_drive_clearance computes
defender_end_coords for beats it is in the middle of creating and consumes them in the same function;
there is no frozen row yet. Needs its own design.

MY DIVERGENCE METRIC WAS MIS-SPECIFIED. "SHOT-vs-STAMP p90 -> 0" compares two different moments and
could never reach 0 under a perfect freeze. That pair should be redefined before being used as a gate.

CPU: +11% sim wall (4.96 -> 5.50 s/game), n=8, noise floor ~3%. Thin but above noise. Sim is ~20s of a
~115s week (persistence dominates), so ~+2s/week -- not alarming, but Stage 3 is where the saving is.

Gates: flag off 40/40 fp AND draws all four cells; §8.1 = 0 both; suite 2850/0/0 both flag states;
0 errors across 320 games. Not flipped, not re-cut, not merged.
