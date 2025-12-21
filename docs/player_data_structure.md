# Player Data Structure - Universal vs Bespoke

**Date:** November 5, 2025  
**Approach:** Option A (Minimal - Keep game instance as-is, track evolution in franchise)

---

## Overview

Player data exists in **four contexts**:
1. **Universal Collection** - Baseline/permanent data (players_collection)
2. **Game Instance** - Runtime snapshot (game.players array)
3. **Franchise Instance** - Evolving data (franchise.players object)
4. **Tournament Instance** - Evolving data (tournament.player_stats object) - **Unified with Franchise architecture**

---

## 1. Universal Players Collection (MongoDB)

**Purpose:** Single source of truth for player baseline data

**Collection:** `players_collection`

### Structure:

```javascript
{
  "_id": "uuid",  // ✅ Primary key (use this everywhere)
  // ❌ "player_id": "uuid"  // REDUNDANT - should be removed (same as _id)
  
  // ==================== BIO (Immutable) ====================
  "first_name": "CJ",
  "last_name": "Castleman",
  "team": "Bentley-Truman",  // Home school
  "jersey": 44,
  "year": "senior",          // Starting year
  "height": 76,              // Inches (probably doesn't change)
  "weight": 218,             // Pounds (probably doesn't change)
  "photo": "/static/images/players/uuid.png",
  
  // ==================== BASELINE ATTRIBUTES (30+ attributes) ====================
  "attributes": {
    // Shooting
    "SC": 75,  // Scoring
    "SH": 70,  // Shooting
    "FT": 68,  // Free Throws
    "3PT": 72, // Three Point (if exists)
    
    // Defense
    "ID": 65,  // Interior Defense
    "OD": 70,  // On-ball Defense
    
    // Playmaking
    "PS": 60,  // Passing
    "BH": 75,  // Ball Handling
    "IQ": 80,  // Basketball IQ
    
    // Physical
    "AG": 85,  // Agility
    "ST": 70,  // Strength
    "RB": 72,  // Rebounding
    
    // Intangibles
    "ND": 6,   // No Dumb fouls
    "CH": 5,   // Clutch (randomized per game)
    "EM": 7,   // Energy/Momentum (randomized per game)
    "MO": 8,   // Moxie (randomized per game)
    
    // Anchors (for training - stores trained values)
    "anchor_SC": 75,
    "anchor_SH": 70,
    // ... all other anchor values
    
    // Energy
    "NG": 1.0  // Current energy level (0.0-1.0)
  },
  
  // ==================== POSITION RATINGS ====================
  "position_ratings": {
    "PG": 65,
    "SG": 80,
    "SF": 90,  // Best position
    "PF": 70,
    "C": 50
  },
  
  // ==================== STATS (Career/Season Tracking) ====================
  "stats": {
    "game": {},  // Always empty in universal (reset each game)
    "season": {  // Current season totals
      "PTS": 123,
      "REB": 45,
      "AST": 23,
      // ... all stats
    },
    "career": {  // All-time totals
      "PTS": 1234,
      "REB": 456,
      "AST": 234,
      // ... all stats
    },
    "applied_games": []  // Game IDs that have been applied to stats
  },
  
  // ==================== METADATA ====================
  "metadata": {
    "fouls": 0,           // Per-game (reset each game)
    "minutes_played": 0,  // Per-game (reset each game)
    "abilities": {}       // TBD - what is this?
  }
}
```

**Size:** ~1,600 bytes per player

---

## 2. Game Instance Players Array (Runtime Snapshot)

**Purpose:** Lightweight runtime data for animation/display

**Location:** `game_document.players` array

### Structure:

