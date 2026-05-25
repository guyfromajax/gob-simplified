# UESS System

The **Universal End-State Sync (UESS)** system is the contract by which every turn type executes consistently across backend and frontend.

---

## 1. Purpose

- Backend owns all game logic: step/turn results, player coords + actions, ball state, clock state.
- Frontend is a pure renderer of backend-emitted payloads.
- Every turn type emits the same `AnimationStep[]` schema, regardless of internal complexity.

This doc is the single source of truth for the contract. Code is the implementation; if they disagree, the code is right and this doc is wrong.

---

## 2. Migration state

| Turn type | Status | Emitter |
|---|---|---|
| Opening Tip | ✅ Migrated | (legacy emitter; schema-compliant payload) |
| BIP | ✅ Migrated | `transition_bridge.build_bip_animation_steps` |
| SIP | ✅ Migrated | `transition_bridge.build_sip_animation_steps` |
| HCT (dynamic) | ✅ Migrated | `dynamic_hct_step_emitter.build_dynamic_hct_animation_steps` |
| Fast Break — Covert Release | ✅ Migrated | `covert_release_step_emitter` |
| Fast Break — Rim Runner | ✅ Migrated | `rim_runner_step_emitter` |
| DREB (rebound capture) | ✅ Migrated | `dreb_step_emitter` |
| HCO | ✅ Migrated | `skeleton_step_emitter` (schema + universal entry orchestrator; natural-travel-time step T) |
| FCP | ✅ Migrated | `skeleton_step_emitter` (shared with HCO; FCP-specific gates + sprint archetypes + walker seed for BIP→FCP ball-owner carry; randomized BIP setup positions) |
| OREB (putback / kickout) | ✅ Migrated | `oreb_step_emitter` (branches by `result_type`: KICKOUT reuses `build_kickout_step`; PUTBACK_MAKE/MISS reuse `[shoot]/[ball_flight]/[hold]/[bounce]` builders; PUTBACK_MISS second rebound is dispatched as a separate DREB turn via the extended `_build_dreb_turn_from_miss` trigger) |
| Fast Break — Triangle | ✅ Migrated | `triangle_step_emitter` (shares burst/outlet with RR) |
| Fast Break — After Steal | ⏳ Not migrated | legacy `fastBreak.js` (CR-shaped; extend emitter later) |
| Free Throw | ✅ Migrated | `ft_step_emitter.build_ft_animation_steps` |
| Timeout | ⏳ Not migrated (low priority — minimal animation) | — |
| Final Shot | ⏳ Not migrated (separate resolver) | — |

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
- `ball` — one of `BallAttached`, `BallInFlight`, `BallLoose`
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
| `build_kickout_step` | BH (front-court) kicks back to step 0 BH. 2 sub-steps (positioning + pass). | HCO entry orchestrator, OREB Kickout |
| `build_pass_step` | Passer + receiver stationary, ball arcs. Other 8 optionally drift. Gated on `ball_reaches_player`. | BIP inbound pass, future migrations |
| `build_bip_animation_steps` | Composer: walk-up + pass for BIP turn. | BIP |
| `build_sip_animation_steps` | Composer: walk-up + pass for SIP turn. Gates step 1 on all 10 players (no teleports). Pins clock — no game-clock burn. | SIP |

### Universal helpers ([`animation_step_helpers.py`](../../BackEnd/utils/animation_step_helpers.py))

- `build_final_coords(game)` — snapshots `player.coords` at end of every turn.
- `build_final_ball_handler_id(turn_result)` — resolves the end-of-turn BH.
- `stamp_tween_durations(start, end_coords, T, off_lineup, def_lineup)` — writes per-player tween durations.

Both `final_coords` and `final_ball_handler_id` are stamped unconditionally on every turn by `_append_turn` in [`game_manager.py`](../../BackEnd/models/game_manager.py). Next-turn emitters read from `prior_turn.final_coords` / `prior_turn.final_ball_handler_id`.

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

---

## 6. Ownership pass-lifecycle contract

Active. Wired in [`turn_manager._attach_uess_ownership_contract`](../../BackEnd/models/turn_manager.py).

### 6.1 Purpose

Define when ball ownership commits during a pass — at pass-receipt, not pass-release.

### 6.2 Required fields per turn

Stamped on every turn:

- `ownership_at_turn_start` — `{owner_player_id}` or `null`.
- `ownership_commit_event` — `{event_type, player_id, timestamp_game_seconds}`.

### 6.3 Mode

`game_state["uess_ownership_contract_mode"]`, default `warn`.

---

## 7. Per-shot state snapshot contract

Active. Built by `ShotManager.resolve_shot` immediately before resolution.

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
- Non-gate movers end at `_interrupted_coord` (`start + rate × T` toward destination).
- Destinations may carry across consecutive steps so a slow mover can keep progressing toward the same target (e.g., HCT defenders: BIP step 1 → BIP step 2 → HCT walk-up all share the same destination).

---

## 10. Spec references

For per-turn-type behavior, see:

- [`Step_By_Step_System.md`](../05_Animation_System/Step_By_Step_System.md) — turn-by-turn step definitions, entry-step decision rules
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
| Free throw shot motion | 12 | `FREE_THROW_SHOT_GRID_PER_GAME_SECOND` | BH → PG on Reset step |

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
