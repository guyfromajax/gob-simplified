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
**Purpose:** UI state cache for teams, rosters, colors, and `game_id`  
**Lifetime:** Runtime only (cleared on page unload)

**What It Stores:**
```javascript
{
  teams: { home: null, away: null },
  colors: { home: {}, away: {} },
  rosters: { home: null, away: null },
  gameId: null
}
```

**When Populated:**
1. **`bootGame.js`**: When game initializes, calls `gameStore.setTeams()`, `gameStore.setColors()`, `gameStore.setRosters()`, `gameStore.setGameId()`
2. **`gameScene.js`**: Updates `gameId` during gameplay

**When Cleared/Invalidated:**
1. **Page navigation**: State lost on page unload
2. **Manual reset**: `gameStore.reset()` clears all state
3. **Game completion**: State cleared when game ends

**Refresh Triggers:**
- **On game start**: Populated from API response (`/api/simulate-quarter`)
- **On navigation**: State is rebuilt from URL params and API calls
- **No automatic refresh**: Must be explicitly populated

**Usage Pattern:**
- **UI rendering**: Read from `gameStore` to avoid repeated API calls
- **Not authoritative**: Always backed by URL params and API responses
- **Performance optimization**: Reduces API calls during active gameplay

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
   - `save_playbooks()`: Updates `GameManager` directly (bidirectional sync)
   - `update_gameplan()`: Updates `GameManager` directly (bidirectional sync)
   - `handle_timeout_save_and_response()`: Calls `refresh_game_cache_from_db()` to sync cache after DB write
   - `simulate_quarter_endpoint()`: Calls `refresh_game_cache_from_db()` to sync cache after DB write

2. **On navigation:**
   - Frontend caches (`gameStore`, `teamColorCache`) automatically cleared on page unload (module re-initialization)
   - Backend cache (`ongoing_games`) persists across requests but cleared on specific triggers:
     - New game scenario (Q1 requested but cached game is Q2+)
     - Timeout resume (forces DB reload)
     - Server restart

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

**Current Status:** Not yet implemented (Phase 3 Task 4)

**Planned Metrics:**
- Cache hit rate (reads from cache vs DB)
- Cache miss rate (reads from DB when cache available)
- Cache invalidation frequency
- Cache size (number of entries)

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

