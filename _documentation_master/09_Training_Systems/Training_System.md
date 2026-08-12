## Training System (**verified 2026-08-11**)

> CPU template training is retired. User and CPU teams now share `execute_training`; CPU teams receive generated allocations/focus and use `cpu_autotrain_week` for per-team idempotency. The split endpoints are `/franchise/run-training/user` and `/franchise/run-training/cpu-train`.

This document should reflect the current franchise training implementation in code. If behavior here conflicts with `BackEnd/models/training_execution_v2.py`, `BackEnd/models/training_notes.py`, `BackEnd/api/franchise_routes.py`, or `BackEnd/constants/training_shape.py`, update this doc to match the live implementation.

**Base Constants**

1. **Flat integer budget** (`CAMP_POINT_BUDGET` / `IN_SEASON_POINT_BUDGET` in `training_shape.py`):
   - **Training camp** (`is_camp_week`: franchise week **1**; `CAMP_WEEKS = 1`): **30** points
   - **In-season** (weeks **2–26**): **24** points
   - **After week 26:** training is unavailable; budget and submit endpoints reject the request
   - Every slider notch costs exactly **1 point**, for every drill, player position, and class. Spend is the raw integer slider sum via `training_points_spent`; there is no weighted-price or roster-maximum pricing path.
2. **Slider Range**: 0-5 points per slider (discrete integer steps)
3. **Training Page Files**: `FrontEnd/static/training.html`, `FrontEnd/static/training.js`, `FrontEnd/static/training.css`
4. **Training Report Page**: `FrontEnd/static/training-report.html`
5. **Backend Execution**: `BackEnd/models/training_execution_v2.py`; shape/gain-fit dials in `BackEnd/constants/training_shape.py`
6. **API Endpoints (franchise training)**:
   - `GET /franchise/training-points` - Budget (30 camp / 24 in-season), `is_camp_week`, `camp_weeks`, and `gain_percentage_matrix` for the client
   - `POST /franchise/run-training/user` - **User phase only**: runs `execute_training` for the user team, persists FPD/FTD + `latest_training`, sets `training_status.user_training_applied_week` and leaves `training_completed` **false** until CPU training completes. Requires auth + franchise ownership.
   - `POST /franchise/run-training/cpu-train` - **CPU phase**: runs real auto-training for eligible CPU teams, **last-camp-week** cuts (`week == CAMP_WEEKS`), and bounded Practice Squad work. During PS weeks it may return `status: "processing"` plus progress and `retry_after_ms`; the client polls until success.
   - `POST /franchise/run-training` - **Legacy/full path**: reaches the same user + CPU end state in one request and resumes the CPU phase when user training is already applied.
   - `GET /franchise/training-report` - Get training report data
   - `GET /franchise/league-news` - Authenticated, read-only national Top 10, key-games, and league-leader payload for the training load screen
7. **Coaching Focus Archetypes**: Authoritarian, Systems Coach, Player Maximizer, Culture Builder — per-leaf code behavior: `Coaching_Focus_Implementation_Map.md` in this folder
8. **Rebound Modifier Range**: 0.0-1.0 (clamped)
9. **Pre-Training defense CMD decay**: Scouting defense rows with effectiveness > 0 reduced by `random.randint(5, 15)` before install training. **Offensive** play effectiveness is **not** decayed here; it is reduced at **EOG** from playcall share (see `End_Of_Game_System.md`).

### Canonical training position

Every training surface uses `resolve_training_position()` from `training_shape.py`:

```text
training_position → position_intent → highest current position rating → SF
```

The backend training-player producer carries `training_position`, `position_intent`, and
`resolved_training_position`. Browser pricing consumes the server-resolved field; user budget
validation, execution floors, CPU grouping/reference focus, Team Builder floor validation, and
offseason development call the same canonical resolver. There is currently no product/UI write
path that lets a user change `training_position`; generation supplies `position_intent`, and
rollover defaults a missing `training_position` to that intent and then carries it forward.

Player Maximizer **Positional Focus is intentionally separate**: it selects its fixed attribute
triple from the player's highest current RT, not from `training_position`.

**Training System Flow (15 Steps)**

1. **Page Load**: Frontend fetches the flat budget + gain-divisor matrix from `/franchise/training-points` (30 in week 1 / 24 in weeks 2–26; rejected after week 26)
2. **User Allocates Points**: User distributes units across 20 sliders; Points Remaining tracks **cost spend** against the week budget
3. **User Selects Focus**: User selects one coaching focus archetype and sub-option
4. **Recruiting Invites Access (Weeks 20-26 only)**: Training page shows a green `Recruiting Invites` button below `Submit Training` that routes to the phase-aware Recruiting Hub at `recruiting.html`
5. **Submit Training (Franchise)**: Frontend sends `POST /franchise/run-training/user` then `POST /franchise/run-training/cpu-train` while the independent **League News Wire** load screen rotates.
6. **Backend Validation**: `training_points_spent(allocations)` must equal the expected flat budget exactly (30 camp / 24 in-season)
   - week 20 special case: if no recruiting orders have ever been saved, training is blocked until the user saves recruiting orders
