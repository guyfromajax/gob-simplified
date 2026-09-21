# Non-HCO phase error: ALSO an artefact. But the frontend has the real thing.

THE NON-HCO "PHASE ERROR" WAS POOLING. Inbounds carry 68.6% of all beyond-10 steps, and on them
the ball handler is literally out of bounds (100% of SIDE_INBOUND steps 1-2, 100% of
BASELINE_INBOUND step 2) and stationary for a step (100% / 95% frozen). When the handler does not
move, d(bh N-1) and d(bh N) are the same number by construction -- BASELINE_INBOUND step 3 reads
25.96 vs 25.96, SIDE_INBOUND step 2 reads 22.58 vs 22.58, across thousands of steps. The
comparison was degenerate. The agent withdrew its own §2 claim from defender-phase-2026-09-20.md,
correctly.

Fast breaks are the opposite of lagging: defenders fail to follow only 6-18% of a 20-42 unit
sprint. DREB is 0.0% beyond 10. Nothing survived to a code path.

SO: three measurement passes, and the backend animation data is correct every time. What Jamie
sees on screen is NOT in the step coordinates.

THE FRONTEND IS WHERE IT IS. turnAnimation.js, on any step that contains a pass:
  4833  defensive tweens are DEFERRED into defensiveStarters, not started
  4859  await passerPromise   <- waits for the PASSER to finish travelling to his spot
  5046  defensiveStarters fired
  5049  pass animation starts
Defenders do not move at all while the passer travels. They hold, then all start at once when the
ball is released. On steps with NO pass (line 4851) they start immediately alongside the offense.
So the behaviour differs between pass steps and non-pass steps.

That matches Jamie's words exactly -- "the defenders have moved to the next step before (or
after?) the ball has been passed." The answer is AFTER, and they were frozen before it.

Why HCO entry steps are worst: they are pass-heavy. 48.5% hco_entry_handoff_hold, 35%
hco_entry_handoff_converge, and step 2 is hco_entry_handoff_pass.

The deferral is DELIBERATE -- the comment says "so we can sync them with the pass." The open
question is magnitude: how long is the passer's tween, i.e. how long are the defenders statues?
200ms is invisible; 1500ms is glaring. That is the measurement to take, and it is in the browser,
not the sim.

CAUTION: this is read from control flow, not observed in playback. Two confident code readings
have already been wrong today. Confirm by instrumentation before building anything.
