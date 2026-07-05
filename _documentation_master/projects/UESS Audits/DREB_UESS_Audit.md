# DREB ↔ UESS Compliance Audit

**Date:** 2026-07-05 · **Scope:** DREB (defensive rebound → secure → possession flip; OTB-foul branch) · **Method:** read-only trace, 4 parallel audits (single-coord/OTB, clock/§5, ball-seam, player-coord) · **Audit only — no code changed.** · Turn #3 of the 11-turn UESS sweep (after HCO, Final Turn, OREB).

---

## ⭐ TL;DR (human topline — read this first)

**DREB is the cleanest turn type audited so far.** It's a single-step capture: a defensive rebounder sprints to the loose ball (from the prior miss), secures it, and possession flips to a transition (Fast Break / HCO / BIP). No shot is resolved, so the whole class of HCO/Final-Turn/OREB coord defects doesn't exist here. Ball chain fully continuous, capture seated-at-ball, coords all-10 and seam-continuous, clock schema-derived. **One MED issue** — a ~1s shot-clock shortfall on the chained `PUTBACK_MISS → DREB` path. Everything else is LOW/cosmetic.

| Symptom | Root cause | Verdict |
|---|---|---|
| New offense's shot clock ~1s short after a chained putback | On `PUTBACK_MISS → DREB`, the DREB's `possession_flips` is cleared (to avoid a double-flip) — which **also disables its own shot-clock reset**, so the ensuing possession starts at ~29 instead of 30 (the primary `MISS → DREB` path gives 30) | ⚠️ **MED** |
| Ball teleport on the rebound | **None** — capture is seated-at-ball; all cross-turn seams continuous | ✅ |
| Shot resolved from wrong coords (the OREB-MED-1 bug) | **Not present** — DREB resolves no shot; the OTB foul reads the *same* live `player.coords` the emitter renders | ✅ |
| Clock on the primary rebound | Schema-derived, monotonic, possession-flip reset fires (fresh 30) | ✅ |

### Compliance scorecard

| UESS contract | DREB status |
|---|---|
| Single coord source for logic (§1/§7) | ✅ Clean (no shot; OTB reads the render's start-frame coords) |
| Ball step-seam continuity (§8.4 inv.1) | ✅ (single step — no intra-turn seam) |
| Ball ownership within-step (§8.4 inv.2) | ✅ (loose→attached within one step) |
| Ball **capture** continuity (§8.4 inv.3) | ✅ **seated-at-ball** |
| Ball turn-seam continuity (§8.4 inv.4) | ✅ (MISS→DREB, DREB→FB/HCO/inbound all continuous) |
| Player coord step-seam continuity (§8.1) | ✅ (no mid-emit writes) |
| All-10 coverage (§8.2) | ✅ (LOW `None`-slot edge, self-healing at next-turn seam) |
| Clock authority (§5, schema-burn) | ✅ schema-derived · ✅ **MED-1 chained-path reset fixed (DREB-Task 1)** |
| Possession-flip orientation | ✅ clean (pass-through normalize, ref-only swap) |
| Seam teleport detection (`[UESS SEAM]`) | ✅ **wired for DREB (DREB-Task 2)** + outbound seam covered by next turn's emitter |

### Which prior fixes carry over
**None directly** (DREB has its own emitter `dreb_step_emitter.py` + spawn `_build_dreb_turn_from_miss`). The `final_ball_coords` snapshot (HCO Task 3b) **does** apply. The `[UESS SEAM]` detector is **not** wired into DREB's own emit path (though the DREB→next seam is caught by the *next* turn's emitter). MED-1 is a cousin of OREB-Task 2 (both are shot-clock-reset gaps on chained rebounds), but a distinct code path.

### Fix status (2026-07-05, uncommitted; not yet prototype-tested)
1. ✅ **MED-1** (DREB-Task 1) — chained `PUTBACK_MISS → DREB` now resets the shot clock (Rule 1b, `rt=="DREB"`). Verified 19 → 30; primary path + OTB foul unchanged.
2. ✅ **LOW cleanup (DREB-Task 2)** — fixed the attemptor-archetype doc drift (L-3: `cruise`→`standard`, matching the code default) + wired `[UESS SEAM]` detection into `_build_dreb_turn_from_miss`. Deferred (rationale below): L-1 OTB ball-owner label, L-2 `None`-slot, L-5 unclamped clock, L-4/L-6 cosmetic.

