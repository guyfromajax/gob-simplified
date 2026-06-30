# Shot Micro-Movements System

**Status:** Implemented (v1, June 2026)  
**Depends on:** Shot System, Block System, UESS / Animation System, Flourish renderer  
**Related:** [`Shot_System.md`](Shot_System.md), [`Block_System.md`](Block_System.md), [`05_UESS_System/UESS_System.md`](../05_UESS_System/UESS_System.md)

---

## 1. Purpose

Shot micro-movements add **backend-authored footwork and contest reactions** at the moment of a field-goal attempt. They extend the existing skeleton emitter and Flourish system — they are **not** a separate animation subsystem.

On eligible shot turns the backend:

1. Selects a **movement family** (jab step, fade, pump-fake chain, etc.) from the shooter’s `shot_type`.
2. When contested, resolves a **contest result** (`offense_win`, `neutral`, `defense_win`) from offensive vs defensive rolls.
3. Emits a short **micro chain** of `AnimationStep`s that **replaces the terminal `[shoot]` step** at the shot spot.
4. Hands off to the existing **`_build_post_shot_sub_steps`** pipeline (`[ball_flight]`, variant hops, `[hold]` / `[bounce]`).

The frontend renders gameplay coords from the schema and dispatches **flourishes** (pump fake, rattle, bite) in render space only.

---

## 2. Design Principles

| Principle | Detail |
|-----------|--------|
| Backend decides, FE renders | Contest outcome, family selection, defender displacement, and flourish stamps are backend-owned. FE never infers contest logic. |
| One hook per emitter | Emitters call `inject_shot_micro_before_post_shot()` — no per-family logic in emitters. |
| Extend, don’t fork | Reuses `AnimationStep` schema, `stamp_tween_durations`, existing post-shot sub-steps, and `flourishes.js`. |
| At-spot footwork | Micro chain plays **where the skeleton already placed the shooter**. Attack **drive** travel is upstream (`attack_drive_clearance`); micro only adds footwork at the release spot. |
| Primary defender only (v1) | Contest reactions use `roles["defender"]` / `turn_result["defender"]` only. |

---

## 3. Architecture Overview

```
Shot resolution (rules)
  ├─ calculate_shot_score → shot_score_pre_defense, shot_defense_score_raw, shot_defense_score_for_sfx
  ├─ resolve_contest(pre_defense, raw) → contest_result, contest_margin   [contested only]
  ├─ select_micro_movement(shot_type, coords) → micro_movement_family
  └─ stamp telemetry on turn_result

Skeleton / HCT / FB / OREB emitter
  ├─ … upstream steps (pass, cut, drive, etc.)
  ├─ terminal [shoot] step (placeholder)
  ├─ inject_shot_micro_before_post_shot()  ← replaces [shoot] with micro chain
  └─ _build_post_shot_sub_steps()          ← ball flight, variant, hold/bounce

Frontend (UESS playback)
  ├─ Step tweens from start.coords → end.coords
  └─ step.start.flourish[playerId] → runFlourish() (render-space only)
```

### 3.1 Core module

| File | Role |
|------|------|
| `BackEnd/engine/shot_micro_movements.py` | Registry, contest resolver, family beats, step builder, emitter hook |
| `BackEnd/constants/shot_micro_movements_constants.py` | Tunable geometry, timing, movement pools |
| `BackEnd/models/shot_manager.py` | Contest + family telemetry; block gate uses `contest_result` |
| `FrontEnd/static/js/phaser/animation/flourishes.js` | Render pump_fake, rattle, bite, shot_dip |
| `FrontEnd/static/js/phaser/animation/animation_config.js` | FE flourish defaults |

---

## 4. Scope

### 4.1 Included (v1)

All **field-goal shot attempts** that emit schema `animation_steps[]` and resolve to `result_type` ∈ `{MAKE, MISS, BLOCK}`:

