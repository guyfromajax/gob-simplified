# Time Elapsed System

This document details how time elapsed is calculated for each turn type in the game. Time elapsed is measured in seconds and is deducted from the game clock.

## Turn Types That Elapse Time

### HCO (Half Court Offense)

**Location:** `BackEnd/models/shot_manager.py` - `resolve_shot()` method (lines 980-996)

**Calculation:**
- **Normal HCO (without pressure phase):**
  - Uses `get_time_elapsed(tempo_call)` function based on offensive tempo setting
  - **Slow tempo:** `int(max(5, min(35, random.gauss(28, 6))))` seconds
  - **Normal tempo:** `int(max(5, min(35, random.gauss(22, 6))))` seconds
  - **Fast tempo:** `int(max(4, min(15, random.gauss(16, 4))))` seconds

- **HCO after FCP/HCT (with pressure phase):**
  - If `pressure_phase_time > 0` (set by previous FCP/HCT turn):
    - HCO time: `random.randint(max(1, 15 - pressure_phase_time), min(35, 35 - pressure_phase_time))`
    - Total time: `hco_time + pressure_phase_time`
    - The `pressure_phase_time` is cleared after use

**Code Reference:**
```python
pressure_phase_time = game_state.get("pressure_phase_time", 0)

if pressure_phase_time > 0:
    min_time = max(1, 15 - pressure_phase_time)
    max_time = min(35, 35 - pressure_phase_time)
    hco_time = random.randint(min_time, max_time)
    time_elapsed += hco_time + pressure_phase_time
    game_state["pressure_phase_time"] = 0
else:
    tempo = off_team.strategy_calls["tempo_call"]
    time_elapsed += get_time_elapsed(tempo)
```

**Helper Function:** `BackEnd/utils/shared.py` - `get_time_elapsed(tempo_call)` (lines 108-116)

#### How `tempo_call` is Determined

**Location:** `BackEnd/models/turn_manager.py` - `set_strategy_calls()` method (lines 1419-1433)

