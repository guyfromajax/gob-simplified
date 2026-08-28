# UESS System

The **Universal End-State Sync (UESS)** system is the contract by which every turn type executes consistently across backend and frontend.

---

## 1. Purpose

- Backend owns all game logic: step/turn results, player coords + actions, ball state, clock state.
- **Single coord source.** Game logic and frontend rendering derive from the *same* real-time coords the UESS emitters produce. Logic must never read a parallel positioning source (live `roles`, ad-hoc `shooter.coords`, `def_lineup` re-derivation) that can drift from the emitted step coords. Where legacy logic still does, that is a **known violation under remediation** (§7), not sanctioned behavior.
- Frontend is a pure renderer of backend-emitted payloads (not yet true on all paths — see §12).
- Every turn type emits the same `AnimationStep[]` schema, regardless of internal complexity.

This doc is the single source of truth for the contract. Code is the implementation; if they disagree, the code is right and this doc is wrong.

### 1.1 Display-oriented coordinate contract

- Gameplay grid space is `x=0..100`, `y=0..50`, with midcourt at `x=50`.
- Runtime `Player.coords`, position snapshots, payload destinations, and schema
  endpoints use final display orientation.
- Reusable backend templates may be authored for home offense, but the backend
  applies horizontal court orientation before emission with
  `x_away = 100 - x_home`; that horizontal mirror leaves the selected point's
  y unchanged. Thus rims mirror `91 <-> 9`, baselines `3 <-> 97`, and midcourt
  remains 50. A resolver may still intentionally choose a different named
  upper/lower spot; that selection is separate from orientation conversion.
- Payload consumers must not infer orientation from team identity. The frontend
  converts grid coordinates to pixels but must not mirror, randomize, replace,
  or otherwise reinterpret gameplay destinations.
- Missing backend coordinates fail closed on migrated paths. A legacy renderer
  may retain fallback behavior only while that renderer itself remains an
  explicitly tracked compatibility path.

Final Turn alignment, BIP, SIP, OREB kickout, and migrated schema shot paths
follow this contract. Remaining legacy exceptions are cataloged in
[`UESS_Backlog.md`](../projects/UESS_Backlog.md) under coordinate-orientation
cleanup.

---

## 2. Migration state

| Turn type | Status | Emitter |
|---|---|---|
| Opening Tip | ⏳ Not migrated | Legacy `animations[]` with non-vocab actions (`TIP_JUMP`, `CONVERGE_ON_BALL`); `opening_tip_step_emitter.py` not built — see backlog item 10 |
| BIP | ✅ Migrated | `transition_bridge.build_bip_animation_steps` |
| SIP | ✅ Migrated | `transition_bridge.build_sip_animation_steps` |
| HCT (dynamic) | ✅ Migrated | `dynamic_hct_step_emitter.build_dynamic_hct_animation_steps` |
| Fast Break — Covert Release | ✅ Migrated | `covert_release_step_emitter` |
| Fast Break — Rim Runner | ✅ Migrated | `rim_runner_step_emitter` |
| DREB (rebound capture) | ✅ Migrated | `dreb_step_emitter` (discrete DREB rows are promoted after HCO/HCT/FCP MISS/BLOCK, final-FT DREB, OREB putback miss → DREB, and migrated Fast Break MISS/BLOCK paths; DREB Over The Back fouls resolve inside this row and emit `turn_stop: FOUL`) |
| HCO | ✅ Migrated | `skeleton_step_emitter` (schema + universal entry orchestrator; natural-travel-time step T) |
| FCP (dynamic) | ✅ Migrated | `dynamic_fcp_step_emitter` wrapper over the shared dynamic HCT emitter; legacy/non-dynamic payloads retain the skeleton fallback |
| OREB (putback / kickout) | ✅ Migrated | `oreb_step_emitter` (branches by `result_type`: KICKOUT reuses `build_kickout_step`; PUTBACK_MAKE/MISS reuse `[shoot]/[ball_flight]/[hold]/[bounce]` builders; PUTBACK_MISS second rebound is dispatched as a separate DREB turn via the extended `_build_dreb_turn_from_miss` trigger) |
| Fast Break — Triangle | ✅ Migrated | `triangle_step_emitter` (shares burst/outlet with RR) |
| Fast Break — After Steal | ✅ Migrated | `after_steal_fast_break_step_emitter.build_after_steal_fast_break_animation_steps` |
| Free Throw | ✅ Migrated | `ft_step_emitter.build_ft_animation_steps` |
| Timeout | ⏳ Not migrated (low priority — minimal animation) | — |
| Final Shot | ✅ Migrated | Routes through `turn_manager._emit_hco_animation_steps` → `build_skeleton_animation_steps` (shared with HCO). Frontend renders the **full** ``animation_steps[]`` via `playTurn()` (no step-0 skip or parallel alignment tween). Empty emit stamps `eoq_schema_emit_failed` (fail closed for MAKE announce). Step 0 hold pacing is backend ``_step_t_floor_game_seconds`` computed backward from a **rolled anchor** (outside shoot @ 1–3s, attack drive @ 2–4s). ``time_elapsed`` derives from schema burn after emit (not a forced full-clock drain). See [`EOQ_System.md`](../06_Gameplay_Systems/EOQ_System.md) §Final Shot. |
| FLSS | ✅ Migrated | Same emitter path as Final Shot/HCO; sprint drive + shoot @ ~1s. Same empty-emit contract. Post-emit clock/quarter-end via `eoq_clock_progression.finalize_flss_post_emit`. SIP/BIP/foul→SIP arm FLSS via `schedule_flss_after_inbound` (chain-active gate). |

