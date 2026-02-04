# Defense Matchups System

> **Last Updated:** February 2025  
> **Purpose:** Custom man-to-man defensive matchups for the **user team** when the user is on defense; computer team matchups are separate and default (position-on-position) for now.

---

## Overview

The Defense Matchups System allows users to set custom man-to-man defensive assignments for **their team only** (e.g., user PG guards computer SG) via a drag-and-drop popup. When the **user** is on defense, the engine uses the user's matchups; when the **computer** is on defense, the engine uses a separate matchup dict (`man_defense_matchups_computer`), which is position-on-position by default. Future logic may set computer matchups. Both dicts reset to defaults at the start of each break (timeout, quarter break, foul out).

---

## When Popup Appears

The Defense Matchups popup appears **after** the Gameplay Buttons popup (Play Quarter, Sim Quarter, Sim Full Game) and **only** when:
- User presses **"Play Quarter"** (not for "Sim Quarter" or "Sim Full Game")
- At the start of Q1
- After quarter breaks
- After timeouts
- After a player fouls out

---

## User Interface

### Layout
- **Title:** "DEFENSE MATCHUPS"
- **Two columns:** Left = User team lineup, Right = Computer team lineup
- **Five rows per side:** PG, SG, SF, PF, C
- **Default assignments:** Position-on-position (PG→PG, SG→SG, etc.)

### Row Content
Each row includes:
- **Position square:** Colored fill (user team = position color, computer team = guarding user position color)
- **Player headshot**
- **Player name:** Formatted as "F. Lastname"
- **Stat strip:** 
  - User team: ID, OD, AG, ST, ND, IQ, NG, DEF%
  - Computer team: SC, SH, AG, ST, ND, IQ, NG, PTS

### Team Headers
- **Background:** Team's primary color
- **Text and border:** Team's secondary color

---

## Drag-and-Drop Functionality

### Interaction Model
- **Drag within user team column only:** User drags and drops players within their own team's column
- **Position swap:** When user drags PG to SG slot, PG and SG swap positions
- **Matchup calculation:** After swap, user position in slot X guards computer position X
  - Example: If user PG is in SG slot (index 1), user PG guards computer SG

### Implementation Pattern
Uses **data + re-render pattern** (like Lineup Screen):
1. Track user team order in data structure (array of positions)
2. On swap, update data structure (swap positions in array)
3. Re-render user team rows based on new order
4. Recalculate matchups from new order
5. Update visual display (computer team colors)

### Visual Feedback
- **Dragging:** Row opacity set to 0.5
- **Drop target:** Highlighted with white overlay
- **Color matching:** Computer team row borders and position squares match the color of the user defender assigned to that player

---

## Data Flow

### Frontend (Local Memory)
- **During drag-and-drop:** Updates stored in popup's `dataset.userTeamOrder` (local memory only)
- **On Submit:** Sends matchups to backend via `/api/save-man-defense-matchups`

### Backend Storage
- **Two keys (SS&S):**
  - **`man_defense_matchups`** — Used when the **user team** is on defense. Set by the popup; persisted to DB.
  - **`man_defense_matchups_computer`** — Used when the **computer team** is on defense. Not set by the popup; default position-on-position for now. Future logic may set this. Persisted to DB; on load from old saves, defaults if missing.
- **In-memory:** Both keys live in `game_state`.
- **Database:** Both keys saved via `summarize_game_state()` in `BackEnd/utils/shared.py`.
- **Structure:** Each dict maps defensive position → offensive position (same format for both):
  ```python
  {
      "PG": "PG",  # Defensive PG guards offensive PG
      "SG": "SG",
      "SF": "SF",
      "PF": "PF",
      "C": "C"
  }
  ```

### Reset Logic
**Both** user and computer matchup dicts reset to defaults (position-on-position) at:
- Start of each timeout (`call_timeout()`)
- Start of each quarter break (`simulate_macro_turn()` when foul out occurs)
- Quarter break in API (`simulate_quarter_endpoint` when applying break state)

---

## Backend Integration

