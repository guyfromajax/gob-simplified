# Unified Data Structure Analysis for 51 Transitions

## Executive Summary

This analysis examines whether we can implement a unified data structure across all 51 transition types. After reviewing the codebase, **a fully unified structure is not recommended**, but **a hybrid approach with a core schema + optional fields** would provide significant benefits while maintaining flexibility.

## Current State Analysis

### 1. Data Flow Pattern

All transitions follow this pattern:
1. **Phase Resolution** (`phase_resolution.py`, `shot_manager.py`) - Creates initial result dict with turn-specific fields
2. **Turn Manager** (`turn_manager.py`) - Adds common metadata fields to ALL results
3. **Game Manager** (`game_manager.py`) - Handles batching (OREBs, inbounds) and transition validation

### 2. Common Fields (Always Present)

These fields are added to **every** result in `turn_manager.py` after phase resolution:

```python
# Core identification
- result_type: str                    # "MAKE", "MISS", "FOUL", "FREE_THROW", etc.
- offense_team_id: str                # ✅ SS&S Standard: Team on offense during this turn (authoritative)
- possession_team_id: str             # ⚠️ DEPRECATED: Backward compatibility only, use offense_team_id
- current_turn: str                   # Explicit turn type (HCO/FCP/HCT/FAST_BREAK/FREE_THROW/OREB/BASELINE_INBOUND/SIDE_INBOUND/OPENING_TIP)
- next_turn: str                      # Explicit next turn type (set by game_manager.determine_next_turn())
- possession_flips: bool              # Whether possession changes after this turn
- quarter: int                        # Current quarter
- turn_count: int                     # Micro turn counter

# Game state
- score: dict                         # {home_team: X, away_team: Y}
- time_elapsed: int                    # Seconds elapsed in this turn
- text: str                           # Human-readable description

# Lineups
- home_lineup: dict                   # Serialized lineup
- away_lineup: dict                   # Serialized lineup

# Stats
- team_stats: dict                    # Scouting data (offense/defense)
- team_totals: dict                   # Cumulative team stats
- deltas: dict                        # Player stat changes
- player_energy: dict                 # Current NG levels

# Plays
- team_plays: dict                    # Play effectiveness data

# Strategy
- offense_tempo_call: str
- offense_aggression_call: str
- defense_tempo_call: str
- defense_aggression_call: str

# Debug
- debug_turn_start: str
- debug_turn_result: str
```

### 3. Conditional Fields (Turn-Specific)

These fields are added **only when relevant** to specific result types:

#### Shot Results (MAKE/MISS)
```python
- shooter: Player / dict
- shooter_id: str
- shooter_pos: str
- ball_handler: Player / dict
- passer: Player / dict
- screener: Player / dict
- defender: Player / dict
- points: int (if made)
- scoring_team: str (if made)
- next_play_type: str (e.g., "BASELINE_INBOUND")
- next_defensive_setup: str (e.g., "FCP", "HCT")
- free_throws_remaining: int (if AND-1 or free throw)
- one_and_one: bool (if 1-and-1 bonus situation)
- has_and_one: bool (if AND-1 on made shot)
- intended_shooter_pos: str
- intended_shooter_id: str
- foul_player_id: str (if shooting foul)
- foul_team: str
```

#### Free Throw Results
```python
- shooter: Player / dict
- shooter_id: str
- shooter_pos: str
- ball_handler: Player / dict
- points: int (if made)
- scoring_team: str (if made)
- free_throws_remaining: int (set by resolve_free_throw_logic())
- one_and_one: bool (indicates 1-and-1 bonus situation)
- attempts: list[str] (ordered results: ["MAKE", "MISS"])
- rebounderId: str (camelCase, primary field - if missed)
- rebound_type: str (if missed, "OREB" or "DREB")
- next_play_type: str (if DREB)
- next_defensive_setup: str
```

#### Foul Results
```python
- ball_handler: Player / dict
- defender: Player / dict
- foul_player_id: str
- foul_team: str
- foul_count: int
- fouled_out: bool
- foul_out_player: dict (if applicable)
- fcp_foul: bool (if FCP foul)
- hct_foul: bool (if HCT foul)
```

#### Turnover Results
```python
- ball_handler: Player / dict
- victim_id: str
- victim_name: str
- stealer_id: str (if STEAL)
- stealer_name: str (if STEAL)
- defender_id: str (if STEAL)
```

#### Fast Break Results
```python
- fast_break: bool
- roles: dict (outlet_passer, outlet_receiver)
- next_play_type: str
```

