# OREB ↔ UESS Compliance Audit

**Date:** 2026-07-04 · **Scope:** OREB (offensive rebound → PUTBACK shot / KICKOUT / PUTBACK_MISS→DREB) · **Method:** read-only trace, 4 parallel audits (single-coord-source, clock/§5.4, ball-seam, player-coord) · **Audit only — no code changed.** · Turn #2 of the 11-turn UESS sweep (after HCO, Final Turn).

---

## ⭐ TL;DR (human topline — read this first)

**OREB is the healthiest turn type audited so far.** It has its own self-contained UESS emitter (`oreb_step_emitter.py`) and does **not** share HCO's/Final Turn's defects: no double animator build, no stale defender read, the ball chain is fully seam-continuous, and the rebound capture is done right (ball stays loose at the bounce spot while the rebounder sprints to it — not snapped). The clock is schema-derived per the §5.4 exception. **Two MED issues** are worth fixing; everything else is LOW/cosmetic.

| Symptom | Root cause | Verdict |
|---|---|---|
| Putback contest/dunk decided from the "wrong" spot | Putback resolves from the rebounder's **post-MISS crash position** (`rebounder.coords`) while the shot **renders** from `bounce_coords` (where he grabs the ball) → nearest-defender pick, dunk eligibility, and bounce calc use a coord the FE never shows as the shot origin | ⚠️ **MED** |
| Chained putback misses slowly drain the shot clock | A chained `PUTBACK_MISS → OREB` does **not** reset the shot clock (Rule 3 lists `MISS`/`FREE_THROW` but not `PUTBACK_MISS`), though a normal `MISS → OREB` does | ⚠️ **MED** |
| Ball teleport on rebound | **None found** — capture is seated-at-ball; every seam continuous | ✅ |
| Uncontested putback makes (the Final-Turn bug) | **Distance-governed** — make/miss is attribute-based; nearest defender is assigned from render-matched coords, graded through 11 grid, and has zero impact beyond 11 | ✅ |
| Clock at rebound | Schema-derived (§5.4), monotonic, no negative, correct resets (except MED-2) | ✅ |

### Compliance scorecard

| UESS contract | OREB status |
|---|---|
| Single coord source for logic (§1/§7) | ✅ Compliant (attribute-based) · ✅ **MED-1 shot-spot fixed (OREB-Task 1)** |
| Ball step-seam continuity (§8.4 inv.1) | ✅ |
| Ball ownership within-step (§8.4 inv.2) | ✅ |
| Ball **capture** continuity (§8.4 inv.3) | ✅ **seated-at-ball** (not snapped) |
| Ball turn-seam continuity (§8.4 inv.4) | ✅ (L-1 latent only on a non-migrated prior MISS) |
| Player coord step-seam continuity (§8.1) | ✅ (no mid-emit writes) |
| All-10 step-0 coverage (§8.2) | ✅ (L-3 `None`-slot edge) |
| Clock authority (§5.4 schema-burn) | ✅ schema-derived · ✅ **MED-2 chained shot-clock reset fixed (OREB-Task 2)** |
| Seam teleport detection (`[UESS SEAM]`) | ❌ not wired for OREB (own emitter) |

### Which HCO/Final-Turn fixes carry over
**None directly** — OREB has its own emitter (`oreb_step_emitter`), resolver (`resolve_offensive_rebound`), and clock path (`_stamp_oreb_animation_steps`). The `final_ball_coords` snapshot (HCO Task 3b) **does** apply (stamped in `_append_turn`). The `[UESS SEAM]` detection is **not** wired for OREB.

