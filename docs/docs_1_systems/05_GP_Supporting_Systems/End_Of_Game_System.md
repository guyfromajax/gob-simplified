## End of Game System ✅ **COMPLETE** (January 2025)

**Base Constants**

1. **Game Completion Trigger**: Q4 ends (or overtime if applicable)
2. **Completion Detection**: `quarter === 4` and game is finalized
3. **Navigation Parameters**:
   - `gameId` - Game document ID
   - `mode` - Game mode: 'single', 'tournament', or 'franchise'
   - `tournamentId` - Tournament ID (for tournament mode only)
   - `franchiseId` - Franchise ID (for franchise mode only)
   - `teamId` - Team ID (ObjectId) for navigation anchor
   - `finalScore` - Final score object with homeTeam, awayTeam, homeScore, awayScore
4. **Command Center URLs**:
   - Tournament Mode: `/static/tournament.html?tournament_id={id}&team_id={id}`
   - Franchise Mode: `/static/franchise-command-center.html?franchise_id={id}&team_id={id}`
   - Single Game Mode: `/static/mode-select.html`
5. **Key Files**:
   - `FrontEnd/static/js/phaser/gameScene.js` - Detects game completion, calls completion popup
   - `FrontEnd/static/js/phaser/utils/gameCompletionPopup.js` - Creates completion popup, constructs navigation URLs
   - `FrontEnd/static/box-score.js` - Handles "Go To Locker Room" button navigation
   - `BackEnd/api/api.py` - ObjectId serialization for tournament/franchise endpoints

**End of Game System Flow (6 Steps)**

1. **Game Completion Detection**: Game completes when Q4 ends (or overtime), detected in `gameScene.js` when `quarter === 4` and game is finalized
2. **Backend Game Finalization** (Franchise Mode Only): 
   - Frontend calls `/franchise/complete-week` with `result: { team1_id, team2_id, team1_score, team2_score }` (and optional `game_document`)
   - Backend resolves team ids via `_normalize_team_id()` (ObjectId, or universal `teams` by _id/name/code, or canonical → name; see below)
   - Player stats are finalized via `stat_updater.finalize_game()`
   - **Team attributes are updated** based on game performance (win/loss, score differential, etc.)
   - Updated team attributes are saved via the franchise team data persistence path (FTD) and reflected in the game's box score
3. **Completion Popup Display**: Shows final score, "Box Score" button, and "Go To Locker Room" button with all navigation parameters
4. **Navigation Anchor Preservation**: Preserves complete navigation anchor set (mode, doc_id, team_id) for seamless return to command center
5. **Box Score Navigation**: User can navigate to Box Score page with all context parameters preserved (box score reflects updated team attributes)
6. **Command Center Navigation**: User can navigate to appropriate Command Center (Tournament, Franchise, or Mode Select) with complete navigation context

### Player Of The Game (POTG) (March 2026)

- POTG is selected deterministically per game (seeded by `game_id`) so popup and box score remain stable across refreshes.
- Candidate pool: players on both teams from game data (`players` + `box_score` merge).
- POTG points:
  - `+2` for each `PTS`, `AST`, `REB` (TREB), `STL`, `BLK`
  - Defensive bonus only if `DEFA (DEF_A) > 10`:
    - `+15` if `DEF% > 80`
    - `+10` if `DEF% > 60`
    - `+5` if `DEF% > 40`
- Selection:
  - If top player leads second by `>= 10` POTG points, top player wins.
  - Otherwise, random draw from all players tied at/above second-place score.
  - If contenders include both teams: winning-team contenders get total weight `67%`, losing-team contenders `33%` (split evenly within each side).
  - If all contenders are on one side, draw evenly across contenders.
- `DEF%` display is rounded to nearest whole number.

### End-Game Popup POTG Content

- Existing popup design remains unchanged; POTG rows are inserted between final score and CTA buttons:
  1. Header: `Game Complete!`
  2. Final score row
  3. POTG image (centered)
  4. POTG stats row: `XX PTS  XX REB  XX AST`
  5. POTG stats row: `XX STL  XX BLK  XX DEF%`
  6. CTA row: `Box Score` and `Go To Locker Room`

### Box Score POTG Section

- Added below **Quarter Scoring** and above team tabs:
  - Header (centered): `Player Of The Game`
  - Row 1 (centered): `{Player Name} - {Player Team}`
  - Row 2 (centered): `XX PTS  XX REB  XX AST  XX STL  XX BLK  XX DEF%`

### Final-Turn Resolution Guardrail (February 2026)