#### FCP/HCT Results
```python
- fcp_foul: bool / hct_foul: bool
- fcp_shot: bool / hct_shot: bool
- skeleton: dict
- roles: dict
- defender_id: str
```

#### Inbound Pass Results
```python
- oDestinations: dict
- dDestinations: dict
- ball_spot: dict
- next_defensive_setup: str
```

#### HCO Results
```python
- offensive_playcall: str
- defensive_playcall: str
- offensive_play_type: str
- offensive_play_focus: str
- defensive_play_type: str
- defensive_play_focus: str
- ev: float
- animations: list
- roles: dict
```

#### OREB Results
```python
- rebounderId: str (camelCase, primary field)
- rebound_type: str ("OREB")
- animations: list (if putback attempt)
```

### 4. Field Categories

Fields can be categorized by **purpose**:

1. **Transition Control** (determines next turn)
   - `result_type`
   - `current_turn` (explicit turn type identifier)
   - `next_turn` (explicit next turn type, set by game_manager.determine_next_turn())
   - `possession_flips`
   - `next_play_type` (informational hint, not authoritative)
   - `next_defensive_setup`
   - `offensive_state` (in game_state, not result)

2. **Animation Data** (frontend rendering)
   - `animations`
   - `skeleton`
   - `roles`
   - `oDestinations` / `dDestinations`
   - `ball_spot`

3. **Player Actions** (who did what)
   - `shooter`, `passer`, `defender`, `ball_handler`
   - `stealer_id`, `victim_id`
   - `foul_player_id`

4. **Game State** (score, time, stats)
   - `score`, `time_elapsed`, `quarter`
   - `deltas`, `team_stats`, `team_totals`
   - `player_energy`

5. **Context** (playcalls, strategy)
   - `offensive_playcall`, `defensive_playcall`
   - `offense_tempo_call`, `defense_aggression_call`
   - `ev`

6. **Metadata** (debugging, tracking)
   - `debug_turn_start`, `debug_turn_result`
   - `turn_count`

## Feasibility Assessment

### Option 1: Fully Unified Structure (NOT RECOMMENDED)

**Approach**: Create a single `TurnResult` class with ALL possible fields, most set to `None` by default.

**Pros**:
- Type safety (TypeScript/Python typing)
- Single source of truth
- Easier validation

**Cons**:
- **Massive bloat**: Every result would have 50+ fields, 90% of which are `None`
- **Performance**: Larger payloads, more memory
- **Maintenance**: Adding new fields requires updating the class definition
- **Confusion**: Hard to see which fields are actually relevant for a given turn
- **Violates SS&S**: Unnecessary complexity

**Verdict**: ❌ **Not feasible** - The overhead outweighs the benefits.

### Option 2: Core Schema + Optional Fields (RECOMMENDED)

**Approach**: Define a **core schema** (always-present fields) and **optional field groups** (turn-specific).

**Structure**:
```python
# Core Schema (always present)
{
    "result_type": str,
    "offense_team_id": str,              # ✅ SS&S Standard (authoritative)
    "possession_team_id": str,           # ⚠️ DEPRECATED (backward compatibility only)
    "current_turn": str,                 # Explicit turn type identifier
    "next_turn": str,                    # Explicit next turn type
    "possession_flips": bool,
    "quarter": int,
    "turn_count": int,
    "score": dict,
    "time_elapsed": int,
    "text": str,
    "home_lineup": dict,
    "away_lineup": dict,
    "team_stats": dict,
    "team_totals": dict,
    "deltas": dict,
    "player_energy": dict,
    "team_plays": dict,
    "offense_tempo_call": str,
    "offense_aggression_call": str,
    "defense_tempo_call": str,
    "defense_aggression_call": str,
    "debug_turn_start": str,
    "debug_turn_result": str
}

# Optional Field Groups (added conditionally)
{
    # Shot fields (if result_type in ["MAKE", "MISS"])
    "shooter": dict,
    "shooter_id": str,
    "passer": dict,
    "defender": dict,
    "points": int,
    "scoring_team": str,
    "next_play_type": str,
    "next_defensive_setup": str,
    
    # Free throw fields (if result_type == "FREE_THROW")
    "free_throws_remaining": int,        # Set by resolve_free_throw_logic()
    "one_and_one": bool,                 # 1-and-1 bonus flag
    "attempts": list[str],                # Ordered results: ["MAKE", "MISS"]
    "rebounderId": str,                  # camelCase (if missed)
    "rebound_type": str,                 # "OREB" or "DREB" (if missed)
    
    # Foul fields (if result_type == "FOUL")
    "foul_player_id": str,
    "foul_team": str,
    "foul_count": int,
    
    # Animation fields (if animations exist)
    "animations": list,
    "skeleton": dict,
    "roles": dict,
    
    # ... etc
}
```

