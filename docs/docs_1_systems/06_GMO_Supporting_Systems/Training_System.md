## Training System

This document should reflect the current franchise training implementation in code. If behavior here conflicts with `BackEnd/models/training_execution_v2.py`, `BackEnd/models/training_notes.py`, or `BackEnd/api/franchise_routes.py`, update this doc to match the live implementation.

**Base Constants**

1. **Total Training Points**:
   - **Training Camp (Week 1, before first games)**: 30 points
   - **All Other Trainings (Week 1+ after games)**: 24 points per training session
2. **Slider Range**: 0-5 points per slider (discrete steps)
3. **Training Page Files**: `FrontEnd/static/training.html`, `FrontEnd/static/training.js`, `FrontEnd/static/training.css`
4. **Training Report Page**: `FrontEnd/static/training-report.html`
5. **Backend Execution**: `BackEnd/models/training_execution_v2.py`
6. **API Endpoints**:
   - `GET /franchise/training-points` - Get available training points (30 for training camp, 24 for regular training)
   - `POST /franchise/run-training` - Submit training
   - `GET /franchise/training-report` - Get training report data
7. **Coaching Focus Archetypes**: Authoritarian, Systems Coach, Player Maximizer, Culture Builder
8. **Rebound Modifier Range**: 0.0-0.4 (clamped)
9. **Pre-Training Decay**: Plays/defenses with effectiveness > 0 reduced by `random.randint(5, 15)`

**Training System Flow (16 Steps)**

1. **Page Load**: Frontend fetches training points from `/franchise/training-points` endpoint (30 for training camp, 24 for regular training)
2. **User Allocates Points**: User distributes training points (30 or 24) across 20 sliders (player drills, team drills, general)
3. **User Selects Focus**: User selects one coaching focus archetype and sub-option
4. **Recruiting Invites Access (Weeks 20-26 only)**: Training page shows a green `Recruiting Invites` button below `Submit Training` that routes to `recruiting-orders.html`
5. **Submit Training**: Frontend sends POST request to `/franchise/run-training` with training data
6. **Backend Validation**: Backend validates total points match expected (30 for training camp, 24 for regular training)
   - week 20 special case: if no recruiting orders have ever been saved, training is blocked until the user saves recruiting orders
7. **Data Auto-Population**: Backend initializes `plays_data` and `scouting_data` if missing
8. **Pre-Training Decay**: All plays/defenses with effectiveness > 0 reduced by 5-15 points (skipped for training camp: week 1 before first games)
9. **Pre-Training Conditions**: Random decreases applied to player attributes (excluding EM, MO, NG); team attributes are no longer decayed here (skipped for training camp: week 1 before first games)
10. **Training Point Application**: Drill allocations mapped to attributes, random increases applied based on points
11. **Coaching Focus Amplifiers**: Selected focus amplifies specific attribute gains
12. **Attribute Clamping**: All values clamped to valid ranges (see **Attribute_Clamp_System.md** for player and team clamp ranges)
13. **Weeks 20-26 Recruiting Invite Processing**: During recruiting invite season, `Submit Training` also runs that week's recruiting invite processing using the user's saved recruiting orders plus CPU weekly recruiting logic
14. **User Team Report Generation**: Training report stored, player/team attributes updated, redirect to report page
15. **Computer Team Training**: All non-user teams run **distant training** using template-based updates (not the full user-team training execution flow)
16. **Post-Training Camp Cuts**: After week 1 training camp only, any team above 12 players must reduce to a legal 12-player roster before gameplay resumes.

### Post-Training Camp Cut Flow

- **Trigger:** Only after franchise week 1 training camp is completed.
- **User Team:**
  - If user roster size is greater than 12 when the user returns to FCC from the training report, FCC shows a modal:
    - `You need to cut X players`
  - Main FCC CTA becomes `Cut Players`
  - User is routed to `cut-players.html`
  - `cut-players.html` shows the full roster table plus a `Players To Cut` checkbox column
  - `Submit Cuts` is active only when exactly `roster_size - 12` players are checked
  - Confirmation modal copy:
    - `You are going to cut {player name}, {player name}, and {player name}. This cannot be undone. Are you sure you want to proceed with the cuts?`
  - Success modal copy:
    - `{player name}, {player name}, and {player name} have been cut.`
  - After successful cuts, user returns to FCC and normal weekly cadence resumes
