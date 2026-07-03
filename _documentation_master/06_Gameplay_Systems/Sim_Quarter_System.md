## Sim Quarter System ✅ **COMPLETE** (January 2025; re-verified against code June 2026)

**Base Constants**

1. **Quarter Display Logic**: Shows quarter that just completed (`quarter - 1`), not the quarter being simulated
2. **Turn Filtering**: Filters turns by `turn.quarter` field, with fallback to `quarter - 1` if no turns found
3. **Event Types in Scroll**: MAKE, MISS, PUTBACK_MAKE/MISS, FREE_THROW, FOUL, DEAD_BALL, STEAL (all displayable turn types create scroll entries; score/clock use event-matching pipeline)
4. **Update Timing**:
   - Shot entries: 2 second delay between each shot
   - Clock updates: 200ms delay for non-shot turns
5. **Key Files**:
   - `FrontEnd/static/js/phaser/bootGame.js`: `showSimQuarterResults()` function, `handleSimQuarter()` function
   - `FrontEnd/static/court.html`: Popup HTML structure and CSS styling
   - `BackEnd/api/api.py`: `/api/simulate-quarter` endpoint
6. **API Endpoint**: `POST /api/simulate-quarter` with `full_sim=true` parameter
7. **Score/clock revert fix (do not remove):** Multiple events can share the same `time_remaining` and type (e.g. two fouls at same clock). If the same event were matched for each turn, the scoreboard would show an older cumulative score and “revert” 2–4 times per quarter. **Fix:** At the start of `eventResults.find(...)` in `showSimQuarterResults()`, skip any event whose index is in `matchedEventIndices`; add every matched event to that set. Each event is then used at most once. Code: `bootGame.js` inside the find callback, first lines.

**System Flow (10 Steps)**

1. **User Initiates**: User clicks "Sim Quarter" button on pre-game or quarter break screen
2. **Quarter Calculation**: Frontend calculates `nextQuarter = quarter + 1` (e.g., Q1 break → simulate Q2)
3. **Backend Simulation**: POST request to `/api/simulate-quarter` with `full_sim=true` (instantly simulates entire quarter)
4. **Turn Filtering**: Frontend filters `lastSummary.turns` array to only include turns from the quarter just simulated
5. **Popup Display**: Sim Quarter popup appears, game control buttons hidden
6. **Real-Time Updates**: 
   - Scoreboard scores update with each shot
   - Scoreboard clock updates with each turn (all turns, not just shots)
   - Shot entries scroll into view with 2-second delays
7. **Event Processing**: Turns that match displayable types (MAKE, MISS, PUTBACK, FREE_THROW, FOUL, DEAD_BALL, STEAL) are matched to events and create scroll entries; each event is used at most once to avoid score/clock revert
8. **Completion**: After all shots processed (or "No shots" message), 2-second delay, then popup hidden
9. **Navigation**: If game complete, show completion popup; otherwise navigate to lineup screen for next quarter
10. **Game Controls**: Game control buttons (Game Speed, Pause, Skip, Timeout) restored when popup hidden

**Long Form Documentation**

### Overview

The Sim Quarter System provides a real-time text scroll experience during quarter simulation. Instead of the static "Simulating Q#" message, users see a scrolling list of shot results with live scoreboard updates. The system processes all turns to update the clock in real-time, but only displays shot events (makes and misses) in the scroll.

**Key Features:**
- Real-time scoreboard score updates (home and away scores)
- Real-time scoreboard clock updates (time remaining decreases with each turn)
- Scrolling text display of shot results with player names, jersey numbers, and shot types
- Team primary colors applied to player names and jersey numbers
- Automatic filtering to show only the current quarter's shots (prevents re-scrolling previous quarters)

### Events Printed in Scroll

**All Event Types Displayed:**

1. **Regular Shots** (`result_type: 'MAKE'` or `'MISS'`):
   - Format: `[Time]: Player Name (#jersey) makes/misses the 2-pt shot.` or `makes/misses the 3-pt shot.`
   - Example: `[7:45]: John Smith (#23) makes the 3-pt shot.`

1b. **Shooting fouls on misses**: when a MISS carries a defensive foul with free throws coming (`foul_team === 'DEFENSE'` and `free_throws_remaining > 0` or `next_play_type === 'FREE_THROW'`), the entry text appends **"Shooting foul!"**.