| Turn context | Resolution path | Emitter hook |
|--------------|-----------------|--------------|
| HCO, FCP, Final Shot, FLSS | `ShotManager.resolve_shot()` | `skeleton_step_emitter.build_skeleton_animation_steps` |
| Dynamic HCT (FB drive, attack-basket shoot/drive) | `dynamic_hct_shot.py` | `dynamic_hct_step_emitter` |
| After-steal fast break | `after_steal_fast_break.py` | `after_steal_fast_break_step_emitter` |
| Rim Runner, Covert Release FB | Shared FB shot paths | `rim_runner_step_emitter`, `covert_release_step_emitter` |
| OREB putback | `shared.py` putback branch | `oreb_step_emitter` |

### 4.2 Excluded (v1)

| Case | Reason |
|------|--------|
| **Free throws** | Separate emitter; no micro chain |
| **CHARGE** early return | Nullified shot attempt — no micro (Block policy B3) |
| **Blocking foul** early return (attack charge path) | Nullified shot attempt — no micro (B3) |
| **Dunks** | Flourish kind registered in schema; **no auto-selection** in v1 |
| **Legacy `animations[]` path** | No `animation_steps[]` → hook is a no-op |
| **Static legacy HCT** (`hct_step_emitter` via old phase resolution) | Not wired unless turn uses dynamic schema emitters |

---

## 5. Contest Layer

### 5.1 When contest runs

Contest resolution runs only when **`has_contest` is true** (same definition as Shot System: role-based on HCO/Final Turn, Euclidean radius on FCP/HCT/FB).

When **`apply_defense=False`** (no contest):

- Skip contest layer entirely.
- Movement family is still selected.
- Defender track uses **neutral** displacement (contest layer off in `build_shot_micro_steps`).
- This is **not** forced `offense_win` — defender simply does not react to contest buckets.

### 5.2 Raw defense score

`calculate_shot_score()` returns six values; the sixth is **`shot_defense_score_raw`**:

- Primary defender’s **raw** attribute roll (`defense_score * random(1..6)`), **before** the 0.6× (single) or 0.35× (double-team) impact applied to `shot_score`.
- Used **only** for contest margin — **not** `shot_defense_score_for_sfx` (which uses the applied penalty for SFX tiering).
- When `second_defender` is present, contest margin uses **primary defender raw only** (v1).

### 5.3 Contest margin formula

```
margin = shot_score_pre_defense − shot_defense_score_raw
```

| Condition | `contest_result` |
|-----------|------------------|
| `margin > 150` | `offense_win` |
| `margin < −150` | `defense_win` |
| otherwise | `neutral` |

Constants: `CONTEST_OFFENSE_WIN_THRESHOLD`, `CONTEST_DEFENSE_WIN_THRESHOLD` in `shot_micro_movements_constants.py` (currently ±150).

### 5.4 Relationship to make/miss

Contest result drives **animation buckets only**. Make/miss still uses full `shot_score` vs `shot_threshold` (including applied defense penalty, variant modifiers, zone deltas, etc.). Contest does **not** override the scoring decision.

---

## 6. Movement Families

Families are chosen **uniformly at random** from the pool for the shooter’s `shot_type`, using the project’s existing `random` module (no per-turn seed in v1).

### 6.1 Pools by `shot_type`

| `shot_type` | Families |
|-------------|----------|
| **inside** | `strong_inside`, `fade_away`, `jab_step`, `under_and_up`, `straight_inside` |
| **attack** | `strong_attack`, `pullup_attack` |
| **outside** | `set`, `set_pump`, `dribble_shoot`, `dribble_pump_shoot`, `pump_dribble_shoot` |

### 6.2 Family beat definitions

Each family expands to an ordered list of beats. The **last beat is always `shot`** (`action: "shoot"`, shooter gate).

