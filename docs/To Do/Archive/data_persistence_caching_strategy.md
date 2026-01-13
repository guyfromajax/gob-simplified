# Data Persistence Caching Strategy

> **Status:** Proposed Enhancement  
> **Priority:** Medium  
> **Created:** February 2025  
> **Related:** Data & Settings Persistence refactor (February 2025)

---

## Problem Statement

### Current Situation

After removing localStorage caching for persistent data (February 2025 refactor), we've achieved **data consistency** but introduced **performance trade-offs**:

1. **Page Load Delays:** Playbooks, Game Plan, and court.html pages show a brief delay while waiting for API responses
2. **Flash of Empty State:** Pages render with default/empty data, then update when API data arrives
3. **Network Dependency:** Every page load requires a fresh API call, even for data that rarely changes
4. **Perceived Performance:** Users see loading states and data updates, which feels slower than instant localStorage

### Root Cause

- **No client-side cache:** All data must be fetched from database on every page load
- **Network latency:** API calls add 50-200ms+ delay per request
- **Synchronous loading:** UI renders before data arrives, causing flash of empty state

### Impact

- **User Experience:** Noticeable delays on page transitions
- **Perceived Performance:** Feels slower than previous localStorage approach
- **Network Usage:** Redundant API calls for data that hasn't changed

---

## Goals

1. **Maintain Data Consistency:** Database remains single source of truth
2. **Improve Perceived Performance:** Instant page loads with cached data
3. **Background Refresh:** Update cache in background, not blocking UI
4. **Smart Invalidation:** Cache invalidates when data changes
5. **SS&S Architecture:** Simple, stable, scalable caching layer

---

## Proposed Solution: Multi-Layer Caching Strategy

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    User Action                          │
│              (Navigate to Playbooks)                    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Service Worker Cache                       │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 1. Check Cache (instant)                          │  │
│  │    - If fresh (< 5 min old) → Return cached      │  │
│  │    - If stale (> 5 min old) → Return cached +     │  │
│  │      background refresh                           │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              IndexedDB Cache (Fallback)                 │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 2. If Service Worker cache miss → Check IndexedDB│  │
│  │    - Return cached data immediately              │  │
│  │    - Background refresh from API                  │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              API Request (Last Resort)                   │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 3. If no cache → Fetch from API                   │  │
│  │    - Store in Service Worker cache               │  │
│  │    - Store in IndexedDB cache                     │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: HTTP Cache Headers (Quick Win)

**Goal:** Leverage browser's built-in HTTP cache

**Implementation:**
- Add `Cache-Control` headers to API responses
- Use `ETag` for cache validation
- Set appropriate `max-age` based on data type

**Cache Durations:**
- **Game Plan Settings:** `max-age=300` (5 minutes) - Changes infrequently
- **Playbooks Settings:** `max-age=300` (5 minutes) - Changes infrequently
- **Game State:** `max-age=60` (1 minute) - Changes during gameplay
- **Team/Player Data:** `max-age=600` (10 minutes) - Changes rarely

**Benefits:**
- Zero code changes required
- Browser handles caching automatically
- Reduces redundant API calls
- Works immediately

**Files to Update:**
- `BackEnd/api/gameplan_routes.py` - Add cache headers to GET endpoints
- `BackEnd/api/gameplan_routes.py` - Add cache headers to GET playbooks endpoint

---

### Phase 2: Skeleton Loading States (UX Improvement)

**Goal:** Improve perceived performance with loading states

**Implementation:**
- Add skeleton/loading UI components
- Show skeleton immediately on page load
- Replace with data when API response arrives
- Better than flash of empty/default data

**Components:**
- `PlaybooksSkeleton` - Loading state for playbooks page
- `GamePlanSkeleton` - Loading state for game plan page
- `CourtSkeleton` - Loading state for gameplay screen

**Benefits:**
- Better UX than empty state
- Users understand data is loading
- No code changes to data layer

**Files to Update:**
- `FrontEnd/static/playbooks.js` - Add skeleton rendering
- `FrontEnd/static/game-plan.js` - Add skeleton rendering
- `FrontEnd/static/js/phaser/bootGame.js` - Add skeleton for game plan loading

---

### Phase 3: Service Worker + Cache API (Production Ready)

**Goal:** Client-side caching with background refresh

**Implementation:**

#### 3.1 Service Worker Setup

**File:** `FrontEnd/static/sw.js` (new file)

