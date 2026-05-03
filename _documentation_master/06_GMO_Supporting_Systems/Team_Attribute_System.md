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
3. **Attribute Updates**: Training updates these team measures in Franchise/Tournament. In **franchise** mode, **end-of-game (EOG)** also adjusts the same FTD team fields from game output via `update_team_attributes_after_game` (see `End_Of_Game_System.md`).
4. **Persistence**: Changes saved to the appropriate document for the game mode.
5. **Play CMD (franchise):** The scalar list in this doc is not play effectiveness. That same EOG hook applies FTD **offensive** `plays.*.effectiveness` decay from each game’s `times_run` share; training only pre-decays **defense** scouting rows (`Training_System.md`).

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

**Team Attribute Faucets & Sinks**

**Notes**
- **Initial seed:** Included below for completeness. It sets the franchise starting baseline, but is not a progression faucet/sink after the team already exists.
- **Training amplifiers:** Matching coaching focus can amplify positive training gains. `breaks` can also multiply positive session gains; it directly adds extra changes to `team_chemistry` at 3-5 points and to `discipline` / `fight` at 4-5 points.
- **CPU teams:** When the user runs training, non-user teams use distant-training templates. Those template deltas are database-driven and can be positive or negative for any standard team attribute except `momentum_score`.

### Shooting (`shot_threshold`) (range: 10 to 210)
This is the team's intangible mindset to convert baskets. Their overall belief in their identity as a basketball team who scores points. This is a compounding attribute, it compounds both upward and downward, based on the team's in-game performance and training activities.

- Initial seed: Franchise init / missing-FTD creation (`range: 100 to 120`, random).
- Faucet: Training System / Scrimmages.
  Condition: `scrimmages` slider at `0`.
  Range: `0 pts -> +5 to +10` (worse shooting attribute).
- Faucet / slight sink: Training System / Scrimmages.
  Condition: `scrimmages` at `1` pt.
  Range: `+= random.randint(-5, 0)` (neutral to slight improvement).
- Sink: Training System / Scrimmages.
  Condition: `scrimmages` at `2+` pts.
  Range: `2 pts -> -5 to -15`, `3 pts -> -10 to -15`, `4 pts -> -10 to -20`, `5+ pts -> -15 to -20`.
- Faucet: End Of Game System.
  Condition: team FG% `<= 45%`.
  Range: **both** teams `+5 to +10`.
- Mixed EOG: End Of Game System.
  Condition: team FG% `> 45%` and `≤ 50%`.
  Range: winner `+= random.randint(-5, 0)`; loser `+= random.randint(0, 5)`.
- Sink: End Of Game System.
  Condition: team FG% `> 50%`.
  Range: **both** teams `+= random.randint(-10, -5)`.

**UI (Shooting pill and deltas):** Raw `shot_threshold` is a golf score (lower is better). Horizontal pills use **110** as center, **10** at the favorable end and **210** at the unfavorable end. **Training report** and **box score attribute-change** copy invert the numeric delta for display: a raw **−10** shows as **+10** in green; a raw **+5** shows as **−5** in red.

### Rebounding (`rebound_modifier`) (range: 0.0 to 0.4)
This is the team's intangible mindset when it comes to rebounding. Their overall belief in their identity as a basketball team who gets more rebounds than their opponent. This is a compounding attribute, it compounds both upward and downward, based on the team's in-game performance and training activities.

- Initial seed: Franchise init / missing-FTD creation (`0.2` fixed).
- Faucet: Training System / Rebounding drill.
  Condition: `rebounding` slider contributes rounded effective points.
  Range: `1-2 effective pts -> +0.01 to +0.05`, `3-4 -> +0.04 to +0.08`, `5+ -> +0.06 to +0.10`.
- Faucet + Sink: Training System / Scrimmages.
  Condition: scrimmages contributes rounded effective points.
  Range: `1-2 effective pts -> +0.00 to +0.03`, `3-4 -> +0.03 to +0.05`, `5+ -> +0.04 to +0.07`.
- Faucet + Sink: End Of Game System.
  Condition: compare team TREB to opponent TREB.
  <!-- Range: `> opp + 5 -> +0.00 to +0.10`, `< opp - 5 -> -0.10 to +0.00`, otherwise `-0.05 to +0.05`. -->
  Range: `> opp + 8 -> +0.00 to +0.05`, `< opp - 8 -> -0.10 to -0.05`, otherwise `-0.05 to -0.01`.

### Offense Efficiency (`offensive_efficiency`) (range: -10 to 10)
This is how well your team executes the Xs & Os of your offense — running plays, setting screens, making reads, and getting open. This affects how cleanly your offense operates as a unit, independent of raw talent. This is a trained attribute. It naturally decays over time as opponents study your game film and adjust to your tendencies, but you can fight that decay — and push it higher — through diverse play-calling and offense-focused training activities.

