# HCO Roles / Victim-ID Audit — handoff brief

**Status:** ACTIVE VERIFICATION DEBT — implementation audit rechecked 2026-08-08.
The original mapping and primary fixes are complete; this file remains because
bounded verification and one low-frequency attribution edge are still open.

## Current status (2026-08-08)

| Finding | Current disposition |
|---|---|
| Stale non-shot ball handler / victim (bug #5) | **Shipped.** The stop-step handler is synchronized into `roles`; dynamic measurement found the no-index fallback dead in practice. |
| Ball-owner snap-back after reversal | **Shipped.** `_walk_ball_owners` carries the running owner instead of reselecting PG-first every step. |
| Moment-defender stash discarded | **Shipped.** `_hco_moment_defender_id` now overrides the later recompute. This is stat/draw-moving and still owes the recorded distributional verification plus seeded-reference re-cut. |
| Zone moment defender selected from the wrong layer | **Shipped.** Selection uses the rendered per-step guard map with documented fallbacks; canonical behavior and remaining validation debt live in `Dynamic_HCO_System.md`. |
| Interception finalizer | **Retain as a separate path.** Measurement found its interceptor/contact correct; passer identity was explicit in 96% of samples. The remaining ~4% stale-victim fallback is low priority but unresolved. |
| Split-encoded reversal DBTO ordering | **Shipped in current code and canonical docs.** The pending-pass walk transfers on the later receive step. No dedicated current test was found by the 2026-08-08 audit, and the recorded in-app confirmation is still not marked complete. |
| Universal stop-state rewrite | **Not recommended from current evidence.** Measurement ruled out the proposed broad consolidation as disproportionate to the remaining defects. |

The unresolved step-zero owner bootstrap disagreement belongs to
`projects/UESS Audits/HCO_UESS_Audit.md`; it is not a reason to broaden this
non-shot finalization audit.

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
- [StepState.md](Z-Completed/StepState.md) — the offense-walk unification (done); this audit is the **non-shot
  finalization** counterpart that was never unified.
- [UESS System §12.3](../05_UESS_System/UESS_System.md#123-stepstate-upstream-ownership-gap) — the broader
  upstream-ownership gap; this audit is in the same family (multi-source re-derivation of a
  game-relevant value).
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
- **Committed + pushed + in-app confirmed "significantly better"** (2026-07-24). Still owed: distributional verification + reference re-cut (batch with any further defender-credit fix).

### Seam-2 measurement — Path B is largely CORRECT (2026-07-24, temp probe, reverted)
Instrumented `_finalize_hco_pass_interception` over 20 games (163 interception-steals). Contrary to the hypothesis that Seam 2 was the visual residual, **Path B holds up**:
- **Defender (interceptor): missing 0/163.** It's the actual pass-contest interceptor — genuinely the right defender, never absent. **No "wrong defender" bug here** (unlike Seam 3's Path A).
- **Victim: stale-fallback only 6/163 = 4%** (`passer_pos` present 96% → victim = the real passer). Small edge.
- **Contact-point / interceptor step-in: present 100% for BOTH man AND zone.** The `# Man defense only` comment (L5903) is **stale** — zone interceptions DO get the step-in. No zone render gap.

**Conclusion:** the big Seam-2 consolidation is **not worth it** — Path B isn't the residual. The measurement (again) prevented a risky, low-value rewrite (cf. Seam 1 dead-in-practice). Only a 4% stale-victim edge remains, and fixing it is itself a stat-moving change (turnover credit → cascade), so it'd batch into the same distributional pass, low priority.

**So the remaining visual "not 100%" is NOT the defender on either path's finalization.** Human-eye localization (2026-07-24): "SOME steals stolen by a defender NOT guarding the BH; interceptions/fouls/DBTOs now correct." → isolates it to **moment-steals** (on-ball strips).

### Residual root cause = (A) zone defender SELECTION, not finalization/render (2026-07-24, discriminator probe, reverted)
Probe (`[SEAM2B]`, sim-safe `_build_all_animations` grid): at each moment-steal, ranked the credited defender by distance-to-BH among all defenders. 70 moment-steals:
- **MAN: credited defender is the NEAREST to the BH 100% of measurable cases** (avg credited-dist == nearest-dist = 3.7). Man is correct.
- **ZONE: credited defender is NOT the nearest ~62% of measurable cases** (rank distribution 1:12, 2:8, 3:11, 4:1). **avg credited-dist-to-BH = 7.3 vs nearest = 3.1** — the credited zone defender is >2× farther from the BH than the actual nearest defender.

**Verdict: (A) SELECTION, zone-only.** The on-ball moment credits (and renders the strip on) a zone defender who isn't the one contesting the BH. NOT a finalization bug (roles audit) and NOT a render step-in gap (B). This is the **zone on-ball-defender selection** feeding the moment — the **defender-grid / dynamic-defense layer**, adjacent to but distinct from this roles audit. The fix is upstream (which zone defender the moment rolls/credits) and — because it changes which defender's attributes roll the strip — a **genuine gameplay change** (draw-moving, distributional verification), bigger than the Seam-3 credit fix.

---

## ✅ SHIPPED status (2026-07-24)
- **Seam 3 (moment-defender credit):** committed `eddd85671`. Owes distributional verify + reference re-cut (batch).
- **Zone on-ball-defender SELECTION (guard-map fix):** committed `e5752203b`. `_stamp_contest_defender_grid` stamps the render's per-step guard map (ZONE-only) into `step["_step_state"]["guard"]`; `_zone_bh_defender` returns the defender whose guarded player == the BH (exact, frame-independent) with the polygon path as unstamped fallback. Zone rank-1 credited==nearest 38%→65%; matches the render by construction. Canonical behavior is now documented in [`Dynamic_HCO_System.md`](../06_Gameplay_Systems/Dynamic_HCO_System.md). Residual (render's own guardian is physical-nearest only ~61% of zone steps) is a **design decision** in `assign_all_zone_defenders`, not a bug — left as-is per product call.
- **DBTO fumble-before-pass timing (split-encoded reversals):** fix is present in the current tree and documented canonically in `Stopper_System.md` and `Step_By_Step_System.md`; render-only.

