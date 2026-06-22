# Dynamic HCO Motion — Implementation Plan

Companion to `Dynamic_HCO_Motion_Brief.md` (source of truth for behavior/numbers). This plan is the *how/where/order*. Phases are independently shippable; each lands behind tests before the next.

## Architecture decisions (settled in brief discussion)
- Step 2 **replaces** the random-step selection in `resolve_motion_offense_shot()` ([phase_resolution.py:4231](BackEnd/engine/phase_resolution.py#L4231)). Called from [phase_resolution.py:4712 & 5447](BackEnd/engine/phase_resolution.py#L4712).
- Any shot **hands off to existing shot execution** — inside/outside dish via `_create_pass_receive_step`/`_create_shoot_step`, attack via `build_attack_drive_sequence()` (which always terminates in a shot). No new shot math.
- Read map is **ephemeral, per-turn**, attached to turn context — not persisted to the team doc (no SS&S/schema surface).
- Scores use **form B**: `(raw_helper + modifier) × random.randint(1,6)` — single roll; needs roll-free helper variants.
- Inside-spot test = canonical set (both lowPost, both midPost, midLane, basketSpot + bounded area). Reuse/extend `_is_inside_location`.

## Key existing pieces to reuse
| Need | Reuse |
|------|-------|
| Man matchups | `get_matchups_for_defending_team(game_state, defending_team_is_user)` → `{def_pos: off_pos}` |
| Zone areas | `defense_zone_shell_variant(playcall)` + `defenses` collection `zone_definitions` (union of all states) |
| Read roll | `player_read()` → raw `(IQ*0.8+CH*0.2)` |
| Pressure D | `calculate_defender_pressure_score()` → raw `(OD*0.3+AG*0.3+IQ*0.2+CH*0.2)[×0.9 zone]` |
| Inside D | paint formula `(ID*0.6+ST*0.2+IQ*0.1+CH*0.1)` (from `shot_manager.calculate_shot_score` paint branch) |
| Aggression | `team.strategy_calls["aggression_call"]` ∈ {passive,normal,aggressive} (both teams, per-break) |
| Sliders | `team.strategy_settings` (discipline/fight/efficiency 0..±10, chemistry 7–25) |
| Spots/coords | `HCO_STRING_SPOTS`, `_is_inside_location`, `_is_outside_location` |
| Attack shot | `build_attack_drive_sequence()` |
| Shot clock | `game_state["shot_clock_remaining"]` (max 30) |

---

## Phase 1 — Read Map (brief Step 0 + Step 1) — PURE COMPUTE, NO UESS
**New:** `BackEnd/engine/motion_read_map.py`
- `build_motion_read_map(game, off_lineup, def_lineup) -> {player_id: {"inside":bool,"attack":bool,"outside":bool}}`
- **Man path:** reverse matchups → per matchup compute Inside `(SC+ST)/2−(ID+ST)/2`, Outside `SH−OD`, Attack `(SC+AG)/2−(ID+AG)/2`; flag `> 15`.
- **Zone path:** build a static `ZONE_AREA_COVERAGE[defense_id] = {pos: set(spots)}` constant derived from the `defenses` collection `zone_definitions` (union of normal + all shift states); D-scores = avg over defenders whose area touches that shot-type region (Inside `(ID+ST)/2`, Outside `OD`, Attack `(ID+AG)/2`); offense individual scores `(SC+ST)/2`, `SH`, `(SC+AG)/2`; mismatch − D-score, flag `> 15`.
- **Spot classification:** one shared `is_inside_spot(location_or_coords)` (canonical set + bounded area) used everywhere.
**Tests:** seeded attribute fixtures → expected flag maps (man + each zone variant); zone coverage constant matches DB.
**Risk:** low. Self-contained.

## Phase 2 — Per-step decision engine (brief Step 2 logic) — PURE, DECISION-ONLY
**New:** `BackEnd/engine/motion_step_decision.py`
- Add roll-free helpers in `shared.py` (`*_raw`), have existing helpers wrap them — no formula fork.
- `decide_step_action(game, step, bh, bh_defender, read_map, shot_clock, off_aggr, def_aggr, rng) -> Decision`
  - `offense_score = (player_read_raw(bh) + discipline) × rand`; if `<110` → desperation block (`roll>4×shot_clock` → 75% shot / 25% kick-out-catch-and-shoot; else fall through).
  - progression: `defense_score = (defender_action_raw + fight) × rand` (inside vs pressure by BH location).
  - offense wins (`> defense + def_eff + def_chem`) → hot-read-or-advance (50/70/30 by aggr; self→closest teammate); defense wins → disruption (50 subtle/20 FF/30 none, aggr-adjusted); else 50/50 subtle/pass (both-team aggr-adjusted).
- Returns an action enum + payload (shooter, shot_type, target) — **no emission yet**.
**Tests:** seeded RNG → deterministic branch coverage for every path + aggression deltas + "normal" baseline.
**Risk:** low/med. No I/O.

## Phase 3 — Integrate loop + shot handoff into `resolve_motion_offense_shot`
- Replace Phase-1 random step pick: walk skeleton steps; per step call `decide_step_action`; stop on a terminating (shot) action or skeleton end.
- Map decisions → existing execution: inside/outside dish + `build_attack_drive_sequence` for attack; hot-read self vs teammate (closest, tie random); desperation + kick-out catch-and-shoot (receiver location/attrs).
- Terminating shot → normal `resolve_hco_outcome` path (unchanged downstream).
**Tests:** integration on a mock motion skeleton — each decision yields a valid truncated+appended skeleton; shooter/shot_type correct; attack reuses drive flags.
**Risk:** med. Touches the live motion entry point — guard behind the new path; keep old behavior reachable until validated.

## Phase 4 — Subtle Movement emission (UESS)
- BH micro-moves (in-place / back 2–5 / side / in 2–5) + non-BH conditional moves; emit as a mid-skeleton step with coords; "hold until next skeleton step" semantics; non-BH selection **random for now**.
**Risk:** high — UESS step-T/no-teleport at boundaries. QA per dish-turn checklist.

## Phase 5 — Freelance Forced emission + resolution
- Relocate ≤9 grid spots (or subtle 50%); off_eff+chem>15 → no same-spot; shot resolution reuses Phase-2/3 logic + tempo; pass-within-20 (80%) / hold (20%); no teammate → shoot. Shot-clock bounds the loop.
**Risk:** high. Depends on Phase 3/4.

## Phase 6 — Frontend / animation (separate PR)
- Collision rattle (3× like rim shots, land offset 2 grid spots) + dribble-in-place idle visuals. No backend dependency.

## Deferred / out of scope
- **Freelance Audible** — defined in brief but no trigger yet; inert until a future pass adds the elective entry point.

## Testing notes
- pytest is **block-listed** from `gob`/`gob-staging` ([tests/conftest.py](tests/conftest.py)). Run with `MONGO_URI="" MONGO_DB_NAME="gob-test"` → in-memory mongomock. Phases 1–2 are pure and need no DB.
- Seed `random` for deterministic branch tests.
