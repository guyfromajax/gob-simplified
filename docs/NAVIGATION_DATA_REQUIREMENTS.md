# Navigation Data Requirements by Experience Bucket

> **Last Updated:** January 2025  
> **Status:** Draft - Aligned with user-flow.md

This document defines the data requirements for all page-to-page transitions across the game experience, organized by experience bucket. Aligned with the user-flow.md structure.

**Instance Type Mapping:**
- **NA (Non-Account)** = Bucket 4
- **GA (General Account)** = Bucket 1
- **GMO (Game Mode Only)** = Bucket 2
- **GP (Gameplay)** = Bucket 3

---

## Bucket 1: General Account (GA) - Non Game Mode

**Definition:** User is logged into their account but not in a specific game mode instance (outside of Single Game, Tournament Mode, or Franchise Mode instance).

**Examples:**
- Mode selection screen (mode-select.html)
- Settings/Account pages (TBD)
- Help/Documentation pages (TBD)

### Navigation Anchor Set
**Required:** None
- No game mode document to anchor to
- No team context needed

### State Data
**Required:** None
- No game state to preserve
- No gameplay data

### Context Data
**Optional:**
- `user_id` - User account identifier (if logged in)
- `session_id` - Session identifier (if using sessions)
- `last_visited` - Last page visited (for back navigation)

### Validation Rules
- No validation needed (no game mode context)
- All data is optional

### Persistence Strategy
- **URL Params:** None required
- **Database:** None required
- **LocalStorage:** Optional (user preferences, last visited page)
- **Session:** Optional (session state if using sessions)

### Transition Patterns
- **To Bucket 1 (GA):** No data needed
- **To Bucket 2 (GMO):** Must initialize game mode document (tournament_id or franchise_id) + team_id
- **To Bucket 3 (GP):** Must initialize game mode document AND game document (game_id) + team_id
- **To Bucket 4 (NA):** Clear all account-related data
- **Note:** All transitions to other buckets MUST go through Mode Select screen (no direct cross-bucket transitions)

---

## Bucket 2: Game Mode Only (GMO) - Non-Gameplay Instance

**Definition:** User is in a Tournament Mode or Franchise Mode instance, but not actively playing a game.

**Sub-categories:**
- **2A: Tournament Mode** (tournament command center, training, playbooks, game plan)
- **2B: Franchise Mode** (franchise command center, training, playbooks, game plan)

**Examples:**
- Tournament/Franchise Command Center
- Training screen (before/after gameplay)
- Training Report
- Playbooks screen
- Game Plan screen
- Team Roster screen
- Standings/Stats screens

### Navigation Anchor Set
**Required:**
- **Mode:** `"tournament"` or `"franchise"` (determines which collection/endpoints)
- **Doc ID:** `tournament_id` (Tournament) or `franchise_id` (Franchise)
- **Team ID:** `team_id` (ObjectId string) - User's team anchor

**Validation:**
- All three parameters must be present for seamless navigation
- `team_id` must be ObjectId format (not team name)

### State Data
**Required:**
- **Game Mode State:**
  - Tournament: `tournament.completed`, `tournament.current_round`, `tournament.training_status`
  - Franchise: `franchise.week`, `franchise.season`, `franchise.training_status`
- **Team State:**
  - Team attributes (from `tournament.teams.{team_id}` or `franchise.franchise_teams.{team_id}`)
  - Strategy settings (from team object)
  - Playbook settings (from team object)

**Optional:**
- Training history (for training report)
- Player attributes (if viewing roster)
- View context (if viewing opponent/other team data)

### Context Data
**Required:**
- `user_team_id` - User's team ObjectId (for navigation anchor)
- `mode` - Game mode type

**Optional:**
- `view_team_id` - Team being viewed (if viewing opponent/other team) - **Display context only, not part of navigation anchor**
- `from` - Source page (for back navigation logic, e.g., "command_center", "lineup")
- `round` - Tournament round (for training report)
- `week` - Franchise week (for navigation context)

### Validation Rules
- **Mode + Doc ID (Strict):** Must be valid and match (tournament_id for tournament mode, franchise_id for franchise mode)
- **Team ID (Non-Strict with Fallback):** 
  - Primary: URL param `team_id` (ObjectId format)
  - Fallback 1: Resolve from database using tournament_id/franchise_id
  - Fallback 2: Use default team from game mode document
  - Only fail if all fallbacks fail
- **View Team ID (Optional):** If provided, must be valid ObjectId (for viewing other teams)

### Persistence Strategy
- **URL Params:** 
  - Always: `mode`, `{mode}_id` (tournament_id or franchise_id), `team_id`
  - Conditionally: `view_team_id`, `from`, `round`, `week`
- **Database:** 
  - Game mode document (tournament or franchise)
  - Team objects within game mode document
