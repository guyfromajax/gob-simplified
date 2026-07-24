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

## Related shot-frame finding (2026-07-22)

The same multi-source pattern was confirmed in HCO shot defense, outside this audit's non-shot scope:
full sims updated the shooter from the final skeleton step but left defenders on stale
`Player.coords`, even though StepState already held per-step defender geometry. The first bounded
resolve-once contract, `ShotAttemptGeometry`, now freezes shooter + defender coordinates and is passed
directly to `resolve_shot()`. Treat it as a proving slice for a future universal decision/stop-state
contract; do not overload it with victim/contact/ball-owner fields until the shot path is validated.

---

## Static write/read map — mapping pass (2026-07-24, read-only, no code changes)

Full field-flow trace of the non-shot finalize path. All line refs `phase_resolution.py` unless noted.

### Two disjoint finalize spines
- **Path A — non-shot block** (`result` already flipped to a non-shot type): `apply_stopper_system_to_skeleton` (L7711) → **defender-override block** (L7729–7894) → non-shot finalize (L8100–8259) → `resolve_turnover_logic` (L8239). Finalizes **DBTO, SHOT_CLOCK_VIOLATION, O_FOUL, D_FOUL, moment-STEAL**.
- **Path B — interception finalizer** (`result` stays `"SHOT"`, a walked/coverage pass got picked): shot branch L8480 → `_finalize_hco_pass_interception` (L5880) **returns early**, bypassing Path A. Finalizes **interception-STEAL** (+ `_finalize_hco_pass_bat_oob` L5970 for BAT_OOB).
- `result` flips to Path A when the fused resolver returns `{"moment_result": …}` (consumed spine L7596), or drive-contact foul (L7604).

### The seams (where one fact is derived ≥2 ways / can go stale)