### Fix status (2026-07-04, uncommitted; not yet prototype-tested)
1. ✅ **MED-1** (OREB-Task 1) — putback resolves from the rendered bounce spot (defender pick + dunk eligibility). Verified crash `{40,20}` → bounce `{88,25}`.
2. ✅ **MED-2** (OREB-Task 2) — `PUTBACK_MISS` added to the shot-clock reset rule. Verified `18 → 30` on chained re-rebound; controls unchanged.
3. ✅ **LOW cleanup** (OREB-Task 3) — removed dead micro-injection call (L-2) + dead `rt=="OREB"` reset branch (L-4); wired `[UESS SEAM]` detection for OREB's emitter (L-1). Deferred (not real fixes): L-3 `None`-slot (a `None` slot = a genuinely-absent player, not a coord bug) and L-7 emitted-clock clamp (cosmetic; master clock already clamped, piecemeal clamp would be inconsistent).

### What's genuinely fine (don't touch)
The self-contained emitter's step chaining · seated-at-ball capture · putback/kickout/`PUTBACK_MISS→DREB` seams · schema-burn clock derivation + putback floor + kickout-deferred-to-HCO · all-10 coverage · no mid-emit `player.coords` writes · nearest-defender attribution with distance-graded putback impact.

---
---

## Full audit detail (agent-facing)

### Method
Four read-only traces against the UESS contract ([UESS_System.md](../05_UESS_System/UESS_System.md)). Primary files: [`oreb_step_emitter.py`](../../BackEnd/engine/oreb_step_emitter.py) (`build_oreb_animation_steps`), [`shared.py`](../../BackEnd/utils/shared.py) (`resolve_offensive_rebound` ~L938, `_resolve_oreb_putback_defender` ~L841), [`turn_manager.py`](../../BackEnd/models/turn_manager.py) (`resolve_offensive_rebound_turn` ~L4358, `_stamp_oreb_animation_steps` ~L4293, `_should_reset_shot_clock` ~L5035), [`game_manager.py`](../../BackEnd/models/game_manager.py) (`_build_dreb_turn_from_miss` ~L922, PUTBACK_MISS→DREB spawn). Doc: [`Rebound_System.md`](../06_GP_Supporting_Systems/Rebound_System.md).

---

### MED-1 — Putback resolved from the rebounder's crash position, rendered from the bounce spot (§1)

The OREB analog of the single-coord-source issue — but **milder** than HCO/Final Turn (make/miss is mostly attribute-based, so no silent "uncontested make").

