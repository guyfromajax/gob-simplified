# Database Query Architecture Overhaul

> **Status:** 🔴 CRITICAL - Strategic Planning Required  
> **Priority:** HIGH - Scalability Blocker  
> **Created:** January 2025  
> **Related:** Full_Season_Team_Stats.md, API_Call_Data_Optimization.md

---

## Executive Summary

**Current State:** We have **far too many database calls** for a scalable architecture. A typical Franchise Command Center page load triggers **15-20+ database queries**, and individual endpoints often make **multiple queries for related data** (N+1 patterns).

**Problem Statement:** We're treating symptoms (slow endpoints) instead of addressing the root cause: **our architecture makes too many database calls in the first place**.

**Goal:** Redesign our data access layer to minimize database calls through strategic batching, caching, and data structure optimization.

---

## Current State Analysis

### Database Calls Per Page Load

#### Franchise Command Center (FCC) Initial Load
**Frontend makes 10+ API calls:**
1. `/franchise/command-center/data` → 1-2 DB queries
2. `/franchise/roster` → **12+ DB queries** (N+1 problem)
3. `/franchise/state` → 1 DB query (300KB players object)
4. `/franchise/standings` → 1 DB query
5. `/franchise/schedule` → **14+ DB queries** (game lookups per week)
6. `/franchise/team-stats` → 1 DB query (300KB players object)
7. `/franchise/recruits` → 1 DB query
8. `/api/gameplan` → 2-3 DB queries
9. `/franchise/team-data` → 2-3 DB queries

**Total: ~35-40 database queries per FCC page load**

#### Individual Endpoint Database Queries

**Backend API endpoints make multiple queries:**

1. **`/franchise/roster` (1.92s)**
   - 1 query: Get franchise document (projection: players)
   - 1 query: Get team document (by name)
   - **12 queries: Get player documents (N+1 pattern)**
   - **Total: 14 queries for 12 players**

2. **`/franchise/scouting-report` (3.55s)**
   - 1 query: Get franchise document (**no projection - 402KB!**)
   - 1 query: Get team document (by name)
   - 1 query: Get last game (potentially no index)
   - **N queries: Match team keys in game document** (worst case: queries per team in league)
   - **Total: 3-10+ queries**

3. **`/franchise/schedule` (2.71s)**
   - 1 query: Get franchise document (with projection)
   - **14 queries: Get game documents (one per week)**
   - **Total: 15 queries for 14 weeks**

4. **`/franchise/team-stats` (3.28s)**
   - 1 query: Get franchise document (players + franchise_teams = ~300KB)
   - **N queries: Get team documents** (in aggregation utility)
   - **Total: 5-10 queries**

5. **`/franchise/team-data` (1.76s)**
   - 1 query: Get franchise document (projection: franchise_teams)
   - 1 query: Get team document (by name or ID)
   - **Total: 2 queries** (relatively good, but could be better)

6. **`/api/gameplan`** (varies)
   - 1 query: Get franchise/tournament document
   - **8 queries: Ensure team objects exist** (one per team in league)
   - **N queries: Populate team plays** (one per team)
   - **Total: 10-20 queries per call**

### Total Database Queries: Backend Analysis

**Backend codebase statistics:**
- `BackEnd/api/franchise_routes.py`: **125 database query operations**
- `BackEnd/api/api.py`: **46 database query operations**
- `BackEnd/api/gameplan_routes.py`: **80 database query operations**
- `BackEnd/api/tournament_routes.py`: **50 database query operations**
- `BackEnd/api/play_routes.py`: **6 database query operations**
- `BackEnd/api/skeleton_routes.py`: **10 database query operations**

**Total: 317+ database query operations across API endpoints**

---

## Root Cause Analysis

### Why Do We Have So Many Database Calls?

#### 1. **No Data Batching Strategy**
**Problem:** Each endpoint fetches its own data independently, even when multiple endpoints need the same data.

