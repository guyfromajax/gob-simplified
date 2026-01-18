## Mode Initialization System ✅ **COMPLETE** (January 2025)

**Base Constants**

1. **Player Attribute Initialization**:
   - **Copied from Universal**: SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT (exact values)
   - **Randomized**: NG=1.0, CH (Character)=random(1-100), MO (Momentum)=0, EM (Emotion)=random(1-100)

2. **Team Attribute Ranges**:
   - **Single Game & Tournament**: `random.randint(-10, 10)` for most attributes, `team_chemistry=random(7-25)`, `rebound_modifier=random(0.0-0.4)`
   - **Franchise**: `random.randint(-3, 3)` for most attributes, `team_chemistry=random(7-13)`, `rebound_modifier=0.2` (fixed)

3. **Common Team Attributes** (all modes):
   - `shot_threshold`: `random.randint(-10, 190)`
   - `discipline`, `fight`, `offensive_efficiency`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`

**Mode Initialization Flow (3 Steps)**

1. **Initialize Player Attributes** - Copy from universal collection, randomize NG/CH/MO/EM for all players
2. **Initialize Team Attributes** - Set mode-specific attribute ranges, initialize `rebound_modifier` and `team_chemistry`
3. **Initialize Playbook Settings** - Set default playbook distributions (first play=100% per section, others=0%)

**Long Form Documentation**

### Overview

The Mode Initialization System diversifies attribute values when users create a new mode instance (Single Game, Tournament, or Franchise). This system ensures that each new game mode instance has unique player and team attributes, adding variety and replayability.

**Location:** `BackEnd/models/team_manager.py`, `BackEnd/models/player.py`  
**Status:** ✅ Fully implemented for all three game modes  
**Scope:** Applies only to new mode instance creation; existing instances persist their unique data

### Initialization Scope

**Single Game Mode:**
- Applies to the 2 teams participating in the game instance
- Player attributes randomized for all players on both teams
- Team attributes randomized for both teams

**Tournament Mode:**
- Applies to all 8 teams in the tournament instance
- Player attributes randomized for all players on all 8 teams
- Team attributes randomized for all 8 teams
- **ALL player attributes stored** in `tournament.player_stats.{player_id}.attributes` (not just EM, CH, MO)

**Franchise Mode:**
- Applies to all 8 teams in the franchise instance
- Player attributes randomized for all players on all 8 teams
- Team attributes randomized for all 8 teams (with different ranges than Single/Tournament)
- **ALL player attributes stored** in `franchise.players.{player_id}.attributes`

### Player Attribute Initialization

**Location:** `BackEnd/models/player.py` - `Player.randomize_game_attributes()` (lines 51-102)

**Copied from Universal Players Collection** (exact values):
- SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT

**Randomized Values:**
- **NG** (Energy): Always `1.0` (full energy at start)
- **CH** (Character): `random.randint(1, 100)`
- **MO** (Momentum): Always `0` (always starts at 0 for all game modes)
- **EM** (Emotion): `random.randint(1, 100)`

**Implementation:**
- Updates both the attribute and its anchor value (e.g., `EM` and `anchor_EM`)
- Called during mode instance creation for all players

### Team Attribute Initialization

**Location:** `BackEnd/models/team_manager.py` - `TeamManager.init_team_attributes()` (lines 185-226)

**Common Attributes (All Modes):**
- `shot_threshold`: `random.randint(-10, 190)`

**Mode-Specific Ranges:**

**Single Game & Tournament Mode:**
- Attribute range: `random.randint(-10, 10)` for:
  - `discipline`, `fight`, `offensive_efficiency`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`
- `team_chemistry`: `random.randint(7, 25)`
- `rebound_modifier`: `random.randint(0, 40) / 100.0` (random 0.0-0.4 in 0.01 increments)

