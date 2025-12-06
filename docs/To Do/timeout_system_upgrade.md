# Timeout System Upgrade: Unified Game State Detection

> **Status:** Proposed Refactor  
> **Priority:** Medium  
> **Created:** January 2025

## Problem Statement

The current timeout system works but relies on **scattered inference logic** to determine game state (new game vs. resuming vs. timeout resume). This creates fragility and maintenance challenges.

### Current State: Patchy Inference Logic

**Frontend (`gameScene.js` line 210):**
```javascript
const isNewGameStart = !this.gameId || 
                      (this.quarter === 1 && !urlGameId && !resumeFromTimeout);
```

**Backend (`api.py` line 804):**
```python
should_check_timeout = game_id and not (request.quarter == 1 and not gm)
```

**Backend (`api.py` line 963):**
```python
is_new_game = (request.quarter == 1 and saved_quarter > 1) and not request.resume_from_timeout
```

### Issues with Current Approach

1. **No Single Source of Truth**: Three different places infer "is this a new game?" from different signals
2. **Fragile**: If assumptions change, we have to update multiple places
3. **Hard to Debug**: When something breaks, it's unclear which inference logic is wrong
4. **Inconsistent**: Different code paths use different heuristics

## Proposed Solution: Unified Game State Detection System

### Core Principle

**Explicit state over inferred state.** Instead of inferring game state from multiple signals, we should have a clear, explicit game state that both frontend and backend can use.

### Architecture

#### 1. Game State Enum

```python
# BackEnd/utils/game_state.py
from enum import Enum

class GameState(Enum):
    """Unified game state types"""
    NEW_GAME = "new_game"              # Brand new game start (Q1, opening tip)
    RESUMING = "resuming"               # Resuming existing game (quarter break, normal resume)
    TIMEOUT_RESUME = "timeout_resume"   # Resuming from timeout (SIP)
    FOUL_OUT_RESUME = "foul_out_resume" # Resuming from player foul out (SIP)
    QUARTER_BREAK = "quarter_break"     # Quarter break (Q2/Q3/Q4, BIP)
```

#### 2. Unified Detection Function

```python
# BackEnd/api/api.py
def determine_game_state(
    request: QuarterSimulationRequest,
    saved: dict | None,
    gm: GameManager | None,
    games_collection
) -> GameState:
    """
    Unified function to determine game state.
    Single source of truth for all game state detection.
    
    Returns:
        GameState enum indicating the current game state
    """
    # Priority 1: Explicit flags from request
    if request.resume_from_timeout:
        return GameState.TIMEOUT_RESUME
    
    if request.resume_from_foul_out:  # Future: player foul out resume
        return GameState.FOUL_OUT_RESUME
    
    # Priority 2: Check database for timeout state
    if request.game_id:
        timeout_state = restore_timeout_resume_state(request.game_id, request, games_collection)
        if timeout_state and timeout_state.get("timeout_next_play_type"):
            # Validate quarter matches (prevent stale data)
            saved_quarter = timeout_state.get("quarter", 0)
            if saved_quarter == request.quarter:
                return GameState.TIMEOUT_RESUME
    
    # Priority 3: Quarter-based detection
    if request.quarter == 1:
        # Q1: Check if this is a new game or resuming
        if not request.game_id:
            return GameState.NEW_GAME  # No game_id = new game
        
        if saved:
            saved_quarter = saved.get("quarter", 1)
            if saved_quarter > 1:
                return GameState.NEW_GAME  # Requesting Q1 but saved game is Q2+ = new game
            else:
                return GameState.RESUMING  # Same quarter = resuming
        else:
            # No saved game found = new game
            return GameState.NEW_GAME
    
    elif request.quarter > 1:
        # Q2/Q3/Q4: Quarter break
        return GameState.QUARTER_BREAK
    
    # Default: Resuming
    return GameState.RESUMING
```

#### 3. Frontend Explicit State Passing

