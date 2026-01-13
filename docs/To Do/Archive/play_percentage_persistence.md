# Playbook Percentage Persistence Analysis

**Date:** January 2026  
**Status:** ✅ Fix Implemented - Bug 1 Resolved  
**Related:** Playbooks Page System, Data Persistence System

---

## Executive Summary

This document analyzes how playbook play percentages are persisted in the database and loaded in the frontend across three scenarios:
1. **First time entering Playbooks page** (new franchise instance)
2. **Saving playbook settings**
3. **Leaving and returning to Playbooks page**

**Key Finding:** The `even_distribution_all` flag causes percentages to be redistributed on every page load, overwriting saved percentages when the flag is `true`.

---

## Database Structure

Playbook percentages are stored in the franchise/tournament document at:
```
franchise_teams.{team_id}.playbook_settings
```

**Structure:**
```javascript
{
  motion: {
    "3-2 Motion": 25,
    "4-1 Motion": 25,
    "5-0 Motion": 25,
    "PF Post Motion": 25
  },
  set_play_inside: {
    "Base Post Play": 17,
    "C Post Iso": 17,
    // ... more plays with percentages
  },
  set_play_attack: { /* percentages by play name */ },
  set_play_outside: { /* percentages by play name */ },
  zone_defense: { /* percentages */ },
  man_defense: { /* percentages */ },
  slot_assignments: { /* slot assignments */ },
  motion_dropdowns: { /* dropdown selections */ },
  position_filters: { /* position filter mappings */ },
  even_distribution_all: false  // Flag that controls redistribution behavior
}
```

**Key Points:**
- Percentages are stored using **play names** as keys (e.g., `"3-2 Motion"`)
- ALL percentages including `0%` are saved (database is single source of truth)
- The `even_distribution_all` flag determines redistribution behavior

---

## Scenario 1: First Time Entering Playbooks Page (New Franchise Instance)

### Frontend Flow

1. **Page Initialization (`playbooks.js:295-325`)**
   - `init()` is called
   - `loadPlays()` fetches from `GET /api/playbooks`
   - API returns empty `playbook_percentages` (no saved data yet)
   - `new PlaybooksState(playData)` is created
   - `initDefaults()` sets temporary defaults (first play = 100%, others = 0%)
   - `loadPositionFilterSelections()` loads position filters from localStorage
   - `loadState()` loads saved state

2. **State Initialization (`PlaybooksState.initDefaults()` - `playbooks.js:63-117`)**
   ```javascript
   // Motion plays: First play = 100%, others = 0%
   this.sections.motion[finalPlayId] = {
     percentage: i === 0 ? 100 : 0,
     slot: null,
   };
   
   // Set plays: First play = 100%, others = 0%
   this.sections[key][finalPlayId] = {
     percentage: i === 0 ? 100 : 0,
     slot: null,
   };
   ```

3. **Loading Saved Percentages (`playbooks.js:505-621`)**
   - `loadPlaybookPercentagesFromAPI()` is called
   - **Lines 518-522: Resets ALL percentages to 0% first**
     ```javascript
     Object.keys(this.state.sections).forEach(sectionKey => {
       Object.keys(this.state.sections[sectionKey] || {}).forEach(playId => {
         this.state.sections[sectionKey][playId].percentage = 0;
       });
     });
     ```
   - **Lines 528-615: Applies saved percentages from API**
     - Tries to match plays by name: `percentages.motion[play.name]`
     - If no saved data exists, everything stays at 0%

