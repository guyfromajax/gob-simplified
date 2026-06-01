# simulate-quarter API + observability cleanup

Backlog of high-leverage cleanups surfaced while wiring the User Archetype System
(the per-quarter stash hook lives in `simulate_quarter_endpoint`). Captured to
revisit later — **not** yet actioned. Do this work behind existing tests, and
verify before deleting (see caveat).

## 1. `simulate_quarter_endpoint` bloat (BackEnd/api/api.py ~2206–4085)

~1,800-line god-function grown by accretion. Signals of dead/stale weight:

| Signal | Example |
|---|---|
| Stacked fix-comments | `# ✅ FIX:`, `# ✅ PHASE 3.3:`, `# ✅ SS&S REFACTOR:`, `# 🔍 DEBUG` |
| Commented-out debug | dead `print` / `# logging.warning(...)` blocks left in place |
| Backward-compat shims | `# BACKWARD COMPATIBILITY: Fallback to old structure`, "old structure: home_team is a string" |
| Redundant save paths | 3 separate `games_collection.update_one({_id},{$set:summary})` sites |
| Debug/profiling branches | `if profile:`, `[DEBUG_PC]`, `[TIMEOUT TRACE]` interleaved with logic |

**Approach (incremental, test-backed):** audit each block, classify as
- **safe-remove** — commented-out code, dead debug, provably unreachable
- **verify-first** — backward-compat branches: confirm no current game doc still hits them before removing
- **load-bearing** — leave

**Caveat:** "looks unused" ≠ "is unused" in this codebase. A legacy-looking
`apply_coords` artifact was previously load-bearing. Broad `except` blocks (below)
also let dead-looking branches run silently. Prune by evidence, not appearance.

## 2. Broad exception swallowing (hot handlers)

Multiple `except Exception: print("🚨 Mongo upsert failed")` style blocks that
catch-and-continue. **This directly cost a full debug round-trip** — it masked the
archetype stash failure as a generic Mongo error.

- Narrow the catch scope, or at minimum `logging.exception(...)` at ERROR with the
  real traceback instead of a generic string.

## 3. No deploy/version visibility

"Is my code even running?" was guesswork — most of the archetype-bug back-and-forth.

- Add `GET /api/version` returning git SHA + build time. One-time add; ends
  stale-vs-fresh ambiguity forever.
- (The `archetype_hook.*.hook_build` / `archetype_debug.*.build` breadcrumbs added
  during archetype debugging are a poor-man's stand-in — replace with the endpoint.)

## 4. Observability / logging

- Everything logs at `WARNING:root:` — no levels. Adopt real levels so INFO debug
  lines are filterable.
- UESS step logs (`🛹 [FB_STEP]`, `[OREB_STEP]`) flood past Railway's 500 logs/sec
  cap (tens of thousands dropped), making log-based debugging useless. **In progress
  separately.**
- "archetype" is overloaded: UESS *movement* archetype (cruise/sprint/burst) vs
  *coaching* archetype. Makes search ambiguous; consider renaming one.

## Payoff

Items 2–4 are small. Any one would have collapsed the archetype-bug debugging from
many deploy→play→inspect loops into one. Item 1 is larger but pays down the root
friction (size + swallowed errors).
