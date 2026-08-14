# Block System (Blocks on Shot Attempts)

**Status:** Implemented (re-verified against code July 2026; attempt roll, fight trigger, thresholds, third individual-player trigger, and the median-relative height scale are in code. Height bands re-anchored to `LEAGUE_MEDIAN_HEIGHT_IN` (75 after the 2026-08 −2 shift), 2026-08.)
**Depends on:** Shot System, Rebound System, Animation System, Data Persistence

---

## 1. Understanding of Requirements

### 1.1 Scope: Which Shots Are Block-Eligible

- **Inside** and **attack** shots: block attempt can occur.
- **Outside** shots: no block attempt; always use standard shot reconciliation.

### 1.2 When the Block Check Runs

- Run the **block attempt check** **before** standard shot reconciliation (i.e. before comparing `shot_score` to `shot_threshold` and deciding make/miss).
- If block attempt is **not** triggered → proceed with existing shot flow (make/miss, then rebound on miss).
- If block attempt **is** triggered → run **block reconciliation logic** instead of the normal make/miss step; only if that logic says “no block, no shooting foul” do we fall back to standard shot logic.

### 1.3 Block Attempt Check

Gating: requires `has_contest`, a shot defender, `shot_type` in (`inside`, `attack`), and **contest_result** in (`neutral`, `defense_win`). **`offense_win` contests cannot be blocked** (shot micro-movements contest layer). Three rolls, in order:

1. **Aggression roll:** **x** = defense team’s aggression level (numeric **0–4**): `def_team.strategy_settings["aggression"]` (default 2). **y** = `random.randint(BLOCK_Y_ROLL_MIN, BLOCK_Y_ROLL_MAX)` (currently **0–4**). If **y <= x** → block attempt → run block reconciliation.
2. **Fight roll (secondary trigger):** if the aggression roll fails, **z** = `random.randint(BLOCK_FIGHT_RANGE_MIN, BLOCK_FIGHT_RANGE_MAX)` (currently **0–10**); if **z <= defense `team_attributes["fight"]`** → block attempt anyway.
3. **Player roll (third trigger):** if the aggression and fight rolls fail, **z** = `random.randint(BLOCK_PLAYER_ROLL_MIN, BLOCK_PLAYER_ROLL_MAX)` (currently **1–300**); if **z <= shot defender's `attributes["ID"]` + (defense team's normalized `defensive_efficiency` × defender's height-rating 0–10)** → block attempt anyway. (Lets an individual rim protector go up on his own when the team rolls miss.)

If neither roll triggers → skip to standard shot reconciliation. Roll ranges are constants in `BackEnd/constants/__init__.py`.

### 1.4 Block Reconciliation Logic

**Inputs:** Same roles as shot (shooter, defender, etc.), plus the **shot_score** already computed for this attempt.

**Defender height_score (same for shooter height_score when used):**

- Map player height (inches) to 0–10, expressed as offsets from `LEAGUE_MEDIAN_HEIGHT_IN` (design §11.2) so a distribution shift is a one-line constant change, not a threshold sweep: **median → 0; +`BLOCK_SCORE_TOP_OFFSET_IN` (10) inches → 10; 1 pt/inch between** (`height_to_block_score`, `shared.py`).
  - At the current median **75**: ≤75 → 0, 76 → 1, 77 → 2, 78 → 3, 79 → 4, 80 → 5, 81 → 6, 82 → 7, 83 → 8, 84 → 9, ≥85 → 10.

**Shooter height_score (for shooting-foul finish):**

- Same 0–10 mapping as above; use the **same scaled form** `(height_score * 10) + random.randint(-9, 9)` in shooter_finish_score (i.e. shooter height is also scaled, not raw 0–10).

**Defender block score:**

- Defender **height_score** (0–10) from table above; then **scaled height term** = `(height_score * 10) + random.randint(-9, 9)`.
- `defense_block_score = (scaled_height_term * 0.4 + defender_ID * 0.4 + defender_IQ * 0.2 + normalized_defensive_efficiency) * random.randint(1, 6)`
  - The height contribution uses `(height_score * 10) + random.randint(-9, 9)`; ID and IQ are raw defender attributes. Defensive efficiency is the core-8 stored value normalized through `core8_gameplay()` before use.

**Comparison:**

