# Navigation Data Requirements - Implementation Plan

> **Last Updated:** January 2025  
> **Status:** ✅ **IMPLEMENTATION COMPLETE** - Historical Document
> 
> **Note:** This document served as the implementation plan. Most items have been completed. See `NAVIGATION_DATA_REQUIREMENTS.md` for current requirements and `NAVIGATION_HELPER_DESIGN.md` for implementation status.

This document provides the implementation plan based on the data requirements analysis and user-flow mapping.

---

## Answers to Design Questions

### 1. view_team_id: Display Context Only (Not Navigation Anchor)

**Decision:** `view_team_id` is **display context only**, not part of navigation anchor set.

**Reasoning:**
- Cleaner URLs when viewing own team (most common case)
- Less redundant data
- Current implementation already uses this pattern
- Conditional logic is manageable with proper helper functions

**Impact:**
- URLs only include `view_team_id` when viewing a different team
- Back navigation preserves `team_id` (user's team) for navigation context
- Display logic checks for `view_team_id` existence to determine which team to show

**Implementation:**
```javascript
// Viewing own team
/team-roster.html?franchise_id=123&team_id=abc

// Viewing opponent
/team-roster.html?franchise_id=123&team_id=abc&view_team_id=xyz
```

---

### 2. Timeout State Validation: Conditional with Lightweight Fallback

**Decision:** Validate timeout state **only when `resume_from_timeout=true`** in URL, with lightweight fallback for Q1.

**Reasoning:**
- Better performance (only query when needed)
- Clearer intent (URL param explicitly indicates timeout resume)
- Lightweight fallback catches cases where URL param is lost
- Best of both worlds: performance + resilience

**Impact:**
- Primary: Check URL param `resume_from_timeout`
- If present: Full timeout state validation from database
- Fallback: If `game_id` exists and `quarter === 1`, do lightweight check
- This prevents unnecessary database queries while catching edge cases

**Implementation:**
```javascript
// Primary check
if (resumeFromTimeout) {
  // Full timeout state validation
  const gameData = await fetch(`/api/game/${gameId}`);
  if (!gameData.timeout_next_play_type) {
    // Clear resume_from_timeout flag
  }
} else if (gameId && quarter === 1) {
  // Lightweight fallback (only for Q1 where timeout is most common)
  const gameData = await fetch(`/api/game/${gameId}?quarter=${quarter}`);
  if (gameData.timeout_next_play_type) {
    resumeFromTimeout = true; // Restore flag
  }
}
```

---

### 3. Bucket 4 (Non-Account): Login/Signup/Homepage Only

**Decision:** Bucket 4 is **only for Login, Signup, and Homepage** instances.

**Clarification:**
- Homepage can be accessed by non-account visitors
- Each Team's General Roster Page is also accessible without account (from universal players collection)
- No guest mode support needed

**Impact:**
- Simplified bucket structure
- Clear separation: Account required for all game modes
- Homepage and General Roster are public access only

---

### 4. Cross-Bucket Transitions: Always Through Mode Select

**Decision:** **No direct cross-bucket transitions** - all transitions between buckets MUST go through Mode Select screen.

**Reasoning:**
- Prevents data loss from direct transitions
- Ensures proper initialization of game mode documents
- Clear user flow (always know where you are in the experience)
- Easier to debug and maintain

**Impact:**
- Cannot go directly from Franchise Mode to Tournament Mode
- Cannot go directly from Gameplay to different game mode
- All transitions: Current Bucket → Mode Select → Target Bucket
- Mode Select becomes the central hub for bucket transitions

**Implementation:**
- Add validation to prevent direct cross-bucket navigation
- Mode Select screen handles all bucket transitions
- Future: Mode Select becomes "Account Command Center"

---

### 5. Data Validation: Hybrid Approach (Strict + Non-Strict)

**Decision:** **Hybrid validation** - Strict for critical data, non-strict for context data.

**Reasoning:**
- Critical data (Mode, Doc ID, Game ID) is essential - fail fast if missing
- Context data (Team ID, View Team ID, From) can often be recovered - use fallback chains
- Best user experience (graceful degradation where possible)
- Prevents bugs (strict validation for critical data)

**Impact:**
- **Critical Data (Strict):**
  - Mode, Doc ID, Game ID (when required)
  - Missing = Redirect to Mode Select with error
  
- **Context Data (Non-Strict):**
  - Team ID, View Team ID, From parameter
  - Fallback chain: URL → localStorage → database → defaults
  - Only fail if all fallbacks fail

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
             localStorage.getItem('team_id') || 
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

## Alignment with user-flow.md

### Instance Type Mapping
- **NA (Non-Account)** = Bucket 4
- **GA (General Account)** = Bucket 1
- **GMO (Game Mode Only)** = Bucket 2
- **GP (Gameplay)** = Bucket 3

### Key Findings from user-flow.md

1. **Known Bugs Identified:**
   - Game Plan navigation loses `from` parameter when going through Playbooks
   - Training "Current Playbook" needs to apply latest Game Plan and Playbook settings

2. **Persistence Rules Clarified:**
   - Single Game: Settings persist per team across games
   - Tournament/Franchise: Settings persist across all instances until changed

3. **Transition Patterns:**
   - All transitions documented in user-flow.md
   - No direct cross-bucket transitions (always through Mode Select)

---

## Implementation Plan - Status

### ✅ Phase 1: Fix Known Bugs - COMPLETE

**Priority 1: Game Plan Navigation Bug** ✅ **FIXED**
- **Issue:** `from` parameter lost when navigating TCC/FCC → Game Plan → Playbooks → Game Plan
- **Fix:** Preserve `from` parameter through Playbooks navigation
- **Files:** `FrontEnd/static/playbooks.js` (lines 1834-1853), `FrontEnd/static/game-plan.js` (lines 555-564)
- **Status:** ✅ **RESOLVED** - Code preserves `from` parameter correctly

**Priority 2: Training Current Playbook** ✅ **IMPLEMENTED**
- **Issue:** "Current Playbook" radio button should apply latest Game Plan and Playbook settings
- **Fix:** Load and apply settings when "Current Playbook" is selected
- **Files:** `FrontEnd/static/training.js` (line 315), `BackEnd/api/tournament_routes.py` (line 1228), `BackEnd/api/franchise_routes.py` (line 1849)
- **Status:** ✅ **RESOLVED** - Feature fully implemented

### ✅ Phase 2: Implement Data Requirements - COMPLETE

**Step 1: Update Navigation Helpers** ✅ **COMPLETE**
- ✅ `TimeoutNavigationHelper` handles all bucket transitions
- ✅ Validation for critical vs context data implemented
- ✅ Fallback chains for context data implemented

**Step 2: Update Page Load Validation** ✅ **COMPLETE**
- ✅ Strict validation for critical data (Mode, Doc ID, Game ID)
- ✅ Non-strict validation with fallback for context data (Team ID)
- ✅ Conditional timeout state validation implemented

**Step 3: Update All Navigation Functions** ✅ **COMPLETE**
- ✅ All navigation preserves complete anchor set
- ✅ `from` parameter preservation through all transitions
- ✅ Cross-bucket transition prevention implemented

### ⚠️ Phase 3: Comprehensive Testing - ONGOING

**Test Matrix:**
- ⚠️ All transitions in user-flow.md (recommended for verification)
- ⚠️ All bucket combinations (recommended for verification)
- ⚠️ All edge cases (timeout, foul out, quarter breaks) (recommended for verification)
- ⚠️ All mode-specific scenarios (recommended for verification)

**Test Coverage:**
- ⚠️ Data persistence across transitions (recommended for verification)
- ⚠️ Validation logic (strict vs non-strict) (recommended for verification)
- ⚠️ Fallback chain behavior (recommended for verification)
- ⚠️ Error handling (recommended for verification)

### ✅ Phase 4: Documentation & Refinement - COMPLETE

**Documentation:**
- ✅ master_game_doc.md updated with navigation patterns
- ✅ Navigation helper design documented
- ✅ Edge cases and special handling documented

**Refinement:**
- ⚠️ Monitor for edge cases in production (ongoing)
- ⚠️ Refine validation rules based on real-world usage (ongoing)
- ✅ Fallback chains optimized

---

## Next Steps

1. **Review this implementation plan** - Confirm approach and priorities
2. **Fix known bugs first** - Game Plan navigation and Training Current Playbook
3. **Implement data requirements** - Update navigation helpers and validation
4. **Create comprehensive test suite** - Test all transitions and edge cases
5. **Deploy and monitor** - Watch for edge cases and refine as needed

---

## Questions for Final Alignment

1. **Priority Order:** Should we fix known bugs first, or implement data requirements first?
2. **Testing Approach:** Should we create tests as we implement, or implement all changes then test?
3. **Deployment Strategy:** Should we implement incrementally (one bucket at a time) or all at once?
4. **Mode Select Transition:** When should we implement the "Account Command Center" update to Mode Select?

