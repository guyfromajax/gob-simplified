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

## Ideal SS&S Transition Structure

### Core Principles

1. **Single Source of Truth** - Each piece of data has one authoritative source
2. **Backend Authority** - Backend determines all routing, possession, and game state
3. **Frontend Display** - Frontend reads and displays, doesn't make decisions
4. **Clear Separation** - Backend = logic and state, Frontend = presentation
5. **Consistent Pattern** - All 51 transitions follow the same pattern

### SS&S Transition Pattern

**Backend Responsibilities (Authoritative):**
1. ✅ Execute turn logic (shot, pass, foul, etc.)
2. ✅ Determine outcome (`result_type`, points, stats, etc.)
3. ✅ **Flip possession if needed** (`switch_possession()` if `possession_flips=True`)
4. ✅ Set next turn routing (`next_play_type`, `next_defensive_setup`, `offensive_state`)
5. ✅ Create animation data (`animations[]`, active player IDs)
6. ✅ Set authoritative offense team (`offense_team_id = game.offense_team.team_id` **AFTER flip**)
7. ✅ Validate transition
8. ✅ Return complete turn data to frontend

**Frontend Responsibilities (Display Only):**
1. ✅ Read `offense_team_id` from turn data
2. ✅ Set `scene.offenseTeamId = turnData.offense_team_id` (simple assignment, no flip logic)
3. ✅ Emit `possessionChange` event if value changed
4. ✅ Animate turn using `animations[]` data
5. ✅ Update UI (scoreboard, playcall display, etc.)
6. ✅ Manage scene state (`currentPressureType`, context flags, FSM)
7. ✅ Route to next turn based on `result_type`

**❌ Frontend Does NOT:**
- ❌ Flip possession (backend already did it)
- ❌ Decide next turn type (backend provides it)
- ❌ Calculate scores/stats (backend provides them)
- ❌ Determine pressure type (backend provides it)

### Ideal Turn Data Structure

**Required Fields (ALL transitions):**
```python
{
    # Core identification
    "result_type": str,              # "MAKE", "MISS", "FOUL", "FREE_THROW", etc.
    "offense_team_id": str,          # ✅ SS&S: Team on offense DURING this turn (AFTER flip if applicable)
    
    # Routing (if applicable)
    "next_play_type": str | None,   # "BASELINE_INBOUND", "HCO", "FAST_BREAK", "FREE_THROW", "SIDE_INBOUND"
    "next_defensive_setup": str | None,  # "FCP", "HCT", "HCO", None
    
    # Animation
    "animations": list,              # Player movements, actions, coords
    "text": str,                     # Turn description
    
    # Game state
    "quarter": int,
    "time_elapsed": int,
    "score": dict,                   # {home_team: X, away_team: Y}
    
    # Stats (if applicable)
    "points": int | None,            # Points scored this turn
    "scoring_team": str | None,      # Team that scored
    "deltas": dict,                  # Player stat changes
    
    # Lineups & energy
    "home_lineup": dict,
    "away_lineup": dict,
    "player_energy": dict,
    
    # Turn-specific fields (varies by result_type)
    # ... shooter_id, rebounder_id, stealer_id, etc.
}
```

**Internal Backend Fields (NOT sent to frontend):**
```python
{
    "possession_flips": bool,        # ✅ Internal flag - tells backend to call switch_possession()
    "offensive_state": str,          # ✅ Internal routing state - persists across API calls
}
```

### SS&S Possession Flow

**Backend (Single Location):**
```python
# In game_manager.py, after turn completes:
if result.get("possession_flips"):
    self.switch_possession()        # ✅ Flip possession internally
    result["possession_flips"] = False  # Clear flag (internal only)

# Set offense_team_id AFTER flip (authoritative)
result["offense_team_id"] = self.game.offense_team.team_id
```

**Frontend (Simple Display):**
```javascript
// In turnPreparation.js handleTurnTransition():
if (turnData.offense_team_id) {
    scene.offenseTeamId = turnData.offense_team_id;  // ✅ Simple assignment
    if (scene.offenseTeamId !== previousOffenseTeamId) {
        scene.events.emit('possessionChange', { offenseTeamId: scene.offenseTeamId });
    }
}
```

### Benefits of SS&S Pattern

**Simple:**
- ✅ Backend flips in ONE place (`game_manager.py`)
- ✅ Frontend reads ONE field (`offense_team_id`)
- ✅ No complex flip logic scattered across files

