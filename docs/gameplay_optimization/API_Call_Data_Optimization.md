# API Call Data Optimization

**Last Updated:** January 2025  
**Status:** 🔴 Critical Performance Issues Identified - Optimization In Progress

## Overview

This document tracks API endpoint performance issues and optimization strategies across all game modes (Franchise, Tournament, Single Game). The primary issue is endpoints loading full mode documents (402KB+ for Franchise) when only small subsets of data are needed.

## Performance Impact

After simulating a full season, franchise documents grow to **402KB+**. Loading these documents multiple times per page load causes:
- **30+ second** page load times
- **5-10 second** navigation delays
- Poor user experience on slow connections
- Unnecessary database load and bandwidth usage

## Optimization Strategy

### Core Principles

1. **Use MongoDB Projections**: Only fetch needed fields from documents
2. **Eliminate Double Loads**: Load document once, reuse data
3. **Lazy Load Large Objects**: Only load `players` object when needed, and filter to specific teams
4. **Use Aggregation Pipelines**: For sorting/filtering large datasets, use MongoDB aggregation instead of in-memory operations
5. **Cache Expensive Operations**: Cache results of `populate_team_plays()`, `initialize_playbook_settings()`, etc.

### Projection Pattern

```python
# ❌ BAD: Loads entire 402KB document
franchise_doc = db.franchises.find_one({"_id": fid})

# ✅ GOOD: Only loads needed fields (~10KB)
franchise_doc = db.franchises.find_one(
    {"_id": fid},
    {
        "franchise_teams": 1,
        "training_status": 1,
        "week": 1,
        "user_team_id": 1,
        "user_team_object_id": 1,
        "_id": 1
    }
)
```

---

## Franchise Mode Optimizations

### Critical Issues (30+ seconds)

#### 1. `/api/gameplan` Endpoint - **30.10 seconds** 🔴

**Location:** `BackEnd/api/gameplan_routes.py:854`

**Current Issues:**
- Line 881: Loads full franchise document (no projection)
- Line 897: Calls `ensure_team_objects_exist()` which:
  - Line 602: Loads full franchise document **again** (no projection)
  - Line 610: Calls `list(db.teams.find())` - unnecessary query for all teams
  - Line 615-617: Calls expensive `populate_team_plays()` and `initialize_playbook_settings()`
  - Line 620-642: Loops through **all 8 teams** to check/initialize objects
  - Line 655-665: Updates entire franchise document

**Optimization Plan:**
- ✅ Add projection to initial load (only `user_team_id`, `user_team_object_id`, `franchise_teams`)
- ✅ Optimize `ensure_team_objects_exist()`: Only check/update the **requested team**, not all 8
- ✅ Cache `populate_team_plays()` and `initialize_playbook_settings()` results
- ✅ Remove unnecessary `db.teams.find()` call

**Expected Impact:** 30 seconds → <1 second

---

### High Priority Issues (5-10 seconds)

#### 2. `/franchise/leaders` Endpoint - **9.33 seconds** 🟠

**Location:** `BackEnd/api/franchise_routes.py:1357`

**Current Issues:**
- Line 1288: Loads entire `players` object (~300KB) with projection `{"players": 1}`
- Line 1291-1315: Sorts all ~96 players **in-memory** (Python sort)
- Only uses aggregation pipeline (faster) if >500 players

**Optimization Plan:**
- ✅ Lower threshold for aggregation pipeline (use for >50 players instead of >500)
- ✅ Use MongoDB aggregation for all leaderboard queries
- ✅ Consider caching leaderboard results on franchise document

**Expected Impact:** 9 seconds → <500ms

---

#### 3. `/franchise/roster` Endpoint - **7.16 seconds** 🟠

**Location:** `BackEnd/api/franchise_routes.py:1727`

**Current Issues:**
- Line 1739: Loads full franchise document (no projection) to get team name
- Line 1753: Loads full franchise document **again** (no projection) to get players
- Loads all ~96 players from all teams, even though only one team's roster is needed