### 2.1 Fast Break StepState bridge

All four migrated Fast Break families also pass through the additive
`FastBreakStepState` bridge in `BackEnd/engine/fb_step_state.py`. The family
emitters currently author `AnimationStep[]`; `TurnManager` freezes those facts
into `turn_result["fb_step_states"]`, projects them back to schema, and stamps
each projected step with `_fb_step_state`. This establishes the lifecycle
`resolve -> emit -> freeze -> project -> draw` without changing gameplay or
frontend playback. Formal StepState ownership may move upstream primitive by
primitive only after projection-parity coverage is retained.

### 2.2 FCP/HCT PressureStepState bridge

Dynamic FCP and HCT share the centralized pressure emission path
`TurnManager._emit_pressure_animation_steps(...)`. The resolver's loop segments
are emitted as schema, frozen into `result["pressure_step_states"]` by
`BackEnd/engine/pressure_step_state.py`, and projected back to schema; every
projected step carries `_pressure_step_state`.

Formal projection currently covers entry/advance/pass steps, pass
interceptions, batted-OOB contact and drift (HCT/FCP natively; HCO via
`skeleton_step_emitter.append_hco_bat_oob_trajectory`, which emits the same two
steps so both turn families share one renderer), terminal steal/foul/dead-ball
steps, dead-ball fumbles, pressure-owned shot setup, and shared post-shot
beats. The remaining architectural migration is upstream ownership: individual
pressure builders still create schema first and should eventually return
formal `PressureStepState` values directly. Until that work is parity-tested,
the whole-turn projection bridge and transitional `schema_projection` snapshot
remain intentional.

---

## 3. Animation step schema

Each step is a `{start, end}` pair. Backend computes `T` (step duration in game-seconds), derives `end` from `start + T`.

Canonical source: [`BackEnd/utils/animation_step_schema.py`](../../BackEnd/utils/animation_step_schema.py). Frontend mirror: [`FrontEnd/static/js/phaser/animation/animationStepSchema.js`](../../FrontEnd/static/js/phaser/animation/animationStepSchema.js).

### 3.1 `step.start`

Required:

- `coords` — `{player_id → {x, y}}` for all on-court players
- `destination` — `{player_id → {x, y} | null}` (null = stationary)
- `action` — `{player_id → PlayerAction}` (vocab below)
- `archetype` — `{player_id → PlayerArchetype}` (vocab below)
- `ball` — one of `BallAttached`, `BallInFlight`, `BallLoose`. **Every ball state resolves to an authoritative position** (see §8.4): `BallAttached` → owner's coords (no explicit coord field), `BallInFlight` → `current_coords`, `BallLoose` → `coords`. Because `BallAttached` carries no coord of its own, an ownership change *is* a ball move and must be continuous — never a teleport (§8.4).
- `clock` — `{clock_remaining, shot_clock_remaining}` (game-seconds)
- `advance_trigger` — `{condition, T_game_seconds, metadata}`

Optional:

- `tween_durations` — `{player_id → game_seconds}`. Per-player tween override. Without it, frontend tweens for full step T (stretches fast finishers).
- `announcement` — `{text, team, hold_ms, style, ...}`. Plays before tweens fire; pauses clocks during hold.
- `ball_motion_style` — e.g. `"shot"`. Ball moves at fixed wall-clock rate independent of step T.

### 3.2 `step.end`

Required:

- `coords` — interrupted position per player: `start + rate × T` toward destination, clamped at destination.
- `ball` — `BallAttached | BallInFlight | BallLoose` at T.
- `time_elapsed` — equals `advance_trigger.T_game_seconds`.
- `clock` — state after T elapses.
- `next` — one of:
  - `{kind: "next_step", index}` — linear continuation. Index past array length ends the turn implicitly.
  - `{kind: "branch", outcome, next_step_index}` — backend-pre-resolved outcome branch.
  - `{kind: "turn_stop", event, payload}` — turn ends with a turn-stop event.

Optional:

- `announcement` — mid-turn announcement. Plays after sprites snap to end coords.

### 3.3 Frontend renderer timing invariants

For ball-motion steps, frontend playback must treat the actual ball tween completion as the visual arrival marker.

- `sfx_on_ball_release` fires when the ball detaches / tween starts.
- `sfx_on_ball_arrival` fires from the ball tween `onComplete`, not from the step timer.
- `timed_sfx` cues are scheduled relative to ball arrival, not step start.
- Step playback may wait longer than the ball tween for readability, but it must not snap / advance before the ball tween completion has fired its arrival cues.
- If the ball does not move and no tween is created, arrival SFX may fire from the step-end fallback.

This preserves main-branch shot/SFX feel while keeping backend-emitted cues authoritative.

