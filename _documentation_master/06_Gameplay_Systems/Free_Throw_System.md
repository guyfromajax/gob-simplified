## Free Throw System ✅ **COMPLETE** (January 2025; re-verified June 2026)

**Base Constants**

1. **Free Throw Score Formula**: `(FT * 0.8) + (CH * 0.2)`
   - FT (Free Throw): 80% weight
   - CH (Clutch): 20% weight
2. **Random Roll**: `random.randint(1, 100)` (1-100 range)
3. **Primary Success Check**: `result < ft_shot_score` → MAKE
4. **Secondary Check (Miss-to-Make Conversion)**: chance to convert miss to make. **Home shooter:** `FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE = 0.40`. **Away shooter:** reduced by the home crowd factor (`effective_ft_miss_to_make_second_chance`): factor ≤1 → 0.40, factor 2–3 → **0.30**, factor ≥4 → **0.20**. See `Home_Crowd_System.md`.
5. **Bonus Thresholds**:
   - 5-9 team fouls: 1-and-1 free throws (must make first to unlock second)
   - 10+ team fouls: 2 free throws (double bonus)
6. **Shooting Foul Free Throws**:
   - 2-point shot attempts: 2 free throws
   - 3-point shot attempts: 3 free throws
   - Always awarded regardless of team foul count

**Free Throw Resolution Flow (8 Steps)**

1. **Get Shooter**
   - Shooter = `game_state.get("shooter")` or `game_state.get("last_ball_handler")`
   - Raise error if no shooter found

2. **Calculate Free Throw Score**
   - Formula: `(FT * 0.8) + (CH * 0.2)`
   - Roll: `random.randint(1, 100)`
   - Primary check: `makes_shot = result < ft_shot_score`

3. **Apply Secondary Check (Miss-to-Make Conversion)**
   - If `makes_shot = False`: chance to convert to make via `effective_ft_miss_to_make_second_chance(game, off_team)`
   - `if random.random() < effective_ft_miss_to_make_second_chance(...): makes_shot = True`
   - Home shooter (or away with crowd factor ≤1) → 0.40; away with crowd factor 2–3 → 0.30; ≥4 → 0.20

4. **Record Stat and Build Animation**
   - Record `FTA` (Free Throw Attempt) for shooter
   - Build animation packet via `animator.capture_free_throw_animation()`
   - Set `attempts = ["MAKE"]` or `["MISS"]`

5. **Handle 1-and-1 Front-End Logic**
   - If `one_and_one = True` and `free_throws_remaining = 1`:
     - If MAKE: Unlock second FT (`free_throws_remaining = 1`, `one_and_one = False`)
     - If MISS: End sequence (`free_throws_remaining = 0`, route to rebound)

6. **Decrement Free Throws Remaining**
   - `game_state["free_throws_remaining"] -= 1` (standard decrement)

7. **Handle Final Free Throw Outcomes**
   - **If `free_throws_remaining <= 0`**:
     - **MAKE**: Determine defensive pressure type (FCP/HCT/HCO), set `next_play_type = "BASELINE_INBOUND"`
     - **MISS**: 
       - Calculate bounce spot (basket being attacked)
       - Use unified geography-based rebound system
       - If DREB: Possession flips, route to FAST_BREAK or HCO
       - If OREB: Store for separate OREB turn processing

8. **Return Result**
   - Include `free_throws_remaining`, `one_and_one` flag, `next_play_type`, and rebound info (if MISS)

**Long Form Documentation**

### Overview

The **Free Throw System** handles free throw shot attempts and outcomes. Free throws are awarded for shooting fouls, bonus situations (5+ team fouls), and double bonus situations (10+ team fouls).

**Key Functions:**
- `resolve_free_throw_logic()` - Handles free throw calculation and outcomes in `BackEnd/engine/phase_resolution.py`
- `capture_free_throw_animation()` - Builds animation packet in `BackEnd/models/animator.py`
- `FreeThrowAnimationSystem` - Handles free throw animations in frontend

### Free Throw Calculation

**Primary Formula:**
```python
ft_shot_score = (attrs["FT"] * 0.8) + (attrs["CH"] * 0.2)
result = random.randint(1, 100)
makes_shot = result < ft_shot_score
```

**Components:**
1. **Player Attributes:**
   - `FT` (Free Throw) - 80% weight
   - `CH` (Clutch) - 20% weight

2. **Random Roll:** `random.randint(1, 100)` (1-100 range)

3. **Success Comparison:**
   - Compares `result` (random 1-100) to `ft_shot_score` (calculated from attributes)
   - If `result < ft_shot_score` → **MAKE**
   - If `result >= ft_shot_score` → **MISS**