**Example:**
- `/franchise/roster` loads franchise document for players
- `/franchise/state` loads franchise document for player stats
- `/franchise/team-stats` loads franchise document for team stats
- **Result:** Same 300KB+ document loaded 3 times in same page load

**Root Cause:** Each endpoint is designed as an independent service, not as part of a coordinated data loading strategy.

#### 2. **N+1 Query Patterns Everywhere**
**Problem:** We fetch a list of items, then make separate queries for each item's related data.

**Examples:**
- **Roster:** Fetch 12 player IDs → 12 separate queries for player details
- **Schedule:** Fetch 14 weeks → 14 separate queries for game documents
- **Gameplan:** Fetch 8 teams → 8 separate queries to ensure team objects exist

**Root Cause:** Code was written to be "simple" (one query at a time) without considering scalability.

#### 3. **No Caching Layer**
**Problem:** Every request hits the database, even for static or rarely-changing data.

**Examples:**
- **Team data** (rarely changes) → loaded fresh every request
- **Play data** (never changes) → loaded fresh every request
- **Franchise metadata** (changes infrequently) → loaded fresh every request

**Root Cause:** No strategic caching strategy was implemented (only ad-hoc in-memory caching in `gameplan_routes.py`).

#### 4. **Document Structure Forces Multiple Queries**
**Problem:** Large documents (402KB franchise docs) force us to load full documents when we only need small subsets.

**Examples:**
- Need player stats → Load entire 402KB franchise document
- Need team attributes → Load entire 402KB franchise document
- Need schedule → Load entire 402KB franchise document

**Root Cause:** Document structure optimized for data organization, not for query efficiency.

#### 5. **Missing Database Indexes**
**Problem:** Queries scan entire collections instead of using indexes.

**Examples:**
- `/franchise/scouting-report` queries games by `franchise_id + home_team_id + away_team_id` (no compound index)
- `/franchise/schedule` queries games by `week + team_id` (potentially no index)
- Team lookups by name (no unique index guarantee)

**Root Cause:** Indexes were not considered during development.

#### 6. **Endpoint Granularity vs. Data Needs Mismatch**
**Problem:** Frontend makes many small API calls for related data that should be fetched together.

**Example:**
- FCC loads: roster, state, standings, schedule, team-stats, recruits, gameplan, team-data
- **All these need the same franchise document**
- **But we fetch them separately, loading the document multiple times**

**Root Cause:** RESTful API design (one resource per endpoint) doesn't match our actual data access patterns.

---

## Scalability Projection

### Current State at Scale

**Assumptions:**
- 200 concurrent users
- Average 2 page loads per user per session
- Each page load = 35-40 database queries
- Average query time: 50-100ms

**Math:**
- 200 users × 2 page loads = 400 page loads
- 400 page loads × 35 queries = **14,000 database queries**
- 14,000 queries × 75ms average = **1,050 seconds of database time**

**Reality:**
- Connection pool (100 connections) → **Saturation at 50-100 users**
- Without fixes → **System fails at 100+ concurrent users**

### Bottlenecks

1. **Connection Pool Exhaustion** (100 connections default)
   - First bottleneck at scale
   - Requests queue → timeouts → user errors

2. **Network Latency Multiplication**
   - Railway → MongoDB Atlas: 50-100ms per query
   - 35 queries × 75ms = **2.6 seconds minimum** (network overhead alone)

3. **Document Size Transfer**
   - 402KB document × 3-5 loads per page = **1.2-2MB transferred**
   - 200 users × 2MB = **400MB transferred per session**

4. **Database CPU/Memory**
   - 14,000 queries/hour → Database CPU saturation
   - Large document loads → Memory pressure

---

## Strategic Overhaul Approach

### Philosophy

**Don't fix symptoms. Fix the architecture.**

Instead of optimizing individual endpoints, redesign the data access layer to:
1. **Batch related queries** into single operations
2. **Cache frequently-accessed data** at multiple levels
3. **Restructure data** for efficient queries
4. **Coordinate frontend data loading** to minimize redundant calls

### Core Principles