### 3.4 Closed vocabularies

**`PlayerAction`**: `handle_ball`, `pass`, `receive`, `cut`, `screen`, `shoot`, `stationary`, `sprint`, `guard_ball`, `guard_offball`, `post_up`.

**`PlayerArchetype`** (rate at AG=50, in grid/game-sec) — **canonical tuning table**; push to [`BackEnd/constants/__init__.py`](../../BackEnd/constants/__init__.py):

| Archetype | Rate @ AG=50 | Constant | Use |
|---|---:|---|---|
| `drift` | 8 | `DRIFT_GRID_PER_GAME_SEC` | Slow off-ball relocation (HCT off-ball drift toward rim on drive/FB steps) |
| `cruise` | 13 | `CRUISE_GRID_PER_GAME_SEC` | BH bring-up, settle / transition pace |
| `shot_motion` | 14 | `SHOT_MOTION_GRID_PER_GAME_SEC` | Shooter during shot |
| `standard` | 14 | `STANDARD_GRID_PER_GAME_SEC` | Base / unaccelerated movement (AG curve anchor + fallback) |
| `sprint` | 18 | `SPRINT_GRID_PER_GAME_SEC` | Max-effort movement (walk-up non-BH, converge) |
| `burst` | 32 | `BURST_GRID_PER_GAME_SEC` | Peak explosive start (FB outlet) |
| `stationary` | 0 | — | Holds position |

Rate scales with AG via `ag_to_grid_per_game_sec` (see §9.3). Unrecognized archetype strings defensively resolve to `standard` rate.

**`TriggerCondition`**: `fixed_duration`, `ball_reaches_player`, `player_reaches_position`, `shot_resolved`, `stopper_action`. Backend pre-computes `T_game_seconds` regardless of condition.

**`TurnStopEvent`**: `SHOT_ATTEMPT`, `FOUL`, `STEAL`, `DEAD_BALL_TURNOVER`, `SHOT_CLOCK_EXPIRED`, `GAME_CLOCK_EXPIRED`, `TIMEOUT`, `JUMP_BALL`.

---

## 4. Universal step primitives

Reusable across turn types. Live in [`BackEnd/utils/transition_bridge.py`](../../BackEnd/utils/transition_bridge.py).

| Primitive | Shape | Used by |
|---|---|---|
| `build_walk_up_step` | All players move from start → end. BH dribbles. Gated on `gate_player_ids`. Non-gate movers interrupted at step T. | BIP setup walk-in, HCO entry walk-up, HCT entry walk-up |
| `build_handoff_step` | BH → PG handoff. 1-step (BH = PG hold) or 2-step (PG converge + inbound pass). | HCO entry orchestrator |
| `build_kickout_step` | BH (frontcourt) kicks back to step 0 BH. 2 sub-steps (positioning + pass). Moving players use `cruise`; passer/receiver hold stationary during the pass while the other 8 continue at `cruise`. | HCO entry orchestrator, OREB Kickout |
| `build_pass_step` | Passer + receiver stationary, ball arcs. Other 8 optionally drift. Gated on `ball_reaches_player`. | BIP inbound pass, future migrations |
| `build_bip_animation_steps` | Composer: walk-up + pass for BIP turn. | BIP |
| `build_sip_animation_steps` | Composer: walk-up + pass for SIP turn. Gates step 1 on all 10 players (no teleports). Pins clock — no game-clock burn. | SIP |

### Universal helpers ([`animation_step_helpers.py`](../../BackEnd/utils/animation_step_helpers.py))

