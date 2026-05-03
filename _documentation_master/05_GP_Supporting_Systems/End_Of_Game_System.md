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
   - `FrontEnd/static/js/phaser/finalizeGame.js` - Tournament save-result; franchise **phase-a** at EOG (see split API below)
   - `FrontEnd/static/js/phaser/utils/gameCompletionPopup.js` - Creates completion popup; franchise phase B pending: starts **phase-b** in background when popup shows; PGPC vs locker CTA via **`FRANCHISE_PGPC_AT_EOG_ENABLED`** (`franchisePhaseBClient.js`); see `Press_Conference_System.md`
   - `FrontEnd/static/box-score.js` - Locker room navigation; franchise **phase-b** when week finish is pending
   - `FrontEnd/static/js/shared/pageLoadOverlay.js` - Full-page pulse overlay during **phase-b** (banner + copy + green bar)
   - `BackEnd/api/franchise_routes.py` - `complete_week_phase_a`, `complete_week_phase_b`, monolithic `complete_week`
   - `BackEnd/api/api.py` - ObjectId serialization for tournament/franchise endpoints

**End of Game System Flow (6 Steps)**

1. **Game Completion Detection**: Game completes when Q4 ends (or overtime), detected in `gameScene.js` when `quarter === 4` and game is finalized
2. **Backend Game Finalization** (Franchise Mode — **split API**, April 2026): 
   - **Phase A (automatic at EOG):** `POST /franchise/complete-week/phase-a` with the same body as the historical monolith (`franchise_id`, `week`, `game_id`, `result`, optional `game_document`). Persists the **user** game: `games` / EOG / inbox / `franchise.results[week]` user row, sets `post_game_status.phase_a_user_week`. Idempotent if phase A already completed for that week.
   - **Phase B (user-triggered):** `POST /franchise/complete-week/phase-b` with **`{ franchise_id, week }` only**. Runs CPU games for the rest of the week, recruiting / rank-prestige / EOS side effects, week advance, and clears `post_game_status.phase_a_user_week`. Requires phase A done and non-empty `results[week]`; idempotent if franchise `week` already advanced past the request.
   - **Monolith (fallback / legacy):** `POST /franchise/complete-week` still runs user block + CPU + advance in one call; if phase A already persisted the week row, the user block is skipped (see `franchise_routes.py`).
   - Team id normalization, `stat_updater.finalize_game()`, and **team attribute updates** follow the same rules as before; see **Franchise post-game split (phase A / phase B)** below.
3. **Completion Popup Display**: Shows final score, "Box Score" button, and "Go To Locker Room" button with all navigation parameters
4. **Navigation Anchor Preservation**: Preserves complete navigation anchor set (mode, doc_id, team_id) for seamless return to command center
5. **Box Score Navigation**: User can navigate to Box Score page with all context parameters preserved (box score reflects updated team attributes)
6. **Command Center Navigation**: User can navigate to appropriate Command Center (Tournament, Franchise, or Mode Select) with complete navigation context

### Final-Turn Resolution Guardrail (February 2026)

- At `0:00`, EOG resolution now follows one consistent rule:
  - If free throws are pending, run the free throws first, then resolve to End of Game or Overtime based on the post-FT score.
  - If free throws are not pending, resolve directly to End of Game or Overtime (skip other in-turn interruption flows).
- This prevents final-turn edge cases from skipping score-impacting free throws and keeps quarter/final scoring consistent.

**Team Attributes Update System**
Team attributes will adjust at the end of game based on the notes below. Note this will replace the team attribute decay we had coded into the Training System. For a side-by-side comparison with Training, see `docs/To Do/team_attributes_eog_vs_training_comparison.md`.
- Values will be capped to normal ranges:
  - `shot_threshold`: 10 to 210
  - `rebound_modifier`: 0 to 0.4
  - `team_chemistry`: 7 to 25
  - all others: -10 to 10
