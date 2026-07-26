# Cache Usage Documentation

**Version:** 1.0  
**Status:** Active Documentation  
**Last Updated:** January 2026  
**Purpose:** Document all caches in the codebase, their refresh triggers, and invalidation logic.

---

## Overview

Caches are **performance mirrors** of truth (database), never truth itself. They can be dropped, invalidated, or rebuilt without affecting correctness.

**Core Principle:** Never read from cache if truth (database) is available. Always prefer DB reads over cache reads.

---

## Cache Inventory

### 1. `ongoing_games` (Backend)

**Location:** `BackEnd/api/api.py`  
**Type:** `dict[str, GameManager]`  
**Purpose:** In-memory cache of active `GameManager` instances during gameplay  
**Lifetime:** Runtime only (cleared on server restart)

**What It Stores:**
- `GameManager` objects for active games
- Key: `game_id` (MongoDB ObjectId string)
- Value: `GameManager` instance with full game state

**When Populated:**
1. **`/api/init-game`**: After creating new game document
2. **`/api/simulate-quarter`**: After loading game from DB for Q1 or resuming from timeout

**When Cleared/Invalidated:**
1. **New game scenario**: When user requests Q1 but cached game is Q2+
2. **Timeout resume**: When resuming from timeout, cache is deleted to force DB reload
3. **Server restart**: All in-memory state lost
4. **Manual deletion**: `del ongoing_games[game_id]` in various error paths

**Refresh Triggers:**
1. **After timeout save** (`handle_timeout_save_and_response`): Calls `refresh_game_cache_from_db()` to sync cache with DB
2. **After settings save** (`save_playbooks`, `update_gameplan`): Directly updates `GameManager` attributes (bidirectional sync)
3. **After quarter break**: Cache is cleared, reloaded from DB on next `simulate-quarter` call

**Usage Pattern:**
- **During active gameplay**: Read from `ongoing_games` cache (fast, many calls)
- **After state changes**: Refresh cache from DB or update cache directly
- **For lineup screen**: Always read from DB (infrequent, ~13 reads per game)

**Refresh Function:**
- `refresh_game_cache_from_db(gm, saved)`: Updates critical game state in existing `GameManager` instance to match saved document

---

### 2. `gameStore` (Frontend)

**Location:** `FrontEnd/static/js/state/gameStore.js`  
**Type:** JavaScript module with in-memory state object  
**Purpose:** UI state cache for teams, rosters, colors, `game_id`, and optional settings cache  
**Lifetime:** Runtime only (cleared on page unload)

**What It Stores:**
```javascript
{
  teams: { home: null, away: null },
  colors: { home: {}, away: {} },
  rosters: { home: null, away: null },
  gameId: null,
  // ✅ PHASE 1.3: Optional cache for settings (disposable, rebuild from truth)
  playbook_settings: null,  // Cached playbook settings (backend is source of truth)
  strategy_settings: null  // Cached strategy settings (backend is source of truth)
}
```

**When Populated:**
1. **`bootGame.js`**: When game initializes, calls `gameStore.setTeams()`, `gameStore.setColors()`, `gameStore.setRosters()`, `gameStore.setGameId()`
2. **`gameScene.js`**: Updates `gameId` during gameplay
3. **`playbooks.js`** (Phase 1.3): After successful backend load, calls `gameStore.setPlaybookSettings()`
4. **`game-plan.js`** (Phase 1.3): After successful backend load, calls `gameStore.setStrategySettings()`

**When Cleared/Invalidated:**
1. **Page navigation**: State lost on page unload
2. **Manual reset**: `gameStore.reset()` clears all state (including settings cache)
3. **Game completion**: State cleared when game ends
4. **After DB writes** (Phase 1.3): `gameStore.invalidatePlaybookSettings()` and `gameStore.invalidateStrategySettings()` called after successful saves

**Refresh Triggers:**
- **On game start**: Populated from API response (`/api/simulate-quarter`)
- **On navigation**: State is rebuilt from URL params and API calls
- **On settings load** (Phase 1.3): Settings cache populated after successful backend load
- **After settings save** (Phase 1.3): Settings cache invalidated, will be repopulated on next load
- **No automatic refresh**: Must be explicitly populated

