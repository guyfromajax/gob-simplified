# Playbook Persistence System - Design & Implementation Plan

## Current Bugs Summary

### Bug 1: Timeout Navigation - Incorrect Percentages
**Scenario:**
1. User sets playbook settings before game start
2. Settings persist correctly during initial gameplay
3. Timeout is called during game
4. User navigates: Game Plan → Playbooks (via timeout flow)
5. **Result:** Playbooks page loads with incorrect percentages

**Hypothesis:**
- Wrong game context (game_id, quarter, etc.) being used when loading from database
- Database query might be using stale or incorrect game_id
- Settings might be saved to one game_id but loaded from a different game_id
- Timeout navigation might not be preserving correct game context

### Bug 2: Play Details Navigation - Lost Settings
**Scenario:**
1. User is on Playbooks page during game (after timeout or quarter break)
2. User clicks a play to view play details
3. User clicks Back to return to Playbooks
4. **Result:** 
   - Many percentages incorrectly reset to zero
   - Playcall center settings (slot assignments) are lost

**Hypothesis:**
- The reset-to-0 fix we implemented is too aggressive - it resets ALL percentages before loading
- If database load fails or returns incomplete data, everything gets reset to 0
- Slot assignments might not be loading correctly from database
- State restoration after navigation might be incomplete

## Root Cause Analysis

### Current System Issues

1. **No Clear State Management Strategy:**
   - Database is supposed to be "single source of truth" but UI state can get out of sync
   - No distinction between "saved state" (database) and "working state" (UI)
   - Navigation state preservation is unclear

2. **Load Strategy Problems:**
   - `loadState()` always loads from database (no localStorage check)
   - But database might have stale/incomplete data
   - No validation that loaded data matches current game context
   - Reset-to-0 happens before verifying database data is valid

3. **Context Tracking Issues:**
   - Game context (game_id, quarter, mode, team_id) might not be consistent across navigation
   - Different entry points (game start, timeout, quarter break) might use different context
   - No validation that loaded settings match current game context

4. **Save Strategy Gaps:**
   - Only saves on explicit "Submit Playbooks" action
   - No auto-save during navigation
   - If user navigates away without submitting, work is lost
   - No way to recover unsaved work

5. **State Restoration Problems:**
   - When returning from play-details, state should be restored
   - But current system always loads from database (which might be stale)
   - No mechanism to preserve "work in progress" during navigation

## Proposed Bulletproof System

### Core Principles

1. **Database as Authoritative Source:**
   - Database is always the source of truth for persisted settings
   - UI state is derived from database state
   - No localStorage persistence of percentages/slot assignments (only UI preferences)

2. **Context Validation:**
   - Always validate that loaded settings match current game context
   - If context mismatch, don't load (or load defaults)
   - Log warnings when context mismatches occur

3. **Explicit Save Model:**
   - Settings only saved to database on explicit "Submit Playbooks" action
   - No auto-save to database (prevents accidental overwrites)
   - User has full control over when settings are persisted

4. **State Restoration Strategy:**
   - When navigating TO play-details: Save current UI state to temporary storage (sessionStorage, not localStorage)
   - When returning FROM play-details: Restore from temporary storage if it exists and matches current context
   - If no temporary storage or context mismatch: Load from database
   - Temporary storage cleared after successful database save

5. **Load Validation:**
   - Before applying database values, validate:
     - Game context matches (game_id, quarter, mode, team_id)
     - Data structure is valid (all required fields present)
     - Percentages total correctly (each section = 100%)
   - If validation fails: Log error, use defaults, don't apply invalid data