```javascript
// Service Worker for API response caching
const CACHE_NAME = 'gob-api-cache-v1';
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

// Cache API responses
self.addEventListener('fetch', (event) => {
  if (event.request.url.includes('/api/gameplan') || 
      event.request.url.includes('/api/playbooks')) {
    event.respondWith(cacheFirstStrategy(event.request));
  }
});

async function cacheFirstStrategy(request) {
  const cache = await caches.open(CACHE_NAME);
  const cachedResponse = await cache.match(request);
  
  if (cachedResponse) {
    const cachedTime = parseInt(cachedResponse.headers.get('x-cached-time'));
    const age = Date.now() - cachedTime;
    
    // If cache is fresh (< 5 min), return immediately
    if (age < CACHE_DURATION) {
      return cachedResponse;
    }
    
    // If cache is stale, return cached + refresh in background
    refreshCache(request, cache);
    return cachedResponse;
  }
  
  // No cache, fetch and store
  const response = await fetch(request);
  const responseClone = response.clone();
  responseClone.headers.set('x-cached-time', Date.now().toString());
  cache.put(request, responseClone);
  return response;
}

async function refreshCache(request, cache) {
  try {
    const response = await fetch(request);
    const responseClone = response.clone();
    responseClone.headers.set('x-cached-time', Date.now().toString());
    cache.put(request, responseClone);
  } catch (error) {
    console.error('Background cache refresh failed:', error);
  }
}
```

#### 3.2 Service Worker Registration

**File:** `FrontEnd/static/js/shared/serviceWorkerRegistration.js` (new file)

```javascript
// Register Service Worker for API caching
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js')
      .then(registration => console.log('SW registered:', registration))
      .catch(error => console.error('SW registration failed:', error));
  });
}
```

**Benefits:**
- Instant page loads from cache
- Background refresh keeps data fresh
- Works offline (shows cached data)
- No changes to existing API code

**Files to Create:**
- `FrontEnd/static/sw.js` - Service Worker implementation
- `FrontEnd/static/js/shared/serviceWorkerRegistration.js` - Registration script

**Files to Update:**
- `FrontEnd/static/playbooks.html` - Include service worker registration
- `FrontEnd/static/game-plan.html` - Include service worker registration
- `FrontEnd/static/court.html` - Include service worker registration

---

### Phase 4: IndexedDB Cache (Robust Fallback)

**Goal:** Persistent client-side database for caching

**Implementation:**

#### 4.1 IndexedDB Cache Manager

**File:** `FrontEnd/static/js/shared/indexedDBCache.js` (new file)

```javascript
// IndexedDB cache manager for API responses
class IndexedDBCache {
  constructor() {
    this.dbName = 'gob-api-cache';
    this.version = 1;
    this.db = null;
  }
  
  async init() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.version);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve(this.db);
      };
      
      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains('apiCache')) {
          const store = db.createObjectStore('apiCache', { keyPath: 'url' });
          store.createIndex('timestamp', 'timestamp', { unique: false });
        }
      };
    });
  }
  
  async get(url) {
    if (!this.db) await this.init();
    const transaction = this.db.transaction(['apiCache'], 'readonly');
    const store = transaction.objectStore('apiCache');
    const request = store.get(url);
    
    return new Promise((resolve, reject) => {
      request.onsuccess = () => {
        const cached = request.result;
        if (cached && this.isFresh(cached.timestamp)) {
          resolve(cached.data);
        } else {
          resolve(null);
        }
      };
      request.onerror = () => reject(request.error);
    });
  }
  
  async set(url, data) {
    if (!this.db) await this.init();
    const transaction = this.db.transaction(['apiCache'], 'readwrite');
    const store = transaction.objectStore('apiCache');
    store.put({ url, data, timestamp: Date.now() });
  }
  
  isFresh(timestamp) {
    const age = Date.now() - timestamp;
    return age < 5 * 60 * 1000; // 5 minutes
  }
  
  async invalidate(url) {
    if (!this.db) await this.init();
    const transaction = this.db.transaction(['apiCache'], 'readwrite');
    const store = transaction.objectStore('apiCache');
    store.delete(url);
  }
}

export const apiCache = new IndexedDBCache();
```

#### 4.2 Integration with Existing Code

**File:** `FrontEnd/static/playbooks.js` (update)

```javascript
import { apiCache } from './js/shared/indexedDBCache.js';

async loadPlaybookPercentagesFromAPI() {
  const url = `/api/playbooks?${params.toString()}`;
  
  // Check IndexedDB cache first
  const cached = await apiCache.get(url);
  if (cached) {
    this.savedPlaybookPercentages = cached;
    this.applyPercentages();
    // Background refresh
    this.refreshPlaybookPercentages(url);
    return;
  }
  
  // No cache, fetch from API
  const response = await fetch(url);
  const data = await response.json();
  await apiCache.set(url, data);
  this.savedPlaybookPercentages = data;
  this.applyPercentages();
}

async refreshPlaybookPercentages(url) {
  const response = await fetch(url);
  const data = await response.json();
  await apiCache.set(url, data);
  // Only update UI if data changed
  if (JSON.stringify(data) !== JSON.stringify(this.savedPlaybookPercentages)) {
    this.savedPlaybookPercentages = data;
    this.applyPercentages();
  }
}
```

