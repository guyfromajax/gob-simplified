## Motion Offense Shot Resolution System ✅ **COMPLETE** (January 2025)

**Base Constants**

1. **Shot Types**: Inside, Outside, Attack
2. **Playcall Mapping**: `{"inside": "Inside", "outside": "Outside", "attack": "Attack"}`
3. **Drive Step Timestamp Offset**: 300ms between drive and shoot steps
4. **Drive Destinations**:
   - **Upper locations** → `["upper lowPost", "upper midPost", "upper bird", "midLane", "basketSpot"]`
   - **Lower locations** → `["lower lowPost", "lower midPost", "lower bird", "midLane", "basketSpot"]`
   - **Central locations** → All destinations (both upper and lower)
5. **Key Functions**:
   - `resolve_motion_offense_shot()` - Main shot resolution function
   - `_create_attack_drive_shoot_steps()` - Creates two-step drive + shoot sequence
   - `_determine_attack_drive_destination()` - Determines valid drive destinations
   - `_check_inside_shot_possibility()` - Checks if inside shot is possible
   - `_check_attack_shot_possibility()` - Checks if attack shot is possible
   - `_check_outside_shot_possibility()` - Checks if outside shot is possible
   - `_build_shot_type_weighted_list()` - Builds weighted list for shot type selection
   - `_apply_attack_penalty()` - Calculates penalty if player stopped short
6. **Key Files**:
   - `BackEnd/engine/phase_resolution.py` - Main implementation
   - `BackEnd/models/animator.py` - Animation processing

**Motion Offense Shot Resolution Flow (8 Steps)**

1. **Select Random Step**: Choose step 1-N (excluding step 0) for shot attempt, truncate skeleton at selected step
2. **Identify Ball Handler**: Find ball handler position and location at selected step from `pos_actions`
3. **Check Possibilities**: Determine which shot types are possible (inside/attack/outside) based on ball handler location and available receivers
4. **Build Weighted List**: Create weighted list based on strategy settings (`inside`, `attack`, `outside` weights) and shot type possibilities
5. **Select Shot Type**: Randomly select from weighted list (inside, outside, or attack)
6. **Execute Shot**:
   - **Inside**: Ball handler shoots from current location OR passes to inside receiver who shoots
   - **Outside**: Ball handler shoots from current location OR passes to outside receiver who shoots
   - **Attack**: Create two steps (drive action → shoot action) and append to skeleton
7. **Append Steps**: Add new shot steps to truncated skeleton
8. **Return Results**: Modified skeleton with shot steps, shooter info, shot type, playcall, and attack penalty

**Long Form Documentation**

### Overview

The Motion Offense Shot Resolution System handles shot attempts in Motion offense plays. Unlike Set Plays which have predetermined shot locations, Motion plays dynamically determine shot type (inside/outside/attack) based on player positions and strategy settings.

**Key Function:** `resolve_motion_offense_shot()` in `BackEnd/engine/phase_resolution.py`

### Shot Type Determination

Motion offense shots are determined dynamically based on:
1. **Ball handler location** at the selected step
2. **Available receivers** at inside/outside locations
3. **Strategy settings** (inside/attack/outside weights)
4. **Player attributes** (IQ can influence decisions)

**Three Shot Types:**

1. **Inside Shots:**
   - Ball handler at inside location → shoots from current spot
   - OR ball handler passes to receiver at inside location → receiver shoots
   - Uses `playcall = "Inside"` for shot calculation

2. **Outside Shots:**
   - Ball handler at outside location → shoots from current spot
   - OR ball handler passes to receiver at outside location → receiver shoots
   - Uses `playcall = "Outside"` for shot calculation

3. **Attack Shots:**
   - Ball handler at non-lane spot chooses to drive
   - **Two-step process** (critical for proper animation):
     - **Step 1:** `action: "drive"` to destination lane spot
     - **Step 2:** `action: "shoot"` at destination lane spot
   - Uses `playcall = "Attack"` for shot calculation
   - **Note:** Two-step approach ensures proper drive animation and accurate shot location detection

### Attack Drive Implementation

