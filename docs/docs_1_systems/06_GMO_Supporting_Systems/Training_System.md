## Training System ✅ **COMPLETE** (January 2025)

**Base Constants**

1. **Total Training Points**: 
   - **First Training (Franchise Mode)**: 30 points (before first game)
   - **All Other Trainings**: 24 points per training session
2. **Slider Range**: 0-5 points per slider (discrete steps)
3. **Training Page Files**: `FrontEnd/static/training.html`, `FrontEnd/static/training.js`, `FrontEnd/static/training.css`
4. **Training Report Page**: `FrontEnd/static/training-report.html`
5. **Backend Execution**: `BackEnd/models/training_execution_v2.py`
6. **API Endpoints**:
   - `GET /franchise/training-points` - Get available training points (30 for first training, 24 otherwise)
   - `POST /franchise/run-training` - Submit training
   - `GET /franchise/training-report` - Get training report data
7. **Coaching Focus Archetypes**: Authoritarian, Systems Coach, Player Maximizer, Culture Builder
8. **Rebound Modifier Range**: 0.0-0.4 (clamped)
9. **Pre-Training Decay**: Plays/defenses with effectiveness > 0 reduced by `random.randint(5, 15)`

**Training System Flow (11 Steps)**

1. **Page Load**: Frontend fetches training points from `/franchise/training-points` endpoint (30 for first training, 24 otherwise)
2. **User Allocates Points**: User distributes training points (30 or 24) across 20 sliders (player drills, team drills, general)
3. **User Selects Focus**: User selects one coaching focus archetype and sub-option
4. **Submit Training**: Frontend sends POST request to `/franchise/run-training` with training data
5. **Backend Validation**: Backend validates total points match expected (30 for first training, 24 otherwise)
6. **Data Auto-Population**: Backend initializes `plays_data` and `scouting_data` if missing
7. **Pre-Training Decay**: All plays/defenses with effectiveness > 0 reduced by 5-15 points
8. **Pre-Training Conditions**: Random decreases applied to player/team attributes (excluding EM, MO, NG)
9. **Training Point Application**: Drill allocations mapped to attributes, random increases applied based on points
10. **Coaching Focus Amplifiers**: Selected focus amplifies specific attribute gains
11. **Attribute Clamping**: All values clamped to valid ranges (player: min 1, team: defined ranges)
12. **Report Generation**: Training report stored, player/team attributes updated, redirect to report page

**Long Form Documentation**

### Training Page Layout

**Desktop-only page** using a 4-column grid layout. All content fits above the fold at common desktop resolutions.

**Header Section (Sticky on Scroll):**
- Centered page title: "TEAM TRAINING"
- Points Remaining display: "POINTS REMAINING: 24" (dynamic)
- Back button (blue, upper-left corner)
- Submit Training button (orange, upper-right corner)
- Auto-Train button (header, right side)
- Horizontal line below Points Remaining

**Main Content Layout:**

**Left Half - Player Drills:**
- **Column 1:**
  - Offense Drills (Inside Offense, Outside Offense sliders)
  - Technical Drills (Passing, Ball Handling, Rebounding sliders)
- **Column 2:**
  - Defense Drills (Inside Defense, Outside Defense sliders)
  - Weight Room (Strength, Agility sliders)

**Right Half - Team Drills:**
- **Column 1:**
  - Offense (Offense Install slider)
  - Fast Breaks (FB Offense Install, FB Defense Install sliders, Scrimmages slider)
- **Column 2:**
  - Defense (Defense Install slider)
  - Presses / Traps (P/T Defense Install, P/T Offense Install sliders)
- **Bottom of Team Drills Section:**
  - Playbook Training Mode (radio buttons):
    - Current Playbooks (default)
    - All Plays / Even Distribution
    - Custom

**General Section (Full Width):**
- Four sliders in a 4-column grid:
  - Conditioning
  - Free Throws
  - Film Study
  - Breaks

**Coaching Style / Focus Section (Bottom):**
- Title: "Coaching Style / Focus (choose one)"
- Four archetype blocks displayed horizontally (4 columns):
  - **Authoritarian** (red header fill)
    - Sub-options: Discipline, Rebounding, Execution, Teamwork
  - **Systems Coach** (dark/burnt yellow header fill)
    - Sub-options: Offense, Defense, Fast Breaks, Press / Trap
  - **Player Maximizer** (darker green header fill)
    - Sub-options: Top 3 Attributes, Attributes 4–6, Custom Attributes, Opportunity
  - **Culture Builder** (purple header fill)
    - Sub-options: Inspire, Confidence, Community Engagement, Teamwork