1c. **Player headshots**: scroll entries include the player's photo (`sim-quarter-player-image`), with environment-aware path normalization (`/static/` prefix on localhost) and a generic-headshot fallback on error.

2. **Fast Break Shots** (`result_type: 'MAKE'` or `'MISS'` with `fast_break: true` or `offensive_state: 'FAST_BREAK'`):
   - Format: `[Time]: [Fast Break] Player Name (#jersey) makes/misses the 2-pt shot.` or `makes/misses the 3-pt shot.`
   - Example: `[6:23]: [Fast Break] Mike Johnson (#5) makes the 2-pt shot.`
   - Special prefix: `[Fast Break]` appears after time, before player name

3. **OREB Putback Attempts** (`result_type: 'PUTBACK_MAKE'` or `'PUTBACK_MISS'`):
   - Format: `[Time]: [Off Rebound] Player Name (#jersey) makes/misses the 2-pt shot.` or `makes/misses the 3-pt shot.`
   - Example: `[5:12]: [Off Rebound] Chris Davis (#42) misses the 2-pt shot.`
   - Special prefix: `[Off Rebound]` appears after time, before player name

4. **Free Throws** (`result_type: 'FREE_THROW'`):
   - Format: `[Time]: Player Name (#jersey) makes/misses the free throw.`
   - Example: `[4:30]: Sarah Williams (#10) makes the free throw.`
   - Note: Made/missed determined by `points > 0` in turn data

5. **Fouls** (`result_type: 'FOUL'`):
   - Format: `[Time]: Player Name (#jersey) commits a foul.`
   - Example: `[3:15]: Tom Brown (#7) commits a foul.`

6. **Dead Ball Turnovers** (`result_type: 'DEAD BALL'` or `'TURNOVER'`):
   - Format: `[Time]: Player Name (#jersey) turnover (dead ball).`
   - Example: `[2:45]: Alex Green (#15) turnover (dead ball).`

7. **Steals** (`result_type: 'STEAL'`):
   - Format: `[Time]: Player Name (#jersey) steals the ball.`
   - Example: `[1:30]: Jordan White (#3) steals the ball.`

**Event Filtering:**
- Only turns matching the above event types are displayed in the scroll
- All other turn types (passes, defensive rebounds, etc.) update the clock but do not create scroll entries
- If no events occur in the quarter, displays: "No shots in this quarter."

**Turn Processing:**
- All turns are processed to update the scoreboard clock in real-time
- Event turns create scroll entries with 2-second delays
- Non-event turns update clock with 200ms delays (faster progression)

### Design Components and Colors

**Container Styling:**
- **Fill Color**: `#c8cdd4` (light gray background)
- **Border**: `1px solid #6b7280` (medium gray border)
- **Position**: Absolute, centered horizontally, positioned below scoreboard
- **Size**: 
  - Width: `600px` (max-width: `90%` for responsive)
  - Height: `calc((100vh - var(--scoreboard-height) - 40px) * 0.8)` (80% of available vertical space)
  - Padding: `20px 50px`
  - Border radius: `12px`
  - Box shadow: `0 8px 32px rgba(0, 0, 0, 0.8)`

**Text Colors:**
- **Main Text** (`#111827` - dark gray/black):
  - Header title: "Simulating Q#..."
  - Shot result text: "makes the 2-pt shot." / "misses the 3-pt shot."
  - "No shots" message
- **Time Remaining** (`#374151` - medium-dark gray):
  - Clock values in brackets: `[7:45]`, `[6:23]`, etc.
- **Team Primary Colors** (from team data):
  - Player names: Team's primary color (e.g., `#ec1d28` for Morristown, `#65308e` for Little York)
  - Jersey numbers: Same team primary color
  - Applied via inline styles: `style="color: ${teamColor}; font-weight: bold;"`

**Typography:**
- **Font Family**: `'Bebas Neue', sans-serif`
- **Header Font Size**: `28px`
- **Content Font Size**: `18px`
- **Line Height**: `1.8`

