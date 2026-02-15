# Settings Persistence Guide

**Purpose:** Clear, concise guide to how playbook and game plan settings persist across all game modes and gameplay scenarios.

**Last Updated:** January 2026

---

## Core Principle

**Database is the single source of truth. Settings flow: Save → DB → Apply to GameManager → Use in gameplay.**

---

## The 6 Core Components

### 1. **Storage Location** (Where settings live)

**Single Game Mode:**
- `games` collection → `teams.{team_id}.playbook_settings`
- `games` collection → `teams.{team_id}.strategy_settings`

**Franchise/Tournament Mode (single source of truth, February 2026):**
- **Franchise:** `franchise_team_data` (FTD) collection → `playbook_settings` / `strategy_settings` (one doc per franchise + team). Used for both pre-game and in-game; the game document is not used for these settings.
- **Tournament:** `tournaments` collection → `teams.{team_id}.playbook_settings` and `teams.{team_id}.strategy_settings`. Used for both pre-game and in-game; the game document is not used for these settings.

**Key Point:** Settings stored in database only. Never localStorage or URL params. Franchise and tournament never use the game document for game plan or playbooks.

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
- Settings loaded from database (GameManager may not be in memory)
- `/api/playbooks` and `/api/gameplan` check GameManager first, fall back to DB

**Key Point:** Load from DB once at start, use GameManager during gameplay.

---

### 4. **Team ID Resolution** (Consistent keys)

**Problem:** Settings must be saved/loaded using the same key format.

**Solution:** Canonical `team_id` format everywhere (e.g., "MORRISTOWN", "OCEAN_CITY")

**Requirements:**
- Same resolution logic in save and load paths
- No team name → team_id conversion needed (use `team_id` directly)
- Consistent key format prevents "settings saved but not found" bugs

**Key Point:** Use canonical `team_id` keys consistently in save and load.

---

### 5. **Timeout Persistence** (Settings survive timeouts)

**Franchise/Tournament:** Game plan and playbook settings are always stored in the master store (FTD or tournament doc), not in the game document. When the user opens Game Plan or Playbooks during a timeout, GET endpoints load from that same store. Saves go to the same store. So settings persist through timeout with no special "restore from game doc" step.

**Single Game:** When timeout is called, `summarize_game_state()` can preserve settings in the game document. On resume, settings are loaded from the game document and applied to GameManager.

**Key Point:** Franchise/tournament use a single source of truth (FTD/tournament doc) for settings, so timeout persistence is automatic. Single game uses the game document.

---

### 6. **Fallback Logic** (GameManager → DB)

**API endpoints (`/api/playbooks`, `/api/gameplan`) use this pattern:**

```
1. Check if GameManager exists in ongoing_games cache
   → If yes: Use settings from GameManager (fast, fresh)
   
2. If GameManager not found:
   → Load settings from database (lineup screen, timeout scenarios)
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

✅ **Do:** Save to DB AND apply to GameManager simultaneously  
✅ **Do:** Use consistent `team_id` format everywhere  
✅ **Do:** Check GameManager first, fall back to DB  
✅ **Do:** Preserve settings in game document during timeout

---

## Reference Implementation

**Save settings:** `BackEnd/api/gameplan_routes.py` → `save_playbooks()`, `update_gameplan()`  
**Load settings:** `BackEnd/api/api.py` → `load_team_settings_from_doc()`  
**Apply settings:** `BackEnd/api/api.py` → `simulate_quarter_endpoint()`  
**Preserve settings:** `BackEnd/utils/shared.py` → `summarize_game_state()`  
**Timeout save:** `BackEnd/api/api.py` → `handle_timeout_save_and_response()`

---

**This guide covers the essential patterns. For detailed implementation, see `Data_Persistence_System.md` and `timeout_data_&_state_persistence.md`.**

