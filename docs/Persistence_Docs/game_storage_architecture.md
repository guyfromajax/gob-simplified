# Game Storage Architecture Across Modes

**Date:** November 5, 2025  
**Purpose:** Analyze game document structure across Single, Tournament, and Franchise modes

---

## Executive Summary

✅ **Game documents are ALREADY optimized** - no redundant fields to remove  
✅ **No need to delineate universal vs bespoke fields** - mode-specific fields are just metadata (<1%)  
✅ **Mode indicators implemented:** `franchise_id` and `tournament_id` are now added to game documents  

---

## Current State

**Total games in DB:** 39 games  
**Storage location:** `games_collection` (all modes)  
**Average size:** ~18KB per game (after optimization)  
**Nested storage:** Code exists but not currently used  

---

## Storage Patterns by Mode

### **1. Single Game / Scrimmage**

**Storage:** `games_collection`  
**Mode indicators:** None  

**Fields:**
```javascript
{
  "_id": ObjectId("..."),
  "game_id": "...",
  
  // Teams
  "home_team": {...},        // Game stats (1.7 KB)
  "away_team": {...},        // Game stats (1.7 KB)
  "home_team_id": "TEAM_ID",
  "away_team_id": "TEAM_ID",
  
  "teams": {...},            // Gameplan data (6.7 KB)
  
  // Players
  "players": [...],          // 3.7 KB
  
  // Game state
  "score": {"Team A": 97, "Team B": 86},
  "is_final": true,
  "quarter": 4,
  "opening_tip_winner": "home",
  
  // Logs
  "text_log": [...],         // 3.9 KB
  "turns": [],               // Empty (excluded after optimization)
  
  // Metadata
  "game_stats_initialized": true
}
```

**Size:** ~18KB

---

### **2. Tournament Mode**

**Storage:** `games_collection` (same as single game)  
**Mode indicators:** ✅ Includes `tournament_id` (added in init-game)  

**Fields:** Same as single game +
```javascript
{
  // Mode-specific metadata
  "tournament_id": "tournament_uuid",  // ✅ Added in init-game (line 2525)
  "round": "round_of_16",              // Optional
  "match_index": 3                     // Optional
}
```

**Process:**
1. Game saved to `games_collection`
2. `stat_updater.finalize_game(game_id, mode="tournament", tournament_id=...)`
3. Stats rolled up to `tournaments.players.{player_uuid}`

**Size:** ~18KB + ~50 bytes metadata

---

### **3. Franchise Mode**

**Storage:** `games_collection` (same as single game)  
**Mode indicators:** ✅ Includes `franchise_id` and `week` (implemented in multiple locations)  

**Fields:** Same as single game +
```javascript
{
  // Mode-specific metadata
  "franchise_id": "franchise_uuid",    // ✅ Added in multiple locations (see below)
  "week": 3,                           // For scheduling
  "team1_id": ObjectId("..."),         // For results tracking
  "team2_id": ObjectId("..."),
  "team1_score": 97,
  "team2_score": 86
}
```

**Process:**
1. Game saved to `games_collection`
2. Additional fields added: `franchise_id`, `week`, `team1_id`, `team2_id`, scores
3. `stat_updater.finalize_game(game_id, mode="franchise", franchise_id=...)`
4. Stats rolled up to `franchise.players.{player_uuid}`

**Implementation locations:**
- `franchise_routes.py` `save_result()` - Adds `franchise_id` when saving user game
- `franchise_routes.py` `_save_game_result()` - Adds `franchise_id` for all games
- `franchise_routes.py` `complete_week()` - Adds `franchise_id` for computer games
- `api.py` `init-game()` - Adds `franchise_id` when initializing game

**Size:** ~18KB + ~100 bytes metadata

---

## Nested Storage (Optional/Unused)

**Code exists for:**
- `tournament.games.{round}.{game_id}`
- `franchise.games.week_{week}.{game_id}`

