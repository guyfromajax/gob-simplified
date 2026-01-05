# Offense & Defense Collections ✅ **COMPLETE** (January 2025)

## Base Constants

**Purpose:** Documents the structure and usage of the universal MongoDB collections that store offensive plays and defensive playcalls.

**Core Collections:**
- `plays` - Universal offensive play definitions (Set Plays and Motion Plays)
- `defenses` - Universal defensive playcall definitions (Man and Zone defenses)

**Key Principles:**
- **Universal Library**: Single source of truth for all play and defense definitions
- **Reference-Based Storage**: Team documents store only references (play_id), not full skeletons
- **Size Reduction**: ~95% document size reduction by storing references instead of full data
- **Full Data on Demand**: Skeletons and zone definitions fetched from collections when needed

**Field Initialization Scripts:**
- `scripts/add_effectiveness_cloaking_fields.py` - Adds `effectiveness` and `cloaking` fields
- `scripts/add_momentum_field_to_plays_defenses.py` - Adds `momentum` field

**Key Files:**
- `BackEnd/db.py` - MongoDB connection and collection definitions
- `BackEnd/api/play_routes.py` - API endpoints for play CRUD operations

## System Flow

1. **Collection Storage**: Full play/defense definitions stored in universal collections
2. **Team References**: Team documents store only `play_id` references and per-team stats
3. **Runtime Fetching**: Full skeletons/zone definitions fetched when needed for gameplay
4. **Per-Team Evolution**: Training and gameplay modify per-team effectiveness/momentum/cloaking
5. **Universal Baseline**: Universal collections maintain baseline effectiveness/momentum/cloaking

## Long Form Documentation

### Overview

The Offense & Defense Collections system uses a reference-based architecture where universal MongoDB collections store complete play and defense definitions, while team documents store only references and per-team statistics. This dramatically reduces document size (~95% reduction) while maintaining full functionality.

**Location:** MongoDB `plays` and `defenses` collections  
**Status:** ✅ Fully implemented - All plays and defenses stored with required fields

**Benefits:**
- ✅ **Efficient Storage**: Team documents ~95% smaller (references vs full skeletons)
- ✅ **Single Source of Truth**: Play/defense definitions updated once in universal collection
- ✅ **Per-Team Evolution**: Teams can have different effectiveness/momentum/cloaking for same play/defense
- ✅ **Scalability**: Easy to add new plays/defenses without bloating team documents

---

### Universal Plays Collection

**Location:** MongoDB `plays` collection  
**Purpose:** Store offensive play definitions with full skeleton data

#### Play Document Structure

**Core Fields:**
- `_id` (ObjectId) - Unique MongoDB document ID
- `name` (str) - Play name (e.g., "4-1 Motion", "3-2 Motion", "Base Post Play")
- `play_type` (str) - "motion" or "set_play"
- `play_focus` (str | null) - "inside", "attack", "outside", "balanced" (Set Plays only), or `null` (Motion Plays)
- `skeletons` (dict) - Full skeleton data with animation steps
  - **Motion Plays:** `{"base_loop": {steps: [...], complete: true}}`
  - **Set Plays:** `{"successful": {...}, "mid_play_change": {...}, "contested": {...}, "broken": {...}}`
- `copy` (dict | null) - Optional descriptive text for play details page (`copy_1`, `copy_2`, `copy_3`)

**Effectiveness, Cloaking, and Momentum Fields:**
- `effectiveness` (float) - Play effectiveness score (default: `0`)
  - Used for calculating play success rates and matchup evaluations
  - Can be modified by training, in-game performance, and coaching focus
- `cloaking` (float) - Cloaking modifier (default: `0`)
  - Used for defensive recognition and counter-play adjustments
  - Higher values make plays harder for defenses to recognize and counter
- `momentum` (integer) - Momentum score (default: `0`)
  - Tracks recent performance trends for the play
  - Can increase or decrease based on success/failure rates
  - Used to adjust play selection probabilities dynamically

**Stats Fields (Optional):**
- `game_stats` (dict) - Game-level usage statistics (if tracked at collection level)
- `season_stats` (dict) - Season-level usage statistics (if tracked at collection level)

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
  - Used for calculating defensive success rates and matchup evaluations
  - Can be modified by training, in-game performance, and coaching focus
- `cloaking` (float) - Cloaking modifier (default: `0`)
  - Used for offensive recognition and counter-play adjustments
  - Higher values make defenses harder for offenses to recognize and counter
- `momentum` (integer) - Momentum score (default: `0`)
  - Tracks recent performance trends for the defense
  - Can increase or decrease based on success/failure rates
  - Used to adjust defense selection probabilities dynamically

**Zone-Specific Fields (Zone defenses only):**
- `zone_definitions` (dict | null) - Zone positioning configurations
  - `normal` - Default zone positions
  - `lower_shift` - Zone positions when ball is in lower areas
  - `upper_shift` - Zone positions when ball is in upper areas
  - Additional shifts for 1-3-1 zone (`lower_corner_shift`, `upper_corner_shift`)
  - `null` for Man defenses
