## Computer Team Game Init System ✅ **COMPLETE** (January 2025)

**Base Constants**

1. **Initialization Method**: `TeamManager._init_strategy_settings()` (lines 130-182)
2. **Code Location**: `BackEnd/models/team_manager.py`
3. **When Called**: During `TeamManager.__init__()` when `strategy_settings` is not provided or is empty
4. **Applies To**: All game modes (Single Game, Tournament, Franchise)
5. **Playbook Settings**: Initialized identically for all teams via `initialize_playbook_settings()` (see `Mode_Init_System.md`)
6. **Strategy Settings Scale**: 0-4 (0 = extreme low, 2 = normal/balanced, 4 = extreme high)
7. **Key Files**:
   - `BackEnd/models/team_manager.py` - `_init_strategy_settings()` (lines 130-182)
   - `BackEnd/api/gameplan_routes.py` - `initialize_playbook_settings()` (lines 206-378)

**System Flow (2 Steps)**

1. **Strategy Settings Initialization**: Computer teams get randomly generated strategy settings using weighted distributions when `strategy_settings` is not provided
2. **Playbook Settings Initialization**: All teams (user and computer) get identical default playbook settings via `initialize_playbook_settings()`

**Long Form Documentation**

### Overview

When computer teams are initialized (for all game modes: Single Game, Tournament, Franchise), their `strategy_settings` are randomly generated using weighted distributions. This ensures most teams play with balanced strategies (value = 2), while some teams have more extreme preferences. Playbook settings are initialized identically for all teams.

**Key Features:**
- Strategy settings use weighted randomization (favors balanced play)
- Different distributions for different setting types
- Playbook settings use even distribution for all teams
- Applies to all game modes consistently

### Strategy Settings Initialization

**Method**: `BackEnd/models/team_manager.py` - `_init_strategy_settings()` (lines 130-182)

**When Called:**
- During `TeamManager.__init__()` when `strategy_settings` parameter is `None` or empty
- Applies to all computer teams in Single Game, Tournament, and Franchise modes
- User teams can override via `strategy_settings` parameter

**Strategy Settings Types:**

#### 1. Weighted Distribution (Most Settings)

**Settings:** `offense`, `fast_breaks`, `play_calling`, `defense`, `aggression` (rebounding uses its own distribution; see below)

**Distribution:** Weighted random that favors balanced play (value = 2)

**Probabilities:**
- **5%** chance for value **0** (extreme low)
- **15%** chance for value **1** (low)
- **60%** chance for value **2** (normal/balanced) ⭐
- **15%** chance for value **3** (high)
- **5%** chance for value **4** (extreme high)

**Implementation:**
```python
weighted_choice = random.choices([0, 1, 2, 3, 4], weights=[5, 15, 60, 15, 5], k=1)[0]
```

#### 2. Weighted Distribution (Rebounding Only)

**Settings:** `rebounding`

**Distribution:** Weighted random that favors higher values (more "get back on D" bias)

**Probabilities:**
- **5%** chance for value **0** (100% crash the boards)
- **10%** chance for value **1**
- **15%** chance for value **2** (50/50)
- **30%** chance for value **3**
- **40%** chance for value **4** (100% get back on D)

**Implementation:**
```python
random.choices([0, 1, 2, 3, 4], weights=[5, 10, 15, 30, 40], k=1)[0]
```

#### 3. Weighted Distribution (Pressure Defense Settings)

**Settings:** `hc_trap`, `fc_press`

**Distribution:** Weighted random that favors lower values (less frequent pressure defense)

**Probabilities:**
- **34%** chance for value **0** (no usage)
- **40%** chance for value **1** (low usage)
- **20%** chance for value **2** (moderate usage)
- **5%** chance for value **3** (high usage)
- **1%** chance for value **4** (extreme usage)

**Implementation:**
```python
trap_press_choice = random.choices([0, 1, 2, 3, 4], weights=[34, 40, 20, 5, 1], k=1)[0]
```

**Note:** Both `hc_trap` and `fc_press` use the same random value (shared choice).

#### 4. Uniform Distribution (Shot Focus Settings)

**Settings:** `inside`, `attack`, `outside`

**Distribution:** Uniform random (1-4, never zero)

**Range:** Random integer from **1 to 4** (inclusive)

**Rationale:** Ensures teams always have some preference for each shot type (never zero)

**Implementation:**
```python
random.randint(1, 4)  # Uniform 1-4 (never zero)
```

#### 5. Tempo Setting

**Setting:** `tempo`

**Special Handling:** NOT initialized in `_init_strategy_settings()`

**Implementation:** Initialized per game (not per team) via `TeamManager.init_tempo_random()`

**Rationale:** Tempo affects time_elapsed calculations and is shared across both teams in a game

### Playbook Settings Initialization

**Method**: `BackEnd/api/gameplan_routes.py` - `initialize_playbook_settings()` (lines 206-378)

**When Called:**
- During team object creation in all three modes
- **Single Game:** `ensure_team_objects_exist()` (lazy initialization)
- **Tournament:** `create_tournament()` (all 8 teams initialized upfront)
- **Franchise:** `initialize_season()` (all 8 teams initialized upfront)

**Initialization:** Identical for all teams (user and computer)

**Default Values:**
- **Percentage Distributions:** Even distribution across all plays in each section
- **Slot Assignments:** Empty `{}`
- **Motion Dropdowns:** Empty `{}`
- **Position Filters:** Pre-populated with Standard and PF plays

**Note:** For detailed playbook settings initialization, see `Mode_Init_System.md` - "Playbook Settings Initialization" section.

### Key Files

**Backend:**
- `BackEnd/models/team_manager.py` - `_init_strategy_settings()` (lines 130-182)
  - Strategy settings initialization with weighted distributions
- `BackEnd/api/gameplan_routes.py` - `initialize_playbook_settings()` (lines 206-378)
  - Playbook settings initialization (shared by all teams)
- `BackEnd/models/team_manager.py` - `TeamManager.__init__()` (lines 39-49)
  - Calls `_init_strategy_settings()` when strategy_settings not provided

### Relationship to Mode Initialization

Computer team initialization is part of the broader Mode Initialization System:
- **Strategy Settings:** Initialized via `_init_strategy_settings()` (computer-specific)
- **Playbook Settings:** Initialized via `initialize_playbook_settings()` (shared by all teams)
- **Team Attributes:** Initialized via `TeamManager.init_team_attributes()` (shared by all teams)

For complete initialization details, see `Mode_Init_System.md`.