**Scroll Container:**
- **Overflow**: `overflow-y: auto` (vertical scrolling)
- **Scrollbar Styling**: Custom styled with orange thumb (`#ff6200`) and dark track
- **Auto-scroll**: Automatically scrolls to bottom as new entries are added

**UI Behavior:**
- **Game Controls**: Hidden when popup is visible (Game Speed, Pause, Skip To End, Timeout buttons)
- **Pre-game Container**: Hidden when popup appears
- **Scoreboard**: Remains visible and updates in real-time (scores and clock)

### Technical Implementation

**Turn Filtering Logic:**
```javascript
// Filter turns to only include the quarter just simulated
const allTurns = lastSummary.turns || [];
let turns = allTurns.filter(turn => turn.quarter === quarter);

// Fallback: If no turns found, try quarter-1 (backend sets quarter before incrementing)
if (turns.length === 0 && quarter > 1) {
  turns = allTurns.filter(turn => turn.quarter === quarter - 1);
}
```

**Shot Result Extraction:**
- Iterates through filtered turns
- Extracts: `shooter_id`, `result_type`, `points`, `time_remaining`, `score`
- Maps player IDs to player data (name, jersey, team) from `lastSummary.players`
- Determines shot type: `points === 3 ? '3-pt' : '2-pt'`

**Event Pipeline (two passes):**
1. **Build `eventResults`**: One pass over `turns`; for each displayable turn (MAKE/MISS, PUTBACK, FREE_THROW, FOUL, DEAD_BALL, STEAL), push an object with `homeScore`/`awayScore` from that turn’s `turn.score` (cumulative), plus time, type, player info.
2. **Match and update**: Second pass over `turns`; for each turn, find the corresponding event in `eventResults` by time and result/event type (with special handling for PUTBACK and FREE_THROW). The scoreboard is updated from the **matched event’s** `homeScore`/`awayScore` (and the scroll entry is built from that event). So scores shown are always the cumulative score from the turn that produced that event.

**Match-at-most-once (prevents score/clock revert):**
- **Problem:** Multiple events can share the same `time_remaining` and type. Without tracking, `find()` returns the first match every time, so the second+ turn at that time would reuse the first event’s (older) score and the scoreboard would revert.
- **Solution:** `matchedEventIndices` (a Set) records which event indices have been matched. At the **start** of every `eventResults.find(...)` callback, `if (matchedEventIndices.has(eventIndex)) return false`. After a match, `matchedEventIndices.add(eventIndex)`. Each event is used at most once; each turn gets the correct event and score. **Do not remove this guard**—see Base Constants item 7.

**Real-Time Scoreboard Updates:**
- **Scores**: Updated from the **matched event’s** `homeScore`/`awayScore` (each event was built from `turn.score` for that turn; same authoritative source as `gameScene.js`).
- **Clock**: Updated from `turn.time_remaining`, `turn.clock`, or `turn.game_clock` on **every** turn (before matching).
- **Clock Format**: Converts seconds to `MM:SS` format if needed.
- **Update Frequency**: 
  - Scores: When a turn has a matched event (score comes from that event).
  - Clock: Every turn (200ms delay for non-event turns, 2s delay when an event is displayed).

**Team Color Resolution:**
- Checks unified `teams[team_id]` structure first (SS&S pattern from `gameScene.js`)
- Fallback to direct `home_team`/`away_team` objects for backward compatibility
- Extracts `colors.primary_color` from team objects
- Applied to player names and jersey numbers in shot entries

**Quarter Display:**
- Header shows: `Simulating Q${displayQuarter}...` where `displayQuarter = quarter - 1` (overtime periods label as `OT1`, `OT2`, … when `displayQuarter > 4`)
- Example: At Q1 break, simulating Q2 → header shows "Simulating Q1..." (the quarter that just completed)
- Scoreboard quarter display is NOT updated during Sim Quarter (stays at completed quarter)

### User Experience Flow

1. **Pre-Game or Quarter Break**: User sees pre-game buttons (Play Quarter, Sim Quarter, Sim Full Game)
2. **User Clicks "Sim Quarter"**: Button disabled, simulation begins
3. **Backend Processing**: Quarter is fully simulated instantly (`full_sim=true`)
4. **Popup Appears**: 
   - Container slides into view
   - Header shows "Simulating Q#..." (quarter that just completed)
   - Game control buttons hidden