- Initial seed: Franchise init / missing-FTD creation (`range: -1 to +1`, random).
- Faucet + Sink: Training System / Offense Install.
  Condition: offense install slider `0-5`.
  Range: `0 -> -2 to -1`, `1 -> +1 to +2`, `2 -> +2 to +3`, `3 -> +3 to +4`, `4 -> +3 to +6`, `5 -> +3 to +7`.
- Sink: End Of Game System.
  Condition: every completed franchise game.
  If total offensive plays used > 12: Range: `-2 to -1`
  Elif total offensive plays used < 13 and > 7: Range: `-3 to -2`
  Elif total offensive plays used < 8: Range: `-4 to -3`

### Defense Efficiency (`defensive_efficiency`) (range: -10 to 10)
This is how well your team executes the Xs & Os of your defense — rotating on time, closing out, communicating switches, and making life difficult for the offense. Raw athleticism only takes you so far; this is what separates a disciplined unit from a collection of individuals. This is a trained attribute. It naturally decays over time as opponents study your game film and adjust to your tendencies, but you can fight that decay — and push it higher — through diverse play-calling and defense-focused training activities.

- Initial seed: Franchise init / missing-FTD creation (`range: -1 to +1`, random).
- Faucet + Sink: Training System / Defense Install.
  Condition: defense install slider `0-5`.
  Range: `0 -> -2 to -1`, `1 -> +1 to +2`, `2 -> +2 to +3`, `3 -> +3 to +4`, `4 -> +3 to +6`, `5 -> +3 to +7`.
- Sink: End Of Game System.
  Condition: every completed franchise game.
  If any one defensive play > 49% of all defensive plays called for that game: Range: `-4 to -3`
  Elif any one defensive play > 39% of all defensive plays called for that game: Range: `-3 to -2`
  Else: Range: `-2 to -1`

### Fast Break Efficiency (`fb_efficiency`) (range: -10 to 10)
This is how well your team executes in transition — pushing the pace, hitting the right moments to run, and converting opportunities before the defense can set up. This affects both how often your team generates fast break chances and how effectively they finish them. This is a trained attribute. It naturally decays over time as opponents study your game film and adjust to your tendencies, but you can fight that decay — and push it higher — through a committed fast break install, a balanced Fast Break playbook and dedicated fast break training activities.

- Initial seed: Franchise init / missing-FTD creation (`range: -1 to +1`, random).
- Faucet + Sink: Training System / Fast Break Offense Install.
  Condition: fast-break offense install slider `0-5`.
  Range: `0 -> -2 to -1`, `1 -> +1 to +2`, `2 -> +2 to +3`, `3 -> +3 to +4`, `4 -> +3 to +6`, `5 -> +3 to +7`.
- Sink: End of Game System
  Condition: every completed franchise game
  If any one Fast Break Play > 60% of Fast Break plays called for that game: Range: `-4 to -3`
  Elif any one Fast Break Play > 50%: Range: `-3 to -2`
  Else: Range: `-2 to -1`
- Faucet + Sink: End Of Game System / distant-sim override.
  Condition: distant-simmed franchise games only.
  Range: `-2 to +1`.

### Press/Trap Break Efficiency (`pt_efficiency`) (range: -10 to 10)
This is how well your team executes full court presses and half court traps — timing the traps, cutting off passing lanes, and turning defensive pressure into live ball turnovers. This affects both how often your team disrupts the opponent's offense and how effectively they convert that pressure into scoring opportunities. This is a trained attribute. It naturally decays over time as opponents study your game film and adjust to your tendencies, but you can fight that decay — and push it higher — through a committed press/trap install, a disciplined approach to how often you deploy it, and dedicated press/trap training activities.

- Initial seed: Franchise init / missing-FTD creation (`range: -1 to +1`, random).
- Faucet + Sink: Training System / P/T Defense Install.
  Condition: press/trap defense install slider `0-5`.
  Range: `0 -> -2 to -1`, `1 -> +1 to +2`, `2 -> +2 to +3`, `3 -> +3 to +4`, `4 -> +3 to +6`, `5 -> +3 to +7`.
- Sink: End of Game System
  If total presses & traps run > 20: Range: `-4 to -3`
  Elif total presses & traps run > 15: Range: `-3 to -2`
  Else: Range: `-2 to -1`
- Faucet + Sink: End Of Game System / distant-sim override.
  Condition: distant-simmed franchise games only.
  Range: `-2 to +1`.

### Fight (`fight`) (range: -10 to 10)
Represents your team’s competitive edge. High Fight teams have great resilience, they handle adverse situations well, and perform with urgency when trailing. This is a compounding attribute, it compounds both upward and downward, based on the team's in-game performance and training activities.

