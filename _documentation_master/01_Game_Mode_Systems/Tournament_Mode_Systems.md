# Tournament Mode Systems

**Status:** ✅ **PRODUCTION** - Fully operational (January 2025)

## Overview

Tournament Mode supports multi-game tournament brackets where team data persists across games within the tournament. The Tournament Command Center provides a comprehensive interface for managing tournament progression, viewing schedules, and bracket management. **Training is disabled** in Tournament mode; users go directly to gameplay.

**Location:** `FrontEnd/static/tournament.html`, `FrontEnd/static/tournament.js`  
**Status:** ✅ Fully implemented with Schedule tab and bracket management. Training disabled (see below).

## Base Constants

**Collection:** `tournaments`  
**Document:** Tournament document (ObjectId)  
**Path:** `tournaments.{tournament_id}.teams.{team_id}`

**Team Attributes:**
- `shot_threshold`: `random.randint(-10, 190)`
- `discipline`: `random.randint(-10, 10)` (formerly `turnover_modifier`)
- `fight`: `random.randint(-10, 10)` (formerly `foul_modifier`)
- `rebound_modifier`: `random.randint(0, 40) / 100.0` (random 0.0-0.4 in 0.01 increments)
- `offensive_efficiency`: `random.randint(-10, 10)`
- `team_chemistry`: `random.randint(7, 25)`
- `defensive_efficiency`: `random.randint(-10, 10)`
- `fb_efficiency`: `random.randint(-10, 10)`
- `pt_efficiency`: `random.randint(-10, 10)`
- `fb_opp_modifier`: `random.randint(-10, 10)`
- `pt_opp_modifier`: `random.randint(-10, 10)`

**Initialization:**
- **Upfront Initialization**: All 8 teams initialized when tournament is created (matches Franchise pattern)
- **Play Randomization**: Each play gets randomized `effectiveness`, `momentum`, `cloaking` values
- **Defense Randomization**: Each defense gets randomized `effectiveness`, `momentum`, `cloaking` values
- **Playbook Settings**: Even distribution across all plays in each category

## System Flow

1. **Tournament Creation** - All 8 teams initialized upfront with mode-specific attributes
2. **Team Object Storage** - Stored in `tournaments` collection under `teams.{team_id}`
3. **Team Object Loading** - Loaded when creating new game instance within tournament
4. **Team Object Persistence** - Persists across all games in tournament, reset for new tournaments

## Long Form Documentation

### Tournament Command Center

**Initialization:**
- **URL Parameter Support:** Reads `tournament_id` and `team_id` from URL parameters on page load
  - Priority 1: URL parameters (when navigating from report pages, etc.)
  - Priority 2: localStorage (for returning to page)
  - Priority 3: Active tournament lookup by `user_team_id`
- **Data Loading:** `loadTournament()` function prioritizes URL parameters over localStorage
  - Uses `/tournament/state?tournament_id=...` endpoint (query parameter format)
  - Updates `userTeamId` from tournament document if not already set
  - Shows error message if tournament fails to load
- **Error Handling:** Page displays error message if tournament fails to load, preventing empty data display

**Tabs (in order):**
1. **Bracket** - Visual bracket display showing tournament progression
2. **Roster** - Team roster (player attributes) and player statistics for the current tournament
3. **Team** - Team Report section (team attributes) and Playbook Summary section (play effectiveness)
4. **Stats** - Team stats table (W/L, PF/PA, shooting stats, rebounding, assists, etc.) and tournament leaderboards for key statistics
5. **Schedule** - Detailed schedule view with First Round, Semifinals, and Championship matchups

**Tab Content Details:**

**Roster Tab:**
- Displays player roster table with attributes (SC, SH, ID, OD, PS, BH, RB, AG, ST, ND, IQ, FT, RT)
- Displays player statistics table (PTS, FGM/FGA, 3PTM/3PTA, FTM/FTA, REB, AST, STL, BLK, F, MIN, TO)
- Player names are clickable links to player detail pages

**Team Tab:**
- **Team Report Section**: Displays team attributes in a grid layout (same as Training Report)
  - Shows team attributes: Shooting, Rebounding, Offense, Defense, Fast Breaks, Press/Trap, Aggression, Discipline, Momentum, Team Chemistry, Fast Break Defense, Press/Trap Breaks
  - Uses visual indicators (pills, progress bars, +/- indicators) matching Training Report styling
  - Styled with scoped CSS (`command-center-team-styles.css`) to maintain light theme consistency