- End of game attribute adjustments (applies to each team, all stat conditions for the game just run):
  - `shot_threshold`
    - Golf-score style attr: lower is better, higher is worse.
    - **Winning team:** If game FG% > 50%: `+= random.randint(-10, -5)`; if FG% > 45%: `+= random.randint(-5, 5)`; else `+= random.randint(5, 15)`.
    - **Losing team:** If game FG% > 50%: `+= random.randint(0, 5)`; if FG% > 45%: `+= random.randint(5, 10)`; else `+= random.randint(10, 25)`.
  - `discipline` (both teams, same criteria)
    - Compare team `(F + TO)` to opponent `(F + TO) + 8`.
    - If lower: `+= random.randint(0, 1)`.
    - If higher: `+= random.randint(-3, -2)`.
    - If equal: `+= random.randint(-1, 0)`.
    - F = team fouls for the game (from box score / team totals).
  - `fight`
    - **Winning team:** += random.randint(0, 1).
    - **Losing team:** += random.randint(-3, -1).
  - `rebound_modifier` (winning and losing team have same criteria)
    - if team TREB for the game > opponents TREB for the game + 8: += `0.00 to 0.05`
    - elif TREB for the game < opponents TREB for the game - 8: += `-0.20 to -0.10`
    - else: += `-0.10 to -0.05`
  - `offensive_efficiency` (winning and losing team have same criteria)
    - Uses offensive play diversity from the completed game's play-usage snapshot.
    - If total offensive plays used > 12: `+= random.randint(-2, -1)`
    - elif total offensive plays used > 7: `+= random.randint(-3, -2)`
    - else: `+= random.randint(-4, -3)`
  - `defensive_efficiency` (winning and losing team have same criteria)
    - Uses defensive play distribution from the completed game's scouting snapshot.
    - If any one defensive play was > 49% of defensive calls: `+= random.randint(-4, -3)`
    - elif any one defensive play was > 39%: `+= random.randint(-3, -2)`
    - else: `+= random.randint(-2, -1)`
  - `fb_efficiency`
    - Uses per-play fast break usage from the completed game's scouting snapshot.
    - If any one fast break play was > 60% of fast break calls: `+= random.randint(-4, -3)`
    - elif any one fast break play was > 50%: `+= random.randint(-3, -2)`
    - else: `+= random.randint(-2, -1)`
  - `fb_opp_modifier` - Fast break opponent modifier
    - If opponent ran > 20 fast breaks: `+= random.randint(-4, -3)`
    - elif opponent ran > 10: `+= random.randint(-3, -2)`
    - else: `+= random.randint(-2, -1)`
  - `pt_efficiency` - Press/Trap efficiency rating
    - If total HCT + FCP uses > 20: `+= random.randint(-4, -3)`
    - elif total HCT + FCP uses > 15: `+= random.randint(-3, -2)`
    - else: `+= random.randint(-2, -1)`
  - `pt_opp_modifier` - Press/Trap opponent modifier
    - If opponent ran > 20 presses + traps: `+= random.randint(-4, -3)`
    - elif opponent ran > 10: `+= random.randint(-3, -2)`
    - else: `+= random.randint(-2, -1)`
  - **Distant-sim override (Franchise distant games only):**
    - For distant-simmed games only, bypass the normal usage-based logic for:
      - `fb_efficiency`
      - `fb_opp_modifier`
      - `pt_efficiency`
      - `pt_opp_modifier`
    - Instead apply: `random.randint(-2, 1)` to each of the four attrs.
    - All other EOG team-attribute logic continues to use the normal finished-game snapshot rules.
  - `team_chemistry` - Team chemistry rating
    - score delta = winning team final score - losing team final score
    - if score_delta < 4:
      - winning team += random.randint(1,2)
      - losing team += random.randint(-2,-1)
    - elif score_delta < 10:
      - winning team += random.randint(1,3)
      - losing team += random.randint(-4,-2)
    - else:
      - winning team += random.randint(2,4)
      - losing team += random.randint(-6,-4)
