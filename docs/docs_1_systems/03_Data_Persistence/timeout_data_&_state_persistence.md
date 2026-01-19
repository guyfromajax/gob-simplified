# Timeout Data & State Persistence

**Purpose:** Documents how data and state values are maintained throughout the timeout/quarter break flow.

---

## Flow Overview

**Timeout Called / Quarter Break / Player Foul Out** → **Situation Popup** → **Lineup Screen** → **Return to Court**

---

## Quarter Breaks vs. Timeouts

**Key Difference:**
- **Quarter Breaks**: Natural game pauses between quarters. `resume_from_timeout=false` (or missing). Pre-game popup appears.
- **Timeouts**: User/computer-initiated pauses. `resume_from_timeout=true`. Pre-game popup hidden (auto-resume).
- **Foul Outs**: Automatic timeouts. `resume_from_timeout=true`. Pre-game popup hidden (auto-resume).

**State Management:**
- Quarter breaks clear timeout state when quarter completes (ensures clean quarter start).
- Timeouts preserve timeout state for resume (maintains possession and play type).
- Both save game state identically (scores, stats, energy, etc.).

---

## 1. Timeout Called / Quarter Break / Player Foul Out

**What Happens:**

**Timeouts (User/Computer/Foul Out):**
- Backend creates `TIMEOUT` turn via `setup_timeout_turn()`
- Game state saved to database via `handle_timeout_save_and_response()`
- Sets `resume_from_timeout=true` in URL

**Quarter Breaks:**
- Quarter completes naturally (time reaches 0)
- Game state saved to database via `summarize_game_state()` (same as timeouts)
- Clears timeout state (if any exists from previous timeout)
- Sets `resume_from_timeout=false` (or omits param) in URL

**Data Saved to Database (`games` collection):**

**Critical State (for resume):**
- `timeout_next_play_type`: `"SIDE_INBOUND"` (or `"FREE_THROW"` if applicable) - **Only for timeouts**
- `timeout_offense_team_id`: Team ID that had possession when timeout called - **Only for timeouts**
- `clock`: Current game clock (e.g., `"4:23"`)
- `time_remaining`: Seconds remaining (e.g., `263`)
- `quarter`: Current quarter (1-4) - **Incremented on quarter break**

**Game State:**
- `score`: `{"Team Name": score}` for both teams
- `teams.{team_id}.timeouts`: Timeout count for each team (reduced by 1 for calling team)
- `teams.{team_id}.team_fouls`: Team foul count for each team
- `teams.{team_id}.box_score`: Cumulative box score stats
- `teams.{team_id}.totals`: Team-level aggregated stats

**Player State:**
- `players[]`: Array of all players (lineup + bench)
  - `attributes.NG`: Real-time energy values (0.0-1.0)
  - `attributes.EM`: Emotion values
  - `attributes.MO`: Momentum values
  - `stats`: Game stats (PTS, REB, AST, etc.)

**Response Data:**
- Returns full game state in API response (for frontend popup display)

---

## 2. Situation Popup

**What Happens:**
- Frontend displays popup (timeout called, quarter end, or player foul out)
- Popup shows current game state from API response

**Data Used:**
- `turn.text`: Message to display
- `clock`: Display current game clock
- `home_score` / `away_score`: Display current scores
- `home_team_timeouts` / `away_team_timeouts`: Display timeout counts
- Navigation params built with `TimeoutNavigationHelper`

**State Persistence:**
- No additional saves (uses data from Step 1)
- URL params set:
  - **Timeouts/Foul Outs**: `resume_from_timeout=true`, `game_id`, `quarter`, `clock`, etc.
  - **Quarter Breaks**: `resume_from_timeout=false` (or omitted), `game_id`, `quarter`, `clock`, etc.

---

## 3. Lineup Screen Experience

**What Happens:**
- User navigates to lineup screen
- User can visit gameplay, playbooks, and box score screens
- User makes lineup/game plan changes (optional)

**Data Loading (`/api/game/{game_id}?source=db`):**