**Current usage:** NOT used in practice

**Trade-offs:**

| Approach | Pros | Cons |
|----------|------|------|
| **Standalone collection** (current) | Single source of truth, easy querying across modes | Need mode indicators to filter |
| **Nested in tournament/franchise** | Games grouped by context, no cross-doc queries | Larger tournament/franchise docs, harder to query all games |

**Recommendation:** Keep current approach (standalone collection with mode indicators)

---

## Field Analysis

### **Universal Fields (All Modes)**

✅ Required for all game types:

```javascript
{
  "_id": ObjectId,
  "game_id": string,
  "home_team": object,          // Game stats
  "away_team": object,          // Game stats  
  "home_team_id": string,
  "away_team_id": string,
  "teams": object,              // Gameplan data
  "players": array,
  "score": object,
  "is_final": boolean,
  "quarter": number,
  "opening_tip_winner": string,
  "text_log": array,
  "turns": array,               // Empty after optimization
  "game_stats_initialized": boolean
}
```

---

### **Mode-Specific Fields (Metadata)**

⚠️ Small (<100 bytes), necessary for organization:

```javascript
// Tournament
{
  "tournament_id": string,     // ~40 bytes
  "round": string,             // ~20 bytes (optional)
  "match_index": number        // ~10 bytes (optional)
}

// Franchise
{
  "franchise_id": string,      // ~40 bytes (✅ NOW ADDED)
  "week": number,              // ~10 bytes
  "team1_id": ObjectId,        // ~24 bytes
  "team2_id": ObjectId,        // ~24 bytes
  "team1_score": number,       // ~10 bytes
  "team2_score": number        // ~10 bytes
}
```

**Note:** Mode-specific fields are **metadata**, not duplicates. They represent <1% of document size.

---

## Redundancy Analysis

### ✅ **No Redundancy Found!**

**teams object (6.7 KB, 37.8%):**
- **Contains:** `strategy_settings`, `plays`, `attributes`, `scouting`
- **Purpose:** Gameplan data (needed for gameplay engine)

**home_team / away_team (1.7 KB each, 9.4% each):**
- **Contains:** `name`, `score`, `box_score`, `totals`
- **Purpose:** Game stats (needed for results display)

**❌ NO OVERLAP** between `teams` and `home_team`/`away_team`

**This was already optimized in previous work!**

---

## Size Breakdown

```
Game Document Size: ~18KB
  teams:          6.7 KB  (37.8%) - Gameplan data
  text_log:       3.9 KB  (21.9%) - Play-by-play
  players:        3.7 KB  (20.6%) - Player data
  home_team:      1.7 KB  ( 9.4%) - Home stats
  away_team:      1.7 KB  ( 9.4%) - Away stats
  score:          0.0 KB  ( 0.2%) - Final score
  Other:          0.3 KB  ( 1.7%) - Metadata
```

**Efficiency:** ~89% reduction from original (~168KB → ~18KB)

---

## Identified Issues

### ✅ **Fixed: franchise_id in Franchise Games**

**Status:** ✅ **IMPLEMENTED** - Franchise game documents now include `franchise_id`

**Implementation:**
- Added in `franchise_routes.py` `save_result()` (line 331)
- Added in `franchise_routes.py` `_save_game_result()` (line 186)
- Added in `franchise_routes.py` `complete_week()` (line 496)
- Added in `api.py` `init-game()` (line 2527)

**Result:**
- ✅ Games can be queried by franchise
- ✅ Clear ownership of games to franchises
- ✅ No longer relies solely on week + team_id matching

---

## Recommendations

### **1. ✅ Mode Indicators Added**

**Tournament games:**
```python
# ✅ IMPLEMENTED in api.py init-game() (line 2525)
game_data["tournament_id"] = str(tournament_id)
game_data["round"] = round_key  # Optional
```