- **Data Sources:**
  - Team totals (F, TO, FG%, TREB) come from the canonical finished-game snapshot built for EOG and box score display.
  - Offensive play usage reads the completed game's `teams[team_id].plays[*].game_stats.times_run`.
  - Defensive play usage reads the completed game's `teams[team_id].scouting.defense` usage counts.
  - Fast break play usage reads the completed game's `teams[team_id].scouting.offense.fast_break_plays[*].A`.
  - Press/trap totals read the same HCT/FCP usage fields shown in the box score's Special Situations section.


**Long Form Documentation**

### Overview

The End of Game System handles game completion, displays final scores, and provides navigation to the Box Score page and appropriate Command Center (Tournament, Franchise, or Mode Select for Single Game).

### Game Completion Flow

**Trigger:**
- Game completes when Q4 ends (or overtime if applicable)
- Detected in `gameScene.js` when `quarter === 4` and game is finalized

**Completion Popup:**
- **Location:** `FrontEnd/static/js/phaser/utils/gameCompletionPopup.js`
- **Display:** Shows final score; franchise + phase B pending: **no Box Score on this popup**, CTA **Post-Game Press Conference** (opens PGPC modal; **phase-b** already started when this popup appeared, then FCC). Otherwise **Box Score** + **Go To Locker Room** (or tournament/single variants).
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

**Box Score primary action (Back to Locker Room / Go To Locker Room when phase B pending from EOG):**
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

### Franchise post-game split (phase A / phase B) — April 2026

Canonical franchise week completion is a **two-step HTTP flow** so the user’s game and box score are safe before CPU games run. Deeper design notes and inventory live in `docs/To Do/Post_Game_Split.md`.

**Phase A — `POST /franchise/complete-week/phase-a`**

- **Body:** Same as `CompleteWeekRequest`: `franchise_id`, `week`, `result` (`team1_id`, `team2_id`, `team1_score`, `team2_score`), optional `game_id`, optional `game_document`.
- **Behavior:** Runs the shared user-game pipeline (`_complete_week_process_user_game_block`), merges the user row into `franchise.results[str(week)]`, persists `season_inbox`, sets `post_game_status.phase_a_user_week` to `week`.
- **Response (success):** `{ status, phase: "a", idempotent, week, results_count }`. If phase A already completed for that week, returns **`idempotent: true`** without re-running side effects.
- **Frontend:** `finalizeGame.js` shows **“Saving game…”**, POSTs phase-a when `canCompleteWeek` (franchise, no tournament, valid `week`). On success, writes `localStorage.franchise_complete_week_pending` as `JSON.stringify({ franchise_id, week })` and passes `franchisePhaseBPending` / `franchisePhaseAOk` into `finalScore` for the EOG popup.

**Start CPU sims — `POST /franchise/complete-week/start-cpu-sims`** (May 2026)

- **Body:** `{ franchise_id, week }`.
- **Behavior:** Sims **non-user** week games only; persists **`results[week]`** (and EOS tournament blobs on EOS weeks). Does **not** advance franchise `week` or run week-closure aggregates. **409** if phase A already completed for that week (use phase B).
- **Frontend:** `bootGame.js` calls **`getOrStartFranchiseStartCpuSims`** (`franchiseStartCpuSimsClient.js`, single-flight, non-fatal errors) when franchise **pre-game (`quarter === 0`)** starts via **Play Quarter**, **Sim Quarter**, or **Sim Full Game**, so CPU games can run in parallel while the user plays.

**Phase B — `POST /franchise/complete-week/phase-b`**

