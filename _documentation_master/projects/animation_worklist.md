# Animation — Open Worklist

**Created 2026-09-04** by splitting `bugs.md`. This file exists because animation items were
scattered across four sections of a 1,068-line task doc while the Animation bucket itself
read as a single line. It is an INDEX plus the ORPHANS — not a new assessment.

---

## Source of truth

The animation assessment already exists and is NOT superseded by this file:

| Doc | What it is |
|---|---|
| [`animation_cleanup_findings.md`](animation_cleanup_findings.md) | **Primary.** Trace findings, 2026-08-27/28. Verdict: no overhaul needed; the missing 30% concentrates in 3 root causes. §§10-18 are implemented passes. |
| [`animation_cleanup_brief.md`](animation_cleanup_brief.md) | Symptoms + references, in the user's words. The "what good feels like" doc. |
| [`UESS_Backlog.md`](UESS_Backlog.md) | Legacy audit remediation items 5, 7, 8, 9, 10, 12-17 still open |
| [`step_transition_centralization.md`](step_transition_centralization.md) | Proposed work plan, implementation not started |
| [`UESS Audits/`](UESS%20Audits/) | Per-path audits (BIP, DREB, FCP, FB, Final Turn, FT, HCO, HCT, OREB, Coord Consumer) |
| `Unified_Animation_System.md` | Blueprint referenced by the P0 items below |

**The three root causes** (`animation_cleanup_findings.md` §§2-4):

1. **Freeze-by-default** — `transition_bridge.build_pass_step(continuing_targets=None)`
   freezes everyone but passer/receiver. Explains 4 of 8 symptoms. Named the
   highest-leverage change in the project: invert the default, promote
   `_initialize_continuing_movement` to a shared builder base.
2. **Geometry-free actor selection** — distant steals/fouls; resolution-layer, not animation.
3. **No shot-release timing model** — shot timing is a byproduct of traversal time.

---

## Orphans — open animation items that lived only in `bugs.md`

**Reconciled against `animation_cleanup_findings.md` on 2026-09-04 — all eight confirmed still
open.** That doc mentions neither `SUBTLE_STEP_ELAPSED_BY_TEMPO` nor the HCO clock-overrun
contracts anywhere (grepped). The two items previously flagged as possible duplicates are not.

### P0 — HCO contract clock overruns (carried from Unified_Animation_System.md, 6-12-26) [CODE-CLEANUP]

*Not in the findings doc's table of contents. Treat as a genuine orphan.*

Two critical issues from the animation blueprint's "Known HCO Turn Issues" list (`projects/Unified_Animation_System.md`):

1. **HCO resolution hard overrun:** observed throw `"[HCO resolution contract] clock overrun ... elapsedGameSeconds=649.00"` on a `DEAD BALL` path. **Partial mitigation (Option A):** turn-boundary guards in `turnAnimation.js` use contract-capped elapsed (`min(wall_elapsed_ms, real_time_elapsed_ms + guard_slack_ms)`). Throws still exist; needs live validation before closing.
2. **HCO step-pass hard overrun in BATCH/DEAD BALL sub-turns:** observed throw `"[HCO step pass contract] clock overrun ... elapsedGameSeconds=405.78"` at `step=6`. **Still uncapped** — step-pass guard uses raw `Date.now() - stepStartMs` (no Option A). Track separately from #1.

### Motion step pauses (Bucket 1)

*✅ RECONCILED 2026-09-04 — **not a duplicate, and probably the largest single source of dead
air in the game.** §5d's backend-hold inventory does not list `SUBTLE_STEP_ELAPSED_BY_TEMPO`;
its largest entry is 1000ms and those are one-off event beats. A Motion subtle beat floors at
2–4 GAME-seconds, which at `clockSecondMs`=350 is **700–1400ms of wall clock on an ordinary
step**, repeatedly, in the most common turn type in the game. §6 attributes seam pauses to
root-cause-#1 stacking and explicitly says "not measured" — it is not this. Fold into the §7
dead-air ledger as its own category before tuning.*

**Meta:** With dynamic HCO on, Motion/Set-Play render via backend `animation_steps[]` (`animationPlayback.js`). Pause durations are stamped in Python (`time_elapsed`, `hold_ms`); FE-only fixes miss the source. Design work applies only to optional idle-sprite drift (Bucket 1 secondary).

