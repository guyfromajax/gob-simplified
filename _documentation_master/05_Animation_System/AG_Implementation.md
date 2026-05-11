# AG → Movement Speed (implementation brief)

**Status:** ✅ **AG v2 in production** (Movement Rate Refactor, May 2026). AG affects both **game-clock burn** (backend) and **visual tween duration** (frontend) by construction, on every relevant turn type. Frontend AG-px-per-sec is now the **fallback** path when backend per-player timing isn't available.

**Scope:** Per-player movement duration/speed from **effective in-game Agility (AG)** for all max-effort movement (drives, fast-break runners, defensive close-outs, in-shot motion, HCO/HCT/FCP skeleton steps). Cruise-speed steps (HCO bring-up, HCT step 1) deliberately ignore AG — see "Cruise vs AG-driven" below.

---

## 1. Goals

- Reflect **player speed differences** in animation and game-clock pacing.
- Use a **smooth linear** mapping from AG → rate (no tier buckets).
- Use **real in-game attributes** (fatigue-aware), not raw anchors only.
- Keep **one universal curve** so tuning happens in one place.
- **Sync game-clock and visuals** so a slow player burns more shot-clock seconds AND visibly moves slower at the same rate.

---

## 2. Effective AG (energy / fatigue) — SS&S with engine

Per **`docs/docs_1_systems/05_GP_Supporting_Systems/Energy_System.md`**:

- After energy changes, malleable attributes (including **AG**) are rescaled:
  - **`effective_attribute = anchor_attribute × NG`**
  - Code path: `attributes[k] = int(anchor_k * ng)` in `BackEnd/models/player.py` (`_rescale_attributes`).
- **NG** is clamped during play (min **0.1**, max **1.0**).

**Animation rule:** Movement speed must use **`attributes.AG` (or equivalent) from the same player payload the sim exposes after rescaling** — i.e. the value that already reflects **anchor × NG**. Do not use `anchor_AG` alone unless we explicitly add it to the API for debugging.

**Alignment check:** If product intent were ever “max speed at full energy should match roster card AG,” that is already true in the engine: at NG=1, effective AG equals anchor AG. No flag raised against the doc; wording **“anchor × NG = in-game value”** matches the Energy System (integer rounding is implementation detail).

---

## 3. Backend AG curve (canonical)

The single source of truth for AG-driven timing is `ag_to_grid_per_game_sec(ag)` in `BackEnd/utils/shared.py`:

```python
rate = 10.0 + (ag / 100.0) * 12.0   # linear
return max(0.5, min(rate, 30.0))    # floor 0.5, soft cap 30
```

| AG | grid/game-sec | Note |
|---|---|---|
| 0 | 10 | Slow |
| 50 | 16 | Average — matches legacy COF rate exactly (critical invariant for safe migration) |
| 100 | 22 | Fast |
| 120 | 24.4 | Above-average rare; linear extrapolation |
| 200+ | 30 | Soft cap |
| None / junk | 16 | Safe default at AG=50 average |

### Archetype multipliers (applied on top of the curve)

In `calc_ag_segment_seconds(start, end, player, archetype=...)`:

| Archetype | Multiplier | Notes |
|---|---|---|
| `default` | 1.0 | Free-running rate (skeleton steps, fast-break runners, defender close-outs) |
| `drive` | 0.75 | Drive contested — at AG=50: 16 × 0.75 = 12 (matches legacy Drive rate exactly) |
| `shot_motion` | 0.625 | Movement into a shot — at AG=50: 16 × 0.625 = 10 (matches legacy HCO Shot rate exactly) |
| `compressed_hco` | 0.625 | Folded into shot_motion under the AG model (legacy Compressed-HCO and HCO-Shot were both 10) |

### Critical invariant

At AG=50, the curve produces the legacy COF rate (16). Combined with the multipliers, AG=50 + each archetype produces the EXACT legacy per-archetype rate. This means migrating any call site to AG-driven is safe — average lineups behave identically; only the spread between fast/slow players manifests.

---

## 4. Cruise vs AG-driven (when AG matters)

Two-tier movement model (Movement Rate Refactor):

**AG-driven steps** — max-effort situations where attribute matters:
- Drives to the basket (archetype `drive`)
- Fast-break runners (archetype `default`, BH AG drives the cover-ground time)
- Defender close-outs / converges (archetype `default`)
- In-shot motion (archetype `shot_motion`)
- HCO/HCT/FCP skeleton step movement (archetype `default` or `shot_motion` per phase)