**Stable:**
- ✅ No double flips (backend flips once, frontend just displays)
- ✅ No missed flips (backend always sets `offense_team_id`)
- ✅ Single source of truth (no conflicts)

**Scalable:**
- ✅ Easy to add new turn types (follow same pattern)
- ✅ Easy to test (backend logic isolated)
- ✅ Easy to debug (one place to check possession logic)

### Deviation Detection

**To identify non-SS&S transitions, check if:**
1. ❌ Frontend flips possession (instead of just reading `offense_team_id`)
2. ❌ Backend doesn't set `offense_team_id`
3. ❌ Possession flip happens in handler (instead of `game_manager.py`)
4. ❌ Frontend makes routing decisions (instead of reading `next_play_type`)

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

1. **Standardize possession flips** - Move ALL flips to backend (Component C)
2. **Add validation logging** (non-blocking) to `game_manager.simulate_macro_turn()`
3. **Track previous turn result** for validation
4. **Create integration tests** for all 51 transitions
5. **Add code comments** referencing transition registry

This gives us:
- ✅ Validation without over-engineering
- ✅ Flexibility for handler-specific logic
- ✅ SS&S: Simple, Stable, Scalable
- ✅ Easy to debug transition issues

---

## Complete Transition Registry (51 Total)

**All possible turn-to-turn transitions in the game engine.**

Note: **(PC)** indicates possession change

### Opening Tip Transitions (1)
1. **Opening Tip → HCO**
   - Opening Tip

### Inbound Pass Transitions (3)
2. **Inbound Pass → HCO**
   - Inbound Pass Complete
3. **Inbound Pass → FCP**
   - Inbound Pass Complete, FCP Setup
4. **Inbound Pass → HCT**
   - Inbound Pass Complete, HCT Setup

### Side Inbound Pass Transitions (1)
5. **Side Inbound Pass → HCO**
   - Side Inbound Pass Complete

### HCO Transitions (7)
6. **HCO → Inbound Pass (PC)**
   - Made Shot, No Foul
7. **HCO → Free Throw**
   - Made Shot, Foul
   - Missed Shot, Foul
   - Non-Shooting Defensive Foul, Bonus Situation
8. **HCO → OREB**
   - Missed Shot, OREB
9. **HCO → HCO (PC)**
   - Missed Shot, DREB, HCO next step
   - Steal, HCO next step
10. **HCO → Fast Break (PC)**
    - Missed Shot, DREB, Fast Break next step
    - Steal, Fast Break next step
11. **HCO → Side Inbound Pass**
    - Non-Shooting Defensive Foul, No Bonus
    - Missed Shot, Non-Shooting Defensive Foul
12. **HCO → Side Inbound Pass (PC)**
    - Offensive Foul
    - Dead Ball Turnover
    - Missed Shot, Offensive Foul

### OREB Transitions (8)
13. **OREB → Inbound Pass (PC)**
    - Made Shot, No Foul
14. **OREB → Free Throw**
    - Made Shot, Foul
    - Missed Shot, Foul
15. **OREB → HCO**
    - Kickout Pass
16. **OREB → HCO (PC)**
    - Missed Shot, DREB, HCO next step
17. **OREB → Fast Break (PC)**
    - Missed Shot, DREB, Fast Break next step
18. **OREB → OREB**
    - Missed Shot, OREB
19. **OREB → Side Inbound Pass (PC)**
    - Missed Shot, Offensive Foul
20. **OREB → Side Inbound Pass**
    - Missed shot, Non-Shooting Defensive Foul

### Free Throw Transitions (7)
21. **Free Throw → Inbound Pass (PC)**
    - Final FT Made
22. **Free Throw → OREB**
    - Final FT Missed, OREB
23. **Free Throw → HCO (PC)**
    - Final FT Missed, DREB, HCO next step
24. **Free Throw → Fast Break (PC)**
    - Final FT Missed, DREB, Fast Break next step
25. **Free Throw → Side Inbound Pass**
    - Final Free Throw Missed, Defensive Foul, No Bonus Situation
26. **Free Throw → Free Throw (PC)**
    - Final Free Throw Missed, Defensive Foul, Bonus Situation
27. **Free Throw → Side Inbound Pass (PC)**
    - Final Free Throw Missed, Offensive Foul

### Fast Break Transitions (8)
28. **Fast Break → HCO**
    - Defensive Stop
