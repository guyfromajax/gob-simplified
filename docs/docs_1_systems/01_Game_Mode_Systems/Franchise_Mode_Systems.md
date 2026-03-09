# Franchise Mode Systems

**Status:** ✅ **PRODUCTION** - Fully operational (January 2025)

## Overview

Franchise Mode supports multi-season career mode where team and player data persists across games and seasons. Team attributes and player attributes can be modified through training and persist throughout the franchise. The Franchise Command Center provides a comprehensive interface for managing franchise progression, viewing schedules, standings, and running training sessions.

Continuing seasons inside a franchise instance are rebuilt from franchise-instance state only. Universal `players` / `teams` data is only used when creating a brand new franchise instance.

Post-championship offseason flow:
- After EOS national week `34` completes, franchise mode advances to week `35`.
- Week `35` is Awards + live recruiting/signings.
- Week `36` is the signed-results / wrap-up state.
- `Go To Next Season` becomes the primary CTA in week `36`.

**Location:** `FrontEnd/static/franchise-command-center.html`, `FrontEnd/static/franchise-command-center.js`  
**Status:** ✅ Fully implemented with Schedule tab, training integration, and franchise management

## Base Constants

**Collection:** `franchises`  
**Document:** Franchise document (ObjectId)  
**Path:** `franchises.{franchise_id}.franchise_teams.{team_id}`

**Team Attributes:**
- `shot_threshold`: `random.randint(-10, 190)`
- `discipline`: `random.randint(-1, 1)` (formerly `turnover_modifier`)
- `fight`: `random.randint(-1, 1)` (formerly `foul_modifier`)
- `rebound_modifier`: `0.2` (fixed center value)
- `offensive_efficiency`: `random.randint(-1, 1)`
- `team_chemistry`: `random.randint(7, 10)` (tighter range for more controlled progression)
- `defensive_efficiency`: `random.randint(-1, 1)`
- `fb_efficiency`: `random.randint(-1, 1)`
- `pt_efficiency`: `random.randint(-1, 1)`
- `fb_opp_modifier`: `random.randint(-1, 1)`
- `pt_opp_modifier`: `random.randint(-1, 1)`

**Initialization:**
- **Upfront Initialization**: All 8 teams initialized when franchise season is created
- **Playbook Settings**: Even distribution across all plays in each category
- **Week Initialization**: Franchise starts at `week = 1` (training camp happens before first games are played)

## System Flow

1. **Season Initialization** - All 8 teams initialized upfront with mode-specific attributes
2. **Team Object Storage** - Stored in `franchises` collection under `franchise_teams.{team_id}`
3. **Team Object Loading** - Loaded when creating new game instance within franchise
4. **Training System** - Team and player attributes updated through training
5. **Team Object Persistence** - Persists across all games and seasons in the franchise

## Long Form Documentation

### Franchise Command Center

**Play Next Game → set-lineup (February 2026):** When the user clicks "Play Next Game", the command center builds the set-lineup URL using the **same approach as tournament**: API-sourced user team first (`topData.team` → `userTeamNameForLeaders` compared to matchup `home`/`away`), then id-derived fallback (`userTeamId` vs `home_id`/`away_id`). This avoids reliance on `localStorage` `franchise_user_team`, which can be missing or stale and caused "Can't determine your team" for some users. Implementation: `FrontEnd/static/franchise-command-center.js` (Play Next Game handler). See Data Persistence System doc: "FCC Play Next Game → set-lineup URL".

**Tabs (in order):**
1. **Standings** - Conference standings table showing wins, losses, win percentage, points for/against, and next opponent
2. **Roster** - Team roster (player attributes) and player statistics for the current season. Each team has 15 players and 12 scholarships. They have an active roster of 12 players, and up to 3 players on their training squad. Franchise-team data stores `scholarship_players`, `training_squad_players`, and `playing_time_promise_players`.
3. **Team** - Team Report section (team attributes) and Playbook Summary section (play effectiveness)
4. **Stats** - Franchise leaderboards for key statistics across all teams, plus team-level statistics
5. **Schedule** - Season schedule view with weekly matchups and training report links
6. **Team Traits** - Team attribute totals for all teams in the franchise with sortable grid and Top 10 list
7. **Recruits** - Recruiting pool with player attributes and position ratings

**Tab Content Details:**