- **CPU Teams:**
  - After week 1 training camp, any CPU team above 12 players automatically cuts down to 12
  - Cut rule:
    - lowest RT first
    - RT tie -> older year first (`Senior`, `Junior`, `Sophomore`, `Freshman`)
    - remaining tie -> random

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
    - **Choose Attributes** opens a modal: **Top 3**, **Attributes 4–6**, **Positional Focus** (primary by highest RT, fixed triple per position), or **Custom** (three distinct attrs per player). Submit sends the resolved leaf (`player-maximizer-top-3`, `player-maximizer-attributes-4-6`, `player-maximizer-positional-focus`, or `player-maximizer-custom`). Off-screen radios support Auto-Train picking top-3 / 4–6 / positional without the modal.
  - **Culture Builder** (purple header fill)
    - Sub-options: Inspire, Confidence, Community Engagement, Team Building

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
- **Users must select a specific focus option** - archetype headers are display-only and cannot be selected
- Selecting any focus option clears all others

**Visual Behavior:**
- **Focus option radio selected:**
  - Only that radio fills with the archetype's header color
  - Archetype block shows a subtle outline in the same color (more subtle than header selection)

### Submit Button Behavior

- Disabled / visually muted (reduced opacity, non-clickable) until:
  1. All training points are allocated (Points Remaining = 0) - 30 for first training, 24 otherwise
  2. A coaching focus is selected
  3. **Player Maximizer / Choose Attributes:** user has tapped **Assign Focus Attributes** in the modal (or Auto-Train selected a hidden leaf). For **Custom**, every player needs three distinct picks.
- Becomes active only when all conditions are met

### Auto-Train Button

- **Button:** "Auto-Train" (header, right side)
- **Behavior when clicked:**
  - Automatically assigns all training points across the 20 sliders
    - Sets all 20 sliders to `1` (20 points)
    - Randomly selects additional sliders to set to `2`:
      - **24 points**: 4 sliders set to `2` (20 + 4 = 24)
      - **30 points**: 10 sliders set to `2` (20 + 10 = 30)
  - Randomly selects a Coaching Focus (one of the existing focus options, not archetype headers)
  - Shows confirmation popup: `Training Points Assigned` then `Assigned {Focus Name} Focus` (e.g. `Assigned Attributes 4–6 (Player Maximizer) Focus` for hidden PM leaves)
    - Popup has a "Close" button; closing keeps the user on the Training page
  - After auto-assign, Points Remaining = 0 and Submit becomes eligible (provided focus set by auto-train)

### Backend Training Execution System

**Location:** `BackEnd/models/training_execution_v2.py`

The training execution system applies pre-training conditions, allocates training points, applies coaching focus amplifiers, and generates training reports.

#### Coaching focus string (API ↔ amplifiers)

- The Training page submits each radio’s **`value`** exactly as in `FrontEnd/static/training.html` (e.g. `authoritarian-discipline`, `systems-coach-offense`, `culture-builder-inspire`).
- The backend **`parse_coaching_focus()`** in `training_execution_v2.py` maps that string to:
  - **`archetype`**: one of `authoritarian`, `systems-coach`, `player-maximizer`, `culture-builder` (for reports and grouping).
  - **`sub_option`**: the **full** radio value for a leaf selection (same string as the UI), or `None` if only an archetype-level value is sent (e.g. some auto-train random picks).
- Amplifiers and Systems Coach play-point multipliers compare **`sub_option`** to those full values (they must **not** use a naive `split("-", 1)` on the raw string, which breaks multi-word archetypes like `systems-coach`).

#### Community Engagement (`culture-builder-community`)