- `build_final_coords(game)` — snapshots `player.coords` at end of every turn.
- `build_final_ball_handler_id(turn_result)` — resolves the end-of-turn BH (owner id only; the ball *position* is re-derived from that owner's coords next turn — see §8.4 invariant 4 for the `final_ball_coords` build target that would carry an explicit ball position across the turn seam).
- `stamp_tween_durations(start, end_coords, T, off_lineup, def_lineup)` — writes per-player tween durations.
- `build_foul_announcement(text, team, fouler_id, *, hold_ms=1000, style="primary", sfx_key="foul", extra_meta=None)` — canonical step-announcement dict for any foul event. Stamps `meta.sfx` so the whistle always fires at overlay mount. Use this in every UESS step emitter that emits a foul announcement; constructing the dict by hand is what caused the DREB OTB foul to ship silent (no `meta.sfx`, no whistle). Current consumers: `dreb_step_emitter` (OTB), `skeleton_step_emitter` (shooting-foul-on-miss).

Both `final_coords` and `final_ball_handler_id` are stamped unconditionally on every turn by `_append_turn` in [`game_manager.py`](../../BackEnd/models/game_manager.py). Next-turn emitters read from `prior_turn.final_coords` / `prior_turn.final_ball_handler_id`.

**SFX architecture invariant.** UESS step announcements carry their SFX via `announcement.meta.sfx` (a key resolved by [`gameSfx.js`](../../FrontEnd/static/js/phaser/utils/gameSfx.js); `"foul"` → `whistle-1-lowervol.wav` today). The frontend's `runStepAnnouncement` is deliberately not allowed to hardcode SFX by announcement text — see comment at [`animationPlayback.js:631`](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L631). All SFX wiring lives in backend emitters; `build_foul_announcement` exists to enforce that for foul-type events.

---

## 5. Clock authority contract

Active. Wired in [`turn_manager.py`](../../BackEnd/models/turn_manager.py) and [`game_manager.py`](../../BackEnd/models/game_manager.py).

### 5.1 Principle

- Unit completion controls animation progression.
- Clock authority controls game/shot clock start-stop-reset.
- `turn.time_elapsed` is **derived** from the clock event ledger, not independently tuned.
- Transition boundaries do not implicitly pause clocks.

### 5.2 Ledger event types

Every turn emits an ordered ledger:

`game_clock_start`, `game_clock_stop`, `shot_clock_start`, `shot_clock_stop`, `shot_clock_reset`, `period_end`, `basket_counted`, `possession_committed`.

### 5.3 Modes

Set via `game_state["uess_clock_authority_mode"]`:

- `warn` (default local dev): mismatches log warnings.
- `observe`: telemetry only, no warnings.
- `off`: disabled.

### 5.4 Elapsed time source

`uess_clock_elapsed_authority = "ledger"` (default). `turn.time_elapsed` derived from the ledger, not from the legacy sum of animation step times.

**OREB exception:** `OREB` turns (`PUTBACK_MAKE`/`PUTBACK_MISS`/`OREB_KICKOUT`) derive `time_elapsed` from the schema's total game-clock burn (`cs_start − cs_end`) in `_stamp_oreb_animation_steps`, not the ledger. Putbacks floor that burn at `OREB_PUTBACK_MIN_TIME_ELAPSED = 2` (self-contained shot attempt); `OREB_KICKOUT` uses the raw burn (its reset time is burned by the following HCO turn's entry orchestrator). See [`Rebound_System.md`](../06_Gameplay_Systems/Rebound_System.md) §OREB clock burn.

---

## 6. Ownership pass-lifecycle contract

Partially built. Wired in [`turn_manager._attach_uess_ownership_contract`](../../BackEnd/models/turn_manager.py).

### 6.1 Purpose

Define when ball ownership commits during a pass — at pass-receipt, not pass-release.

### 6.2 What is implemented today

The code stamps a **`uess_ownership_contract`** validation blob (fields like `pass_event_count`, `pass_receipt_valid_count`, `pass_lifecycle_valid`, `terminal_owner_pos`) — and only on turns that carry `steps[]` + `ball_owner_by_step`. Turns without those (BIP, SIP, FT, DREB, OREB, Opening Tip, Timeout, force-foul) are stamped `applicable: false` and skip validation.

The spec'd discrete fields — `ownership_at_turn_start` (`{owner_player_id}` or `null`) and `ownership_commit_event` (`{event_type, player_id, timestamp_game_seconds}`) — are **not yet built**. Per backlog decision 14+15, they ship together with the FE pure-renderer cleanup (their consumer), at which point `applicable` coverage extends to all turn types.

### 6.3 Mode

`game_state["uess_ownership_contract_mode"]`, default `warn`. Today a failed `pass_lifecycle_valid` only logs.

---

## 7. Per-shot state snapshot contract

**Not yet implemented** (backlog item 9 — largest open item). This is the flagship case of the **single-coord-source contract (§1)**: shot outcomes must resolve from the emitter's real-time coords, not a parallel path. The spec below is the build target: construct in `ShotManager.resolve_shot` immediately before resolution. Today `resolve_shot` re-derives positioning per branch from live `roles` / `shooter.coords` / `def_lineup` — a **known §1 violation under remediation**, not sanctioned behavior — and the `SHOT_COORD_DEBUG` / `NO_DEFENDER_SHOT` log tags do not exist. (The audit-only `position_snapshots` ledger is separate forensic machinery — different shape, never consumed by `resolve_shot`.)

### 7.1 Purpose

Every shot resolves contest, foul, block, rebound, and make/miss from **one** authoritative snapshot. No branch-specific coord fallbacks.

### 7.2 Required snapshot fields

Stored at `turn_result["roles"]["shot_state_snapshot"]`:

- `turn_type` — `HCO`, `HCT`, `FCP`, `FAST_BREAK`, `OREB`, `DREB`, `FREE_THROW`, `OPENING_TIP`, `FINAL_SHOT`, `BIP`, `SIP`
- `shot_type`
- `shooter` — `{player_id, name, pos, x, y, coord_source}`
- `shot_spot` — `{present, x, y}`
- `primary_defender`, `secondary_defender`, `nearest_defender`
- `assigned_defender_count`, `contest_box_defender_count`, `contest_box_defenders`
- `has_assigned_defender`, `has_contest_box_defender`

### 7.3 Authority rule

- `shooter.x/y` is the authoritative shooter coord.
- If `shot_spot.present`, shooter coords derive from `shot_spot`. Otherwise from `shooter.coords` (logged as such).
- Contest evaluation reads from the same snapshot that is logged.

### 7.4 Logging

- Every shot emits `SHOT_COORD_DEBUG` from the snapshot.
- Every shot with zero assigned defenders emits `NO_DEFENDER_SHOT`.

