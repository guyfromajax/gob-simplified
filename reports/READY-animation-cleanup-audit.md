# READY — animation-cleanup-audit.md (verified)

Verified 2026-09-25. **Accepted.** Branch `feature/animation-cleanup-audit` off develop
(`e4ff0d78e` — develop had moved from 8d6d8252d; the agent noticed and said so).

## Read-only held — verified, not assumed
Committed diff is 1 commit touching ONLY: the report, `scratch_guard_ball_census.py`,
`tests/e2e/scratch-onaction-probe.spec.js`, and two reused `tests/e2e/helpers/` harness files.
**Zero production files.** Five FrontEnd files showed fresh mtimes mid-run; I md5'd all five
against develop and every one was byte-identical — branch-checkout artifacts, not edits.
The agent applied the palette-null workaround to the SERVED FILE TEXT inside its probe rather
than to a repo file, which is the right call and it declared it.

## ITEM 10 — VERDICT: STALE AS DESCRIBED, and the reason is the headline
The double call is REAL in source and my hypothesis was confirmed: `turnAnimation.js:4810`
creates `promise` once; offence pushes it (`:4823`), defence pushes
`defensiveStarters.push(() => animateStep({...identical args...}))` (`:4841`), and both the
no-pass (`:4859`) and pass (`:5054`) branches invoke those closures — so every defender gets
`animateStep` called twice on every step, with the first promise discarded.
`animateStep.js:262` fires `onAction` synchronously on the zero-distance path, which a
stationary defender hits every time.

**But the code does not run.** Live-browser instrumentation across four runs, the longest
covering 8:00 → 3:56 of game clock with the score advancing 0 → 6:

| counter | observed |
|---|---|
| `animateStep` calls | **0** |
| `onAction` fires (all three sites) | **0** |
| `playTurnAnimation` calls | **0** |
| `AnimationEngine.determineHandler` | 1 (`handleOpeningTip`) |
| UESS `animationPlayback.playTurn` | **38 turns** |
| UESS `animationPlayback.playAnimationStep` | **274 steps** |

The live product animates through `animationPlayback.js`. `turnAnimation.js` (~5,000 lines) and
`animateStep.js` are still imported and fetched but never called. The agent re-instrumented after
realising a zero inside `if (currentAction && onAction)` could not distinguish "never ran" from
"ran with onAction undefined" — moving the counter to `animateStep` ENTRY is what made the zero
trustworthy. That is the difference between a measured zero and a probe failure, and it caught it
itself.

**This retroactively explains this morning's depth-ordering bug more completely than I did.** I
diagnosed `installDepthOrdering` as living in "one of ~16 handlers". It was worse: it lived in a
function that never executes at all. The scene-setup fix was right for a stronger reason than the
one I gave.

**What Jamie is seeing is NOT this bug.** Traced to the terminal consumer `animation/onAction.js`:
`receive` = 10px bounce, `screen` = ±5° shake, `steal` = alpha flash; `handle_ball`/`pass`/`shoot`
are explicitly sunset no-ops; everything else hits `default:` and does nothing. Defender actions
are `guard_ball`/`guard_offball` → `default:` → no effect. The double-call path is defenders only,
so the duplicate is an invisible no-op fired twice. The ONLY viewer-visible symptom this bug could
ever produce is a **doubled steal-flash**. A doubled bounce on a catch or shake on a screen is a
different bug.

Fix would be frontend-only, under ten lines (reuse `promise` instead of re-calling), and delivers
nothing visible. The real question it raises is whether to retire the legacy modules outright.

## ITEM 9 — VERDICT: ALREADY FIXED, but inert
`guard_ball` tagged **8,092 times across 12 games**, 9.4% of defender-steps (17,275 HCO steps,
78,283 `guard_offball`). Fixed by the position-lookup-2 work — the old code used
`getattr(defender, "position", None)`, an attribute `Player` does not have, so it returned None on
every call. Now `lineup_slot(def_lineup, defender)`. Gate at `skeleton_step_emitter.py:731`:
54.6% of calls have no defender in `roles` (matches the docstring), 45.4% resolve, and
**0.0% fail to resolve when a defender is present** — the lookup never fails.

**No consumer on the live path.** Both frontend consumers (`animateStep.js:81` and `:523-598`) are
in the dead legacy path. Grepping the live UESS chain (`animationPlayback.js`,
`pathKnotPlayback.js`, `flourishes.js`, `arrivalHeartbeat.js`) for `guard_ball` returns 0 hits.
The data is correct and in the payload; anything that wants to draw an on-ball defender
differently is new frontend work, not a repair.

## LANDMINE WORTH RECORDING
The guard_ball fix is conditional on `GOB_LINEUP_POSITION_LOOKUP` (default "1"). Measured with it
OFF: `guard_ball` drops to **0** and unresolved jumps to 202 — item 9 returns exactly. That flag is
**#19 on the retirement candidate list in reports/flag-registry.md** (highest guard count, 11).
Retiring it by deleting the wrong branch reintroduces this bug. Anyone doing that retirement needs
to know.

## THE FINDING THAT REACHES BACK ACROSS THE WHOLE WORKSTREAM — verified myself
`turns_fingerprint(turns, score)` at `scratch_equiv3_fbdedupe.py:396-399` hashes
`[(result_type, next_turn) for each turn]` plus the score. **It does not cover coordinates, the
actions map, or any part of the animation payload.** I read the function; the claim is correct.

So a change that moves every player on the floor but alters no shot outcome, foul or rebound
passes 240/240 cleanly — and `draws` would not move either, since geometry consumes no RNG.
**equiv-v3 is a RESULTS gate, not an ANIMATION gate.**

This does not invalidate the session's gating: the collision and AG-spread work measured outcomes
separately at n=120 seed-paired, and the flag-off 240/240 gates were valid because flag-off means
the code path is not taken. No report in this workstream claimed flag-on 240/240 proved safety.
But the limitation is real and it matters most for exactly this workstream — a harness that cannot
see animation, used to gate animation changes. Record it before anyone treats a green 240/240 as
proof an actions-map or coordinate change was safe.

## Honest limitations the agent volunteered
- The 0.69% figure was neither reproduced nor refuted — the path it describes did not execute, so
  there was nothing to count. It may well have been correct when `turnAnimation.js` was live.
- Only `OPENING_TIP` identified from the payload it hooked; it states 38 UESS turns / 274 steps
  rather than inventing a turn-type distribution, and explicitly notes that
  `animateGameTurns.js:1037`/`:1076` DO call `playTurnAnimation` directly for FCP/HCT setup turns,
  none of which occurred in its runs. So "dead" means "not observed in ~4 minutes of game clock",
  not "provably unreachable".
- All observed steps were HCO; FCP/HCT emitters not instrumented.
- Scale stated as 1 live game per run, 4 runs — not dressed up as a rate.

## Strategic implication for the 2D physics brief
The live animation path is `animationPlayback.js`, not `turnAnimation.js`. Any physics/pathing
work builds there. And ~5,000 lines of legacy animation code that no longer runs is its own
cleanup candidate — with the caveat above that "not observed" is not "unreachable", so retiring it
needs a reachability pass first.

## Still open
- `feature/flag-registry` merge, parked under Operations.
- The palette-null fragility fix, still only on `feature/depth-ordering-fix`, unmerged.
- Items 5, 6, 8 deferred into the 2D physics brief (8 especially).
- 7 parked: `int(round(...))` grid quantisation, not missing jitter, is why deny looks robotic.
- 11, 12 on the Operations track.
