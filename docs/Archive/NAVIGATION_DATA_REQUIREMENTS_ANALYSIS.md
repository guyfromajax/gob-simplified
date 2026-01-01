# Navigation Data Requirements - Impact Analysis

> **Last Updated:** January 2025  
> **Status:** Analysis Document

This document provides impact analysis for key design decisions in the navigation data requirements.

---

## Question 1: view_team_id - Navigation Anchor vs Display Context

### Option A: view_team_id as Part of Navigation Anchor Set

**What it means:**
- `view_team_id` is treated as a required/standard part of the navigation anchor
- It's always passed in URLs, even when viewing your own team
- When viewing your own team: `team_id === view_team_id`
- When viewing opponent: `team_id !== view_team_id`

**Impact:**
- **Pros:**
  - Consistent URL structure (always has view_team_id)
  - Easier to implement (no conditional logic)
  - Clear separation: `team_id` = navigation context, `view_team_id` = display context
  - Back navigation always knows what team was being viewed
  
- **Cons:**
  - Redundant when viewing your own team (team_id and view_team_id are the same)
  - Slightly longer URLs
  - More parameters to validate

**Example URL:**
```
/team-roster.html?franchise_id=123&team_id=abc&view_team_id=abc  (viewing own team)
/team-roster.html?franchise_id=123&team_id=abc&view_team_id=xyz  (viewing opponent)
```

### Option B: view_team_id as Display Context Only

**What it means:**
- `view_team_id` is only present when viewing a different team
- When viewing your own team: Only `team_id` is present
- When viewing opponent: Both `team_id` and `view_team_id` are present

**Impact:**
- **Pros:**
  - Cleaner URLs when viewing own team (no redundant parameter)
  - Less validation (optional parameter)
  - More intuitive (only present when needed)
  