- Use **shot_score before defense penalty** (the offensive component only). In block reconciliation, **defense_block_score is the defense component**; we do not apply the normal shot defense penalty here.
- **Thresholds:** the shooting-foul threshold is `BLOCK_RECONCILIATION_SHOOTING_FOUL_THRESHOLD` (**150**). The block threshold is dynamic: `BLOCK_RECONCILIATION_BLOCK_THRESHOLD_BASE` (**70**) plus normalized defensive efficiency. The two outcome thresholds remain independently tunable.
- If **diff > BLOCK_RECONCILIATION_SHOOTING_FOUL_THRESHOLD** → **shooting foul** (see below).
- Elif **diff < 70 + normalized defensive efficiency** → **block** (no basket; rebound).
- Else → **no block, no shooting foul** → proceed with **standard shot logic** (make/miss using existing threshold and shot_score, including normal defense penalty).

### 1.5 Shooting Foul in Block Reconciliation

When block reconciliation decides **shooting foul**:

- **shooter_finish_score** = shooter attributes:  
  `(ST * 0.4 + SC * 0.3 + shooter_scaled_height * 0.2 + IQ * 0.1) * random.randint(1, 6)`  
  where **shooter_scaled_height** = `(shooter_height_score * 10) + random.randint(-9, 9)` (same 0–10 table then scale as defender).
- If **shooter_finish_score > 250** → basket is **made** (and-one).
- Else → basket is **missed** (foul, free throws, no bucket).

From here, existing shooting-foul and free-throw flows (stats, next_play_type, game_state) should apply; no new one-off logic.

### 1.6 Animation: Block vs Shot

- **Shot micro-movements (v1):** On eligible block turns, the schema emitter plays the **micro footwork chain** at the shot spot first (terminal `[shoot]` replacement), then the existing BLOCK post-shot sub-steps (`[ball_flight]` to block spot, no variant/bounce hops). CHARGE / blocking-foul early returns skip micro entirely.
- When the outcome is a **block** (not a shooting foul, not “else” to standard shot):
  - Animate the ball to the **block spot** (not the rim), then run the same miss path (bounce, rebound). The block spot is used as the reference for both the ball flight target and the bounce/rebound so the ball does not snap to the opposite side of the court.
  - **Frontend:** In `ShotAnimationSystem`, (1) ball flight uses `ball_bounce_x`/`ball_bounce_y` as the target when `result_type === 'BLOCK'`; (2) in the miss path, `rimCoords` for BLOCK is also set from the block spot (not `getRimCoordinates`) so the bounce and rebound logic use the block spot as the reference; (3) shot **variant** animations (rattle/backboard) are skipped for BLOCK.
- When outcome is shooting foul or “else” to standard shot, keep current shot (and optional foul) animation behavior.
- If the standard shooting-foul roll has already produced a defensive shooting foul and block reconciliation also reaches the block threshold, the **shooting foul owns the rules outcome**:
  - Backend keeps `result_type: "MISS"` / `next_play_type: "FREE_THROW"` rather than `result_type: "BLOCK"`.
  - Backend may stamp `foul_block_contact: true` plus `foul_block_contact_x/y` for animation-only contact.
  - The schema emitter sends the ball to that contact point and suppresses rim/clank arrival SFX and the bounce sub-step.
  - No `BLK` stat is credited, no blocker momentum is applied, no `blocker_id` is stamped, and no "BLOCK!" announcement or block SFX fires.
  - The defender still receives the shooting foul, and the shooter receives the appropriate free throws.

**Result_type BLOCK (dedicated, both backend and frontend):**

- **Backend:** Set and return **`result_type: "BLOCK"`** in the turn result (same way as "MAKE" or "MISS"). BLOCK is used in the backend.
- **Frontend:** Receive `result_type: "BLOCK"`. Route to a **dedicated BLOCK handler** for **ball animation only** (block animation, no shot arc). For **all other behavior, treat BLOCK the same as MISS**: timeout eligibility, rebound handling, possession flip, `_previousTurnWasShot`, get-back/release logic, stat application, next_play_type, etc. Only the ball animation differs (MISS → shot to rim; BLOCK → ball to block spot then rebound).
- **Implementation audit:** Anywhere the frontend (or backend) checks `result_type === "MISS"` for non-animation behavior (e.g. "was this a shot attempt?", "should we flip possession on DREB?", "is previous turn a shot?", "timeout after DREB?"), include **`result_type === "BLOCK"`** in that check so BLOCK is treated like MISS. Only the animation path should branch on BLOCK to run block animation instead of shot animation.

