# Franchise Mode Navigation Fixes

**Date:** February 2025  
**Purpose:** Proposed fixes to ensure all GMO transitions preserve the core navigation anchor set (`mode`, `franchise_id`, `team_id`)

---

## Fix Priority

- **🔴 Critical:** Must fix - breaks navigation or data persistence
- **🟡 Important:** Should fix - improves consistency and prevents future bugs
- **🟢 Minor:** Nice to have - improves code clarity

---

## Critical Fixes

### Fix 1: FCC → Game Plan - Use `team_id` instead of `user_team_id`

**File:** `FrontEnd/static/franchise-command-center.js`  
**Line:** 533  
**Current Code:**
```javascript
const url = `/game-plan.html?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}&user_team_id=${encodeURIComponent(userTeamId)}&from=command_center`;
```

**Fixed Code:**
```javascript
const url = `/game-plan.html?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}&team_id=${encodeURIComponent(userTeamId)}&from=command_center`;
```

**Reason:** Standardize to `team_id` parameter name to match navigation pattern and backend expectations.

---

### Fix 2: FCC → Lineup (Play Next Game) - Use `team_id` and add `mode`

**File:** `FrontEnd/static/franchise-command-center.js`  
**Line:** 509-512  
**Current Code:**
```javascript
let url = `/static/set-lineup.html?franchise_id=${encodeURIComponent(franchiseId)}&week=${week}&home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}&home_id=${encodeURIComponent(home_id)}&away_id=${encodeURIComponent(away_id)}`;
// ✅ SS&S: Use ObjectId for consistent navigation
if (userTeamId) url += `&user_team_id=${encodeURIComponent(userTeamId)}`;
if (mySide) url += `&my_team=${mySide}`;
```

**Fixed Code:**
```javascript
let url = `/static/set-lineup.html?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}&week=${week}&home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}&home_id=${encodeURIComponent(home_id)}&away_id=${encodeURIComponent(away_id)}`;
// ✅ SS&S: Use ObjectId for consistent navigation
if (userTeamId) url += `&team_id=${encodeURIComponent(userTeamId)}`;
if (mySide) url += `&my_team=${mySide}`;
```

**Reason:** 
- Standardize to `team_id` parameter name
- Add explicit `mode=franchise` for consistency and clarity

---

### Fix 3: Playbooks → FCC - Use `team_id` (ObjectId) instead of `user_team_name` and add `mode`

**File:** `FrontEnd/static/playbooks.js`  
**Lines:** 1852-1865, 1869-1879 (two locations - main navigation and fallback)  
**Current Code:**
```javascript
if (from === 'franchise-command-center') {
  // Navigate back to Franchise Command Center
  const franchiseId = urlParams.get('franchise_id');
  const userTeamName = urlParams.get('team_id') || urlParams.get('user_team_id');
  
  console.log('✅ [PLAYBOOKS BACK] Navigating to Franchise Command Center');
  
  // For command centers, we don't need game context, just mode-specific params
  const params = new URLSearchParams();
  if (franchiseId) params.set('franchise_id', franchiseId);
  if (userTeamName) params.set('user_team_name', userTeamName);
  
  window.location.href = `/static/franchise-command-center.html?${params.toString()}`;
  return;
}
```

**Fixed Code:**
```javascript
if (from === 'franchise-command-center') {
  // Navigate back to Franchise Command Center
  const franchiseId = urlParams.get('franchise_id');
  const teamId = urlParams.get('team_id') || urlParams.get('user_team_id'); // Support both for backward compatibility
  
  console.log('✅ [PLAYBOOKS BACK] Navigating to Franchise Command Center');
  
  // For command centers, we don't need game context, just mode-specific params
  const params = new URLSearchParams();
  params.set('mode', 'franchise'); // Always include mode for consistency
  if (franchiseId) params.set('franchise_id', franchiseId);
  if (teamId) params.set('team_id', teamId); // Use team_id (ObjectId), not user_team_name
  
  window.location.href = `/static/franchise-command-center.html?${params.toString()}`;
  return;
}
```

**Also fix the fallback case (lines 1869-1879):**
```javascript
// Fallback: If mode is franchise but no 'from' parameter, assume franchise-command-center
if (mode === 'franchise' && !from) {
  console.log('⚠️ [PLAYBOOKS BACK] No "from" parameter, but mode is franchise - assuming franchise-command-center');
  const franchiseId = urlParams.get('franchise_id');
  const teamId = urlParams.get('team_id') || urlParams.get('user_team_id'); // Support both for backward compatibility
  
  const params = new URLSearchParams();
  params.set('mode', 'franchise'); // Always include mode for consistency
  if (franchiseId) params.set('franchise_id', franchiseId);
  if (teamId) params.set('team_id', teamId); // Use team_id (ObjectId), not user_team_name
  
  window.location.href = `/static/franchise-command-center.html?${params.toString()}`;
  return;
}
```

**Reason:** 
- Use `team_id` (ObjectId) instead of `user_team_name` (team name string) - ObjectId is required for backend lookups
- Add explicit `mode=franchise` for consistency
- Variable name `userTeamName` is misleading - it should be `teamId` since we're getting ObjectId from URL

---

## Important Fixes

### Fix 4: Game Plan → FCC - Add `mode` parameter