**Seam 1 — stale intended-shooter vs true stop-step handler (bug-#5 family; has a REMAINING GAP).** `assign_roles` seeds `roles["ball_handler"] = shooter` = the **final step's `shoot` action** (turn_manager ~L6300). On a non-shot outcome the true handler is at the *stop* step. The override block scrubs it (L7742 `get_ball_handler_from_skeleton(step_index=stop_step_index)` → L7757 sync) — **but only `if stop_step_index is not None` (L7740)**. With no pin/index it falls back to `roles.get("ball_handler")` (L7745) = the stale shooter; `victim_id` (L2614) and the dead-ball fumble (`_resolve_ball_handler_id`, dead_ball_fumble.py L69, precedence `victim_id > shooter_id > ball_handler_id`) inherit it. **→ bug #5's fix does not cover the no-index path — a concrete residual to confirm + close.**

**Seam 2 — the two STEAL paths derive victim / stop-step / defender / contact independently.** Never share code past `resolve_turnover_logic`:
| Field | moment-STEAL (Path A) | interception-STEAL (Path B) |
|---|---|---|
| victim/handler | `get_ball_handler_from_skeleton(step_index=steal_stop_step_index)` L7742 → synced L7757 | `off_lineup[passer_pos]` L5888 |
| stop step | `_hco_moment_stop_index` L6510 → `steal_stop_step_index` L3814 | `_hco_last_pass_step_index` → `_hco_pass_intercept_stop_index` L5894 |
| defender | matchup/zone recompute at stop-handler L7875/7884 | `def_lineup[interceptor_pos]` L5930 |
| contact | reverse-engineered from animation end coords L8219 | geometric `pass_contact_point` L5904 |

**Seam 3 — moment-defender stash usually silently discarded.** `game_state["_hco_moment_defender_id"]` (live writer = fused resolver L6509) is consumed at L8144 **only `if not roles.get("defender")`** — but the override block already set `roles["defender"]` from a fresh matchup/zone recompute (L7875/7884). Docstring (L6250) says the stash exists precisely because the man position-match ≠ the actual zone contesting defender → the credited moment defender and the finalized defender can disagree, stash loses.

**Seam 4 — `_hco_moment_stop_index` pin leak.** Written by 4 sites (L4653/L6308/L6510/L7610), popped by `apply_stopper` (L3693). If a writer sets it but the result routes to SHOT (L7622 fallback) instead of through `apply_stopper`, the pin survives into a later turn's stopper (guarded by pop-on-consume + defensive clears L6264/L6447 — verify the guard holds).

### Draw-impact classification (drives Plan-A verification per fix)
- **Attribution-only (no RNG draw change → exact-diff verifiable; scores/flow byte-identical, only credit/sprite moves):** Seam 1 handler propagation, Seam 2 victim unification, Seam 3 defender-credit, the emitter `_walk_ball_owners` (render-only, no RNG at all).
- **Draw-changing (→ poison-stash + re-cut reference):** anything touching the **stop-step PIN** logic in `apply_stopper` — O_FOUL/D_FOUL random step `random.randint(1,len-2)` L3709, DBTO/STEAL random blast-radius L3714–3732, zone-tie defender `random.choice` L7869. If a fix makes a pin *always present* so a `random.*` fallback stops firing, it removes draws by construction.

### Sim vs render
Every field write/read above runs in the **backend sim** (`phase_resolution.py`/`turn_manager.py`/`pass_contest.py`), RNG all `sim_rng`. `_walk_ball_owners` (emitter) + `_resolve_ball_handler_id` (dead_ball_fumble) run **render-only**, no core RNG → **zero bulk-sim cost.**

## Dynamic measurement — 20-game exhibition sim (2026-07-24, temp probes, reverted)

Ran `scripts/test_hco_resolution_stats.py` (20 full Morristown-vs-Four-Corners games, in-memory, no DB writes) with 4 read-only ERROR probes at the seam branches. 494 non-shot finalizations. Probes reverted via `git checkout` (tree was clean).

| Seam | Measured | Verdict |
|---|---|---|
| **1 — no-index stale-handler gap** | **0 / 494** hit the fallback (`apply_stopper` always sets `steal_stop_step_index`, so `stop_step_index` at L7735 is always truthy → the scrub always runs) | **Dead in practice.** Bug #5 is effectively closed live. Fix = optional defensive comment only. |
| **2 — two independent steal finalizers** | Path A moment-steal **76** vs Path B interception-steal **173** (~**70% of steals** go through the *separate* `_finalize_hco_pass_interception`) | **High-frequency structural seam.** ~250 steals/20 games split across two victim/defender/contact derivations. |
| **3 — moment-defender stash discarded** | stash present on **460/494**; **discarded 100%** (override block always pre-set `roles["defender"]`). Refined probe: credited defender **differs** from the stash in **238/487 = 49%** overall — **MAN 13%, ZONE 69%** | **Pervasive + wrong ~half the time.** The stash (designed as the *accurate* contesting defender, esp. zone) never wins; the credited/rendered defender is the position-on-position recompute, wrong on ~½ of non-shot outcomes (69% in zone). |
| **stop-step pin** | **0** random fallbacks — every stop-step pinned (moment/intercept pin) | The `random.randint` fallbacks in `apply_stopper` (L3709/L3730) **never fire** → stop-step consolidation is **draw-neutral in practice**. |

**Reprioritization from the data:**
1. **Seam 3 is the highest-value target** — 49% wrong defender (69% zone), and the *minimal* fix (prefer the stash at L8145 even when `roles["defender"]` is preset) is **attribution-only / draw-neutral**: the zone-tie `random.choice` in the recompute still fires (draw preserved), we just keep the stash value → exact-diff verifiable, no reference re-cut (Plan A cheap tier).
2. **Seam 2 (two steal finalizers) is the biggest structural cleanup** but higher-risk (two paths may draw differently) — a later, heavier consolidation.
3. **Seam 1 is dead in practice** — deprioritize (defensive hardening at most).

### Seam-3 fix candidate — implemented, verification OVERTURNED the "cheap" prediction (2026-07-24)
Fix: at L8145 drop the `and not roles.get("defender")` guard so the moment-defender stash is **preferred** over the override block's recompute (matches the code's own docstring intent). **Seeded before/after (12 exhibition games, `scratchpad/seam3_verify.py`, PYTHONHASHSEED=0): NOT draw-neutral — 8/12 games diverged** (scores/turns/outcome-sequence). The prediction that this was attribution-only was **wrong, and the exact-diff caught it.**
- **Root cause:** the credited defender's *identity* is not terminal — it feeds foul/steal accumulation → **foul-outs → substitutions → downstream game state**, and likely attribute-driven RNG resolution. So re-crediting the *correct* defender changes the game's evolution.
- **Plan-A reclassification:** this is a **basketball change**, not a relabel → distributional verification (N seeds before/after) + a reference **re-cut** (requires human OK per the harness-access decision), NOT exact-diff.
- **Direction still likely correct** (matches the human-eye "wrong defender" disconnect), but "correct" now means "moves the stat distribution" — needs the heavier path + ideally an in-app visual confirm that the defender now renders on the right player.