7. **Data Auto-Population**: Backend initializes `plays_data` and `scouting_data` if missing; `execute_training` merges any legacy `scouting_data.defense` row keys onto canonical `defense_id` keys before baselines (same remap as gameplay). **Defense and offensive play CMD effectiveness decay from game usage share runs at franchise EOG only** (`End_Of_Game_System.md`); not during training.
8. **Pre-Training Conditions**: Random decreases applied to player attributes (excluding EM, MO, NG); team attributes are no longer decayed here (**skipped on camp weeks**: `is_camp_week(week)` → `skip_pre_training_depreciation=True`)
9. **Training Point Application**: Drill allocations mapped to attributes, random increases applied based on points (camp uses `CAMP_GAIN_SCALE=1.4`; in-season uses `IN_SEASON_GAIN_SCALE=0.18`)
10. **Coaching Focus Amplifiers**: Selected focus amplifies specific attribute gains
11. **Attribute Clamping**: All values clamped to valid ranges (see **Attribute_Clamp_System.md** for player and team clamp ranges); decay/gains also respect weight-scaled position floors
12. **Weeks 20-26 Recruiting Invite Processing**: During recruiting invite season, `Submit Training` also runs that week's recruiting invite processing using the user's saved recruiting orders plus CPU weekly recruiting logic
13. **User team persisted (phase 1)**: User-team training report stored on FTD and in `latest_training`; franchise doc records `user_training_applied_week`. **`training_completed` stays false** until step 14.
14. **Computer team training (phase 2)**: Eligible non-user teams run real auto-training through `execute_training`. FTDs record `cpu_autotrain_week` for idempotent retries. The franchise then records `training_completed` and `cpu_training_complete_week`.
15. **Post-Training Camp Cuts**: After the **last** camp week (`week == CAMP_WEEKS`), applied during the CPU phase; user cut flow from FCC when roster > 12.

### Training load League News Wire (franchise, between user and CPU phases)

While training runs, `PageLoadOverlay` uses its separate `newswire` variant to rotate neutral national league graphics. The retired archetype loading-feed generator is no longer produced or returned by training APIs.

- `GET /franchise/league-news` consolidates the national Top 10, current-week key games, and eight qualified leaderboards into pre-ranked lists of exactly ten. In Week 4, standings and leaders are through Week 3 while Key Games are Week 4.
- Week 1 uses the preseason deck: program-rank Top 10 and season marquee matchups. Preseason Top 10 rows intentionally have no trailing record.
- `training.js` prefetches and session-caches the payload by franchise, season, and week. At submit, the news request and training request proceed independently.
- A pending news request shows only the header and green “Training in progress” pulse. A rejected request falls back to the existing team-banner pulse variant.
- Available graphics rotate in a fixed order every 6000ms. Missing or short lists are omitted. Rotation stops immediately when the overlay hides.
- During weeks 2–19, phase 2 remains a durable polling workflow. Refreshing or revisiting detects an applied user phase with incomplete CPU training and resumes automatically under the same newswire.

**Franchise training state helpers**

- `BackEnd/utils/franchise_training_state.py` — `franchise_training_fully_complete_for_week`, `franchise_user_training_applied_for_week`. FCC `training_completed` reflects user + CPU completion.
- If user training is applied but CPU/PS work is unfinished, APIs expose `cpu_training_resume`; completion sets `training_completed` + `cpu_training_complete_week`.

### Post-Training Camp Cut Flow

- **Trigger:** After week **1** training completes (`week == CAMP_WEEKS`, currently **1**), during the CPU training phase (`cpu_training_camp_cuts_applied`).
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
  - After the last camp week, any CPU team above 12 players automatically cuts down to 12
  - Cut rule:
    - lowest RT first
    - RT tie -> older year first (`Senior`, `Junior`, `Sophomore`, `Freshman`)
    - remaining tie -> random

**Long Form Documentation**

**Table of contents** (Markdown anchor targets; slug style matches common renderers such as GitHub.)

