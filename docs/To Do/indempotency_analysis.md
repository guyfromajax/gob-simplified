# Idempotency Analysis

## Scope

This note summarizes the current idempotency status of:

- Weeks 20-26 recruiting invites
- Week 35 recruiting assignments
- Weekly training
- Gameplay results
- Franchise season transition

`Idempotency` here means re-triggering the same action does not apply it twice or produce a second committed result after the first commit has already occurred.

## Weeks 20-26 Recruiting Invites

### Current Status

`Hard idempotent`

### What Is Protected

- Weekly invite processing is guarded once results for that week already exist.
- In `franchise_routes.py`, weekly invite processing checks `franchise.recruiting_results[week]` first and returns the existing results instead of recomputing them.
- Weekly training also will not rerun once that week is marked complete.
- In normal UI flow, once invites have been processed for that week, `recruiting-orders.html` redirects to `recruiting-results.html`.

### Practical Impact

- Already-established weekly invite results do not rerun or change.
- Late order saves after processing are now rejected at the backend, so the raw API behavior matches the UI lockout.

### Summary

- Backend processing: idempotent
- Normal UI flow: idempotent
- Save-orders API after processing: idempotent

## Week 35 Recruiting Assignments

### Current Status

`Hard idempotent`

### What Is Protected

- `run_week_35_recruiting` checks `week_35_recruiting_ran`.
- If that flag is already `true`, the backend rejects the rerun.
- After a successful run:
  - the franchise advances to week 36
  - `week_35_recruiting_ran` is set to `true`
  - `week_35_recruiting_results` is persisted
- The frontend then redirects away from the recruiting-orders page at week 36.

### Practical Impact

- The user cannot rerun week 35 recruiting in normal UI flow.
- The backend also hard-blocks reruns even if someone tries to bypass the UI.

### Summary

- Backend processing: idempotent
- UI flow: idempotent
- Raw API behavior: idempotent

## Weekly Training

### Current Status

`Idempotent per week`

### What Is Protected

- Franchise training checks whether training has already been completed for the current week.
- If training is already complete, the backend returns an `already_completed` style response and redirects the user to the training report instead of applying training again.
- This prevents duplicate player/team attribute updates for the same week.

### Practical Impact

- The user cannot keep pressing `Submit Training` and stack additional training gains for the same week.
- Training is effectively a one-time weekly commit.

### Summary

- Backend processing: idempotent
- UI flow: idempotent

## Gameplay Results

### Current Status

`Backend idempotent, UX history hardened`

### What Is Protected

- Computer games inside `complete_week()` are mostly protected from duplicate reruns because existing game documents are checked before another sim is executed for the same matchup/week/franchise.
- Franchise standings/results storage is largely stable because `results[week]` is rewritten as a weekly result set, not incremented blindly.
- Team attribute end-of-game recomputation is closer to idempotent because it recalculates from the canonical saved game state rather than stacking arbitrary deltas.

### Practical Impact

- Duplicate franchise-game finalization now claims the game at the franchise level before any player-stat writes occur.
- Revisiting stale gameplay pages through browser history now reloads the page and redirects the user back to the authoritative FCC state once the week has advanced.

### Summary

- Backend processing: idempotent
- UI flow: terminal-safe for normal browser history restore
- Raw API behavior: idempotent

## Franchise Season Transition

### Current Status

`Hard idempotent`

### What Is Protected

- In normal FCC flow, `Go To Next Season` is only presented in the intended post-recruiting state.
- The FCC CTA disables itself and changes text after the user confirms the action.
- On success, the frontend redirects directly back into FCC for the same franchise instance.

### Practical Impact

- `finish_season()` now requires week `36` and consumes a one-time season-transition token before any rollover work begins.
- Revisiting a cached FCC page through browser history forces a reload, so the user lands on the authoritative current franchise state instead of a stale week-36 snapshot.

### Summary

- Backend processing: idempotent
- UI flow: terminal-safe in normal browser history flow
- Raw API behavior: idempotent

## Overall Assessment

### Strongest Idempotency

- Week 35 recruiting assignments
- Weekly training

These both have meaningful backend rerun guards.

### Partial / Softest Idempotency

- No major gaps remain in the flows covered by this note.
- The main residual risks are now around edge-case browser history behavior and any future new commit-style pages that do not adopt the same terminal pattern.

## Recommended Follow-Up

### Backend Idempotency Fixes

The planned hardening steps below have now been implemented:

1. Franchise gameplay finalization now claims the game before any franchise-player stat writes.
2. `finish_season()` now uses a week-36-only one-time transition token.
3. Weeks 20-26 recruiting order saves now reject late writes after results already exist.
4. Gameplay pages (`set-lineup`, `court`) now reload on browser-history restore and redirect back to FCC once the week has advanced.
5. Training now reloads on browser-history restore and redirects to the current training report if that week's training is already committed.
6. FCC now reloads on browser-history restore so stale week-36 transition pages do not persist.
7. Recruiting orders now reload on browser-history restore so stale pre-commit pages are re-evaluated against current franchise state.

### Recommended Implementation Order

1. Monitor the existing one-way transitions in manual QA and staging logs.
2. If another commit-style flow is introduced, give it both:
   - a backend one-time guard before side effects
   - a terminal-history UX treatment on restore
3. Keep new recruiting/gameplay/season-transition changes aligned with this pattern instead of adding page-specific exceptions later.
7. Optional final recruiting UI cleanup / consistency review
