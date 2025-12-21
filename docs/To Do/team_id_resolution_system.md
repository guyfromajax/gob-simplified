# Team ID Resolution System - Standardization Work Plan

**Date:** January 2025  
**Status:** 📋 Planning - Awaiting Approval  
**Priority:** High (Blocks franchise/tournament game plan persistence)

---

## Problem Statement

### Symptom
In Franchise mode, when users navigate from the Franchise Command Center to the Game Plan screen and attempt to save settings, the changes do not persist. The same issue likely affects Tournament mode.

### Root Cause
**Inconsistent team_id resolution across endpoints:**
- Frontend sends `team_id` which can be either:
  - Team name (e.g., "Morristown") - when coming from command center
  - ObjectId string (e.g., "507f1f77bcf86cd799439011") - when coming from game flow
- Backend endpoints handle this inconsistently:
  - Some endpoints resolve team names → ObjectId strings
  - Other endpoints assume `team_id` is already an ObjectId string
  - Result: Updates fail when team name is sent but endpoint expects ObjectId

### Impact
- Users cannot save game plan settings in Franchise/Tournament mode
- Settings are lost when navigating away from Game Plan screen
- Poor user experience - settings appear to save but don't persist
- Inconsistent behavior across different navigation paths

---

## Current State Analysis

### Database Structure

**Franchise Mode:**
- Path: `franchises.{franchise_id}.franchise_teams.{team_id}.playcall_settings`
- Keys in `franchise_teams` are ObjectId strings: `str(team["_id"])`
- Example: `franchise_teams["507f1f77bcf86cd799439011"].playcall_settings`

**Tournament Mode:**
- Path: `tournaments.{tournament_id}.teams.{team_id}.playcall_settings`
- Keys in `teams` are ObjectId strings: `str(team["_id"])`
- Example: `teams["507f1f77bcf86cd799439011"].playcall_settings`

**Single Game Mode:**
- Path: `games.{game_id}.teams.{team_id}.playcall_settings`
- Keys in `teams` are ObjectId strings: `str(team["_id"])`
- Example: `teams["507f1f77bcf86cd799439011"].playcall_settings`

### Current Team ID Resolution Implementations

We have **4-5 different implementations** of team name → ObjectId resolution:

#### 1. `ensure_team_objects_exist()` (gameplan_routes.py:250-260)
- **Scope:** Single/Tournament modes only
- **Logic:** 
  ```python
  team = db.teams.find_one({"name": team_id})
  if not team:
      team = db.teams.find_one({"_id": ObjectId(team_id)})
  actual_team_id = str(team["_id"])
  ```
- **Status:** ✅ Works for single/tournament, ❌ NOT used for franchise

#### 2. `get_playbooks()` (gameplan_routes.py:535-618)
- **Scope:** All modes (franchise + tournament/single)
- **Logic:** 
  - Franchise: Iterates through `franchise_teams` keys, looks up each in `db.teams`, matches by name
  - Tournament/Single: Iterates through `teams` keys, looks up each in `db.teams`, matches by name
- **Lines:** ~80 lines of duplicated resolution logic
- **Status:** ✅ Works, but duplicated

#### 3. `save_playbooks()` (gameplan_routes.py:746-807)
- **Scope:** All modes (franchise + tournament/single)
- **Logic:** Same as `get_playbooks()` - **DUPLICATED CODE**
- **Lines:** ~60 lines of duplicated resolution logic
- **Status:** ✅ Works, but duplicated

#### 4. `update_gameplan()` (gameplan_routes.py:416-479)
- **Scope:** All modes
- **Logic:** **NO RESOLUTION** - uses `request.team_id` directly
- **Status:** ❌ **BUG** - fails when team name is sent

#### 5. `_normalize_team_id()` (franchise_routes.py:68-77)
- **Scope:** Franchise routes only
- **Logic:** Different implementation, tries `_id`, `name`, `code`
- **Status:** ✅ Works, but different pattern

### Frontend Team ID Handling

**game-plan.js:**
- Line 45: `teamId = myTeamSide === 'home' ? homeId : awayId`
- **Problem:** When coming from command center, `myTeamSide`, `homeId`, `awayId` are all `undefined`
- **Result:** `teamId` is `undefined` when saving
- **Available but unused:** `userTeamIdParam` (line 25) contains team name but is never used

**franchise-command-center.js:**
- Line 485: Sends `user_team_id=${userTeamName}` (team name, not ID)
- This is correct behavior - frontend should be able to send names

---

## Proposed Solution: Standardized Team ID Resolution Helper

### Design Principles

1. **Single Source of Truth:** One function handles all team_id resolution
2. **Consistent Behavior:** Same logic works for all modes (franchise, tournament, single)
3. **Flexible Input:** Accepts team name, ObjectId string, or ObjectId
4. **Mode-Aware:** Returns the correct `team_id` format for the target document structure
5. **Robust Fallbacks:** Multiple lookup strategies to handle edge cases

### Function Signature

