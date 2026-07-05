# SIP (Side Inbound Pass) — UESS Compliance Audit

**Verdict: LARGELY COMPLIANT — cleaner than BIP.** One real defect (entry ball teleport, HIGH) — the exact BIP-Task 3 fix SIP never received. Everything else is clean or shared-with-BIP MED/LOW. (2026-07-05, 4-dimension parallel trace.)

## Topline (human-scannable)
- **Clock (§5):** ✅ compliant. Both game + shot clocks pinned flat on all 3 steps (transition_bridge.py:1418-1420); shot-clock reset happens on the trigger turn, SIP pins the fresh value; no seam jumps.
- **Coord-source (§1):** ✅ SIP's own logic is clean — **better than BIP**. Only coord-consumer (force-foul defender) reads emitted `oDestinations`/`dDestinations`, and SIP gates all 10 → those == rendered coords. No shot/contest/steal geometry.
- **Player-coord (§8.1-8.3):** ✅ internal step seams clean; all-10 gate → destinations honored.
- **Ball-seam (§8.4):** ⚠️ **the one real hole** — entry loose-ball seeded from `player.coords` (BH body), not the rendered `final_ball_coords` → teleport on steal/dead-ball/in-flight prior states.

SIP = 3 steps (setup walk-in gate=all-10 / passer-hold 1s / inbound pass SF→PG); triggers = dead-ball turnover, steal, non-shooting foul.

## Findings (ranked)

| # | Sev | Dim | Finding | Location |
|---|---|---|---|---|
| 1 | **HIGH** | §8.4 | **Entry ball teleport (inv.4).** `ball_start_coord` = `prior_final_coords[BH]` (a `player.coords` body snapshot), not `prior_turn["final_ball_coords"]` (rendered ball rest). On STEAL (`final_ball_handler_id` = stealer, but ball may be loose/in-flight), dead-ball, or non-shooting foul, the two diverge → ball jumps to the BH's body at SIP entry. **BIP got this fix (BIP-Task 3, turn_manager.py:1131-1148); SIP never got parity.** `final_ball_coords` is already stamped on `prior_turn` (game_manager.py:803) and in scope at the call site. | transition_bridge.py:1350; turn_manager.py:686 |
| 2 | MED | §8.4 | **No `[UESS SEAM]` entry detector.** Every sibling (HCO skeleton_step_emitter.py:1151, DREB game_manager.py:1129, OREB turn_manager.py:4388, FLSS 2034) compares prior `final_ball_coords` vs emitted step-0 ball and logs teleports > `UESS_SEAM_TELEPORT_GRID_EPSILON`. SIP has none → finding #1 (or any regression) is silent. | turn_manager.py `setup_side_inbound` |
| 3 | MED | §1/§8.2 | **Step-0 seed indirection (shared w/ BIP, not worse).** Player seed + ball derive from `prior_final_coords` = `build_final_coords` = `player.coords` snapshot, not the emitted `animation_steps[-1].end.coords` directly. Render-sync only as good as `sync_lineup_coords_from_turn`'s schema choice for the (often legacy) foul/charge/turnover trigger turn. | turn_manager.py:533; transition_bridge.py:1360 |
| 4 | MED | §8.2/§8.3 | **`len >= 8` guard rejects before backfill → SIP→HCO teleport.** `_resolve_inbound_prior_seam` only backfills inside the `len(prior_fc) >= 8` branch; a <8 seed returns `{}, None` → `build_sip` returns `[]` → **SIP emits no `animation_steps`**. Then `sync_lineup_coords_from_turn`'s emitted-steps branch is skipped → `player.coords` never advance to setup → `final_coords` snapshots STALE prior positions, *while* the attached `oDestinations`/`position_snapshots` tell the FE the players ARE at setup → teleport at the SIP→HCO seam. Fix: gate `>= 1`, or apply the guard *after* backfill. Edge (rarely drops >2 players) but a real teleport, not just degradation. | turn_manager.py:534-547 |
| 5 | LOW | §1 | **Force-foul target `SITUATIONAL_SIP_RECEIVER_POS="SG"` ≠ animated receiver (PG).** SIP passes to `pg_id` (transition_bridge.py:1399); force-foul reads `oDestinations["SG"]` — a stationary scatter player who never touches the ball. Not a §1 divergence (SG's dest == SG's render), but the foul lands on a non-receiver + the "pass receiver" comment is wrong. Mirror of BIP L-4. | turn_manager.py:642; situational_logic.py:290 |
| 6 | LOW | §5 | **Per-step `end.time_elapsed` non-zero vs pinned zero-delta clock.** The pin overrides `clock` blocks but not sibling `time_elapsed` (step1=t, step2=1.0, step3=t). Harmless — turn-level `time_elapsed=0` is authoritative and the ledger keys off it; only a consumer summing per-step elapsed would over-burn ~2-6s. | transition_bridge.py:414/798/1116 |
| 7 | LOW | §1 | Force-foul helper fallbacks read raw `player.coords` / `HCO_STRING_SPOTS` — **dead code** (`dDestinations` always carries all 5 defenders). | phase_resolution.py:610/656 |

## Clean / wins (verified, no violation)
- **§5:** clock pin is real and definitive; both seams (trigger→SIP, SIP→HCO) continuous.
- **§1:** SIP force-foul geometry fully render-synced (all-10 gate → `dDestinations` == emitted end coords) — **strictly better than BIP's SF-only gate**. No shot/contest/steal/eligibility coord consumers.
- **§8.1:** internal step seams literal-wired (step N+1 start = step N end).
- **§8.3:** all-10 gate → every player reaches `setup_coords`; no non-gate freeze.
- **§8.4 exit + internal:** loose→SF-attach→hold→pass seams correct (inv.1-3); exit to HCO carried via `final_ball_coords` + covered by HCO's `[UESS SEAM]` detector.

## Work plan
- ✅ **SIP-Task 1 (HIGH, §8.4, finding #1) — DONE (2026-07-05).** `build_sip_animation_steps` now takes optional `ball_start_coord`; the SIP call site (`setup_side_inbound`) resolves it from `prior_turn["final_ball_coords"]`, fallback → `prior_final_coords[BH]` → SF. BIP-Task 3 parity. Verified: step-0 ball seeds from the rendered rest, not the BH body; fallback intact. Regression-clean.
- ✅ **SIP-Task 2 (MED, §8.4, finding #2) — DONE.** `[UESS SEAM]` entry teleport detector added in `setup_side_inbound` (mirrors OREB-Task 3); detection-only, behavior-neutral.
- ✅ **SIP-Task 3 (MED, §8.2, finding #4) — DONE.** `_resolve_inbound_prior_seam` gate lowered `>= 8` → `>= 1` so backfill rescues sparse seeds instead of SIP emitting no steps (SIP→HCO teleport). Shared with BIP inbound; regression-clean.
- ⬜ **SIP-Task 4 (LOW, §1, finding #5):** `SG`→`PG` force-foul target + misnomer comment. Not yet done.
- **Deferred/shared (not SIP-specific):** finding #3 legacy-seam indirection (shared with BIP; UESS-migration-wide), finding #6 per-step `time_elapsed` cosmetic, finding #7 dead-code fallback.

## Cross-turn note
Findings #1 and #3 are the same root as the coord-consumer work: SIP reads `player.coords` where it should read the emitted/rendered coord. The **ball** (#1) is the acute, fixable case; the player seed (#3) is the shared UESS-migration indirection tracked across BIP too.
