# READY — sim HCO coord staleness fixed, 0.00 vs placement, played untouched

`4f856721a` on `feature/animation-reward`. Report: `reports/sim-hco-coord-staleness-2026-09-17.md`.

## Verdict: land it.

- **S1 came back clean.** `compute_defender_grid` runs on **every** HCO turn on both arms
  (sim 2,018/2,018, played 1,862/1,862, poison-verified). This was the good branch — a fix,
  not a design question.
- **The fix is a read, not a new build.** It takes the placement stamp already on the skeleton
  and writes all ten players at the two points played writes them. No third draw, no extra
  placement build. Cost ~20 ms/game (0.4%); wall-clock Δ unresolved.
- **Played is byte-identical 40/40 on both footings.** Nothing crossed the arm boundary.
- **Sim rebounder now agrees with played ~94% of the time** (was: picks change on 50% of turns).
  OREB share 30.3% → **24.7%**, played **24.8%**. DREB 69.7% → 75.3%, played 75.2%.
  It landed on played's number, not near it.

## Three things needing your call

1. **Sim reference needs re-cutting at `4f856721a`.** Sim draws moved (+1,667 ±828, resolved,
   on the D=0 footing). Played's reference stands. Nothing should be measured against
   `d9a4f1517` on the sim arm from here.
2. **Simmed league stats will shift.** Per team-game: ~1.5 fewer OREB, ~3.4 fewer
   second-chance points, more possessions. Correct direction, but any balance read you took
   off sim box scores this week is now stale.
3. **Two residuals left open, both known:**
   - **Final Turn shot (`phase_resolution.py:8183`)** still updates only the shooter on sim.
     Buzzer putbacks are exactly where rebound position matters. Small, same pattern — worth
     closing in the same pass.
   - **Stopper path carries a 4.13-unit defensive residual** vs played (the write uses the stop
     step; played renders the appended stopper step). ~15% of writes.
   - Over-the-back in-play rolls 15.1 → 25.9, played 39.0. The rest is crash destinations,
     which is the next item anyway.

Ping me and I'll write the next brief.
