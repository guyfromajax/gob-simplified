# Settings Persistence Guide

**Purpose:** Clear, concise guide to how playbook and game plan settings persist across all game modes and gameplay scenarios.

**Last Updated:** April 2026

> **Mode note:** Tournament and Single Game are sunset modes (`../01_Game_Mode_Systems/Sunset_Modes.md`); their settings paths below remain documented while the code stays in the repo. Franchise is the active mode.

---

## Core Principle

**Database-backed persistence is the source of truth. Settings flow: Save → DB → Apply to GameManager → Use in gameplay.**

---

## The 6 Core Components

### 1. **Storage Location** (Where settings live)

**Single Game Mode:**
- `games` collection → `teams.{team_id}.playbook_settings`
- `games` collection → `teams.{team_id}.strategy_settings`

**Franchise/Tournament Mode (two-stage source of truth, April 2026):**
- **Pregame / FCC / TCC:** master settings live in the franchise master store (`franchise_team_data` / FTD) or the tournament document
- **Active Gameplay:** settings live in the active game document under `teams.{canonical_team_id}.playbook_settings` and `teams.{canonical_team_id}.strategy_settings`

**Key Point:** Settings stored in database only. Never localStorage or URL params. Franchise and tournament use the master store before game start, then use the game document after game initialization.

**Franchise `POST /api/init-game`:** For `mode=franchise`, the backend loads **both** teams’ rows from `franchise_team_data` (by `franchise_id` + each team’s `teams` collection `_id`, resolved from `home_team` / `away_team` names). It seeds `GameManager` with **`team_attributes`**, **`strategy_settings`**, **`plays`** (per-game stats reset; effectiveness/cloaking/momentum preserved), **`scouting_data`** (merged onto the canonical scouting template, then defense per-game counters reset in `prepare_ftd_for_new_game`), and assigns **`playbook_settings`** on each `TeamManager`. **Any** time `TeamManager` receives `scouting_data` (init, simulate-quarter greenfield, or load from `games`), **`normalize_scouting_data_for_gameplay`** ensures defense rows include top-level **`used` / `success`** and full **`game_stats` / `season_stats`** so sim code does not rely on partial FTD-shaped blobs. The first `summarize_game_state` persists those fields under `games.teams.{canonical_team_id}`. This matches the franchise greenfield Q1 path in `simulate-quarter` (shared FTD normalizer: `BackEnd/utils/franchise_ftd_game_seed.py`; scouting shape: `BackEnd/models/team_manager.py`).

---

### 2. **Save Flow** (How settings are saved)

**When user saves settings:**
1. Frontend calls `/api/playbooks` or `/api/gameplan`
2. Backend saves to database
3. Backend applies to GameManager (if game is in `ongoing_games` cache)
4. Return success

**Why apply to GameManager?**
- Settings immediately available during active gameplay
- No need to reload from database every turn
- Bidirectional sync: DB is truth, GameManager is performance cache

**Key Point:** Save to DB **AND** apply to GameManager simultaneously.

---

### 3. **Load Flow** (How settings are loaded)

**At game start (`simulate-quarter`):**
1. Load settings from database
2. Apply to GameManager
3. Start simulation

**During active gameplay:**
- Settings come from GameManager (in-memory cache)
- Fast, no database reads needed

**During timeout/lineup screen:**
- Settings loaded from the active game document when `game_id` is present
- `/api/playbooks` and `/api/gameplan` check GameManager first, then fall back to the correct database source

**Key Point:** Load from DB once at start, use GameManager during gameplay.

---

### 4. **Team ID Resolution** (Consistent keys)

**Problem:** Settings must be saved/loaded using the same key format.

**Solution:**
- **Single game:** Canonical `team_id` format (e.g., "MORRISTOWN", "OCEAN_CITY").
- **Franchise/Tournament:** Backend uses the **authoritative** `user_team_object_id` from the franchise or tournament document for master saves/loads. Active game documents still use canonical team keys, so game-doc writes must normalize team identity correctly.

**Requirements:**
- Same resolution logic in save and load paths
- Franchise/tournament: resolve team id from master doc, not from URL/request
- Consistent key format prevents "settings saved but not found" bugs