### Key Files
- **`BackEnd/utils/man_defense_matchups.py`:** Utility functions for matchups
  - `get_default_matchups()`: Returns default position-on-position matchups
  - `reset_matchups_to_defaults(game_state)`: Resets **both** user and computer matchup dicts in game_state
  - `validate_man_defense_matchups(matchups)`: Validates 1-to-1 mapping
  - `get_matchups_for_defending_team(game_state, defending_team_is_user)`: Returns the matchup dict for the given defending team (user or computer).
  - `get_defender_position_for_man_defense(offensive_pos, game_state, fallback_to_default, defending_team_is_user)`: Returns defensive position that should guard offensive position. **`defending_team_is_user`** selects which dict to use (no new variable; derived from `game.defense_team.is_user_team` at call sites).

### API Endpoints
- **`GET /api/game/{game_id}/lineup-for-matchups`:** Fetches lineup data and **user** matchups only (for popup). Returns `current_matchups` from `man_defense_matchups`.
- **`POST /api/save-man-defense-matchups`:** Saves **user** matchups only to `game_state["man_defense_matchups"]` and database.

### Usage in Game Logic
At each call site, the engine uses the matchup dict for **whoever is on defense** (derived from existing `game.defense_team` / `is_user_team`; no new variable):
1. **`BackEnd/engine/phase_resolution.py`:** Steal attempts, turnovers, HCO resolution — passes `defending_team_is_user=game.defense_team.is_user_team` into `get_defender_position_for_man_defense`.
2. **`BackEnd/models/turn_manager.py`:** Shooter assignment for man defense — same.
3. **`BackEnd/models/animator.py`:** Defensive sprite positioning — uses `get_matchups_for_defending_team(game_state, defense_team.is_user_team)` to get the correct dict for defender→offensive position.

---

## Persistence

### Game-Scoped
- Both `man_defense_matchups` and `man_defense_matchups_computer` are saved to the specific game document (not the master franchise/tournament document).
- Persist across game saves/loads via `summarize_game_state()` in `BackEnd/utils/shared.py`.
- On load from DB (and in `apply_timeout_resume_state_to_gm`), both keys are restored; if `man_defense_matchups_computer` is missing (old saves), it is set to default position-on-position.

### "Don't Show Again" Option
- Checkbox: "Don't show this pop up again this game"
- If checked, popup is suppressed for the remainder of the current game
- Default matchups (position-on-position) are used for man defense for the rest of the game
- Flag resets at start of Q1

---

## Technical Details

### Frontend Files
- **`FrontEnd/static/js/phaser/utils/defenseMatchupsPopup.js`:** Main popup implementation
  - `showDefenseMatchupsPopup(gameId, scene)`: Main entry point
  - `createPopupElement()`: Creates popup DOM structure
  - `initializeDragAndDrop()`: Sets up drag-and-drop with data + re-render pattern
  - `renderUserTeamRows()`: Re-renders user team rows based on order
  - `calculateMatchupsFromOrder()`: Calculates matchups from user team order

### Position Colors
- **PG:** Pink (`#ff69b4`)
- **SG:** Orange (`#ff9800`)
- **SF:** Yellow (`#ffd700`)
- **PF:** Light Blue (`#87ceeb`)
- **C:** Purple (`#9370db`)

---

## Acceptance Criteria

✅ Popup appears at specified moments (Q1 start, quarter breaks, timeouts, foul outs)  
✅ Popup only appears after "Play Quarter" is pressed (not for "Sim Quarter" or "Sim Full Game")  
✅ Default matchups are position-on-position  
✅ Drag-and-drop within user team column swaps positions  
✅ Matchups recalculate automatically after each swap  
✅ Computer team colors reflect which user position is guarding them  
✅ Position squares show correct colors for both teams  
✅ "Submit Defense Matchups" saves to backend and database  
✅ "Don't show again this game" suppresses popup for remainder of game  
✅ Matchups reset to defaults at start of each break (both user and computer dicts)  
✅ Matchups persist across game saves/loads  
✅ User custom matchups apply only when user team is on defense; computer uses its own dict (default position-on-position)  