1. **Single Data Load Per Context**
   - Load franchise document once per page load
   - Share data across endpoints in same request context

2. **Batch Operations**
   - Use `$in` queries instead of loops
   - Combine related lookups into single queries

3. **Strategic Caching**
   - Cache static data (teams, plays, defenses)
   - Cache semi-static data (franchise metadata)
   - Invalidate cache on updates

4. **Efficient Data Structures**
   - Separate read-optimized views from write-optimized documents
   - Denormalize for read-heavy operations

5. **Index-Driven Queries**
   - Create indexes for all query patterns
   - Use compound indexes for multi-field queries

---

## Proposed Architecture Changes

### Phase 1: Data Access Layer (Backend)

#### 1.1 Create Data Access Manager

**Purpose:** Centralize all database operations and implement batching/caching logic.

**Responsibilities:**
- Load franchise document once, share across endpoints
- Batch player lookups (`$in` queries)
- Batch game lookups (fetch multiple weeks at once)
- Cache static data (teams, plays, defenses)
- Cache franchise metadata (TTL-based)

**Implementation:**
```python
# BackEnd/utils/data_access_manager.py (new file)
class DataAccessManager:
    """Centralized data access with batching and caching"""
    
    # In-memory cache for static data
    _team_cache = {}
    _play_cache = {}
    
    # Request-scoped cache for franchise data
    _request_cache = {}
    
    def load_franchise_with_players(self, franchise_id: str, projection: dict):
        """Load franchise document once per request context"""
        # Check request cache first
        # If not cached, load with projection
        # Cache for request duration
        pass
    
    def batch_load_players(self, player_ids: List[str]):
        """Load multiple players in single query"""
        # Use $in query instead of loop
        pass
    
    def batch_load_games(self, game_ids: List[str]):
        """Load multiple games in single query"""
        # Use $in query instead of loop
        pass
```

#### 1.2 Refactor Endpoints to Use Data Access Manager

**Changes:**
- Replace direct `db.franchises.find_one()` calls with `DataAccessManager.load_franchise()`
- Replace player loops with `DataAccessManager.batch_load_players()`
- Replace game loops with `DataAccessManager.batch_load_games()`

**Impact:**
- Single franchise document load per page load (instead of 5-10)
- Single player batch query (instead of 12 separate queries)
- Single game batch query (instead of 14 separate queries)

#### 1.3 Add Database Indexes

**Critical Indexes to Create:**
```javascript
// Games collection
db.games.createIndex({franchise_id: 1, home_team_id: 1, away_team_id: 1});
db.games.createIndex({franchise_id: 1, week: 1, _id: -1});
db.games.createIndex({franchise_id: 1, is_final: 1, _id: -1});

// Franchises collection (already exists, verify)
db.franchises.createIndex({_id: 1});

// Teams collection
db.teams.createIndex({name: 1}); // Unique index
db.teams.createIndex({_id: 1});

// Players collection
db.players.createIndex({_id: 1});
```

#### 1.4 Increase Connection Pool Size

**Current:** Default 100 connections

**Proposed:** 200 connections with warm pool

```python
# BackEnd/db.py
client = MongoClient(
    uri,
    serverSelectionTimeoutMS=5000,
    maxPoolSize=200,    # Increase from 100
    minPoolSize=10      # Keep connections warm
)
```

### Phase 2: API Consolidation (Backend)

#### 2.1 Create Composite Endpoints

**Problem:** Frontend makes 10+ separate API calls for related data.

**Solution:** Create endpoints that return multiple related resources.

**New Endpoints:**
- `/franchise/command-center/all-data` - Returns: top data, roster, standings, schedule, team-stats, recruits in single response
- `/franchise/gameplay/initial-state` - Returns: gameplan, team-data, rosters in single response

**Benefits:**
- Single franchise document load
- Single network round trip
- Atomic data consistency

#### 2.2 Implement GraphQL-Style Field Selection

**Problem:** Endpoints return full objects when only small subsets are needed.

**Solution:** Allow clients to specify which fields to return.

