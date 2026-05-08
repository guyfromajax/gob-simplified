# Fast Break Refactor

> **Status:** Phase 0 — discovery + scoping. No code changes yet. This doc is the alignment artifact; scope is finalized with the user before Phase 1 starts.
>
> **Predecessor:** [`Movement_Rate_Refactor.md`](Movement_Rate_Refactor.md) (✅ shipped May 2026). Patterns established there — AG curve, per-player `game_seconds`, dual-path helpers — are the template for this work.
>
> **Handoff context:** [`Fast_Break_Handoff.md`](Fast_Break_Handoff.md) — captures user-reported issues and prior-thread carry-over.

## Goal

Address two classes of issues in the Fast Break animation system:

1. **Advance triggers don't reliably take hold.** Phase boundaries inside fast-break sequences (outlet → BH cover-ground → shot, rim-runner sub-branches, defensive stop) sometimes hang or short-circuit. The user reports this is the more pressing of the two.
2. **Animation timing feels off.** Visual pacing during fast breaks doesn't match the rest of the engine after Movement Rate Refactor — durations are still distance/AG-pixel-based on the frontend (`getPlayerDuration`) rather than backend-authoritative `game_seconds × clockSecondMs` (the pattern that won for HCT/HCO/FCP).

Both stem from the same architectural gap: **fast break never adopted the timing-authority shift Phase 3/4 of Movement Rate Refactor delivered everywhere else**. The frontend choreographs durations locally; the backend doesn't stamp per-player `game_seconds` into the animation payload (except for `apply_fast_break_cg_time`'s scalar cover-ground time, which is a clock total, not per-player visuals).

The refactor's outcome: backend produces per-player `game_seconds` for every fast-break tween, frontend uses that as the authoritative tween duration (with AG-pixel fallback), and advance triggers are tightened so phase transitions are deterministic rather than ad-hoc.

---

## Current-state map

### Entry path

