# Block System (Blocks on Shot Attempts)

**Status:** Implemented  
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

- **x** = defense team’s aggression level (numeric **0–4**): use `def_team.strategy_settings["aggression"]`.
- **y** = `random.randint(0, 10)`.
- If **y < x** → block attempt is **true** → run block reconciliation.
- Else → block attempt is **false** → skip to standard shot reconciliation (current code).

### 1.4 Block Reconciliation Logic

**Inputs:** Same roles as shot (shooter, defender, etc.), plus the **shot_score** already computed for this attempt.

**Defender height_score (same for shooter height_score when used):**

- Map player height (inches) to 0–10:
  - ≥82 → 10, 81 → 9, 80 → 8, 79 → 7, 78 → 6, 77 → 5, 76 → 4, 75 → 3, 74 → 2, 73 → 1, ≤72 → 0.

**Shooter height_score (for shooting-foul finish):**

- Same 0–10 mapping as above; use the **same scaled form** `(height_score * 10) + random.randint(-9, 9)` in shooter_finish_score (i.e. shooter height is also scaled, not raw 0–10).

**Defender block score:**

- Defender **height_score** (0–10) from table above; then **scaled height term** = `(height_score * 10) + random.randint(-9, 9)`.
- `defense_block_score = (scaled_height_term * 0.4 + defender_ID * 0.4 + defender_IQ * 0.2) * random.randint(1, 6)`  
  - So the height contribution uses the scaled value `(height_score * 10) + random.randint(-9, 9)`; attributes ID and IQ are the raw defender values.

**Comparison:**

- Use **shot_score before defense penalty** (the offensive component only). In block reconciliation, **defense_block_score is the defense component**; we do not apply the normal shot defense penalty here.
- **Constants** (in `BackEnd/constants/__init__.py`): `BLOCK_RECONCILIATION_SHOOTING_FOUL_THRESHOLD`, `BLOCK_RECONCILIATION_BLOCK_THRESHOLD` (defaults 200 each) so you can adjust easily.
- If **shot_score − defense_block_score > BLOCK_RECONCILIATION_SHOOTING_FOUL_THRESHOLD** → **shooting foul** (see below).
- Elif **shot_score − defense_block_score < −BLOCK_RECONCILIATION_BLOCK_THRESHOLD** → **block** (no basket; rebound).
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

- When the outcome is a **block** (not a shooting foul, not “else” to standard shot):
  - Animate the ball to the **block spot** (not the rim), then run the same miss path (bounce, rebound). The block spot is used as the reference for both the ball flight target and the bounce/rebound so the ball does not snap to the opposite side of the court.
  - **Frontend:** In `ShotAnimationSystem`, (1) ball flight uses `ball_bounce_x`/`ball_bounce_y` as the target when `result_type === 'BLOCK'`; (2) in the miss path, `rimCoords` for BLOCK is also set from the block spot (not `getRimCoordinates`) so the bounce and rebound logic use the block spot as the reference.
- When outcome is shooting foul or “else” to standard shot, keep current shot (and optional foul) animation behavior.

**Result_type BLOCK (dedicated, both backend and frontend):**

- **Backend:** Set and return **`result_type: "BLOCK"`** in the turn result (same way as "MAKE" or "MISS"). BLOCK is used in the backend.
- **Frontend:** Receive `result_type: "BLOCK"`. Route to a **dedicated BLOCK handler** for **ball animation only** (block animation, no shot arc). For **all other behavior, treat BLOCK the same as MISS**: timeout eligibility, rebound handling, possession flip, `_previousTurnWasShot`, get-back/release logic, stat application, next_play_type, etc. Only the ball animation differs (MISS → shot to rim; BLOCK → ball to block spot then rebound).
- **Implementation audit:** Anywhere the frontend (or backend) checks `result_type === "MISS"` for non-animation behavior (e.g. "was this a shot attempt?", "should we flip possession on DREB?", "is previous turn a shot?", "timeout after DREB?"), include **`result_type === "BLOCK"`** in that check so BLOCK is treated like MISS. Only the animation path should branch on BLOCK to run block animation instead of shot animation.

### 1.7 Block Spot (Where the Block Happens)

- **X:** 2–15 **back** from the shooter’s X (toward the offense’s own basket).
  - Home on offense: shooter_x + (-15 to -2) → range [shooter_x − 15, shooter_x − 2].
  - Away on offense: shooter_x + (2 to 15) → range [shooter_x + 2, shooter_x + 15].
- **Y:** shooter_y ± 6 (i.e. `shooter_y + random.randint(-6, 6)` or equivalent).
- Rebound: use this block spot as the **bounce/rebound spot** and run **standard rebound logic** (existing geography-based rebound, `calculate_bounce_spot`-style usage or a dedicated block-spot helper that returns the same shape `{x, y}` so `determine_rebounder` and existing rebound flow are reused).

**Future:** You want location-based rebound adjustments later; the block spot is the single “bounce” location for this turn so current rebound logic stays as-is until that future work.

### 1.8 Team Attributes: Momentum

- When a **block** occurs (outcome = block, not shooting foul):
  - Defense team **momentum +1**.
  - Offense team **momentum −1**.
- Apply to **`team_attributes["momentum"]`** for each team (confirmed as the right place for block impact).

### 1.10 Block Announcement

- When a block occurs, use the **Announcement System** to announce **"BLOCK!"** and show the **blocker’s image** (same pattern as other player-centric announcements, e.g. rebound or steal).
- **Timing:** "BLOCK!" is announced **when the ball reaches the block spot** (at the start of the miss path in `ShotAnimationSystem.handleMissedShot`), **before** the rebound is announced, so the order is always Block → Rebound.

