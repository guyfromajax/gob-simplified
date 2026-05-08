# Animation System Cleanup

## Context

The frontend animation system has accumulated multiple layered/competing subsystems over several refactor passes. Today's HCT debugging surfaced a clear example: BIP setup tween done in `handleBaselineInbound` was being silently overridden by legacy `runInboundSetup`'s own player-positioning logic. The competing systems are a real source of bugs and onboarding friction, but the system mostly works in production — so the cleanup approach is **incremental and risk-graded**, not rip-and-replace.

Animation lives primarily in `FrontEnd/static/js/phaser/animation/`. The two largest files:
- `turnAnimation.js` (~5750 lines after this session's cleanup) — main step-loop animator + legacy helpers (`runInboundSetup`, `runSideInboundSetup`, `runDefensiveReboundSetup`, `runOffensiveReboundKickoutSetup`)
- `AnimationEngine.js` (~1620 lines) — top-level handler dispatch (`handleBaselineInbound`, `handleSideInbound`, `handleSteal`, `handleFastBreak`, `handleDefault`, etc.)

Plus subsystem classes (`PassAnimationSystem`, `ShotAnimationSystem`, `ReboundAnimationSystem`, `FreeThrowAnimationSystem`, `HCOAnimationSystem`), the ball-attachment layer (`BallController`, `BallControllerAdapter`, plus older `attachBallToPlayer` / `setBallHolderId` / `currentBallOwnerRef` paths), and the pressure-rework phasing system (`phase1_scaffold` / `phase2_split` / `phase3_lead_in`).

## Completed (2026-05-08 session)

### Tier 1 — Pure dead-code/comment cleanup
- Removed `// ✅ REMOVED:` and stale `// ✅ Phase X.Y:` status-marker comments from `turnAnimation.js` and `AnimationEngine.js`
- Removed `if (false) console.log(...)` blocks from `AnimationEngine.js`
- Removed multi-line `// COMMENTED OUT:` blocks of disabled `console.log` / `animationDebugLog` calls in `turnAnimation.js`
- Net: ~77 lines removed, runtime behavior verifiably unchanged

### Tier 2 (partial) — Unused imports in `turnAnimation.js`
- Removed 8 unused symbols across 6 import declarations (verified via per-symbol grep — symbol appeared only on its import line, never re-exported, no dynamic access)
- Imports retired: `PASS_DEBUG`, `computeFastBreakOutletTarget`, `isAnimationDebugEnabled`, `getDebugTransitions`, `createTransitionGuard`, `transitionWithDebug`, the entire `timeoutButtonManager.js` import block (4 symbols), `animateBallToPosition`

### One scope-creep removal noted for transparency
- An `if (cond) { /* only comments */ }` block in `turnAnimation.js` was removed alongside its inner comments. The removal is runtime-safe (pure boolean condition, empty body) but went slightly beyond the strict comment-only bar. Side effect: `hasPutbackMake` and `hasPendingFreeThrow` are now unread declarations (RHS expressions still evaluate, results discarded — harmless).

## Pending diagnostic-log removal

These were added during HCT debugging and the bug is now confirmed fixed. Should come down on the next pass:
- `🔍 [HCT-DIAG]` block in `BackEnd/engine/dynamic_hct.py` (gated on `is_user_facing_game`, prints setup vs stale player.coords for each offense position at HCT entry)
- `🔍 [HCT-FE-DIAG]` block in `FrontEnd/static/js/phaser/animation/turnAnimation.js` (browser console, prints sprite px vs expected px per player at HCT step 1)

## Remaining low-risk cleanup tiers

### Tier 2 continued — Unused imports in other animation files
**Risk:** ~99% confidence with per-symbol grep verification. Same process as the `turnAnimation.js` pass.

**Scope:** `AnimationEngine.js` plus any other files in `FrontEnd/static/js/phaser/animation/` flagged by the IDE. Likely a similar small pile per file.

**Process:**
1. Open file, list IDE-flagged "declared but never read" hints for imports
2. Per symbol: `grep -n "<symbol>" <file>` — confirm only on import line
3. `grep -rn "<symbol>" .` to confirm not re-exported through this file via `export { ... }`
4. Delete only after both checks pass; report ambiguous cases

### Tier 3 — Unused locals and unread function params
**Risk:** ~98% with grep + scope-walk verification. Slightly higher than imports because locals' RHS expressions may have side effects (rare in this codebase but possible).

**Currently flagged in `turnAnimation.js`:**
- `currentGrid` (line ~471)
- `getBallDuration` (line ~522)
- `delayMs` (line ~530)
- `getStepBallHandlerId` (line ~539)
- `stepDurationMs` (line ~589)
- `ballController` (line ~3405)
- `defensivePromiseArray` (line ~4917)
- `getBallHandlerIdFromTurn` (line ~5335)
- `hasPutbackMake`, `hasPendingFreeThrow` (lines ~5366, ~5385 — orphaned by Tier 1's if-block removal)
- `pos` (line ~5716)
- Function params: `turnIndex`, `onUpdate` on `playTurnAnimation` (line ~3272)

**Process per item:**
1. Read the declaration's RHS — if it's a property access, array literal, or pure function call (no side effects), safe.
2. If RHS calls a method that *could* have side effects (`new X()`, `.subscribe()`, etc.), trace it before removing.
3. For unused function params: confirm no `arguments` usage inside the function and no callers passing positionally with expectations.

### Tier 4 — "Unreachable code" hint at `turnAnimation.js:5497`
**Risk:** Cannot be cleared without real tracing. TS flags this statically but the upstream condition may be toggled by a runtime flag, env var, or dynamic dispatch.

**Process:** Read ~30 lines of context around line 5497, walk the call sites of the enclosing function, confirm no caller path can reach the unreachable block. If confirmed dead, remove. If ambiguous, leave with a comment explaining.

### Tier 5 — Stale phase / status comments
**Risk:** Low for runtime, medium for losing context. Many `// ✅ PHASE 2.1:`, `// ✅ PHASE 2.6:`, `// ✅ SS&S:` comments are next to load-bearing code and explain *why* something is the way it is. Need case-by-case judgment.

**Process:** Don't do these in a sweep. Address individually when touching the surrounding code for other reasons.

## Major projects (need structured time, not "between bugs")

These are the real consolidations that would meaningfully simplify the system. Each needs: a clear before/after spec, a per-turn-type test matrix, and dedicated time without other work in flight.

### Project A — BIP→inbound→HCT consolidation (priority 1)
**The seam exposed by today's HCT bug.** Currently:
1. `handleBaselineInbound` does its own `Promise.all` over player tweens to authored spots
2. Then `passSystem.executeInboundSequence` calls legacy `runInboundSetup` which **kills those tweens** at line ~2799 and re-tweens players to its own destinations
3. `runInboundSetup` advances on a "SF and PG settled" trigger (`requiredPromises: [sfTween, pgTween]`); SG/PF/C are non-required and may be cut off mid-tween

**Goal:** Single tween system per BIP. `handleBaselineInbound` owns offense positioning; `runInboundSetup`'s setup-tween logic gets retired. The pass-and-ball-pickup logic from `runInboundSetup` extracted into a dedicated helper.

**Estimated:** 1-2 days. Touches HCO-after-BIP, FCP-after-BIP, HCT-after-BIP, plus side inbound (which uses `runSideInboundSetup`, similar structure).

**Test matrix:** HCO BIP, FCP BIP, HCT BIP, BIP-after-OREB, free-throw BIP, force-foul-after-BIP. Eyeball verify each.

### Project B — Ball-attachment API consolidation
Currently overlapping APIs: `BallController` (state machine), `attachBallToPlayer` (direct), `setBallHolderId` (simple ID tracker), `currentBallOwnerRef.value` (mutable ref). Each handler has to remember to update some subset.

**Goal:** Single API. `BallController` is the most modern; retire the others or make them thin wrappers.

**Estimated:** 1-2 days. Many call sites. Risk: shot animations, putbacks, fast breaks all interact with ball ownership in different ways.

### Project C — Pressure-rework phasing — complete or retire
The `phase1_scaffold` / `phase2_split` / `phase3_lead_in` system in `turnAnimation.js` (around lines 3600-3700) controls strict-mode behavior for FCP/HCT contracts. It's mid-migration with `pressureReworkPhase === "off"` as the production default.

**Goal:** Either finish the migration (move to `phase3_lead_in` permanently and retire the other branches) or abandon it (delete the phasing entirely). Don't leave it in limbo.

**Estimated:** 1 day to either complete or retire, plus regression testing.

### Project D — Splitting `turnAnimation.js`
At ~5750 lines, this file mixes step-loop animation, inbound setup helpers, defensive rebound setup, free-throw alignment, and various other helpers. Hard to navigate.

**Goal:** Split into `playTurnAnimation.js`, `inboundHelpers.js`, `reboundHelpers.js`, etc.

**Estimated:** 1 day, mostly mechanical. Best done *after* Project A so we're not splitting code that's about to be retired.

## Process and safety bar

The user's standing rule: very high confidence required for cleanup edits. Three certainty tiers used during today's work:

| Tier | Operation | Confidence | Verification |
|---|---|---|---|
| 1 | Remove pure comments / `if (false)` blocks | 1000% | None needed — comments don't execute |
| 2 | Remove unused imports | ~99% | Per-symbol grep; check re-export list |
| 3 | Remove unused locals / params | ~98% | Per-item RHS inspection + scope walk |
| 4 | Remove "unreachable" code | varies | Real trace required, case by case |

Anything below ~98% confidence: stop and report rather than guess.

## Useful cross-references
- `_documentation_master/projects/Dynamic_HCT_Turns.md` — the HCT spec and bug history that motivated today's session
- `BackEnd/engine/dynamic_hct.py` — the new dynamic-HCT engine that bypasses legacy MongoDB skeletons
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` — the main animation file
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` — handler dispatch
- `FrontEnd/static/js/phaser/animation/PassAnimationSystem.js` — pass system (delegates to legacy `runInboundSetup` for inbound passes)