### What's genuinely fine (don't touch)
Seated-at-ball capture · MISS→DREB / DREB→FB / DREB→HCO / DREB(OTB)→inbound seams · single-step structure · all-10 seed + carry · possession-flip orientation · schema-burn `time_elapsed` · primary-path shot-clock reset · OTB foul possession/clock handling.

---
---

## Full audit detail (agent-facing)

### Method
Four read-only traces against the UESS contract ([UESS_System.md](../../05_UESS_System/UESS_System.md)). Primary files: [`dreb_step_emitter.py`](../../../BackEnd/engine/dreb_step_emitter.py) (`build_dreb_animation_steps` ~L81), [`game_manager.py`](../../../BackEnd/models/game_manager.py) (`_build_dreb_turn_from_miss` ~L922), [`shared.py`](../../../BackEnd/utils/shared.py) (`resolve_over_the_back_foul` ~L871), [`animation_step_helpers.py`](../../../BackEnd/utils/animation_step_helpers.py), [`turn_manager.py`](../../../BackEnd/models/turn_manager.py) (`_should_reset_shot_clock` ~L5068).

---

### MED-1 — Chained `PUTBACK_MISS → DREB` leaves the new offense ~1s short on the shot clock (§5)

The DREB analog of OREB-Task 2 (a shot-clock-reset gap on a chained rebound), but a distinct path.