**Flow:**
1. **User Override (if applicable):**
   - If the user's team is on offense and has set a `tempo_override`:
     - `tempo_call = tempo_override` (directly uses user's selection: "slow", "normal", or "fast")
     - The override is cleared after use

2. **Team Strategy Setting (default):**
   - Reads `strategy_settings["tempo"]` (integer 0-4) from the offensive team
   - Maps the tempo setting to a tempo call using `STRATEGY_CALL_DICTS["tempo"]`:
     - **0:** `["slow"]` → Always "slow"
     - **1:** `["slow", "normal"]` → Randomly selects "slow" or "normal"
     - **2:** `["normal"]` → Always "normal"
     - **3:** `["normal", "fast"]` → Randomly selects "normal" or "fast"
     - **4:** `["fast"]` → Always "fast"
   - Randomly selects one value from the list

**Code Reference:**
```python
if is_offense_user:
    tempo_override = self.game.offense_team.strategy_calls.get("tempo_override")
    if tempo_override:
        self.game.offense_team.strategy_calls["tempo_call"] = tempo_override
        # Clear override after use
        self.game.offense_team.strategy_calls["tempo_override"] = None
    else:
        tempo_setting = self.game.offense_team.strategy_settings.get("tempo", 2)
        self.game.offense_team.strategy_calls["tempo_call"] = random.choice(STRATEGY_CALL_DICTS["tempo"][tempo_setting])
else:
    tempo_setting = self.game.offense_team.strategy_settings.get("tempo", 2)
    self.game.offense_team.strategy_calls["tempo_call"] = random.choice(STRATEGY_CALL_DICTS["tempo"][tempo_setting])
```

**Constants:** `BackEnd/constants/__init__.py` - `STRATEGY_CALL_DICTS["tempo"]` (lines 89-95)

**Summary:**
- `strategy_settings["tempo"]` (0-4 integer) → `STRATEGY_CALL_DICTS["tempo"][tempo_setting]` (list of strings) → `random.choice()` → `tempo_call` (string: "slow", "normal", or "fast") → `get_time_elapsed(tempo_call)` → `time_elapsed` (seconds)

---

### Fast Break

**Location:** `BackEnd/engine/phase_resolution.py` - `resolve_fast_break_logic()` function

**Calculation:**
- **Defensive Stop:** Fixed `3` seconds
  - **Code Location:** Line 1222
  - Used when defense successfully stops the fast break attempt

- **Shot Attempts (MAKE/MISS):** `random.randint(5, 10)` seconds
  - **Code Location:** `BackEnd/models/shot_manager.py` - `resolve_fast_break_shot()` method (line 1497)
  - Applies to all fast break shot attempts regardless of outcome

**Code Reference:**
```python
# Defensive Stop
result = {
    "result_type": "DEFENSIVE_STOP",
    "time_elapsed": 3,
    # ...
}

# Shot Attempt
time_elapsed = random.randint(5, 10)
```

---

### FCP (Full Court Press)

**Location:** `BackEnd/engine/phase_resolution.py` - `resolve_full_court_press_logic()` function (lines 4612-4643)

**Calculation:**
- **FCP Phase Time:** `random.randint(5, 9)` seconds
- **Special Case:** If FCP transitions to HCO (result_type == "HCO"):
  - FCP time is stored in `game_state["pressure_phase_time"]`
  - This stored time is later added to the HCO time calculation (see HCO section above)
  - The FCP time itself is still returned in the turn result

**Code Reference:**
```python
# Calculate time elapsed for FCP phase
fcp_time_elapsed = random.randint(5, 9)

# If transitioning to HCO, store the FCP time for HCO to add to its time
if result_type == "HCO":
    game_state["pressure_phase_time"] = fcp_time_elapsed

result = {
    "result_type": result_type,
    "time_elapsed": fcp_time_elapsed,  # Time spent in FCP phase
    # ...
}
```

---

### HCT (Half Court Trap)

**Location:** `BackEnd/engine/phase_resolution.py` - `resolve_half_court_trap_logic()` function (lines 5585-5616)

**Calculation:**
- **HCT Phase Time:** `random.randint(5, 9)` seconds
- **Special Case:** If HCT transitions to HCO (result_type == "HCO"):
  - HCT time is stored in `game_state["pressure_phase_time"]`
  - This stored time is later added to the HCO time calculation (see HCO section above)
  - The HCT time itself is still returned in the turn result

**Code Reference:**
```python
# Calculate time elapsed for HCT phase
hct_time_elapsed = random.randint(5, 9)

# If transitioning to HCO, store the HCT time for HCO to add to its time
if result_type == "HCO":
    game_state["pressure_phase_time"] = hct_time_elapsed

result = {
    "result_type": result_type,
    "time_elapsed": hct_time_elapsed,  # Time spent in HCT phase
    # ...
}
```

---

### OREB (Offensive Rebound)

**Location:** `BackEnd/utils/shared.py` - `resolve_offensive_rebound()` function (lines 140-255)

**Calculation:**

#### Putback Attempt (90% chance)
- **Time Elapsed:** `random.randint(2, 5)` seconds
- **Code Location:** Line 162
- Applies to both made and missed putback attempts

#### Kickout (10% chance)
- **Time Elapsed:** `random.randint(1, 3)` seconds
- **Code Location:** Line 241 (stored as `duration`)
- Used when rebounder passes ball out to PG instead of attempting putback

**Code Reference:**
```python
if random.random() < 0.90:  # 90% putback attempt
    time_elapsed = random.randint(2, 5)
    # ... putback logic ...
else:  # 10% kickout
    duration = random.randint(1, 3)
    # ... kickout logic ...
    return {
        "event_type": "KICKOUT_RESET",
        "timeElapsed": duration,
        # ...
    }
```

---

### Opening Tip

**Location:** `BackEnd/utils/opening_tip.py` - `execute_opening_tip()` function (lines 157-160)

**Calculation:**
- **Current Implementation:** `0` seconds (time consumption disabled)
- **Previous Implementation (commented out):** `random.randint(2, 5)` seconds
- **Reason for Change:** Disabled to prevent clock issues at game start

**Code Reference:**
```python
# ✅ TEMPORARILY DISABLED: Opening tip no longer consumes time to avoid clock issues
# time_elapsed = random.randint(2, 5)
time_elapsed = 0  # Set to 0 to prevent clock consumption
```

---

## Turn Types That Do NOT Elapse Time

The following turn types explicitly set `time_elapsed = 0`:

### Free Throws
- **Location:** `BackEnd/engine/phase_resolution.py` - `resolve_free_throw_logic()` function (line 1497)
- **Reason:** Clock does not run during free throw attempts

### TNS (Turn Navigation System) Instances
- All TNS instances (timeouts, quarter breaks, etc.) do not consume game time
- **Location:** `BackEnd/models/turn_manager.py` - `call_timeout()` method (line 1878)

---

## Additional Time Elapsed Instances

### DREB (Defensive Rebound)

**Location:** `BackEnd/models/rebound_manager.py` - `handle_rebound()` method (line 73)

**Calculation:**
- **Time Elapsed:** `random.randint(3, 6)` seconds
- **Note:** DREB is typically handled as part of other turn outcomes (e.g., missed shots) rather than as a standalone turn type. However, when `ReboundManager.handle_rebound()` is called directly, it returns this time elapsed value.

**Code Reference:**
```python
return {
    "result_type": stat,  # "DREB" or "OREB"
    "time_elapsed": random.randint(3, 6),
    # ...
}
```

---

## Notes

1. **Outlet Passes:** Outlet passes (from DREB to Fast Break) do not have separate time elapsed. They are part of the Fast Break turn sequence and do not consume additional time beyond the Fast Break calculation.

2. **Post-Steal Actions:** Steals that transition to Fast Break or HCO do not have separate time elapsed. The time is consumed by the resulting turn type (Fast Break or HCO).

3. **Pressure Phase Time:** When FCP or HCT transitions to HCO, the pressure phase time is stored and added to the HCO time calculation. This ensures the total time reflects both the pressure phase and the subsequent half-court offense.

4. **Time Tracking:** All time elapsed values are tracked in `player.stats["game"]["MIN"]` for all active players (both teams) at the end of each turn, but only if `time_elapsed > 0`.

5. **Clock Management:** Time elapsed is deducted from `game_state["time_remaining"]` in `BackEnd/models/turn_manager.py` - `update_clock_and_possession()` method (line 2472).