- [Training load League News Wire (franchise, between user and CPU phases)](#training-load-league-news-wire-franchise-between-user-and-cpu-phases)
- [Post-Training Camp Cut Flow](#post-training-camp-cut-flow)
- [Training Page Layout](#training-page-layout)
- [Slider Behavior](#slider-behavior)
- [Coaching Focus Selection](#coaching-focus-selection)
- [Submit Button Behavior](#submit-button-behavior)
- [Auto-Train Button](#auto-train-button)
- [Backend Training Execution System](#backend-training-execution-system)
  - [Coaching focus string (API ↔ amplifiers)](#coaching-focus-string-api-amplifiers)
  - [Community Engagement](#community-engagement-culture-builder-community)
  - [Training Execution Flow](#training-execution-flow) — play/defense CMD decay at **EOG** only (`End_Of_Game_System.md`); install training, clamps, report deltas
  - [Drill-to-Attribute Mapping](#drill-to-attribute-mapping)
  - [Training Point Ranges](#training-point-ranges)
  - [Coaching Focus Amplifiers](#coaching-focus-amplifiers)
  - [Breaks Effect](#breaks-effect)
  - [NG Reduction from Scrimmages and Conditioning](#ng-reduction-from-scrimmages-and-conditioning)
- [Training Report Page](#training-report-page)
  - [FCC Inbox](#fcc-inbox-training-report-shortcut), [Page Layout](#page-layout), [Recruiting summary](#recruiting-summary-franchise-only), [Training Focus Display Format](#training-focus-display-format), [Schedule Integration](#schedule-integration)
- [Data Flow](#data-flow)
- [Team ID Resolution](#team-id-resolution)
- [Computer Team Training (Franchise Mode Only)](#computer-team-training-franchise-mode-only)
- [Player Development & Coaching Quality](#player-development--coaching-quality)
- [Data Storage](#data-storage)
- [Key Files](#key-files)
- [Current Play / Report Identity Notes](#current-play--report-identity-notes)

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
  - Playbook training mode (**franchise**): toggle between **Current Playbooks** (default) and **Custom Playbook** (opens `training-playbooks.html` to choose plays/defenses for install CMD only). Tournament/single-game pages that still expose playbook mode may use the historical `playbook_training_mode` values from the API.

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

- Each slider has discrete integer steps from 0 to 5; every notch spends one point
- Default value for all sliders on page load: 0
- Flat point budget from `/franchise/training-points`:
  - **Camp week** (`is_camp_week`, week 1): **30**
  - **In-season weeks 2–26**: **24**
  - **Weeks 27+**: unavailable
- Franchise client also loads `gain_percentage_matrix` + roster years/positions to display each player drill's effective-value range across the roster
- Moving any slider by +1 subtracts exactly **1** from Points Remaining
- Prevents allocating past the budget (clamps or reverts last interaction)
- Submit requires `Points Remaining == 0`; decimal and unspendable remainders are impossible
- Player-drill labels show `Effective value: 25%–100%` across the roster, or collapse to a single Full/Half/Quarter/percentage label. The tooltip identifies position fit and class as the causes.

### Position fit and class taper

Position fit and class affect **gain, never price**. They are stored directly as percentages in `TRAINING_GAIN_PERCENTAGES` and `CLASS_GAIN_PERCENTAGES`; there is no cost matrix or reciprocal derivation. Class rates are FR 100%, SO ~91%, JR 80%, SR ~71%. The execution path applies `session_gain_scale × position_fit × class_gain` to the raw positive roll **before** splitting whole gain from `training_gain_remainders`.

This moved the fractional component off the budget so the user always sees and spends whole points while retaining the original cross-position granularity. Shape floors and `resolve_training_position()` are unchanged.

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
  1. Budget exhausted exactly: remaining `== 0` — 30 camp / 24 in-season
  2. A coaching focus is selected
  3. **Player Maximizer / Choose Attributes:** user has tapped **Assign Focus Attributes** in the modal (or Auto-Train selected a hidden leaf). For **Custom**, every player needs three distinct picks.
- Becomes active only when all conditions are met

### Auto-Train Button

- **Button:** "Auto-Train" (header, right side)
- **Behavior when clicked:**
  - Assigns whole points under the flat budget, then randomly bumps sliders until all points are spent
  - Randomly selects a Coaching Focus (one of the existing focus options, not archetype headers; Custom excluded)
  - Shows confirmation popup with the chosen focus (e.g. `Assigned Attributes 4–6 (Player Maximizer) Focus` for hidden PM leaves)
    - Popup has a "Close" button; closing keeps the user on the Training page
  - After auto-assign, Submit becomes eligible (provided focus set by auto-train)

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
- **Computer:** CPU auto-training can select Community Engagement inside the shared engine, but its persistence path does not currently set `pending_community_engagement`; this next-game effect is therefore user-team-only today.
- **Both teams pending CE** in the same matchup: shifts **cancel** (normal roll from actual home `team_chemistry`).
- **Bye week:** if no game is played after training, the pending flag stays until the **next** game in that season.

#### Training Execution Flow

**Postseason training freeze (franchise weeks 27-34):** Training is disabled during the EOS tournament window. This blocks user training, full training, and distant CPU-only training, so player anchor attributes, play effectiveness, and defense effectiveness do not change from training in weeks 27-34. Week 35 already stays outside the training loop because it is the postseason recruiting week. This freeze is implemented as a centralized postseason policy so it can be relaxed later for a smaller postseason training variant.

**Defense scouting keys (before baselines):** At the start of `execute_training`, `scouting_data["defense"]` is passed through `_remap_defense_scouting_keys_for_merge` (`BackEnd/models/team_manager.py`) so legacy row keys (display names such as `Man`, `2-3 Zone`, etc.) fold onto canonical half-court keys (`man`, `2-3-zone`, …), matching gameplay normalization. Defense install training only writes effectiveness to those canonical rows; baselines for `defenses_effectiveness_changes` use this normalized map. **Franchise defense row effectiveness** is reduced at **EOG** from each row’s share of defensive `used` counts (same percentage rule as offensive CMD); see `End_Of_Game_System.md`.

1. **Pre-Training Conditions** (`apply_pre_training_conditions`)
   - Applies random decreases to player attributes (excluding EM, MO, NG)
   - Player attributes: see pre-training decay section below
   - Team attributes are no longer decayed in training. They are updated at the end of each game based on performance (see End_Of_Game_System.md). For a side-by-side of how each team attribute is changed in EOG vs Training, see `docs/To Do/team_attributes_eog_vs_training_comparison.md`.
   - **Skipped during camp** — `is_camp_week(week)` sets `skip_pre_training_depreciation=True` for week 1

2. **Training Point Application** (`apply_training_points`)
   - Maps drill allocations to player/team attributes
   - Applies random increases based on points allocated
   - Scales positive gains by `CAMP_GAIN_SCALE` (1.4) on camp weeks or `IN_SEASON_GAIN_SCALE` (0.18) in-season; the per-attribute fractional remainder is loaded from and persisted back to FPD after both user and CPU training
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
- Scrimmages → Team Chemistry: 0.25 points, Shot Threshold: 1 point, Rebound Modifier: 0.5 points, NG Reduction (if 3-5 points)

#### Training Point Ranges

**Player Attributes (Base Ranges)** (`PLAYER_ATTR_GAIN_RANGE_BY_POINTS` in `training_execution_v2.py`; year-max adjustments still apply on the high end only):
- 0 points: `+= random.randint(-2, -1)`
- 1 point: `+= random.randint(1, 3)`
- 2 points: `+= random.randint(2, 3)`
- 3 points: `+= random.randint(2, 4)`
- 4 points: `+= random.randint(3, 5)`
- 5 points: `+= random.randint(3, 6)`

Positive gains are then scaled by `IN_SEASON_GAIN_SCALE` (0.18) or `CAMP_GAIN_SCALE` (camp), with a per-attribute fractional remainder (`training_gain_remainders`) so sub-integer signal accumulates across weeks instead of rounding away. The sidecar is read from and written to each franchise player document, never the core player, and is carried through season rollover. Attribute and anchor values remain integers.

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

**Year-Based Pre-Training Decay** (code: `PRE_TRAINING_DECAY_BY_YEAR` in `training_execution_v2.py`; applied only when `skip_pre_training_depreciation` is false — i.e. skipped for training camp):
- **Freshman / Sophomore**: -2 min, 0 max
- **Junior / Senior**: -1 min, 0 max

**Training Camp (what it actually is today)**

Training camp is **not** a separate growth event. It is the same `execute_training` → `apply_training_points` path as in-season weeks, for franchise week **1** (`CAMP_WEEKS = 1`). Differences vs in-season:

1. **Pre-training decay is skipped** (`skip_pre_training_depreciation=True` via `is_camp_week`).
2. **Flat point budget is 30** (`CAMP_POINT_BUDGET`) instead of 24.
3. **Gain scale is `CAMP_GAIN_SCALE` (1.4)** instead of `IN_SEASON_GAIN_SCALE` (0.18).
4. **Camp cuts** run once after week 1 (`week == CAMP_WEEKS`).

There is **no** camp-only CH/core-attribute bonus, **no** year-based camp bonus roll, and **no** camp HT/WT growth. Those used to exist; they were removed when the offseason development event took ownership of career physical/level growth (see comment in `apply_training_points` — `training_camp_physique_notes` is always empty). Height and weight growth live in `develop_one_offseason` at season rollover, not at camp.

*(Older docs described a full Training Camp Bonus System, week-1-only camp, and FR/SO HT/WT camp rolls. That behaviour is gone; do not re-implement from this paragraph's absence — HT/WT/level live in the offseason; shape lives in camp + in-season training.)*

**Team Attributes (training ranges by group):**
- Standard install attrs (`offensive_efficiency`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`):
  `0 -> -2 to -1`, `1 -> 0 to +1`, `2 -> +1 to +3`, `3 -> +2 to +3`, `4 -> +2 to +4`, `5 -> +2 to +5`
- `fight` and `discipline` (same bucket table after their respective 0.5× / 0.25× accruals round to 0–5):
  `0 -> -4 to -3`, `1 -> -1 to +1`, `2 -> 0 to +2`, `3 -> +1 to +3`, `4 -> +2 to +4`, `5+ -> +3 to +5`
  - **Fight:** Strength + Conditioning → sum × **0.5**, half-up → `_apply_team_training_points(..., "fight", ...)`.
  - **Discipline:** Inside/Outside defense + Passing + Ball Handling → sum × **0.25**, half-up → `_apply_team_training_points(..., "discipline", ...)`.
- `team_chemistry`:
  `0 -> -3 to -1`, `1 -> 0 to +1`, `2 -> +1 to +2`, `3 -> +2 to +3`, `4 -> +2 to +4`, `5 -> +2 to +5`
  - Free Throws × **0.25** + Film Study × **0.25** + Scrimmages × **0.25**, half-up → `_apply_team_training_points(..., "team_chemistry", ...)`.

**Rebound Modifier (Technical Drills - in 0.01 increments):**
- `<1 effective point -> -0.05 to -0.03`
- `1-2 effective points -> +0.03 to +0.05`
- `3-4 effective points -> +0.03 to +0.07`
- `5+ effective points -> +0.03 to +0.10`

**Rebound Modifier (Scrimmages - in 0.01 increments):**
- `<1 effective point -> -0.05 to -0.03`
- `1-2 effective points -> +0.03 to +0.05`
- `3-4 effective points -> +0.03 to +0.07`
- `5+ effective points -> +0.03 to +0.10`

**Shot Threshold:**
- 0 points: `+= random.randint(5, 15)`
- 1 point: `+= random.randint(0, 5)`
- 2 points: `-= random.randint(3, 8)`
- 3 points: `-= random.randint(5, 11)`
- 4 points: `-= random.randint(5, 15)`
- 5+ points: `-= random.randint(5, 20)`

#### Coaching Focus Amplifiers

> For a per-leaf **implementation-status matrix** (which of the 16 focus leaves are fully Implemented / Partial), see `Coaching_Focus_Implementation_Map.md` — the code-truth companion to this design prose.

**Two multiplier mechanisms in code** (`training_execution_v2.py`):

1. **Drill / team-attribute training:** When `_should_amplify_player_attr` / `_should_amplify_team_attr` (or special cases) apply, qualifying gains use `focus_multiplier = random.choice([1.5, 1.6, 1.7, 1.8])` in `_apply_player_training_points`, `_apply_team_training_points`, and rebound-modifier training. *(Older docs listed 1.3–1.6 for some focuses; implementation uses this single band.)*
2. **Install training (play/defense effectiveness only):** Authoritarian **Execution** and **Teamwork** use one session roll of the same `[1.5, 1.6, 1.7, 1.8]` values on integer **effectiveness** (Command) increments only, via `_scale_install_training_effectiveness_points`—not on momentum/cloaking (install does not allocate to those).

**Authoritarian (all four sub-options implemented):**
- **Discipline:** Amplifies BH, `fight`, `discipline` (drill / team-attribute mechanism *#1*). Also adds flat `discipline += random.randint(1, 2)` once per training session (shared with Rebounding and Execution only — not Teamwork).
- **Rebounding:** Amplifies RB, `rebound_modifier` (mechanism *#1*). Receives the shared flat `discipline += random.randint(1, 2)` once per session.
- **Teamwork:** Amplifies PS, IQ (mechanism *#1*). Also amplifies install **effectiveness** gains on **motion** plays and **zone** defenses only (mechanism *#2*). Man and set plays receive base install gains only under this focus. Adds flat **`team_chemistry += random.randint(0, 1)`** once per session (clamped). Does **not** add the shared Authoritarian **discipline** flat.
- **Execution:** Amplifies install **effectiveness** gains on **set plays** and **Man** only (mechanism *#2*). Motion and zone defenses receive base install gains only under this focus. Receives the shared flat `discipline += random.randint(1, 2)` once per session.

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
- **Team Building** (`culture-builder-teamwork`): **Team chemistry** `+random.randint(1, 3)` once per session (clamped like other team attrs). UI label only; API `value` unchanged. Does **not** add the shared Culture Builder **`fight`** flat (that applies only to Inspire, Confidence, and Community Engagement).
- **Build Confidence:** **CH** (conditioning, film study) and **FT** (free throws) drill gains use the standard focus multiplier `random.choice([1.5, 1.6, 1.7, 1.8])` (after CH’s 0.5 drill coefficient). No flat EM/MO block; no Inspire-style team chemistry mult.
- **Inspire**, **Confidence**, and **Community Engagement** also add flat **`fight += random.randint(1, 2)`** once per training session (Culture Builder shared block; Team Building excluded).
- **Culture Builder**, except **Confidence**, also adds flat **`discipline += random.randint(-2, -1)`** once per training session.
- **Authoritarian**, except **Rebounding**, also adds flat **`fight += random.randint(-2, -1)`** once per training session.

#### Breaks Effect

The "Breaks" slider applies a multiplier to all positive gains (not losses), except **`rebound_modifier`** (float 0.01-step attribute; breaks does not scale or reset it):
- 0 points: `random.choice([0.85, 0.9, 0.95])`
- 1 point: `random.choice([0.9, 0.95, 1, 1, 1])`
- 2 points: `random.choice([1, 1, 1.05, 1.1])`
- 3 points: `random.choice([1, 1.05, 1.1])` + Team Chemistry `+= random.randint(-1, 1)` + Discipline/Fight `+= random.randint(-1, 0)`
- 4 points: `random.choice([1, 1.05, 1.1, 1.1])` + Team Chemistry `+= random.randint(-2, 1)` + Discipline/Fight `+= random.randint(-2, -1)`
- 5+ points: `random.choice([1, 1.05, 1.1, 1.15])` + Team Chemistry `+= random.randint(-3, 1)` + Discipline/Fight `+= random.randint(-3, -1)`

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
- **Row 1 (meta):** Week number, Upcoming Opponent (from schedule), Training Focus (formatted as "Focus (Archetype)", e.g., "Inspire (Culture Builder)"). Franchise-only recruit **detail** (name / RT line) is **not** in this row; it sits under the recruit strip title in the Notes header (see below).
- **Top-right header control** (behavior depends on `from` query parameter):
  - **`from=inbox` (franchise):** **Back** → Franchise Command Center, Inbox tab
  - **Otherwise (e.g. `from=training` or absent):** Orange **Go To Locker Room** → Franchise or Tournament Command Center (existing behavior)

#### Recruiting summary (Franchise only)

The Notes block no longer shows a static **Internal** label. Instead, **franchise** training reports show week-specific recruiting copy (right-aligned), driven by the API and persisted on the user-team FTD snapshot for that week.

**Placement (UI):**
- **Same row as the Notes `h2` (right column):** **Title** (`#training-report-recruit-header`), e.g. `Recruiting Visit` or `Recruits Leaning Your Way`, with **detail line directly beneath** (`#training-report-recruit-meta-line`): e.g. `{Recruit Name} - RT: {n}` or a comma-separated list (see week rules). Tournament mode hides both slots.

**Week rules:**
- **Weeks 20–26 (official visit window):** Title **`Recruiting Visit`**. Detail line is the **single recruit assigned to visit the user’s team that week** — `{Name} - RT: {RT}` — resolved from franchise `recruiting_results.{week}[user_team_object_id]` → recruit row in **FRD** (`franchise_recruits_data`). **Do not** show the “recruits leaning” list in these weeks. Weekly visit assignment still runs from training when results for that week are not yet present (see recruiting flow in `franchise_routes`).
- **Weeks 1–19 and 27–34:** Title **`Recruits Leaning Your Way`**. Detail line lists recruits whose **`Lean.1` / `Lean.2` / `Lean.3`** equals the user’s team (same lean semantics as FCC). Sorted by **RT** (max `position_ratings` value) descending. **At most three** recruits are listed, formatted `Name - RT: n`, comma-separated; if **more than three** lean toward the team, append **` ...`** after the third entry.
- **Other weeks (e.g. 35+):** No recruiting title or meta line (elements stay hidden).

**API (`GET /franchise/training-report`, franchise):**
- Response includes optional string fields **`recruiting_header`** and **`recruiting_meta_line`** (may be `null` when out of scope or empty).

**Persistence:**
- On each successful **user** training run, the snapshot written to **FTD** `training_reports.{week}` includes `recruiting_header` and `recruiting_meta_line` when applicable, so reopening a **past** week’s report shows the lean/visit copy from **that** run. Older snapshots without these keys are **recomputed** on read from current franchise + FRD state (visit weeks can still resolve from `recruiting_results`; lean lines may differ from history if leans changed later).

**Implementation:**
- Backend: `_training_report_recruiting_display` (and helpers) in `BackEnd/api/franchise_routes.py`; wired into `GET /franchise/training-report` and user training report persistence.
- Frontend: `FrontEnd/static/training-report.html` / `training-report.css` / `training-report.js` (`renderTrainingReportRecruitingBanner`, called from `renderHeader`).

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
    - **Shooting (`shot_threshold`):** Golf-score attribute (lower raw value is better). Pill centers at **70** with span **−30–170** (better toward the right). See [Shot_Threshold_Scale_Tuning.md](../00_Operations/Shot_Threshold_Scale_Tuning.md). The **numeric change** next to the label uses **inverted sign** versus the raw delta: raw **−10** displays as **+10** (green); raw **+5** displays as **−5** in red.
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
- **Effectiveness change indicator (Playbook Summary):**
  - **Defense:** Original baseline is post-remap effectiveness at session start (no random pre-training decay). Delta reflects **install training** for that session; usage-share decay is applied at **EOG** (franchise).
  - **Offense (motion/set):** Original baseline is **unchanged** at session start (no random play decay in training). Delta reflects **install training only** for that session. Longer-term CMD drift from game usage is applied at **EOG** (franchise), not on the training report.
  - Minimum displayed effectiveness logic still clamps at 0 in the engine where applicable.
  - **Training camp:** Pre-training **player** conditions are skipped on `is_camp_week` (week 1); play/defense CMD is unchanged during training regardless.

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
- **Play identity in notes:** notes that reference offensive plays display the play **`name`** (user-facing string); any underlying matching/ranking may use `play_id`, but note text stays display-name based. Notes are a reporting/output layer, not a persistence-identity layer. (`training_notes.py` keys `plays_data` by name.)
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
   - User spends the flat integer budget (24 in-season / 30 camp) across sliders and selects coaching focus on `training.html`
   - **Player Maximizer:** `GET /franchise/training-points` includes `custom_focus_roster` (attrs, `position_ratings`, both position identity fields, and `resolved_training_position`) and `player_maximizer_ranking_attrs` for the modal. Submit sends a **resolved** leaf (never bare `player-maximizer-choose-attributes`). Payload includes `coaching_focus_custom_by_player` when `coaching_focus` is `player-maximizer-custom`.
   - **Franchise:** Frontend sends `POST /franchise/run-training/user` with training data, then `POST /franchise/run-training/cpu-train` with `{ franchise_id }`, with the independent League News Wire overlay covering both phases. The legacy combined endpoint still reaches the same final state.
   - **Data Initialization (Auto-Population):**
     - If `plays_data` is empty or missing, backend automatically populates it from the universal `plays` collection using `populate_team_plays()`
     - If `scouting_data` is empty or missing the `defense` structure, backend automatically initializes it using `TeamManager._init_scouting_data()`
     - Initialized data is saved to the database before training execution
     - This ensures training works even if game plan or playbooks haven't been submitted yet
   - Backend executes training for user's team (pre-conditions, point allocation, clamping)
   - Backend stores the user report in FTD `training_reports.{week}` and franchise `latest_training`; CPU auto-training stores per-team reports on CPU FTDs.
   - **Computer Team Training:** Triggered by `POST /franchise/run-training/cpu-train` or the second half of the combined endpoint.
   - The CPU phase returns the redirect URL to the user's training report.

2. **Training Report Display:**
   - Frontend loads training report data from `/franchise/training-report` endpoint
   - Backend resolves team_id (handles both name and ID formats)
   - Backend retrieves players from franchise-instance `FPD`
   - Franchise player membership comes from `FTD.players` (not universal `teams.player_ids`)
   - Backend retrieves training report from `franchise_teams.{team_id}.training_reports.{week}`
   - **Franchise:** Response may include **`recruiting_header`** and **`recruiting_meta_line`** for the week-gated recruiting strip (see **Recruiting summary (Franchise only)** under **Training Report Page**).
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

Eligible non-user teams run the same `execute_training()` engine. CPU allocation is **not random**: `auto_train_one_cpu_team` applies a fixed team-wide **base allocation** plus per-player `player-maximizer-custom` focus steering each player toward his own position's reference top-3, tuned so the team scores ≈1.0 against the frozen coaching reference (see **Player Development & Coaching Quality**).

**Current behavior:**
- The CPU phase starts after the user phase.
- `cpu_autotrain_week` claims each FTD before delta writes so retries cannot double-train a team.
- Player attributes, position ratings, and `training_gain_remainders`; team attributes, plays, scouting data, coaching-focus counters, and `training_reports.{week}` are persisted.
- EOS-eliminated teams are skipped.
- After camp (`week == CAMP_WEEKS`, currently week 1), CPU teams are cut to 12 players.
- CPU auto-training does not currently persist the user-path `pending_community_engagement` next-game flag.

**Franchise Roster Source Of Truth:**
- User-team training execution and the training report page both use `FTD.players` as the franchise roster membership list
- CPU auto-training uses `FTD.players` as its roster source.

**Note:** Player attributes saved by training are automatically loaded during game initialization — `load_roster(team_name, franchise_id=...)` (`BackEnd/utils/roster_loader.py`) reads FPD and merges trained attributes over the universal player base. See `../01_Game_Mode_Systems/Franchise_Mode_Overview.md` ("How a game consumes franchise state").

### Player Development & Coaching Quality

> **Shape** (relative attribute mix) is owned by **camp + in-season training**. **Level** (ladder RT) and HT/WT are owned by the **offseason** level-only rescale (`BackEnd/utils/player_development.py`). Full derivation archived at `../projects/Z-Completed/Player_Attribute_Recalibration_Design.md` and `../10_Players_Systems/Player_Development_System.md`.

**Division of labor.** Offseason rollover (before Training Camp) rescales current attributes onto an absolute RT target: `jh_anchor × ladder_value × f(coaching_quality)`, plus HT/WT. It does **not** redistribute shape. Camp and weekly training apply the gain bands below; camp uses `CAMP_GAIN_SCALE`, in-season uses `IN_SEASON_GAIN_SCALE`.

**Camp / in-season model.** Gains stay report-visible but scaled. Invariant: **reference allocation holds flat; neglect costs; focus gains.**

| Weekly allocation (per attribute) | Net over a season |
|---|---|
| 0 points (neglect) | declines — **but the penalty is PROBABILITY-GATED as of the leveling pass**, see below |
| reference primaries (pts=3) | ≈ flat |
| reference baseline (pts=1) | mild drag (bands are distinct; see Player Development § gain bands) |
| focused (pts=4/5) | gains |

> **⚠️ TEAM-attribute neglect decay is gated (August 2026).** Point-bucket 0 used to charge
> `−4…−3` (fight/discipline) or `−3…−1` (chemistry) **every week**. Because the CPU reference
> plan allocates nothing to the chemistry and discipline categories, those attributes decayed
> **~−3.5/week indefinitely** — measured **team_chemistry −93.6/season** on an 18-point range
> and **discipline −91.6** on a 40-point range, flooring every team. The bucket-0 range is now
> `(−1, 0)` and fires on a fraction of weeks: `NEGLECT_DECAY_CHANCE_CHEMISTRY = 0.10`,
> `NEGLECT_DECAY_CHANCE_DEFAULT = 0.25`. `FIGHT_GAIN_CHANCE = 0.45` gates positive fight deltas
> for the mirror-image reason. Measured after gating: chemistry **−5.3**, discipline **−6.0**,
> fight **+3.3**. These attributes are rolled **~4.7x per week** across their source categories,
> so per-roll intuition is misleading. See
> [Team_Attribute_System.md](../04_Franchise_Mode_Systems/Team_Attribute_System.md) § Neglect decay.

Position floors (`SHAPE_P6_FLOOR_BASE` × weight scale) replace the retired shape attractor (`OFFSEASON_ATTRACTOR_ALPHA=0`). Pre-training decay by year is unchanged (see **Year-Based Pre-Training Decay** above) and never subtracts below the weight-scaled position floor.

**Coaching-quality metric.** A season's allocation is scored in **points per attribute per week, not shares**:

```
contribution_a = weight_a × min(points_a / COACHING_SATURATION_CAP, 1)
quality        = Σ contribution / Σ contribution(reference)
```

- Points (not shares): a smaller budget saturates fewer attributes and scores lower automatically — spreading thin saturates nothing; concentrating saturates what matters.
- Normalized **affinely per position** so the frozen reference scores exactly **1.0** and a budget optimum scores **1.0 + COACHING_HEADROOM**; headroom is comparable across all five positions.

**The frozen reference.** The allocation that scores 1.0 is a **frozen, named constant**: a deliberately-mediocre, top-3-weighted baseline per position (primary attrs at a higher points value, other on-position attrs at a baseline points value; the tail neglected). It is the calibration anchor — reference-coached development lands exactly on the validated ladder (`f = 1.0`). Test-asserted at all five positions.

**Coaching factor `f`.** Quality maps to a bounded multiplier `f ∈ [COACHING_F_MIN, COACHING_F_MAX]` (≈ 0.85–1.20) on the offseason RT target. Reference → `f = 1.0`; neglect / off-position floors at ~0.85; broad or multi-attribute focus tops out near 1.20. Worth roughly **±1 tier step**; recruiting stays ~2× the lever.

**CPU trains the reference.** `auto_train_one_cpu_team` uses a fixed team-wide base allocation plus per-player `player-maximizer-custom` focus toward each player's position reference top-3, tuned so CPU scores ≈1.0 (measured 0.98–1.01). This holds the CPU league exactly on the ladder. The base allocation and the frozen reference are **coupled** — neither can change alone; `tests/test_cpu_reference_training.py` asserts the relationship.

**STATUS — dormant until pillar 3.** The per-player coaching-quality **capture is not wired up**. `_coaching_accumulator_for_player` returns `None`, so `f = 1.0` for **every** player and the coaching-quality multiplier currently does nothing in gameplay — the league holds exactly at the recalibration pass-1 ladder. Activation requires per-player allocation capture (gated at the calling endpoint, since user and CPU share `execute_training`) and ships with **pillar 3**, alongside the training-position UI and CPU season-start assignment.

**Constants** (values in `../11_Design_Systems/Tunable_Constants.md`):

| Constant | Role |
|---|---|
| `COACHING_SATURATION_CAP` | points/attr/week at which a contribution saturates (4) |
| `COACHING_STANDARD_BUDGET` | reference weekly budget the affine per-position normalization anchors to |
| `COACHING_HEADROOM` | how far a budget optimum scores above 1.0 |
| `COACHING_F_MIN` / `COACHING_F_MAX` | offseason multiplier bounds (0.85 / 1.20) |
| `IN_SEASON_GAIN_SCALE` | in-season gain scale (0.18) |
| `CAMP_WEEKS` / `CAMP_GAIN_SCALE` / `CAMP_POINT_BUDGET` | camp length (1 week), camp gain scale (1.4), flat camp budget (30) |
| `IN_SEASON_POINT_BUDGET` | flat in-season budget (24) |
| `TRAINING_GAIN_PERCENTAGES` / `CLASS_GAIN_PERCENTAGES` | direct position-fit and class-year gain percentages; neither changes budget spend |
| `OFFSEASON_ATTRACTOR_ALPHA` | **retired (0.0)** — shape attractor removed; offseason is level-only |

### Data Storage

**FTD / Franchise Team Data:**
- `training_reports.{week}` - User-team training report for a specific week (includes standard report fields; **franchise** snapshots also store **`recruiting_header`** and **`recruiting_meta_line`** when the recruiting strip applies so historical weeks match the run that produced them)
- `team_attributes.*` - Updated user-team and CPU-team team attributes
- `plays` - User-team plays data after training
- `scouting_data` - User-team scouting data after training
- `pending_community_engagement` - Optional flag for next-game crowd impact
- **`coaching_focus` (user team only, lazy from deploy forward):** object with integer counters for how many times the coach submitted training with each **archetype** in the current franchise season: `authoritarian`, `systems_coach`, `player_maximizer`, `culture_builder`. Incremented on each successful **user** training execution (same moment as FTD `training_reports` / report persistence), normally by **+1** per archetype chosen. **Camp weeks** (`is_camp_week` / `training_camp_first_week`): that increment is **`random.randint(2, 4)`** instead of 1 (one roll per submit). **New season** (`POST /franchise/finish-season`): each of the four counters is replaced with **`int(round(prior * 0.25))`** — i.e. a **75% reduction**, carrying over 25% as the starting totals for the new season. Not backfilled for past weeks. CPU FTDs do not use this field. Implementation: `BackEnd/utils/franchise_coaching_focus_counts.py`; rollover applied in `finish_season` when FTDs are rewritten for the new year.

**FPD / Franchise Player Data:**
- `attributes.anchor_{attr}` and `attributes.{attr}` - Updated player attribute values
- `position_ratings` - Recalculated position ratings after training
- `training_position`, `position_intent` - Persisted position identity used by the canonical resolver
- `training_gain_remainders.{attr}` - Fractional positive-gain carry stored beside, never inside, `attributes`; read and written only by franchise training and carried across season rollover through `PLAYER_DEV_CARRY_FIELDS`. It is never stored on universal/core `players`.
- `attributes.NG` - Updated NG value when conditioning or scrimmages apply energy reduction
- `meta.height` and `meta.weight` (integer inches / pounds) — carried on the FPD; **career HT/WT growth is applied at offseason rollover** (`develop_one_offseason`), not at training camp. If `meta` omitted height/weight (legacy or lazy FPD row), `run_franchise_training` backfills missing values from the universal `players` document before training runs; `finalize_game` lazy FPD inserts also copy height/weight/year/jersey from `players` into `meta`.

**Franchise Document:**
- `latest_training` - Most recent training report (backward-compatible quick access)
- `training_status.training_completed` - Boolean; true only after user + CPU phases complete
- `training_status.week` - Week number aligned with last training
- `training_status.user_training_applied_week` - User phase done for that week (split flow)
- `training_status.cpu_training_complete_week` - CPU phase done for that week
- `training_status.cpu_training_camp_cuts_applied` - Final-camp-week CPU cuts have run (when applicable)

**FCC API (`GET /franchise/command-center/data`):**
- `last_training_report_week` - Integer week for the current **latest** user training report (`latest_training.week`), used to render the Inbox message and link; omitted or null when no report exists yet

**Computer Team Updates (Franchise Mode Only):**
- CPU auto-training updates FPD player attributes, position ratings, and gain remainders plus FTD team attributes, plays, scouting data, coaching-focus counters, and training reports.

### Key Files

**Frontend:**
- `FrontEnd/static/training.html` - Training allocation page
- `FrontEnd/static/training.css` - Training page styling
- `FrontEnd/static/training.js` - Training logic; franchise submit uses user + CPU endpoints and prefetches the newswire
- `FrontEnd/static/js/shared/pageLoadOverlay.js` - Shared loader and `newswire` variant host
- `FrontEnd/static/js/shared/trainingNewswire.js` / `FrontEnd/static/css/training-newswire.css` - League-news rendering, motion, asset fallback, and rotation
- `FrontEnd/static/training-report.html` - Training report display page
- `FrontEnd/static/training-report.css` - Report page styling
- `FrontEnd/static/training-report.js` - Report data loading and rendering
- `FrontEnd/static/franchise-command-center.js` - Schedule rendering with training report links

**Backend:**
- `BackEnd/models/training_execution_v2.py` - Core training execution logic (gains, remainder, floor clamp)
- `BackEnd/constants/training_shape.py` - Camp weeks/flat budgets/gain scale, position-fit divisors, class gain taper, P6 floors, `training_points_spent`
- `BackEnd/models/training_notes.py` - Structured training-notes generation for report sections
- `BackEnd/api/franchise_routes.py` - Training API endpoints (`run-training`, `run-training/user`, `run-training/cpu-train`) and CPU auto-training/idempotency; also `GET /franchise/training-report`, `GET /franchise/schedule`, and `GET /franchise/league-news`.
- `BackEnd/utils/franchise_league_news.py` - Consolidated, pre-ranked training newswire payload
- `BackEnd/utils/franchise_training_state.py` - Split-phase completion helpers for FCC and cuts
- `BackEnd/utils/franchise_coaching_focus_counts.py` - FTD `coaching_focus` archetype counters (user team)
- `BackEnd/utils/player_development.py` - Offseason level-only RT rescale + HT/WT (not weekly training)

### Current Play / Report Identity Notes

- Training report play deltas use `play_id` as the canonical key when available
- `training_report["plays_effectiveness_changes"]` is keyed by `play_id` for offense and by **canonical defense row keys** (`man`, `2-3-zone`, … — same as `scouting_data["defense"]` after `execute_training`) for defensive sets; the report UI may still show human-readable names via defense display helpers
- The Training Report frontend resolves offensive deltas by `play_id` first, while still displaying the play `name`
- The training load newswire is league context only; play/defense effectiveness deltas remain in the Training Report.
- Offensive `playbook_settings` are now expected to be `play_id`-keyed, though runtime compatibility still tolerates older name-keyed maps

---

## Randomness: training draws from its OWN stream (August 2026)

Training draws from **`training_rng`** (`BackEnd/utils/training_random.py`), not the global
`random` module and **not** `sim_rng`.

**Why it was changed.** Training shared the global stream with `pymongo`, and `bulk_write`
consumes that stream even when it matches zero documents. So unrelated database activity
shifted training results. Measured on a 12-man roster over 4 weeks under an identical seed:
adding a **single no-op `bulk_write`** before training changed the attributes of **all 12
players** (RB 17→14, SH 69→71, and so on). Training is deterministic in isolation but the
franchise path does a variable amount of DB work, so **a seeded training run could not be
replayed.**

**Why a separate stream and not `sim_rng`.** Training runs concurrently with simulation — a
franchise week sims games and trains teams. Sharing `sim_rng` would reintroduce exactly the
cross-subsystem coupling both modules exist to remove: the number of games simmed would shift
training outcomes.

| module | binding |
|---|---|
| `models/training_execution_v2.py` | `from BackEnd.utils.training_random import training_rng as random` |
| `models/training_notes.py` | same |
| `models/training_manager.py` | same |

**Deliberately NOT converted:** `populate_team_plays` / `populate_scouting_data` in
`api/gameplan_routes.py` (function-local `import random`, lines 572 and 879). They seed play
effectiveness/momentum/cloaking at franchise and game **creation**; `run_franchise_training`
contains no call to either. They belong to whatever stream game setup eventually owns.

**Verification (the check that matters).** Two runs, identical seed, the only difference being
one no-op `pymongo` write:

| | before | after |
|---|---|---|
| BackEnd draws on the GLOBAL stream | 640 | **0** |
| draws on `training_rng` | 0 | **640** |
| identical player attributes | **False** (12 of 12 differed) | **True** |
| identical team attributes | True | True |

**Draw count is unchanged — 640 → 640, site for site**, which is the point: the conversion is a
pure rebinding, not a behaviour change.

| draws | site |
|---|---|
| 624 | `training_execution_v2:apply_pre_training_conditions` |
| 12 | `training_execution_v2:_apply_team_training_points` |
| 4 | `training_notes:_locker_room_note` |

Re-check with `BackEnd.utils.sim_random.install_global_draw_guard()` +
`global_draw_report()`; the tally must stay empty on the training path.