```javascript
{
  "playerId": "uuid",  // Reference to universal _id
  
  // Runtime assignments
  "name": "CJ Castleman",  // Derived from first_name + last_name
  "team": "home",          // Which side in THIS game
  "team_id": "BENTLEY_TRUMAN",
  "pos": "SF",             // Position in THIS game
  
  // Display (from team)
  "primary_color": "#c0976a",
  "secondary_color": "#00954b",
  "photo": "/static/images/players/uuid.png",
  "jersey": 44,
  
  // Runtime position (animation)
  "x": 50,
  "y": 25,
  
  // Simplified attributes (runtime only - NOT persisted to DB after game)
  "attributes": {
    "EM": 7,   // Randomized per game
    "CH": 6,   // Randomized per game
    "MO": 8,   // Randomized per game
    "NG": 0.9  // Energy level (depletes during game)
  }
}
```

**Size:** ~350 bytes per player  
**Total for 11 players:** ~3.7KB (minimal, not worth optimizing)

**Note:** This array is generated at runtime for animation. Stats are tracked in box_score separately.

---

## 3. Franchise Players Object (Evolving Data)

**Purpose:** Track player growth/evolution throughout franchise mode

**Location:** `franchise_document.players`

### Structure:

```javascript
{
  "uuid": {  // Keyed by player _id
    // ==================== META (Reference Data) ====================
    "meta": {
      "first_name": "CJ",
      "last_name": "Castleman",
      "team": "Bentley-Truman",
      "team_id": "BENTLEY_TRUMAN"
    },
    
    // ==================== EVOLVED ATTRIBUTES ====================
    "attributes": {
      "SC": 78,  // Improved from 75 via training
      "SH": 73,  // Improved from 70 via training
      "IQ": 82,  // Improved from 80 via training
      // ... all attributes (evolved from universal baseline)
      
      // Anchors track trained values
      "anchor_SC": 78,
      "anchor_SH": 73,
      // ...
      
      // Game attributes (randomized per game)
      "EM": 7,
      "CH": 6,
      "MO": 8,
      "NG": 1.0
    },
    
    // ==================== EVOLVED POSITION RATINGS ====================
    "position_ratings": {
      "PG": 70,  // Improved from 65 via training
      "SG": 85,  // Improved from 80 via training
      "SF": 92,  // Improved from 90 via training
      "PF": 72,  // Improved from 70 via training
      "C": 55    // Improved from 50 via training
    },
    
    // ==================== SEASON STATS ====================
    "season": {
      "PTS": 450,
      "REB": 120,
      // ... season totals
    },
    
    // ==================== CAREER STATS ====================
    "career": {
      "PTS": 1234,
      "REB": 456,
      // ... career totals (accumulated)
    }
  }
}
```

**How Evolution Works:**
1. **Franchise starts:** Clone from universal collection
2. **Training session:** Update `attributes.anchor_X` values
3. **Games:** Use evolved attributes from franchise doc
4. **Season ends:** Attributes carry over to next season

---

## 4. Tournament Players Object (Evolving Data)

**Purpose:** Track player growth/evolution throughout tournament mode (unified with Franchise architecture)

**Location:** `tournament_document.player_stats`

### Structure:

```javascript
{
  "player_stats": {
    "uuid": {  // Keyed by player _id
      "first_name": "CJ",
      "last_name": "Castleman",
      "team": "Bentley-Truman",
      
      // ==================== EVOLVED ATTRIBUTES ====================
      "attributes": {
        "SC": 78,  // Improved from 75 via training
        "SH": 73,  // Improved from 70 via training
        "IQ": 82,  // Improved from 80 via training
        // ... all attributes (evolved from universal baseline)
        
        // Anchors track trained values
        "anchor_SC": 78,
        "anchor_SH": 73,
        // ...
        
        // Game attributes (randomized per tournament)
        "EM": 7,
        "CH": 6,
        "MO": 8,
        "NG": 1.0
      },
      
      // ==================== SEASON STATS ====================
      "season": {
        "PTS": 450,
        "REB": 120,
        // ... season totals (tournament-specific)
      }
    }
  }
}
```

**How Evolution Works:**
1. **Tournament starts:** Clone ALL attributes from universal collection (not just EM, CH, MO)
2. **Training session:** Update `attributes.anchor_X` values
3. **Games:** Use evolved attributes from tournament doc
4. **Tournament ends:** Attributes don't carry over to new tournaments

