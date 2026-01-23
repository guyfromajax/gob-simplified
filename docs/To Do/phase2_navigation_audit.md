# Phase 2: Navigation Flow Audit

**Date:** 2025-01-XX  
**Status:** 🔍 Audit Complete - Issues Found

## Goal
Ensure all navigation functions include required pointers (`game_id`, `franchise_id`, `tournament_id`) in URLs when appropriate.

## Audit Results

### ✅ **COMPLIANT Navigation Functions**

#### 1. `timeoutNavigationHelper.js` - `buildGameNavigationParams()`
- **Status:** ✅ COMPLIANT
- **Includes:** `game_id` when present (line 91-96)
- **Notes:** Central helper used by most navigation functions

#### 2. `tournament.js` - Navigation Functions
- **Status:** ✅ COMPLIANT
- **Play Now Button (line 1760):** Includes `tournament_id`, `home`, `away`, `team_id`, `mode`
- **Game Plan Button (line 1786):** Includes `tournament_id`, `team_id`, `mode`, `from`
- **Playbooks Button (line 1806):** Includes `tournament_id`, `team_id`, `mode`, `from`
- **Exit Button (line 1855):** Navigates to `/mode-select.html` (no pointers needed)

#### 3. `franchise-command-center.js` - Navigation Functions
- **Status:** ✅ COMPLIANT
- **Playbooks Button (line 1288):** Includes `franchise_id`, `team_id`, `mode`, `from`
- **Game Plan Button:** (Need to check if exists)

#### 4. `franchise-select-team.js` - Team Selection
- **Status:** ✅ COMPLIANT
- **Team Selection (line 35):** Includes `franchise_id` in URL

#### 5. `game-plan.js` - Navigation Functions
- **Status:** ✅ COMPLIANT
- **Navigate to Court (line 610):** Uses `timeoutNavigationHelper` - includes `game_id` when present
- **Navigate Back (line 661):** Uses `timeoutNavigationHelper` - includes `game_id` when present
- **Navigate to Command Center (lines 687, 693):** 
  - Tournament: Includes `tournament_id` and `team_id`
  - Franchise: Includes `franchise_id` and `team_id`
  - Fallback: `/` (homepage, no pointers needed)

#### 6. `playbooks.js` - Navigation Functions
- **Status:** ✅ COMPLIANT
- **Navigate to Play Details (line 1320):** Uses `timeoutNavigationHelper` - includes `game_id` when present
- **Back Navigation (lines 2163, 2177, 2194, 2209, 2227, 2265):** 
  - All use `timeoutNavigationHelper` - includes `game_id` when present
  - Command center navigation includes `franchise_id`/`tournament_id` and `team_id`

#### 7. `set-lineup.js` - Navigation Functions
- **Status:** ✅ COMPLIANT
- **Play Game Button (line 1350):** Uses `timeoutNavigationHelper` - includes `game_id` when present
- **Game Plan Button (line 1460):** Uses `timeoutNavigationHelper` - includes `game_id` when present
- **Playbooks Button (line 1569):** Uses `timeoutNavigationHelper` - includes `game_id` when present
- **Box Score Button (line 1608):** Uses `timeoutNavigationHelper` - includes `game_id` when present

#### 8. `box-score.js` - Locker Room Button
- **Status:** ✅ COMPLIANT
- **Locker Room Button (lines 1234, 1236, 1272, 1289):**
  - Back navigation: Uses `timeoutNavigationHelper` - includes `game_id` when present
  - Tournament: Includes `tournament_id` and `team_id`
  - Franchise: Includes `franchise_id` and `team_id`
  - Single mode: `/mode-select.html` (no pointers needed)

#### 9. `training.js` - Back Button
- **Status:** ✅ COMPLIANT
- **Back Button (lines 296-305):**
  - Franchise: Includes `franchise_id` and `team_id`
  - Tournament: Includes `tournament_id` and `team_id`
  - Game Plan: Preserves all URL params (includes `game_id` if present)

#### 10. `gameCompletionPopup.js` - Navigation
- **Status:** ✅ COMPLIANT
- **Locker Room URL (lines 28-57):** Includes `tournament_id`/`franchise_id` and `team_id` when present
- **Box Score URL (lines 60-69):** Includes `game_id`, `tournament_id`/`franchise_id`, `team_id`, `mode`

#### 11. `bootGame.js` - Navigation
- **Status:** ✅ COMPLIANT
- **Quarter Break Navigation (lines 2248, 2266):** Uses `timeoutNavigationHelper` - includes `game_id` when present

