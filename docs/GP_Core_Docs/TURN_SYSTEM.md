# Turn System

> **Last Updated:** February 2025  
> **Status:** Complete reference for turn data structure and execution patterns

This document combines the turn data structure and execution patterns into a single comprehensive reference.

---

## Table of Contents

1. [Part 1: Turn Data Structure](#part-1-turn-data-structure)
2. [Part 2: Turn Execution Patterns](#part-2-turn-execution-patterns)
3. [Part 3: Documentation Status](#part-3-documentation-status)

---

# Part 1: Turn Data Structure

This section documents the payload our backend returns for each **micro-turn** (the smallest unit of game simulation) and how the frontend consumes it.

The data is produced inside `BackEnd/models/turn_manager.py::run_micro_turn`. Additional helpers (animator, fast break logic, free-throw resolution) augment the result before it is serialised to JSON and sent to the client.

## High-Level Shape

```json5
{
  "turn_count": 42,
  "result_type": "MAKE" | "DREB" | "OREB" | "TURNOVER" | "FOUL" | "FREE_THROW" | "HCO" | "FAST_BREAK",
  "time_elapsed": 1280,
  "offense_team_id": "TEAM_UUID",
  "current_turn": "HCO" | "FCP" | "HCT" | "FAST_BREAK" | "FREE_THROW" | "OREB" | "BASELINE_INBOUND" | "SIDE_INBOUND" | "OPENING_TIP" | "TIMEOUT",
  "next_turn": "HCO" | "FCP" | "HCT" | "FAST_BREAK" | "FREE_THROW" | "BASELINE_INBOUND" | "SIDE_INBOUND",
  "possession_flips": true,
  "score": { "Home": 44, "Away": 40 },

  // Participant metadata (strings; player objects are normalised away)
  "shooter_id": "PLAYER_UUID",
  "shooter": "Player Name",
  "ball_handler": "Player Name",
  "passer": "Player Name",
  "stealer_id": "PLAYER_UUID",
  "victim_id": "PLAYER_UUID",

  // Animation + role context
  "animations": [...],
  "events": [...],
  "roles": {...},
  "next_play_type": "HCO" | "FAST_BREAK" | "FREE_THROW" | null,

  // Free throw details (optional)
  "attempts": ["MAKE", "MISS"],
  "ftContext": { "ftIndex": 1, "ftTotal": 2, "bonusType": "REGULAR" },

  // Rebound information (optional)
  "rebound_type": "DREB" | "OREB" | null,
  "rebounderId": "PLAYER_UUID" | null,  // Primary field (camelCase). Note: `rebounder_id` and `rebounder_player_id` may also be present for backward compatibility

  // Player positioning data (for shot attempts - optional)
  "offense_getback": ["PLAYER_UUID", ...],  // Array of offensive player IDs getting back on defense
  "defense_release": ["PLAYER_UUID", ...],  // Array of defensive player IDs releasing for fast break
  "offense_rebounders": ["PLAYER_UUID", ...],  // Array of offensive player IDs crashing boards
  "defense_rebounders": ["PLAYER_UUID", ...],  // Array of defensive player IDs staying for rebound
  "offense_getback_coords": {  // Coordinates for get-back players (for fast break logic)
    "PLAYER_UUID": {"x": 50, "y": 30}
  },
  "defense_release_coords": {  // Coordinates for release players (for fast break logic)
    "PLAYER_UUID": {"x": 50, "y": 25}
  },

  // Scoreboard snapshots
  "home_lineup": { "PG": {...}, ... },
  "away_lineup": { "PG": {...}, ... },
  "deltas": {
    "PLAYER_UUID": {
      "team": "Home",
      "stats": { "PTS": 2, "REB": 1 }
    }
  },
  "homeFouls": 4,
  "awayFouls": 3,
  "clock": "3:12",
  "quarter": 2,
  "period_label": "Q2",

  // Narrative & flags
  "text": "Player drills the mid-range jumper.",
  "fast_break": false,
  "hold_up": false,
  "stopper_id": "PLAYER_UUID",
  "is_three_pointer": false,
  "is_and_one": false,
  "putback_attempt": false
}
```

All player references are serialised to ids/names via `convert_players` before the turn leaves the backend. The frontend should not expect live class instances.

## Core Fields

| Field | Type | Notes |
| ----- | ---- | ----- |
| `turn_count` | int | Sequential counter for micro-turns. |
| `result_type` | string | Primary routing key (MAKE/DREB/OREB/TURNOVER/FOUL/FREE_THROW/HCO/FAST_BREAK). |
| `time_elapsed` | int | Milliseconds deducted from the game clock. |
| `offense_team_id` | string | **SS&S Standard:** Team on offense during this turn (authoritative). Replaces deprecated `possession_team_id`. **Note:** `possession_team_id` may still be present in some turn types for backward compatibility, but `offense_team_id` should always be used as the authoritative source. |
| `current_turn` | string | Explicit turn type identifier (HCO/FCP/HCT/FAST_BREAK/FREE_THROW/OREB/BASELINE_INBOUND/SIDE_INBOUND/OPENING_TIP/TIMEOUT). Used for routing and debugging. |
| `next_turn` | string | Explicit next turn type (set by `game_manager.determine_next_turn()`). Used for transition logic. |
| `possession_flips` | bool | If true, backend flips possession immediately after the turn. |
| `score` | object | Authoritative team scores after the turn. Always use this rather than re-adding `points`. |
| `text` | string | Guaranteed non-empty narrative for the play-by-play ticker. |

## Participant Metadata (optional)

Depending on the play type, one or more of the following string fields may be present: `shooter_id`, `shooter`, `ball_handler`, `passer`, `screener`, `defender`, `stealer_id`, `victim_id`, `stopper_id`. These are already coerced into simple strings.

## Animation & Roles

- **`animations`** – Array of per-player movement tracks (positions, actions, `hasBallAtStep`) used by both the legacy animator and the new `PossessionRunner`.
- **`events`** – Optional array of high-level events (`PUTBACK_ATTEMPT`, `KICKOUT_RESET`, `STEAL`, etc.) the frontend uses to trigger specialised flows.
- **`roles`** – Optional map describing offensive/defensive roles for the turn (ball handler, rebounder, outlet receiver, etc.).
- **`next_play_type`** – Hint about what the backend expects next (`HCO`, `FAST_BREAK`, `FREE_THROW`), useful when staging transitions. (Note: `next_turn` is the authoritative value set by `game_manager.determine_next_turn()`)

## Free Throw Metadata

- **`attempts`** – Ordered results of each free throw (`MAKE` or `MISS`).
- **`free_throws_remaining`** – Number of free throws remaining after this turn (turn-by-turn mode). Set by `BackEnd/engine/phase_resolution.py::resolve_free_throw_logic()`. If undefined, fall back to `ftContext`.
- **`one_and_one`** – Boolean flag indicating if this is a 1-and-1 free throw situation (front-end must make first FT to unlock second).
- **`ftContext`** – Added by `animateGameTurns.annotateFreeThrowTurns` to expose attempt index/total and bonus type for UI copy (batch mode fallback).

## Rebounds

- **`rebound_type`** – `DREB` or `OREB` for missed shots/free throws.
- **`rebounderId`** – Player ID securing the rebound (camelCase, primary field). **Note:** For backward compatibility, `rebounder_id` (snake_case) and `rebounder_player_id` may also be present in some contexts, but `rebounderId` is the standard field in turn results.

When an offensive rebound occurs, the backend now emits *two* turns:

1. `result_type = "OREB"` describing the rebound itself.
2. A follow-up turn (putback attempt, kick-out reset, etc.) where normal shot or HCO logic applies.

## Scoreboard Snapshots & Deltas

- **`home_lineup` / `away_lineup`** – Serialised lineup info (position → player metadata) used by overlays and debugging.
- **`deltas`** – Per-player stat increments accumulated during the turn (scoring, rebounds, steals, etc.). Note: REB is excluded from deltas (automatically calculated from OREB + DREB).
- **`homeFouls` / `awayFouls`** – Team foul totals this quarter.
- **`clock`**, **`quarter`**, **`period_label`** – Human-readable game-clock state after the turn.

## Player Positioning Data (Shot Attempts)

When a shot is attempted, the backend includes player positioning data for animation:

- **`offense_getback`** – Array of player IDs getting back on defense (based on offensive team's rebounding strategy setting).
- **`defense_release`** – Array of player IDs releasing early for fast break (based on defensive team's fast_breaks strategy setting).
- **`offense_rebounders`** – Array of player IDs crashing the offensive boards.
- **`defense_rebounders`** – Array of player IDs staying for the rebound.
- **`offense_getback_coords`** – Object mapping player IDs to coordinates for get-back players (backend as source of truth for fast break logic).
- **`defense_release_coords`** – Object mapping player IDs to coordinates for release players (backend as source of truth for fast break logic).

These fields are set during shot attempts (both makes and misses) to enable proper animation and fast break logic.

## Team Data

- **`team_stats`** – Current team stats from scouting_data (offense/defense effectiveness).
  Structure: `{"Team Name": {"offense": {...}, "defense": {...}}}`
- **`team_totals`** – Cumulative team game stats (aggregated from all players).
  Structure: `{"Team Name": {/* team game stats */}}`
- **`team_plays`** – Play data for tooltips (effectiveness and tracking).
  Structure: `{"Team Name": [/* array of play objects */]}`

## Player State

- **`player_energy`** – Energy levels (NG attribute) for all active players (fatigue display).
  Structure: `{"PLAYER_UUID": {"NG": 1.0, "team": "Team Name"}}`

## Strategy Calls

- **`offense_tempo_call`** – Actual tempo call made by offense team (for strategy bars).
- **`offense_aggression_call`** – Actual aggression call made by offense team (for strategy bars).
- **`defense_tempo_call`** – Actual tempo call made by defense team (for strategy bars).
- **`defense_aggression_call`** – Actual aggression call made by defense team (for strategy bars).

## Flags & Routing Helpers

- **`fast_break`** – Set when the backend is resolving a transition play. Paired with `hold_up` and `stopper_id` for defensive stops.
- **`is_three_pointer`**, **`is_and_one`**, **`putback_attempt`** – Shot context used for commentary and animation choices.

## Sample Payloads

### Made Shot
```python
{
    "turn_count": 47,
    "result_type": "MAKE",
    "shooter_id": "player-123",
    "shooter": "John Smith",
    "time_elapsed": 1820,
    "offense_team_id": "TEAM_HOME",
    "current_turn": "HCO",
    "next_turn": "BASELINE_INBOUND",
    "possession_flips": true,
    "score": {"Home": 44, "Away": 40},
    "is_three_pointer": false,
    "fast_break": false,
    "animations": [...],
    "events": [],
    "deltas": {"player-123": {"team": "Home", "stats": {"PTS": 2}}},
    "homeFouls": 4,
    "awayFouls": 3,
    "clock": "3:12",
    "quarter": 2,
    "text": "John Smith sinks the jumper from mid-range."
}
```

### Defensive Rebound Launching a Fast Break
```python
{
    "turn_count": 48,
    "result_type": "DREB",
    "shooter_id": "player-321",
    "time_elapsed": 860,
    "offense_team_id": "TEAM_AWAY",
    "current_turn": "HCO",
    "next_turn": "FAST_BREAK",
    "possession_flips": true,
    "score": {"Home": 44, "Away": 40},
    "rebound_type": "DREB",
    "rebounderId": "player-456",  // Primary field (camelCase)
    "fast_break": true,
    "next_play_type": "FAST_BREAK",
    "animations": [...],
    "events": [
        {"event_type": "FAST_BREAK_START", "rebounderId": "player-456"}
    ],
    "text": "Doe pulls down the board and immediately looks to run."
}
```

### Free Throw (Missed – Defensive Rebound)
```python
{
    "turn_count": 52,
    "result_type": "FREE_THROW",
    "shooter_id": "player-123",
    "time_elapsed": 0,
    "offense_team_id": "TEAM_HOME",
    "current_turn": "FREE_THROW",
    "next_turn": "HCO",
    "possession_flips": true,
    "score": {"Home": 45, "Away": 40},
    "attempts": ["MISS"],
    "free_throws_remaining": 0,  # Turn-by-turn mode: 0 means this was the final FT (set by phase_resolution.py)
    "one_and_one": False,  # 1-and-1 flag (False if not 1-and-1, or after first FT made)
    "ftContext": {"ftIndex": 1, "ftTotal": 2, "bonusType": "REGULAR"},  # Batch mode fallback
    "rebound_type": "DREB",
    "rebounderId": "player-789",  # Primary field (camelCase)
    "next_play_type": "HCO",
    "animations": [...],
    "events": [],
    "text": "Smith misses the first, but the defense controls the glass."
}
```

## Design Notes

- **Authoritative scoring** – `turn.score` always reflects the official game score. Even if a turn includes a `points` field (legacy helpers occasionally add it), treat it as informational only.
- **No generic "MISS"** – Missed shots resolve to either `DREB` or `OREB`. Use `rebound_type` to differentiate defensive/offensive rebounds.
- **SS&S Possession System** – Use `offense_team_id` (not deprecated `possession_team_id`) as the authoritative team on offense. Backend flips possession based on `possession_flips` flag. **Note:** `possession_team_id` may still be included in some turn types for backward compatibility (e.g., inbound passes), but `offense_team_id` is always the authoritative source and should be used by all new code.
- **Turn Type Identification** – Use `current_turn` to identify turn type and `next_turn` for transition logic (both set by backend).
- **Free Throw Modes** – Backend supports both turn-by-turn mode (`free_throws_remaining`) and batch mode (`ftContext`). Frontend should prefer `free_throws_remaining` if available.
- **Frontend annotations** – The frontend may append helper context (currently `ftContext`). Do not mutate core fields that the backend controls.
- **Telemetry** – With `window.DEBUG_ANIM = true` the Possession Runner emits `possessionRunner:*` events to help reason about timeline stalls and FSM transitions.
- **Debug Fields** – `debug_turn_start` and `debug_turn_result` are optional debug-only fields (only present if backend DEBUG flag is enabled).

Keep this document in sync whenever backend fields change so frontend and instrumentation work remain aligned.

---

# Part 2: Turn Execution Patterns

This section maps the execution structure of each turn type to identify patterns, streamline code, and ensure all execution cases are handled.

## Turn Type Execution Patterns

### 1. HCO (Half Court Offense)

**Structure**: `Skeleton Animation + Result Handling`

**Execution Flow**:
1. **Setup**: Players move to step 0 positions (from previous turn or inbound)
2. **Skeleton Animation**: Animate all steps from playcall skeleton (full skeleton, tempo doesn't affect step count anymore)
3. **Result Handling**:
   - **MAKE**: Ball hold at rim → Inbound pass (if no foul) OR Free throw (if foul/AND-1)
   - **MISS**: Rebound handling (OREB or DREB)
   - **FOUL**: Foul animation → Free throw (if shooting/bonus) OR Side inbound (if non-shooting, no bonus)
   - **TURNOVER**: Turnover animation → Side inbound (PC) OR Fast Break (if live ball)
   - **STEAL**: Steal animation → HCO (PC) OR Fast Break (PC)

**Key Characteristics**:
- Full skeleton animation (all steps from playcall)
- Result determined AFTER skeleton completes
- Result handling is separate from skeleton animation

**Code Locations**:
- Backend: `resolve_half_court_offense_logic()` → `shot_manager.resolve_shot()`
- Frontend: `AnimationRouter` → `ShotAnimationSystem.processShot()` → `playTurnAnimation()`

---

### 2. FCP / HCT (Full Court Press / Half Court Trap)

**Structure**: `Skeleton Animation + Result Handling` (Same as HCO)

**Execution Flow**:
1. **Setup**: Players move to step 0 positions (from inbound or previous pressure turn)
2. **Skeleton Animation**: Animate all skeleton steps (full skeleton, same as HCO)
   - Uses press break skeletons (different data from playcall skeletons, but same animation system)
   - Full skeleton animation (all steps) - same pattern as HCO
3. **Result Handling**: 
   - **Unique Results**: Press Break/Trap Break to HCO (unique to FCP/HCT)
   - **Common Results**: MAKE, MISS, STEAL, DEAD_BALL_TURNOVER, FOUL, TURNOVER
   - Same result handling pattern as HCO (routed through same handlers)

**Key Characteristics**:
- ✅ **Uses same execution pattern as HCO** - Routes through AnimationRouter
- ✅ Full skeleton animation (all steps) - same as HCO
- ✅ Uses press break skeletons (different data, but same animation system)
- ✅ Routes to SHOT_ATTEMPT handler (for MAKE/MISS) or respective handlers (FOUL, TURNOVER, etc.)
- ✅ No special routing needed - unified with HCO system

**Code Locations**:
- Backend: `resolve_full_court_press_logic()` / `resolve_half_court_trap_logic()` → Press break skeleton data
- Frontend: `AnimationRouter` → Routes to same handlers as HCO (SHOT_ATTEMPT, FOUL, TURNOVER, etc.)
- Frontend: `playTurnAnimation()` → Same skeleton animation system as HCO

**Similarities to HCO**:
- ✅ Full skeleton animation (all steps)
- ✅ Routes through AnimationRouter
- ✅ Same result handling pattern
- ✅ Same animation system (`playTurnAnimation()`)
- ✅ Only difference: Uses press break skeleton data (not playcall skeleton data)

**State Management**:
- FCP/HCT state set via `next_defensive_setup` on BASELINE_INBOUND turns
- `scene.currentPressureType` tracks active pressure type ("FCP" or "HCT")
- `scene.pressureSequenceActive` tracks if pressure sequence is active
- State cleared when sequence completes (shot attempt completes, foul, turnover, or transition to HCO)

---

### 3. Free Throw

**Structure**: `Setup Animation + Result Handling`

**Execution Flow**:
1. **Setup Animation**: 
   - Players move to free throw line positions (offense + defense)
   - Ball attaches to shooter
   - Lane setup (or no-lane for technical fouls)
2. **Shot Animation**: Ball flight to rim
3. **Result Handling**:
   - **MAKE**: Ball hold at rim → Next free throw (if more remain) OR Inbound pass (if final)
   - **MISS**: Ball bounce from rim → Rebound handling (OREB or DREB)

**Bonus vs Set Number Handling**:
- **Turn-by-Turn Mode** (Preferred):
  - Uses `free_throws_remaining` field (number of FTs remaining after this turn, set by `BackEnd/engine/phase_resolution.py::resolve_free_throw_logic()`)
  - Uses `one_and_one` field (boolean flag indicating if this is a 1-and-1 situation)
  - If `free_throws_remaining > 0`: More shots remain
  - If `free_throws_remaining === 0`: This was the final shot
  - For 1-and-1: If first shot is missed → Rebound (no second shot); if made → Second shot unlocked
  - Works for all bonus types (1-and-1, 2-shot, 3-shot) and set number FTs
- **Batch Mode** (Fallback):
  - Uses `ftContext` (ftIndex, ftTotal, bonusType) if `free_throws_remaining` is undefined
  - **1-and-1 Bonus**: 
    - First shot: If made → Second shot (ftIndex: 1, ftTotal: 2)
    - If missed → Rebound
    - Second shot: If made → Inbound pass, If missed → Rebound
  - **2-Shot Bonus**: 
    - First shot: If made → Second shot (ftIndex: 1, ftTotal: 2)
    - Second shot: If made → Inbound pass, If missed → Rebound
  - **3-Shot Bonus**: 
    - First shot: If made → Second shot (ftIndex: 1, ftTotal: 3)
    - Second shot: If made → Third shot (ftIndex: 2, ftTotal: 3)
    - Third shot: If made → Inbound pass, If missed → Rebound
  - **Set Number (Non-Bonus)**: 
    - Each shot: If made → Next shot (if more remain) OR Inbound pass (if final)
    - If missed → Rebound

**Key Characteristics**:
- Setup is always the same (FT line positions)
- Result handling varies by bonus type and remaining shots
- **Turn-by-turn mode**: Uses `free_throws_remaining` (set by backend) and `one_and_one` flag to determine if more shots remain (preferred)
- **Batch mode**: Uses `ftContext` (ftIndex, ftTotal, bonusType) if `free_throws_remaining` is undefined (fallback)

**Code Locations**:
- Backend: `resolve_free_throw_logic()` → `capture_free_throw_animation()`
- Frontend: `FreeThrowAnimationSystem.processFreeThrow()` → `executeFreeThrowSequence()`

---

### 4. BIP (Baseline Inbound Pass)

**Structure**: `Standard Animation + FCP/HCT Setup (Conditional)`

**Execution Flow**:
1. **Setup Animation**: 
   - Offense: Players move to baseline inbound positions
   - Defense: Players move to defensive positions (normal OR FCP/HCT if `next_defensive_setup`)
2. **Pass Animation**: Inbound pass (SF → PG, or dynamic from animation data)
3. **State Setup**: 
   - If `next_defensive_setup === "FCP"` or `"HCT"`: Set `pressureSequenceActive = true`
   - Otherwise: Normal inbound (no pressure state)

**Key Characteristics**:
- Standard animation (positioning + pass)
- **Special handling**: Must check `next_defensive_setup` to set FCP/HCT state
- Sets up the NEXT turn (FCP/HCT or HCO)

**Code Locations**:
- Backend: `setup_baseline_inbound()` → `get_defender_coords()` (with pressure type)
- Frontend: `AnimationEngine.handleBaselineInbound()` → `runInboundSetup()`

---

### 5. SIP (Side Inbound Pass)

**Structure**: `Standard Animation`

**Execution Flow**:
1. **Setup Animation**: 
   - Offense: Players move to sideline inbound positions
   - Defense: Players move to defensive positions (normal, no FCP/HCT)
2. **Pass Animation**: Inbound pass (dynamic from animation data or fallback)
3. **State Setup**: Always transitions to HCO (no pressure setup)

**Key Characteristics**:
- Standard animation (positioning + pass)
- No FCP/HCT setup (only BIP handles pressure)
- Always leads to HCO

**Code Locations**:
- Backend: `setup_side_inbound()`
- Frontend: `AnimationEngine.handleSideInbound()` → `runInboundSetup()`

---

### 6. Fast Break

**Structure**: `Outlet Pass (Conditional) + Fast Break Resolution`

**Execution Flow**:
1. **Phase 1: Outlet Pass (Conditional)**:
   - **If DREB-initiated**: Outlet pass from rebounder to outlet receiver
   - **If STEAL-initiated**: No outlet pass (ball already with stealer)
2. **Phase 2: Fast Break Resolution**:
   - Animate fast break sequence (players moving down court)
   - Resolve outcome:
     - **MAKE**: Shot animation → Inbound pass (if no foul) OR Free throw (if foul)
     - **MISS**: Shot animation → Rebound handling (OREB or DREB)
     - **DEFENSIVE_STOP**: Fast break stopped → HCO (no possession change) - **Unique to Fast Break**
     - **FOUL**: Foul animation → Free throw (if shooting/bonus) OR Side inbound (if non-shooting)
     - **TURNOVER**: Turnover animation → Side inbound (PC) OR Fast Break (PC, if live ball)

**Key Characteristics**:
- Two-phase structure (outlet pass + resolution)
- Outlet pass is conditional (only for DREB-initiated)
- Fast break resolution is similar to HCO shot resolution
- Uses `fast_break` flag and `roles` (outlet_passer, outlet_receiver)
- **Unique Result**: DEFENSIVE_STOP (not available in HCO, FCP, HCT)

**Code Locations**:
- Backend: `resolve_fast_break_logic()` → `capture_fast_break_animation()`
- Frontend: `AnimationEngine.handleFastBreak()` → `runFastBreakSequence()`

---

### 7. OREB (Offensive Rebound)

**Structure**: `Rebound Animation + Putback/Kickout Decision`

**Execution Flow**:
1. **Rebound Animation**: 
   - Ball bounces from rim to rebounder
   - Rebounder catches ball
2. **Decision Point**: Putback attempt OR Kickout pass
   - **Putback Attempt**: 
     - Rebounder shoots immediately (PUTBACK_MAKE or PUTBACK_MISS)
     - If PUTBACK_MAKE: Inbound pass (if no foul) OR Free throw (if foul)
     - If PUTBACK_MISS: Another OREB (if offensive rebound) OR DREB (if defensive rebound)
   - **Kickout Pass**: 
     - Rebounder passes to perimeter → HCO (no possession change)

**Key Characteristics**:
- Rebound animation is always the same
- Decision (putback vs kickout) happens after rebound
- Putback attempts create separate PUTBACK_MAKE/PUTBACK_MISS turns
- Consecutive OREBs are batched in same API call

**Code Locations**:
- Backend: `resolve_offensive_rebound_turn()` → `resolve_putback_attempt()` or `resolve_kickout_pass()`
- Frontend: `handleOrebTurn()` → Putback animation OR Kickout animation

---

### 8. Opening Tip

**Structure**: `Standard Animation + Result Resolution`

**Execution Flow**:
1. **Setup Animation**: 
   - Both teams' centers at center court
   - Ball at center court
2. **Tip Animation**: Ball goes up, both centers jump
3. **Result Resolution**: 
   - Winner gains possession
   - Transitions to HCO (winning team on offense)

**Key Characteristics**:
- Simple animation (tip + possession determination)
- Always leads to HCO
- Only occurs at start of Q1 or OT

**Code Locations**:
- Backend: `resolve_opening_tip()` (if exists) or handled in `simulate_quarter()`
- Frontend: `AnimationEngine.handleOpeningTip()` or `playTurnAnimation()`

---

## Missing Turn Types?

Based on `transition_registry.py`, all turn types are:
- ✅ OPENING_TIP
- ✅ INBOUND_PASS (BIP)
- ✅ SIDE_INBOUND_PASS (SIP)
- ✅ HCO
- ✅ OREB
- ✅ FREE_THROW
- ✅ FAST_BREAK
- ✅ FCP
- ✅ HCT

**All turn types are accounted for.**

---

## Code Reuse Opportunities

### 1. **Skeleton Animation System**
- **Shared by**: HCO, FCP, HCT
- **Unified**: All use full skeleton animation (all steps)
  - HCO: Uses playcall skeletons
  - FCP/HCT: Uses press break skeletons (different data, same animation system)
- **Status**: ✅ **Unified** - All use `playTurnAnimation()` with full skeleton animation

### 2. **Result Handling**
- **Shared by**: HCO, FCP, HCT, Fast Break, OREB Putback
- **Common Results**: MAKE, MISS, FOUL, TURNOVER, STEAL
- **Unique Results**:
  - FCP/HCT: Press Break/Trap Break to HCO
  - Fast Break: DEFENSIVE_STOP
  - OREB Putback: PUTBACK_MAKE, PUTBACK_MISS
- **Streamlining**: Unified result handler with turn-type-specific logic (but results are NOT identical)

### 3. **Inbound Pass System**
- **Shared by**: BIP, SIP
- **Differences**: 
  - BIP: Handles FCP/HCT setup
  - SIP: Always leads to HCO
- **Streamlining**: Unified inbound system with conditional pressure setup

### 4. **Rebound System**
- **Shared by**: HCO MISS, Free Throw MISS, Fast Break MISS, OREB Putback MISS
- **Common Logic**: Ball bounce → Rebounder catch → Decision (OREB vs DREB)
- **Streamlining**: Already unified in `ReboundAnimationSystem`

### 5. **Setup Tween (Step 0 Positioning)**
- **Shared by**: HCO, FCP, HCT, Fast Break (after outlet)
- **Common Logic**: Move players to step 0 positions before skeleton animation
- **Streamlining**: Already unified in `runSetupTween()`

---

## Execution Case Coverage

### HCO Execution Cases:
- ✅ MAKE (no foul) → Inbound pass
- ✅ MAKE (foul) → Free throw
- ✅ MISS (OREB) → OREB turn
- ✅ MISS (DREB) → HCO (PC) OR Fast Break (PC)
- ✅ FOUL (shooting) → Free throw
- ✅ FOUL (non-shooting, bonus) → Free throw
- ✅ FOUL (non-shooting, no bonus) → Side inbound
- ✅ TURNOVER (dead ball) → Side inbound (PC)
- ✅ TURNOVER (live ball) → Fast Break (PC)
- ✅ STEAL → HCO (PC) OR Fast Break (PC)
- ⚠️ **Future**: More result types (fouls, turnovers) - structure supports this

### FCP/HCT Execution Cases:
- ✅ MAKE/MISS → Routes to SHOT_ATTEMPT handler (same as HCO)
- ✅ HCO (press break) → HCO (no PC)
- ✅ FOUL → Routes to FOUL handler (same as HCO)
- ✅ TURNOVER → Routes to TURNOVER handler (same as HCO)
- ✅ STEAL → Routes to STEAL handler (same as HCO)
- ✅ DEAD BALL → Routes to DEAD_BALL handler (same as HCO)
- ✅ **Fixed**: Now routes through AnimationRouter (same as HCO) - no special routing needed

### Free Throw Execution Cases:
- ✅ **Turn-by-turn mode**: Uses `free_throws_remaining` field
  - If `free_throws_remaining > 0`: More shots remain → Next free throw
  - If `free_throws_remaining === 0`: Final shot → Rebound OR Inbound
- ✅ **Batch mode**: Uses `ftContext` (ftIndex, ftTotal, bonusType) if `free_throws_remaining` is undefined
  - Single FT → Make/Miss → Rebound OR Inbound
  - 1-and-1 Bonus → First shot → Second shot (if made) OR Rebound (if missed)
  - 2-Shot Bonus → First shot → Second shot (if made) OR Rebound (if missed)
  - 3-Shot Bonus → First → Second → Third → Rebound OR Inbound
  - Set Number → Each shot → Next (if more) OR Rebound/Inbound (if final)
- ✅ **Fixed**: Inbound pass timing (now flips possession before inbound)

### Fast Break Execution Cases:
- ✅ DREB-initiated → Outlet pass → Resolution
- ✅ STEAL-initiated → Resolution (no outlet)
- ✅ Resolution: MAKE, MISS, DEFENSIVE_STOP, FOUL, TURNOVER
- ✅ **Fixed**: Possession flip timing (now flips before inbound)

### OREB Execution Cases:
- ✅ Putback attempt → PUTBACK_MAKE OR PUTBACK_MISS
- ✅ Kickout pass → HCO (no PC)
- ✅ Consecutive OREBs → Batched in same API call
- ✅ Putback with foul → Free throw

### BIP/SIP Execution Cases:
- ✅ BIP (normal) → HCO
- ✅ BIP (FCP setup) → FCP turn
- ✅ BIP (HCT setup) → HCT turn
- ✅ SIP → HCO (always)

---

## Recommendations for Streamlining

### 1. **Unified Skeleton Animation System**
- Create `SkeletonAnimationSystem` that handles:
  - Full skeleton (HCO)
  - Filtered skeleton (FCP/HCT)
  - Step filtering logic
- Parameter: `filterByResultType: boolean`

### 2. **Unified Result Handler**
- Create `ResultHandler` that routes to appropriate handlers:
  - Shot results (MAKE/MISS)
  - Foul results (shooting/non-shooting, bonus/no bonus)
  - Turnover results (dead ball/live ball)
  - Steal results
- Turn-type-specific logic as parameters

### 3. **Unified Inbound System**
- Enhance `runInboundSetup()` to handle:
  - BIP (with FCP/HCT setup)
  - SIP (always HCO)
- Parameter: `inboundType: "baseline" | "side"`

### 4. **Execution Structure Template**
- Define common execution pattern:
  ```typescript
  interface TurnExecution {
    setup: () => Promise<void>;
    animation: () => Promise<void>;
    resultHandling: () => Promise<void>;
  }
  ```
- Each turn type implements this interface

---

## Summary

**Turn Types Covered**: 9 (all from transition registry)

**Execution Patterns Identified**:
1. **Skeleton + Result** (HCO, FCP, HCT) - All use same pattern (AnimationRouter)
2. **Setup + Result** (Free Throw)
3. **Standard Animation** (BIP, SIP, Opening Tip)
4. **Multi-Phase** (Fast Break: outlet + resolution)
5. **Animation + Decision** (OREB: rebound + putback/kickout)

**Code Reuse Opportunities**: 5 major areas identified

**Execution Case Coverage**: All cases documented, some issues identified (FCP/HCT skeleton skipping)

**Next Steps**: 
1. ✅ **Completed**: FCP/HCT now routes through AnimationRouter (unified with HCO) - Verified in code (old FCP/HCT handling commented out in `animateGameTurns.js`, now uses standard AnimationRouter flow)
2. ✅ **Completed**: Unified skeleton animation system (`playTurnAnimation()`) - All turn types (HCO, FCP, HCT) use same skeleton animation system
3. ✅ **Completed**: Unified result handler (AnimationRouter routes to appropriate handlers) - AnimationEngine.determineHandler() routes all turn types to appropriate handlers
4. ⚠️ **Optional Future**: Create execution structure template (optional future enhancement) - Current structure works well, template would be nice-to-have for consistency

---

# Part 3: Documentation Status

> **Last Reviewed:** February 2025  
> **Status:** ✅ **CURRENT** - Both data structure and execution patterns are up-to-date with codebase

## Documentation Currency

### ✅ **Data Structure Section (Part 1)**
- All fields documented and current
- `offense_team_id` properly documented as authoritative (replaces deprecated `possession_team_id`)
- All new fields added (`current_turn`, `next_turn`, `team_stats`, `team_totals`, `team_plays`, `player_energy`, strategy calls, `free_throws_remaining`)
- Sample payloads reflect current structure

### ✅ **Execution Patterns Section (Part 2)**
- All turn types documented (9 total)
- FCP/HCT execution pattern updated to reflect AnimationRouter usage (unified with HCO)
- Free Throw section documents both turn-by-turn and batch modes
- All execution cases covered
- Code locations verified

### ⚠️ **Optional Items (Low Priority)**
- Debug fields (`debug_turn_start`, `debug_turn_result`) are optional debug-only fields - not critical to document

## Code References (Verified February 2025)

### Backend Fields (turn_manager.py)
- Line 790-793: `result["offense_team_id"] = self.game.offense_team.team_id`
- Line 469: `result["current_turn"] = state`
- Line 474: `result["next_turn"] = result["next_play_type"]`
- Lines 642-651: `result["team_stats"]`
- Lines 656-659: `result["team_totals"]`
- Lines 662-665: `result["team_plays"]`
- Lines 746-756: `result["player_energy"]`
- Lines 759-762: Strategy call fields

### Frontend Execution (animateGameTurns.js)
- Line 806: Comment: "✅ COMMENTED OUT: FCP/HCT now routes through AnimationRouter (same as HCO)"
- Line 1190: HCO routes through AnimationRouter
- AnimationRouter.js: FCP/HCT routes to same handlers as HCO

---

**This document consolidates the previous `turn_data_structure.md` and `TURN_EXECUTION_STRUCTURE.md` into a single comprehensive reference.**