### 1.7 Block Spot (Where the Block Happens)

- **Reference point:** uses the explicit `roles["shot_spot"]` from the caller when present (same data the animation uses); falls back to `shooter.coords`.
- **X:** 2–15 **back** from the shooter’s X (toward the offense’s own basket).
  - Home on offense: shooter_x + (-15 to -2) → range [shooter_x − 15, shooter_x − 2].
  - Away on offense: shooter_x + (2 to 15) → range [shooter_x + 2, shooter_x + 15].
- **Y:** shooter_y ± 6 (i.e. `shooter_y + random.randint(-6, 6)` or equivalent).
- Result clamped to court bounds (`calculate_block_spot` in `BackEnd/utils/shared.py`).
- Rebound: use this block spot as the **bounce/rebound spot** and run **standard rebound logic** (existing geography-based rebound, `calculate_bounce_spot`-style usage or a dedicated block-spot helper that returns the same shape `{x, y}` so `determine_rebounder` and existing rebound flow are reused).

**Future:** You want location-based rebound adjustments later; the block spot is the single “bounce” location for this turn so current rebound logic stays as-is until that future work.

### 1.8 Team Attributes: Momentum

- When a **block** occurs (outcome = block, not shooting foul):
  - Defense team **momentum +1** (clamped to max 10).
  - Offense team **momentum −1** (clamped to min 0).
- Apply to **`team_attributes["momentum"]`** for each team (confirmed as the right place for block impact).
- Note: team-level momentum is a legacy early-build mechanic (see flagged note in the doc sweep) — blocks are one of its live feeders.

### 1.10 Block Announcement

- When a block occurs, use the **Announcement System** to announce **"BLOCK!"** and show the **blocker’s image** (same pattern as other player-centric announcements, e.g. rebound or steal).
- **Timing:** "BLOCK!" is announced **when the ball reaches the block spot** (at the start of the miss path in `ShotAnimationSystem.handleMissedShot`), **before** the rebound is announced, so the order is always Block → Rebound.

### 1.9 Stats and Fouls

- **Block:** Defender credited with a block (BLK); shooter’s FGA (and 3PTA if applicable) recorded; shot is a miss; no points. **Possession:** Possession flips **only on DREB** (same as any miss). OREB does not flip possession; defense +1 / offense −1 momentum still applies when the block occurs.
- **Shooting foul (from block reconciliation):** Use existing shooting-foul stat and free-throw flow (defender foul, shooter FTs, optional and-one bucket from shooter_finish_score).
- **Shooting foul with block-like contact:** If a normal defensive shooting foul is already active when block reconciliation reaches the block threshold, treat it as a shooting foul with animation-only contact. Do not credit BLK or block momentum.

---

## 2. Integration Points (Reuse)

- **Shot type:** Reuse existing `shot_type` (inside / attack / outside) from `resolve_shot()`; only inside/attack enter block attempt.
- **Shot score:** Reuse `calculate_shot_score()` output; block reconciliation uses that value (and possibly the same defender used there for block height/ID/IQ).
- **Aggression:** Reuse `def_team.strategy_settings["aggression"]` and/or `strategy_calls["aggression_call"]`; add a single helper that maps to the numeric x used in “y <= x”.
- **Rebound:** Reuse `determine_rebounder(game, bounce_spot, ...)` and existing rebound stat/delta flow; for blocks, pass the **block spot** as the bounce spot instead of calling `calculate_bounce_spot` for a shot.
- **Bounce spot shape:** Block spot is `{"x": ..., "y": ...}` like `calculate_bounce_spot` return value so all existing rebound and animation code that expects `ball_bounce_x` / `ball_bounce_y` keeps working.
- **Animation:** Dedicated `result_type: "BLOCK"`; BLOCK handler for ball animation only; treat BLOCK like MISS everywhere else (see §1.6). No change to rebound animation contract.
- **Announcement:** Use existing Announcement System (see `Announcement_System.md`) to announce "BLOCK!" and show blocker's image.
- **Momentum:** Apply ±1 in the same place and shape as any existing momentum updates (e.g. in the same result payload and game_state updates used for other momentum changes).
- **Data persistence:** Turn result and game_state changes for block, shooting foul from block, and momentum must follow the same patterns as existing shot/miss, foul, and momentum (no new persistence paths).

---

## 3. Work Plan (SS&S)