**Function:** `_create_attack_drive_shoot_steps()`

**Returns:** List of two steps `[drive_step, shoot_step]`

**Drive Step:**
```python
{
    "timestamp": timestamp,
    "pos_actions": {
        ball_handler_pos: {
            "location": destination_location,  # e.g., "basketSpot"
            "action": "drive"
        }
    },
    "events": []
}
```

**Shoot Step:**
```python
{
    "timestamp": timestamp + 300,
    "pos_actions": {
        ball_handler_pos: {
            "location": destination_location,  # Same as drive step
            "action": "shoot"
        }
    },
    "events": [{"type": "shot"}],
    "_attack_drive": {
        "start_location": start_location,
        "intended_destination": destination_location,
        "final_location": final_location,
        "stopped_short": False
    }
}
```

**Why Two Steps?**

1. **Proper Animation:** Frontend animator needs separate `drive` action to create movement animation from start → destination
2. **Accurate Shot Location:** Frontend shot detection finds `shoot` action at final location (not start location)
3. **3-Point Detection:** Shot location detection uses final step's location, ensuring correct 3-point classification
4. **Visual Clarity:** Users see the drive animation before the shot, making the play more realistic

**Drive Destinations:**

Based on starting location:
- **Upper locations** → `["upper lowPost", "upper midPost", "upper bird", "midLane", "basketSpot"]`
- **Lower locations** → `["lower lowPost", "lower midPost", "lower bird", "midLane", "basketSpot"]`
- **Central locations** → All destinations (both upper and lower)

### Execution Flow Details

**Phase 1: Select Random Step**
- Choose step 1-N (excluding step 0) for shot attempt
- Truncate skeleton at selected step
- Store last timestamp for new step creation

**Phase 2: Identify Ball Handler**
- Find ball handler position and location at selected step from `pos_actions`
- Look for actions: `handle_ball`, `receive`, or `pass`
- Extract ball handler position (e.g., "PG", "SG") and location (e.g., "upper wing", "key")

**Phase 3: Check Shot Possibilities**
- `_check_inside_shot_possibility()`: Checks if ball handler is at inside location OR if there are available inside receivers
- `_check_attack_shot_possibility()`: Checks if ball handler is NOT at inside location (attack shots require non-inside starting position)
- `_check_outside_shot_possibility()`: Checks if ball handler is at outside location OR if there are available outside receivers
- Each function returns boolean possibility and list of viable receivers/players