### Slider Behavior

- Each slider has discrete steps from 0 to 5
- Default value for all sliders on page load: 0
- Total available training points:
  - **First Training (Franchise Mode)**: 30 points (before first game)
  - **All Other Trainings**: 24 points
- Training points are fetched from `/franchise/training-points` endpoint on page load
- Moving a slider to value N subtracts N from Points Remaining
- Prevents user from allocating more than available total points (clamps or reverts last interaction)
- Points Remaining = TOTAL_POINTS - sum(all slider values)

### Coaching Focus Selection

- All radios in the Coaching Focus section are part of ONE global radio group
- Only one selection can be active at a time
- Selecting any archetype header or sub-option clears all others

**Visual Behavior:**
- **Archetype header radio selected:**
  - Entire archetype block gets a highlight outline in the archetype's color
  - Header and all four sub-options appear "active" with neutral grey fill
- **Sub-option radio selected:**
  - Only that radio fills with the archetype's header color
  - Archetype block shows a subtle outline in the same color (more subtle than header selection)

### Submit Button Behavior

- Disabled / visually muted (reduced opacity, non-clickable) until:
  1. All training points are allocated (Points Remaining = 0) - 30 for first training, 24 otherwise
  2. A coaching focus is selected
- Becomes active only when both conditions are met

### Auto-Train Button

- **Button:** "Auto-Train" (header, right side)
- **Behavior when clicked:**
  - Automatically assigns all training points across the 20 sliders
    - Sets all 20 sliders to `1` (20 points)
    - Randomly selects additional sliders to set to `2`:
      - **24 points**: 4 sliders set to `2` (20 + 4 = 24)
      - **30 points**: 10 sliders set to `2` (20 + 10 = 30)
  - Randomly selects a Coaching Focus (one of the existing focus radio options)
  - Shows confirmation popup: `Training Points Assigned - {Focus Name} Focus Chosen`
    - Popup has a "Close" button; closing keeps the user on the Training page
  - After auto-assign, Points Remaining = 0 and Submit becomes eligible (provided focus set by auto-train)

### Backend Training Execution System

**Location:** `BackEnd/models/training_execution_v2.py`

The training execution system applies pre-training conditions, allocates training points, applies coaching focus amplifiers, and generates training reports.

#### Training Execution Flow

0. **Pre-Training Effectiveness Decay** (`_apply_pre_training_effectiveness_decay`, `_apply_pre_training_defense_decay`)
   - All plays and defenses with effectiveness > 0 are reduced by `random.randint(5, 15)`
   - Minimum effectiveness is clamped to 0 (cannot be negative)
   - This represents natural skill degradation between training sessions
   - Original effectiveness values are tracked for change calculation

1. **Pre-Training Conditions** (`apply_pre_training_conditions`)
   - Applies random decreases to player attributes (excluding EM, MO, NG)
   - Player attributes: `+= random.randint(-2, 0)` per attribute
   - Team attributes: Random decreases based on attribute type
   - Rebound modifier: `+= -0.1 or 0` (pre-training)
   - Shot threshold: `+= random.randint(0, 15)`
   - Other team attributes: `+= random.choice([-2, -1, 0])`

2. **Training Point Application** (`apply_training_points`)
   - Maps drill allocations to player/team attributes
   - Applies random increases based on points allocated
   - Applies coaching focus amplifiers
   - Handles special cases (conditioning, film study, breaks)

3. **Play/Defense Training Application** (placeholder - to be implemented)
   - Updates play effectiveness and momentum based on training allocations
   - Updates defense effectiveness and momentum based on training allocations
   - Uses playbook_training_mode to determine which plays/defenses receive training benefits
   - Considers playcall_settings, strategy_settings, and playbook_settings for weighted distribution

4. **Attribute Clamping**
   - Player attributes: Minimum 1, no maximum
   - Team attributes: Clamped to defined ranges (see `TEAM_ATTR_CLAMPS` in code)

5. **Training Report Generation**
   - Calculates changes from original baselines
   - Returns player_changes and team_changes dictionaries
   - Includes coaching focus information

#### Drill-to-Attribute Mapping

