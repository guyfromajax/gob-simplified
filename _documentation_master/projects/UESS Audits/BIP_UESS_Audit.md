# BIP ↔ UESS Compliance Audit

**Date:** 2026-07-05 · **Scope:** BIP (Ball In Play / BASELINE_INBOUND — inbound + bring-up after a made basket) · **Method:** read-only trace, 4 parallel audits (single-coord/pressure, clock/§5, ball-seam, player-coord) · **Audit only — no code changed.** · Turn #4 of the 11-turn UESS sweep (after HCO, Final Turn, OREB, DREB).

---

## ⭐ TL;DR (human topline — read this first)

**BIP's coordinates and ball are clean — its clock is not.** The ball chain (made-basket → inbounder pickup → SF→PG inbound pass → bring-up), the player coords (no cross-court teleport on the possession flip), and the single-coord-source (no shot; force-foul reads the rendered coords) are all solid. **But BIP lets the game clock run during what is a dead-ball inbound**, while the authoritative clock only burns a 2s runoff — so the emitted animation and the counted `time_elapsed` diverge, and **the visible clock jumps backward ~4s at every BIP→HCO seam** (made basket with >60s left).

| Symptom | Root cause | Verdict |
|---|---|---|
| Clock jumps **backward** ~4s after a made basket (>60s left) | BIP emitter pins only the **shot** clock; the **game** clock burns the full ~4–8s walk-up+hold+pass in the emitted steps, but `time_elapsed` = the 2s runoff constant → next HCO turn starts ~4s *higher* than BIP's animation ended | ❌ **HIGH** |
| A player occasionally missing/frozen through a whole inbound | Prior-seam guard accepts `len(final_coords) >= 8` → a <10 BIP chain if the prior turn dropped a player (coords=None) | ⚠️ **MED** |
| Ball teleport on the inbound | **None** — made-basket ball rests loose at the rim sweet-spot; SF walks over and picks it up (seated-at-ball) | ✅ |
| Shot decided from wrong coords (the OREB-MED-1 bug) | **Not present** — BIP resolves no shot; force-foul fouler reads the rendered `dDestinations` | ✅ |
| Cross-court teleport on the possession flip | **None** — step 0 seeds from the prior turn's real post-shot `final_coords`; players walk up continuously | ✅ |

### Compliance scorecard

| UESS contract | BIP status |
|---|---|
| Single coord source for logic (§1/§7) | ✅ Clean (no shot; force-foul reads render coords) |
| Ball step-seam continuity (§8.4 inv.1) | ✅ |
| Ball ownership within-step (§8.4 inv.2) | ✅ (inbound pass tweened within one step) |
| Ball capture continuity (§8.4 inv.3) | ✅ SF picks up loose ball seated-at-rim |
| Ball turn-seam continuity (§8.4 inv.4) | ✅ (MAKE→BIP, BIP→HCO) · ✅ **now derived from `final_ball_coords` (BIP-Task 3 / L-1)** |
| Player coord step-seam continuity (§8.1) | ✅ (no mid-emit writes) |
| All-10 coverage (§8.2) | ✅ **Fixed (BIP-Task 2, 2026-07-05)** — missing players backfilled from live coords |
| **Clock authority (§5)** | ✅ **Fixed (BIP-Task 1, 2026-07-05)** — game clock pinned during the dead-ball inbound (no backward seam) |
| Possession-flip orientation | ✅ clean (pass-through normalize, single frame) |
| Seam teleport detection (`[UESS SEAM]`) | ⚠️ not wired for the transition_bridge composer (BIP/SIP) |

### Which prior fixes carry over
**None directly** — BIP is built by the `transition_bridge` composer (`build_bip_animation_steps`), not the skeleton/OREB/DREB emitters. The `final_ball_coords` snapshot (HCO Task 3b) **does** apply. The `[UESS SEAM]` detector is **not** wired for the composer. **SIP is BIP's mirror** and pins **both** clocks (`build_sip_animation_steps`) — that's the fix precedent for the clock bug.