---

## 8. Coords tracking

### 8.1 Within a turn (step → step)

- Each step emitter sets `step[N+1].start.coords = step[N].end.coords` per player.
- Emitter does **not** write to `player.coords` mid-emit.
- Frontend snaps each sprite to `step.end.coords` at the end of every step.

### 8.2 Turn → turn

Single end-of-turn sync function: `sync_lineup_coords_from_turn` in [`shared.py`](../../BackEnd/utils/shared.py). Runs in `_append_turn`.

Sources, in order:

1. Existing `player.coords` (carry forward).
2. Legacy `animations[]` (un-migrated turns).
3. New `animation_steps[-1].end.coords` (migrated turns — takes precedence).
4. Post-shot overlay maps (see §9.1).

After sync, `build_final_coords` snapshots `player.coords` to `turn_result.final_coords` for next-turn emitters to read.

### 8.3 Emitter contract for new migrations

When migrating a turn:

1. Emit `animation_steps[]` with each step's `end.coords` populated for all 10 active players.
2. Trust `sync_lineup_coords_from_turn` to write `player.coords` at turn end. Do not write directly.
3. Within the emitter, ensure step N+1's `start.coords` matches step N's `end.coords` per player.
4. Uphold **ball-coord continuity (§8.4)**: the ball's resolved position at step N+1 start must equal its resolved position at step N end, and any ownership change must route through a `BallInFlight` (or explicit hand-off) step — never a direct owner swap between two attached states at different positions.

### 8.4 Ball-coord continuity (no teleports)

The ball has an authoritative position at every step and turn boundary, and that position must be **continuous** — the ball never jumps unless a step explicitly directs it (a pass/shot routes through `BallInFlight`; a knocked-loose ball routes through `BallLoose`).

Position by state: `BallAttached` → owner's coords (no explicit coord field), `BallInFlight` → `current_coords`, `BallLoose` → `coords`.

**Invariants:**

1. **Step seam.** The ball's resolved position at `step[N+1].start` equals its resolved position at `step[N].end`. This is the ball analog of §8.1's player rule — but, unlike player coords, it is **not enforced by construction** (`BallAttached` carries no coord to copy forward), so each emitter must uphold it explicitly.
2. **Ownership changes happen *within* a step, never across a seam.** A change of ball owner must be expressed as a single step whose `start.ball` = `BallAttached{owner:A}` and `end.ball` = `BallAttached{owner:B}` (or via an intermediate `BallInFlight` pass) — the FE tweens that A→B move as a pass over step T. What is a **teleport bug** is an owner (or position) change that appears *across* a seam: step N `end.ball` ≠ step N+1 `start.ball`, or turn-final ball ≠ turn-entry ball. At a seam the FE does not tween — it renders the position delta as an unconditional `setPosition` snap (see "FE rendering model" below).
3. **Capture continuity.** A `BallLoose{coords:L}` or `BallInFlight{current_coords:F}` → `BallAttached{owner:P}` transition is continuous only if P is at (≈) L / F at capture time. Emitters must seat the catcher at the ball — not snap the ball to the catcher.
4. **Turn seam.** The ball's position at a turn's first step must equal the prior turn's final ball position. Today the turn-seam carry is **owner id only** (`build_final_ball_handler_id`); the position is re-derived from that owner's coords in the new turn. **Build target:** a `final_ball_coords` snapshot (parallel to `build_final_coords`) so the turn seam carries an explicit ball position, closing the case where the new owner's coord ≠ where the ball actually was.

**Teleport-audit checklist for emitters:** at every step seam and turn seam, confirm the ball's resolved position moved continuously from its prior resolved position — or that a `BallInFlight` / `BallLoose` step explicitly authorizes the jump. Intermittent teleports concentrate at the seams (ownership change, loose→attached capture, turn boundary) because same-owner steps derive position continuously and look fine; the seams are where an unenforced invariant leaks.

**FE rendering model (verified against `animationPlayback.js`, 2026-07).** The frontend is a faithful renderer *within* a step and a naive snapper *at* seams — every teleport originates from a seam discontinuity the backend emits, not from FE logic:

- **Position resolution.** `ballCoordFromState` ([`animationPlayback.js:63`](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L63)) resolves `BallAttached` → owner's coord at that boundary, `BallInFlight` → `current_coords`, `BallLoose` → `coords`.
- **Within a step (tweened, no teleport).** `renderBallTransition` ([`:272`](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L272)) tweens the ball from its start-resolved coord to its end-resolved coord over step T, handling all diff cases — including `attached(A)→attached(B)`, which it detaches and tweens as a pass ([`:306`](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L306)). An ownership change expressed inside one step renders smoothly.
- **Step seam (snap — invariant 1).** `renderBallTransition` opens with an *unconditional* `ballSprite.setPosition(startPx)` ([`:293`](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L293)); its own comment notes this is "a no-op" only "if previous step ended at the same coord." A step-seam discontinuity therefore renders as a hard snap.
- **Turn seam (snap — invariant 4).** `playTurn` snaps the ball to the entry step's start state exactly once, unconditionally, via `snapBallToStartState` ([`:1204`](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L1204) → [`:532`](../../FrontEnd/static/js/phaser/animation/animationPlayback.js#L532)), with no reconciliation against the prior turn's final ball position — the persistent `ballSprite` carries over, so a turn-final ≠ turn-entry delta snaps. This is precisely the gap the `final_ball_coords` build target (invariant 4) would close.

