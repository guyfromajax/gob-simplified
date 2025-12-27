# Franchise Weekly Database Saves

## Overview

This document details exactly what data is saved to the database after each game and each week in Franchise mode. The goal is to identify what data is necessary vs. what can be removed to prevent database bloat.

---

## Current Database Architecture

### Collections Used

1. **`games` Collection** - Full game data (detailed, potentially large)
2. **`franchises` Collection** - Aggregated stats and references (optimized for reads)

---

## After Each Game Completion

### 1. User's Game (via "Sim Full Game", "Play Quarter", "Sim to 4th Quarter")

**Location:** `games` collection  
**Document ID:** Generated game_id (ObjectId or string)

**Data Saved (via `summarize_game_state()` with `exclude_animations=True`):**

```javascript
{
  "_id": "game_id",  // Unique game identifier
  "game_id": "game_id",  // Duplicate for compatibility
  "mode": "franchise",
  "franchise_id": "franchise_object_id",
  "week": 1,
  "quarter": 4,
  "is_final": true,
  "clock": "0:00",
  "time_remaining": 0,
  
  // Score data
  "score": {
    "Team Name": 85,
    "Opponent Name": 72
  },
  
  // Team metadata
  "home_team_id": "team_object_id",
  "away_team_id": "team_object_id",
  "home_team": {
    "name": "Team Name",
    "team_id": "team_object_id",
    "score": 85,
    "colors": {...},
    "box_score": {...},  // Full box score by position
    "totals": {...},  // Aggregated team totals
    "points_by_quarter": [20, 22, 21, 22],
    "team_fouls": 12,
    "timeouts": 2,
    "attributes": {...},  // Team attributes
    "strategy_calls": {...},  // Playcall overrides
    "plays": {...},  // Play data
    "scouting_data": {...}  // Opponent scouting
  },
  "away_team": { /* same structure */ },
  
  // Teams object (by team_id) for game state persistence
  "teams": {
    "team_id_1": {
      "strategy_calls": {...},
      "plays": {...},
      "attributes": {...},
      "scouting_data": {...}
    },
    "team_id_2": { /* same */ }
  },
  
  // Players array (lineup + any referenced players)
  "players": [
    {
      "playerId": "player_object_id",
      "name": "Player Name",
      "team": "home" | "away",
      "team_id": "team_object_id",
      "pos": "PG",
      "jersey": 23,
      "x": 0,  // Court coordinates
      "y": 0,
      "stats": {
        "game": {
          "PTS": 15,
          "REB": 8,
          "AST": 5,
          // ... all game stats
        }
      },
      "attributes": {
        "EM": 75,  // Energy
        "CH": 80,  // Chemistry
        "MO": 5,   // Momentum
        "NG": 1.0  // Natural Growth
      }
    },
    // ... all players in lineup
  ],
  
  // Turn data (EMPTY ARRAY for database saves - turns not saved)
  "turns": [],  // ✅ Already optimized: turns array is empty for database saves
  
  // Text log (play-by-play text)
  "text_log": [
    "Turn 1: Player makes shot",
    "Turn 2: Player rebounds",
    // ... all text entries
  ],
  
  // Game state metadata
  "opening_tip_winner": "team_id",
  "game_stats_initialized": true,
  "user_team_side": "home" | "away",
  "timeout_next_play_type": "HCO",
  "timeout_offense_team_id": "team_id",
  
  // Box score (top-level, by team name)
  "box_score": {
    "Team Name": {
      "PG": {...},  // Stats by position
      "SG": {...},
      // ...
    }
  },
  
  // Team totals (aggregated from players)
  "team_totals": {
    "Team Name": {
      "PTS": 85,
      "REB": 42,
      // ... all team totals
    }
  }
}
```

**Key Observations:**
- ✅ **Animations are EXCLUDED** (`exclude_animations=True`) - saves significant space
- ✅ **Turns array is EMPTY** (`turns: []`) - already optimized, turns not saved to database
- ✅ **Full text_log IS included** - needed for play-by-play display
- ✅ **All player game stats included** - needed for rollup
- ✅ **Team strategy/plays/scouting included** in `teams` object - needed for game state persistence

**Size Estimate:** ~50-200KB per game (depending on number of turns)

---

### 2. Computer vs Computer Games (simulated during week completion)

**Location:** `games` collection  
**Document ID:** `"{week}-{away_id}-{home_id}"` (string token)

**Data Saved:** Same structure as user's game, but:
- Generated via `summarize_game_state(gm)` after `run_simulation()`
- Saved with `upsert=True` using token as `_id`
- Also calls `finalize_game()` to rollup stats