**Usage Pattern:**
- **UI rendering**: Read from `gameStore` to avoid repeated API calls
- **Settings cache** (Phase 1.3): Optional performance optimization - checked first, falls back to backend if cache miss
- **Not authoritative**: Always backed by URL params and API responses
- **Performance optimization**: Reduces API calls during active gameplay and page navigation

---

### 3. `teamColorCache` (Frontend)

**Location:** 
- `FrontEnd/static/franchise-command-center.js`
- `FrontEnd/static/tournament.js`

**Type:** JavaScript object mapping team names to primary colors  
**Purpose:** Cache team primary colors for UI rendering  
**Lifetime:** Runtime only (cleared on page unload)

**What It Stores:**
```javascript
{
  "Team Name": "#hexcolor",
  ...
}
```

**When Populated:**
1. **Franchise Command Center**: `initializeTeamColorCache()` - Called once on page load
2. **Tournament**: `initializeTeamColorCache()` - Called once on page load

**When Cleared/Invalidated:**
1. **Page navigation**: State lost on page unload
2. **Manual reset**: `teamColorCache = {}` in initialization function

**Refresh Triggers:**
- **On page load**: Populated from command center data
- **No automatic refresh**: Must be explicitly populated

**Usage Pattern:**
- **UI rendering**: Read from cache to avoid repeated lookups
- **Not authoritative**: Always backed by command center data
- **Performance optimization**: Reduces data processing during rendering

---

### 4. Backend Module-Level Memoization Caches

Process-lifetime caches that memoize stable lookups (plays collection, scouting templates, etc.). All are populated lazily on first read and **never invalidated** within a process — they reset only on server restart.

| Cache | Location | Stores | Populate |
|---|---|---|---|
| `_plays_by_type_focus_cache` | `BackEnd/models/turn_manager.py` | `{(type, focus) → list}` of plays filtered by type + focus | `plays_collection.find()` on cache miss |
| `_play_doc_by_name_cache` | `BackEnd/models/turn_manager.py` | `{name → dict \| None}` of individual play documents | `plays_collection.find_one()` on cache miss |
| `_plays_cache` | `BackEnd/models/team_manager.py` | Full plays collection (list of dicts) | `plays_collection.find({})` once at first `TeamManager` init (~16s→1s speedup) |
| `_plays_names_cache` | `BackEnd/models/team_manager.py` | Play names list, derived from `_plays_cache` | First `TeamManager` init |
| `_scouting_data_template_cache` | `BackEnd/models/team_manager.py` | Nested scouting-data template structure | `_create_scouting_data_template_base()` once; subsequent inits deepcopy (~7.5s→3ms) |
| `_QUESTION_BANK_CACHE` | `BackEnd/pgpc_qualification.py` | Press-conference question bank | First module import via `importlib` |

**Correctness model:** the underlying `plays_collection` (and the question bank module) is treated as immutable per-process. Code that mutates the source mid-process would produce stale reads. No invalidation API exists.

---

### 5. Backend `@lru_cache` Decorators

Function-result caches that wrap pure-function calls. `maxsize=1` makes them "compute once per process." Reset on process restart only.

| Cache | Location | Stores |
|---|---|---|
| `_load_franchise_first_name_rankings()` | `BackEnd/models/franchise_manager.py` | Ranked first-name tuples loaded from `franchise_first_name_rankings.json` |
| `get_franchise_name_assets()` | `BackEnd/models/franchise_manager.py` | Composite tuple of first/last names + weights for franchise generation |

---

### 6. Backend Per-Game Cache: `_skeleton_cache`