Because the FE snaps unconditionally at both seams, seam continuity is an emitter obligation, not something the renderer can rescue.

---

## 9. Cross-cutting invariants

### 9.1 Post-shot overlays — single authority

`ShotManager` is the sole authority for post-shot positions. It populates four overlay maps on the turn result:

- `offense_rebounder_coords`
- `defense_rebounder_coords`
- `offense_getback_coords`
- `defense_release_coords`

Invariant: **each player appears in at most one overlay map.** Enforced by `canonicalize_post_shot_overlays` in [`shared.py`](../../BackEnd/utils/shared.py). Priority: shooter > outlet passer > release > getback > rebound cluster.

### 9.2 Overlay apply order (in sync)

```
offense_rebounder_coords → defense_rebounder_coords →
offense_getback_coords → defense_release_coords
```

Rebounder maps apply first (default for everyone eligible); get-back / release apply last so they override rebounder for designated non-rebounders.

### 9.3 AG curve

Base movement curve (`ag_to_grid_per_game_sec` in [`shared.py`](../../BackEnd/utils/shared.py)):

```
base_rate = STANDARD × (0.90 + (AG / 100) × 0.2)
```

Anchored at **AG=50 → STANDARD** (= `STANDARD_GRID_PER_GAME_SEC`). Spread: AG=0 → `STANDARD × 0.90`, AG=100 → `STANDARD × 1.10` (1.22x). Curve auto-rebalances when STANDARD changes. Capped 0.5–60 in `ag_to_grid_per_game_sec`.

With current `STANDARD = 14`: AG=0 → 12.6, AG=50 → 14, AG=100 → 15.4.

The AG fed into the curve is the player's **effective** AG — `attributes["AG"]` after energy rescaling (`anchor × NG`, see `Player._rescale_attributes`) — not the raw anchor. Tired players move slower in both game-clock burn and visuals.

Per-archetype rate at use sites (`_ag_grid_per_game_sec`):

```
archetype_rate = ARCHETYPE_CONSTANT × (base_rate / STANDARD_GRID_PER_GAME_SEC)
```

At AG=50, `base_rate / STANDARD` = 1, so each archetype runs at its table rate in §3.4.

### 9.4 Game-time / wall-time

- `tickMs = 350` (1 game-sec = 350 ms wall-clock).
- Playback renders each step at `step.end.time_elapsed × tickMs` wall-clock. No cap.
- Backend-computed T directly drives both clock burn and animation duration.

### 9.5 Destinations are intent, not guarantees

- Only `gate_player_ids` are guaranteed to reach `destination` by step end.
- Non-gate movers end at `_interrupted_coord` (`start + rate × T` toward destination). The advance trigger (the gate reaching its destination / step T elapsing) ends the step; every other player stops at wherever they've progressed to.
- Destinations may carry across consecutive steps so a slow mover can keep progressing toward the same target (e.g., HCT defenders: BIP step 1 → BIP step 2 → HCT walk-up all share the same destination; RR/Triangle trailing players continue through pass/drive → shot motion). Carry uses the prior step's authored destination, not a re-rolled/reconstructed target; explicit later-step roles such as shooter or shot defender override it.

**Logic reads the interrupted end, not the destination (§1 applied to motion).** A player's authoritative step-end position is the interrupted `end.coords[p]` the emitter renders — NOT the `destination` intent. All game logic — contest, steal, foul, rebound, over-and-back / frontcourt / shot-clock reads — MUST decide from `end.coords[p]`. Reading the `destination` (or "snapping" a player to their full target) means deciding from a position the FE never showed — a §1 single-coord-source violation, not merely a render detail.

**No teleport by construction — the corollary.** Because `end.coords[p]` is always the reachable interrupted coord (bounded by `rate × T`), a player can never be *placed* where they couldn't travel: the destination may be unreachable, but the rendered end never is. Teleports therefore arise only from two failures — (a) a *decision* consuming the `destination`/a snap instead of `end.coords` (the HCT/FCP trap-collapse + over-and-back class — see [`Trap_Press_Positioning_Decision.md`](../projects/UESS%20Audits/Trap_Press_Positioning_Decision.md)), or (b) a *seam* dropping a player so a downstream default (e.g. `{50,25}`) fills in (the backfill class). The planned reachability capstone audits every logic consumer for (a).

---

## 10. Spec references

For per-turn-type behavior, see:

- [`Step_By_Step_System.md`](Step_By_Step_System.md) — turn-by-turn step definitions, entry-step decision rules, turn routing (`offensive_state`)
- [`Fast_Break_System.md`](../05_GP_Supporting_Systems/Fast_Break_System.md) — FB variants and outlet mechanics
- [`Rebound_System.md`](../05_GP_Supporting_Systems/Rebound_System.md) — rebounder selection per turn type
- Constants: [`BackEnd/constants/__init__.py`](../../BackEnd/constants/__init__.py)