**Example:**
```
GET /franchise/data?fields=week,schedule,standings,roster
```

**Benefits:**
- Clients request only needed data
- Reduces data transfer
- Maintains flexibility

### Phase 3: Caching Strategy (Backend + Infrastructure)

#### 3.1 In-Memory Caching (Application Level)

**Cache Static Data:**
- Teams (never changes)
- Plays (never changes)
- Defenses (never changes)
- Skeletons (rarely changes)

**Implementation:**
```python
# BackEnd/utils/data_access_manager.py
class DataAccessManager:
    @staticmethod
    @lru_cache(maxsize=1)
    def get_all_teams():
        """Cache teams (static data)"""
        return list(db.teams.find({}))
    
    @staticmethod
    @lru_cache(maxsize=100)
    def get_play(play_id: str):
        """Cache plays (static data)"""
        return db.plays.find_one({"_id": play_id})
```

**Cache Semi-Static Data (TTL-based):**
- Franchise metadata (5-minute TTL)
- Tournament metadata (5-minute TTL)
- Player stats (1-minute TTL)

**Implementation:**
```python
# BackEnd/utils/cache.py (new file)
from functools import wraps
import time

_cache = {}
_cache_ttl = {}

def cached(ttl_seconds: int = 300):
    """Decorator for TTL-based caching"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            now = time.time()
            
            # Check if cached and not expired
            if cache_key in _cache:
                if now - _cache_ttl[cache_key] < ttl_seconds:
                    return _cache[cache_key]
            
            # Cache miss - call function and cache result
            result = func(*args, **kwargs)
            _cache[cache_key] = result
            _cache_ttl[cache_key] = now
            return result
        return wrapper
    return decorator
```

#### 3.2 Redis Caching (Infrastructure Level)

**When to Implement:** After Phase 1-2, if in-memory caching insufficient for scale.

**What to Cache:**
- Franchise metadata (shared across all users)
- Team stats (computed aggregations)
- Game results (historical data)

**Benefits:**
- Shared cache across multiple application instances
- Faster than database queries
- Automatic TTL and eviction

### Phase 4: Frontend Data Loading Strategy

#### 4.1 Consolidate API Calls

**Problem:** Frontend makes 10+ separate API calls on page load.

**Solution:** Create single "page data" endpoint or batch requests.

**Current:**
```javascript
// 10 separate API calls
const topData = await fetch('/franchise/command-center/data');
const roster = await fetch('/franchise/roster');
const state = await fetch('/franchise/state');
const standings = await fetch('/franchise/standings');
// ... etc
```

**Proposed:**
```javascript
// Single API call with all data
const pageData = await fetch('/franchise/command-center/all-data');
// Returns: { topData, roster, state, standings, schedule, teamStats, recruits }
```

#### 4.2 Implement Request Batching

**Alternative Approach:** Use request batching to combine multiple API calls.

**Implementation:**
```javascript
// FrontEnd/static/js/shared/apiBatcher.js (new file)
class ApiBatcher {
    constructor() {
        this.pendingRequests = [];
        this.batchTimeout = 50; // ms
    }
    
    async batchFetch(url, options) {
        return new Promise((resolve, reject) => {
            this.pendingRequests.push({ url, options, resolve, reject });
            
            // Debounce batch execution
            clearTimeout(this.batchTimer);
            this.batchTimer = setTimeout(() => {
                this.executeBatch();
            }, this.batchTimeout);
        });
    }
    
    async executeBatch() {
        // Combine multiple requests into single batch request
        // Backend processes batch and returns multiple responses
    }
}
```

#### 4.3 Client-Side Caching

**Implement:** `sessionStorage` caching for page load data.

**Strategy:**
- Cache franchise data for duration of session
- Invalidate on navigation away and back
- Use for "instant" subsequent page loads