- **LocalStorage:** 
  - Optional: Last visited page, user preferences
  - Not used for game state (database is source of truth)

### Transition Patterns
- **To Bucket 1 (GA):** Clear game mode context (remove mode, doc_id, team_id from URL) - **Must go through Mode Select**
- **To Bucket 2 (GMO - same mode):** Preserve all navigation anchor set (mode, doc_id, team_id)
- **To Bucket 2 (GMO - different mode):** **NOT ALLOWED** - Must go through Mode Select first
- **To Bucket 3 (GP):** Must initialize game document (game_id) in addition to game mode context
- **To Bucket 4 (NA):** Clear all game mode and account data - **Must go through Mode Select/Logout**

### Special Cases
- **Training Report:** Requires `round` parameter (or backend determines from tournament state)
- **Game Plan:** Requires `from` parameter to determine back navigation
  - **Known Bug:** When navigating TCC → Game Plan → Playbooks → Game Plan, the `from` parameter is lost, causing "Back to Lineup" instead of "Back to Locker Room"
  - **Fix Required:** Preserve `from` parameter through Playbooks navigation
- **Viewing Other Teams:** Requires `view_team_id` (display context only) while preserving `team_id` (user's team for navigation)
- **Playbooks Navigation:** Must preserve `from` parameter when navigating Game Plan ↔ Playbooks

---

## Bucket 3: Game Mode Instance / Gameplay Instance

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
- Box Score screen (after game)
- Timeout/Foul Out popup → Lineup screen

### Navigation Anchor Set
**Required:**
- **Mode:** `"single"`, `"tournament"`, or `"franchise"`
- **Doc ID:** 
  - Single: `game_id` only
  - Tournament: `tournament_id` + `game_id`
  - Franchise: `franchise_id` + `game_id`
- **Team ID:** `team_id` (ObjectId string) - User's team anchor

**Validation:**
- All required parameters must be present
- `game_id` must exist in database
- For Tournament/Franchise: game must be nested in correct document

### State Data
**Required:**
- **Game State:**
  - `game_id` - Current game identifier
  - `quarter` - Current quarter number
  - `clock` - Current game clock (for timeout resume)
  - `score` - Current scores (home/away)
  - `time_remaining` - Time remaining in seconds
- **Game Mode State (if Tournament/Franchise):**
  - Same as Bucket 2 (tournament_id/franchise_id, team_id)
- **Timeout State (if resuming from timeout):**
  - `timeout_next_play_type` - "SIDE_INBOUND" or "FREE_THROW"
  - `timeout_offense_team_id` - Team that had possession
  - `resume_from_timeout` - Boolean flag (URL param)
- **Lineup State:**
  - `home_lineup` / `away_lineup` - Current lineups (player IDs by position)
  - `my_team` - User's team side ("home" or "away")
- **Game Plan State:**
  - `strategy_settings` - Current strategy settings
  - `playcall_settings` - Current playcall settings

**Optional:**
- `resume_from_timeout` - Flag for timeout resume
- `clock` - Game clock (for timeout resume)
- `game_plan_settings` - Serialized game plan (for pre-population)

### Context Data
**Required:**
- `game_id` - Game identifier
- `mode` - Game mode type
- `my_team` - User's team side ("home" or "away")
- `team_id` - User's team ObjectId

**Conditionally Required:**
- `tournament_id` - If mode is "tournament"
- `franchise_id` - If mode is "franchise"
- `resume_from_timeout` - If resuming from timeout/foul out
- `clock` - If resuming from timeout/foul out
- `quarter` - If quarter > 1 or resuming from timeout

**Optional:**
- `from` - Source page (for back navigation)
- `home` / `away` - Team names (for display/validation)
- `home_id` / `away_id` - Team ObjectIds (for gameplan API compatibility)

### Validation Rules
- **Game ID Logic (Strict):**
  - Required if: `quarter > 1` OR `resume_from_timeout === true`
  - NOT required for: New Q1 game start
  - Must exist in database
- **Resume From Timeout (Conditional Validation):**
  - Only validate when `resume_from_timeout=true` in URL
  - Must have: `game_id`, `clock`, `quarter`
  - Backend validates: Database must have `timeout_next_play_type` for that quarter
  - **Lightweight Fallback:** If `game_id` exists and `quarter === 1`, do lightweight check (catches lost URL param)
- **Quarter Breaks (Strict):**
  - Required: `game_id` (quarter > 1)
  - NOT required: `resume_from_timeout` (quarter breaks are not timeouts)
- **Mode + Doc ID (Strict):**
  - Tournament: Must have `tournament_id` + `game_id`
  - Franchise: Must have `franchise_id` + `game_id`
  - Single: Only `game_id` needed
- **Team ID (Non-Strict with Fallback):**
  - Primary: URL param `team_id`
  - Fallback: Resolve from database
  - Only fail if all fallbacks fail

### Persistence Strategy
- **URL Params:**
  - Always: `mode`, `game_id` (if applicable), `team_id`, `my_team`
  - Conditionally: `tournament_id`, `franchise_id`, `resume_from_timeout`, `clock`, `quarter`
  - Lineup: `{side}_{position}` (e.g., `home_pg`, `away_sg`)
- **Database:**
  - Game document (single source of truth for game state)
  - Timeout state (if applicable): `timeout_next_play_type`, `timeout_offense_team_id`
  - Game mode document (if Tournament/Franchise)
- **LocalStorage:**
  - Optional: `game_id` (for fallback, but database is source of truth)
  - NOT used for: Timeout state, game state (database is source of truth)

### Transition Patterns
- **To Bucket 1 (GA):** Clear all game and game mode context - **Must go through Mode Select**
- **To Bucket 2 (GMO):** Clear game context (`game_id`), preserve game mode context (mode, doc_id, team_id)
- **To Bucket 3 (GP - same game):** Preserve all navigation anchor set + game state
- **To Bucket 3 (GP - new game):** Initialize new game document, preserve game mode context (if applicable)
- **To Bucket 4 (NA):** Clear all game, game mode, and account data - **Must go through Mode Select/Logout**

### Special Cases
- **Timeout Resume:**
  - Must preserve: `game_id`, `resume_from_timeout`, `clock`, `quarter`, `team_id`
  - Backend validates: Database must have timeout state for that quarter
  - Frontend: Uses first turn's clock if timeout resume detected
- **Foul Out:**
  - Same as timeout resume
  - Additional: Must remove fouled-out player from lineup
- **Quarter Breaks:**
  - Must preserve: `game_id`, `quarter`, `team_id`
  - NOT timeout: `resume_from_timeout` should NOT be set
- **Game Completion:**
  - Must preserve: `game_id`, `mode`, `tournament_id`/`franchise_id`, `team_id`
  - Navigation: Back to command center with complete anchor set

---

## Bucket 4: Non-Account (NA) Instances

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
- **To Bucket 4 (NA):** Clear all account-related data (logout)

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
4. **Complete Anchor Set:** Always preserve complete navigation anchor set (mode, doc_id, team_id)
5. **No Direct Cross-Bucket Transitions:** All transitions between buckets MUST go through Mode Select screen

### Data Validation on Transition
- **Validate on Entry:** Each page validates required data on load
- **Hybrid Validation:**
  - **Strict (Critical Data):** Mode, Doc ID, Game ID (when required) - fail fast if missing
  - **Non-Strict (Context Data):** Team ID, View Team ID, From parameter - use fallback chains
- **Fallback Chains:** Use fallback chains for context data (URL → localStorage → database → defaults)
- **Error Handling:** 
  - Critical data missing: Redirect to Mode Select with error message
  - Context data missing: Attempt recovery via fallback chain, only fail if all fallbacks fail

### Testing Requirements
- **Transition Tests:** Test all transitions between buckets
- **Data Persistence Tests:** Verify data persists correctly across transitions
- **Edge Case Tests:** Test timeout resume, foul out, quarter breaks, game completion
- **Mode-Specific Tests:** Test Single Game, Tournament, and Franchise modes separately

---

## Implementation Checklist

### Phase 1: Data Requirements (Current)
- [x] Define data requirements for each bucket
- [ ] Review and refine with feedback
- [ ] Validate against existing codebase

### Phase 2: Flow Mapping
- [ ] Map all page-to-page transitions
- [ ] Annotate each transition with required data
- [ ] Identify gaps where data isn't being passed
- [ ] Flag transitions needing new persistence logic

### Phase 3: Implementation
- [ ] Implement missing persistence logic
- [ ] Update navigation helpers
- [ ] Add validation on page load
- [ ] Create comprehensive test suite

### Phase 4: Documentation
- [ ] Update master documentation
- [ ] Create transition flow diagrams
- [ ] Document edge cases and special handling

---

## Game Plan & Playbooks Persistence Rules

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
  - Non-gameplay instances (Command Center, etc.)

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

## Franchise & Tournament Mode Data Persistence

**All changes persist across entire mode instance:**
- Game Plan and Playbooks changes
- Player attributes changes
- Team attributes changes
- Playcall attributes changes
- Player stats
- Team stats
- Playcall stats

## Known Bugs & Fixes Required

1. **Game Plan Navigation Bug:**
   - **Issue:** When navigating TCC/FCC → Game Plan → Playbooks → Game Plan, the `from` parameter is lost
   - **Result:** Game Plan shows "Back to Lineup" instead of "Back to Locker Room"
   - **Fix:** Preserve `from` parameter through Playbooks navigation

2. **Training Current Playbook:**
   - **Issue:** When user selects "Current Playbook" radio button, latest Game Plan and Playbook settings should apply
   - **Status:** Needs verification/implementation