29. **Fast Break → Inbound Pass (PC)**
    - Made Shot, No Foul
30. **Fast Break → Free Throw**
    - Made Shot, Foul
    - Missed Shot, Foul
    - Non-Shooting Defensive Foul, Bonus Situation
31. **Fast Break → OREB**
    - Missed Shot, OREB
32. **Fast Break → HCO (PC)**
    - Missed Shot, DREB, HCO next step
    - Steal, HCO next step
33. **Fast Break → Fast Break (PC)**
    - Missed Shot, DREB, Fast Break next step
    - Steal, Fast Break next step
34. **Fast Break → Side Inbound Pass**
    - Non-Shooting Defensive Foul, No Bonus Situation
35. **Fast Break → Side Inbound Pass (PC)**
    - Offensive Foul
    - Dead Ball Turnover

### FCP Transitions (8)
36. **FCP → HCO**
    - Press/Trap Break, HCO next step
37. **FCP → Inbound Pass (PC)**
    - Press/Trap Break, Made Shot Attempt, No Foul
38. **FCP → Free Throw**
    - Press/Trap Break, Made Shot Attempt, Shooting Foul
    - Press/Trap Break, Missed Shot Attempt, Shooting Foul
    - Non-shooting Defensive Foul, Bonus Situation
39. **FCP → OREB**
    - Press/Trap Break, Missed Shot Attempt, OREB
40. **FCP → HCO (PC)**
    - Press/Trap Break, Missed Shot Attempt, DREB, HCO next step
    - Steal, HCO as next step
41. **FCP → Fast Break (PC)**
    - Press/Trap Break, Missed Shot Attempt, DREB, Fast Break next step
    - Steal, Fast Break as next step
42. **FCP → Side Inbound Pass (PC)**
    - Offensive Foul
    - Dead Ball Turnover
43. **FCP → Side Inbound Pass**
    - Non-Shooting Defensive Foul

### HCT Transitions (8)
44. **HCT → HCO**
    - Press/Trap Break, HCO next step
45. **HCT → Inbound Pass (PC)**
    - Press/Trap Break, Made Shot Attempt, No Foul
46. **HCT → Free Throw**
    - Press/Trap Break, Made Shot Attempt, Shooting Foul
    - Press/Trap Break, Missed Shot Attempt, Shooting Foul
    - Non-shooting Defensive Foul, Bonus Situation
47. **HCT → OREB**
    - Press/Trap Break, Missed Shot Attempt, OREB
48. **HCT → HCO (PC)**
    - Press/Trap Break, Missed Shot Attempt, DREB, HCO next step
    - Steal, HCO as next step
49. **HCT → Fast Break (PC)**
    - Press/Trap Break, Missed Shot Attempt, DREB, Fast Break next step
    - Steal, Fast Break as next step
50. **HCT → Side Inbound Pass (PC)**
    - Offensive Foul
    - Dead Ball Turnover
51. **HCT → Side Inbound Pass**
    - Non-Shooting Defensive Foul

---

**Total: 51 transitions**

**Breakdown by Turn Type:**
- Opening Tip: 1
- Inbound Pass: 3
- Side Inbound Pass: 1
- HCO: 7
- OREB: 8
- Free Throw: 7
- Fast Break: 8
- FCP: 8
- HCT: 8

**Note:** FCP and HCT have identical transition patterns but are counted separately.

---

## SS&S Transition Evaluation

### Batch 1: HCO Transitions (7 Total)

#### 1. HCO → Inbound Pass (PC) - Made Shot, No Foul

**Handler:** `shot_manager.py` `resolve_shot()` (line 337-379)

**Current Implementation:**
- ✅ Sets `possession_flips = True` (line 337)
- ✅ Sets `next_play_type = "BASELINE_INBOUND"` (line 379)
- ✅ Sets `next_defensive_setup` = pressure type (line 376)
- ✅ Creates animations via animator
- ❌ Backend does NOT flip possession (no `switch_possession()` call)
- ❌ Backend does NOT set `offense_team_id`
- ❌ **Frontend flips possession** in `runInboundSetup()` (turnAnimation.js line 872-884)

**SS&S Compliance:** ❌ **NOT SS&S**

**Issues:**
1. Possession flip happens in frontend (line 872-884 in turnAnimation.js)
2. Frontend calculates `newOffenseSide` and updates `scene.offenseTeamId`
3. No authoritative `offense_team_id` from backend
4. Frontend makes routing decision instead of just displaying