**Secondary Check (Miss-to-Make Conversion):**
After the initial calculation, if the free throw is a miss, there is a chance to convert it to a make. The probability comes from `effective_ft_miss_to_make_second_chance(game, off_team)` (`BackEnd/utils/home_crowd.py`):
```python
if not makes_shot:
    if random.random() < effective_ft_miss_to_make_second_chance(game, off_team):
        makes_shot = True
        ft_made_on_second_chance = True
```

- **Home shooter** (`off_team.is_home_team`): `FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE = 0.40`.
- **Away shooter**: scaled down by `home_crowd_factor` — factor ≤1 → 0.40, factor 2–3 → **0.30**, factor ≥4 → **0.20**. This is a home-court free-throw pressure effect; see `Home_Crowd_System.md`.

This secondary check provides a "second chance" mechanic that increases overall free throw percentage, helping to achieve the target FT% of ~72% per game (lower for away shooters in a loud building).

**Example (home shooter):**
- Player with `FT = 80`, `CH = 70`
- `ft_shot_score = (80 * 0.8) + (70 * 0.2) = 64 + 14 = 78`
- Random roll: `80` (1-100)
- Initial result: `80 >= 78` → **MISS**
- Secondary check (home, 0.40): `random.random() = 0.35` (35% < 40%) → **CONVERTED TO MAKE**
- Final result: **MAKE**

### When Free Throws Are Awarded

**Shooting Fouls:**
- 2 free throws for 2-point shot attempts
- 3 free throws for 3-point shot attempts
- Always awarded regardless of team foul count

**Bonus Situations (Non-Shooting Fouls):**
- **5-9 team fouls:** 1-and-1 free throws (must make first to unlock second)
- **10+ team fouls:** 2 free throws (double bonus)

**1-and-1 Logic:**
- First free throw must be made to unlock the second
- If first is missed, possession changes (defensive rebound)
- Front-end logic handled in `resolve_free_throw_logic()` (lines 1419-1448)

### Free Throw Outcomes

**Made Free Throw:**
- Awards 1 point
- Decrements `free_throws_remaining`
- If last free throw, determines next defensive setup (pressure type: FCP/HCT/HCO)
- Next play type: `BASELINE_INBOUND` (after made shot)
- Possession flips (unless `no_lane = True`)

**Missed Free Throw:**
- No points awarded
- Rebound logic determines offensive or defensive rebound
- Uses unified geography-based rebound system:
  - Calculate bounce spot (basket being attacked)
  - Home team attacks away basket (x=91), away team attacks home basket (x=9)
  - Use `calculate_bounce_spot()` and `determine_rebounder()` functions
- If defensive rebound: Next play type determined by fast break chance (FAST_BREAK or HCO)
- If offensive rebound: Stored for separate OREB turn processing
- Time elapsed: 0 seconds (clock does not run during free throws)

### 1-and-1 Free Throw Logic

**Front-End Handling:**
- When `one_and_one = True` and `free_throws_remaining = 1`:
  - **If MAKE**: Unlock second FT
    - Set `free_throws_remaining = 1` (second FT now available)
    - Set `one_and_one = False` (no longer in 1-and-1 mode)
    - Return result with `free_throws_remaining = 1` so frontend knows more FTs remain
  - **If MISS**: End sequence
    - Set `free_throws_remaining = 0`
    - Set `one_and_one = False`
    - Route to rebound (defensive rebound, possession changes)

**Implementation:**
```python
if game_state.get("one_and_one", False):
    if game_state["free_throws_remaining"] == 1:
        if makes_shot:
            # Made front end → unlock second FT
            game_state["free_throws_remaining"] = 1
            game_state["one_and_one"] = False
            return result  # Return with free_throws_remaining = 1
        else:
            # Missed front end → dead ball, rebound
            game_state["free_throws_remaining"] = 0
            game_state["one_and_one"] = False
            game_state["offensive_state"] = "HCO"
```

### Rebound Handling (Final FT only)

**Missed Final Free Throw Rebound:**
- Authoritative rebound resolves only when `free_throws_remaining <= 0` (final attempt).
- Uses unified geography-based rebound system (same as HCO, Fast Break, Putback):
  - Calculate `bounce_spot` via `calculate_bounce_spot()` from the basket being attacked.
  - Use `determine_rebounder()` to find closest player to bounce spot.
- **Defensive Rebound (DREB)**: possession flips → next play = FAST_BREAK (if FB chance) or HCO. A discrete DREB schema turn is built via `_build_dreb_turn_from_miss`.
- **Offensive Rebound (OREB)**: stored in `game_state["pending_oreb"]` → separate OREB turn fires next.

**Non-final FT misses** do not run authoritative rebound logic — the ball returns to the shooter for the next attempt (see Animation Sequence below).

---

### Animation Sequence (UESS Schema)