- **Franchise only** (no training in Single Game / Tournament).
- **Immediate training effect:** small EM bump for all players (see `training_execution_v2.py`).
- **Next franchise game (home crowd roll):** sets **`pending_community_engagement`** on that team’s **FTD** (`franchise_team_data`). When a franchise game is started (`/api/init-game` or new-game `simulate-quarter` path), the engine reads pending flags for **both** teams, resolves a single band shift for the **home crowd weight table** (see `Home_Crowd_System.md`), then clears both teams’ flags.
- **User home:** shift crowd weights **up** one chemistry band vs the user’s current `team_chemistry` for the home team in that game; if already in **21–25**, use the **Upper Bonus Range** row from `Home_Crowd_System.md` instead.
- **User away:** shift **down** one band vs the **home opponent’s** `team_chemistry`; if opponent chemistry is in **7–10**, no downward effect.
- **Computer:** distant training templates may set `community_engagement` on the template; when applied, that CPU team gets `pending_community_engagement` on FTD for the same rules (only CE vs no CE: CPU home → shift up from CPU chemistry; CPU away → shift down from user’s home chemistry).
- **Both teams pending CE** in the same matchup: shifts **cancel** (normal roll from actual home `team_chemistry`).
- **Bye week:** if no game is played after training, the pending flag stays until the **next** game in that season.

#### Training Execution Flow

0. **Pre-Training Effectiveness Decay** (`_apply_pre_training_effectiveness_decay`, `_apply_pre_training_defense_decay`)
   - All plays and defenses with effectiveness > 0 are reduced by `random.randint(5, 15)`
   - Minimum effectiveness is clamped to 0 (cannot be negative)
   - This represents natural skill degradation between training sessions
   - Original effectiveness values are tracked for change calculation
   - **Skipped for training camp in franchise mode** - determined by `week == 1 and not results.get("1")`, no depreciation occurs before first games

1. **Pre-Training Conditions** (`apply_pre_training_conditions`)
   - Applies random decreases to player attributes (excluding EM, MO, NG)
   - Player attributes: see pre-training decay section below
   - Team attributes are no longer decayed in training. They are updated at the end of each game based on performance (see End_Of_Game_System.md). For a side-by-side of how each team attribute is changed in EOG vs Training, see `docs/To Do/team_attributes_eog_vs_training_comparison.md`.
   - **Skipped for training camp in franchise mode** - determined by `week == 1 and not results.get("1")`, no depreciation occurs before first games

2. **Training Point Application** (`apply_training_points`)
   - Maps drill allocations to player/team attributes
   - Applies random increases based on points allocated
   - Applies coaching focus amplifiers
   - Handles special cases (conditioning, film study, breaks)

3. **Play/Defense Training Application** (`apply_play_defense_training`, `_apply_offense_play_training`, `_apply_defense_training`)
   - Distributes offense/defense **install** point pools to **effectiveness** (Command) on plays and defenses (not per-play momentum/cloaking).
   - Uses `playbook_training_mode` (`current-playbooks`, `all-plays-even`, etc.), `strategy_settings`, and `playbook_settings` for motion/set and man/zone splits.
   - **Systems Coach** offense/defense: multiplies the install point **pool** before distribution when the matching focus is selected.
   - **Authoritarian Execution** / **Teamwork**: after points are allocated to specific plays/defenses, multiplies only the **effectiveness** gains that land on **set + Man** (Execution) or **motion + zone** defenses (Teamwork); see **Coaching Focus Amplifiers**.

4. **Attribute Clamping**
   - Player attributes: Minimum 1, no maximum
   - Team attributes: Clamped to defined ranges (see **Attribute_Clamp_System.md** for full list; implemented as `TEAM_ATTR_CLAMPS` in `training_execution_v2.py`)

5. **Training Report Generation**
   - Calculates changes from original baselines
   - Returns player_changes and team_changes dictionaries
   - Includes coaching focus information

#### Drill-to-Attribute Mapping

**Player Drills:**
- Inside Offense → SC
- Outside Offense → SH
- Inside Defense → ID, (Discipline: 0.25 points)
- Outside Defense → OD, (Discipline: 0.25 points)
- Ball Handling → BH, (Discipline: 0.25 points)
- Passing → PS, (Discipline, 0.25 points)
- Rebounding → RB (Rebound Modifier: 0.5 points)
- Strength Training → ST, (Fight, 0.5 points)
- Agility Training → AG
- Free Throws → FT, (Team Chemistry: 0.25 points)
- Conditioning → ND (Endurance), CH, (Fight: 0.5 points)
- Film Study → IQ, CH, (Team Chemistry: 0.25 points)