**Principles:** Reuse existing shot/rebound/aggression/foul flows; one clear insertion point in shot resolution; no siloed block-only duplicate logic; preserve data persistence and existing systems.

1. **Align and lock** — All locked (shooter height scaled; momentum in team_attributes; BLOCK result_type both ends; BLOCK = MISS except animation + announcement).

2. **Backend: block attempt and reconciliation**
   - Add **block attempt** step in `resolve_shot()`: after `shot_type` and **pre–defense-penalty** shot_score (and motion attack penalty) are available. If `shot_type` in (`"inside"`, `"attack"`): x = `def_team.strategy_settings["aggression"]` (0–4), y = `random.randint(BLOCK_Y_ROLL_MIN, BLOCK_Y_ROLL_MAX)` (currently 0–4), if y <= x run block reconciliation. If that fails, run the secondary fight roll: z = `random.randint(BLOCK_FIGHT_RANGE_MIN, BLOCK_FIGHT_RANGE_MAX)` (currently 0–10); if z <= defense `team_attributes["fight"]`, run block reconciliation.
   - **Block reconciliation:** Use **shot_score before defense penalty**. Inputs = that shot score, shooter, defender, roles. Compute the defender score as `(scaled height × 0.4 + ID × 0.4 + IQ × 0.2 + normalized defensive efficiency) × random integer 1–6`; then **diff** = shot_score − defense_block_score. If **diff > 150**: shooting foul; if **diff < 70 + normalized defensive efficiency**: block; else: fall back to standard shot (with normal defense penalty and threshold).
   - **Height score:** One shared helper for “height inches → 0–10”; use `(height_score * 10) + random.randint(-9, 9)` for defender block score (and shooter_finish if confirmed).
   - **Block outcome:** Set result_type or flag so frontend does block animation (no shot arc). Compute block spot; call existing rebound flow with that spot; record BLK; FGA (and 3PTA if applicable) for shooter; no FGM; no points; momentum defense +1 / offense −1. **Possession flips only on DREB** (OREB does not flip possession). Reuse result shape (`ball_bounce_x`/`ball_bounce_y`, `rebounder_id`, `rebound_type`, etc.).
   - **Shooting foul from block:** Reuse existing shooting-foul and free-throw handling (game_state, next_play_type, stats, foul recording). Only the trigger is “block reconciliation said shooting foul”; the rest is existing paths.

3. **Backend: block spot**
   - Implement block spot as a function that, given shooter (x, y) and whether home/away offense, returns `{x, y}` in the 2–15 back and ±6 y rules. Use this as the bounce_spot for `determine_rebounder` and for `ball_bounce_x`/`ball_bounce_y` in the result so rebound and animation stay unchanged.

4. **Frontend: animation**
   - In the path that currently chooses “shot” vs “miss” animation, add a branch: if result is block (result_type or flag), play **block animation** (no shot arc), then rebound from the existing `ball_bounce_x`/`ball_bounce_y` (block spot). Reuse existing rebound animation and announcements; only the “shot” part is replaced by “block” for that turn.

5. **Momentum**
   - When applying defense +1 / offense −1 for a block, update the same structures used elsewhere for momentum (e.g. `team_attributes["momentum"]`) and include any required deltas in the turn result so persistence and UI stay consistent.

6. **Tests and regression**
   - Unit tests: block attempt (y <= x vs y > x), block reconciliation (shooting foul / block / else to standard shot), height_score mapping, block spot coordinates.
   - Integration: one inside and one attack shot path that triggers block and one that doesn’t; confirm rebound and possession; confirm no double FGA, correct BLK; confirm shooting-foul-from-block path uses existing foul/FT flow.
   - Regression: existing shot/charge/blocking foul/rebound flows unchanged when block attempt is false or when block reconciliation falls to “else”.

7. **Docs**
   - After implementation: update Shot_System.md to add “Block attempt (inside/attack only)” before shot reconciliation and “Block reconciliation” as an alternative branch; add a short “Block” subsection under animation; reference this doc. Update Rebound_System.md if we add a “block spot” variant of bounce spot.

---

## 4. Clarifications / Alignment Checklist