**Benefits:**
- Persistent cache (survives page reloads)
- Works as fallback if Service Worker unavailable
- Can store complex data structures
- Better performance than localStorage

**Files to Create:**
- `FrontEnd/static/js/shared/indexedDBCache.js` - IndexedDB cache manager

**Files to Update:**
- `FrontEnd/static/playbooks.js` - Integrate IndexedDB cache
- `FrontEnd/static/game-plan.js` - Integrate IndexedDB cache
- `FrontEnd/static/js/phaser/bootGame.js` - Integrate IndexedDB cache

---

### Phase 5: Cache Invalidation Strategy

**Goal:** Ensure cache updates when data changes

**Implementation:**

#### 5.1 Invalidation on Save

**Pattern:** Invalidate cache when user saves data

```javascript
// In playbooks.js - after saving
async savePlaybookSettings() {
  const response = await fetch('/api/playbooks', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
  
  if (response.ok) {
    // Invalidate cache for this endpoint
    const url = `/api/playbooks?mode=${mode}&team_id=${teamId}...`;
    await apiCache.invalidate(url);
    // Service Worker cache will be invalidated on next fetch
  }
}
```

#### 5.2 Version-Based Invalidation

**Pattern:** Use version numbers to invalidate all caches

```javascript
// Backend returns version with data
{
  "data": {...},
  "version": "2025-02-15-v1"
}

// Frontend checks version
const cached = await apiCache.get(url);
if (cached && cached.version !== currentVersion) {
  // Cache is stale, refresh
  await apiCache.invalidate(url);
}
```

#### 5.3 Time-Based Invalidation

**Pattern:** Cache expires after set duration (already implemented in Phase 3/4)

**Benefits:**
- Cache always reflects latest data after saves
- No stale data issues
- Automatic expiration prevents old data

---

## Implementation Priority

### Immediate (Quick Wins)
1. ✅ **Phase 1: HTTP Cache Headers** - 30 minutes
2. ✅ **Phase 2: Skeleton Loading States** - 2-3 hours

### Short Term (1-2 weeks)
3. ✅ **Phase 3: Service Worker + Cache API** - 1 week
4. ✅ **Phase 5: Cache Invalidation** - 2-3 days

### Medium Term (Future Enhancement)
5. ✅ **Phase 4: IndexedDB Cache** - 1 week (if Service Worker insufficient)

---

## Testing Strategy

### Performance Metrics
- **Time to First Paint:** Should be < 100ms with cache
- **Time to Interactive:** Should be < 200ms with cache
- **API Call Reduction:** Should reduce API calls by 70-80% on repeat visits

### Test Cases
1. **First Visit:** No cache, should fetch from API
2. **Repeat Visit:** Should load from cache instantly
3. **Stale Cache:** Should show cached data + background refresh
4. **After Save:** Should invalidate cache and refresh
5. **Offline:** Should show cached data if available

---

## Risks & Mitigations

### Risk 1: Stale Data
- **Mitigation:** Time-based expiration + invalidation on save
- **Mitigation:** Background refresh for stale cache

### Risk 2: Cache Size
- **Mitigation:** Limit cache size (e.g., max 50MB)
- **Mitigation:** LRU eviction for old entries

### Risk 3: Service Worker Compatibility
- **Mitigation:** Feature detection + IndexedDB fallback
- **Mitigation:** Graceful degradation to API-only

### Risk 4: Complex Implementation
- **Mitigation:** Phased approach (start with HTTP headers)
- **Mitigation:** Incremental rollout per phase

---

## Success Criteria

1. ✅ **Page Load Time:** < 200ms for cached pages
2. ✅ **API Call Reduction:** 70-80% reduction on repeat visits
3. ✅ **User Experience:** No visible loading delays
4. ✅ **Data Consistency:** Cache always reflects latest data after saves
5. ✅ **Offline Support:** Cached data available when offline

---

## Notes

- **Database remains single source of truth:** Cache is for performance only
- **Cache is transparent:** Existing code doesn't need major changes
- **Progressive enhancement:** Works without cache, better with cache
- **SS&S principle:** Simple caching layer, stable invalidation, scalable architecture

---

## References

- [MDN: Service Workers](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
- [MDN: Cache API](https://developer.mozilla.org/en-US/docs/Web/API/Cache)
- [MDN: IndexedDB](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API)
- [HTTP Caching](https://developer.mozilla.org/en-US/docs/Web/HTTP/Caching)

