# Frontend Performance Fix Plan - Lineup Screen 5-10s Bottleneck

**Date Created:** January 11, 2026  
**Status:** ⏳ IN PROGRESS  
**Priority:** 🔴 CRITICAL - Blocking user experience  
**Related:** Task 2 (Database Optimization) from Go Live Plan

## Problem Summary

**Symptom:** Lineup screen takes 5-10 seconds to display after network request completes (294ms).  
**Location:** `FrontEnd/static/set-lineup.js`  
**Root Cause:** Frontend JavaScript processing bottleneck (not network/backend)

## Identified Bottlenecks

### 1. **Nested Loops in `loadRoster()` (Lines 221-281)**
**Problem:**
```javascript
gamePlayers.forEach(gp => {
  // O(n) loop
  let rosterPlayer = roster.find(p => { ... }); // O(n) nested search
  if (!rosterPlayer) {
    rosterPlayer = roster.find(p => p.name === gp.name); // O(n) nested search again
  }
  // ... processing ...
});
```
**Complexity:** O(n²) - For each game player, search entire roster twice  
**Impact:** With 15 players × 2 searches = 30 operations, but scales poorly

**Fix:** Use Map/Set for O(1) lookups:
```javascript
// Build lookup maps once (O(n))
const rosterById = new Map(roster.map(p => [String(p._id || p.playerId || p.player_id), p]));
const rosterByName = new Map(roster.map(p => [p.name, p]));

// Then O(1) lookups
gamePlayers.forEach(gp => {
  const playerId = String(gp._id || gp.playerId || gp.player_id);
  let rosterPlayer = rosterById.get(playerId) || rosterByName.get(gp.name);
  // ... processing ...
});
```
**Expected Improvement:** 50-80% reduction in processing time

---

### 2. **Multiple Sequential Roster Iterations**
**Problem:**
- Line 276-281: `roster.forEach()` - Build playerMap
- Line 295-298: `roster.sort()` - Sort roster
- Line 300-303: `roster.forEach()` - Build playerMap AGAIN (duplicate!)
- Line 304: `renderRoster()` - Render (another iteration)

**Fix:** Combine operations:
```javascript
// Sort first, then build playerMap once
roster.sort((a, b) => {
  const diff = getRT(b) - getRT(a);
  return diff !== 0 ? diff : a._idx - b._idx;
});

// Build playerMap once (after sorting)
roster.forEach(p => {
  delete p._idx;
  playerMap[p._id] = p;
});

renderRoster();
```
**Expected Improvement:** 20-30% reduction

---

### 3. **Synchronous DOM Operations in `renderRoster()`**
**Problem:**
- Line 315: `tbody.innerHTML = ''` - Clears DOM (triggers reflow)
- Line 318-350: `roster.map()` - Calculates RT for all players
- Line 352-400: `rosterDataForSorting.forEach()` - Creates DOM elements synchronously

**Fix:** Batch DOM updates using DocumentFragment:
```javascript
function renderRoster() {
  const tbody = document.getElementById('roster-body');
  if (!tbody) return;
  
  // Calculate RT once (keep this)
  rosterDataForSorting = roster.map(p => {
    // ... RT calculation ...
  });
  
  // Use DocumentFragment to batch DOM updates
  const fragment = document.createDocumentFragment();
  
  rosterDataForSorting.forEach(p => {
    const row = createRosterRow(p); // Extract to function
    fragment.appendChild(row);
  });
  
  // Single DOM update (triggers one reflow)
  tbody.appendChild(fragment);
}
```
**Expected Improvement:** 30-50% reduction in rendering time

---

### 4. **Heavy Processing in `renderPlayerView()` (Lines 1263-1306)**
**Problem:**
- Line 1270-1295: Multiple sorts and maps (O(n log n) + O(n))
- Line 1297-1300: `sortedPlayers.forEach()` - Creates player cards synchronously
- Each `createPlayerCard()` does heavy DOM manipulation

**Fix:** 
1. Optimize sorting (do once, cache result)
2. Use DocumentFragment for batching
3. Defer non-critical rendering (tooltips, images)

**Expected Improvement:** 40-60% reduction

---

### 5. **Synchronous Image Loading**
**Problem:**
- Player images load synchronously, blocking rendering
- `onerror` handlers fire synchronously

**Fix:** Lazy load images, use `loading="lazy"` attribute:
```javascript
img.loading = 'lazy';
img.decoding = 'async';
```

---

## Implementation Plan

### Phase 1: Quick Wins (1-2 hours)
**Priority:** 🔴 HIGH - Biggest impact, lowest risk

1. **Fix nested loops** (Bottleneck #1)
   - Replace `find()` with Map lookups
   - Expected: 50-80% improvement

2. **Remove duplicate playerMap building** (Bottleneck #2)
   - Build playerMap once after sorting
   - Expected: 20-30% improvement

**Total Expected Improvement:** 60-85% reduction (5-10s → 1-2s)

---

### Phase 2: DOM Optimization (1-2 hours)
**Priority:** 🟡 MEDIUM - Good improvement, low risk

3. **Batch DOM updates** (Bottleneck #3)
   - Use DocumentFragment
   - Expected: 30-50% improvement

4. **Optimize renderPlayerView** (Bottleneck #4)
   - Cache sorted results
   - Batch DOM operations
   - Expected: 40-60% improvement

**Total Expected Improvement:** Additional 30-50% reduction (1-2s → 0.5-1s)

---

### Phase 3: Advanced Optimizations (1-2 hours)
**Priority:** 🟢 LOW - Nice to have, can defer

5. **Lazy load images**
6. **Virtual scrolling** (if roster > 20 players)
7. **Web Workers** for heavy calculations (if still needed)

---

## Testing Plan

1. **Before fixes:**
   - Measure current time: Network request → UI visible
   - Use browser Performance tab
   - Document baseline

2. **After Phase 1:**
   - Re-measure
   - Verify improvement
   - Check for regressions

3. **After Phase 2:**
   - Final measurement
   - Verify <1s target achieved
   - Full regression testing

---

## Success Criteria

- **Target:** Lineup screen loads in <1 second after network request
- **Current:** 5-10 seconds
- **Improvement Needed:** 80-90% reduction

---

## Next Steps

1. **Immediate:** Implement Phase 1 fixes (nested loops + duplicate operations)
2. **Then:** Test and measure improvement
3. **If still slow:** Implement Phase 2 (DOM batching)
4. **If still slow:** Profile with browser DevTools to find remaining bottlenecks