5. **Real-Time Updates**:
   - Scoreboard scores increment as shots are made
   - Scoreboard clock decreases with each turn
   - Shot entries scroll into view one by one
6. **Shot Display Format**: Each shot shows time, colored player name/jersey, and result
7. **Completion**: 
   - If shots occurred: Last shot displayed, 2-second delay
   - If no shots: "No shots in this quarter." message, 2-second delay
8. **Navigation**:
   - If game complete: Completion popup appears
   - If game continues: Navigate to lineup screen for next quarter
9. **Popup Hidden**: Container hidden, game controls restored

### Key Implementation Details

**Backend Quarter Simulation:**
- Uses `simulate_quarter()` function with `turn_by_turn_mode=False` (full simulation)
- Backend sets `turn.quarter = gm.quarter` BEFORE simulating
- After simulation, `gm.quarter` is incremented
- This means turns created during Q2 simulation have `quarter=1` (the quarter that was active)

**⚠️ `_is_full_simulation` flag — invariant (silent failure mode):** The full-sim loop sets `game_state["_is_full_simulation"]=True` to skip work that a full sim doesn't need. Beyond timeout logic ([`Computer_Timeout_System.md`](Computer_Timeout_System.md)), it makes the **animator early-return `[]`** — `skeleton_to_animations()` returns no animations, so `build_skeleton_animation_steps()` returns `None` and the turn emits **zero `animation_steps`** (no exception, no warning). If this flag ever leaks onto a turn-by-turn/saved game (it's persisted wholesale by `GameManager.to_dict()`), turns **resolve but don't animate** — players freeze in place. Invariants that keep this safe: (1) the flag's set/clear is wrapped in `try/finally` in `simulate_quarter()` so a mid-loop error can't leak it; (2) `simulate_turn_endpoint()` clears it on entry so turn-by-turn playback self-heals. Do **not** rely on the animator's early-return as an error path — it's a deliberate perf skip.

**Frontend Quarter Handling:**
- Frontend receives `nextQuarter` (the quarter being simulated)
- Filters turns by `nextQuarter` first, falls back to `nextQuarter - 1` if needed
- Display quarter is `nextQuarter - 1` (the quarter that just completed)

**Score Synchronization:**
- Authoritative source is `turn.score` (dict: `{homeTeamName: score, awayTeamName: score}`), same as `updateScoreboard` in `gameScene.js`. When building `eventResults`, each event stores that turn’s cumulative score; when we match a turn to an event, we update the scoreboard from that event’s score.
- Initial scores from `lastSummary.start_box_score` (or first turn’s score if unavailable).
- Each displayed event updates the scoreboard from the **matched event’s** score (one-to-one matching via `matchedEventIndices` prevents reusing an event and avoids reverts).

**Error Handling:**
- Popup elements checked before processing
- Graceful fallback if team colors not found (uses orange `#ff6200`)
- "No shots" message if quarter has no shot events
- Game controls always restored even if error occurs

### Integration Points

**With Scoreboard System:**
- Updates `#home-score` and `#away-score` elements in real-time
- Updates `#game-clock` element with each turn
- Does NOT update `#quarter` element (stays at completed quarter)

**With Game Control System:**
- Hides `.game-controls` container when popup visible
- Restores game controls when popup hidden
- Only affects Sim Quarter popup visibility (not other game states)

**With Navigation System:**
- Uses `TimeoutNavigationHelper` for consistent URL parameter building
- Navigates to `set-lineup.html` after quarter simulation
- Preserves game mode, team IDs, and other context

**With Game Completion System:**
- Checks `lastSummary.is_final` to determine if game is complete
- Uses shared `handleGameCompletion()` function if game ends
- Shows completion popup instead of navigating to lineup screen

### Future Enhancements

**Potential Additions:**
- Real-time box score updates during scroll
- Animation/transition effects for score updates
- Customizable scroll speed/delay settings
- Filter options (show only makes, only misses, etc.)

**Design Considerations:**
- Colors are easily adjustable (documented above for experimentation)
- Container size and positioning can be modified in CSS
- Text formatting can be enhanced with additional styling
- Scroll behavior can be customized (smooth scrolling, auto-pause, etc.)

