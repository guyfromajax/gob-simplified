# Navigation Data Requirements by Experience Bucket

> **Last Updated:** February 2025  
> **Status:** Current - Source of Truth for Navigation Requirements

This document defines the data requirements for all page-to-page transitions across the game experience, organized by instance type. Includes the Team ID Navigation Pattern (SS&S) as a core requirement. Aligned with the user-flow.md structure.

**Instance Type Mapping:**
- **NA (Non-Account)** = Bucket 4
- **GA (General Account)** = Bucket 1
- **GMO (Game Mode Only)** = Bucket 2
- **GP (Gameplay)** = Bucket 3

---

## Bucket 1: General Account (GA)

**Definition:** User is logged into their account but not in a specific game mode instance (outside of Single Game, Tournament Mode, or Franchise Mode instance).

**Examples:**
- Homepage (homepage.html)
- Mode selection screen (mode-select.html)
- Settings/Account pages (TBD)
- Tutorial pages (TBD)

### Navigation Anchor Set
**Required:**
- `user_id` - User account identifier (required - user must be logged in to be in GA instance)

### State Data
**Required:** None
- No game state to preserve
- No gameplay data

### Context Data
**Optional:**
- `session_id` - Session identifier (if using sessions)
- `last_visited` - Last page visited (for back navigation)

### Validation Rules
- **User ID (Strict):** Must be present and valid (user must be logged in to be in GA instance)
- **No game mode validation:** No game mode context to validate

### Persistence Strategy
- **URL Params:** 
  - Always: `user_id` (required)
  - Optional: `session_id`, `last_visited`
- **Database:** 
  - User account data (if needed for page display)
- **LocalStorage:** 
  - Optional: User preferences, last visited page
- **Session:** 
  - Optional: Session state if using sessions

### Transition Patterns
- **To Bucket 2 (GMO):** 
  - Must initialize game mode document (tournament_id or franchise_id) + team_id
  - **Note:** `user_id` should be maintained (not in Navigation Anchor Set but needed for authorization/logging)
- **To Bucket 3 (GP):** 
  - Must initialize game mode document AND game document (game_id) + team_id
  - **Note:** `user_id` should be maintained (not in Navigation Anchor Set but needed for authorization/logging)
- **To Bucket 4 (NA):** Clear all account-related data (including `user_id`)

---

## Bucket 2: Game Mode Only (GMO)

**Definition:** User is in a Tournament Mode or Franchise Mode instance, but not actively playing a game. User can never be in a GMO instance in Single Game mode.

**Sub-categories:**
- **2A: Tournament Mode** (tournament command center, playbooks, game plan)
- **2B: Franchise Mode** (franchise command center, training, playbooks, game plan)

**Examples:**
- Tournament/Franchise Command Center
- Training screen (Franchise only)
- Training Report (Franchise only)
- Playbooks screen
- Game Plan screen
- Team Roster screen
- Standings/Stats screens/tabs

### Navigation Anchor Set
**Required:**
- **Mode:** `"tournament"` or `"franchise"` (determines which collection/endpoints)
- **Doc ID:** `tournament_id` (Tournament) or `franchise_id` (Franchise)
- **Team ID:** `team_id` (ObjectId string) - User's team anchor

**Validation:**
- All three parameters must be present for seamless navigation
- `team_id` must be ObjectId format (not team name)

**Note on `team_id` vs `user_team_object_id`:**
- **URLs/Navigation:** Always use `team_id` (ObjectId string) in URL parameters and navigation
- **Database:** Stored as `user_team_object_id` in game mode documents (tournament/franchise)
- **Consistency:** The codebase standardizes on `team_id` for all navigation and URL parameters, even though the database field is named `user_team_object_id`. This ensures consistent navigation patterns across the application.

### State Data
**Required:**
- **Game Mode State:**
  - Tournament: `tournament.completed`, `tournament.current_round`
  - Franchise: `franchise.week`, `franchise.season`, `franchise.training_status`
- **Team State:**
  - Team attributes (from `tournament.teams.{team_id}` or `franchise.franchise_teams.{team_id}`)
  - Strategy settings (from team object)
  - Playbook settings (from team object)

**Optional:**
- Training history (for training report - Franchise only)
- Player attributes (if viewing roster)
- View context (if viewing opponent/other team data)

**Note:** Optional state data is only needed for specific screens (e.g., training history for Training Report, player attributes for Roster view). It's not required for all GMO screens.

### Context Data
**Optional:**
- `view_team_id` - Team being viewed (if viewing opponent/other team) - **Display context only, not part of navigation anchor**
- `from` - Source page (for back navigation logic, e.g., "command_center", "lineup")
- `week` - Franchise week (for navigation context - Franchise only)
- `session_id` - Session identifier (if using sessions)
- `last_visited` - Last page visited (for back navigation)

**Note:** Context Data items are optional and provide additional context for specific operations but are not required for navigation. Items already in Navigation Anchor Set (`mode`, `doc_id`, `team_id`) are not duplicated here.

