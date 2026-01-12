# Database Normalization vs Projections Analysis

**Date Created:** January 11, 2026  
**Status:** 🔍 DISCUSSION  
**Priority:** 🟡 MEDIUM  
**Related:** Task 2 (Database Optimization) from Go Live Plan

## Proposed Approach: Separate Collections

**Idea:** Create separate collections:
- `game_players` - Player data for each game (keyed by `game_id`)
- `game_teams` - Team data for each game (keyed by `game_id`)

**Benefits:**
- Smaller game documents (faster to load)
- Can query players/teams independently
- Can delete game_players/game_teams after game ends
- Better for scaling

**Tradeoffs:**
- More complex queries (need to fetch multiple documents)
- More database round trips (potential N+1 problem)
- Transaction complexity (consistency issues)
- More code complexity

---

## Analysis: When Normalization Makes Sense

### ✅ **Normalization IS Good When:**
1. **Documents are too large** (>1MB) - MongoDB has 16MB limit
2. **Different access patterns** - Some queries need players, others don't
3. **High write frequency** - Updating players doesn't require updating game doc
4. **Need to query across games** - "Find all players who scored 20+ in any game"
5. **Lifecycle differences** - Players/teams deleted after game, game doc kept

### ❌ **Normalization IS NOT Good When:**
1. **Documents are manageable** (<500KB) - Current issue is loading speed, not size
2. **Always need together** - Lineup screen always needs players + game state
3. **Atomic updates needed** - Need to update players + game state together
4. **Simple access patterns** - Most queries need the same data
5. **Performance is query-based** - Problem is loading too much, not document size

---

## Current Situation Analysis

### What We Actually Need:

**Lineup Screen:**
- Player energy (`players[].attributes.NG`)
- Player stats (`players[].stats`)
- Player attributes (`players[].attributes.EM`, `players[].attributes.MO`)
- Ineligible players (`ineligible_players`)
- **NOT needed:** Full game state, all team data, text_log

**Playbooks Screen:**
- Team playbook settings (`teams[team_id].playbook_settings`)
- **NOT needed:** Players, game state, stats

**Game Plan Screen:**
- Team strategy settings (`teams[team_id].strategy_settings`)
- **NOT needed:** Players, game state, stats

**Box Score Screen:**
- Player stats (`players[].stats`)
- Team totals (`teams[team_id].totals`)
- **NOT needed:** Full game state, plays, scouting

### Current Problem:
- Loading **ENTIRE** game document (500KB) when we only need **10-50KB**
- **Solution:** Use projections to only load what's needed

---

## Comparison: Projections vs Normalization

### Approach 1: Projections (Simpler, Lower Risk) ✅ RECOMMENDED FIRST

**How it works:**
```python
# Lineup screen - only load what's needed
saved = games_collection.find_one(
    {"_id": game_id},
    {
        "players": 1,           # Only players array
        "ineligible_players": 1, # Fouled out players
        "quarter": 1,           # Current quarter
        "_id": 1
    }
)
```

**Pros:**
- ✅ **Simple** - Just add projection parameter
- ✅ **Low risk** - No schema changes
- ✅ **Fast to implement** - 1-2 hours
- ✅ **High impact** - 80-95% reduction in data transfer
- ✅ **No code complexity** - Same query pattern, just limit fields
- ✅ **Atomic** - Still single document, single query

**Cons:**
- ⚠️ Still loading some unnecessary data (but much less)
- ⚠️ Document still grows (but we're not loading it all)

**Expected Improvement:**
- Lineup screen: 500KB → 10-50KB (90-98% reduction)
- Playbooks screen: 500KB → 5-10KB (98% reduction)
- Game Plan screen: 500KB → 5-10KB (98% reduction)

---

### Approach 2: Normalization (More Complex, Higher Risk) ⚠️ CONSIDER LATER

**How it works:**
```python
# Load game document (lightweight)
game = games_collection.find_one({"_id": game_id}, {"quarter": 1, "is_final": 1})

# Load players separately
players = game_players_collection.find({"game_id": game_id})

# Load teams separately
teams = game_teams_collection.find({"game_id": game_id})
```

**Pros:**
- ✅ **Smallest documents** - Game doc ~1-2KB, players ~10-20KB, teams ~5-10KB
- ✅ **Can delete after game** - Clean up game_players/game_teams
- ✅ **Better for scaling** - Can query players across games
- ✅ **Independent updates** - Update players without touching game doc

**Cons:**
- ❌ **More complex** - Need to manage 3 collections
- ❌ **More queries** - 3 queries instead of 1 (3x network round trips)
- ❌ **Transaction complexity** - What if one save fails?
- ❌ **Code complexity** - Need to handle joins, consistency
- ❌ **Higher risk** - Schema changes, migration needed
- ❌ **More time** - 8-16 hours to implement properly

**Expected Improvement:**
- Lineup screen: 500KB → 10-20KB (96-98% reduction)
- But: 3 queries instead of 1 (slower if network latency is high)

---

## Network Latency Impact

**Current (No Projection):**
- 1 query × 500KB × 100ms = 500ms

**With Projections:**
- 1 query × 10KB × 100ms = 10ms (50x faster!)

**With Normalization:**
- 3 queries × 10KB × 100ms = 30ms (16x faster, but 3x more queries)

**In production (higher latency):**
- Current: 1 query × 500KB × 200ms = 200ms
- Projections: 1 query × 10KB × 200ms = 20ms (10x faster!)
- Normalization: 3 queries × 10KB × 200ms = 60ms (3.3x faster, but 3x more queries)

**Key Insight:** In high-latency environments (production), **fewer queries is better**, even if each query is smaller.

---

## Recommendation: Try Projections First ✅

### Phase 1: Add Projections (1-2 hours, Low Risk)
1. Add projections to `/api/game/{game_id}` endpoint
2. Test and measure improvement
3. If 80-95% improvement is enough → **Done!**

### Phase 2: If Still Needed, Consider Normalization (8-16 hours, Higher Risk)
1. Only if projections don't solve the problem
2. Only if documents are still too large (>1MB)
3. Only if we need to query across games
4. Only if we need independent lifecycle management

---

## When Normalization Makes Sense

**Consider normalization if:**
1. ✅ Documents exceed 1MB (approaching 16MB limit)
2. ✅ Need to query players across multiple games
3. ✅ Need to delete game_players/game_teams after game ends
4. ✅ High write frequency (updating players frequently)
5. ✅ Different access patterns (some queries need players, others don't)

**Current situation:**
- Documents are ~500KB (well under 1MB limit)
- Most queries need players + game state together
- Low write frequency (save every 25 turns)
- Similar access patterns (lineup, playbooks, game plan all need different subsets)

**Conclusion:** **Projections are the right first step.** Normalization could be considered later if needed.

---

## Your Idea is Valid! But...

**Your normalization idea is actually a good database design pattern!** It's called "referencing" vs "embedding" in MongoDB terminology.

**However:**
- It's more complex than needed right now
- Projections will solve 80-95% of the problem with 10% of the effort
- We can always normalize later if projections aren't enough
- "Make it work, then make it better" - projections first, normalize if needed

**Think of it like this:**
- **Projections** = "Don't load what you don't need" (simple, fast, low risk)
- **Normalization** = "Store separately so you can load independently" (complex, slower queries, higher risk)

---

## Next Steps

1. **Implement projections** (1-2 hours)
2. **Test and measure** (30 minutes)
3. **If still slow:** Investigate other bottlenecks (connection pool, memory leaks)
4. **If still slow AND documents >1MB:** Consider normalization

**Your idea is good, but let's try the simpler solution first!**