**Cruise-speed steps** — comfortable jogs where AG doesn't apply:
- HCO bring-up (post-BIP/SIP/DREB → HCO step 0)
- HCT step 1 BH advance to engagement spot
- HCT step 1 non-BH offense + defenders

Cruise rate (`CRUISE_BASELINE_GRID_PER_GAME_SEC = 16`) is constant for non-BH movers; the BH gets a fresh `random.uniform(8, 16)` per turn for organic variation. See `calc_cruise_segment_seconds` in `BackEnd/utils/shared.py`.

---

## 5. Frontend AG-px-per-sec helper (fallback path)

Frontend `playerMovementSpeed.js` defines `agToSpeedPxPerSec(ag, { isBallHandler })`:
- Maps AG → px/sec (linear, with a 5% reduction for ball-handler tweens)
- Used by `getPlayerDuration(sprite, targetX, targetY)` for tween durations
- **Now a FALLBACK**: only consulted when backend doesn't provide per-player game-seconds for the segment

The frontend fallback uses the same conceptual mapping but operates in pixel space. Synchronization with backend AG curve isn't strictly required since backend authority (`game_seconds × clockSecondMs`) takes precedence whenever it's populated.

---

## 6. Relation to global animation speed

- `getGameSpeedPxPerSec()` / `window.__GAME_SPEED` apply a global multiplier on the **fallback** AG-px-per-sec path.
- Game-speed presets (Slow/Normal/Fast/Super Fast) currently disabled — focus has been on perfecting the execution feel before reintroducing presets. When reintroduced, they will act as a **visual-only** multiplier on `clockSecondMs` so the AG curve and game-clock burn aren't affected (visual time accelerates without changing game time).

---

## 7. Backend authority (architecture)

Phase 4 of the Movement Rate Refactor migrated 10 call sites of `calc_skeleton_step_timing_contract` to pass `off_lineup`, plus dedicated migrations in `dynamic_hct.py` (HCT step 2/3) and `phase_resolution.py` (fast-break BH cover-ground). Result:

- `step_clock_seconds[]` per turn now reflects per-player AG via the curve and archetype multipliers
- `bringup_per_player_seconds` per HCO turn reflects BH random cruise + others baseline
- HCT waypoints carry `game_seconds` per segment (BH cruise time for step 1 advance, AG-derived drive time for step 3, etc.)

Frontend reads these values and uses `× clockSecondMs` as the tween duration. AG spread is preserved across game-clock and visuals by construction.

---

## 8. Testing plan (support for “dunce mode” friendly tests)

**Unit-level (recommended first):**

- Pure function tests for **`agToSpeedPxPerSec(ag, { isBallHandler })`** (or equivalent):
  - Monotone increasing in AG.
  - AG **0**, **50**, **100**, **120** (extrapolation).
  - Ball handler flag **~5%** slower than off-ball for same AG.
  - Missing AG → defaults to **50**.

**Integration (lighter):**

- Mock sprite positions + `getPlayerDuration`-style call: longer AG **80** vs **40** over same pixel distance → shorter duration for higher AG.

**Fixtures:** `FrontEnd/static/js/phaser/utils/playerMovementSpeed.test.js` — run:

`cd FrontEnd/static/js/phaser && npm run test:movement` (speed + fatigue sprite sync)

---

## 9. Open items / follow-ups

- **AG curve tuning** based on franchise-mode pacing data (slope/intercept may need adjustment once we have data on shot-clock-violation rates per lineup AG distribution).
- **BH movement multiplier**: No BH penalty — ball-handlers move at their full AG-derived rate, matching off-ball players at equal AG. The frontend `BALL_HANDLER_SPEED_MULTIPLIER` constant in `playerMovementSpeed.js` is `1.0` (the v1 0.95 penalty was removed); the `isBallHandler` plumbing through `getPlayerMovementDurationMs` → `resolveMovementSpeedPxPerSec` → `agToSpeedPxPerSec` is preserved as a no-op lever for re-introducing or retuning a BH-specific factor without touching callers.
- **Game speed presets**: when reintroduced, multiply `clockSecondMs` only — don't touch the AG curve.
- **Shot gating (§11.2–11.3):** still optional — HCO shot keyed on **shooter-only** vs current "all offense finish before `shootBall`"; rebound / display SS&S if shot fires early.