[`AnimationEngine.js:handleFastBreak`](FrontEnd/static/js/phaser/animation/AnimationEngine.js) → [`fastBreak.js:runFastBreakSequence`](FrontEnd/static/js/phaser/animation/fastBreak.js#L1721) (~370-line orchestrator).

`runFastBreakSequence` walks three sequential phases:

| Phase | Lines | Purpose |
|---|---|---|
| **State + telemetry init** | [1728–1768](FrontEnd/static/js/phaser/animation/fastBreak.js#L1728-L1768) | Stop active timeline, transition state machine into `FastBreak`/`FastBreakOutlet`, init `__fbTelemetry`, emit `fb:start` |
| **Phase 1 — entry** | [1773–1852](FrontEnd/static/js/phaser/animation/fastBreak.js#L1773-L1852) | One of: rim-runner burst / standard outlet / steal entry. Lead-in contract enforced. |
| **Phase 2 — resolution** | [1867–2042](FrontEnd/static/js/phaser/animation/fastBreak.js#L1867-L2042) | Routes by `phase2Kind` from [`classifyFastBreakPhase2`](FrontEnd/static/js/phaser/animation/fastBreak.js#L64) |
| **Cleanup + finalize** | [2069–2086](FrontEnd/static/js/phaser/animation/fastBreak.js#L2069-L2086) | Final contract check, `fb:end` event, telemetry flush |

### Phase 1 entry branches

| Branch | Gate (turnData field) | Frontend handler | Notes |
|---|---|---|---|
| Rim Runner burst | `roles.rim_runner_burst_phase` | [`animateRimRunnerBurstPhase:2095`](FrontEnd/static/js/phaser/animation/fastBreak.js#L2095) | RR sprint + secondary movers + outlet pass; produces `rrBurstResult` snapshot used by phase 2 |
| Standard outlet (Covert Release) | `roles.outlet_passer && roles.outlet_receiver` | [`animateOutletPhase:2252`](FrontEnd/static/js/phaser/animation/fastBreak.js#L2252) | Outlet receiver to target, pass animation, defender chase |
| Steal entry | `roles.is_steal_entry` (or absence of outlet roles) | [`animateStealEntry:2432`](FrontEnd/static/js/phaser/animation/fastBreak.js#L2432) | Stealer (BH) advance from steal pickup |

Lead-in contract (`enforceFbUnitContract`) fires after each entry branch with `unitId="fb.lead_in.from_hco_steal"` or `"fb.lead_in.from_dreb_release"`.

### Phase 2 routing — `classifyFastBreakPhase2`

| `phase2Kind` | Driver | Handler | Lines |
|---|---|---|---|
| `fast_break_shot` | `result_type ∈ {MAKE,MISS,BLOCK}` | Triangle lead-in (if setup) → [`animateFastBreakShotWithStopper:2555`](FrontEnd/static/js/phaser/animation/fastBreak.js#L2555) **or** [`animateFastBreakShot:2909`](FrontEnd/static/js/phaser/animation/fastBreak.js#L2909) | [1895–1915](FrontEnd/static/js/phaser/animation/fastBreak.js#L1895-L1915) |
| `fast_break_shot_foul` | `result_type==="CHARGE"` or blocking foul | Same shot path in foul-only mode | [1916–1932](FrontEnd/static/js/phaser/animation/fastBreak.js#L1916-L1932) |
| `rim_runner_steal` | `rim_runner_interception && STEAL` | [`animateRimRunnerInterception:1495`](FrontEnd/static/js/phaser/animation/fastBreak.js#L1495) | [1933–1953](FrontEnd/static/js/phaser/animation/fastBreak.js#L1933-L1953) |
| `rim_runner_bat_oob` | `rim_runner_bat_oob && DEAD BALL` | [`animateRimRunnerBatOob:1606`](FrontEnd/static/js/phaser/animation/fastBreak.js#L1606) | [1954–1967](FrontEnd/static/js/phaser/animation/fastBreak.js#L1954-L1967) |
| `rim_runner_hco_settle` | `DEFENSIVE_STOP` or `rim_runner_outlet_failed` | [`animateRimRunnerOutletDeniedBeat:1155`](FrontEnd/static/js/phaser/animation/fastBreak.js#L1155) **or** [`animateRimRunnerHoldUpLeadIn:1399`](FrontEnd/static/js/phaser/animation/fastBreak.js#L1399) → [`finalizeRimRunnerNonShotTurn:1006`](FrontEnd/static/js/phaser/animation/fastBreak.js#L1006) | [1968–2013](FrontEnd/static/js/phaser/animation/fastBreak.js#L1968-L2013) |
| `triangle_hco_settle` | Triangle + (DEFENSIVE_STOP or `triangle_enter_hco`) | [`animateTriangleHcoSettle:900`](FrontEnd/static/js/phaser/animation/fastBreak.js#L900) | [2014–2027](FrontEnd/static/js/phaser/animation/fastBreak.js#L2014-L2027) |
| *default* | anything else | [`animateDefensiveStop:3329`](FrontEnd/static/js/phaser/animation/fastBreak.js#L3329) | [2028–2042](FrontEnd/static/js/phaser/animation/fastBreak.js#L2028-L2042) |

Inline before Phase 2 routing: rim-runner lane pass via [`shouldAnimateRimRunnerLanePass:532`](FrontEnd/static/js/phaser/animation/fastBreak.js#L532) → [`animateRimRunnerLanePass:569`](FrontEnd/static/js/phaser/animation/fastBreak.js#L569). Triangle setup phase ([`animateTriangleSetupPhase:787`](FrontEnd/static/js/phaser/animation/fastBreak.js#L787)) runs in front of shot routing if `triangle_setup` payload present.

### Backend structure

[`phase_resolution.py:resolve_fast_break_logic:991`](BackEnd/engine/phase_resolution.py#L991) is the orchestrator. Two top-level paths:

1. **Rim Runner / Triangle** ([1040–1043](BackEnd/engine/phase_resolution.py#L1040-L1043)) — delegates to [`rim_runner_fast_break.py:resolve_rim_runner_fast_break:676`](BackEnd/engine/rim_runner_fast_break.py#L676). Internal sub-cases: outlet denied, burst phase, PG read, lane pass, hold-up, interception (3 tiers), bat OOB, plus triangle's 7 branches.
2. **Covert Release / Standard outlet / Steal entry** (rest of `resolve_fast_break_logic`) — DREB outlet path ([1045–1116](BackEnd/engine/phase_resolution.py#L1045-L1116)), steal-entry path ([1119–1139](BackEnd/engine/phase_resolution.py#L1119-L1139)), defender-ahead check ([1360–1468](BackEnd/engine/phase_resolution.py#L1360-L1468)), defensive-stop vs shot decision ([1504–1566](BackEnd/engine/phase_resolution.py#L1504-L1566)), shot resolution via `shot_manager` ([1677–1776](BackEnd/engine/phase_resolution.py#L1677-L1776)).

Animation payload built by [`animator.py:capture_fast_break_animation`](BackEnd/models/animator.py) — produces `start`/`end` grid coords + a 2-step `movement` array with hardcoded `timestamp: 0` and `timestamp: 800`. **No per-player `game_seconds`. No `bringup_per_player_seconds`-style dict. No AG-aware timing in the payload.**

Backend constant: 800 ms duration is the only timing field surfaced ([animator.py:103, 142–144](BackEnd/models/animator.py)).

### Timing computation today

**Backend authority — clock only:**
- [`apply_fast_break_cg_time`](BackEnd/engine/phase_resolution.py#L918-L988) computes total `time_elapsed` for the turn using `calc_ag_segment_seconds(start, end, bh, "default")` per BH path segment (Phase 4b migration). Fast-break BH cover-ground time is correctly AG-driven on the clock side.
- This is the **only** AG-aware site in the fast-break backend.
- Outlet pass overhead: scalar `calc_pass_segment_seconds(passer, receiver)` ([978](BackEnd/engine/phase_resolution.py#L978)).
- Shot overhead: hardcoded `+1.0` second ([982](BackEnd/engine/phase_resolution.py#L982)).
- Final clamp to 30 seconds ([984–987](BackEnd/engine/phase_resolution.py#L984-L987)).

**Frontend authority — visuals:**
- Per-player tween durations come from [`getPlayerDuration(sprite, px, py, burst)`](FrontEnd/static/js/phaser/animation/turnAnimation.js) — distance ÷ AG-pixel-rate. **Distance-based, computed at the sprite, no backend input.**
- This means frontend visuals and backend `time_elapsed` are *not* synchronized by construction — they're independent calculations that happen to be calibrated to feel close.
- Hardcoded literals (sample, line numbers from current trace):
  - 50 ms post-pass ball-attachment delays (multiple sites: [1170, 1571, 1703, 2170–2176, 2370](FrontEnd/static/js/phaser/animation/fastBreak.js))
  - 60 ms rebound-monitor startup delay ([278](FrontEnd/static/js/phaser/animation/fastBreak.js#L278))
  - 40 ms rebound-monitor poll ([273](FrontEnd/static/js/phaser/animation/fastBreak.js#L273))
  - 450 ms rebound-monitor max ([270](FrontEnd/static/js/phaser/animation/fastBreak.js#L270))
  - 1000 ms outlet-denied / interception holds ([1290, 1596](FrontEnd/static/js/phaser/animation/fastBreak.js))
  - 650 ms bat-OOB hold ([1704](FrontEnd/static/js/phaser/animation/fastBreak.js#L1704))
  - 520 ms RR drift phase floor (`clampRrAgSharedPhaseDurationMs:920`)
  - 2500 ms default `awaitWithTimeout` if no label-specific config ([508](FrontEnd/static/js/phaser/animation/fastBreak.js#L508))
  - +2000 ms grace added to phase duration for some `awaitWithTimeout` calls ([1332, 1472](FrontEnd/static/js/phaser/animation/fastBreak.js))

### Advance triggers (the user's main complaint)

Phase advancement is driven by `await` boundaries on tween / pass promises. Most have no explicit timeout; some use [`awaitWithTimeout:507`](FrontEnd/static/js/phaser/animation/fastBreak.js#L507) which returns a boolean (`true`=resolved, `false`=timed out).

**Sites where the timeout boolean is computed but not branched on** (continues silently regardless of outcome):
- [`animateRimRunnerOutletDeniedBeat:1331-1333`](FrontEnd/static/js/phaser/animation/fastBreak.js#L1331-L1333) — receiver settle; if timeout, fallthrough into drift phase with potentially-still-animating sprite
- [`animateRimRunnerHoldUpLeadIn:1470-1473`](FrontEnd/static/js/phaser/animation/fastBreak.js#L1470-L1473) — BH settle; same pattern

**Sites that `await` raw promises with no timeout at all:**
- [`animateRimRunnerBurstPhase:2141`](FrontEnd/static/js/phaser/animation/fastBreak.js#L2141) — `await receiverPromise` (only the receiver; secondary movers are awaited later at [2210](FrontEnd/static/js/phaser/animation/fastBreak.js#L2210))
- Shot phases — `await shooterPromise` in [`animateFastBreakShot`](FrontEnd/static/js/phaser/animation/fastBreak.js#L2909) and `animateFastBreakShotWithStopper`
- [`animateDefensiveStop:3470`](FrontEnd/static/js/phaser/animation/fastBreak.js#L3470) — `await Promise.all(promises)` for BH + stopper + get-back + rebounders

**Other early-exit risks worth investigating:**
- Several sub-flows return early on missing sprites without queueing a fallback resolved promise ([2102–2104, 2258, 2915, 3001–3009](FrontEnd/static/js/phaser/animation/fastBreak.js)). If the parent uses `Promise.all`, missing entries skew completion timing.
- [`finalizeRimRunnerNonShotTurn:1030`](FrontEnd/static/js/phaser/animation/fastBreak.js#L1030) calls `scene.startNextHalfCourtOffense()` synchronously in a fire-and-forget pattern — if HCO setup depends on FB cleanup, the handoff is implicit.
- The 50 ms hardcoded ball-reattachment delays after pass animation ([2170, 1571, 1170](FrontEnd/static/js/phaser/animation/fastBreak.js)) — if `runPass` resolves before the ball is actually back in the receiver's hand, ownership verification can fail intermittently.

### Telemetry

[`__fbTelemetry`](FrontEnd/static/js/phaser/animation/fastBreak.js#L121) is initialized at phase 2 entry. Counters: `fbFallbackCount`, `fbRequiredRoleCount`, `fbClampCount`, `fbSnapCount`. Events: `fb_contract_missing_endpoint`, `fb_fallback_used`, `fb_clamp_destination`, `fb_transition_snap`, `fb_phase_clock_overrun`. Configurable mode via `UESS_FB_CONTRACT_MODE` (`off`/`observe`/`warn`/`throw`).

Strict-branch enforcement currently scoped to: `rr_lane_shot`, `rr_outlet_denied`, `rr_hold_up`, `generic_fb_shot_stop` ([180](FrontEnd/static/js/phaser/animation/fastBreak.js#L180)).

---

## Diagnosis (May 2026)

The user reports three concrete visual symptoms:

1. **Players animate all the way to far-end destinations (e.g., the OOB clamp on the horizontal sides of the court).** Backend payload destinations *are intentionally* far-end in many cases — the bug is that the player reaches them. An advance trigger should fire long before, stopping or redirecting the tween.
2. **Triangle: trailing teammates surpass the outlet receiver after he receives the pass.** Receiver should be ahead of trailers (only RR going to low post and the corner-bound teammate on the BH's vertical half should lead him). Refined observation: the BH/receiver actually *holds his position* while others move — so trailers don't just out-pace him, they advance while he's static. Two candidates for root cause (TBD when Phase 4f lands): (a) Triangle setup phase has an intentional BH-only hold step that needs to be removed/rebalanced, or (b) the BH has no advance tween in Triangle setup and his movement is deferred to decision lead-in or shot.
3. **Covert release defensive stop: a single offensive teammate of the BH animates all the way to the offensive basket while the other 9 players stop earlier.** Same root pattern as #1 — that teammate's burst-phase tween targets a near-rim destination and is not stopped when the defensive stop resolves.

Root pattern across all three: **`runFastBreakSequence` lacks a "critical event fires → stop parallel tweens → advance" convention.** Today's pattern is dominated by `await Promise.all(...)` over every spawned tween — phases either wait for the slowest player to naturally reach a far destination, or advance and leave the parallel tweens running. The exception is [`startRebounderCatchMonitor:257`](FrontEnd/static/js/phaser/animation/fastBreak.js#L257), which *does* explicitly call `tween.stop()` on a poll-and-stop pattern when the rebound event fires — exactly the right shape, but it's the only such site.

## Bug hypotheses (to validate in Phase 1)

These are specific code-level manifestations of the root pattern. Ranked by likelihood. Phase 1 instrumentation will confirm which are real.

1. **No `tween.stop()` discipline at phase boundaries.** Outside of `startRebounderCatchMonitor`, no fast-break phase explicitly stops parallel tweens when its critical event fires. Examples to audit:
   - [`animateRimRunnerBurstPhase:2210`](FrontEnd/static/js/phaser/animation/fastBreak.js#L2210) `await Promise.all(secondary)` — secondaries gate the phase
   - [`animateOutletPhase`](FrontEnd/static/js/phaser/animation/fastBreak.js#L2252) — defenders chasing during the outlet pass; what stops them when receiver gets the ball?
   - [`animateDefensiveStop:3470`](FrontEnd/static/js/phaser/animation/fastBreak.js#L3470) `await Promise.all(promises)` — every parallel tween must complete naturally
   - [`moveOtherPlayersToStandardPositions`](FrontEnd/static/js/phaser/animation/fastBreak.js#L3905) — get-back tweens have no stop signal
   - Burst-phase teammates whose tweens target near-rim spots are *not stopped* when the result resolves to defensive stop. **This is the prime suspect for symptom #3.**

2. **`awaitWithTimeout` boolean ignored** at [1331](FrontEnd/static/js/phaser/animation/fastBreak.js#L1331-L1333) and [1470](FrontEnd/static/js/phaser/animation/fastBreak.js#L1470-L1473). When the timeout fires, the function returns `false` and the caller continues as if success. Independent confirmed bug; mechanical fix.

3. **Raw `await` on tween promises with no timeout** in shot phases ([2141, 3032](FrontEnd/static/js/phaser/animation/fastBreak.js)) and defensive stop. Phaser tweens *can* stall (sprite removed, scene paused, tab backgrounded) and silently never resolve. Without timeout + cleanup, the phase blocks indefinitely.

4. **Triangle trailer sequencing.** Receiver and trailers tween in parallel from the same moment. With distance-based `getPlayerDuration`, faster trailers with shorter distances finish first. Two fixes possible: (a) gate trailer start on the "receiver has the ball" event, or (b) pace via backend `game_seconds` calibrated so receiver arrives first. **Prime suspect for symptom #2.**

5. **Frontend visual / backend clock divergence** (separate from symptoms above; tied to "timing feels off"). Frontend computes durations distance-based via `getPlayerDuration`; backend's `apply_fast_break_cg_time` is AG-driven on the clock. After Movement Rate Refactor, this is the only remaining engine flow with this divergence.

6. **Hardcoded post-pass ball-reattachment delays (50 ms).** If pass tween runs longer than expected, 50 ms isn't enough buffer for `BallController` to settle. The verify-and-retry block at [2189–2206](FrontEnd/static/js/phaser/animation/fastBreak.js#L2189-L2206) papers over it — a sign the timing is brittle.

7. **`finalizeRimRunnerNonShotTurn` HCO handoff race.** Calls `scene.startNextHalfCourtOffense()` after a 1000 ms hold without verifying state machine readiness ([1030](FrontEnd/static/js/phaser/animation/fastBreak.js#L1030)).

8. **Stale `player.coords` in backend fast-break code.** Carried from prior thread; same staleness pattern that affected HCT pre-fix. Likely contributes to coordinate computation errors but not the primary cause of any of the three reported symptoms.

---

## Pattern transfer from Movement Rate Refactor

The shipped patterns from the prior refactor we'll re-apply:

- **AG curve + archetype multipliers** — [`calc_ag_segment_seconds(start, end, player, archetype)`](BackEnd/utils/shared.py) is ready to call wherever a `Player` is in scope.
- **Per-player `game_seconds` on waypoints** — [`dynamic_hct.py`](BackEnd/engine/dynamic_hct.py) stamps `game_seconds` on every waypoint; frontend [`playTurnAnimation`](FrontEnd/static/js/phaser/animation/turnAnimation.js) consumes `× clockSecondMs` as authoritative tween duration. Same pattern works for fast-break waypoints.
- **Per-turn `bringup_per_player_seconds`-style dict** — for setup-tween-style movements (e.g., the parallel non-BH movers in burst phase), a `{playerId: game_seconds}` map propagated through the payload mirrors HCO bring-up.
- **Dual-path safety** — every helper supports `player=None` legacy fallback. Lets us migrate one site at a time without breaking unmigrated callers. AG=50 invariant means an average lineup behaves identically to today.
- **Incremental phasing** — helper-only Phase 1 → wire one site at a time → prototype-test between → retire legacy paths last.

---

## Proposed phased plan

Each phase is one PR, mergeable independently. Order is biased toward **diagnosing-before-fixing** so we don't ship guesses.

### Phase 0 — Discovery + scoping (this doc)
**Status:** in progress (this PR is Phase 0).
**Output:** this document.
**Risk:** zero (no code).

### Phase 1 — Instrumentation (deferred; fallback if Phase 2 surprises us)
**Status:** deferred. Diagnosis is concrete enough to skip straight to Phase 2. If Phase 2 work surfaces unknowns or unexplained regressions, fall back to this phase to add targeted logging.

If we do come back to it, the scope would be: log critical-advance events and parallel-tween cleanup status per phase, modify [`awaitWithTimeout`](FrontEnd/static/js/phaser/animation/fastBreak.js#L507) to always log on timeout, and run a prototype session to collect a transcript. Bump `UESS_FB_CONTRACT_MODE` to `warn` during the diagnosis window.

### Phase 2 — Critical-event advance pattern (the centerpiece)
**Goal:** rework `runFastBreakSequence`'s advance pattern so phases gate on a *critical event*, not on `Promise.all` over every spawned tween. This is what fixes symptoms #1 and #3.

The pattern (template: [`startRebounderCatchMonitor:257`](FrontEnd/static/js/phaser/animation/fastBreak.js#L257), generalized):
- Each phase identifies its **critical advance event** — the simulated game event that ends the phase (pass received / shot released / defensive stop locked / interception / bat OOB / etc.).
- Phase orchestrator awaits the critical event with a budget (`Promise.race([criticalEvent, awaitWithTimeout(criticalEvent, budget)])`).
- On either path (event fires or timeout), the orchestrator **explicitly stops all parallel tweens** spawned within the phase before returning. Sprites hold at their interrupted positions.
- Next phase starts; if any sprite needs to redirect, the next phase spawns a fresh tween for it.

**Sub-PRs:**

| Sub-PR | Scope | Risk |
|---|---|---|
| **2a — Plumbing** | Add `UESS_FB_CRITICAL_EVENT_PATTERN` global flag (default off) using the existing [`getFbContractGlobalScope`](FrontEnd/static/js/phaser/animation/fastBreak.js#L143) pattern. Fix `awaitWithTimeout` return-ignored at [1331](FrontEnd/static/js/phaser/animation/fastBreak.js#L1331-L1333) and [1470](FrontEnd/static/js/phaser/animation/fastBreak.js#L1470-L1473) — branch on return, emit telemetry counter + console warning on timeout. No tween-cleanup behavior change yet. | Very low |
| **2b — Burst phase** | Convert [`animateRimRunnerBurstPhase`](FrontEnd/static/js/phaser/animation/fastBreak.js#L2095) from `await Promise.all(secondary)` ([2210](FrontEnd/static/js/phaser/animation/fastBreak.js#L2210)) to critical-event-then-stop pattern, gated on the new flag. Validates the pattern on the smallest meaningful sub-flow. Eyeball-test in prototype. | Medium — pattern validation |
| **2c — Defensive stop** | Apply pattern to [`animateDefensiveStop`](FrontEnd/static/js/phaser/animation/fastBreak.js#L3329) and [`moveOtherPlayersToStandardPositions`](FrontEnd/static/js/phaser/animation/fastBreak.js#L3905). Symptom #3 should resolve here. | Medium |
| **2d — Remaining sub-flows** | Outlet, shot phases, lane pass, interception, bat OOB, steal entry, RR hold-up / outlet-denied. Pattern is mechanical at this point. | Low |
| **2e step 1 — Flip flag default to on** | `isCriticalEventPatternEnabled()` defaults to `true`. Explicit `window.UESS_FB_CRITICAL_EVENT_PATTERN = false` (or `"off"`) acts as kill switch — restores legacy `await Promise.all` paths if a regression surfaces. | Low |
| **2e step 2 — Retire flag + legacy paths** | After a few days of stable dev use on the flag-on default. Delete `isCriticalEventPatternEnabled` calls, remove the legacy `await Promise.all` branches, delete the helper function. Flag becomes a no-op. | Low |

**Risk:** medium-high overall. Largest single behavior shift in the refactor. Mitigated by the flag (toggle off if regressions surface) and by 2b validating the pattern on a single sub-flow before fanning out.

### Phase 3 — Backend per-player `game_seconds` + `sprint` archetype
**Goal:** make the backend the timing authority for fast-break visuals, mirroring HCT/HCO. Add a new AG archetype for max-effort movement.
- **New archetype.** Add `archetype="sprint"` to [`calc_ag_segment_seconds`](BackEnd/utils/shared.py) and a `SPRINT_MULTIPLIER` constant in [`BackEnd/constants/__init__.py`](BackEnd/constants/__init__.py). Multiplier > 1.0 (faster than free-running default); exact value calibrated so AG=50 produces a visually-comparable RR burst duration to today. Used for: rim-runner burst, BH cover-ground after open court, fast-break shot motion. Default archetype stays for outlet receiver settling, get-back defenders, etc. (lower urgency).
- Extend [`capture_fast_break_animation`](BackEnd/models/animator.py) to stamp `game_seconds` on each `movement` waypoint via `calc_ag_segment_seconds(start, end, player, archetype=...)` with the appropriate archetype per role. AG=50 invariant: average-AG players match today's `getPlayerDuration` calibration → visually identical for AG=50 lineups.
- For parallel-mover patterns (burst secondaries, get-back defenders, rebounders), produce a `fast_break_per_player_seconds: {playerId: game_seconds}` dict on the payload (mirrors `bringup_per_player_seconds` pattern from HCO).
- Frontend consumption (analogous to HCT's [`playTurnAnimation`](FrontEnd/static/js/phaser/animation/turnAnimation.js) step loop): every fast-break tween prefers `waypoint.game_seconds × clockSecondMs` if present, falls back to `getPlayerDuration` if absent. Ship as dual-path so unmigrated payload fields keep working.
- **Risk:** medium. AG=50 invariant is the safety net — verify with a Python smoke test before browser-testing. Fast/slow players will visibly differ from current behavior; that's expected and matches HCT/HCO/FCP. `sprint` calibration may need a follow-up tweak after eyeball testing.

### Phase 4 — Per-sub-flow migration: timing + sequencing
**Goal:** wire each sub-flow's frontend tweens to consume backend `game_seconds`, AND audit the *start order* of tweens within the sub-flow. One sub-flow per PR.

Each sub-flow PR does two things:
- **Duration:** swap `getPlayerDuration` for `waypoint.game_seconds × clockSecondMs` (with the AG-pixel fallback). Dual-path safe.
- **Sequencing:** audit when each tween starts within the sub-flow. Are tweens that should be sequential currently parallel? If yes, gate the later tween on the earlier event (or on a backend-stamped `start_offset_seconds`).

Sub-flow queue:
- 4a — Outlet phase ([`animateOutletPhase`](FrontEnd/static/js/phaser/animation/fastBreak.js#L2252))
- 4b — Rim-runner burst ([`animateRimRunnerBurstPhase`](FrontEnd/static/js/phaser/animation/fastBreak.js#L2095))
- 4c — Lane pass / interception / bat-OOB
- 4d — Shot phases ([`animateFastBreakShot`](FrontEnd/static/js/phaser/animation/fastBreak.js#L2909), `animateFastBreakShotWithStopper`)
- 4e — Defensive stop ([`animateDefensiveStop`](FrontEnd/static/js/phaser/animation/fastBreak.js#L3329))
- 4f — **Triangle setup / decision / hco-settle.** This sub-flow carries the trailer-sequencing fix for symptom #2 — receiver gates trailer start, or backend stamps a `start_offset_seconds` per trailer so the receiver always leads.
- 4g — Steal entry

**Triangle ordering switch.** Default ordering above places Triangle as 4f. If Phase 1 evidence shows the trailer-sequencing bug (symptom #2) is the most visible/frequent issue, promote Triangle to 4a or 4b. Decision point: end of Phase 1.

**Risk per sub-PR:** low. AG=50 invariant + dual-path means each PR is reversible. Sequencing audit is the main risk surface — generous testing in prototype between sub-PRs.

### Phase 5 — `player.coords` staleness audit
**Goal:** apply the HCT fix pattern (`_hct_setup_start_coords` reads from `HCT_SETUP_POSITIONS`) to every fast-break `player.coords` read.
- Inventory `player.coords` reads in [`phase_resolution.py:resolve_fast_break_logic`](BackEnd/engine/phase_resolution.py#L991) and [`rim_runner_fast_break.py`](BackEnd/engine/rim_runner_fast_break.py).
- For each, identify the authoritative position source for that flow's entry state (post-BIP, post-DREB, post-steal-entry).
- Read directly from the source, not `player.coords`.
- **Risk:** low. Coord computations only; no animation logic touched.

### Phase 6 — Retire hardcoded delays
**Goal:** kill or justify each hardcoded ms value.
- Each of the 50 ms / 1000 ms / 650 ms / 60 ms / 40 ms / 450 ms / 2500 ms / 2000 ms literals: either move to a named constant with a `# Why:` comment, or convert to a `game_seconds × clockSecondMs` value driven by the backend, or delete if Phases 2–5 made it redundant.
- Outcome: one place to read fast-break timing rules.
**Risk:** low.

### Phase 7 — Decision: contract/tolerance system simplification (carried over)
The Phase 3 leftover from Movement Rate Refactor: [`turnAnimation.js:4900-5075`](FrontEnd/static/js/phaser/animation/turnAnimation.js#L4900-L5075) tolerance system is ~125 lines of overhead per step that no longer detects anything (since clock and visual are synced by construction post-refactor). Decision point: is the equivalent fast-break contract system ([`enforceFbContractGuardrail`, `enforceFbUnitContract`](FrontEnd/static/js/phaser/animation/fastBreak.js)) similarly redundant once Phase 3+4 ship? Likely yes. Optional cleanup; defer until the rest is stable.

---

## Open questions — resolved

1. **Scope: full timing-authority shift + bug fix.** Phases 0 → 6 in scope; Phase 7 (contract simplification) stays optional. Bug fixes (Phase 2) and visual-authority migration (Phase 3+4) are both in plan.
2. **Phase 1 deferred — go straight to Phase 2.** Diagnosis is concrete enough that pre-emptive instrumentation would be overhead. Phase 2 ships behind a feature flag (`UESS_FB_CRITICAL_EVENT_PATTERN`); if regressions surface we either toggle the flag off or fall back to the Phase 1 logging plan to investigate.
3. **Triangle stays as Phase 4f by default; switch flippable after Phase 1.** Treating Triangle separately is unnecessary for the bug fix — Phase 2's advance-trigger tightening is play-agnostic and fixes Triangle alongside everything else. The only Triangle-specific question is *when* its visual migration ships in Phase 4. If Phase 1 evidence shows Triangle is the worst visual offender, promote to 4a/4b.
4. **`UESS_FB_CONTRACT_MODE=warn` for the Phase 1 dev session.** Dial to `observe` once Phase 2 ships and the system is stable.
5. **Sprint archetype added in Phase 3.** New `archetype="sprint"` in [`calc_ag_segment_seconds`](BackEnd/utils/shared.py) with `SPRINT_MULTIPLIER > 1.0`, used for max-effort movement (RR burst, BH cover-ground in open court, FB shot motion). Default archetype stays for lower-urgency fast-break movement (outlet receiver settle, get-back defenders).

---

## Rollback strategy

Tag `develop` HEAD as `pre-fastbreak-refactor` once the user pushes any in-flight changes:

```bash
# After the user's checkpoint commit lands on develop:
git tag pre-fastbreak-refactor <sha>
git push --tags
```

Each phase ships as its own PR. To roll back any phase:

```bash
git revert <phase-pr-merge-sha>
```

Whole-refactor rollback (only with explicit user approval):

```bash
git reset --hard pre-fastbreak-refactor
git push --force-with-lease
```

Dual-path helpers + AG=50 invariant mean the only true regression risk is Phase 2 (advance-trigger tightening). All other phases are visually-identical-for-average-lineups by construction.

---

## Cross-references

- [`Fast_Break_Handoff.md`](Fast_Break_Handoff.md) — prior-thread handoff context (May 2026).
- [`Movement_Rate_Refactor.md`](Movement_Rate_Refactor.md) — predecessor refactor, source of patterns reused here.
- [`Animation_Cleanup.md`](Animation_Cleanup.md) — broader animation tech-debt queue.
- [`05_Animation_System/Core_Animation_System.md`](../05_Animation_System/Core_Animation_System.md) — tween-duration-authority section (added during Movement Rate Refactor).
- [`05_Animation_System/AG_Implementation.md`](../05_Animation_System/AG_Implementation.md) — AG curve canon (v2).
- [`05_Animation_System/Transition_Systems.md`](../05_Animation_System/Transition_Systems.md) — hold/delay reference.
- Frontend: [`fastBreak.js`](../../FrontEnd/static/js/phaser/animation/fastBreak.js), [`AnimationEngine.js`](../../FrontEnd/static/js/phaser/animation/AnimationEngine.js), [`turnAnimation.js`](../../FrontEnd/static/js/phaser/animation/turnAnimation.js).
- Backend: [`phase_resolution.py`](../../BackEnd/engine/phase_resolution.py), [`rim_runner_fast_break.py`](../../BackEnd/engine/rim_runner_fast_break.py), [`animator.py`](../../BackEnd/models/animator.py), [`shot_manager.py`](../../BackEnd/models/shot_manager.py), [`shared.py`](../../BackEnd/utils/shared.py), [`fast_break_constants.py`](../../BackEnd/constants/fast_break_constants.py).