```python
def resolve_team_id_for_mode(
    mode: str,
    doc_id: str,
    team_identifier: str,
    collection=None,
    doc=None
) -> str:
    """
    Resolve a team identifier (name, ObjectId string, or ObjectId) to the 
    actual team_id string used in mode-specific documents.
    
    Args:
        mode: "franchise", "tournament", or "single"
        doc_id: The document ID (franchise_id, tournament_id, or game_id)
        team_identifier: Team name, ObjectId string, or ObjectId
        collection: Optional MongoDB collection (auto-determined if None)
        doc: Optional pre-loaded document (avoids duplicate queries)
    
    Returns:
        str: The team_id string used as a key in the mode document
            - For franchise: key in franchise_teams dict
            - For tournament/single: key in teams dict
    
    Raises:
        HTTPException: If team cannot be resolved
    """
```

### Resolution Strategy

**For All Modes:**
1. **Direct Lookup:** Check if `team_identifier` is already a key in the document's team dict
2. **Name Lookup in Document:** Iterate through document's team keys, look up each in `db.teams`, match by name
3. **Name Lookup in Teams Collection:** Look up `team_identifier` in `db.teams` by name, then find matching key in document
4. **ObjectId Lookup:** Try `team_identifier` as ObjectId, look up in `db.teams`, then find matching key in document

**Mode-Specific Details:**
- **Franchise:** Resolves to key in `franchise_teams` dict
- **Tournament/Single:** Resolves to key in `teams` dict
- **Single Game:** Handles both UUID string and ObjectId document IDs

### Implementation Plan

#### Phase 1: Create Helper Function
1. Create `resolve_team_id_for_mode()` in `BackEnd/api/gameplan_routes.py`
2. Implement resolution logic for all three modes
3. Add comprehensive error handling and logging
4. Add unit tests (if test framework exists)

#### Phase 2: Refactor Existing Endpoints
1. **`update_gameplan()`:**
   - Call `resolve_team_id_for_mode()` before building update path
   - Use resolved `actual_team_id` in update fields
   - Remove dependency on `ensure_team_objects_exist()` for resolution

2. **`get_playbooks()`:**
   - Replace duplicated resolution logic (lines 535-618) with helper call
   - Reduce from ~80 lines to ~5 lines

3. **`save_playbooks()`:**
   - Replace duplicated resolution logic (lines 746-807) with helper call
   - Reduce from ~60 lines to ~5 lines

4. **`get_gameplan()`:**
   - Add resolution for franchise mode (currently missing, line 379)
   - Use helper for consistency

#### Phase 3: Frontend Fixes
1. **game-plan.js:**
   - Add fallback: `teamId = homeId || awayId || userTeamIdParam || teamName`
   - Ensure `teamId` is always defined before API calls
   - Add debug logging to show which value is used

2. **Consistency Check:**
   - Verify all navigation paths (command center, game flow, timeout) pass correct `team_id`
   - Ensure consistent parameter naming across all entry points

#### Phase 4: Cleanup & Documentation
1. Remove duplicate resolution code from other files (if any)
2. Update API documentation to clarify that `team_id` can be name or ObjectId
3. Add inline comments explaining resolution strategy
4. Update master_game_doc.md with new resolution system

---

## Benefits

### Immediate Benefits
- ✅ Fixes franchise/tournament game plan persistence bug
- ✅ Consistent behavior across all endpoints
- ✅ Single place to fix bugs or add features

### Long-Term Benefits
- ✅ **Reduced Code Duplication:** Eliminate ~140 lines of duplicated resolution logic
- ✅ **Easier Maintenance:** Fix resolution bugs in one place
- ✅ **Easier Testing:** Test one function instead of 4-5 implementations
- ✅ **Better Documentation:** One function to document instead of multiple
- ✅ **Future-Proof:** Easy to add new resolution strategies or modes

### SS&S Principles
- **Simple:** One function, clear purpose, easy to understand
- **Stable:** Single implementation = fewer bugs, consistent behavior
- **Sustainable:** Easy to maintain, extend, and test

---

## Risks & Considerations

### Potential Issues

1. **Breaking Changes:**
   - **Risk:** Low - Helper function maintains same behavior as existing code
   - **Mitigation:** Test thoroughly with existing data, ensure backward compatibility

2. **Performance:**
   - **Risk:** Low - Helper may add 1-2 extra database queries in worst case
   - **Mitigation:** Helper can accept pre-loaded `doc` parameter to avoid duplicate queries
   - **Note:** Current implementations already do multiple queries, so no performance regression

3. **Edge Cases:**
   - **Risk:** Medium - Need to handle all edge cases (team not found, invalid IDs, etc.)
   - **Mitigation:** Comprehensive error handling, clear error messages, extensive testing

4. **Migration:**
   - **Risk:** Low - No database changes required, only code refactoring
   - **Mitigation:** Can be done incrementally (one endpoint at a time)

### Testing Strategy

1. **Unit Tests:**
   - Test helper function with various inputs (name, ObjectId string, ObjectId)
   - Test all three modes (franchise, tournament, single)
   - Test edge cases (team not found, invalid IDs, etc.)

