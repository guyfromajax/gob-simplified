## Free Throw System ✅ **COMPLETE** (January 2025)

**Base Constants**

1. **Free Throw Score Formula**: `(FT * 0.7) + (CH * 0.2) + MO`
   - FT (Free Throw): 70% weight
   - CH (Clutch): 20% weight
   - MO (Momentum): Full value (not weighted)
2. **Random Roll**: `random.randint(1, 100)` (1-100 range)
3. **Primary Success Check**: `result < ft_shot_score` → MAKE
4. **Secondary Check (Miss-to-Make Conversion)**: 40% chance to convert miss to make
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
   - Formula: `(FT * 0.7) + (CH * 0.2) + MO`
   - Roll: `random.randint(1, 100)`
   - Primary check: `makes_shot = result < ft_shot_score`

3. **Apply Secondary Check (Miss-to-Make Conversion)**
   - If `makes_shot = False`: 40% chance to convert to make
   - `if random.random() < 0.40: makes_shot = True`

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
ft_shot_score = (attrs["FT"] * 0.7) + (attrs["CH"] * 0.2) + attrs["MO"]
result = random.randint(1, 100)
makes_shot = result < ft_shot_score
```

**Components:**
1. **Player Attributes:**
   - `FT` (Free Throw) - 70% weight
   - `CH` (Clutch) - 20% weight
   - `MO` (Momentum) - Full value added (not weighted)

2. **Random Roll:** `random.randint(1, 100)` (1-100 range)

3. **Success Comparison:**
   - Compares `result` (random 1-100) to `ft_shot_score` (calculated from attributes)
   - If `result < ft_shot_score` → **MAKE**
   - If `result >= ft_shot_score` → **MISS**

**Secondary Check (Miss-to-Make Conversion):**
After the initial calculation, if the free throw is a miss, there is a **40% chance** to convert it to a make:
```python
if not makes_shot:
    if random.random() < 0.40:
        makes_shot = True
```

This secondary check provides a "second chance" mechanic that increases overall free throw percentage, helping to achieve the target FT% of 72% per game.

**Example:**
- Player with `FT = 80`, `CH = 70`, `MO = 5`
- `ft_shot_score = (80 * 0.7) + (70 * 0.2) + 5 = 56 + 14 + 5 = 75`
- Random roll: `80` (1-100)
- Initial result: `80 >= 75` → **MISS**
- Secondary check: `random.random() = 0.35` (35% < 40%) → **CONVERTED TO MAKE**
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

### Rebound Handling

**Missed Free Throw Rebound:**
- Uses unified geography-based rebound system (same as HCO, Fast Break, Putback)
- Calculate bounce spot from basket being attacked
- Use `determine_rebounder()` to find closest player to bounce spot
- **Defensive Rebound (DREB)**:
  - Possession flips
  - Next play type: FAST_BREAK (if fast break chance) or HCO
  - Route to appropriate transition
- **Offensive Rebound (OREB)**:
  - Stored in `game_state["pending_oreb"]` for separate OREB turn processing
  - OREB turn created separately (not in same turn as free throw)

### Key Files

**Backend:**
- `BackEnd/engine/phase_resolution.py`
  - `resolve_free_throw_logic()` - Free throw calculation and outcome handling (lines 1379-1541)
  - Handles 1-and-1 logic, rebound determination, and next play type routing
- `BackEnd/models/turn_manager.py`
  - `determine_defensive_pressure_type()` - Determines FCP/HCT/HCO after made free throw
- `BackEnd/utils/shared.py`
  - `calculate_bounce_spot()` - Calculates bounce spot for missed free throw
  - `determine_rebounder()` - Unified rebound system for all missed shots

**Frontend:**
- `FrontEnd/static/js/phaser/animation/FreeThrowAnimationSystem.js` - Free throw animation orchestration
- `FrontEnd/static/js/phaser/animation/freeThrow.js` - Free throw sequence handler

### Future Enhancements

- **Foul Shooting Pressure**: Consider game situation (clutch time, score differential) for secondary check probability
- **Free Throw Streaks**: Track consecutive makes/misses for momentum effects
- **Technical Fouls**: Add support for technical foul free throws (1 shot + possession)