| Family | Beats | Notes |
|--------|-------|-------|
| `strong_inside` / `strong_attack` | move toward rim → shoot | Bucket A; `shot_motion` archetype |
| `fade_away` | move away from rim → shoot | Bucket B |
| `jab_step` | short perpendicular jab → shoot | Bucket B |
| `under_and_up` | jab (D bucket) → counter jab opposite 2× (B bucket) → shoot | Composite D+B |
| `straight_inside` / `pullup_attack` / `set` | shoot only | Bucket C — no coord pre-beat |
| `set_pump` | pump_fake flourish → shoot | Bucket D |
| `dribble_shoot` | move_to adjacent arc spot → shoot | Falls back to shoot-only if no open spot |
| `dribble_pump_shoot` | move_to → pump_fake → shoot | Composite; static fallback = set_pump pattern |
| `pump_dribble_shoot` | pump_fake → move_to → shoot | Composite |

### 6.3 Outside dribble target selection

Moving outside families (`dribble_shoot`, `dribble_pump_shoot`, `pump_dribble_shoot`):

1. Find nearest HCO arc spot to shooter (`OUTSIDE_ARC_SPOT_ORDER`).
2. Consider **adjacent** spots along the arc (lower/higher y neighbor).
3. Reject spots occupied by a teammate within **`ARC_SPOT_OCCUPIED_RADIUS`** (3 grid).
4. If no valid target → fall back to static family (`set` or `set_pump`).

Arc spot coords come from `HCO_STRING_SPOTS` (home orientation).

### 6.4 Jab direction

Perpendicular jab sign: shooter above midcourt (`y > 25`) jabs toward lower side; below midcourt jabs toward upper; at `y = 25` defaults to +y.

---

## 7. Buckets and Defender Behavior

Each family maps to a **bucket** (A–D). Bucket × `contest_result` selects a **defender behavior token** that sets defender end coords for that beat.

### 7.1 Family → bucket

| Bucket | Families | Character |
|--------|----------|-----------|
| **A** (muscle) | `strong_inside`, `strong_attack` | Power toward rim |
| **B** (separation) | `fade_away`, `jab_step`, `under_and_up` (counter beat), `dribble_shoot` | Create space |
| **C** (quick/set) | `straight_inside`, `pullup_attack`, `set` | Stationary release |
| **D** (pump) | `set_pump`, pump-fake beats in composites | Deception |
| **D+B** | `under_and_up`, `dribble_pump_shoot`, `pump_dribble_shoot` | Per-beat bucket override via `beat_bucket` |

### 7.2 Bucket × contest → defender behavior

| Bucket | offense_win | neutral | defense_win |
|--------|-------------|---------|-------------|
| **A** | seal | stick | wall |
| **B** | stranded | stick | glue |
| **C** | stationary | lean | pushoff |
| **D** | bite | pause | glue |

**Override:** `pullup_attack` + `offense_win` → defender **seal** (instead of stationary).

### 7.3 Defender displacement tokens

| Token | Effect |
|-------|--------|
| `seal` | Rim-side position behind shooter path |
| `stick` | Standard contest gap (`DEFENDER_STICK_GAP`) |
| `wall` | Tight wall at rim side |
| `stranded` | Defender holds start coord (beaten) |
| `glue` | Tight closeout; clamped min gap from shooter |
| `stationary` | No move |
| `lean` | Light stick |
| `pushoff` | Offset away from shooter toward rim vector |
| `bite` | Short lunge + `bite` flourish on defender |
| `pause` | Hold on pump-fake beat |

Defender gap constants (grid units): `DEFENDER_TRACK_GAP` (2.4), derived glue/stick/wall gaps in `shot_micro_movements_constants.py`.

### 7.4 Muscle loss (bucket A + defense_win)

On bucket **A** move beats when `contest_result == defense_win`, shooter displacement is scaled by **`MUSCLE_LOSS_COMPLETION`** (0.11) — the drive is “ walled ” before completion.

---

