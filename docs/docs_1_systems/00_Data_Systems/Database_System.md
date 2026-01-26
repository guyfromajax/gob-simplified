# Database System ✅ **COMPLETE** (January 2025)

## Base Constants

**Purpose:** Documents the MongoDB database structure, collections, and document schemas used across all game modes.

**Core Collections:**
- `plays` - Universal offensive play definitions
- `defenses` - Universal defensive playcall definitions
- `teams` - Universal team baseline data
- `players` - Universal player baseline data
- `games` - Single Game mode documents
- `tournaments` - Tournament mode documents
- `franchises` - Franchise mode documents
- `training_logs` - Historical training sessions

**Key Principles:**
- **Reference-Based Architecture**: Team documents store references to universal collections, not full data
- **Universal Collections**: Source of truth for baseline data (plays, defenses, teams, players)
- **Mode Documents**: Store mode-specific and evolved data (game stats, training improvements, team/player evolution)

## System Flow

1. **Universal Collections**: Store baseline definitions (plays, defenses, teams, players)
2. **Mode Initialization**: Copy baseline data from universal collections to mode documents
3. **Reference Storage**: Team documents store play/defense IDs, not full skeletons
4. **Data Evolution**: Training and gameplay update mode-specific data
5. **Persistence**: Changes saved to appropriate mode document

## Long Form Documentation

### Overview

The Database System uses a reference-based architecture where universal collections store baseline definitions, and mode documents store references and evolved data. This dramatically reduces document size (~95% reduction) while maintaining full functionality.

**Key Design Patterns:**
- **Universal Collections**: Single source of truth for baseline data
- **Reference-Based Storage**: Team documents store play/defense IDs, fetch full data when needed
- **Mode-Specific Evolution**: Training and gameplay modify data in mode documents, not universal collections

---

### Universal Plays Collection

**Location:** MongoDB `plays` collection  
**Purpose:** Store offensive play definitions with full skeleton data

#### Play Document Structure

**Core Fields:**
- `_id` (ObjectId) - Unique MongoDB document ID
- `name` (str) - Play name (e.g., "4-1 Motion", "3-2 Motion")
- `play_type` (str) - "motion" or "set_play"
- `play_focus` (str | null) - "inside", "attack", "outside", "balanced" (Set Plays only), or `null` (Motion Plays)
- `skeletons` (dict) - Full skeleton data with animation steps
- `copy` (dict | null) - Optional descriptive text for play details page (`copy_1`, `copy_2`, `copy_3`)

**Effectiveness, Cloaking, and Momentum Fields:**
- `effectiveness` (float) - Play effectiveness score (default: `0`)
- `cloaking` (float) - Cloaking modifier (default: `0`)
- `momentum` (integer) - Momentum score (default: `0`)

**Stats Fields (Optional):**
- `game_stats` (dict) - Game-level usage statistics
- `season_stats` (dict) - Season-level usage statistics

#### Example Play Document

```json
{
  "_id": ObjectId("..."),
  "name": "4-1 Motion",
  "play_type": "motion",
  "play_focus": null,
  "effectiveness": 0,
  "cloaking": 0,
  "momentum": 0,
  "skeletons": {
    "base_loop": {
      "steps": [...],
      "complete": true
    }
  },
  "copy": {
    "copy_1": "Description text...",
    "copy_2": "More description...",
    "copy_3": "Additional details..."
  }
}
```

---

### Universal Defenses Collection

**Location:** MongoDB `defenses` collection  
**Purpose:** Store defensive playcall definitions with zone configurations

#### Defense Document Structure

**Core Fields:**
- `_id` (ObjectId) - Unique MongoDB document ID
- `defense_id` (str) - Unique defense identifier (e.g., "man", "2-3-zone", "3-2-zone", "1-3-1-zone", "base-man")
- `defense_type` (str) - "Man" or "Zone"
- `name` (str) - Defense display name (e.g., "Man-to-Man", "2-3 Zone", "Base Man")
- `description` (str) - Defense description text

