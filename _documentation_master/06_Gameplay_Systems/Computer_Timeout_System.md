## Computer Timeout System ✅ **COMPLETE** (January 2025; re-verified June 2026)

**Base Constants**

1. **Timeout Turn Type**: `TIMEOUT` (with `timeout_reason="COMPUTER"`)
2. **Evaluation Timing**: Only during BIP (Baseline Inbound) and SIP (Side Inbound) turns
3. **Timeout Limits** (per quarter, from `should_computer_call_timeout()`):
   - **Q1–Q2**: Maximum **1** timeout per quarter
   - **Q3**: Maximum = **remaining timeouts − 1** (clamped to ≥ 0)
   - **Q4**: Maximum = **remaining timeouts** upon entering the quarter
   - **Q4 time gate**: Computer cannot call a timeout in the fourth quarter until time remaining is less than 4 minutes (240 seconds). If time_remaining ≥ 240 in Q4, no timeout is evaluated.
4. **Deferred Creation**: Pending timeout stored in `game_state["pending_computer_timeout"]` instead of creating immediately
5. **State Tracking**: `game_state["computer_timeouts"][team_name][quarter]["count"]` and `["checked_conditions"]`
6. **Key Files**:
   - `BackEnd/models/turn_manager.py`: `should_computer_call_timeout()` method
   - `BackEnd/models/game_manager.py`: Integrates computer timeout check into BIP/SIP turn creation
   - `BackEnd/api/api.py`: `/api/simulate-turn` endpoint checks for pending timeout; restores `computer_timeouts` when loading from DB (timeout resume + simulate-quarter load path)
   - `BackEnd/utils/shared.py`: `serialize_computer_timeouts()` / `deserialize_computer_timeouts()` for DB persistence (checked_conditions set ↔ list)

**System Flow (8 Steps)**

1. **Timeout Evaluation** - During BIP/SIP turn creation, computer team evaluates timeout conditions
2. **Condition Checking** - Checks foul and energy conditions in order (quarter-specific for fouls, all quarters for energy)
3. **Pending Timeout** - If timeout called, sets `game_state["pending_computer_timeout"]` (deferred creation)
4. **Turn Completion** - Current turn (e.g., shot) is returned and animated first
5. **Timeout Creation** - On next `/api/simulate-turn` call, pending timeout is created and returned immediately
6. **State Persistence** - Game state saved to database (same as user timeouts)
7. **Frontend Navigation** - Same navigation flow as user timeouts (direct to lineup screen)
8. **Lineup Rebuild** - Computer team lineup rebuilt using autoset lineup process

**Long Form Documentation**

### Overview

The computer timeout system enables AI-controlled teams to call timeouts during gameplay. Computer teams automatically evaluate timeout conditions and call timeouts when strategic situations arise.

**Timeout Timing:**
- Computer can only call timeouts during BIP (Baseline Inbound) and SIP (Side Inbound) turns
- **Play Quarter Mode:** Computer timeout checks **do run** — but only **non-user (computer)** teams are added to the check list, so the user team never has a timeout called for it
- **Sim Quarter / Sim Full Game Mode:** Both teams are added to the check list; the user team uses the same timeout logic silently inside the sim (no UX interruption)
- Computer timeout is evaluated when the BIP/SIP turn would be created (backend)
- **Team Filtering (two layers):** (1) the caller in `game_manager` only adds the user team to the check list when `_is_full_simulation` is `True`; (2) `should_computer_call_timeout()` independently returns `False` for a user team when `not is_full_simulation`
- User timeout button is only active during the 2-second pause window (after turn is received by frontend)
- **Precedence:** If computer timeout is called, it takes precedence over user timeout (computer timeout is checked before the BIP/SIP turn is created)

**Timeout Limits:**
- **Q1–Q2:** Computer can call maximum 1 timeout per quarter
- **Q3:** Maximum = remaining timeouts − 1 (clamped to ≥ 0)
- **Q4:** Computer can call maximum number of timeouts equal to remaining timeouts upon entering the quarter
- **Q4 time gate:** Computer cannot call a timeout in the fourth quarter until time remaining is less than 4 minutes (240 seconds). When time_remaining ≥ 240 in Q4, the computer does not evaluate any timeout conditions for that turn.
- If max timeouts are reached, all timeout percentages become 0% for that quarter

### Timeout Conditions

Computer evaluates timeout conditions in order. Each condition only checks once per occurrence (tracked per quarter). Conditions are quarter-specific for foul logic, but energy conditions apply to all quarters.

**Important:** Timeout conditions are evaluated **only for players in the active lineup** (not all players on the team). This aligns with the autoset lineup logic - the computer only evaluates timeout conditions for players who are currently playing. This prevents timeouts from being triggered by players who were already excluded from the lineup at quarter breaks due to foul or energy restrictions.