---

## 11. Speed values (tuning surface)

**Player archetypes:** single source of truth is **§3.4** (do not duplicate tables here). When §3.4 changes, update [`BackEnd/constants/__init__.py`](../../BackEnd/constants/__init__.py) and the `ag_to_grid_per_game_sec` anchor in §9.3 so AG=50 matches `STANDARD_GRID_PER_GAME_SEC`.

### 11.1 Ball motion speeds

Ball moves at fixed grid/game-sec rate independent of player rates.

| Context | Rate | Constant | Notes |
|---|---:|---|---|
| HCO half-court pass | 24 | `PASS_GRID_SPOTS_PER_GAME_SECOND` | Half-court passes; clock-burn accounting |
| FB pass (sharp) | 40 | `FB_PASS_GRID_SPOTS_PER_GAME_SECOND` | Outlet quality ≥ 50 |
| FB pass (sloppy) | 30 | `FB_PASS_GRID_SPOTS_PER_GAME_SECOND_SLOPPY` | Outlet quality < 50 |
| Reset inbound pass | 24 | `RESET_INBOUND_PASS_GRID_PER_GAME_SECOND` | BH → PG on Reset step |
| Inbound pass (BIP / SIP) | 24 | `INBOUND_PASS_GRID_PER_GAME_SECOND` | SF → PG; deliberate, slower than Reset |
| Shot ball motion | 27 | `SHOT_BALL_GRID_PER_GAME_SECOND` | `ball_motion_style="shot"` on `[ball_flight]` (and variant hops). FE: `duration_ms = max(400, gridDist ÷ 27 × tickMs)`; step playback wait `max(step T × tickMs, 400 ms)` so short shots do not jet. Arrival SFX anchors to ball tween completion; ball tween and step floor match main-branch `shootBall` parity so short shots do not reach the rim early and idle before result handling. Backend `time_elapsed` unchanged. Slower than passes — deliberate release vs quick-twitch pass. |
| Free throw shot motion | 12 | `FREE_THROW_SHOT_GRID_PER_GAME_SECOND` | FT ball flight (line → rim); deliberately slowest ball motion |

### 11.2 Floors and timing

| Setting | Value | Constant | Notes |
|---|---:|---|---|
| Pass min duration | 0.5 game-sec | `FB_PASS_MIN_GAME_SECONDS` | T floor for short pass steps |
| Walk-up step T floor | 1.5 game-sec | (literal in [`transition_bridge.py`](../../BackEnd/utils/transition_bridge.py)) | T = max(1.5, slowest_gate_natural) |
| HCO skeleton step T floor | 0.5 game-sec | `HCO_STEP_T_FLOOR_GAME_SECONDS` | Min T for HCO skeleton steps (short-distance steps still play visibly) |
| Shot ball min wall-clock | 400 ms | `SHOT_BALL_MIN_WALL_CLOCK_MS` in [`animationPlayback.js`](../../FrontEnd/static/js/phaser/animation/animationPlayback.js) | FE-only playback floor (ball tween + step wait). Does not change backend `time_elapsed`. |
| Pass / other ball tween min | 50 ms | (literal in [`animationPlayback.js`](../../FrontEnd/static/js/phaser/animation/animationPlayback.js)) | Safety floor for very short non-shot ball tweens |

### 11.3 Wall-clock / game-time conversion

| Setting | Value | Source |
|---|---:|---|
| `tickMs` | 350 ms / game-sec | `scene.gameClock`, frontend |

1 game-second = 350 ms wall-clock. Backend-computed T directly drives both clock burn and animation wall-clock duration. No per-step cap.

---

## 12. Known gaps and remediation (from legacy audit)

Single source of truth for the violation catalog, remediation order, and item statuses: [`UESS_Backlog.md`](../projects/UESS_Backlog.md) (status header at top). Turn-routing hardening and centralization: [`step_transition_centralization.md`](../projects/step_transition_centralization.md).

**Headline state (June 2026):** All gameplay turn types except Opening Tip and Timeout emit schema steps. The FE is not yet a pure renderer on all paths, and the §6 / §7 contracts remain unbuilt — see the backlog for open items. Ball-coord continuity (§8.4) is now a documented invariant but is **not enforced by construction** (no `final_ball_coords` snapshot; step-seam continuity is emitter-upheld, not asserted) — the likely source of the intermittent ball-teleport bugs at ownership/turn seams.

### 12.1 Shot classification coord — ~2% residual gap (2PT/3PT)

**What it is.** 2PT/3PT classification must read the *same* terminal shoot coord the FE renders (§1 single-coord-source). Historically it read the pre-emit skeleton **named spot**, which diverges from the emitter's step-sequential terminal coord on dish / dynamic-motion paths → **~25% of arc shots mis-scored** relative to the rendered position (a corner dish scored 3 while the shooter is rendered inside the arc, and vice-versa).

