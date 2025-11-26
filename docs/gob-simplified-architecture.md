# GOB-Simplified Architecture Guide for New Engineers

## Overview

GOB-Simplified is a basketball simulation game that allows users to simulate games, manage franchises, run tournaments, and train teams. The application uses a Python backend with FastAPI for the API layer and a JavaScript frontend using Phaser for game animations.

## High-Level Architecture

The codebase follows a client-server architecture with clear separation between backend simulation logic and frontend visualization:

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   HTML/CSS   │  │  JavaScript  │  │    Phaser    │      │
│  │    Pages     │  │   UI Logic   │  │  Animation   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                    HTTP/REST API
                            │
┌─────────────────────────────────────────────────────────────┐
│                        Backend                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   FastAPI    │  │   Managers   │  │   Engine     │      │
│  │   Routes     │  │   (Models)   │  │  (Simulation)│      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                            │                                 │
│                    ┌──────────────┐                         │
│                    │   MongoDB    │                         │
│                    │   Database   │                         │
│                    └──────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

### Root Level
- **BackEnd/** - All Python backend code
- **FrontEnd/** - All frontend HTML/CSS/JavaScript
- **docs/** - Architecture documentation and design documents
- **tests/** - Test files for simulation logic
- **teams/** - Team data files
- **scripts/** - Utility scripts

### Backend Structure (`BackEnd/`)

```
BackEnd/
├── api/                    # API route handlers
│   ├── api.py             # Main API endpoints (1693 lines)
│   ├── franchise_routes.py # Franchise mode endpoints
│   ├── gameplan_routes.py  # Game plan management
│   ├── tournament_routes.py # Tournament mode endpoints
│   ├── training_routes.py  # Training system endpoints
│   └── play_routes.py      # Custom play endpoints
├── models/                 # Core business logic classes
│   ├── game_manager.py    # Orchestrates entire game (316 lines)
│   ├── turn_manager.py    # Manages individual turns (2146 lines)
│   ├── team_manager.py    # Team state and operations (540 lines)
│   ├── player.py          # Player model and stats (181 lines)
│   ├── shot_manager.py    # Shot mechanics (1070 lines)
│   ├── animator.py        # Animation data generation (1648 lines)
│   ├── franchise_manager.py # Franchise mode logic (584 lines)
│   ├── play_manager.py    # Custom play execution (379 lines)
│   ├── training_manager.py # Training system (344 lines)
│   └── rebound_manager.py # Rebound mechanics (75 lines)
├── engine/                 # Core simulation engine
│   └── phase_resolution.py # Turn phase resolution (89K lines)
├── utils/                  # Utility functions
├── data/                   # Static data (names, etc.)
├── constants.py           # Game constants and configuration
├── db.py                  # MongoDB connection setup
├── main.py                # Core simulation functions (1045 lines)
└── flask_app.py           # Flask wrapper (legacy)
```

### Frontend Structure (`FrontEnd/`)

```
FrontEnd/
├── static/
│   ├── js/
│   │   ├── phaser/        # Phaser game engine integration
│   │   │   ├── gameScene.js      # Main game scene (82K lines)
│   │   │   ├── bootGame.js       # Game initialization
│   │   │   ├── finalizeGame.js   # Game completion
│   │   │   ├── animation/        # Animation components
│   │   │   ├── setup/            # Setup utilities
│   │   │   ├── state/            # State management
│   │   │   ├── ui/               # UI components
│   │   │   └── utils/            # Helper functions
│   │   ├── state/         # Frontend state management
│   │   └── utils/         # Frontend utilities
│   ├── images/            # Sprites and graphics
│   ├── sounds/            # Audio files
│   ├── court.html         # Main game visualization (112K lines)
│   ├── box-score.html     # Box score display
│   ├── game-plan.html     # Game plan editor
│   ├── franchise-*.html   # Franchise mode pages
│   ├── tournament.html    # Tournament mode
│   ├── training.html      # Training interface
│   └── *.js/*.css         # Supporting files
└── app.js                 # Legacy app entry point
```

## Core Components

### 1. Game Simulation Engine

The simulation engine is the heart of the application, responsible for simulating basketball games turn by turn.

#### GameManager (`BackEnd/models/game_manager.py`)
The top-level orchestrator that manages the entire game state.

**Key Responsibilities:**
- Initializes home and away teams
- Manages game clock and quarter progression
- Tracks score and game state
- Coordinates between turn manager and shot manager
- Generates box scores and statistics

**Key Methods:**
- `__init__()` - Sets up teams, managers, and initial state
- `simulate_macro_turn()` - Executes one possession/turn
- `switch_possession()` - Flips offense/defense
- `get_box_score()` - Returns player statistics
- `update_team_stats()` - Aggregates team totals

#### TurnManager (`BackEnd/models/turn_manager.py`)
Manages individual possessions and turn-by-turn gameplay (2146 lines - the largest model).

**Key Responsibilities:**
- Executes micro-turns (individual actions within a possession)
- Handles ball movement, passes, and player decisions
- Manages defensive pressure and offensive states
- Supports both man-to-man and zone defense strategies
- Resolves turnovers, steals, and fouls
- Coordinates with shot manager for shooting attempts

**States:**
- HCO (Half Court Offense) - Normal offense
- FCP (Full Court Press) - Aggressive defense
- HCT (Half Court Trap) - Trapping defense

**Defensive Strategies:**
- Man-to-Man Defense - Standard man-to-man coverage
- Zone Defense (2-3, 3-2, 1-3-1) - Zone-based defensive positioning with automatic zone shifts based on ball location

#### ShotManager (`BackEnd/models/shot_manager.py`)
Handles all shooting mechanics and outcomes (1070 lines).

**Key Responsibilities:**
- Calculates shot probabilities based on player attributes
- Determines shot outcomes (make/miss)
- Handles free throws
- Manages blocks and contested shots
- Tracks shooting statistics

#### TeamManager (`BackEnd/models/team_manager.py`)
Manages team state, roster, and team-level operations (540 lines).

**Key Responsibilities:**
- Loads team data from database
- Manages lineup (5 active players)
- Tracks bench players
- Maintains team attributes (chemistry, efficiency, etc.)
- Handles scouting data and play calling
- Manages team fouls and timeouts

#### Player Model (`BackEnd/models/player.py`)
Represents individual players with attributes and statistics (181 lines).

**Key Attributes:**
- Base attributes: SC (Scoring), SH (Shooting), ID (Interior Defense), etc.
- Malleable attributes: EM (Energy/Momentum), CH (Chemistry), MO (Momentum)
- Position ratings: PG, SG, SF, PF, C
- Statistics: Points, rebounds, assists, etc.

### 2. Simulation Flow

#### Full Game Simulation
```
run_simulation() [main.py]
    ↓
GameManager initialization
    ↓
For each quarter (1-4 + OT if needed):
    simulate_quarter()
        ↓
    Opening tip / Quarter start
        ↓
    While time_remaining > 0:
        simulate_macro_turn()
            ↓
        TurnManager.run_micro_turn()
            ↓
        Update clock, stats, score
        ↓
    Quarter complete
    ↓
Game complete → Generate summary
```

#### Turn-by-Turn Mode
For interactive gameplay with animations:
```
Frontend requests quarter initialization
    ↓
Backend: simulate_quarter(turn_by_turn_mode=True)
    - Sets up quarter (tip-off/inbound)
    - Does NOT run full simulation loop
    ↓
Frontend repeatedly calls /api/simulate-turn
    ↓
Backend: simulate_turn_endpoint()
    - Executes ONE macro turn
    - Returns turn data + animation payload
    ↓
Frontend animates the turn
    ↓
Repeat until quarter ends
```

### 3. Database Architecture

The application uses MongoDB with the following collections:

#### Core Collections
- **players** - Universal player pool (baseline attributes)
- **teams** - Team definitions and base attributes
- **games** - Active and completed game data
- **tournaments** - Tournament state and brackets
- **franchises** - Franchise mode season data
- **plays** - Custom offensive plays
- **defenses** - Custom defensive schemes
- **training_sessions** - Historical training logs

#### Data Storage Patterns

**Franchise Mode (Hybrid Storage):**
- **Franchise document** - Season state, evolved player/team attributes
- **Games collection** - Individual game data (primary storage)
- **Training log** - Historical training sessions

**Player Evolution:**
- `players_collection` - Universal baseline (never modified)
- `franchise.players.{uuid}` - Franchise-specific evolved attributes
- Each franchise maintains its own player attribute progression

**Game Storage:**
- Active games: Stored in `games_collection` with composite ID
- Nested option: Can also store in `franchise.games.week_X.{game_id}`
- Results summary: `franchise.results.{week_number}`

### 4. API Layer

The FastAPI application (`BackEnd/api/api.py`) provides RESTful endpoints:

#### Core Endpoints
- `POST /api/simulate` - Simulate full game instantly
- `POST /api/simulate-quarter` - Initialize quarter (turn-by-turn mode)
- `POST /api/simulate-turn` - Execute single turn
- `GET /api/game/{game_id}` - Get current game state
- `GET /teams` - List all teams
- `GET /api/team/{team_name}/roster` - Get team roster

#### Mode-Specific Routes
- **Franchise routes** (`franchise_routes.py`)
  - Create/manage franchises
  - Play weekly games
  - Recruit players
  - View standings
  
- **Tournament routes** (`tournament_routes.py`)
  - Create/manage tournaments
  - Advance rounds
  - Track brackets
  
- **Training routes** (`training_routes.py`)
  - Allocate training points
  - Improve player/team attributes
  
- **Gameplan routes** (`gameplan_routes.py`)
  - Set offensive/defensive strategies
  - Configure play calling preferences

### 5. Frontend Architecture

#### Page Structure
The frontend consists of multiple HTML pages for different features:

- **court.html** - Main game visualization with Phaser canvas
- **homepage.html** - Landing page and mode selection
- **mode-select.html** - Choose game mode
- **franchise-command-center.html** - Franchise management hub
- **tournament.html** - Tournament bracket and management
- **training.html** - Training allocation interface
- **game-plan.html** - Strategy configuration
- **box-score.html** - Detailed statistics view
- **play-builder.html** - Custom play designer

#### Phaser Integration
The game uses Phaser 3 for real-time basketball animations:

**Key Components:**
- **gameScene.js** (82K lines) - Main game scene with court rendering
- **bootGame.js** - Initializes Phaser and loads assets
- **finalizeGame.js** - Handles game completion
- **animation/** - Animation state machines and sprite management
- **ui/** - Scoreboard, shot clock, and UI overlays

**Animation Flow:**
```
Backend generates animation payload
    ↓
Frontend receives turn data
    ↓
Phaser processes animation sequence
    ↓
Sprites move on court
    ↓
UI updates (score, clock, stats)
    ↓
Ready for next turn
```

### 6. Game Modes

#### Single Game Mode
- Quick simulation between any two teams
- Optional turn-by-turn animation
- Customizable lineups and strategies

#### Franchise Mode
- Multi-season career mode
- Player development through training
- Recruiting system
- Weekly schedule (14 weeks)
- Conference standings
- Player/team attribute evolution

#### Tournament Mode
- Bracket-style elimination
- Multiple rounds
- Tracks tournament stats
- Saves tournament state

### 7. Key Systems

#### Training System
Players and teams improve through training allocation:
- Allocate points to different drill categories
- Shooting drills → SC, SH attributes
- Defense drills → ID, PD attributes
- Film study → Team chemistry, efficiency
- Preseason training (larger improvements)
- Weekly training (incremental improvements)

#### Play Calling System
Teams can use custom offensive plays:
- Plays stored in database
- Define player movements and actions
- Skeleton system for play execution
- Defensive schemes to counter plays (man-to-man, zone defense)

#### Energy System
Players have energy (NG attribute) that affects performance:
- Depletes during gameplay
- Recharges between quarters
- Affects attribute effectiveness
- Substitutions manage energy

#### Momentum System
Game momentum affects team performance:
- Momentum score tracked per team
- Influenced by runs, big plays
- Affects shooting percentages
- Creates realistic game flow

## Data Flow Examples

### Example 1: Simulating a Single Turn

```
1. Frontend: POST /api/simulate-turn
   Body: { game_id, offense_override, defense_override }

2. Backend: simulate_turn_endpoint()
   - Loads GameManager from ongoing_games cache
   - Applies user overrides (if any)
   - Calls gm.simulate_macro_turn()

3. TurnManager.run_micro_turn()
   - Determines offensive play call
   - Checks for turnovers, steals
   - Generates pass chain
   - Resolves shot attempt (if applicable)
   - Updates game state

4. ShotManager (if shot taken)
   - Calculates shot probability
   - Determines make/miss
   - Handles rebounds
   - Updates player stats

5. Animator.generate_animation_payload()
   - Creates sprite positions
   - Defines movement sequences
   - Packages for frontend

6. Backend returns:
   {
     turn_data: { result_type, text, points, ... },
     animation: { sprites, movements, events },
     game_state: { score, clock, box_score, ... }
   }

7. Frontend receives response
   - Updates UI (score, clock)
   - Plays animation via Phaser
   - Waits for next turn request
```

### Example 2: Starting a Franchise

```
1. Frontend: POST /api/franchise/create
   Body: { team_name, username, conference }

2. Backend: FranchiseManager.initialize_franchise()
   - Loads 8 teams for conference
   - Clones 40 recruits from recruits_collection
   - Generates 14-week schedule
   - Initializes player attributes from players_collection
   - Creates franchise document in MongoDB

3. Franchise document structure:
   {
     _id: ObjectId,
     week: 0,
     schedule: [[team_A, team_B], ...],
     players: { uuid: { attributes, stats } },
     franchise_teams: { team_id: { attributes } },
     recruits: [{ name, attributes, ... }],
     training_status: { completed: false },
     results: {}
   }

4. Frontend redirects to command center
   - Displays schedule
   - Shows training button
   - Lists standings
```

### Example 3: Training Session

```
1. Frontend: POST /api/training/allocate
   Body: {
     franchise_id,
     allocations: {
       shooting_drills: { player_A: 5, player_B: 3 },
       defense_drills: { player_C: 4 },
       ...
     }
   }

2. Backend: TrainingManager.apply_training()
   - Loads franchise document
   - For each allocation:
     - Calculates attribute improvements
     - Updates franchise.players.{uuid}.attributes
     - Updates anchor values
   - Updates team attributes
   - Saves to franchise.latest_training
   - Logs to training_log_collection

3. Backend returns:
   {
     player_logs: { "Player A": { SC: +4, SH: +2 } },
     team_log: { team_chemistry: +3 }
   }

4. Frontend displays improvements
   - Shows attribute deltas
   - Marks training as complete
   - Enables "Advance Week" button
```

## Key Design Patterns

### 1. Manager Pattern
Each major component has a dedicated manager class that encapsulates its logic and state. This provides clear separation of concerns and makes the codebase easier to navigate.

### 2. Hybrid Storage Pattern
Franchise mode uses a hybrid approach:
- **Nested storage** for frequently accessed data (players, teams)
- **Separate collections** for large/historical data (games, training logs)
- **Template pool** for recruits (universal templates → franchise-specific)

### 3. Turn-by-Turn Architecture
Games can be simulated in two modes:
- **Batch mode** - Simulate entire game instantly
- **Turn-by-turn mode** - Execute one turn at a time for animation

This allows the same simulation engine to support both quick simulations and interactive gameplay.

### 4. Attribute Evolution
Player attributes follow a three-tier system:
- **Universal baseline** - Never changes (players_collection)
- **Franchise-specific** - Evolves with training (franchise.players)
- **Game-specific** - Temporary modifiers (EM, CH, MO)

## Technology Stack

### Backend
- **Python 3.x** - Primary language
- **FastAPI** - Modern async web framework
- **Uvicorn** - ASGI server
- **PyMongo** - MongoDB driver
- **Pydantic** - Data validation

### Frontend
- **HTML5/CSS3** - Structure and styling
- **Vanilla JavaScript** - UI logic
- **Phaser 3** - Game engine for animations
- **Fetch API** - HTTP requests

### Database
- **MongoDB** - NoSQL document database
- **mongomock** - In-memory testing

## Development Workflow

### Running the Application

1. **Start MongoDB** (if using real database)
   ```bash
   # Set MONGO_URI environment variable
   export MONGO_URI="mongodb://localhost:27017"
   ```

2. **Start Backend**
   ```bash
   cd BackEnd
   uvicorn api.api:app --reload
   ```

3. **Access Frontend**
   - Open browser to `http://localhost:8000/static/homepage.html`
   - Or use specific pages directly

### Testing

The codebase includes test files for core simulation logic:
- `test_gameplan_functionality.py` - Game plan system tests
- `test_gameplan_scenarios.py` - Scenario-based tests
- `test_quarter_simulation_standardization.py` - Quarter simulation tests
- `test_sim_to_4th_quarter.py` - Multi-quarter tests

Run tests with pytest:
```bash
pytest test_gameplan_functionality.py
```

## Common Development Tasks

### Adding a New Player Attribute

1. Add to `BackEnd/constants.py`:
   ```python
   ALL_ATTRS = [..., "NEW_ATTR"]
   MALLEABLE_ATTRS = [..., "NEW_ATTR"]  # if malleable
   ```

2. Update `Player.randomize_game_attributes()` if needed

3. Update position rating calculations in `utils/position_ratings.py`

4. Update training system in `TrainingManager` if trainable

### Adding a New API Endpoint

1. Create route in appropriate file (`api/api.py` or route module)
   ```python
   @app.post("/api/new-endpoint")
   def new_endpoint(request: RequestModel):
       # Implementation
       return response
   ```

2. Add request/response models using Pydantic

3. Update frontend to call new endpoint

### Modifying Simulation Logic

1. Identify the appropriate manager:
   - Shot mechanics → `ShotManager`
   - Turn flow → `TurnManager`
   - Team behavior → `TeamManager`

2. Update the relevant method

3. Test with simulation tests

4. Verify animation data generation if needed

## Performance Considerations

### Caching
- Active games stored in `ongoing_games` dict (in-memory)
- Avoids repeated database queries during turn-by-turn play

### Database Queries
- Franchise mode loads entire franchise doc once
- Players/teams loaded at game start, not per turn
- Batch updates for statistics

### Animation Optimization
- Animation payloads generated server-side
- Frontend only handles rendering
- Sprite pooling in Phaser

## Common Pitfalls for New Engineers

1. **Don't modify universal collections during gameplay**
   - `players_collection` is baseline only
   - Use franchise-specific storage for evolution

2. **Understand turn-by-turn vs batch mode**
   - Different code paths for same simulation
   - Turn-by-turn requires state persistence

3. **Player stats have multiple scopes**
   - `stats["game"]` - Current game only
   - `stats["season"]` - Franchise season
   - `stats["career"]` - Franchise career

4. **Energy system affects all attributes**
   - Low energy reduces effectiveness
   - Must recharge between quarters

5. **Possession changes require state updates**
   - Switch offense/defense teams
   - Update game_state
   - Reset play calls

## Getting Help

- **Documentation**: Check `docs/` folder for detailed design docs
- **Code Comments**: Most complex functions have inline documentation
- **Test Files**: Show expected behavior and usage patterns
- **Architecture Docs**: This file and others in `docs/`

## Next Steps for New Engineers

1. **Run a simple simulation**
   - Start backend
   - Use `/api/simulate` endpoint
   - Examine response structure

2. **Trace a turn execution**
   - Set breakpoints in `simulate_macro_turn()`
   - Follow execution through managers
   - Observe state changes

3. **Explore a game mode**
   - Try franchise mode end-to-end
   - Examine database documents
   - Understand data flow

4. **Read key documentation**
   - `docs/franchise_mode_architecture.md`
   - `docs/game_storage_architecture.md`
   - `docs/animation_system.md`

5. **Make a small change**
   - Add a new stat to track
   - Modify a probability calculation
   - Add a UI element

## Conclusion

GOB-Simplified is a complex basketball simulation with multiple game modes, detailed player/team modeling, and real-time animations. The architecture separates concerns cleanly between simulation logic (backend) and visualization (frontend), with MongoDB providing flexible data storage for evolving game state.

The key to understanding the codebase is following the data flow from API request through managers to database and back to the frontend. Start with simple simulations and gradually explore more complex features like franchise mode and custom plays.

Welcome to the team!