**Player Drills:**
- Inside Offense → SC (Shooting Close)
- Outside Offense → SH (Shooting)
- Inside Defense → ID (Inside Defense)
- Outside Defense → OD (Outside Defense)
- Ball Handling → BH
- Passing → PS
- Rebounding → RB
- Strength Training → ST
- Agility Training → AG
- Free Throws → FT
- Conditioning → ND (Endurance), CH (Chemistry, 0.5x multiplier)
- Film Study → IQ, CH (Chemistry, 0.5x multiplier)

**Team Drills:**
- Offense Install → `offensive_efficiency`
- Defense Install → `defensive_efficiency`
- Fast Break Offense Install → `fb_efficiency`
- Fast Break Defense Install → `fb_opp_modifier`
- P/T Defense Install → `pt_efficiency`
- P/T Offense Install → `pt_opp_modifier`
- Scrimmages → Team Chemistry, Shot Threshold (decreases), Rebound Modifier, NG Reduction (if 3-5 points)

#### Training Point Ranges

**Player Attributes:**
- 1 point: `+= random.randint(1, 3)`
- 2 points: `+= random.randint(2, 5)`
- 3 points: `+= random.randint(3, 7)`
- 4 points: `+= random.randint(3, 8)`
- 5 points: `+= random.randint(3, 9)`

**Team Attributes (standard):**
- 1 point: `+= random.randint(1, 2)`
- 2 points: `+= random.randint(2, 3)`
- 3 points: `+= random.randint(3, 5)`
- 4 points: `+= random.randint(3, 6)`
- 5 points: `+= random.randint(3, 7)`

**Rebound Modifier (Technical Drills - in 0.01 increments):**
- 1 point: `+= random.randint(1, 6) / 100.0` (0.01 to 0.06)
- 2 points: `+= random.randint(3, 8) / 100.0` (0.03 to 0.08)
- 3 points: `+= random.randint(4, 10) / 100.0` (0.04 to 0.10)
- 4 points: `+= random.randint(4, 12) / 100.0` (0.04 to 0.12)
- 5 points: `+= random.randint(4, 14) / 100.0` (0.04 to 0.14)

**Rebound Modifier (Scrimmages - in 0.01 increments):**
- 1 point: `+= random.randint(1, 3) / 100.0` (0.01 to 0.03)
- 2 points: `+= random.randint(2, 5) / 100.0` (0.02 to 0.05)
- 3 points: `+= random.randint(3, 8) / 100.0` (0.03 to 0.08)
- 4 points: `+= random.randint(3, 9) / 100.0` (0.03 to 0.09)
- 5 points: `+= random.randint(3, 10) / 100.0` (0.03 to 0.10)

**Shot Threshold:**
- 1 point: `-= random.randint(10, 25)`
- 2 points: `-= random.randint(15, 35)`
- 3 points: `-= random.randint(20, 45)`
- 4 points: `-= random.randint(20, 55)`
- 5 points: `-= random.randint(20, 65)`

#### Coaching Focus Amplifiers

**Authoritarian:**
- Discipline: Amplifies BH, `fight`, `discipline` (multiplier: `random.choice([1.3, 1.4, 1.5, 1.6])`)
- Rebounding: Amplifies RB, `rebound_modifier` (multiplier: `random.choice([1.5, 1.6, 1.7, 1.8])`)
- Teamwork: Amplifies PS, Motion Play Effectiveness, Zone Defense Effectiveness
- Execution: Amplifies Set Play Effectiveness, Man Defense Effectiveness

**Systems Coach:**
- Offense: Amplifies `offensive_efficiency` gains, offensive play effectiveness
- Defense: Amplifies `defensive_efficiency` gains, defensive play effectiveness
- Fast Breaks: Amplifies `fb_efficiency` gains, `fb_opp_modifier` gains
- Presses/Traps: Amplifies `pt_efficiency` gains, `pt_opp_modifier` gains

**Player Maximizer:**
- Top 3 Attributes: Amplifies gains to player's top 3 attributes (excluding CH, EM, MO, NG)
- Attributes 4-6: Amplifies gains to player's 4th-6th highest attributes
- Custom: Amplifies gains to user-selected attributes (TODO)
- Be Opportunistic: Improves Set Play and Motion Shot Scores (carried to next game)