**Phase 4: Build Weighted List**
- Get strategy settings from `off_team.strategy_settings` (`inside`, `attack`, `outside` weights)
- `_build_shot_type_weighted_list()` creates weighted list based on:
  - Strategy settings (user preferences)
  - Shot type possibilities (what's actually available)
  - Ball handler location (if at inside, inside shots get weight boost)
- Returns list like `["inside", "inside", "attack", "outside"]` for random selection

**Phase 5: Select Shot Type**
- Randomly select from weighted list
- Log selected shot type for debugging

**Phase 6: Execute Shot**

**Inside Shot Execution:**
- If ball handler at inside location:
  - Create single shoot step at current location
- Else (ball handler not at inside):
  - Find closest inside receiver using `_find_closest_receiver()`
  - Create pass/receive step
  - Create shoot step for receiver
  - Update shooter to receiver

**Outside Shot Execution:**
- If ball handler at outside location:
  - Create single shoot step at current location
- Else (ball handler not at outside):
  - Find closest outside receiver using `_find_closest_receiver()`
  - Create pass/receive step
  - Create shoot step for receiver
  - Update shooter to receiver

**Attack Shot Execution:**
- Determine valid drive destinations using `_determine_attack_drive_destination(ball_handler_location)`
- Randomly select destination from valid destinations
- Create two steps using `_create_attack_drive_shoot_steps()`:
  - Drive step: Player moves to destination with `action: "drive"`
  - Shoot step: Player shoots at destination with `action: "shoot"` (300ms later)
- Calculate attack penalty using `_apply_attack_penalty()` if player was stopped short
- Update shooter location to final destination

**Phase 7: Append Steps**
- Append all new steps to truncated skeleton
- Skeleton now contains: original steps up to selected step + new shot steps

**Phase 8: Return Results**
- Map shot type to playcall: `{"inside": "Inside", "outside": "Outside", "attack": "Attack"}`
- Return dictionary with:
  - `skeleton`: Modified skeleton with shot steps
  - `shooter`: Player object who will take the shot
  - `shooter_pos`: Position of shooter (e.g., "PG", "C")
  - `shooter_location`: Location where shot will be taken
  - `shot_type`: "inside", "outside", or "attack"
  - `playcall`: "Inside", "Outside", or "Attack" (for shot calculation)
  - `attack_penalty`: Penalty value if attack shot was stopped short (0 otherwise)

### Attack Penalty System

**Function:** `_apply_attack_penalty(shot_location, is_away_offense)`

**Purpose:** Calculate penalty if player was stopped short of intended destination during attack drive

**Logic:**
- No penalty for ideal spots: `["basketSpot", "upper lowPost", "lower lowPost"]`
- For other locations: Calculate distance from shot location to basket
- Penalty = `abs(shot_coords["x"] - basket_coords["x"])`
- Penalty is subtracted from shot score during shot calculation

**Note:** Currently, defensive stop logic is not fully implemented (TODO in code), so `stopped_short` is always `False`. Penalty calculation is prepared for future implementation.

### Integration with Shot Detection

**3-Point Detection:**
- Uses `shooter_location` from final step (shoot step for attack shots)
- Compares location against `THREE_POINT_SPOTS` constant
- Two-step approach ensures correct location is detected (not start location for attack shots)

**Shot Calculation:**
- Uses `playcall` parameter ("Inside", "Outside", "Attack") for shot calculation
- `playcall` determines which attribute weights to use:
  - Inside: SC=6, ST=2, IQ=1, CH=1
  - Attack: SC=5, AG=2, ST=1, IQ=1, CH=1
  - Outside: SH=8, IQ=1, CH=1
- Applies attack penalty if `attack_penalty > 0` (subtracted from shot score)
- Uses base shot calculation (no variant modifier for Motion plays, unlike Set Plays)

### Key Files

**Backend:**
- `BackEnd/engine/phase_resolution.py`
  - `resolve_motion_offense_shot()` (lines 3104-3298) - Main shot resolution function
  - `_create_attack_drive_shoot_steps()` (lines 3008-3068) - Creates drive + shoot steps
  - `_determine_attack_drive_destination()` (lines 2945-2963) - Determines valid drive destinations
  - `_check_inside_shot_possibility()` (lines 2767-2808) - Checks if inside shot is possible
  - `_check_attack_shot_possibility()` (lines 2810-2816) - Checks if attack shot is possible
  - `_check_outside_shot_possibility()` (lines 2818-2840) - Checks if outside shot is possible
  - `_build_shot_type_weighted_list()` (lines 2842-2903) - Builds weighted list for shot type selection
  - `_apply_attack_penalty()` (lines 3071-3101) - Calculates penalty if stopped short
  - `_create_pass_receive_step()` (lines 2966-2986) - Creates pass/receive step
  - `_create_shoot_step()` (lines 2989-3005) - Creates shoot step

**Frontend:**
- `BackEnd/models/animator.py` - Converts skeleton steps to animation data
  - Processes `drive` action to create movement animation
  - Processes `shoot` action to trigger shot animation
  - Processes `pass` and `receive` actions for pass animations

### Differences from Set Play Shot Resolution

**Motion Offense:**
- Shot type determined dynamically during resolution
- Shot location determined by player positions and strategy settings
- Uses `base_loop` skeleton (no variants)
- No variant modifier applied to shot threshold
- Attack shots use two-step drive + shoot process

**Set Plays:**
- Shot location predetermined in skeleton
- Shot type determined from skeleton analysis (location + drive detection)
- Uses variant skeletons (`successful`, `mid_play_change`, `contested`, `broken`)
- Variant modifier applied to shot threshold
- Attack shots detected from skeleton (drive action before shoot action)

