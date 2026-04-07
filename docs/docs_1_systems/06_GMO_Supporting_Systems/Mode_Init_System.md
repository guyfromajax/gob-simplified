## Mode Initialization System ✅ **COMPLETE** (January 2025)

**Base Constants**

1. **Player Attribute Initialization**:
   - **Copied from Universal**: SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT (exact values)
   - **Randomized**: NG=1.0, CH (Character)=random(1-100), MO (Momentum)=0, EM (Emotion)=random(1-100)

2. **Team Attribute Ranges**:
   - **Single Game**: `random.randint(-10, 10)` for A Group, `team_chemistry=random(7-25)`, `rebound_modifier=random(0.0-0.4)`, `shot_threshold=random(10, 210)`
   - **Tournament**: Seed-based (Seed 1 best → Seed 8 worst); see "Team Attribute Initialization" below for per-seed ranges
   - **Franchise**: `random.randint(-1, 1)` for most attributes, `team_chemistry=random(7-10)`, `rebound_modifier=0.2` (fixed), `shot_threshold=random(100, 120)`

3. **Common Team Attributes** (all modes):
   - `shot_threshold`
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


**Mode-Specific Ranges:**

**Single Game:**
- Attribute range: `random.randint(-10, 10)` for:
  - `discipline`, `fight`, `offensive_efficiency`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`
- `team_chemistry`: `random.randint(7, 25)`
- `rebound_modifier`: `random.randint(0, 40) / 100.0` (random 0.0-0.4 in 0.01 increments)
- `shot_threshold`: `random.randint(10, 210)`

**Tournament Mode:**
Ranges will be determined by each team's seed
- A Group:
  - `discipline`, `fight`, `offensive_efficiency`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`
- Custom Group: `team_chemistry`, `rebound_modifier`,`shot_threshold`
- Seed 1: 
  - A Group: each gets random.randint(5,10), 
  - Custom Group: team_chemistry random.randint(20,25), rebound_modifier `random.randint(30, 40) / 100.0` (random 0.3-0.4 in 0.01 increments), shot_threshold random.randint(10, 110)
- Seeds 2-4: 
  - A Group: each gets random.randint(-2,10), 
  - Custom Group: team_chemistry random.randint(12,25), rebound_modifier `random.randint(15, 40) / 100.0` (random 0.15-0.4 in 0.01 increments), shot_threshold random.randint(10,160)
- Seeds 5-7: 
  - A Group: each gets random.randint(-8,5), 
  - Custom Group: team_chemistry random.randint(8,18), rebound_modifier `random.randint(1, 40) / 100.0` (random 0.01-0.4 in 0.01 increments), shot_threshold random.randint(60,210)
- Seeds 8: 
  - A Group: each gets random.randint(-10,-2), 
  - Custom Group: team_chemistry random.randint(7,12), rebound_modifier `random.randint(1, 20) / 100.0` (random 0.01-0.2 in 0.01 increments), shot_threshold random.randint(110,210)