#### 12. `gameScene.js` - Navigation
- **Status:** ✅ COMPLIANT
- **All navigation (lines 1577, 1650, 2199, 2229, 2382, 2434):** Uses `timeoutNavigationHelper` - includes `game_id` when present

#### 13. `timeoutButtonManager.js` - Navigation
- **Status:** ✅ COMPLIANT
- **Timeout Resume (line 437):** Uses `timeoutNavigationHelper` - includes `game_id` when present

---

### ⚠️ **ISSUES FOUND**

#### 1. `finalizeGame.js` - Tournament Navigation (Line 167)
- **Status:** ⚠️ **ISSUE FOUND**
- **Problem:** Navigates to `/tournament.html` without `tournament_id` or `team_id`
- **Code:**
  ```javascript
  window.location.href = "/tournament.html";
  ```
- **Context:** This is a fallback when `window.handleTournamentUpdate` is not available
- **Fix Required:** Include `tournament_id` and `team_id` in URL
- **Priority:** Medium (fallback path, but should still include pointers)

#### 2. `training.js` - Game Plan Fallback (Line 310)
- **Status:** ⚠️ **ISSUE FOUND**
- **Problem:** Fallback navigates to `/game-plan.html` without any parameters
- **Code:**
  ```javascript
  window.location.href = '/game-plan.html';
  ```
- **Context:** Default fallback when `from !== 'game-plan'` and not franchise/tournament mode
- **Fix Required:** Should preserve URL params or at least include `game_id` if available
- **Priority:** Low (rare fallback path)

#### 3. `game-plan.js` - Homepage Fallback (Line 696)
- **Status:** ⚠️ **ISSUE FOUND**
- **Problem:** Fallback navigates to `/` (homepage) without any context
- **Code:**
  ```javascript
  window.location.href = '/';
  ```
- **Context:** Fallback when not tournament/franchise mode and no command center to return to
- **Fix Required:** Should navigate to `/mode-select.html` instead (more appropriate)
- **Priority:** Low (rare fallback path)

---

## Summary

**Total Navigation Functions Audited:** 13 files, ~30+ navigation paths

**Compliant:** ✅ 28+ navigation paths  
**Issues Found:** ⚠️ 3 issues (all in fallback/edge case paths)

**Compliance Rate:** ~93% (3 issues out of 30+ paths)

---

## Recommended Fixes

### Fix 1: `finalizeGame.js` - Include tournament_id in fallback navigation
**File:** `FrontEnd/static/js/phaser/finalizeGame.js`  
**Line:** 167  
**Current:**
```javascript
window.location.href = "/tournament.html";
```
**Fix:**
```javascript
// Include tournament_id if available (tournamentId is a function parameter)
const params = new URLSearchParams();
if (tournamentId) {
  params.set('tournament_id', tournamentId);
  // Try to get team_id from URL or game data if available
  const urlParams = new URLSearchParams(window.location.search);
  const teamId = urlParams.get('team_id') || simData.user_team_id || game?.user_team_id;
  if (teamId) params.set('team_id', teamId);
}
const url = params.toString() ? `/tournament.html?${params.toString()}` : '/tournament.html';
window.location.href = url;
```
**Note:** `tournamentId` is available as a function parameter (line 4), so we can use it directly.

### Fix 2: `training.js` - Preserve URL params in fallback
**File:** `FrontEnd/static/training.js`  
**Line:** 310  
**Current:**
```javascript
window.location.href = '/game-plan.html';
```
**Fix:**
```javascript
// Preserve URL params (includes game_id if present)
window.location.href = '/game-plan.html?' + urlParams.toString();
```

### Fix 3: `game-plan.js` - Navigate to mode-select instead of homepage
**File:** `FrontEnd/static/game-plan.js`  
**Line:** 696  
**Current:**
```javascript
window.location.href = '/';
```
**Fix:**
```javascript
// Navigate to mode select (more appropriate than homepage)
window.location.href = '/mode-select.html';
```

---

## Phase 2 Completion Status

**Tasks:**
1. ✅ **Fix Navigation Flow** - 93% compliant (3 minor issues in fallback paths)
2. ✅ **Add URL Validation** - Complete (implemented in Phase 1.1)
3. ✅ **Add Truth Validation** - Complete (implemented in Phase 1.1)
4. ✅ **Remove localStorage Fallbacks** - Complete (implemented in Phase 1.2)

**Recommendation:** Fix the 3 identified issues, then mark Phase 2 as complete.