- At `0:00`, EOG resolution now follows one consistent rule:
  - If free throws are pending, run the free throws first, then resolve to End of Game or Overtime based on the post-FT score.
  - If free throws are not pending, resolve directly to End of Game or Overtime (skip other in-turn interruption flows).
- This prevents final-turn edge cases from skipping score-impacting free throws and keeps quarter/final scoring consistent.

**Team Attributes Update System**
Team attributes will adjust at the end of game based on the notes below. Note this will replace the team attribute decay we had coded into the Training System. For a side-by-side comparison with Training, see `docs/To Do/team_attributes_eog_vs_training_comparison.md`.
- Values will be capped to normal ranges:
  - `shot_threshold`: 0 to 200
  - `rebound_modifier`: 0 to 0.4
  - `team_chemistry`: 7 to 25
  - all others: -10 to 10
- End of game attribute adjustments (applies to each team, all stat conditions for the game just run):
  - `shot_threshold`
    - **Winning team:** If game FG% > 50%: −(10 to 20); if FG% > 45%: −(0 to 10); else +(0 to 10).
    - **Losing team:** If game FG% > 50%: −(5 to 15); if FG% > 45%: −(0 to 5); else +(0 to 15).
  - `discipline` (both teams, same criteria)
    - If team (F + TO) < opponent's (F + TO): += random.randint(0, 1). Otherwise: += random.randint(-3, -1).
    - F = team fouls for the game (from box score / team totals).
  - `fight`
    - **Winning team:** += random.randint(0, 1).
    - **Losing team:** += random.randint(-3, -1).
  - `rebound_modifier` (winning and losing team have same criteria)
    - if team TREB for the game > opponents TREB for the game + 5: += random.uniform(0, 0.1)
    - elif TREB for the game < opponents TREB for the game - 5: += random.uniform(-0.1, 0)
    - else: += random.uniform(-0.05, 0.05)
  - `offensive_efficiency` (winning and losing team have same criteria)
    - += random.randint(-2, -1)
  - `defensive_efficiency` (winning and losing team have same criteria)
    - += random.randint(-2, -1)
  - `fb_efficiency`
    - if fast break success rate > 60%: += random.randint(0,1)
    - else: += random.randint(-2,-1)
  - `fb_opp_modifier` - Fast break opponent modifier
    - if opponents fast break success rate < 20%: += random.randint(0,2)
    - elif oppoent's fast break success rate > 55% OR total fast breaks run by opponent in the game > 12: += random.randint(-3,-2)
    - else: += random.randint(-1,0)
  - `pt_efficiency` - Press/Trap efficiency rating
    - if (fc press success rate + hc trap success rate) combined > 60%: += random.randint(1,2)
    - elif (fc press success rate + hc trap success rate) combined < 30%: += random.randint(-3,-1)
    - else: += random.randint(-1,0)
    - Note: Combined rate = (FC Press successes + HC Trap successes) / (FC Press attempts + HC Trap attempts)
  - `pt_opp_modifier` - Press/Trap opponent modifier
    - if opponents (press success rate + trap success rate) combined < 20%: += random.randint(1,2)
    - elif opponents (press success rate + trap success rate) combined > 50% OR total FCP and HCT run by opponent in the game > 12: += random.randint(-3,-2)
    - else: += (-2,-1)
    - Note: Combined rate = (FC Press successes + HC Trap successes) / (FC Press attempts + HC Trap attempts)
  - `team_chemistry` - Team chemistry rating
    - score delta = winning team final score - losing team final score
    - if score_delta < 4:
      - winning team += random.randint(1,2)
      - losing team += random.randint(-2,-1)
    - elif score_delta < 10:
      - winning team += random.randint(1,3)
      - losing team += random.randint(-3,-1)
    - else:
      - winning team += random.randint(1,4)
      - losing team += random.randint(-6,-2)
- **Data Sources:**
  - Team statistics (F, TO, STL, TREB, FG%) come from the current game's box score / team totals (F = team fouls; used with TO for discipline rule)
  - Fast Break, HC Trap, and FC Press success rates come from the box score's "Special Situations" section
  - Success rates are calculated as: (successes / attempts) * 100%
  - [FOR REFERENCE ONLY]: Previous deprecation rates when run in training:
    - Rebound modifier: `+= random.uniform(-0.1, 0)` (pre-training, range from -0.1 to 0)
    - Shot threshold: `+= random.randint(5, 20)`
    - Other team attributes: `+= random.choice([-2, -1, 0])`


