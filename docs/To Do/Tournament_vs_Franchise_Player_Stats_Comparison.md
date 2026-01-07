# Tournament vs Franchise Player Stats Flow Comparison

## Overview
This document compares how Tournament and Franchise modes initialize, maintain, and save player stats to identify gaps causing Tournament mode stats to remain at zero.

---

## 1. INITIALIZATION (When Mode is Created)

### Franchise Mode (`initialize_season()`)
**Location:** `BackEnd/models/franchise_manager.py:109-164`

**Process:**
1. Loads **ALL players from ALL teams** in the database
2. For each player:
   - Creates `meta` object with `first_name`, `last_name`, `team`, `team_id`
   - Initializes `season: zero_stats.copy()` (all stat keys = 0)
   - Preserves `career` stats from previous season (if exists)
   - Clones and randomizes `attributes` (EM, CH, MO)
   - Clones `position_ratings`
3. Saves entire `players_map` to `franchise.players` in one operation

**Result:** All players from all 8 teams are initialized with complete structure:
```python
players[playerId] = {
    "meta": {...},
    "season": {PTS: 0, REB: 0, ...},  # All stat keys initialized
    "career": {...},
    "attributes": {...},
    "position_ratings": {...}
}
```

### Tournament Mode (`create_tournament()`)
**Location:** `BackEnd/tournament/tournament_manager.py:36-178`

**Process:**
1. Loads **ALL players from the 8 teams in the tournament** (filtered by `{"team": {"$in": teams}}`)
2. For each player:
   - Creates `meta` object with `first_name`, `last_name`, `team`, `team_id`
   - Initializes `season: zero_stats.copy()` (all stat keys = 0)
   - **NO career stats** (tournament-only mode)
   - Clones and randomizes `attributes` (EM, CH, MO)
   - Clones `position_ratings`
3. Saves entire `players_dict` to `tournament.players` in one operation

**Result:** All players from the 8 tournament teams are initialized with complete structure:
```python
players[playerId] = {
    "meta": {...},
    "season": {PTS: 0, REB: 0, ...},  # All stat keys initialized
    "attributes": {...},
    "position_ratings": {...}
}
```

**✅ Status:** Both modes initialize players correctly during creation.

---

## 2. DURING GAMEPLAY

### Both Modes
- Use same `init_game()` endpoint
- Use same `simulate-quarter` endpoint
- Use same game state management
- Players are loaded from `players_collection` (universal), not from mode-specific documents

**✅ Status:** No differences - both modes work identically during gameplay.

---

## 3. AFTER GAME COMPLETION (Stat Saving)

### Franchise Mode (`finalize_game()`)
**Location:** `BackEnd/utils/stat_updater.py:1165-1595`

**Process:**
1. **Loads game document** from `games_collection`
2. **Extracts `box_score`** from game document (nested under `home_team.box_score` and `away_team.box_score`)
3. **Processes ALL players from `box_score`**:
   - Iterates through `box_score[team_name][position]` for each team
   - Builds `inc_doc` with `$inc` operations: `players.{playerId}.season.{stat}`
   - Builds `set_doc` with `$set` operations: `players.{playerId}.meta.team_id`
4. **Checks existing players** in franchise document
5. **Initializes missing players** using `$setOnInsert`:
   ```python
   set_on_insert_doc[f"players.{pid_str}"] = {
       "meta": {...},
       "season": zero_stats.copy(),
       "career": zero_stats.copy(),
       "attributes": {...},
       "position_ratings": {...}
   }
   ```
6. **Single MongoDB update** with:
   - `$addToSet: {applied_games: game_id}` (idempotency)
   - `$inc: inc_doc` (stat increments)
   - `$set: set_doc` (meta updates)
   - `$setOnInsert: set_on_insert_doc` (initialize missing players)
7. **Query filter:** `{"_id": fid, "applied_games": {"$ne": game_id}}`

**Key Features:**
- ✅ Uses `$setOnInsert` to handle missing players automatically
- ✅ Single atomic update operation
- ✅ Simple query filter (just checks `applied_games`)
- ✅ Processes ALL players from `box_score` (lineup + bench)

### Tournament Mode (`finalize_game()` → `apply_stats_from_summary()`)
**Location:** `BackEnd/utils/stat_updater.py:1083-1163` (finalize_game) and `115-352` (apply_stats_from_summary)

**Process:**
1. **Loads game document** from `games_collection`
2. **Calls `apply_stats_from_summary(game, game_id, tournament_id)`**
3. **Inside `apply_stats_from_summary()`:**
   - Extracts `box_score` from game document
   - Processes players from `box_score` one at a time
   - For each player:
     - **Checks if player exists** in tournament document (line 210-216)
     - **If player doesn't exist:** Initializes with `$setOnInsert` (line 299-311) - **RECENT FIX**
     - **Builds `tournament_inc_doc`** with `$inc` operations: `players.{playerId}.season.{stat}`
     - **Builds `tournament_update`** with `$inc` and `$set` operations
     - **Complex query filter** with `$or`:
       ```python
       {
           "_id": tid,
           "$or": [
               {f"players.{playerId}.season.applied_games": {"$exists": False}},
               {f"players.{playerId}.season.applied_games": {"$nin": [token]}}
           ]
       }
       ```
     - **Per-player update** (one MongoDB operation per player)
