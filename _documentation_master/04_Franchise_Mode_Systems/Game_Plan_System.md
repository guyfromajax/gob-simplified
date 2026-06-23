# Game Plan System (**verified 2026-06-23**)

> Verified vs code: `FrontEnd/static/game-plan.js`, `FrontEnd/static/game-plan.html`, `BackEnd/api/gameplan_routes.py` (`get_default_settings`, `validate_settings`, `GET/PUT /api/gameplan`), `BackEnd/utils/team_settings_manager.py` (`save_team_settings`). Persistence policy matches `../01_Data_Persistence/Settings_Persistence_Guide.md` (April 2026 two-stage model).

## Overview

The Game Plan screen (`game-plan.html`) lets the **user team** configure ten strategic sliders (`strategy_settings`) that influence sim behavior. Settings are database-backed, mode-scoped, and never stored in `localStorage` or URL params.

**Active product mode:** Franchise. Single Game and Tournament paths still exist in code but are sunset — see `Sunset_Modes.md`.

**Source of truth (implementation):**

- `FrontEnd/static/game-plan.html`
- `FrontEnd/static/game-plan.js`
- `FrontEnd/static/game-plan.css`
- `BackEnd/api/gameplan_routes.py`
- `BackEnd/utils/team_settings_manager.py`

**Related docs (do not duplicate here):**

- Persistence architecture → `../01_Data_Persistence/Settings_Persistence_Guide.md`, `../01_Data_Persistence/Data_Persistence_System.md` ("Game Plan & Playbook Settings Persistence")
- FCC summary tab → `FCC.md` ("Game Plan Tab")
- How sliders affect play selection → `../06_Gameplay_Systems/Sim_Playcalling_System.md`
- CPU opponent defaults → `../06_Gameplay_Systems/Computer_Team_Game_Init_System.md`
- Playbook percentages (separate screen) → `../08_Playbooks_Systems/Playbooks_Page.md`

---

## User Flows

### Franchise Command Center (primary)

1. User opens FCC → **Game Plan** tab (read-only summary) or clicks **Edit Game Plan**.
2. Navigates to `game-plan.html` with `mode=franchise`, `franchise_id`, `team_id`, `from=command_center`, and optional `return_url`.
3. User adjusts sliders → **Save Game Plan** → settings persist to FTD (pregame) or active game doc (when `game_id` present) → toast → return to FCC.

FCC loads summary via `GET /api/gameplan?mode=franchise&franchise_id=...&team_id=...` (no `game_id` → FTD master read).

### Set Lineup → Game Plan (pregame or timeout)

1. User on `set-lineup.html` clicks **Game Plan** (`#gameplan-optional`).
2. If no `game_id` yet (and not a timeout resume), set-lineup may call `POST /api/init-game` first, then navigate with full lineup + context params and `from=lineup`.
3. User adjusts sliders → **Save Game Plan** → persist → toast → navigate back to set-lineup.
4. **Play Game** lives on set-lineup, not on the Game Plan page.

### Timeout / in-game re-entry

When `game_id` and `resume_from_timeout=true` are present, franchise/tournament saves and loads use the **active game document** snapshot (not FTD / tournament master). See persistence section below.

### Tutorial (FTE v2)

- Frontend passes `mode=tutorial`; backend aliases `tutorial → single`.
- Page is **read-only**: sliders disabled, Save hidden, subhead shown.
- Settings load from the throwaway tutorial game doc like single mode.

---

## Page UI — Ten Sliders

All sliders are `input[type=range]` with `min=0`, `max=4`, `step=1` (five discrete positions). Endpoint labels appear under each slider in HTML; intermediate values (1 and 3) use blended semantics (see FCC `mapGamePlanValue()` for full text).

| UI label | `strategy_settings` key | Endpoint semantics (0 / 2 / 4) |
|----------|---------------------------|--------------------------------|
| Offense | `offense` | 100% Motion / 50-50 / 100% Set Plays |
| Inside Offense | `inside` | Never / Normal / Most |
| Attack Offense | `attack` | Never / Normal / Most |
| Outside Offense | `outside` | Never / Normal / Most |
| Fast Break | `fast_breaks` | 100% Half-Court Sets / 50-50 / 100% Fast Breaks |
| Defense | `defense` | 100% Man / 50-50 / 100% Zone |
| Aggression | `aggression` | Passive / Normal / Aggressive |
| Half-Court Trap | `hc_trap` | Never / Normal / Most |
| Full-Court Press | `fc_press` | Never / Normal / Most |
| Offensive Rebounding | `rebounding` | 100% Crash the Boards / 50-50 / 100% Get Back on D |

Frontend mapping: `strategySliders` in `game-plan.js` (keys → slider element IDs).