---

## After Week Completion (via `/franchise/complete-week`)

### 1. User's Game Stats Rollup

**Location:** `franchises` collection  
**Path:** `franchises.{franchise_id}.players.{player_id}`

**Process:**
1. Find user's game in `games` collection
2. Call `finalize_game(game_id, mode="franchise", franchise_id=franchise_id)`
3. `finalize_game()` reads game from `games` collection
4. Extracts `box_score` and `players` array
5. Increments `franchise.players.{pid}.season.{stat}` for each stat
6. Increments `franchise.players.{pid}.career.{stat}` for each stat
7. Adds `game_id` to `franchise.applied_games` array (prevents double-counting)

**Data Written:**
```javascript
{
  "franchises": {
    "_id": "franchise_id",
    "players": {
      "player_id": {
        "season": {
          "PTS": 450,  // Incremented by game stats
          "REB": 120,
          "AST": 85,
          "GP": 5,  // Games played
          // ... all stats
        },
        "career": {
          "PTS": 1234,  // Incremented by game stats
          // ... all stats
        }
      }
    },
    "applied_games": ["game_id_1", "game_id_2", ...]  // Prevents double-counting
  }
}
```

**Also Calls:**
- `apply_stats_from_summary(game, game_id)` - Writes to universal `players_collection` (legacy/backup)

---

### 2. Computer vs Computer Games Stats Rollup

**Location:** `franchises` collection  
**Path:** Same as user's game

**Process:**
1. For each computer vs computer game:
   - Simulate game via `run_simulation()`
   - Save to `games` collection with token `_id`
   - Call `finalize_game(token, mode="franchise", franchise_id=franchise_id)`
   - Same rollup process as user's game

---

### 3. Week Results Summary

**Location:** `franchises` collection  
**Path:** `franchises.{franchise_id}.results.{week}`

**Data Saved:**
```javascript
{
  "franchises": {
    "_id": "franchise_id",
    "results": {
      "1": [  // Week 1
        {
          "away_id": "team_id",
          "home_id": "team_id",
          "away_score": 85,
          "home_score": 72
        },
        // ... all games in week
      ],
      "2": [ /* Week 2 */ ],
      // ...
    }
  }
}
```

**Size:** ~1-2KB per week (minimal, just scores)

---

### 4. Team Records Update

**Location:** `teams` collection  
**Path:** `teams.{team_id}.record`

**Data Updated:**
```javascript
{
  "teams": {
    "_id": "team_id",
    "record": {
      "W": 5,  // Wins (incremented)
      "L": 2   // Losses (incremented)
    }
  }
}
```

---

## Data Size Analysis

### Per Game (in `games` collection):
- **With animations:** ~500KB - 2MB (excluded in current saves ✅)
- **Without animations:** ~50-200KB (current saves)
- **Turn data:** ~0KB (already excluded ✅ - `turns: []`)
- **Text log:** ~10-20KB (play-by-play text)
- **Player stats:** ~5-10KB (game stats for all players)
- **Box score:** ~5-10KB (by position)
- **Team strategy/plays/scouting:** ~20-50KB (in `teams` object)
- **Player coordinates:** ~1-2KB (x, y for each player)

### Per Week (in `franchises` collection):
- **Player stats rollup:** ~50-100KB (all players, season + career)
- **Results summary:** ~1-2KB (just scores)
- **Total per week:** ~51-102KB

### Per Season (20 weeks):
- **Games collection:** ~1-4MB (20 games × 50-200KB)
- **Franchise document:** ~1-2MB (20 weeks × 51-102KB)
- **Total:** ~2-6MB per season

---

## Potential Optimizations

### 1. Remove Turn Data from `games` Collection ✅

**Current:** Turns array is already empty (`turns: []`) for database saves  
**Status:** ✅ **ALREADY OPTIMIZED** - Turns are not saved to database

**Code Location:** `BackEnd/utils/shared.py:762-763`
```python
if exclude_animations:
    turns = []  # Empty array - don't save turns to database
```

**Impact:**
- ✅ **Already saves ~30-100KB per game** (significant reduction)
- ✅ **Box score still available** (in `box_score` and `team_totals`)
- ✅ **Text log still available** for play-by-play

**Recommendation:** ✅ **ALREADY IMPLEMENTED** - No action needed

---

### 2. Remove Text Log from `games` Collection ❓

**Current:** Full `text_log` array is saved  
**Proposal:** Remove `text_log` array

**Impact:**
- ✅ **Saves ~10-20KB per game**
- ❌ **Cannot display play-by-play** (but can generate from box_score)
- ✅ **Box score has all stat data**