**Team Drills:**
- Offense Install → `offensive_efficiency`
- Defense Install → `defensive_efficiency`
- Fast Break Offense Install → `fb_efficiency`
- Fast Break Defense Install → `fb_opp_modifier`
- P/T Defense Install → `pt_efficiency`
- P/T Offense Install → `pt_opp_modifier`
- Scrimmages → Team Chemistry: 0.5 points, Shot Threshold: 1 point, Rebound Modifier: 0.5 points, NG Reduction (if 3-5 points)

#### Training Point Ranges

**Player Attributes (Base Ranges):**
- 0 points: `+= random.randint(-2, -1)`
- 1 point: `+= random.randint(0, 1)`
- 2 points: `+= random.randint(2, 3)`
- 3 points: `+= random.randint(2, 4)`
- 4 points: `+= random.randint(3, 5)`
- 5 points: `+= random.randint(3, 6)`

**High Attribute Gain Reduction**
- If a player's starting value for a trained attribute at the beginning of the training session is `> 100`, any positive gain to that attribute is reduced by `50%`, using rounded integer value.
- Example: if a player starts training with `SH = 102` and rolls a gain of `+5`, the applied gain becomes `+3`.
- This check uses the player's value at the start of training, not the running updated value during the session.
- If a player starts training at `99` and gains `+6`, the full `+6` applies even if the player finishes above `100`.

**Year-Based Adjustments:**
Leave minimums as is, only change maximums
- **Freshman**: 0 to min, 5 to max (e.g., 1 point: `random.randint(0, 6)`)
- **Sophomore**: 0 to min, 3 to max
- **Junior**: 0 to min, 2 to max
- **Senior**: 0 to min, 1 to max

**Year-Based Pre-Training Decay**
- **Freshman**: -5  min, -2  max
- **Sophomore**: -4  min, -1  max
- **Junior**: -3  min to -1  max
- **Senior**: -2  min to 0  max

**Training Camp Bonus System**
For training camp only, the following bonus will be run for each player, based on his CH value and his highest RT position.
- Core Attributes by position:
  - PG: PS, BH, IQ
  - SG: SH, FT, OD
  - SF: AG, choose 2 of these at random (SC, SH, ID, OD)
  - PF: RB, ST, ID
  - C: SC, ST, ID
- Note: if a player has multiple positions tied for the highest RT, choose one at random

Then use the following CH scale for each player:
- If CH > 80, for each core attribute `+= random.randint(4, 8)`
- `elif CH > 60`: for each core attribute `+= random.randint(3, 6)`
- `elif CH > 40`: for each core attribute `+= random.randint(2, 4)`
- `elif CH > 20`: for each core attribute `+= random.randint(1, 2)`
- else: no bonus applied

