# Gameplay Buttons System

**Purpose**: User controls for starting quarters in different modes (play with animation, simulate without animation).

---

## Four Buttons Overview

1. **Play Quarter** - Turn-by-turn gameplay with animation (`full_sim=false`)
2. **Sim Quarter** - Simulate one quarter instantly without animation (`full_sim=true`)
3. **Sim Rest of Game** - Simulate all remaining quarters (Q2-Q3 only)
4. **Sim Full Game** - Simulate entire game from Q1 (Q1 only)

---

## Button Behavior by Quarter

| Quarter | Play Quarter | Sim Quarter | Sim Rest of Game | Sim Full Game |
|---------|--------------|-------------|------------------|---------------|
| Pre-game (0) | ✅ Enabled | ✅ Enabled (sim Q1) | ❌ Hidden | ✅ Enabled |
| Q1 Break | ✅ Enabled | ✅ Enabled (sim Q2) | ❌ Hidden | ✅ Enabled |
| Q2 Break | ✅ Enabled | ✅ Enabled (sim Q3) | ✅ Enabled | ❌ Hidden |
| Q3 Break | ✅ Enabled | ✅ Enabled (sim Q4) | ✅ Enabled | ❌ Hidden |
| Q4+ Break | ✅ Enabled | ✅ Disabled | ❌ Hidden | ❌ Hidden |

---

## Code Flow

### Play Quarter Button

**Frontend** (`bootGame.js`):
1. User clicks `.play-button` → calls `handleButtonClick(true)`
2. Removes `.pre-game-container` from DOM
3. Fetches rosters for both teams
4. Calls `startGame({ homeRoster, awayRoster, animate: true })`
5. Loads Phaser game scene for turn-by-turn animation

**Backend** (`api.py` - `/api/simulate-quarter`):
- `full_sim=False` (implicit, not sent)
- Sets `turn_by_turn_mode=True`
- Calls `simulate_quarter()` with animation enabled
- Game state saved to DB after each turn

**Data Persistence**:
- Game saved to `games_collection` after each turn
- Uses `ongoing_games` cache during gameplay
- Lineup screen reads from DB (`source=db`)

**Pre-game container lifecycle:**
- On court load, `court.html` includes `.pre-game-container` in the DOM. `initGame()` either shows it (quarter break) or hides it and auto-starts (timeout resume).
- Play Quarter **removes** the container from the DOM for that page; the buttons are gone until the next full load (e.g. after "Go To Locker Room" and return to court).
- Sim Quarter **hides** the container (`classList.add('hidden')`) then navigates away; the next court load is a new page, so the container is present again and `initGame()` controls visibility.

---

### Sim Quarter Button

**Frontend** (`bootGame.js` - `handleSimQuarter()`):
1. User clicks `.sim-to-fourth-button` → calls `handleSimQuarter()`
2. Calculates `nextQuarter = quarter + 1`
3. Auto-generates lineups for both teams
4. POST to `/api/simulate-quarter` with `full_sim: true`
5. Displays results in popup (`showSimQuarterResults()`) with text scroll
6. Navigates to lineup screen after quarter completes

**Status Text Display**:
- Does NOT show "Simulating Q..." text (uses text scroll popup instead)
- Popup header shows "Simulating Q#..." but main display is scrolling shot results

**Backend** (`api.py` - `/api/simulate-quarter`):
- `full_sim=True` (explicit in request)
- Sets `turn_by_turn_mode=False`
- Calls `simulate_quarter()` which instantly simulates entire quarter
- Returns `lastSummary` with all turns, scores, stats

**Data Persistence**:
- Game saved to `games_collection` once after quarter completes
- `quarter` field in DB is incremented after simulation
- Response includes `quarter` (the NEXT quarter, not the completed one)

---

### Sim Rest of Game / Sim Full Game

**Frontend** (`bootGame.js` - `handleSimFullGame()`):
1. User clicks `.sim-full-game-button` → calls `handleSimFullGame()`
2. Loops from current quarter through Q4
3. For each quarter:
   - Shows "Simulating Q1...", "Simulating Q2...", etc. (stops at Q4, no Q5+)
   - Auto-generates lineups
   - POST to `/api/simulate-quarter` with `full_sim: true`
   - Waits for response
   - Increments to next quarter
4. Stops when `lastSummary.is_final === true`
5. Clears status text
6. Navigates to completion popup

**Status Text Display**:
- Shows "Simulating Q1...", "Simulating Q2...", "Simulating Q3...", "Simulating Q4..." during simulation
- Does NOT show for Sim Quarter button (uses text scroll popup instead)
- When transitioning to computer games (Tournament/Franchise modes), shows "Simulating Computer Games..." instead of "Simulating Q5..."

**Backend**: Same as Sim Quarter (calls `/api/simulate-quarter` multiple times)

**Data Persistence**: Same as Sim Quarter (saves after each quarter)

---

## Quarter Break vs Timeout Resume (SS&S)

