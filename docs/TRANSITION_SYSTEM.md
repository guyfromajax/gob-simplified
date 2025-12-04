# Transition System

> **Last Updated:** January 2025  
> **Status:** Definitive reference for turn-to-turn transitions

## Overview

This document defines the **complete data and execution requirements** for turn-to-turn transitions in the GOB game engine. A transition encompasses everything that happens between one turn completing and the next turn beginning.

---

## Comprehensive Transition Data Components

### A. Next Turn Routing Data

**Purpose:** Tells the backend what turn type to create next

**Backend Fields:**
- `next_play_type` → Turn type to create (`"BASELINE_INBOUND"`, `"HCO"`, `"FAST_BREAK"`, `"FREE_THROW"`, `"SIDE_INBOUND"`)
- `next_defensive_setup` → Pressure type (`"FCP"`, `"HCT"`, `"HCO"`, `None`)
- `offensive_state` → Backend routing state (internal, persistent across API calls)

**Where Set:**
- Shot handlers (`shot_manager.py`)
- Phase resolution handlers (`phase_resolution.py`)
- Turn manager (`turn_manager.py`)

**Example:**
```python
result["next_play_type"] = "BASELINE_INBOUND"
result["next_defensive_setup"] = "FCP"
game_state["offensive_state"] = "FCP"  # For next API call routing
```

---

### B. Frontend Animation Data

**Purpose:** Provides all data needed to animate the turn visually

**Backend Fields:**
- `animations[]` → Player movements, actions, coords per step
- `hasBallAtStep[]` → Ball ownership per step (legacy, being phased out)
- **Active player IDs:**
  - `shooter_id`, `ball_handler`, `defender_id`
  - `rebounder_id`, `stealer_id`, `victim_id`
  - `passer_id`, `receiver_id`
- **Turn-specific data:**
  - `shot_spot`, `rim_coords`, `ballSpot`
  - `offense_getback[]`, `defense_release[]`
  - `offense_rebounders[]`, `defense_rebounders[]`
- **Announcement data:**
  - `text` → Turn description for text scroll
  - `result_type` → Used by announcement system

**Where Set:**
- Animator (`animator.py`) creates animation packets
- Handlers add turn-specific fields

**Example:**
```python
result["animations"] = animator.skeleton_to_animations(...)
result["shooter_id"] = shooter.player_id
result["shot_spot"] = {"x": 75, "y": 20}
```

---

### C. Possession Management

**Purpose:** Ensures correct team is on offense for each turn

**Backend Responsibility:**
- Sets `result["offense_team_id"] = game.offense_team.team_id` (team on offense DURING this turn)
- Uses `possession_flips` as **internal flag** (tells backend when to call `switch_possession()`)
- Flips possession during transition if `possession_flips=True`
- Next turn automatically has correct `game.offense_team` (updated state)

**Frontend Responsibility:**
- Reads `turnData.offense_team_id` from each turn
- Sets `scene.offenseTeamId = turnData.offense_team_id` (simple assignment, no flip logic)
- Emits `possessionChange` event if value changes

**Where Backend Flips (Current Code):**
1. **OREB turns** (`game_manager.py` line 176-178)
2. **Side inbound setup** (`game_manager.py` line 200-205) - Dead ball turnovers, offensive fouls

**Where Backend DOESN'T Flip (Frontend handles):**
- Made shots (HCO, Fast Break) - Frontend flips in `runInboundSetup()`
- Free throws - Frontend flips in `FreeThrowAnimationSystem`
- OREB putbacks - Frontend flips in `handleOrebTurn()`

**⚠️ Current Issue:** Possession flips happen in **multiple places** (backend AND frontend), causing bugs

**Example:**
```python
# Backend
if result.get("possession_flips"):
    self.switch_possession()
    result["possession_flips"] = False  # Clear to prevent frontend double flip
```

---

### D. Game State Updates

**Purpose:** Track scoring, fouls, stats, clock

**Backend Updates:**
- **Scoring:** `result["points"]`, `result["scoring_team"]`
- **Team fouls:** `def_team.team_fouls += 1`, `off_team.team_fouls += 1`
- **Player stats:** `player.record_stat("FGM")`, `player.record_stat("AST")`, etc.
- **Clock:** `result["time_elapsed"]`, `game.quarter`, `game.period`
- **Stat deltas:** Changes from this turn (for frontend UI updates)

**Where Updated:**
- Handlers update stats directly on player/team objects
- `game_manager.update_team_stats()` called after each turn
- Frontend receives deltas for scoreboard updates

**Example:**
```python
apply_scoring(game, off_team, shooter, points, ["FGM"])
shooter.record_stat("AST")
result["points"] = 2
result["scoring_team"] = off_team.name
```

---

### E. Scene State Updates (Frontend)

**Purpose:** Track animation context and sequences across turns

**Frontend State:**
- `scene.offenseTeamId` → Current offense team (from `offense_team_id`)
- `scene.currentPressureType` → FCP/HCT sequence tracking (`"FCP"` | `"HCT"` | `null`)
- `scene.pressureSequenceActive` → Boolean flag for active pressure
- `scene._previousTurnWasShot` → Context for next turn (skip step 0 ball attachment)
- `scene._previousTurnWasInbound` → Context for HCO setup (uncapped durations)
- `scene.gameState.ballHolder` → Ball ownership (synchronized with BallController)
- **State machine:** Transitions between states (HalfCourt, Inbound, FastBreak, etc.)