**Long Form Documentation**

### Overview

The End of Game System handles game completion, displays final scores, and provides navigation to the Box Score page and appropriate Command Center (Tournament, Franchise, or Mode Select for Single Game).

### Game Completion Flow

**Trigger:**
- Game completes when Q4 ends (or overtime if applicable)
- Detected in `gameScene.js` when `quarter === 4` and game is finalized

**Completion Popup:**
- **Location:** `FrontEnd/static/js/phaser/utils/gameCompletionPopup.js`
- **Display:** Shows final score, "Box Score" button, and "Go To Locker Room" button
- **Parameters Passed:**
  - `gameId` - Game document ID
  - `mode` - Game mode: 'single', 'tournament', or 'franchise'
  - `tournamentId` - Tournament ID (for tournament mode only)
  - `franchiseId` - Franchise ID (for franchise mode only)
  - `teamId` - Team ID (ObjectId) for navigation anchor
  - `finalScore` - Final score object with homeTeam, awayTeam, homeScore, awayScore

### Navigation Anchor Preservation (SS&S - January 2025)

**✅ Complete Navigation Anchor Set:** When a game completes, the completion popup preserves all three navigation parameters:
1. **`mode`** (franchise/tournament/single) - Which collection/endpoints to use
2. **`doc_id`** (franchise_id/tournament_id) - Which document within that collection
3. **`team_id`** (ObjectId string) - Which team within that document (user's team)

**Implementation Flow:**
- **`bootGame.js`:** Reads `team_id` from URL params (or `home_id`/`away_id` fallback), passes to game scene via `sceneData`
- **`gameScene.js`:** Stores `teamId` from scene data, passes it to completion popup when game ends
- **`gameCompletionPopup.js`:** Constructs command center URLs with complete navigation anchor set:
  ```javascript
  // Tournament mode example
  const params = new URLSearchParams();
  if (tournamentId) params.set('tournament_id', tournamentId);
  if (teamId) params.set('team_id', teamId);  // ✅ Preserve navigation anchor
  lockerRoomUrl = `/static/tournament.html?${params.toString()}`;
  ```

**Benefits:**
- **No Fallback Needed:** Prevents fallback to `/tournament/active?user_team_id=...` which requires ObjectId serialization
- **Complete Context:** All three navigation parameters preserved for seamless return to command center
- **Consistent Pattern:** Matches navigation anchor preservation pattern used throughout the application

### Box Score Navigation

**Box Score URL Construction:**
- **Location:** `gameCompletionPopup.js` (lines 59-64)
- **Parameters Included:**
  - `game_id` - Game document ID
  - `home` - Home team name
  - `away` - Away team name
  - **✅ SS&S (January 2025):** Also includes `mode`, `tournament_id`, `franchise_id`, and `team_id` for proper navigation from Box Score page

**Box Score "Go To Locker Room" Button:**
- **Location:** `FrontEnd/static/box-score.js` - `setupLockerRoomButton()` function
- **Navigation Logic (Priority Order):**
  1. **Mode Parameter (Highest Priority):** If `mode` is set in URL params, use it directly
  2. **ID Parameters:** Check for `tournament_id` or `franchise_id` in URL params
  3. **LocalStorage (Last Resort):** Only check localStorage if URL params are not available (for backward compatibility)
- **Command Center URLs:**
  - **Tournament Mode:** `/static/tournament.html?tournament_id={id}&team_id={id}`
  - **Franchise Mode:** `/static/franchise-command-center.html?franchise_id={id}&team_id={id}`
  - **Single Game Mode:** `/static/mode-select.html`

**Key Fix (January 2025):**
- Box Score page now receives `mode`, `tournament_id`, `franchise_id`, and `team_id` in URL params
- Navigation logic prioritizes URL parameters over localStorage to prevent stale data issues
- Franchise mode uses correct path: `/static/franchise-command-center.html` (not `/franchise/command-center`)

### Franchise complete-week team id resolution (February 2026)

- **Endpoint:** `POST /franchise/complete-week` (request body: `franchise_id`, `week`, `result: { team1_id, team2_id, team1_score, team2_score }`, optional `game_id`, optional `game_document`).
- **Team ids:** Backend normalizes `result.team1_id` and `result.team2_id` via `_normalize_team_id()` in `BackEnd/api/franchise_routes.py`:
  1. If the value is a valid ObjectId string, it is returned.
  2. Else lookup in universal `teams` by `_id`, `name`, or `code`; if found, return that document’s `_id`.
  3. **Canonical fallback:** If still not found and the value contains an underscore (e.g. `FOUR_CORNERS`), convert to a name by replacing `_` with space and title-casing (e.g. `"Four Corners"`), then lookup by `name`; if found, return that document’s `_id`.
- This allows the frontend to send either ObjectIds (e.g. from URL params) or canonical keys from the game doc (e.g. when Play Quarter completes and URL params are missing). Sim Quarter, Sim Full Game, and Play Quarter all use the same flow; only the value sent for team ids can differ.

### Backend ObjectId Serialization

- **`/tournament/active` endpoint:** Now serializes all ObjectIds in nested structures using `jsonable_encoder(doc, custom_encoder={ObjectId: str})`
- **Consistent with `/tournament/state`:** Both endpoints use the same serialization pattern
- **Prevents 500 Errors:** Ensures nested ObjectIds (e.g., in `teams` collection) are properly serialized for JSON response

### Games Collection Structure

**Game Document Storage:**
- Game documents are stored in the `games` collection (standalone documents, not nested in franchise/tournament documents)
- **Team Identification Fields:** Game documents use `home_team_id` and `away_team_id` fields (team_id strings like "XAVIEN"), NOT `team1_id` / `team2_id`
- **Teams Object:** The `teams` object is keyed by `team_id` strings (e.g., `teams["XAVIEN"]`), matching the `home_team_id` / `away_team_id` values
- **Plays Data:** Plays data with `game_stats` (times_run, successes) is stored in `teams[team_id]["plays"]`

**Key Fix (January 2025):**
- Scouting report queries were updated to use `home_team_id` / `away_team_id` fields instead of non-existent `team1_id` / `team2_id` fields
- Queries now match against `team_id` strings (like "XAVIEN") instead of ObjectId strings

**Reference:** See `docs/docs_1_systems/00_Data_Systems/Games_Collection.md` for complete games collection documentation.

### Key Files

- **`FrontEnd/static/js/phaser/gameScene.js`** - Detects game completion, calls completion popup
- **`FrontEnd/static/js/phaser/utils/gameCompletionPopup.js`** - Creates completion popup, constructs navigation URLs
- **`FrontEnd/static/box-score.js`** - Handles "Go To Locker Room" button navigation
- **`BackEnd/api/api.py`** - ObjectId serialization for tournament/franchise endpoints

### EOG Data Source & Access Method

- **Design goal:** EOG team-attribute calculations must read from one frozen per-game snapshot.
- **Canonical snapshot field:** `games.eog_inputs`
- **Built from:**
  - `teams[team_id].scouting` for FB/HCT/FCP rates and attempts
  - `team_totals` for box-score totals (`FGM/FGA`, `TO/STL`, `DREB/OREB`)
  - fallback to aggregated `box_score` only if `team_totals` is missing
- **Backend access point:** `BackEnd/api/franchise_routes.py` → `update_team_attributes_after_game()`
- **Processing rule:** Build and persist `eog_inputs` once, then compute all EOG attribute changes from `eog_inputs` only.
- **Postgame display rule:** Box Score "Special Situations" (Fast Breaks, HC Traps, FC Presses) should read from `eog_inputs.*.scouting` so displayed rates match EOG calculations exactly.
- **Why this method:** Prevents source drift between `team_stats`, `teams.scouting`, and totals; keeps EOG deltas deterministic and aligned to final game state.

### EOG Persistence Guardrails (February 2026)

- **Issue observed:** EOG logs showed `totals_source=none` and zero team totals/scouting during `complete-week`, causing incorrect deltas (for example PT/FB opponent modifiers and discipline).
- **Root cause:** Mixed game `_id` handling in franchise flow could create/read two docs for the same game:
  - canonical gameplay doc with `_id` as **string** (full teams/totals/scouting),
  - partial metadata doc with `_id` as **ObjectId** (missing totals).
- **Fix implemented:**
  - `complete_week()` now persists the provided `game_document` snapshot before EOG runs.
  - `_save_game_result()` now prefers string `_id` to avoid creating new ObjectId clone docs.
  - `update_team_attributes_after_game()` now evaluates both `_id` variants and selects the richer doc for EOG (`[EOG-GAME-DOC-SELECT]` log).
- **Expected log health:**
  - `🧪 [EOG-SNAPSHOT-SOURCES]` should report `teams.totals` or `teams.box_score` (not `none`) for completed games.
  - `🧭 [EOG-GAME-DOC-SELECT]` should show which candidate doc was used and its richness score.
