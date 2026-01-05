## Playbooks Page ✅ **IMPLEMENTED** (January 2025)

**Base Constants**

1. **Page Location**: `FrontEnd/static/playbooks.html`
2. **API Endpoints**:
   - `GET /api/playbooks` - Loads plays and playbook settings
   - `POST /api/playbooks` - Saves playbook settings
3. **Data Storage**: `teams.{team_id}.playbook_settings` in mode documents (games/tournaments/franchises)
4. **Six Percentage Sections** (must total 100% each):
   - **Offense**: Motion (4 slots), Set Play Inside (3 slots), Set Play Attack (3 slots), Set Play Outside (3 slots)
   - **Defense**: Man Defense (3 plays), Zone Defense (5 plays)
5. **Validation**: All six sections must total exactly 100% to enable Submit button
6. **Default Values**: Top row = 100%, all others = 0% (first-time users)

**System Flow (8 Steps)**

1. **Page Load** - Check localStorage for full state, if not found load from API (database)
2. **Play Loading** - Loads plays from `teams.{team_id}.plays` filtered by `play_type` and `play_focus`
3. **User Configuration** - User sets percentages, slot assignments, motion dropdowns, position filters
4. **Position Filter Changes** - When position filters change, percentages for hidden plays are reset to 0% (ensures totals remain valid)
5. **Even Distribution** - Optional toggle per section to auto-distribute percentages evenly
6. **Navigation** - Before navigating to Play Details, save full state to localStorage
7. **Return Navigation** - Restore full state from localStorage (skip API to preserve work)
8. **Submit** - Save all settings to database via `POST /api/playbooks`, clear localStorage
9. **Back Button** - Warn if unsaved changes exist, navigate back to previous page

**Long Form Documentation**

### Overview

The Playbooks page allows users to configure their team's offensive and defensive playcall distributions and priority assignments. Users set percentage distributions for each play type and assign priority slots 1-6 to specific plays.

**Location:** `FrontEnd/static/playbooks.html`  
**Purpose:** Configure playcall percentages and priority assignments for offense and defense  
**Status:** ✅ Backend integration complete - loads plays from database

### Layout Structure

**Desktop Grid Layout:**
- **2-column grid** (4 equal columns total, each section spans 2 columns)
- **Column 1-2:** Offense Play Calls (spans 2 columns, 50% width)
- **Column 3-4:** Defense Play Calls (spans 2 columns, 50% width)

**Header Row:**
- **Left:** Page title "Playbooks"
- **Right:** Submit button with helper text

### Six Percentage Sections

Each section contains multiple rows with numeric percentage inputs (0-100) and must total exactly 100%:

**Offense Sections:**
1. **Motion Offense** - 4 slots (loads from database, fills empty slots with "To Be Added")
2. **Set Play Inside Offense** - 3 slots (loads from database, fills empty slots with "To Be Added")
3. **Set Play Attack Offense** - 3 slots (loads from database, fills empty slots with "To Be Added")
4. **Set Play Outside Offense** - 3 slots (loads from database, fills empty slots with "To Be Added")

**Defense Sections:**
5. **Man Defense** - 3 plays (Man Defense, Man Defense Variant 2, Man Defense Variant 3)
6. **Zone Defense** - 5 plays (2-3 Zone, 3-2 Zone, 1-3-1 Zone, Zone Variant 4, Zone Variant 5)

**Validation Rules:**
- Each section displays live total (e.g., "Total: 100%")
- If user edit would push section over 100%, change is prevented/reverted
- Inline error message: "This section must total 100%. You're over by X%."
- Warning state (subtle color + helper text) when section total ≠ 100%
- Submit button disabled unless ALL six sections total exactly 100%

### Even Distribution Button ✅ **IMPLEMENTED** (January 2025)

**Location:** Right-aligned in each section header, next to the section title  
**Styling:** Silver border, semi-transparent background, matches other UI buttons  
**Purpose:** Automatically distribute percentages evenly across all plays in a section

**Behavior:**
- **Button Text:** "Even Distribution"
- **Click Action:** Distributes percentages evenly across all plays in that section (excluding "To Be Added" placeholders)
- **Position Filtering:** For offense sections, only distributes to plays that match the selected position filters

**Distribution Logic:**
1. **Calculate Base Percentage:** `Math.floor(100 / num_plays)`
2. **Calculate Remainder:** `100 - (base * num_plays)`
3. **Assign Base:** All plays receive the base percentage
4. **Distribute Remainder:** Remainder is distributed one percentage point at a time to the top plays (in order) until remainder is exhausted