- `shift_triggers` (dict | null) - Ball locations that trigger zone shifts
  - Maps shift names to arrays of location strings
  - Example: `{"lower_shift": ["lower wing", "lower midCorner", "lower corner"]}`
  - `null` for Man defenses

**Stats Fields:**
- `game_stats` (dict) - Game-level usage and success tracking
  - `used` (int) - Number of times defense was used
  - `success` (int) - Number of successful defensive stops
  - Granular tracking: `vs_motion`, `vs_set`, `vs_inside`, `vs_attack`, `vs_outside`, etc.
- `season_stats` (dict) - Season-level usage and success tracking (same structure as `game_stats`)

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

### Field Initialization

**Scripts:**
- `scripts/add_effectiveness_cloaking_fields.py` - Adds `effectiveness` and `cloaking` fields to all plays and defenses
- `scripts/add_momentum_field_to_plays_defenses.py` - Adds `momentum` field to all plays and defenses

**Required Fields:**
All plays and defenses must have these fields initialized:
- `effectiveness: 0` - Play/defense effectiveness score
- `cloaking: 0` - Cloaking modifier
- `momentum: 0` - Momentum score

**Usage:**
```bash
python scripts/add_effectiveness_cloaking_fields.py
python scripts/add_momentum_field_to_plays_defenses.py
```

---

### Reference-Based Architecture

**Principle:** Team documents store only **references** to universal collections, not full data.

#### Team Plays Storage

**Structure:** `{play_name: {play_id: "...", effectiveness: 0, momentum: 0, cloaking: 0, game_stats: {...}, season_stats: {...}}}`

- `play_id` (str) - Reference to universal play document `_id` (the "library card")
- `effectiveness` (float) - Per-team effectiveness score (initialized from universal, can be modified by training)
- `momentum` (int) - Per-team momentum score (initialized from universal, can be modified by training)
- `cloaking` (int) - Per-team cloaking modifier (initialized from universal, can be modified by training)
- `game_stats` (dict) - Game-level tracking (times_run, shot_attempts, made_shots, turnovers, etc.)
- `season_stats` (dict) - Season-level tracking (tournament/franchise modes only)

**Full skeleton data fetched from `plays` collection when needed for gameplay.**

#### Team Defenses Storage

**Structure:** `{defense_name: {used: 0, success: 0, effectiveness: 0, momentum: 0, cloaking: 0, game_stats: {...}, season_stats: {...}}}`

- No `defense_id` reference stored (defense identified by name)
- `effectiveness` (float) - Per-team effectiveness score (initialized to `0.0`, can be modified by training)
- `momentum` (int) - Per-team momentum score (initialized to `0`, can be modified by training)
- `cloaking` (int) - Per-team cloaking modifier (initialized to `0`, can be modified by training)
- `game_stats` (dict) - Game-level stats (attempts, success, ev_scores, lean_scores, vs_motion/set/inside/attack/outside)
- `season_stats` (dict) - Season-level stats (tournament/franchise modes only)

**Full zone definitions fetched from `defenses` collection when needed for gameplay.**

#### Benefits

- **~95% Document Size Reduction**: Full skeletons not stored in team documents
- **Single Source of Truth**: Play/defense definitions updated once in universal collection
- **Per-Team Evolution**: Different teams can have different effectiveness/momentum/cloaking for same play/defense
- **Efficient Storage**: Only references and per-team stats stored in team documents
- **Scalability**: Easy to add new plays/defenses without bloating team documents

---

### Per-Team vs Universal Values

**Universal Collections:**
- Store baseline `effectiveness`, `cloaking`, and `momentum` values (default: `0`)
- These are the "library" values that all teams start with

**Team Documents:**
- Store per-team `effectiveness`, `cloaking`, and `momentum` values
- Initial values copied from universal collection when team object is created
- Per-team values can be modified by:
  - Training system (based on playbook settings and game plan mix)
  - In-game performance (future implementation)
  - Coaching focus selections (future implementation)

**Result:**
- Different teams can have different effectiveness/momentum/cloaking for the same play/defense
- Allows for team-specific play/defense evolution and specialization
- Universal collection maintains baseline values for new teams

---

### Key Files

**Backend:**
- `BackEnd/db.py` - MongoDB connection and collection definitions
  - `plays_collection` - Universal plays collection
  - `defenses_collection` - Universal defenses collection
- `BackEnd/api/play_routes.py` - API endpoints for play CRUD operations
- `BackEnd/models/team_manager.py` - `_init_plays_from_universal()` method (lines 331-383)
  - Fetches plays from universal collection
  - Creates reference-based play entries in team objects

**Scripts:**
- `scripts/add_effectiveness_cloaking_fields.py` - Adds `effectiveness` and `cloaking` fields
- `scripts/add_momentum_field_to_plays_defenses.py` - Adds `momentum` field

**Reference Documentation:**
- `docs/docs_1_systems/00_Data_Systems/Database_System.md` - Full database system documentation
- `docs/docs_1_systems/06_GMO_Supporting_Systems/Plays_System.md` - Plays system functionality
- `docs/docs_1_systems/06_GMO_Supporting_Systems/Play_Builder_System.md` - Play Builder documentation