- Initial seed: Franchise init / missing-FTD creation (`range: -1 to +1`, random).
- Faucet: Training System / Strength + Conditioning.
  Condition: strength and conditioning contribute positive rounded effective points.
  Range (shared fight/discipline bucket table after 0.5× accrual rounds): `0 -> -4 to -3`, `1 -> -3 to -1`, `2 -> -1 to +1`, `3 -> +1 to +2`, `4 -> +2 to +3`, `5+ -> +2 to +4`.
- Sink: Training System / Breaks.
  Condition: `breaks` slider at `4` or `5`.
  Range: `4 pts -> -2 to 0`, `5 pts -> -3 to -1`.
- Faucet: Traning System / Coaching Focus
  If the user chooses any of the Culture Builder:  Range: `0 to +1`
- Faucet: End Of Game System.
  Condition: team won the game.
  Range: `-1 to +1`.
- Sink: End Of Game System.
  Condition: team lost the game.
  Range: `-3 to -1`.

### Discipline (`discipline`) (range: -10 to 10)
Reflects polish and control. Disciplined teams commit fewer unnecessary fouls and turnovers, execute aggressive strategies with precision, and maintain composure late in games. It balances Fight very well — aggression without structure becomes chaos. This is a compounding attribute, it compounds both upward and downward, based on the team's in-game performance and training activities.

- Initial seed: Franchise init / missing-FTD creation (`range: -1 to +1`, random).
- Faucet: Training System / Inside Defense, Outside Defense, Passing, Ball Handling.
  Condition: those drills contribute positive rounded effective points (0.25× per drill point, summed, half-up).
  Range: same bucket table as **Fight** after rounding: `0 -> -4 to -3`, `1 -> -3 to -1`, `2 -> -1 to +1`, `3 -> +1 to +2`, `4 -> +2 to +3`, `5+ -> +2 to +4`.
- Sink: Training System / Breaks.
  Condition: `breaks` slider at `4` or `5`.
  Range: `4 pts -> -2 to 0`, `5 pts -> -3 to -1`.
- Faucet: Traning System / Coaching Focus
  If the user chooses any of the Authoritarian:  Range: `0 to +1`
- Faucet: End Of Game System.
  Condition: team `(F + TO)` is lower than opponent `(F + TO)` + 8.
  Range: `0 to +1`.
- Sink: End Of Game System.
  Condition: team `(F + TO)` is greater than or equal to opponent `(F + TO)` + 8.
  Range: `-3 to -2`.
- Else: Range: `-1 to 0`

### Momentum (`momentum_score`) (range: -10 to 10)

- Initial seed: FTD creation sets `0`.
- No current franchise progression faucets or sinks in the working code.
- Note: `momentum_score` exists in clamps / legacy paths, but current training and EOG flows do not update it.

### Team Chemistry (`team_chemistry`) (range: 7 to 25)
The connective tissue of your roster. Chemistry influences how well players support one another through mistakes, adversity, and high-pressure moments. Winning strengthens it. Internal friction and extended losing can strain it. You may not see the impact of this attribute directly — but you will definitely feel it. This is a compounding attribute, it compounds both upward and downward, based on the team's in-game performance and training activities.

- Initial seed: Franchise init / missing-FTD creation (`range: 7 to 10`, random).
- Faucet: Training System / Free Throws, Film Study, Scrimmages.
  Condition: those drills contribute positive rounded effective points.
  Range: standard team-attr training range after rounding: `0 -> -3 to -1`, `1 -> +1 to +2`, `2 -> +2 to +3`, `3 -> +3 to +4`, `4 -> +3 to +6`, `5 -> +3 to +7`.
- Faucet + Sink: Training System / Breaks.
  Condition: `breaks` slider at `4` or `5`.
  Range: `3 pts -> -1 to +1`, `4 pts -> -2 to +2`, `5 pts -> -3 to +3`.
- Faucet: Training System / Team Building.
  Condition: coaching focus = `culture-builder-teamwork`.
  Range: `+1 to +3`.
- Faucet: End Of Game System.
  Condition: team won the game.
  Range: score delta `<4 -> +1 to +2`, `<10 -> +1 to +3`, `>=10 -> +2 to +4`.
- Sink: End Of Game System.
  Condition: team lost the game.
  Range: score delta `<4 -> -2 to -1`, `<10 -> -2 to -4`, `>=10 -> -6 to -4`.

### FB Opp Modifier (`fb_opp_modifier`) (range: -10 to 10)
This is how well your team defends fast breaks and transition offenses. Containing the pace, cutting off passing lanes, and not allowing easy transition buckets. This is a trained attribute. It naturally decays over time as opponents study your game film and adjust to your tendencies, but you can fight that decay — and push it higher — through a committed Fast Break Defense install and film study of your opponent.