**Examples:**
- **Motion Offense (4 plays):** Each play gets 25% (100 ÷ 4 = 25, no remainder)
- **Set Play Inside (6 plays):** Base = 16%, remainder = 4% → Top 2 plays get 17%, remaining 4 plays get 16%
- **Set Play Attack (3 plays):** Base = 33%, remainder = 1% → Top play gets 34%, remaining 2 plays get 33%
- **Man Defense (3 plays):** Base = 33%, remainder = 1% → Top play gets 34%, remaining 2 plays get 33%
- **Zone Defense (5 plays):** Base = 20%, remainder = 0% → All plays get 20%

**Toggle Behavior (January 2025):**
- **Toggle On/Off:** Clicking the button toggles Even Distribution for that section
- **Visual Indicator:** When enabled, button shows "Even Distribution ✓" with orange highlight
- **Auto-Recalculate:** When position filters change, sections with Even Distribution enabled automatically recalculate percentages for the currently visible plays
- **Manual Edit Disables:** If a user manually edits a percentage in a section with Even Distribution enabled, the toggle is automatically disabled for that section

**Implementation Details:**
- **Frontend:** `handleEvenDistribution(sectionKey)` method in `PlaybooksUI` class toggles state
- **State Tracking:** `this.evenDistributionEnabled` object tracks which sections have Even Distribution enabled
- **Distribution Logic:** `distributePercentagesEvenly(sectionKey)` method performs the actual distribution
- **State Update:** Updates `this.state.sections[sectionKey][playId].percentage` for each play
- **Re-render:** Automatically re-renders the section and updates totals after distribution
- **Position Filter Integration:** When position filters change, `handlePositionFilterClick()` checks if Even Distribution is enabled and auto-recalculates percentages

### Even Distribution - All Button ✅ **IMPLEMENTED** (January 2025)

**Location:** Right-aligned next to the "Offense" column title header  
**Styling:** Matches individual Even Distribution buttons (silver border, semi-transparent background)  
**Purpose:** Apply Even Distribution to all offense sections (Motion, Set Play Inside, Set Play Attack, Set Play Outside) with a single click

**Behavior:**
- **Button Text:** "Even Distribution - All"
- **Click Action:** Enables Even Distribution for all four offense sections and distributes percentages evenly across all plays in each section
- **Visual Indicator:** When all offense sections have Even Distribution enabled, button shows "Even Distribution - All ✓" with orange highlight
- **State Synchronization:** Button state automatically updates when individual section Even Distribution toggles change (e.g., if user manually edits a percentage and disables one section, the "All" button reflects this)

**Implementation Details:**
- **Frontend:** `handleEvenDistributionAll()` method in `PlaybooksUI` class applies Even Distribution to all offense sections
- **State Tracking:** `updateEvenDistributionAllButton()` method checks if all offense sections have Even Distribution enabled and updates button visual state accordingly
- **Integration:** Button state is updated whenever individual section Even Distribution states change (via `updateEvenDistributionButton()`)

### Default Values (First-Time User)

**If no saved settings exist:**
- Top row in each section = 100%
- All other rows = 0%
- Motion dropdowns default to "-" (explicit unselected state - user must select Inside/Attack/Outside)

### Submit Button

**Location:** Top-right of page header  
**Styling:** Orange button (`#ff7a00`)  
**Behavior:**
- **Enabled:** Only when ALL six section totals == 100%
- **Disabled:** When any section total != 100%
  - Reduced opacity (0.5)
  - Disabled pointer events
  - Helper text displayed: "All sections must total 100% to submit."
- **On Click (when enabled):**
  - Runs final validation
  - Saves UI state to localStorage (for UI persistence)
  - Saves playbook percentages to database via `POST /api/playbooks`
  - Saves position filter button selections to localStorage (for session persistence)
  - Shows success toast notification ("Playbooks saved successfully")
  - On error, shows error toast with details

