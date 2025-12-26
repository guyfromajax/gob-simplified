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
**Location:** `franchise-command-center.js:533`  
**URL:** `/game-plan.html?mode=franchise&franchise_id=${franchiseId}&user_team_id=${userTeamId}&from=command_center`

**Status:** ⚠️ **ISSUE FOUND**
- ✅ Has `mode`
- ✅ Has `franchise_id`
- ⚠️ Uses `user_team_id` instead of `team_id` (should be standardized to `team_id`)

**Fix Required:** Change `user_team_id` to `team_id` for consistency

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
**Location:** `franchise-command-center.js:509-512`  
**URL:** `/static/set-lineup.html?franchise_id=${franchiseId}&week=${week}&home=${home}&away=${away}&home_id=${home_id}&away_id=${away_id}&user_team_id=${userTeamId}&my_team=${mySide}`

**Status:** ⚠️ **ISSUE FOUND**
- ✅ Has `franchise_id`
- ⚠️ Uses `user_team_id` instead of `team_id` (should be standardized to `team_id`)
- ⚠️ Missing `mode` parameter (should include `mode=franchise`)

**Fix Required:** 
- Change `user_team_id` to `team_id`
- Add `mode=franchise` parameter

---

### ✅ **Game Plan → FCC**
**Location:** `game-plan.js:457-462`  
**URL:** `/static/franchise-command-center.html?franchise_id=${franchiseId}&team_id=${teamIdParam}`

**Status:** ✅ **CORRECT** (conditional - only if mode is franchise)
- ✅ Has `franchise_id`
- ✅ Has `team_id`
- ⚠️ Missing `mode` parameter (optional but recommended for consistency)

**Note:** `mode` is inferred from presence of `franchise_id`, but explicit `mode` would be better

---

### ✅ **Game Plan → Playbooks**
**Location:** `game-plan.js` (Playbooks button navigation)  
**Status:** ⚠️ **NEEDS VERIFICATION**

**Action Required:** Check if Game Plan → Playbooks preserves all three variables

---

### ✅ **Playbooks → Game Plan**
**Location:** `playbooks.js:1886-1916`  
**Method:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()` to preserve all params

**Status:** ✅ **CORRECT**
- ✅ Preserves `mode`, `franchise_id`, `team_id` via helper
- ✅ Preserves `from` parameter to maintain navigation context

---

### ⚠️ **Playbooks → FCC**
**Location:** `playbooks.js:1860-1864`  
**URL:** `/static/franchise-command-center.html?franchise_id=${franchiseId}&user_team_name=${userTeamName}`

**Status:** ❌ **ISSUE FOUND**
- ✅ Has `franchise_id`
- ❌ Uses `user_team_name` instead of `team_id` (ObjectId)
- ❌ Missing `mode` parameter

**Fix Required:**
- Change `user_team_name` to `team_id` (use ObjectId, not team name)
- Add `mode=franchise` parameter

---

### ✅ **Training → Training Report**
**Location:** Backend redirect (training.js:415)  
**Method:** Backend returns `result.redirect` URL

**Status:** ⚠️ **NEEDS VERIFICATION**

**Action Required:** Verify backend redirect includes `mode`, `franchise_id`, `team_id`

---

### ✅ **Training Report → FCC**
**Location:** `training-report.js:126`  
**URL:** `/static/franchise-command-center.html?franchise_id=${franchiseId}&team_id=${teamId}`

**Status:** ✅ **CORRECT**
- ✅ Has `franchise_id`
- ✅ Has `team_id`
- ⚠️ Missing `mode` parameter (optional but recommended)

---

### ✅ **Training → FCC (Back Button)**
**Location:** `training.js:240-242`  
**URL:** `/static/franchise-command-center.html?franchise_id=${franchiseId}&team_id=${teamId}`

**Status:** ✅ **CORRECT**
- ✅ Has `franchise_id`
- ✅ Has `team_id`
- ⚠️ Missing `mode` parameter (optional but recommended)

---

## Tournament Mode GMO Transitions

### ✅ **TCC → Game Plan**
**Location:** `tournament.js:947`  
**URL:** `/game-plan.html?mode=tournament&tournament_id=${tournament._id}&user_team_id=${userTeamId}&from=command_center`

**Status:** ⚠️ **ISSUE FOUND**
- ✅ Has `mode`
- ✅ Has `tournament_id`
- ⚠️ Uses `user_team_id` instead of `team_id` (should be standardized to `team_id`)

**Fix Required:** Change `user_team_id` to `team_id` for consistency

---

### ✅ **TCC → Playbooks**
**Location:** `tournament.js:962-968`  
**URL:** `/static/playbooks.html?mode=tournament&tournament_id=${tournament._id}&team_id=${userTeamId}&from=tournament-command-center`

**Status:** ✅ **CORRECT**
- ✅ Has `mode`
- ✅ Has `tournament_id`
- ✅ Has `team_id`

---

### ⚠️ **TCC → Training**
**Location:** `tournament.js` (Training button)  
**Status:** ⚠️ **NEEDS VERIFICATION**

**Action Required:** Check if TCC → Training preserves all three variables

---

### ⚠️ **TCC → Lineup (Play Next Game)**
**Location:** `tournament.js:923-928`  
**URL:** `/static/set-lineup.html?tournament_id=${tournament._id}&home=${home}&away=${away}&home_id=${home_id}&away_id=${away_id}&user_team_id=${userTeamId}&my_team=${mySide}`

**Status:** ⚠️ **ISSUE FOUND**
- ✅ Has `tournament_id`
- ⚠️ Uses `user_team_id` instead of `team_id` (should be standardized to `team_id`)
- ❌ Missing `mode` parameter (should include `mode=tournament`)

**Fix Required:**
- Change `user_team_id` to `team_id`
- Add `mode=tournament` parameter

---

### ✅ **Game Plan → TCC**
**Location:** `game-plan.js:451-456`  
**URL:** `/static/tournament.html?tournament_id=${tournamentId}&team_id=${teamIdParam}`

**Status:** ✅ **CORRECT** (conditional - only if mode is tournament)
- ✅ Has `tournament_id`
- ✅ Has `team_id`
- ⚠️ Missing `mode` parameter (optional but recommended for consistency)

**Note:** `mode` is inferred from presence of `tournament_id`, but explicit `mode` would be better

---

### ✅ **Game Plan → Playbooks**
**Location:** `game-plan.js` (Playbooks button navigation)  
**Status:** ⚠️ **NEEDS VERIFICATION**

**Action Required:** Check if Game Plan → Playbooks preserves all three variables

---

### ✅ **Playbooks → Game Plan**
**Location:** `playbooks.js:1886-1916`  
**Method:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()` to preserve all params