**Culture Builder:**
- Inspire: Improves EM, MO by `random.randint(1, 2)`, amplifies Team Chemistry gains
- Community Engagement: Improves EM, affects crowd factors (carried to next game)
- Teamwork: Amplifies Team Chemistry gains, improves Motion Play and Zone Defense Effectiveness
- Build Confidence: Improves Set Play Effectiveness, Man Defense Effectiveness (multiplier: `random.choice([1.3, 1.4, 1.5, 1.6])`)

#### Breaks Effect

The "Breaks" slider applies a multiplier to all positive gains (not losses):
- 0 points: `random.choice([0.85, 0.9, 0.95])`
- 1 point: `random.choice([0.9, 0.95, 1, 1, 1])`
- 2 points: `random.choice([0.95, 1, 1, 1, 1])`
- 3 points: `random.choice([0.9, 0.95, 1])`
- 4 points: `random.choice([0.9, 0.95, 1])` + Team Chemistry `+= random.randint(-1, 1)`
- 5 points: `random.choice([0.9, 0.95, 1])` + Team Chemistry `+= random.randint(-3, 3)`

#### NG Reduction from Scrimmages and Conditioning

When scrimmages or conditioning are allocated 3, 4, or 5 points, players may experience NG (Nerve/Game) reduction, which affects their energy for the next game. These reductions can stack if both scrimmages and conditioning are allocated.

**Scrimmages NG Reduction:**
- **3 points:** `reduce_ng_list = [0, 0.01, 0.01, 0.02]`
- **4 points:** `reduce_ng_list = [0, 0.01, 0.02, 0.02, 0.03]`
- **5 points:** `reduce_ng_list = [0.01, 0.02, 0.03, 0.03, 0.04]`

**Conditioning NG Reduction:**
- **3 points:** `reduce_ng_list = [0, 0.01, 0.01, 0.02]`
- **4 points:** `reduce_ng_list = [0, 0.01, 0.02, 0.02, 0.03]`
- **5 points:** `reduce_ng_list = [0.01, 0.02, 0.03, 0.03, 0.04]`

**Process:**
- For each player, `player.NG -= random.choice(reduce_ng_list)`
- NG is clamped to a minimum of 0.0
- NG is rounded to 2 decimal places

**High Endurance (ND > 79) Special Handling:**
Players with ND (Endurance) greater than 79 receive reduced NG penalties:
- **Scrimmages 3:** Omitted entirely (no NG reduction)
- **Scrimmages 4:** Uses scrimmages 3 reduction list
- **Scrimmages 5:** Uses scrimmages 4 reduction list
- **Conditioning 3:** Omitted entirely (no NG reduction)
- **Conditioning 4:** Uses conditioning 3 reduction list
- **Conditioning 5:** Uses conditioning 4 reduction list

**Training Notes:**
The training report automatically generates notes when players have NG reductions:
- **Multiple players (conditioning):** "Multiple players will start the next game with reduced energy due to the amount of conditioning."
- **Single player (conditioning):** "{player name} will start the next game with reduced energy due to the amount of conditioning."
- **Multiple players (scrimmages):** "Multiple players will start the next game with reduced energy due to the amount of scrimmages."
- **Single player (scrimmages):** "{player name} will start the next game with reduced energy due to the amount of scrimmages."

### Training Report Page

**Location:** `FrontEnd/static/training-report.html`

After training is submitted, users are automatically redirected to the training report page which displays detailed information about attribute changes. The report can also be accessed via links on the schedule in the Franchise Command Center.

#### Page Layout

**Header Section:**
- Page title: "TRAINING REPORT"
- Week number
- Upcoming Opponent (from schedule)
- Training Focus (formatted as "Archetype (Sub-Option)", e.g., "Culture Builder (Inspire)")
- Orange "Go To Locker Room" button (top-right) - navigates to Franchise/Tournament Command Center