**Rule:** Every time the user finishes a quarter (Play Quarter or Sim Quarter), the next time they land on the court should show the **Gameplay Buttons popup** (Play Quarter, Sim Quarter, Sim Rest of Game). The only time the popup is hidden and the game auto-starts is when they are **resuming from a timeout or foul-out** (same quarter).

- **Quarter break:** User completed a quarter → "Go To Locker Room" (Play Quarter) or redirect (Sim Quarter) → lineup → court for next quarter. URL to lineup must have `resume_from_timeout=false` so the next court load does not auto-start. All such navigations use `TimeoutNavigationHelper.buildGameNavigationParams` with `resumeFromTimeout: false` (in `bootGame.js` for Sim Quarter, in `gameScene.js` for both "Go To Locker Room" paths: animation-complete and no-animation/skip).
- **Timeout resume:** User called a timeout mid-quarter → navigates to lineup → clicks back to court. That lineup → court URL is built with `resumeFromTimeout: true` (e.g. in timeout button manager). Court then auto-starts and skips the Gameplay Buttons popup (intended).

**Key files:** `gameScene.js` (animation-complete "Go To Locker Room" block, and no-animation quarter-advance block), `bootGame.js` (`handleSimQuarter` redirect, `initGame()` auto-start when `resume_from_timeout=true`), `FrontEnd/static/js/shared/timeoutNavigationHelper.js`.

---

## Key Parameters

### Request Payload (`/api/simulate-quarter`)

```javascript
{
  game_id: string,
  home_team: string,
  away_team: string,
  quarter: number,           // Quarter to simulate (1-4+)
  full_sim: boolean,         // true = simulate, false = play
  home_lineup: string[],     // Player IDs
  away_lineup: string[],     // Player IDs
  resume_from_timeout: boolean,  // For timeout resumes
  starting_possession: string,   // "home" | "away"
  start_with_inbound: boolean,
  strategy_settings: object,
  user_team_side: string     // "home" | "away"
}
```

### Response (`/api/simulate-quarter`)

```javascript
{
  game_id: string,
  quarter: number,           // NEXT quarter (incremented after sim)
  turns: array,              // All turns from simulated quarter
  box_score: object,
  score: object,
  clock: string,
  time_remaining: number,
  is_final: boolean,
  quarter_complete: boolean
}
```

---

## Data Persistence Flow

### Play Quarter Flow

1. **Initialization**: `/api/init-game` creates the game document in `games_collection`. **Franchise:** seeds **home and away** from each team’s FTD (`team_attributes`, playbook, game plan, plays, scouting) before the first save so the live game matches FCC/master data (see Settings Persistence Guide).
2. **During Gameplay**: Each turn saves to DB via `summarize_game_state()`
3. **Cache**: `ongoing_games` dict keeps GameManager in memory for performance
4. **Lineup Screen**: Always reads from DB (`source=db`) for consistency
5. **Timeout**: Game state saved, resumed from DB on return

### Sim Quarter Flow

1. **Before Sim**: Frontend auto-generates lineups (or uses saved)
2. **Simulation**: Backend simulates entire quarter instantly (`turn_by_turn_mode=False`)
3. **After Sim**: Single save to `games_collection` with all quarter data
4. **Response**: Returns `lastSummary` with all turns and stats
5. **Navigation**: Frontend displays results, then navigates to lineup screen

### State Saving

**When Saved**:
- Play Quarter: After every turn (during gameplay)
- Sim Quarter: Once after quarter completes
- Timeout: Immediately when timeout called
- Quarter Break: When quarter completes

**Where Saved**:
- `games_collection` (standalone document for all game modes)
- `ongoing_games` cache (in-memory, for Play Quarter performance)

---

## Key Differences

| Feature | Play Quarter | Sim Quarter |
|---------|--------------|-------------|
| Animation | ✅ Yes (turn-by-turn) | ❌ No (instant) |
| DB Saves | After every turn | Once after quarter |
| `full_sim` | `false` (implicit) | `true` (explicit) |
| `turn_by_turn_mode` | `true` | `false` |
| Computer Timeouts | ✅ Enabled | ✅ Enabled |
| User Timeouts | ✅ Enabled | ❌ N/A (instant sim) |
| Response Time | Real-time | ~1-2 seconds |

---

## Troubleshooting Reference

### Common Issues

1. **CORS Error on Sim Quarter**
   - Check: Is endpoint crashing? (check Railway logs for Python exceptions)
   - Check: OPTIONS handler working? (`/api/simulate-quarter` OPTIONS should return 204)
   - Fix: Ensure `full_sim` parameter is set correctly

2. **Wrong Quarter Simulated**
   - Check: `nextQuarter = quarter + 1` calculation in `handleSimQuarter()`
   - Check: Backend `quarter` field in request (should be quarter to simulate, not completed)
   - Note: Response `quarter` is NEXT quarter (incremented after sim)

3. **Game State Not Persisting**
   - Check: `games_collection` has game document
   - Check: `ongoing_games` cache state (might be stale)
   - Fix: Lineup screen should use `source=db` parameter