- **Resolution reads `rebounder.coords`** (the live post-MISS *interrupted crash position*): `shot_manager` shooter coords ([`shared.py:995-997`](../../BackEnd/utils/shared.py#L995)); defender pick `_resolve_oreb_putback_defender(game, rebounder, def_lineup, basket_x)` iterates `def_lineup[*].coords` and returns the Euclidean-nearest to `rebounder.coords` ([`shared.py:841-862`](../../BackEnd/utils/shared.py#L841)); dunk-location eligibility `dunk_location_eligible(dist, ag)` with `dist = _euclid(rebounder.coords, basket)` ([`shot_micro_movements.py:260-287`](../../BackEnd/engine/shot_micro_movements.py#L260), reached via `shared.py:1099`); `calculate_bounce_spot(shooter_coords=rebounder.coords)`.
- **The emitter renders the shot from `bounce_coords`** (where the ball landed = `prior_turn.ball_bounce_x/y`): the `[rebound_capture]` step moves the rebounder to `bounce_coords`, and `[putback_shoot]`/`[ball_flight]` originate there ([`oreb_step_emitter.py:285, 386, 656`](../../BackEnd/engine/oreb_step_emitter.py#L285)).
- **Divergence:** the defender chosen as "nearest to the rebounder's crash coord" may not be nearest to the *rendered* shot location; that changes **which defender's attributes drive the putback contest** (`ID/ST/IQ/CH`, `shot_manager.py:2615-2622`) → outcome-affecting. Dunk eligibility + the 1% `force_miss` and the miss bounce spot are also computed from the un-rendered coord.
- **Severity: MED.** The core make/miss threshold is coord-independent (attribute-based), so this is **not** the HIGH "outcome from coords the FE never shows" of HCO/Final Turn — but the defender-selection path is genuinely outcome-affecting when the crash coord and bounce coord differ (long rebound). Flagged independently by both the single-coord-source and player-coord traces.
- **Fix direction:** pass `bounce_coords` (the prior miss's `ball_bounce_x/y`, available to `resolve_offensive_rebound` via `prior_turn`) as the shooter coord into the putback resolution (defender pick + dunk eligibility + bounce calc), so resolution == render.

---

### MED-2 — Chained `PUTBACK_MISS → OREB` does not reset the shot clock (§5 / rules)

- `_should_reset_shot_clock` ([`turn_manager.py:5035-5064`](../../BackEnd/models/turn_manager.py#L5035)) Rule 3: `if rebound_type == "OREB" and rt in {"MISS","FREE_THROW"}: return True` (5062). A chained OREB (offense rebounds its own putback miss) has `result_type="PUTBACK_MISS"`, which is **not** in that set, and `possession_flips=False` (Rule 1 doesn't fire) → **no reset**.
- A normal `MISS → OREB` **does** reset via Rule 3. And `game_manager.py:1509-1512` explicitly treats `PUTBACK_MISS` as "just another kind of miss," so the omission reads as an oversight.
- **Repro:** miss (SC reset→30) → OREB → putback miss → offense rebounds again → the 2nd OREB enters with SC≈28, not 30; each further chained putback miss drains ~2s; ~13 consecutive would false-trigger the `entry_shot_clock<=2` violation gate (`turn_manager.py:4410`).
- **Severity: MED** (semantically wrong/inconsistent; low practical frequency).
- **Fix direction:** add `PUTBACK_MISS` to the Rule-3 set (or gate on `current_turn == "OREB"`).

---

### LOW findings

| ID | Finding | Location |
|---|---|---|
| L-1 | Turn seam (INV 4) reads `prior_turn.ball_bounce_x/y` **directly**, not `final_ball_coords`. Continuous today; only diverges if the prior MISS were non-UESS-migrated (no `[bounce]` step) — moot in a fully-migrated regime | `oreb_step_emitter.py:597-608` |
| L-2 | Dead shot-micro injection: `inject_shot_micro_before_post_shot` is a guaranteed no-op for putbacks (`apply_shot_micro_steps_to_chain` gates on `MAKE/MISS/BLOCK`, not `PUTBACK_*`). Harmless but misleading; the micro family stamped in `resolve_offensive_rebound` is unused. Latent: if putback types were ever normalized to `MISS`, a **player-coord** seam would open (`flight_step` seeds from `shoot_step.end`, not `steps[-1].end`) | `oreb_step_emitter.py:668`; `shot_micro_movements.py:1267` |
| L-3 | All-10 coverage degrades to <10 if a lineup slot is `None` (fouled-out-not-yet-substituted): `_player_iter` skips `None`; `_build_start_coords_from_prior` drops pids absent from both `final_coords` and `player.coords`. Graceful (guarded), but not strictly all-10 in that edge | `oreb_step_emitter.py:100-124` |
| L-4 | Dead reset branch: `if rt == "OREB": return True` is unreachable (no turn carries `result_type=="OREB"`) | `turn_manager.py:5060` |
| L-5 | Putback floor (`OREB_PUTBACK_MIN_TIME_ELAPSED=2`) creates a sub-second clock discontinuity into the next turn when the raw schema burn (~1.5s) rounds below 2 — the emitted step clocks show ~1.5s but the authoritative clock burns 2. Monotonic, non-negative; **documented/sanctioned** | `turn_manager.py:4351-4352`; `constants:322-328` |
| L-6 | OREB_KICKOUT effective burn can `round(0.5)→0` (capture-only step). Intended per §5.4 (reset/bring-up burned by the following HCO entry); not double-counted or dropped within OREB scope | `oreb_step_emitter.py:643-649`; `turn_manager.py:4952` |
| L-7 | Emitted `end.shot_clock_remaining` in capture/shoot steps isn't clamped ≥0 (`shot_clock − t`, no `max(0,…)`), so the payload *display* could show slightly negative on a low-clock putback; the **master** clock is clamped (`update_clock_and_possession`). Cosmetic | `oreb_step_emitter.py:269, 346` |

---

### Verified COMPLIANT (coverage — do not "fix")

| Contract / boundary | Evidence | Result |
|---|---|---|
| **No `resolve_shot` / animator build** in putback — resolves inline via `calculate_shot_score` (attribute-based defense) | `shared.py:1036-1087, 1125-1129`; `shot_manager.py:2610-2622` | ✅ no HCO/FT defect |
| Defender: nearest is assigned; impact is graded at ≤11 and zero beyond 11 | `_resolve_oreb_putback_defender`, `resolve_offensive_rebound` | ✅ |
| Coords from same canonical source (resolver live `player.coords` == emitter `prior_turn.final_coords` via `build_final_coords`) | `animation_step_helpers.py:22-45`; `game_manager.py:798`; `oreb_step_emitter.py:610-613` | ✅ |
| Capture seated-at-ball (loose @ bounce, rebounder sprints to it, gate `player_reaches_position`) | `oreb_step_emitter.py:172-286`; `stamp_rebound_capture_player_motion` | ✅ §8.4 inv.3 |
| Putback chain seams `capture→shoot→ball_flight→hold/bounce` (ball + coords) | `oreb_step_emitter.py:656, 692, 711, 743, 794, 824` | ✅ |
| KICKOUT emits capture only; transfer deferred to HCO entry (within-step there) | `oreb_step_emitter.py:643-649`; `transition_bridge.py:751-756` | ✅ |
| `PUTBACK_MISS→DREB` seam: ball (`bounce`) + all-10 coords continuous | `game_manager.py:786, 798, 1409, 1440, 963-974`; `dreb_step_emitter.py:173` | ✅ §8.2 |
| No mid-emit `player.coords` write (emitter or resolver) | grep clean; only write is end-of-turn sync `shared.py:3638` | ✅ §8.1 |
| Putback uses §9.5-interrupted coords, not snapped overlays (sync omits overlay maps) | `shared.py:3617-3630` | ✅ |
| `time_elapsed` schema-derived from emitted first/last clock; PUTBACK floored at 2; KICKOUT raw | `turn_manager.py:4333-4352` | ✅ §5.4 |
| No negative/non-monotonic clock; DREB spawn reads decremented clock after OREB append | `turn_manager.py:4338, 5080, 5096`; `game_manager.py:1411, 1440` | ✅ |
| PUTBACK_MAKE / PUTBACK_MISS→DREB shot-clock resets fire once (no double flip) | `turn_manager.py:5155-5156`; `game_manager.py:1414-1418, 1465` | ✅ |
| §7 per-shot snapshot unbuilt; OREB snapshots are audit-only ledgers (not consumed) | `position_snapshot_ledger.py:224-253`; `shared.py:1159, 1348` | ✅ (consistent w/ backlog) |

---

### Work Plan — OREB → 100% UESS alignment

Order **1 → 2 → 3**. Much shorter than HCO/Final Turn — OREB is largely compliant.

**OREB-Task 1 — Resolve the putback from the rendered shot spot (fixes MED-1, §1) — ✅ DONE & VERIFIED (2026-07-04).**
`resolve_offensive_rebound` ([`shared.py`](../../BackEnd/utils/shared.py)) now derives `shooter_coords` from `game.turns[-1].ball_bounce_x/y` (the prior miss's landing spot = where the rebounder captures and shoots, `game.turns[-1]` == the prior MISS at resolve time), falling back to `rebounder.coords` if unavailable. That coord feeds the nearest-defender pick (`_resolve_oreb_putback_defender`, given a new `shooter_coords` param), the dunk-location eligibility, and the shot-micro/variant stamps — all now match the rendered `[putback_shoot]` origin. Note: `calculate_bounce_spot` (the *next* DREB's bounce) is basket-relative and correctly unchanged; `rebounder.coords` (the animation's crash→capture start) is NOT mutated.
**Verification (mongomock, driven putback):** the coord passed to defender-resolve + dunk-stamp went from the crash `{40,20}` **before** → the bounce `{88,25}` **after**. Regression: OREB tests pass; the failures observed (2 HCT tests + the unseeded order-dependent `test_repair_enables_dreb_promotion`) are **pre-existing** (fail identically on clean code / clean batch). **Gameplay consequence (accepted):** slightly changes which defender contests some putbacks + dunk-family selection — minor (both coords near the rim).

**OREB-Task 2 — Reset the shot clock on chained offensive rebounds (fixes MED-2, §5/rules) — ✅ DONE & VERIFIED (2026-07-04).**
Added `PUTBACK_MISS` to the `_should_reset_shot_clock` Rule-3 set ([`turn_manager.py:5062`](../../BackEnd/models/turn_manager.py#L5062)): `if rebound_type == "OREB" and rt in {"MISS","FREE_THROW","PUTBACK_MISS"}`. A putback miss that's offensively re-rebounded (`rebound_type=OREB`, no possession flip) now renews the shot clock like a normal `MISS → OREB`.
**Verification (mongomock, `update_clock_and_possession`):** `PUTBACK_MISS + OREB` shot clock **18 → 30** (before → after). Controls unchanged: `MISS + OREB` stays 30 (no regression); `BLOCK + OREB` stays 18 (correctly still excluded — no over-reset). Regression: 27 clock/ownership tests pass; the 1 failure (`test_make_shot_family…`) is the known pre-existing MAKE-shot test (fails on clean code).

**OREB-Task 3 — LOW cleanups — ✅ DONE (2026-07-04).**
- **L-2** removed the dead `inject_shot_micro_before_post_shot` call ([`oreb_step_emitter.py`](../../BackEnd/engine/oreb_step_emitter.py)) — guaranteed no-op for putbacks (verified: `apply_shot_micro_steps_to_chain` gates on MAKE/MISS/BLOCK; no other side effects).
- **L-4** removed the dead `rt == "OREB"` reset branch ([`turn_manager.py`](../../BackEnd/models/turn_manager.py) `_should_reset_shot_clock`) — verified no turn/test sets `result_type=="OREB"`.
- **L-1** wired `[UESS SEAM]` detection into `_stamp_oreb_animation_steps` (OREB has its own emitter, not covered by the skeleton detector) — compares prior `final_ball_coords` vs the emitted step-0 ball position; behavior-neutral (should never fire, since OREB step 0 is `BallLoose` at the prior bounce == prior `final_ball_coords`).
- **Deferred:** L-3 (`None`-slot = genuinely-absent player, not a coord bug) and L-7 (emitted-clock clamp — cosmetic; master clock already clamped via `update_clock_and_possession`, and clamping only 2 of several step builders would be inconsistent).
**Verification:** compile ✓; OREB emits + detection runs without crash; regression shows no deterministic new failures (the OREB-kickout batch failures are unseeded RNG-order flakiness — a *different* kickout test flips on clean-code batch too; `test_make_shot_family` is the known pre-existing failure).

### Appendix — key line index
- Single-coord / putback: `shared.py:938, 841-862, 995-997, 1036-1087, 1099, 1125-1129`; `shot_manager.py:2558, 2610-2622`; `shot_micro_movements.py:237-294`.
- Ball seams: `oreb_step_emitter.py:172-286, 247, 265, 656, 692, 711, 794, 824`; `dreb_step_emitter.py:173`; `animation_step_helpers.py:100, 143-145, 264-313`.
- Player coords: `oreb_step_emitter.py:100-127, 213-215, 610-620`; `game_manager.py:786, 798, 963-974, 1409-1440`; `shared.py:3617-3638`.
- Clock: `turn_manager.py:4293-4356, 4410, 5035-5064, 5080-5156`; `game_manager.py:1411-1465`; `constants:322-328`.
