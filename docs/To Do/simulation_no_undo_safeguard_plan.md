# Simulation "No Undo" Safeguard Plan

**Status:** Plan (not yet implemented)  
**Goal:** Prevent users from using the browser back button (or re-requesting) to re-run simulations until they get a desired result (training, quarter, turn, game result). The game is a sports sim; outcomes should be commit-once, not re-rollable.

---

## Approach

**Do not** try to block or intercept the back button in the frontend—that hurts normal navigation and isn’t fully reliable.

**Do** enforce **server-side “already applied” checks**: once a simulation step is persisted, the backend **refuses to run it again**. If the user goes back and clicks “Play Quarter” (or equivalent) again, the server either returns the existing result (idempotent) or returns an error (e.g. 409 “already simulated”) and does **not** re-run the simulation.

---

## Plan by Area

### 1. Quarter / turn (simulate-quarter, simulate-turn)

- Before running a quarter or turn, load the game from the DB.
- If that quarter is already complete (or that turn already applied and saved), **do not** run the simulation again.
- Either:
  - **Idempotent:** Return the existing summary/state for that quarter/turn, or
  - **Strict:** Return 409 Conflict (or 400) with a message like “Quarter already simulated.”
- Ensures: going back and clicking “Play Quarter” again does not re-roll the quarter.

### 2. Training

- Once training for a given franchise/session is marked complete and results are stored, treat a second “run training” for the same session as:
  - No-op (already completed), or
  - Reject with 409 / clear error.
- Ensures: going back and clicking “Run Training” again does not re-apply training or overwrite results.

### 3. Game / week result (save-result, complete-week, etc.)

- When a game is finalized (saved), mark it as such in the DB.
- A second save-result (or equivalent) for the same `game_id` (or same franchise week) should be:
  - **Idempotent:** No double-apply of stats, no double-advance of week/state, or
  - **Reject:** 409 “Game result already saved.”
- Ensures: going back and submitting the result again doesn’t double-count or re-apply.

---

## Implementation Notes

- **Source of truth:** The database. If the persisted state says “quarter 2 complete” or “training complete” or “game saved,” the server must not re-run or re-apply that step.
- **Existing behavior:** The codebase may already have related checks (e.g. quarter regression, “game not found”). This plan extends that idea consistently: **refuse or no-op when the step is already committed.**
- **Edge cases:** Cached pre-quarter page, duplicate tabs, or slow double-clicks should all be handled by the same rule: server checks DB and refuses/no-ops if already applied.

---

## Checklist (when implementing)

- [ ] **simulate-quarter:** Load game from DB; if requested quarter already complete (or later quarter already started), refuse or return existing state.
- [ ] **simulate-turn:** If this turn (or later) already persisted, refuse or return existing state.
- [ ] **Training:** If session/franchise training already completed for this context, refuse or no-op.
- [ ] **save-result / complete-week / game finalization:** If this game/week already saved, idempotent or 409.
- [ ] Document any new error codes or response shapes for the frontend (e.g. 409 handling, optional “already_applied” flag in JSON).