**Fix Required:**
- Backend: Flip possession in `game_manager.py` before creating BASELINE_INBOUND turn
- Backend: Set `result["offense_team_id"]` AFTER flip
- Frontend: Read `offense_team_id` and display (remove flip logic from runInboundSetup)

---

#### 2. HCO → Free Throw - Made/Missed Shot with Foul

**Handlers:** 
- `shot_manager.py` `resolve_shot()` (AND-1, line 341-369)
- `phase_resolution.py` `resolve_non_shooting_foul()` (bonus fouls, line 166-183)

**Current Implementation (AND-1):**
- ✅ Sets `possession_flips = False` (line 342) - Correct, no flip for AND-1
- ✅ Sets `offensive_state = "FREE_THROW"` (line 353)
- ✅ Sets `next_play_type = "FREE_THROW"` (line 357)
- ✅ No possession flip needed (offense keeps ball)
- ❌ Does NOT set `offense_team_id`

**SS&S Compliance:** ⚠️ **PARTIAL**

**Issues:**
1. Missing `offense_team_id` in result

**Fix Required:**
- Backend: Set `result["offense_team_id"] = off_team.team_id` (no flip needed)

---

#### 3. HCO → OREB - Missed Shot, OREB

**Handler:** `shot_manager.py` `resolve_shot()` (line 575-582)

**Current Implementation:**
- ✅ Sets `possession_flips = False` (line 576) - Correct, no flip for OREB
- ✅ Sets `pending_oreb` (line 578) - Triggers OREB turn creation
- ✅ OREB turn flipped in `game_manager.py` (line 176-178) if putback makes
- ❌ Does NOT set `offense_team_id`

**SS&S Compliance:** ⚠️ **PARTIAL**

**Issues:**
1. Missing `offense_team_id` in result
2. OREB turn possession flip is in `game_manager.py` ✅ but original MISS turn doesn't have `offense_team_id`

**Fix Required:**
- Backend: Set `result["offense_team_id"] = off_team.team_id` on MISS turn

---

#### 4. HCO → HCO (PC) - Missed Shot DREB, Steal

**Handlers:**
- `shot_manager.py` `resolve_shot()` (DREB, line 586-619)
- `phase_resolution.py` `resolve_turnover_logic()` (Steal)

**Current Implementation:**
- ✅ Sets `possession_flips = True` (line 586)
- ✅ Sets `next_play_type = "HCO"` (line 619 for DREB)
- ❌ Backend does NOT flip possession in `game_manager.py`
- ❌ Does NOT set `offense_team_id`
- ❌ **No possession flip executed anywhere!**

**SS&S Compliance:** ❌ **NOT SS&S**

**Issues:**
1. Possession flip flag set but NEVER executed (backend or frontend)
2. No `offense_team_id` set
3. Next turn will have wrong offense team

**Fix Required:**
- Backend: Add possession flip in `game_manager.py` for DREB → HCO transitions
- Backend: Set `offense_team_id` AFTER flip

---

#### 5. HCO → Fast Break (PC) - Missed Shot DREB, Steal

**Handlers:**
- `shot_manager.py` `resolve_shot()` (DREB with release, line 586-625)
- `phase_resolution.py` `resolve_turnover_logic()` (Steal with fast break)

**Current Implementation:**
- ✅ Sets `possession_flips = True` (line 586)
- ✅ Sets `next_play_type = "FAST_BREAK"` (line 618)
- ✅ Sets `offensive_state = "FAST_BREAK"` (line 617)
- ❌ Backend does NOT flip possession in `game_manager.py`
- ❌ Does NOT set `offense_team_id`
- ❌ **Frontend flips possession** in `fastBreak.js` (line 548-563)

**SS&S Compliance:** ❌ **NOT SS&S**

**Issues:**
1. Possession flip happens in frontend (fastBreak.js line 548-563)
2. No authoritative `offense_team_id` from backend
3. Frontend makes routing decision

**Fix Required:**
- Backend: Flip possession in `game_manager.py` for DREB → FAST_BREAK transitions
- Backend: Set `offense_team_id` AFTER flip
- Frontend: Remove flip logic from fastBreak.js

---

#### 6. HCO → Side Inbound Pass - Non-Shooting Foul (No Bonus)