4. **After all players processed:** Calls `_ensure_all_roster_players_initialized()` to initialize bench players

**Key Features:**
- ⚠️ **Complex query filter** requires `players.{playerId}.season.applied_games` path to exist or be evaluable
- ⚠️ **Per-player updates** (multiple MongoDB operations, not atomic)
- ⚠️ **Idempotency check** is per-player (checks `season.applied_games` array)
- ✅ Processes ALL players from `box_score` (lineup + bench)
- ✅ Initializes missing players (recent fix)

---

## 4. KEY DIFFERENCES & GAPS

### Gap #1: Update Query Complexity
**Franchise:** Simple query - just checks `applied_games` at document level
```python
{"_id": fid, "applied_games": {"$ne": game_id}}
```

**Tournament:** Complex query - requires nested path to exist
```python
{
    "_id": tid,
    "$or": [
        {f"players.{playerId}.season.applied_games": {"$exists": False}},
        {f"players.{playerId}.season.applied_games": {"$nin": [token]}}
    ]
}
```

**Problem:** If `players.{playerId}.season` doesn't exist, MongoDB can't evaluate the `$exists: False` check on `applied_games`, causing the query to fail silently.

**Solution:** Recent fix initializes players BEFORE updating, but this is a workaround. Better solution would be to match Franchise pattern.

### Gap #2: Update Atomicity
**Franchise:** Single atomic update for all players
- One MongoDB operation
- All-or-nothing (if one player fails, entire update fails)

**Tournament:** Multiple updates (one per player)
- N MongoDB operations (where N = number of players)
- Partial failures possible (some players update, others don't)

**Problem:** If one player's update fails, others may still succeed, leading to inconsistent state.

### Gap #3: Idempotency Check Location
**Franchise:** Document-level idempotency (`applied_games` array at document root)
- Simple check: `applied_games: {"$ne": game_id}`
- Easy to verify and debug

**Tournament:** Player-level idempotency (`applied_games` array per player in `season`)
- Complex check: `players.{playerId}.season.applied_games: {"$nin": [token]}`
- Requires nested path to exist
- Harder to verify and debug

### Gap #4: Player Initialization Strategy
**Franchise:** Uses `$setOnInsert` in the same update operation
- Atomic: Initialize and update in one operation
- MongoDB handles "if not exists" automatically

**Tournament:** Initializes players BEFORE updating (recent fix)
- Two-step process: Initialize, then update
- Race condition possible between steps
- More complex code

---

## 5. RECOMMENDED FIXES

### Fix #1: Match Franchise Pattern for Update Query
**Current (Tournament):**
```python
result = tournaments_collection.update_one(
    {
        "_id": tid,
        "$or": [
            {f"players.{str(query_pid)}.season.applied_games": {"$exists": False}},
            {f"players.{str(query_pid)}.season.applied_games": {"$nin": [token]}}
        ]
    },
    tournament_update,
)
```

**Recommended (Match Franchise):**
```python
# Use document-level applied_games check (like Franchise)
result = tournaments_collection.update_one(
    {"_id": tid, "applied_games": {"$ne": game_id}},
    tournament_update,
)
```

### Fix #2: Use Single Atomic Update (Like Franchise)
**Current (Tournament):** Per-player updates in a loop

**Recommended:** Build all increments in one `inc_doc`, then single update:
```python
# Build inc_doc for ALL players (like Franchise does)
inc_doc = {}
for player in all_players:
    for stat, val in player_stats.items():
        inc_doc[f"players.{playerId}.season.{stat}"] = val

# Single atomic update
result = tournaments_collection.update_one(
    {"_id": tid, "applied_games": {"$ne": game_id}},
    {
        "$inc": inc_doc,
        "$set": set_doc,
        "$setOnInsert": set_on_insert_doc,
        "$addToSet": {"applied_games": game_id}
    }
)
```

### Fix #3: Use `$setOnInsert` for Player Initialization
**Current (Tournament):** Initialize players before updating (two-step)

**Recommended:** Use `$setOnInsert` in the same update (like Franchise):
```python
update = {
    "$inc": inc_doc,
    "$set": set_doc,
    "$setOnInsert": {
        f"players.{playerId}": {
            "meta": {...},
            "season": zero_stats.copy(),
            ...
        }
    },
    "$addToSet": {"applied_games": game_id}
}
```

---

## 6. SUMMARY

**Root Cause:** Tournament mode uses a more complex, per-player update pattern that:
1. Requires nested paths to exist for query filters
2. Uses multiple MongoDB operations (not atomic)
3. Has complex idempotency checks per player

**Franchise mode works because:**
1. Simple document-level query filter
2. Single atomic update operation
3. Uses `$setOnInsert` for automatic player initialization

**Recommended Action:** Refactor Tournament mode's `apply_stats_from_summary()` to match Franchise mode's pattern in `finalize_game()` - use single atomic update with `$setOnInsert` and document-level `applied_games` check.