**Roster Tab:**
- Displays player roster table with attributes (SC, SH, ID, OD, PS, BH, RB, AG, ST, ND, IQ, FT, RT)
- Displays player statistics table for the current season (PTS, FGM/FGA, 3PTM/3PTA, FTM/FTA, REB, AST, STL, BLK, F, MIN, TO)
- Player names are clickable links to player detail pages
- **Data Loading**: ✅ UNIFIED: Roster loaded from `/roster/{team_name}?franchise_id={id}` endpoint, stats merged from franchise document's `players` collection

**Team Tab:**
- **Team Report Section**: Displays team attributes in a grid layout (same as Training Report)
  - Shows team attributes: Shooting, Rebounding, Offense, Defense, Fast Breaks, Press/Trap, Aggression, Discipline, Momentum, Team Chemistry, Fast Break Defense, Press/Trap Breaks
  - Uses visual indicators (pills, progress bars, +/- indicators) matching Training Report styling
  - Styled with scoped CSS (`command-center-team-styles.css`) to maintain light theme consistency
- **Playbook Summary Section**: Displays play and defense effectiveness
  - Shows offensive plays (motion and set plays) with effectiveness progress bars
  - Shows defensive schemes (man and zone defenses) with effectiveness progress bars
  - Organized by Offense and Defense categories
  - Data loaded from franchise document: `franchises.{franchise_id}.franchise_teams.{team_id}.plays` and `franchises.{franchise_id}.franchise_teams.{team_id}.scouting_data`
  - Loaded when Team tab is opened via `loadTeamData()` function

**Styling Implementation:**
- Team Report and Playbook Summary sections use scoped CSS (`command-center-team-styles.css`)
- Sections wrapped in `.training-report-styled` container to prevent style conflicts
- Maintains command center's light theme while providing Training Report-style visuals
- CSS variables adjusted for light background (white) instead of dark gradient

**Stats Tab:**
- **Leaders Section**: Franchise leaderboards for key statistics across all teams
- **Team Stats Section**: Team-level statistics table (points, rebounds, assists, steals, blocks)
- Combined into single tab for better organization

**Header Controls:**
- **Set Game Plan** - Navigate to Game Plan screen with franchise context
- **Playbooks** - Navigate to Playbooks page with franchise context
- **Run Training / Play Now** - Dynamic button that changes based on training status

**Schedule Tab:**
- Displays full season schedule organized by week
- Shows completed games with scores (winner highlighted in bold)
- Shows upcoming games without scores
- Training report links appear next to user's team's games when training has been completed for that week
- Also displays latest training session results below the schedule

**Team Traits Tab:**
- **Team Attribute Totals Grid**: Displays a sortable table with team attribute totals for all teams in the franchise
  - Shows totals for SC, SH, ID, OD, PS, BH, RB, AG, ST, ND, IQ, FT
  - Headers are clickable and sortable (same as player attribute sorting on roster pages)
  - Default sort is by FT descending
- **Top 10 List**: Displays the top 10 team attribute values excluding FT
  - Each team's row content is displayed in their primary color with bold font
  - Shows format: `Rank. Team Name Attribute: Value`
- **Data Loading**: ✅ Aggregates from franchise.players object (franchise-specific attributes), not from universal players_collection
  - If `meta.team_id` is missing for a player, resolves it from the player's `team` name by looking up the team's ObjectId in the teams collection
  - Uses franchise-specific attributes (anchor_ prefixed if available, otherwise regular attributes)
- Loaded via `/franchise/team-traits` endpoint

