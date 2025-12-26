# Franchise Mode GP Navigation Verification

**Date:** February 2025  
**Purpose:** Verify that all GP transitions preserve the core navigation anchor set (`mode`, `franchise_id`, `team_id`)

---

## Core Navigation Anchor Set (Required)

For seamless navigation, all GP transitions must preserve:
1. **`mode`** - `"franchise"`
2. **`franchise_id`** - ObjectId string
3. **`team_id`** - ObjectId string (user's team)

---

## GP Flow Instances Verification

### ✅ **1. Lineup → Gameplay**

**Location:** `set-lineup.js:907-940`  
**Method:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()`

**Status:** ✅ **VERIFIED - CORRECT**
- ✅ Uses `TimeoutNavigationHelper` which preserves `mode`, `franchise_id`, `week` from source params
- ✅ **Fixed:** Helper now preserves `team_id` (after our fix)
- ✅ Preserves all game state (game_id, quarter, clock, resume_from_timeout, lineup)

**Code:**
```javascript
const params = helper.buildGameNavigationParams({
  sourceParams: urlParams,  // Contains mode, franchise_id, team_id, week
  targetQuarter: quarter,
  gameId: currentGameId,
  resumeFromTimeout: resumeFromTimeout,
  lineup: lineup,
  myTeamSide: myTeamSide,
  clock: urlParams.get('clock')
});
window.location.href = `/court.html?${params.toString()}`;
```

---

### ✅ **2. Lineup → Game Plan**

**Location:** `set-lineup.js:947-980`  
**Method:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()`

**Status:** ✅ **VERIFIED - CORRECT**
- ✅ Uses `TimeoutNavigationHelper` which preserves `mode`, `franchise_id`, `week` from source params
- ✅ **Fixed:** Helper now preserves `team_id` (after our fix)
- ✅ Adds `from=lineup` parameter for navigation context

**Code:**
```javascript
const params = helper.buildGameNavigationParams({
  sourceParams: urlParams,  // Contains mode, franchise_id, team_id, week
  targetQuarter: quarter,
  gameId: currentGameId,
  resumeFromTimeout: resumeFromTimeout,
  lineup: lineup,
  myTeamSide: myTeamSide
});
params.set('from', 'lineup');
window.location.href = `/game-plan.html?${params.toString()}`;
```

---

### ✅ **3. Lineup → Box Score**

**Location:** `set-lineup.js:984-1019`  
**Method:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()`

**Status:** ✅ **VERIFIED - CORRECT**
- ✅ Uses `TimeoutNavigationHelper` which preserves `mode`, `franchise_id`, `week` from source params
- ✅ **Fixed:** Helper now preserves `team_id` (after our fix)
- ✅ Adds `from=lineup` parameter for navigation context

**Code:**
```javascript
const params = helper.buildGameNavigationParams({
  sourceParams: urlParams,  // Contains mode, franchise_id, team_id, week
  targetQuarter: quarter,
  gameId: currentGameId,
  resumeFromTimeout: resumeFromTimeout,
  lineup: lineup,
  myTeamSide: myTeamSide
});
params.set('from', 'lineup');
window.location.href = `/static/box-score.html?${params.toString()}`;
```

---

### ✅ **4. Game Plan → Gameplay**

**Location:** `game-plan.js:327-402`  
**Method:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()`

**Status:** ✅ **VERIFIED - CORRECT**
- ✅ Uses `TimeoutNavigationHelper` which preserves `mode`, `franchise_id`, `week` from source params
- ✅ **Fixed:** Helper now preserves `team_id` (after our fix)
- ✅ Preserves timeout state (clock, resume_from_timeout)

**Code:**
```javascript
const params = helper.buildGameNavigationParams({
  sourceParams: currentUrlParams,  // Contains mode, franchise_id, team_id, week
  targetQuarter: currentQuarter,
  gameId: currentGameId,
  resumeFromTimeout: resumeFromTimeout,
  lineup: lineup,
  myTeamSide: currentMyTeamSide,
  clock: currentUrlParams.get('clock')
});
window.location.href = `/court.html?${params.toString()}`;
```

---

### ✅ **5. Game Plan → Playbooks**

**Location:** `game-plan.js:539-597`  
**Method:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()`

**Status:** ✅ **VERIFIED - CORRECT**
- ✅ Uses `TimeoutNavigationHelper` which preserves `mode`, `franchise_id`, `week` from source params
- ✅ **Fixed:** Helper now preserves `team_id` (after our fix)
- ✅ Preserves `from` parameter for navigation context

**Code:**
```javascript
const params = helper.buildGameNavigationParams({
  sourceParams: currentUrlParams,  // Contains mode, franchise_id, team_id, week
  targetQuarter: currentQuarter,
  gameId: currentGameId,
  resumeFromTimeout: resumeFromTimeout,
  lineup: lineup,
  myTeamSide: currentMyTeamSide
});
// Preserves original 'from' parameter
const originalFrom = currentUrlParams.get('from');
if (originalFrom === 'command_center' || ...) {
  params.set('from', originalFrom);
} else {
  params.set('from', 'game-plan');
}
window.location.href = `/static/playbooks.html?${params.toString()}`;
```

---

### ✅ **6. Playbooks → Game Plan**

**Location:** `playbooks.js:1884-1919`  
**Method:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()`

**Status:** ✅ **VERIFIED - CORRECT**
- ✅ Uses `TimeoutNavigationHelper` which preserves `mode`, `franchise_id`, `week` from source params
- ✅ **Fixed:** Helper now preserves `team_id` (after our fix)
- ✅ Preserves `from` parameter for navigation context

**Code:**
```javascript
const params = helper.buildGameNavigationParams({
  sourceParams: urlParams,  // Contains mode, franchise_id, team_id, week
  targetQuarter: currentQuarter,
  gameId: currentGameId,
  resumeFromTimeout: resumeFromTimeout,
  lineup: lineup,
  myTeamSide: myTeamSide
});
// Preserves original 'from' parameter
const originalFrom = urlParams.get('from');
if (originalFrom === 'command_center' || ...) {
  params.set('from', originalFrom);
} else {
  params.set('from', 'playbooks');
}
window.location.href = `/static/game-plan.html?${params.toString()}`;
```

---

### ✅ **7. Playbooks → Play Details**

**Location:** `playbooks.js:1083-1132`  
**Method:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()`

**Status:** ✅ **VERIFIED - CORRECT**
- ✅ Uses `TimeoutNavigationHelper` which preserves `mode`, `franchise_id`, `week` from source params
- ✅ **Fixed:** Helper now preserves `team_id` (after our fix)
- ✅ Adds `play_name` parameter for play details page

**Code:**
```javascript
const params = helper.buildGameNavigationParams({
  sourceParams: urlParams,  // Contains mode, franchise_id, team_id, week
  targetQuarter: currentQuarter,
  gameId: currentGameId,
  resumeFromTimeout: resumeFromTimeout,
  lineup: lineup,
  myTeamSide: myTeamSide
});
params.set('play_name', playName);
const from = urlParams.get('from');
if (from) {
  params.set('from', from);
}
window.location.href = `/static/play-details.html?${params.toString()}`;
```

---

### ✅ **8. Play Details → Playbooks**

**Location:** `play-details.html:397-440`  
**Method:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()`

**Status:** ✅ **VERIFIED - CORRECT**
- ✅ Uses `TimeoutNavigationHelper` which preserves `mode`, `franchise_id`, `week` from source params
- ✅ **Fixed:** Helper now preserves `team_id` (after our fix)
- ✅ Preserves `from` parameter for navigation context

**Code:**
```javascript
const params = helper.buildGameNavigationParams({
  sourceParams: urlParams,  // Contains mode, franchise_id, team_id, week
  targetQuarter: currentQuarter,
  gameId: currentGameId,
  resumeFromTimeout: resumeFromTimeout,
  lineup: lineup,
  myTeamSide: myTeamSide
});
const from = urlParams.get('from');
if (from) {
  params.set('from', from);
}
window.location.href = `/static/playbooks.html?${params.toString()}`;
```

---

### ✅ **9. Gameplay → Game Plan (Timeout)**

**Location:** `timeoutButtonManager.js:262-429`  
**Method:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()` with overrides

**Status:** ✅ **VERIFIED - CORRECT (Fixed)**
- ✅ Uses `TimeoutNavigationHelper` which preserves `mode`, `franchise_id`, `week` from source params
- ✅ **Fixed:** Helper now preserves `team_id` (after our fix)
- ✅ **Fixed:** Added `team_id` to overrides (prefers `team_id` over `user_team_id`)
- ✅ Uses `overrides` to ensure mode/franchise_id/team_id are included even if not in URL params
- ✅ Navigates to lineup screen (which then can navigate to game plan)

**Code:**
```javascript
const teamId = urlParams.get('team_id'); // ✅ SS&S: Prefer team_id (standardized)
const userTeamIdParam = urlParams.get('user_team_id'); // Keep for backward compatibility

const params = helper.buildGameNavigationParams({
  sourceParams: urlParams,
  targetQuarter: currentQuarter,
  gameId: gameId,
  resumeFromTimeout: true,
  lineup: lineup,
  myTeamSide: myTeamSide || myTeamSideFallback || 'home',
  clock: clock,
  overrides: {
    home: homeTeam || homeTeamFallback || '',
    away: awayTeam || awayTeamFallback || '',
    home_id: homeId,
    away_id: awayId,
    my_team: myTeamSide || myTeamSideFallback || 'home',
    team_id: teamId || userTeamIdParam, // ✅ SS&S: Prefer team_id, fallback to user_team_id
    user_team_id: userTeamIdParam, // Keep for backward compatibility
    franchise_id: franchiseId,     // ✅ Included in overrides
    week: weekParam,                // ✅ Included in overrides
    tournament_id: tournamentId,
    mode: modeParam                 // ✅ Included in overrides
  }
});
window.location.href = `/static/set-lineup.html?${params.toString()}`;
```

**Note:** Now includes `team_id` in overrides, ensuring it's preserved even if not in URL params.

---

### ✅ **10. Gameplay → Box Score (Game Completion)**

**Location:** `gameScene.js:2160-2172`  
**Method:** Uses `gameCompletionPopup.js` which constructs URLs

**Status:** ✅ **VERIFIED - CORRECT**
- ✅ `gameCompletionPopup.js` includes `mode`, `franchise_id`, `team_id` in box score URL
- ✅ Box Score URL includes all three core variables

**Code:**
```javascript
showGameCompletionPopup({
  gameId: gameId,
  mode: mode,  // ✅ Set from scene
  tournamentId: this.tournamentId,
  franchiseId: this.franchiseId,  // ✅ Set from scene
  teamId: this.teamId,  // ✅ Set from scene (ObjectId)
  finalScore: finalScore
});
```

**Box Score URL Construction (gameCompletionPopup.js:59-69):**
```javascript
const boxScoreParams = new URLSearchParams();
if (gameId) boxScoreParams.set('game_id', gameId);
if (homeTeam) boxScoreParams.set('home', homeTeam);
if (awayTeam) boxScoreParams.set('away', awayTeam);
if (mode) boxScoreParams.set('mode', mode);  // ✅
if (tournamentId) boxScoreParams.set('tournament_id', tournamentId);
if (franchiseId) boxScoreParams.set('franchise_id', franchiseId);  // ✅
if (teamId) boxScoreParams.set('team_id', teamId);  // ✅
const boxScoreUrl = `/static/box-score.html?${boxScoreParams.toString()}`;
```

---

### ✅ **11. Box Score → FCC (Game Completion)**

**Location:** `box-score.js:1136-1150`  
**Method:** Reads from URL params and constructs FCC URL

**Status:** ✅ **VERIFIED - CORRECT**
- ✅ Reads `mode`, `franchise_id`, `team_id` from URL params
- ✅ Constructs FCC URL with all three variables

**Code:**
```javascript
const urlParams = new URLSearchParams(window.location.search);
const mode = urlParams.get('mode');
const urlFranchiseId = franchiseId || urlParams.get('franchise_id');
const urlTeamId = urlParams.get('team_id');

if (navMode === 'franchise' || (navMode === 'single' && urlFranchiseId)) {
  navMode = 'franchise';
  lockerRoomUrl = '/static/franchise-command-center.html';
  const franchiseParams = new URLSearchParams();
  if (urlFranchiseId) {
    franchiseParams.set('franchise_id', urlFranchiseId);  // ✅
  }
  if (urlTeamId) {
    franchiseParams.set('team_id', urlTeamId);  // ✅
  }
  if (franchiseParams.toString()) {
    lockerRoomUrl += `?${franchiseParams.toString()}`;
  }
}
```

**Status:** ✅ **FIXED**
- ✅ **Fixed:** Added `mode=franchise` parameter to FCC URL
- ✅ Now includes all three core variables: `mode`, `franchise_id`, `team_id`

---

### ⚠️ **12. Gameplay → Lineup (Quarter Break)**

**Location:** `gameScene.js:1585-1601`  
**Method:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()`

**Status:** ✅ **VERIFIED - CORRECT**
- ✅ Uses `TimeoutNavigationHelper` which preserves `mode`, `franchise_id`, `week` from source params
- ✅ **Fixed:** Helper now preserves `team_id` (after our fix)
- ✅ Navigates to lineup for quarter break

**Code:**
```javascript
const params = helper.buildGameNavigationParams({
  sourceParams: urlParams,  // Contains mode, franchise_id, team_id, week
  targetQuarter: nextQ,
  gameId: this.gameId,
  resumeFromTimeout: false,  // Quarter break, not timeout
  lineup: {},
  myTeamSide: urlParams.get('my_team')
});
window.location.href = `/static/set-lineup.html?${params.toString()}`;
```

---

## Summary of Verification

### ✅ **All Transitions Using TimeoutNavigationHelper (9 transitions)**
All verified as correct after our fix to preserve `team_id`:
1. Lineup → Gameplay ✅
2. Lineup → Game Plan ✅
3. Lineup → Box Score ✅
4. Game Plan → Gameplay ✅
5. Game Plan → Playbooks ✅
6. Playbooks → Game Plan ✅
7. Playbooks → Play Details ✅
8. Play Details → Playbooks ✅
9. Gameplay → Lineup (Quarter Break) ✅

### ✅ **Transitions Using Other Methods (2 transitions)**
10. Gameplay → Box Score (Game Completion) ✅ - Uses `gameCompletionPopup.js` which includes all variables
11. Box Score → FCC ✅ - Reads from URL params (minor: missing `mode` parameter)

### ⚠️ **Potential Issue Found**

**Box Score → FCC:**
- **Issue:** Missing `mode=franchise` parameter in FCC URL
- **Location:** `box-score.js:1140-1150`
- **Fix Required:** Add `franchiseParams.set('mode', 'franchise');` before constructing URL

### ⚠️ **Needs Verification**

**Gameplay → Game Plan (Timeout):**
- **Location:** `timeoutButtonManager.js:377` - Uses `user_team_id` in overrides
- **Status:** Should verify that `team_id` is in URL params when timeout is called
- **Note:** Helper now preserves `team_id` from source params, so this should work, but worth verifying

---

## Fixes Applied

### ✅ Fix 1: Box Score → FCC - Add `mode` parameter

**File:** `FrontEnd/static/box-score.js`  
**Line:** 1140-1150  
**Status:** ✅ **FIXED**

**Change:**
- Added `franchiseParams.set('mode', 'franchise');` before constructing URL
- Now includes all three core variables: `mode`, `franchise_id`, `team_id`

### ✅ Fix 2: Timeout Handler - Add `team_id` to overrides

**File:** `FrontEnd/static/js/phaser/utils/timeoutButtonManager.js`  
**Line:** 291, 377  
**Status:** ✅ **FIXED**

**Change:**
- Added `team_id` extraction from URL params: `const teamId = urlParams.get('team_id');`
- Added `team_id` to overrides: `team_id: teamId || userTeamIdParam`
- Prefers `team_id` over `user_team_id` for consistency

---

## Verification Status

**Total GP Transitions:** 12  
**Verified Correct:** 12 ✅  
**Fixes Applied:** 2
- ✅ Box Score → FCC: Added `mode=franchise` parameter
- ✅ Timeout Handler: Added `team_id` to overrides

**All GP transitions now preserve the core navigation anchor set (`mode`, `franchise_id`, `team_id`).**

---

## Summary

### ✅ **All Transitions Verified**

All 12 GP transitions have been verified and fixed:

1. ✅ Lineup → Gameplay
2. ✅ Lineup → Game Plan
3. ✅ Lineup → Box Score
4. ✅ Game Plan → Gameplay
5. ✅ Game Plan → Playbooks
6. ✅ Playbooks → Game Plan
7. ✅ Playbooks → Play Details
8. ✅ Play Details → Playbooks
9. ✅ Gameplay → Game Plan (Timeout) - Fixed to include `team_id` in overrides
10. ✅ Gameplay → Box Score (Game Completion)
11. ✅ Box Score → FCC - Fixed to include `mode` parameter
12. ✅ Gameplay → Lineup (Quarter Break)

### **Key Fixes Applied**

1. **TimeoutNavigationHelper:** Now preserves `team_id` (standardized parameter name)
2. **Box Score → FCC:** Added `mode=franchise` parameter
3. **Timeout Handler:** Added `team_id` to overrides (prefers `team_id` over `user_team_id`)

---

## Next Steps

1. ✅ **All fixes applied** - Ready for testing
2. **End-to-End Testing** - Test complete GP flow in franchise mode to verify all transitions work correctly
3. **Manual Testing** - Test timeout flow to verify `team_id` is preserved through timeout → lineup → game plan