**Handler:** `phase_resolution.py` `resolve_non_shooting_foul()` (line 185-186)

**Current Implementation:**
- ✅ Sets `possession_flips` based on foul type (offensive vs defensive)
- ✅ Sets `offensive_state = "HCO"` (line 186)
- ✅ **Backend flips in `game_manager.py`** (line 200-205) before SIP
- ✅ Clears `possession_flips = False` after flip (line 204)
- ✅ SIP turn has `offense_team_id` (turn_manager.py line 131)

**SS&S Compliance:** ✅ **SS&S COMPLIANT**

**No issues found!** This is the gold standard pattern.

---

#### 7. HCO → Side Inbound Pass (PC) - Offensive Foul, Dead Ball

**Handlers:**
- `phase_resolution.py` `resolve_non_shooting_foul()` (offensive fouls)
- `phase_resolution.py` `resolve_turnover_logic()` (dead ball)

**Current Implementation:**
- ✅ Sets `possession_flips = True`
- ✅ Sets `offensive_state = "HCO"` (line 191)
- ✅ **Backend flips in `game_manager.py`** (line 200-205) before SIP
- ✅ Clears `possession_flips = False` after flip (line 204)
- ✅ SIP turn has `offense_team_id` (turn_manager.py line 131)

**SS&S Compliance:** ✅ **SS&S COMPLIANT**

**No issues found!** This is the gold standard pattern.

---

### Batch 1 Summary

| # | Transition | SS&S Status | Primary Issue |
|---|-----------|-------------|---------------|
| 1 | HCO → Inbound Pass (PC) | ❌ NOT SS&S | Frontend flips possession |
| 2 | HCO → Free Throw | ⚠️ PARTIAL | Missing offense_team_id |
| 3 | HCO → OREB | ⚠️ PARTIAL | Missing offense_team_id |
| 4 | HCO → HCO (PC) | ❌ NOT SS&S | Possession flip NEVER executed |
| 5 | HCO → Fast Break (PC) | ❌ NOT SS&S | Frontend flips possession |
| 6 | HCO → Side Inbound (No PC) | ✅ SS&S | None |
| 7 | HCO → Side Inbound (PC) | ✅ SS&S | None |

**Results:**
- ✅ **2 out of 7** are SS&S compliant (29%)
- ⚠️ **2 out of 7** are partial (29%)
- ❌ **3 out of 7** are NOT SS&S (43%)

