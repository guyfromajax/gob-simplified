# Document Structure Optimization Audit

**Date:** November 5, 2025  
**Status:** Analysis Complete - Optimization Opportunities Identified

---

## Current Document Sizes

| Game Mode | Document Size | Notes |
|-----------|---------------|-------|
| **Single Game** | 168.5 KB | Has redundant data |
| **Tournament** | Varies | Multiple games nested |
| **Franchise** | Varies | Multiple games nested |

---

## 🚨 **Critical Redundancies Found**

### **1. PLAYS DATA - Massive Duplication (75KB waste per game)**

**Problem:** Plays stored in THREE places with different structures:

#### **Location A: `home_team.plays`** ❌ **75KB with embedded skeletons**
```javascript
{
  plays: [  // ❌ Array, not dict
    {
      play_id: "...",
      name: "4-1 Motion",
      skeletons: {  // ❌ Still has full skeletons embedded!
        successful: {...},
        mid_play_change: {...},
        contested: {...},
        broken: {...}
      },
      game_stats: {...}
    }
  ]
}
```
**Source:** `BackEnd/utils/shared.py:612`  
**Issue:** Pulls from `game.home_team.plays.values()` which are in-memory Play objects with embedded skeletons

#### **Location B: `away_team.plays`** ❌ **75KB with embedded skeletons**
Same issue as home_team

#### **Location C: `teams.{team_id}.plays`** ✅ **2KB reference-based (CORRECT)**
```javascript
{
  "4-1 Motion": {
    play_id: "68f919f9...",  // ← Reference only
    name: "4-1 Motion",
    game_stats: {...}
    // NO SKELETONS ✅
  }
}
```
**Source:** `populate_team_plays()` - correctly uses references

**Total Waste:** 75KB + 75KB = **150KB per game** of duplicate play data  
**Impact:** 2 teams × 75KB old + 2 teams × 2KB new = **154KB when we only need 4KB!**

---

### **2. Other Duplications (Small but unnecessary)**

#### **`strategy_settings`** - 88 bytes × 2 = 176 bytes
- In `home_team.strategy_settings`
- In `teams.{team_id}.strategy_settings`

#### **`attributes`** - 287 bytes × 2 = 574 bytes
- In `home_team.attributes`
- In `teams.{team_id}.attributes`

#### **`scouting`** - 991 bytes × 2 = 1,982 bytes
- In `home_team.scouting`
- In `teams.{team_id}.scouting`

**Total small duplications:** ~2.7KB per game (not huge, but unnecessary)

---

## 📊 **What Should Be Where**

### **`teams` Object (by team_id)** - ✅ **Keep This**
**Purpose:** Game state persistence, strategy, play tracking

```javascript
teams: {
  "TEAM_ID_123": {
    strategy_settings: {...},  // Game-specific settings
    plays: {...},              // Play stats (reference-based) ✅
    attributes: {...},         // Team attributes (could be universal?)
    scouting: {...}            // Opponent scouting data
  }
}
```

### **`home_team` / `away_team` Objects** - 🔧 **Needs Cleanup**
**Purpose:** Display data for frontend

```javascript
home_team: {
  // Identification
  name: "Four Corners",
  team_id: "FOUR_CORNERS",
  mascot: "Eagles",
  colors: {...},
  
  // Game state
  score: 97,
  points_by_quarter: [24, 25, 26, 22],
  team_fouls: 5,
  
  // Stats (Frontend display)
  box_score: {...},  // Player stats by position
  totals: {...},     // Team totals
  
  // ❌ REMOVE THESE (already in teams object):
  plays: [...],              // ❌ 75KB duplicate
  strategy_settings: {...},  // ❌ Duplicate
  attributes: {...},         // ❌ Duplicate
  scouting: {...}            // ❌ Duplicate
}
```

**Recommendation:** Remove plays, strategy_settings, attributes, scouting from home_team/away_team

---

## 🎯 **Optimization Recommendations**

### **PRIORITY 1: Remove Plays from home_team/away_team (HIGH IMPACT)**

**File:** `BackEnd/utils/shared.py` lines 612, 637  
**Change:**
```python
# BEFORE
"plays": list(game.home_team.plays.values()),  # ❌ 75KB embedded skeletons

# AFTER
# Remove this line entirely - plays already in teams object
```

**Impact:**
- Single game: 168KB → **93KB** (⬇️ 44% reduction)
- Per game savings: **150KB**
- Tournament with 15 games: **2.25MB savings**
- Franchise with 30 games: **4.5MB savings**

---

### **PRIORITY 2: Remove Other Duplicates (LOW IMPACT)**

**File:** `BackEnd/utils/shared.py` lines 609-611, 634-636  
**Remove:**
```python
"attributes": game.home_team.team_attributes,     # ❌ Duplicate (287 bytes)
"strategy_settings": game.home_team.strategy_settings,  # ❌ Duplicate (88 bytes)
"scouting": game.home_team.scouting_data,         # ❌ Duplicate (991 bytes)
```

