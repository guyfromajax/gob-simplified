# Team Attribute Management System ✅ **COMPLETE** (January 2025)

## Base Constants

1. **Core Team Attributes**:
   - `shot_threshold` - Shot attempt threshold (range: 10 to 210)
   - `discipline` - Turnover modifier (formerly `turnover_modifier`)
   - `fight` - Foul modifier (formerly `foul_modifier`)
   - `rebound_modifier` - Rebound effectiveness modifier (range: 0.0-0.4)
   - `offensive_efficiency` - Offensive efficiency rating
   - `team_chemistry` - Team chemistry rating
   - `defensive_efficiency` - Defensive efficiency rating
   - `fb_efficiency` - Fast break efficiency rating
   - `pt_efficiency` - Press/Trap efficiency rating
   - `fb_opp_modifier` - Fast break opponent modifier
   - `pt_opp_modifier` - Press/Trap opponent modifier

2. **Mode-Specific Attribute Ranges**:
   - **Single Game & Tournament**: Most attributes use `random.randint(-10, 10)`, `team_chemistry=random(7-25)`, `rebound_modifier=random(0.0-0.4)`
   - **Franchise**: Most attributes use `random.randint(-1, 1)`, `team_chemistry=random(7-10)`, `rebound_modifier=0.2` (fixed)

3. **Initialization Source**: Universal `teams` collection in MongoDB → Team objects → Fallback to `TeamManager.init_team_attributes()`

4. **Attribute clamp ranges**: See **Attribute_Clamp_System.md** for absolute min/max clamp values for all player and team attributes.

## System Flow

1. **Team Object Creation**: Attributes copied from universal `teams` collection
2. **Missing Attributes**: Initialized from universal collection or generated randomly
3. **Attribute Updates**: Training system updates attributes in Franchise/Tournament modes
4. **Persistence**: Changes saved to appropriate document based on game mode

## Long Form Documentation

### Overview

The Team Attribute Management System handles the initialization, storage, and updates of team attributes across all game modes. Team attributes control various aspects of team performance, including shooting tendencies, defensive capabilities, fast break efficiency, and team chemistry.

**Location:** `BackEnd/models/team_manager.py`, `BackEnd/api/gameplan_routes.py`  
**Status:** ✅ Fully implemented for all game modes  
**Key Function:** `TeamManager.init_team_attributes(mode)`

### Attribute List

All team attributes are stored in team objects across all game modes:

**Core Attributes:**
- `shot_threshold` - Shot attempt threshold (range: 10 to 210, center at 110 for pill display)
- `discipline` - Turnover modifier (formerly `turnover_modifier`)
- `fight` - Foul modifier (formerly `foul_modifier`)
- `rebound_modifier` - Rebound effectiveness modifier (range: 0.0-0.4, center at 0.2 for pill display)
- `offensive_efficiency` - Offensive efficiency rating
- `team_chemistry` - Team chemistry rating

**Additional Attributes (January 2025):**
- `defensive_efficiency` - Defensive efficiency rating
- `fb_efficiency` - Fast break efficiency rating
- `pt_efficiency` - Press/Trap efficiency rating
- `fb_opp_modifier` - Fast break opponent modifier
- `pt_opp_modifier` - Press/Trap opponent modifier

**Note:** `momentum_score` exists in some legacy code paths but is NOT initialized in the standard `init_team_attributes()` flow. It may be set manually in specific scenarios but is not part of the standard team attribute initialization.

### Default Values

**Mode-Specific Initialization:**

**Single Game & Tournament Mode:**
- Attribute range: `random.randint(-10, 10)` for:
  - `discipline`, `fight`, `offensive_efficiency`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`
- `shot_threshold`: `random.randint(10, 210)` (clamped to same range; see Attribute_Clamp_System.md)
- `team_chemistry`: `random.randint(7, 25)`
- `rebound_modifier`: `random.randint(0, 40) / 100.0` (random 0.0-0.4 in 0.01 increments)

**Franchise Mode:**
- Attribute range: `random.randint(-1, 1)` for:
  - `discipline`, `fight`, `offensive_efficiency`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`