```javascript
// FrontEnd/static/js/phaser/gameScene.js
// When starting a new game, explicitly set flag
const isNewGame = !this.gameId || 
                  (this.quarter === 1 && !urlParams.get('game_id') && !resumeFromTimeout);

const payload = {
  home_team: homeTeam,
  away_team: awayTeam,
  quarter: this.quarter,
  is_new_game: isNewGame  // ✅ Explicit flag instead of inferring
};

// Only pass game_id if it's not a new game
if (this.gameId && !isNewGame) {
  payload.game_id = this.gameId;
}
```

#### 4. Backend State-Based Routing

```python
# BackEnd/api/api.py
@app.post("/api/simulate-quarter")
def simulate_quarter_endpoint(request: QuarterSimulationRequest, ...):
    # Determine game state using unified function
    game_state = determine_game_state(request, saved, gm, games_collection)
    
    # Route based on explicit state
    if game_state == GameState.NEW_GAME:
        # New game: Generate new game_id, create opening tip
        if request.game_id:
            # Frontend passed game_id but this is a new game - ignore it
            game_id = generate_game_id()
        else:
            game_id = generate_game_id()
        # ... create new game ...
    
    elif game_state == GameState.TIMEOUT_RESUME:
        # Timeout resume: Restore timeout state, create SIP
        timeout_state = restore_timeout_resume_state(...)
        apply_timeout_resume_state_to_gm(gm, timeout_state)
        request.resume_from_timeout = True
    
    elif game_state == GameState.QUARTER_BREAK:
        # Quarter break: Create BIP
        # ... quarter break logic ...
    
    elif game_state == GameState.RESUMING:
        # Normal resume: Continue existing game
        # ... resume logic ...
    
    # Call simulate_quarter with explicit state
    simulate_quarter(gm, ..., game_state=game_state)
```

#### 5. Simulate Quarter State-Based Logic

```python
# BackEnd/main.py
def simulate_quarter(
    gm: GameManager,
    ...,
    game_state: GameState | None = None,  # ✅ Explicit state parameter
):
    # Use explicit state instead of inferring
    if game_state == GameState.TIMEOUT_RESUME:
        # Create SIP turn
        ...
    elif game_state == GameState.NEW_GAME:
        # Create opening tip (Q1) or BIP (OT)
        ...
    elif game_state == GameState.QUARTER_BREAK:
        # Create BIP for Q2/Q3/Q4
        ...
    # etc.
```

## Benefits of Unified System

1. **Single Source of Truth**: One function determines game state
2. **Explicit Over Inferred**: Clear state instead of scattered conditionals
3. **Easier to Debug**: One place to check when something breaks
4. **Easier to Extend**: Adding new game states is straightforward
5. **Consistent**: All code paths use the same logic
6. **Testable**: Can unit test the state detection function

## Migration Plan

### Phase 1: Create Infrastructure
1. Create `GameState` enum
2. Create `determine_game_state()` function
3. Add `game_state` parameter to `simulate_quarter()`

### Phase 2: Frontend Updates
1. Add `is_new_game` flag to `QuarterSimulationRequest`
2. Update frontend to explicitly set `is_new_game` flag
3. Remove inference logic from frontend

### Phase 3: Backend Refactor
1. Replace all inference logic with `determine_game_state()` calls
2. Update `simulate_quarter()` to use explicit `game_state` parameter
3. Remove scattered `is_new_game` / `should_check_timeout` conditionals

### Phase 4: Testing & Validation
1. Test all game state transitions
2. Verify timeout resume works correctly
3. Verify new game starts work correctly
4. Verify quarter breaks work correctly

## Current Workarounds (What We Have Now)

The current system works but uses these workarounds:

1. **Frontend**: Clears stale `game_id` for new games (prevents stale data)
2. **Backend**: Clears timeout state from DB after resume (defensive cleanup)
3. **Backend**: Validates quarter match before using timeout state (prevents stale data)

These workarounds are functional but not structural. The unified system would replace them with explicit state management.

## Related Systems

- **Timeout Resume System**: Uses this for timeout resume detection
- **Quarter Break System**: Uses this for quarter break detection
- **Game Initialization**: Uses this for new game detection

## Notes

- This refactor is **not urgent** - current system works
- This refactor is **structural improvement** - makes system more maintainable
- Can be done incrementally without breaking existing functionality
- Should be done when we have time for structural improvements