4. **Gameplay Buttons Popup Not Holding After Play Quarter**
   - **Intended:** After Play Quarter or Sim Quarter, the next quarter should show the Gameplay Buttons popup (Play Quarter, Sim Quarter, Sim Rest of Game) and hold until the user chooses.
   - **Cause if broken:** The "Go To Locker Room" URL (when the quarter ends after Play Quarter) must set `resume_from_timeout=false` so the next court load is treated as a quarter break, not a timeout resume. Otherwise `bootGame.js` `initGame()` auto-starts (hides buttons, shows Defense Matchups).
   - **Fix:** All quarter-break navigations (court → lineup after quarter ends) use `TimeoutNavigationHelper.buildGameNavigationParams` with `resumeFromTimeout: false`. In `gameScene.js` this applies to both the animation-complete "Go To Locker Room" path and the no-animation/skip path. Timeout flow is unchanged (lineup → court with `resume_from_timeout=true` is built when returning from timeout).

5. **Button Not Appearing/Enabled**
   - Check: `initGame()` function sets button state based on `quarter`
   - Check: `resumeFromTimeout` flag (hides buttons on timeout resume)
   - Check: Game completion status (disables Sim Quarter after Q4)

6. **Sim Quarter Shows Wrong Quarter**
   - Note: Backend returns `quarter` as NEXT quarter (already incremented)
   - Frontend should use `lastSummary.quarter` directly, not `quarter + 1`

---

## Key Files

**Frontend**:
- `FrontEnd/static/js/phaser/bootGame.js`:
  - `handleButtonClick()` - Play Quarter handler
  - `handleSimQuarter()` - Sim Quarter handler
  - `handleSimFullGame()` - Sim Rest/Full Game handler
  - `initGame()` - Button initialization and state (shows Gameplay Buttons unless `resume_from_timeout=true`)
  - `showSimQuarterResults()` - Display simulation results
- `FrontEnd/static/js/phaser/gameScene.js`:
  - Animation-complete "Go To Locker Room" block - builds lineup URL via `TimeoutNavigationHelper` with `resumeFromTimeout: false` (quarter break)
  - No-animation quarter-advance block - same pattern for skip/instant path
- `FrontEnd/static/js/shared/timeoutNavigationHelper.js` - Single source for building lineup/court URLs with correct `resume_from_timeout`

**Backend**:
- `BackEnd/api/api.py`:
  - `/api/simulate-quarter` - Main endpoint (handles both play and sim)
  - `/api/init-game` - Game initialization
  - `simulate_quarter()` - Core quarter simulation logic

**HTML**:
- `FrontEnd/static/court.html` - Button HTML structure

---

## Critical Code Sections

### Button State Logic (`bootGame.js` – `initGame()` ~2600-2633)

```javascript
// Sim Full Game button
if (currentQuarter >= 4) {
  simFullBtn.style.display = 'none';  // Hide after Q3
} else if (currentQuarter >= 2) {
  simFullBtn.textContent = 'Sim Rest Of Game';  // Q2-Q3
} else {
  simFullBtn.textContent = 'Sim Full Game';  // Q1
}

// Sim Quarter button
if (currentQuarter > 4) {
  sim4Btn.disabled = true;  // Disable after Q4 completes
} else {
  sim4Btn.disabled = false;  // Enable for Q1-Q4
}
```

### Full Sim Flag (`bootGame.js` – `handleSimQuarter()` ~2177-2178, `handleSimFullGame()` ~2447-2448)

```javascript
// Sim Quarter / Sim Full Game set full_sim=true
payload.full_sim = true;
```

### Turn-by-Turn Mode (`api.py` – `simulate_quarter_endpoint` ~3282-3285)

Backend receives the request body as a Pydantic model (`body`); use `body.full_sim`, not `request.full_sim`.

```python
# full_sim parameter determines animation mode
turn_by_turn_mode = not body.full_sim
# true = Play Quarter (animation), false = Sim Quarter (instant)
```

---

## Data Flow Summary

1. **User Clicks Button** → Frontend handler called
2. **Frontend Prepares** → Fetches rosters, generates lineups, builds payload
3. **POST Request** → `/api/simulate-quarter` with `full_sim` flag
4. **Backend Simulation** → `simulate_quarter()` runs with appropriate mode
5. **State Saved** → Game document saved to `games_collection`
6. **Response Returned** → Frontend receives `lastSummary` with results
7. **UI Updated** → Popup shown (Sim Quarter) or game started (Play Quarter)
8. **Navigation** → Lineup screen (Sim Quarter) or next turn (Play Quarter)

**Play Quarter navigation (quarter break):** When the quarter ends after Play Quarter, the user sees "Go To Locker Room". That link is built with `resume_from_timeout=false` (via `TimeoutNavigationHelper` in `gameScene.js`). They go to lineup → game-plan → court; the next court load therefore gets `resume_from_timeout=false`, so `initGame()` shows the Gameplay Buttons popup again instead of auto-starting.