- Initial seed: Franchise init / missing-FTD creation (`range: -1 to +1`, random).
- Faucet + Sink: Training System / Fast Break Defense Install.
  Condition: fast-break defense install slider `0-5`.
  Range: `0 -> -2 to -1`, `1 -> +1 to +2`, `2 -> +2 to +3`, `3 -> +3 to +4`, `4 -> +3 to +6`, `5 -> +3 to +7`.
- Sink: End of Game System
  Condition: every completed franchise game
  If opponent ran > 20 Fast Breaks: Range: `-4 to -3`
  Elif Opponent ran > 10 Fast Breaks: Range: `-3 to -2`
  Else: Range: `-2 to -1`
- Faucet + Sink: End Of Game System / distant-sim override.
  Condition: distant-simmed franchise games only.
  Range: `-2 to +1`.

### P/T Opp Modifier (`pt_opp_modifier`) (range: -10 to 10)
This is how well your team and work through your opponent's presses and traps. Handling the pressure of these disruptive defenses is key to avoiding the many mistakes they can cause. This is a trained attribute. It naturally decays over time as opponents study your game film and adjust to your tendencies, but you can fight that decay — and push it higher — through a committed Press/Trap Offense install and film study of your opponent.

- Initial seed: Franchise init / missing-FTD creation (`range: -1 to +1`, random).
- Faucet + Sink: Training System / P/T Offense Install.
  Condition: press/trap offense install slider `0-5`.
  Range: `0 -> -2 to -1`, `1 -> +1 to +2`, `2 -> +2 to +3`, `3 -> +3 to +4`, `4 -> +3 to +6`, `5 -> +3 to +7`.
- Sink: End of Game System
  Condition: every completed franchise game
  If opponent ran > 20 Presses + Traps: Range: `-4 to -3`
  Elif Opponent ran > 10 Presses + Traps: Range: `-3 to -2`
  Else: Range: `-2 to -1`
- Faucet + Sink: End Of Game System / distant-sim override.
  Condition: distant-simmed franchise games only.
  Range: `-2 to +1`.


**Team Attribute Impact on Gameplay**

1. Shot Threshold
- Determines the make/miss threshold for standard shot resolution.
- Impacts fast-break shot thresholds during fast-break scoring sequences.
- Impacts special late-game balancing shot-threshold overrides.
- Combines with Home Crowd shot-threshold adjustments.

2. Rebound Modifier
- Impacts offensive-rebound outcomes.
- Impacts defensive-rebound outcomes.
- Impacts rebound resolution after missed standard shots.
- Impacts rebound resolution after missed free throws.

3. Offense Efficiency
- Impacts half-court possession resolution on offense.
- Helps determine offensive execution advantage during standard possession play.

4. Defense Efficiency
- Impacts half-court possession resolution on defense.
- Helps determine defensive execution advantage during standard possession play.

5. Fast Break Efficiency
- Impacts fast-break offensive success.
- Impacts rim-runner fast-break outlet and conversion sequences.
- Impacts fast-break-specific shot-threshold overrides.

6. P/T Efficiency
- Impacts Full-Court Press defensive resolution.
- Impacts Half-Court Trap defensive resolution.
- Impacts defensive pressure success during press/trap gameplay events.

7. Fight
- Impacts offensive foul tendency.
- Impacts defensive foul tendency.
- Impacts turnover/foul calibration during possession resolution.
- Impacts late-game balancing behavior for trailing teams.
- Impacts fast-break shot-threshold adjustments against set defenders.
- Impacts Full-Court Press resolution.
- Impacts Half-Court Trap resolution.
- Impacts block-attempt checks in shot resolution.

8. Discipline
- Impacts steal and turnover calibration during possession resolution.
- Impacts dead-ball turnover calibration.
- Impacts shot-foul likelihood in shot resolution.
- Impacts late-game balancing behavior for leading teams.
- Impacts turnover checks during gameplay resolution.
- Impacts Full-Court Press resolution.
- Impacts Half-Court Trap resolution.
- Impacts violation / recalibration checks tied to offensive organization.
- Impacts charge resolution.

9. Momentum
- No current direct gameplay impact in the working code.

10. Team Chemistry
- Impacts fast-break shot-threshold adjustments against set defenders.
- Impacts Full-Court Press resolution.
- Impacts Half-Court Trap resolution.
- Impacts charge resolution.
- Impacts lineup auto-selection / autoset-lineup pool behavior.
- Impacts Home Crowd strength bands through the Home Crowd system.

11. FB Opp Modifier
- Impacts fast-break defensive success.
- Impacts rim-runner fast-break outlet and conversion defense.

12. P/T Opp Modifier
- Impacts Full-Court Press offensive resistance.
- Impacts Half-Court Trap offensive resistance.
- Impacts offensive resistance to press/trap pressure during gameplay events.