6. **Reset Strategy:**
   - Only reset percentages to 0 if we have valid database data to apply
   - If database load fails or returns invalid data, preserve current UI state
   - Don't reset if we can't replace with valid data

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Playbooks Page Load                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────┐
        │  Check sessionStorage for          │
        │  temporary state (from navigation) │
        └───────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
            ▼                               ▼
    ┌───────────────┐              ┌───────────────┐
    │  Temp State   │              │  No Temp State │
    │  Exists?      │              │  or Mismatch  │
    └───────────────┘              └───────────────┘
            │                               │
            ▼                               ▼
    ┌───────────────┐              ┌───────────────┐
    │  Validate     │              │  Load from     │
    │  Context      │              │  Database     │
    └───────────────┘              └───────────────┘
            │                               │
            ▼                               ▼
    ┌───────────────┐              ┌───────────────┐
    │  Context      │              │  Validate     │
    │  Matches?     │              │  Data         │
    └───────────────┘              └───────────────┘
            │                               │
    ┌───────┴───────┐              ┌───────┴───────┐
    │               │              │               │
    ▼               ▼              ▼               ▼
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│ Restore │   │ Load    │   │ Apply   │   │ Use     │
│ from    │   │ from    │   │ Valid   │   │ Defaults│
│ Temp    │   │ DB      │   │ Data    │   │         │
└─────────┘   └─────────┘   └─────────┘   └─────────┘
```

## Step-by-Step Implementation Plan

### Phase 1: Context Validation System

**Goal:** Ensure we always load settings for the correct game context

**Steps:**
1. Create `validateGameContext()` function that checks:
   - Current URL params (game_id, quarter, mode, team_id)
   - Database response context (if provided)
   - Returns boolean + mismatch details

2. Update `loadSlotAssignmentsFromAPI()` to:
   - Accept game context parameters
   - Validate context before applying assignments
   - Log warnings if context mismatch
   - Return validation result

3. Update `loadPlaybookPercentagesFromAPI()` to:
   - Accept game context parameters
   - Validate context before applying percentages
   - Log warnings if context mismatch
   - Return validation result

4. Update API calls to include context in request/response:
   - Include game_id, quarter, mode, team_id in API request
   - Backend should return context in response
   - Frontend validates response context matches request context

### Phase 2: Temporary State Management

**Goal:** Preserve work in progress during navigation without polluting database

**Steps:**
1. Create `saveTemporaryState()` function:
   - Saves current UI state to sessionStorage (not localStorage)
   - Includes: percentages, slot assignments, motion dropdowns, position filters, even distribution toggles
   - Includes: game context (game_id, quarter, mode, team_id) for validation
   - Key format: `playbooks_temp_state_{mode}_{teamId}_{gameId}_{quarter}`

2. Create `loadTemporaryState()` function:
   - Loads from sessionStorage
   - Validates context matches current game context
   - Returns state if valid, null if invalid/missing

3. Create `clearTemporaryState()` function:
   - Clears temporary state from sessionStorage
   - Called after successful database save

4. Update `navigateToPlayDetails()`:
   - Call `saveTemporaryState()` before navigation
   - Include current game context in saved state

5. Update `loadState()`:
   - First check for temporary state (with context validation)
   - If valid temporary state exists: restore from it
   - If no temporary state or invalid: load from database
   - Clear temporary state after successful database load

### Phase 3: Safe Reset Strategy

**Goal:** Only reset percentages when we have valid replacement data

**Steps:**
1. Update `loadPlaybookPercentagesFromAPI()`:
   - Don't reset to 0 immediately
   - First validate database data:
     - Context matches
     - Data structure is valid
     - Percentages total correctly (each section = 100%)
   - Only reset to 0 if validation passes
   - If validation fails: preserve current UI state, log error

2. Add validation function `validatePlaybookData()`:
   - Checks data structure (required fields present)
   - Validates percentages total 100% per section
   - Validates play names exist in current play data
   - Returns validation result + error details

3. Add error handling:
   - If database load fails: preserve current UI state, show warning
   - If validation fails: preserve current UI state, show warning
   - Don't apply invalid data that would corrupt UI state

### Phase 4: Slot Assignments Persistence

**Goal:** Ensure slot assignments persist correctly

**Steps:**
1. Review `loadSlotAssignmentsFromAPI()`:
   - Ensure it validates context before applying
   - Ensure it handles missing/incomplete data gracefully
   - Add logging for debugging

2. Update slot assignment loading:
   - Include in temporary state save/restore
   - Validate slot assignments match current play data
   - Handle cases where assigned plays no longer exist

3. Add validation for slot assignments:
   - Ensure assigned plays exist in current play data
   - Ensure slot numbers are valid (1-6)
   - Log warnings for invalid assignments

### Phase 5: Testing & Edge Cases

**Goal:** Ensure system handles all edge cases

**Test Cases:**
1. **Game Start → Playbooks → Submit → Navigate to Play Details → Return**
   - Should restore from temporary state
   - Should match submitted values

2. **Timeout → Game Plan → Playbooks**
   - Should load from database with correct game context
   - Should validate context matches

3. **Quarter Break → Playbooks → Navigate to Play Details → Return**
   - Should restore from temporary state
   - Should preserve work in progress

4. **Database Load Fails**
   - Should preserve current UI state
   - Should show warning to user
   - Should not reset everything to 0

5. **Context Mismatch**
   - Should not load incorrect data
   - Should show warning
   - Should use defaults or preserve current state

6. **Multiple Navigation Cycles**
   - Playbooks → Play Details → Playbooks → Play Details → Playbooks
   - Should preserve state correctly through multiple cycles

7. **Submit After Navigation**
   - Navigate to Play Details → Return → Make Changes → Submit
   - Should save correctly to database
   - Should clear temporary state

## Implementation Priority

1. **Phase 1 (Context Validation)** - Critical for fixing Bug 1
2. **Phase 2 (Temporary State)** - Critical for fixing Bug 2
3. **Phase 3 (Safe Reset)** - Important for preventing data loss
4. **Phase 4 (Slot Assignments)** - Important for complete persistence
5. **Phase 5 (Testing)** - Essential for validation

## Success Criteria

- ✅ Settings persist correctly across all navigation scenarios
- ✅ No data loss when navigating between pages
- ✅ Context validation prevents loading incorrect data
- ✅ Temporary state preserves work in progress
- ✅ Database remains authoritative source of truth
- ✅ User has full control over when settings are saved
- ✅ System handles edge cases gracefully (failures, mismatches, etc.)

## Open Questions

1. Should we auto-save to database on navigation away from playbooks? (Currently: No, only on Submit)
2. Should we show a warning if user navigates away with unsaved changes? (Currently: Yes, but might need improvement)
3. How should we handle play data changes (plays added/removed) between sessions?
4. Should temporary state expire after a certain time? (Currently: sessionStorage, cleared on browser close)
5. Should we support "undo" functionality for playbook changes?