## DBTO fumble-before-ball-arrival — trace + fix (2026-07-24)
- **Symptom (product-eye):** on some (not all) HCO dead-ball turnovers, the victim's sprite animated the DBTO micro-movement + announcement *before* the ball had been passed to him; the pass landed only after.
- **Root cause (agent trace):** `_walk_ball_owners` (`skeleton_step_emitter.py`) transfers ball ownership only when ONE step holds both a `pass` and a `receive`. On **split-encoded reversals** — the receiver relocates into the catch, so his `receive` lands on a *separate* step from the passer's `pass` — the transfer never fired → `is_pass_step` false everywhere → no timed ball flight / no `ball_reaches_player` gate. The ball stayed with the passer until the injected fumble step hardcoded `ball_state = victim` ([dead_ball_fumble.py:149](../../BackEnd/engine/dead_ball_fumble.py#L149)). So the fumble jitter + whistle collapsed onto the ownership flip → visibly *before* arrival. **Same-step reversals were always correct** (transfer fired → timed flight waited for the ball); **non-reversal DBTOs** had no pending pass → never affected. That's the some-but-not-all.
- **Fix (#1, consumer-side):** the walk now carries a **pending pass** (lone `pass` sets it; owner stays with passer) and flips ownership on the **next `receive` step**. Chosen over stamping `receive` onto the pass step because flipping on the receive step keeps flight geometry correct (meet-point resolves from the receiver's actual catch motion, not his pre-move spot — the same coord-frame landmine that made zone Attempt-1 worse). One rule, handles all splits uniformly; HCT shares the walk so it benefits too.
- **Verification:** unit test — split reversal now flips owner on the receive step (`…(PG,PG),(PG,SG)`); same-step control unchanged. **Game-outcome neutral** (seeded 20-game signature identical fix on/off) → render-only, **NO reference re-cut owed** (unlike Seam-3/zone). **Sim Perf Capstone NOT disrupted:** `_walk_ball_owners` is *not called in the stat-sim path* (0 calls across 20 games / 147 HCO turns — HCO animation build is gated to the render path via `TurnManager.resolve_half_court_offense`, which pooled/stat sims bypass); the cpu/turn deltas seen mid-measurement were thermal noise (FIX-OFF came out both faster and slower than ON).
- **Owed:** retain an in-app visual confirmation on a split-reversal DBTO (ball lands before the fumble jitter/announce) and add durable focused regression coverage for the pending-pass ownership walk.
- **Producer cause (unconfirmed, low priority):** what makes a reversal split-encode vs same-step — leaning "receiver relocating into the catch" (movement pass) over "hot read"; not needed for the fix, a one-probe census (`phase_resolution.py:6084-6109` same/split tally) would settle it.
