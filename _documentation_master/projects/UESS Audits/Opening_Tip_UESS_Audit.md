# Opening Tip — UESS Compliance Audit

**Verdict: benign, not-yet-migrated legacy turn.** Not a §1 problem (backend is authoritative, FE is a pure renderer); the game's first seam into HCO is clean (no teleport); game-start clock is correct. **One worthwhile fix** (a dead `time_elapsed` stamp causing FE clock jitter + log noise) + a few LOW/optional items. Migration to the schema is **backlog item 10**, a cleanup — not a correctness fix. (2026-07-05, 3 focused traces.)

> **Unmigrated:** Opening Tip (+ Timeout) are the only turns that emit NO schema `animation_steps`. `execute_opening_tip` (opening_tip.py:67) returns a legacy result (`animations[]` with non-vocab `TIP_JUMP`/`CONVERGE_ON_BALL`, `ball_landing_coords`, `ball_handler_id`, `winner`), rendered by the dedicated FE `openingTip.js`. Explicitly stamped `uess_ownership_contract applicable:false` (excluded from UESS validation).

## Topline
- **§1 / FE-logic:** ✅ **Clean** — `openingTip.js` is a pure renderer (no RNG, no decisions); backend owns tip winner, landing, possession, BH, timing.
- **Exit seam → HCO:** ✅ **Clean** — no teleport at the game's first possession (BH = tip winner, players + ball at tip-end positions carry via `player.coords`).
- **§5 clock:** ✅ **Correct** — game clock inits to full period (480/240 OT), tip burns 0, shot clock fresh 30, OT lengths correct. But one advisory-field bug (below).

## Findings (ranked)

| # | Sev | Dim | Finding | Location |
|---|---|---|---|---|
| 1 | **MED** | §5 | **Dead `time_elapsed` stamp → FE clock jitter + log noise.** `opening_tip.py:202` stamps `time_elapsed = randint(1,5)+1` (2-6s) with a "tip burns 2-6s" comment, but the pipeline **discards it** (the tip correctly burns 0). Fallout: (a) `real_time_elapsed_ms` is computed from the un-zeroed value *before* it's zeroed (turn_manager.py:217 vs :296) → encodes 2-6s of implied tick; if the FE interpolates clock motion from it, the clock visibly ticks down 2-6s during the tip then snaps back to 8:00. (b) Every tip logs a spurious `[CLOCK CONTRACT] backend reconciliation fail` (legacy 2-6s vs ledger 0) — noise that can mask real failures. **Removing the dead stamp (set 0) resolves all three.** | opening_tip.py:201-202; turn_manager.py:217 |
| 2 | LOW | seam | `final_ball_coords` is None for OT (no `animation_steps`) → the HCO entry `[UESS SEAM]` detector is silently skipped at the game's first seam. **Observability only** — no teleport (owner coord ≡ ball rest). | animation_step_helpers.py:120 |
| 3 | LOW | logic | **`execute_opening_tip` runs twice** — `run_simulation`→`setup_opening_tip` executes + discards the turn, then `simulate_quarter` re-runs + appends the authoritative one. Wasted work; the two RNG draws can pick different winners (harmless — the appended one wins). | main.py:1193 vs :690 |
| 4 | LOW | §1/possession | **Rare wrong-team BH.** The winner-match loop iterates home-appended-first (opening_tip.py:128-162) and picks the first player whose `end == ball_landing_coords`; a home (losing) player landing on the exact integer coord would be picked as BH even when away wins → wrong-possession start. Extremely unlikely (integer-grid collision). | opening_tip.py:209-216 |
| 5 | LOW | §1 smell | `openingTip.js:findTipWinner` re-derives the winner by coord-matching instead of reading the authoritative `ball_handler_id` — brittle (wrong sprite if a non-winner lands on the coord), currently correct via identical iteration order. | openingTip.js:306-321 |

## Clean (verified)
- **Exit seam:** BH continuity (`final_ball_handler_id` = tip winner via top-level `ball_handler_id`), player continuity (`final_coords` from synced `player.coords`, all 10 at tip-end), ball continuity (winner coord ≡ landing spot) → first HCO possession seeds cleanly.
- **§5:** period clock init (480 / 240 OT), 0 tip burn, fresh 30 shot clock, OT lengths — all correct.
- **§1:** FE pure renderer; all decisions backend-owned.

## Work plan
- **OT-Task 1 (MED #1):** remove the dead `time_elapsed` 2-6s stamp (set 0) in `execute_opening_tip` — fixes the inflated `real_time_elapsed_ms` (FE clock jitter risk) + the per-tip reconciliation warning. Trivial, low-risk, **sim-verifiable** (tip fires at game start). The one fix worth doing.
- **Optional / LOW (not urgent):** #5 have `openingTip.js` consume `ball_handler_id` directly; #4 make the BH resolver read the winner id, not coord-match; #3 dedupe the double tip execution; #2 stamp `final_ball_coords` for OT (observability).
- **Migration to schema (backlog item 10):** build `opening_tip_step_emitter.py` + route the FE through `playTurn()`. Cleanup, not correctness — deferred, out of sweep scope.

## Cross-turn note
Findings #3 (double-exec + RNG winner disagreement) and #4 (coord-match BH) are **latent correctness** edges worth hardening someday, but neither causes a UESS seam/teleport. The only user-visible risk is #1 (clock jitter during the tip).
