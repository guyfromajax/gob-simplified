# Performance Diagnostic Plan

**Date Created:** January 11, 2026  
**Status:** 🔍 IN PROGRESS  
**Priority:** 🔴 CRITICAL  
**Related:** Task 2 (Database Optimization) from Go Live Plan

## Problem Statement

Performance is still extremely slow, even on the **first game instance** (small document). This suggests the bottleneck is NOT:
- ❌ Game document size (new games are small)
- ❌ Frontend processing (we fixed O(n²) loops)
- ❌ Missing projections (we added them)

**The bottleneck must be something else.**

---

## Diagnostic Approach: Measure, Don't Guess

### Step 1: Add Performance Logging (30 minutes) 🔴 START HERE

**Goal:** Measure actual time spent in each operation

**Add timing logs to key endpoints:**

```python
import time

# In /api/game/{game_id}
start = time.time()
saved = games_collection.find_one({"_id": game_id}, projection)
query_time = (time.time() - start) * 1000  # ms
doc_size = len(str(saved)) if saved else 0
logging.warning(f"⏱️ [PERF] /api/game/{game_id} - DB query: {query_time:.2f}ms, doc_size: {doc_size} bytes")

# Measure processing time
start = time.time()
# ... process data ...
process_time = (time.time() - start) * 1000
logging.warning(f"⏱️ [PERF] /api/game/{game_id} - Processing: {process_time:.2f}ms")
```

**What to measure:**
1. Database query time (find_one, update_one)
2. Data processing time (merging, transforming)
3. JSON serialization time
4. Total endpoint time

**Endpoints to instrument:**
- `/api/game/{game_id}`
- `/api/playbooks`
- `/api/gameplan`
- `/api/simulate-quarter`

---

### Step 2: Check Railway Logs (15 minutes)

**What to look for:**
1. **Slow queries:**
   - Any queries taking >100ms
   - Connection pool exhaustion messages
   - Timeout errors

2. **Resource constraints:**
   - CPU throttling messages
   - Memory warnings
   - Instance restart messages

3. **Database connection issues:**
   - Connection pool errors
   - MongoDB connection failures
   - Network timeouts

**How to check:**
- Railway dashboard → Project → Deployments → Latest deployment → Logs
- Filter for: "PERF", "ERROR", "WARNING", "timeout", "connection"

---

### Step 3: Check MongoDB Connection Pool (15 minutes) 🔴 HIGH PRIORITY

**Current setup:**
- `MongoClient(uri, serverSelectionTimeoutMS=5000)` - **No connection pool configuration!**
- Default pool size: 100 connections
- But no monitoring or logging

**What to check:**
1. **Connection pool status:**
   - Current connections in use
   - Connections waiting
   - Connection acquisition time

2. **MongoDB Atlas metrics:**
   - Connection count (is it maxed out?)
   - Query execution time
   - Network latency

**How to diagnose:**
```python
# Add to db.py
from pymongo import monitoring

class ConnectionLogger(monitoring.CommandListener):
    def started(self, event):
        logging.warning(f"⏱️ [DB] Query started: {event.command_name}, request_id: {event.request_id}")
    
    def succeeded(self, event):
        duration = (event.duration_micros / 1000)  # Convert to ms
        logging.warning(f"⏱️ [DB] Query succeeded: {event.command_name}, duration: {duration:.2f}ms")
    
    def failed(self, event):
        logging.error(f"❌ [DB] Query failed: {event.command_name}, error: {event.failure}")

# Register listener
monitoring.register(ConnectionLogger())
```

---

### Step 4: Measure Network Latency (15 minutes)

**Goal:** Determine if network latency is the bottleneck

**Test from production/staging:**
1. **Frontend → Backend:**
   - Use browser DevTools Network tab
   - Check "Time" column (total time)
   - Check "Waiting (TTFB)" (time to first byte)

2. **Backend → MongoDB:**
   - Add test endpoint that pings MongoDB
   - Measure round-trip time

**Expected latencies:**
- Frontend → Backend: 50-200ms (cross-cloud)
- Backend → MongoDB: 20-100ms (cloud-to-cloud)
- **If latencies are >500ms, network is the bottleneck**

---

### Step 5: Check for N+1 Query Problems (15 minutes) 🔴 HIGH PRIORITY

**Symptoms:**
- Multiple sequential queries
- Each query waits for previous to complete
- Total time = sum of all query times