| Item | Status |
|------|--------|
| Aggression | **Locked (updated):** x = `def_team.strategy_settings["aggression"]` (0–4); y = `random.randint(0, 4)` (`BLOCK_Y_ROLL_*`); block attempt if y <= x. Secondary fight roll: z = `random.randint(0, 10)` (`BLOCK_FIGHT_RANGE_*`); block attempt if z <= defense `team_attributes["fight"]`. |
| height_score formula | **Locked:** `(height_score * 10) + random.randint(-9, 9)` for the scaled height term in defense_block_score (and shooter_finish if same). |
| shot_score in block | **Locked:** Use shot_score **before** defense penalty; defense_block_score is the defense component in the block contest. |
| Possession on block | **Locked:** Possession flips only on DREB; OREB does not flip possession. |
| Shooter_finish height | **Locked:** Use scaled `(height_score * 10) + random.randint(-9, 9)` in shooter_finish_score (same as defender). |
| Momentum | **Locked:** Apply block impact to `team_attributes["momentum"]` (defense +1, offense −1). |
| Animation | **Locked:** Dedicated `result_type: "BLOCK"` in both backend and frontend; treat BLOCK like MISS except ball animation and announcement. |
| Block announcement | **Locked:** Announcement System: "BLOCK!" and show blocker's image. |

---

## 5. Summary

- **Eligibility:** Inside and attack only (contested, with a shot defender); outside unchanged.
- **Block attempt (any of 3 triggers, in order):** (1) aggression — y = random 0–4 ≤ `aggression` (0–4); (2) fight — z = random 0–10 ≤ normalized defense team `fight`; (3) player — z = random 1–300 ≤ shot defender `ID` + (normalized `defensive_efficiency` × defender height-rating 0–10). First pass → block reconciliation; all miss → standard shot.
- **Block reconciliation:** Use **shot_score before defense penalty**. Defense score is `(scaled height × 0.4 + ID × 0.4 + IQ × 0.2 + normalized defensive efficiency) × random integer 1–6`. For `shot_score − defense_block_score`: > 150 → shooting foul; < `70 + normalized defensive efficiency` → block; else → standard shot.
- **Block outcome:** No shot animation; block spot 2–15 back from shooter, y ±6; standard rebound; **possession flips only on DREB** (OREB does not flip); defense +1 / offense −1 momentum; BLK and FGA recorded.
- **Animation:** Dedicated `result_type: "BLOCK"` in backend and frontend. BLOCK is treated like MISS everywhere except: (1) ball animation (block anim, no shot arc), (2) announcement ("BLOCK!" + blocker image via Announcement System). Audit: wherever code checks for MISS for non-animation behavior, include BLOCK.
- **Announcement:** On block, Announcement System announces "BLOCK!" and shows blocker's image.
- **Reuse:** Same shot_type, pre-penalty shot_score from calculate_shot_score (block uses it before penalty), aggression 0–4, rebound flow, result shape, persistence, foul/FT handling.

**Implementation notes (post-implementation):**
- Historical block-volume recalibration (July 2026): the former fixed threshold moved from `-150` to `-100`, then to `-50`. In August 2026, an initial subtractive composite and `40 - normalized defensive efficiency` threshold suppressed blocks nearly to zero because stronger defense moved the score in the wrong direction. The corrected model uses an additive defensive composite and `70 + normalized defensive efficiency`. A `block_funnel_tracking` diagnostic follows eligible shots through trigger, reconciliation foul/fallback/block bands, actual blocks, and foul-owned block contacts; it is included in per-game and week-aggregate shot diagnostics.
- Height mapping (July 2026 correction; re-anchored 2026-08): `height_to_block_score()` is `h − LEAGUE_MEDIAN_HEIGHT_IN`, clamped 0 at the median and 10 at `median + BLOCK_SCORE_TOP_OFFSET_IN`. It moved from literal 73–81 bands to median-relative offsets in the 2026-08 −2 height shift, so at median 75 the scale is ≤75 → 0 … ≥85 → 10 (was the ≤72 → 0 … ≥82 → 10 literal band). The original July fix was correcting an accidentally-reversed `82 - height` expression.
- Block announcement order: "BLOCK!" is fired from `ShotAnimationSystem.handleMissedShot` when `result_type === 'BLOCK'` (turnData._blockAnnounced set); `finalizeTurnAfterAnimation` only announces BLOCK if `!turn._blockAnnounced` (fallback).
- Ball snap fix: `executeCompleteShotSequence` uses block spot (`ball_bounce_x`/`ball_bounce_y`) as `rimCoords` for BLOCK so the miss path (bounce, rebound) never references the rim for blocks.
