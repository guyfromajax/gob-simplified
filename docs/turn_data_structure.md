# Turn Data Structure

This document defines the standardized turn data structure used throughout the GOB basketball simulation system.

## Overview

The turn data structure represents a single turn/action in a basketball game, containing all necessary information for both backend logic and frontend animations.

## Core Structure

```python
turn = {
    # === CORE TURN DATA ===
    "turn_count": 1,
    "result_type": "MAKE" | "DREB" | "OREB" | "TURNOVER" | "FOUL" | "FREE_THROW" | "HCO",
    "shooter_id": "player-uuid" | None,
    "shooter": "player-name" | None,
    "time_elapsed": 1000,
    "possession_team_id": "team-uuid",
    "possession_flips": True | False,
    
    # === AUTHORITATIVE SCORING ===
    "score": {  # This is the authoritative score
        "Team A": 15,
        "Team B": 12
    },
    
    # === SPECIAL FLAGS ===
    "fast_break": True | False,        # Animation routing
    "hold_up": True | False,           # Fast break defense
    "stopper_id": "player-uuid" | None, # Hold-up scenarios
    "is_three_pointer": True | False,  # Three-point shot flag
    "is_and_one": True | False,        # And-one situation flag
    "putback_attempt": True | False,   # Putback animations
    
    # === FREE THROW SPECIFIC ===
    "attempts": ["MAKE", "DREB", "OREB"],      # Backend generated for multiple attempts
    "ftContext": "AND_ONE" | "TECHNICAL" | "REGULAR",  # Frontend generated
    
    # === REBOUND SPECIFIC ===
    "rebound_type": "DREB" | "OREB" | None,  # Essential
    "rebounder_id": "player-uuid" | None,    # Essential
    
    # === ANIMATION DATA ===
    "animations": [...],  # Essential for animations
}
```

## Field Descriptions

### Core Turn Data

- **`turn_count`** (int): Sequential turn number in the game
- **`result_type`** (string): The outcome of the turn
  - `"MAKE"`: Shot was made
  - `"DREB"`: Defensive rebound (shot missed, defense got rebound)
  - `"OREB"`: Offensive rebound (shot missed, offense got rebound)
  - `"TURNOVER"`: Ball was turned over
  - `"FOUL"`: Foul was committed
  - `"FREE_THROW"`: Free throw attempt
- **`shooter_id`** (string|null): UUID of the player who shot (if applicable)
- **`shooter`** (string|null): Name of the player who shot (if applicable)
- **`time_elapsed`** (int): Time in milliseconds that elapsed during this turn
- **`possession_team_id`** (string): UUID of the team with possession
- **`possession_flips`** (boolean): Whether possession changed hands

### Authoritative Scoring

- **`score`** (object): The authoritative team scores after this turn
  - Keys: Team names
  - Values: Current score totals
  - **This is the single source of truth for scoring**

### Special Flags

- **`fast_break`** (boolean): Whether this was a fast break play
- **`hold_up`** (boolean): Whether the fast break was stopped by defense
- **`stopper_id`** (string|null): Player ID who stopped the fast break (if hold_up is true)
- **`is_three_pointer`** (boolean): Whether this was a three-point shot attempt
- **`is_and_one`** (boolean): Whether this was an and-one situation
- **`putback_attempt`** (boolean): Whether this was a putback shot attempt

### Free Throw Specific

- **`attempts`** (array): Array of free throw results for multiple attempts
  - `["MAKE"]`: Made the free throw
  - `["DREB"]`: Missed the free throw (defensive rebound)
  - `["OREB"]`: Missed the free throw (offensive rebound)
  - `["MAKE", "DREB"]`: Multiple attempts (made first, missed second)
  - `["DREB", "MAKE"]`: Multiple attempts (missed first, made second)
- **`ftContext`** (string): Context of the free throw
  - `"AND_ONE"`: And-one free throw
  - `"TECHNICAL"`: Technical free throw
  - `"REGULAR"`: Regular free throw

### Rebound Specific

- **`rebound_type`** (string|null): Type of rebound (used for missed shots and free throws)
  - `"DREB"`: Defensive rebound
  - `"OREB"`: Offensive rebound
- **`rebounder_id`** (string|null): Player ID who got the rebound

### Animation Data

- **`animations`** (array): Animation data for frontend rendering
- **`events`** (array): Complex event data for animation routing
  - Contains events like `PUTBACK_ATTEMPT`, `KICKOUT_RESET`, `STEAL`, etc.

## Design Principles

### Removed Redundant Fields

The following fields were removed as they were redundant or could be derived:

- **`points`** - Redundant with `score` field (backend updates team scores directly)
- **`scoring_team`** - Can derive from `score` comparison
- **`shot_result`** - Redundant with `result_type`
- **`"MISS"` result_type** - Every miss becomes either DREB or OREB

### Key Benefits

1. **Simplified Data Model** - Removed 4 redundant fields
2. **Clear Result Types** - No more confusing "MISS" type, every miss is either DREB or OREB
3. **Authoritative Scoring** - `turn.score` is the single source of truth
4. **Essential Flags Only** - Every field serves a specific purpose
5. **Cleaner Logic** - Frontend can derive missing information from existing data
6. **Better Performance** - Smaller payload, less data to process
7. **Easier Maintenance** - Fewer fields to manage and validate

## Usage Examples

