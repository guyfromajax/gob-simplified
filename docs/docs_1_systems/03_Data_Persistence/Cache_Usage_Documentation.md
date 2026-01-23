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

**Location:** `BackEnd/api/api.py` (line 234)  
**Type:** `dict[str, GameManager]`  
**Purpose:** In-memory cache of active `GameManager` instances during gameplay  
**Lifetime:** Runtime only (cleared on server restart)

**What It Stores:**
- `GameManager` objects for active games
- Key: `game_id` (MongoDB ObjectId string)
- Value: `GameManager` instance with full game state

**When Populated:**
1. **`/api/init-game`** (line 3952): After creating new game document
2. **`/api/simulate-quarter`** (line 2272): After loading game from DB for Q1 or resuming from timeout

**When Cleared/Invalidated:**
1. **New game scenario** (line 1629): When user requests Q1 but cached game is Q2+
2. **Timeout resume** (line 1743): When resuming from timeout, cache is deleted to force DB reload
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
- `refresh_game_cache_from_db(gm, saved)` (line 777): Updates critical game state in existing `GameManager` instance to match saved document

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
- `FrontEnd/static/franchise-command-center.js` (line 17)
- `FrontEnd/static/tournament.js` (line 11)

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
1. **Franchise Command Center**: `initializeTeamColorCache()` (line 115) - Called once on page load
2. **Tournament**: `initializeTeamColorCache()` (line 639) - Called once on page load

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

**Current Status:** ✅ Implemented (Phase 1.3 and Phase 3 Task 4)

**Backend Telemetry:**
- **Location:** `BackEnd/api/api.py` and `BackEnd/api/gameplan_routes.py`
- **Logs:**
  - `✅ [CACHE-TELEMETRY] Cache HIT` - Cache read successful
  - `❌ [CACHE-TELEMETRY] Cache MISS` - Cache not available, reading from DB
  - `🔄 [CACHE-TELEMETRY] Cache SKIP` - source=db, forcing DB read
  - `🔄 [CACHE-TELEMETRY] Cache REFRESHED` - Cache updated after DB write
  - `🔄 [CACHE-TELEMETRY] Cache INVALIDATED` - Cache cleared
  - `✅ [CACHE-TELEMETRY] Cache POPULATED` - Cache entry added

**Frontend Telemetry:**
- **Location:** `FrontEnd/static/js/state/gameStore.js` (via `StateTelemetry`)
- **Logs:**
  - `🟢 [CACHE-HIT]` - Cache read successful
  - `🟡 [CACHE-MISS]` - Cache not available, reading from backend
  - `🔴 [CACHE-INVALIDATION]` - Cache cleared (with reason)

**Metrics Captured:**
- Cache hit rate (reads from cache vs DB)
- Cache miss rate (reads from DB when cache available)
- Cache invalidation frequency (with reasons)
- Cache population events

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

1. **Cache telemetry** (Phase 3 Task 4):
   - Log cache hits/misses
   - Track cache performance metrics
   - Monitor cache invalidation events

2. **Version-based invalidation:**
   - Invalidate cache on version mismatch
   - Ensure cache compatibility across deployments

3. **Cache size limits:**
   - Implement LRU eviction for `ongoing_games`
   - Prevent memory bloat from abandoned games