## 8. Step Placement (Option B)

Micro chain placement is **locked to Option B**:

1. Upstream skeleton steps bring players to the shot moment.
2. Emitter emits a **terminal `[shoot]` step** as today.
3. **`inject_shot_micro_before_post_shot`** finds that step and **replaces it** with N micro beats (last beat = `shoot`).
4. **`_build_post_shot_sub_steps`** appends ball flight and follow-ups unchanged.

This preserves a single post-shot contract across HCO, HCT, FB, and OREB.

---

## 9. Timing and Clock Burn

| Beat type | Duration |
|-----------|----------|
| **Coord-changing beats** (`move`, `move_to`) | Organic: `distance / ag_rate(archetype)`, floor `MICRO_MOVE_STEP_T_FLOOR` (0.15 s) |
| **Flourish-only beats** (`pump_fake`) | Fixed `MICRO_FLOURISH_BEAT_T` (0.4 s) |
| **Terminal shoot beat** | `max(MICRO_MOVE_STEP_T_FLOOR, MICRO_FLOURISH_BEAT_T)` |

Per-player **`tween_durations`** are stamped via `stamp_tween_durations()` so fast finishers don’t “lazy drift” through step T.

Game clock and shot clock decrement through each micro beat’s `end.time_elapsed`.

**Attack drive** time is **not** double-counted: drive travel lives in upstream skeleton steps (`build_attack_drive_sequence` / motion append); micro only burns at-spot footwork.

---

## 10. Coord vs Flourish

| Kind | Backend | FE |
|------|---------|-----|
| **Displacement** | Emitted `end.coords` (seal, wall, glue, stranded, bite side-step) | Standard step tweens |
| **Cosmetic** | `step.start.flourish[playerId]` | `runFlourish()` — render space only, never mutates gameplay coords |
| **Pump fake** | Flourish on shooter entry, `target: "ball"` | Ball sprite bobs; **shooter container does not move** |
| **Bite** | Defender coord nudge + `bite` flourish | Reach-in-style lunge toward ball |
| **Rattle** | Stamped on shoot beat per contest | Horizontal oscillation on shooter/defender sprite |

### 10.1 Shoot-beat disruption flourishes

On the final **`shot`** beat, contest drives optional **rattle** stamps:

| `contest_result` | Rattle target |
|------------------|---------------|
| `defense_win` | Shooter (3 cycles) |
| `offense_win` | Primary defender (3 cycles) |
| `neutral` + inside/attack | Both shooter and defender (2 cycles each) |

---

## 11. Display Orientation

Micro geometry uses the same contract as Shot System and UESS:

- **Home offense** → attacks `HOME_RIM_COORDS` (x ≈ 91, y ≈ 25); x increases toward rim.
- **Away offense** → attacks `AWAY_RIM_COORDS` (x ≈ 9, y ≈ 25); x decreases toward rim.
- **y is never mirrored** for away teams.
- Backend mirrors `x → 100 − x` before emit; frontend renders coords as-is.

Rim-relative move vectors (`strong_inside`, `fade_away`) use `_unit_toward_rim()` from the shooter’s display coord.

---

## 12. Turn Telemetry

Stamped on `turn_result` for eligible shot turns:

| Field | Type | When present |
|-------|------|--------------|
| `micro_movement_family` | string | Always on FG MAKE/MISS/BLOCK paths |
| `contest_result` | `offense_win` \| `neutral` \| `defense_win` | Contested only |
| `contest_margin` | float | Contested only |
| `shot_defense_score_raw` | float | Contested only |
| `has_contest` | bool | Always |

Self-contained shot paths (`dynamic_hct_shot`, `after_steal_fast_break`, OREB putback in `shared.py`) call `select_and_stamp_shot_micro()` directly because they bypass `ShotManager.resolve_shot()`.

---

## 13. Block System Interaction