**Franchise Mode:**
- Attribute range: `random.randint(-1, 1)` for:
  - `discipline`, `fight`, `offensive_efficiency`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`
- `team_chemistry`: `random.randint(7, 10)` (tighter range for more controlled progression)
- `rebound_modifier`: `0.2` (fixed center value)
- `shot_threshold`: `random.randint(100, 120)`

**Implementation:**
- `TeamManager.init_team_attributes(mode, tournament_seed=None)`: accepts `mode` and, for `mode="tournament"`, optional `tournament_seed` (1–8). When `tournament_seed` is provided, uses the seed-based ranges above; otherwise falls back to single-game-style ranges.
- Tournament: called from `create_tournament()` with `tournament_seed` = 1 for first team in seed order through 8 for the last (seed order is set by the initial shuffle of the 8 teams).
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
  4. Team attributes are initialized in the **franchise_team_data (FTD)** structure with Franchise-specific ranges
  5. Each team's Franchise starting **`prestige`** is derived from the universal team prestige plus a one-time `random.randint(-30, 30)` adjustment, then clamped to a minimum of `200`.
  6. Each team's FTD doc includes **`total_player_attrs`**: the sum of that team's player core attributes (SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT). Used for national ranking. When the universal **teams** collection has a `total_player_attrs` field for a team, franchise init uses that value; otherwise it is computed from the universal **players** collection (sum by team name) during init.
  7. Each team's FTD doc includes recruiting support fields:
     - `scholarship_players`: array of the team's 12 initial player id strings
     - `training_squad_players`: array of the other 3 initial player id strings
     - `playing_time_promise_players`: initialized to `[]`
     - `Recruits`: keys `"1"` through `"20"` initialized to `None`
     - `recruiting_orders_week_35`: initialized to `{}`
     - `recruit_visit`: initialized to `None`
  8. On each new franchise season, those recruiting support fields are reset before the new season begins.
    - `scholarship_players` and `training_squad_players` are retained in the schema for future use, but are currently dormant in roster-assignment UI/logic.
  9. Brand new franchise init still loads from universal collections. Continuing franchise seasons do not; see `Season_Init_System.md`.

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
  - Fast Break: Seeded to `covert_release = 50`, `rim_runner = 50`, `triangle = 0`
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

### Strategy Settings (Game Plan)

`strategy_settings` holds the numeric sliders from the Game Plan screen (typically **0–4**, with **2 = Normal**). They are persisted on the mode document per team (Franchise FTD, Tournament team blob, or loaded into memory for Single Game).

**Canonical defaults (API / backfill helper):** `BackEnd/api/gameplan_routes.py` — `get_default_settings()` returns all listed keys at **2**, except it does **not** include `tempo` in that dict (Game Plan API treats tempo as per-game in places; see code comments there). Franchise and Tournament **do** store `tempo` on init (see below).

**Franchise Mode (new instance / FTD seed):**

- **Location:** `BackEnd/models/franchise_manager.py` — `initialize_season()` builds each team’s `franchise_team_data` entry.
- **Initialization:** Every team gets the **same fixed** `strategy_settings` object — **all keys below are set to `2`**:

| Key | Init value | Role (summary) |
|-----|------------|----------------|
| `offense` | 2 | Motion vs set-play mix |
| `inside` | 2 | Inside focus |
| `attack` | 2 | Attack focus |
| `outside` | 2 | Outside focus |
| `fast_breaks` | 2 | Fast-break defense / release tendency |
| `tempo` | 2 | Tempo preference (stored for all teams) |
| `defense` | 2 | Man vs zone mix |
| `aggression` | 2 | Defensive aggression |
| `hc_trap` | 2 | Half-court trap usage |
| `fc_press` | 2 | Full-court press usage |
| `rebounding` | 2 | Offensive rebounding (crash vs get back) |

**Tournament Mode (new instance):**

- **Location:** `BackEnd/tournament/tournament_manager.py` — `create_tournament()` builds each of the **8** teams’ embedded objects.
- **Initialization:** Same pattern as Franchise — **all keys in the table above are set to `2`** for every team. (No weighted randomization at tournament creation.)

**Single Game Mode:**

- **Location:** `BackEnd/models/team_manager.py` — `TeamManager._init_strategy_settings()`.
- **Initialization:** **Weighted random** per key (not all 2). Summary:
  - **`offense`**, **`fast_breaks`**, **`defense`**: 5% / 15% / **60%** / 15% / 5% for values 0–4 (emphasis on 2).
  - **`inside`**, **`attack`**, **`outside`**: uniform **1–4** (never 0).
  - **`aggression`**: 10% / 20% / **40%** / 20% / 10% for 0–4.
  - **`hc_trap`**, **`fc_press`**: shared draw — 34% / 40% / 20% / 5% / 1% for 0–4.
  - **`rebounding`**: 5% / 10% / 15% / **30%** / **40%** for 0–4.
  - **`tempo`**: `TeamManager.init_tempo_random()` (not fixed at 2).
  - **`play_calling`**: weighted like offense/fast_breaks/defense — present in this default dict for Single Game CPU path; **Franchise and Tournament FTD/tournament seeds do not** set `play_calling` at instance init (only what’s in their explicit `strategy_settings` blobs).

When a team is constructed with a **non-empty** `strategy_settings` dict from the DB (Franchise/Tournament), `TeamManager.__init__` merges it with `_init_strategy_settings()` defaults so any missing keys are filled.

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
- `BackEnd/api/gameplan_routes.py` - `initialize_playbook_settings()` (lines 206-378) - Playbook settings initialization; `get_default_settings()` - default strategy keys for API/merges
- `BackEnd/models/franchise_manager.py` - FTD `strategy_settings` (all keys at 2) on `initialize_season()`
- `BackEnd/tournament/tournament_manager.py` - per-team `strategy_settings` (all keys at 2) on `create_tournament()`
- `BackEnd/models/team_manager.py` - `_init_strategy_settings()` - Single Game weighted defaults; merge behavior when DB provides partial settings

**Franchise Mode New Season Schedule Logic**
At the start of any new season in Franchise mode we will build team schedules for all 128 teams with teh following logic:
-Each team will schedule 26 regular season games
  - 14 conference games, 2 against each conference opponent, 1 home and 1 away
  - 8 region games, 1 against each team in the sister conference in their region (4 home and 4 away). Home / away assignments will be randomly chosen for the first season in teh franchise instnace, then will rotate for each subsequent season. So if Morristown from Conference A1 plays at home against Crickstown from Conferecne A2 in season 1, Morristown will play away against Crickstown in season 2, home against Crickstown in season 3, away against Crickstown in season 4, etc.
  - 4 out-of-region games (2 home and 2 away), the four out-of-region opponents can be any team that is not in their region, radomly chosen. Home away assignments will be randomly chosen.

Rules
- All teams must have 13 home game and 13 away games in the regular season