### Made Shot
```python
{
    "turn_count": 1,
    "result_type": "MAKE",
    "shooter_id": "player-123",
    "shooter": "John Smith",
    "time_elapsed": 2000,
    "possession_team_id": "team-456",
    "possession_flips": True,
    "score": {"Team A": 2, "Team B": 0},
    "fast_break": False,
    "is_three_pointer": False,
    "is_and_one": False,
    "putback_attempt": False,
    "animations": [...],
    "events": []
}
```

### Defensive Rebound
```python
{
    "turn_count": 2,
    "result_type": "DREB",
    "shooter_id": "player-123",
    "shooter": "John Smith",
    "time_elapsed": 1500,
    "possession_team_id": "team-789",
    "possession_flips": True,
    "score": {"Team A": 2, "Team B": 0},
    "rebound_type": "DREB",
    "rebounder_id": "player-456",
    "fast_break": True,
    "animations": [...],
    "events": []
}
```

### Offensive Rebound with Putback
```python
{
    "turn_count": 3,
    "result_type": "OREB",
    "shooter_id": "player-123",
    "shooter": "John Smith",
    "time_elapsed": 1200,
    "possession_team_id": "team-456",
    "possession_flips": False,
    "score": {"Team A": 2, "Team B": 0},
    "rebound_type": "OREB",
    "rebounder_id": "player-789",
    "putback_attempt": True,
    "animations": [...],
    "events": [
        {
            "event_type": "PUTBACK_ATTEMPT",
            "shooterId": "player-789",
            "timeElapsed": 800,
            "result": "MAKE",
            "possession_flips": True
        }
    ]
}
```

### Free Throw (Made)
```python
{
    "turn_count": 4,
    "result_type": "FREE_THROW",
    "shooter_id": "player-123",
    "shooter": "John Smith",
    "time_elapsed": 0,
    "possession_team_id": "team-456",
    "possession_flips": False,
    "score": {"Team A": 3, "Team B": 0},
    "attempts": ["MAKE"],
    "ftContext": "REGULAR",
    "animations": [...],
    "events": []
}
```

### Free Throw (Missed - Defensive Rebound)
```python
{
    "turn_count": 5,
    "result_type": "FREE_THROW",
    "shooter_id": "player-123",
    "shooter": "John Smith",
    "time_elapsed": 0,
    "possession_team_id": "team-456",
    "possession_flips": True,
    "score": {"Team A": 3, "Team B": 0},
    "attempts": ["DREB"],
    "ftContext": "REGULAR",
    "rebound_type": "DREB",
    "rebounder_id": "player-789",
    "next_play_type": "HCO",
    "animations": [...],
    "events": []
}
```

### Free Throw (Missed - Offensive Rebound)
```python
{
    "turn_count": 6,
    "result_type": "FREE_THROW",
    "shooter_id": "player-123",
    "shooter": "John Smith",
    "time_elapsed": 0,
    "possession_team_id": "team-456",
    "possession_flips": False,
    "score": {"Team A": 3, "Team B": 0},
    "attempts": ["OREB"],
    "ftContext": "REGULAR",
    "rebound_type": "OREB",
    "rebounder_id": "player-456",
    "animations": [...],
    "events": []
}
```

### Three-Pointer
```python
{
    "turn_count": 5,
    "result_type": "MAKE",
    "shooter_id": "player-123",
    "shooter": "John Smith",
    "time_elapsed": 1800,
    "possession_team_id": "team-456",
    "possession_flips": True,
    "score": {"Team A": 6, "Team B": 0},
    "is_three_pointer": True,
    "is_and_one": False,
    "putback_attempt": False,
    "animations": [...],
    "events": []
}
```

## Implementation Notes

- The `score` field is authoritative and should be used instead of calculating from individual turn points
- The `result_type` field directly indicates the outcome without needing additional mapping
- Every missed shot becomes either "DREB" or "OREB" - there is no generic "MISS" type
- The `events` array contains complex animation logic that the frontend processes
- All player references use UUIDs for consistency
- Time values are in milliseconds
- The backend generates `attempts` and `ftContext` for free throws
- The frontend can derive additional context from the turn sequence and existing data

## OREB Follow-Up System

When an offensive rebound occurs, the system now generates **separate turns** instead of using events:

### Turn 1: OREB
```python
{
    "result_type": "OREB",
    "rebounder_id": "player-uuid",
    "rebound_type": "OREB",
    "text": "Player grabs the offensive rebound",
    "possession_flips": False
}
```

### Turn 2: Follow-Up Action
The backend automatically generates a follow-up turn with one of two outcomes:

#### Putback Attempt
```python
{
    "result_type": "MAKE" | "DREB" | "OREB",  # Outcome of putback
    "shooter": "player-name",
    "is_putback": True,
    "text": "Player goes back up for the putback",
    "points": 2,  # If made
    "possession_flips": True  # If made
}
```

#### Kickout Pass
```python
{
    "result_type": "HCO",
    "ball_handler": "player-name",
    "is_kickout": True,
    "text": "Player kicks it out to reset",
    "pass": {
        "fromCoords": {"x": 25, "y": 50},
        "toCoords": {"x": 25, "y": 50},
        "duration": 300
    },
    "possession_flips": False
}
```

This approach provides:
- **Architectural consistency** - All actions are turns
- **Simpler data structure** - No complex events processing
- **Better turn counting** - Each action gets proper turn_count
- **Easier maintenance** - Clear turn boundaries