**Implementation:**
```javascript
// FrontEnd/static/js/shared/cache.js (new file)
class SessionCache {
    static get(key) {
        const cached = sessionStorage.getItem(key);
        if (!cached) return null;
        
        const { data, timestamp, ttl } = JSON.parse(cached);
        if (Date.now() - timestamp > ttl) {
            sessionStorage.removeItem(key);
            return null;
        }
        
        return data;
    }
    
    static set(key, data, ttlSeconds = 300) {
        sessionStorage.setItem(key, JSON.stringify({
            data,
            timestamp: Date.now(),
            ttl: ttlSeconds * 1000
        }));
    }
}
```

### Phase 5: Document Structure Optimization

#### 5.1 Separate Read-Optimized Views

**Problem:** Large franchise documents (402KB) are read-heavy but written infrequently.

**Solution:** Create separate collections for read-optimized views.

**Proposed Structure:**
```
franchises (write-optimized)
  ├── _id
  ├── franchise_teams
  ├── players (full objects)
  └── ... (all fields)

franchise_views (read-optimized)
  ├── _id (same as franchises._id)
  ├── summary (week, user_team, etc.) - 10KB
  ├── schedule_data (schedule + results) - 20KB
  ├── standings_data (computed standings) - 5KB
  └── team_stats_data (computed team stats) - 15KB
```

**Benefits:**
- Read queries load small documents (10-50KB vs 402KB)
- Write operations update full document
- Views updated on write (synchronous or async)

#### 5.2 Denormalize for Read Performance

**Problem:** Computing team stats requires loading entire players object.

**Solution:** Denormalize computed stats into separate collection.

**Proposed:**
```
franchise_team_stats (denormalized)
  ├── franchise_id
  ├── team_id
  ├── computed_stats (W, L, PF, PA, etc.)
  └── last_updated
```

**Benefits:**
- Team stats queries load 1KB instead of 300KB
- Stats computed once, cached indefinitely
- Updated on game completion

---

## Implementation Roadmap

### Phase 1: Critical Fixes (Week 1)
**Goal:** Fix immediate scalability blockers

1. **Fix N+1 Queries**
   - Batch player lookups in `/franchise/roster`
   - Batch game lookups in `/franchise/schedule`
   - Batch team lookups in `/api/gameplan`

2. **Add Database Indexes**
   - Create compound indexes on games collection
   - Verify indexes on franchises/teams/players

3. **Increase Connection Pool**
   - Set `maxPoolSize=200` in MongoClient

**Expected Impact:**
- Roster endpoint: 1.92s → 0.3s (85% improvement)
- Schedule endpoint: 2.71s → 0.5s (80% improvement)
- Connection pool: Handle 200 users (vs 100)

### Phase 2: Data Access Layer (Week 2-3)
**Goal:** Centralize database operations

1. **Create DataAccessManager**
   - Implement batching logic
   - Implement in-memory caching for static data
   - Request-scoped caching for franchise data

2. **Refactor High-Traffic Endpoints**
   - `/franchise/roster`
   - `/franchise/schedule`
   - `/franchise/scouting-report`
   - `/franchise/team-stats`

**Expected Impact:**
- Single franchise document load per page load (vs 5-10)
- 70% reduction in database queries
- 60% reduction in data transfer

### Phase 3: API Consolidation (Week 4)
**Goal:** Reduce number of API calls

1. **Create Composite Endpoints**
   - `/franchise/command-center/all-data`
   - `/franchise/gameplay/initial-state`

2. **Update Frontend**
   - Replace 10 API calls with 1-2 composite calls
   - Maintain backward compatibility during transition

**Expected Impact:**
- Frontend API calls: 10+ → 2-3 (70% reduction)
- Page load time: 5-8s → 1-2s (75% improvement)

### Phase 4: Caching Strategy (Week 5-6)
**Goal:** Implement multi-layer caching

1. **In-Memory Caching**
   - Cache static data (teams, plays, defenses)
   - Cache semi-static data (franchise metadata) with TTL

2. **Client-Side Caching**
   - Implement `sessionStorage` caching
   - Cache page load data for session duration

**Expected Impact:**
- Static data queries: 0ms (100% cache hit rate)
- Subsequent page loads: Instant (cached)
- Database load: 50% reduction