**Player Report Section:**
- Header: "Player Report"
- Toggle between "Attributes" and "Training Changes" views
- **Attributes View:** Shows current attribute values after training
  - **Attribute Order:** Attributes displayed in exact order: SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT, NG, EM, MO
  - **Attribute Formatting:**
    - **SC through FT (first 12):** Displayed as integer values
    - **NG:** Displayed with 2 decimal places (e.g., 1.00, 0.99, 0.98, 0.90)
    - **EM:** Displayed with emoji based on value:
      - >= 80: 😎 (Sunglasses)
      - >= 60: 😊 (Big smile)
      - >= 40: 😐 (Straight face)
      - >= 20: 😕 (Slight frown)
      - < 20: 😞 (Sad face)
    - **MO:** Displayed with red/green horizontal pill visualization
      - Green fill on right side for positive momentum
      - Red fill on left side for negative momentum
      - Yellow center line at 50%
      - No integer value displayed on top of pill
  - **Tooltip Feature:** Hovering over any attribute value displays the training change for that attribute
    - Green tooltip for positive changes (e.g., "+5")
    - Red tooltip for negative changes (e.g., "-3")
    - Black tooltip for zero changes
    - Tooltip appears above the attribute value
- **Training Changes View:** Shows net changes from training
  - **Attribute Order:** Same exact order as Attributes view (SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT, NG, EM, MO)
  - Only displays attributes that have changes (maintains order)
  - Positive changes: Green text with `+` prefix
  - Negative changes: Red text with `-` prefix
  - Zero changes: Black text
  - **Aggregated Total Row:** Bottom row displays "Total" in the first column and sums all attribute changes across all players
    - Styled with gold background highlight and bold text
    - Provides quick overview of total training impact
- Displays all players on the team with their attribute values or changes

**Team Report Section:**
- Header: "Team Report"
- Displays all team attributes with visualizations:
  - **Red/Green Pills:** Most attributes (Shooting, Rebounding, Offense, Defense, Fast Breaks, Press/Trap, Aggression, Discipline, Momentum)
    - Yellow center line
    - Green fill to the right for positive values
    - Red fill to the left for negative values
    - Proportional fill based on max value
    - No value displayed on top of pill (value shown in change indicator only)
  - **Progress Bar:** Team Chemistry (0-25 scale, blue fill)
    - Shows value as "X / 25" centered on bar
    - Only attribute that displays its value
  - **+/- Indicators:** Fast Break Defense and Press/Trap Breaks
    - Centered, bold indicators
    - No value displayed next to indicators
    - `+++` (green) for value = 10
    - `++` (green) for values 5-9
    - `+` (green) for values 1-4
    - `-` (yellow) for value = 0
    - `-` (red) for values -1 to -4
    - `--` (red) for values -5 to -9
    - `---` (red) for value = -10

**Playbook Summary Section:**
- Header: "Playbook Summary"
- Located between Team Report and Training Notes sections
- Displays all plays and defenses attached to the team object
- **Layout:**
  - **Offense Section:**
    - All Motion Plays (sorted alphabetically)
    - All Set Plays (sorted alphabetically)
    - Empty row separator
  - **Defense Section:**
    - All Man Defense Plays (sorted alphabetically)
    - All Zone Defense Plays (sorted alphabetically)
- **For each play/defense:**
  - Play/defense name (left-aligned, min-width 200px)
  - Horizontal progress bar (max value 500, fills proportionally based on effectiveness score)
  - Change indicator (right-aligned, min-width 60px):
    - **Positive changes:** Green text with "+" prefix (e.g., "+10")
    - **Negative changes:** Red text with "-" prefix (e.g., "-5")
    - **Zero changes:** White text (e.g., "0")
- **Pre-Training Effectiveness Decay:**
  - Before applying training points, all plays and defenses with effectiveness > 0 are reduced by a random value between 5-15
  - Minimum effectiveness value is 0 (cannot be negative)
  - This decay represents natural skill degradation between training sessions
  - The change indicator shows the net change from the original effectiveness (before decay) to the final effectiveness (after decay + training)

**Training Notes Section:**
- Header: "Training Notes"
- Displays automatically generated notes about training effects
- **NG Reduction Notes:** Automatically generated when players experience NG reduction from scrimmages or conditioning
  - Shows message for multiple players or individual player names
  - Notes appear as paragraphs in the container
- **Placeholder:** If no notes are generated, displays "No training notes for this session." in italic gray text
- Same horizontal width as Player Report and Team Report sections
- Dynamic height: Expands automatically with content
- No internal scrolling: All text is always visible

#### Training Focus Display Format

The training focus is formatted as "Archetype (Sub-Option)" with proper capitalization:
- **Authoritarian** archetype options:
  - "Authoritarian (Discipline)"
  - "Authoritarian (Rebounding)"
  - "Authoritarian (Teamwork)"
  - "Authoritarian (Execution)"
