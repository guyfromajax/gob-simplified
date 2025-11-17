# Failsafe Revert Point

## Safe Commit to Revert To (if needed)

**Commit:** `48eb1e4d`  
**Message:** "Fix: Set quarter to 1 in init-game to avoid simulation conflicts"  
**Date:** Before Emotion/Momentum feature was added

This is the **last known stable commit** before the Emotion/Momentum lineup screen feature that exposed the game_id reuse issue.

## How to Revert (if needed):

```bash
git checkout 48eb1e4d
# Test that everything works
# If good, create a new branch:
git checkout -b revert-to-stable
git push origin revert-to-stable
```

## What Changed After This Commit:

- `ae8382b3`: Initialize game on lineup screen to show Emotion and Momentum
  - Added `/api/init-game` endpoint
  - Started storing `game_id` in localStorage
  - Exposed game_id reuse bug that was always there
  
- All subsequent commits: Attempts to fix stats carrying over between games

## Current Fix Strategy (Option 3):

Instead of reverting, we're implementing Option 3:
- Frontend clears `game_id` from localStorage when starting a new game
- Removes all complex heuristic detection logic
- Simple rule: No game_id = New game, Has game_id = Resume game