2. **Integration Tests:**
   - Test game plan save/load in franchise mode
   - Test game plan save/load in tournament mode
   - Test game plan save/load in single game mode
   - Test from different navigation paths (command center, game flow, timeout)

3. **Manual Testing:**
   - Navigate from Franchise Command Center → Game Plan → Save → Verify persistence
   - Navigate from Tournament Command Center → Game Plan → Save → Verify persistence
   - Test with team names and team IDs
   - Test error cases (invalid team, missing document, etc.)

---

## Alternative Approaches Considered

### Option 1: Copy Resolution Logic to `update_gameplan()`
- **Pros:** Quick fix, reuses existing pattern
- **Cons:** Adds more duplication, doesn't fix root cause, harder to maintain
- **Verdict:** ❌ Less SS&S - creates more problems than it solves

### Option 2: Frontend Always Sends ObjectId
- **Pros:** Simpler backend (no resolution needed)
- **Cons:** Requires frontend changes everywhere, breaks existing working code, less flexible
- **Verdict:** ❌ Less SS&S - shifts complexity to frontend, breaks existing patterns

### Option 3: Store Team Names as Keys in Documents
- **Pros:** No resolution needed
- **Cons:** Requires database migration, breaks existing data structure, inconsistent with current design
- **Verdict:** ❌ Less SS&S - major breaking change, not worth it

---

## Implementation Checklist

### Phase 1: Helper Function
- [ ] Create `resolve_team_id_for_mode()` function
- [ ] Implement resolution logic for franchise mode
- [ ] Implement resolution logic for tournament mode
- [ ] Implement resolution logic for single game mode
- [ ] Add error handling and logging
- [ ] Add docstring with examples
- [ ] Test helper function in isolation

### Phase 2: Refactor Endpoints
- [ ] Update `update_gameplan()` to use helper
- [ ] Update `get_playbooks()` to use helper
- [ ] Update `save_playbooks()` to use helper
- [ ] Update `get_gameplan()` to use helper (add franchise resolution)
- [ ] Remove duplicate resolution code
- [ ] Test each endpoint after refactoring

### Phase 3: Frontend Fixes
- [ ] Fix `teamId` fallback chain in `game-plan.js`
- [ ] Add debug logging for team_id resolution
- [ ] Test from Franchise Command Center
- [ ] Test from Tournament Command Center
- [ ] Test from game flow (set-lineup → game-plan)
- [ ] Test from timeout navigation

### Phase 4: Cleanup
- [ ] Remove any remaining duplicate resolution code
- [ ] Update API documentation
- [ ] Update master_game_doc.md
- [ ] Add inline comments
- [ ] Code review

---

## Success Criteria

1. ✅ Game plan settings persist in Franchise mode when saved from Command Center
2. ✅ Game plan settings persist in Tournament mode when saved from Command Center
3. ✅ All existing functionality continues to work (no regressions)
4. ✅ Code duplication reduced (eliminate ~140 lines of duplicate code)
5. ✅ Consistent behavior across all endpoints
6. ✅ Clear error messages when team cannot be resolved
7. ✅ Documentation updated

---

## Questions for Review

1. **Should the helper function be in `gameplan_routes.py` or a shared utility file?**
   - Current thinking: `gameplan_routes.py` since it's primarily used by gameplan endpoints
   - Alternative: Create `BackEnd/utils/team_resolution.py` for reusability

2. **Should we also refactor `_normalize_team_id()` in `franchise_routes.py`?**
   - Current thinking: Yes, for consistency, but lower priority
   - Alternative: Leave it as-is if it's only used in franchise-specific routes

3. **Should we add caching for team lookups?**
   - Current thinking: No, premature optimization - database lookups are fast
   - Alternative: Add simple in-memory cache if performance becomes an issue

4. **Should we standardize on team names or ObjectId strings for frontend?**
   - Current thinking: Keep flexible - backend handles both
   - Alternative: Standardize frontend to always send ObjectId strings

---

## Estimated Effort

- **Phase 1 (Helper Function):** 2-3 hours
- **Phase 2 (Refactor Endpoints):** 2-3 hours
- **Phase 3 (Frontend Fixes):** 1-2 hours
- **Phase 4 (Cleanup & Docs):** 1-2 hours
- **Testing:** 2-3 hours

**Total:** ~8-13 hours

---

## Next Steps

1. Review this work plan
2. Approve or request modifications
3. Begin implementation once approved
4. Test thoroughly before merging
5. Update documentation

---

## Related Files

**Backend:**
- `BackEnd/api/gameplan_routes.py` - Main file to modify
- `BackEnd/api/franchise_routes.py` - Has `_normalize_team_id()` helper
- `BackEnd/api/tournament_routes.py` - May have similar issues

**Frontend:**
- `FrontEnd/static/game-plan.js` - Needs teamId fallback fix
- `FrontEnd/static/franchise-command-center.js` - Sends team name
- `FrontEnd/static/tournament.js` - May send team name

**Documentation:**
- `docs/gameplan.md` - Update with resolution system
- `docs/master_game_doc.md` - Update with new system