**How to diagnose:**
- Add logging to count queries per request
- Check if queries are sequential (not parallel)
- Look for loops that make database calls

**Example:**
```python
# Bad: N+1 queries
for player in players:
    stats = db.players.find_one({"_id": player.id})  # Query in loop!

# Good: Batch query
player_ids = [p.id for p in players]
stats = db.players.find({"_id": {"$in": player_ids}})  # Single query
```

---

### Step 6: Check Railway Instance Performance (15 minutes)

**What to check:**
1. **Instance metrics:**
   - CPU usage (is it maxed out?)
   - Memory usage (is it swapping?)
   - Network I/O (is it saturated?)

2. **Instance type:**
   - What instance type is being used?
   - Is it being throttled under load?
   - Are there resource limits?

**How to check:**
- Railway dashboard → Project → Metrics tab
- Check CPU, Memory, Network graphs
- Look for throttling patterns

---

## Most Likely Culprits (Based on Symptoms)

### 1. **Database Connection Pool Issues** 🔴 HIGHEST PROBABILITY

**Why:**
- Slow even on new games (suggests connection issue, not document size)
- Gets slower over time (connections not being released)
- No connection pool configuration (using defaults)

**How to diagnose:**
- Add connection pool monitoring
- Check MongoDB Atlas connection count
- Log connection acquisition time

**Fix:**
- Configure connection pool properly
- Ensure connections are properly closed
- Add connection pool monitoring

---

### 2. **N+1 Query Problems** 🔴 HIGH PROBABILITY

**Why:**
- Slow even on new games (suggests multiple queries)
- Sequential queries amplify network latency
- We fixed some N+1 issues, but may have missed others

**How to diagnose:**
- Count queries per request
- Check if queries are in loops
- Look for sequential queries

**Fix:**
- Batch queries using `$in` operator
- Use aggregation pipelines
- Make queries parallel where possible

---

### 3. **MongoDB Atlas Performance Issues** 🟡 MEDIUM PROBABILITY

**Why:**
- Slow queries even for small documents
- Consistent slowness across all operations
- Network latency to MongoDB is high

**How to diagnose:**
- Check MongoDB Atlas metrics (query time, CPU, memory)
- Test direct MongoDB connection latency
- Check if queries are using indexes

**Fix:**
- Upgrade MongoDB Atlas tier
- Add missing indexes
- Optimize query patterns

---

### 4. **Railway Instance Throttling** 🟡 MEDIUM PROBABILITY

**Why:**
- Slow even on new games (suggests instance issue)
- Gets slower under load
- CPU/Memory maxed out

**How to diagnose:**
- Check Railway metrics (CPU, Memory)
- Check instance type and limits
- Look for throttling patterns

**Fix:**
- Upgrade Railway instance
- Optimize resource usage
- Add more instances (if needed)

---

## Recommended Diagnostic Order

1. **Add performance logging** (30 min) - Get actual measurements 🔴 START HERE
2. **Check for N+1 queries** (15 min) - Count queries per request
3. **Check connection pool** (15 min) - Monitor connection usage
4. **Check Railway logs** (15 min) - Look for obvious errors
5. **Check MongoDB Atlas metrics** (15 min) - Database performance
6. **Check Railway instance metrics** (15 min) - Instance performance

**Total time: ~2 hours to identify the bottleneck**

---

## Quick Diagnostic Questions

**Answer these to narrow down the issue:**

1. **Is it slow on ALL endpoints or just specific ones?**
   - If all: Connection pool or instance issue
   - If specific: That endpoint has a problem

2. **Is it slow from the start or gets slower over time?**
   - From start: Configuration issue
   - Gets slower: Memory leak or connection pool exhaustion

3. **What does browser DevTools Network tab show?**
   - Long "Waiting (TTFB)": Backend is slow
   - Long "Content Download": Large response (but we fixed this)
   - Long total time: Multiple issues

4. **What do Railway logs show?**
   - Slow queries: Database issue
   - Connection errors: Connection pool issue
   - No errors: Processing issue

---

## Next Steps

1. **Immediate:** Add performance logging to key endpoints
2. **Then:** Check Railway logs for slow queries/connections
3. **Then:** Count queries per request (N+1 check)
4. **Finally:** Fix the identified bottleneck

**The key is to measure, not guess!**
