# Franchise Mode Architecture

**Date:** November 5, 2025  
**Purpose:** Document how games, recruits, and training are handled in franchise mode

---

## Overview

Franchise mode uses a **hybrid storage approach**:
- **Franchise document** → Season state, player evolution, team stats
- **Games collection** → Active game data (primary storage)
- **Training log collection** → Historical training sessions

---

## 1. GAMES Storage (Dual System)

### **Primary: games_collection (During Active Play)**

**When:** User plays their game or CPU simulates games  
**Where:** `games_collection` (separate collection)

**Structure:**
```javascript
// games_collection document
{
  "_id": "{week}-{team1_id}-{team2_id}",  // Composite key
  "team1_id": ObjectId("..."),
  "team2_id": ObjectId("..."),
  "team1_score": 97,
  "team2_score": 86,
  "week": 3,
  
  // Full game data (with teams, players, box_score, etc.)
  "teams": {...},
  "home_team": {...},
  "away_team": {...},
  "players": [...],
  "text_log": [...]
  // NO turns (animations excluded)
}
```

**Code:** `franchise_routes.py:316`
```python
summary = summarize_game_state(gm)
token = f"{req.week}-{away_id}-{home_id}"
summary["_id"] = token
db.games.update_one({"_id": token}, {"$set": summary}, upsert=True)
```

---

### **Secondary: franchise.games (Nested, Optional)**

**When:** Can also be saved nested in franchise doc  
**Where:** `franchise_document.games.week_X.{game_id}`

**Structure:**
```javascript
// franchise_document
{
  "_id": ObjectId("franchise_id"),
  "games": {
    "week_1": {
      "game_id_1": { /* full game data */ },
      "game_id_2": { /* full game data */ }
    },
    "week_2": {
      "game_id_3": { /* full game data */ }
    }
  }
}
```

**Code:** `api.py:258-263`
```python
update_path = f"games.week_{week}.{game_id}"
franchises_collection.update_one(
    {"_id": ObjectId(doc_id)},
    {"$set": {update_path: game_data}},
    upsert=True
)
```

**Note:** Most franchises use games_collection (primary). Nested structure is optional/alternative.

---

### **Results Tracking**

**Where:** `franchise_document.results.{week_number}`

**Structure:**
```javascript
{
  "results": {
    "1": [  // Week 1 results
      {
        "away_id": "team_uuid",
        "home_id": "team_uuid",
        "away_score": 97,
        "home_score": 86
      },
      // ... more games
    ],
    "2": [  // Week 2 results
      // ...
    ]
  }
}
```