- **Body:** `CompleteWeekPhaseBRequest`: **`franchise_id`**, **`week`** only.
- **Preconditions:** Let `current_week` be the franchise doc’s `week`. If **`current_week > req.week`**, the week already advanced — returns **200** with **`idempotent: true`** (no-op). If **`current_week < req.week`**, **400**. If **`current_week == req.week`**, phase A must be done and `results[week]` must be a non-empty list; otherwise **409** (run phase-a or use the monolith).
- **Behavior:** Loads saved week results from DB, runs `_complete_week_finish_cpu_and_persist` (CPU sims, recruiting, rank/prestige, EOS, week advance). Full turn-based CPU games (`run_simulation`) may run **in parallel** inside one phase-b request (`ThreadPoolExecutor`; optional env **`FRANCHISE_CPU_SIM_MAX_WORKERS`**, default **4**). Clears `post_game_status.phase_a_user_week` on successful persist.
- **Response:** Extends the usual complete-week payload with `status`, `phase: "b"`, `idempotent`.
- **Frontend triggers:**
  - EOG popup: **`getOrStartFranchisePhaseB`** runs when the franchise completion modal is shown (`gameCompletionPopup.js`). **Franchise EOG primary CTA:** controlled by **`FRANCHISE_PGPC_AT_EOG_ENABLED`** in `gameCompletionPopup.js`. When **`false`** (current default), the popup shows **Box Score** + **Go To Locker Room**; **Go To Locker Room** dismisses the modal, shows the same **`PageLoadOverlay`** pulse as box-score (“Simulating Computer Games”), **awaits** the same phase-b Promise, then clears pending `localStorage` and navigates to the FCC (no extra click). When **`true`**, the legacy **Post-Game Press Conference** button is shown and **`postGamePressConference.js`** attaches to the same phase-b Promise (PGPC code paths remain in the repo). Box-score entry with `post_game_phase_b=1` uses the **Go To Locker Room** label for the phase-b finish action (see below).
  - Box score: **Back to Locker Room** or **Go To Locker Room** (phase-b pending from EOG; see below) — same POST and overlay when pending matches URL `franchise_id`. Legacy pending shape `{ body: full CompleteWeekRequest }` still POSTs monolithic **`/franchise/complete-week`**.

**Monolith — `POST /franchise/complete-week`**

- **Body:** Same as phase A. Runs user block then `_complete_week_finish_cpu_and_persist` unless phase A already persisted `results[week]` (user block skipped to avoid double finalize / GP).
- **Use:** Escape hatch for old clients or the box-score legacy pending `{ body }` path.

**Box score URL flag (`post_game_phase_b=1`)**

- When the EOG popup builds the **Box Score** link and phase B is pending, it appends **`post_game_phase_b=1`**.
- `box-score.js` shows **Go To Locker Room** (same phase-b + overlay behavior as the historical “Sim Computer Games” control) only if that flag is present **and** `localStorage.franchise_complete_week_pending` exists **and** `franchise_id` matches the URL. All other entry paths keep **Back to Locker Room**; phase-b wiring when pending is unchanged.

### Franchise complete-week team id resolution (February 2026)

- **Endpoints:** Team ids in `result` apply to **phase-a** and the **monolith** the same way. **Phase-b** does not send `result`; the server uses the saved week row and schedule.
- **Frontend week resolution:** `finalizeGame()` resolves `week` in this order **before posting phase-a**:
  1. `window.location.search`
  2. `localStorage.franchise_week`
  3. `simData.week`
  4. `simData.final_game_document.week`
  5. backend franchise state fallback via `/franchise/command-center/data`, then `/franchise/state`
- **Reason for backend fallback:** Prevent intermittent franchise EOG failures where command-center navigation context is incomplete at game end; if local/frontend week sources are missing, the finalizer recovers the authoritative current franchise week instead of silently skipping franchise completion.
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
- **`FrontEnd/static/js/phaser/finalizeGame.js`** - Franchise EOG: **phase-a**; builds `finalScore` with phase B pending for popup
- **`FrontEnd/static/js/phaser/utils/gameCompletionPopup.js`** - Completion popup; kicks off **`getOrStartFranchisePhaseB`** when franchise + phase B pending; **`FRANCHISE_PGPC_AT_EOG_ENABLED`** toggles PGPC vs Box Score + locker on franchise EOG; `post_game_phase_b` on box-score link when pending
- **`FrontEnd/static/js/phaser/utils/franchisePhaseBClient.js`** - Single-flight `POST …/phase-b` Promise per franchise week (EOG + PGPC share)
- **`FrontEnd/static/js/phaser/utils/postGamePressConference.js`** - PGPC modal; attaches to shared phase-b Promise + `press_conference_sessions` API
- **`FrontEnd/static/box-score.js`** - **phase-b** when `franchise_complete_week_pending` matches; label branching per `post_game_phase_b`
- **`FrontEnd/static/js/shared/pageLoadOverlay.js`** - Pulse overlay during phase-b
- **`BackEnd/api/franchise_routes.py`** - `complete_week_phase_a`, `complete_week_phase_b`, `complete_week`, `_complete_week_finish_cpu_and_persist`
- **`BackEnd/api/api.py`** - ObjectId serialization for tournament/franchise endpoints