**Effectiveness, Cloaking, and Momentum Fields:**
- `effectiveness` (float) - Defense effectiveness score (default: `0`)
- `cloaking` (float) - Cloaking modifier (default: `0`)
- `momentum` (integer) - Momentum score (default: `0`)

**Zone-Specific Fields (Zone defenses only):**
- `zone_definitions` (dict | null) - Zone positioning configurations
  - `normal` - Default zone positions
  - `lower_shift` - Zone positions when ball is in lower areas
  - `upper_shift` - Zone positions when ball is in upper areas
  - Additional shifts for 1-3-1 zone (`lower_corner_shift`, `upper_corner_shift`)
  - `null` for Man defenses
- `shift_triggers` (dict | null) - Ball locations that trigger zone shifts
  - Maps shift names to arrays of location strings
  - `null` for Man defenses

**Stats Fields:**
- `game_stats` (dict) - Game-level usage and success tracking
- `season_stats` (dict) - Season-level usage and success tracking

#### Example Defense Document

```json
{
  "_id": ObjectId("..."),
  "defense_id": "2-3-zone",
  "defense_type": "Zone",
  "name": "2-3 Zone",
  "description": "Standard 2-3 zone defense with two guards up top and three players in the paint",
  "effectiveness": 0.0,
  "cloaking": 0,
  "momentum": 0,
  "zone_definitions": {
    "normal": {...},
    "lower_shift": {...},
    "upper_shift": {...}
  },
  "shift_triggers": {
    "lower_shift": ["lower wing", "lower midCorner", "lower corner"],
    "upper_shift": ["upper wing", "upper midCorner", "upper corner"]
  },
  "game_stats": {...},
  "season_stats": {...}
}
```

---

### Universal Teams Collection

**Location:** MongoDB `teams` collection  
**Purpose:** Source of truth for baseline team data

#### Team Document Structure

**Core Fields:**
- `_id` (ObjectId) - Unique MongoDB document ID
- `name` (str) - Team name (e.g., "Morristown", "Bentley Truman")
- `team_id` (str) - Unique team identifier (e.g., "MORRISTOWN", "BENTLEY_TRUMAN")
- `primary_color` (str) - Primary team color (hex format)
- `secondary_color` (str) - Secondary team color (hex format)
- `mascot` (str) - Team mascot name
- `player_ids` (array) - Array of player ObjectIds for roster

**Team Attributes (Optional):**
- `shot_threshold` (int) - Shot attempt threshold (range: -10 to 190)
- `discipline` (int) - Turnover modifier (range: -10 to 10)
- `fight` (int) - Foul modifier (range: -10 to 10)
- `rebound_modifier` (float) - Rebound effectiveness modifier (range: 0.0-0.4)
- `offensive_efficiency` (int) - Offensive efficiency rating (range: -10 to 10)
- `team_chemistry` (int) - Team chemistry rating (range: 7-25)
- `defensive_efficiency` (int) - Defensive efficiency rating (range: -10 to 10)
- `fb_efficiency` (int) - Fast break efficiency rating (range: -10 to 10)
- `pt_efficiency` (int) - Press/Trap efficiency rating (range: -10 to 10)
- `fb_opp_modifier` (int) - Fast break opponent modifier (range: -10 to 10)
- `pt_opp_modifier` (int) - Press/Trap opponent modifier (range: -10 to 10)

**Coaching Attributes:**
- `coaching` (dict) - Coaching attributes object (see Coaching Attributes System below)

**Note:** Team attributes in the universal collection are optional. If not present, they're generated randomly when team objects are created via `TeamManager.init_team_attributes(mode)`.

---

### Reference-Based Architecture

**Principle:** Team documents store only **references** to universal collections, not full data.

**Team Plays Storage:**
- Structure: `{play_name: {play_id: "...", effectiveness: 0, momentum: 0, cloaking: 0, game_stats: {...}, season_stats: {...}}}`
- `play_id` - Reference to universal play document `_id`
- Full skeleton data fetched from `plays` collection when needed