**Purpose:** Quick summary of who played whom and scores (doesn't store full game data)

---

## 2. RECRUITS (Hybrid: Template Pool + Nested)

### **Architecture: Template Pool Pattern**

**Two Storage Locations:**

1. **`recruits_collection`** (Standalone) → Universal template pool
2. **`franchise_document.recruits`** (Nested) → Franchise-specific pool

---

### **A. Template Collection (recruits_collection)**

**Purpose:** Universal template pool / seed data

**Structure:**
```javascript
// recruits_collection
{
  "_id": ObjectId("..."),  // Has MongoDB _id
  "name": "Henry Buchanan",
  "attributes": {
    "SC": 37,
    "SH": 40,
    // ... all attributes
  },
  "position_ratings": { "PG": 18, "SG": 20, ... },
  "height": 73,
  "weight": 197,
  "archetype": "Three & D",
  "year": "Freshman",
  "created_at": "2025-10-14 23:32:31"
}
// ... 40 template recruits
```

**Usage:**
- Created once (seed data)
- Read **only** when franchise is created
- Cloned into `franchise.recruits`
- **Never modified** during gameplay

**Size:** ~20KB (40 recruits × ~500 bytes)

---

### **B. Nested in Franchise (franchise.recruits)**

**Where:** `franchise_document.recruits` (array)

**Structure:**
```javascript
{
  "recruits": [
    {
      "name": "Jarrell Heath",
      "attributes": {
        "SC": 30,
        "SH": 35,
        "ID": 34,
        // ... all 13 base attributes
      },
      "position_ratings": {
        "PG": 20,
        "SG": 18,
        "SF": 20,
        "PF": 27,
        "C": 30
      },
      "height": 69,
      "weight": 163,
      "archetype": "Pure Shooter",
      "year": "Freshman",
      "created_at": "2025-10-14 23:52:06"
    },
    // ... 40 recruits total
  ]
}
```

**Purpose:** Franchise-specific recruit pool (mutable)

**Characteristics:**
- Cloned from `recruits_collection` at franchise creation
- **No `_id` field** (plain objects, not documents)
- 40 recruits in the pool
- Have baseline attributes (lower than veterans)
- Assigned archetype (Pure Shooter, Floor General, etc.)
- Start as Freshmen
- **Modified** as recruits are signed

**Usage:**
- Always loaded WITH franchise (single query)
- Accessed during recruiting screen
- Updated when recruit is signed (removed from array)

**Size:** ~17KB for 40 recruits (2.3% of franchise doc)

---

### **C. Recruiting Flow:**

**Franchise Creation:**
```
1. Query recruits_collection (40 templates)
2. Clone/randomize for this franchise
3. Store in franchise.recruits array (strip _id)
```

**During Season:**
```
1. Load franchise → recruits already in doc ✅
2. No extra query needed ✅
```

**Recruit Signing (Inferred - May Not Be Implemented):**
```
1. User selects recruit from franchise.recruits
2. Remove from franchise.recruits array
3. Add to franchise.players with new UUID
4. Recruit joins roster with baseline attributes
```

---

### **D. Why Template Pool Pattern?**

**Benefits:**

✅ **Variety:** Each franchise can get different/randomized recruits  
✅ **Performance:** No extra queries during gameplay (nested storage)  
✅ **Maintainability:** Easy to add more templates to collection  
✅ **Clean separation:** Collection = immutable, nested = mutable

**Comparison to Alternatives:**

❌ **Only standalone with franchise_id:** Extra queries, slower  
❌ **Only nested, no templates:** Hard-coded recruits, no variety  
✅ **Hybrid (current):** Templates + nested = best of both worlds

**Analogy:**
- `players_collection` → Universal baseline (104 players)
- `franchise.players` → Evolved/franchise-specific stats

Similarly:
- `recruits_collection` → Universal templates (40 recruits)
- `franchise.recruits` → Franchise-specific pool

---

## 3. TRAINING (Dual System)

### **A. Latest Training (Franchise Doc)**

**Where:** `franchise_document.latest_training`

**Structure:**
```javascript
{
  "latest_training": {
    "session_type": "preseason",  // or "weekly"
    "week": 0,
    
    // Player improvements this session
    "player_logs": {
      "Mose Hawkins": {
        "SC": +4,
        "SH": +8,
        "ID": +4,
        // ... attribute deltas
      },
      "Kevin Nelson": {
        "SC": +4,
        "SH": +6,
        // ... deltas
      }
    },
    
    // Team improvements this session
    "team_log": {
      "team_chemistry": +4,
      "offensive_efficiency": +20
    }
  }
}
```

**Purpose:** Show user what changed in most recent training session

**Size:** ~1KB

---

### **B. Training Status (Franchise Doc)**

**Where:** `franchise_document.training_status`

**Structure:**
```javascript
{
  "training_status": {
    "current_week": 0,
    "training_completed": true,
    "session_type": "preseason"
  }
}
```

**Purpose:** Track whether user has completed training for current week

**Logic:**
- Start of week: `training_completed = false`
- User completes training: `training_completed = true`
- Can't advance to next week until training done

---

### **C. Training Log Collection (Separate DB)**

**Where:** `training_log_collection` (separate MongoDB collection)

**Structure:**
```javascript
{
  "_id": ObjectId("session_id"),
  "session_type": "preseason",  // or "weekly"
  "date": "2025-07-18",
  "team_id": "team_uuid",
  
  // How user allocated training points
  "allocations": {
    "shooting_drills": { "total_points": 10, "allocations": {...} },
    "defense_drills": { "total_points": 5, "allocations": {...} },
    "film_study": { "total_points": 8, "allocations": {...} },
    // ... more categories
  },
  
  // What changed
  "log": [
    "Player X SC +4",
    "Player Y SH +2",
    "Team chemistry +3"
  ]
}
```

**Purpose:** Historical record of all training sessions (for analytics, doesn't affect gameplay)

**Size:** ~4.6KB per session

---

## 4. PLAYER EVOLUTION (Franchise Doc)

### **Storage:**

**Where:** `franchise_document.players.{player_uuid}`

**Structure:**
```javascript
{
  "players": {
    "uuid-123": {
      "meta": {
        "first_name": "CJ",
        "last_name": "Castleman",
        "team": "Bentley-Truman",
        "team_id": "BENTLEY_TRUMAN"
      },
      
      // EVOLVED attributes (trained values)
      "attributes": {
        "SC": 78,  // Started at 75, improved via training
        "SH": 73,  // Started at 70, improved
        "anchor_SC": 78,  // Training updates anchors
        "anchor_SH": 73,
        // ... all 30+ attributes with anchors
      },
      
      // EVOLVED position ratings
      "position_ratings": {
        "PG": 70,  // Improved from 65
        "SG": 85,  // Improved from 80
        "SF": 92   // Improved from 90
      },
      
      // Season stats (this franchise only)
      "season": {
        "PTS": 450,
        "REB": 120,
        // ...
      },
      
      // Career stats (this franchise only)
      "career": {
        "PTS": 1234,
        "REB": 456,
        // ...
      }
    },
    
    "uuid-456": { /* another player */ }
  }
}
```

**Isolation:** ✅ **Each franchise has its own players object**
- Your franchise: `franchise_A.players.{CJ_uuid}.attributes.SC = 100`
- My franchise: `franchise_B.players.{CJ_uuid}.attributes.SC = 20`
- Universal collection: `players.{CJ_uuid}.attributes.SC = 75` (baseline, unchanged)

**Size:** ~1KB per player × 96 players = ~96KB for full roster evolution tracking

---

## 5. FRANCHISE TEAMS (Team Evolution)

**Where:** `franchise_document.franchise_teams.{team_id}`

**Structure:**
```javascript
{
  "franchise_teams": {
    "TEAM_ID_123": {
      // Team attributes (evolve via training)
      "team_chemistry": 75,
      "offensive_efficiency": 68,
      "offensive_adjust": 50,
      "defense_threshold": 300,
      "shot_threshold": 250,
      "turnover_threshold": 200,
      "foul_threshold": 100,
      "rebound_modifier": 1.0,
      
      // Scouting data
      "o_tendency_reads": {...},
      "d_tendency_reads": {...},
      
      // Strategy (per team in franchise)
      "playcall_settings": {...},
      "strategy_settings": {...}
    }
  }
}
```

**Purpose:** Track team stat evolution (chemistry, efficiency improve with training)

**Size:** ~75KB per team × 8 teams = ~600KB

---

## 6. SCHEDULE & STANDINGS

### **Schedule:**

**Where:** `franchise_document.schedule` (array)

**Structure:**
```javascript
{
  "schedule": [
    // Week 1 matchups
    [ObjectId("team_A"), ObjectId("team_B")],
    [ObjectId("team_C"), ObjectId("team_D")],
    [ObjectId("team_E"), ObjectId("team_F")],
    [ObjectId("team_G"), ObjectId("team_H")],
    
    // Week 2 matchups
    [ObjectId("team_A"), ObjectId("team_C")],
    // ... 14 weeks total
  ]
}
```

**Purpose:** Pre-generated schedule for entire season

---

### **Current Week:**

**Where:** `franchise_document.week` (number)

**Example:** `"week": 3` (currently on week 3)

---

## Complete Franchise Document Structure

```javascript
{
  "_id": ObjectId("franchise_id"),
  
  // Season progress
  "week": 3,
  "current_week": 3,
  
  // Schedule (pre-generated for season)
  "schedule": [[team_A, team_B], ...],  // 14 weeks
  
  // Results (weekly summaries)
  "results": {
    "1": [{away_id, home_id, scores}],
    "2": [{away_id, home_id, scores}]
  },
  
  // Player evolution (THIS FRANCHISE ONLY)
  "players": {
    "uuid_1": {
      meta: {...},
      attributes: {...},     // Evolved via training
      position_ratings: {...}, // Evolved via training
      season: {...},
      career: {...}
    }
  },
  
  // Team evolution (8 teams in conference)
  "franchise_teams": {
    "TEAM_ID_1": {
      team_chemistry: 75,
      offensive_efficiency: 68,
      playcall_settings: {...},
      strategy_settings: {...}
    }
  },
  
  // Recruiting pool
  "recruits": [
    { name, attributes, position_ratings, archetype, year }
  ],
  
  // Training tracking
  "training_status": {
    current_week: 0,
    training_completed: true,
    session_type: "preseason"
  },
  
  "latest_training": {
    player_logs: {...},  // What improved
    team_log: {...},
    session_type: "preseason",
    week: 0
  },
  
  // Stat tracking
  "applied_games": ["game_id_1", "game_id_2"],  // Prevent double-counting
  
  // Optional: Nested games (alternative to games_collection)
  "games": {
    "week_1": { "game_id": {...} }  // Full game data
  }
}
```

**Total Size:** Varies (~700KB for 8 teams + 96 players + games)

---

## How Each System Works

### **GAMES:**

1. **During Week:**
   - User plays their game → Saved to `games_collection`
   - CPU simulates other games → Saved to `games_collection`
   - Each game gets composite ID: `"{week}-{team1}-{team2}"`

2. **Week Complete:**
   - Game results summarized in `franchise.results.{week}`
   - Full games remain in `games_collection` (or optionally `franchise.games.week_X`)

3. **Player Stats Updated:**
   - Game stats rolled into `franchise.players.{uuid}.season`
   - Applied games tracked in `franchise.applied_games` (prevent double-counting)

---

### **RECRUITS:**

1. **Franchise Creation:**
   - 40 recruits generated
   - Stored in `franchise.recruits` array
   - Lower attributes than veterans (18-35 range)
   - Assigned archetypes (Pure Shooter, Defensive Anchor, etc.)

2. **Recruiting (Inferred - May Not Be Implemented):**
   - Off-season: User reviews `franchise.recruits`
   - User selects recruits to join roster
   - Selected recruits added to `franchise.players`
   - Recruits removed from `franchise.recruits` pool

3. **Recruit Structure:**
   - No `_id` or `player_id` (not in universal collection yet)
   - Once recruited → get UUID and added to players_collection
   - Then tracked in `franchise.players.{uuid}`

---

### **TRAINING:**

**Flow:**

1. **Start of Week:**
   - `training_status.training_completed = false`
   - User must train before advancing to next week

2. **User Allocates Training Points:**
   - Frontend sends allocations (shooting drills, defense, etc.)
   - Backend applies attribute improvements
   - Updates `franchise.players.{uuid}.attributes.anchor_X`
   - Updates `franchise.franchise_teams.{team_id}` team attributes

3. **Training Results Saved:**
   
   **A. In Franchise Doc:**
   ```javascript
   franchise.latest_training = {
     player_logs: { "CJ Castleman": { "SC": +4, "SH": +2 } },
     team_log: { "team_chemistry": +3 },
     week: 3
   }
   franchise.training_status.training_completed = true
   ```
   
   **B. In Training Log Collection:**
   ```javascript
   training_log_collection.insert({
     session_type: "weekly",
     date: "2025-11-05",
     team_id: "user_team_id",
     allocations: {...},
     log: ["CJ SC +4", "Team chemistry +3"]
   })
   ```

4. **Week Advances:**
   - `franchise.week` incremented
   - `training_status.training_completed = false` (reset for next week)

---

## Isolation & Scalability

### **✅ Player Evolution is Isolated Per Franchise:**

```
Franchise A (Your Save):
  franchise.players.{CJ_uuid}.attributes.SC = 100 ✅

Franchise B (My Save):
  franchise.players.{CJ_uuid}.attributes.SC = 20 ✅

Universal Collection (Unchanged):
  players.{CJ_uuid}.attributes.SC = 75 (baseline)
```

**Same player UUID, different franchises, independent evolution!**

---

### **✅ Using Universal Player IDs is Safe:**

**Why it works:**
- Universal `_id` is just a **lookup key**
- Actual evolved data stored in **franchise-specific** `franchise.players.{uuid}`
- Each franchise clones baseline from universal collection
- Evolution tracked separately per franchise
- No cross-contamination

**Analogy:**
- Universal collection = "Library catalog" (baseline stats)
- Your franchise = "Your copy of the book with your notes" (evolved stats)
- My franchise = "My copy with my notes" (different evolved stats)
- Same book ID, different annotations!

---

## Storage Costs

| Component | Size | Storage |
|-----------|------|---------|
| **Games (per game)** | ~18KB | games_collection (primary) |
| **Games (nested)** | ~18KB | franchise.games.week_X (optional) |
| **Players (96)** | ~104KB | franchise.players |
| **Teams (8)** | ~600KB | franchise.franchise_teams |
| **Recruits (40)** | ~17KB | franchise.recruits |
| **Training (latest)** | ~1KB | franchise.latest_training |
| **Training (history)** | ~5KB/session | training_log_collection |
| **Schedule** | ~3KB | franchise.schedule |
| **Results** | ~1KB/week | franchise.results |

**Total Franchise Doc:** ~725KB (without nested games)  
**With 14 weeks of nested games:** ~725KB + (14 weeks × 4 games × 18KB) = ~1.7MB

---

## Key Files

**Backend:**
- `BackEnd/models/franchise_manager.py` - Franchise initialization
- `BackEnd/api/franchise_routes.py` - API endpoints (select team, play game, training, etc.)
- `BackEnd/models/training_manager.py` - Training session logic
- `BackEnd/utils/stat_updater.py` - Roll up game stats to franchise

**Frontend:**
- `FrontEnd/static/franchise-command-center.js` - Main UI
- (Others TBD based on your implementation)

---

## Summary

**Games:** Primarily in `games_collection`, optionally nested in franchise doc  
**Recruits:** Array in franchise doc, generated at franchise start  
**Training:** Latest results in franchise doc, full history in `training_log_collection`  
**Player Evolution:** Completely isolated per franchise (same UUID, different data)  

✅ **Using universal player IDs is safe - each franchise tracks its own evolution independently!**

