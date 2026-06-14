# UESS Backlog (legacy audit)

> **Archived May 2026** from `projects/UESS_Legacy_Audit.md`. This file is the single source of truth for remediation items and their statuses; [`UESS_System.md`](../00_General_Systems/UESS_System.md) §12 points here. It retains the full violation catalog and file:line citations.

> **Status update (2026-06-12)** — remediation items shipped since the audit (line numbers in the catalog below have drifted; treat citations as point-in-time):
> - **Item 1 (§8.1 step-chain) — DONE.** Skeleton loop now seeds step N+1 `start.coords` from step N `end.coords` (`{**anim_start, **prior_end}` merge; code comment cites UESS §8.1).
> - **Item 2 (Handoff `_HCO_LANE_DRIFT_SPOTS` mismatch) — DONE.** Handoff drifts non-key players to their actual `setup_coords` when provided; random lane spots are fallback-only.
> - **Item 3 (cluster A announcements) — largely done.** DREB emitter now stamps announcements; `runShotAttempt`'s `schema_rendered_arc` short-circuit is now the *correct* path (step-level cues fire both SFX), no longer a gap.
> - **Item 4 (FB schema post-shot sub-steps) — DONE.** RR / Triangle / CR route MAKE/MISS/BLOCK through skeleton's `_build_post_shot_sub_steps`.
> - **Item 6 — partial.** FT make-hold now uses the `make_hold` `fixed_duration` shape (decision 5).
> - **Item 11 (After-Steal FB migration) — DONE (May 2026).** New resolver `after_steal_fast_break.py` + emitter `after_steal_fast_break_step_emitter.py`; schema steps + shared post-shot chain. §2.7 / §3.2 After-Steal rows below are obsolete.
> - **Still open:** 5 (backend visual clamping), 7 (`apply_coords_from_animations_list` mid-resolution calls — now 12 sites in phase_resolution + 6 in rim_runner), 8 (clock-authority ordering bug), 9 (`shot_state_snapshot` — still zero grep hits), 10 (Opening Tip emitter — not built), 12 (remaining embedded-DREB paths), 13 (FE pure-renderer cleanup), 14 (ownership fields — still zero grep hits), 15 (static HCT removal — callers still live in phase_resolution), 16 (dead FE code), 17 (UESS §2 doc updates).

Read-only audit of the UESS (Universal End-State Sync) migration. No code edits. All findings cited file:line.

References: [`UESS_System.md`](../00_General_Systems/UESS_System.md), [`Step_By_Step_System.md`](../00_General_Systems/Step_By_Step_System.md).

---

## 1. Executive summary

**State of the migration: load-bearing legacy, two unbuilt §7/§6 contracts, FE is far from a pure renderer.**

Five themes dominate. Each generates a cluster of bugs.

1. **§7 `shot_state_snapshot` is entirely unimplemented.** Grep returns zero hits BE-wide and FE-wide. No `SHOT_COORD_DEBUG`/`NO_DEFENDER_SHOT` emissions either. `ShotManager.resolve_shot` re-derives positioning per branch from live `roles`/`shooter.coords`/`def_lineup` instead of from one snapshot. The audit-only `position_snapshots` ledger is a different shape, built by callers, never consumed by `resolve_shot`.

2. **§6 `ownership_at_turn_start` / `ownership_commit_event` are also unimplemented.** Zero grep hits for either field name. The code instead stamps a differently-named `uess_ownership_contract` blob — and only on turns that have `steps[]` + `ball_owner_by_step`. BIP, SIP, FT, DREB, OREB, Opening Tip, Timeout, side-inbound, force-foul all skip it.

3. **FE is not a pure renderer.** ~46 FE violations: BallController is the FE-side ownership authority (UESS §6 commit events never consumed in FE); AnimationRouter runs its own clock tween + decides when to pause/resume; ShotAnimationSystem/ballManager/fastBreak/turnAnimation/HCOAnimationSystem fabricate rebounder/release/getback positions with `Phaser.Math.Between`/`Math.random` when backend payload is sparse. Schema-path `runShotAttempt` still picks ball end coord based on `result === "MAKE"`.

4. **Clock authority is two-layered with a subtle ordering bug.** Ledger derivation IS wired in `_attach_clock_contract` (turn_manager.py:189-291) and overwrites `time_elapsed` correctly. But ~20 legacy sites still write `time_elapsed` first (via `calc_skeleton_step_timing_contract`, `apply_fast_break_cg_time`, the FCP/HCO/OREB schema-game-burn realignment), and `_compute_real_time_elapsed_ms` consumes `result["time_elapsed"]` BEFORE the ledger overwrite — so FE wall-clock duration uses the pre-ledger value. `dynamic_hct_step_emitter.py:386-388` is the cleanest §5.4 violation: emitter literally sums step times into `turn_result["time_elapsed"]`.

5. **Skeleton emitter does not honor §8.1 step-chain coords.** `skeleton_step_emitter.build_skeleton_animation_steps` reads each step's `start.coords` from the legacy animator's `animations[i].movement` (= skeleton destinations) instead of `steps[i-1]["end"]["coords"]` (= interrupted ends). For non-gate movers interrupted at, say, 60%, step N's end shows 60%, step N+1's start shows 100% — a teleport every step. This is the root cause of most "teleport" bugs in the list (5, 7, 9, 12, 13, 16).

**Bug-list hypothesis check.** Of the 18 listed bugs, ~9 trace cleanly to invariant violations, ~4 are independent logic errors, ~5 are logic gaps adjacent to invariants. The "legacy lingering causing inconsistencies" framing is accurate for half; the other half are post-migration emitter completeness gaps (announcements/SFX missing on schema path) and unrelated bugs (clamping, IQ-gated reads, animator data sparsity).

**Bottom line.** The base migration is real but partial. Three of the seven invariants (§6, §7, §1) are essentially unbuilt or extensively violated. The most productive next moves are (a) build the §7 snapshot so shot resolution stops branching, (b) fix the §8.1 step-chain in skeleton emitter (root of cluster B teleports), (c) emit announcements on schema-pure paths so the user-visible regressions go away. Detailed remediation order in §6.

---

## 2. Violations by invariant

### 2.1 Invariant 1 — FE is a pure renderer

#### 2.1.1 Position mutation outside end-of-step snap (FE rolls / FE-computed gameplay positions)

