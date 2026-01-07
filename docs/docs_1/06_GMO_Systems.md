# GMO Systems

> **Last Updated:** February 2025  
> **Status:** Current – Source of Truth for Game Mode Only (GMO) Supporting Systems

This document defines the systems that operate within **Game Mode Only (GMO) instances**, including Tournament and Franchise modes. These systems manage long-lived preparation, planning, and progression state outside of active gameplay.

---

## GMO Supporting Systems Overview

GMO systems persist across multiple gameplay instances and are the primary owners of long-term team and mode state. These systems may read from gameplay results but do not directly manage live game simulation.

---

## Training System (Franchise Mode Only)

### Purpose
Applies player and team development between games.

### Required State
- `franchise.week`
- `franchise.training_status`

### Persistence Rules
- Training effects persist across all GMO and GP instances
- Training history is stored for reporting

### Invariants
- Training effects are applied between games
- Training does not occur during gameplay

---

## Scouting System

### Purpose
Provides opponent intelligence for preparation and planning.

### Behavior
- Scouting reports are displayed as modal overlays
- No separate navigation or URL persistence required

### Invariants
- Scouting data is read-only
- Scouting does not modify game or team state

---

## Game Plan System

### Purpose
Manages strategic settings used in gameplay.

### Persistence Rules
- `strategy_settings` stored in team object
- Loaded during GMO and GP
- Persist until changed by user

### Invariants
- Game Plan settings are not URL parameters
- Settings must load consistently across all instances

---

## Playbooks System

### Purpose
Manages offensive and defensive play selection.

### Persistence Rules
- `playbook_settings` stored in team object
- Includes `slot_assignments` for Playcall Center
- Persist across GMO and GP instances

### Invariants
- Playbook settings are loaded from database
- Legacy `playcall_settings` is deprecated

---

## Team & Roster Viewing

### Purpose
Allows viewing user and opponent team data.

### Required Context
- `team_id` for user team (navigation anchor)
- `view_team_id` or `team_name` for display context

### Invariants
- Navigation anchor must always preserve user team context
- Display context must not override navigation context

---

## GMO Exit Transitions

### To Gameplay (GP)
- Preserve `mode`, `{mode}_id`, `team_id`
- Initialize `game_id`

### To General Account (GA)
- Clear game mode context
- Preserve `user_id`

### To Non-Account (NA)
- Clear all game mode and account data


