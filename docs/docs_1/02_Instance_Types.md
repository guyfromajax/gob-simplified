# Instance Types

> **Last Updated:** January 2026  
> **Status:** Current – Source of Truth for Instance Types

This document defines the **four instance types** used throughout Geeked-Out Basketball (GOB).  
Each instance type represents a distinct **user context**, with explicit rules governing what data may exist, what must persist, and which transitions are allowed.

---

## Instance Type Mapping

- **NA (Non-Account)** = Bucket 4  
- **GA (General Account)** = Bucket 1  
- **GMO (Game Mode Only)** = Bucket 2  
- **GP (Gameplay)** = Bucket 3  

---

## Bucket 1: General Account (GA)

### Definition
User is logged into their account but not in a specific game mode instance (outside of Single Game, Tournament Mode, or Franchise Mode instance).

### Examples
- Homepage (homepage.html)
- Mode selection screen (mode-select.html)
- Settings/Account pages (TBD)
- Tutorial pages (TBD)

### Required State
- `user_id` - User account identifier

### Persisted State
- User account data (if needed for page display)
- Optional user preferences

### Validation Rules
- **User ID (Strict):** Must be present and valid (user must be logged in to be in GA instance)
- **No game mode validation:** No game mode context to validate

### Entry Conditions
- Account creation
- Successful login

### Exit Conditions
- Enter a game mode instance
- Logout (transition to NA)

---

## Bucket 2: Game Mode Only (GMO)

### Definition
User is in a Tournament Mode or Franchise Mode instance, but not actively playing a game.  
User can never be in a GMO instance in Single Game mode.

### Sub-categories
- **Tournament Mode**
- **Franchise Mode**

### Examples
- Tournament / Franchise Command Center
- Training screen (Franchise only)
- Training Report (Franchise only)
- Playbooks screen
- Game Plan screen
- Team Roster screen
- Standings / Stats screens

### Required State
- **Mode:** `"tournament"` or `"franchise"`
- **Game Mode Document ID:** `tournament_id` or `franchise_id`
- **Team ID:** `team_id` (ObjectId string - user's team anchor)

### Persisted State
- Game mode document (tournament or franchise)
- Team objects within game mode document
- Strategy settings
- Playbook settings

### Validation Rules
- **Mode + Document ID (Strict):** Must be valid and match
- **Team ID:** Must resolve to a valid team for the user

### Entry Conditions
- User selects Tournament or Franchise mode
- Game mode document initialized

### Exit Conditions
- Start a gameplay instance
- Exit to General Account
- Logout

---

## Bucket 3: Gameplay (GP)

### Definition
User is actively playing a game.

### Sub-categories
- **Single Game Mode Gameplay**
- **Tournament Mode Gameplay**
- **Franchise Mode Gameplay**

### Examples
- Court / Gameplay screen
- Lineup selection (during game)
- Game Plan (during game)
- Playbooks (during game)
- Box Score screen
- Timeout / foul-out flows
- Plays pages (during game)

### Required State
- **Game ID** (when game exists)
- **Mode:** `"single"`, `"tournament"`, or `"franchise"`
- **Team ID:** `team_id` (user's team anchor)
- **Quarter**
- **Score**
- **Time remaining**
- **Lineups**
- **User team side:** `my_team`

### Persisted State
- Game document (single source of truth for game state)
- Timeout state (if applicable)
- Strategy settings (loaded from team object)
- Playbook settings (loaded from team object)

### Entry Conditions
- Game initialized (new or resumed)
- Game context fully resolved

### Exit Conditions
- Game completion
- User exits mid-game
- Logout

---

## Bucket 4: Non-Account (NA)

### Definition
User either does not have an account or is logged out.

### Examples
- Homepage (homepage.html)
- Account creation screen (TBD)
- Account login screen (TBD)
- Public team roster pages

### Required State
- None

### Persisted State
- None

### Entry Conditions
- App load without authentication
- Logout

### Exit Conditions
- Login or account creation

---

## Cross-Bucket Principles

### General Principles
1. **Database is Source of Truth** for game state and game mode state  
2. **Instance Types are Explicit** – user is always in exactly one instance type  
3. **Only One Gameplay Instance** may exist per user at a time  
4. **Game Mode Context** never exists without a valid document ID  
5. **Gameplay State** never directly mutates long-term progression state