**Key Finding:** 
**Side Inbound transitions (#6, #7) are the ONLY SS&S-compliant transitions.** They flip possession in `game_manager.py` (single location) and set `offense_team_id` on the SIP turn. This is the gold standard pattern that should be replicated for ALL transitions.

**Common Issues:**
1. **Missing `offense_team_id`** - 5 out of 7 transitions don't set it
2. **Frontend possession flips** - 2 transitions flip in frontend (runInboundSetup, fastBreak.js)
3. **Missing possession flip** - 1 transition sets flag but never executes flip (#4)

---

### Batch 2: Free Throw Transitions (7 Total)

#### 1. Free Throw → Inbound Pass (PC) - Final FT Made

**Handler:** `phase_resolution.py` `resolve_free_throw_logic()` (line 691-698)

**Current Implementation:**
- ✅ Sets `next_defensive_setup` = pressure type (line 692)
- ✅ Sets `possession_team_id` = new offense team (line 696-698)
- ❌ Does NOT set `next_play_type` (should be "BASELINE_INBOUND")
- ❌ Backend does NOT flip possession
- ❌ Backend does NOT set `offense_team_id`
- ❌ **Frontend flips possession** in `FreeThrowAnimationSystem.handleFinalMadeFreeThrow()` (line 477-523)
- ❌ **Frontend calls `runInboundSetup()` directly** (line 513)

**SS&S Compliance:** ❌ **NOT SS&S**

**Issues:**
1. Frontend handles inbound pass (should be BASELINE_INBOUND turn)
2. Frontend flips possession (calculates newOffenseSide from shooter sprite)
3. No authoritative `offense_team_id` from backend
4. Duplicates HCO made shot pattern (same frontend code path)

**Fix Required:**
- Same as HCO → Inbound Pass (use gold standard pattern)

---

#### 2. Free Throw → OREB - Final FT Missed, OREB

**Handler:** `phase_resolution.py` `resolve_free_throw_logic()` (line 640-644, sets pending_oreb)

**Current Implementation:**
- ✅ Sets `pending_oreb` via rebound logic
- ✅ Sets `possession_flips = False` (no flip for OREB)
- ✅ OREB turn created in `game_manager.py` (line 169)
- ✅ OREB turn flipped in `game_manager.py` (line 176-178) if putback makes
- ❌ Does NOT set `offense_team_id`

**SS&S Compliance:** ⚠️ **PARTIAL**

**Issues:**
1. Missing `offense_team_id` in FREE_THROW result

**Fix Required:**
- Backend: Set `result["offense_team_id"] = off_team.team_id`

---

#### 3. Free Throw → HCO (PC) - Final FT Missed, DREB

**Handler:** `phase_resolution.py` `resolve_free_throw_logic()` (line 616-650, rebound logic)

**Current Implementation:**
- ✅ Sets `possession_flips = True` (via rebound logic)
- ✅ Sets `next_play_type = "HCO"` (line 706)
- ❌ Backend does NOT flip possession in `game_manager.py`
- ❌ Does NOT set `offense_team_id`
- ❌ **No possession flip executed anywhere!**

**SS&S Compliance:** ❌ **NOT SS&S**

**Issues:**
1. Possession flip flag set but NEVER executed (same as HCO → HCO)
2. No `offense_team_id` set
3. Next turn will have wrong offense team

**Fix Required:**
- Backend: Add possession flip in `game_manager.py` for DREB → HCO transitions
- Backend: Set `offense_team_id` AFTER flip

---

#### 4. Free Throw → Fast Break (PC) - Final FT Missed, DREB

**Handler:** `phase_resolution.py` `resolve_free_throw_logic()` (line 616-650, rebound logic with fast break)

**Current Implementation:**
- ✅ Sets `possession_flips = True`
- ✅ Sets `next_play_type = "FAST_BREAK"` (would be set by rebound logic)
- ❌ Backend does NOT flip possession in `game_manager.py`
- ❌ Does NOT set `offense_team_id`
- ❌ **Frontend flips possession** in `fastBreak.js`

**SS&S Compliance:** ❌ **NOT SS&S**

**Issues:**
1. Possession flip happens in frontend (same as HCO → Fast Break)
2. No authoritative `offense_team_id`

**Fix Required:**
- Backend: Flip possession in `game_manager.py` before Fast Break
- Backend: Set `offense_team_id` AFTER flip
- Frontend: Remove flip logic from fastBreak.js

---

#### 5. Free Throw → Side Inbound Pass - Final FT Missed, Defensive Foul (No Bonus)

**Handler:** `phase_resolution.py` (FT miss → rebound → foul detection)

**Current Implementation:**
- ⚠️ This transition path is **complex** - FT misses, then foul is detected during rebound
- Would need to trace through rebound → foul logic
- Likely routes to `resolve_non_shooting_foul()` → Side Inbound

**SS&S Compliance:** ⚠️ **NEEDS INVESTIGATION**

**Issues:**
- Complex multi-step path, hard to trace

---

#### 6. Free Throw → Free Throw (PC) - Final FT Missed, Defensive Foul (Bonus)

**Handler:** Same as #5, but routes to FREE_THROW instead of Side Inbound

**Current Implementation:**
- ⚠️ This transition path is **complex** - FT miss → rebound → foul → bonus check
- Would route to FREE_THROW if team fouls >= 5

**SS&S Compliance:** ⚠️ **NEEDS INVESTIGATION**

**Issues:**
- Complex multi-step path, hard to trace

---

#### 7. Free Throw → Side Inbound Pass (PC) - Final FT Missed, Offensive Foul

**Handler:** Same as #5/#6, but offensive foul instead of defensive

**Current Implementation:**
- ⚠️ This transition path is **complex** - FT miss → rebound → offensive foul
- Would route to Side Inbound with `possession_flips=True`
- **If** it reaches `game_manager.py` line 200-205, would flip correctly

**SS&S Compliance:** ⚠️ **POSSIBLY SS&S** (if it reaches SIP setup logic)

**Issues:**
- Hard to verify without tracing full path

---

### Batch 2 Summary

| # | Transition | SS&S Status | Primary Issue |
|---|-----------|-------------|---------------|
| 1 | FT → Inbound Pass (PC) | ❌ NOT SS&S | Frontend flips possession |
| 2 | FT → OREB | ⚠️ PARTIAL | Missing offense_team_id |
| 3 | FT → HCO (PC) | ❌ NOT SS&S | Possession flip NEVER executed |
| 4 | FT → Fast Break (PC) | ❌ NOT SS&S | Frontend flips possession |
| 5 | FT → Side Inbound (No PC) | ⚠️ NEEDS INVESTIGATION | Complex multi-step path |
| 6 | FT → Free Throw (PC) | ⚠️ NEEDS INVESTIGATION | Complex multi-step path |
| 7 | FT → Side Inbound (PC) | ⚠️ POSSIBLY SS&S | Hard to verify |

**Results:**
- ✅ **0 out of 7** are SS&S compliant (0%)
- ⚠️ **4 out of 7** need investigation or are partial (57%)
- ❌ **3 out of 7** are clearly NOT SS&S (43%)

**Key Finding:**
**Free Throw transitions mirror HCO transitions** - same issues:
1. Final FT makes flip in frontend (same as HCO makes)
2. DREB → HCO/Fast Break never flip (same as HCO)
3. Missing `offense_team_id` throughout

**Transitions #5, #6, #7** involve fouls AFTER FT misses during rebound scramble - these are complex edge cases that are hard to trace. They may or may not be SS&S compliant.

---

### Batch 3: Fast Break Transitions (8 Total)

#### 1. Fast Break → HCO - Defensive Stop

**Handler:** `phase_resolution.py` `resolve_fast_break_logic()` (line 393-418)

**Current Implementation:**
- ✅ Sets `possession_flips = False` (line 412) - Correct, no flip for defensive stop
- ✅ Sets `next_play_type = "HCO"` (line 415)
- ✅ Sets `offensive_state = "HCO"` (line 395)
- ✅ No flip needed (offense keeps ball after defensive stop)
- ❌ Does NOT set `offense_team_id`

**SS&S Compliance:** ⚠️ **PARTIAL**

**Issues:**
1. Missing `offense_team_id`

**Fix Required:**
- Backend: Set `result["offense_team_id"] = off_team.team_id`

---

#### 2. Fast Break → Inbound Pass (PC) - Made Shot, No Foul

**Handler:** `shot_manager.py` `resolve_fast_break_shot()` (line 929-936)

**Current Implementation:**
- ✅ Sets `possession_flips = True` (line 929)
- ✅ Sets `next_play_type = "BASELINE_INBOUND"` (line 936)
- ✅ Sets `next_defensive_setup` = pressure type (line 933)
- ❌ Backend does NOT flip possession
- ❌ Does NOT set `offense_team_id`
- ❌ **Frontend flips possession** in `fastBreak.js` (line 548-563)

**SS&S Compliance:** ❌ **NOT SS&S**

**Issues:**
- **IDENTICAL to HCO → Inbound Pass** (Pattern A)
- Frontend flips, no authoritative `offense_team_id`

**Fix Required:**
- Same as Pattern A (backend flip before BASELINE_INBOUND)

---

#### 3. Fast Break → Free Throw - Fouls

**Handler:** `shot_manager.py` `resolve_fast_break_shot()` (AND-1), `phase_resolution.py` (non-shooting fouls)

**Current Implementation:**
- ✅ Sets `possession_flips = False` for AND-1
- ✅ Sets `offensive_state = "FREE_THROW"`
- ❌ Does NOT set `offense_team_id`

**SS&S Compliance:** ⚠️ **PARTIAL**

**Issues:**
- **IDENTICAL to HCO → Free Throw** (Pattern D)
- Missing `offense_team_id`

**Fix Required:**
- Backend: Set `result["offense_team_id"] = off_team.team_id`

---

#### 4. Fast Break → OREB - Missed Shot, OREB

**Handler:** `shot_manager.py` `resolve_fast_break_shot()` (line 986-996)

**Current Implementation:**
- ✅ Sets `possession_flips = False` (line 991)
- ✅ Sets `pending_oreb` (line 993-996)
- ❌ Does NOT set `offense_team_id`

**SS&S Compliance:** ⚠️ **PARTIAL**

**Issues:**
- **IDENTICAL to HCO → OREB** (Pattern D)
- Missing `offense_team_id`

**Fix Required:**
- Backend: Set `result["offense_team_id"] = off_team.team_id`

---

#### 5. Fast Break → HCO (PC) - Missed Shot DREB, Steal

**Handler:** `shot_manager.py` `resolve_fast_break_shot()` (line 1003-1008)

**Current Implementation:**
- ✅ Sets `possession_flips = True` (line 1003)
- ✅ Sets `next_play_type = "HCO"` (line 1008)
- ✅ Sets `offensive_state = "HCO"` (line 1005)
- ❌ Backend does NOT flip possession in `game_manager.py`
- ❌ Does NOT set `offense_team_id`
- ❌ **No possession flip executed!**

**SS&S Compliance:** ❌ **NOT SS&S**

**Issues:**
- **IDENTICAL to HCO → HCO** (Pattern B)
- Flip flag set but never executed

**Fix Required:**
- Same as Pattern B (backend flip before HCO)

---

#### 6. Fast Break → Fast Break (PC) - Missed Shot DREB, Steal

**Handler:** `phase_resolution.py` `resolve_fast_break_logic()` (STEAL with fast break chance, line 392-464)

**Current Implementation:**
- Steals in fast break can trigger another fast break
- Would set `possession_flips = True` (steal always flips)
- Would set `next_play_type = "FAST_BREAK"`
- ❌ Backend does NOT flip possession
- ❌ Does NOT set `offense_team_id`
- ❌ **Frontend flips** (if it reaches fastBreak.js)

**SS&S Compliance:** ❌ **NOT SS&S**

**Issues:**
- **IDENTICAL to Pattern C** (DREB → Fast Break)
- Frontend flips possession

**Fix Required:**
- Same as Pattern C (backend flip before Fast Break)

---

#### 7. Fast Break → Side Inbound Pass - Non-Shooting Foul (No Bonus)

**Handler:** `phase_resolution.py` `resolve_fast_break_logic()` → `resolve_non_shooting_foul()`

**Current Implementation:**
- Routes through Fast Break logic → foul handler
- Would use standard non-shooting foul logic
- ✅ Should use Side Inbound gold standard pattern
- ✅ Backend flips in `game_manager.py` (line 200-205)
- ✅ SIP has `offense_team_id`

**SS&S Compliance:** ✅ **LIKELY SS&S**

**Issues:**
- None (uses gold standard SIP pattern)

---

#### 8. Fast Break → Side Inbound Pass (PC) - Offensive Foul, Dead Ball

**Handler:** `phase_resolution.py` `resolve_fast_break_logic()` (line 471-490)

**Current Implementation:**
- ✅ Routes to `resolve_non_shooting_foul()` or `resolve_turnover_logic()`
- ✅ Should use Side Inbound gold standard pattern
- ✅ Backend flips in `game_manager.py` (line 200-205)
- ✅ SIP has `offense_team_id`

**SS&S Compliance:** ✅ **LIKELY SS&S**

**Issues:**
- None (uses gold standard SIP pattern)

---

### Batch 3 Summary

| # | Transition | SS&S Status | Primary Issue | Pattern |
|---|-----------|-------------|---------------|---------|
| 1 | FB → HCO | ⚠️ PARTIAL | Missing offense_team_id | D |
| 2 | FB → Inbound Pass (PC) | ❌ NOT SS&S | Frontend flips | A |
| 3 | FB → Free Throw | ⚠️ PARTIAL | Missing offense_team_id | D |
| 4 | FB → OREB | ⚠️ PARTIAL | Missing offense_team_id | D |
| 5 | FB → HCO (PC) | ❌ NOT SS&S | Flip never executed | B |
| 6 | FB → Fast Break (PC) | ❌ NOT SS&S | Frontend flips | C |
| 7 | FB → Side Inbound (No PC) | ✅ LIKELY SS&S | None | E |
| 8 | FB → Side Inbound (PC) | ✅ LIKELY SS&S | None | E |

**Results:**
- ✅ **2 out of 8** are SS&S compliant (25%)
- ⚠️ **3 out of 8** are partial (38%)
- ❌ **3 out of 8** are NOT SS&S (38%)

**Key Finding:**
**Fast Break transitions are IDENTICAL to HCO/FT patterns!**
- Same Pattern A: Made shots flip in frontend
- Same Pattern B: DREB → HCO never flips
- Same Pattern C: DREB → Fast Break flips in frontend
- Same Pattern D: Missing `offense_team_id`
- Same Pattern E: Side Inbound works perfectly ✅

**Overall Progress:**
- **6/22 evaluated transitions are SS&S compliant (27%)**
- All compliant transitions use Side Inbound gold standard pattern