---

## 10. Reference files

**Backend (timing source of truth):**
- `BackEnd/utils/shared.py` — `ag_to_grid_per_game_sec` (AG curve), `calc_ag_segment_seconds` (archetype-aware AG segment duration), `calc_cruise_segment_seconds` (cruise BH random + baseline), `calc_skeleton_step_timing_contract` (per-step game-clock with `off_lineup` plumbing), `_calc_hco_bringup_per_player_seconds` (per-player HCO bring-up dict)
- `BackEnd/engine/dynamic_hct.py` — HCT step 1 (cruise), step 2 (defender AG converge), step 3 (BH AG drive)
- `BackEnd/engine/phase_resolution.py` — `apply_fast_break_cg_time` (BH AG cover-ground); HCO turnover/foul/recalibration timing contract callers (all pass `off_lineup`)
- `BackEnd/models/shot_manager.py` — HCO/FCP/HCT shot-attempt timing contract callers (all pass `off_lineup`)
- `BackEnd/constants/__init__.py` — `CRUISE_BASELINE_GRID_PER_GAME_SEC`, `BH_CRUISE_MIN/MAX`, `DRIVE_MULTIPLIER`, `SHOT_MOTION_MULTIPLIER`, `PASS_GRID_SPOTS_PER_GAME_SECOND` (legacy pace constants retired in Phase 4d)

