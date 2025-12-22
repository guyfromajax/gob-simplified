# Team ID Navigation Pattern (SS&S)

> **Last Updated:** January 2025  
> **Status:** ✅ Implemented

## Overview

This document describes the standardized pattern for using `team_id` (ObjectId string) as the navigation anchor across the entire application. This pattern ensures seamless page-to-page transitions, consistent data persistence, and stable user experience flow.

## Core Principle

**`team_id` (ObjectId) = User's Team Anchor**

The `team_id` parameter in URLs always represents the **user's team** (ObjectId string). This serves as the consistent anchor that allows seamless navigation between screens without losing context or data.

## Navigation Anchor Set

For seamless navigation, you need three parameters:

1. **`mode`** (franchise/tournament/single) - Which collection/endpoints to use
2. **`doc_id`** (franchise_id/tournament_id/game_id) - Which document within that collection
3. **`team_id`** (ObjectId string) - Which team within that document (user's team)

Together, these three parameters form the complete navigation anchor.

## Implementation Pattern

### Frontend: Command Center Entry

**Franchise Mode:**
```javascript
// 1. Check URL params first (for navigation from other pages)
const urlParams = new URLSearchParams(window.location.search);
const urlTeamId = urlParams.get('team_id');
if (urlTeamId) {
  userTeamId = urlTeamId;
  localStorage.setItem('franchise_user_team_id', userTeamId);
}

// 2. Load command center data (includes team_id)
const topData = await fetchJSON(`/franchise/command-center/data?franchise_id=${franchiseId}`);
if (topData && topData.team_id && !userTeamId) {
  userTeamId = topData.team_id;
  localStorage.setItem('franchise_user_team_id', userTeamId);
}
```

**Tournament Mode:**
```javascript
// Similar pattern - check URL params, then tournament state
const urlTeamId = urlParams.get('team_id');
if (urlTeamId) {
  userTeamId = urlTeamId;
  localStorage.setItem('userTeamId', userTeamId);
}

// Tournament state endpoint returns user_team_object_id
if (tournament && tournament.user_team_object_id && !userTeamId) {
  userTeamId = tournament.user_team_object_id;
  localStorage.setItem('userTeamId', userTeamId);
}
```

### Frontend: Navigation URLs

**All navigation URLs include `team_id` (ObjectId):**

```javascript
// Command Center → Game Plan
const url = `/game-plan.html?mode=franchise&franchise_id=${franchiseId}&user_team_id=${userTeamId}&from=command_center`;

// Game Plan → Command Center
const url = `/franchise-command-center.html?franchise_id=${franchiseId}&team_id=${userTeamId}`;

// Command Center → Training
const url = `/static/training.html?franchise_id=${franchiseId}&mode=franchise&team_id=${userTeamId}`;

// Training → Training Report (backend redirects with team_id)
// Backend includes: ?team_id=${userTeamId}

// Training Report → Command Center
const url = `/franchise-command-center.html?franchise_id=${franchiseId}&team_id=${teamId}`;
```

### Backend: Endpoint Pattern

**All endpoints prefer `team_id` (ObjectId), with backward compatibility:**

```python
@router.get("/franchise/team-data")
def get_franchise_team_data(franchise_id: str, team_id: str = None, team_name: str = None):
    """
    ✅ SS&S: Prefers team_id (ObjectId) for consistent navigation.
    Falls back to team_name resolution for backward compatibility.
    """
    # Prefer team_id (ObjectId) if provided
    if team_id:
        try:
            ObjectId(team_id)  # Validate
            actual_team_id = team_id
        except:
            # If not ObjectId, resolve as team name
            team_doc = db.teams.find_one({"name": team_id})
            if team_doc:
                actual_team_id = str(team_doc["_id"])
    elif team_name:
        # Fallback to team_name resolution
        team_doc = db.teams.find_one({"name": team_name})
        actual_team_id = str(team_doc["_id"])
    
    # Use actual_team_id directly as database key
    team_obj = franchise_teams.get(actual_team_id, {})
```

## Roster Viewing Pattern

When implementing functionality to view computer team rosters, use a separate parameter:

**Pattern:**
- **`team_id`** = User's team (ObjectId) - for navigation context
- **`view_team_id`** = Team being viewed (ObjectId) - for display only

**Example Navigation:**
```javascript
// Command Center → View Opponent Roster
function viewOpponentRoster(opponentObjectId) {
  const userTeamId = getTeamId(); // User's team ObjectId
  const url = `/team-roster.html?franchise_id=${franchiseId}&team_id=${userTeamId}&view_team_id=${opponentObjectId}`;
  window.location.href = url;
}

// Roster View → Back to Command Center
function backToCommandCenter() {
  const urlParams = new URLSearchParams(window.location.search);
  const userTeamId = urlParams.get('team_id'); // User's team
  const franchiseId = urlParams.get('franchise_id');
  window.location.href = `/franchise-command-center.html?franchise_id=${franchiseId}&team_id=${userTeamId}`;
}
```

**Backend Endpoint Pattern:**
```python
@router.get("/team-data")
def get_team_data(team_id: str, view_team_id: str = None, ...):
    """
    If view_team_id provided: return read-only data for viewed team
    Otherwise: return editable data for user's team (team_id)
    """
    target_id = view_team_id if view_team_id else team_id
    read_only = view_team_id is not None
    
    # Fetch team data using target_id
    # Return with read_only flag if needed
```

## Benefits

1. **Consistent Identifier:** ObjectId matches database keys exactly
2. **No Resolution Overhead:** Backend uses ObjectId directly (no name lookup needed)
3. **Stable Navigation:** Same format everywhere prevents resolution errors
4. **Data Persistence:** Settings save/load using same key format
5. **Experience Continuity:** User's team context preserved across all navigation
6. **Future-Proof:** Pattern scales to viewing any team without breaking navigation

## Files Updated

### Frontend
- `FrontEnd/static/franchise-command-center.js` - Resolves and stores ObjectId, updates all navigation
- `FrontEnd/static/tournament.js` - Resolves and stores ObjectId, updates all navigation
- `FrontEnd/static/game-plan.js` - Uses ObjectId consistently
- `FrontEnd/static/training.js` - Passes team_id in navigation
- `FrontEnd/static/training-report.js` - Uses ObjectId from URL params

### Backend
- `BackEnd/api/franchise_routes.py` - `/franchise/command-center/data` returns `team_id`, `/franchise/team-data` accepts `team_id`
- `BackEnd/api/tournament_routes.py` - `/tournament/state` returns `user_team_object_id`, `/tournament/team-data` accepts `team_id`
- `BackEnd/api/gameplan_routes.py` - `get_gameplan()` and `update_gameplan()` prefer ObjectId

## Migration Notes

- **Backward Compatibility:** All endpoints still accept team names for backward compatibility
- **Gradual Migration:** Frontend now passes ObjectId, but backend can still resolve names if needed
- **No Breaking Changes:** Existing URLs with team names still work (backend resolves them)

## Related Documentation

- `docs/master_game_doc.md` - Team ID Resolution section
- `docs/NAVIGATION_HELPER_DESIGN.md` - URL parameter patterns