**Pros**:
- ✅ **Clear separation**: Core vs. optional fields
- ✅ **Type safety**: Can define TypeScript/Python types for core + optional groups
- ✅ **Validation**: Can validate core fields always present, optional fields conditionally
- ✅ **Documentation**: Clear which fields belong to which result types
- ✅ **Performance**: Only includes relevant fields
- ✅ **SS&S**: Maintains simplicity while adding structure

**Cons**:
- ⚠️ **Implementation effort**: Need to refactor phase resolution functions
- ⚠️ **Testing**: Need to ensure all transitions still work

**Verdict**: ✅ **Feasible and recommended**

### Option 3: Validation Layer Only (MINIMAL)

**Approach**: Keep current structure, add validation functions that check required fields per result type.

**Pros**:
- ✅ Minimal code changes
- ✅ Can catch bugs early
- ✅ No performance impact

**Cons**:
- ❌ Doesn't solve the "what fields exist?" problem
- ❌ No type safety
- ❌ Still requires manual documentation

**Verdict**: ⚠️ **Partial solution** - Good for catching bugs, but doesn't provide structure benefits.

## Recommended Implementation Plan

### Phase 1: Define Core Schema (Low Risk)

1. Create `TurnResultCore` type/class with always-present fields
2. Document optional field groups in `docs/`
3. Add validation function: `validate_turn_result(result: dict) -> bool`
4. Add to transition validator to catch missing core fields

**Impact**: Documentation + validation, no code changes required

### Phase 2: Refactor Phase Resolution (Medium Risk)

1. Create helper functions for each optional field group:
   - `add_shot_fields(result, shooter, passer, ...)`
   - `add_free_throw_fields(result, shooter, ...)`
   - `add_foul_fields(result, foul_player, ...)`
   - etc.
2. Refactor phase resolution functions to use helpers
3. Ensure all 51 transitions still work

**Impact**: Cleaner code, easier to maintain, type safety possible

### Phase 3: Type Definitions (Low Risk)

1. Create TypeScript types for frontend:
   - `TurnResultCore`
   - `TurnResultWithShots`
   - `TurnResultWithFreeThrows`
   - etc.
2. Create Python TypedDict equivalents
3. Update frontend to use types

**Impact**: Type safety, better IDE support, catch errors at compile time

## Transition-Specific Considerations

### Different Data Needs by Transition Type

1. **Opening Tip → HCO**: Minimal data (no previous turn context)
2. **HCO → Inbound Pass**: Needs `next_defensive_setup` for FCP/HCT
3. **HCO → Free Throw**: Needs `free_throws_remaining`, `has_and_one`
4. **Free Throw → Free Throw**: Needs `free_throws_remaining`, `one_and_one`
5. **OREB → OREB**: Needs `rebounderId`, `rebound_type`
6. **Fast Break → Fast Break**: Needs `fast_break`, `roles`
7. **FCP/HCT → HCO**: Needs `skeleton`, `roles`, pressure flags

**Key Insight**: The **transition type** determines which optional fields are needed, not just the result type.

## Recommendations

### ✅ DO:
1. **Implement Option 2 (Core Schema + Optional Fields)**
2. **Start with Phase 1** (validation + documentation)
3. **Create field group documentation** mapping result types → field groups
4. **Add transition-aware validation** (check fields based on transition pair)

### ❌ DON'T:
1. **Don't create a monolithic class** with all fields
2. **Don't break existing transitions** - refactor incrementally
3. **Don't add fields "just in case"** - only add when needed

### 🎯 Success Criteria:
- All 51 transitions still work
- Type safety for core fields
- Clear documentation of optional fields
- Validation catches missing required fields
- No performance regression
- Easier to add new transition types

## Conclusion

A **unified data structure is feasible** using a **hybrid approach**:
- **Core schema** (always-present fields) provides consistency
- **Optional field groups** (turn-specific) provide flexibility
- **Validation layer** ensures correctness

This approach balances **SS&S principles** (simplicity, scalability) with **type safety** and **maintainability**. The implementation can be done incrementally without breaking existing functionality.

