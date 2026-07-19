# HCO Roles / Victim-ID Audit — handoff brief

**Status:** scoped, not started. Spun out of the StepState thread (2026-07-19) so it can run in a
separate agent WITHOUT blocking the StepState work plan. One concrete instance (bug #5) is already
**confirmed + fixed**; this brief hands off the broader audit it implies.

> **Purpose:** determine whether HCO **non-shot outcome finalization** (turnover / foul / steal) is
> structurally unsound — the same fact (who has the ball / who is the victim / where did it happen)
> re-derived in multiple places that can disagree — and if so, collapse it to one authoritative
> "stop state." This is the layer the StepState refactor did NOT unify (it unified the offense walk).

---

## TL;DR hypothesis
`roles` is a mutable bag populated + patched at ≥4 stages from different sources. The only real
source of truth for "who holds the ball when the possession ends" is
`get_ball_handler_from_skeleton(skeleton, step_index=stop_step_index)`, but it is **not uniformly
propagated** — several consumers read stale `roles` fields or re-derive independently. When those
disagree, the animation renders the outcome on the wrong player / wrong spot. This is the same
"multiple independent re-derivations of one game-relevant value" pattern the StepState *governing
law* exists to kill; the non-shot finalization path just never got the resolve-once treatment.

---

## ✅ Confirmed instance (bug #5) — already fixed
- **Symptom:** HCO dead-ball turnover after a ball reversal — ball correctly reaches the receiver,
  holds a beat, then **snaps back to the original passer** and the DB-turnover jitter renders on the
  passer's sprite.
- **Root cause:** the defender-override block in `resolve_half_court_offense_logic`
  (`phase_resolution.py`, entered for `result in [STEAL, DEAD_BALL_TURNOVER, SHOT_CLOCK_VIOLATION,
  O_FOUL, D_FOUL]`, ~L7506) recomputes the true stop-step handler into a LOCAL `ball_handler`
  (`get_ball_handler_from_skeleton(..., step_index=stop_step_index)`) and used it only to fix
  `roles["defender"]` — it **never wrote `roles["ball_handler"]` back**. So `roles["ball_handler"]`
  stayed the stale `assign_roles` value (the intended shooter / original passer). `resolve_turnover_logic`
  then set `victim_id = roles["ball_handler"].player_id` = the passer → the dead-ball fumble
  (`_resolve_ball_handler_id`, prefers `victim_id`) drew on the passer.
- **Fix (shipped, ~L7525):** `roles["ball_handler"] = ball_handler` + `roles["ball_handler_id"] = …`
  right where the defender is corrected.
- **Headless verification:** instrumented run showed `roles.ball_handler` corrected passer→receiver
  on DBTO turns — **and the same stale-handler defect also hit `D_FOUL` and `SHOT_CLOCK_VIOLATION`**
  on reversal turns (they appeared in the same log). So it was a *class*, not a one-off.
- **Pre-existing** (not introduced by the scenario-3 dead-ball feature; matches bugs.md #1). The
  scenario-3 work just made reversals frequent enough to expose it.

---

## The seam — where the same fact is derived (audit these for disagreement)
| # | Site (function / approx line, `phase_resolution.py` unless noted) | Sets/derives | Source |
|---|---|---|---|
| 1 | `assign_roles` (called ~L7501) | `roles["ball_handler"]`, `roles["shooter"]` | skeleton's **intended shooter** (early, often wrong for non-shot) |
| 2 | defender-override block (~L7506–7662) | `roles["defender"]` (+ now `roles["ball_handler"]` via fix) | `get_ball_handler_from_skeleton(stop_step_index)` — **the truth** |
| 3 | non-shot event block (~L7895–8008) | reads `roles["ball_handler"]`, calls `resolve_turnover_logic` | prefers `roles["ball_handler"]` if set, else re-derives |
| 4 | `resolve_turnover_logic` (~L2576) | `victim_id = roles["ball_handler"].player_id` (~L2610) | `roles["ball_handler"]` |
| 5 | dead-ball fumble `_resolve_ball_handler_id` (`dead_ball_fumble.py` L65) | fumble target sprite | `victim_id` > `shooter_id` > `ball_handler_id` > `ball_handler` (first in `coords`) |
| 6 | stopper build `apply_stopper_system_to_skeleton` (~L3651) | stopper-step BH + `steal_stop_step_index` | scans the stop step's `pos_actions`; consumes `_hco_moment_stop_index` pin (~L3689) |
| 7 | moment defender stash | `roles["defender"]` for zone | `game_state["_hco_moment_defender_id"]` (consumed ~L7913) |

**Source of truth:** `get_ball_handler_from_skeleton(skeleton, off_lineup, step_index=…)` (~L350) +
`_motion_bh_at_step` (~L4611, returns the **receiver** on a pass step). Everything should trace to these.

**Note:** interception STEALs bypass the block — `_finalize_hco_pass_interception` (~L5273) returns
early from the `[5]` shot-resolution block and does its own pinning (`_hco_pass_intercept_stop_index`
+ `_hco_uncatch_receiver_on_pass`). So there are effectively **two** steal paths (moment-steal through
the block; interception-steal through the finalizer) with separate victim/stop logic — a prime
disagreement candidate.

---

## Symptoms to confirm (suspected same root — NOT yet traced)
1. **Steals happening away from the ball handler.** Check: moment-steal victim/defender/stop-step vs.
   rendered position; the zone position-on-position fallback in the override block; the two-steal-path
   split above.
2. **Fouls (O_FOUL/D_FOUL) in odd places.** Check: `_hco_moment_stop_index` pin vs. rendered foul
   position; stale victim (same #5 class — partially addressed by the fix, verify O_FOUL specifically).
3. **General ball teleports on non-shot outcomes.** Check: emitter ball-owner walk (`_walk_ball_owners`,
   `skeleton_step_emitter.py` ~L369) end-owner vs. `turn_result` victim/handler at the stopper.

---

## Recommended audit plan (read-only first, then collapse)
1. **Map writes+reads** of `ball_handler`, `ball_handler_id`, `victim_id`, `shooter`/`shooter_id`,
   `defender`, `stop_step_index`, `contact_point` across the non-shot finalize path (sites 1–7 above).
2. **Find disagreements** — instrument each non-shot outcome to log (chosen-by-engine vs. read-by-emitter)
   for handler / victim / defender / stop-step; run the sim; diff. (Full-sim skips the emitter, so
   verify backend values headlessly + eyeball the render for the emitter half — see caveat below.)
3. **Collapse to one authoritative "stop state"** frozen once (handler, victim, defender, step index,
   contact point) and read everywhere downstream — mirroring what StepState did for the offense walk.
   Likely subsumes bug #5 + the steal-location + foul-location issues together.

**Verification caveat (learned this session):** the full-sim harness
(`scripts/test_hco_resolution_stats.py`) does NOT build `animation_steps` (emitter early-returns), so
you can validate **backend** values (victim_id, roles, stop index) headlessly but CANNOT observe the
rendered ball trajectory from a script. The render half needs an in-app look or a render harness that
bypasses the full-sim gate. Bug #5's render symptom was diagnosed via the user's in-app observation
("ball reaches receiver, holds, snaps back to passer") — plan for that loop.

---

## Key files
- `BackEnd/engine/phase_resolution.py` — `resolve_half_court_offense_logic` (spine), the defender-override
  block, `resolve_turnover_logic`, `get_ball_handler_from_skeleton`, `_motion_bh_at_step`,
  `apply_stopper_system_to_skeleton`, `_finalize_hco_pass_interception`.
- `BackEnd/engine/dead_ball_fumble.py` — `inject_dead_ball_fumble_before_turn_stop`, `_resolve_ball_handler_id`.
- `BackEnd/engine/skeleton_step_emitter.py` — `_walk_ball_owners`, `build_skeleton_animation_steps`.

---

## Update 2026-07-19 — second seam of bug #5 found + fixed (ball-owner walk)
After the `roles["ball_handler"]` fix corrected the turnover **victim/jitter**, the **ball sprite**
still animated back to the passer. Confirmed this is a SECOND, independent derivation of "who has the
ball": the emitter's `_walk_ball_owners` (`skeleton_step_emitter.py` ~L369). It re-scanned every step
and reset the owner to the first `_OFFENSE_POSITIONS`-order (PG-first) `handle_ball`/`pass` pos —
ignoring the running owner. The loop skeleton keeps `PG: handle_ball` nominally set at PG's home spot
even after a reversal, so the walk snapped ownership back to PG.

- **Headless proof:** ran `_walk_ball_owners` on real reversal-DBTO skeletons → `step1: PG→SF`
  (ball reverses), `step2: PG→PG` (snaps back) — exactly the observed render.
- **Fix (shipped):** bootstrap the owner only when there's no running owner; then CARRY it, changing
  ownership only via a pass→receive transition. `skeleton_step_emitter.py` ~L390.
- **Verified:** reversal-DBTO flip-back-to-start 12→**0**; shot-turn final owner == shooter 290/294
  (the 4 are kickout/dish + degenerate-2-step edge cases, being confirmed as not-a-regression via an
  old-vs-new diff). `_walk_ball_owners` is a **shared HCO/FCP function** — regression-checked.

**Lesson for the audit — this is the pattern to hunt.** ONE game fact ("who has the ball") had TWO
independent derivations (`roles`/`victim_id` for the jitter, `_walk_ball_owners` for the sprite) that
disagreed; fixing one left the other. Expect the steal-location and foul-location symptoms to have the
SAME shape — a jitter/credit path and a sprite/coord path derived separately. Look for every consumer
that re-derives handler/victim/owner rather than reading one frozen value, and check the two halves
(logic credit vs. rendered position) agree. Doc updated: [HCO_UESS_Audit.md](UESS%20Audits/HCO_UESS_Audit.md)
Resolver B description (§ the two-resolver seam). The step-0 A-vs-B seam there is still OPEN — the
bootstrap still uses B's PG-first rule.

## Cross-links
- [StepState.md](StepState.md) — the offense-walk unification (done); this audit is the **non-shot
  finalization** counterpart that was never unified.
- [stepState_gaps.md](stepState_gaps.md) — the broader UESS-compliance gaps; this is a new one in the
  same family (multi-source re-derivation of a game-relevant value).
- bugs.md #1 (HCO entry-step DB-turnover teleport), #5 (DB turnover ball snaps back — fixed).