### Fix status (2026-07-05, uncommitted; not yet prototype-tested)
1. ✅ **HIGH-1** (BIP-Task 1) — game clock pinned across the BIP inbound (mirrors SIP); no backward clock snap at BIP→HCO; no negative emitted clock. Verified 300-frozen vs 295.6-burned. (Residual: 2s instant drop for made-FG>60s — LOW, deferred.)
2. ✅ **MED-1 (BIP-Task 2)** — prior-seam coverage now backfills missing players from live coords (reuses HCO Task-4 helper). Verified 9→10.
3. ✅ **LOW (BIP-Task 3)** — ball seeded from `prior.final_ball_coords` (MSSS fallback) so the MAKE→BIP seam is derived (L-1, supersedes the need for a `[UESS SEAM]` detector — the seam is now continuous by construction); fixed the stale "2-step" BIP docstring (L-5) and the force-foul `receiver_pos` misnomer comment (L-4). Deferred: L-6 dual clock-rule paths (latent, not colliding); the SIP "2-step" comment (SIP-scope, verified in the SIP audit).

### What's genuinely fine (don't touch)
Made-basket→inbounder ball hand-off (loose-at-rim pickup) · inbound pass within-step · step chaining all-10 · possession-flip orientation · BIP→HCO seam · shot-clock reset (fresh 30) · runoff clamping (never negative game_state) · ≤60s / FT-make clock-dead rule · the force-foul reading the rendered coords.

---
---

## Full audit detail (agent-facing)

### Method
Four read-only traces against the UESS contract ([UESS_System.md](../../05_UESS_System/UESS_System.md)). Primary files: [`transition_bridge.py`](../../../BackEnd/utils/transition_bridge.py) (`build_bip_animation_steps` ~L1125, `build_walk_up_step` ~L224, `build_pass_step` ~L692, `build_sip_animation_steps`), [`turn_manager.py`](../../../BackEnd/models/turn_manager.py) (`setup_baseline_inbound` ~L810), [`game_manager.py`](../../../BackEnd/models/game_manager.py) (`_resolve_post_make_bip_clock_runoff` ~L133, MAKE→BIP ~L1962-2084, force-foul ~L1304), [`eoq_clock_progression.py`](../../../BackEnd/utils/eoq_clock_progression.py). Docs: [`BIP_System.md`](../../06_Gameplay_Systems/BIP_System.md), `Shot_Clock_System.md`.

BIP is a **4-step** composer (SF→rim, SF rim→inbound spot, passer hold, SF→PG inbound pass); some call-site docstrings still say "2-step" (stale — see LOW).

---

### HIGH-1 — BIP runs the game clock during the dead-ball inbound; `time_elapsed` is an independent constant (§5)

A made basket → inbound is a **dead ball** — the game clock should be pinned during the inbound animation, with only a small runoff (2s for made FG >60s; 0 otherwise) counted. BIP does the opposite in the emitted steps.