### 1.9 Stats and Fouls

- **Block:** Defender credited with a block (BLK); shooter’s FGA (and 3PTA if applicable) recorded; shot is a miss; no points. **Possession:** Possession flips **only on DREB** (same as any miss). OREB does not flip possession; defense +1 / offense −1 momentum still applies when the block occurs.
- **Shooting foul (from block reconciliation):** Use existing shooting-foul stat and free-throw flow (defender foul, shooter FTs, optional and-one bucket from shooter_finish_score).

---

## 2. Integration Points (Reuse)

- **Shot type:** Reuse existing `shot_type` (inside / attack / outside) from `resolve_shot()`; only inside/attack enter block attempt.
- **Shot score:** Reuse `calculate_shot_score()` output; block reconciliation uses that value (and possibly the same defender used there for block height/ID/IQ).
- **Aggression:** Reuse `def_team.strategy_settings["aggression"]` and/or `strategy_calls["aggression_call"]`; add a single helper that maps to the numeric x used in “y < x”.
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
   - Add **block attempt** step in `resolve_shot()`: after `shot_type` and **pre–defense-penalty** shot_score (and motion attack penalty) are available. If `shot_type` in (`"inside"`, `"attack"`): x = `def_team.strategy_settings["aggression"]` (0–4), y = `random.randint(0, 10)`, if y < x run block reconciliation.
   - **Block reconciliation:** Use **shot_score before defense penalty**. Inputs = that shot_score, shooter, defender, roles. Compute defender scaled height term, defense_block_score; compare shot_score − defense_block_score using **`BLOCK_RECONCILIATION_SHOOTING_FOUL_THRESHOLD`** and **`BLOCK_RECONCILIATION_BLOCK_THRESHOLD`** from `BackEnd/constants/__init__.py`. If diff > shooting-foul threshold: shooting foul; if diff < −block threshold: block; else: fall back to standard shot (with normal defense penalty and threshold).
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
   - Unit tests: block attempt (y < x vs y ≥ x), block reconciliation (shooting foul / block / else to standard shot), height_score mapping, block spot coordinates.
   - Integration: one inside and one attack shot path that triggers block and one that doesn’t; confirm rebound and possession; confirm no double FGA, correct BLK; confirm shooting-foul-from-block path uses existing foul/FT flow.
   - Regression: existing shot/charge/blocking foul/rebound flows unchanged when block attempt is false or when block reconciliation falls to “else”.

7. **Docs**
   - After implementation: update Shot_System.md to add “Block attempt (inside/attack only)” before shot reconciliation and “Block reconciliation” as an alternative branch; add a short “Block” subsection under animation; reference this doc. Update Rebound_System.md if we add a “block spot” variant of bounce spot.

---

## 4. Clarifications / Alignment Checklist

| Item | Status |
|------|--------|
| Aggression | **Locked:** x = `def_team.strategy_settings["aggression"]` (0–4); y = `random.randint(0, 10)`; block attempt if y < x. |
| height_score formula | **Locked:** `(height_score * 10) + random.randint(-9, 9)` for the scaled height term in defense_block_score (and shooter_finish if same). |
| shot_score in block | **Locked:** Use shot_score **before** defense penalty; defense_block_score is the defense component in the block contest. |
| Possession on block | **Locked:** Possession flips only on DREB; OREB does not flip possession. |
| Shooter_finish height | **Locked:** Use scaled `(height_score * 10) + random.randint(-9, 9)` in shooter_finish_score (same as defender). |
| Momentum | **Locked:** Apply block impact to `team_attributes["momentum"]` (defense +1, offense −1). |
| Animation | **Locked:** Dedicated `result_type: "BLOCK"` in both backend and frontend; treat BLOCK like MISS except ball animation and announcement. |
| Block announcement | **Locked:** Announcement System: "BLOCK!" and show blocker's image. |

---

## 5. Summary

- **Eligibility:** Inside and attack only; outside unchanged.
- **Block attempt:** x = `def_team.strategy_settings["aggression"]` (0–4), y = random 0–10; if y < x → block reconciliation.
- **Block reconciliation:** Use **shot_score before defense penalty**; defense_block_score uses scaled height `(height_score * 10) + random(-9, 9)` plus ID/IQ. shot_score − defense_block_score: > 200 → shooting foul; < −200 → block; else → standard shot.
- **Block outcome:** No shot animation; block spot 2–15 back from shooter, y ±6; standard rebound; **possession flips only on DREB** (OREB does not flip); defense +1 / offense −1 momentum; BLK and FGA recorded.
- **Animation:** Dedicated `result_type: "BLOCK"` in backend and frontend. BLOCK is treated like MISS everywhere except: (1) ball animation (block anim, no shot arc), (2) announcement ("BLOCK!" + blocker image via Announcement System). Audit: wherever code checks for MISS for non-animation behavior, include BLOCK.
- **Announcement:** On block, Announcement System announces "BLOCK!" and shows blocker's image.
- **Reuse:** Same shot_type, pre-penalty shot_score from calculate_shot_score (block uses it before penalty), aggression 0–4, rebound flow, result shape, persistence, foul/FT handling.

**Implementation notes (post-implementation):**
- Block announcement order: "BLOCK!" is fired from `ShotAnimationSystem.handleMissedShot` when `result_type === 'BLOCK'` (turnData._blockAnnounced set); `finalizeTurnAfterAnimation` only announces BLOCK if `!turn._blockAnnounced` (fallback).
- Ball snap fix: `executeCompleteShotSequence` uses block spot (`ball_bounce_x`/`ball_bounce_y`) as `rimCoords` for BLOCK so the miss path (bounce, rebound) never references the rim for blocks.