**Team Attributes (training ranges by group):**
- Standard install attrs (`offensive_efficiency`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`):
  `0 -> -2 to -1`, `1 -> +1 to +2`, `2 -> +2 to +3`, `3 -> +3 to +4`, `4 -> +3 to +6`, `5 -> +3 to +7`
- `fight` and `discipline`:
  `0 -> -3 to -1`, `1 -> +1 to +2`, `2 -> +2 to +3`, `3 -> +2 to +5`, `4 -> +2 to +6`, `5 -> +2 to +7`
- `team_chemistry`:
  `0 -> -3 to -1`, `1 -> +1 to +2`, `2 -> +2 to +3`, `3 -> +3 to +4`, `4 -> +3 to +6`, `5 -> +3 to +7`

**Rebound Modifier (Technical Drills - in 0.01 increments):**
- `1-2 points -> +0.00 to +0.03`
- `3-4 points -> +0.03 to +0.07`
- `5 points -> +0.04 to +0.10`

**Rebound Modifier (Scrimmages - in 0.01 increments):**
- `1-2 points -> -0.03 to +0.03`
- `3-4 points -> +0.02 to +0.05`
- `5 points -> +0.03 to +0.07`

**Shot Threshold:**
- 0 points: `+= random.randint(10, 20)`
- 1 point: `+= random.randint(-5, 5)`
- 2 points: `-= random.randint(5, 15)`
- 3 points: `-= random.randint(5, 25)`
- 4 points: `-= random.randint(10, 25)`
- 5 points: `-= random.randint(10, 30)`

#### Coaching Focus Amplifiers

**Two multiplier mechanisms in code** (`training_execution_v2.py`):

1. **Drill / team-attribute training:** When `_should_amplify_player_attr` / `_should_amplify_team_attr` (or special cases) apply, qualifying gains use `focus_multiplier = random.choice([1.5, 1.6, 1.7, 1.8])` in `_apply_player_training_points`, `_apply_team_training_points`, and rebound-modifier training. *(Older docs listed 1.3–1.6 for some focuses; implementation uses this single band.)*
2. **Install training (play/defense effectiveness only):** Authoritarian **Execution** and **Teamwork** use one session roll of the same `[1.5, 1.6, 1.7, 1.8]` values on integer **effectiveness** (Command) increments only, via `_scale_install_training_effectiveness_points`—not on momentum/cloaking (install does not allocate to those).

**Authoritarian (all four sub-options implemented):**
- **Discipline:** Amplifies BH, `fight`, `discipline` (drill / team-attribute mechanism *#1*). Also adds flat `discipline += random.randint(0, 1)` once per training session.
- **Rebounding:** Amplifies RB, `rebound_modifier` (mechanism *#1*).
- **Teamwork:** Amplifies PS, IQ (mechanism *#1*). Also amplifies install **effectiveness** gains on **motion** plays and **zone** defenses only (mechanism *#2*). Man and set plays receive base install gains only under this focus.
- **Execution:** Amplifies install **effectiveness** gains on **set plays** and **Man** only (mechanism *#2*). Motion and zone defenses receive base install gains only under this focus.

**Systems Coach:**
- Offense / Defense: Drill gains to `offensive_efficiency` / `defensive_efficiency` use mechanism *#1* above. Install: multiplies offense or defense **play point pool** by the same `[1.5, 1.6, 1.7, 1.8]` band before `_apply_offense_play_training` / `_apply_defense_training` when `systems-coach-offense` or `systems-coach-defense` is selected.
- Fast Breaks: Amplifies `fb_efficiency` and `fb_opp_modifier` drill gains (mechanism *#1*).
- Presses/Traps: Amplifies `pt_efficiency` and `pt_opp_modifier` drill gains (mechanism *#1*).

**Player Maximizer:**
- Top 3 Attributes: Amplifies gains to player's top 3 attributes (excluding CH, EM, MO, NG)
- Attributes 4-6: Amplifies gains to player's 4th–6th highest attributes among the same set as Top 3 (excluding CH, EM, MO, NG)
- **Positional Focus** (`player-maximizer-positional-focus`): Primary position from highest **RT** (ties PG→SG→SF→PF→C); fixed triple per primary—PG: PS/BH/IQ; SG: SH/OD/AG; SF: SC/ST/AG; PF: RB/ID/ST; C: SC/ID/ST. Same focus multiplier on drill gains to those attrs.
- **Custom:** User picks **three** distinct attributes per player (same ranking set as Top 3 / 4–6). Franchise UI sends `coaching_focus_custom_by_player` with `{ player_id: [attrA, attrB, attrC] }` for every roster player. Roster rows include `attrs` and `position_ratings`; list order **highest RT** descending.

**Culture Builder:**
- Inspire: **Flat block:** each player gets **EM** `+random.randint(2, 5)` and **MO** `+random.randint(1, 2)` (caps apply); no focus multiplier on those. **team_chemistry** training gains use `random.choice([1.5, 1.6, 1.7, 1.8])` under Inspire.
- Community Engagement: Improves EM, affects crowd factors (carried to next game)
- **Team Building** (`culture-builder-teamwork`): **Team chemistry** `+random.randint(1, 3)` once per session (clamped like other team attrs). UI label only; API `value` unchanged.
- **Build Confidence:** **CH** (conditioning, film study) and **FT** (free throws) drill gains use the standard focus multiplier `random.choice([1.5, 1.6, 1.7, 1.8])` (after CH’s 0.5 drill coefficient). No flat EM/MO block; no Inspire-style team chemistry mult.
- Any Culture Builder archetype also adds flat `fight += random.randint(0, 1)` once per training session.

#### Breaks Effect

The "Breaks" slider applies a multiplier to all positive gains (not losses):
- 0 points: `random.choice([0.85, 0.9, 0.95])`
- 1 point: `random.choice([0.9, 0.95, 1, 1, 1])`
- 2 points: `random.choice([1, 1, 1.05, 1.1])`
- 3 points: `random.choice([1, 1.05, 1.1])` + Team Chemistry `+= random.randint(-1, 1)`
- 4 points: `random.choice([1, 1.05, 1.1, 1.1])` + Team Chemistry `+= random.randint(-2, 2)` + Discipline `+= random.randint(-2, 0)` + Fight `+= random.randint(-2, 0)`
- 5 points: `random.choice([1, 1.05, 1.1, 1.15])` + Team Chemistry `+= random.randint(-3, 3)` + Discipline `+= random.randint(-3, -1)` + Fight `+= random.randint(-3, -1)`

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

After training is submitted, users are automatically redirected to the training report page which displays detailed information about attribute changes. The report can also be opened from the **Inbox** tab on the Franchise Command Center (see below) and via other FCC links (e.g. schedule) where applicable.

#### FCC Inbox (training report shortcut)

- **Tab:** Franchise Command Center → **Inbox** (`tutorials-tab` in the FCC HTML).
- **Message:** When the franchise has a stored latest training report (`latest_training.week` on the franchise document), the API exposes `last_training_report_week` on `GET /franchise/command-center/data`. The Inbox shows: `Week {N} training report` with **`here`** as a link to `training-report.html` with `from=inbox`.
- **Single active link:** The Inbox only surfaces the **most recent** training report week. When the user runs training for a new week, `latest_training` updates and the Inbox copy and link target week update; older weeks are not listed in the Inbox.
- **Training report behavior when `from=inbox`:** The header control is labeled **Back** and returns to `franchise-command-center.html` with `tab=tutorials-tab` (Inbox). There is no **Go To Locker Room** action on this entry path.
- **Training report behavior when `from=training` (or omitted for legacy URLs):** After `POST /franchise/run-training`, redirects include `from=training`. The header control is **Go To Locker Room** and uses the existing locker-room / command-center navigation (same as before). This is the only path that shows that action button.

#### Page Layout

**Header Section:**
- Page title: "TRAINING REPORT"
- Week number
- Upcoming Opponent (from schedule)
- Training Focus (formatted as "Focus (Archetype)", e.g., "Inspire (Culture Builder)")
- Top-right header control (behavior depends on `from` query parameter):
  - **`from=inbox` (franchise):** **Back** → Franchise Command Center, Inbox tab
  - **Otherwise (e.g. `from=training` or absent):** Orange **Go To Locker Room** → Franchise or Tournament Command Center (existing behavior)

**Player Report Section:**
- Header: "Player Report"
- Toggle between "Attributes" and "Training Changes" views
- **Player Order:** Players are displayed by highest `RT` value, descending. If two players share the same highest `RT`, their existing roster/report order is the tiebreaker.
- **Attributes View:** Shows current attribute values after training
  - **Attribute Order:** Attributes displayed in exact order: SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT, NG, EM, RT
  - **Note:** MO (Momentum) is excluded from Training Report display
  - **Attribute Formatting:**
    - **SC through FT (first 12):** Displayed as integer values
    - **NG:** Displayed with 2 decimal places (e.g., 1.00, 0.99, 0.98, 0.90)
    - **EM:** Displayed with emoji based on value:
      - >= 80: 😎 (Sunglasses)
      - >= 60: 😊 (Big smile)
      - >= 40: 😐 (Straight face)
      - >= 20: 😕 (Slight frown)
      - < 20: 😡 (Angry face)
    - **MO:** Displayed with red/green horizontal pill visualization
      - Green fill on right side for positive momentum
      - Red fill on left side for negative momentum
      - Yellow center line at 50%
      - No integer value displayed on top of pill
    - **RT:** Static highest position-rating value for the player
  - **Tooltip Feature:** Hovering over any attribute value displays the training change for that attribute
    - Green tooltip for positive changes (e.g., "+5")
    - Red tooltip for negative changes (e.g., "-3")
    - Black tooltip for zero changes
    - Tooltip appears above the attribute value
  - **Training Changes View:** Shows net changes from training
  - **Attribute Order:** Same exact order as Attributes view (SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT, NG, EM, RT)
  - **Note:** MO (Momentum) is excluded from Training Report display
  - Only displays attributes that have changes (maintains order)
  - Positive changes: Green text with `+` prefix
  - Negative changes: Red text with `-` prefix
  - Zero changes: Black text
  - **RT Column:** Static highest position-rating value; does not toggle to a delta/change view
  - **Aggregated Total Row:** Bottom row displays "Total" in the first column and sums all attribute changes across all players
    - Styled with gold background highlight and bold text
    - Provides quick overview of total training impact
- Displays all players on the team with their attribute values or changes

**Team Report Section:**
- Header: "Team Report"
- Displays all team attributes with visualizations:
  - **Red/Green Pills:** Most attributes (Shooting, Rebounding, Offense, Defense, Fast Breaks, Press/Trap, Fight, Discipline, Momentum)
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
  - **Note:** Pre-training depreciation is skipped for training camp in franchise mode - determined by `week == 1 and not results.get("1")`, so no skill degradation occurs before first games

**Training Notes Section:**
- Header: "Training Notes"
- Displays structured sections generated by `BackEnd/models/training_notes.py`
- Current structured sections include:
  - Training camp or in-season MVP / biggest regression style sections
  - Most Positive Locker Room Influence
  - Strong Cumulative Increase / Concerning Progression or Regression
  - Strongest Offensive Plays
  - Strongest Defensive Set
  - Fast Break Readiness
  - Press/Trap Readiness
  - Player Energy Levels
- Legacy flat NG-reduction notes are still generated inside training execution, then folded into the structured **Player Energy Levels** section
- **Placeholder:** If no notes are generated, displays "No training notes for this session." in italic gray text
- Same horizontal width as Player Report and Team Report sections
- Dynamic height: Expands automatically with content
- No internal scrolling: All text is always visible

#### Training Focus Display Format

The training focus is formatted as "Focus (Archetype)" with the focus outside parentheses and archetype inside:
- **Authoritarian** archetype options:
  - "Discipline (Authoritarian)"
  - "Rebounding (Authoritarian)"
  - "Teamwork (Authoritarian)"
  - "Execution (Authoritarian)"
- **Systems Coach** archetype options:
  - "Offense (Systems Coach)"
  - "Defense (Systems Coach)"
  - "Fast Breaks (Systems Coach)"
  - "Press / Trap (Systems Coach)"
- **Player Maximizer** archetype options:
  - "Top 3 Attributes (Player Maximizer)"
  - "Attributes 4-6 (Player Maximizer)"
  - "Positional Focus (Player Maximizer)"
  - "Custom (Player Maximizer)"
- **Culture Builder** archetype options:
  - "Inspire (Culture Builder)"
  - "Community Engagement (Culture Builder)"
  - "Team Building (Culture Builder)"
  - "Build Confidence (Culture Builder)"

**Note:** Archetype names inside parentheses must be exactly: "Authoritarian", "Systems Coach", "Player Maximizer", or "Culture Builder"

#### Schedule Integration

Training report links appear next to scheduled games on the Franchise Command Center schedule:
- Link appears only for user's team's games
- Link appears only if training has been completed for that week
- Link styled in blue (#4a90e2) with reduced font size
- Link text: "[Training Report]"
- Navigates to training report page with correct parameters (mode, franchise_id, team_id, week)

### Data Flow

1. **Training Submission:**
   - User allocates 24 training points (or 30 for first training) and selects coaching focus on `training.html`
   - **Player Maximizer:** `GET /franchise/training-points` includes `custom_focus_roster` (attrs + `position_ratings`) and `player_maximizer_ranking_attrs` for the modal. Submit sends a **resolved** leaf (never bare `player-maximizer-choose-attributes`). Payload includes `coaching_focus_custom_by_player` when `coaching_focus` is `player-maximizer-custom`.
   - Frontend sends POST request to `/franchise/run-training` with training data
   - **Data Initialization (Auto-Population):**
     - If `plays_data` is empty or missing, backend automatically populates it from the universal `plays` collection using `populate_team_plays()`
     - If `scouting_data` is empty or missing the `defense` structure, backend automatically initializes it using `TeamManager._init_scouting_data()`
     - Initialized data is saved to the database before training execution
     - This ensures training works even if game plan or playbooks haven't been submitted yet
   - Backend executes training for user's team (pre-conditions, point allocation, clamping)
   - Backend stores training report in `franchise_teams.{team_id}.training_reports.{week}`
   - Backend updates player attributes and team attributes in franchise document for user's team
   - **Computer Team Training (Franchise Mode Only):**
     - Backend iterates through all computer teams in the franchise
     - For each computer team:
       - Generates random training allocations (same total points as user's team)
       - Generates random coaching focus (archetype and sub-option)
       - Executes training with separate randomizations (pre-training decay, training)
       - Recalculates position ratings for all players
       - Updates player attributes and team attributes in franchise document
     - All updates (user team + computer teams) consolidated into single database update
   - Backend returns redirect URL to training report page (user's team only)

2. **Training Report Display:**
   - Frontend loads training report data from `/franchise/training-report` endpoint
   - Backend resolves team_id (handles both name and ID formats)
   - Backend retrieves players from franchise-instance `FPD`
   - Franchise player membership comes from `FTD.players` (not universal `teams.player_ids`)
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

### Computer Team Training (Franchise Mode Only)

In Franchise mode, when the user submits training for their team, all non-user teams are updated in the same overall training step, but they do **not** run the full `execute_training()` path. They use the separate **Distant Team Training System**.

**Current Behavior:**
- **Automatic Execution**: Distant training runs immediately after the user's team training completes
- **Template-Based**: CPU teams pull a random template from the `distant_training` collection for `tc` or `regular` training type
- **No Full User-Team Logic**: CPU teams do not run the same pre-training decay, drill-allocation, playbook-training, or report-generation flow as the user team
- **What Updates**:
  - team attributes on FTD
  - player attributes on FPD
  - player position ratings after attribute changes
  - optional `pending_community_engagement`
- **What Does Not Update**:
  - offensive play effectiveness
  - defensive set effectiveness
  - team `plays` data
  - team `scouting_data`
  - training reports for CPU teams
- **EOS Tournament Behavior**: eliminated teams are skipped during EOS tournament weeks
- **Post-Training Camp Cuts**: after first-training camp, CPU teams still cut down to 12 players if needed

**Franchise Roster Source Of Truth:**
- User-team training execution and the training report page both use `FTD.players` as the franchise roster membership list
- CPU distant training also uses `FTD.players` order when available; if absent, it falls back to the core team roster order

**Note:** Player attributes saved by training are automatically loaded during game initialization. See `Franchise_Mode_Systems.md` section "3.5. Player Attribute Loading During Game Initialization" for complete details on how trained attributes are loaded into gameplay.

### Data Storage

**FTD / Franchise Team Data:**
- `training_reports.{week}` - User-team training report for a specific week
- `team_attributes.*` - Updated user-team and CPU-team team attributes
- `plays` - User-team plays data after training
- `scouting_data` - User-team scouting data after training
- `pending_community_engagement` - Optional flag for next-game crowd impact

**FPD / Franchise Player Data:**
- `attributes.anchor_{attr}` and `attributes.{attr}` - Updated player attribute values
- `position_ratings` - Recalculated position ratings after training
- `attributes.NG` - Updated NG value when conditioning or scrimmages apply energy reduction

**Franchise Document:**
- `latest_training` - Most recent training report (backward-compatible quick access)
- `training_status.training_completed` - Boolean flag
- `training_status.week` - Week number for last training

**FCC API (`GET /franchise/command-center/data`):**
- `last_training_report_week` - Integer week for the current **latest** user training report (`latest_training.week`), used to render the Inbox message and link; omitted or null when no report exists yet

**Computer Team Updates (Franchise Mode Only):**
- CPU distant training updates FTD team attributes and FPD player attributes / position ratings
- CPU distant training does **not** store training reports and does **not** update team `plays` or `scouting_data`

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
- `BackEnd/models/training_notes.py` - Structured training-notes generation for report sections
- `BackEnd/api/franchise_routes.py` - Training API endpoints
  - `POST /franchise/run-training` - Submit training
  - `GET /franchise/training-report` - Get training report data
  - `GET /franchise/schedule` - Get schedule with training report flags

### Current Play / Report Identity Notes

- Training report play deltas use `play_id` as the canonical key when available
- `training_report["plays_effectiveness_changes"]` is keyed by `play_id` for offense and by defense name for defensive sets
- The Training Report frontend resolves offensive deltas by `play_id` first, while still displaying the play `name`
- Offensive `playbook_settings` are now expected to be `play_id`-keyed, though runtime compatibility still tolerates older name-keyed maps