### Validation Rules

Validation Rules define how data is validated on page entry:

- **Mode + Doc ID (Strict):** Must be valid and match (tournament_id for tournament mode, franchise_id for franchise mode)
  - **Behavior:** Fail fast if missing or invalid
  - **No fallback:** These are critical for navigation

- **Team ID (Non-Strict with Fallback):** 
  - **Primary:** URL param `team_id` (ObjectId format)
  - **Fallback 1:** Resolve from database using tournament_id/franchise_id (check `user_team_object_id` field)
  - **Fallback 2:** Use default team from game mode document
  - **Only fail if all fallbacks fail:** This allows graceful recovery if URL param is missing

- **View Team ID (Optional):** If provided, must be valid ObjectId (for viewing other teams)
  - **Behavior:** Only validate if present (optional parameter)

### Persistence Strategy
- **URL Params:** 
  - Always: `mode`, `{mode}_id` (tournament_id or franchise_id), `team_id` (ObjectId string)
  - Conditionally: `view_team_id`, `from`, `week` (Franchise only)
- **Database:** 
  - Game mode document (tournament or franchise)
  - Team objects within game mode document (accessed via `tournament.teams.{team_id}` or `franchise.franchise_teams.{team_id}`)
  - **Note:** Team objects are explicitly specified because they are the primary navigation/data access point, even though they are nested within the game mode document
  - **Game Plan & Playbooks Settings:** Stored in team object (`strategy_settings`, `playbook_settings`) and persist across all GMO and GP instances until changed
- **LocalStorage:** 
  - Optional: Last visited page
  - **Future:** User preferences (not yet implemented)
  - Not used for game state (database is source of truth)

**Navigation Persistence Requirements:**
- **TCC/FCC → Game Plan/Playbooks:** Navigation Anchor Set (`mode`, `doc_id`, `team_id`) must be preserved to maintain context and allow settings to load/save correctly
- **Playbooks → Play Details Pages:** Navigation Anchor Set (`mode`, `doc_id`, `team_id`) and `from` parameter must be preserved to allow return navigation
- **Scouting Reports:** Displayed as modal (no separate page navigation), so no URL parameter persistence needed

### Transition Patterns
- **To Bucket 1 (GA):** 
  - Clear game mode context (remove `mode`, `doc_id`, `team_id` from URL)
  - **Preserve:** `user_id` (required for GA instance)
- **To Bucket 2 (GMO - same mode):** 
  - Preserve all navigation anchor set (`mode`, `doc_id`, `team_id`)
  - **Note:** Intra-bucket navigation (GMO → GMO) just maintains Navigation Anchor Set
- **To Bucket 2 (GMO - different mode):** 
  - **NOT ALLOWED** - Must go through Mode Select first