### Open — Bucket 1: Long pauses between HCO steps (Motion only)
- **Symptom:** All ten players frozen 700–1400ms on many Motion steps; Set Play unaffected.
- **Root cause:** Motion "subtle-movement" beats floor at **2–4 game-seconds** (`SUBTLE_STEP_ELAPSED_BY_TEMPO` in `motion_step_decision.py`; stamped via `skeleton_step_emitter.py`). Schema engine hard-waits full `time_elapsed` (`animationPlayback.js`). Set Play forces `offense_reads=False` → fewer subtle beats.
- **Fix:** Decouple sim clock from visual time — keep 2–4s on game ledger, stamp small visual `time_elapsed`. Optional: off-ball drift during BH hold so 9 players don't read as frozen.
- **Secondary:** Confirm BH hold doesn't block the other 9 from moving; consider idle organic sprite animation on truly stationary steps.

### Fast Break animation backlog (legacy path) [CODE-CLEANUP]

*✅ RECONCILED 2026-09-04 — **not superseded.** §15 fixed the board-crash early-out on the
SCHEMA path (`transition_shot_board_crash.py`). Every item below is about the LEGACY
`fastBreak.js` / `runFastBreakSequence` fallback: advance triggers, FE `getPlayerDuration`
timing, charge/blocking foul. Different path, different code. Priority is genuinely lower —
UESS retires this path per backlog items 14–15 — but nothing here is fixed.*

Tracked from archived [`Z-Completed/Fast_Break_Refactor.md`](Z-Completed/Fast_Break_Refactor.md). **UESS schema path is primary** for `covert_release`, `rim_runner`, `triangle`, `after_steal` when `animation_steps` exist; legacy `runFastBreakSequence` remains the fallback when steps are missing / variant unmigrated.

