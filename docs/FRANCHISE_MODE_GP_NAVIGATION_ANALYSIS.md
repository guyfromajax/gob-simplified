# Franchise Mode GP (Gameplay) Navigation Analysis

**Date:** February 2025  
**Purpose:** Identify all GP flow instances and core variables used for seamless data and user settings persistence in Franchise mode

---

## GP Flow Instances (from user-flow.md)

Based on `user-flow.md`, the GP (Gameplay) instances are:

### **Lineup Select Experience (GP)**
- **Lineup Screen** Links To:
  - Game Plan
  - Box Score
  - Gameplay Screen (court.html)

- **Game Plan** (from Lineup) Links To:
  - Lineup Screen
  - Playbooks Page
  - Gameplay Screen

- **Box Score** Links To:
  - Lineup Screen

- **Playbooks Page** (from Game Plan) Links To:
  - Game Plan
  - **Play Details Page** (individual play pages) ← **GP Context**

- **Play Details Page** Links To:
  - Playbooks Page (back navigation)

---

## Core Variables for Franchise Mode GP Navigation

### **Core Navigation Anchor Set (Required for all GP transitions)**

These three variables form the foundation for seamless navigation and data persistence across all GP screens:

1. **`mode`** (string)
   - **Value:** `"franchise"`
   - **Purpose:** Identifies franchise mode for routing and data access
   - **Location:** URL parameter
   - **Required:** Yes - must be present in all GP transitions

2. **`franchise_id`** (ObjectId string)
   - **Value:** ObjectId string (e.g., `"507f1f77bcf86cd799439011"`)
   - **Purpose:** Identifies the franchise document for data persistence
   - **Location:** URL parameter
   - **Required:** Yes - must be present in all GP transitions