- **To Bucket 3 (GP):** 
  - **Preserve:** `mode`, `doc_id` (tournament_id/franchise_id), `team_id`, `user_id`
  - **Initialize:** `game_id`, `quarter` (if Q1), `my_team` (user's team side: "home" or "away")
- **To Bucket 4 (NA):** 
  - Clear all game mode and account data (including `user_id`)

### Special Cases
- **Training Report (Franchise only):** 
  - Backend determines training week from franchise state
  - `week` parameter optional (for explicit navigation context)
- **Game Plan:** 
  - Requires `from` parameter to determine back navigation
  - **Status:** ✅ **RESOLVED** - `from` parameter is preserved through Playbooks navigation
  - **Settings Persistence:** Game Plan settings (`strategy_settings`) persist in team object and are loaded when accessing from TCC/FCC or during gameplay
- **Playbooks:** 
  - Must preserve `from` parameter when navigating Game Plan ↔ Playbooks
  - **Settings Persistence:** Playbook settings (`playbook_settings`) persist in team object and are loaded when accessing from TCC/FCC or during gameplay
- **Play Details Pages (from Playbooks):** 
  - Must preserve Navigation Anchor Set (`mode`, `doc_id`, `team_id`) and `from` parameter
  - **Current Implementation:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()` which preserves `team_id` and should preserve `mode`/`doc_id` from sourceParams
  - **Note:** When navigating from GMO context (TCC/FCC), ensure `mode` and `doc_id` are explicitly preserved (not just gameplay params)
- **Scouting Reports:** 
  - Displayed as modal overlay (not separate page), so no navigation persistence needed
  - Data loaded via API using `franchise_id` and `team_name` parameters
- **Viewing Other Teams:** 
  - Requires `view_team_id` (display context only) while preserving `team_id` (user's team for navigation)
  - **Pattern:** `team_id` = user's team (navigation anchor), `view_team_id` = team being viewed (display only)

---

## Bucket 3: Gameplay (GP)

**Definition:** User is actively playing a game (in gameplay experience).

**Sub-categories:**
- **3A: Single Game Mode** (no tournament/franchise context)
- **3B: Tournament Mode Gameplay** (game within tournament)
- **3C: Franchise Mode Gameplay** (game within franchise)

**Examples:**
- Court/Gameplay screen
- Set Lineup screen (during game)
- Game Plan screen (during game)
- Playbooks screen (during game)
- Box Score screen (during and after game)
- Timeout/Foul Out popup → Lineup screen
- Plays pages (during game)

### Understanding the Three Classifications

**Navigation Anchor Set:** Minimal identifiers required for navigation between screens. These form the "anchor" that maintains context.

**State Data:** Actual game/system state that must be loaded from database or URL params. Represents the current state of the game.

**Context Data:** Additional URL parameters and context information used for operations, display, or special cases. Not required for core navigation but needed for specific functionality.

**Note:** Some items appear in multiple sections because they serve different purposes:
- In Navigation Anchor Set: needed for navigation routing
- In State Data: needed to load/preserve actual state
- In Context Data: needed as URL parameter for operations

### Navigation Anchor Set
**Required:**
- **Mode:** `"single"`, `"tournament"`, or `"franchise"`
- **Doc ID:** 
  - Single: `game_id` only
  - Tournament: `tournament_id` + `game_id`
  - Franchise: `franchise_id` + `game_id`
- **Team ID:** `team_id` (ObjectId string) - User's team anchor

**Note:** `user_id` is not in Navigation Anchor Set (not needed for navigation), but should be maintained during transitions (see Transition Patterns).

**Validation:**
- All required parameters must be present
- `game_id` must exist in database (when required - see Validation Rules)
- For Tournament/Franchise: game must be nested in correct game mode document

### State Data
**Required:**
- **Game State:**
  - `game_id` - Current game identifier (when game exists - not required for new Q1 start)
  - `quarter` - Current quarter number
  - `score` - Current scores (home/away)
  - `time_remaining` - Time remaining in seconds
- **Game Mode State (if Tournament/Franchise):**
  - `tournament_id` / `franchise_id` - Game mode document identifier
  - `team_id` - User's team anchor (same as Navigation Anchor Set)
- **Timeout State (if resuming from timeout/foul out):**
  - `timeout_next_play_type` - "SIDE_INBOUND" or "FREE_THROW" (from database)
  - `timeout_offense_team_id` - Team that had possession (from database)
  - `resume_from_timeout` - Boolean flag (URL param)
  - `clock` - Game clock at timeout (URL param)
- **Lineup State:**
  - `home_lineup` / `away_lineup` - Current lineups (player IDs by position, URL params: `{side}_{position}`)
    -**Note:** fouled out players will be removed from the current lineup at the start of player foul out instances. If the foul out player is on the user's team, he will be removed from the active lineup display upon Lineup Screen page download
  - `my_team` - User's team side ("home" or "away")
- **Game Plan State:**
  - `strategy_settings` - Current strategy settings (loaded from team object in database)
  - `playbook_settings` - Current playbook settings (loaded from team object in database)
    - **Note:** The 6 Playcall Center preset plays are stored in `playbook_settings.slot_assignments` (slots 1-6)
    - **Legacy Note:** `playcall_settings` is a legacy term - the current system uses `playbook_settings` which includes `slot_assignments` for the Playcall Center

**Optional:**
- Additional game state not required for core functionality

**Note:** `game_plan_settings` is NOT a URL parameter - it's loaded via API (`/api/gameplan`) in `bootGame.js` and sent to backend. It's not part of State Data.

### Context Data
**Required:**
- `game_id` - Game identifier (URL param, same as Navigation Anchor Set)
- `mode` - Game mode type (URL param, same as Navigation Anchor Set)
- `my_team` - User's team side ("home" or "away", URL param)
- `team_id` - User's team ObjectId (URL param, same as Navigation Anchor Set)

**Conditionally Required:**
- `tournament_id` - If `mode === "tournament"` (URL param, same as Navigation Anchor Set)
- `franchise_id` - If `mode === "franchise"` (URL param, same as Navigation Anchor Set)
- `resume_from_timeout` - If resuming from timeout/foul out (URL param, boolean flag)
- `clock` - If resuming from timeout/foul out (URL param, game clock time)
- `quarter` - If `quarter > 1` OR `resume_from_timeout === true` (URL param)

**Optional:**
- `from` - Source page (for back navigation logic, e.g., "command_center", "lineup")
- `home` / `away` - Team names (for display/validation)
- `home_id` / `away_id` - Team ObjectIds (for gameplan API compatibility)

**Note:** "Conditionally Required" means the parameter is required only in specific scenarios (e.g., `tournament_id` only when `mode === "tournament"`). "Optional" means the parameter is never required but may be useful for specific operations.

### Validation Rules

Validation Rules define how data is validated on page entry. They specify when data is required, how to handle missing data, and what backend validation occurs.

- **Game ID Logic (Strict):**
  - **When Required:** `quarter > 1` OR `resume_from_timeout === true`
  - **When NOT Required:** New Q1 game start (game hasn't been created yet)
  - **Why:** For new Q1 games, the game document doesn't exist yet, so `game_id` can't be validated. For Q1+ or timeout resume, the game exists and `game_id` is required.
  - **Validation:** Must exist in database if required

- **Resume From Timeout (Conditional Validation):**
  - **When Validated:** Only when `resume_from_timeout=true` in URL
  - **Must Have (Frontend):** `game_id`, `clock`, `quarter` (URL params)
  - **Must Have (Backend):** `timeout_next_play_type`, `timeout_offense_team_id` (from database)
  - **Backend Validation:** Database must have `timeout_next_play_type` for that quarter
  - **Difference:** "Must Have" = frontend must pass these URL params. "Backend validates" = backend checks database for consistency.
  - **Lightweight Fallback:** If `game_id` exists and `quarter === 1`, do lightweight check (catches lost URL param)

- **Quarter Breaks (Strict):**
  - **Required:** `game_id` (when `quarter > 1`)
  - **NOT Required:** `resume_from_timeout` (quarter breaks are not timeouts, so this flag should NOT be set)

- **Mode + Doc ID (Strict):**
  - **Tournament:** Must have `tournament_id` + `game_id` (both in Navigation Anchor Set)
  - **Franchise:** Must have `franchise_id` + `game_id` (both in Navigation Anchor Set)
  - **Single:** Only `game_id` needed (no game mode document)
  - **Note:** This validates the Navigation Anchor Set requirements based on mode

- **Team ID (Non-Strict with Fallback):**
  - **Primary:** URL param `team_id` (ObjectId format)
  - **Fallback:** Resolve from database using `tournament_id`/`franchise_id` (check `user_team_object_id` field)
  - **Only fail if all fallbacks fail:** This allows graceful recovery if URL param is missing
  - **Why Non-Strict:** Team ID is important but not critical for navigation - we can recover from database if URL param is lost

### Persistence Strategy
- **URL Params:**
  - Always: 
    - `mode` - Game mode type ("single", "tournament", or "franchise")
    - `team_id` - User's team ObjectId (identifies WHICH team)
    - `my_team` - User's team side ("home" or "away") (identifies WHICH SIDE the user's team is on in the current game)
    - `tournament_id` - If `mode === "tournament"` (part of Navigation Anchor Set)
    - `franchise_id` - If `mode === "franchise"` (part of Navigation Anchor Set)
  - Conditionally: 
    - `game_id` (if `quarter > 1` OR `resume_from_timeout === true`)
    - `resume_from_timeout` (if resuming from timeout/foul out)
    - `clock` (if resuming from timeout/foul out)
    - `quarter` (if `quarter > 1` OR `resume_from_timeout === true`)
  - Lineup: `{side}_{position}` (e.g., `home_pg`, `away_sg`)
- **Database:**
  - Game document (single source of truth for game state)
  - Timeout state (if applicable): `timeout_next_play_type`, `timeout_offense_team_id` (stored in game document)
  - Game mode document (if Tournament/Franchise) - contains team objects with `strategy_settings` and `playbook_settings`
    - **Note:** Legacy `playcall_settings` has been replaced by `playbook_settings` (which includes `slot_assignments` for Playcall Center)
- **LocalStorage:**
  - Optional: `game_id` (for fallback, but database is source of truth)
  - NOT used for: Timeout state, game state (database is source of truth)

### Transition Patterns
- **To Bucket 1 (GA):** 
  - Clear all game and game mode context (remove `game_id`, `mode`, `doc_id`, `team_id` from URL)
  - **Preserve:** `user_id` (required for GA instance)
  - **Special Cases:**
    - **Mid-Game Transition:** If transitioning mid-game (user exits before game completion), preserve game state in database for potential return (game document remains in database)
    - **Post-Game Transition:** If transitioning after game completion but before returning to GMO, ensure EOG (End of Game) logic/data that typically occurs in GP → GMO transition is handled appropriately (stat rollup, game completion flags, etc.)
- **To Bucket 2 (GMO):** 
  - Clear game context (`game_id` and all gameplay-specific params)
  - **Preserve:** Navigation Anchor Set (`mode`, `doc_id` (tournament_id/franchise_id), `team_id`), `user_id`
  - **Data Updates (Backend):**
    - Increment Season and Career stats for players, teams, and plays
    - Clear all game stats for players, teams, and plays to zero (reset for next game)
    - Update game mode document with final game results
- **To Bucket 4 (NA):** 
  - Clear all game, game mode, and account data (including `user_id`)
  - **Special Cases:**
    - **Mid-Game Transition:** If transitioning mid-game (user exits before game completion), preserve game state in database for potential return (game document remains in database)
    - **Post-Game Transition:** If transitioning after game completion but before returning to GMO, ensure EOG (End of Game) logic/data that typically occurs in GP → GMO transition is handled appropriately (stat rollup, game completion flags, etc.)

### Special Cases
- **Timeout Resume:**
  - **Must Preserve (URL Params):** `game_id`, `resume_from_timeout`, `clock`, `quarter`, `team_id`, `mode`, `doc_id`
  - **Must Have (Database):** `timeout_next_play_type`, `timeout_offense_team_id` (stored in game document)
  - **Backend Validates:** Database must have timeout state (`timeout_next_play_type`, `timeout_offense_team_id`) for that quarter
  - **Frontend:** Uses first turn's clock if timeout resume detected
  - **Note:** `timeout_offense_team_id` is required - it identifies which team had possession when timeout was called
- **Foul Out:**
  - Same as timeout resume (all requirements above)
  - **Additional:** Must remove fouled-out player from lineup
- **Quarter Breaks:**
  - **Must Preserve:** `game_id`, `quarter`, `team_id`, `mode`, `doc_id`
  - **NOT Timeout:** `resume_from_timeout` should NOT be set (quarter breaks are not timeouts)
- **Game Completion:**
  - **Navigation Flow:**
    - Immediately upon game completion: EOG (End of Game) popup appears
    - User can visit Box Score screen before navigating back to FCC/TCC (GMO) or Mode Select (Single Game mode)
    - Final navigation: Back to command center (FCC/TCC) with complete anchor set, or to Mode Select for Single Game mode
  - **Must Preserve:** Navigation Anchor Set (`game_id`, `mode`, `tournament_id`/`franchise_id`, `team_id`)
  - **Stat Rollup Requirements (Transition Data):**
    - **Tournament Mode:** `game_id` must be passed to `save_result()` endpoint
    - **Franchise Mode:** `game_id` must be passed to `complete_week()` endpoint
    - **Note:** `save_result()` and `complete_week()` serve similar purposes but are mode-specific:
      - Tournament: Handles round-based bracket structure and round advancement
      - Franchise: Handles week-based schedule and weekly progression
    - `finalize_game()` is called **within** `save_result()` (Tournament) or `complete_week()` (Franchise)
    - `finalize_game()` is called for **both user games AND computer games** (all games in the round/week)
    - `finalize_game()` must be called with `game_id`, `mode`, and `franchise_id`/`tournament_id`
    - **Race Condition Prevention (Franchise Mode):**
      - When Q4/OT ends with a winner (`is_final=True`), `simulate-quarter` endpoint returns `final_game_document` in response
      - Frontend passes `final_game_document` to `complete_week()` endpoint as `game_document` parameter
      - `complete_week()` uses `game_document` directly if provided (eliminates race condition where database lookup happens before Q4 save completes)
      - Falls back to database lookup if `game_document` not provided (backward compatibility)
      - **Works for:** Q4 (not tied) and any OT that ends with a winner
      - **Benefits:** Ensures complete `box_score` is available immediately, no waiting for database save to complete
    - Game document must have complete `box_score` (all 12 players per team) before `finalize_game()` is called
    - Stats are rolled up into `franchise.players.{pid}.season` and `franchise.players.{pid}.career` (or `tournament.players` for Tournament mode)
    - **FCC Endpoints:** (`/franchise/team-stats`, `/franchise/team-player-stats`, `/franchise/roster`) read from `franchise.players` object
    - **TCC Endpoints:** (`/tournament/team-stats`, `/tournament/team-data`, `/tournament/roster`) read from `tournament.players` object
    - **Note:** Navigation parameters alone are sufficient for FCC/TCC to retrieve stats, but stat rollup must complete successfully for stats to be available

---

## Bucket 4: Non-Account (NA)

**Definition:** User either doesn't have an account or is logged out of their account.

**Examples:**
- Homepage (homepage.html)
- Account Creation screen (TBD)
- Account Login screen (TBD)
- Each Team's General Roster Page (from universal players collection)

### Navigation Anchor Set
**Required:** None
- No account context
- No game mode context
- No team context

### State Data
**Required:** None
- No persistent state
- No game data

### Context Data
**Optional:**
- `guest_session_id` - Guest session identifier (if using guest mode)
- `return_url` - URL to return to after login (for post-login redirect)

### Validation Rules
- No validation needed (no account context)
- All data is optional

### Persistence Strategy
- **URL Params:** 
  - Optional: `return_url` (for post-login redirect)
- **Database:** 
  - None (no account, no persistent data)
- **LocalStorage:** 
  - Optional: Guest preferences (if using guest mode)
  - NOT used for: Account data, game data

### Transition Patterns
- **To Bucket 1 (GA):** After login/account creation, redirect to Mode Select (no data needed)
- **To Bucket 2 (GMO):** **NOT ALLOWED** - Must login/create account first, then go through Mode Select
- **To Bucket 3 (GP):** **NOT ALLOWED** - Must login/create account first, then go through Mode Select

### Special Cases
- **Post-Login Redirect:**
  - Preserve `return_url` to redirect user after successful login
  - Clear `return_url` after redirect
- **Each Team's General Roster Page:**
  - No account required
  - Displays players from universal players collection
  - Links back to Mode Select

---

## Cross-Bucket Data Flow Rules

### General Principles
1. **Database is Source of Truth:** Game state, timeout state, and game mode state always come from database
2. **URL Params for Navigation:** URL parameters are for navigation/routing, not business logic
3. **ObjectId Standardization:** Always use ObjectId strings (not team names) for `team_id`
4. **Complete Anchor Set:** Always preserve complete navigation anchor set for the target bucket:
   - **Bucket 1 (GA):** `user_id` only
   - **Bucket 2 (GMO):** `mode`, `doc_id` (tournament_id/franchise_id), `team_id`
   - **Bucket 3 (GP):** `mode`, `doc_id` (tournament_id/franchise_id + game_id), `team_id`
   - **Bucket 4 (NA):** None (no anchor set)
   - **Note:** `user_id` should always be maintained during transitions (even when not in Navigation Anchor Set) for authorization/logging purposes
5. **Cross-Bucket Transition Rules:**
   - **Direct Transitions Allowed:**
     - GP → GMO (game completion - returns to command center)
     - GP → GA (exit game - returns to mode select)
     - GP → NA (logout - clears all data)
     - GMO → GP (start game - initializes game document)
     - GA → GMO (start game mode - initializes game mode document)
     - GA → GP (start game - initializes game and game mode documents)
   - **Mode Select Required:**
     - GMO → GMO (different mode) - Cannot switch from Tournament to Franchise (or vice versa) without Mode Select
     - NA → GMO/GP - Must login/create account first, then go through Mode Select
   - **Rationale:** Direct transitions are allowed when they maintain or clear context appropriately. Mode Select is required when switching between different game modes to ensure proper initialization and prevent data conflicts.

### Data Validation on Transition
- **Validate on Entry:** Each page validates required data on load
- **Hybrid Validation with Fallbacks:**
  - **Mode (Critical with Fallback):** 
    - Primary: URL param `mode`
    - Fallback: Detect from `tournament_id` → 'tournament', `franchise_id` → 'franchise', else 'single'
    - Only fail if cannot be determined
  - **Doc ID (Critical with Fallback):**
    - Primary: URL param `tournament_id` or `franchise_id`
    - Fallback: localStorage (for franchise_id)
    - Only fail if cannot be determined
  - **Game ID (Conditional with Fallback):**
    - Required when: `quarter > 1` OR `resume_from_timeout === true`
    - Primary: URL param `game_id`
    - Fallback: localStorage (for single mode)
    - Only fail if required but cannot be determined
  - **Team ID (Non-Strict with Multiple Fallbacks):**
    - Primary: URL param `team_id` (ObjectId format)
    - Fallback 1: `user_team_id` URL param
    - Fallback 2: `home_id` or `away_id` URL params (based on `my_team`)
    - Fallback 3: Resolve from database using `tournament_id`/`franchise_id` (check `user_team_object_id` field)
    - Only fail if all fallbacks fail
  - **Context Data (Optional with Fallbacks):** View Team ID, From parameter - use fallback chains
- **Fallback Chain Priority:** URL params → localStorage → database lookup → defaults
- **Error Handling:** 
  - Critical data missing after all fallbacks: Log warning/error, attempt graceful degradation
  - Context data missing: Attempt recovery via fallback chain, only fail if all fallbacks fail
  - **Note:** Current implementation prioritizes graceful recovery over strict fail-fast validation

### Testing Requirements
- **Transition Tests:** Test all transitions between buckets
- **Data Persistence Tests:** Verify data persists correctly across transitions
- **Edge Case Tests:** Test timeout resume, foul out, quarter breaks, game completion
- **Mode-Specific Tests:** Test Single Game, Tournament, and Franchise modes separately

---

## Team ID Navigation Pattern (SS&S) - Implementation Reference

> **Status:** ✅ Implemented  
> **Last Verified:** February 2025  
> **Purpose:** Implementation patterns and code examples for developers

### Quick Reference

- **`team_id`** (ObjectId string) = User's team anchor in URLs/navigation
- **`user_team_object_id`** = Database field name (same value, different name)
- **Mapping:** When reading from database → use `user_team_object_id` as `team_id` in URLs. When writing to database → use `team_id` as `user_team_object_id` in storage.

**Note:** For conceptual details, see the "Team ID Navigation Pattern" notes in Bucket 2 (GMO) and Bucket 3 (GP) sections above.

### Implementation Pattern

#### Frontend: Command Center Entry

**Franchise Mode:**
```javascript
// 1. Check URL params first (for navigation from other pages)
const urlParams = new URLSearchParams(window.location.search);
const urlTeamId = urlParams.get('team_id');
if (urlTeamId) {
  userTeamId = urlTeamId;
  localStorage.setItem('franchise_user_team_id', userTeamId);
} else {
  // 2. Fallback to localStorage
  userTeamId = localStorage.getItem('franchise_user_team_id');
}

// 3. Load command center data (includes team_id)
const topData = await fetchJSON(`/franchise/command-center/data?franchise_id=${franchiseId}`);
if (topData && topData.team_id && !userTeamId) {
  // 4. Resolve from command center data if not already set
  userTeamId = topData.team_id;
  localStorage.setItem('franchise_user_team_id', userTeamId);
}
```

**Tournament Mode:**
```javascript
// 1. Check URL params first (for navigation from other pages)
const urlParams = new URLSearchParams(window.location.search);
const urlTeamId = urlParams.get('team_id');
if (urlTeamId) {
  userTeamId = urlTeamId;
  localStorage.setItem('userTeamId', userTeamId);
} else {
  // 2. Fallback to localStorage
  userTeamId = localStorage.getItem('userTeamId') || '';
}

// 3. Load command center data (includes team_id)
const commandCenterData = await fetch(`/tournament/command-center/data?tournament_id=${tournamentId}`);
if (commandCenterData && commandCenterData.team_id && !userTeamId) {
  // 4. Resolve from command center data if not already set
  userTeamId = commandCenterData.team_id;
  localStorage.setItem('userTeamId', userTeamId);
}
```

#### Frontend: Navigation URLs

**All navigation URLs include `team_id` (ObjectId) with URL encoding:**

```javascript
// Franchise Mode Examples:

// Command Center → Game Plan
const url = `/game-plan.html?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}&team_id=${encodeURIComponent(userTeamId)}&from=command_center`;

// Game Plan → Command Center
const url = `/static/franchise-command-center.html?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}&team_id=${encodeURIComponent(userTeamId)}`;

// Command Center → Training
const url = `/static/training.html?franchise_id=${encodeURIComponent(franchiseId)}&mode=franchise&team_id=${encodeURIComponent(userTeamId)}`;

// Training Report → Command Center
const url = `/static/franchise-command-center.html?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}&team_id=${encodeURIComponent(teamId)}`;

// Tournament Mode Examples:

// Command Center → Training
const url = `/static/training.html?mode=tournament&tournament_id=${encodeURIComponent(tournamentId)}&team_id=${encodeURIComponent(userTeamId)}&round=${round}`;

// Training Report → Command Center
const url = `/static/tournament.html?tournament_id=${encodeURIComponent(tournamentId)}&team_id=${encodeURIComponent(teamId)}`;
```

#### Backend: Endpoint Pattern

**All endpoints prefer `team_id` (ObjectId), with backward compatibility:**

```python
@router.get("/franchise/team-data")
def get_franchise_team_data(franchise_id: str, team_id: str = None, team_name: str = None):
    """
    ✅ SS&S: Prefers team_id (ObjectId) for consistent navigation.
    Falls back to team_name resolution for backward compatibility.
    """
    # ✅ SS&S: Prefer team_id (ObjectId) if provided
    if team_id:
        try:
            # Validate it's a valid ObjectId
            ObjectId(team_id)
            actual_team_id = team_id
        except Exception:
            # If not a valid ObjectId, try to resolve as team name
            team_doc = db.teams.find_one({"name": team_id})
            if not team_doc:
                raise HTTPException(status_code=404, detail=f"Team not found: {team_id}")
            actual_team_id = str(team_doc["_id"])
    elif team_name:
        # Fallback to team_name resolution for backward compatibility
        team_doc = db.teams.find_one({"name": team_name})
        if not team_doc:
            raise HTTPException(status_code=404, detail="Team not found")
        actual_team_id = str(team_doc["_id"])
    else:
        # Final fallback: Get from franchise document
        franchise_doc = db.franchises.find_one({"_id": ObjectId(franchise_id)})
        user_team_id, user_team_object_id = get_user_team_from_franchise(franchise_doc)
        actual_team_id = user_team_object_id
    
    # Use actual_team_id directly as database key
    franchise_teams = franchise_doc.get("franchise_teams", {})
    team_obj = franchise_teams.get(actual_team_id, {})
```

### Roster Viewing Pattern

When implementing functionality to view computer team rosters, use separate parameters:

**Pattern:**
- **`team_id`** = User's team (ObjectId) - for navigation context and back navigation
- **`team_name`** = Team being viewed (display name) - for API calls and display
- **`returnUrl`** or **`returnTab`** = For back navigation to command center

**Example Navigation:**
```javascript
// Command Center → View Opponent Roster
function viewOpponentRoster(opponentTeamName) {
  const userTeamId = getTeamId(); // User's team ObjectId
  const url = `/static/team-roster-view.html?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}&team_id=${encodeURIComponent(userTeamId)}&team_name=${encodeURIComponent(opponentTeamName)}&return_tab=standings-tab`;
  window.location.href = url;
}

// Roster View → Back to Command Center
function backToCommandCenter() {
  const urlParams = new URLSearchParams(window.location.search);
  const returnUrl = urlParams.get('return_url');
  if (returnUrl) {
    window.location.href = returnUrl;
  } else {
    // Build return URL from params
    const franchiseId = urlParams.get('franchise_id');
    const userTeamId = urlParams.get('team_id'); // User's team
    const returnTab = urlParams.get('return_tab');
    let returnPath = `/static/franchise-command-center.html?franchise_id=${encodeURIComponent(franchiseId)}&team_id=${encodeURIComponent(userTeamId)}`;
    if (returnTab) {
      returnPath += `&tab=${returnTab}`;
    }
    window.location.href = returnPath;
  }
}
```

**Backend Endpoint Pattern:**
```python
@router.get("/franchise/roster")
def get_franchise_roster(franchise_id: str, team_name: str):
    """
    Returns roster data for the specified team (by team name).
    Team name is used for API calls, not ObjectId, for consistency with display.
    """
    # Backend resolves team_name to ObjectId internally
    # Returns roster data for the specified team
```

### Game Completion Navigation

When a game completes, the completion popup must preserve the complete navigation anchor set:

**Pattern:**
```javascript
// Game Scene → Completion Popup (Primary Flow)
showGameCompletionPopup({
  gameId: gameId,
  mode: mode,
  tournamentId: this.tournamentId,  // doc_id for tournament mode
  franchiseId: this.franchiseId,    // doc_id for franchise mode
  teamId: this.teamId,              // team_id (ObjectId) - navigation anchor
  finalScore: finalScore,
  homeTeam: homeTeam,
  awayTeam: awayTeam
});

// Completion Popup → Command Center URL Construction
case 'tournament':
  lockerRoomUrl = '/static/tournament.html';
  const tournamentParams = new URLSearchParams();
  if (tournamentId) tournamentParams.set('tournament_id', tournamentId);
  if (teamId) tournamentParams.set('team_id', teamId);  // ✅ Preserve navigation anchor
  if (tournamentParams.toString()) {
    lockerRoomUrl += `?${tournamentParams.toString()}`;
  }
  break;

case 'franchise':
  lockerRoomUrl = '/static/franchise-command-center.html';
  const franchiseParams = new URLSearchParams();
  if (franchiseId) franchiseParams.set('franchise_id', franchiseId);
  if (teamId) franchiseParams.set('team_id', teamId);  // ✅ Preserve navigation anchor
  if (franchiseParams.toString()) {
    lockerRoomUrl += `?${franchiseParams.toString()}`;
  }
  break;
```

**Benefits:**
- **Complete Context:** All three navigation parameters (mode, doc_id, team_id) preserved
- **Seamless Flow:** User returns to command center with full context intact
- **Box Score Navigation:** Box Score URL also includes complete navigation anchor for proper back navigation

**Implementation Details:**
- `gameScene.js` stores `teamId` from scene data and passes it explicitly to completion popup
- `bootGame.js` doesn't pass `teamId` but popup has fallback to read from URL params (`team_id`, `home_id`, or `away_id`)
- `gameCompletionPopup.js` constructs both locker room and box score URLs with complete navigation anchor set
- Box Score URL includes `mode`, `tournament_id`/`franchise_id`, and `team_id` for proper navigation back to command center

### Key Implementation Files

**Frontend:**
- `FrontEnd/static/franchise-command-center.js` - Resolves and stores ObjectId, updates all navigation
- `FrontEnd/static/tournament.js` - Resolves and stores ObjectId, updates all navigation
- `FrontEnd/static/js/phaser/utils/gameCompletionPopup.js` - Constructs URLs with complete navigation anchor

**Backend:**
- `BackEnd/api/franchise_routes.py` - `/franchise/command-center/data` returns `team_id`, `/franchise/team-data` accepts `team_id`
- `BackEnd/api/tournament_routes.py` - `/tournament/command-center/data` returns `team_id`, `/tournament/team-data` accepts `team_id`

---

## Game Plan & Playbooks Persistence Rules

> **Note:** This section documents how navigation affects data persistence. For complete persistence rules, see `docs/user-flow.md`.

### Single Game Mode (Bucket 3 - GP)
- **During Game:** User settings from Lineup Select Experience persist across entire current game instance (Lineup → Game Plan → Playbooks → Gameplay)
- **Across Games:** User settings per team persist by team across Single Game instances
  - Example: If user finishes a game as Lancaster, next time they play as Lancaster, settings from previous Lancaster game persist
  - If they play as Morristown next, settings from last Morristown game persist
  - First game as a team: Use default settings

### Tournament and Franchise Modes (Bucket 2 - GMO & Bucket 3 - GP)
- **Across All Instances:** User settings from accessing Game Plan and Playbooks (from Command Center OR Lineup Select Experience) persist across all instances until changed
- **Persistence Scope:** Settings persist into:
  - Training screen
  - Lineup Select Experience
  - Gameplay instances
  - Non-gameplay instances (Command Center, Scouting Report, Play Pages, Training Report, Box Score screens, Team Roster pages, etc)

### Default Settings
- **Game Plan:** All settings = 2
- **Playbooks:** Equal distribution among number of plays available in each section
  - Motion Offense
  - Set Play Inside
  - Set Play Attack
  - Set Play Outside
  - Man Defense
  - Zone Defense
- **Playcall Center Plays:**
  1. 3-2 Motion (Inside)
  2. 4-1 Motion (Attack)
  3. 5-0 Motion (Outside)
  4. Base Post Play
  5. Pick & Roll (Lower Wing)
  6. Double Screen for SG