**Recommendation:** **KEEP** - Text log is small and useful for play-by-play display

---

### 3. Store Only Final Box Score (Not Per-Quarter) ❓

**Current:** `points_by_quarter` array saved  
**Proposal:** Remove or simplify

**Impact:**
- ✅ **Saves ~100 bytes per game** (minimal)
- ❌ **Cannot display quarter-by-quarter breakdown**

**Recommendation:** **KEEP** - Minimal size, useful for UI

---

### 4. Remove Player Coordinates (x, y) ❓

**Current:** Player `x` and `y` coordinates saved in `players` array  
**Proposal:** Remove coordinates (only needed during gameplay)

**Impact:**
- ✅ **Saves ~1-2KB per game**
- ✅ **Not needed after game completion**

**Recommendation:** **REMOVE** - Only needed during active gameplay

---

### 5. Store Minimal Game Summary in `games` Collection ❓

**Proposal:** Store only essential data needed for:
- Box score display
- Stats rollup
- Game reference

**Minimal Structure:**
```javascript
{
  "_id": "game_id",
  "franchise_id": "franchise_id",
  "week": 1,
  "home_team": "Team Name",
  "away_team": "Opponent Name",
  "home_score": 85,
  "away_score": 72,
  "box_score": {...},  // Essential for stats
  "players": [...],  // Essential for stats (minimal: just playerId + stats)
  "text_log": [...],  // Useful for play-by-play
  "is_final": true,
  "quarter": 4
  // Remove: turns, team strategy, scouting, coordinates, etc.
}
```

**Impact:**
- ✅ **Saves ~70-80% of current size** (~10-40KB per game vs 50-200KB)
- ✅ **Still has all essential data** for stats rollup and display
- ❌ **Cannot replay game** (but animations already excluded anyway)
- ❌ **Cannot access strategy/plays** (but not needed after game completion)

**Recommendation:** **IMPLEMENT** - Significant space savings with minimal functionality loss

---

## Recommended Database Strategy

### Option A: Minimal Game Storage (Recommended)

**Store in `games` collection:**
- Game metadata (week, teams, scores, final status)
- Box score (by position)
- Player game stats (minimal: playerId + stats only)
- Text log (for play-by-play)
- Remove: turns, coordinates, strategy, scouting, team attributes

**Store in `franchises` collection:**
- Aggregated player stats (season + career)
- Week results summary (scores only)
- Applied games array (prevents double-counting)

**Benefits:**
- ✅ **~70-80% size reduction** per game
- ✅ **All essential data preserved**
- ✅ **Faster queries** (smaller documents)
- ✅ **Lower storage costs**

---

### Option B: Current Approach (Keep Full Data)

**Keep current structure but:**
- ✅ Already excludes animations (good)
- ❌ Still stores turn data (redundant)
- ❌ Still stores coordinates (unnecessary)
- ❌ Still stores strategy/plays (not needed after game)

**Benefits:**
- ✅ Can replay game (but animations excluded anyway)
- ✅ Can access full game state
- ❌ Larger storage footprint

---

## Implementation Notes

### Current Code Locations

1. **Game Save:** `BackEnd/api/api.py:1681` - `games_collection.update_one()`
2. **Game Summary:** `BackEnd/utils/shared.py:507` - `summarize_game_state()`
3. **Stats Rollup:** `BackEnd/utils/stat_updater.py:555` - `finalize_game()`
4. **Week Completion:** `BackEnd/api/franchise_routes.py:306` - `complete_week()`

### Key Functions

- `summarize_game_state(game, exclude_animations=True)` - Creates game summary
- `finalize_game(game_id, mode="franchise", franchise_id=...)` - Rolls up stats
- `apply_stats_from_summary(game, game_id)` - Writes to universal players collection (legacy)

---

## Questions for Review

1. **Do we need turn data after game completion?** ✅ **ALREADY REMOVED** - Turns array is empty
2. **Do we need player coordinates after game completion?** (Recommendation: NO - remove x, y)
3. **Do we need team strategy/plays/scouting after game completion?** (Recommendation: NO - only needed during active gameplay)
4. **Do we need text_log for play-by-play?** (Recommendation: YES, keep it - small and useful)
5. **Should we store minimal game summary?** (Recommendation: YES - remove coordinates, strategy, scouting)

---

## Next Steps

1. Review this document and confirm optimization strategy
2. Implement minimal game storage (if approved)
3. Test stats rollup still works correctly
4. Test box score display still works
5. Monitor database size reduction