- On the chained path, `_build_dreb_turn_from_miss` clears `dreb_turn["possession_flips"] = False` ([`game_manager.py:1465`](../../../BackEnd/models/game_manager.py#L1465)) to avoid a **double** possession flip (the parent `PUTBACK_MISS` OREB turn already flipped at `game_manager.py:1414-1418`). But clearing the flag also disables the DREB turn's own shot-clock reset: `_should_reset_shot_clock` Rule 1 needs `possession_flips` ([`turn_manager.py:5077`](../../../BackEnd/models/turn_manager.py#L5077)), and the DREB turn carries no `rebound_type=="OREB"`, so Rule 3 can't fire either.
- Result: the parent `PUTBACK_MISS` resets the shot clock **for the DREB** (DREB starts ~30); the DREB burns ~1s of sprint traversal and does **not** re-reset → the ensuing HCO/FB possession starts at **~29, not 30**.
- **Contrast the primary path** (`MISS → DREB`): the DREB keeps `possession_flips=True`, burns its time, then resets to `min(30, clock_end)` at the end (`turn_manager.py:5194-5195`), so the new offense gets a full **30**. The two paths are inconsistent.
- **Repro:** MISS → OREB → putback attempt → `PUTBACK_MISS` (`rebound_type="DREB"`) → DREB → HCO. Observe HCO `shot_clock_start` ≈ 29 instead of 30.
- **Severity: MED** — ~1s shortfall + path inconsistency; not negative/non-monotonic. Rare (chained-putback branch only).
- **Fix direction:** make a DREB turn reset the shot clock regardless of the double-flip guard — e.g. gate `_should_reset_shot_clock` on `current_turn == "DREB"` (a defensive rebound always renews the ensuing possession's clock). Redundant-but-harmless for the primary path (Rule 1 already fires there); fixes the chained path. Decouples "reset shot clock" from "flip possession."

---

### LOW findings

| ID | Finding | Location |
|---|---|---|
| L-1 | **OTB defensive-foul ball-owner label:** on a *defensive* OTB foul, possession is awarded to the offense, but the DREB step attaches the ball to the **defensive** rebounder. Ball *position* stays continuous (the inbound re-seeds from `final_ball_coords` — a dead-ball hand-off, not a tweened move), so no teleport; just an owner-label quirk. Matters only if a later turn reads `final_ball_handler_id` as "who inbounds." | `dreb_step_emitter.py:176`; `shared.py:918-921` |
| L-2 | **`None`-slot / missing-coord under-coverage** (same as OREB L-3): a `None` lineup slot or a player missing `x`/`y` is silently dropped from the DREB step's `end.coords` (<10). **Self-healing at the next-turn seam**: `sync_lineup_coords_from_turn` seeds all 10 with a `{50,25}` fallback *before* the end.coords override, so `player.coords` is never <10. Needs an abnormal state. | `game_manager.py:964-974`; `dreb_step_emitter.py:149-151` |
| L-3 | **Doc drift:** the emitter docstring says attemptors use `cut + cruise`, but `stamp_rebound_capture_player_motion` is called without `attemptor_archetype` → defaults to `standard`. Affects only the tween rate/label, not coords. Cosmetic. | `dreb_step_emitter.py:26, 158-171` |
| L-4 | **OTB banner-timing nuance:** the "Over The Back!" banner fires after sprites snap to end coords (rebounder @ bounce, opponents held), but the OTB proximity gate was evaluated on the step **start** frame (crash cluster). Not a phantom coord — the gated configuration *is* rendered (at t=0) — and a rebound-battle contact is arguably a start-frame event. Cosmetic. | `dreb_step_emitter.py:269-273`; `shared.py:892-904` |
| L-5 | **Unclamped emitted clock** (same as OREB L-7): `clock_remaining - t` / `shot_clock_remaining - t` with no `max(0,…)` in the emitted step — display could show negative on a low-clock/quarter-boundary DREB. The **authoritative** contract is re-derived from clamped `game_state`; master clock never negative. Cosmetic. | `dreb_step_emitter.py:194-197` |
| L-6 | Sub-second `time_elapsed` quantization (T 0.5–0.99s → 1) — consistent with OREB, minor rounding. | `game_manager.py:1053-1054` |
| INFO | DREB seeds step-0 from `player.coords` directly (single source) rather than OREB's `prior_turn.final_coords`-then-fallback. Functionally equivalent (`build_final_coords` *is* a `player.coords` snapshot at the same sync point). | `game_manager.py:963-974` |
| OPT | `[UESS SEAM]` detection is not wired into DREB's own emit path (`_build_dreb_turn_from_miss`), though the DREB→next seam is caught by the next turn's emitter. Wire for sweep consistency (detection-only). | `game_manager.py:922`; `dreb_step_emitter.py` |

---

### Verified COMPLIANT (coverage — do not "fix")

| Contract / boundary | Evidence | Result |
|---|---|---|
| **No shot / contest / block** in DREB (grep clean) | `dreb_step_emitter.py`; `_build_dreb_turn_from_miss` calls only `resolve_over_the_back_foul` + (on OTB) `resolve_non_shooting_foul` | ✅ no OREB-MED-1 analog |
| Rebounder pre-stamped upstream, scored vs the same `bounce_spot` the emitter renders | `shot_manager.py:2035-2050`; `game_manager.py:941, 986` | ✅ single source |
| OTB foul reads the render's start-frame `player.coords` (shared source) | `shared.py:892-904`; `game_manager.py:963-974` | ✅ §1 |
| Capture seated-at-ball (loose @ bounce; rebounder is gate player, full tween to bounce, ownership flips at end) | `dreb_step_emitter.py:127-132, 173-176`; `animation_step_helpers.py:193-202, 282-297` | ✅ §8.4 inv.3 |
| MISS→DREB turn seam (loose@bounce → loose@bounce, same `ball_bounce_x/y`) | `skeleton_step_emitter.py:2336, 3101-3108`; `game_manager.py:1029`; `dreb_step_emitter.py:173-175` | ✅ inv.4 |
| DREB→next (FB/HCO/inbound) seam: next step-0 ball == DREB `final_ball_coords` (bounce) | `covert_release_step_emitter.py:524, 691`; `skeleton_step_emitter.py:1128-1188`; `transition_bridge.py:1328-1336` | ✅ inv.4 |
| Single step — no intra-turn N→N+1 seam | `dreb_step_emitter.py:213, 279` | ✅ |
| No mid-emit `player.coords` write (emitter; OTB read-only) | `shared.py:892-899`; `resolve_non_shooting_foul` no coords | ✅ §8.1 |
| Possession-flip orientation clean (pass-through normalize + ref-only team swap) | `shared.py:3480-3500`; `game_manager.py:2280-2285` | ✅ |
| DREB→next all-10: sync seeds 10 w/ fallback then overrides | `shared.py:3543-3609` | ✅ §8.2 |
| Primary DREB shot-clock reset fires (possession flip → fresh 30), reset ordering before `switch_possession` | `game_manager.py:1107, 1120, 1603, 1610`; `turn_manager.py:5077, 5194-5195` | ✅ §5 |
| `time_elapsed` schema-derived from emitted step `end.time_elapsed` | `dreb_step_emitter.py:267`; `game_manager.py:1053-1054` | ✅ §5 |
| OTB foul: no clock double-count; possession flips correctly (offensive OTB → flip, defensive OTB → no flip); shot clock resets via Rule 1/Rule 2; no double flip | `phase_resolution.py:739`; `game_manager.py:1075, 1097, 1605-1611`; `turn_manager.py:5080-5087` | ✅ |
| Chained OREB→DREB double-flip guard clears redundant `possession_flips` | `game_manager.py:1459-1465` | ✅ (but see MED-1) |
| §7 per-shot snapshot: N/A (no shot); no `position_snapshots` on DREB turn | grep clean | ✅ (consistent w/ backlog) |

---

### Root-cause map to symptoms
- **New offense shot clock ~1s short after chained putback** → **MED-1** (double-flip guard also disables the DREB's reset).
- **No ball teleports / no wrong-coord shots** → DREB resolves no shot; capture seated-at-ball; all seams continuous.

### Work Plan — DREB → 100% UESS alignment

Very short — DREB is nearly fully compliant.

**DREB-Task 1 — Reset the shot clock on chained `PUTBACK_MISS → DREB` (fixes MED-1, §5) — ✅ DONE & VERIFIED (2026-07-05).**
Added Rule 1b to `_should_reset_shot_clock` ([`turn_manager.py:5071-5079`](../../../BackEnd/models/turn_manager.py#L5071)): `if rt == "DREB": return True`. A defensive rebound renews the shot clock for the securing team's ensuing possession, even when the chained-path double-flip guard clears `possession_flips`. Gated on `result_type=="DREB"` (not `current_turn`) so the OTB-foul branch (`rt="FOUL"`, `current_turn="DREB"`) keeps its own Rule 1/Rule 2 handling.
**Verification (mongomock, `update_clock_and_possession`):** chained DREB (`rt=DREB`, no flip) shot clock **19 → 30**; primary DREB (`rt=DREB`, flip) unchanged at 30 (Rule 1 already fired); OTB foul (`rt=FOUL`, `current_turn=DREB`) stays 19 — the new rule correctly does **not** fire. Regression: 27 clock/ownership tests pass; the 1 failure (`test_make_shot_family…`) is the known pre-existing MAKE-shot test.

**DREB-Task 2 — LOW cleanups — ✅ DONE (2026-07-05).**
- **L-3** corrected the attemptor-archetype docstring ([`dreb_step_emitter.py`](../../../BackEnd/engine/dreb_step_emitter.py)): `cruise` → `standard`. Verified `stamp_rebound_capture_player_motion`'s `attemptor_archetype` defaults to `standard` and neither DREB nor OREB overrides it — `standard` is the real convention (arguably more correct for board-crashers than `cruise`).
- **[UESS SEAM]** wired into `_build_dreb_turn_from_miss` ([`game_manager.py`](../../../BackEnd/models/game_manager.py), before `return dreb_turn`): compares the prior turn's `final_ball_coords` to the DREB step-0 loose-ball coord (`bx,by`); logs `🎯 [UESS SEAM] DREB entry ball teleport candidate…` on divergence > 1.5 grid. **Positive-tested:** a synthetic divergent `final_ball_coords {10,10}` vs bounce `{88,25}` fired the log (gap 79.4) with the DREB still built; behavior-neutral otherwise.
- **Deferred:** L-1 (OTB ball-owner label — position stays continuous via inbound re-seed; changing the emitted owner risks downstream `final_ball_handler_id` readers, ambiguous fix); L-2 (`None`-slot = genuinely-absent player, self-healing at the next-turn seam); L-5 (emitted-clock clamp — cosmetic, master clock already clamped); L-4/L-6 (cosmetic banner-timing + rounding).
**Verification:** compile ✓; positive `[UESS SEAM]` test fires; regression shows no deterministic new failures (the OREB-kickout batch failures are unseeded RNG-order flakiness — a *different* kickout test flips each run, incl. on clean-code batch; `test_make_shot_family` is the known pre-existing).

### Appendix — key line index
- Clock/reset: `turn_manager.py:5068-5103, 5119, 5135-5136, 5194-5195, 4800, 4807-4808`; `game_manager.py:1053-1054, 1107, 1120, 1414-1418, 1459-1465, 1603-1611`.
- Ball seams: `dreb_step_emitter.py:127-132, 173-176, 194-197, 213, 267, 279`; `animation_step_helpers.py:78-86, 147-153, 193-202, 282-297`; `game_manager.py:942-943, 1029`.
- Coord/OTB source: `shared.py:871-941, 892-904`; `game_manager.py:963-974, 993-998, 1605-1611`; `shot_manager.py:2035-2050`; `phase_resolution.py:739`.