- **Cons:**
  - Conditional logic needed (check if view_team_id exists)
  - Inconsistent URL structure (sometimes has it, sometimes doesn't)
  - Back navigation needs to handle both cases (with/without view_team_id)
  - Risk of bugs if conditional logic is wrong

**Example URL:**
```
/team-roster.html?franchise_id=123&team_id=abc                    (viewing own team)
/team-roster.html?franchise_id=123&team_id=abc&view_team_id=xyz  (viewing opponent)
```

### Recommendation: **Option B (Display Context Only)**

**Reasoning:**
- Current implementation already uses this pattern (from NAVIGATION_TEAM_ID_PATTERN.md)
- Cleaner URLs when viewing own team (most common case)
- Less redundant data
- Conditional logic is manageable with proper helper functions

---

## Question 2: Timeout State Validation - Every Page Load vs Conditional

### Option A: Validate Timeout State on Every Page Load

**What it means:**
- Every page that could potentially resume from timeout checks the database
- Even if `resume_from_timeout` is not in URL, backend checks for timeout state
- Frontend always queries database for timeout state on load

**Impact:**
- **Pros:**
  - More resilient (catches cases where URL param is lost)
  - Defensive programming (handles edge cases automatically)
  - Works even if navigation helper fails to set URL param
  
- **Cons:**
  - Performance overhead (database query on every page load)
  - More complex logic (always checking, even when not needed)
  - Potential for false positives (stale timeout state from previous session)
  - Harder to debug (timeout state might come from unexpected source)

**Example:**
```javascript
// Every page load
const gameData = await fetch(`/api/game/${gameId}`);
if (gameData.timeout_next_play_type) {
  // Treat as timeout resume, even if URL param missing
}
```

### Option B: Validate Timeout State Only When resume_from_timeout Present

**What it means:**
- Only check database for timeout state when `resume_from_timeout=true` in URL
- If URL param is missing, don't check database
- Trust the navigation helper to set URL param correctly

**Impact:**
- **Pros:**
  - Better performance (only query when needed)
  - Clearer logic (explicit intent via URL param)
  - Easier to debug (timeout resume is explicit)
  - Less risk of false positives
  
- **Cons:**
  - Less resilient (if URL param is lost, timeout state is lost)
  - Requires navigation helper to always work correctly
  - Potential for bugs if navigation helper has issues

**Example:**
```javascript
// Only when resume_from_timeout is present
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('resume_from_timeout') === 'true') {
  const gameData = await fetch(`/api/game/${gameId}`);
  // Validate timeout state
}
```

### Recommendation: **Option B (Conditional Validation) with Fallback**

**Reasoning:**
- Better performance (only query when needed)
- Clearer intent (URL param explicitly indicates timeout resume)
- Add fallback: If `game_id` exists and `quarter === 1`, do lightweight check (current implementation in bootGame.js)
- This gives us best of both worlds: performance + resilience

**Hybrid Approach:**
```javascript
// Primary: Check URL param
if (resumeFromTimeout) {
  // Full timeout state validation
} else if (gameId && quarter === 1) {
  // Lightweight fallback check (only for Q1, where timeout is most common)
  // This catches cases where URL param is lost but timeout state exists
}
```

---

## Question 5: Strict vs Non-Strict Data Validation

### Option A: Strict Validation (Fail if Missing)

**What it means:**
- If required data is missing, show error and prevent navigation
- Redirect to appropriate fallback page (e.g., Mode Select)
- No graceful degradation

**Impact:**
- **Pros:**
  - Prevents bugs (catches data loss early)
  - Forces correct implementation (can't proceed with bad data)
  - Clear error messages (user knows what went wrong)
  - Easier to debug (failures are explicit)
  
- **Cons:**
  - Poor user experience (errors interrupt flow)
  - Can't recover from partial data loss
  - Requires robust error handling UI
  - May be too strict for optional data

**Example:**
```javascript
if (!tournamentId || !teamId) {
  showError('Missing required data. Redirecting to Mode Select.');
  window.location.href = '/mode-select.html';
  return;
}
```

### Option B: Non-Strict Validation (Fallback to Defaults)

**What it means:**
- If required data is missing, attempt to recover
- Use fallback chains (URL → localStorage → database → defaults)
- Only show error if all fallbacks fail

**Impact:**
- **Pros:**
  - Better user experience (graceful degradation)
  - Can recover from partial data loss
  - More resilient to navigation issues
  - Handles edge cases gracefully
  
- **Cons:**
  - Can hide bugs (silent failures)
  - Harder to debug (data might come from unexpected source)
  - Risk of using wrong data (stale localStorage, wrong defaults)
  - More complex logic (multiple fallback chains)

**Example:**
```javascript
// Fallback chain
let teamId = urlParams.get('team_id') || 
             localStorage.getItem('team_id') || 
             await fetchTeamIdFromDatabase() || 
             null;

if (!teamId) {
  // Only then show error
  showError('Unable to determine team. Redirecting to Mode Select.');
  window.location.href = '/mode-select.html';
}
```

### Recommendation: **Hybrid Approach (Strict for Critical, Non-Strict for Optional)**

**Reasoning:**
- **Critical Data (Strict):** Mode, Doc ID, Game ID (when required)
  - These are essential for functionality
  - Missing these means we can't proceed
  - Better to fail fast than use wrong data
  
- **Context Data (Non-Strict):** Team ID, View Team ID, From parameter
  - These can often be recovered from database
  - Fallback chains are appropriate
  - Better UX to recover gracefully

**Implementation:**
```javascript
// Critical data - strict validation
if (!mode || !tournamentId) {
  showError('Missing critical data. Redirecting to Mode Select.');
  window.location.href = '/mode-select.html';
  return;
}

// Context data - non-strict with fallback
let teamId = urlParams.get('team_id') || 
             await resolveTeamIdFromDatabase(tournamentId) || 
             null;
             
if (!teamId) {
  // Only show error if all fallbacks fail
  showError('Unable to determine team. Redirecting to Mode Select.');
  window.location.href = '/mode-select.html';
  return;
}
```

---

## Summary of Recommendations

1. **view_team_id:** Display context only (Option B) - cleaner URLs, current pattern
2. **Timeout Validation:** Conditional with lightweight fallback (Option B + fallback) - performance + resilience
3. **Bucket 4:** Login/Signup/Homepage only - clarified
4. **Cross-Bucket Transitions:** Always through Mode Select - no direct transitions
5. **Data Validation:** Hybrid (strict for critical, non-strict for context) - best of both worlds