- `shot_threshold`: `random.randint(100, 120)` (within clamp range 10–210; see Attribute_Clamp_System.md)
- `team_chemistry`: `random.randint(7, 10)` (tighter range for more controlled progression)
- `rebound_modifier`: `0.2` (fixed center value)

**New Attributes**: All default to `0` if not present in the universal collection.

### Attribute Initialization

**Initialization Flow:**

1. **First Access**: Team attributes are copied from the **universal `teams` collection** in MongoDB (the core/master team data)
2. **Missing Attributes**: If attributes don't exist in team object, they're initialized from the **universal `teams` collection**
3. **Fallback**: If the **universal `teams` collection** doesn't have attributes, `TeamManager.init_team_attributes(mode)` generates random values based on the game mode

**Implementation:**
- **Location**: `BackEnd/models/team_manager.py` - `init_team_attributes()` (lines 185-226)
- **Method**: Static method that accepts `mode` parameter ("single", "tournament", or "franchise")
- **Returns**: Dictionary of team attributes with mode-specific randomization

### Universal Teams Collection

The **universal `teams` collection** in MongoDB (`db.teams`) is the source of truth for initial team attribute values. This collection contains the master/base team data that is copied when team objects are first created in any game mode. It stores:

- Team metadata (name, colors, mascot, team_id)
- Base team attributes (`shot_threshold`, `discipline`, `fight`, `rebound_modifier`, `offensive_efficiency`, `team_chemistry`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`)
- Coaching attributes object (effectiveness, training focus list, archetype scores and momentum)
- Initial playbook and strategy settings (if any)

When team objects are created in Single Game, Tournament, or Franchise modes, they copy attribute values from this universal collection. If attributes don't exist in the universal collection, they default to `0` (for new attributes) or are generated randomly (for core attributes via `init_team_attributes()`).

### Attribute Updates

**Training System:**
- **Franchise Mode**: Team attributes can be updated through training
  - **Location**: `BackEnd/api/franchise_routes.py` - `run_franchise_training()` (lines 1045-1061)
  - **Process**: Training changes are saved to `franchises.{franchise_id}.franchise_teams.{team_id}.{attribute_name}`
  - **Example**: `franchises.{franchise_id}.franchise_teams.{team_id}.defensive_efficiency = new_value`
- **Tournament Mode**: Team attributes can be updated through training (future implementation)
- **Single Game Mode**: Team attributes are not updated during gameplay (training not implemented)

**Gameplay:**
- Team attributes are read-only during gameplay (not modified by game events)
- Attributes are used in calculations but remain constant throughout a game

**Persistence:**
- Changes persist to the appropriate document based on game mode:
  - **Single Game**: `games.{game_id}.teams.{team_id}`
  - **Tournament**: `tournaments.{tournament_id}.teams.{team_id}`
  - **Franchise**: `franchises.{franchise_id}.franchise_teams.{team_id}`

### Attribute Name Migration

**Historical Note:**
- `turnover_modifier` was renamed to `discipline` (January 2025)
- `foul_modifier` was renamed to `fight` (January 2025)
- A migration script (`scripts/migrate_foul_turnover_to_aggression_discipline.py`) was used to update existing database documents

### Key Files

- `BackEnd/models/team_manager.py` - `init_team_attributes()` (lines 185-226)
  - Static method for initializing team attributes with mode-specific ranges
- `BackEnd/api/gameplan_routes.py` - `ensure_team_objects_exist()` (lines 152-299)
  - Creates team objects and initializes attributes from universal collection
- `BackEnd/api/api.py` - `load_team_attributes_from_doc()` (lines 196-244)
  - Loads team attributes from mode-specific documents
- `BackEnd/api/franchise_routes.py` - `run_franchise_training()` (lines 1045-1061)
  - Updates team attributes through training system
- `BackEnd/models/training_execution_v2.py` - `_apply_team_training_points()` (lines 685-726)
  - Applies training point allocations to team attributes