- Advance triggers unreliable on legacy `fastBreak.js` / `runFastBreakSequence` (phase boundaries hang or short-circuit).
- FB visual timing still uses FE `getPlayerDuration` on legacy path; backend does not stamp per-player `game_seconds` in legacy `animator.capture_fast_break_animation` payload.
- Charge/blocking foul on FB: stop animation immediately (don't wait for defensive spot) — see Bugs §14.
- Full phase map and backend sites: archived refactor doc.

### Legacy shot handler crashes on turns with no animations[] (`ShotAnimationSystem.runSetupTween`)

*Moved from `bugs.md` Bugs §5. A live diagnostic is armed and waiting to fire.*

   - Symptom: `TypeError: turnData.animations is not iterable`. Caught by `processShot`, so no crash,
     but that shot silently does not animate (possession appears to skip its shot).
   - A SHOT_ATTEMPT reached the LEGACY handler carrying no `animations[]`. Schema turns bypass these
     handlers entirely, so this is either (a) an un-migrated path whose backend emit produced nothing,
     or (b) a routing bug where a turn WITH `animation_steps[]` was sent to the legacy handler anyway.
   - NOT fixed with a `|| []` guard on purpose: that would silence the console and hide the emission
     failure behind a shot that quietly does not animate. A `[SHOT-NO-ANIM]` diagnostic is in place
     (2026-08-27) logging result_type / current_turn / fast_break_play / hasAnimationSteps / turnKeys.
     `hasAnimationSteps: true` => routing bug. `false` => upstream emission bug.
   - Next occurrence identifies the culprit; fix by migrating that path, then delete the diagnostic block.
   - Related: `ShotAnimationSystem.js` guards `turnData.animations` inconsistently (guarded at 295/479/486,
     bare at 352/455/572/666). Sites 572/666 remain unguarded on the final_turn-skips-setup path.
   - Pre-existing; unrelated to the animation cleanup pass.

### Steal -> HCO setup: backend computes positioning the frontend no longer renders [CODE-CLEANUP]

*Related to root cause #2 (the `apply_coords` antipattern) but is a separate dead-compute cleanup.*

- **Issue**: `resolve_half_court_offense_logic` (`BackEnd/engine/phase_resolution.py`) still emits `is_steal_hco_setup`, `ball_handler_hco_setup_*`, and `other_players_hco_setup_movements`. The frontend has removed `animateStealHCOSetup()` and stopped reading those fields. UESS has a replacement (`_append_post_steal_hco_transition` in `skeleton_step_emitter.py`), but the old role-field contract is unused.
- **Impact**: Low — backend is doing compute-but-unrendered work. No visible bug, just wasted computation and a misleading contract.
- **Action**: Remove the Steal → HCO setup positioning computation and its emitted fields from the backend resolver. Confirm no other consumer reads those fields first.
- **Priority**: Low (dead/unrendered compute, not causing bugs)

### Legacy steal-entry Fast Break dead code + unused `STEAL_ENTRY_*` constants [CODE-CLEANUP]

- **Issue**: All steals are short-circuited to the UESS-migrated `after_steal` resolver early in `resolve_fast_break_logic` (~L1205), which makes the legacy steal-entry movement block later in the same function (~L1517–1541) unreachable dead code. The `STEAL_ENTRY_MOVE_*` / `STEAL_ENTRY_Y_*` constants that block relied on are now unused on the rendered path in both `BackEnd/constants/fast_break_constants.py` and `FrontEnd/static/js/phaser/constants/fastBreakConstants.js`.
- **Impact**: Low — unreachable code + orphaned constants. No runtime effect, just bloat/confusion for anyone reading the FB resolver.
- **Action**: Delete the unreachable steal-entry block in `resolve_fast_break_logic` and remove the unused `STEAL_ENTRY_*` constants from both the backend and frontend constants files. Verify nothing on the live `after_steal` path references those constants before removing.
- **Priority**: Low (dead code; tie in with the FB-coverage follow-up noted in the "Stale FB test suite" item above)

### Invalid State Transition Warning [CODE-CLEANUP]

- **Issue**: State machine attempts no-op transition (HalfCourt -> HalfCourt)
- **Location**: `FrontEnd/static/js/phaser/animation/AnimationEngine.js` → `handleBaselineInbound()` still calls `safeTransition` unconditionally (tip path has an `is(HalfCourt)` guard; BIP does not)
- **Impact**: Low - harmless but indicates unnecessary `safeTransition()` call
- **Action**: Review `handleBaselineInbound()` to avoid calling `safeTransition()` when already in target state
- **Priority**: Low (code cleanup)

### Stale FB test suite — open follow-up [CODE-CLEANUP]

Stale pre-refactor FB tests were deleted 6-12-26; suite is green. **Still open:** current-engine FB coverage is thin — `test_fast_break_rr_triangle_updates.py` covers RR/Triangle emitters, but the CR resolver path and `after_steal_fast_break.py` (resolver + emitter) have little/no direct test coverage. Write new tests against the current resolvers when FB work resumes.

---

## Adjacent — filed elsewhere, animation-suspected

- `bugs.md` Bugs §1 — "Getting some double rebounds (SFX, maybe animation, not sure about logic)". Unattributed.
- `bugs.md` Full Product Perfection §131 — "Centralized Turn Transition Helper / System". See [`step_transition_centralization.md`](step_transition_centralization.md).
- `bugs.md` Open Investigations — "Play Quarter" requires two clicks (`bootGame.js` init timing). Frontend boot, not animation, but it is the first thing a playtester hits.

---

## Known gap

There is no single map of **which turn types render via the UESS schema path
(`animation_steps[]`) versus which still fall through to a legacy orchestrator**. The
per-path UESS audits cover this piecemeal; nothing consolidates it. That map is what makes
"the fragmentation is visible in execution" measurable rather than felt.

---

## Reconcile finding (2026-09-04): one meta-pattern behind several of these

Four separate defects in this system share a single shape — **a failure converted into a silent
degradation**:

| where | the silence |
|---|---|
| `animation_cleanup_findings.md` §17 | emitter `try/except` swallows a `TypeError` → `animation_steps` unset → silent legacy render → HCO cold start → teleport. "It was never a guard, it was an exception." |
| `animation_cleanup_findings.md` §15 | `transition_shot_board_crash` early-`continue` for players inside radius 11 → the board-crash system silently no-ops in exactly the case it exists for. "The fix existed, and an early-out was hiding it." |
| `ShotAnimationSystem` orphan above | `processShot` catches the throw → "no crash, but that shot silently does not animate" |
| `scripts/verify_deploy.py` (found 2026-09-04, see `bugs.md`) | `pin_hash_seed()` at import re-execs the interpreter → the entire pytest session exits 0 reporting nothing |

**This is very likely a large part of what "the fragmentation is visible in execution" actually
is.** Individual fixes land; a silent fallback keeps serving the old broken path; the symptom
survives and looks like a new bug. §17's own conclusion — the FB freeze "survived 5–6 fixes"
because the default kept reintroducing it — is the same story from the other side.

The `[SHOT-NO-ANIM]` diagnostic already in the tree is the right instinct, and the deliberate
refusal to add a `|| []` guard (recorded in the orphan above) is the right call for the same
reason. **Worth considering as its own work item:** an emitter-level counter for every
schema→legacy fallback, surfaced rather than swallowed, so the rate is visible instead of
inferred. Today a fallback is indistinguishable from normal operation until a user reports a
teleport.
