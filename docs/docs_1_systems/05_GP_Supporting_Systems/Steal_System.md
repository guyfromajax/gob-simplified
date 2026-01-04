## Steal System ✅ **COMPLETE** (January 2025)

**Base Constants**

1. **Steal Entry Movement (Fast Break)**:
   - X: 5-10 spots toward basket (`STEAL_ENTRY_MOVE_X_MIN = 5`, `STEAL_ENTRY_MOVE_X_MAX = 10`)
   - Y: ±4 spots (`STEAL_ENTRY_MOVE_Y_RANGE = 4`)
   - Y Clamp: 3-47 (`STEAL_ENTRY_Y_MIN = 3`, `STEAL_ENTRY_Y_MAX = 47`)
2. **Steal HCO Setup Movement (HCO)**:
   - X: 3-7 spots away from basket (`STEAL_HCO_SETUP_MOVE_X_MIN = 3`, `STEAL_HCO_SETUP_MOVE_X_MAX = 7`)
   - Y: ±3 spots (`STEAL_HCO_SETUP_MOVE_Y_RANGE = 3`)
   - Y Clamp: 3-47 (`STEAL_HCO_SETUP_Y_MIN = 3`, `STEAL_HCO_SETUP_Y_MAX = 47`)
3. **Other Players Movement (HCO Setup)**: X: 15-30 spots toward new offense basket, Y: ±6 spots (clamped 4-46)
4. **Defensive Stop Y-Range**: `DEFENSIVE_STOP_Y_RANGE = 6` (same as DREB Fast Breaks)
5. **Fast Break Chance (Aggression-Based)**: `{0: 0.0, 1: 0.25, 2: 0.5, 3: 0.75, 4: 1.0}` (based on offensive team's aggression setting)

**Steal System Flow (6 Steps)**

1. **Steal Occurs**
   - Steal happens in FCP, HCT, or HCO turn (via `resolve_steal_attempt()`)
   - Ball attached to stealer (defender who made the steal)
   - `game_state["last_stealer"]` set to stealer
   - `game_state["last_stealer_coords"]` stored (position at moment of steal)

2. **Determine Next Turn Type**
   - Fast break chance determined by `get_fast_break_chance()` using **offensive team's aggression setting**
   - If fast break chance succeeds → `offensive_state = "FAST_BREAK"`
   - If fast break chance fails → `offensive_state = "HCO"`

3. **Steal Entry (Fast Break Path)**
   - **Trigger**: `offensive_state = "FAST_BREAK"` after steal
   - **Movement**: Stealer moves 5-10 x spots toward basket, ±4 y spots (clamped 3-47)
   - **Direction**: Toward offense basket (home: +X toward x=90, away: -X toward x=10)
   - **Ball**: Remains attached to stealer throughout movement
   - **No Outlet Pass**: Steal-initiated Fast Breaks bypass outlet phase

4. **Steal HCO Setup (HCO Path)**
   - **Trigger**: `offensive_state = "HCO"` after steal
   - **Movement**: Stealer moves 3-7 x spots away from basket, ±3 y spots (clamped 3-47)
   - **Direction**: Away from offense basket (opposite of Steal Entry)
   - **Ball**: Remains attached to stealer throughout movement
   - **Other Players**: All 9 other players move 15-30 x spots toward new offense basket, ±6 y spots
   - **Timing**: Runs as first step of HCO turn, before skeleton animation

5. **Fast Break Resolution (if Fast Break Path)**
   - After Steal Entry movement, uses same logic as DREB Fast Breaks:
     - Check if defender is ahead AND within ±6 y-coords
     - If yes: Skill check (break_score vs stop_score)
     - If defender wins skill check → DEFENSIVE_STOP
     - If ball handler wins skill check → SHOT (beats defender)
     - Otherwise → SHOT

6. **HCO Skeleton Animation (if HCO Path)**
   - After Steal HCO Setup movement, proceeds with normal HCO skeleton animation
   - Stealer's position after setup becomes starting point for skeleton

**Long Form Documentation**

### Overview

The **Steal System** handles steal-initiated transitions for Fast Breaks and HCO turns. The system includes two bespoke movement steps:
- **Steal Entry**: Moves the stealer toward the basket before Fast Break resolution (defensive stop or shot attempt)
- **Steal HCO Setup**: Moves the stealer away from the basket before HCO skeleton animation begins

**Key Functions:**
- `resolve_fast_break_logic()` - Handles steal entry movement and outcome determination in `BackEnd/engine/phase_resolution.py`
- `resolve_half_court_offense_logic()` - Handles steal HCO setup movement in `BackEnd/engine/phase_resolution.py`
- `animateStealEntry()` - Animates stealer movement for Fast Breaks in `FrontEnd/static/js/phaser/animation/fastBreak.js`
- `animateStealHCOSetup()` - Animates stealer movement for HCO in `FrontEnd/static/js/phaser/animation/turnAnimation.js`

**Current Implementation:**
- ✅ **Fast Break**: Steal → Steal Entry → Fast Break resolution
- ✅ **HCO**: Steal → Steal HCO Setup → HCO skeleton animation
- ✅ **FCP/HCT**: Steal → Steal Entry/Setup → Fast Break or HCO (both paths implemented)

### When Steal Steps Activate

**Steal Entry (Fast Break):**
- After a steal occurs in FCP, HCT, or HCO turns
- When the next turn is determined to be a Fast Break (based on team aggression setting)
- Ball is already attached to the stealer from the steal turn
- No outlet pass occurs (steal-initiated Fast Breaks bypass outlet phase)

**Steal HCO Setup (HCO):**
- After a steal occurs in FCP, HCT, or HCO turns
- When the next turn is determined to be HCO (fast break chance fails)
- Ball is already attached to the stealer from the steal turn
- Runs as the first step of the HCO turn, before skeleton animation

**State Flow (Fast Break):**
1. Steal occurs → Ball attached to stealer
2. Fast break chance determined by `get_fast_break_chance()` using team **aggression** setting
3. If Fast Break → Steal Entry step executes
4. Stealer moves 5-10 x spots toward basket, ±4 y spots (clamped to 3-47)
5. After movement, defensive stop vs shot determination occurs
6. Fast Break resolution proceeds (shot attempt or defensive stop)

**State Flow (HCO):**
1. Steal occurs → Ball attached to stealer
2. Fast break chance determined by `get_fast_break_chance()` using team **aggression** setting
3. If HCO (fast break chance fails) → Steal HCO Setup step executes
4. Stealer moves 3-7 x spots away from basket, ±3 y spots (clamped to 3-47)
5. All 9 other players move 15-30 x spots toward new offense basket, ±6 y spots
6. After movement, HCO skeleton animation proceeds normally

### Steal Entry Movement

**Movement Parameters:**
- **X Movement**: Random 5-10 grid spots toward offense basket
  - Home team: +5 to +10 (toward x=90)
  - Away team: -10 to -5 (toward x=10)
- **Y Movement**: Random -4 to +4 grid spots
  - Clamped to y min = 3, y max = 47 (stays in bounds)

**Constants:**
- `STEAL_ENTRY_MOVE_X_MIN = 5`
- `STEAL_ENTRY_MOVE_X_MAX = 10`
- `STEAL_ENTRY_MOVE_Y_RANGE = 4` (±4 y-coords)
- `STEAL_ENTRY_Y_MIN = 3`
- `STEAL_ENTRY_Y_MAX = 47`

**Implementation:**
```python
# Backend: BackEnd/engine/phase_resolution.py
ball_handler_start_x = getattr(ball_handler, "coords", {}).get("x", 50)
ball_handler_start_y = getattr(ball_handler, "coords", {}).get("y", 25)

# Use stored stealer position from skeleton step (if available)
if "last_stealer_coords" in game_state and game_state["last_stealer_coords"]:
    stealer_coords = game_state["last_stealer_coords"]
    ball_handler_start_x = stealer_coords.get("x", 50)
    ball_handler_start_y = stealer_coords.get("y", 25)

steal_entry_move_x = random.randint(STEAL_ENTRY_MOVE_X_MIN, STEAL_ENTRY_MOVE_X_MAX)
steal_entry_move_y = random.randint(-STEAL_ENTRY_MOVE_Y_RANGE, STEAL_ENTRY_MOVE_Y_RANGE)

ball_handler_after_entry_x = ball_handler_start_x + (direction * steal_entry_move_x)
ball_handler_after_entry_y = max(STEAL_ENTRY_Y_MIN, min(STEAL_ENTRY_Y_MAX, ball_handler_start_y + steal_entry_move_y))

# Store in fb_roles for frontend
fb_roles["ball_handler_move_x"] = steal_entry_move_x
fb_roles["ball_handler_move_y"] = steal_entry_move_y
fb_roles["ball_handler_outlet_x"] = ball_handler_after_entry_x
fb_roles["ball_handler_outlet_y"] = ball_handler_after_entry_y
fb_roles["is_steal_entry"] = True
```

**Frontend Animation:**
```javascript
// Frontend: FrontEnd/static/js/phaser/animation/fastBreak.js
const moveX = turnData.roles?.ball_handler_move_x || 
              Phaser.Math.Between(STEAL_ENTRY_MOVE_X_MIN, STEAL_ENTRY_MOVE_X_MAX);
const moveY = turnData.roles?.ball_handler_move_y || 
              Phaser.Math.Between(-STEAL_ENTRY_MOVE_Y_RANGE, STEAL_ENTRY_MOVE_Y_RANGE);

const targetGrid = {
  x: currentGrid.x + (direction * moveX),
  y: Phaser.Math.Clamp(
    currentGrid.y + moveY,
    STEAL_ENTRY_Y_MIN,
    STEAL_ENTRY_Y_MAX
  )
};
```

### Defensive Stop vs Shot Determination (Steal-Initiated Fast Break)

After the stealer completes the steal entry movement, the system uses the **same logic as DREB Fast Breaks** to determine if it's a defensive stop or shot attempt:

**Logic (HOME Orientation):**

**Home Offense:**
- Basket at x=90 (larger x is closer to basket)
- Defender ahead if: `defender_x >= stealer_x` (after steal entry movement)
- **Defender must also be within ±6 y-coords of stealer**
- If defender ahead AND within y-range → Skill check (geography + skill)
- Otherwise → SHOT

**Away Offense:**
- Basket at x=10 (smaller x is closer to basket)
- Defender ahead if: `defender_x <= stealer_x` (after steal entry movement)
- **Defender must also be within ±6 y-coords of stealer**
- If defender ahead AND within y-range → Skill check (geography + skill)
- Otherwise → SHOT

**Y-Coord Range Barrier:**
- Uses `DEFENSIVE_STOP_Y_RANGE = 6` (same as DREB Fast Breaks)
- Defender must be within ±6 y-coords of stealer to force defensive stop
- If defender is ahead but outside y-range, it becomes a shot attempt

**Multiple Defenders:**
- If multiple defenders meet both conditions (ahead AND within y-range), the closest one (by x-distance) forces the defensive stop
- If no defender meets both conditions, the closest defender overall (by Euclidean distance) becomes the shot defender

### Integration with Fast Break System

**Steal-Initiated Fast Break Flow:**

1. **Steal Entry Phase** (Bespoke Step)
   - Stealer moves 5-10 x spots toward basket, ±4 y spots (clamped)
   - Ball remains attached to stealer throughout movement
   - No outlet pass occurs (steal-initiated Fast Breaks bypass outlet phase)

2. **Defensive Stop vs Shot Check**
   - Uses stealer's position **after** steal entry movement
   - Applies same logic as DREB Fast Breaks (defender ahead AND within ±6 y-coords)
   - If geography check passes, skill check determines outcome

3. **Fast Break Resolution**
   - If SHOT → Animate shot attempt (same as DREB Fast Breaks)
   - If DEFENSIVE_STOP → Animate defensive stop (same as DREB Fast Breaks)

**Key Differences from DREB Fast Breaks:**
- **No Outlet Pass**: Steal-initiated Fast Breaks skip the outlet pass phase
- **Steal Entry Step**: Stealer moves before defensive stop/shot determination
- **Ball Attachment**: Ball is already attached to stealer from steal turn, remains attached during steal entry

**Backend Data Flow:**
```python
# Backend stores steal entry movement in fb_roles
fb_roles["ball_handler_move_x"] = steal_entry_move_x
fb_roles["ball_handler_move_y"] = steal_entry_move_y
fb_roles["ball_handler_outlet_x"] = ball_handler_after_entry_x  # Position after steal entry
fb_roles["ball_handler_outlet_y"] = ball_handler_after_entry_y
fb_roles["is_steal_entry"] = True  # Flag to indicate steal entry vs outlet pass
```

**Frontend Animation Flow:**
```javascript
// Frontend: FrontEnd/static/js/phaser/animation/fastBreak.js
if (turnData.roles?.is_steal_entry || (!turnData.roles?.outlet_passer && !turnData.roles?.outlet_receiver)) {
  // Steal Entry Phase
  await animateStealEntry(scene, turnData, playerSprites, ballSprite, width, height);
}

// Then proceed with Fast Break resolution (shot or defensive stop)
if (result === "MAKE" || result === "MISS") {
  await animateFastBreakShot(scene, turnData, playerSprites, ballSprite, width, height);
} else {
  await animateDefensiveStop(scene, turnData, playerSprites, ballSprite, width, height);
}
```

### Steal HCO Setup Movement

**Movement Parameters:**
- **X Movement**: Random 3-7 grid spots away from offense basket
  - Home team: -7 to -3 (away from x=90, toward x=10)
  - Away team: +3 to +7 (away from x=10, toward x=90)
- **Y Movement**: Random -3 to +3 grid spots
  - Clamped to y min = 3, y max = 47 (stays in bounds)

**Constants:**
- `STEAL_HCO_SETUP_MOVE_X_MIN = 3`
- `STEAL_HCO_SETUP_MOVE_X_MAX = 7`
- `STEAL_HCO_SETUP_MOVE_Y_RANGE = 3` (±3 y-coords)
- `STEAL_HCO_SETUP_Y_MIN = 3`
- `STEAL_HCO_SETUP_Y_MAX = 47`

**Other Players Movement (HCO Setup):**
- **X Movement**: Random 15-30 grid spots toward new offense basket
- **Y Movement**: Random -6 to +6 grid spots
- **Y Clamp**: 4-46 (`STEAL_HCO_SETUP_OTHER_PLAYERS_Y_MIN = 4`, `STEAL_HCO_SETUP_OTHER_PLAYERS_Y_MAX = 46`)

**Implementation:**
```python
# Backend: BackEnd/engine/phase_resolution.py
ball_handler_start_x = getattr(ball_handler, "coords", {}).get("x", 50)
ball_handler_start_y = getattr(ball_handler, "coords", {}).get("y", 25)

# Use stored stealer position from skeleton step (if available)
if "last_stealer_coords" in game_state and game_state["last_stealer_coords"]:
    stealer_coords = game_state["last_stealer_coords"]
    ball_handler_start_x = stealer_coords.get("x", 50)
    ball_handler_start_y = stealer_coords.get("y", 25)

hco_setup_move_x = random.randint(STEAL_HCO_SETUP_MOVE_X_MIN, STEAL_HCO_SETUP_MOVE_X_MAX)
hco_setup_move_y = random.randint(-STEAL_HCO_SETUP_MOVE_Y_RANGE, STEAL_HCO_SETUP_MOVE_Y_RANGE)

# Direction away from basket (opposite of steal entry)
is_away_offense = off_team.team_id == game.away_team.team_id
if is_away_offense:
    direction = 1  # Away from x=10 (toward x=90)
else:
    direction = -1  # Away from x=90 (toward x=10)

hco_setup_final_x = ball_handler_start_x + (direction * hco_setup_move_x)
hco_setup_final_y = max(STEAL_HCO_SETUP_Y_MIN, min(STEAL_HCO_SETUP_Y_MAX, ball_handler_start_y + hco_setup_move_y))

# Store in roles for frontend
roles["is_steal_hco_setup"] = True
roles["ball_handler_hco_setup_x"] = hco_setup_final_x
roles["ball_handler_hco_setup_y"] = hco_setup_final_y
roles["ball_handler_hco_setup_move_x"] = hco_setup_move_x
roles["ball_handler_hco_setup_move_y"] = hco_setup_move_y
```

**Frontend Animation:**
```javascript
// Frontend: FrontEnd/static/js/phaser/animation/turnAnimation.js
const moveX = turnData.roles?.ball_handler_hco_setup_move_x || 
              Phaser.Math.Between(STEAL_HCO_SETUP_MOVE_X_MIN, STEAL_HCO_SETUP_MOVE_X_MAX);
const moveY = turnData.roles?.ball_handler_hco_setup_move_y || 
              Phaser.Math.Between(-STEAL_HCO_SETUP_MOVE_Y_RANGE, STEAL_HCO_SETUP_MOVE_Y_RANGE);

const targetGrid = {
  x: currentGrid.x + (direction * moveX),
  y: Phaser.Math.Clamp(
    currentGrid.y + moveY,
    STEAL_HCO_SETUP_Y_MIN,
    STEAL_HCO_SETUP_Y_MAX
  )
};
```

### Integration with HCO System

**Steal-Initiated HCO Flow:**

1. **Steal HCO Setup Phase** (Bespoke Step)
   - Stealer moves 3-7 x spots away from basket, ±3 y spots (clamped)
   - All 9 other players move 15-30 x spots toward new offense basket, ±6 y spots
   - Ball remains attached to stealer throughout movement
   - Runs before HCO skeleton animation begins

2. **HCO Skeleton Animation**
   - Proceeds normally after steal HCO setup completes
   - Stealer's position after setup becomes the starting point for skeleton animation

**Key Characteristics:**
- **Movement Direction**: Away from basket (opposite of Steal Entry for Fast Breaks)
- **Timing**: Runs as first step of HCO turn, before skeleton animation
- **Ball Attachment**: Ball is already attached to stealer from steal turn, remains attached during setup
- **Other Players**: All 9 other players reposition toward new offense basket

**Backend Data Flow:**
```python
# Backend stores steal HCO setup movement in roles
roles["is_steal_hco_setup"] = True
roles["ball_handler_hco_setup_x"] = hco_setup_final_x
roles["ball_handler_hco_setup_y"] = hco_setup_final_y
roles["ball_handler_hco_setup_move_x"] = hco_setup_move_x
roles["ball_handler_hco_setup_move_y"] = hco_setup_move_y
roles["ball_handler_id"] = getattr(ball_handler, "player_id", None)

# Clear last_stealer after use to prevent persistence
game_state["last_stealer"] = None
```

**Frontend Animation Flow:**
```javascript
// Frontend: FrontEnd/static/js/phaser/animation/turnAnimation.js
// In playTurnAnimation(), before step loop starts:
if (turnData.roles?.is_steal_hco_setup) {
  await animateStealHCOSetup(scene, turnData, playerSprites, ballSprite);
}

// Then proceed with normal HCO skeleton animation
for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++) {
  // ... skeleton animation steps
}
```

### Fast Break Chance Determination

**Team Aggression Setting:**
- Fast break chance after steals is determined by the **offensive team's aggression setting** (not tempo)
- Function: `get_fast_break_chance()` in `BackEnd/utils/shared.py`
- Aggression levels: 0-4 (0 = 0%, 1 = 25%, 2 = 50%, 3 = 75%, 4 = 100%)

**Implementation:**
```python
def get_fast_break_chance(game):
    """
    Determine fast break probability based on the OFFENSIVE team's aggression setting.
    Called after defensive rebounds or steals when the team is now on offense.
    """
    off_team = game.offense_team
    level = off_team.strategy_settings.get("aggression", 2)
    return [0.0, 0.25, 0.5, 0.75, 1.0][level]
```

**Usage:**
- Called in `resolve_turnover_logic()` when `turnover_type == "STEAL"`
- Determines whether `offensive_state = "FAST_BREAK"` or `offensive_state = "HCO"`
- Same function used for both steal-initiated and DREB-initiated fast breaks

### Key Files

**Backend:**
- `BackEnd/engine/phase_resolution.py`
  - `resolve_fast_break_logic()` - Steal entry movement calculation (lines 926-951)
  - `resolve_half_court_offense_logic()` - Steal HCO setup movement calculation (lines 3572-3604)
- `BackEnd/engine/phase_resolution.py`
  - `resolve_turnover_logic()` - Steal outcome handling and fast break chance determination (lines 1544-1610)
- `BackEnd/constants/fast_break_constants.py` - Steal entry and steal HCO setup constants
- `BackEnd/utils/shared.py` - `get_fast_break_chance()` (aggression-based fast break chance)

**Frontend:**
- `FrontEnd/static/js/phaser/animation/fastBreak.js`
  - `animateStealEntry()` - Steal entry animation for Fast Breaks
  - `runFastBreakSequence()` - Orchestrates Fast Break sequence (checks for steal entry)
- `FrontEnd/static/js/phaser/animation/turnAnimation.js`
  - `animateStealHCOSetup()` - Steal HCO setup animation (lines 128-284)
  - `playTurnAnimation()` - Checks for steal HCO setup before skeleton animation
- `FrontEnd/static/js/phaser/constants/fastBreakConstants.js` - Steal entry and steal HCO setup constants

### Future Enhancements

**Additional Steal Contexts:**
- Consider if steals in other contexts (e.g., during Fast Break) need bespoke setup steps
- May require different movement parameters or logic based on specific context

**Steal Success Rate Calibration:**
- Currently uses HCO resolution system for steal attempts
- Could add context-specific modifiers (e.g., steals during Fast Break might have different success rates)