See [`Block_System.md`](Block_System.md) for full block rules. Micro-movements add one **gating rule**:

**Block attempt + reconciliation run only when:**

```
has_contest
AND shot_type ∈ {inside, attack}
AND defender present
AND contest_result ∈ {neutral, defense_win}
```

**`offense_win` contests cannot be blocked.**

### 13.1 Block + micro animation order

| Outcome | Micro? | Post-shot |
|---------|--------|-----------|
| Clean block (`result_type: BLOCK`) | Yes — full micro chain | `[ball_flight]` to block spot; no variant/bounce hops |
| Block-recon shooting foul (AND-1 / 2 FT) | Yes — full micro chain | Then FT path |
| `foul_block_contact` (shooting foul wins rules) | Yes | Miss/FT animation; not `result_type: BLOCK` |
| CHARGE / blocking foul early return | **No** | — |
| Outside shot | Micro yes; **no block attempt** (unchanged) |

Block reconciliation math (`shot_score_pre_defense − defense_block_score`, ±150 thresholds) is **unchanged** when eligible.

---

## 14. Frontend Rendering

### 14.1 Playback hook

`animationPlayback.js` dispatches `step.start.flourish` in parallel with step tweens (~line 855):

```javascript
for (const [playerId, flourish] of Object.entries(flourishMap)) {
  runFlourish(scene, sprite, flourish, { ballSprite, turnData });
}
```

### 14.2 Implemented flourish kinds (v1)

| `kind` | Renderer | Notes |
|--------|----------|-------|
| `pump_fake` | Ball vertical bob | Shooter sprite stationary |
| `rattle` | Sprite horizontal oscillation | `cycles` from backend |
| `bite` | Defender lunge toward ball | Reuses reach-in geometry |
| `shot_dip` | Single-cycle rattle | Placeholder depth motion |
| `reach_in` | (pre-existing) | Not used by micro v1 |

Defaults: `animation_config.js` → `flourish.pumpFake`, `flourish.rattle`.

Unknown kinds are accepted no-ops (schema contract).

---

## 15. Constants Reference

All tunables live in `BackEnd/constants/shot_micro_movements_constants.py`:

| Constant | Default | Purpose |
|----------|---------|---------|
| `CONTEST_OFFENSE_WIN_THRESHOLD` | 150 | Contest offense win |
| `CONTEST_DEFENSE_WIN_THRESHOLD` | −150 | Contest defense win |
| `MICRO_STEP_GRID` | 4.5 | Standard footwork step (grid) |
| `JAB_STEP_GRID` | 0.8 | Jab amplitude |
| `JAB_COUNTER_MULTIPLIER` | 2.0 | Under-and-up counter |
| `DEFENDER_TRACK_GAP` | 2.4 | Base defender spacing |
| `DEFENDER_GLUE_GAP` | 0.72 | Tight closeout |
| `DEFENDER_STICK_GAP` | 1.488 | Standard stick |
| `DEFENDER_WALL_GAP` | 1.2 | Wall position |
| `DEFENDER_GLUE_CLAMP_MIN` | 1.3 | Min shooter–defender separation |
| `MUSCLE_LOSS_COMPLETION` | 0.11 | A-bucket defense_win move scale |
| `MICRO_MOVE_STEP_T_FLOOR` | 0.15 s | Min coord beat duration |
| `MICRO_FLOURISH_BEAT_T` | 0.4 s | Fixed flourish beat |
| `ARC_SPOT_OCCUPIED_RADIUS` | 3.0 | Teammate blocks adjacent arc spot |

Registry tables (`FAMILY_BUCKET`, `BUCKET_BEHAVIOR`, beat builders) live in `shot_micro_movements.py`.

---

## 16. API Summary

### 16.1 Resolution helpers

```python
resolve_contest(shot_score_pre_defense, shot_defense_score_raw) → (contest_result, margin)

select_micro_movement(shot_type, shooter_coord, shooter_id, off_lineup, all_coords) → family_id

select_and_stamp_shot_micro(turn_result, ...) → family_id  # stamps telemetry
```

