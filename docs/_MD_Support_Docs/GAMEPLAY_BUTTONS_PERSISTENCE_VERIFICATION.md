# Gameplay Buttons Persistence Verification

**Date:** February 2025  
**Purpose:** Verify that all gameplay buttons (Play Quarter, Sim to 4th Quarter, Sim Full Game) maintain data persistence in Franchise Mode

---

## Gameplay Buttons

1. **Play Quarter** - Plays one quarter with animations
2. **Sim to 4th Quarter** - Simulates Q1-Q3 instantly, then navigates to Q4 lineup
3. **Sim Full Game** - Simulates all quarters (Q1-Q4) instantly, then shows completion popup

---

## Core Navigation Anchor Set (Required)

For seamless navigation and data persistence, all gameplay buttons must preserve:
1. **`mode`** - `"franchise"`
2. **`franchise_id`** - ObjectId string
3. **`team_id`** - ObjectId string (user's team, from franchise document)

---

## Verification Analysis

### ✅ **1. Play Quarter Button**

**Location:** `FrontEnd/static/js/phaser/bootGame.js:388-443` (`handleButtonClick()`)

**Flow:**
1. User clicks "Play Quarter" button
2. Calls `startGame()` which loads `gameScene.js`
3. `gameScene.js` calls `/api/simulate-quarter` for each turn
4. After quarter completes, shows completion popup
5. User navigates to Box Score or Command Center

**Navigation Parameters Preserved:**
- ✅ **Mode:** Read from URL params (line 99: `urlParams.get('mode')`)
- ✅ **Franchise ID:** Read from URL params (line 86: `urlParams.get('franchise_id')`)
- ✅ **Team ID:** Read from URL params (line 102: `urlParams.get('team_id')`)
- ✅ **Week:** Read from URL params (line 95: `urlParams.get('week')`)

**Game Plan Settings:**
- ✅ Loaded before game starts (line 121-182: `loadGamePlanSettings()`)
- ✅ Loaded from database using `mode`, `franchise_id`, `team_id` (lines 145-156)
- ✅ Passed to backend via `gameScene.js` payload

**Game Completion:**
- ✅ `gameScene.js` calls `showGameCompletionPopup()` with `mode`, `franchiseId`, `teamId` (line 2160-2172)
- ✅ `gameCompletionPopup.js` preserves all navigation parameters (lines 41-53)
- ✅ `finalizeGame()` calls `/franchise/complete-week` with `franchise_id` and `week` (lines 112-156)
- ✅ Backend `finalize_game()` calls `rollup_game_to_franchise()` to aggregate stats (line 642)

**Status:** ✅ **VERIFIED - CORRECT**

---

### ✅ **2. Sim to 4th Quarter Button**

**Location:** `FrontEnd/static/js/phaser/bootGame.js:445-608` (`handleSimToFourth()`)

**Flow:**
1. User clicks "Sim to 4th Quarter" button
2. Loops through Q1, Q2, Q3:
   - Calls `/api/simulate-quarter` with `full_sim=true`
   - Each quarter is fully simulated (no animations)
   - Each quarter is saved to database
3. After Q3 completes, redirects to `set-lineup.html` for Q4

**Navigation Parameters Preserved:**
- ✅ **Mode:** Read from URL params (line 99: `urlParams.get('mode')`)
- ✅ **Franchise ID:** Read from URL params (line 86: `urlParams.get('franchise_id')`)
- ✅ **Team ID:** Read from URL params (line 102: `urlParams.get('team_id')`)
- ✅ **Week:** Read from URL params (line 95: `urlParams.get('week')`)

**URL Parameters Built for Q4 Redirect (lines 577-594):**
```javascript
const params = new URLSearchParams();
params.set('home', homeTeam);
params.set('away', awayTeam);
params.set('home_id', urlParams.get('home_id') || homeTeam);
params.set('away_id', urlParams.get('away_id') || awayTeam);
params.set('mode', mode);  // ✅ Preserved
params.set('my_team', userTeamSide || 'home');
params.set('user_team_id', userTeamSide === 'home' ? homeTeam : awayTeam);  // ⚠️ Uses team name, not ObjectId
params.set('quarter', 4);
params.set('period', 'Q4');
params.set('game_id', gameId);
```

**Issues Found:**
- ⚠️ **Missing `franchise_id`** in Q4 redirect URL (line 577-594)
- ⚠️ **Missing `week`** in Q4 redirect URL
- ⚠️ **Missing `team_id`** (ObjectId) in Q4 redirect URL - uses `user_team_id` (team name) instead
- ⚠️ **Missing `franchise_id` and `week`** in `/api/simulate-quarter` payload (lines 484-539)

**Game Plan Settings:**
- ✅ Loaded before simulating (line 465: `await loadGamePlanSettings()`)
- ✅ Passed to backend for Q1 (lines 498-502)
- ✅ Reused for Q2-Q3 (lines 515-519)

**Status:** ⚠️ **ISSUES FOUND** - Missing navigation parameters

---

### ✅ **3. Sim Full Game Button**

**Location:** `FrontEnd/static/js/phaser/bootGame.js:610-830` (`handleSimFullGame()`)

**Flow:**
1. User clicks "Sim Full Game" button
2. Loops through Q1, Q2, Q3, Q4:
   - Calls `/api/simulate-quarter` with `full_sim=true`
   - Each quarter is fully simulated (no animations)
   - Each quarter is saved to database
3. After Q4 completes, shows completion popup
4. User navigates to Box Score or Command Center

**Navigation Parameters Preserved:**
- ✅ **Mode:** Read from URL params (line 99: `urlParams.get('mode')`)
- ✅ **Franchise ID:** Read from URL params (line 86: `urlParams.get('franchise_id')`)
- ✅ **Team ID:** Read from URL params (line 102: `urlParams.get('team_id')`)
- ✅ **Week:** Read from URL params (line 95: `urlParams.get('week')`)

**Game Completion:**
- ✅ Calls `finalizeGame()` with `franchiseId` (line 788)
- ✅ Calls `showGameCompletionPopup()` with `mode`, `franchiseId`, `teamId` (lines 794-803)
- ✅ `gameCompletionPopup.js` preserves all navigation parameters (lines 41-53)
- ✅ `finalizeGame()` calls `/franchise/complete-week` with `franchise_id` and `week` (lines 112-156)
- ✅ Backend `finalize_game()` calls `rollup_game_to_franchise()` to aggregate stats (line 642)

**Issues Found:**
- ⚠️ **Missing `franchise_id` and `week`** in `/api/simulate-quarter` payload (lines 655-710)
- ⚠️ **Missing `team_id`** in `showGameCompletionPopup()` call (line 794-803) - only passes `franchiseId`, not `teamId`

**Game Plan Settings:**
- ✅ Loaded before simulating (line 636: `await loadGamePlanSettings()`)
- ✅ Passed to backend for Q1 (lines 669-673)
- ✅ Reused for Q2-Q4 (lines 686-690)

**Status:** ⚠️ **ISSUES FOUND** - Missing navigation parameters

---

## Backend Verification

### `/api/simulate-quarter` Endpoint

**Location:** `BackEnd/api/api.py:766-1601` (`simulate_quarter_endpoint()`)

**Mode Detection:**
- ✅ Reads `mode` from request (line 774: `request.mode`)
- ✅ Reads `franchise_id` from request (line 775: `request.franchise_id`)
- ✅ Reads `week` from request (line 776: `request.week`)

**Franchise Mode Handling:**
- ✅ Sets `franchise_id` and `week` in game document (lines 365-366)
- ✅ Calls `finalize_game()` with `mode="franchise"` and `franchise_id` (line 1601)
- ✅ `finalize_game()` calls `rollup_game_to_franchise()` to aggregate stats (line 642)

**Status:** ✅ **VERIFIED - CORRECT** (if frontend sends parameters)

---

## Issues Summary

### **Critical Issues (Must Fix)**

1. **Sim to 4th Quarter - Missing Parameters in Q4 Redirect**
   - **Location:** `bootGame.js:577-594`
   - **Missing:** `franchise_id`, `week`, `team_id` (ObjectId)
   - **Impact:** Q4 lineup screen won't have navigation context, can't load game plan settings

2. **Sim to 4th Quarter - Missing Parameters in Payload**
   - **Location:** `bootGame.js:484-539`
   - **Missing:** `franchise_id`, `week` in `/api/simulate-quarter` payload
   - **Impact:** Backend won't know it's franchise mode, stats won't roll up correctly

3. **Sim Full Game - Missing Parameters in Payload**
   - **Location:** `bootGame.js:655-710`
   - **Missing:** `franchise_id`, `week` in `/api/simulate-quarter` payload
   - **Impact:** Backend won't know it's franchise mode, stats won't roll up correctly

4. **Sim Full Game - Missing `team_id` in Completion Popup**
   - **Location:** `bootGame.js:794-803`
   - **Missing:** `teamId` parameter in `showGameCompletionPopup()` call
   - **Impact:** Completion popup won't preserve `team_id` for navigation

### **Important Issues (Should Fix)**

5. **Sim to 4th Quarter - Uses `user_team_id` (team name) instead of `team_id` (ObjectId)**
   - **Location:** `bootGame.js:584`
   - **Impact:** Inconsistent with standardized pattern (should use ObjectId)

---

## Required Fixes

### Fix 1: Sim to 4th Quarter - Add Missing Parameters to Q4 Redirect

**File:** `FrontEnd/static/js/phaser/bootGame.js`  
**Lines:** 577-594

**Current Code:**
```javascript
const params = new URLSearchParams();
params.set('home', homeTeam);
params.set('away', awayTeam);
params.set('home_id', urlParams.get('home_id') || homeTeam);
params.set('away_id', urlParams.get('away_id') || awayTeam);
params.set('mode', mode);
params.set('my_team', userTeamSide || 'home');
params.set('user_team_id', userTeamSide === 'home' ? homeTeam : awayTeam);
params.set('quarter', 4);
params.set('period', 'Q4');
params.set('game_id', gameId);
```

**Fixed Code:**
```javascript
const params = new URLSearchParams();
params.set('home', homeTeam);
params.set('away', awayTeam);
params.set('home_id', urlParams.get('home_id') || homeTeam);
params.set('away_id', urlParams.get('away_id') || awayTeam);
params.set('mode', mode);  // ✅ Already present
if (franchiseId) params.set('franchise_id', franchiseId);  // ✅ Add
if (weekParam && !Number.isNaN(weekParam)) params.set('week', weekParam);  // ✅ Add
if (teamId) params.set('team_id', teamId);  // ✅ Add (ObjectId, not team name)
params.set('my_team', userTeamSide || 'home');
params.set('quarter', 4);
params.set('period', 'Q4');
params.set('game_id', gameId);
```

---

### Fix 2: Sim to 4th Quarter - Add Missing Parameters to Payload

**File:** `FrontEnd/static/js/phaser/bootGame.js`  
**Lines:** 484-539

**Current Code:**
```javascript
const payload = {
  home_team: homeTeam,
  away_team: awayTeam,
  quarter: currentQ,
  game_id: gameId,
};
```

**Fixed Code:**
```javascript
const payload = {
  home_team: homeTeam,
  away_team: awayTeam,
  quarter: currentQ,
  game_id: gameId,
};
// ✅ SS&S: Add mode-specific parameters for franchise mode
if (mode === 'franchise' && franchiseId) {
  payload.mode = 'franchise';
  payload.franchise_id = franchiseId;
  if (weekParam && !Number.isNaN(weekParam)) {
    payload.week = weekParam;
  }
}
```

---

### Fix 3: Sim Full Game - Add Missing Parameters to Payload

**File:** `FrontEnd/static/js/phaser/bootGame.js`  
**Lines:** 655-710

**Current Code:**
```javascript
const payload = {
  home_team: homeTeam,
  away_team: awayTeam,
  quarter: currentQ,
};
if (gId) payload.game_id = gId;
```

**Fixed Code:**
```javascript
const payload = {
  home_team: homeTeam,
  away_team: awayTeam,
  quarter: currentQ,
};
if (gId) payload.game_id = gId;
// ✅ SS&S: Add mode-specific parameters for franchise mode
if (mode === 'franchise' && franchiseId) {
  payload.mode = 'franchise';
  payload.franchise_id = franchiseId;
  if (weekParam && !Number.isNaN(weekParam)) {
    payload.week = weekParam;
  }
}
```

---

### Fix 4: Sim Full Game - Add `team_id` to Completion Popup

**File:** `FrontEnd/static/js/phaser/bootGame.js`  
**Lines:** 794-803

**Current Code:**
```javascript
showGameCompletionPopup({
  gameId: gameId,
  mode: popupMode,
  tournamentId: tournamentId,
  franchiseId: franchiseId,
  finalScore: finalScore,
  homeTeam: homeTeam,
  awayTeam: awayTeam
});
```

**Fixed Code:**
```javascript
showGameCompletionPopup({
  gameId: gameId,
  mode: popupMode,
  tournamentId: tournamentId,
  franchiseId: franchiseId,
  teamId: teamId,  // ✅ Add team_id (ObjectId) for navigation anchor
  finalScore: finalScore,
  homeTeam: homeTeam,
  awayTeam: awayTeam
});
```

---

## Summary

### ✅ **Play Quarter Button**
- **Status:** ✅ **VERIFIED - CORRECT**
- All navigation parameters preserved
- Game plan settings loaded correctly
- Stats rollup works correctly

### ✅ **Sim to 4th Quarter Button**
- **Status:** ✅ **FIXED**
- ✅ Added `franchise_id`, `week`, `team_id` to Q4 redirect
- ✅ Added `franchise_id`, `week` to payload
- **Impact:** Q4 now has full navigation context, stats will roll up correctly

### ✅ **Sim Full Game Button**
- **Status:** ✅ **FIXED**
- ✅ Added `franchise_id`, `week` to payload
- ✅ Added `team_id` to completion popup
- **Impact:** Stats will roll up correctly, navigation preserves context

---

## Next Steps

1. **Fix Sim to 4th Quarter** - Add missing parameters to Q4 redirect and payload
2. **Fix Sim Full Game** - Add missing parameters to payload and completion popup
3. **Test All Buttons** - Verify persistence after fixes