**Impact:** ~2.7KB per game (minimal but cleaner structure)

---

### **PRIORITY 3: Player Data Optimization (FUTURE)**

**Current:** Each game embeds full player data (11 players × 341 bytes = 3.7KB)

**Potential Optimization:**
```javascript
// CURRENT (Embedded)
players: [
  {
    playerId: "uuid",
    name: "John Smith",
    pos: "PG",
    jersey: 23,
    photo: "/static/...",
    team: "home",
    team_id: "FOUR_CORNERS",
    x: 50, y: 25,
    attributes: { EM: 7, CH: 6, MO: 8, NG: 0.9 },
    primary_color: "#...",
    secondary_color: "#..."
  }
]

// OPTIMIZED (Reference + Game Data)
players: [
  {
    player_ref: "uuid",  // ← Reference to universal players_collection
    team: "home",        // ← Game-specific
    x: 50, y: 25,        // ← Game-specific (current position)
    runtime_attrs: { EM: 7, CH: 6, MO: 8, NG: 0.9 }  // ← Simplified for runtime
  }
]
```

**Savings:** ~250 bytes per player × 11 = ~2.7KB per game  
**Complexity:** Higher - requires fetching from players_collection during game load  
**Recommendation:** **Not worth it** - savings too small vs complexity added

---

## 🎯 **Recommended Actions**

### **Immediate (Do Now):**
1. ✅ Remove `plays` from `home_team` / `away_team` objects (**150KB savings per game**)
2. ✅ Remove `strategy_settings`, `attributes`, `scouting` from `home_team` / `away_team` (**2.7KB savings**)
3. ✅ Update frontend to read from `teams` object instead of `home_team`/`away_team`

**Total Impact:** ~153KB reduction per game (90% of bloat eliminated!)

### **Future (Consider Later):**
- ❌ Player reference system - too complex for minimal savings (~2.7KB)
- ✅ Keep current player embedding - it's efficient enough

---

## 📐 **Proposed Clean Structure**

### **Single Game Document (After Optimization):**

```javascript
{
  // Game metadata
  game_id: "uuid",
  quarter: 4,
  is_final: true,
  opening_tip_winner: "Four Corners",
  
  // Team IDs (for quick lookup)
  home_team_id: "FOUR_CORNERS",
  away_team_id: "BENTLEY_TRUMAN",
  
  // Frontend display data ONLY
  home_team: {
    name: "Four Corners",
    team_id: "FOUR_CORNERS",
    mascot: "Eagles",
    colors: {...},
    score: 97,
    points_by_quarter: [24, 25, 26, 22],
    team_fouls: 5,
    box_score: {...},  // Player stats
    totals: {...}      // Team totals
    // ✅ NO plays, strategy_settings, attributes, scouting
  },
  
  away_team: { /* same structure */ },
  
  // Game state persistence (the source of truth)
  teams: {
    "FOUR_CORNERS": {
      strategy_settings: {...},
      plays: {...},        // Reference-based
      attributes: {...},
      scouting: {...}
    },
    "BENTLEY_TRUMAN": { /* same */ }
  },
  
  // Players (runtime positions)
  players: [...],  // Keep as-is (3.7KB is fine)
  
  // Game data
  turns: [],       // Empty for saves
  text_log: [...]
}
```

**Result:** 168KB → **~15KB** (⬇️ 91% reduction!)

---

## 🔧 **Implementation Steps**

1. Update `BackEnd/utils/shared.py`:
   - Remove plays from home_team_data (line 612)
   - Remove plays from away_team_data (line 637)
   - Optionally remove strategy_settings, attributes, scouting

2. Verify frontend doesn't rely on home_team.plays:
   - Check if anything reads from these fields
   - Update to use teams object instead

3. Migration script:
   - Remove plays/strategy/attributes/scouting from existing home_team/away_team objects
   - Clean up 25 single games + tournament/franchise nested games

---

## 💾 **Storage Impact**

| Scenario | Current | After Optimization | Savings |
|----------|---------|-------------------|---------|
| Single game | 168.5 KB | ~15 KB | 91% |
| Tournament (15 games) | ~2.5 MB | ~225 KB | 91% |
| Franchise (30 games) | ~5 MB | ~450 KB | 91% |

With 50 plays at 20 skeletons each, you'd STILL be under 1MB per tournament!

---

## ⚠️ **Why home_team.plays Still Has Skeletons**

The migration cleaned the **database**, but `summarize_game_state()` pulls from **in-memory** `game.home_team.plays` which has Play objects with skeletons. Every new save re-embeds them!

**Fix:** Don't include plays in home_team/away_team at all.

---

**Want me to implement these optimizations?**