**Status:** ✅ **CORRECT**
- ✅ Preserves `mode`, `tournament_id`, `team_id` via helper
- ✅ Preserves `from` parameter to maintain navigation context

---

### ⚠️ **Playbooks → TCC**
**Location:** `playbooks.js:1834-1848`  
**Status:** ⚠️ **NEEDS VERIFICATION**

**Action Required:** Check if Playbooks → TCC preserves all three variables (similar pattern to FCC)

---

### ✅ **Training → Training Report**
**Location:** Backend redirect (training.js:415)  
**Method:** Backend returns `result.redirect` URL

**Status:** ⚠️ **NEEDS VERIFICATION**

**Action Required:** Verify backend redirect includes `mode`, `tournament_id`, `team_id`

---

### ✅ **Training Report → TCC**
**Location:** `training-report.js:129`  
**URL:** `/static/tournament.html?tournament_id=${tournamentId}&team_id=${teamId}`

**Status:** ✅ **CORRECT**
- ✅ Has `tournament_id`
- ✅ Has `team_id`
- ⚠️ Missing `mode` parameter (optional but recommended)

---

### ✅ **Training → TCC (Back Button)**
**Location:** `training.js:247-249`  
**URL:** `/static/tournament.html?tournament_id=${tournamentId}&team_id=${teamId}`

**Status:** ✅ **CORRECT**
- ✅ Has `tournament_id`
- ✅ Has `team_id`
- ⚠️ Missing `mode` parameter (optional but recommended)

---

## Summary of Issues

### Critical Issues (Must Fix)
1. **FCC → Game Plan:** Uses `user_team_id` instead of `team_id`
2. **TCC → Game Plan:** Uses `user_team_id` instead of `team_id`
3. **FCC → Lineup:** Uses `user_team_id` instead of `team_id`, missing `mode`
4. **TCC → Lineup:** Uses `user_team_id` instead of `team_id`, missing `mode`
5. **Playbooks → FCC:** Uses `user_team_name` instead of `team_id`, missing `mode`

### Minor Issues (Should Fix)
6. **Game Plan → FCC/TCC:** Missing `mode` parameter (inferred but not explicit)
7. **Training Report → FCC/TCC:** Missing `mode` parameter (inferred but not explicit)
8. **Training → FCC/TCC (Back):** Missing `mode` parameter (inferred but not explicit)

### Needs Verification
9. **Game Plan → Playbooks:** Need to verify all three variables are preserved
10. **TCC → Training:** Need to verify all three variables are preserved
11. **Playbooks → TCC:** Need to verify all three variables are preserved
12. **Training → Training Report (Backend Redirect):** Need to verify backend includes all three variables

---

## Recommendations

1. **Standardize Parameter Names:**
   - Always use `team_id` (ObjectId) instead of `user_team_id` or `user_team_name`
   - Always include `mode` parameter explicitly (don't rely on inference)

2. **Create Navigation Helper:**
   - Consider creating a GMO-specific navigation helper (similar to `TimeoutNavigationHelper`)
   - Helper should ensure all three core variables are always included

3. **Backend Redirect Verification:**
   - Verify that backend training redirect includes all three variables
   - Update backend if needed to ensure consistency

4. **Testing:**
   - Test all GMO transitions to ensure navigation anchor set is preserved
   - Verify that data loads correctly when navigating between screens

---

## Next Steps

1. Fix critical issues (items 1-5)
2. Verify items that need verification (items 9-12)
3. Fix minor issues (items 6-8) for consistency
4. Update documentation with verified navigation patterns