- **Playbook Summary Section**: Displays play and defense effectiveness
  - Shows offensive plays (motion and set plays) with effectiveness progress bars
  - Shows defensive schemes (man and zone defenses) with effectiveness progress bars
  - Organized by Offense and Defense categories
  - Data loaded from tournament document: `tournaments.{tournament_id}.teams.{team_id}.plays` and `tournaments.{tournament_id}.teams.{team_id}.scouting_data`
  - **Data Loading**: Uses `/tournament/team-data` endpoint (matches pattern used by `/tournament/roster`)
    - Endpoint resolves `team_name` to `team_id` server-side using multiple fallback strategies
    - Handles both formatted ("ocean-city") and unformatted ("Ocean City") team names
    - Falls back to `tournament.user_team_id` if provided team_name doesn't match
    - Initializes `scouting_data.defense` structure if missing
    - Defaults team attributes to 0 if not present

**Stats Tab:**
- **Team Stats Table**: Displays aggregated team statistics for all teams in the tournament
  - ✅ **SS&S**: Uses shared `TeamStatsTable` module (`FrontEnd/static/js/shared/teamStatsTable.js`) - same code as Franchise mode
  - Columns: Team, W (Wins), L (Losses), PF (Points For), PA (Points Against), FGM/FGA, FG%, 3PTM/3PTA, 3PT%, FTM/FTA, FT%, DREB, OREB, TREB, AST, STL, BLK, F, TO, DEF_A, DEF%, SCR_A, SCR%
  - Includes a TOTALS row that sums all team stats (W/L, shooting stats, rebounding, assists, etc.)
  - Stats are sortable by clicking column headers
  - Data loaded from `/tournament/team-stats` endpoint which uses shared `team_stats_aggregator.py` utility
  - **Data Refresh**: Automatically refreshes when returning to TCC after game completion via `handleTournamentUpdate()`
  - **Container Formatting**: Uses `overflow-x: auto` on container div (matches Franchise pattern)
- **Leaderboards**: Displays tournament leaders for key statistics (PTS, REB, AST, etc.)

**Roster Tab:**
- ✅ **SS&S**: Uses identical execution pattern as Franchise mode
  - `loadRoster()`: ✅ UNIFIED: Loads roster from `/roster/{team_name}?tournament_id={id}`, loads tournament doc from `/tournament/state`, merges stats into roster data
  - `renderRoster()`: Renders roster table and calls `renderRosterStats()` internally (matches Franchise `renderTeam()` pattern)
  - Player stats are merged from `tournament.players[playerId].season` into `rosterData.players[].stats.season`
  - Stats table uses `roster-stats-body` tbody ID (matches Franchise)
  - **Result**: Tournament and Franchise modes execute the exact same code with only variable names different

**Header Controls:**
- **Set Game Plan** - Navigate to Game Plan screen
- **Playbooks** - Navigate to Playbooks page
- **Play Next Game / Sim Remaining Games** - Dynamic button based on user's matchup status
  - Shows "Play Next Game" when the user has an upcoming game in the current round
  - Shows "Sim Remaining Games" when the user is eliminated or has no game this round
  - Removes opponent name from button text (simplified display)

### Schedule Tab

**Location:** `FrontEnd/static/tournament.js` - `renderSchedule()` function

**Display Structure:**
- **First Round** - Shows all 4 matchups with seed numbers:
  - Team 8 @ Team 1
  - Team 5 @ Team 4
  - Team 6 @ Team 3
  - Team 7 @ Team 2
- **Semifinals** - Shows 2 matchups:
  - Initially displays "TBD @ TBD" for both matchups
  - Dynamically filled based on First Round winners
  - Shows scores when games are completed
- **Championship** - Shows 1 matchup:
  - Initially displays "TBD @ TBD"
  - Dynamically filled based on Semifinals winners
  - Shows scores when game is completed

### Training (Disabled)

Training is **not used** in Tournament mode. Users go directly to gameplay (Play Next Game / Sim Remaining). `POST /tournament/run-training` exists as a stub and returns **404** ("Training is not available in Tournament mode") for backward compatibility. No "Run Training" button or training flow in TCC.

**Training Endpoint (stub only):**
- **Location:** `BackEnd/api/tournament_routes.py` - `run_tournament_training()`
- **Endpoint:** `POST /tournament/run-training`
- Always returns **404** with detail "Training is not available in Tournament mode". No training logic.

### Team Object Lifecycle

#### 1. Team Object Creation

**Primary Trigger:** When tournament is created via `TournamentManager.create_tournament()`

**Location:** `BackEnd/tournament/tournament_manager.py` - `create_tournament()` (lines 36-267)