**Optimization Plan:**
- ✅ Add projection to both loads (only `players` field, or filter to requested team's players)
- ✅ Fix double-load: Load once, reuse data
- ✅ Filter `players` object to only return players for the requested team

**Expected Impact:** 7 seconds → <1 second

---

#### 4. `/franchise/command-center/data` Endpoint - **6.92 seconds** 🟠

**Location:** `BackEnd/api/franchise_routes.py:843`

**Current Status:** ✅ **PARTIALLY OPTIMIZED** (projection added, but still slow)

**Optimization Plan:**
- ✅ Already has projection (only needed fields)
- ⚠️ Still slow - may need database indexing on `_id` field
- ⚠️ Consider caching top-level data that doesn't change frequently

**Expected Impact:** 7 seconds → <1 second (with indexing)

---

### Medium Priority Issues (3-5 seconds)

#### 5. `/franchise/state` Endpoint - **3.58 seconds** 🟡

**Location:** `BackEnd/api/franchise_routes.py:1575`

**Current Status:** ✅ **PARTIALLY OPTIMIZED** (projection added, but still large)

**Current Issues:**
- Returns only `players` object with projection `{"players": 1}`
- But `players` object contains **all ~96 players** from all 8 teams (~300KB)
- Only used for merging stats into roster display

**Optimization Plan:**
- ✅ Filter `players` object to only return players for the user's team
- ✅ Or create separate endpoint `/franchise/team-player-stats` that only returns one team's players

**Expected Impact:** 3.5 seconds → <500ms

---

#### 6. `/franchise/standings` Endpoint - **3.53 seconds** 🟡

**Location:** `BackEnd/api/franchise_routes.py:971`

**Current Status:** ✅ **OPTIMIZED** (projection added)

**Optimization Plan:**
- ✅ Already has projection (only `schedule`, `week`, `eos_tournament`, `eos_tournament_active`)
- ⚠️ Still slow - may need database indexing

**Expected Impact:** 3.5 seconds → <500ms (with indexing)

---

#### 7. `/franchise/team-data` Endpoint - **3.48 seconds** 🟡

**Location:** `BackEnd/api/franchise_routes.py:1599`

**Current Status:** ✅ **OPTIMIZED** (projection added, double-load fixed)

**Optimization Plan:**
- ✅ Already has projection (only `franchise_teams` field)
- ⚠️ Still slow - may need database indexing

**Expected Impact:** 3.5 seconds → <500ms (with indexing)

---

#### 8. `/franchise/team-stats` Endpoint - **3.21 seconds** 🟡

**Location:** `BackEnd/api/franchise_routes.py:1379`

**Current Status:** ✅ **OPTIMIZED** (projection added)

**Optimization Plan:**
- ✅ Already has projection (only `players`, `franchise_teams`)
- ⚠️ Still slow - aggregation may be expensive on large `players` object

**Expected Impact:** 3 seconds → <1 second

---

### Training-Related Endpoints

#### 9. `/franchise/run-training` Endpoint

**Location:** `BackEnd/api/franchise_routes.py:1968`

**Current Issues:**
- Line 1979: Loads full franchise document (no projection) when submitting training

**Optimization Plan:**
- ✅ Add projection (only `players` for user's team, `franchise_teams`, `training_status`)
- ✅ Only load players for the user's team, not all teams

**Expected Impact:** Significant reduction in training submission time

---

#### 10. `/franchise/training-report` Endpoint

**Location:** `BackEnd/api/franchise_routes.py:2439`

**Current Issues:**
- Line 2501: Loads full franchise document (no projection) when loading training report

**Optimization Plan:**
- ✅ Add projection (only `franchise_teams`, `schedule`, `week`, `latest_training`)

**Expected Impact:** Significant reduction in training report load time

---

## Tournament Mode Optimizations

### Current Status

Tournament mode documents are typically smaller than franchise documents, but similar optimization patterns apply.

### Endpoints to Optimize

#### 1. `/tournament/roster` Endpoint

**Optimization Plan:**
- ✅ Add projection (only `players` field, or filter to requested team's players)
- ✅ Fix double-load if present

---

#### 2. `/tournament/leaders` Endpoint

**Location:** `BackEnd/api/tournament_routes.py:108`

**Current Status:** Uses cached leaderboards (good!)

**Optimization Plan:**
- ✅ Already optimized (caches leaderboards on tournament document)
- ⚠️ Ensure leaderboard recomputation uses aggregation pipeline

---

#### 3. `/api/gameplan` Endpoint (Tournament Mode)

**Location:** `BackEnd/api/gameplan_routes.py:854`

**Optimization Plan:**
- ✅ Same optimizations as Franchise mode
- ✅ Add projection to tournament document loads
- ✅ Optimize `ensure_team_objects_exist()` for tournament mode

---

## Single Game Mode Optimizations

### Current Status

Single game documents are typically small, but similar patterns apply.

### Endpoints to Optimize

#### 1. `/api/gameplan` Endpoint (Single Game Mode)

**Optimization Plan:**
- ✅ Add projection to game document loads
- ✅ Optimize `ensure_team_objects_exist()` for single game mode

---

## Implementation Checklist

### Phase 1: Critical Fixes (30+ second endpoints)

- [x] Fix `/api/gameplan` endpoint: ✅ **COMPLETED**
  - [x] Add projection to initial franchise document load (98% reduction: 402KB → ~10KB)
  - [x] Optimize `ensure_team_objects_exist()` to only check requested team (not all 8)
  - [x] Fix caching bug - make `populate_team_plays()` caching mode-aware (was global, now per-mode)
  - [x] Add projection to `ensure_team_objects_exist()` franchise document load
  - [x] Fix double-loads in PUT and POST endpoints (pass pre-loaded doc)
  - [x] Remove unnecessary double-loads (was loading doc twice, now loads once and passes it)
- [ ] Fix `/franchise/leaders` endpoint:
  - [ ] Lower aggregation threshold to 50 players
  - [ ] Use aggregation pipeline for all queries
- [ ] Fix `/franchise/roster` endpoint:
  - [ ] Add projection to both loads
  - [ ] Fix double-load issue
  - [ ] Filter players to requested team only

### Phase 2: High Priority Fixes (5-10 second endpoints)

- [ ] Optimize `/franchise/command-center/data`:
  - [ ] Add database indexing on `_id` field
  - [ ] Consider caching top-level data
- [ ] Optimize `/franchise/state`:
  - [ ] Filter players to user's team only
  - [ ] Or create separate `/franchise/team-player-stats` endpoint

### Phase 3: Medium Priority Fixes (3-5 second endpoints)

- [ ] Add database indexing on commonly queried fields
- [ ] Optimize `/franchise/standings` (already has projection, may need indexing)
- [ ] Optimize `/franchise/team-data` (already has projection, may need indexing)
- [ ] Optimize `/franchise/team-stats` (already has projection, may need indexing)

### Phase 4: Training Endpoints

- [ ] Optimize `/franchise/run-training`:
  - [ ] Add projection
  - [ ] Only load players for user's team
- [ ] Optimize `/franchise/training-report`:
  - [ ] Add projection

### Phase 5: Tournament Mode

- [ ] Apply same optimization patterns to Tournament mode endpoints
- [ ] Ensure leaderboard caching is working correctly

### Phase 6: Database Indexing

- [ ] Add index on `franchises._id`
- [ ] Add index on `tournaments._id`
- [ ] Add index on `games._id`
- [ ] Consider compound indexes for common query patterns

---

## Performance Metrics

### Before Optimization

| Endpoint | Time | Data Transferred |
|----------|------|------------------|
| `/api/gameplan` | 30.10s | 0.3 kB |
| `/franchise/leaders` | 9.33s | 6.7 kB |
| `/franchise/roster` | 7.16s | 7.7 kB |
| `/franchise/command-center/data` | 6.92s | 0.4 kB |
| `/franchise/state` | 3.58s | 318 kB |
| `/franchise/standings` | 3.53s | 1.1 kB |
| `/franchise/team-data` | 3.48s | 14.1 kB |
| `/franchise/team-stats` | 3.21s | 1.9 kB |

### After Optimization (Target)

| Endpoint | Time | Data Transferred |
|----------|------|------------------|
| `/api/gameplan` | <1s | 0.3 kB |
| `/franchise/leaders` | <500ms | 6.7 kB |
| `/franchise/roster` | <1s | 7.7 kB |
| `/franchise/command-center/data` | <1s | 0.4 kB |
| `/franchise/state` | <500ms | ~50 kB (filtered) |
| `/franchise/standings` | <500ms | 1.1 kB |
| `/franchise/team-data` | <500ms | 14.1 kB |
| `/franchise/team-stats` | <1s | 1.9 kB |

---

## Notes

- **Document Size Growth**: After simulating a full season, franchise documents grow from ~50KB to 402KB+. This makes optimization critical.
- **Network vs. Processing**: Some endpoints (like `/api/gameplan`) have small response sizes but long processing times, indicating server-side inefficiency rather than data transfer issues.
- **MongoDB Aggregation**: For sorting/filtering large datasets, MongoDB aggregation pipelines are much faster than in-memory Python operations.
- **Caching Strategy**: Consider caching expensive operations (like `populate_team_plays()`) and frequently accessed data (like leaderboards).

---

## Related Documents

- `docs/gameplay_optimization/Full_Season_Team_Stats.md` - Related performance optimization for team stats aggregation
- `docs/docs_1_systems/01_Game_Mode_Systems/Franchise_Mode_Systems.md` - Franchise mode system documentation
- `docs/docs_1_systems/01_Game_Mode_Systems/Tournament_Mode_Systems.md` - Tournament mode system documentation