**Key Point:** Use the same team key for save and load within each source. Master docs use `user_team_object_id`; active game docs use canonical team IDs.

---

### 5. **Timeout Persistence** (Settings survive timeouts)

**Franchise/Tournament:** During active gameplay, game plan and playbook settings are stored in the game document. When the user opens Game Plan or Playbooks during a timeout, GET endpoints load from that game document, and saves go back there. FCC / TCC continue to use the master store outside of active gameplay.

**Single Game:** When timeout is called, `summarize_game_state()` can preserve settings in the game document. On resume, settings are loaded from the game document and applied to GameManager.

**Key Point:** Franchise/tournament have two clear sources of truth by context: master store before the game starts, game document after the game starts. Single game uses the game document throughout.

---

### 6. **Fallback Logic** (GameManager → DB)

**API endpoints (`/api/playbooks`, `/api/gameplan`) use this pattern:**

```
1. Check if GameManager exists in ongoing_games cache
   → If yes: Use settings from GameManager (fast, fresh)
   
2. If GameManager not found:
   → Load settings from database
   → Active gameplay: game document
   → Pregame FCC/TCC: master store (FTD or tournament doc)
   → Apply settings to any newly created GameManager
```

**Why this works:**
- Active gameplay: Settings from GameManager (already in memory)
- Timeout lineup screen: Settings from DB (GameManager not in memory)
- Seamless experience: User always sees correct settings

**Key Point:** Check GameManager first, fall back to DB when needed.

---

## Visual Flow

### Save Settings
```
User saves → API endpoint → Database (save) → GameManager (apply) → Success
```

### Load Settings (Game Start)
```
simulate-quarter → Database (load) → GameManager (apply) → Gameplay
```

### Load Settings (Timeout/Lineup)
```
User visits Playbooks → /api/playbooks → Check GameManager → If missing: Database (load)
```

### Timeout Flow
```
Timeout called → summarize_game_state() → Settings preserved in DB → 
GameManager removed → Resume → Settings loaded from DB → GameManager created with settings
```

---

## Success Criteria

Settings persist correctly when:
- ✅ User saves settings before game starts
- ✅ User starts Q1 (Play Quarter, Sim Quarter, Sim Full Game)
- ✅ User calls timeout during gameplay
- ✅ User visits lineup screen during timeout
- ✅ User visits playbooks/game plan screens during timeout
- ✅ User resumes from timeout
- ✅ Settings work in Single Game, Tournament, and Franchise modes

---

## Common Pitfalls to Avoid

❌ **Don't:** Save settings to localStorage (not persisted across devices)  
❌ **Don't:** Store settings in URL params (too long, not scalable)  
❌ **Don't:** Use different team ID formats in save vs. load (settings won't match)  
❌ **Don't:** Only save to GameManager without saving to DB (settings lost on timeout)  
❌ **Don't:** Only save to DB without applying to GameManager (settings not used in gameplay)
❌ **Don't:** Let in-game franchise/tournament edits write back to FTD / tournament master settings

✅ **Do:** Save to DB AND apply to GameManager simultaneously  
✅ **Do:** Use consistent `team_id` format everywhere  
✅ **Do:** Check GameManager first, fall back to DB  
✅ **Do:** Preserve settings in game document during timeout
✅ **Do:** Keep FCC/TCC saves in the master store and gameplay saves in the game doc

---

## Reference Implementation

**Save settings:** `BackEnd/api/gameplan_routes.py` → `save_playbooks()`, `update_gameplan()`  
**Load settings:** `BackEnd/api/api.py` → `load_team_settings_from_doc()`  
**Apply settings:** `BackEnd/api/api.py` → `simulate_quarter_endpoint()`  
**Preserve settings:** `BackEnd/utils/shared.py` → `summarize_game_state()`  
**Timeout save:** `BackEnd/api/api.py` → `handle_timeout_save_and_response()`

---

**This guide covers the essential patterns. For detailed implementation, see `Data_Persistence_System.md` and `timeout_data_&_state_persistence.md`.**
