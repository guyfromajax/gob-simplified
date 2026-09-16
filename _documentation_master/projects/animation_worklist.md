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
| [`animation_cleanup_findings.md`](animation_cleanup_findings.md) **Appendix A** | Symptoms + references, in the user's words. The "what good feels like" doc. Merged into findings 2026-09-14 (was `animation_cleanup_brief.md`). |
| [`UESS_Backlog.md`](UESS_Backlog.md) | Legacy audit remediation items 5, 7, 8, 9, 10, 12-17 still open |
| [`step_transition_centralization.md`](step_transition_centralization.md) | Proposed work plan, implementation not started |
| [`UESS Audits/`](UESS%20Audits/) | Per-path audits (BIP, DREB, FCP, FB, Final Turn, FT, HCO, HCT, OREB, Coord Consumer) |
| ~~`Unified_Animation_System.md`~~ | **Not in the tree.** Retired August 2026 (was `00_General_Systems/`, then `projects/`). Durable UESS principles and the hybrid `unitCompletionContract.js` layer live in [`UESS_System.md`](../05_UESS_System/UESS_System.md), [`Core_Animation_System.md`](../05_UESS_System/Core_Animation_System.md), and [`UESS_Backlog.md`](UESS_Backlog.md) (hybrid-layer section). Orphan #1 (P0 HCO clock) closed 2026-09-15 — not a paying-user crash. See `Z-Completed/_documentation_sweep.md`. |

**The three root causes** (`animation_cleanup_findings.md` §§2-4):

1. **Freeze-by-default — SHIPPED 2026-08-27 for the FB/transition family** (`animation_cleanup_findings.md` §12). `build_pass_step` now defaults to `CONTINUE_FROM_PREVIOUS` (`transition_bridge.py:780`). Explicit `None` still freezes (a caller decision). HCO stationary / SIP-BIP passer holds were left as-is in that pass. **Do not re-implement. Not the highest-leverage open change.**
2. **Geometry-free actor selection** — distant steals/fouls; resolution-layer, not animation.
3. **No shot-release timing model** — shot timing is a byproduct of traversal time.

---

## Orphans — animation items that lived only in `bugs.md`

**2026-09-04 said "all eight confirmed still open." That line is retired.**
Re-verified against the tree 2026-09-15. Same trap as item 47 (fixed before anyone
scoped it). Do not brief from the 2026-09-04 sentence.

| # | orphan | status 2026-09-15 | tree check |
|---|---|---|---|
| 1 | P0 HCO clock overruns | **CLOSED 2026-09-15** | Traced. **Not a paying-user crash on the Played schema path** (0/1159 Played contract turns entered `playTurnAnimation`). Do not re-litigate from the old P0 label. `:4344` still throws but is Option-A capped (`getGuardedTurnElapsedMs`). `:5211` step-pass clock is **warn-only** on HCO — no per-step `real_time_elapsed_ms`, so Option A cannot cap it; aborting a tab-hide makes the turn worse. |
| 2 | Motion / Bucket 1 subtle-step pauses | **OPEN** | `SUBTLE_STEP_ELAPSED_BY_TEMPO` still `{slow:(2,4), normal:(2,3), fast:(1,3)}` (`motion_step_decision.py:43`). Not decoupled from visual `time_elapsed`. |
| 3 | Fast Break legacy backlog | **OPEN** (UESS is primary) | `runFastBreakSequence` still in `fastBreak.js:1809`; `AnimationEngine.js` and `turnoverAdapter.js` still import it. |
| 4 | Legacy shot handler / `runSetupTween` | **emission SUPERSEDED 2026-09-08; FE unguard OPEN** | bugs.md item 11 closed the FLSS stranded-skeleton emit (5 render-nothing / 8 games → 0). `ShotAnimationSystem.js:572` / `:666` still iterate `turnData.animations` unguarded. |
| 5 | Steal → HCO setup dead compute | **OPEN** | `phase_resolution.py:8868-8874` still stamps `is_steal_hco_setup` / `ball_handler_hco_setup_*` / `other_players_hco_setup_movements`. No FE readers. |
| 6 | Legacy steal-entry FB + `STEAL_ENTRY_*` | **OPEN** | after_steal returns at `:1549`. Steal-entry block at `:1858-1882` is still in the file. Constants still in `fast_break_constants.py:196-200` and `fastBreakConstants.js:104-108`. |
| 7 | Invalid HalfCourt → HalfCourt `safeTransition` | **OPEN** | `handleBaselineInbound` still calls `safeTransition(..., States.HalfCourt)` unconditionally (`AnimationEngine.js:1268`). No `is(HalfCourt)` guard. |
| 8 | Stale FB test suite follow-up | **PARTIAL** | `test_after_steal_fast_break_stats.py` and `test_steal_fast_break_routing.py` now exist. `test_fast_break_rr_triangle_updates.py` still the RR/Triangle coverage. CR resolver path still thin. |