**Save Process:**
1. Extracts percentages from state (excludes "To Be Added" plays)
2. Builds request with mode, team_id, and mode-specific ID (game_id/tournament_id/franchise_id)
3. Falls back to localStorage for game_id if not in URL (single mode)
4. Validates required parameters before sending
5. Backend resolves team_id (name to ID) and ensures team objects exist
6. Saves to `teams.{team_id}.playbook_settings` in appropriate mode document
7. **After successful save:** Clears unsaved changes flag and removes full state from localStorage (since it's now persisted in database)

**Unsaved Changes Warning (January 2025):**
- **Tracking:** `hasUnsavedChanges` flag tracks if user has made any changes since last submit
- **Warning Popup:** When user clicks "Back" button with unsaved changes, a modal popup appears:
  - **Message:** "You haven't submitted playbook changes."
  - **"Submit Playbooks" Button:** Saves changes to database, then navigates back
  - **"Leave Without Submitting" Button:** Clears localStorage state and navigates back without saving
  - **"Don't show this message again" Checkbox:** Stores preference in `sessionStorage` (session-based for now, will migrate to user accounts later)
- **Suppression:** If user checks "Don't show again", warning is suppressed for the current browser session
- **State Persistence:** Settings are saved to localStorage when navigating to play details, so they persist when user returns to Playbooks page

### Data Persistence Strategy (January 2025)

**Core Principle:** User work should persist during navigation, but only be saved to database on explicit user action (Submit Playbooks). This minimizes database calls and gives users control over when their work is persisted.

**Key Preferences:**
1. **Preserve Work During Navigation:** All user work (percentages, slot assignments, toggles, filters) must persist when navigating between pages (e.g., Playbooks → Play Details → Playbooks)
2. **Database Save Only on Submit:** Only save to database when user explicitly clicks "Submit Playbooks" - no auto-saves to database
3. **localStorage for Navigation:** Use localStorage to preserve work in progress during navigation
4. **Database for Persistence:** Use database as source of truth for saved settings (after Submit)
5. **Minimize Database Calls:** Avoid unnecessary database reads/writes - only read on initial load (when no localStorage), only write on Submit

**Persistence Behavior:**

1. **Initial Page Load:**
   - **Priority 1:** Check for full state in localStorage (`playbooks_full_state_{mode}_{teamId}`)
     - If exists: Restore everything from localStorage (percentages, slot assignments, motion dropdowns, Even Distribution toggles, position filter selections)
     - This indicates user is returning from play details page or has unsaved work
     - **Skip API call** to avoid overwriting user's current work
   - **Priority 2:** If no localStorage full state, load from API (database)
     - Loads slot assignments, motion dropdowns, and percentages from `teams.{team_id}.playbook_settings`
     - This is the source of truth for persisted settings (after Submit)
   - **Priority 3:** Fallback to old localStorage format (backward compatibility)

2. **Navigation to Play Details:**
   - **Before navigating:** Save complete state to localStorage (`playbooks_full_state_{mode}_{teamId}`)
   - **Includes:** 
     - Percentages (all sections)
     - Slot assignments (Playcall Center 1-6)
     - Motion dropdowns (Inside/Attack/Outside selections)
     - Even Distribution toggles (active/inactive per section)
     - Position filter selections (Standard/PG/SG/SF/PF/C active buttons)
     - Unsaved changes flag
   - **Purpose:** Preserve all user work during navigation
   - **No database call:** Only saves to localStorage

3. **Returning from Play Details:**
   - **Restore from localStorage:** All components restored from full state:
     - ✅ Percentages (all sections) - restored from `fullState.state.sections`
     - ✅ Slot assignments (Playcall Center 1-6) - restored from `fullState.state.slotAssignments`
     - ✅ Motion dropdowns (Inside/Attack/Outside selections) - restored from `fullState.state.motionDropdowns`
     - ✅ Even Distribution toggles (active/inactive per section) - restored from `fullState.evenDistributionEnabled`
     - ✅ Position filter selections (Standard/PG/SG/SF/PF/C active buttons) - restored from `fullState.selectedPositions`
   - **No API call:** Skips API loading to avoid overwriting user's current work
   - **Implementation:** `loadState()` checks localStorage first, only loads from API if localStorage full state doesn't exist

4. **Submit Playbooks:**
   - **Saves to database:** All settings saved to `teams.{team_id}.playbook_settings` in appropriate mode document
   - **Clears localStorage:** Removes full state from localStorage (since it's now persisted in database)
   - **Clears unsaved changes flag:** Resets `hasUnsavedChanges` to `false`
   - **Database becomes source of truth:** Next page load will use database data (since localStorage is cleared)

5. **Back Button (Without Submit):**
   - **If unsaved changes exist:** Shows warning popup
   - **If "Leave Without Submitting":** Clears localStorage full state and navigates away
   - **User's work is lost:** Not saved to database, localStorage cleared

**Key Design Decisions:**
- **localStorage for navigation persistence:** Preserves user work during page-to-page navigation
- **Database for long-term persistence:** Only updated on explicit "Submit Playbooks" action
- **localStorage-first on return:** When returning from play details, localStorage takes precedence over API to preserve current work
- **API-first on initial load:** When no localStorage state exists, API (database) is the source of truth
- **Clear separation:** Navigation persistence (localStorage) vs. long-term persistence (database)

### Back Button

**Location:** Top-right of page header (next to Submit button)  
**Styling:** Blue button (`#4a90e2`)  
**Behavior:**
- **Navigation Logic:**
  - If `from=command_center` parameter exists:
    - Tournament mode → `/static/tournament.html`
    - Franchise mode → `/static/franchise-command-center.html`
  - Otherwise, tries to use `document.referrer` if it's a game-plan URL
  - Falls back to game-plan.html with current mode parameters
- **Purpose:** Returns user to the page they came from (Game Plan, Tournament Command Center, or Franchise Command Center)

### Position Filter Buttons ✅ **IMPLEMENTED** (January 2025, Updated February 2025)

**Location:** Row of buttons above the main playbooks grid  
**Buttons:** Standard, PG, SG, SF, PF, C  
**Behavior:** 
- Users can select up to 2 position filters at once (FIFO - oldest deselected when adding a third)
- When a position filter is toggled off (deselected), percentages for plays that are ONLY in that position filter are automatically reset to 0%
- This ensures section totals remain valid (don't exceed 100% due to hidden plays retaining percentages)
- If Even Distribution is enabled for a section, percentages are automatically redistributed evenly among visible plays after hidden plays are reset
- Position filter selections are saved to localStorage for session persistence

**Percentage Reset Logic (February 2025):**
- When position filters change, `resetHiddenPlayPercentages()` is called for each offense section BEFORE re-rendering
- For each play in a section, if the play is not visible (doesn't match current position filters), its percentage is reset to 0%
- This prevents validation errors where section totals exceed 100% due to hidden plays retaining their percentages
- After percentages are reset, sections are re-rendered and totals are updated
- If Even Distribution is enabled for a section, percentages are automatically redistributed evenly among visible plays after the reset

**Integration with Even Distribution:**
- If Even Distribution is enabled for a section, after hidden plays are reset, percentages are automatically redistributed evenly among visible plays
- This maintains a 100% total for the section while only including visible plays

### Database Integration

**API Endpoint:** `GET /api/playbooks`

**Query Parameters:**
- `mode` (required): `"single"`, `"tournament"`, or `"franchise"`
- `team_id` (required): Team ID
- `game_id` (conditional): Required if mode is `"single"`
- `tournament_id` (conditional): Required if mode is `"tournament"`
- `franchise_id` (conditional): Required if mode is `"franchise"`

**Response:**
```json
{
  "motion": [
    { "name": "3-2 Motion", "play_id": "...", "play_type": "motion", "play_focus": "attack" },
    ...
  ],
  "set_play_inside": [
    { "name": "Base Post Play", "play_id": "...", "play_type": "set_play", "play_focus": "inside" },
    ...
  ],
  "set_play_attack": [...],
  "set_play_outside": [...],
  "slot_assignments": {...},
  "motion_dropdowns": {...},
  "position_filters": {...},
  "even_distribution_all": false,
  "playbook_percentages": {
    "motion": {...},
    "set_play_inside": {...},
    "set_play_attack": {...},
    "set_play_outside": {...},
    "zone_defense": {...},
    "man_defense": {...}
  }
}
```

**Data Source:**
- Plays are loaded from `teams.{team_id}.plays` in the appropriate mode document:
  - **Single Game:** `games_collection` → `game_doc.teams.{team_id}.plays`
  - **Tournament:** `tournaments_collection` → `tournament_doc.teams.{team_id}.plays`
  - **Franchise:** `franchises_collection` → `franchise_doc.teams.{team_id}.plays`

**Play Loading:**
- Frontend loads plays from API on page initialization
- Plays are filtered by `play_type` (motion vs set_play) and `play_focus` (inside/attack/outside)
- Empty slots are filled with "To Be Added" placeholders (disabled for interaction)

**Save Endpoint:** `POST /api/playbooks`

**Request Body:**
```json
{
  "mode": "single" | "tournament" | "franchise",
  "team_id": "...",
  "game_id": "..." (if mode is "single"),
  "tournament_id": "..." (if mode is "tournament"),
  "franchise_id": "..." (if mode is "franchise"),
  "playbook_settings": {
    "motion": {...},
    "set_play_inside": {...},
    "set_play_attack": {...},
    "set_play_outside": {...},
    "zone_defense": {...},
    "man_defense": {...},
    "slot_assignments": {...},
    "motion_dropdowns": {...},
    "position_filters": {...},
    "even_distribution_all": false
  }
}
```

**Save Process:**
- Backend resolves team_id (name to ID) and ensures team objects exist
- Saves to `teams.{team_id}.playbook_settings` in appropriate mode document
- **Single Game Cross-Instance Persistence:** If game document has no settings, checks core `teams` collection for fallback settings

**Even Distribution Toggle Persistence (February 2025):**
- **Macro Toggle:** `even_distribution_all` boolean flag stored in `playbook_settings`
- **Default Value:** `false` (initialized in `initialize_playbook_settings()`)
- **Load Behavior:**
  - If `even_distribution_all === true`: Frontend automatically applies even distribution to all offense sections (motion, set_play_inside, set_play_attack, set_play_outside) on page load, ignoring saved percentages for those sections
  - If `even_distribution_all === false`: Frontend uses saved percentages from `playbook_percentages`
- **Save Behavior:**
  - When user clicks "Even Distribution - All" button: Flag is set to `true` and saved to database
  - When user manually edits any percentage: Flag is set to `false` and saved to database (user's last action)
  - Flag always reflects the user's last action (macro toggle or manual edit)
- **Edge Case:** If user re-enables "Even Distribution - All" after fine-tuning, flag is set to `true` again (stores user's last action)

### Team ID Resolution (SS&S - ObjectId Standardization)

**✅ Standardized Pattern (January 2025):** All navigation now uses `team_id` (ObjectId string) as the consistent anchor for seamless page-to-page transitions.

**Frontend Resolution:**
- **Command Center Entry:** Resolves team name to ObjectId once on page load, stores in `userTeamId` variable and localStorage
- **URL Parameters:** All navigation URLs pass `team_id` (ObjectId) instead of team name
- **Fallback Chain:** Functions use this consistent pattern:
  1. Primary: `team_id` parameter (ObjectId)
  2. Fallback 1: `user_team_id` parameter (ObjectId, used by Game Plan page)
  3. Fallback 2: `home_id` parameter (ObjectId)
  4. Fallback 3: `away_id` parameter (ObjectId)
- This ensures consistency across all navigation paths (Command Center → Game Plan → Playbooks → Play Details → Court → Training → Training Report)

**Backend Resolution:**
- **Prefer ObjectId:** All endpoints (`/api/gameplan`, `/api/playbooks`, `/franchise/team-data`, `/tournament/team-data`) now prefer `team_id` (ObjectId) parameter
- **Backward Compatibility:** Endpoints still accept `team_name` for backward compatibility, but ObjectId is preferred
- **Direct Database Access:** When ObjectId is provided, backend uses it directly as database key (no resolution needed)

**Benefits:**
- **Consistent Navigation:** Same identifier format across all pages
- **No Resolution Overhead:** Backend uses ObjectId directly as database key
- **Data Persistence:** Settings save/load using same key format
- **Experience Continuity:** User's team context preserved across all navigation

**Roster Viewing Pattern:**
- **User's Team:** `team_id` (ObjectId) represents user's team (for navigation context)
- **Viewed Team:** `view_team_id` (ObjectId) represents team being viewed (read-only display)
- **Clear Separation:** User context (`team_id`) vs. display (`view_team_id`) prevents navigation confusion
- **Future-Proof:** Pattern scales to viewing any team (opponents, league teams, etc.) without breaking navigation

**Backend:** The API endpoint (`GET /api/playbooks`) performs team name resolution for backward compatibility, but prefers ObjectId:
- **Single Game/Tournament Mode:** Resolves team names to team_id by:
  1. Direct lookup in document's `teams` collection
  2. Iterating through teams to match by name
  3. Looking up in `teams` collection by name and matching back to document
- **Franchise Mode:** Uses the same team name resolution logic:
  1. Direct lookup in document's `franchise_teams` collection
  2. Iterating through `franchise_teams` to match by name
  3. Looking up in `teams` collection by name and matching back to document
- This ensures that team names (e.g., "Morristown") passed from the frontend are correctly resolved to the actual `team_id` used in the document structure

### Key Files

**Frontend:**
- `FrontEnd/static/playbooks.html` - Page structure
- `FrontEnd/static/playbooks.js` - `PlaybooksUI` class with all UI logic

**Backend:**
- `BackEnd/api/gameplan_routes.py` - `GET /api/playbooks` and `POST /api/playbooks` endpoints