**Defaults:** Missing keys normalize to **2** on load (`get_default_settings()` backend; frontend uses `?? 2`).

**Legacy key migration (GET only):** Backend maps old keys `half_court_trap` → `hc_trap` and `full_court_press` → `fc_press` before returning.

---

## Validation

### Offense-not-all-zero rule

At least one of **`offense`**, **`inside`**, **`attack`**, or **`outside`** must be **> 0**.

- Frontend: `validateOffenseSettings()` blocks save; modal message: *"At least one Offense setting must be above 'Never'. Please increase any Offense slider."*
- Backend: `validate_settings()` raises HTTP 400 with the same message.

`fast_breaks` is **not** part of this check.

### Range rule

Every submitted value must be an integer **0–4**. Backend returns 400: *"Strategy setting '{key}' must be an integer between 0 and 4"*.

### Defense / general sliders

No additional restrictions.

---

## Buttons and Navigation

Navigation source is the `from` URL param (default `lineup`):

| `from` value | UI shown | Save behavior | After successful save |
|--------------|----------|---------------|------------------------|
| `lineup` (default) | **Back To Lineup**, **Save Game Plan** | PUT `/api/gameplan` | Toast → navigate to `set-lineup.html` |
| `command_center`, `franchise-command-center`, `tournament-command-center` | **Back to Locker Room** (page header link), **Save Game Plan** | PUT `/api/gameplan` | Toast → navigate to FCC / TCC |

**Important (current behavior):**

- **Only `Save Game Plan` writes to the database.** Back / locker-room navigation is nav-only (no quiet auto-save). Unsaved edits trigger a warning modal with **Save Game Plan** or **Leave Without Saving** (suppressible via `sessionStorage.gameplan_suppress_warning`).
- There is **no Play Game button** on this page and **no Reset button** wired in HTML (`resetSettings()` exists in JS but is unused).
- `return_url` is set when FCC links out but **`game-plan.js` does not read it**; return navigation uses mode-specific hardcoded targets.

---

## Required URL Context

| Param | Required when | Purpose |
|-------|---------------|---------|
| `mode` | Always | `franchise` (active), or legacy `tournament` / `single` / `tutorial` |
| `team_id` | Franchise / tournament from command center | User team ObjectId (preferred). Legacy `user_team_id` still accepted. |
| `home`, `away`, `home_id`, `away_id`, `my_team` | From set-lineup | Matchup + user side; team id resolved from `my_team` when not from command center |
| `franchise_id` | `mode=franchise` | Franchise instance |
| `tournament_id` | `mode=tournament` | Tournament instance |
| `game_id` | Single/tutorial always; franchise/tournament when game exists | Determines game-doc vs master persistence; required for single GET |
| `quarter`, `resume_from_timeout`, lineup `{side}_pg`… | Timeout / multi-quarter flows | Passed through via `TimeoutNavigationHelper` |
| `from` | Optional | Controls button layout and post-save destination |

**`game_id` guard:** Page errors if `game_id` is required but missing (`single` mode, `quarter > 1`, or timeout resume).

---

## Data Model

Game Plan persists a single object:

```javascript
strategy_settings = {
  "offense": 0-4,
  "inside": 0-4,
  "attack": 0-4,
  "outside": 0-4,
  "fast_breaks": 0-4,
  "defense": 0-4,
  "aggression": 0-4,
  "hc_trap": 0-4,
  "fc_press": 0-4,
  "rebounding": 0-4
}
```

**Not on this screen:**