#### Q1 Conditions

**Foul Conditions:**
1. **Player with 3 fouls:** 100% chance (immediate timeout)
2. **Player with 2 fouls:** 30% chance (checks once at first BIP/SIP after foul)

**Energy Conditions (Q1–Q2 use 80% / 70% / 60%; Q3–Q4 use 75% / 65% / 55%):**
3. **3 players below high threshold (80% in Q1–Q2, 75% in Q3–Q4):** 50% chance (checks once at first BIP/SIP after condition met)
4. **4 players below high threshold:** 75% chance (checks once at first BIP/SIP after condition met)
5. **5 players below high threshold:** 90% chance (checks once at first BIP/SIP after condition met)
6. **3 players below mid threshold (70% in Q1–Q2, 65% in Q3–Q4):** 80% chance (checks once at first BIP/SIP after condition met)
7. **4 players below mid threshold:** 90% chance (checks once at first BIP/SIP after condition met)
8. **5 players below mid threshold:** 95% chance (checks once at first BIP/SIP after condition met)
9. **3 players below low threshold (60% in Q1–Q2, 55% in Q3–Q4):** 100% chance (immediate timeout)

#### Q2 Conditions

**Foul Conditions:**
1. **Player with 4 fouls:** 100% chance (immediate timeout)
2. **Player with 3 fouls:** 90% chance (checks once at first BIP/SIP after foul)

**Energy Conditions:** Same as Q1 (80% / 70% / 60% thresholds; conditions 3–9 above)

#### Q3 Conditions

**Foul Conditions (only if time_remaining ≤ 240 seconds / 4:00):**
1. **Player with 4 fouls:** 100% chance (immediate timeout)
2. **Player with 3 fouls:** 90% chance (checks once at first BIP/SIP after foul)

If time_remaining > 240 (more than 4:00 left in the quarter), foul conditions are not evaluated in Q3; energy conditions still apply.

**Energy Conditions:** Same thresholds as Q4: **75% / 65% / 55%** (5% lower than Q1–Q2). Conditions 3–9 apply with these thresholds.

#### Q4 Conditions

**Q4 time gate:** Computer cannot call a timeout in Q4 until time remaining is less than 4 minutes (time_remaining < 240 seconds). If time_remaining ≥ 240, no timeout conditions are evaluated for that turn (no foul or energy checks).

**Foul Conditions (only if time_remaining < 240 and time_remaining > 60 seconds):**
1. **Player with 4 fouls:** 90% chance (checks once at first BIP/SIP after foul, only if more than 1 minute remaining)

**Energy Conditions:** Same thresholds as Q3: **75% / 65% / 55%** (5% lower than Q1–Q2). Conditions 3–9 apply with these thresholds (only when time_remaining < 240 in Q4).

**Note:** Conditions are evaluated in order. If a higher-priority condition triggers (e.g., 4 fouls = 100% in Q2/Q3), lower-priority conditions are not checked. Energy conditions apply to all quarters (Q1-Q4). In Q4, the time gate is applied first; only when time remaining is under 4 minutes are any conditions evaluated.

### Implementation Details

**Key Files:**
- `BackEnd/models/turn_manager.py`: `should_computer_call_timeout()` method evaluates timeout conditions
- `BackEnd/models/game_manager.py`: Integrates computer timeout check into BIP/SIP turn creation
- `BackEnd/models/turn_manager.py`: `setup_timeout_turn()` creates timeout turn with `timeout_reason="COMPUTER"`

**Timeout Turn Structure:**
- Same structure as user timeout turns
- `timeout_reason: "COMPUTER"`
- `text: "{Team Name} Calls a Timeout"`
- Computer team lineup is rebuilt using autoset lineup process (same as user timeouts)

**State Tracking:**
- Computer timeout count per quarter stored in `game_state["computer_timeouts"][team_name][quarter]["count"]`
- Checked conditions tracked in `game_state["computer_timeouts"][team_name][quarter]["checked_conditions"]` set
- Prevents duplicate condition checks within the same quarter
- **Persistence (source of truth: database):** `computer_timeouts` is persisted to the game document on every save via `summarize_game_state()` (shared.py). `checked_conditions` sets are serialized to lists for JSON/DB. Restored when loading from DB in `apply_timeout_resume_state_to_gm()` (timeout resume) and in the simulate-quarter load path so the "max 1 per quarter Q1–Q3" limit is enforced after returning from timeout or any other DB load.
- **Pending Timeout:** When computer timeout is detected, `game_state["pending_computer_timeout"]` is set with:
  - `calling_team`: TeamManager instance for the team calling timeout
  - `turn_type`: "BASELINE_INBOUND" or "SIDE_INBOUND"
  - `timeout_reason`: "COMPUTER"
- The pending timeout is cleared when the timeout turn is created on the next API call

