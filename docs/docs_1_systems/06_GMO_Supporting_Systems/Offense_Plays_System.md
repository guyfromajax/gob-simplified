## Plays System ✅ **COMPLETE** (January 2025)

**Base Constants**

1. **Play Types**: Motion, Set Play
2. **Set Play Focus Types**: Inside, Attack, Outside, Balanced
3. **Set Play Variants**: `successful`, `mid_play_change`, `contested`, `broken`
4. **Defense Types**: Man, Zone (2-3 Zone, 3-2 Zone, 1-3-1 Zone)
5. **Strategy Settings Range**: 0-4 sliders for offense/defense preferences
6. **Playbook Percentages**: 0-100 per play/defense
7. **Universal Collections**: `plays` collection, `defenses` collection
8. **Team Storage**: `teams.{team_id}.plays`, `teams.{team_id}.playbook_settings`, `scouting_data["defense"]`
9. **Key Backend Files**:
   - `BackEnd/models/turn_manager.py` - `set_playcalls()` method
   - `BackEnd/engine/phase_resolution.py` - Play execution and skeleton retrieval
10. **Key Frontend Files**:
    - `FrontEnd/static/play-details.html` - Play details page
    - `FrontEnd/static/playbooks.js` - Navigation integration

**Plays System Flow (Backend - 8 Steps)**

1. **User Override Check**: Check for user-selected play/defense overrides (one-time for offense, persistent for defense)
2. **Play Type Selection**: Determine Motion vs Set Play based on strategy settings (0-4 slider)
3. **Play Focus Selection**: For Set Plays, determine Inside/Attack/Outside based on strategy settings
4. **Specific Play Selection**: Query universal `plays` collection and use playbook-weighted selection
5. **Skeleton Retrieval**: Fetch play skeleton from universal collection (Motion: `base_loop`, Set Play: variant based on outcome)
6. **Resolution Integration**: Execute play and determine outcome (SHOT, O_FOUL, D_FOUL, STEAL, DEAD_BALL_TURNOVER)
7. **Variant Selection**: For Set Plays, select skeleton variant based on lean score from resolution
8. **Animation Generation**: Convert skeleton steps to frontend animation data

**Plays Page System Flow (Frontend - 6 Steps)**

1. **Navigation**: User clicks play name in Playbooks page, navigates to `/static/play-details.html` with `play_name` parameter
2. **Page Load**: Extract `play_name` from URL, fetch play data from `/api/play/{play_name}` endpoint
3. **Skeleton Loading**: Load appropriate skeleton (Motion: `base_loop`, Set Play: `successful` variant)
4. **Animation Initialization**: Initialize animation state and auto-start animation
5. **Animation Loop**: Process steps, update player positions, render court visualization, handle looping
6. **User Controls**: Pause/Resume button allows user to control animation playback

**Long Form Documentation**

### Backend: Play Selection and Execution System

**Location:** `BackEnd/models/turn_manager.py` - `set_playcalls()` method  
**Status:** ✅ Fully implemented with playbook integration, user overrides, and effectiveness tracking

The Plays System is the core mechanism for selecting and executing offensive and defensive plays during gameplay. It integrates playbook settings, strategy preferences, user overrides, and play effectiveness tracking to determine which plays are used in each turn.

#### Play Selection Process

The play selection process occurs at the start of each HCO (Half Court Offense) turn via `set_playcalls()`. The system uses a hierarchical approach:

**1. User Override Check**

**Offensive Play Override:**
- Checks `offense_team.strategy_calls.get("offense_call")` for user-selected play
- If set, uses the specific play name (e.g., "3-2 Motion", "Base Post Play")
- Override is cleared after use (one-time override)
- Looks up play details from database to determine `play_type` and `play_focus`

**Defensive Play Override:**
- Checks `user_team.strategy_calls.get("defense_call")` (regardless of current offense/defense)
- If set, uses the specific defense (e.g., "Man", "2-3 Zone", "Zone")
- Override is persistent until manually cleared by user
- If "Zone" is selected, converts to specific zone type using playbook weights

**2. Normal Play Selection (If No Override)**