**Process:**
1. **Upfront Initialization**: All 8 teams initialized when tournament is created (matches Franchise pattern)
2. For each team in the tournament:
   - Resolves team name to team document and ObjectId
   - Uses `TeamManager.init_team_attributes(mode="tournament")` to generate mode-specific team attributes
   - Creates team object with:
     - `playcall_settings`: Default settings (all set to 2 = Normal)
     - `strategy_settings`: Default settings (all set to 2 = Normal)
     - `plays`: Populated via `populate_team_plays(mode="tournament")`
       - **Tournament Mode Randomization**: Each play gets randomized values:
         - `effectiveness`: `random.randint(0, 80)`
         - `momentum`: `random.randint(0, 10)`
         - `cloaking`: `random.randint(0, 10)`
       - Each play and each value gets its own random roll
     - `scouting_data`: Initialized via `populate_scouting_data(mode="tournament")`
       - **Tournament Mode Randomization**: Each defense (Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone) gets randomized values:
         - `effectiveness`: `random.randint(0, 80)`
         - `momentum`: `random.randint(0, 10)`
         - `cloaking`: `random.randint(0, 10)`
       - Each defense and each value gets its own random roll
       - **Location**: `BackEnd/api/gameplan_routes.py` - `populate_scouting_data()` function (lines 403-521)
     - `playbook_settings`: Even distribution across all plays in each category (via `initialize_playbook_settings()`)
     - **Team attributes**: Initialized via `TeamManager.init_team_attributes(mode="tournament")`

**Fallback Trigger:** `ensure_team_objects_exist()` when accessing Game Plan or Playbooks

**Location:** `BackEnd/api/gameplan_routes.py` (lines 525-651)

**Process:** Same as above, but only creates missing team objects (doesn't recreate existing ones)

**Initialization Pattern:**
- **Upfront Initialization**: All 8 teams initialized when tournament is created (eliminates race conditions)
- **Mode-Specific Attributes**: Uses Tournament mode attribute ranges
- **Play Randomization**: Each play gets unique randomized effectiveness/momentum/cloaking values
- **Defense Randomization**: Each defense gets unique randomized effectiveness/momentum/cloaking values
- **Playbook Settings**: Even distribution (not first play = 100%)

#### 2. Team Object Storage

**Collection:** `tournaments`  
**Document:** Tournament document (ObjectId)  
**Path:** `tournaments.{tournament_id}.teams.{team_id}`

**Structure:** Same as Single Game Mode (see Single Game Mode documentation for structure)

#### 3. Team Object Loading

**Location:** `BackEnd/api/api.py` - `load_team_attributes_from_doc()` (lines 196-244)

**Process:**
1. `load_team_attributes_from_doc()` is called with `mode="tournament"` and `doc_id=tournament_id`
2. Loads team attributes from `tournaments.{tournament_id}.teams.{team_id}`
3. If not found, falls back to the **universal `teams` collection** in MongoDB
4. Attributes are passed to `GameManager()` constructor
5. If no attributes are loaded, `TeamManager.init_team_attributes(mode="tournament")` generates random values

**Team Data API Endpoint:**
- **Location:** `BackEnd/api/tournament_routes.py` - `get_tournament_team_data()`
- **Endpoint:** `GET /tournament/team-data?tournament_id=...&team_name=...`
- **Process:**
  1. Resolves `team_name` to `team_id` server-side using multiple fallback strategies:
     - Strategy 1: Exact name match
     - Strategy 2: Case-insensitive match
     - Strategy 3: Normalized name (replace dashes with spaces, title case)
     - Strategy 4: Fallback to `tournament.user_team_id`
  2. Returns team object from `tournaments.{tournament_id}.teams.{team_id}`
  3. Initializes `scouting_data.defense` structure if missing
  4. Defaults team attributes to 0 if not present
- **Pattern**: Matches the successful pattern used by `/tournament/roster` - server-side team name resolution with robust fallback strategies

#### 4. Team Object Updates

**Playbook Settings:**
- Saved to `tournaments.{tournament_id}.teams.{team_id}.playbook_settings`
- Updated when user submits playbook changes

**Strategy Settings:**
- Saved to `tournaments.{tournament_id}.teams.{team_id}.strategy_settings`
- Updated when user submits game plan changes

**Team Attributes:**
- Set at tournament creation; **training is disabled**, so no training updates
- Player attributes in `tournament.players.{player_id}.attributes` (or `player_stats` for legacy)
- Team attributes in `tournament.teams.{team_id}`; persist for duration of tournament

#### 5. Team Object Persistence

- Team objects persist for the duration of the tournament
- Changes to team attributes persist across all games in the tournament
- When a new tournament is started, new team objects are created (no carryover from previous tournaments)

## Key Files

- `BackEnd/tournament/tournament_manager.py` - `create_tournament()` (lines 36-267) - Upfront initialization
- `BackEnd/api/gameplan_routes.py` - `ensure_team_objects_exist()` (lines 525-651) - Fallback initialization
- `BackEnd/api/api.py` - `load_team_attributes_from_doc()` (lines 196-244)
- `BackEnd/api/api.py` - Game creation logic (lines 1246-1253, 1337-1344)
- `BackEnd/api/tournament_routes.py` - `get_tournament_team_data()` - Team data endpoint
- `BackEnd/api/tournament_routes.py` - `run_tournament_training()` - Stub only (returns 404; training disabled)

## See Also

- `Mode_Init_System.md` - Complete mode initialization system documentation
- `Training_System.md` - Training system documentation
- `Playbooks_Page.md` - Playbook settings management