### Phase 5: Document Structure Optimization (Week 7-8)
**Goal:** Optimize data structures for read performance

1. **Create Read-Optimized Views**
   - Implement `franchise_views` collection
   - Update views on write operations

2. **Denormalize Computed Stats**
   - Create `franchise_team_stats` collection
   - Compute stats on game completion

**Expected Impact:**
- Document size: 402KB → 10-50KB per query (90% reduction)
- Query time: 50-100ms → 10-20ms (80% improvement)

---

## Success Metrics

### Performance Targets

**Single User (1 concurrent user):**
- FCC page load: **< 1 second** (currently 5-8 seconds)
- Individual endpoints: **< 200ms** (currently 1-4 seconds)

**Medium Scale (50 concurrent users):**
- FCC page load: **< 2 seconds** (currently 10-15 seconds)
- 95th percentile response time: **< 500ms**

**High Scale (200 concurrent users):**
- FCC page load: **< 3 seconds** (currently times out)
- 95th percentile response time: **< 1 second**
- Zero connection pool exhaustion errors

### Database Metrics

**Target Reductions:**
- Database queries per page load: **35-40 → 5-10** (75% reduction)
- Data transfer per page load: **2MB → 200KB** (90% reduction)
- Average query time: **50-100ms → 10-20ms** (80% improvement)

---

## Risks and Considerations

### Risk 1: Breaking Changes
**Risk:** Refactoring data access layer could introduce bugs in existing functionality.

**Mitigation:**
- Comprehensive test coverage before refactoring
- Gradual rollout (feature flags)
- Maintain backward compatibility during transition

### Risk 2: Cache Invalidation Complexity
**Risk:** Caching introduces cache invalidation bugs (stale data).

**Mitigation:**
- TTL-based cache expiration (auto-invalidation)
- Explicit cache invalidation on writes
- Cache versioning for critical data

### Risk 3: Increased Code Complexity
**Risk:** DataAccessManager adds abstraction layer, increasing code complexity.

**Mitigation:**
- Clear documentation and examples
- Gradual migration (not all-at-once)
- Code reviews to ensure maintainability

### Risk 4: Memory Usage
**Risk:** In-memory caching increases application memory usage.

**Mitigation:**
- Limit cache size (LRU eviction)
- Monitor memory usage
- Consider Redis if memory pressure

---

## Open Questions

1. **Redis vs. In-Memory Caching?**
   - Start with in-memory, add Redis if needed for multi-instance scale?

2. **Composite Endpoints vs. GraphQL?**
   - Composite endpoints simpler, but GraphQL more flexible?
   - Start with composite endpoints, consider GraphQL later?

3. **Synchronous vs. Async View Updates?**
   - Synchronous: Consistent but slower writes
   - Async: Faster writes but eventual consistency

4. **Document Structure: Separate Views vs. Projections?**
   - Separate views: Better read performance, more complex writes
   - Projections: Simpler, but still transfer document metadata

---

## Conclusion

**Current State:** We have a **systemic problem** with too many database calls, not just individual endpoint performance issues.

**Solution:** A **strategic architecture overhaul** focusing on:
1. Batching related queries
2. Caching frequently-accessed data
3. Consolidating API calls
4. Optimizing data structures

**Approach:** **Don't fix symptoms. Fix the architecture.**

This requires **2-3 months of focused work** but will result in a **scalable, maintainable system** that can handle hundreds of concurrent users.

---

## Related Documents

- `docs/gameplay_optimization/Full_Season_Team_Stats.md` - Performance issues identified
- `docs/gameplay_optimization/API_Call_Data_Optimization.md` - API endpoint optimization plan
- `docs/To Do/data_persistence_caching_strategy.md` - Client-side caching strategy

---

**Next Steps:**
1. Review and align on this approach
2. Prioritize phases based on immediate needs
3. Create detailed implementation plans for Phase 1
4. Begin Phase 1: Critical Fixes (N+1 queries, indexes, connection pool)

