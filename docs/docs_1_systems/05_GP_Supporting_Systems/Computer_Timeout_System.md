## Computer Timeout System ✅ **COMPLETE** (January 2025)

**Base Constants**

1. **Timeout Turn Type**: `TIMEOUT` (with `timeout_reason="COMPUTER"`)
2. **Evaluation Timing**: Only during BIP (Baseline Inbound) and SIP (Side Inbound) turns
3. **Timeout Limits**:
   - **Q1-Q3**: Maximum 1 timeout per quarter
   - **Q4**: Maximum number of timeouts equal to remaining timeouts upon entering the quarter
4. **Deferred Creation**: Pending timeout stored in `game_state["pending_computer_timeout"]` instead of creating immediately
5. **State Tracking**: `game_state["computer_timeouts"][team_name][quarter]["count"]` and `["checked_conditions"]`
6. **Key Files**:
   - `BackEnd/models/turn_manager.py`: `should_computer_call_timeout()` method
   - `BackEnd/models/game_manager.py`: Integrates computer timeout check into BIP/SIP turn creation
   - `BackEnd/api/api.py`: `/api/simulate-turn` endpoint checks for pending timeout

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
- Computer timeout is evaluated when the BIP/SIP turn would be created (backend)
- **Deferred Creation:** If computer calls timeout, a pending timeout is stored in `game_state["pending_computer_timeout"]` instead of creating the timeout turn immediately
- This allows the current turn (e.g., shot) to be returned and animated before the timeout is created
- On the next API call (`/api/simulate-turn`), the pending timeout is created and returned immediately
- User timeout button is only active during the 2-second pause window (after turn is received by frontend)
- **Precedence:** If computer timeout is called, it takes precedence over user timeout (computer timeout is checked before the BIP/SIP turn is created)

**Timeout Limits:**
- **Q1-Q3:** Computer can call maximum 1 timeout per quarter
- **Q4:** Computer can call maximum number of timeouts equal to remaining timeouts upon entering the quarter
- If max timeouts are reached, all timeout percentages become 0% for that quarter

### Timeout Conditions

Computer evaluates timeout conditions in order. Each condition only checks once per occurrence (tracked per quarter). Conditions are quarter-specific for foul logic, but energy conditions apply to all quarters.

**Important:** Timeout conditions are evaluated **only for players in the active lineup** (not all players on the team). This aligns with the autoset lineup logic - the computer only evaluates timeout conditions for players who are currently playing. This prevents timeouts from being triggered by players who were already excluded from the lineup at quarter breaks due to foul or energy restrictions.

#### Q1 Conditions

**Foul Conditions:**
1. **Player with 3 fouls:** 100% chance (immediate timeout)
2. **Player with 2 fouls:** 30% chance (checks once at first BIP/SIP after foul)

**Energy Conditions (apply to all quarters Q1-Q4):**
3. **3 players < 80% NG:** 50% chance (checks once at first BIP/SIP after condition met)
4. **4 players < 80% NG:** 75% chance (checks once at first BIP/SIP after condition met)
5. **5 players < 80% NG:** 90% chance (checks once at first BIP/SIP after condition met)
6. **3 players < 70% NG:** 80% chance (checks once at first BIP/SIP after condition met)
7. **4 players < 70% NG:** 90% chance (checks once at first BIP/SIP after condition met)
8. **5 players < 70% NG:** 95% chance (checks once at first BIP/SIP after condition met)
9. **3 players < 60% NG:** 100% chance (immediate timeout)

#### Q2 & Q3 Conditions

**Foul Conditions:**
1. **Player with 4 fouls:** 100% chance (immediate timeout)
2. **Player with 3 fouls:** 90% chance (checks once at first BIP/SIP after foul)

**Energy Conditions:** Same as Q1 (conditions 3-9 above)

#### Q4 Conditions

**Foul Conditions (only if time_remaining > 60 seconds):**
1. **Player with 4 fouls:** 90% chance (checks once at first BIP/SIP after foul, only if more than 1 minute remaining)

**Energy Conditions:** Same as Q1 (conditions 3-9 above)

