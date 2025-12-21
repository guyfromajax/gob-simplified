# Game Plan System

## Overview

The Game Plan screen allows users to customize their team's offensive and defensive strategies before each game. Settings are persisted per game mode (Franchise, Tournament, Single Game) and are specific to the user's team only.

## User Flow

### From Lineup Screen (Single Game Mode)
1. **Lineup Selection** → User sets their starting 5 players
2. **Game Plan** → User adjusts offensive and defensive sliders
3. **Gameplay** → Game begins with the configured game plan

### From Command Center (Tournament/Franchise Mode)
1. **Command Center** → User clicks "Set Game Plan" button
2. **Game Plan** → User adjusts offensive and defensive sliders
3. **Save Game Plan** → Settings saved to team's game plan, returns to Command Center

## Sliders

The Game Plan screen features **11 sliders** divided into two categories:

### Offense (6 sliders)
Each slider controls the frequency of a specific offensive playcall:

- **Base** - Base offense plays
- **Freelance** - Freelance motion plays
- **Inside** - Inside scoring plays
- **Attack** - Attacking plays
- **Outside** - Perimeter/outside plays
- **Set** - Set plays

**Value Range:** 0-4  
**Labels:**
- 0 = "Never"
- 2 = "Normal"
- 4 = "Most"

### Defense / General (5 sliders)

- **Defense** - Man vs Zone defense preference
  - 0 = "100% Man"
  - 2 = "50/50"
  - 4 = "100% Zone"

- **Tempo** - Game pace
  - 0 = "Slow"
  - 2 = "Normal"
  - 4 = "Fast"

- **Aggression** - Defensive intensity
  - 0 = "Passive"
  - 2 = "Normal"
  - 4 = "Aggressive"

- **Fast Breaks** - Fast break frequency
  - 0 = "Never"
  - 2 = "Normal"
  - 4 = "Always"

- **FC Press** - Full court press usage
  - 0 = "Never"
  - 2 = "Normal"
  - 4 = "Always"

- **HC Trap** - Half court trap usage
  - 0 = "Never"
  - 2 = "Normal"
  - 4 = "Always"

## Validation Rules

### "Offense Not All Zero" Rule

**Requirement:** At least one offensive slider must be above 0.

**Enforcement:**
- Frontend validation blocks save attempt
- Backend validation returns 400 error
- User sees modal: *"At least one Offense setting must be above 'Never'. Please increase any Offense slider."*

**Rationale:** A team must run at least some offensive plays during a game.

### Defense/General Settings

No restrictions - all defense/general sliders can be set to any value (0-4).

## Data Storage

### Database Structure

Settings are stored in **mode-specific documents**, NOT in the global Teams collection:

```javascript
// Franchise Mode
{
  "_id": ObjectId("..."),
  "franchise_teams": {
    "<team_id>": {
      "playcall_settings": {
        "Base": 2,
        "Freelance": 2,
        "Inside": 2,
        "Attack": 2,
        "Outside": 2,
        "Set": 2
      },
      "strategy_settings": {
        "defense": 2,
        "tempo": 2,
        "aggression": 2,
        "fast_break": 2,
        "half_court_trap": 2,
        "full_court_press": 2
      },
      // ... other team attributes
    }
  }
}

// Tournament Mode
{
  "_id": ObjectId("..."),
  "teams": {
    "<team_id>": {
      "playcall_settings": { /* ... */ },
      "strategy_settings": { /* ... */ }
    }
  }
}

// Single Game Mode
{
  "_id": ObjectId("..."),
  "teams": {
    "<team_id>": {
      "playcall_settings": { /* ... */ },
      "strategy_settings": { /* ... */ }
    }
  }
}
```

### Default Values

When a new team object is created (or settings are missing), all sliders default to **2** (Normal/middle position).

### Franchise Mode Special Handling

- When a franchise season is initialized, **all 8 teams** in the league receive team objects with default game plan settings
- Only the user's team can be edited via the Game Plan screen
- Opponent teams use their default settings

## API Endpoints

### GET /api/gameplan

Fetch current game plan settings for a team.

**Query Parameters:**
- `mode` (required): `"franchise"`, `"tournament"`, or `"single"`
- `team_id` (required): MongoDB ObjectId of the team
- `franchise_id` (conditional): Required if mode is `"franchise"`
- `tournament_id` (conditional): Required if mode is `"tournament"`
- `game_id` (conditional): Required if mode is `"single"`

**Response:**
```json
{
  "playcall_settings": {
    "Base": 2,
    "Freelance": 3,
    "Inside": 4,
    "Attack": 1,
    "Outside": 2,
    "Set": 2
  },
  "strategy_settings": {
    "defense": 2,
    "tempo": 3,
    "aggression": 2,
    "fast_break": 4,
    "half_court_trap": 1,
    "full_court_press": 0
  }
}
```

