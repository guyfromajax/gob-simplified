# State and Persistence

> **Last Updated:** February 2025  
> **Status:** Current – Source of Truth for State, Persistence, and Navigation Contracts

This document defines how state is owned, persisted, validated, and transitioned across instance types in Geeked-Out Basketball (GOB). It serves as the authoritative reference for navigation anchors, persistence strategies, validation rules, fallback behavior, and cross-bucket data flow.

---

## Core Concepts

### Navigation Anchor Set
Minimal identifiers required for navigation between screens. These form the "anchor" that maintains context.

### State Data
Actual game or system state that must be loaded from database or URL parameters. Represents the current state of the experience.

### Context Data
Additional URL parameters and context information used for operations, display, or special cases. Not required for core navigation but needed for specific functionality.

---

## Bucket-Level Navigation Anchor Sets

- **Bucket 1 (GA):**
  - `user_id`

- **Bucket 2 (GMO):**
  - `mode`
  - `{mode}_id` (tournament_id or franchise_id)
  - `team_id`

- **Bucket 3 (GP):**
  - `mode`
  - `{mode}_id` (tournament_id or franchise_id)
  - `game_id`
  - `team_id`

- **Bucket 4 (NA):**
  - None

**Note:** `user_id` should always be maintained during transitions (even when not in Navigation Anchor Set) for authorization/logging purposes.

---

## Bucket 1: General Account (GA)

### Navigation Anchor Set
**Required:**
- `user_id`

### State Data
**Required:** None  
- No game state  
- No gameplay data

### Context Data
**Optional:**
- `session_id`
- `last_visited`

### Persistence Strategy
- **URL Params:** `user_id`, optional `session_id`, `last_visited`
- **Database:** User account data
- **LocalStorage:** Optional user preferences
- **Session:** Optional session state

---

## Bucket 2: Game Mode Only (GMO)

### Navigation Anchor Set
**Required:**
- `mode` ("tournament" or "franchise")
- `tournament_id` or `franchise_id`
- `team_id` (ObjectId string)

### State Data
**Required:**
- Tournament:
  - `tournament.completed`
  - `tournament.current_round`
- Franchise:
  - `franchise.week`
  - `franchise.season`
  - `franchise.training_status`
- Team state:
  - Team attributes
  - Strategy settings
  - Playbook settings

**Optional:**
- Training history
- Player attributes
- View context

### Context Data
**Optional:**
- `view_team_id`
- `from`
- `week`
- `session_id`
- `last_visited`

---

### Validation Rules

- **Mode + Doc ID (Strict):**
  - Must be valid and match
  - Fail fast if missing or invalid

- **Team ID (Non-Strict with Fallback):**
  - Primary: URL param `team_id`
  - Fallback 1: Resolve from database using tournament_id/franchise_id
  - Fallback 2: Default team from game mode document
  - Only fail if all fallbacks fail

- **View Team ID (Optional):**
  - Validate only if present

---

### Persistence Strategy

- **URL Params:**
  - Always: `mode`, `{mode}_id`, `team_id`
  - Conditionally: `view_team_id`, `from`, `week`
- **Database:**
  - Game mode document
  - Team objects within game mode document
  - Strategy and playbook settings stored in team object
- **LocalStorage:**
  - Optional last visited page
  - Not used for game state

---

## Bucket 3: Gameplay (GP)

### Navigation Anchor Set
**Required:**
- `mode`
- `game_id`
- `team_id`

**Conditionally Required:**
- `tournament_id` (Tournament)
- `franchise_id` (Franchise)

---

### State Data

**Required:**
- `game_id`
- `quarter`
- `score`
- `time_remaining`
- Game mode state (if applicable)
- Lineup state
- `my_team`

**Timeout State (if applicable):**
- `timeout_next_play_type`
- `timeout_offense_team_id`
- `resume_from_timeout`
- `clock`

**Game Plan State:**
- `strategy_settings`
- `playbook_settings`

---

### Context Data

**Required:**
- `game_id`
- `mode`
- `my_team`
- `team_id`

**Conditionally Required:**
- `tournament_id`
- `franchise_id`
- `resume_from_timeout`
- `clock`
- `quarter`

**Optional:**
- `from`
- `home` / `away`
- `home_id` / `away_id`

---

### Validation Rules

- **Game ID Logic (Strict):**
  - Required when `quarter > 1` OR `resume_from_timeout === true`
  - Not required for new Q1 start
  - Must exist in database when required

- **Resume From Timeout (Conditional):**
  - Requires frontend URL params and backend timeout state
  - Database must contain timeout state for the quarter

- **Quarter Breaks (Strict):**
  - `game_id` required
  - `resume_from_timeout` must not be set

- **Mode + Doc ID (Strict):**
  - Tournament: `tournament_id` + `game_id`
  - Franchise: `franchise_id` + `game_id`
  - Single: `game_id` only

- **Team ID (Non-Strict with Fallback):**
  - Primary: URL param
  - Fallback: Database resolution
  - Only fail if all fallbacks fail

---

### Persistence Strategy

- **URL Params:**
  - Always: `mode`, `team_id`, `my_team`
  - Conditionally: `game_id`, `resume_from_timeout`, `clock`, `quarter`
- **Database:**
  - Game document (source of truth)
  - Timeout state
  - Game mode document (Tournament/Franchise)
- **LocalStorage:**
  - Optional `game_id`
  - Not used for game state

---

## Bucket 4: Non-Account (NA)

### Navigation Anchor Set
**Required:** None

### State Data
**Required:** None

### Context Data
**Optional:**
- `guest_session_id`
- `return_url`

### Persistence Strategy
- **URL Params:** Optional `return_url`
- **Database:** None
- **LocalStorage:** Optional guest preferences

---

## Cross-Bucket Data Flow Rules

### General Principles
1. **Database is Source of Truth**
2. **URL Params for Navigation Only**
3. **ObjectId Standardization for `team_id`**
4. **Complete Anchor Set Must Be Preserved**
5. **Hybrid Validation with Fallbacks**
6. **Graceful Recovery Preferred Over Fail-Fast**

---

## Data Validation on Transition

- Validate on entry for each page
- Fallback priority:
  - URL params
  - LocalStorage
  - Database lookup
  - Defaults
- Only fail when critical data cannot be resolved

---

## Testing Requirements

- Transition tests between buckets
- Data persistence tests
- Edge case tests (timeout, foul out, quarter breaks, completion)
- Mode-specific tests