**Where Updated:**
- `turnPreparation.js` - Universal transition handler
- Individual handlers - Set context flags
- State machine - FSM transitions

**Example:**
```javascript
scene.offenseTeamId = turnData.offense_team_id;
scene.currentPressureType = "FCP";
scene.pressureSequenceActive = true;
```

---

### F. Validation & Verification

**Purpose:** Ensure transitions are valid and catch bugs

**Backend Validation:**
- `validate_transition()` → Checks if transition is legal
- Transition validator → Validates from_turn → to_turn with possession change
- Logging → Tracks all transitions for debugging

**Where Validated:**
- `game_manager.py` after each turn
- Logs warnings for invalid transitions (non-blocking)

**Example:**
```python
is_valid, error = validate_transition(
    from_result=previous_result,
    to_offensive_state=game_state["offensive_state"],
    possession_changed=result.get("possession_flips", False)
)
if not is_valid:
    logging.warning(f"⚠️ Invalid transition: {error}")
```

---

## Summary: What's Included in a Transition

| Component | Backend | Frontend | Current Status |
|-----------|---------|----------|----------------|
| **A. Routing Data** | Sets next_play_type, next_defensive_setup | Reads and routes | ✅ Standardized |
| **B. Animation Data** | Creates animations[], sets active player IDs | Animates | ✅ Standardized |
| **C. Possession** | Flips if needed, sets offense_team_id | Reads and displays | ⚠️ **FRAGMENTED** (flips in multiple places) |
| **D. Game State** | Updates scores, fouls, stats, clock | Displays updates | ✅ Standardized |
| **E. Scene State** | Provides data | Updates scene state, FSM | ✅ Working |
| **F. Validation** | Validates transitions | N/A | ✅ Working |

**Key Issue:** Component C (Possession) is fragmented across backend AND frontend. This causes possession flip bugs.

---

## Current State (After Revert)

**Current Approach**: Decentralized - Each handler directly sets `game_state["offensive_state"]`:
- `shot_manager.py`: Sets state for shot outcomes
- `phase_resolution.py`: Sets state for free throws, turnovers, fast breaks, FCP/HCT
- `turn_manager.py`: Sets state for OREB outcomes
- `game_manager.py`: Sets state for inbound passes

**Total locations**: 26+ places where `offensive_state` is set directly

## Standardization Analysis

### Option 1: Full Standardization (Single Transition Handler)
**Pros**:
- Single source of truth for all transitions
- Easy to validate all transitions in one place
- Consistent logging/error handling

**Cons**:
- **Over-engineering**: Different handlers need different data (rebound data, foul data, pressure type, etc.)
- **Complexity**: Would need to pass all possible data to a single function
- **Tight coupling**: All handlers would depend on transition handler
- **Less flexible**: Hard to handle edge cases that need custom logic

### Option 2: Lightweight Validation Layer (Recommended)
**Pros**:
- **SS&S aligned**: Keeps current working system, adds validation
- **Non-intrusive**: Doesn't require refactoring existing code
- **Flexible**: Handlers keep their specific logic
- **Validates**: Catches invalid transitions without blocking functionality
- **Easy to implement**: Just add validation calls

**Cons**:
- Transitions still set in multiple places (but that's actually fine - each handler knows its context)

### Option 3: No Standardization
**Pros**:
- Current system works
- No changes needed

**Cons**:
- No validation of transitions
- Hard to catch bugs
- No centralized logging

## Recommendation: Option 2 - Lightweight Validation Layer

### Implementation

Add validation **after** handlers set `offensive_state`, without changing how they set it:

```python
# In game_manager.py, after simulate_macro_turn completes:
from BackEnd.utils.transition_validator import validate_transition

# After result is created, validate the transition
is_valid, error = validate_transition(
    from_result=previous_result,  # Track previous turn's result
    to_offensive_state=game_state["offensive_state"],
    possession_changed=result.get("possession_flips", False),
    game_state=game_state
)

if not is_valid:
    logging.warning(f"⚠️ Invalid transition detected: {error}")
    # Don't block - just log for debugging
```

### Why This Works

1. **Different handlers need different data**:
   - Shot handler needs: shooter, defender, make/miss, foul info
   - Free throw handler needs: makes_shot, free_throws_remaining, bonus status
   - Turnover handler needs: turnover_type, stealer, fast_break_chance
   - OREB handler needs: rebounder, putback result, kickout option

2. **Each handler is the expert** for its domain - they know best what the next state should be

3. **Validation layer** ensures correctness without dictating implementation

## Data Structure Standardization

**Current result structure** is already fairly standardized:
```python
result = {
    "result_type": "MAKE" | "MISS" | "FOUL" | "STEAL" | etc.,
    "possession_flips": bool,
    "next_play_type": "BASELINE_INBOUND" | "HCO" | etc.,  # Informational
    "next_defensive_setup": "FCP" | "HCT" | None,  # For pressure
    # ... handler-specific fields
}
```

**Recommendation**: Keep this structure. It's already standardized enough. Different handlers add their own fields as needed (e.g., `shooter`, `rebounder`, `stealer`), which is fine.

## Next Steps

1. **Add validation logging** (non-blocking) to `game_manager.simulate_macro_turn()`
2. **Track previous turn result** for validation
3. **Create integration tests** for all 51 transitions
4. **Add code comments** referencing transition registry

This gives us:
- ✅ Validation without over-engineering
- ✅ Flexibility for handler-specific logic
- ✅ SS&S: Simple, Stable, Scalable
- ✅ Easy to debug transition issues

