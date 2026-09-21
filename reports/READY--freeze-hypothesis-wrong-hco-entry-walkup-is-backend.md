# My freeze hypothesis was WRONG. But the symptom is real, it IS on HCO entry, and it is BACKEND.

WHERE I WAS WRONG. I read the deferral at turnAnimation.js 4833/4859/5046 and missed line 4801 --
animateStep is called unconditionally for EVERY player BEFORE the branch. Defenders' tween starts
immediately, on time, every step. The deferral defers a DUPLICATE tween, not the motion. Worst case
~50ms on 16.4% of defender-instances.

AND THE FILE BARELY RUNS. turnAnimation.js draws 0.69% of turns (119 of 17,143). 82.3% go through
the schema renderer animationPlayback.js, which has NO deferral -- one loop starts offense and
defence alike. NO HCO turn is in the legacy 119 (they are BASELINE_INBOUND 60, OPENING_TIP 40,
DREB 14, OREB 5). The code I pointed at cannot draw what Jamie is seeing.

WHAT IS ACTUALLY HAPPENING. On the schema path: 12.8% of offense-moving steps (8,680 of 67,562) draw
a COMPLETELY STATIC DEFENCE. Cause, on all 8,680, per the repo's own shipped detector
deadAirLedger.js:171 detectDefenseFrozen:
  destination == start (emitter authored a no-op)  6,071  69.9%
  no destination authored                          2,609  30.1%
  destination differs from start -> FRONTEND           0   0.0%
Zero frontend. The emitter is not authoring defender movement.

THE STANDOUT IS hco_entry_walkup: 4,070 steps, 22.6% draw a motionless defence, and the beat is LONG
-- 548ms p50, 1249ms p90, 1716ms max. On HCO entry, and long enough to see. The three
hco_entry_handoff_* reasons are clean (0.0 / 0.0 / 0.8%).

CONFIRM IT IN TWO MINUTES, NO NEW CODE. The detector already ships and is ON BY DEFAULT. Load a game,
set window.UESS_TRACE_PLAYBACK = true, filter console on [DEF-FROZEN]. It should fire on ~12.8% of
offense-moving steps and EVERY one should say BACKEND. If any says FRONTEND, the above is wrong and
the frontend is back in scope.

SMALL REAL DEFECT FOUND ALONG THE WAY: on the legacy path the duplicate tween re-fires onAction via
the distance<1 early return, so onAction runs twice per defender per pass step. 0.69% of turns. Not
traced into its handlers.

Part 2 not run -- no browser in that environment. No instrumentation added, so nothing to revert;
git diff is 0 lines at a4c691c9c apart from the report.