**Team Defenses Storage:**
- Structure: `{defense_name: {used: 0, success: 0, effectiveness: 0, momentum: 0, cloaking: 0, game_stats: {...}, season_stats: {...}}}`
- No full zone definitions stored - fetched from `defenses` collection when needed

**Benefits:**
- **~95% Document Size Reduction**: Full skeletons not stored in team documents
- **Single Source of Truth**: Play/defense definitions updated once in universal collection
- **Efficient Storage**: Only references and per-team stats stored

**Field Initialization Scripts:**
- `scripts/add_effectiveness_cloaking_fields.py` - Adds `effectiveness` and `cloaking` fields
- `scripts/add_momentum_field_to_plays_defenses.py` - Adds `momentum` field

---

### Team Objects (Mode Documents)

**Location:** Mode-specific documents (`games`, `tournaments`, `franchises` collections)  
**Path:** `{mode_document}.teams.{team_id}` or `{mode_document}.franchise_teams.{team_id}` (Franchise)

#### Team Object Structure

**Base Fields (From Universal Teams Collection):**
- Team attributes are copied from universal `teams` collection or generated randomly
- See Universal Teams Collection section above for attribute list

**Instance Fields:**
- `is_home_team` (bool) - Whether this team is the home team (runtime only, not persisted)
- `is_user_team` (bool) - Whether this is the user's team (runtime only, not persisted)

**Player and Lineup Data:**
- `players` (dict) - Full roster dictionary: `{player_id: Player object}` (runtime only)
- `lineup` (dict) - Active lineup dictionary: `{position: Player object}` (runtime only)
  - Positions: `"PG"`, `"SG"`, `"SF"`, `"PF"`, `"C"`

**Game State Fields (Runtime Only):**
- `points` (int) - Current game score
- `points_by_quarter` (list) - Points scored per quarter
- `team_fouls` (int) - Current team foul count
- `timeouts` (int) - Remaining timeouts
- `stats` (dict) - Team-level statistics dictionary
- `team_stats` (dict) - Team-level tracking stats

**Team Attributes (Persisted):**

Initialized via `TeamManager.init_team_attributes(mode)` with mode-specific ranges:

**Single Game & Tournament Mode:**
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

**Franchise Mode:**
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

**Note:** `momentum_score` exists in some legacy code paths but is NOT initialized in the standard `init_team_attributes()` flow.

**Strategy Settings (Persisted):**

Initialized via `TeamManager._init_strategy_settings()` with weighted randomization (0-4 scale):

- `offense` - Weighted: 5% for 0/4, 15% for 1/3, 60% for 2
- `inside` - Uniform: `random.randint(1, 4)` (never zero)
- `attack` - Uniform: `random.randint(1, 4)` (never zero)
- `outside` - Uniform: `random.randint(1, 4)` (never zero)
- `tempo` - Per-game randomization via `init_tempo_random()`
- `fast_breaks` - Weighted: 5% for 0/4, 15% for 1/3, 60% for 2
- `play_calling` - Weighted: 5% for 0/4, 15% for 1/3, 60% for 2
- `defense` - Weighted: 5% for 0/4, 15% for 1/3, 60% for 2
- `aggression` - Weighted: 5% for 0/4, 15% for 1/3, 60% for 2
- `hc_trap` - Special weighted: 10% for 0, 40% for 1, 35% for 2, 10% for 3, 5% for 4
- `fc_press` - Special weighted: 10% for 0, 40% for 1, 35% for 2, 10% for 3, 5% for 4
- `rebounding` - Weighted: 5% for 0/4, 15% for 1/3, 60% for 2

**Strategy Calls (User Overrides):**
- `offense_call` (str or None) - Play name string or None (user override persists until used)
- `defense_call` (str or None) - "Man", "Zone", or None (user override persists until used)
- `aggression_override` (str or None) - "normal", "aggressive", "passive", or None (temporary override)
- `tempo_override` (str or None) - "slow", "normal", "fast", or None (temporary override)
- `press_override` (str or None) - Future: FCP override
- `trap_override` (str or None) - Future: HCT override