**Franchise games:**
```python
# ✅ IMPLEMENTED in multiple locations:
# - franchise_routes.py save_result() (line 331)
# - franchise_routes.py _save_game_result() (line 186)
# - franchise_routes.py complete_week() (line 496)
# - api.py init-game() (line 2527)
game_data["franchise_id"] = str(franchise_id)
game_data["week"] = week
```

---

### **2. NO Delineation Needed**

**No need to separate universal vs bespoke fields because:**
- ✅ Mode-specific fields are just metadata (<1%)
- ✅ No redundant data between modes
- ✅ All modes use the same core structure
- ✅ Adding a few metadata fields doesn't cause bloat

**Keep current structure:**
- Universal fields work for all modes
- Mode-specific fields added as needed
- Clean, simple, no redundancy

---

### **3. Keep Current Architecture**

✅ **games_collection** as primary storage  
✅ **teams** object for gameplan data  
✅ **home_team**/**away_team** for game stats  
✅ **Mode indicators** for organization  

**No changes needed to core structure!**

---

### **4. Optional: Implement Nested Storage**

**If you want games grouped by context:**

**Tournament:**
```javascript
tournament.games: {
  "round_of_16": {
    "game_id_1": { /* full game */ },
    "game_id_2": { /* full game */ }
  },
  "quarterfinals": {
    "game_id_3": { /* full game */ }
  }
}
```

**Franchise:**
```javascript
franchise.games: {
  "week_1": {
    "game_id_1": { /* full game */ },
    "game_id_2": { /* full game */ }
  },
  "week_2": {
    "game_id_3": { /* full game */ }
  }
}
```

**Benefits:**
- Games grouped by context
- Single query gets all games for a round/week
- No need for mode indicators

**Trade-offs:**
- Larger tournament/franchise docs
- 16MB MongoDB doc limit could be reached (14 weeks × 4 games × 18KB = ~1MB, still safe)
- Harder to query all games across tournaments/franchises

**Recommendation:** Keep current standalone approach unless you need context-grouped queries.

---

## Final Verdict

### ✅ **Game Documents Are Already Optimized**

**No redundancy to remove:**
- `teams` vs `home_team`/`away_team` serve different purposes
- No duplicate data between modes
- Already achieved ~89% size reduction (168KB → 18KB)

**No delineation needed:**
- Universal fields work for all modes
- Mode-specific fields are just metadata (<1%)
- Simple, clean architecture

**Status:**
- ✅ `franchise_id` now added to franchise game documents
- ✅ `tournament_id` now added to tournament game documents

**Keep current structure:**
- ✅ games_collection as primary storage
- ✅ Universal fields for all modes
- ✅ Mode indicators for organization
- ✅ No nested storage (unless needed)

---

## Code Locations

**Game saving:**
- `BackEnd/api/api.py` - `simulate_quarter_endpoint()` (lines 821-828)
- `BackEnd/api/tournament_routes.py` - `save_result()` (line 336)
- `BackEnd/api/franchise_routes.py` - `save_result()` (lines 237-249)

**Nested storage (unused):**
- `BackEnd/api/api.py` - `save_game_to_nested_structure()` (lines 234-267)
- `BackEnd/api/api.py` - `load_game_from_nested_structure()` (lines 207-232)

**Stat rollup:**
- `BackEnd/utils/stat_updater.py` - `finalize_game()` (lines 431-473)

**Game summarization:**
- `BackEnd/utils/shared.py` - `summarize_game_state()` (optimized to exclude redundant fields)

---

## Summary

**Your game storage architecture is already optimal!**

- ✅ No redundant fields to remove
- ✅ No need to delineate universal vs bespoke fields  
- ✅ Clean structure across all modes
- ✅ Already achieved massive size reduction

**Status:** All mode indicators are now implemented! `franchise_id` and `tournament_id` are added to game documents for clear ownership and querying. You're good to go! 🚀