**Note:** Conditions are evaluated in order. If a higher-priority condition triggers (e.g., 4 fouls = 100% in Q2/Q3), lower-priority conditions are not checked. Energy conditions apply to all quarters (Q1-Q4).

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
- **Pending Timeout:** When computer timeout is detected, `game_state["pending_computer_timeout"]` is set with:
  - `calling_team`: TeamManager instance for the team calling timeout
  - `turn_type`: "BASELINE_INBOUND" or "SIDE_INBOUND"
  - `timeout_reason`: "COMPUTER"
- The pending timeout is cleared when the timeout turn is created on the next API call

**Integration Points:**
- Computer timeout check occurs in `game_manager.simulate_macro_turn()` when creating SIP turns
- Computer timeout check occurs in `game_manager.simulate_macro_turn()` when creating BIP turns
- **Deferred Timeout Creation:** If computer calls timeout, `game_state["pending_computer_timeout"]` is set with the calling team and turn type. The BIP/SIP turn is NOT appended, and the function returns normally, allowing the current turn (e.g., shot) to be returned and animated.
- **Turn-by-turn mode:** The `/api/simulate-turn` endpoint checks for `pending_computer_timeout` at the START of the call (before calling `simulate_macro_turn()`). If a pending timeout exists, it creates the timeout turn immediately and returns it to the frontend. This ensures the previous turn has been animated before the timeout is created.
- **Game state persistence:** When a computer timeout is returned from `/api/simulate-turn`, the game state is immediately saved to the database (same as user timeouts). This ensures clock, scores, fouls, and timeout state are preserved when the user returns from the lineup screen.
- **Game state restoration:** When resuming from a computer timeout, the backend checks for timeout state in the saved document before calculating `should_restore_stats`. This ensures that scores, fouls, timeouts, and other team-level data are properly restored (same as user timeouts). The timeout state check happens early in the game loading process to ensure all state is restored correctly.
- **Frontend navigation:** Computer timeout turns trigger the exact same navigation flow as user timeouts (no popup, direct navigation). The `AnimationEngine.handleTimeout()` method detects computer timeouts and automatically calls `showTimeoutPopup()` to navigate directly to the lineup screen with proper `resume_from_timeout` and `clock` parameters. The `showTimeoutPopup()` function accepts optional `computerTimeout` and `computerTeamName` parameters, which are passed as URL parameters (`computer_timeout=true` and `computer_team_name={Team Name}`) to the lineup screen.
- **Lineup screen display:** When the lineup screen loads with `computer_timeout=true` in the URL, bold red text is displayed in the header (to the right of the team scores) that reads "{Computer Team Name} Called Timeout". This text only appears when `computer_timeout=true` is present in the URL, ensuring it does not persist to the next TNS instance unless it's another computer timeout. The text is implemented using a `<span>` element with inline styles (`color: red; font-weight: bold; margin-left: 20px;`) appended to the header text in `set-lineup.js`.
- **Works during simmed quarters:** Computer timeout logic runs during "Sim To 4th Quarter" and "Sim Full Game" operations
- **Two computer teams:** Both teams are checked for timeout conditions; first team to meet conditions calls timeout
- **Lineup adjustments:** When computer calls timeout during simmed quarters, both team lineups are rebuilt using `build_lineup_from_mongo()` (same autoset logic as regular timeouts)

### Simmed Quarter Behavior

**Sim To 4th Quarter and Sim Full Game:**
- Computer timeout logic runs during all simmed quarters (Q1-Q3 for "Sim To 4th Quarter", Q1-Q4 for "Sim Full Game")
- Computer teams can call timeouts during simmed quarters using the same conditions and logic as regular gameplay
- **User team lineup handling:** When a computer timeout occurs during simmed quarters, the user team's lineup is also automatically rebuilt using the same autoset lineup process (`build_lineup_from_mongo()`). This ensures both teams have optimal lineups based on current energy levels and foul status, even though the user is not actively managing the lineup during simmed quarters.
- **Two computer teams:** In games where both teams are computer-controlled, both teams are evaluated for timeout conditions. The first team to meet timeout conditions calls the timeout, and both team lineups are rebuilt using autoset lineup logic.

**Key Implementation:**
- Computer timeout checking happens in `game_manager.simulate_macro_turn()` which is called during the simulation loop in `simulate_quarter()`
- When computer timeout is called during simmed quarters, both `calling_team.lineup` and `other_team.lineup` are rebuilt via `build_lineup_from_mongo()`
- This ensures consistent lineup management across all gameplay modes (regular gameplay, simmed quarters, user timeouts, computer timeouts)