**Playcall Trackers:**
- `playcall_tracker` (dict) - Offensive playcall usage tracker: `{playcall_name: count}`
- `defense_playcall_tracker` (dict) - Defensive playcall usage tracker: `{"Man": 0, "Zone": 0}`

**Scouting Data (Persisted):**

Initialized via `TeamManager._init_scouting_data()` with comprehensive tracking structure:

**Offense Scouting:**
- `Fast_Break_Entries` - Fast break attempt count
- `Fast_Break_Success` - Fast break success count
- `Playcalls` - Nested structure for Motion and Set plays:
  - `Motion` / `Set` buckets with `overall`, `inside`/`attack`/`outside`, `vs_man`/`vs_zone`/etc.
  - `Cumulative` - Cross-play type focus tracking
- `last_play_by_category` - Tracks last play run for each category

**Defense Scouting:**
- `Man` / `2-3 Zone` / `3-2 Zone` / `1-3-1 Zone` - Defense type tracking:
  - `used` - Usage count
  - `success` - Success count
  - `effectiveness` (float) - Per-team effectiveness score (training-impacted, initialized to `0.0`)
  - `momentum` (int) - Per-team momentum score (training-impacted, initialized to `0`)
  - `cloaking` (int) - Per-team cloaking modifier (training-impacted, initialized to `0`)
  - `game_stats` - Game-level stats
  - `season_stats` - Season-level stats (tournament/franchise modes)
- `vs_Fast_Break` - Fast break defense tracking
- `FCP` / `HCT` - Pressure defense tracking

**Plays Data (Persisted):**

Initialized via `TeamManager._init_plays_from_universal(mode)` with reference-based structure:

**Structure:** `{play_name: play_data}`

Each play entry contains:
- `play_id` (str) - Reference to universal play document `_id`
- `name` (str) - Play name
- `play_type` (str) - "motion" or "set_play"
- `play_focus` (str) - "inside", "attack", or "outside" (for set plays)
- `effectiveness` (float) - Per-team effectiveness score (training-impacted, initialized from universal play)
- `momentum` (int) - Per-team momentum score (training-impacted, initialized from universal play)
- `cloaking` (int) - Per-team cloaking modifier (training-impacted, initialized from universal play)
- `game_stats` (dict) - Game-level tracking (times_run, shot_attempts, made_shots, turnovers, etc.)
- `season_stats` (dict) - Season-level tracking (tournament/franchise modes only)

**Note:** Plays data does NOT include full skeletons - skeletons are fetched from the universal `plays` collection when needed.

**Playbook Settings (Persisted):**

Initialized via `initialize_playbook_settings()` with even distribution:

- `motion` (dict) - Motion play percentages: `{play_name: percentage}` (evenly distributed)
- `set_play_inside` (dict) - Inside set play percentages (evenly distributed)
- `set_play_attack` (dict) - Attack set play percentages (evenly distributed)
- `set_play_outside` (dict) - Outside set play percentages (evenly distributed)
- `zone_defense` (dict) - Zone defense percentages (evenly distributed)
- `man_defense` (dict) - Man defense percentages (currently only "Man": 100)
- `slot_assignments` (dict) - Playcall Center slot assignments (slots 1-6)
- `motion_dropdowns` (dict) - Motion play dropdown selections (Inside/Attack/Outside)
- `position_filters` (dict) - Position filter button assignments

**Coaching Attributes (Persisted):**

**Location:** Universal `teams` collection - `coaching` field (copied to team objects)

**Structure:**
```json
{
  "coaching": {
    "effectiveness": 0,
    "training_focus_list": [],
    "authoritarian": {
      "score": 0,
      "momentum": 0
    },
    "systems coach": {
      "score": 0,
      "momentum": 0
    },
    "player maximizer": {
      "score": 0,
      "momentum": 0
    },
    "culture builder": {
      "score": 0,
      "momentum": 0
    }
  }
}
```