**Integration Points:**
- Computer timeout check occurs in `game_manager.simulate_macro_turn()` when creating SIP and BIP turns — in **all modes** (Play Quarter, Sim Quarter, Sim Full Game). The check itself is **not** gated by `_is_full_simulation`.
- **What the simulation flag actually gates:** which teams get evaluated. In full simulation, both `home_team` and `away_team` are checked (so the user team can use the same timeout logic silently inside the sim). In turn-by-turn (Play Quarter), only **non-user** teams are added to the check list. In both cases `should_computer_call_timeout()` also re-filters: it returns `False` for a user team when `not is_full_simulation`.
- **Two paths for creating the timeout (the real `is_full_simulation` branch):**
  - **Full simulation → immediate creation:** the timeout turn is created inline via `call_timeout(..., rebuild_both_lineups=True)` and the method returns without appending the SIP/BIP turn (no deferred creation since animations are skipped). Game state is saved to the DB (clock, scores, fouls, timeout state).
  - **Turn-by-turn → deferred creation:** sets `game_state["pending_computer_timeout"]` (`calling_team`, `turn_type`) and returns without appending the inbound turn; the pending timeout is created on the next `/api/simulate-turn` call so the current turn animates first.
- **Game state restoration:** When resuming from a computer timeout, the backend checks for timeout state in the saved document before calculating `should_restore_stats`. This ensures that scores, fouls, timeouts, and other team-level data are properly restored (same as user timeouts). The timeout state check happens early in the game loading process to ensure all state is restored correctly.
- **Frontend navigation:** Computer timeout turns trigger the exact same navigation flow as user timeouts (no popup, direct navigation). The `AnimationEngine.handleTimeout()` method detects computer timeouts and automatically calls `showTimeoutPopup()` to navigate directly to the lineup screen with proper `resume_from_timeout` and `clock` parameters. The `showTimeoutPopup()` function accepts optional `computerTimeout` and `computerTeamName` parameters, which are passed as URL parameters (`computer_timeout=true` and `computer_team_name={Team Name}`) to the lineup screen.
- **Lineup screen display:** When the lineup screen loads with `computer_timeout=true` in the URL, bold red text is displayed in the header (to the right of the team scores) that reads "{Computer Team Name} Called Timeout". This text only appears when `computer_timeout=true` is present in the URL, ensuring it does not persist to the next TNS instance unless it's another computer timeout. The text is implemented using a `<span>` element with inline styles (`color: red; font-weight: bold; margin-left: 20px;`) appended to the header text in `set-lineup.js`.
- **Two teams:** Both teams' eligible entries are checked for timeout conditions; first team to meet conditions calls timeout.
- **Lineup adjustments:** When a computer timeout is created in full simulation, both team lineups are rebuilt via `call_timeout(rebuild_both_lineups=True)` (same autoset logic as regular timeouts).

### Simmed Quarter Behavior

**Sim Quarter and Sim Full Game (Full Simulation Mode):**
- Computer timeout logic ONLY runs during full simulation mode ("Sim Quarter" or "Sim Full Game")
- Computer timeout checks are gated by the `_is_full_simulation` flag in `game_manager.simulate_macro_turn()`
- Computer teams can call timeouts during simmed quarters using the same conditions and logic as regular gameplay
- **User team lineup handling:** When a computer timeout occurs during simmed quarters, the user team's lineup is also automatically rebuilt using the same autoset lineup process (`build_lineup_from_mongo()`). This ensures both teams have optimal lineups based on current energy levels and foul status, even though the user is not actively managing the lineup during simmed quarters.
- **Two computer teams:** In games where both teams are computer-controlled, both teams are evaluated for timeout conditions. The first team to meet timeout conditions calls the timeout, and both team lineups are rebuilt using autoset lineup logic.

**Play Quarter Mode (Turn-by-Turn Mode):**
- Computer timeout checks **DO run** during "Play Quarter" mode for computer teams
- User teams are filtered out by `should_computer_call_timeout()` method (checks `is_user_team` flag)
- This allows computer opponents to call timeouts during "Play Quarter" mode, but prevents computer from calling timeouts for the user team

**Key Implementation:**
- Computer timeout checking happens in `game_manager.simulate_macro_turn()` when creating SIP (Side Inbound) and BIP (Baseline Inbound) turns
- `should_computer_call_timeout()` method filters out user teams by checking `computer_team.is_user_team` flag (returns `False` if user team)
- This allows computer timeout checks to run in all modes (Play Quarter, Sim Quarter, Sim Full Game) while ensuring user teams never have computer timeouts called for them
- When computer timeout is called, both `calling_team.lineup` and `other_team.lineup` are rebuilt via `build_lineup_from_mongo()`
- This ensures consistent lineup management across all gameplay modes while respecting the user's choice between "Play Quarter" and "Sim Quarter"