3. **`team_id`** (ObjectId string)
   - **Value:** ObjectId string (user's team)
   - **Purpose:** User's team anchor for navigation and data access
   - **Location:** URL parameter
   - **Required:** Yes - must be present in all GP transitions
   - **Note:** Should be ObjectId format, not team name

---

### **Game-Specific Variables (Required for gameplay state)**

These variables track the current game state and are required when in an active game:

4. **`game_id`** (ObjectId string)
   - **Value:** ObjectId string of the game document
   - **Purpose:** Identifies the active game document
   - **Location:** URL parameter, database `games_collection`
   - **Required:** Yes - when game is initialized
   - **Note:** Created when game is initialized, persists throughout game instance

5. **`quarter`** (integer)
   - **Value:** Quarter number (1-4)
   - **Purpose:** Tracks current quarter
   - **Location:** URL parameter
   - **Required:** Yes - for game state tracking

6. **`clock`** (string, optional)
   - **Value:** Clock time (e.g., `"12:00"`, `"8:34"`)
   - **Purpose:** Preserves clock time during timeout navigation
   - **Location:** URL parameter
   - **Required:** Conditional - only when resuming from timeout

7. **`resume_from_timeout`** (boolean, optional)
   - **Value:** `"true"` or `"false"` (as string)
   - **Purpose:** Indicates game is resuming from timeout
   - **Location:** URL parameter
   - **Required:** Conditional - only when resuming from timeout

---

### **Lineup Variables (Required for lineup management)**

8. **`my_team`** (string)
   - **Value:** `"home"` or `"away"`
   - **Purpose:** Identifies which side the user's team is on
   - **Location:** URL parameter
   - **Required:** Yes - for lineup management

9. **`home`** (string)
   - **Value:** Team name (e.g., `"Morristown"`)
   - **Purpose:** Home team name for display
   - **Location:** URL parameter
   - **Required:** Yes - for game context

10. **`away`** (string)
    - **Value:** Team name (e.g., `"Bentley-Truman"`)
    - **Purpose:** Away team name for display
    - **Location:** URL parameter
    - **Required:** Yes - for game context

11. **`home_id`** (ObjectId string)
    - **Value:** ObjectId string of home team
    - **Purpose:** Home team ObjectId for backend lookups
    - **Location:** URL parameter
    - **Required:** Yes - for backend operations

12. **`away_id`** (ObjectId string)
    - **Value:** ObjectId string of away team
    - **Purpose:** Away team ObjectId for backend lookups
    - **Location:** URL parameter
    - **Required:** Yes - for backend operations

13. **Lineup Position Parameters** (optional, but recommended)
    - **Format:** `{my_team}_{position}` (e.g., `home_pg`, `away_sg`)
    - **Positions:** `pg`, `sg`, `sf`, `pf`, `c`
    - **Purpose:** Preserves lineup selections during navigation
    - **Location:** URL parameters
    - **Required:** Conditional - when lineup is set
    - **Example:** `home_pg=507f...&home_sg=507f...&home_sf=507f...&home_pf=507f...&home_c=507f...`

---

### **Franchise-Specific Variables**

14. **`week`** (integer)
    - **Value:** Week number (1-14)
    - **Purpose:** Identifies which week of the franchise season
    - **Location:** URL parameter
    - **Required:** Yes - for franchise context

---

### **Context Variables (Optional, for navigation context)**

15. **`from`** (string, optional)
    - **Value:** Source screen identifier (e.g., `"lineup"`, `"game-plan"`, `"command_center"`)
    - **Purpose:** Determines back navigation behavior
    - **Location:** URL parameter
    - **Required:** No - but recommended for proper back navigation

16. **`user_team_id`** (ObjectId string, deprecated)
    - **Value:** ObjectId string (legacy parameter name)
    - **Purpose:** Legacy parameter - should use `team_id` instead
    - **Location:** URL parameter (for backward compatibility)
    - **Required:** No - deprecated, use `team_id` instead
    - **Note:** Still supported for backward compatibility, but `team_id` is preferred

---

## Navigation Patterns

### **Pattern 1: GMO → GP (Starting a Game)**

**Flow:** FCC → Lineup → Gameplay

**Required Variables:**
- `mode=franchise`
- `franchise_id={franchise_id}`
- `team_id={team_id}` (user's team ObjectId)
- `week={week}`
- `home={home_team_name}`
- `away={away_team_name}`
- `home_id={home_team_objectId}`
- `away_id={away_team_objectId}`
- `my_team={home|away}`

**Game Initialization:**
- `game_id` is created when game is initialized (via `/api/init-game`)
- `game_id` is added to URL after initialization

---

### **Pattern 2: GP → GP (Timeout Navigation)**

**Flow:** Gameplay → Game Plan → Gameplay (resume)

**Required Variables:**
- All core navigation anchor set (`mode`, `franchise_id`, `team_id`)
- `game_id` (required for active game)
- `quarter` (current quarter)
- `clock` (clock time at timeout)
- `resume_from_timeout=true`
- Lineup parameters (`{my_team}_{position}`)

**Implementation:**
- Uses `TimeoutNavigationHelper.buildGameNavigationParams()` to preserve all state
- Helper automatically includes `mode`, `franchise_id`, `week` from source params

---

### **Pattern 3: GP → GMO (Game Completion)**

**Flow:** Gameplay → Box Score → FCC

**Required Variables:**
- All core navigation anchor set (`mode`, `franchise_id`, `team_id`)
- `game_id` (for box score access)
- `home`, `away` (for box score display)

**Implementation:**
- `gameCompletionPopup.js` constructs FCC URL with complete anchor set
- Box Score "Go To Locker Room" button preserves all variables

---

### **Pattern 4: GP → GP (Between GP Screens)**

**Flow:** Lineup ↔ Game Plan ↔ Playbooks ↔ Play Details ↔ Box Score

**Required Variables:**
- All core navigation anchor set (`mode`, `franchise_id`, `team_id`)
- `game_id` (if game is active)
- `quarter` (if game is active)
- Lineup parameters (if lineup is set)
- `from` (for back navigation context)

**Implementation:**
- All transitions use `TimeoutNavigationHelper.buildGameNavigationParams()`
- Helper preserves all game state and navigation context

---

## Key Implementation Details

### **TimeoutNavigationHelper Usage**

The `TimeoutNavigationHelper.buildGameNavigationParams()` function automatically preserves:

1. **Core Navigation Anchor Set:**
   - `mode` (from source params)
   - `franchise_id` (from source params)
   - `week` (from source params)

2. **Game State:**
   - `game_id`
   - `quarter`
   - `clock`
   - `resume_from_timeout`

3. **Lineup State:**
   - All lineup position parameters (`{my_team}_{position}`)

4. **Team Context:**
   - `home`, `away`
   - `home_id`, `away_id`
   - `my_team`

**Note:** The helper now automatically preserves `team_id` (standardized parameter name) from source params. It prefers `team_id` over `user_team_id` but maintains backward compatibility.

---

## Summary: Core Variables for Franchise Mode GP

### **Always Required (Core Navigation Anchor Set)**
1. `mode` = `"franchise"`
2. `franchise_id` = ObjectId string
3. `team_id` = ObjectId string (user's team)

### **Required When Game is Active**
4. `game_id` = ObjectId string
5. `quarter` = integer (1-4)
6. `week` = integer (1-14) - franchise-specific

### **Required for Game Context**
7. `home` = team name string
8. `away` = team name string
9. `home_id` = ObjectId string
10. `away_id` = ObjectId string
11. `my_team` = `"home"` or `"away"`

### **Conditional (Timeout Navigation)**
12. `clock` = string (when resuming from timeout)
13. `resume_from_timeout` = `"true"` (when resuming from timeout)

### **Conditional (Lineup Management)**
14. `{my_team}_{position}` = ObjectId strings (when lineup is set)

### **Optional (Navigation Context)**
15. `from` = string (for back navigation)

---

## Verification Checklist

For each GP transition, verify these variables are preserved:

- [ ] `mode=franchise` is present
- [ ] `franchise_id` is present (ObjectId format)
- [ ] `team_id` is present (ObjectId format, not team name)
- [ ] `game_id` is present (when game is active)
- [ ] `quarter` is present (when game is active)
- [ ] `week` is present (franchise-specific)
- [ ] `home`, `away`, `home_id`, `away_id` are present
- [ ] `my_team` is present
- [ ] Lineup parameters are preserved (when applicable)
- [ ] Timeout state is preserved (when applicable)

---

## GP Flow Instances to Verify

Based on `user-flow.md` and codebase analysis, the following GP transitions need verification:

### **Core GP Transitions**
1. **Lineup → Gameplay** - Starting a new game
2. **Lineup → Game Plan** - Accessing game plan from lineup
3. **Lineup → Box Score** - Viewing box score during game
4. **Game Plan → Gameplay** - Resuming game from game plan
5. **Game Plan → Playbooks** ← **NEEDS VERIFICATION** (GP context)
6. **Playbooks → Game Plan** ← **NEEDS VERIFICATION** (GP context)
7. **Playbooks → Play Details** ← **NEEDS VERIFICATION** (GP context)
8. **Play Details → Playbooks** ← **NEEDS VERIFICATION** (GP context)
9. **Gameplay → Game Plan** - Timeout navigation
10. **Gameplay → Box Score** - Game completion
11. **Box Score → FCC** - Returning to command center after game

### **Status of Playbooks/Play Details Navigation**

**Current Implementation:**
- ✅ **Game Plan → Playbooks:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()` (line 539-597 in `game-plan.js`)
- ✅ **Playbooks → Game Plan:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()` (line 1884-1919 in `playbooks.js`)
- ✅ **Playbooks → Play Details:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()` (line 1083-1132 in `playbooks.js`)
- ✅ **Play Details → Playbooks:** Uses `TimeoutNavigationHelper.buildGameNavigationParams()` (line 397-440 in `play-details.html`)

**Issue Fixed:**
- ✅ **`team_id` is now preserved:** Updated `TimeoutNavigationHelper` to preserve `team_id` (standardized parameter name)
- **Location:** `timeoutNavigationHelper.js:62-70` - now preserves `team_id` from source params (prefers `team_id` over `user_team_id`)
- **Backward Compatibility:** Still preserves `user_team_id` if it exists and differs from `team_id`
- **Status:** ✅ Fixed - All GP transitions using the helper will now preserve `team_id` correctly

---

## Next Steps

1. ✅ **Fixed `TimeoutNavigationHelper` to preserve `team_id`** - All GP transitions using the helper will now preserve `team_id` correctly

2. **Verify all GP transitions preserve the core navigation anchor set:**
   - Test each transition to ensure `mode`, `franchise_id`, and `team_id` are preserved
   - Verify Playbooks/Play Details transitions work correctly

3. **Identify any missing variables in GP transitions:**
   - Check if any transitions manually add parameters that should be handled by the helper
   - Verify all transitions use the helper consistently

4. **Test complete GP flow end-to-end:**
   - Test all navigation paths in franchise mode
   - Verify data persistence across all transitions