- **`time_elapsed` is the runoff constant, written straight to game_state** ([`game_manager.py:2074-2077`](../../../BackEnd/models/game_manager.py#L2074)): `time_elapsed = _resolve_post_make_bip_clock_runoff(...)` = 0 or 2, via the `source="bypass:BIP"` path (not `update_clock_and_possession`).
- **But the emitter pins only the SHOT clock; the GAME clock burns naturally** ([`transition_bridge.py:1275-1284`](../../../BackEnd/utils/transition_bridge.py#L1275)): each step end decrements the game clock by its own `t` (walk-ups + the 1s passer hold + pass), so the emitted steps burn `T_total` ≈ **4–8s**, while `time_elapsed` = 2 (or 0).
- **H2 — Non-monotonic BIP→HCO seam (clock jumps backward).** The BIP animation ends at `clock_r − T_total` (~294 from a 300 start), but `game_state.time_remaining = clock_r − runoff` (298) seeds the next HCO turn's `clock_remaining_at_start` ([`turn_manager.py:1087`](../../../BackEnd/models/turn_manager.py#L1087)). Since `runoff (0/2) < T_total (~6)`, **HCO opens ~4s higher than BIP's animation ended → the visible clock snaps backward** at every made-basket→HCO boundary (>60s). §5 monotonicity violation.
- **H3 — Reconciliation is blind.** The clock ledger derives `game_elapsed = clock_start − clock_end` from the **contract** (= runoff), not the emitted steps ([`turn_manager.py:363`](../../../BackEnd/models/turn_manager.py#L363)); `_derive_elapsed_from_clock_event_ledger` sums back the runoff, so observe-mode reconciliation always reports "within tolerance." The ~T_total animation burn is never audited.
- **M1 (folded in) — Negative emitted clock at low game clock.** BIP is created for a made FG down to `time_remaining > 0` (guard at `game_manager.py:1984` only skips at `==0`); with `clock_r ≈ 3` and `T_total ≈ 6`, the last emitted step's `clock_remaining` goes negative (e.g. `3 → −3`). Contract `clock_end` stays ≥0 (clamped), so only the animation shows negative.
- **Severity: HIGH** — user-visible backward clock jump on every made basket >60s; `time_elapsed` is a decoupled constant, not derived from the emitted steps.
- **Fix direction (SIP precedent + docs):** pin the BIP **game** clock in `build_bip_animation_steps` (SIP's `build_sip_animation_steps` pins **both** clocks — `Shot_Clock_System.md`/`BIP_System.md`: BIP is clock-dead through the inbound, clock starts "after the receiver has the ball"). Make the emitted steps' total game-burn == the runoff (pass the runoff into the emitter; burn it on the post-inbound step, or pin fully for the 0 case), so `time_elapsed` derives from the steps and the BIP→HCO clock is continuous. Add a game_clock ledger event for the runoff.

---

### MED-1 — Prior-seam guard admits a <10-player BIP chain (§8.1/§8.3)

- The step-0 seed guard accepts 8 ([`turn_manager.py:534`](../../../BackEnd/models/turn_manager.py#L534)): `if isinstance(prior_fc, dict) and len(prior_fc) >= 8:`. `build_final_coords` skips any player whose `coords` is `None`/invalid (unlike `sync_lineup_coords_from_turn`, which fallback-fills `{50,25}`), so a prior turn can hand BIP an 8–9-entry map. BIP then emits a 4-step chain that never mentions the dropped player(s) → the FE has no BIP position for them (invisible/frozen through the whole inbound).
- **Repro:** a MADE turn ends with a player carrying `coords=None` → `final_coords` has 9 → BIP builds a 9-player chain → that player is stale through the inbound.
- **Severity: MED** (real all-10 gap; requires an abnormal upstream drop).
- **Fix direction:** backfill missing active players from live `player.coords` (mirror the HCO Task-4 backfill), or require all-10 and log when short.

---

### LOW findings

| ID | Finding | Location |
|---|---|---|
| L-1 | Ball step-1 is seeded from a **fixed `MADE_SHOT_SWEET_SPOT_*` constant**, not `prior_turn.final_ball_coords`. Continuous today (every make variant settles at MSSS), but a future make/And-1/made-FT variant resting elsewhere would teleport the ball at MAKE→BIP. And the composer has no `[UESS SEAM]` detector. | `transition_bridge.py:1110-1114, 1214` |
| L-2 | Non-gate movers (SG/PF/C + 5 defenders) routinely finish BIP short of their setup: step 1 gates on **SF only** (rim-pickup mechanic), so cumulative gated T can be shorter than their travel. §9.5-legal (interrupted coords carry to HCO correctly), but BIP `final_coords ≠ setup_coords` for these players — any downstream code assuming they reached `o_dest` is wrong. | `transition_bridge.py:1207, 749` |
| L-3 | Asymmetric receiver guard: checks `pg_id in setup_coords` but not `pg_id in prior_final_coords`; if PG is missing from the prior seam, `build_pass_step` raises `ValueError` → caught → **no `animation_steps`**, BIP silently degrades to the legacy payload (UESS-off). Normally moot (prior=10). | `transition_bridge.py:1175, 720-722`; `turn_manager.py:1131` |
| L-4 | **Force-foul target misnomer:** the situational force-foul targets `SITUATIONAL_BIP_RECEIVER_POS = "SG"` (a scatter player), but the animated inbound receiver is PG; the `receiver_pos` "pass receiver" comment is inaccurate. Not a §1 divergence (SG's coords still match the render) — doc/naming only. | `turn_manager.py:1004`; `constants:241` |
| L-5 | Stale docstrings call BIP a "2-step" turn; it's a 4-step composer. Doc drift. | `turn_manager.py:654`; various call sites |
| L-6 | Dual clock-rule paths for the same turn type: `_is_no_impact_turn` treats `BASELINE_INBOUND` as always 0-elapsed, while the bypass path assigns 2s. Latent inconsistency (they don't collide today because BIP uses `source="bypass:BIP"`). | `turn_manager.py:5026-5032`; `game_manager.py:2074-2077` |

---

### Verified COMPLIANT (coverage — do not "fix")

| Contract / boundary | Evidence | Result |
|---|---|---|
| **No shot / steal / pressure** resolved in BIP (grep clean) | `setup_baseline_inbound`, `build_bip_animation_steps`; inbound pass always completes (`build_pass_step`) | ✅ no OREB-MED-1 analog |
| Force-foul fouler reads the rendered `dDestinations` (same source as `setup_coords` via `_inbound_setup_coords_from_dest`) | `game_manager.py:1327-1331`; `turn_manager.py:504-522` | ✅ §1 |
| MAKE→BIP ball hand-off: loose @ MSSS (make-hold) → BIP step-1 loose @ same MSSS → SF picks up seated-at-rim | `skeleton_step_emitter.py:2457-2464`; `transition_bridge.py:1194, 1214, 411-413` | ✅ §8.4 inv.3/4 |
| Inbound pass SF→PG within one step (Attached→InFlight→Attached, tweened) | `transition_bridge.py:751-756` | ✅ inv.2 |
| Step continuity step1→2→3→4, all 10 | `transition_bridge.py:1217, 1247, 1263` | ✅ inv.1 / §8.1 |
| No mid-emit `player.coords` write | grep clean; only write is end-of-turn sync | ✅ §8.1 |
| Step-0 seeded from prior MADE `final_coords` (real post-shot positions) — no cross-court teleport on the flip | `turn_manager.py:533-535, 1082-1084`; `transition_bridge.py:1199` | ✅ |
| Possession-flip orientation single-frame (pass-through normalize; `is_away_offense` = new offense) | `shared.py:3474-3500`; `turn_manager.py:828, 878` | ✅ |
| BIP→HCO seam: HCO step-0 == BIP `final_coords` (all 10, interrupted spots carried) | `game_manager.py:786, 798`; `skeleton_step_emitter.py:515` | ✅ §8.2 |
| **Shot-clock reset (fresh 30)** on MAKE→BIP (Rule 1 on the MAKE possession flip; shot clock pinned across BIP, opens 30 at HCO) | `turn_manager.py:5077-5078, 5202-5203`; `transition_bridge.py:1279-1282` | ✅ §5 |
| Runoff clamped ≥0 game_state; ≤60s / FT-make → clock-dead (0); late/EOQ runoff bounded, no double-count | `game_manager.py:144-153, 161, 169`; `eoq_clock_progression.py:344-346` | ✅ |
| §7 snapshot: BIP builds + attaches `bip_inbound_setup` snapshot from the same `o_dest`/`d_dest` (further along than audit-only) | `turn_manager.py:1047-1061` | ✅ |

---

### Root-cause map to symptoms
- **Backward clock jump after a made basket** → **HIGH-1** (game clock runs during the dead-ball inbound; `time_elapsed` = decoupled runoff constant).
- **Occasional missing/frozen player through the inbound** → **MED-1** (`len>=8` guard).
- **No ball teleport / no wrong-coord logic** → clean ball chain + no shot.

### Work Plan — BIP → 100% UESS alignment

**BIP-Task 1 — Pin the BIP game clock (fixes HIGH-1, §5) — ✅ DONE & VERIFIED (2026-07-05).**
`build_bip_animation_steps` ([`transition_bridge.py:1275-1296`](../../../BackEnd/utils/transition_bridge.py#L1275)) now pins **both** clocks across all 4 steps (mirrors `build_sip_animation_steps`), instead of pinning only the shot clock and letting the game clock burn ~4–8s. The emitted steps freeze the game clock at the turn-start value during the dead-ball inbound; the authoritative `game_state` still burns only the runoff (0/2s) at the turn level (`game_manager` `bypass:BIP`), so the next turn ticks **down** from there.
**Verification (direct emitter call, before/after):** per-step game clock went from `300 → 297.6 → 297.1 → 296.1 → 295.6` (burned ~4.4s → HCO opened at ~298 = **backward jump**) to `300 → 300 → 300 → 300` (**frozen** → HCO opens at 298 = ticks down, no jump; no negative emitted clock at low clock). Regression: the BIP-clock test (`test_game_manager_post_make_bip_clock.py`) + transition-continuity pass; zero new failures (the 7 BIP/transition-pipeline test failures are **pre-existing harness issues** — `KeyError: PG not in offense lineup … EMPTY` in mongomock — identical with/without this change).
**Chosen approach vs alternative:** full-pin (like SIP) — lowest risk, touches only the emitted step clocks, not the authoritative contract. **Residual (LOW, deferred):** for a made FG >60s the 2s runoff appears as a 2s instant drop at the BIP→HCO seam (the clock resumes after receipt) rather than a smoothly-animated tick. A fully-continuous variant (thread the runoff into the emitter and burn it on the post-inbound step so `time_elapsed` == emitted burn) is a possible refinement if the 2s step reads poorly in the prototype; for runoff=0 (≤60s / FT makes / most of the game) it's already seamless.

**BIP-Task 2 — All-10 coverage guard (fixes MED-1, §8.2) — ✅ DONE & VERIFIED (2026-07-05).**
`_resolve_inbound_prior_seam` ([`turn_manager.py:534`](../../../BackEnd/models/turn_manager.py#L534)) now backfills any active player missing from `prior_final_coords` from live `player.coords` (reuses the HCO Task-4 `_backfill_missing_active_coords`; adds only, never overrides) before returning the seam coords for the BIP/SIP chain. **Verification (direct call):** a prior turn with `final_coords` missing a player → returned coords **9 → 10** (the dropped player backfilled from live coords). Compiles; no new failures.

**BIP-Task 3 — LOW cleanups — ✅ DONE (2026-07-05).**
- **L-1** — the loose-ball seed for a made-shot BIP now comes from `prior.final_ball_coords` (MSSS rim constant as fallback), so the MAKE→BIP seam is **derived from the prior turn's rendered rest**, not a fixed constant ([`turn_manager.py:1110`](../../../BackEnd/models/turn_manager.py#L1110)). This makes the seam continuous **by construction** — so a `[UESS SEAM]` detector on BIP would be dead code (it'd compare `final_ball_coords` against a step-0 ball seeded *from* `final_ball_coords`); skipped deliberately. Behavior-neutral today (all make variants rest at MSSS == `final_ball_coords`); robust to future variants.
- **L-5** — corrected the stale "BIP is a 2-step turn" docstring to the actual 4-step rim-pickup ([`turn_manager.py:1076`](../../../BackEnd/models/turn_manager.py#L1076)).
- **L-4** — corrected the force-foul `receiver_pos` misnomer comment (it's the foul TARGET "SG", not the inbound receiver PG) ([`turn_manager.py:1017`](../../../BackEnd/models/turn_manager.py#L1017)).
- **Deferred:** L-6 (dual clock-rule paths — latent, not colliding today); the SIP "2-step" comment (SIP-scope — will verify SIP's real step count in the SIP audit #5).

### Appendix — key line index
- Clock: `game_manager.py:133-161, 1984, 2072-2084`; `transition_bridge.py:1099-1101, 1275-1284`, SIP `1312-1314`; `turn_manager.py:257-272, 351-386, 1087, 5026-5032, 5077-5078, 5202-5203`; `eoq_clock_progression.py:344-346`.
- Ball seams: `transition_bridge.py:411-413, 692-756, 1110-1114, 1182-1219, 1247-1273`; `skeleton_step_emitter.py:2457-2464, 1132, 1270`.
- Player coords: `turn_manager.py:504-522, 533-535, 810-1135`; `transition_bridge.py:1175, 1199, 1207, 1217-1263, 749`; `game_manager.py:786-805, 1962-2000`.
- Single-coord/force-foul: `turn_manager.py:1004, 1006, 1047-1061`; `game_manager.py:1304-1362`; `phase_resolution.py:627-663`.