### PUT /api/gameplan

Update game plan settings for a team.

**Request Body:**
```json
{
  "mode": "franchise",
  "team_id": "507f1f77bcf86cd799439011",
  "franchise_id": "507f1f77bcf86cd799439012",
  "playcall_settings": {
    "Base": 2,
    "Freelance": 3,
    "Inside": 4,
    "Attack": 1,
    "Outside": 2,
    "Set": 2
  },
  "strategy_settings": {
    "defense": 2,
    "tempo": 3,
    "aggression": 2,
    "fast_break": 4,
    "half_court_trap": 1,
    "full_court_press": 0
  }
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Game plan saved successfully"
}
```

**Response (Validation Error):**
```json
{
  "detail": "At least one Offense setting must be above 'Never'. Please increase any Offense slider."
}
```

## Frontend Files

- **`game-plan.html`** - Page structure with 11 sliders
- **`game-plan.css`** - Styling (gradient backgrounds, slider styling)
- **`game-plan.js`** - Logic for load/save/validation

## Backend Files

- **`BackEnd/api/gameplan_routes.py`** - API endpoints
- **`BackEnd/models/franchise_manager.py`** - Franchise initialization includes settings
- **`BackEnd/api/api.py`** - Router registration

## User Actions

### Navigation Source Detection
The Game Plan screen detects where the user came from via the `from` URL parameter:
- `from=lineup` (default): User came from Lineup Selection screen
- `from=command_center`: User came from Tournament or Franchise Command Center

### Button Behavior by Navigation Source

#### From Lineup Screen (`from=lineup`)
- **"Back To Lineup"** button: Visible, navigates back to Lineup Selection screen (saves settings quietly)
- **"Play Game"** button: Visible, validates and saves settings, then navigates to `court.html` to start game
- **"Cancel"** button: Hidden
- **"Back To Locker Room"** button: Hidden

#### From Command Center (`from=command_center`)
- **"Back To Locker Room"** button: Visible, saves settings quietly and navigates back to Command Center
- **"Save Game Plan"** button: Visible, validates and saves settings, then navigates back to Command Center
- **"Back To Lineup"** button: Hidden
- **"Cancel"** button: Hidden

### Save & Continue (From Lineup)
- Validates offense settings
- Saves to database (or localStorage for single game mode)
- Shows toast "Game plan saved!"
- Redirects to gameplay screen (`court.html`)

### Save Game Plan (From Command Center)
- Validates offense settings
- Saves to database (`playcall_settings` and `strategy_settings` to team object)
- Shows toast "Game plan saved!"
- Redirects back to Command Center (Tournament or Franchise)

### Back To Lineup (From Lineup)
- Saves settings quietly (no validation, no toast)
- Navigates back to Lineup Selection screen
- Preserves all lineup and game state parameters

### Back To Locker Room (From Command Center)
- Saves settings quietly (no validation, no toast)
- Navigates back to Command Center
- Includes `team_id` in URL for proper command center initialization

### Reset
- Reloads current settings from database
- Resets all sliders to saved values
- Shows toast "Settings reset"

## Implementation Notes

- **Read-only Teams Collection:** The global `teams` collection is never modified by this feature
- **Mode Isolation:** Each game mode maintains its own settings (franchise settings don't affect tournament settings)
- **URL Parameter Passing:** All context (mode, team, game ID, lineup, etc.) is passed via URL query parameters
- **Slider Snapping:** Sliders have 5 discrete positions (0, 1, 2, 3, 4) with no in-between values
- **Responsive Design:** Layout adapts for mobile/tablet viewing
- **Team ID Resolution:** When coming from command center, uses `user_team_id` URL parameter; when from lineup, uses `home_id`/`away_id` based on `my_team` side
- **Data Storage:** Game plan consists of two separate objects:
  - `playcall_settings`: Offense settings (Base, Freelance, Inside, Attack, Outside, Set)
  - `strategy_settings`: Defense/General settings (defense, tempo, aggression, half_court_trap, full_court_press)
- **Storage Locations:**
  - Franchise: `franchise_teams.{team_id}.playcall_settings` and `franchise_teams.{team_id}.strategy_settings`
  - Tournament: `teams.{team_id}.playcall_settings` and `teams.{team_id}.strategy_settings`
  - Single Game: `teams.{team_id}.playcall_settings` and `teams.{team_id}.strategy_settings`

## Future Enhancements

Potential future additions:
- AI opponent game plan customization
- Game plan templates/presets
- In-game adjustments
- Analytics showing which settings correlate with wins
- Coach recommendations based on opponent tendencies