Orphans **#2–#8 stay open as post-launch tech debt** (tree check 2026-09-15 above). #1 is closed — do not re-brief it as a P0 player crash.

Freeze-by-default is **not** one of the eight and is **not open** as a re-implement (root cause #1 above).

### P0 — HCO contract clock overruns [CODE-CLEANUP] — **CLOSED 2026-09-15**

*Not in the findings doc's table of contents. Genuine orphan. Blueprint cite retired — see Source of truth.*

**Traced 2026-09-15. Not a paying-user crash on the Played schema path.** Schema `playTurn` never reaches these contracts. Played seeds 1–8: 0/1159 `isStepContractTurn` rows entered `playTurnAnimation`. Do not re-open from the P0 keyword.

1. **HCO resolution hard overrun (`:4344`):** leftover on the no-steps `playTurnAnimation` path. Option A caps elapsed (`min(wall, real_time_elapsed_ms + 1500)`). Still throws if that cap exceeds budget.
2. **HCO step-pass hard overrun (`:5211`):** **warn-only** as of 2026-09-15. `real_time_elapsed_ms` is turn-level, not a step-pass contract, so Option A cannot gate this. A backgrounded tab is a normal player action; aborting the turn is worse than a warn.

### Motion step pauses (Bucket 1) — **OPEN** (2026-09-15)

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

### Fast Break animation backlog (legacy path) [CODE-CLEANUP] — **OPEN** (2026-09-15)

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

### Legacy shot handler crashes on turns with no animations[] (`ShotAnimationSystem.runSetupTween`) — **emission SUPERSEDED 2026-09-08; FE unguard OPEN**

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
   - ✅ ANSWERED 2026-09-08 by measurement rather than by waiting for the next occurrence:
     **`false` — an upstream emission bug.** FLSS normal/penalty shots built a skeleton into a local
     `roles` dict and returned a different dict from `resolve_shot`, so the skeleton never travelled;
     `turn_manager.py:2096` gates the whole FLSS emit block on it, and FLSS carries no `roles` for
     the legacy fallback either. 5 render-nothing shot turns per 8 games, now 0. See bugs.md item 11.
   - The FE-side cleanup below is still open — the emission gap that reached it is closed, but the
     handler stays unguarded at 572/666.
   - Related: `ShotAnimationSystem.js` guards `turnData.animations` inconsistently (guarded at 295/479/486,
     bare at 352/455/572/666). Sites 572/666 remain unguarded on the final_turn-skips-setup path.
   - Pre-existing; unrelated to the animation cleanup pass.

### Steal -> HCO setup: backend computes positioning the frontend no longer renders [CODE-CLEANUP] — **OPEN** (2026-09-15)

*Related to root cause #2 (the `apply_coords` antipattern) but is a separate dead-compute cleanup.*

- **Issue**: `resolve_half_court_offense_logic` (`BackEnd/engine/phase_resolution.py`) still emits `is_steal_hco_setup`, `ball_handler_hco_setup_*`, and `other_players_hco_setup_movements`. The frontend has removed `animateStealHCOSetup()` and stopped reading those fields. UESS has a replacement (`_append_post_steal_hco_transition` in `skeleton_step_emitter.py`), but the old role-field contract is unused.
- **Impact**: Low — backend is doing compute-but-unrendered work. No visible bug, just wasted computation and a misleading contract.
- **Action**: Remove the Steal → HCO setup positioning computation and its emitted fields from the backend resolver. Confirm no other consumer reads those fields first.
- **Priority**: Low (dead/unrendered compute, not causing bugs)

### Legacy steal-entry Fast Break dead code + unused `STEAL_ENTRY_*` constants [CODE-CLEANUP] — **OPEN** (2026-09-15)

- **Issue**: All steals are short-circuited to the UESS-migrated `after_steal` resolver early in `resolve_fast_break_logic` (~L1205), which makes the legacy steal-entry movement block later in the same function (~L1517–1541) unreachable dead code. The `STEAL_ENTRY_MOVE_*` / `STEAL_ENTRY_Y_*` constants that block relied on are now unused on the rendered path in both `BackEnd/constants/fast_break_constants.py` and `FrontEnd/static/js/phaser/constants/fastBreakConstants.js`.
- **Impact**: Low — unreachable code + orphaned constants. No runtime effect, just bloat/confusion for anyone reading the FB resolver.
- **Action**: Delete the unreachable steal-entry block in `resolve_fast_break_logic` and remove the unused `STEAL_ENTRY_*` constants from both the backend and frontend constants files. Verify nothing on the live `after_steal` path references those constants before removing.
- **Priority**: Low (dead code; tie in with the FB-coverage follow-up noted in the "Stale FB test suite" item above)

### Invalid State Transition Warning [CODE-CLEANUP] — **OPEN** (2026-09-15)

- **Issue**: State machine attempts no-op transition (HalfCourt -> HalfCourt)
- **Location**: `FrontEnd/static/js/phaser/animation/AnimationEngine.js` → `handleBaselineInbound()` still calls `safeTransition` unconditionally (tip path has an `is(HalfCourt)` guard; BIP does not)
- **Impact**: Low - harmless but indicates unnecessary `safeTransition()` call
- **Action**: Review `handleBaselineInbound()` to avoid calling `safeTransition()` when already in target state
- **Priority**: Low (code cleanup)

### Stale FB test suite — open follow-up [CODE-CLEANUP] — **PARTIAL** (2026-09-15)

Stale pre-refactor FB tests were deleted 6-12-26; suite is green. **2026-09-15:**
`test_after_steal_fast_break_stats.py` and `test_steal_fast_break_routing.py` now
exist. `test_fast_break_rr_triangle_updates.py` still covers RR/Triangle.
**Still thin:** the CR resolver path. Write those when FB work resumes.

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
reason. It paid off on 2026-09-08: its backend twin `[SHOT-NO-SCHEMA]` is what made the FLSS
stranded-skeleton defect countable (30 fires per 8 games, 5 of them rendering nothing at all),
and a `|| []` guard would have hidden exactly those 5. **Worth considering as its own work item:** an emitter-level counter for every
schema→legacy fallback, surfaced rather than swallowed, so the rate is visible instead of
inferred. Today a fallback is indistinguishable from normal operation until a user reports a
teleport.

---

## Phase 2 — within-step ball travel (scoped 2026-09-14, not started)

Founder's Mode moved to 1 Nov. Phases 2–4 move outcomes and must land before Jamie's
balance pass. Full diagnostic: [`bugs.md`](bugs.md) item 50. **No design and no code
in that entry — what exists, and what each application would take.**

The mechanism is already live: **1,938 within-step attached A→B transfers per 8
played games** (published 1,905). Payload is ``start.ball.owner_player_id=A``,
``end.ball.owner_player_id=B``, ``ball_motion_style="pass"``,
``ball_arrival_coord``. Writer: ``_walk_ball_owners`` + the HCO emit loop
(``skeleton_step_emitter.py:375``, ``:2242``, ``:2574``). Not ``BallInFlight``.

| application | n | cost | use the 1,905 as-is? |
|---|---|---|---|
| 3a HCT entry | published 23 / this-tree 27 → **CLOSED; 3 survivors parked** (bugs.md item 51) | **not a pass.** Consuming-worker PlayedState `PLAYED=1` (`_is_full_simulation` false), consume wrap, seeds 1–8, `0xB40000`: 27 → 3. Walk-up skipped when `prior_final_bh_id` is None. Do not author an entry pass. | no — inventing a handover is the same lie as `or play_bh` |
| 3b catch-and-shoot | published 21 / 1,018 / 929 | **cause `phase_resolution.py:8197-8198`.** **1,313 HCO micros = 21 hop + 1,292 clean.** Footing: `PLAYED=1`, seeds 1–8, `0xB40000`. Not the micro writer. | no — truncate discarded the receive; do not thread a new inbound owner in the micro |
| item 47 fumble handover | published 8 (10 this tree; 6 at ea2c382da) | **CLOSED — 0 hops both footings** (Played 70/0, wrap 84/0). Credit fix, not a pass. `PLAYED=1` / wrap `PLAYED=0`, seeds 1–8, `0xB40000`, consume wrap. | no |
| loose-ball trajectory | published 46.2% | **RETIRED.** That walk measured §8.1 working, not a missing trajectory. | no — parked ``coords``, no owners; do not author from 46.2% |

Item 47 is not a Phase 2 pass (closed by the TO-credit write; **0/0 both footings**).
3a is **closed** except 3 parked TIMEOUT hops (item 51). 3b's cause is the
shot-at-1 truncate at `:8197-8198`, not a catalogue gap. Loose is retired as
a Phase 2 size.
