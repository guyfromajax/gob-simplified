# GMO Navigation Variable Verification

**Date:** February 2025  
**Purpose:** Verify that all GMO screen transitions preserve the core navigation anchor set (`mode`, `doc_id`, `team_id`)

---

## Core Navigation Anchor Set (Required)

For seamless navigation, all GMO transitions must preserve:
1. **`mode`** - `"franchise"` or `"tournament"`
2. **`doc_id`** - `franchise_id` (Franchise) or `tournament_id` (Tournament)
3. **`team_id`** - ObjectId string (user's team)

---

## Franchise Mode GMO Transitions

### ✅ **FCC → Game Plan**
**Location:** `franchise-command-center.js:1178`  
**URL:** `/game-plan.html?mode=franchise&franchise_id=${franchiseId}&team_id=${userTeamId}&from=command_center`

**Status:** ✅ **FIXED**
- ✅ Has `mode`
- ✅ Has `franchise_id`
- ✅ Uses `team_id` (fixed from `user_team_id`)

---

### ✅ **FCC → Playbooks**
**Location:** `franchise-command-center.js:548-554`  
**URL:** `/static/playbooks.html?mode=franchise&franchise_id=${franchiseId}&team_id=${userTeamId}&from=franchise-command-center`

**Status:** ✅ **CORRECT**
- ✅ Has `mode`
- ✅ Has `franchise_id`
- ✅ Has `team_id`

---

### ✅ **FCC → Training**
**Location:** `franchise-command-center.js:480-481`  
**URL:** `/static/training.html?franchise_id=${franchiseId}&mode=franchise&session_type=${sessionType}&team_id=${userTeamId}`

**Status:** ✅ **CORRECT**
- ✅ Has `mode`
- ✅ Has `franchise_id`
- ✅ Has `team_id`

---

### ✅ **FCC → Lineup (Play Next Game)**
**Location:** `franchise-command-center.js:1154-1157`  
**URL:** `/static/set-lineup.html?mode=franchise&franchise_id=${franchiseId}&week=${week}&home=${home}&away=${away}&home_id=${home_id}&away_id=${away_id}&team_id=${userTeamId}&my_team=${mySide}`

**Status:** ✅ **FIXED**
- ✅ Has `mode=franchise`
- ✅ Has `franchise_id`
- ✅ Uses `team_id` (fixed from `user_team_id`)

---

### ✅ **Game Plan → FCC**
**Location:** `game-plan.js:435-437`  
**URL:** `/static/franchise-command-center.html?mode=franchise&franchise_id=${franchiseId}&team_id=${teamIdParam}`

**Status:** ✅ **CORRECT** (conditional - only if mode is franchise)
- ✅ Has `mode=franchise`
- ✅ Has `franchise_id`
- ✅ Has `team_id`

---

### ✅ **Playbooks → Game Plan**
**Location:** `playbooks.js:1886-1916`  
**Method:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()` to preserve all params

**Status:** ✅ **CORRECT**
- ✅ Preserves `mode`, `franchise_id`, `team_id` via helper
- ✅ Preserves `from` parameter to maintain navigation context

---

### ✅ **Playbooks → FCC**
**Location:** `playbooks.js:1797-1803, 1812-1818`  
**URL:** `/static/franchise-command-center.html?mode=franchise&franchise_id=${franchiseId}&team_id=${teamId}`

**Status:** ✅ **FIXED**
- ✅ Has `mode=franchise`
- ✅ Has `franchise_id`
- ✅ Uses `team_id` (ObjectId format, fixed from `user_team_name`)

---

### ✅ **Training → Training Report**
**Location:** Backend redirect (`franchise_routes.py:1703, 1961` and `tournament_routes.py:1076, 1335`)  
**Method:** Backend returns `result.redirect` URL

**Status:** ✅ **VERIFIED - CORRECT**
- ✅ Franchise: `/static/training-report.html?mode=franchise&franchise_id=${franchise_id}&team_id=${team_id}&week=${week}`
- ✅ Tournament: `/static/training-report.html?mode=tournament&tournament_id=${tournament_id}&team_id=${team_id}`
- ✅ All three core variables (`mode`, `doc_id`, `team_id`) are included in redirect URLs

---

### ✅ **Training Report → FCC**
**Location:** `training-report.js:126`  
**URL:** `/static/franchise-command-center.html?mode=franchise&franchise_id=${franchiseId}&team_id=${teamId}`

**Status:** ✅ **CORRECT**
- ✅ Has `mode=franchise`
- ✅ Has `franchise_id`
- ✅ Has `team_id`

---

### ✅ **Training → FCC (Back Button)**
**Location:** `training.js:240-242`  
**URL:** `/static/franchise-command-center.html?mode=franchise&franchise_id=${franchiseId}&team_id=${teamId}`

**Status:** ✅ **CORRECT**
- ✅ Has `mode=franchise`
- ✅ Has `franchise_id`
- ✅ Has `team_id`

---

## Tournament Mode GMO Transitions

### ✅ **TCC → Game Plan**
**Location:** `tournament.js:1893-1899`  
**URL:** `/game-plan.html?mode=tournament&tournament_id=${tournament._id}&team_id=${userTeamId}&from=tournament-command-center`

**Status:** ✅ **FIXED**
- ✅ Has `mode=tournament`
- ✅ Has `tournament_id`
- ✅ Uses `team_id` (fixed from `user_team_id`)

---

### ✅ **TCC → Playbooks**
**Location:** `tournament.js:962-968`  
**URL:** `/static/playbooks.html?mode=tournament&tournament_id=${tournament._id}&team_id=${userTeamId}&from=tournament-command-center`

**Status:** ✅ **CORRECT**
- ✅ Has `mode`
- ✅ Has `tournament_id`
- ✅ Has `team_id`

---

### ✅ **TCC → Training**
**Location:** `tournament.js:1834`  
**URL:** `/static/training.html?mode=tournament&tournament_id=${tournament._id}&team_id=${userTeamId}&round=${tournament.current_round}`

**Status:** ✅ **VERIFIED - CORRECT**
- ✅ Has `mode=tournament`
- ✅ Has `tournament_id`
- ✅ Has `team_id`

---

### ⚠️ **TCC → Lineup (Play Next Game)**
**Location:** `tournament.js:1868-1873`  
**URL:** `/static/set-lineup.html?mode=tournament&tournament_id=${tournament._id}&home=${home}&away=${away}&home_id=${home_id}&away_id=${away_id}&user_team_id=${userTeamId}&my_team=${mySide}`

**Status:** ⚠️ **PARTIALLY FIXED**
- ✅ Has `mode=tournament` (fixed)
- ✅ Has `tournament_id`
- ⚠️ Still uses `user_team_id` instead of `team_id` (should be standardized to `team_id`)

**Fix Required:**
- Change `user_team_id` to `team_id` for consistency

---

### ✅ **Game Plan → TCC**
**Location:** `game-plan.js:429-431`  
**URL:** `/static/tournament.html?tournament_id=${tournamentId}&team_id=${teamIdParam}`

**Status:** ✅ **CORRECT** (conditional - only if mode is tournament)
- ✅ Has `tournament_id`
- ✅ Has `team_id`
- ⚠️ Missing `mode` parameter (optional but recommended for consistency)

**Note:** `mode` is inferred from presence of `tournament_id`, but explicit `mode` would be better

---

### ✅ **Game Plan → Playbooks**
**Location:** `game-plan.js:546-571`  
**Method:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()` to preserve all params

**Status:** ✅ **VERIFIED - CORRECT**
- ✅ Preserves `mode`, `tournament_id`/`franchise_id`, `team_id` via helper
- ✅ Preserves `from` parameter to maintain navigation context
- ✅ Preserves all game context (game_id, quarter, lineup, etc.)

---

### ✅ **Playbooks → Game Plan**
**Location:** `playbooks.js:1886-1916`  
**Method:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()` to preserve all params

**Status:** ✅ **CORRECT**
- ✅ Preserves `mode`, `tournament_id`, `team_id` via helper
- ✅ Preserves `from` parameter to maintain navigation context

---

### ⚠️ **Playbooks → TCC**
**Location:** `playbooks.js:1760-1786`  
**URL:** `/static/tournament.html?tournament_id=${tournamentId}&user_team_id=${userTeamId}`

**Status:** ⚠️ **ISSUE FOUND**
- ✅ Has `tournament_id`
- ⚠️ Uses `user_team_id` instead of `team_id` (should be standardized to `team_id`)
- ❌ Missing `mode` parameter (should include `mode=tournament`)

**Fix Required:**
- Change `user_team_id` to `team_id` for consistency
- Add `mode=tournament` parameter

---

### ✅ **Training → Training Report**
**Location:** Backend redirect (`tournament_routes.py:1076, 1335`)  
**Method:** Backend returns `result.redirect` URL

**Status:** ✅ **VERIFIED - CORRECT**
- ✅ Redirect: `/static/training-report.html?mode=tournament&tournament_id=${tournament_id}&team_id=${team_id}`
- ✅ All three core variables (`mode`, `tournament_id`, `team_id`) are included in redirect URL

---

### ✅ **Training Report → TCC**
**Location:** `training-report.js:129`  
**URL:** `/static/tournament.html?tournament_id=${tournamentId}&team_id=${teamId}`

**Status:** ✅ **CORRECT**
- ✅ Has `tournament_id`
- ✅ Has `team_id`
- ⚠️ Missing `mode` parameter (optional but recommended for consistency)

---

### ✅ **Training → TCC (Back Button)**
**Location:** `training.js:247-249`  
**URL:** `/static/tournament.html?tournament_id=${tournamentId}&team_id=${teamId}`

**Status:** ✅ **CORRECT**
- ✅ Has `tournament_id`
- ✅ Has `team_id`
- ⚠️ Missing `mode` parameter (optional but recommended for consistency)

---

## Summary of Issues

### ✅ Fixed Issues
1. ✅ **FCC → Game Plan:** Now uses `team_id` (fixed)
2. ✅ **TCC → Game Plan:** Now uses `team_id` and includes `mode` (fixed)
3. ✅ **FCC → Lineup:** Now uses `team_id` and includes `mode` (fixed)
4. ✅ **Playbooks → FCC:** Now uses `team_id` and includes `mode` (fixed)
5. ✅ **Game Plan → Playbooks:** Verified - preserves all variables via helper (fixed)
6. ✅ **TCC → Training:** Verified - includes all three variables (fixed)
7. ✅ **Training → Training Report (Backend Redirect):** Verified - backend includes all three variables (fixed)

### ⚠️ Remaining Critical Issues (Must Fix)
1. **TCC → Lineup:** Still uses `user_team_id` instead of `team_id` (has `mode` now)
2. **Playbooks → TCC:** Still uses `user_team_id` instead of `team_id`, missing `mode`

### Minor Issues (Should Fix)
3. **Game Plan → TCC:** Missing `mode` parameter (inferred but not explicit)
4. **Training Report → TCC:** Missing `mode` parameter (inferred but not explicit)
5. **Training → TCC (Back):** Missing `mode` parameter (inferred but not explicit)

---

## Recommendations

1. **Standardize Parameter Names:**
   - Always use `team_id` (ObjectId) instead of `user_team_id` or `user_team_name`
   - Always include `mode` parameter explicitly (don't rely on inference)

2. **Create Navigation Helper:**
   - Consider creating a GMO-specific navigation helper (similar to `TimeoutNavigationHelper`)
   - Helper should ensure all three core variables are always included

3. ✅ **Backend Redirect Verification:**
   - ✅ Verified that backend training redirect includes all three variables (`mode`, `doc_id`, `team_id`)
   - ✅ Both Franchise and Tournament modes correctly include all navigation anchor variables

4. **Testing:**
   - Test all GMO transitions to ensure navigation anchor set is preserved
   - Verify that data loads correctly when navigating between screens

---

## Next Steps

1. ✅ **COMPLETED:** Fixed most critical issues (FCC → Game Plan, TCC → Game Plan, FCC → Lineup, Playbooks → FCC)
2. ✅ **COMPLETED:** Verified items that needed verification (Game Plan → Playbooks, TCC → Training, Training → Training Report)
3. ⚠️ **REMAINING:** Fix remaining critical issues:
   - TCC → Lineup: Change `user_team_id` to `team_id`
   - Playbooks → TCC: Change `user_team_id` to `team_id` and add `mode=tournament`
4. **OPTIONAL:** Fix minor issues (add `mode` parameter where inferred) for consistency