- **`tempo`** — per-game sim setting (randomized at game init via `TeamManager.init_tempo_random()` / `GameManager`). FTD season init currently seeds `tempo: 2` in `franchise_manager.py`, but the Game Plan UI does not expose or save it; a save replaces the stored blob with the ten UI keys only. Gameplay re-injects `tempo` on `GameManager` when missing. Backlog: add tempo to Game Plan UI (`projects/bugs.md` #113).
- **`playbook_settings`** — configured on Playbooks / Playbook Report, not here.

**Legacy note:** Old `playcall_settings` (Base/Freelance/Inside/Attack/Outside/Set) is **not** used by current API or UI. GET/PUT responses no longer include it.

---

## Persistence

**Principle:** Database is source of truth. Optional `gameStore` cache is performance-only (check cache → fallback GET → invalidate on save).

### Storage locations

| Context | Where `strategy_settings` lives |
|---------|----------------------------------|
| Franchise pregame / FCC (no active game doc write path) | `franchise_team_data` (FTD), keyed by `(franchise_id, user_team_object_id)` — request `team_id` ignored on master save |
| Franchise with `game_id` (game exists) | `games` doc → `teams.{canonical_team_id}.strategy_settings` |
| Tournament pregame | Tournament document → `teams.{user_team_object_id}.strategy_settings` |
| Tournament with `game_id` | `games` doc → `teams.{canonical_team_id}.strategy_settings` |
| Single / tutorial | `games` doc only |

**Two-stage rule (franchise / tournament):**

- Pregame / FCC edits → master store (FTD or tournament doc).
- Game init snapshots master settings into the game doc.
- In-game / timeout edits with `game_id` → game doc only (do not overwrite master).
- GET may merge from master into the HTTP response when the game snapshot lacks meaningful strategy data (read merge only; does not write master).

**Save path:** `PUT /api/gameplan` → `validate_settings()` → `save_team_settings(settings_type="strategy_settings", apply_to_gamemanager=True)`.

**Load path:** `GET /api/gameplan` → normalize keys → merge with defaults → return `{ strategy_settings }`. Single mode may read from `ongoing_games` GameManager cache unless `source=db`.

Full persistence flows, pitfalls, and timeout behavior: `../01_Data_Persistence/Settings_Persistence_Guide.md`.

---

## API

### `GET /api/gameplan`

**Query params:**

- `mode` (required): `franchise`, `tournament`, `single`, or `tutorial` (aliased to `single`)
- `team_id` (required)
- `franchise_id` — required for franchise
- `tournament_id` — required for tournament
- `game_id` — required for single/tutorial; optional for franchise/tournament (selects game-doc read path)
- `source` — optional; `source=db` skips GameManager cache (single mode)

**Response:**

```json
{
  "strategy_settings": {
    "offense": 2,
    "inside": 2,
    "attack": 2,
    "outside": 2,
    "fast_breaks": 2,
    "defense": 2,
    "aggression": 2,
    "hc_trap": 2,
    "fc_press": 2,
    "rebounding": 2
  }
}
```

### `PUT /api/gameplan`

**Body:**

```json
{
  "mode": "franchise",
  "team_id": "<user team ObjectId or resolvable identifier>",
  "franchise_id": "<when franchise>",
  "tournament_id": "<when tournament>",
  "game_id": "<when saving to game doc>",
  "strategy_settings": { "...": 0-4 }
}
```

**Success:** `{ "success": true, "message": "Game plan saved successfully" }`

**Validation error:** HTTP 400 with offense-not-all-zero or range message.

---

## Initialization and Opponents

### User team (franchise)

- Season init creates FTD rows for **all 128 teams** with default `strategy_settings` (all **2**, plus `tempo: 2` at init).
- Only the **user team** is edited through the Game Plan screen / API master-save path (authoritative `user_team_object_id` from franchise doc).

### CPU / opponent teams

- Do not use the Game Plan UI.
- At game time, computer teams derive settings via `TeamManager` (`_compute_strategic_strategy_settings()` or weighted random defaults) when not the user team. See `Computer_Team_Game_Init_System.md`.

---

## Gameplay Effects (summary)

| Setting | Primary runtime use |
|---------|---------------------|
| `offense`, `inside`, `attack`, `outside` | Motion vs set-play choice and set-play focus (`turn_manager.py` / Sim Playcalling) |
| `defense` | Man vs zone tendency; specific scheme from `playbook_settings` when zone/man chosen |
| `fast_breaks` | Fast-break opportunity rate (`Fast_Break_System.md`) |
| `fc_press`, `hc_trap` | Press / half-court trap frequency (`FCP_System.md`, HCT systems) |
| `aggression` | Defensive intensity; block attempts, etc. (`Block_System.md`) |
| `rebounding` | Offensive rebound crash vs get-back (`shot_manager.py`) |

Playbook **which play** is chosen still comes from `playbook_settings` percentages and Playcall Center order.

---

## Migration note

This document supersedes `docs/GMO_&_GP_Supporting_Systems/game_plan_screen.md` as the canonical Game Plan reference in `_documentation_master`.

**Update To Game Plan Screen**
Step 1: add a new field to every FTD strategy_settings titled "alterations". We'll also need to write and run a script to add this new field to all FTD documents in the gob and gob-staging databases. Set all defaults to 2. 

Step 2: Update the gameplan.html screen
1. Move the Fast Breaks slider to the right column, sitting below the Full-Court Press slider and above the Offensive Rebounding Slider
2. In the left column, place a slider under the Outside Offense slider, place a new slider with teh following info
    - Title: "Offense Tempo"
    - Slider copy: left toggle: "Slow", middle toggle: "Normal", right toggle: "Fast"
    - Wiring: wire it to set the user team's "tempo" in the strategy_settings of the team's FTD document
3. Place a slider below the "Offense Tempo" slider with following info:
    - Title: "Play Alteration"
    - Slider copy: left toggle: "Least", middle toggle: "Normal", right toggle: "Most"
    - Wiring: wire it to set the team's "alteration" in the strategy_settings field

Step 3: update the Game_Plan_System.md doc with this new and current info.