**Current fix (shipped).** HCO, Final Turn, and FCP now classify from the emitter's terminal shoot coord: a **throwaway, RNG-neutral pre-pass** of `build_skeleton_animation_steps` runs before `resolve_shot` (`_uess_terminal_shoot_coord` in [`phase_resolution.py`](../../BackEnd/engine/phase_resolution.py)), and its shoot-step `end.coords[shooter]` is stamped into `roles["shot_spot"]`. The pre-pass saves/restores the global RNG state, so it changes classification only — never make/miss or any downstream outcome. This cuts the bug from ~25% to **~2%**. (HCT is unaffected — it already classifies from procedural coords via its own emitter.)

**The residual ~2%.** The pre-pass does **not** perfectly reproduce the final render coord: the positional pass's live context (backfill, entry orchestrator, prior-turn seam) differs slightly between the pre-resolve call and the real turn_manager emit, so the two shoot coords can differ by a grid unit or two. On **borderline-arc** shots (release point a hair on/off the line) that occasionally flips 2↔3. It is *not* a systematic bias — it is boundary jitter on the ~2% of shots sitting on the arc.

**Why not exact.** True 0% (`classification coord == render coord` by construction) requires **pinning** the pre-pass coord into the emitter's gate/destination logic so the late render uses the identical value — a change to the shared render path (coordinate-frame + §8.1 continuity care), deliberately deferred as higher-risk. Full analysis + the exact-fix (Option C pin): [`Shot_Classification_UESS_Fix_Scope.md`](../projects/UESS%20Audits/Shot_Classification_UESS_Fix_Scope.md).

**Deeper implication.** Backend `player.coords` (via `apply_coords`) desyncs from the emitter-rendered position on ~58% of shots — the emitter is the true single coord source, and any game logic reading `player.coords` instead of the emitted step inherits this gap. Classification was the first symptom; the full coord-consumer audit is §12.2. (The classification fix was since generalized — `_uess_terminal_shoot_coord` → `_uess_sync_emitted_shot_coords`, which now syncs *all* players, not just the shooter.)

### 12.2 Coord-consumer audit — `player.coords` vs render

Full audit: [`Coord_Consumer_UESS_Audit.md`](../projects/UESS%20Audits/Coord_Consumer_UESS_Audit.md). Root cause = shot logic reading `player.coords` (animator row-end, all players fully-arrived) instead of the emitter's *interrupted* shoot-step render coords (§9.5: only the gate/shooter fully arrives).

**Systemic question — resolved favorably:** the desync is **per-shot, not cross-turn** — `sync_lineup_coords_from_turn` writes the emitted `animation_steps[-1].end.coords` with precedence, so carry-forward into the next turn is render-synced.

**Fixed (binary-outcome holes):**
- **Contest defenders** — `_uess_sync_emitted_shot_coords` (phase_resolution.py) stamps the emitted shoot-step coords onto every `player.coords` before `resolve_shot` (HCO/FT/FCP), so the contest loop reads on-screen geometry (over-contest ~98.7%→96.7%).
- **Covert Release block** — `fb_geometry_contest_resolved` flag makes `resolve_shot` honor CR's render-matched defender instead of stale pre-race coords (block now fires on contested CR).
- **Rebounder / near-bounce pool** — covered by the same sync (selection runs after it). Measured: coord divergence flips *which* rebounder ~75% but **possession ~0%** (box-out/team weighting is possession-stable) — an attribution effect, not an outcome flip.

**Accepted gaps (second-order, deferred):**
- **Zone matchup / double-team** — reads `zone_defender_assignments_by_step`, built from animator coords (animator.py:1912). Rebuilding from render coords risks the function's home/away orientation handling. Impact is second-order: zone contest ~95% stable + coarse zones → primary defender rarely flips; residual is double-team/attribution. Revisit if a zone-FG% anomaly appears.
- **OREB putback defender / over-the-back foul / zone `defense_score`** — attribution / margin-only effects. Deferred with the above.

### 12.3 StepState upstream-ownership gap

**Open, medium priority.** HCO's shipped StepState work unified the resolution
walk and defender-grid authority, but StepState is not yet the upstream owner of
all game-relevant per-step facts. The emitter/animator still calculates some
pass meet-points, step durations, clock progression, advance gates, and
interrupt positions. The resolution engine can separately estimate or consume
the same facts, leaving more than one derivation capable of drifting.

The remediation target is:

1. Calculate each game-relevant per-step value once in the resolution engine.
2. Freeze it into StepState before projection.
3. Make emitters project those frozen values without recalculating them.
4. Keep only outcome-inert styling—such as tween interpolation or cosmetic SFX
   selection—outside StepState.

Start with pass meet-points and `_estimate_step_game_seconds()`, then inventory
advance-gate and interrupt-position derivations. Preserve RNG topology and use
schema exact-diff/parity tests so this remains a behavior-preserving ownership
change.

This is the actionable residue from the completed HCO StepState refactor. Two
related implementation details are not backlog items:

- The pre-emit contest grid and eventual render grid cannot literally be one
  physical calculation because the contest can truncate the skeleton before
  emission. They use the same engine-owned placement contract and have measured
  effectively zero divergence.
- Batted-OOB contact and exit positions are backend-owned. The frontend's
  imperative OOB bounce path controls cosmetic trajectory shape only; moving
  that shape into schema is optional cleanup, not a gameplay-correctness task.
