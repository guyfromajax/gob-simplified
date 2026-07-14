# Defense Matchups System

> **Last Updated:** July 2026  
> **Purpose:** Custom man-to-man defensive matchups for the **user team** when the user is on defense; computer team matchups are separate and default (position-on-position) for now.

**Related:** [Pre-Game Experience System](./Pre_Game_XP_System.md) (franchise Q1 cinematic)

---

## Overview

The Defense Matchups System allows users to set custom man-to-man defensive assignments for **their team only** (e.g., user PG guards computer SG) via a drag-and-drop UI. When the **user** is on defense, the engine uses the user's matchups; when the **computer** is on defense, the engine uses a separate matchup dict (`man_defense_matchups_computer`), which is position-on-position by default. Future logic may set computer matchups. Both dicts reset to defaults at the start of each break (timeout, quarter break, foul out).

**UI surfaces:**

1. **Franchise Q1** — full-screen [Pre-Game Experience](./Pre_Game_XP_System.md) (reveal → matchups → tip-off)
2. **All other Play Quarter gates** (and single-game Q1) — restyled **Strategic Modal** (home left / away right, card DNA shared with pre-game)

---

## When Popup Appears

The Defense Matchups UI appears **after** the Gameplay Buttons popup (Play Quarter, Sim Quarter, Sim Full Game) and **only** when:
- User presses **"Play Quarter"** (not for "Sim Quarter" or "Sim Full Game")
- At the start of Q1
- After quarter breaks
- After timeouts
- After a player fouls out

Tutorial mode (`?mode=tutorial`) skips the UI entirely.

---

## User Interface

### Layout (current)
- **Columns:** Home team **left**, away team **right** (all surfaces)
- **Draggable:** Only the **user** team column
- **Five slots:** Opponent positions PG → C; user defender in slot *i* guards that opponent position
- **In-game headers:** Team names centered with **team-color underline** (no tinted pill fills); no modal title
- **Submit:** Content-sized centered button above the Don't-show checkbox

### Card Content
Each tile:
- Headshot (`getPlayerImageUrl(..., { size: 'card' })`)
- Name (`#jersey`) · HT · WT (no class year)
- Stat strip: **franchise Q1 full-screen pre-game** = season PPG/RPG/APG/DEF%; **in-game modal** = game PTS/REB/AST/DEF%
- RT: fixed outer gutter on all surfaces (Attribute Bar Scale; tabular-nums; sized for 3 digits) — no headshot badge
---

## Drag-and-Drop Functionality

### Interaction Model
- Drag within the **user** column only; drop swaps two slots
- After swap, user position in slot X guards opponent position X
- Example: If user PG is in the SG slot (index 1), user PG guards opponent SG

### Implementation Pattern
Uses **data + re-render** (`userOrder` array of user positions → `matchupsFromUserOrder`):
1. Track user team order (array of positions)
2. On swap, update order and re-render
3. On submit, POST `{ userPos: guardedOppPos }`

### Visual Feedback
- Dragging opacity ~0.45; drop target inset highlight
- Favorability borders / center arrow from RT comparison (team primary colors)

---

## Data Flow

### Frontend (Local Memory)
- During drag-and-drop: order lives in JS memory for the open UI
- On Submit: `POST /api/save-man-defense-matchups`

### Backend Storage
- **Two keys (SS&S):**
  - **`man_defense_matchups`** — Used when the **user team** is on defense. Set by the UI; persisted to DB.
  - **`man_defense_matchups_computer`** — Used when the **computer team** is on defense. Not set by the UI; default position-on-position for now.
- **In-memory:** Both keys live in `game_state`.
- **Database:** Both keys saved via `summarize_game_state()` in `BackEnd/utils/shared.py`.
- **Structure:**
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
**Both** user and computer matchup dicts reset to defaults via `reset_matchups_to_defaults()` at:
- Every timeout — unified timeout-creation in `BackEnd/models/game_manager.py`
- Quarter breaks — `simulate_quarter_endpoint` when advancing the quarter

---

## Backend Integration

### Key Files
- **`BackEnd/utils/man_defense_matchups.py`:** Defaults, reset, validate, lookup helpers
- **`GET /api/game/{game_id}/lineup-for-matchups`:** Lineups + matchups + jersey/RT/game+season stats (see Pre-Game XP doc)
- **`POST /api/save-man-defense-matchups`:** Saves user matchups only

### Usage in Game Logic
Engine uses the matchup dict for **whoever is on defense** (`defending_team_is_user`):
1. `BackEnd/engine/phase_resolution.py`
2. `BackEnd/models/turn_manager.py`
3. `BackEnd/models/shot_manager.py`
4. `BackEnd/models/animator.py`

---

## Persistence

### Game-Scoped
- Both matchup dicts saved on the game document; restored on load / timeout resume

### "Don't Show Again" Option
- Checkbox on pre-game matchups step and in-game modal
- `sessionStorage` key: `defenseMatchupsDontShow_<gameId>`
- Resets via `resetDontShowAgainFlag()` only for a **truly new game** (new `game_id` at Q1)

### Other Suppression / SFX
- **FTE v2 tutorial:** UI skipped
- **In-game modal announce:** `defense-sammy.mp3` first open per game (`defenseMatchupsAnnouncePlayed_<gameId>`)
- **UI clicks:** drop reorder → `click-tiny.wav`; Submit → `confirm-1-lowervol.wav`; Don't show checkbox → `click-tiny.wav` (see Sound Design System)
- **Franchise Q1:** pregame bed + reveal click-beeps (see Pre-Game XP); not used for mid-game modal
- Gameplay BG music remains deferred until the matchups await completes (Q1 tip music still follows tip-winner path)

---

## Technical Details

### Frontend Files
- `FrontEnd/static/js/phaser/utils/defenseMatchupsPopup.js` — entry + in-game modal
- `FrontEnd/static/js/phaser/utils/preGameExperience.js` — franchise Q1 cinematic
- `FrontEnd/static/js/phaser/utils/matchupsUiShared.js` — shared tiles / order / save

### Position Colors (face-off / legacy accents)
- **PG:** `#4A90D9` · **SG:** `#7B5EA7` · **SF:** `#3A8C4A` · **PF:** `#C0392B` · **C:** `#D4A017`

---

## Acceptance Criteria

✅ UI appears at specified moments after Play Quarter only  
✅ Franchise Q1 uses pre-game cinematic; other gates use Strategic Modal  
✅ Home left / away right; only user column drags  
✅ Default matchups are position-on-position  
✅ Submit saves via `/api/save-man-defense-matchups`  
✅ Don't show again suppresses for remainder of game  
✅ Matchups reset at each break; persist across saves/loads  
✅ User custom matchups apply only when user is on defense  
