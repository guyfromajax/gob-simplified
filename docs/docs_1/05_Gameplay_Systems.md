# Gameplay Systems

> **Last Updated:** February 2025  
> **Status:** Current – Source of Truth for Gameplay (GP) Supporting Systems

This document defines the gameplay-supporting systems that operate within **Gameplay (GP) instances**. These systems are active only during live games and interact with core game state, turn resolution, and persistence boundaries.

---

## Gameplay Supporting Systems Overview

Gameplay systems operate only within GP instances and must obey GP invariants. These systems may read long-lived configuration (e.g., playbooks, strategy settings) but must not directly mutate long-term progression data.

**HCO Turn Resolution System**
1. Get Base Constants
2. Get Team Attributes / Strategy Calls
3. Calibrate Constants based on Team Attributes & Strategy Calls
3. Randomize Order of Stopping Event Checks
-Standard Fouls
-Steal Attempt
-Dead Ball Turnover
4. Shot Attempt (if not Stopping Event)

**FCP/HCT Turn Resolution System**

**Fast Break Turn Resolution System**

**OREB Tuyrn Resolution System**

**Free Throw Turn Resolution System**

---

## Timeout & Resume System

### Purpose
Supports resuming gameplay from timeout or foul-out scenarios with full state continuity.

### Required State
- `game_id`
- `quarter`
- `clock`
- `resume_from_timeout`

### Database State
- `timeout_next_play_type`
- `timeout_offense_team_id`

### Validation Rules
- Timeout resume requires both frontend URL parameters and backend timeout state
- Database must contain timeout state for the quarter
- Lightweight fallback allowed when `game_id` exists and `quarter === 1`

### Invariants
- Timeout state must exist before resume
- Timeout resume cannot occur without a valid `game_id`
- Quarter breaks must not set `resume_from_timeout`

---

## Foul-Out Resume System

### Purpose
Handles player foul-out events that interrupt gameplay and require lineup updates.

### Required Behavior
- Remove fouled-out player from lineup
- Resume gameplay using same mechanics as timeout resume

### Invariants
- Fouled-out player must not appear in active lineup after resume
- Foul-out resume uses timeout resume rules

---

## Quarter Break System

### Purpose
Handles transitions between quarters without timeout semantics.

### Required State
- `game_id`
- `quarter`

### Validation Rules
- `game_id` is required
- `resume_from_timeout` must not be set

### Invariants
- Quarter breaks are not timeouts
- No timeout state should be applied

---

## Game Completion System

### Purpose
Finalizes game state and triggers post-game transitions.

### Required Behavior
- Display End-of-Game popup
- Allow Box Score viewing
- Navigate back to GMO or Mode Select

### Required State
- `game_id`
- `mode`
- `team_id`
- `tournament_id` or `franchise_id` (if applicable)

### Invariants
- Game document must contain complete `box_score`
- Final game state must be persisted before transition

---

## Stat Rollup & Finalization

### Purpose
Rolls up game statistics into long-term records.

### Required Behavior
- Tournament Mode: call `save_result()`
- Franchise Mode: call `complete_week()`
- `finalize_game()` is invoked within both flows
- Applies to user games and computer games

### Invariants
- `finalize_game()` must be called with correct identifiers
- Game document must be complete before rollup

### Race Condition Prevention (Franchise Mode)
- `simulate-quarter` returns `final_game_document`
- `complete_week()` uses provided document if available
- Falls back to database lookup if not provided

---

## Gameplay Exit Transitions

### Mid-Game Exit
- Preserve game document in database
- Allow future resume

### Post-Game Exit
- Ensure stat rollup and completion flags are applied
- Transition to GMO or GA as appropriate


### Turn Types
-HCO
-Fast Break
-FCP/HCT
-OREB
-Free Throw
-BIP
-SIP
-Opening Tip

### Supporting Systems
-Rebounding System: /Users/jamesdavies/gob-simplified/docs/docs_1_systems/05_GP_Supporting_Systems/Rebound_System.md
-HCO Resolution System: /Users/jamesdavies/gob-simplified/docs/docs_1_systems/05_GP_Supporting_Systems/HCO_Turn_Resolution_System.md
-Energy System
-FCP/HCT Resolution System
-Fast Break Resolution System
-Animation System
-Stopper System
-Steal System
-Statistics System