### 16.2 Emitter hook

```python
inject_shot_micro_before_post_shot(steps, turn_result, off_lineup, def_lineup, away_offense)
```

Called **immediately before** `_build_post_shot_sub_steps()` in every wired emitter.

Internal builder:

```python
build_shot_micro_steps(family_id, contest_result, start_coords, ...) → List[AnimationStep]
```

---

## 17. Composite Beats

Multi-beat families (`under_and_up`, `dribble_pump_shoot`, `pump_dribble_shoot`) use **one** `contest_result` for the whole chain but may assign **per-beat buckets** via `beat_bucket`:

- Pump-fake beats use bucket **D** defender reactions (bite / pause / glue).
- Separation / shot beats use bucket **B** (or family default).

Each beat is a separate `AnimationStep` with its own gate, clock burn, and defender displacement.

---

## 18. v1 Limitations and Future Work

| Item | v1 status |
|------|-----------|
| Dunks | Schema kind exists; not in selection pool |
| Second defender contest animation | Not rendered; only primary defender track |
| Per-turn RNG seed | Uses global `random` like rest of sim |
| Static legacy HCT emitter | Not hooked |
| Triangle FB lane-pass shot | Uses shared rim-runner lane chain (hooked via rim runner path when `_build_post_shot_sub_steps` runs) |
| Tunable polish | Footwork amplitudes/timing may need playtest pass |

---

## 19. Verification Checklist

1. **Telemetry:** Turn JSON includes `micro_movement_family` on MAKE/MISS/BLOCK FG attempts.
2. **Step count:** `animation_steps` has more steps than pre-micro on the same skeleton (terminal shoot replaced by 1–3 beats).
3. **Contested:** `contest_result` and `contest_margin` present when `has_contest: true`.
4. **Block gate:** No `result_type: BLOCK` when `contest_result: offense_win` on inside/attack contested shots.
5. **FE:** Pump fake visible as ball bob; rattle on contested release; defender glue/stranded on fade/jab families.
6. **Excluded:** FT turns, CHARGE turns — no micro fields, no extra pre-shot beats.

Unit tests: `tests/test_shot_micro_movements.py` (contest resolver, registry, coords snapshot).

---

## 20. File Index

| Path | Role |
|------|------|
| `BackEnd/engine/shot_micro_movements.py` | Core system |
| `BackEnd/constants/shot_micro_movements_constants.py` | Constants + pools |
| `BackEnd/models/shot_manager.py` | Contest, telemetry, block gate |
| `BackEnd/engine/skeleton_step_emitter.py` | HCO/FCP/Final hook |
| `BackEnd/engine/dynamic_hct_step_emitter.py` | Dynamic HCT hook |
| `BackEnd/engine/dynamic_hct_shot.py` | HCT shot resolution telemetry |
| `BackEnd/engine/after_steal_fast_break.py` | After-steal telemetry |
| `BackEnd/engine/after_steal_fast_break_step_emitter.py` | After-steal hook |
| `BackEnd/engine/rim_runner_step_emitter.py` | Rim Runner hook |
| `BackEnd/engine/covert_release_step_emitter.py` | Covert Release hook |
| `BackEnd/engine/oreb_step_emitter.py` | OREB putback hook |
| `BackEnd/utils/shared.py` | OREB putback resolution telemetry |
| `BackEnd/utils/animation_step_schema.py` | `Flourish` TypedDict |
| `FrontEnd/static/js/phaser/animation/flourishes.js` | FE renderers |
| `FrontEnd/static/js/phaser/animation/animationPlayback.js` | Flourish dispatch |
| `FrontEnd/static/js/phaser/animation/animation_config.js` | FE defaults |
| `tests/test_shot_micro_movements.py` | Unit tests |