**Always Reads from Database (fresh data):**
- `score`: Team scores displayed in header
- `players[]`: Player stats (PTS, REB, AST, Def %, Emotion, Momentum, Fouls)
- `players[].attributes.NG`: Energy levels for all players
- `quarter`: Current quarter
- `clock` / `time_remaining`: Time remaining

**User Actions (optional changes):**
- Lineup changes: Saved to URL params (not database until return)
- Game plan changes: Saved to database immediately (`/api/gameplan`)
- Playbook changes: Saved to database immediately (`/api/gameplan`)

**State Persistence:**
- Database remains single source of truth for game state
- Lineup changes stored in URL params (applied on return)
- Game plan/playbook changes saved immediately to database

---

## 4. Return to Court (court.html)

**What Happens:**
- User navigates back to court.html
- Backend loads game from database
- Backend restores timeout state via `apply_timeout_resume_state_to_gm()`

**Data Restored from Database:**

**Critical State (overwrites in-memory state):**
- `timeout_next_play_type`: Used to determine next turn type
- `timeout_offense_team_id`: Used to set `gm.offense_team` and `gm.defense_team`
- `clock` / `time_remaining`: Restored to exact values at timeout
- `score`: Team scores restored from saved document
- `quarter`: Current quarter

**Team State:**
- `teams.{team_id}.timeouts`: Restored from unified teams structure (with fallback to old structure)
- `teams.{team_id}.team_fouls`: Restored from saved document

**Player State:**
- `players[].attributes.NG`: Energy values restored for all players (lineup + bench)
- `players[].stats`: Game stats restored
- `players[].attributes.EM` / `players[].attributes.MO`: Emotion/Momentum restored

**Possession Restoration:**
- `gm.offense_team` set based on `timeout_offense_team_id`
- `gm.defense_team` set to opposite team
- Ensures correct possession after timeout (e.g., user calls timeout during BIP, computer retains possession)

**Next Turn Creation:**
- Backend creates appropriate turn (`SIDE_INBOUND`, `BASELINE_INBOUND`, or `FREE_THROW`)
- Uses `timeout_next_play_type` and restored `offense_team`
- Game continues from exact point where timeout was called

---

## Key Principles

1. **Database is Single Source of Truth**: All critical game state saved to database at timeout/quarter break
2. **Unified Structure**: Uses `teams.{team_id}` structure (with backward compatibility fallback)
3. **Complete Restoration**: All game state restored when resuming (scores, clock, timeouts, fouls, player stats)
4. **Possession Preservation**: `timeout_offense_team_id` ensures correct team has possession after timeout (not applicable for quarter breaks)
5. **Fresh Reads**: Lineup screen always reads from database (`source=db`) to avoid stale data
6. **Quarter Break State Cleanup**: Quarter breaks explicitly clear timeout state to ensure clean quarter starts
7. **Popup Logic**: Pre-game popup shows for quarter breaks (`resume_from_timeout=false`), hidden for timeouts/foul outs (`resume_from_timeout=true`)

---

## Data Structure Reference

**Saved in `games` collection:**
```javascript
{
  "game_id": "...",
  "timeout_next_play_type": "SIDE_INBOUND",
  "timeout_offense_team_id": "TEAM_ID",
  "quarter": 1,
  "clock": "4:23",
  "time_remaining": 263,
  "score": {
    "Team Name 1": 15,
    "Team Name 2": 12
  },
  "teams": {
    "home_team_id": {
      "timeouts": 3,
      "team_fouls": 4,
      "score": 15,
      "box_score": {...},
      "totals": {...}
    },
    "away_team_id": {
      "timeouts": 4,
      "team_fouls": 2,
      "score": 12,
      "box_score": {...},
      "totals": {...}
    }
  },
  "players": [
    {
      "playerId": "...",
      "name": "...",
      "team": "home",
      "attributes": {
        "NG": 0.85,
        "EM": 75,
        "MO": 5
      },
      "stats": {
        "PTS": 8,
        "REB": 5,
        "AST": 2,
        ...
      }
    },
    ...
  ]
}
```