**File:** `FrontEnd/static/game-plan.js`  
**Line:** 457-462  
**Current Code:**
```javascript
} else if (mode === 'franchise' && franchiseId) {
  // Include team_id in URL for franchise command center
  const teamIdParam = teamId || userTeamIdParam || teamName;
  const url = `/static/franchise-command-center.html?franchise_id=${encodeURIComponent(franchiseId)}`;
  const finalUrl = teamIdParam ? `${url}&team_id=${encodeURIComponent(teamIdParam)}` : url;
  window.location.href = finalUrl;
}
```

**Fixed Code:**
```javascript
} else if (mode === 'franchise' && franchiseId) {
  // Include team_id in URL for franchise command center
  const teamIdParam = teamId || userTeamIdParam || teamName;
  const url = `/static/franchise-command-center.html?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}`;
  const finalUrl = teamIdParam ? `${url}&team_id=${encodeURIComponent(teamIdParam)}` : url;
  window.location.href = finalUrl;
}
```

**Reason:** Add explicit `mode` parameter for consistency, even though it can be inferred from `franchise_id` presence.

---

### Fix 5: Training Report → FCC - Add `mode` parameter

**File:** `FrontEnd/static/training-report.js`  
**Line:** 126  
**Current Code:**
```javascript
if (mode === 'franchise') {
  window.location.href = `/static/franchise-command-center.html?franchise_id=${franchiseId}&team_id=${teamId}`;
}
```

**Fixed Code:**
```javascript
if (mode === 'franchise') {
  window.location.href = `/static/franchise-command-center.html?mode=franchise&franchise_id=${franchiseId}&team_id=${teamId}`;
}
```

**Reason:** Add explicit `mode` parameter for consistency.

---

### Fix 6: Training → FCC (Back Button) - Add `mode` parameter

**File:** `FrontEnd/static/training.js`  
**Line:** 240-242  
**Current Code:**
```javascript
if (mode === 'franchise') {
  const franchiseId = urlParams.get('franchise_id');
  const teamId = urlParams.get('team_id');
  const url = `/static/franchise-command-center.html?franchise_id=${encodeURIComponent(franchiseId)}`;
  const finalUrl = teamId ? `${url}&team_id=${encodeURIComponent(teamId)}` : url;
  window.location.href = finalUrl;
}
```

**Fixed Code:**
```javascript
if (mode === 'franchise') {
  const franchiseId = urlParams.get('franchise_id');
  const teamId = urlParams.get('team_id');
  const url = `/static/franchise-command-center.html?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}`;
  const finalUrl = teamId ? `${url}&team_id=${encodeURIComponent(teamId)}` : url;
  window.location.href = finalUrl;
}
```

**Reason:** Add explicit `mode` parameter for consistency.

---

## Verification Needed

### Verify 1: Game Plan → Playbooks

**File:** `FrontEnd/static/game-plan.js`  
**Line:** 570-596  
**Status:** ✅ **Appears Correct**

**Analysis:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()` which should preserve all parameters including `mode`, `franchise_id`, and `team_id`. However, should verify that the helper properly includes these for GMO (non-gameplay) contexts.

**Action:** Test navigation from Game Plan → Playbooks in franchise mode and verify all three variables are preserved in the URL.

---

### Verify 2: Training → Training Report (Backend Redirect)

**File:** `BackEnd/api/franchise_routes.py` (or training routes)  
**Status:** ⚠️ **Needs Verification**

**Action:** Check backend training endpoint to verify that the redirect URL includes:
- `mode=franchise`
- `franchise_id={franchise_id}`
- `team_id={team_id}`

**Expected Pattern:**
```python
redirect_url = f"/static/training-report.html?mode=franchise&franchise_id={franchise_id}&team_id={team_id}&week={week}"
```

---

## Summary

### Critical Fixes (3)
1. FCC → Game Plan: Change `user_team_id` to `team_id`
2. FCC → Lineup: Change `user_team_id` to `team_id`, add `mode=franchise`
3. Playbooks → FCC: Change `user_team_name` to `team_id`, add `mode=franchise` (2 locations)

### Important Fixes (3)
4. Game Plan → FCC: Add `mode=franchise`
5. Training Report → FCC: Add `mode=franchise`
6. Training → FCC (Back): Add `mode=franchise`

### Verification Needed (2)
7. Game Plan → Playbooks: Verify helper preserves all variables
8. Training → Training Report: Verify backend redirect includes all variables

---

## Implementation Order

1. **Fix Critical Issues First** (Fixes 1-3)
   - These directly impact navigation and data persistence
   - Test each fix individually

2. **Fix Important Issues** (Fixes 4-6)
   - Improves consistency
   - Can be done together

3. **Verify Remaining Items** (Verify 1-2)
   - Test and document findings
   - Fix if issues found

---

## Testing Checklist

After implementing fixes, test the following navigation flows:

- [ ] FCC → Game Plan → Back to FCC
- [ ] FCC → Playbooks → Back to FCC
- [ ] FCC → Game Plan → Playbooks → Back to Game Plan → Back to FCC
- [ ] FCC → Training → Training Report → Back to FCC
- [ ] FCC → Lineup (Play Next Game) → Verify all parameters present
- [ ] Game Plan → Playbooks → Verify all parameters preserved
- [ ] Training → Training Report → Verify backend redirect includes all parameters

---

## Notes

- All fixes maintain backward compatibility by supporting both `team_id` and `user_team_id` in URL reading (where applicable)
- Variable names in JavaScript can remain `userTeamId` - the important part is using `team_id` as the URL parameter name
- The `mode` parameter, while inferable, should be explicit for consistency and clarity