**Franchise Mode:**
- Attribute range: `random.randint(-3, 3)` for:
  - `discipline`, `fight`, `offensive_efficiency`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`
- `team_chemistry`: `random.randint(7, 13)` (lower range for more challenging progression)
- `rebound_modifier`: `0.2` (fixed center value)

**Implementation:**
- Accepts `mode` parameter to determine attribute ranges
- Called during team initialization when `team_attributes` is not provided

### Initialization Points

**Single Game Mode:**
- **Location:** `BackEnd/api/api.py` - `init_game()` endpoint
- **Process:**
  1. `GameManager` is created with team names
  2. `TeamManager.__init__()` loads roster and initializes team attributes
  3. `_initialize_game_stats()` randomizes player attributes (EM, CH, MO)
  4. Game document is created with initialized attributes

**Tournament Mode:**
- **Location:** `BackEnd/tournament/tournament_manager.py` - `create_tournament()` method
- **Process:**
  1. Tournament document is created
  2. All players from participating teams are loaded
  3. `Player.randomize_game_attributes()` is called for each player
  4. **ALL player attributes are stored** in `tournament.player_stats.{player_id}.attributes` (not just EM, CH, MO)
  5. Team attributes are initialized when teams are first used in games
- **Attribute Storage:** Tournament mode uses the same architecture as Franchise mode - all attributes are stored in the tournament document to support training and evolution

**Franchise Mode:**
- **Location:** `BackEnd/models/franchise_manager.py` - `initialize_season()` method
- **Process:**
  1. Season is initialized
  2. All players from all teams are loaded
  3. `Player.randomize_game_attributes()` is called for each player
  4. Team attributes are initialized in `franchise_teams` structure with Franchise-specific ranges

### Playbook Settings Initialization

**Location:** `BackEnd/api/gameplan_routes.py` - `initialize_playbook_settings()` (lines 206-378)

**Initialization Function:**
- Called during team object creation in all three modes:
  - **Single Game:** `ensure_team_objects_exist()` (lazy initialization when teams are first accessed)
  - **Tournament:** `create_tournament()` (all 8 teams initialized upfront)
  - **Franchise:** `initialize_season()` (all 8 teams initialized upfront)

**Default Playbook Settings:**
- **Percentage Distributions:** Even distribution across all plays in each section
  - Motion: Evenly distributed across all motion plays
  - Set Play Inside: Evenly distributed across all inside set plays
  - Set Play Attack: Evenly distributed across all attack set plays
  - Set Play Outside: Evenly distributed across all outside set plays
  - Zone Defense: Evenly distributed across all zone defenses ("2-3 Zone", "3-2 Zone", "1-3-1 Zone")
  - Man Defense: "Man" = 100% (only one man defense exists)
- **Slot Assignments:** Empty (no plays assigned to priority slots 1-6)
- **Motion Dropdowns:** Empty (all motion plays default to "-")
- **Position Filters:** Pre-populated with play assignments:
  - **Standard:** All basic plays (3-2 Motion, 4-1 Motion, 5-0 Motion, Base Post Play, Pick & Roll (Lower Wing), Double Screen for SG)
  - **PF:** Power Forward specific plays (PF Post Motion, PF Post Up, PF High Post Drive, PF Corner Shot, PF Quick Jumper)
  - **PG, SG, SF, C:** Empty (can be customized later)

**Position Filter Storage:**
- Position filters store `play_id` (ObjectId strings) for each play
- Play names are mapped to `play_id` by querying the universal `plays` collection
- If a play name is not found in the database, a warning is logged and the play is skipped

### Data Persistence

**Important:** Once a mode instance is created, its unique attribute values persist:
- **Single Game:** Attributes stored in game document, persist across quarters
- **Tournament:** **ALL attributes** stored in `tournament.player_stats.{player_id}.attributes`, persist across rounds (unified with Franchise architecture)
- **Franchise:** **ALL attributes** stored in `franchise.players.{player_id}.attributes`, persist across weeks and seasons

**Evolution:**
- Attributes can change based on:
  - Training system (Franchise/Tournament modes)
  - In-game performance (momentum, chemistry adjustments)
  - User interactions (coaching decisions, lineup changes)
- Initial randomization provides the starting point; subsequent changes build upon these values

### Key Files

**Backend:**
- `BackEnd/models/player.py` - `Player.randomize_game_attributes()` (lines 51-102)
- `BackEnd/models/team_manager.py` - `TeamManager.init_team_attributes()` (lines 185-226)
- `BackEnd/api/api.py` - `init_game()` (lines 2099-2142) - Single Game mode initialization
- `BackEnd/tournament/tournament_manager.py` - `create_tournament()` (lines 32-86) - Tournament mode initialization
- `BackEnd/models/franchise_manager.py` - `initialize_season()` (lines 109-210) - Franchise mode initialization
- `BackEnd/api/gameplan_routes.py` - `initialize_playbook_settings()` (lines 206-378) - Playbook settings initialization