**Frontend (visual rendering, fallback path):**
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` — `playTurnAnimation` step loop reads `curr.game_seconds × clockSecondMs` as authoritative duration; falls back to `getPlayerDuration`. `runSetupTween` reads `turnData.bringup_per_player_seconds[pos]` for HCO bring-up.
- `FrontEnd/static/js/phaser/utils/playerMovementSpeed.js` — `agToSpeedPxPerSec` fallback helper
- `FrontEnd/static/js/phaser/utils/playerMovementDuration.js` — `getPlayerMovementDurationMs` fallback helper

**Energy / scaling:**
- `docs/docs_1_systems/05_GP_Supporting_Systems/Energy_System.md`
- `BackEnd/models/player.py` (`_rescale_attributes`)

**Project history:**
- `_documentation_master/projects/Movement_Rate_Refactor.md` — phase-by-phase implementation record

---

## 11. Animation gating & phase completion (brainstorm — Feb 2026)

**Purpose:** Record how steps advance today, how that intersects **AG** (variable finish times), and **product intent** for “who paces the beat.” Helps avoid blindly waiting on the slowest player when speeds diverge, while staying honest about **sim vs display**.

### 11.1 Concepts

- **Paced motion:** What **must** finish (or hit a milestone) before the next step/phase begins (ball handler spot, pass complete, shooter spot, shot release, etc.).
- **Ambient / trailer motion:** Spacing, trailers, get-backs — often should **not** block the beat unless the design says so.
- **Interrupted movement:** If a new step starts before a tween ends, **retarget from current pixels** (stop old tween, new duration from current position)—normal case, not edge case.

### 11.2 HCO skeleton steps (`turnAnimation.js`, `ShotAnimationSystem.js`)

**Non-shot steps (broadly “run the play”) — offense-gated:**

- **No pass on the step:** Client waits for **all offensive** step tweens (`Promise.all(offensivePromises)`), then advances. Defensive tweens start **in parallel** and are **not** awaited; the next step may begin while defenders are still moving (retarget from current pixels — §11.1).
- **Pass on the step:** **Staged:** (1) **`await` passer** (passer’s offensive tween); (2) start defensive step tweens when the pass path does (keeps pass and defense visually aligned); **`await` pass animation only** — defense does **not** gate; (3) **`await Promise.all(offensivePromises)`** so **every offensive** player (including the passer) finishes the step. The beat is “offense + pass,” not “slowest defender.”

**FCP / HCT:** Same skeleton machinery as HCO (§11.5).

**AG note:** Everyone on offense still **finishes the step together** (after pass choreography). Variable AG changes **how long** the step takes. **Shot** timing is still separate: see below — **shooter-only** shot gating is not implemented yet.

**Shot steps — product vs implementation:**

- **Desired product (discussion):** Shot should fire when the **shooter** reaches the shooting spot; shooter does **not** wait for trailing teammates.
- **Current client behavior:** After pass/defense, code **`await`s all remaining offensive** step tweens, **then** calls `shootBall`. So the **shooter currently waits for the rest of the offense** before the shot animation. Adopting shooter-only gating is a **deliberate change**, not a documentation polish.

### 11.3 Rebounds & “actual location at shot”

- **Backend SS&S:** After a turn is applied, **`sync_lineup_coords_from_turn`** aligns all ten lineup `Player.coords` with the **final step** of each player’s row in **`animations`**, plus overlays (get-back / release, etc.) — see `BackEnd/utils/shared.py`. That is **skeleton end state for the turn**, not live Phaser sprite positions mid-tween.
- **Implication:** Rebound **resolution** uses whatever geometry the **engine** already used for that turn when it resolved (turn payload is authoritative). The client animates **toward** those finals over time.
- **If we gate the shot on shooter-only:** On screen, teammates may still be **mid-tween** at release. Either we **accept** a display-vs-abstract-sim gap, or we later push **release-time** positions into resolution (heavier SS&S). Worth an explicit decision when implementing shot gating.

### 11.4 Fast breaks

**More event- / key-player-based** in many paths (e.g. burst awaits outlet receiver; shot flow keys off shooter or parallel trailers with early tween stops). Not one global `Promise.all` for every player—**per-sequence** rules in `fastBreak.js` and related code.

### 11.5 Press / traps (FCP / HCT)

**Same as HCO** in practice: shared skeleton / step loop uses **offense-gated** step progression (§11.2). Same pass vs no-pass and **shot** caveats as §11.2 (shooter-only shot still a future change).

### 11.6 Free throws & side inbounds (SIPs)

**Default:** Animate like HCO — wait for setup positions unless a given path keys off one player (verify per handler when auditing).

### 11.7 Baseline inbounds (BIPs)

**For now:** Like HCO. **Future:** Possible **dynamic** BIP when offense is in fast-break mode (not in scope for AG v1).

### 11.8 OREB turns

**Directionally action-based:** Advance on putback shot, kickout pass, or analogous **key action**—verify each path in rebound / OREB animation routing (`ballManager.js`, etc.).

### 11.9 Turn-type checklist (routing / `current_turn`)

**Primary reference:** `docs/docs_1_systems/05_GP_Supporting_Systems/Turn_by_Turn_System.md` (Bucket 1 examples).

**Types commonly used for gameplay animation routing include:**

| Bucket | Examples |
|--------|----------|
| Half court / pressure | `HCO`, `FCP`, `HCT` |
| Transition | `FAST_BREAK` |
| Dead-ball / special | `FREE_THROW`, `OREB` |
| Inbound | `BASELINE_INBOUND`, `SIDE_INBOUND` |
| Flow interrupt | `TIMEOUT` |

**Not the same axis:** `result_type` values (`MAKE`, `MISS`, `FOUL`, `STEAL`, `BLOCK`, `CHARGE`, `DEAD BALL`, …) are **outcomes** carried inside flows—they matter for animation choice but are not a parallel “turn type” list.

**Broader index (not a full enum):** `docs/docs_1/05_Gameplay_Systems.md`.

### 11.10 Design principle (AG + gating)

- Prefer **one gate per step** (“we advance when \_\_\_ completes”) and classify everyone else as **ambient** unless the play truly requires synchronization.
- **Universal AG** first; if HCO shot gating changes, treat **rebound/coords story** as part of the same ticket or an explicit follow-up so art direction and sim truth stay discussable.

---

## 12. Work history

**AG v1 (frontend px/sec only):** Shipped Feb 2026. Frontend `getPlayerDuration` consumes `agToSpeedPxPerSec(ag, { isBallHandler })`; tween durations vary with AG. Game-clock burn unchanged (still using flat pace constants). Visual ≠ clock divergence remained.

**AG v2 / Movement Rate Refactor (May 2026):** Backend AG curve, archetype multipliers, per-player game-seconds plumbed through HCO/HCT/FCP main game flow + fast break + BH cruise random for bring-up. Frontend now reads backend per-player timing as authoritative. Legacy pace constants retired. Visual and game-clock synced by construction. AG=50 invariant verified (preserves legacy timing exactly for average-AG lineups).

For the full phase-by-phase record, see `_documentation_master/projects/Movement_Rate_Refactor.md`.