| File:line | Description | Inference? | Load-bearing — what breaks if removed |
|---|---|---|---|
| [animateStep.js:110-114](../../FrontEnd/static/js/phaser/animation/animateStep.js#L110-L114) | `clampGridCoords(targetStep.coords, …)` — FE rewrites backend end coords to FE court bounds before tween | confirmed | Legacy step engine `playTurnAnimation`; non-schema turns rely on it for off-bounds backend coords |
| [animateStep.js:279-281, 316-341, 370-408](../../FrontEnd/static/js/phaser/animation/animateStep.js#L279-L408) | FE detects "first HCO pass", reorders pass action vs tween (`shouldDelayPass`), owns ball-attach on receive | confirmed | Legacy HCO pass animation timing + receive ball-attach |
| [turnAnimation.js:1636-1650, 2011](../../FrontEnd/static/js/phaser/animation/turnAnimation.js#L1636-L2011) | `getFallbackOutletTarget`: invents outlet target via `Phaser.Math.Between(3,6)`/`(-6,6)` from rebounder when backend contract missing | confirmed | `runDefensiveReboundSetup` — DREB→HCO outlet fallback |
| [turnAnimation.js:2207-2225](../../FrontEnd/static/js/phaser/animation/turnAnimation.js#L2207-L2225) | Transition-player destinations rolled via `Phaser.Math.Between(20,30)` / ±10 Y when `animations_end` absent | confirmed | 8 non-rebounder/non-outlet players on DREB transitions |
| [turnAnimation.js:2787-2797](../../FrontEnd/static/js/phaser/animation/turnAnimation.js#L2787-L2797) | `animateQuickFoulDefenderToReceiver` rolls defender offset (`Math.random() < 0.5 ? 1 : 2`, ±1 y) | confirmed | Quick-foul defender on inbound flows |
| [turnAnimation.js:2896-2924](../../FrontEnd/static/js/phaser/animation/turnAnimation.js#L2896-L2924) | `runInboundSetup` rolls per-position inbound destinations via `Phaser.Math.Between` | confirmed | All SIDE/BASELINE inbound setups; heavy callers |
| [turnAnimation.js:2930-2972](../../FrontEnd/static/js/phaser/animation/turnAnimation.js#L2930-L2972) | `fcpDefensiveSetup` hard-codes FCP/HCT defender base positions + flip math instead of reading `dDestinations` | confirmed | FCP/HCT defender press formations |
| [turnAnimation.js:3030-3088](../../FrontEnd/static/js/phaser/animation/turnAnimation.js#L3030-L3088) | Defender retreat-to-midcourt picks x via `Phaser.Math.Between(-10,10)` from a base | confirmed | Defender retreat jitter on inbound flows |
| [turnAnimation.js:393-396](../../FrontEnd/static/js/phaser/animation/turnAnimation.js#L393-L396) | `STEAL_HCO_SETUP_MOVE_X*` rolled via `Phaser.Math.Between`; called from schema path too (AnimationEngine.js:304) | confirmed | **Schema path infected** — steal-HCO setup beat |
| [outletUtils.js:19-69](../../FrontEnd/static/js/phaser/animation/outletUtils.js#L19-L69) | `computeFastBreakOutletTarget` with `randomDistance()`/`randomYOffset()` from rebounder | confirmed | FB outlet receiver target — Triangle/RR after-steal paths |
| [drebOutletTargetResolver.js:16-66](../../FrontEnd/static/js/phaser/animation/drebOutletTargetResolver.js#L16-L66) | FE picks outlet receiver target from candidate sources + applies `meaningfulDeltaThreshold` no-op rule | inference | turnAnimation.js:1950 — `contract_receiver_target_no_op` short-circuit |
| [HCOAnimationSystem.js:131-257](../../FrontEnd/static/js/phaser/animation/HCOAnimationSystem.js#L131-L257) | Entire PG/8-player outlet positioning via `Phaser.Math.Between(3,6)`/`(20,30)` + direction inference from `offense_team_id` | confirmed | Wired into AnimationEngine, possibly dead — see Open Questions |
| [ShotAnimationSystem.js:980-1038](../../FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js#L980-L1038) | Rebound-window per-player target via `Phaser.Math.Between(3,6)` x, `(1,6)` y, clamped | confirmed | "Settle near basket during ball flight" on legacy HCO shots |
| [ShotAnimationSystem.js:1494-1530](../../FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js#L1494-L1530) | Non-rebounder collapse-to-bounce offsets via `Phaser.Math.Between(-4,4)`/y±6 | confirmed | Crowd-around-bounce on legacy MISS |
| [ShotAnimationSystem.js:1545-1573](../../FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js#L1545-L1573) | `animatePlayerToReboundSpot` rolls polar `Math.random()*2π` and `Math.random()*10` | confirmed | Per-rebounder crowd spot |
| [ShotAnimationSystem.js:1961-1978](../../FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js#L1961-L1978) | `animatePGToOutlet` offsets PG by `(Math.random()-0.5)*20` | confirmed | Legacy DREB→HCO outlet PG |
| [ShotAnimationSystem.js:2070-2104](../../FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js#L2070-L2104) | `calculateBounceCoords` fallback rolls x/y variance + team sign-flip when backend lacks `ball_bounce_x/y` | confirmed | Loose-ball bounce on legacy miss (code comment admits "shouldn't happen on standard miss turns") |
| [ShotAnimationSystem.js:2355-2388](../../FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js#L2355-L2388) | `_applyDebugVariantOverride` writes `shot_variant_*` fields via `Math.random()` (dev query-param gated) | confirmed | Dev affordance; FE writing backend-authoritative fields |
| [ShotAnimationSystem.js:2732-2734, 3076-3077](../../FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js#L2732-L3077) | FB rebounder spots offset via `Phaser.Math.Between` | confirmed | FB shot rendering when `animations_end` missing |
| [ballManager.js:160-197](../../FrontEnd/static/js/phaser/animation/ballManager.js#L160-L197) | `bounceFromRim` computes bounce X/Y via `Phaser.Math.Between` | confirmed | Legacy `shootBall` miss bounce |
| [ballManager.js:400-401](../../FrontEnd/static/js/phaser/animation/ballManager.js#L400-L401) | `defense_release` rolled via `Phaser.Math.Between(15,35)`/`(45,55)` instead of reading backend coords | confirmed | Legacy shootBall defender release |
| [ballManager.js:944-953](../../FrontEnd/static/js/phaser/animation/ballManager.js#L944-L953) | Rebound participant spots via `Phaser.Math.Between(-6,6)/(-8,8)` + FE eligibility filter (`currentGridX >= 74 ‖ ≤ 25`) | confirmed | Legacy rebound crowd; eligibility filter is FE gameplay decision |
| [ballManager.js:307](../../FrontEnd/static/js/phaser/animation/ballManager.js#L307) | `getMadeShotSweetSpotGrid` vs rim choice based on `result === "MAKE"` | inference | Legacy `shootBall` ball end position |
| [fastBreak.js:1545-1546, 1964-1965, 2086-2090](../../FrontEnd/static/js/phaser/animation/fastBreak.js#L1545-L2090) | Rebound polar random, PG outlet `(Math.random()-0.5)*20`, FB bounce fallback variance | confirmed | After-Steal FB + FB miss positioning fallbacks |
| [fastBreak.js:4029-4053, 4246-4248](../../FrontEnd/static/js/phaser/animation/fastBreak.js#L4029-L4248) | Rebounder/get-back target spots via `Phaser.Math.Between` when `animations_end` missing | confirmed | FB non-shot-participant positions |
| [PassAnimationSystem.js:443-461](../../FrontEnd/static/js/phaser/animation/PassAnimationSystem.js#L443-L461) | `calculateInboundPosition` / `calculateFastBreakPosition` pick from court width + `(Math.random()-0.5)*20` y variance | confirmed | Inbound + FB receiver positioning |
| [countdownAnimation.js:134, 164-208, 265-271](../../FrontEnd/static/js/phaser/animation/countdownAnimation.js#L134-L271) | Quarter-transition countdown rolls all ball-handler / offense / defender spots via `Math.random()` | confirmed | Q1/OT countdown transition |
| [arrivalHeartbeat.js:46-52, 175-211](../../FrontEnd/static/js/phaser/animation/arrivalHeartbeat.js#L46-L211) | Heartbeat BPM derived from `sprite.attributes.NG` via FE formula | inference | Cosmetic-only; FE reads raw gameplay attribute |
| [animationPlayback.js:894-970](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L894-L970) | `runShotAttempt` (schema path) picks shot end position via `getMadeShotSweetSpotGrid` vs rim based on `result === "MAKE"` | inference | Schema-path SHOT_ATTEMPT turn-stop arc/bounce; load-bearing for every FB shot |
| [animationPlayback.js:419-505](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L419-L505) | `inferStepAnnouncementPlayerData`/`enrichStepAnnouncementPlayerData` infers stopper from action scan; `isCovertReleaseDefensiveStopAnnouncement` rewrites "Nice Stop!" → "Great Stop!" | inference / confirmed | Headshot card rendering; CR announcement rewrite |

#### 2.1.2 FE owns ball state / ownership (UESS §6 commit events never consumed in FE)

| File:line | Description | Inference? | Load-bearing |
|---|---|---|---|
| [BallController.js:147-180, 185-225, 253-316](../../FrontEnd/static/js/phaser/animation/BallController.js#L147-L316) | Full FE ownership lifecycle: `attachToPlayer`/`detachFromPlayer`/`startFlight`/`endFlight` mutate `currentOwner`/`scene.gameState.ballHolder`, fire `recordOwnershipChange` | confirmed | EVERY animation system asks "who has the ball" from this FE state; BE event never consumed |
| [ballAnimationSimple.js:136-173](../../FrontEnd/static/js/phaser/animation/ballAnimationSimple.js#L136-L173) | `getPlayerTweenTargets` inspects FE `ballHolderId`/`passInFlight`/`ballControllerInFlight` to decide whether to include ball in player's tween | confirmed | animateStep.js depends on it for ball-following on player tweens |
| [passDetection.js:17-138](../../FrontEnd/static/js/phaser/animation/passDetection.js#L17-L138) | `detectPassAtStep` re-derives `{passerId, receiverId}` from `animations[].movement[]` action sniffing | confirmed | Heavy use across legacy HCO/DREB/shot pipelines |
| [animateStep.js:165-211](../../FrontEnd/static/js/phaser/animation/animateStep.js#L165-L211) | `clearBallHolder`/`setBallHolderId` on FE action sniff (`pass`/`receive`) | confirmed | Legacy ball-holder rendering |
| [turnAnimation.js:2296-2297](../../FrontEnd/static/js/phaser/animation/turnAnimation.js#L2296-L2297) | `setPendingOwner`/`setCurrentOwner(rebounder)` on PG-self-dribble DREB→HCO branch | inference | PG-self-dribble DREB→HCO ball-handler |
| [turnoverAdapter.js:42-46](../../FrontEnd/static/js/phaser/animation/turnoverAdapter.js#L42-L46) | FE adopts `turnData.offense_team_id` + emits `possessionChange` event | inference | UI listening for possession transitions |
| [fastBreak.js:1590-1635](../../FrontEnd/static/js/phaser/animation/fastBreak.js#L1590-L1635) | `animateRimRunnerInterception` calls `attachBallToPlayer(scene, ballSprite, stealer)` — FE decides ownership at end of steal + fires `playStealSfx` | confirmed | RR interception ownership transfer; UESS §6 says BE-stamped |
| [PossessionRunner.js:488-494, 568-577](../../FrontEnd/static/js/phaser/animation/possession/PossessionRunner.js#L488-L577) | `onFrameStart`/tween-start flips `currentOwnerId` based on legacy animator's release-time `hasBallAtStep` — FE commits at frame START, not after pass tween | confirmed | FE consequence of `animator.capture_halfcourt_animation`'s release-time flip |

#### 2.1.3 FE-side dispatch branching on game state

| File:line | Description | Inference? | Load-bearing |
|---|---|---|---|
| [fastBreak.js:66-105](../../FrontEnd/static/js/phaser/animation/fastBreak.js#L66-L105) | `classifyFastBreakPhase2` FE decision tree (`fast_break_shot_foul`, `rim_runner_steal`, `rim_runner_bat_oob`, `rim_runner_hco_settle`, `triangle_hco_settle`, `generic_fb_stop`) | inference | `deriveFbBranchKind` — which animation branch runs in `runFastBreakSequence` |
| [AnimationEngine.js:737-849](../../FrontEnd/static/js/phaser/animation/AnimationEngine.js#L737-L849) | `determineHandler`/`isShotAttempt`/`isRebound`/`isPass` branch on `fast_break`/`result_type`/`fcp_*`/`hct_*`/`final_turn` | inference | Every legacy turn dispatch |
| [AnimationEngine.js:929-1039](../../FrontEnd/static/js/phaser/animation/AnimationEngine.js#L929-L1039) | `handleBaselineInbound` polls `scene.passInFlight` with `setInterval`/`setTimeout`, decides when transition fires + pressure-state change | confirmed | Legacy BIP rendering |
| [animateGameTurns.js:1118-1267](../../FrontEnd/static/js/phaser/animation/animateGameTurns.js#L1118-L1267) | Large FCP/HCT routing tree using `fcp_shot`/`hct_shot`/`fcp_foul`/`hct_foul`/`next_defensive_setup` + FE-cached `scene.currentPressureType`/`scene.pressureSequenceActive` | inference | FCP/HCT routing |

**Themes (Invariant 1):**
- FE-side fallback randomization is endemic across all legacy handlers — silent `Phaser.Math.Between`/`Math.random` for any sparse backend payload.
- Ball ownership is FE-authoritative: `BallController.currentOwner`, `scene.gameState.ballHolder`, `scene.passInFlight` are the production sources. UESS `ownership_commit_event` never consumed.
- FE makes outcome-rendering choices: `runShotAttempt`/`shootBall` pick ball end coord from `result === "MAKE"`; CR "Nice Stop!" rewritten to "Great Stop!".

---

### 2.2 Invariant 2 — Clock authority is ledger-derived

#### 2.2.1 Backend violations

| File:line | Description | Inference? | Load-bearing |
|---|---|---|---|
| [dynamic_hct_step_emitter.py:386-388](../../BackEnd/engine/dynamic_hct_step_emitter.py#L386-L388) | `total_elapsed = walk_up_t + converge_seconds + attack_seconds; turn_result["time_elapsed"] = …` — **emitter sums step times into `turn_result["time_elapsed"]`, exactly what §5.4 forbids** | No | Caller `turn_manager.py:1410-1412`. `_attach_clock_contract` overwrites at runtime; but `step_clock_seconds`/`resolution_step_index` survive and feed `_shot_detach_elapsed_seconds` for shot-clock burn. Cleanest §5.4 violation in the tree. |
| [phase_resolution.py:984-987](../../BackEnd/engine/phase_resolution.py#L984-L987) | `apply_fast_break_cg_time`: `time_elapsed = clamp_turn_time_elapsed(round(distance_seconds + overhead_seconds), cap=30)` — tuned independently | No | 8 call sites (RR/CR/Triangle/DEFENSIVE_STOP). Final ledger overwrites, but `_attach_clock_elapsed_observe_reconciliation` reads this as `legacy_elapsed` for delta reporting. |
| [turn_manager.py:1377-1393, 3186-3202, 3752-3761](../../BackEnd/models/turn_manager.py#L1377-L3761) | FCP/HCO/OREB schema-game-burn realignment: `schema_game_burn = cs_start - cs_end` from first/last step clocks → overwrites `result["time_elapsed"]`. Derived from per-step clock readings, not from `clock_event_ledger` rows | No | Required to align with `[ball_flight]+[bounce]` sub-step burn; without it FCP/HCO/OREB under-burn game clock by ~1-1.5s. Functionally close to ledger, technically not. |
| [game_manager.py:781-799](../../BackEnd/models/game_manager.py#L781-L799) | `_build_dreb_turn_from_miss`: `time_elapsed = animation_steps[0]["end"]["time_elapsed"]` — one step's value | No | `update_clock_and_possession(dreb_turn)` later overwrites via ledger; removal would corrupt `real_time_elapsed_ms` due to ordering bug below |
| [turn_manager.py:3279-3285](../../BackEnd/models/turn_manager.py#L3279-L3285) | `_build_final_hold_result`: `"time_elapsed": int(time_remaining_sec)` — drain quarter clock | No | Final Hold semantics; ledger override explicitly skipped at turn_manager.py:3181-3184 |
| [phase_resolution.py:4289](../../BackEnd/engine/phase_resolution.py#L4289) | `resolve_final_turn_shot_logic`: `shot_result["time_elapsed"] = int(time_remaining)` — drain ≤30s Final Shot | No | Only `time_elapsed` source for Final Shot turns; bypasses ledger |
| [phase_resolution.py:5241-5243](../../BackEnd/engine/phase_resolution.py#L5241-L5243) | `_shot_at_one_second_time_elapsed`: direct write to force `shot_clock_end == 1` | No | Shot-at-1 rule; bypasses ledger by design |
| [phase_resolution.py:4994/5054/5114/6091-6117/7524-7557](../../BackEnd/engine/phase_resolution.py#L4994-L7557) | HCO turnover/O_FOUL/D_FOUL/FCP wrap/HCT wrap: `turn_result["time_elapsed"] = timing_contract["time_elapsed"]` where helper sums per-step movement seconds — explicitly the "legacy sum" §5.4 forbids | No | Final emitted overwritten by ledger; removal leaves `time_elapsed=0` going into `_compute_real_time_elapsed_ms` |
| [shot_manager.py:747-769, 824-848, 919-940, 1899+](../../BackEnd/models/shot_manager.py#L747-L1899) | Multiple `result["time_elapsed"] = timing_contract["time_elapsed"]` writes from `calc_skeleton_step_timing_contract` | No | Same as above; `step_clock_seconds`/`resolution_step_index` survive for shot-clock-detach accounting |
| [opening_tip.py:202, 221](../../BackEnd/utils/opening_tip.py#L202-L221) | `time_elapsed = random.randint(1,5)+1` — random, not ledger | No | Could not confirm Opening Tip routes through `_attach_clock_contract` |
| [quarter_start.py:162](../../BackEnd/utils/quarter_start.py#L162) | `"time_elapsed": 4` hardcoded for quarter-start BASELINE_INBOUND | No | Bypasses ledger; intentional |
| [situational_logic.py:157-162](../../BackEnd/utils/situational_logic.py#L157-L162) + turn_manager.py:1286/3317, game_manager.py:1256 | `force_foul_time_elapsed()` returns `random.randint(MIN,MAX)`; injected as `time_elapsed_override` | No | Random; later overwritten by ledger |

#### 2.2.2 FE clock manipulation (inference-grade per §1+§5)

| File:line | Description | Inference? | Load-bearing |
|---|---|---|---|
| [ShotAnimationSystem.js:1118-1186](../../FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js#L1118-L1186) | Every MAKE: `scene.gameClock.pause('made_shot_hold')` + `shotClock.pause()`, awaits hardcoded `holdMs = animationConfig.shot?.makeAnnouncementHoldMs ?? 1000`, resumes. **Backend `_build_make_hold_sub_step` already emits the same hold** (skeleton_step_emitter.py:1471-1520, `MAKE_HOLD_MS=1000.0`). Both could fire = double hold; only FE = no backend honoring; only BE = no FE clock pause. **Prior incident: "lost the 1000ms make-hold once already".** | Yes | Legacy `makeShot`; all turn types unless migrated. Critical to disambiguate before touching. |
| [animationPlayback.js:518-519, 576-579, 580-581](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L518-L581) | `runStepAnnouncement`: `scene.gameClock.pause/resume()` + hardcoded `1000`ms fallback when backend omits `hold_ms` | Yes | UESS-compliant step announcement path; backend should always supply `hold_ms` |
| [AnimationRouter.js:524-534](../../FrontEnd/static/js/phaser/animation/AnimationRouter.js#L524-L534) | `applyClockControl`: FE classifies `no_impact_turn` from `time_elapsed === 0` or `result_type ∈ {FREE_THROW, SIDE_INBOUND, BASELINE_INBOUND, TIMEOUT}` and pauses both clocks | Yes | Without it clocks tick during FT/SIP/BIP/TIMEOUT or stall on real turns |
| [AnimationRouter.js:579-644](../../FrontEnd/static/js/phaser/animation/AnimationRouter.js#L579-L644) | FE Phaser tween drives `gameClock`/`shotClock` via `syncWithBackend(seconds)` every frame, computing `gameSeconds`/`shotSeconds` between `clockStart` and `clockEnd` (two-phase ratio math) | Yes | Visible clock animation between turn boundaries; without it clocks jump to BE snapshot |
| [gameScene.js:2216-2218](../../FrontEnd/static/js/phaser/gameScene.js#L2216-L2218) | `if (isNoImpactShotClockTurn(turn)) this.shotClock.pause('no_impact_turn')` — FE second-guesses shot-clock | Yes | Mirror of AnimationRouter pattern |
| [AnimationEngine.js:382-383, 902-903, 1548-1549, 1596-1601](../../FrontEnd/static/js/phaser/animation/AnimationEngine.js#L382-L1601) | Hardcoded `setTimeout(holdMs)` with `?? 3000`/`?? 1800`/`?? 2000` for Final Turn FE flourishes | Yes | Final Turn visual delays; not strictly clock pauses |
| [turnAnimation.js:1085-1098](../../FrontEnd/static/js/phaser/animation/turnAnimation.js#L1085-L1098) | `holdMs = animationConfig.inbound?.holdAfterPlaceMs ?? 200` — FE hardcoded inbound hold | Yes | Inbound FE delay |
| [fastBreak.js:1657-1660](../../FrontEnd/static/js/phaser/animation/fastBreak.js#L1657-L1660) | `holdMs = animationConfig.fastBreak?.defensiveStopHoldMs ?? 1000` — FE FB defensive-stop hold | Yes | Legacy FB FE hold |

#### 2.2.3 Notes on `time_elapsed` derivation

- **Ledger derivation IS wired**: `_attach_clock_contract` (turn_manager.py:189-230) calls `_build_clock_event_ledger` emitting all spec'd event types, then `_attach_clock_elapsed_observe_reconciliation` (line 269-322) derives `ledger_elapsed` by summing `game_clock_before - game_clock_after` over `game_clock_stop` rows. When `elapsed_authority == "ledger"` (default), `result["time_elapsed"] = int(ledger_elapsed)` at line 291.
- **Ordering bug**: `_compute_real_time_elapsed_ms` consumes `result["time_elapsed"]` at turn_manager.py:116/212 BEFORE ledger overwrite at line 291. So `real_time_elapsed_ms` uses the **pre-ledger** value for FE wall-clock duration (AnimationRouter.js:541). Subtle — would manifest as visible FE drift on turns where ledger ≠ legacy sum.
- **Coverage**: `_attach_clock_contract` runs via `update_clock_and_possession` (turn_manager.py:4488) and 4 game_manager paths (TIMEOUT, FOUL_AFTER_DREB, SIP, BIP). Opening Tip flow was not traced.
- **SIP/BIP boundary pins** (transition_bridge.py:1238-1247/1120-1127) are **explicit** clock-state writes tied to documented inbound semantics, not implicit — acceptable per §5.1 wording.

---

### 2.3 Invariant 3 — Emitters never write `player.coords` mid-emit

#### 2.3.1 Direct `player.coords =` writes inside emitters/resolvers

| File:line | Description | Inference? | Load-bearing |
|---|---|---|---|
| [rim_runner_fast_break.py:267](../../BackEnd/engine/rim_runner_fast_break.py#L267) | `_triangle_apply_coords` helper does `player.coords = {…}`; called from `_triangle_commit_setup_positions` + 3 drive branches | No | Triangle UESS emitter (triangle_step_emitter.py:601) + RR emitter + shot snapshot all read `player.coords` for shooter/start coords |
| [rim_runner_fast_break.py:368, 369, 381, 382, 394, 395](../../BackEnd/engine/rim_runner_fast_break.py#L368-L395) | `_triangle_apply_coords(ball_handler, drive_to)` / `(rim_runner, mid_lane)` inside `_triangle_build_turn_result` per drive branch | No | Same as above |
| [rim_runner_fast_break.py:410](../../BackEnd/engine/rim_runner_fast_break.py#L410) | `shooter.coords = {"x": float(shot_spot["x"]), "y": float(shot_spot["y"])}` before `resolve_shot` | No | Feeds shot snapshot + roles + Triangle UESS emitter |
| [rim_runner_fast_break.py:936, 938](../../BackEnd/engine/rim_runner_fast_break.py#L936-L938) | `rr.coords` / `ball_handler.coords` post-outlet burst writes mid-resolution | No | Consumed by `rim_runner_step_emitter._all_player_start_coords` |
| [rim_runner_fast_break.py:1128, 1181, 1347](../../BackEnd/engine/rim_runner_fast_break.py#L1128-L1347) | `rr.coords = shot_spot` after lane-pass success (3 branches) | No | Shot snapshot + RR UESS emitter |
| [phase_resolution.py:2327](../../BackEnd/engine/phase_resolution.py#L2327) | `defender.coords = stealer_coords.copy()` in `resolve_turnover_logic` on STEAL | No | Read downstream by `_build_dreb_turn_from_miss`, post-stop snapshots, next-turn emitter |
| [phase_resolution.py:3925](../../BackEnd/engine/phase_resolution.py#L3925) | `shooter.coords = coords` in `set_shooter_coords_from_skeleton_last_step` (HCO/FCP/HCT before `resolve_shot`) — pulls a `HCO_STRING_SPOTS` lane coord and writes mid-resolution | No | Feeds `shot_state_snapshot.shooter.x/y` (if it existed), block reconciliation, `[shoot]` step's `start.coords` for shooter |
| [phase_resolution.py:6026, 7466](../../BackEnd/engine/phase_resolution.py#L6026-L7466) | `defender.coords = stealer_coords.copy()` in FCP/HCT MISS-shoot path on STEAL | No | Same downstream as 2327 |
| [quarter_start.py:136, 152](../../BackEnd/utils/quarter_start.py#L136-L152) | `player.coords = end.copy()` for every offense + defense player in `create_quarter_start_turn` | No | Next-turn HCO emitter reads `prior_turn.final_coords`; sync would pick up via legacy `animations[]` path |
| [game_manager.py:1258](../../BackEnd/models/game_manager.py#L1258) | `victim.coords = {…}` in `force_foul_after_dreb` branch before `_append_turn(foul_result)` | No | Sync uses `player.coords` as source #1 |
| [turn_manager.py:1292, 3322](../../BackEnd/models/turn_manager.py#L1292-L3322) | `victim.coords = {…}` in Force-Foul-on-inbound + final-turn Force-Foul builders | No | Snapshot + sync use it |
| [shared.py:2874-2902 (`apply_coords_from_animations_list`)](../../BackEnd/utils/shared.py#L2874-L2902) | Independent helper walks `animations[]`, picks per-row final coord, calls `player.coords = dict(final)`. **Called 14× from phase_resolution.py (1767, 1843, 2062, 4941, 5235, 5782, 6043, 7230, 7483) and rim_runner_fast_break.py (1125, 1179, 1264, 1304, 1345) MID-RESOLUTION before `resolve_shot`** (HCO/FCP/HCT/FT/FB paths) | No | Downstream `shot_state_snapshot` shooter coords + rebound geography + UESS step emitters' `_all_player_start_coords` all consume `player.coords` |

#### 2.3.2 Turn→turn coord syncs bypassing `sync_lineup_coords_from_turn`

| File:line | Description | Inference? | Load-bearing |
|---|---|---|---|
| [shared.py:2874-2902](../../BackEnd/utils/shared.py#L2874-L2902) | `apply_coords_from_animations_list` is an independent coord-writer that runs DURING turn resolution, not at boundary. Writes same target as `sync_lineup_coords_from_turn` but many times per turn | No | See above — every legacy resolver relies on this to seed `player.coords` for snapshots and next emitter |
| [quarter_start.py:136, 152](../../BackEnd/utils/quarter_start.py#L136-L152) | Quarter-start writes `player.coords` directly; universal `_append_turn → sync` still fires after but emitter already established new coords outside sync authority | No | No race today (sync step-1 carries forward); violates §8.3 contract |

#### 2.3.3 Step N+1 start.coords NOT derived from step N end.coords

| File:line | Description | Inference? | Load-bearing |
|---|---|---|---|
| [skeleton_step_emitter.py:916-917](../../BackEnd/engine/skeleton_step_emitter.py#L916-L917) | Loop body: `start_coords = _coords_at_movement_index(animations, i)`, `end_coords = _coords_at_movement_index(animations, i + 1)`. Step N+1 reads independently from legacy animator's `animations[].movement[]` skeleton template — NOT from prior step's `end.coords`. Step N's `end.coords` then overwritten by `_build_step_end_coords_with_interrupts` (§9.5 interrupted-coord math), so non-gate movers end at interrupted positions while step N+1 starts at the skeleton waypoint. **This is the root of "every step teleports non-gate defenders by the gap between interrupted and waypoint."** | No | Cluster B teleport bugs (7, 9, 12, 13, 16) all root here. First prepended Reset/Walk-Up correctly seeds from prior step end (`start_coords = dict(steps[-1]["end"]["coords"])` at line 906) — the divergence is specifically the skeleton-loop body at i≥0 (when no entry steps prepended) and at i≥1 (always). |
| [skeleton_step_emitter.py:911-914](../../BackEnd/engine/skeleton_step_emitter.py#L911-L914) | FCP `fcp_seed_coords` branch: step 0's start_coords is `animations[i].movement[0]` overridden per-player by `prior_turn.final_coords`. Overlay correct; rest of loop body has same problem as 916-917 | No | Same as preceding row |

---

### 2.4 Invariant 4 — Ownership commits at receipt, not release

#### 2.4.1 Release-time ownership flips

| File:line | Description | Inference? | Load-bearing |
|---|---|---|---|
| [animator.py:806-810](../../BackEnd/models/animator.py#L806-L810) | Legacy animator's `ball_owner_by_step`: flips on `event.type == "pass"` → `owner = off_lineup.get(event.get("to"))`. Owner set to **receiver** on same step that emits pass — release, not receipt. Contrast skeleton emitter's `_walk_ball_owners` (line 189-211) which correctly flips on `receive`/`handle_ball` | No | Feeds per-player `hasBallAtStep` (lines 859, 925, 1081); FE `PossessionRunner.findOwnerFromFrame` consumes it; every legacy turn renders pass with ownership pre-committed |
| [PossessionRunner.js:488-494](../../FrontEnd/static/js/phaser/animation/possession/PossessionRunner.js#L488-L494) | `onFrameStart`: `if (ownerId && ownerId !== this.currentOwnerId)` flips on frame-start based on `hasBall` from frame payload. On pass step where receiver marked `hasBall=true`, FE commits ownership at frame-start, not after tween | No | FE consequence of animator's release-time flip; combined with end-of-pass commit at line 618, same id flipped twice (visually harmless if same id) |
| [PossessionRunner.js:568-577](../../FrontEnd/static/js/phaser/animation/possession/PossessionRunner.js#L568-L577) | `createPlayerTween.onStart`: when player payload has `hasBall=true` and current owner differs, FE attaches ball at tween START | No | Same FE/sprite consequence; mid-step ownership write |

#### 2.4.2 Missing `ownership_at_turn_start` / `ownership_commit_event` stamps

| File:line | Description | Inference? | Load-bearing |
|---|---|---|---|
| ENTIRE TREE | **Neither field name appears in code.** Grep `ownership_at_turn_start` and `ownership_commit_event` returns zero hits BE-wide and FE-wide. UESS §6.2 contract unimplemented as specified. Per the audit rule "code is ground truth," the actual shape is `uess_ownership_contract.*` (turn_manager.py:420-497) with fields `pass_event_count`, `pass_receipt_valid_count`, `pass_lifecycle_valid`, `terminal_owner_pos`, etc. | No | No downstream consumer reads the missing fields (they don't exist). `uess_ownership_contract` only powers a warn/throw log when `pass_lifecycle_valid` is false. |
| [turn_manager.py:420-497](../../BackEnd/models/turn_manager.py#L420-L497) | Even implemented `uess_ownership_contract` is gated on `applicable = isinstance(steps, list) and len(steps) > 0 and isinstance(owner_by_step, list)`. Turns without `steps` + `ball_owner_by_step` (BIP, SIP, FT, DREB, OREB, Opening Tip, TIMEOUT, side-inbound setups, force-foul) get `applicable: false` and skip validation. §6.2 "stamped on every turn" rule not enforced for half the turn types | No | Observational only today; would silently fail §6.2 promise if/when wired to consumers |

---

### 2.5 Invariant 5 — ShotManager is sole post-shot position authority

#### 2.5.1 Bypasses of the four overlay maps

| File:line | Description | Inference? | Load-bearing |
|---|---|---|---|
| [animator.py:440-468](../../BackEnd/models/animator.py#L440-L468) | `capture_fast_break_animation` independently computes rebounder end-coords using `random.randint(REBOUNDER_X_MIN/MAX)` + rim-±`SHOT_ATTEMPT_REBOUNDER_Y_RANGE`. **Animator runs BEFORE `shot_manager.resolve_shot`** (rim_runner_fast_break.py:444, 1124, 1178, 1344); its movement endpoints attach to `turn_result["animations"]`; Triangle/RR step emitters then read via `_movement_end_coord`. FB end-positions for rebound cluster come from animator, not ShotManager overlays. | No | Triangle's `_build_triangle_shot_motion_step` (triangle_step_emitter.py:489-495) consumes; FE / sync_lineup downstream |
| [ballManager.js:396-414](../../FrontEnd/static/js/phaser/animation/ballManager.js#L396-L414) | `defense_release` block rolls target via `Phaser.Math.Between(15,35)`/`(45,55)` instead of reading `defense_release_coords`. Sibling block at lines 418-451 correctly reads `offense_getback_coords` — two FE paths disagree on shot_manager authority | No | Release-player tweens during legacy shot animation |
| [ShotAnimationSystem.js:945-1039](../../FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js#L945-L1039) | Rebounder positioning computed via `Phaser.Math.Between(3,6)`/`(1,6)`. **`offense_rebounder_coords` / `defense_rebounder_coords` not read anywhere on FE** (grep returns 0 hits) | No | Visible rebounder tween during shot flight |
| [ReboundAnimationSystem.js:210-253](../../FrontEnd/static/js/phaser/animation/ReboundAnimationSystem.js#L210-L253) | `animatePlayerCollapse` / `animatePlayerCollapseToRebounder` computes target as `sprite.x + dx * collapseRatio` — no backend overlay read | No | DREB/OREB collapse in legacy path |
| [triangle_step_emitter.py:489-538](../../BackEnd/engine/triangle_step_emitter.py#L489-L538) | `_build_triangle_shot_motion_step` populates end_coords from `_movement_end_coord(animations, pid)` — animator's pre-computed random rebounder positions, not overlay maps. `_finalize_rr_steps` calls `canonicalize_post_shot_overlays` for bookkeeping but never writes overlay coords into the schema step | No | Triangle FB last step's `end.coords` is what `sync_lineup_coords_from_turn` reads (shared.py:2961-2980), so non-shooter/defender post-FB positions authored by animator, not ShotManager |
| [shared.py:2982-3004](../../BackEnd/utils/shared.py#L2982-L3004) | `_build_post_shot_sub_steps` intentionally suppresses overlay maps from overriding `animation_steps[-1].end.coords` for MAKE/MISS/BLOCK; in-code comment notes legacy DREB / shooting-foul still read overlays directly. Documented split-authority, sound for HCO migrated turns but flags as deliberate violation of §9.1 wording | Yes (re: §9.1 wording) | Cross-turn carry-forward depends on `sync_lineup_coords_from_turn` reading schema end coords; overlay maps vestigial for migrated turns |

#### 2.5.2 Role-exclusivity weaknesses

| File:line | Description | Inference? | Load-bearing |
|---|---|---|---|
| [shot_manager.py:1281-1339, 1411-1455, 1561-1617, 1741-1784](../../BackEnd/models/shot_manager.py#L1281-L1784) | All four overlay maps populated unconditionally per branch without membership-cross-check. Role-exclusivity relies entirely on `canonicalize_post_shot_overlays` at the bottom (2048-2052, 2596-2600). **Early returns bypass it**: 792 (block-recon shooting foul), 865 (CHARGE), 969 (BLOCKING_FOUL), 1554 (FB over-the-back), 1728 (HCO over-the-back) | No | Currently benign — early-return paths produce FOUL/CHARGE results with no overlay writes — but invariant unprotected against future regressions |
| [shared.py:2773-2797](../../BackEnd/utils/shared.py#L2773-L2797) | `canonicalize_post_shot_overlays` removes shooter from all 4 maps and outlet_passer/getback/release from rebounder maps, but does **NOT remove getback↔release collisions**. Construction in shot_manager builds them from disjoint position lists, so works in practice, but enforcer is incomplete | No | Future shot_manager change shipping release player into getback wouldn't be caught |

---

### 2.6 Invariant 6 — One shot snapshot

#### 2.6.1 The §7 snapshot is unbuilt

| File:line | Description | Inference? | Load-bearing |
|---|---|---|---|
| ENTIRE TREE | **`shot_state_snapshot` key never appears in the codebase.** Grep returns 0 hits BE-wide and 0 hits FE-wide. UESS §7 prescribed location `turn_result["roles"]["shot_state_snapshot"]` is not implemented. All contest/foul/block/rebound/make-miss resolution branches in `shot_manager.resolve_shot` instead read directly from `roles`, `shooter.coords`, `def_lineup` values, and `game_state` | No | UESS §7 contract not met for any shot |
| [shot_manager.py:410-2053 (resolve_shot)](../../BackEnd/models/shot_manager.py#L410-L2053) | Method does not build any snapshot of its own. Pre-shot snapshots (`build_skeleton_pre_resolve_shot_snapshot`, `build_hco_pre_resolve_shot_snapshot`, `build_fast_break_pre_shot_snapshot`) are constructed by **callers** (phase_resolution.py:4280/5237/5784/7232, turn_manager.py:2018, rim_runner_fast_break.py:441/1131/1184/1350) and attached AFTER `resolve_shot` returns via `attach_position_snapshots`. **Resolve_shot never reads from them.** | No | Snapshot machinery is audit-only (consumed by `position_snapshot_ledger`); resolve_shot's logic reads live game state |
| [position_snapshot_ledger.py:103-203](../../BackEnd/utils/position_snapshot_ledger.py#L103-L203) | Snapshots store only `positions` + checkpoint metadata + optional `ball_handler_id`/`possession_team_id`. **Lack the UESS §7 fields**: `shot_type`, `shooter {x,y,coord_source}`, `shot_spot {present,x,y}`, `primary_defender`, `secondary_defender`, `nearest_defender`, `assigned_defender_count`, `contest_box_defender_count`, `contest_box_defenders`, `has_assigned_defender`, `has_contest_box_defender`. None appear anywhere in BE code (grep `contest_box_defender_count`/`has_assigned_defender` → 0) | No | Snapshot schema diverges from UESS doc |
| ENTIRE TREE | **No `SHOT_COORD_DEBUG` log emission** anywhere in code. Only appears in UESS_System.md doc itself | No | UESS §7/§10 observability contract violated for every shot |
| ENTIRE TREE | **No `NO_DEFENDER_SHOT` log emission.** Counter `no_defender_shots` is incremented (shot_manager.py:1023, 2455) but per-shot log tag does not exist | No | UESS §7/§10 zero-defender observability missing |

#### 2.6.2 Branch-specific coord fallbacks in shot resolution

| File:line | Description | Inference? | Load-bearing |
|---|---|---|---|
| [shot_manager.py:90-95 (`_shooter_xy_from_roles`)](../../BackEnd/models/shot_manager.py#L90-L95) | Shot_spot → shooter.coords fallback. Allowed by §7.3 — **but spec says "logged as such" and the fallback does NOT log** (no `logging.` near helper) | No | Drives shot location for `geometry_has_contest`, `rim_unguarded_99`, contest box test, block-spot |
| [shot_manager.py:619-625](../../BackEnd/models/shot_manager.py#L619-L625) | Defender geometry contest iterates `def_lineup.values()` and reads each defender's live `.coords` at evaluation time. Second authoritative source for defender positions, not a snapshot. The exact pattern §7 forbids ("contest evaluation reads from current game state") | No | `geometry_has_contest` / `rim_unguarded_99` |
| [shot_manager.py:1462-1487, 1631-1645](../../BackEnd/models/shot_manager.py#L1462-L1645) | `_eligible_fb_lineup(lineup_dict)` and rebound math read `getattr(player, "coords", {})` and pass `bounce_spot` to `choose_rebounder` — all live `player.coords` at rebound time, no snapshot | No | Rebound team selection — drives DREB/OREB result_type |
| [shot_manager.py:1188-1339, 1456-1617, 1618-1784](../../BackEnd/models/shot_manager.py#L1188-L1784) | MAKE / MISS+foul / FB miss / HCO miss branches each re-derive positioning info from `off_team.lineup` / `def_team.lineup` / `shooter` independently. No common snapshot. Three code paths can diverge silently on rebounder-cluster generation rules — exactly what §7 forbids | No | Branch silos |
| [shot_manager.py:1486-1487, 1644-1645](../../BackEnd/models/shot_manager.py#L1486-L1645) | `choose_rebounder` computes via live `.coords` distance to `bounce_spot` | No | Rebounder selection from live state, not snapshot |
| [shot_manager.py:799-807, 693-697](../../BackEnd/models/shot_manager.py#L693-L807) | Block-spot fallback (`shot_spot` → `shooter.coords`) is the §7.3 allowed fallback. Block reconciliation `shooter_coords_recon = getattr(shooter, "coords", {"x": 50, "y": 25})` is logging-only | N/A allowed / No | `calculate_block_spot` |

#### 2.6.3 Notes on snapshot integrity

- `canonicalize_post_shot_overlays` is called inconsistently:
  - shot_manager.py:2048-2052 / 2596-2600 — both exits call it (good).
  - rim_runner_step_emitter.py:1773-1779 — re-call after RR/Triangle finalize.
  - covert_release_step_emitter.py:1280-1281 — re-canonicalizes after `outlet_passer` attach (good).
  - **Not called from** hct_step_emitter.py / dreb_step_emitter.py / oreb_step_emitter.py / ft_step_emitter.py — rely on shot_manager's earlier call.
  - **Early returns in `resolve_shot` bypass** (lines 792, 865, 969, 1554, 1728). Benign today (no overlay writes on those paths), unprotected for future.

---

### 2.7 Invariant 7 — Every turn emits the same schema

| Turn type | Path | Expected per §2? | Surprising? |
|---|---|---|---|
| Fast Break — After Steal | ~~emits `animations[]` only~~ **Resolved (May 2026):** migrated to `after_steal_fast_break.py` resolver + `after_steal_fast_break_step_emitter.py` (schema steps + shared post-shot chain) | Migrated | — |
| Timeout | [turn_manager.py:3349-3424 (`setup_timeout_turn`)](../../BackEnd/models/turn_manager.py#L3349-L3424); no `animations` or `animation_steps` | Yes (Not migrated) | Not surprising |
| **Final Shot** | UESS §2 says Not migrated; **code routes through HCO emitter at [turn_manager.py:3208-3218](../../BackEnd/models/turn_manager.py#L3208-L3218)** → `_emit_hco_animation_steps` → `build_skeleton_animation_steps`. Final Shot DOES emit `animation_steps[]` | Doc says No, code says Yes | **Resolved (§4.2 decision 3)** — update UESS §2 to mark Migrated; note `time_elapsed` clock-drain is intentional |
| **Opening Tip** | [opening_tip.py:124-225 (`execute_opening_tip`)](../../BackEnd/utils/opening_tip.py#L124-L225) emits legacy `animations[]` with non-vocab actions (`TIP_JUMP`, `CONVERGE_ON_BALL`); no `animation_steps[]` key | UESS §2 says "Migrated (legacy emitter; schema-compliant payload)" | **Resolved (§4.2 decision 2)** — actually migrate. UESS §2 stays "Not migrated" until `opening_tip_step_emitter.py` ships |
| HCT static (legacy non-dynamic) | [hct_step_emitter.py](../../BackEnd/engine/hct_step_emitter.py) invoked from phase_resolution.py:7313, 7630 for static HCT skeleton | UESS §2 mentions only dynamic HCT as migrated | **Resolved (§4.2 decision 9)** — dead path; remove file + callers |
| **DREB coverage gap** | [game_manager.py:702-704 (`_build_dreb_turn_from_miss`)](../../BackEnd/models/game_manager.py#L702-L704) now fires for HCT / HCO / FCP / migrated Fast Break MISS/BLOCK, final-FT DREB, and OREB putback miss → DREB. Historical gap: FCP, Rim Runner, Triangle, After-Steal MISS did not spawn a discrete DREB turn (rebound capture absorbed into legacy MISS turn). | UESS §2 marks DREB migrated for current promoted paths | **Partially resolved (§4.2 decision 8)** — FCP closed May 2026; continue sunsetting any remaining embedded-DREB legacy paths. |

---

## 3. Schema completeness — per-step gaps

### 3.1 Migrated turn types (only steps with at least one missing/malformed field)

#### BIP

| Step | Field path | Issue | File:line |
|---|---|---|---|
| Step 1 (SF→rim walk) | `start.action[sf_id]` | `build_walk_up_step` defaults to `"handle_ball"` while `start.ball` overridden to `BallLoose @ rim` — contradictory semantics for `handle_ball` with no owner | [transition_bridge.py:1046-1064](../../BackEnd/utils/transition_bridge.py#L1046-L1064) |

All other BIP steps populate required §3.1/§3.2 fields. Ownership stamp lives outside step schema per §6.2 (not on step level).

#### SIP

No per-step gaps. Same `handle_ball`-while-loose pattern in step 1 as BIP.

#### HCT (dynamic)

| Step | Field path | Issue | File:line |
|---|---|---|---|
| Step 3 (attack) | `end.next` | `_resolve_final_step_next` only branches on `DEAD_BALL_TURNOVER` and HCO continuation. **No `turn_stop` event branch for STEAL / FOUL / SHOT_ATTEMPT** even though `TurnStopEvent` vocab supports them | [dynamic_hct_step_emitter.py:64-74](../../BackEnd/engine/dynamic_hct_step_emitter.py#L64-L74) |

#### HCO (skeleton)

| Step | Field path | Issue | File:line |
|---|---|---|---|
| All skeleton steps | `end.coords` | `_build_step_end_coords_with_interrupts` drops any player whose `destinations[pid] is None` from `end.coords`. **Violates §3.2 "coords required for all on-court players"** | [skeleton_step_emitter.py:373-398](../../BackEnd/engine/skeleton_step_emitter.py#L373-L398) |
| Post-shot `[bounce]` | `start.advance_trigger.T_game_seconds` | Uses `BOUNCE_STEP_GAME_SECONDS`; spec says 300ms wall-clock. Need to verify constant value matches | [skeleton_step_emitter.py:1901-1909](../../BackEnd/engine/skeleton_step_emitter.py#L1901-L1909) |

#### FCP (skeleton)

Same emitter as HCO. Stopper step `advance_trigger.condition` correctly = `player_reaches_position`.

#### OREB

| Step | Field path | Issue | File:line |
|---|---|---|---|
| Putback shoot step | `start.advance_trigger.condition` | `player_reaches_position` with shooter as target — but shooter is already AT shot spot (no motion). 0-distance gate firing immediately; T floored to `HCO_STEP_T_FLOOR`. Trigger choice technically valid but semantically odd | [oreb_step_emitter.py:284-302](../../BackEnd/engine/oreb_step_emitter.py#L284-L302) |

#### DREB

| Step | Field path | Issue | File:line |
|---|---|---|---|
| Single step | (no announcement) | DREB emitter emits NO `announcement` field on any step. Coverage of DREB-as-own-turn limited to HCT/HCO/CR-FB MISS — see §2.7 surprising violation | [dreb_step_emitter.py:189-203](../../BackEnd/engine/dreb_step_emitter.py#L189-L203) |

#### Fast Break — Covert Release

| Step | Field path | Issue | File:line |
|---|---|---|---|
| Multiple sites | inline | Non-vocab `"normal"` archetype passed to `_ag_grid_per_game_sec`; resolves to `STANDARD` in lookup helper. Cosmetic | [covert_release_step_emitter.py:757, 799, 1050](../../BackEnd/engine/covert_release_step_emitter.py#L757-L1050) |

*(`sprint` on shoot step withdrawn per §4.1 decision 4 — FB shoot uses `sprint` deliberately.)*

#### Fast Break — Rim Runner

No per-step gaps. *(`sprint` on shoot step withdrawn per §4.1 decision 4.)*

#### Fast Break — Triangle

No per-step gaps. *(`sprint` on shoot step withdrawn per §4.1 decision 4.)*

#### Free Throw

| Step | Field path | Issue | File:line |
|---|---|---|---|
| Step 1 shoot | `start.advance_trigger.condition` | `fixed_duration` w/ T=0.35 — skeleton-emitter shoot step uses `player_reaches_position`. Inconsistent | [ft_step_emitter.py:215-219](../../BackEnd/engine/ft_step_emitter.py#L215-L219) |
| Step 3 hold (make) | `start.advance_trigger.condition` | `shot_resolved` w/ T=0.05 — **UESS §3.3 + Step_By_Step §Hold say `fixed_duration` w/ T=0 + announcement drives wall-clock**. Also lacks `step.start.announcement` for "It's Good!" beat. Skeleton emitter wires it correctly via `_build_make_hold_sub_step`; FT emitter does not | [ft_step_emitter.py:441-451](../../BackEnd/engine/ft_step_emitter.py#L441-L451) |
| Step 4 bounce (final miss) | `start.advance_trigger.condition` | `shot_resolved` via `_ball_motion_step` — **§Bounce says `fixed_duration` w/ T=300ms** | [ft_step_emitter.py:494-501, 257-261](../../BackEnd/engine/ft_step_emitter.py#L494-L501) |

#### Opening Tip

Does NOT emit `animation_steps[]`. Granular gap inventory:

| Step | Missing required fields |
|---|---|
| Step 1 (Jump Ball) | `coords`, `destination`, `action` (uses non-vocab `TIP_JUMP`/`CONVERGE_ON_BALL`), `archetype`, `ball`, `clock`, `advance_trigger`, `end.coords`, `end.ball`, `end.time_elapsed`, `end.clock`, `end.next` |
| Step 2 (Resolution) | All of the above |

### 3.2 Un-migrated turn types (granular per-step gap inventory)

All steps below are missing every required UESS §3.1 / §3.2 field: `start.{coords, destination, action, archetype, ball, clock, advance_trigger}` and `end.{coords, ball, time_elapsed, clock, next}`.

#### Fast Break — After Steal

**Resolved (May 2026):** migrated. `after_steal_fast_break_step_emitter.py` emits schema steps (drive step + skeleton post-shot chain). The gap inventory below no longer applies.

#### Timeout

Step_By_Step inventory unspecified ("minimal animation"). Source: turn_manager.py:3349-3424; `time_elapsed: 0`, no step list.

| Step | Status |
|---|---|
| Step 1 (Timeout idle / lineup-swap freeze) | All §3.1/§3.2 fields absent |

#### Final Shot

UESS §2 says Not migrated; code routes through `_emit_hco_animation_steps`. Inherits HCO skeleton gaps in §3.1 above. Step_By_Step §Final Shot section is empty (header only), so canonical step inventory is undefined.

---

## 4. Schema gaps — decisions (all resolved)

### 4.1 Closed-vocab + schema shape

| # | Decision | Scope / file |
|---|---|---|
| 1 | `metadata` minimum: `{reason: string}` mandatory everywhere. `target_player_id` + `target_coords` mandatory for `player_reaches_position` and `ball_reaches_player`. `kind` mandatory for variant `fixed_duration` sub-steps. FT bounce extra keys (`free_throw_shot`, `ball_grid_per_game_second`, `result`) are FT-specific telemetry — keep. | Update UESS §3.1 metadata spec; emitter audit to backfill missing keys |
| 4 | `sprint` IS the FB shoot archetype (deliberate — FB shooter is mid-sprint). Withdraw the audit's "wrong archetype" finding for [covert_release_step_emitter.py:698](../../BackEnd/engine/covert_release_step_emitter.py#L698), [rim_runner_step_emitter.py:908](../../BackEnd/engine/rim_runner_step_emitter.py#L908), [triangle_step_emitter.py:514](../../BackEnd/engine/triangle_step_emitter.py#L514). | Update UESS §3.3 — non-FB shoot stays `shot_motion`; FB shoot uses `sprint` |
| 5 | FT make-hold → switch to `_build_make_hold_sub_step` shape (`fixed_duration` T=0; `announcement.hold_ms` drives wall-clock; "It's Good!" beat). **Preserve the 1000ms hold per prior-incident memory** — that one was lost in a prior turn-type migration. | [ft_step_emitter.py:441-451](../../BackEnd/engine/ft_step_emitter.py#L441-L451) |
| 6 | FT final-miss bounce → switch to `fixed_duration` T=300ms. | [ft_step_emitter.py:494-501](../../BackEnd/engine/ft_step_emitter.py#L494-L501) |
| 10 | Skeleton `end.coords` for stationary players: carry start→end (copy start). Satisfies §3.2 "coords required for all on-court players." | [skeleton_step_emitter.py:373-398](../../BackEnd/engine/skeleton_step_emitter.py#L373-L398) |
| 11 | `build_walk_up_step` stationary destinations: switch from `dict(start_coord)` to `None` (matches UESS §3.1 "null = stationary"). **Verify consumers (`_interpolate_step_end`, FE tween logic, schema validators) don't break on `None`** during implementation. | [transition_bridge.py:248-260](../../BackEnd/utils/transition_bridge.py#L248-L260) |
| 12 | BIP/SIP step 1 (alignment) SF action: **`cut`** (not `handle_ball`). Ball stays `BallLoose` at step 1 start; `BallAttached(SF)` at step 1 end. Step 2 SF action stays `pass`. | [transition_bridge.py:1046-1064](../../BackEnd/utils/transition_bridge.py#L1046-L1064) + SIP analogue |
| 16 | Add getback↔release exclusivity check to `canonicalize_post_shot_overlays`. | [shared.py:2773-2797](../../BackEnd/utils/shared.py#L2773-L2797) |
| 17 | OREB Kickout other-8: assign random destinations within 6-grid Euclidean of start (so they have visible motion). Small helper needed. | [oreb_step_emitter.py](../../BackEnd/engine/oreb_step_emitter.py) |

### 4.2 Migration status — UESS §2 doc updates

| # | Decision |
|---|---|
| 2 | **Opening Tip — actually migrate.** Build `opening_tip_step_emitter.py` modeled on `build_bip_animation_steps`. Two steps (Jump Ball + Resolution) per Step_By_Step. Likely needs a new vocab action (e.g. `jump_ball`) — current code uses non-vocab `TIP_JUMP`/`CONVERGE_ON_BALL`. Until built, UESS §2 row stays "Not migrated." |
| 3 | **Final Shot — mark as Migrated.** Code already routes through `_emit_hco_animation_steps` (commit `b4fc67bf2`). Update UESS §2 row. Note that `time_elapsed = int(time_remaining)` ([phase_resolution.py:4289](../../BackEnd/engine/phase_resolution.py#L4289)) is intentional quarter-clock drain — outside ledger by design. |
| 7 | Dynamic HCT: wire `_resolve_final_step_next` for STEAL / FOUL / SHOT_ATTEMPT capacity now (future-proof; branches not exercised yet but emitter must support them). | [dynamic_hct_step_emitter.py:64-74](../../BackEnd/engine/dynamic_hct_step_emitter.py#L64-L74) |
| 8 | Extend `_build_dreb_turn_from_miss` to all MISS/BLOCK DREB sources; FCP is now covered. Continue sunsetting any remaining embedded-DREB legacy logic. | [game_manager.py:702-704](../../BackEnd/models/game_manager.py#L702-L704) |
| 9 | Static HCT path is dead — **remove**. Drop `hct_step_emitter.py` and its callers at [phase_resolution.py:7313, 7630](../../BackEnd/engine/phase_resolution.py#L7313-L7630). | — |

### 4.3 §6 / §7 contracts — build

| # | Decision |
|---|---|
| 13 | **Build `shot_state_snapshot`.** Construct in `ShotManager.resolve_shot` immediately before resolution; store at `turn_result["roles"]["shot_state_snapshot"]`; route all contest / foul / block / rebound / make-miss reads through it; emit `SHOT_COORD_DEBUG` from it on every shot; emit `NO_DEFENDER_SHOT` when `assigned_defender_count == 0`. `position_snapshot_ledger` remains as separate forensic audit machinery (different concern). |
| 14 + 15 | **Build `ownership_at_turn_start` + `ownership_commit_event` discrete fields when FE pure-renderer cleanup (remediation step 10) begins** — that's the consumer (FE will need them to attach ball at receipt, not frame-start). Until then `uess_ownership_contract` validation alone is sufficient. Extend `applicable` scope to all turn types at the same time so BIP / SIP / FT / DREB / OREB / Opening Tip / Timeout / force-foul stop being skipped. |

---

## 5. Bug → root cause map

| Bug | Candidate cause(s) | Invariant | File:line | Shared with | Confidence |
|---|---|---|---|---|---|
| 1. Quick HCO passes teleporting | Step T floored to `HCO_STEP_T_FLOOR_GAME_SECONDS=0.5` causes natural_t≤T snap-to-target; FE schema path lacks `clampGridCoords` | 5 partial / Logic gap | [skeleton_step_emitter.py:1049](../../BackEnd/engine/skeleton_step_emitter.py#L1049), [animationPlayback.js:766-773](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L766-L773) | 6, 16 | medium |
| 2. Announcements not consistently executing | `runShotAttempt` short-circuits on `schema_rendered_arc:true` ("intentionally skipped — followup task"); DREB schema emits no `announcement` field; `runFoul` unimplemented | 7 / Logic gap | [animationPlayback.js:907, 966-969, 972-975](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L907-L975), [dreb_step_emitter.py:205-237](../../BackEnd/engine/dreb_step_emitter.py#L205-L237) | 4, 11, 17 | high |
| 3. Secondary swish SFX not triggering on Bank/Rim makes | `timed_sfx` cues scheduled via `scene.time.delayedCall` may not survive step advance (race); secondary swish is via `timed_sfx`, primary via `sfx_on_ball_arrival` | None — logic/timing | [animation_step_helpers.py:426-454](../../BackEnd/utils/animation_step_helpers.py#L426-L454), [animationPlayback.js:635-654](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L635-L654) | — | medium |
| 4. Blocks not executing properly | `_variant_flight_end` falls back to MSSS/rim when `shot_variant` None (BLOCK skips `select_shot_variant`) so ball flies to rim not block_spot; legacy `_getShotFlightTargetGrid` handles BLOCK correctly. Block announcement skipped by schema-path short-circuit | 6 partial / Logic gap | [skeleton_step_emitter.py:1599-1601](../../BackEnd/engine/skeleton_step_emitter.py#L1599-L1601), [shot_manager.py:1932-1934](../../BackEnd/models/shot_manager.py#L1932-L1934), [ShotAnimationSystem.js:2186-2189, 1229](../../FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js#L1229-L2189) | 2, 11 | high |
| 5. HCO skeleton steps not animating consistently | `_build_step_end_coords_with_interrupts` interrupts non-gate movers; if gate has natural_t < T floor, others interrupted prematurely. `_slowest_among` returns None on stationary offense steps → fallback advance_trigger | 5 partial | [skeleton_step_emitter.py:373-398, 324-344, 1095](../../BackEnd/engine/skeleton_step_emitter.py#L324-L1095) | 9 | medium |
| 6. We need clamping | Schema-path `playAnimationStep` writes `step.end.coords` directly without `clampGridCoords`; legacy `animateStep.js:111` + `turnAnimation.js:3043` apply visual safe area (5–95, 2–49) | 1 (FE-side workaround) | [animationPlayback.js:766-773](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L766-L773), [courtClamp.js](../../FrontEnd/static/js/phaser/animation/courtClamp.js) | — | high |
| 7. DREB→HCO jetting/teleport | HCO entry orchestrator's Handoff uses `_HCO_LANE_DRIFT_SPOTS` (random spots) as drift targets — distinct from actual setup_coords; walk-up step T floor 1.5s with single-player gate, defenders interrupted short; large traversal in walk-up reads as jet | 5 | [transition_bridge.py:48-58, 495](../../BackEnd/utils/transition_bridge.py#L48-L495), [skeleton_step_emitter.py:744-877, 862](../../BackEnd/engine/skeleton_step_emitter.py#L744-L877) | 12, 13 | high |
| 8. Defenders moving before pass on HCO steps with a pass | Skeleton emitter has no concept of pre/post-pass within a single step. Defender tween_durations from `_ag_grid_per_game_sec` — start at step start in parallel with ball. No backend gate forces defenders to wait | 1 (BE should express pre-pass holds) | [skeleton_step_emitter.py:1145, 1170](../../BackEnd/engine/skeleton_step_emitter.py#L1145-L1170), [animationPlayback.js:664-719](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L664-L719) | 9 | medium |
| 9. Some but not all HCO skeleton steps teleporting defenders | `_build_step_end_coords_with_interrupts` excludes players with `destinations.get(pid) is None`; `_coords_at_movement_index` skips players whose movement array is too short → defender excluded from `final_end_coords` → FE never tweens, next step's `start.coords` differs → snap | 3 (root cause is §8.1 violation — see invariant 3 finding) | [skeleton_step_emitter.py:373-398, 139](../../BackEnd/engine/skeleton_step_emitter.py#L139-L398) | 5 | high |
| 10. Made FB shots not resolving on Rim Sweet Spot | `rim_runner_step_emitter._build_shot_motion_step` returns `turn_stop: SHOT_ATTEMPT` WITHOUT `schema_rendered_arc:True`. Falls back to FE legacy `runShotAttempt`. **RR/Triangle/CR FB emitters do NOT build variant-aware `[ball_flight]`/`[hold]`/`[bounce]` sub-steps** — only skeleton emitter does | 7 (FB emitters missing schema-pure post-shot path) | [rim_runner_step_emitter.py:715-739, 972](../../BackEnd/engine/rim_runner_step_emitter.py#L715-L972), [animationPlayback.js:894-970](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L894-L970) | — | medium |
| 11. Announcements not triggering on Shooting Fouls | Same as bug 2 — `runShotAttempt` skip; `runFoul` unimplemented; schema `[hold]` has "It's Good! And 1!" text but no FOUL_SHOOTING card; `_resolve_final_step_next` maps FOUL → `turn_stop: FOUL`, FE handler missing | None — handler incomplete | [animationPlayback.js:907, 972-975](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L907-L975), [skeleton_step_emitter.py:550-559, 1509](../../BackEnd/engine/skeleton_step_emitter.py#L550-L1509), [ShotAnimationSystem.js:1162, 1245-1257](../../FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js#L1162-L1257) | 2, 17 | high |
| 12. OREB→DREB→HCO transitions broken / DREB→HCO skips handoff + walk-up | Same root as bug 7. HCO entry orchestrator fires correctly; Handoff drift-spots → setup_coords transition in walk-up reads as teleport. Step T floor exposes long-distance defenders as snapping | 5, 7 | [transition_bridge.py:48-58, 495](../../BackEnd/utils/transition_bridge.py#L48-L495), [skeleton_step_emitter.py:744-877](../../BackEnd/engine/skeleton_step_emitter.py#L744-L877) | 7, 13 | high |
| 13. SIP→HCO transition broken, teleporting | Same mechanism as bug 7. SIP setup-coords ≈ midcourt; walk-up gates only BH; defender interrupted short of HCO setup → skeleton step 0 sees mismatch | 5 | [skeleton_step_emitter.py:744-877, 905-906](../../BackEnd/engine/skeleton_step_emitter.py#L744-L906) | 7, 12 | medium |
| 14. Handoff+walk-up after steal too fast | `_build_handoff_converge_substep` step T = `max(0.1, dist/rate)`; for 10-grid PG converge at AG=50 sprint (18), T≈0.56s. Whole post-steal entry ~2s. `reset_step_helper.build_reset_steps` exists with steal mention in docstring but is NOT invoked from skeleton emitter — orchestrator uses regular handoff path | 7 (After-Steal not migrated) / Logic | [transition_bridge.py:513](../../BackEnd/utils/transition_bridge.py#L513), [reset_step_helper.py:18](../../BackEnd/utils/reset_step_helper.py#L18) | — | high |
| 15. RR FB not reading geography — hold-up with open path | `rim_runner_fast_break.py:961-963` computes `fb_open`; `_primary_burst_defender` looks only at `getback_ids`. `correct_read = read_score > read_threshold` (PG IQ). Low-IQ PG misreads open break → hold-up. Backend `fb_open` is correct; PG IQ gate forces hold-up | None — IQ-gated game logic | [rim_runner_fast_break.py:942, 961-981, 1065](../../BackEnd/engine/rim_runner_fast_break.py#L942-L1065) | — | high |
| 16. Some players teleporting on shot attempts in HCO | When orchestrator does NOT fire (BH already at step 0 BH in front-court), step 0 uses animator coords for ALL players including defenders whose actual sprite position is from prior-turn-end (not animator). Defenders snap before tween. `_apply_overlay_motion_to_shoot_step` writes overlay player end_coords AFTER end_coords computed → overlay mismatches | 3 (root §8.1 violation), 5 | [skeleton_step_emitter.py:905-906, 1340-1375, 1054, 1692](../../BackEnd/engine/skeleton_step_emitter.py#L905-L1692) | 1, 9 | high |
| 17. Not announcing all DREBs | DREB schema emitter emits no `announcement` field; `_maybeRunDiscreteDrebOutletLeadIn` does not call `announceReboundHeadlineIfNeeded`. Embedded-DREB legacy path DOES call it → inconsistent | 7 | [dreb_step_emitter.py:205-237](../../BackEnd/engine/dreb_step_emitter.py#L205-L237), [AnimationEngine.js:609-732](../../FrontEnd/static/js/phaser/animation/AnimationEngine.js#L609-L732), [ReboundAnimationSystem.js:147](../../FrontEnd/static/js/phaser/animation/ReboundAnimationSystem.js#L147) | 2 | high |
| 18. Steal→FB Make: inbound passer for BIP jets | After-Steal FB not migrated; legacy `fastBreak.js` emitter doesn't populate post-make `player.coords` the same way schema emitters do. SF (new inbound passer) `prior_final_coords` may be wrong → BIP step 1 distance computation off → jets | 7 (After-Steal not migrated) | [phase_resolution.py:991-1944](../../BackEnd/engine/phase_resolution.py#L991-L1944), [transition_bridge.py:978-1129](../../BackEnd/utils/transition_bridge.py#L978-L1129), [turn_manager.py:1036-1064](../../BackEnd/models/turn_manager.py#L1036-L1064) | — | medium |
| 19. Teleporting on rebound step or get-into-rebound-position overlay during shot/bounce | Overlay players (offense/defense rebounder, getback, release) get interrupted positions via `_apply_overlay_motion_to_shoot_step` AFTER end_coords are computed; if their prior-step end ≠ overlay-rewritten end, sprite snaps. Compounded by §8.1 step-chain (now fixed in remediation item 1) when overlay step is N≥1. Also possible: overlay map fields missing for some players on the turn result | 5 (overlay authority), 3 (§8.1) | [skeleton_step_emitter.py:1340-1375, 1692](../../BackEnd/engine/skeleton_step_emitter.py#L1340-L1692), [shot_manager.py:2048-2052, 2596-2600](../../BackEnd/models/shot_manager.py#L2048-L2600) | 16, 20 | medium |
| 20. Some HCO shots: rebound overlay not animating | Overlay maps not populated for the affected shot (per audit §2.5.1 — early-return paths in `resolve_shot` skip `canonicalize_post_shot_overlays`: 792, 865, 969, 1554, 1728). OR: overlay players excluded by `_apply_overlay_motion_to_shoot_step` filter. Compounded by FE legacy paths (`ShotAnimationSystem.js:945-1039`) NOT reading `offense_rebounder_coords`/`defense_rebounder_coords` (grep returns 0 hits in FE) | 5 (overlay authority) | [shot_manager.py:792, 865, 969, 1554, 1728](../../BackEnd/models/shot_manager.py#L792-L1728), [ShotAnimationSystem.js:945-1039](../../FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js#L945-L1039) | 19 | medium |
| 21. Made/missed shot SFX not perfectly synced to ball reaching rim | `timed_sfx` cues scheduled via `scene.time.delayedCall` with fixed `delay_ms` (100/150ms) at `[ball_flight]` step start, but the actual ball-tween wall-clock duration depends on grid distance and `SHOT_BALL_MIN_WALL_CLOCK_MS=400`. If step T < tween wall-clock, the step advances before the tween completes → arrival SFX fires from step transition, not from tween completion. Variant chain SFX (per-hop, settle) compounds the drift | 7 (FB lacks schema post-shot sub-steps; rim/bank cues affected) / Logic gap | [animation_step_helpers.py:426-454](../../BackEnd/utils/animation_step_helpers.py#L426-L454), [animationPlayback.js:635-654](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L635-L654), [animationPlayback.js:332](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L332) | 3 | high |

### 5.1 Shared root-cause clusters

- **Cluster A — Schema-path skips legacy announcements/SFX**: bugs 2, 4 (BLOCK), 11, 17. Root: `runShotAttempt` short-circuits on `schema_rendered_arc:true`; `runFoul` unimplemented; emitters don't stamp `announcement` for REBOUND/BLOCK/FOUL_SHOOTING. Code comment at animationPlayback.js:966-969 calls it "Followup task".
- **Cluster B — HCO entry orchestrator handoff/walk-up step T + lane-target mismatch**: bugs 7, 12, 13, 16. Root: `build_handoff_step` uses `_HCO_LANE_DRIFT_SPOTS` (random) for non-key drift; `build_walk_up_step` step T floor 1.5s with single-player gate; skeleton loop only seeds step 0 from prior entry steps when `reset_count > 0`.
- **Cluster C — Schema engine lacks visual coord clamping**: bugs 1, 6 (contributing to 7, 13, 16). `playAnimationStep` writes `step.end.coords` directly to sprites without `clampGridCoords`. Only legacy paths apply the FE visual safe area.
- **Cluster D — FB shot path bypasses schema post-shot sub-steps**: bugs 3, 10. RR/Triangle/CR don't emit `[ball_flight]`/`[hold]`/`[bounce]` schema sub-steps with variant-aware MSSS + `timed_sfx`.
- **Cluster E — Animator step-array gaps cause defender teleports**: bugs 5, 9, 16. Root cause is the §8.1 violation in skeleton emitter (`start.coords` from `animations[]` not from prior step end).

### 5.2 Hypothesis check — legacy-vs-UESS split

- **Trace cleanly to invariant violations** (legacy/UESS conflict): **9 bugs** — 2, 7, 9, 11, 12, 13, 16, 17, 18.
- **Logic gaps adjacent to invariants** (post-migration emitter incompleteness): **5 bugs** — 1, 4, 5, 8, 10.
- **Independent logic errors** (no invariant fit): **4 bugs** — 3, 6, 14, 15.
- **Verdict**: The "legacy lingering causing inconsistencies" hypothesis holds for ~half the list (9/18). Of the remaining 9, 5 are post-migration emitter-completeness gaps (announcements/SFX/clamping) and 4 are unrelated game-logic bugs. The migration IS the primary failure surface, but it is not the whole story.

---

## 6. Recommended remediation order

Sequenced by what unblocks the most + what is safest to cut first. Each item is **what to do** and **why now**, not implementation detail. All §4 decisions baked in.

1. **Fix §8.1 step-chain in skeleton emitter** ([skeleton_step_emitter.py:916-917](../../BackEnd/engine/skeleton_step_emitter.py#L916-L917)). Change loop body so `start_coords = dict(steps[-1]["end"]["coords"])` for i≥1. **This single fix is the root of cluster B teleports (bugs 5, 7, 9, 12, 13, 16) — largest payoff per line.** Safe: only re-routes step-start sourcing. **Audit `MAKE_HOLD_MS=1000` and 1.5s walk-up beats before shipping** per migration-feel memory.

2. **Fix `_HCO_LANE_DRIFT_SPOTS` mismatch in Handoff** ([transition_bridge.py:48-58, 495](../../BackEnd/utils/transition_bridge.py#L48-L495)). Either drift to actual `setup_coords` directly or align Handoff/Walk-up so the transition is continuous. **Knocks out the remaining cluster B teleports** (DREB→HCO, SIP→HCO, OREB→DREB→HCO). Audit hold/pause/SFX beats before shipping.

3. **Stamp schema announcements for cluster A** (DREB header, REBOUND, BLOCK, FOUL_SHOOTING, And-1). Emit on the relevant schema step's `start.announcement` / `end.announcement`. Remove `schema_rendered_arc:true` short-circuit in `runShotAttempt` once schema-side announcements exist. **Restores user-visible regressions** (bugs 2, 4, 11, 17). **Preserve the 1000ms make-hold beat** per memory note — that one was lost in a prior turn-type migration.

4. **Add schema-pure post-shot sub-steps to FB emitters** (RR/Triangle/CR). Mirror `skeleton_step_emitter._build_post_shot_sub_steps`: emit `[shoot]`/`[ball_flight]`/`[hold]`/`[bounce]` with variant-aware MSSS and `timed_sfx`. Use `sprint` archetype on shoot step per §4.1 decision 4. **Fixes bugs 3 + 10 and unifies the post-shot schema across HCO/FCP/OREB/FB**, letting the cluster A fix apply uniformly.

5. **Backend visual clamping in the emitter output** (so FE `courtClamp.js` becomes unnecessary). **Bug 6.** Avoid FE clamp — duplicates the §1 violation pattern.

6. **Schema-shape backfills (§4.1 decisions)** — bundle into one PR:
   - FT make-hold → `_build_make_hold_sub_step` shape (decision 5)
   - FT bounce → `fixed_duration` T=300ms (decision 6)
   - Skeleton `end.coords` for stationary players (decision 10)
   - `build_walk_up_step` stationary destinations → `None` (decision 11; verify consumers first)
   - BIP/SIP step 1 SF action → `cut` (decision 12)
   - `canonicalize_post_shot_overlays` getback↔release exclusivity (decision 16)
   - OREB Kickout other-8 random destinations (decision 17)
   - Dynamic HCT `_resolve_final_step_next` STEAL/FOUL/SHOT_ATTEMPT branches (decision 7)
   - `advance_trigger.metadata` minimum-key backfill (decision 1)

7. **Replace 14 `apply_coords_from_animations_list` mid-resolution calls with proper §8.2 sync at end of turn** (shared.py:2874-2902 + 14 call sites). Load-bearing legacy that lets shot snapshots read pre-skeleton coords. **Foundational fix; precondition for item 9 (`shot_state_snapshot` build).** High effort.

8. **Tighten clock authority**: start with [dynamic_hct_step_emitter.py:386-388](../../BackEnd/engine/dynamic_hct_step_emitter.py#L386-L388) — the cleanest §5.4 violation. Then fix the `_compute_real_time_elapsed_ms` ordering bug (turn_manager.py:212) so `real_time_elapsed_ms` reads the ledger value, not the legacy sum. **Safe-ish: ledger already overwrites the final value; this removes the redundant pre-write.**

9. **Build `shot_state_snapshot` (§4.3 decision 13)**. Construct in `ShotManager.resolve_shot`, store at `turn_result["roles"]["shot_state_snapshot"]`, route all contest/foul/block/rebound reads through it, emit `SHOT_COORD_DEBUG` + `NO_DEFENDER_SHOT`. **Largest single change**; do after item 7 stabilizes.

10. **Migrate Opening Tip (§4.2 decision 2)**. Build `opening_tip_step_emitter.py` modeled on `build_bip_animation_steps`. Two steps (Jump Ball + Resolution). Add `jump_ball` to PlayerAction vocab (UESS §3.3). Update UESS §2 row to "Migrated."

11. **Migrate After-Steal FB to a step emitter** (currently legacy `fastBreak.js`). Resolves bug 18; removes the last `animations[]`-only FB path. **Audit hold/pause/announcement/SFX beats from current legacy execution before shipping** per migration-feel memory.

12. **Extend `_build_dreb_turn_from_miss` (§4.2 decision 8)** to all MISS/BLOCK DREB sources; FCP is covered. Continue validating RR / Triangle / After-Steal and sunset embedded-DREB where still present.

13. **FE pure-renderer cleanup** (cluster of ~46 violations). Dominant patterns: (a) BallController as FE ownership authority → replace by consuming `ownership_commit_event` (per §4.3 decision 14+15, build the discrete fields when this item starts); (b) FE clock-tween + pause logic in AnimationRouter → replace by passive rendering of backend ledger state; (c) FE `Phaser.Math.Between`/`Math.random` for sparse-payload fallbacks → replace by mandatory backend positions + hard FE error when payload incomplete. **Largest blast radius; do last.** Most legacy FE paths can run in parallel while schema path matures.

14. **§6.2 ownership coverage extension** (§4.3 decision 14+15). Build `ownership_at_turn_start` + `ownership_commit_event` discrete fields; extend `uess_ownership_contract` `applicable` scope to all turn types (BIP, SIP, FT, DREB, OREB, Opening Tip, Timeout, force-foul). **Pair with item 13 since FE is the consumer.**

15. **Remove static HCT path (§4.2 decision 9)** — drop `hct_step_emitter.py` + callers at [phase_resolution.py:7313, 7630](../../BackEnd/engine/phase_resolution.py#L7313-L7630). Pure deletion, no replacement.

16. **Cut dead FE code** (`HCOAnimationSystem.js` likely dead, `possession/` runner gated off). Verify no callers, then remove. **Reduces audit surface for future migrations.**

17. **Update UESS spec docs to reflect decisions**:
    - §2: Final Shot → Migrated; DREB row should enumerate promoted paths; Opening Tip stays "Not migrated" until item 10
    - §3.1: `metadata` minimum-key requirements per trigger condition (decision 1)
    - §3.3: PlayerAction vocab adds `jump_ball` if item 10 takes that path; document FB shoot uses `sprint` (decision 4)
    - §6.2: align field names with `uess_ownership_contract` + the new discrete fields (when item 14 ships)
    - §7: document `shot_state_snapshot` build site + field list once item 9 ships

---

## 7. Open questions / things still requiring runtime investigation

(Items previously listed here that you've already answered — static HCT path live, opening tip status, etc. — are now in §4. What remains is things needing actual runtime observation or app execution to confirm.)

1. **HCOAnimationSystem.js live caller?** Imported and instantiated in AnimationEngine.js:2011; `executeHCOOutletPassStep`/`processHCO` exist in AnimationRouter; no production caller found. Likely dead but still wired. **Verify with runtime trace before cutting in remediation item 16.**
2. **`runShotAttempt` double-hold risk?** ShotAnimationSystem.js:1118-1186 imposes 1000ms made-shot hold; `_build_make_hold_sub_step` (skeleton_step_emitter.py:1471) emits the same `MAKE_HOLD_MS=1000.0`. Critical to disambiguate before remediation step 3 ships (prior incident per migration-feel memory). **Needs runtime check on a UESS-migrated HCO MAKE to see whether both fire.**
3. **`real_time_elapsed_ms` ordering bug visible in production?** Pre-ledger value reaches FE wall-clock duration. Visible drift would require running and comparing legacy-vs-ledger deltas across many turns.
4. **Opening Tip clock-ledger coverage** — could not trace whether OT routes through `_attach_clock_contract`. Will be moot once remediation item 10 (Opening Tip migration) ships.
5. **`fastBreak.js` After-Steal vs. CR/RR/Triangle reachability** — `runFastBreakSequence` is shared. Bug 18 assumes legacy path fires for After-Steal. Confirm with runtime trace.
6. **Legacy FE rebounder/release/getback random tweens actually rendered?** Unconditional guards like `turnData.offense_getback && ...` would fire for any FB/HCO MISS. If schema emitter sets sprite positions first, subsequent random tweens may move sprites AWAY from correct destination. **Visible effect requires running the app.** Per migration-feel memory: this is the kind of regression that loses beats.
7. **DREB schema turn defender coverage?** `build_dreb_animation_steps` iterates both lineups via `_player_iter`. Could not verify every `pid` flows through `start_coords`/`coords_end` in every scenario.
8. **Bug 3 SFX cancellation?** Whether `scene.time.delayedCall` for `timed_sfx` survives step advance — needs runtime test.
9. **Bug 14 STEAL→HCO Reset?** `build_reset_steps` exists with steal mention in docstring; no grep hit shows it being called from `skeleton_step_emitter`. Orchestrator path used instead. Intentional, or should Reset wrap the steal→HCO seam?
10. **Bug 1 root cause** — step T floor vs animator-coord mismatch — both candidates plausible; runtime trace needed to disambiguate before remediation item 1 ships.
11. **HCT outlet_passer role?** HCT has no outlet_passer concept; lack of re-`canonicalize_post_shot_overlays` in `hct_step_emitter` plausibly intentional but asymmetric with covert_release/rim_runner. Confirm scope.