### EOG Data Source & Access Method

- **Design goal:** EOG team-attribute calculations must read from one frozen per-game snapshot.
- **Canonical snapshot field:** `games.eog_inputs`
- **Built from:**
  - `teams[team_id].scouting` for FB/HCT/FCP rates and attempts
  - `team_totals` for box-score totals (`FGM/FGA`, `TO/STL`, `DREB/OREB`)
  - fallback to aggregated `box_score` only if `team_totals` is missing
- **Distant-sim note:** Distant franchise games persist `simulation_engine="distant"` on the game doc. EOG uses this as an explicit branch signal so only the four FB/PT attrs switch to the simplified random rule; TBT games keep the normal scouting-based formulas.
- **Backend access point:** `BackEnd/api/franchise_routes.py` → `update_team_attributes_after_game()`
- **Processing rule:** Build and persist `eog_inputs` once, then compute all EOG attribute changes from `eog_inputs` only.
- **Postgame display rule:** Box Score "Special Situations" (Fast Breaks, HC Traps, FC Presses) should read from `eog_inputs.*.scouting` so displayed rates match EOG calculations exactly.
- **Why this method:** Prevents source drift between `team_stats`, `teams.scouting`, and totals; keeps EOG deltas deterministic and aligned to final game state.

### Postseason Team Attribute Freeze

- **Franchise weeks 27-34:** EOG team attribute changes are frozen for EOS tournament games.
- **Persistence rule:** The game doc still receives `team_attribute_changes: {}` for box score compatibility, but franchise team-data attributes are not mutated.
- **Scope:** Game results, stats, inbox entries, and tournament bracket advancement still persist normally. In-game NG effects may still change live game state during play; the frozen values are the postgame anchor team attributes.
- **Reversibility:** The freeze is controlled by a centralized postseason policy in `BackEnd/api/franchise_routes.py` so future postseason EOG team attribute changes can be re-enabled without rewriting the EOG formulas.

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

##Player Of The Game##
Calculate player of the game by assigning each player on boht teams wiht POTG Points with teh follwing scale:
1. 2 POTG Points for every point scored, assist, rebound, block, and steal
2. if DEFA > 10:
  - 15 POTG points if DEF % > 80%
  - or 10 POTG points if DEF% > 60%
  - or 5 POTG points if DEF% > 40%

If the top ranking player's POTG points is 16 or more points greater than the second ranking player, then he is the player of the game.

Else, ranomly choose from teh top 2. And if one player is on the winning team and another is on the losing team in teh top 2, the player on the winning team has a 67% chance of being randomly chosen. If the top to players are on teh same team, each player has a 50% chance of being chosen.

End of Game Pop up
-Header Text: Game Complete!
- Row 1 (Final Score Row): left team+score vs right team+score
- Row 2: POTG image (horizontally centered with equal spece between row above and row below it)
- Row 3: POTG stats "XX PTS  XX Reb  XX Ast" (Reb is TREB)
- Row 4: POTG stats "XX STL  XX BLK  XX Def%"
- Row 5: Two CTA buttons (same as currenlty designed)
Keep all design components of the pop up as is, jsut add the POTG content as instructed above

Also, add "Player Of The Game" section to Box Score at end of game, below the Team Quarterly Scoring and above the two team tabs.

Header, horizontally centered "Player Of The Game"
Row 1: horizontally centered: "{Player Name} - {Player Team}"
Row 2 (stats)" XX PTS  XX REB  XX AST  XX STL  XX BLK  XX DEF%"