**Standings Tab:**
- Displays conference standings table only (schedule moved to Schedule tab)
- Shows team name, wins, losses, win percentage, points for, points against, and next opponent
- **EOS Tournament Support**: Next opponent column populates from tournament bracket during weeks 15-17 (reuses Tournament mode's bracket lookup pattern)

### End-of-Season (EOS) Tournament System

**Overview:**
After completing the regular season (week 14), the top 8 teams advance to a single-elimination tournament spanning weeks 15-17. The tournament consists of three rounds: Round 1 (Quarterfinals), Round 2 (Semifinals), and Final (Championship).

**Initialization:**
- **Trigger**: Automatically initialized when week 14 is completed via `/franchise/complete-week`
- **Location**: `BackEnd/tournament/eos_tournament.py` - `initialize_eos_tournament()`
- **Process**:
  1. Calculates regular season standings (sorted by wins, PF-PA differential, random tiebreaker)
  2. Generates seeds 1-8 from top 8 teams
  3. Creates bracket structure with Round 1 matchups: 1v8, 4v5, 2v7, 3v6
  4. Sets `eos_tournament_active = True` and `week = 15` on franchise document
  5. Stores tournament state in `franchise_doc.eos_tournament`:
     - `bracket`: `{round1: [...], round2: [], final: []}`
     - `current_round`: 1, 2, or 3
     - `completed`: Boolean flag
     - `champion`: Winning team ObjectId (string)
     - `seeds`: Dictionary mapping team_id to seed number
     - `results`: Array of completed game results

**Bracket Structure:**
- Each matchup contains:
  - `home_team`: ObjectId string
  - `away_team`: ObjectId string
  - `game_id`: Game document ID (set after game completion)
  - `winner`: Winning team ObjectId string (set after game completion)
  - `score`: Dictionary with team_id keys and score values

**Gameplay Flow:**
- **Week 15**: Round 1 (Quarterfinals) - 4 games
- **Week 16**: Round 2 (Semifinals) - 2 games (winners from Round 1)
- **Week 17**: Final (Championship) - 1 game (winners from Round 2)

**API Endpoints:**
- **`POST /franchise/play-next-game`**: Returns user's matchup for current week
  - ✅ **EOS Tournament Support**: Checks `eos_tournament_active` and `week >= 15`
  - Reuses Tournament mode's bracket lookup pattern:
    1. Gets current round from `eos_tournament.current_round`
    2. Determines round name (`round1`, `round2`, or `final`) via `get_round_name()`
    3. Finds user's matchup in bracket by matching `user_team_id`
    4. Returns matchup with team names and IDs (same format as regular season)
  - **Location**: `BackEnd/api/franchise_routes.py` (lines 355-395)

- **`GET /franchise/standings`**: Returns standings with next opponent column
  - ✅ **EOS Tournament Support**: Populates "Next Opponent" from tournament bracket during weeks 15-17
  - Reuses same bracket lookup pattern as `play-next-game`
  - **Location**: `BackEnd/api/franchise_routes.py` (lines 957-1003)

**Frontend Integration:**
- **Scouting Report Button**: 
  - ✅ **EOS Tournament Support**: Shows during weeks 15-17 if user team is not eliminated
  - Extended week check from `week <= 14` to `week <= 17` (with elimination check)
  - Reuses `play-next-game` endpoint to get opponent (now handles EOS Tournament)
  - **Location**: `FrontEnd/static/franchise-command-center.js` - `updateScoutingButton()` (lines 1769-1829)

- **Next Opponent Column**:
  - ✅ **EOS Tournament Support**: Populates from tournament bracket during weeks 15-17
  - Backend endpoint (`/franchise/standings`) handles bracket lookup automatically
  - **Location**: `FrontEnd/static/franchise-command-center.js` - `renderStandings()` (line 108)

- **Play Now Button**:
  - Changes to "Sim Rest of Tournament" if user team is eliminated
  - Changes to "Finish Current Season" when tournament is complete
  - **Location**: `FrontEnd/static/franchise-command-center.js` - `updatePlayButton()` (lines 800-846)

**Tournament Progression:**
- **Round Advancement**: Automatically advances to next round when all games in current round are complete
- **Location**: `BackEnd/tournament/eos_tournament.py` - `advance_tournament_round()`
- **Process**:
  - Round 1 → Round 2: When all 4 Round 1 games have winners
  - Round 2 → Final: When both Round 2 games have winners
  - Final → Complete: When Final game has winner (sets `completed = True` and `champion`)

**Key Files:**
- `BackEnd/tournament/eos_tournament.py` - Tournament initialization, bracket generation, round advancement
- `BackEnd/api/franchise_routes.py` - `play_next_game()`, `standings()`, `complete_week()` (EOS Tournament initialization)
- `FrontEnd/static/franchise-command-center.js` - `updateScoutingButton()`, `updatePlayButton()`, `renderStandings()`

**SS&S Principles:**
- ✅ **Code Reuse**: EOS Tournament gameplay flow reuses Tournament mode's bracket lookup pattern
- ✅ **Consistent API**: Same endpoint (`/franchise/play-next-game`) handles both regular season and EOS Tournament
- ✅ **Single Source of Truth**: Tournament bracket stored in `franchise_doc.eos_tournament.bracket`
- ✅ **Idempotent Operations**: Round advancement checks for completion before advancing

### Team Object Lifecycle

#### 1. Team Object Creation

**Primary Trigger:** When franchise season is initialized via `FranchiseManager.initialize_season()`

**Location:** `BackEnd/models/franchise_manager.py` - `initialize_season()` (lines 109-235)

**Process:**
1. **Week Initialization**: Franchise `week` field set to `1` (training camp occurs at week 1 before first games)
2. **Upfront Initialization**: All 8 teams initialized when franchise season is created
3. Creates `franchise_teams` objects for all 8 teams in the franchise
4. Each team object includes:
   - `playcall_settings`: Default settings (all set to 2 = Normal)
   - `strategy_settings`: Default settings (all set to 2 = Normal)
   - `plays`: Populated via `populate_team_plays(mode="franchise")`
   - `scouting_data`: Initialized via `populate_scouting_data(mode="franchise")`
   - `playbook_settings`: Even distribution across all plays in each category (via `initialize_playbook_settings()`)
   - **Team attributes**: Initialized via `TeamManager.init_team_attributes(mode="franchise")`
     - Uses Franchise mode attribute ranges (narrower ranges: -1 to +1, tighter team_chemistry: 7-10, fixed rebound_modifier: 0.2)

**Fallback Trigger:** `ensure_team_objects_exist()` when accessing Game Plan or Playbooks

**Location:** `BackEnd/api/gameplan_routes.py` (lines 525-651)

**Process:** Same as above, but only creates missing team objects (doesn't recreate existing ones)

**Initialization Pattern:**
- **Upfront Initialization**: All 8 teams initialized when franchise season is created (eliminates race conditions)
- **Mode-Specific Attributes**: Uses Franchise mode attribute ranges (narrower ranges for more challenging progression)
- **Playbook Settings**: Even distribution (not first play = 100%)

#### 2. Team Object Storage

**Collection:** `franchises`  
**Document:** Franchise document (ObjectId)  
**Path:** `franchises.{franchise_id}.franchise_teams.{team_id}`

**Structure:** Same as Single Game Mode (see Single Game Mode documentation for structure)

#### 3. Team Object Loading

**Location:** `BackEnd/api/api.py` - `load_team_attributes_from_doc()` (lines 196-244)

**Process:**
1. `load_team_attributes_from_doc()` is called with `mode="franchise"` and `doc_id=franchise_id`
2. Loads team attributes from `franchises.{franchise_id}.franchise_teams.{team_id}`
3. If not found, falls back to the **universal `teams` collection** in MongoDB
4. Attributes are passed to `GameManager()` constructor
5. If no attributes are loaded, `TeamManager.init_team_attributes(mode="franchise")` generates random values

**Team Data API Endpoint:**
- **Location:** `BackEnd/api/franchise_routes.py` - `get_franchise_team_data()`
- **Endpoint:** `GET /franchise/team-data?franchise_id=...&team_name=...`
- **Process:**
  1. Resolves `team_name` to `team_id` server-side using `db.teams.find_one({"name": team_name})`
  2. Returns team object from `franchises.{franchise_id}.franchise_teams.{team_id}`
  3. Initializes `scouting_data.defense` structure if missing
  4. Defaults team attributes to 0 if not present
- **Pattern**: Matches the successful pattern used by `/franchise/roster` - server-side team name resolution

#### 3.5. Player Attribute Loading During Game Initialization ✅ **FIXED** (January 2026)

**Problem:** Player attributes from training were not being loaded during game initialization. Training saves attributes to `franchise.players.{player_id}.attributes`, but game initialization was loading from the universal `players` collection, ignoring trained attributes.

**Root Cause:**
- `TeamManager._load_roster()` called `load_roster()` which always loaded from the universal `players` collection
- No `franchise_id` was passed to `load_roster()`, so it couldn't check `franchise.players`
- This meant trained attributes (including NG reductions from training) were ignored during gameplay

**Solution:**
1. **Modified `roster_loader.py`**: Added `franchise_id` parameter to `load_roster()` and `_load_from_db()`
   - When `franchise_id` is provided, checks `franchise.players` first
   - Merges franchise-specific attributes (from `franchise.players.{player_id}.attributes`) into base player data
   - Falls back to universal `players` collection if franchise data not found
2. **Modified `TeamManager`**: Added `franchise_id` parameter to `__init__()` and `_load_roster()`
   - Stores `franchise_id` on TeamManager instance
   - Passes `franchise_id` to `load_roster()` when loading roster
3. **Modified `GameManager`**: Added `franchise_id` parameter to `__init__()`
   - Passes `franchise_id` to both home and away TeamManager instances
4. **Modified `simulate_quarter_endpoint()`**: Passes `franchise_id` when creating GameManager
   - Extracts `franchise_id` from request or saved game document
   - Only passes `franchise_id` when `mode == "franchise"`

**Data Flow:**
1. Training saves attributes to `franchise.players.{player_id}.attributes.{attr}` (e.g., SC, SH, ID, OD, NG)
2. When game initializes, `GameManager` is created with `franchise_id`
3. `TeamManager._load_roster()` calls `load_roster(team_name, franchise_id=franchise_id)`
4. `load_roster()` checks `franchise.players` for each player on the team
5. Franchise-specific attributes are merged into base player data
6. `Player` objects are created with trained attributes
7. Gameplay uses trained attributes throughout the game

**Key Files:**
- `BackEnd/utils/roster_loader.py` - `load_roster()`, `_load_from_db()` (franchise player loading)
- `BackEnd/models/team_manager.py` - `TeamManager.__init__()`, `_load_roster()` (franchise_id parameter)
- `BackEnd/models/game_manager.py` - `GameManager.__init__()` (franchise_id parameter)
- `BackEnd/api/api.py` - `simulate_quarter_endpoint()`, `init_game()` (pass franchise_id to GameManager)

**Benefits:**
- ✅ Trained player attributes are now used during gameplay
- ✅ NG reductions from training (scrimmages/conditioning) persist to next game
- ✅ All attribute improvements from training are reflected in gameplay
- ✅ Consistent with FCC Roster tab (which already loads from `franchise.players`)

**Related Documentation:**
- See `Training_System.md` for details on how training saves attributes
- See `Data_Persistence_System.md` for franchise player data structure

#### 4. Team Object Updates

**Playbook Settings:**
- Saved to `franchises.{franchise_id}.franchise_teams.{team_id}.playbook_settings`
- Updated when user submits playbook changes

**Strategy Settings:**
- Saved to `franchises.{franchise_id}.franchise_teams.{team_id}.strategy_settings`
- Updated when user submits game plan changes

**Team Attributes:**
- Updated through training
- **Location:** `BackEnd/api/franchise_routes.py` (lines 1045-1061)
- **Process**: Training changes are saved to `franchises.{franchise_id}.franchise_teams.{team_id}.{attribute_name}`
- **Example**: `franchises.{franchise_id}.franchise_teams.{team_id}.defensive_efficiency = new_value`

#### 5. Team Object Persistence

- Team objects persist across all games and seasons in the franchise
- Changes to team attributes persist permanently (until modified again)
- When a new season is started, team objects are preserved (carryover from previous seasons)

## Key Files

- `BackEnd/models/franchise_manager.py` - `initialize_season()` (lines 109-235) - Upfront initialization
- `BackEnd/api/gameplan_routes.py` - `ensure_team_objects_exist()` (lines 525-651) - Fallback initialization
- `BackEnd/api/api.py` - `load_team_attributes_from_doc()` (lines 196-244)
- `BackEnd/api/api.py` - Game creation logic (lines 1246-1253, 1337-1344)
- `BackEnd/api/franchise_routes.py` - `get_franchise_team_data()` - Team data endpoint
- `BackEnd/api/franchise_routes.py` - Training save logic (lines 1045-1061)

## See Also

- `Mode_Init_System.md` - Complete mode initialization system documentation
- `Training_System.md` - Training system documentation
- `Playbooks_Page.md` - Playbook settings management

## Regression Tests

- `tests/test_franchise_game_scoping.py::test_schedule_scopes_game_lookup_to_franchise`
- `tests/test_franchise_game_scoping.py::test_save_game_result_legacy_lookup_uses_franchise_scope`
- `tests/test_franchise_game_scoping.py::test_schedule_endpoint_does_not_leak_cross_franchise_game_docs`