One backend turn = one FT attempt. The FT emitter (`BackEnd/engine/ft_step_emitter.py`) builds `animation_steps[]` per the UESS contract. Clock is **pinned** for the entire FT turn (no game-clock burn). Every `_ball_motion_step` stamps `advance_trigger.metadata.free_throw_shot = True` so the FE's 400ms `SHOT_BALL_MIN_WALL_CLOCK_MS` step-wait floor is bypassed for FT ball steps (the floor exists for non-FT shot-ball steps only).

**Common step prefix (every FT turn):**

| Step | Coords | Notes |
|---|---|---|
| Lane setup | All 10 walk to lane positions; shooter to FT line | Gate = all 10 (every player aligned before shot) |
| Shoot | Shooter `shoot` action / `shot_motion` archetype | Ball attached |
| Ball flight | Ball: shot_spot → MSSS (make) or rim (miss) | Rate: `FREE_THROW_SHOT_GRID_PER_GAME_SECOND` (12 grid/sec). Arrival SFX: `free-throw-swish.wav` (make) / `free-throw-miss.wav` (miss). |

Outcome-specific tails:

#### MAKE (final or non-final)

| Step | Coords | T |
|---|---|---|
| `[make_hold]` | Ball at MSSS; all players stationary | `0.0` game-sec; `start.announcement` = `"It's Good!"` with `hold_ms=1000` (announcement drives the 1000ms wall-clock rim hold; FE's `runStepAnnouncement` pauses both clocks during the hold) |
| **Non-final only** — return to shooter | Ball: MSSS → shooter's lane spot | `distance / 12` game-sec; ball reattaches to shooter for next FT |
| **Final only** — implicit turn end | — | Routes to next turn (BIP / HCO / DREB / OREB depending on `next_play_type`) |

#### Non-final MISS (4-step recovery)

| Step | Coords | T |
|---|---|---|
| 2. Bounce | Ball: rim → bounce_spot | `distance / 12` game-sec |
| 3. Bounce hold | Ball stationary at bounce_spot | `1000ms / 350ms-per-game-sec ≈ 2.857` game-sec (= 1000ms wall) |
| 4a. Baseline travel | Ball: bounce_spot → baseline OOB | `distance / 12` game-sec |
| 4b. Fast return | Ball: baseline → shooter's lane spot | `distance / 40` game-sec (FB pass rate — snappy ball-boy return). Ball reattaches to shooter. |

#### Final MISS

| Step | Coords | T |
|---|---|---|
| 2. Bounce | Ball: rim → authoritative `ball_bounce_x/y` (from `calculate_bounce_spot`) | `max(BOUNCE_STEP_GAME_SECONDS, distance/12)` |
| Implicit turn end | — | Routes to discrete DREB (`_build_dreb_turn_from_miss`) or OREB (`pending_oreb`) |

#### Bounce spot direction (non-final miss)

The non-final miss `bounce_spot` is a visual stand-in computed inline (the authoritative `calculate_bounce_spot` only runs on final misses):

```python
mid_ft_x_offset = 5.0 if away_offense else -5.0
bounce = {"x": rim["x"] + mid_ft_x_offset, "y": rim["y"]}
```

Direction is **away from the basket toward midcourt**:
- Away offense (rim x=9) → bounce x = **14**
- Home offense (rim x=91) → bounce x = **86**

Y stays at the rim y (25, centered). Baseline OOB spot in step 4a is `x=3` (away offense) / `x=97` (home offense), `y=25`.

---

### Key Files

**Backend (game logic):**
- `BackEnd/engine/phase_resolution.py`
  - `resolve_free_throw_logic()` — FT calculation, outcome handling, 1-and-1 logic, rebound determination, next play routing
- `BackEnd/models/turn_manager.py`
  - `determine_defensive_pressure_type()` — FCP/HCT/HCO selection after a made final FT
- `BackEnd/utils/shared.py`
  - `calculate_bounce_spot()` — authoritative bounce spot (used for final-miss rebound)
  - `determine_rebounder()` — unified rebound system

**Backend (animation):**
- `BackEnd/engine/ft_step_emitter.py`
  - `build_ft_animation_steps()` — UESS schema emitter (lane setup + shoot + ball flight + outcome tail per the tables above)
  - `_ball_motion_step()` — universal FT ball-motion step builder (stamps FT meta so FE bypasses the 400ms shot-ball floor)

**Frontend:**
- `FrontEnd/static/js/phaser/animation/animationPlayback.js` — schema engine that plays the FT `animation_steps[]` (primary path)
- `FrontEnd/static/js/phaser/animation/FreeThrowAnimationSystem.js`, `freeThrow.js` — legacy FE FT handlers; mid-FT rebound outlet was removed (see comments in those files) and the schema engine is now authoritative for FT turn rendering

### Future Enhancements

- **Foul Shooting Pressure**: Consider game situation (clutch time, score differential) for secondary check probability
- **Free Throw Streaks**: Track consecutive makes/misses for momentum effects
- **Technical Fouls**: Add support for technical foul free throws (1 shot + possession)