- **Systems Coach** archetype options:
  - "Systems Coach (Offense)"
  - "Systems Coach (Defense)"
  - "Systems Coach (Fast Breaks)"
  - "Systems Coach (Presses/Traps)"
- **Player Maximizer** archetype options:
  - "Player Maximizer (Top 3 Attributes)"
  - "Player Maximizer (Attributes 4-6)"
  - "Player Maximizer (Custom)"
  - "Player Maximizer (Be Opportunistic)"
- **Culture Builder** archetype options:
  - "Culture Builder (Inspire)"
  - "Culture Builder (Community Engagement)"
  - "Culture Builder (Teamwork)"
  - "Culture Builder (Build Confidence)"

#### Schedule Integration

Training report links appear next to scheduled games on the Franchise Command Center schedule:
- Link appears only for user's team's games
- Link appears only if training has been completed for that week
- Link styled in blue (#4a90e2) with reduced font size
- Link text: "[Training Report]"
- Navigates to training report page with correct parameters (mode, franchise_id, team_id, week)

### Data Flow

1. **Training Submission:**
   - User allocates 24 training points and selects coaching focus on `training.html`
   - Frontend sends POST request to `/franchise/run-training` with training data
   - **Data Initialization (Auto-Population):**
     - If `plays_data` is empty or missing, backend automatically populates it from the universal `plays` collection using `populate_team_plays()`
     - If `scouting_data` is empty or missing the `defense` structure, backend automatically initializes it using `TeamManager._init_scouting_data()`
     - Initialized data is saved to the database before training execution
     - This ensures training works even if game plan or playbooks haven't been submitted yet
   - Backend executes training (pre-conditions, point allocation, clamping)
   - Backend stores training report in `franchise_teams.{team_id}.training_reports.{week}`
   - Backend updates player attributes and team attributes in franchise document
   - Backend returns redirect URL to training report page

2. **Training Report Display:**
   - Frontend loads training report data from `/franchise/training-report` endpoint
   - Backend resolves team_id (handles both name and ID formats)
   - Backend retrieves players from `franchise.players` collection (filtered by `meta.team_id`)
   - Backend retrieves training report from `franchise_teams.{team_id}.training_reports.{week}`
   - Frontend renders players table and team attributes with visualizations

3. **Schedule Integration:**
   - Schedule endpoint (`/franchise/schedule`) checks for training reports
   - Adds `has_training_report` and `is_user_team` flags to each game
   - Frontend renders training report links for eligible games

#### Team ID Resolution

The training report system handles team_id in multiple formats:
- **Team Name:** Resolved to team `_id` via database lookup
- **Team ID (string):** Used directly
- **Team ID (ObjectId):** Converted to string

For player loading, the system:
- Checks `meta.team_id` first
- Falls back to `meta.team` name lookup if `team_id` is missing
- Compares resolved team IDs to filter players

### Data Storage

**Franchise Document:**
- `franchise_teams.{team_id}.training_reports.{week}` - Training report for specific week
- `latest_training` - Most recent training report (quick access)
- `training_status.training_completed` - Boolean flag
- `training_status.week` - Week number for last training

**Player Updates:**
- `players.{player_id}.attributes.anchor_{attr}` - Updated attribute values
- `players.{player_id}.position_ratings` - Recalculated position ratings

**Team Updates:**
- `franchise_teams.{team_id}.{attribute_name}` - Updated team attribute values

### Key Files

**Frontend:**
- `FrontEnd/static/training.html` - Training allocation page
- `FrontEnd/static/training.css` - Training page styling
- `FrontEnd/static/training.js` - Training logic and submission
- `FrontEnd/static/training-report.html` - Training report display page
- `FrontEnd/static/training-report.css` - Report page styling
- `FrontEnd/static/training-report.js` - Report data loading and rendering
- `FrontEnd/static/franchise-command-center.js` - Schedule rendering with training report links

**Backend:**
- `BackEnd/models/training_execution_v2.py` - Core training execution logic
- `BackEnd/api/franchise_routes.py` - Training API endpoints
  - `POST /franchise/run-training` - Submit training
  - `GET /franchise/training-report` - Get training report data
  - `GET /franchise/schedule` - Get schedule with training report flags

### Future Enhancements

- Tournament mode training execution
- Single game mode training
- Training history tracking and archiving
- Custom attribute selection for Player Maximizer focus
- Play effectiveness score updates from training
- Training simulation for computer teams