**Field Descriptions:**

**Top-Level Fields:**
- `effectiveness` (integer) - Overall coaching effectiveness score (initialized to `0`)
- `training_focus_list` (array of strings) - Historical list of training focus selections (initialized as `[]`)

**Archetype Objects:**
Each of the four coaching archetypes has:
- `score` (integer) - Performance score for this archetype (initialized to `0`)
- `momentum` (integer) - Momentum score for this archetype (initialized to `0`)

**Archetypes:**
1. `authoritarian` - Discipline, Rebounding, Execution, Teamwork focus
2. `systems coach` - Offense, Defense, Fast Breaks, Presses/Traps focus
3. `player maximizer` - Top 3 Attributes, Attributes 4-6, Custom, Be Opportunistic focus
4. `culture builder` - Inspire, Community Engagement, Teamwork, Build Confidence focus

**Initialization:**
- Script: `scripts/add_coaching_field_to_teams.py`
- Ensures all teams in universal `teams` collection have complete coaching structure
- Initializes all fields with default values (0 for integers, [] for arrays)

**Integration:**
- Training focus selections can update archetype scores and momentum
- Training effectiveness can influence overall coaching effectiveness
- Historical training focus list tracks coaching style evolution

---

### Initialization Methods

**Team Object Creation:**
- `TeamManager.__init__()` - Main initialization method
- `_load_roster()` - Loads roster from roster files
- `_load_lineup()` - Returns empty dictionary (populated later)
- `_init_team_attributes()` - Generates random team attributes (mode-specific)
- `_init_strategy_settings()` - Generates random strategy settings (weighted distribution)
- `_init_scouting_data()` - Creates comprehensive scouting data structure
- `_init_plays_from_universal(mode)` - Fetches plays from universal collection, creates references
- `_create_defense_structure_template()` - Creates standard defense structure template

**Team Attribute Initialization:**
- `TeamManager.init_team_attributes(mode)` - Static method for mode-specific attribute initialization
- Uses universal `teams` collection as source of truth
- Falls back to random generation if attributes not present

---

### Key Files

**Backend:**
- `BackEnd/models/team_manager.py` - `TeamManager` class (lines 8-468)
  - `__init__()` - Main initialization (lines 9-84)
  - `_init_team_attributes()` - Team attribute initialization (lines 228-242)
  - `_init_strategy_settings()` - Strategy settings initialization (lines 130-182)
  - `_init_scouting_data()` - Scouting data initialization (lines 188-329)
  - `_init_plays_from_universal()` - Plays initialization (lines 331-383)
  - `_create_defense_structure_template()` - Defense template creation (lines 144-186)
  - `init_team_attributes()` - Static method for mode-specific attributes (lines 185-226)

- `BackEnd/api/gameplan_routes.py` - `ensure_team_objects_exist()` (lines 152-299)
  - Creates team objects in mode documents
  - Initializes team attributes, plays, scouting data, playbook settings

- `BackEnd/db.py` - MongoDB connection and collection definitions
  - `plays_collection` - Universal plays collection
  - `defenses_collection` - Universal defenses collection
  - `teams_collection` - Universal teams collection

**Scripts:**
- `scripts/add_effectiveness_cloaking_fields.py` - Adds `effectiveness` and `cloaking` fields to plays/defenses
- `scripts/add_momentum_field_to_plays_defenses.py` - Adds `momentum` field to plays/defenses
- `scripts/add_coaching_field_to_teams.py` - Adds `coaching` field to universal teams collection

**Reference Documentation:**
- `docs/docs_1_systems/06_GMO_Supporting_Systems/Team_Attribute_Mgmt_System.md` - Team attribute management details
- `docs/docs_1_systems/06_GMO_Supporting_Systems/Mode_Init_System.md` - Mode initialization system
- `docs/docs_1_systems/03_Data_Persistence/Data_Persistence_System.md` - Data persistence across modes