**Unified Architecture:**
- Tournament mode now uses the same attribute storage pattern as Franchise mode
- All attributes are stored in the tournament document (not just EM, CH, MO)
- This enables consistent training and attribute evolution across both modes
- **Backward Compatibility:** Old tournaments that only have EM, CH, MO are automatically merged with core collection when accessed

---

## Field-by-Field Breakdown

| Field | Universal | Game Instance | Franchise | Tournament | Notes |
|-------|-----------|---------------|-----------|------------|-------|
| **_id / playerId** | ✅ _id | ✅ playerId | ✅ Key | ✅ Key | Same UUID everywhere |
| **player_id** | ❌ Remove | ❌ | ❌ | ❌ | Redundant (same as _id) |
| **first_name** | ✅ | Derived→name | Meta | |
| **last_name** | ✅ | Derived→name | Meta | |
| **team** | ✅ School | ✅ Side (home/away) | Meta | Different meaning! |
| **team_id** | | ✅ Current team | Meta | |
| **jersey** | ✅ | ✅ | Meta | |
| **year** | ✅ Starting | | Evolves | Fr→So→Jr→Sr |
| **height** | ✅ | | (Meta?) | Probably static |
| **weight** | ✅ | | (Meta?) | Probably static |
| **photo** | ✅ Path | ✅ Path | | Never changes |
| **attributes** | ✅ Baseline (30+) | ✅ Runtime (4) | ✅ Evolved | |
| **position_ratings** | ✅ Baseline | | ✅ Evolved | Improve with training |
| **stats.game** | ✅ Empty | | | Reset each game |
| **stats.season** | ✅ Current | | ✅ Franchise | |
| **stats.career** | ✅ Lifetime | | ✅ Franchise | |
| **metadata.fouls** | ✅ Reset | | | Per-game |
| **metadata.minutes** | ✅ Reset | | | Per-game |
| **metadata.abilities** | ✅ ? | | | TBD |
| **pos** | | ✅ | | Which position THIS game |
| **x, y** | | ✅ | | Court position (runtime) |
| **primary_color** | | ✅ | | From team (runtime) |
| **secondary_color** | | ✅ | | From team (runtime) |

---

## Current Implementation Status

### ✅ **Already Working:**
- Single games pull from universal collection ✅
- Franchise mode tracks evolution in `franchise.players` ✅
- Training updates franchise player attributes ✅
- Game instance players array is lean (3.7KB) ✅

### 🔧 **Cleanup Needed:**
- ❌ Remove `player_id` field from universal collection (redundant with `_id`)
- ✅ Document the structure (this document)

---

## Optimization Impact

### **Current State:**
- Universal collection: 1,600 bytes/player (has redundant player_id)
- Game instance: 350 bytes/player (already lean)
- Franchise instance: Varies (tracks evolution)

### **After Removing player_id:**
- Universal collection: 1,560 bytes/player (⬇️ 40 bytes)
- 8 teams × 13 players = 104 players × 40 bytes = **4KB savings** in universal collection

**Recommendation:** Remove `player_id` redundancy but **keep game instance structure as-is** (already optimal).

---

## Migration Plan (Optional)

If you want to remove `player_id` redundancy:

1. **Update code to use `_id` instead of `player_id`** everywhere
2. **Migration script:** `$unset player_id` from all players
3. **Benefits:** Cleaner structure, 4KB universal collection savings

**However:** This is low priority since player_id is only ~40 bytes per player and code likely uses it extensively.

---

## Summary

✅ **Structure is already well-optimized for Option A:**
- Universal collection has baseline data
- Game instances are lean (3.7KB for 11 players)
- Franchise mode tracks evolution
- No major optimizations needed

✅ **Only cleanup:** Remove `player_id` redundancy (optional, minimal impact)

---

**Your player architecture is solid!** The game instance players array at 3.7KB is totally fine and not worth complicating with references.

