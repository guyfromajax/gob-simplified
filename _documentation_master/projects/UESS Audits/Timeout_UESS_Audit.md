# Timeout — UESS Compliance Audit

**Verdict: benign non-animated state event — but the sweep's ONE genuine §1 (FE-logic) violation.** Timeout has zero coord/animation content (it doesn't need schema migration); the resume seam is clean for players; §5 is correct (0 burn, shot clock *preserved*). The real finding: the **FE owns the "when can a timeout fire" rule**, un-mirrored backend-side. (2026-07-05, 3 focused traces.)

> **Unmigrated (benign):** Timeout emits NO schema `animation_steps`. `setup_timeout_turn` (turn_manager.py:4136) returns a plain result dict (result_type "TIMEOUT", `time_elapsed:0`, timeout counts, resume state); the FE renders a modal + navigates to the lineup screen. `uess_ownership_contract applicable:false`. It's inherently a non-animated dead-ball event — the schema doesn't apply, and it does NOT need migration.

## Topline
- **§1 / FE-logic:** ⚠️ **HIGH — the FE decides timeout eligibility** (a game rule), not just rendering.
- **§5 clock:** ✅ Correct — 0 game-clock burn, shot clock **PRESERVED** on resume (not reset — `_should_reset_shot_clock` guards `rt != "TIMEOUT"`), count gated. One MED stale-flag edge.
- **Resume seam:** ✅ Clean for players — all 10 (incl. subbed-in) seed at the triangle entrance + animate into the inbound setup (all-10 gate); no player teleport. One MED ball-origin edge.

## Findings (ranked)

| # | Sev | Dim | Finding | Location |
|---|---|---|---|---|
| 1 | **HIGH** | §1 | **FE owns timeout eligibility (game rule on the FE).** `checkTimeoutEligibility` allows a queued timeout only on BIP/SIP, or HCO-after-DREB with the user on offense (DREB/BLOCK excluded). The backend `call_timeout` validates only the **count**, not the current turn type → the "when may a timeout fire" rule lives solely in JS and is un-mirrored backend-side. Genuine FE logic, not pure rendering. | timeoutButtonManager.js:346-408; AnimationRouter.js:696; game_manager.py:291 |
| 2 | MED | §5 | **Stale-flag quarter-break clock skip.** At a quarter boundary, if `resume_from_timeout=True` but `timeout_next_play_type` is None (stale/corrupt), the full-period reset (main.py:481) is skipped, the flag flips False (504-507), and the fall-through to quarter init does NOT re-reset → quarter starts with a wrong (possibly 0:00) clock. Edge/corruption path. | main.py:481 vs 504-507 |
| 3 | MED | seam | **Stale `timeout_seam_ball_handler_id`.** Captured by scanning back for the last non-TIMEOUT `final_ball_handler_id`, independent of `timeout_offense_team_id`. On a possession-flip-before-timeout, the BH now belongs to the *defending* team → the resume ball animates from an opponent's coord. On a subbed-out BH → degrades gracefully to the inbounder. Animated (not hard-teleport), semantically wrong. | game_manager.py:446-451 |
| 4 | LOW | seam | FREE_THROW resume skips the triangle seam (uses the older `BENCH_ENTRY` fallback) — inconsistent with SIP/BIP but still renders an entrance. | main.py:548-558 |
| 5 | LOW | seam | Sparse triangle map if a rebuilt lineup slot is None (<10 coords) — rare edge, adjacent to SIP #4. | transition_bridge.py:1338 |
| 6 | LOW | §5 | Count decrement lives in `setup_timeout_turn`, not `call_timeout` (fragile split; `>0` guard still prevents negatives); `can_call_timeout` defaults a missing `timeouts` attr to 4. | turn_manager.py:4192/4231 |

## Clean (verified)
- **Migration benign:** zero coord/animation content — doesn't need the schema.
- **§1 count + can-call:** backend-authoritative (FE button-disable is a benign mirror; DOM-scraped clock/score is reconciled backend-side with skew logging).
- **§5:** game clock 0-burn; **shot clock preserved on resume** (never writes 30/24; `_should_reset_shot_clock` excludes TIMEOUT); count gated + decremented; clock seam continuous; quarter-break vs timeout separated (except the #2 edge).
- **Resume seam (players):** all 10 incl. subbed-in seed at triangle → animate into setup (all-10 gate); `prior_turn` is None on resume so the stale `final_ball_coords` path is correctly inert; no double-animation.

## Work plan
- **TO-Task 1 (HIGH §1) — needs a decision.** Mirror the timeout-eligibility rule in the backend: `call_timeout` (or `can_call_timeout`) should validate the current turn type (reject a timeout the rule disallows), making the rule backend-authoritative — the FE check becomes UX convenience, not the authority. **Localized backend addition, but it changes a gameplay rule's authority** (FE and backend rules must agree), so it warrants a conscious call, not a blind ship.
- **TO-Task 2 (MED §5):** on the stale-flag downgrade path (main.py:504-507), re-run the full-period clock reset before falling through to quarter init. Edge/corruption hardening — safe.
- **TO-Task 3 (MED seam):** validate `timeout_seam_ball_handler_id` against `timeout_offense_team_id` (use the stored offense's BH, not the last-turn scan) so the resume ball origin is on the correct team. Cosmetic.
- **LOW (#4/#5/#6):** documented; optional consistency/robustness.

## Cross-turn note
Timeout is the only turn in the sweep with a genuine §1 (FE-logic) violation (#1). Its coord/clock/ball handling is otherwise correct — as expected for a non-animated state event. Migration to the schema is unnecessary (no animation content), correcting the "backlog item" framing for this specific turn.