4. **Even Distribution Check (`playbooks.js:478-497`)**
   - Checks `even_distribution_all` flag (defaults to `false`)
   - Since flag is `false`, saved percentages are used (but they're all 0%)

### Backend Flow (`BackEnd/api/gameplan_routes.py:1163-1572`)

1. **GET /api/playbooks Endpoint**
   - Resolves `actual_team_id` from document's `user_team_object_id`
   - Ensures team objects exist via `ensure_team_objects_exist()`
   - Loads `playbook_settings` from database
   - Returns:
     - Plays list (filtered by position filters if applicable)
     - `playbook_percentages`: Empty `{}` on first load
     - `even_distribution_all`: `false` (default)

### Database State

**Before first save:**
- `playbook_settings` does not exist or is empty
- No percentages are stored

**Result:**
- All percentages end up at 0% after the reset (default 100% for first play is overwritten)
- This is actually **correct behavior** - no saved data means 0%

---

## Scenario 2: Saving Playbook Settings

### Frontend Flow

1. **User Interaction**
   - User sets custom percentages manually (e.g., Motion: 25%, 25%, 25%, 25%)
   - User clicks "Save Playbooks" button

2. **Collecting Percentages (`playbooks.js:2064-2125`)**
   - `handleSubmit()` → `savePlaybookSettings()`
   - Builds `playbookSettings` object from `this.state.sections`
   - **Key: Uses play NAMES as keys** (not play IDs)
     ```javascript
     Object.keys(this.state.sections.motion || {}).forEach(playId => {
       const play = this.playData.motion?.find(p => p.id === playId);
       if (play && play.name !== 'To Be Added') {
         const percentage = playData.percentage || 0;
         playbookSettings.motion[play.name] = percentage;  // ← Play NAME as key
       }
     });
     ```

3. **Including All Data (`playbooks.js:2150-2171`)**
   ```javascript
   playbookSettings.slot_assignments = this.state.slotAssignments;
   playbookSettings.motion_dropdowns = this.state.motionDropdowns;
   playbookSettings.even_distribution_all = this.evenDistributionAllFlag || false;
   ```
   - **Important:** Saves ALL percentages including `0%`
   - Saves `even_distribution_all` flag (will be `false` if user set custom percentages)

4. **Sending to Backend (`playbooks.js:2174-2200`)**
   ```javascript
   const requestBody = {
     mode: mode,
     team_id: teamId,
     playbook_settings: playbookSettings,
     franchise_id: franchiseId,  // or tournament_id, game_id
   };
   
   fetch(API_CONFIG.buildUrl('/api/playbooks'), {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify(requestBody)
   });
   ```

### Backend Flow (`BackEnd/api/gameplan_routes.py:1585-1868`)

1. **POST /api/playbooks Endpoint**
   - Resolves `actual_team_id` from document's `user_team_object_id`
   - Ensures team objects exist
   - Reloads document after `ensure_team_objects_exist()` (in case it was modified)

2. **Saving to Database (`BackEnd/api/gameplan_routes.py:1735-1803`)**
   ```python
   if request.mode == "franchise":
       update_path = f"franchise_teams.{actual_team_id}.playbook_settings"
   else:
       update_path = f"teams.{actual_team_id}.playbook_settings"
   
   collection.update_one(
       {"_id": ObjectId(doc_id)},
       {"$set": {update_path: request.playbook_settings}}
   )
   ```

3. **Verification (`BackEnd/api/gameplan_routes.py:1817-1830`)**
   - Reads back saved data to verify
   - Logs sample percentages for debugging

### Database State After Save

```javascript
{
  motion: {
    "3-2 Motion": 25,
    "4-1 Motion": 25,
    "5-0 Motion": 25,
    "PF Post Motion": 25
  },
  set_play_inside: {
    "Base Post Play": 17,
    "C Post Iso": 17,
    "PF Post Up": 17,
    "PG Post Up": 17,
    "SF Back Door": 17,
    "SG Pass & Cut": 15
  },
  set_play_attack: { /* percentages */ },
  set_play_outside: { /* percentages */ },
  zone_defense: { /* percentages */ },
  man_defense: { "Man": 100 },
  slot_assignments: { /* slot assignments */ },
  motion_dropdowns: { /* dropdown selections */ },
  position_filters: { /* position filter mappings */ },
  even_distribution_all: false  // User had custom percentages, so flag is false
}
```

**Key Points:**
- Percentages are stored using **play names** as keys
- ALL percentages including `0%` are saved
- `even_distribution_all` is `false` when user sets custom percentages

---

## Scenario 3: Leaving and Returning to Playbooks Page

### Frontend Flow

1. **Page Initialization (Same as Scenario 1)**
   - `init()` → `loadPlays()` → Fetches from `GET /api/playbooks`
   - API now returns saved `playbook_percentages` from database
   - `new PlaybooksState(playData)` → `initDefaults()` sets temporary defaults
   - `loadPositionFilterSelections()` loads position filters

2. **Loading Saved Percentages (`playbooks.js:505-621`)**
   - `loadPlaybookPercentagesFromAPI()` is called
   - **Lines 518-522: Resets ALL percentages to 0% first**
     ```javascript
     Object.keys(this.state.sections).forEach(sectionKey => {
       Object.keys(this.state.sections[sectionKey] || {}).forEach(playId => {
         this.state.sections[sectionKey][playId].percentage = 0;
       });
     });
     ```
   - **Lines 528-615: Applies saved percentages from API**
     ```javascript
     // Motion percentages
     Object.keys(this.state.sections.motion || {}).forEach(playId => {
       const play = this.playData.motion?.find(p => p.id === playId);
       if (play) {
         if (percentages.motion[play.name] !== undefined) {
           this.state.sections.motion[playId].percentage = percentages.motion[play.name];
         }
       }
     });
     
     // Set play percentages (same pattern for inside, attack, outside)
     // Defense percentages (same pattern)
     ```
     - **Key:** Matches plays by `play.name` to find saved percentage
     - If `play.name` doesn't match saved key exactly, percentage won't apply

3. **✅ FIXED: Even Distribution Check (`playbooks.js:469-503`)**
   ```javascript
   // ✅ FIX: even_distribution_all flag controls UI state only, NOT automatic redistribution on load
   if (this.evenDistributionAllFlag === true) {
     // Sync button states to show that even distribution was last used
     const offenseSections = ['motion', 'set-play-inside', 'set-play-attack', 'set-play-outside'];
     offenseSections.forEach(sectionKey => {
       this.evenDistributionEnabled[sectionKey] = true;
       this.updateEvenDistributionButton(sectionKey);
     });
     // ✅ Saved percentages are already loaded and displayed (no redistribution)
   }
   ```
   - **If `even_distribution_all: true`**, UI state is synced to show button as active
   - **Saved percentages are always respected** - no redistribution on load
   - Redistribution only happens when user explicitly clicks "Even Distribution - All" button

### Backend Flow (Same as Scenario 1)

1. **GET /api/playbooks Endpoint**
   - Loads `playbook_settings` from database
   - Returns saved percentages in `playbook_percentages` object
   - Returns `even_distribution_all` flag

### Database State

**When returning:**
- `playbook_settings` exists with saved percentages
- `even_distribution_all` flag may be `true` or `false`

**Result (After Fix):**
- If `even_distribution_all: false` → Saved percentages are loaded correctly ✅
- If `even_distribution_all: true` → Saved percentages are loaded correctly (they were already evenly distributed when saved) ✅
- Redistribution only happens when user clicks "Even Distribution - All" button, not on page load ✅

---

## Bugs and Issues Identified

### ✅ Bug 1: `even_distribution_all` Flag Redistributes on Every Load - **FIXED**

**Location:** `FrontEnd/static/playbooks.js:469-503`

**Problem (Before Fix):**
- When `even_distribution_all: true`, percentages were redistributed on **every page load**
- This overwrote saved percentages that the user manually set
- The flag triggered automatic redistribution instead of just controlling UI state

**Root Cause:**
- The implementation treated `even_distribution_all: true` as "redistribute on every load"
- This conflicted with the user's expectation that saved percentages should persist

**Impact (Before Fix):**
- User sets custom percentages → Saves → Returns to page → Percentages were redistributed
- User could not persist custom percentages when `even_distribution_all: true`

**Fix Implemented:**
- Changed `loadState()` to **never redistribute on load**
- Flag now only controls UI state (button appearance), not redistribution behavior
- Saved percentages are **always respected** regardless of flag value
- Redistribution only happens when user explicitly clicks "Even Distribution - All" button
- When user saves after redistribution, the evenly-distributed percentages are saved to database
- On next load, saved evenly-distributed percentages are displayed (no redistribution occurs)

**Fixed Code:**
```javascript
async loadState() {
  // Always load saved percentages from database first
  await this.loadSlotAssignmentsFromAPI();
  await this.loadPlaybookPercentagesFromAPI();
  
  // ✅ FIX: even_distribution_all flag controls UI state only, NOT automatic redistribution on load
  // Saved percentages are always respected regardless of flag value
  if (this.evenDistributionAllFlag === true) {
    // Sync button states to show that even distribution was last used
    const offenseSections = ['motion', 'set-play-inside', 'set-play-attack', 'set-play-outside'];
    offenseSections.forEach(sectionKey => {
      this.evenDistributionEnabled[sectionKey] = true;
      this.updateEvenDistributionButton(sectionKey);
    });
    this.updateEvenDistributionAllButton();
    // ✅ Saved percentages are already loaded and displayed (they were saved when user clicked "Even Distribution - All")
  } else {
    // Flag is false - saved percentages are already loaded, just sync button states
    const offenseSections = ['motion', 'set-play-inside', 'set-play-attack', 'set-play-outside'];
    offenseSections.forEach(sectionKey => {
      this.evenDistributionEnabled[sectionKey] = false;
      this.updateEvenDistributionButton(sectionKey);
    });
    this.updateEvenDistributionAllButton();
  }
}
```

---

### ✅ Issue 2: Percentage Matching - State Sections Only Contain First N Plays - **FIXED**

**Location:** `FrontEnd/static/playbooks.js:505-622`

**Problem (Before Fix):**
- Saved percentages use **play names** as keys (e.g., `"Base Post Play"`, `"SG Pass & Cut"`)
- Loading iterated through `this.state.sections[sectionKey]` which only contains first N plays (first 3 for set plays, first 4 for motion)
- State sections are initialized with first N plays from API, regardless of position filters
- When position filters are active, visible plays might not be in state sections
- Result: Percentages for plays not in state sections (e.g., plays at index 4, 5, 6) never get loaded

**Root Cause:**
- `initDefaults()` creates state entries for first N plays only (based on array index)
- `loadPlaybookPercentagesFromAPI()` iterated through state sections, not all plays
- If a play wasn't in the first N plays, it wasn't in state sections, so its percentage couldn't be loaded

**Fix Implemented:**
- Changed `loadPlaybookPercentagesFromAPI()` to iterate through **ALL plays** in `this.playData[settingsKey]`
- For each play, find or create the corresponding state entry (by playId)
- Apply saved percentage using `play.name` as key
- This ensures ALL plays from database are matched, not just the first N that were initialized in state

**Fixed Code:**
```javascript
// ✅ FIX: Iterate through ALL plays in playData, not just state sections
// State sections only contain first N plays, but saved percentages include ALL plays
const plays = this.playData[settingsKey] || [];

plays.forEach((play, index) => {
  if (!play || play.name === 'To Be Added') return;
  
  const playId = play.id || `${sectionKey}-${index + 1}`;
  
  // Ensure this play exists in state sections (create if needed)
  if (!this.state.sections[sectionKey][playId]) {
    this.state.sections[sectionKey][playId] = {
      percentage: 0,
      slot: null,
    };
  }
  
  // Apply saved percentage if it exists in database
  if (sectionPercentages[play.name] !== undefined) {
    this.state.sections[sectionKey][playId].percentage = sectionPercentages[play.name];
  }
});
```

**Matching Strategy:**
- **Database/API Storage:** Uses **play names** as keys (`{"Base Post Play": 50, "SG Pass & Cut": 50}`)
- **Frontend State:** Uses **generated IDs** like `set-inside-1`, `set-inside-2` based on array index
- **Matching Process:**
  1. Iterate through ALL plays in `playData` (not just state sections)
  2. For each play, find or create state entry by `playId`
  3. Look up saved percentage using `play.name` as key
  4. Apply percentage to state entry

**Remaining Considerations:**
- Play names must match exactly (whitespace, casing, etc.)
- If play names change in database, old percentages won't apply
- Future enhancement: Use `play_id` (database ID) instead of play names for more robustness

---

### ℹ️ Issue 3: `initDefaults()` Creates Temporary Defaults That Get Overwritten

**Location:** `FrontEnd/static/playbooks.js:63-117`

**Problem:**
- `initDefaults()` sets first play = 100%, others = 0%
- These defaults are immediately overwritten by `loadPlaybookPercentagesFromAPI()` which resets all to 0%
- This is harmless but unnecessary work

**Current Code:**
```javascript
// initDefaults() sets:
this.sections.motion[finalPlayId] = {
  percentage: i === 0 ? 100 : 0,  // First play = 100%
  slot: null,
};

// Then loadPlaybookPercentagesFromAPI() resets:
this.state.sections[sectionKey][playId].percentage = 0;  // Everything to 0%
```

**Impact:**
- Minor performance impact (setting values that are immediately overwritten)
- Code confusion (defaults don't actually matter)

**Note:** This is low priority - not a bug, just inefficient

---

## Recommended Solutions

### ✅ Solution 1: Fix `even_distribution_all` Flag Behavior - **IMPLEMENTED**

**Problem:** Flag was causing redistribution on every page load, overwriting saved percentages

**Fix Implemented:**
1. **Changed flag semantics:** `even_distribution_all: true` now means "user last used even distribution" but does **NOT** auto-redistribute on load
2. **Save percentages when flag is true:** When user clicks "Even Distribution - All", the redistributed percentages are saved to the database
3. **Always respect saved percentages:** Saved percentages are always loaded and displayed, regardless of flag value
4. **Flag controls UI state only:** The flag now only controls button state (enabled/disabled appearance) and does not trigger redistribution

**Implementation Details:**

**Frontend (`playbooks.js:469-503`):**
```javascript
async loadState() {
  // Always load saved percentages from database first
  await this.loadSlotAssignmentsFromAPI();
  await this.loadPlaybookPercentagesFromAPI();
  
  // ✅ FIX: even_distribution_all flag controls UI state only, NOT automatic redistribution on load
  // Saved percentages are always respected regardless of flag value
  if (this.evenDistributionAllFlag === true) {
    // Sync button states to show that even distribution was last used
    const offenseSections = ['motion', 'set-play-inside', 'set-play-attack', 'set-play-outside'];
    offenseSections.forEach(sectionKey => {
      this.evenDistributionEnabled[sectionKey] = true;
      this.updateEvenDistributionButton(sectionKey);
    });
    this.updateEvenDistributionAllButton();
    // ✅ Saved percentages are already loaded and displayed (they were saved when user clicked "Even Distribution - All")
  } else {
    // Flag is false - saved percentages are already loaded, just sync button states
    const offenseSections = ['motion', 'set-play-inside', 'set-play-attack', 'set-play-outside'];
    offenseSections.forEach(sectionKey => {
      this.evenDistributionEnabled[sectionKey] = false;
      this.updateEvenDistributionButton(sectionKey);
    });
    this.updateEvenDistributionAllButton();
  }
  
  // Update button visual states after loading
  Object.keys(this.evenDistributionEnabled).forEach(sectionKey => {
    this.updateEvenDistributionButton(sectionKey);
  });
}
```

**When User Clicks "Even Distribution - All" (`playbooks.js:1345-1386`):**
- Already correctly implemented: Redistributes percentages, sets flag to true, marks as unsaved
- User must click "Save Playbooks" to persist the redistributed percentages

**When User Saves (`playbooks.js:2064-2225`):**
- Already correctly implemented: Saves current percentages (including evenly-distributed ones) and flag value
- On next load, saved evenly-distributed percentages are loaded and displayed

**When Position Filters Change (`playbooks.js:1520-1584`):**
- Already correctly implemented: If `even_distribution_all: true`, redistributes among new visible plays and marks as unsaved
- This behavior is intentional - maintains even distribution when visible plays change

**Summary (After Fix):**
- ✅ `even_distribution_all: true` means "user last used even distribution" (saved percentages are already evenly distributed)
- ✅ When user clicks "Even Distribution - All", redistribute and mark as unsaved
- ✅ When user saves, save redistributed percentages to database with flag = true
- ✅ On load, **always respect saved percentages** (no redistribution)
- ✅ When position filters change and flag is true, redistribute among new visible plays (intentional behavior)
- ✅ Flag controls UI state (button appearance) only - does not auto-redistribute on load

---

### ✅ Solution 2: Use Play IDs for Percentage Matching (Future Enhancement)

**Problem:** Percentage matching relies on play names, which could break if names change

**Recommended Fix (Future):**
- Use `play_id` (database ID) as keys instead of play names
- This ensures percentages persist even if play names change
- Requires migration of existing data

**Current Approach (Keep for now):**
- Play names are stable and consistent
- Migration is not necessary immediately
- Document as potential future enhancement

**If Implementing:**
1. Change saving to use `play_id` as key:
   ```javascript
   playbookSettings.motion[play.play_id] = percentage;  // Use play_id instead of play.name
   ```
2. Change loading to match by `play_id`:
   ```javascript
   if (percentages.motion[play.play_id] !== undefined) {
     this.state.sections.motion[playId].percentage = percentages.motion[play.play_id];
   }
   ```
3. Migrate existing database entries from names to IDs

---

### ℹ️ Solution 3: Optimize `initDefaults()` (Low Priority)

**Problem:** Sets defaults that are immediately overwritten

**Recommended Fix:**
- Remove default percentage assignments from `initDefaults()`
- Start with all percentages at 0%
- Only set percentages when loading from API or when user interacts

**Implementation:**
```javascript
initDefaults() {
  // ✅ FIX: Don't set default percentages - they'll be loaded from API or set to 0
  // Just initialize the structure
  const motionPlays = this.playData.motion || [];
  const motionSlots = 4;
  
  for (let i = 0; i < motionSlots; i++) {
    const play = i < motionPlays.length ? motionPlays[i] : TO_BE_ADDED_PLACEHOLDER;
    const playId = play.id || `motion-${i + 1}`;
    const finalPlayId = (play.name === 'To Be Added') ? `motion-tba-${i + 1}` : playId;
    
    this.sections.motion[finalPlayId] = {
      percentage: 0,  // ✅ Always start at 0, will be loaded from API
      slot: null,
    };
  }
  
  // Same for set plays and defense...
}
```

**Note:** This is a minor optimization - not critical, but cleaner code

---

## Testing Plan

### Test Case 1: First Time Load (No Saved Data)
1. Create new franchise instance
2. Navigate to Playbooks page
3. **Expected:** All percentages are 0%
4. **Verify:** No errors in console

### Test Case 2: Save Custom Percentages
1. Set custom percentages (e.g., Motion: 25%, 25%, 25%, 25%)
2. Click "Save Playbooks"
3. **Expected:** Percentages saved to database
4. **Verify:** Check database to confirm percentages are stored with play names as keys

### Test Case 3: Return to Page with Custom Percentages (`even_distribution_all: false`)
1. Set custom percentages and save
2. Navigate away from Playbooks page
3. Return to Playbooks page
4. **Expected:** Saved percentages are loaded and displayed correctly
5. **Verify:** Percentages match what was saved

### Test Case 4: Even Distribution All (`even_distribution_all: true`) - ✅ FIXED
1. Click "Even Distribution - All" button
2. Percentages redistribute evenly
3. Click "Save Playbooks"
4. Navigate away and return
5. **Expected:** Saved evenly-distributed percentages are loaded and displayed
6. **Verify:** Percentages match what was saved (NOT redistributed again on load)
7. **Status:** ✅ This test case should now pass - percentages are not redistributed on load

### Test Case 5: Position Filter Change with Even Distribution
1. Set `even_distribution_all: true` and save
2. Return to page, confirm percentages are loaded correctly (not redistributed on load)
3. Change position filter (e.g., add SG)
4. **Expected:** Percentages redistribute among new visible plays, marked as unsaved (intentional behavior)
5. Save again
6. Return to page
7. **Expected:** Saved redistributed percentages are loaded correctly (not redistributed again on load)
8. **Status:** ✅ This test case should now pass - redistribution only happens on position filter change, not on load

### Test Case 6: Percentage Matching (Play Names)
1. Save percentages for specific plays
2. Verify play names in database match play names in frontend
3. Return to page
4. **Expected:** Percentages apply correctly for matching play names

---

## Implementation Status

1. **✅ COMPLETED:** Fix `even_distribution_all` flag behavior (Bug 1)
   - Fixed: Flag no longer causes redistribution on page load
   - Saved percentages are always respected
   - Core functionality issue resolved

2. **PENDING:** Document play name matching as known limitation (Issue 2)
   - Currently working but could break if play names change
   - Future enhancement to use play IDs
   - Status: Documented as potential future enhancement

3. **PENDING:** Optimize `initDefaults()` (Issue 3)
   - Minor performance improvement
   - Code cleanliness
   - Status: Low priority, not blocking

---

## Related Files

**Frontend:**
- `FrontEnd/static/playbooks.js` - Main playbooks logic
- `FrontEnd/static/playbooks.html` - Playbooks page structure

**Backend:**
- `BackEnd/api/gameplan_routes.py` - GET/POST /api/playbooks endpoints

**Documentation:**
- `docs/docs_1_systems/06_GMO_Supporting_Systems/Playbooks_Page.md` - Playbooks page system documentation
- `docs/docs_1_systems/03_Data_Persistence/Data_Persistence_System.md` - Data persistence system overview

---

## Notes

- Percentages are stored using **play names** as keys (not play IDs)
- ALL percentages including `0%` are saved to ensure database is complete source of truth
- The `even_distribution_all` flag currently causes redistribution on every load - this is the primary bug
- Position filters affect which plays are visible, but saved percentages for hidden plays are preserved (reset to 0% only when visible)

---

## Questions for Review

1. **Should `even_distribution_all: true` auto-redistribute on position filter changes?**
   - Current implementation: Yes (when flag is true)
   - Recommended: Yes (makes sense - if user wants even distribution, maintain it when filters change)
   - Question: Should this auto-save or require user to click Save?

2. **Should percentages be stored using play IDs instead of play names?**
   - Current: Play names
   - Future: Play IDs (more robust)
   - Question: Is migration worth the effort now, or defer to future enhancement?

3. **What should happen if play names don't match between database and frontend?**
   - Current: Silent failure (percentage stays 0%)
   - Recommended: Log warning, but keep current behavior
   - Question: Should we add validation/error handling?