**Location:** `BackEnd/engine/phase_resolution.py`
**Type:** `dict[str, dict]` keyed by `play_id`
**Lifetime:** Per-game (effectively scoped to the game's resolution context)
**Purpose:** Caches skeleton play documents by `play_id` to avoid repeated DB queries during a single game.
**Invalidation:** None — destroyed when the game context ends.

---

### 7. Frontend Page-Local Module Caches

Page-local caches stored as module-level `let xCache = ...` variables. Lifetime is the page session — all are cleared on navigation / unload (the JS module re-initializes on the next page load). They are NOT central state management; they're per-module performance optimizations for repeated data lookups.

#### Franchise Command Center (`FrontEnd/static/franchise-command-center.js`)

Beyond the already-documented `teamColorCache`, the FCC defines 14+ sibling caches following the same pattern:

| Cache | Stores | Invalidation |
|---|---|---|
| `teamMetaByNameCache` | Team metadata by name (mascot, colors) | Reset on init |
| `leadersDataCache` | Conference leaders leaderboard | Never explicitly |
| `teamStatsDataCache` | Team statistics (conference scope) | Never explicitly |
| `teamTraitsDataCache` | Team traits / characteristics | Never explicitly |
| `fccTeamStatsSummaryCache` | Team stats summary | Never explicitly |
| `commandCenterTopDataCache` | Top-level command center data (standings, schedules); also mirrored to `sessionStorage` | `invalidateFccTeamScopedCaches()` on team change |
| `standingsDataCache` | League standings table | `invalidateFccTeamScopedCaches()` / `invalidateHomeWeekSensitiveCaches()` |
| `playbooksWeekSavedCache` | Playbooks saved for current week | Never explicitly |
| `fccPlaybooksSummaryCache` | Playbook summary | `invalidateFccTeamScopedCaches()` |
| `userRosterPlayersCache` | Current user's roster players | `invalidateFccTeamScopedCaches()` / `invalidateHomeWeekSensitiveCaches()` |
| `userScheduleDataCache` | User team's game schedule | `invalidateHomeWeekSensitiveCaches()` |
| `homeLastGameDataCache` | Last game result for home view | `invalidateHomeWeekSensitiveCaches()` |
| `homeOpponentRosterCache` (Map) | Opponent rosters by team_id | `invalidateFccTeamScopedCaches()` / `invalidateHomeWeekSensitiveCaches()` |
| `leanRecruitsDataCache` | Available recruits | Never explicitly |
| `signedRecruitsDataCache` | Signed user recruits | Never explicitly |
| `scoutingTabDataCache` | Scouting view data | Never explicitly |
| `fccNewsListCache` | Season news stories for the News tab (`GET /franchise/news`) | Reset on init |

**Invalidation hooks (FCC-specific):**
- `invalidateFccTeamScopedCaches()` — called when the user switches their controlled team
- `invalidateHomeWeekSensitiveCaches()` — called when advancing to the next week

#### Tournament (`FrontEnd/static/tournament.js`) — **sunset mode** (wiring remains until the tournament code purge)

Mirrors a subset of the FCC pattern:

| Cache | Stores |
|---|---|
| `teamColorCache` (already documented in §3) | Team primary colors |
| `teamMetaByNameCache` | Team metadata by name |

#### Set Lineup (`FrontEnd/static/set-lineup.js`)

| Cache | Stores | Invalidation |
|---|---|---|
| `lineupPlaybooksModalCache` | Playbook settings + shot weights for the lineup-editor modal | Re-fetched on next modal open; no explicit clear |

---

### 8. `ResourceCache` Module

**Location:** `FrontEnd/static/js/shared/resourceCache.js`
**API:** `window.ResourceCache.createResourceCache(page, franchiseId, season, week)` — factory returning a scoped cache object with `get(scopeKey)` / `set(scopeKey, value)` methods.
**Backing store:** In-memory (per page load) + `sessionStorage` (per tab) under keys of the form `resource:{page}:{franchiseId}:{season}:{week}:{scopeKey}`.
**Used by:** `leaders.js`, `team-stats.js` (and likely others — grep `ResourceCache.createResourceCache` for the full list).
**Purpose:** Reusable cache primitive for FCC sub-pages that need scoped session-level caching (e.g., conference leaders by week).
**Invalidation:** Memory cleared on page navigation; sessionStorage entries persist until the tab closes.

---

### 9. Persistent Browser Storage

`localStorage` (persists indefinitely) and `sessionStorage` (per-tab session) carry both cache-like data and source-of-truth user preferences. The list below is comprehensive across `FrontEnd/static/`.

#### `localStorage` Keys

**Auth / Session**
- `auth_token` — JWT for API requests. Removed on logout / auth failure.
- `auth_user` — Serialized user object (username, email, etc.).

**Franchise Context**
- **Canonical (Phase 3 hybrid):** `franchise:{id}:week`, `franchise:{id}:user_team`, `franchise:{id}:user_team_id`, `franchise:{id}:user_team_primary_color`, `franchise:{id}:complete_week_pending`, `franchise:{id}:eog_pgpc_snapshot`, `franchise:{id}:last_game_id`, `franchise:{id}:last_game_user_team_side` — via `window.FranchiseLS` (`FrontEnd/static/js/shared/franchiseLocalStorage.js`).
- `playbooks_position_filters_franchise_*` (dynamic prefix) — Per-franchise playbook filter state
- **Identity:** `API_CONFIG.currentFranchiseId()` is **URL-only** (`?franchise_id=`). Do not store or fall back to bare `franchise_id` / `franchiseId`.
- **Legacy bare keys** (`franchise_user_team`, `franchise_week`, `franchise_complete_week_pending`, etc.): no longer written; migrated one-shot on read where needed; wiped by `FranchiseLS.clearOnFranchiseExit()` / mode-select exit.

**Game State (Single / Franchise)**
- `last_game_id` — For resume functionality
- `last_game_user_team_side` — home / away
- `last_box_score_gameId`, `last_box_score_url` — Debug helpers
- `game_home`, `game_away` — Selected team names

**Tournament** — *sunset mode; keys remain until the tournament code purge*
- `activeTournament` — Serialized active tournament object
- `userTeamId` — User team ID in tournament context

**UI Preferences (never cleared — true source of truth)**
- `alpha_disclaimer_dismissed_version` — Alpha disclaimer dismissal version
- `gob_dont_show_new_franchise_warning` — Warning suppression flag

**Canonical cleanup:** `mode-select.js:clearFranchiseLocalStorage()` → `FranchiseLS.clearOnFranchiseExit()` (bare keys + all `franchise:*` namespaces + last-game globals + playbook filter prefixes).

**Orphans flagged:**
- `franchiseId` in `tournament.js` — legacy; superseded by `userTeamId` / `activeTournament`
- `game_id` in `box-score.js` — commented-out removal; unclear if read anywhere

#### `sessionStorage` Keys

**Game Setup State**
- `homeTeam`, `awayTeam`, `myTeam` — Team selection for game setup
- `mode` — single / franchise / tournament fallback

**UI View State**
- `lineupView`, `rosterView` — View-mode preferences
- `gameplan_suppress_warning` — Per-session warning suppression

**Training Playbooks**
- `gob_training_playbook_focus` — Serialized focused playbook rows (offense / defense)
- `gob_playbook_training_mode` — Training mode (custom / standard)
- `gob_training_team_drills_snapshot` — Serialized team drill install snapshot
- `gob_training_form_draft_*` (dynamic, scoped by `{franchiseId}|{teamId}|w{week}|{stageType}`) — Form draft state

**Playbooks Editor**
- `playbooksDraft:*` (dynamic, scoped by `{mode}:{teamId}:{franchiseId}:{tournamentId}:{gameId}`) — Editor draft state
- `playbooksDraftRestoreOnce:*` (matching keys) — One-time draft-restore flag

**Popups / Notifications**
- `defenseMatchupsDontShow_{gameId}` — Suppress defense-matchups popup for this game
- `defenseMatchupsAnnouncePlayed_{gameId}` — Game-announced flag (prevents re-announcing)

**FCC Session Cache**
- `fcc-shell:{franchiseId}:{teamId|unknown}` — Serialized FCC top-level data snapshot (mirrors `commandCenterTopDataCache` / `standingsDataCache` etc.). Restored data is used only as a behind-the-overlay warm paint on FCC entry; the full-page loading overlay remains visible until authoritative `/franchise/command-center/data` returns and current UI state is applied.

**Generic ResourceCache**
- `resource:*` (dynamic pattern) — `ResourceCache` module entries; see §8

**Error Telemetry**
- `errorTelemetry` — Last 10 errors, serialized array

---

## Cache Invalidation Strategy

### Automatic Invalidation

1. **After DB writes:**
   - **Backend:**
     - `save_playbooks()`: Updates `GameManager` directly (bidirectional sync)
     - `update_gameplan()`: Updates `GameManager` directly (bidirectional sync)
     - `handle_timeout_save_and_response()`: Calls `refresh_game_cache_from_db()` to sync cache after DB write
     - `simulate_quarter_endpoint()`: Calls `refresh_game_cache_from_db()` to sync cache after DB write
   - **Frontend** (Phase 1.3):
     - `playbooks.js`: After successful save, calls `gameStore.invalidatePlaybookSettings('backend_save')`
     - `game-plan.js`: After successful save, calls `gameStore.invalidateStrategySettings('backend_save')`

2. **On navigation:**
   - **Frontend caches:**
     - `gameStore` (teams, rosters, colors, gameId): Automatically cleared on page unload (module re-initialization)
     - `gameStore` (playbook_settings, strategy_settings): Automatically cleared on page unload (module re-initialization)
     - `teamColorCache`: Automatically cleared on page unload (module re-initialization)
     - **Note:** No manual invalidation needed - JavaScript modules are re-initialized on each page load, ensuring fresh cache
   - **Backend cache (`ongoing_games`):**
     - Persists across requests but cleared on specific triggers:
       - New game scenario (Q1 requested but cached game is Q2+)
       - Timeout resume (forces DB reload)
       - Server restart
     - **Note:** Backend cache persists across page navigations (same game_id), which is correct for active gameplay

3. **On version mismatch:**
   - Not currently implemented (future enhancement)
   - Planned: Invalidate cache when backend version changes

### Invalidation by Cache Category

The matrix above covers the original three caches in detail. The remaining categories follow these patterns:

- **Backend memoization caches (§4) and `@lru_cache` decorators (§5):** Never invalidated within a process. Reset only on server restart. Risk surface: assumes the underlying source (plays collection, ranking JSON files) is immutable per-process.
- **Backend per-game cache `_skeleton_cache` (§6):** Lifetime tied to the game-context object; destroyed when the game ends. No explicit invalidation API.
- **Frontend page-local module caches (§7):** Automatically cleared on page navigation (module re-init). Some FCC caches additionally honor `invalidateFccTeamScopedCaches()` / `invalidateHomeWeekSensitiveCaches()` for mid-page invalidation when the user switches team or advances week.
- **`ResourceCache` (§8):** Memory cleared on navigation; sessionStorage entries persist until the tab closes.
- **`localStorage` / `sessionStorage` (§9):** Invalidation is per-key and explicit. `mode-select.js:clearFranchiseLocalStorage()` is the canonical cleanup for franchise-context exit. Tab close clears all `sessionStorage`; `localStorage` survives indefinitely unless explicitly removed.

### Manual Invalidation

1. **Error recovery:**
   - `del ongoing_games[game_id]` in error paths
   - Forces reload from DB on next request

2. **New game scenario:**
   - Cache cleared when user requests Q1 but cached game is Q2+
   - Forces reload from DB where new game detection runs

3. **Timeout resume:**
   - Cache cleared when resuming from timeout
   - Forces reload from DB to ensure fresh state

---

## Cache Performance Metrics

**Backend:** No structured cache telemetry. `ongoing_games` hits/misses are inferred from request flow; no per-cache-event log line is emitted.

**Frontend Telemetry** (via `StateTelemetry` in `FrontEnd/static/js/shared/stateTelemetry.js`):
- `✅ [CACHE-HIT]` — `gameStore` read returned a cached value
- `⚠️ [CACHE-MISS]` — `gameStore` had no cached value; caller fell back to backend
- `🔄 [CACHE-INVALIDATE]` — `gameStore` entry cleared (reason logged)

Plus state-contract logs from the same module:
- `🟢 [STATE-WRITE]` / `🔵 [STATE-READ]` — normal state I/O
- `🔴 [STATE-VIOLATION]` — read or write hit a non-contract source

**Metrics derivable from frontend logs:** cache hit rate, miss rate, invalidation frequency with reasons. No equivalent backend instrumentation today.

---

## Best Practices

1. **Never read from cache if truth is available:**
   - Always prefer DB reads over cache reads
   - Cache is for performance, not correctness

2. **Always invalidate after DB writes:**
   - Update cache immediately after DB write
   - Use bidirectional sync pattern (DB → Cache)

3. **Fail loudly if cache is stale:**
   - Don't silently fall back to stale cache
   - Clear cache and reload from DB if stale

4. **Document cache refresh triggers:**
   - Clear documentation of when cache is populated/cleared
   - Explicit refresh logic, not implicit

---

## Future Enhancements

1. **Version-based invalidation:**
   - Invalidate cache on version mismatch
   - Ensure cache compatibility across deployments

3. **Cache size limits:**
   - Implement LRU eviction for `ongoing_games`
   - Prevent memory bloat from abandoned games