**Offensive Play Selection - Three-Level System:**

**Level 1: Determine Play Type (Motion vs Set Play)**
- Uses `offense_setting` from strategy settings (0-4 slider)
- Weighted random selection based on setting:
  - Setting 0: 100% Motion, 0% Set Play
  - Setting 1: 75% Motion, 25% Set Play
  - Setting 2: 50% Motion, 50% Set Play
  - Setting 3: 25% Motion, 75% Set Play
  - Setting 4: 0% Motion, 100% Set Play

**Level 2: Determine Play Focus (Inside/Attack/Outside)**
- Only applies to Set Plays (Motion plays don't filter by focus)
- Uses `inside`, `attack`, `outside` values from strategy settings
- Weighted random selection:
  - Roll random number from 1 to total (inside + attack + outside)
  - If roll <= inside_val → "inside"
  - Else if roll <= inside_val + attack_val → "attack"
  - Else → "outside"

**Level 3: Select Specific Play**
- Queries universal `plays` collection:
  - **Motion Plays:** `{"play_type": "motion"}`
  - **Set Plays:** `{"play_type": "set_play", "play_focus": chosen_focus}`
- Uses playbook-weighted selection (see Playbook Integration below)
- Falls back to equal weights if no playbook settings exist

**Defensive Play Selection:**
- Uses `defense_setting` from strategy settings (0-4 slider)
- Maps setting to defense options via `STRATEGY_CALL_DICTS["defense"]`
- If "Zone" is selected, converts to specific zone type:
  - Uses playbook-weighted selection for user teams
  - Falls back to equal weights for CPU teams
- Available defenses: "Man", "2-3 Zone", "3-2 Zone", "1-3-1 Zone"

#### Playbook Integration

**Weighted Selection System:**
- Loads playbook settings from team document: `teams.{team_id}.playbook_settings`
- Uses `weighted_random_from_dict()` utility for selection
- Only applies to user teams (CPU teams use equal weights)

**Motion Offense Selection:**
- Uses `playbook_settings.motion` dictionary
- Keys are play names, values are percentages (0-100)
- Example: `{"5-0 Motion": 50, "4-1 Motion": 30, "3-2 Motion": 20}`
- Excludes "To Be Added" plays (0% weight)

**Set Play Selection:**
- Uses `playbook_settings.set_play_{focus}` dictionaries
- Separate dictionaries for each focus: `set_play_inside`, `set_play_attack`, `set_play_outside`
- Keys are play names, values are percentages
- Example: `{"set_play_inside": {"Base Post Play": 60, "Wing Entry": 40}}`

**Zone Defense Selection:**
- Uses `playbook_settings.zone_defense` dictionary
- Keys are zone type names: "2-3 Zone", "3-2 Zone", "1-3-1 Zone"
- Values are percentages
- Example: `{"2-3 Zone": 40, "3-2 Zone": 35, "1-3-1 Zone": 25}`

**Fallback Behavior:**
- If no playbook settings exist → Equal weights for all plays
- If CPU team → Equal weights (playbook settings ignored)
- If "To Be Added" play → Excluded from selection (0% weight)

#### Play Execution Flow

**1. Skeleton Retrieval:**
- `get_hco_skeleton()` retrieves play skeleton from universal collection
- Uses reference-based architecture: looks up `play_id` from team plays, then fetches skeleton
- **Motion Plays:** Always uses `base_loop` skeleton (no variant selection)
- **Set Plays:** Selects variant based on resolution outcome:
  - `successful` - Play works perfectly (lean_score >= 0.5)
  - `mid_play_change` - Play adjusts mid-execution (0 <= lean_score < 0.5)
  - `contested` - Defense engaged (-0.5 < lean_score < 0)
  - `broken` - Defense disrupts (lean_score <= -0.5)

**2. Resolution System Integration:**
- `resolve_half_court_offense_logic()` calls `resolve_hco_outcome()`
- Determines turn outcome: SHOT, O_FOUL, D_FOUL, STEAL, DEAD_BALL_TURNOVER
- For Set Plays, outcome determines skeleton variant selection
- For Motion Plays, outcome determines shot type (Inside/Attack/Outside)

**3. Stopper System:**
- If non-shot outcome occurs, `apply_stopper_system_to_skeleton()` truncates skeleton
- Appends "stopper step" at the point of interruption
- Preserves animation continuity while reflecting game event

**4. Animation Generation:**
- `skeleton_to_animations()` converts skeleton steps to frontend animation data
- Processes player movements, ball passes, and actions
- Frontend animates the play execution

#### Play Effectiveness and Momentum Tracking

**Dual Storage Architecture:**

Effectiveness, momentum, and cloaking values exist in **two locations**:

1. **Universal Collections** (`plays` and `defenses` collections):
   - Template/library values for all plays and defenses
   - Initialized to `0` for all plays and defenses
   - Serve as default starting values when team objects are created
   - Can be modified globally (affects all teams using that play/defense)

2. **Team Objects** (`teams.{team_id}.plays` and `scouting_data["defense"]`):
   - **Per-team instances** with team-specific values
   - Initialized from universal collection values when team object is created
   - Can be modified independently per team by:
     - **Training system** - Based on playbook settings and game plan mix
     - In-game performance (future implementation)
     - Coaching focus selections (future implementation)
   - Allows different teams to have different effectiveness/momentum/cloaking for the same play/defense

**Effectiveness:**
- **Per-team effectiveness** stored in `teams.{team_id}.plays.{play_name}.effectiveness`
- **Per-team defense effectiveness** stored in `scouting_data["defense"][defense_name].effectiveness`
- Separate from calculated effectiveness in `game_stats`/`season_stats`
- Used in matchup calculations and play/defense selection weighting
- Modified by training system based on:
  - Playbook percentages (plays used more frequently get more training benefit)
  - Game plan mix (motion vs set plays, inside vs attack vs outside focus)
  - Defense preferences (man vs zone percentages)

**Momentum:**
- **Per-team momentum** stored in `teams.{team_id}.plays.{play_name}.momentum`
- **Per-team defense momentum** stored in `scouting_data["defense"][defense_name].momentum`
- Tracks recent performance trends for this team's use of the play/defense
- Can increase or decrease based on:
  - Training system modifications
  - Recent success/failure rates (future implementation)
  - Coaching focus selections (future implementation)
  - Game situation and context (future implementation)
- Used to adjust play/defense selection probabilities dynamically

**Cloaking:**
- **Per-team cloaking** stored in `teams.{team_id}.plays.{play_name}.cloaking`
- **Per-team defense cloaking** stored in `scouting_data["defense"][defense_name].cloaking`
- Makes plays/defenses harder for opponents to recognize and counter
- Higher values reduce opponent's ability to anticipate and adjust
- Can be modified by training system
- Used in matchup calculations and offensive/defensive recognition systems

#### Database Structure

**Offensive Plays (Universal `plays` Collection)**

**Location:** MongoDB `plays` collection  
**Purpose:** Store offensive play definitions with full skeleton data

**Document Structure:**
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

**Field Descriptions:**
- `_id` (ObjectId) - Unique MongoDB document ID
- `name` (str) - Play name (e.g., "4-1 Motion", "3-2 Motion", "Base Post Play")
- `play_type` (str) - "motion" or "set_play"
- `play_focus` (str | null) - "inside", "attack", "outside", "balanced" (Set Plays only), or `null` (Motion Plays)
- `skeletons` (dict) - Full skeleton data with animation steps
  - **Motion Plays:** `{"base_loop": {steps: [...], complete: true}}`
  - **Set Plays:** `{"successful": {...}, "mid_play_change": {...}, "contested": {...}, "broken": {...}}`
- `copy` (dict | null) - Optional descriptive text for play details page
- `effectiveness` (float) - Play effectiveness score (default: `0`)
- `cloaking` (float) - Cloaking modifier (default: `0`)
- `momentum` (integer) - Momentum score (default: `0`)

**Defensive Plays (Universal `defenses` Collection)**

**Location:** MongoDB `defenses` collection  
**Purpose:** Store defensive playcall definitions with zone configurations

**Document Structure:**
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

**Field Descriptions:**
- `_id` (ObjectId) - Unique MongoDB document ID
- `defense_id` (str) - Unique defense identifier (e.g., "man", "2-3-zone", "3-2-zone", "1-3-1-zone", "base-man")
- `defense_type` (str) - "Man" or "Zone"
- `name` (str) - Defense display name (e.g., "Man-to-Man", "2-3 Zone", "Base Man")
- `description` (str) - Defense description text
- `effectiveness` (float) - Defense effectiveness score (default: `0`)
- `cloaking` (float) - Cloaking modifier (default: `0`)
- `momentum` (integer) - Momentum score (default: `0`)
- `zone_definitions` (dict | null) - Zone positioning configurations (Zone defenses only)
  - `normal` - Default zone positions
  - `lower_shift` - Zone positions when ball is in lower areas
  - `upper_shift` - Zone positions when ball is in upper areas
  - Additional shifts for 1-3-1 zone (`lower_corner_shift`, `upper_corner_shift`)
  - `null` for Man defenses
- `shift_triggers` (dict | null) - Ball locations that trigger zone shifts
  - Maps shift names to arrays of location strings
  - `null` for Man defenses
- `game_stats` (dict) - Game-level usage and success tracking
- `season_stats` (dict) - Season-level usage and success tracking

#### Integration with Resolution System

**HCO Resolution:**
- Plays are selected before resolution begins
- Selected play determines skeleton retrieval
- Resolution outcome (for Set Plays) determines skeleton variant
- Play effectiveness and momentum can influence resolution calculations (future implementation)

**Motion Offense Resolution:**
- Uses `base_loop` skeleton for all turns
- `resolve_motion_offense_shot()` determines shot type dynamically
- Shot type (Inside/Attack/Outside) is determined by player positioning and opportunities
- Attack penalty applied to shot scores for drive-and-shoot actions

**Set Play Resolution:**
- Resolution outcome determines which variant skeleton to use
- Variant selection based on lean score from matchup evaluation
- Each variant has different shot opportunities and player movements

### Frontend: Plays Page System

**Location:** `FrontEnd/static/play-details.html`  
**Purpose:** Display play details, animations, and information  
**Status:** ✅ Fully implemented with auto-animating play visualization

The Plays Page System provides detailed views for individual plays, allowing users to see play animations and information. Each play has its own dedicated page that displays the play's animation and descriptive content.

#### Navigation

**Entry Point:**
- Play names in the Playbooks page are clickable links (except "To Be Added" placeholders)
- Clicking a play name navigates to `/static/play-details.html` with:
  - `play_name` parameter (URL encoded)
  - All context parameters (mode, team_id, game_id/tournament_id/franchise_id)
  - Preserves navigation context for back button functionality

**Back Navigation:**
- Back button (top-left) returns to Playbooks page
- Reconstructs Playbooks URL with all original parameters
- Maintains user's context across navigation

#### Layout Structure

**Header:**
- **Play Name:** Centered, large gold font (2.5rem), with text shadow
- **Play Type:** Centered, smaller font (1.2rem), muted color (Motion or Set Play)

**2-Column Layout:**
- **Left Column (50% width):**
  - Three horizontal info containers
  - Each container has:
    - Title (gold color, 1.1rem)
    - Content area (placeholder "Copy Goes Here" for future content)
  - Containers are vertically centered as a unit, middle-aligned with animation container
  - Containers: "Play Description", "Key Concepts", "Usage Tips"
  
- **Right Column (50% width):**
  - Court animation container
  - Same dimensions and styling as Play Builder v2 animation container
  - Centered horizontally and vertically within its column
  - Uses same court image: `/static/images/courts/bentley_truman.jpg`

#### Animation System

**Auto-Start Behavior:**
- Animation begins automatically on page load
- No user interaction required
- Fetches play data from `/api/play/{play_name}` endpoint
- Loads appropriate skeleton based on play type:
  - **Motion Plays:** Uses `base_loop` skeleton
  - **Set Plays:** Uses `successful` skeleton

**Animation Controls:**
- **Pause/Resume Button:** Located below the animation container, horizontally centered
- Button text changes: "⏸️ Pause" when playing, "▶️ Resume" when paused
- Button styling changes: Blue gradient when playing, green gradient when paused
- Clicking pauses/resumes the animation at the current step
- Animation state persists when paused (can resume from same step)

**Animation Logic:**
- Reuses animation system from Play Builder v2:
  - Same constants (court coordinates, positions, ball-handling actions)
  - Same rendering logic (`renderCourtVisualization()`)
  - Same step-by-step animation (`animateNextStep()`)
  - Player icons positioned using percentage-based coordinates
  - Ball sprite follows ball handler or pass/shoot actions
  - Smooth transitions between steps (1 second delay per step)

**Motion Play Animation:**
- Continuous loop behavior
- When reaching final step (marked with `is_final_step: true`), loops back to step 0
- If no final step marked, loops back to step 0 when reaching end of steps
- Runs indefinitely until page is closed

**Set Play Animation:**
- Runs animation from start to finish
- Pauses for 2 seconds after completion
- Restarts from step 0
- Repeats continuously

**Player Rendering:**
- Player icons positioned at court locations based on skeleton step data
- Icons animate smoothly between positions using CSS transitions
- Ball sprite follows ball handler or shows pass/shoot animations
- Position offsets applied for screen actions (collision handling)

#### Data Flow

**Page Load:**
1. Extract `play_name` from URL parameters
2. Fetch play data from `/api/play/{play_name}` endpoint
3. Display play name and type in header
4. Load skeleton data:
   - **Motion:** `base_loop` (direct steps array)
   - **Set Play:** `successful` variant, version v0 from `versions` array (or direct steps for backward compatibility)
5. Initialize animation state
6. Auto-start animation

**Animation Loop:**
1. Process current step's `pos_actions` data
2. Update player positions and actions
3. Render court visualization with player icons and ball
4. Move to next step after 1 second delay
5. Handle looping logic (Motion: loop to 0, Set Play: pause then restart)

#### Responsive Design

**Desktop:**
- 2-column grid layout
- All content fits above the fold
- Left column containers vertically centered
- Animation container centered in right column

**Mobile/Tablet:**
- Stacks vertically (right column first, then left column)
- Animation container remains full width
- Info containers stack below animation
- Maintains readability and usability

### Key Files

**Backend:**
- `BackEnd/models/turn_manager.py` - `set_playcalls()` method (lines 793-1264)
  - Play selection logic
  - User override handling
  - Playbook-weighted selection
- `BackEnd/engine/phase_resolution.py` - `resolve_half_court_offense_logic()` (lines 3105-3200)
  - Play execution and resolution
  - Skeleton retrieval and variant selection
- `BackEnd/engine/phase_resolution.py` - `get_hco_skeleton()` (lines 4709-4791)
  - Skeleton retrieval from universal collection
  - Reference-based architecture
- `BackEnd/engine/phase_resolution.py` - `_get_skeleton_from_team_plays()` (lines 4794-4891)
  - Team play reference lookup
  - Skeleton caching
- `BackEnd/utils/shared.py` - `weighted_random_from_dict()` (lines 21-37)
  - Weighted random selection utility
- `BackEnd/db.py` - `plays_collection`, `defenses_collection`
  - MongoDB collection access

**Frontend:**
- `FrontEnd/static/play-details.html` - Main page structure and animation logic
- `FrontEnd/static/playbooks.js` - Navigation integration (clickable play names)

**API Endpoints:**
- `GET /api/play/{play_name}` - Fetch play data for details page

### Future Enhancements

**Backend:**
- In-game performance tracking for effectiveness/momentum
- Coaching focus selections affecting play effectiveness
- Game situation and context affecting play selection

**Frontend:**
- Populate info containers with actual play descriptions, concepts, and tips
- Add play statistics (usage rate, success rate, etc.)
- Add variant selector for Set Plays (successful, mid_play_change, contested, broken)
- Add animation controls (speed adjustment)
- Add step-by-step navigation (previous/next step buttons)

