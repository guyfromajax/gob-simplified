# Position Checkpoints & Snapshot Schema

**Document status (updated 2026-06-13):** **Emission side implemented and broadly wired** — the position ledger (`BackEnd/utils/position_snapshot_ledger.py`) exists, attaches `position_snapshots` across HCO/FCP/HCT, fast break + Rim Runner, Final Turn, shot-clock forced shot, free throws, OREB, inbound (BIP/SIP), opening tip, and force-foul paths, with unit tests (`tests/test_position_snapshot_ledger.py`) and an audit script (`scripts/audit_position_snapshots.py`). See **§8.1** (coverage matrix) and **§12** (implementation reference) for what's live today. **Still pending:** (1) **consumer adoption** — location-based rules have *not* yet migrated off `Player.coords` to read the ledger (§9, §11.2–11.3); the ledger currently *records* authoritative layout rather than *driving* rules; (2) a few **coverage gaps** remain open (§8.2 — e.g. After-Steal fast break, FB `DEFENSIVE_STOP`, FCP/HCT break→HCO). This file is the **standard reference** for checkpoint identity and snapshot payload shape; §5–§7 are stable, §8/§11 track remaining work.

**Related:** [Defense Coordinate System](./Defense_Coords_System.md) (HOME grid, orientation rules).

---

## 1. Purpose

We need a **single, explicit contract** for *where every active player is on the court* at **discrete checkpoints** during resolution, so **location-based gameplay** (contests, fouls, help, fast-break defense, future rules) reads from one authoritative story instead of ad hoc `Player.coords` reads mixed with stale or partial updates.

This doc defines:

1. **Checkpoint identity** — how we name *when* a snapshot applies (steps vs procedural phases).
2. **Snapshot schema** — what data we store at each checkpoint.

**Non-goal (for now):** Continuous or frame-by-frame physics. Checkpoints are **milestone-based** (see §3).

**Future direction:** The long-term engine vision is **more dynamic and less rigid** than today’s skeleton-heavy flows. Checkpoint semantics are designed to survive a migration from strict skeleton steps to more procedural motion; skeleton step indices are one **kind** of checkpoint, not the only kind.

---

## 2. Terminology

| Term | Meaning |
|------|--------|
| **Checkpoint** | Any discrete moment in resolution where we record a full-court player layout for gameplay or parity with the client. |
| **Snapshot** | The payload at one checkpoint: positions for all relevant players, plus metadata. |
| **Step-based turn** | Turn types driven by a **skeleton** with ordered steps (e.g. HCO, FCP, HCT). Checkpoints align with **skeleton step index** (and optionally terminal “after full play” points). |
| **Procedural / phase-based turn** | Turn types where layout is driven by **resolution phases** (e.g. fast break: outlet, steal entry, shot attempt). Checkpoints use a **phase enum**, not a skeleton index. |
| **Position ledger** (implementation) | The subsystem that **appends** snapshots per turn and exposes them to sim logic (name TBD in code). |

---

## 3. Milestone granularity (“phase-level”)

Snapshots are taken at **checkpoints** that matter for **rules and UI parity**, not at every animation tick.

- For **step-based** plays: checkpoints are typically **per skeleton step** and/or **after the full play animation** (finals), depending on which rules need which moment.
- For **procedural** plays: checkpoints are **named phases** in the fast-break (or other) resolver.

Adding a new checkpoint is a **product/engine decision** (new rule needs a new moment), not a change to the core schema shape.

---

## 4. Coordinate authority

- **Grid:** Same **HOME** court grid as the rest of the sim and frontend (see Defense Coordinate System doc).
- **Authority rule:** Positions at a checkpoint must be **derivable from the same inputs used to build animations** for that turn (skeleton → `skeleton_to_animations`, overlays such as get-back / release, fast-break-specific computed coords). **Do not** invent parallel geometry in the ledger.
- **Lineup scope:** Default is **all ten active lineup players** (`player_id` → `{ x, y }`). If a future rule needs only a subset, the snapshot still **may** carry the full ten for consistency; filters live in consumers.

---

## 5. Checkpoint identity model

Checkpoints are identified by a **structured reference**, not a single global enum of every possible moment (that would grow without bound).

### 5.1 Common fields (all checkpoints)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `turn_type` | string | yes | Align with existing turn classification (e.g. `HCO`, `FCP`, `HCT`, `FAST_BREAK`, `INBOUND_PASS`, …). Must match whatever the engine uses for the current turn. |
| `checkpoint_kind` | string | yes | Discriminator: see §5.2. |
| `label` | string | no | Human-readable label for logs and debugging (e.g. `"before_resolve_shot"`). |

### 5.2 `checkpoint_kind` values

| `checkpoint_kind` | Extra fields | Use when |
|-------------------|--------------|----------|
| `skeleton_step` | `step_index` (int, 0-based), optional `step_count` (int) | HCO / FCP / HCT (and any skeleton-driven turn). |
| `fast_break_phase` | `phase` (enum string, see §6.2) | Fast break and similar procedural flows. |
| `turn_terminal` | none | End of turn: aligns with post-animation finals and `sync_lineup_coords_from_turn` semantics. |
| `custom` | `custom_id` (string) | Escape hatch for rare paths; prefer adding a proper kind or phase over time. |

**Resolution:** `checkpoint_kind` + `turn_type` + kind-specific fields **uniquely** identify the checkpoint within a turn’s sequence (append order disambiguates repeats if ever needed).

---

## 6. Enums (initial, extensible)

### 6.1 `turn_type` (illustrative)

Align with existing engine enums / transition registry; do not fork naming in the ledger.

Examples: `HCO`, `FCP`, `HCT`, `FAST_BREAK`, `OREB`, `FREE_THROW`, `INBOUND_PASS`, `SIDE_INBOUND_PASS`, `OPENING_TIP`, …

**Rule:** add new values only when the engine adds a distinct turn type.

### 6.2 `fast_break_phase` — aligned with `phase_resolution` and `rim_runner_fast_break`

Fast break is resolved along **three disjoint entry paths** in code:

| Path | Function | File |
|------|----------|------|
| **Standard / Covert Release / steal-initiated (legacy)** | `resolve_fast_break_logic` | `BackEnd/engine/phase_resolution.py` |
| **Rim Runner (and Thirty-Two on DREB)** | `resolve_rim_runner_fast_break` | `BackEnd/engine/rim_runner_fast_break.py` |
| **After Steal (steal-initiated, new resolver)** | `resolve_after_steal_fast_break` | `BackEnd/engine/after_steal_fast_break.py` |

`resolve_fast_break_logic` **returns early** into `resolve_rim_runner_fast_break` when `rebound` and `fb_play_key in (RIM_RUNNER, TRIANGLE)`, and into `resolve_after_steal_fast_break` when `not rebound and fb_play_key == AFTER_STEAL` (the new resolver builds the complete turn result including `animation_steps`; downstream legacy steal logic is bypassed). So a given turn uses **one** of these functions end-to-end, not several.

Use **`phase`** strings below in snapshot checkpoints. Prefer the **code anchor** column when wiring the ledger so names stay traceable in reviews.

#### A — Standard fast break (`resolve_fast_break_logic`)

| `phase` | Code anchor (approximate) | What is true at this moment |
|---------|---------------------------|------------------------------|
| `fb_logic_fb_roles_defense_ready` | After `fb_roles["defense"] = get_in_play_defenders(...)` and optional defensive PG chaser | Ball handler, `fb_roles["defense"]`, outlet metadata (DREB) or steal metadata set; **not** yet `ball_handler_outlet_x` / `y`. |
| `fb_logic_ball_handler_outlet_position` | After `fb_roles["ball_handler_outlet_x"]` / `y` (and move fields) — follows block comments **“DREB → FAST BREAK: OUTLET PASS LOGIC”** or **“STEAL → FAST BREAK: STEAL ENTRY LOGIC”** | DREB: receiver at release/get-back coords, no extra move. Steal: after steal-entry delta toward basket. |
| `fb_logic_defender_outlet_loop_done` | After `for defender in def_lineup.values():` loop that sets `defender.outlet_coords`, tracks ahead/y-range, `shot_defender`, closest defender | Geometry for stop vs shot (`defender_ahead`, `closest_stopping_defender`, `closest_defender_overall`) resolved. |
| `fb_logic_stop_skill_check` | Only when geography says a stop is possible: `break_score` vs `stop_score` on `closest_stopping_defender` | Optional checkpoint; skip if branch not taken. |
| `fb_logic_event_type_resolved` | After `event_type` is `SHOT` or `DEFENSIVE_STOP` (incl. skill check) | Knows SHOT vs stop before animation/shot manager. |
| `fb_logic_pre_shot` | `event_type == "SHOT"`: immediately before `Animator.capture_fast_break_animation` then `shot_manager.resolve_shot` | Same region as `fb_roles` shot-spot fields `_bh_final_x` / `_bh_final_y` after animation capture. |
| `fb_logic_defensive_stop` | Early return with `result_type == "DEFENSIVE_STOP"` | No shot; HCO next. |

#### B — Rim Runner fast break (`resolve_rim_runner_fast_break`)

| `phase` | Code anchor (approximate) | What is true at this moment |
|---------|---------------------------|------------------------------|
| `fb_rr_rim_runner_burst_phase_built` | After `fb_roles["rim_runner_burst_phase"] = { ... }` (includes `rr_from` / `rr_to`, `receiver_to`, outlet defender, `other_players`) | Burst geometry and outlet animation payload for RR path. |
| `fb_rr_outlet_contest` | After outlet offense/defense scores; before `if not outlet_ok` | Outlet pass vs pressure decided (`outlet_ok`). |
| `fb_rr_outlet_denied` | Branch: `outlet_ok` false → `DEFENSIVE_STOP`, `rim_runner_outlet_failed` | Early exit; no burst/PG read. |
| `fb_rr_post_outlet_coords` | After `rr.coords` / `ball_handler.coords` updated from `rr_to` / `receiver_to` | Positions synced for burst step. |
| `fb_rr_lane_threat_geo` | After `lane_threat_count` / `fb_open` from BH→RR steal/bat positional gate | Objective open-lane geo for pass vs hold read. |
| `fb_rr_pg_read` | After `correct_read`, `pass_attempted` (aggression branches) | Ball handler read on whether to pass to rim runner. |
| `fb_rr_hold_up_stop` | Branch: `not pass_attempted` → `DEFENSIVE_STOP` (“holding up”) | No pass to finisher. |
| `fb_rr_pre_shot` | Before `capture_fast_break_animation` + `resolve_shot` for RR shot outcomes (open pass, no primary, intercept tiers completion, etc.) | Includes `_bh_final_x` / `y` when set for shot spot. |
| `fb_rr_turnover_steal` | `resolve_turnover_logic(..., turnover_type="STEAL")` high intercept tier | Possession change. |
| `fb_rr_dead_ball_bat_oob` | `result_type == "DEAD BALL"` bat OOB branch | Side inbound next. |

#### C — Shared / outcome

| `phase` | When |
|---------|------|
| `fb_turn_terminal` | After turn dict finalized (optional if global `turn_terminal` on the same turn is enough). |

**Implementation note:** Rim Runner phases (`fb_rr_*`) never run together with **A** in the same turn because of the early return from `resolve_fast_break_logic`. Standard phases (`fb_logic_*`) apply to non–Rim Runner / non-Thirty-Two fast breaks handled entirely in `resolve_fast_break_logic`.

**Note:** Subtypes of `DEFENSIVE_STOP` (outlet denied vs geography vs RR hold-up) can share `fb_logic_defensive_stop` / `fb_rr_outlet_denied` / `fb_rr_hold_up_stop` for snapshots; use `turn_result` keys like `rim_runner_outlet_failed` for disambiguation if needed.

---

## 7. Snapshot payload schema

Each **snapshot** is one row in the turn’s ledger (conceptually append-only).

### 7.1 `CourtPositionSnapshot` (logical)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `checkpoint` | object | yes | Checkpoint identity (§5). |
| `positions` | map | yes | `player_id` (string) → `{ "x": number, "y": number }` in HOME grid. |
| `ball_handler_id` | string | no | If known at this checkpoint; helps consumers without inferring. |
| `possession_team_id` | string | no | If useful for debugging multi-team events. |
| `source` | string | no | Provenance (`"skeleton_to_animations"`, `"overlay:getback"`, `"fb_resolver"`, …). |
| `schema_version` | int | yes | Bump when the snapshot shape changes (start at `1`). |

### 7.2 JSON example (illustrative)

```json
{
  "checkpoint": {
    "turn_type": "HCO",
    "checkpoint_kind": "skeleton_step",
    "step_index": 2,
    "step_count": 5,
    "label": "after_skeleton_step_2"
  },
  "positions": {
    "player-uuid-01": { "x": 64, "y": 25 },
    "player-uuid-02": { "x": 55, "y": 18 }
  },
  "ball_handler_id": "player-uuid-01",
  "source": "skeleton_to_animations",
  "schema_version": 1
}
```

### 7.3 Turn payload attachment (optional)

For debugging and client parity audits, the **list of snapshots** for the turn may be attached to the turn result (e.g. `position_snapshots: []`) behind size limits. Exact key name is an implementation detail.

---

## 8. Coverage matrix (universal snapshot policy)

**Policy:** Every **gameplay** turn that moves or fixes players on the court should attach at least one `position_snapshots` entry (see `attach_position_snapshots` in `BackEnd/utils/position_snapshot_ledger.py`), derived from the same geometry as animations where applicable.

**Explicitly out of scope:** **Timeout** turns (no court layout requirement). Anything else that returns a turn to the client without spatial meaning should be listed under §8.2.

### 8.1 Implemented paths (reference for audits)

| Area | Checkpoint / source | Where wired |
|------|---------------------|-------------|
| HCO shot | `pre_resolve_shot` (`build_hco_pre_resolve_shot_snapshot`) | `phase_resolution.resolve_half_court_offense_logic` |
| HCO turnover / non-shooting foul | `post_stopper_animation` + `outcome_kind` (`build_phase_post_stopper_snapshot`) | Same, non-shot branches |
| FCP shot | `pre_resolve_shot` (`build_skeleton_pre_resolve_shot_snapshot`, turn_type `FCP`) | `resolve_full_court_press_logic` |
| FCP turnover / steal / non-shooting foul | `post_stopper_animation` | FCP non-shot branch |
| HCT shot | same pattern as FCP with turn_type `HCT` | `resolve_half_court_trap_logic` |
| HCT turnover / steal / non-shooting foul | `post_stopper_animation` | HCT non-shot branch |
| Fast break shot | `fb_logic_pre_shot` / `fb_rr_pre_shot` (`build_fast_break_pre_shot_snapshot`) | `resolve_fast_break_logic`, `rim_runner_fast_break` |
| Fast break turnover / foul | `post_stopper` (`build_phase_post_stopper_snapshot`, `FAST_BREAK`) | `resolve_fast_break_logic`, Rim Runner steal / bat OOB |
| Final Turn shot | `build_skeleton_pre_resolve_shot_snapshot` (`FINAL_TURN`) | `phase_resolution` |
| Free throw | `build_free_throw_snapshot` | `resolve_free_throw_logic` |
| OREB putback / kickout | `build_oreb_*` | `shared.resolve_offensive_rebound`, `turn_manager` |
| Side / baseline inbound | `build_inbound_destinations_snapshot` | `turn_manager`, `quarter_start` (BIP) |
| Opening tip | `build_opening_tip_snapshot_from_animations` | `opening_tip.execute_opening_tip` |
| Shot-clock forced shot | `build_skeleton_pre_resolve_shot_snapshot` | `turn_manager` |
| Force foul (situational after inbound, final-turn, after DREB) | `post_stopper` (`build_phase_post_stopper_snapshot`, `turn_type: HCO`) | `turn_manager`, `game_manager` — see §12.5 |

**Non-shooting fouls** use the same `post_stopper` snapshots as turnovers on HCO, FCP, HCT, and fast break (outcome_kind `non_shooting_foul`), plus the dedicated force-foul rows above when there is no skeleton animation.

### 8.2 Known gaps (to close for “universal” parity)

| Situation | Why it matters | Suggested checkpoint |
|-----------|----------------|----------------------|
| Fast break `DEFENSIVE_STOP` (early return before shot/TO/foul branch) | Full turn with `animations`, no snapshot yet *(re-verified open 2026-06-12)* | `FAST_BREAK` + `post_stopper` or `fb_logic_defensive_stop` phase |
| **After Steal fast break** (`resolve_after_steal_fast_break`, `BackEnd/engine/after_steal_fast_break.py`) | New resolver builds the full turn result (`animation_steps`, end coords for all 10) with **no** `attach_position_snapshots` call *(found 2026-06-12)* | `fast_break_phase` rows analogous to §6.2-A, or at minimum a `pre_shot` + `post_stopper` pair |
| FCP / HCT non-shot when resolution is **press/trap break → HCO** (`result_type == "HCO"`) | Transition turn with skeleton/animations, no dedicated snapshot row in §8.1 | `post_stopper` or `skeleton_step` with label `fcp_hct_break_to_hco` |
| Any **new** resolver that builds a `result` dict with `animations` or `current_turn` | Easy to miss in code review | Add snapshot in the same PR, or add a row here under §8.2 until done |

Re-run the mechanical audit after engine changes: `python scripts/audit_position_snapshots.py` (repo root).

### 8.3 How to keep coverage complete (process)

1. **Single inventory:** Treat §8.1 + §8.2 as the checklist. When you add a turn type or a new early-return branch, update the table in the same PR (or file a follow-up with a §8.2 row).
2. **Mechanical sweep (code):**  
   - `rg "attach_position_snapshots" BackEnd --glob '*.py'` — lists all wiring sites (should grow only when new modules emit snapshots).  
   - `rg '"result_type"' BackEnd/engine/phase_resolution.py` — spot-check that new `result = {` blocks near `return` either call `attach_position_snapshots` or are documented in §8.2.  
   - Same idea for `rim_runner_fast_break.py`, `turn_manager.py`, `opening_tip.py`, `quarter_start.py`.
3. **Cross-check docs:** Align with `Turn_by_Turn_System.md` (or your turn taxonomy): each **TurnType** / `current_turn` that represents live play should map to at least one §8.1 row or an intentional §8.2 gap.
4. **Optional hardening (later):** A shared `finalize_turn_result(..., snapshots)` used by all resolvers would make omissions harder; until then, §8 + code review is the contract.

**Principle:** The ledger is only “universal” if the **inventory** stays next to the code changes.

**Detailed wiring (helpers, files, `source` strings):** see **§12**.

---

## 9. Relationship to `Player.coords` and sync

- Today, `Player.coords` is updated opportunistically and **after** `sync_lineup_coords_from_turn` on append.
- The ledger **does not** replace lineup sync by itself initially; it **records** what the rules should use.
- Long-term: consider **one** derivation path that feeds both **Player.coords** and **snapshots** to avoid drift (implementation detail).

---

## 10. Future work (not in current scope)

- **More dynamic motion:** Loosening skeleton rigidity may move some `skeleton_step` checkpoints to **procedural** or **custom** checkpoints; the schema in §5–7 is intended to absorb that without a redesign.
- **Finer time resolution:** Only if a specific rule needs sub-step or sub-phase data.

---

## 11. Implementation phases (delivery plan)

This section turns the schema into a **sequenced work plan**. Scope boundaries are intentional: ship a thin vertical slice, then expand.

### 11.1 Version 1 — acceptance criteria

**Goal:** Introduce a **position ledger** in code that can **append** `CourtPositionSnapshot` records (§7) during resolution and expose them for **one** high-value path, without yet migrating all location-based rules off `Player.coords`.

**In scope for v1**

| Item | Detail |
|------|--------|
| **Ledger API** | Minimal object or module: `append(snapshot)`, optional `snapshots()` / clear per turn; `schema_version: 1`. |
| **HCO shot path** | Emit at least **one** snapshot immediately **before** `shot_manager.resolve_shot` in the standard HCO shot flow in `phase_resolution`, after `apply_coords_from_animations_list` and `set_shooter_coords_from_skeleton_last_step` (so positions match what shot logic should see). Checkpoint: `checkpoint_kind: skeleton_step` or a dedicated `label` e.g. `pre_resolve_shot` per §5. |
| **Turn attachment (optional)** | If low-risk: attach list to turn result under a key such as `position_snapshots` for debugging (§7.3). |
| **Tests** | At least one **fixture-style** test: fixed skeleton + lineups → assert snapshot count ≥ 1 and **10** position entries at pre-shot checkpoint. |

**Out of scope for v1**

- Full **per-skeleton-step** snapshots for entire HCO play (can be v2).
- **FCP / HCT** checkpoint emission (v2 unless trivial reuse).
- **Fast break** (`fb_logic_*` / `fb_rr_*`) phases (v2+).
- Replacing **`sync_lineup_coords_from_turn`** or unifying all `Player.coords` writers (later).
- **Location-based rule migration** (contests, fouls): consume ledger in v1 only if trivial; otherwise **v2** after ledger is trusted.

**Done when:** v1 acceptance table is satisfied and tests pass in CI.

**Implementation (v1+ breadth):** `BackEnd/utils/position_snapshot_ledger.py` — helpers include `build_skeleton_pre_resolve_shot_snapshot`, `build_fast_break_pre_shot_snapshot`, `build_free_throw_snapshot`, OREB putback/kickout, `build_inbound_destinations_snapshot`, `attach_position_snapshots`. Wired (non-exhaustive list): HCO / FCP / HCT / Final Turn / shot-clock forced shot (`phase_resolution.py`, `turn_manager.py`), standard fast break + Rim Runner (`phase_resolution.py`, `rim_runner_fast_break.py`), free throws (`resolve_free_throw_logic`), OREB (`shared.resolve_offensive_rebound` + `turn_manager.resolve_offensive_rebound_turn`), BASELINE/SIDE inbound (`setup_baseline_inbound`, `setup_side_inbound`), quarter-start BIP (`quarter_start.create_quarter_start_inbound`). Tests: `tests/test_position_snapshot_ledger.py`.

### 11.2 Version 2 — expand checkpoints and consumers

- HCO: optional **per-step** snapshots from skeleton + animator (where rules need mid-play positions).
- FCP / HCT: same pattern as HCO where skeleton-driven.
- Fast break: emit for **`fb_logic_pre_shot`** (standard) and/or **`fb_rr_pre_shot`** (rim runner) first; add other §6.2 phases as rules require.
- Migrate **one class** of location rules to read the ledger (with dual-read or logging guard in dev if needed).

### 11.3 Version 3+ — convergence

- Single derivation path feeding **both** finalized `Player.coords` and snapshots where possible (§9).
- Additional turn types (`turn_terminal` everywhere, then granular as needed).
- Sub-step / sub-phase density only where a **specific** rule demands it (§10).

---

## 12. Implementation reference (implemented features)

This section documents **what is implemented in code today**: module API, builder helpers, where they attach to turn payloads, and the `source` strings used for provenance. Implementation lives primarily in `BackEnd/utils/position_snapshot_ledger.py`.

### 12.1 Core API

| Symbol | Role |
|--------|------|
| `SCHEMA_VERSION` | Integer `1` on every snapshot until a shape change forces a bump. |
| `attach_position_snapshots(turn_result, snapshots)` | Sets `turn_result["position_snapshots"]` to a non-empty list (no-op if list empty). |
| `collect_lineup_positions(off_lineup, def_lineup)` | Builds `player_id` → `{x, y}` from each player’s current `coords` (defaults `(50, 25)` if missing). |

### 12.2 Builder helpers

| Helper | Typical checkpoint | When used |
|--------|-------------------|-----------|
| `build_skeleton_pre_resolve_shot_snapshot` | `skeleton_step`, `label: pre_resolve_shot` | Immediately before `resolve_shot` after coord sync; `turn_type` passed as `HCO`, `FCP`, `HCT`, or `FINAL_TURN` as applicable. |
| `build_hco_pre_resolve_shot_snapshot` | Same (HCO only) | Wrapper calling the above with `turn_type: HCO`, `source: hco_pre_resolve_shot`. |
| `build_fast_break_pre_shot_snapshot` | `fast_break_phase`, `label: pre_resolve_shot` | Standard FB and Rim Runner paths before `resolve_shot`; `phase` string identifies resolver (e.g. `fb_logic_pre_shot`, `fb_rr_pre_shot`). |
| `build_phase_post_stopper_snapshot` | `skeleton_step` with `label: post_stopper_animation` and `outcome_kind`, or `custom` for pure FB | After **non-shot** outcomes (turnover, non-shooting foul) once animations exist and `apply_coords_from_animations_list` has run where applicable. `outcome_kind` is `turnover` or `non_shooting_foul`. For `turn_type: FAST_BREAK` without a skeleton, checkpoint uses `custom_id` `fb_<outcome_kind>`. |
| `build_free_throw_snapshot` | `custom`, `custom_id: ft_attempt` | Free throw attempt layout. |
| `build_oreb_putback_attempt_snapshot` / `build_oreb_kickout_snapshot` | `custom` | OREB putback vs kickout (`shared.py` and `turn_manager` merge paths). |
| `build_inbound_destinations_snapshot` | `custom`, `inbound_setup` | SIDE_INBOUND / BASELINE_INBOUND from `oDestinations` / `dDestinations`. |
| `build_opening_tip_snapshot_from_animations` | `OPENING_TIP`, `opening_tip_animation_finals` | Positions from animation rows (`end` → `jumpCoords` → `start`). |
| `build_positions_from_destinations` | (used inside inbound builder) | Slot-based destinations → player ids. |

### 12.3 Coord sync before snapshots (non-shot skeleton paths)

For HCO / FCP / HCT **stopper** results (turnover or foul), the engine calls `apply_coords_from_animations_list` (`BackEnd/utils/shared.py`) after `skeleton_to_animations` so `Player.coords` matches animation finals before `collect_lineup_positions` runs inside `build_phase_post_stopper_snapshot`. Fast break turnover/foul paths apply the same helper to the fast-break `animations` list when present.

### 12.4 Wiring by file (attach sites)

| File | What gets `position_snapshots` |
|------|-------------------------------|
| `BackEnd/engine/phase_resolution.py` | HCO shot (`pre_resolve_shot`); HCO turnover + O/D non-shooting fouls (`post_stopper`); Final Turn shot; FCP/HCT shot and non-shot (turnover, steal, dead ball, foul); fast break shot (`pre_shot`); FB turnover/foul (`post_stopper`); free throws (`resolve_free_throw_logic`); and-one / FT-related branches as wired. |
| `BackEnd/engine/rim_runner_fast_break.py` | Rim Runner shots (`pre_shot`); high-tier steal (`resolve_turnover_logic` + animations + `post_stopper`); bat-OOB dead ball (`post_stopper`); other RR shot branches. |
| `BackEnd/models/turn_manager.py` | Shot-clock forced shot (`pre_resolve_shot`); SIDE_INBOUND / BASELINE_INBOUND setup payloads; OREB kickout merge; **situational force foul after BIP/SIP** (`hco_situational_force_foul_inbound`); **`_execute_final_turn_force_foul`** (`hco_force_foul_final_turn`). |
| `BackEnd/models/game_manager.py` | **Force foul after DREB** when `force_foul_after_dreb` (`hco_force_foul_after_dreb`). |
| `BackEnd/utils/opening_tip.py` | Opening tip (`opening_tip` source on snapshot). |
| `BackEnd/utils/quarter_start.py` | Quarter-start baseline inbound. |
| `BackEnd/utils/shared.py` | OREB putback / kickout dicts include `position_snapshots` inline where those events are built. |

### 12.5 `source` strings (snapshot provenance)

These appear on snapshot objects for grep-friendly tracing (not exhaustive of every call site):

| `source` (representative) | Meaning |
|---------------------------|--------|
| `hco_pre_resolve_shot` | HCO shot path before `resolve_shot`. |
| `hco_turnover_post_stopper` / `hco_o_foul_post_stopper` / `hco_d_foul_post_stopper` | HCO non-shot stopper outcomes. |
| `fcp_turnover_post_stopper` / `fcp_non_shooting_foul_post_stopper` | FCP non-shot. |
| `hct_turnover_post_stopper` / `hct_non_shooting_foul_post_stopper` | HCT non-shot. |
| `fb_turnover_post_stopper` / `fb_non_shooting_foul_post_stopper` | Standard fast break non-shot (dynamic suffix on FB path). |
| `fb_rr_turnover_post_stopper` / `fb_rr_bat_oob_post_stopper` | Rim Runner steal tier and batted ball OOB. |
| `hco_situational_force_foul_inbound` | Situational “quick foul” after inbound (`situational_force_foul_pending`). Victim `coords` set from pending payload before snapshot. |
| `hco_force_foul_final_turn` | Final-turn force foul (`_execute_final_turn_force_foul`); victim/defender picks use live `Player.coords`. |
| `hco_force_foul_after_dreb` | Force foul injected after DREB branch; rebounder/defender picks use synced `Player.coords` (fallback: `defense_rebounder_coords` / bounce). |
| `opening_tip` | Opening tip animation finals. |
| `free_throw_attempt` | FT snapshot helper. |
| Inbound / OREB | See `build_inbound_destinations_snapshot` and OREB builder `source` arguments at call sites. |

### 12.6 Tests and maintenance tooling

| Artifact | Purpose |
|----------|---------|
| `tests/test_position_snapshot_ledger.py` | Unit tests for ledger helpers (lineups, inbound destinations, opening tip, `build_phase_post_stopper_snapshot` shapes). |
| `scripts/audit_position_snapshots.py` | Lists `attach_position_snapshots` usage across `BackEnd/` and counts `position_snapshots` references; suggested greps for manual review (see §8.3). |

### 12.7 Relationship to end-of-turn `Player.coords`

`GameManager._append_turn` calls `sync_lineup_coords_from_turn` after appending a turn. That updates **live** `Player.coords` from the turn’s animations and overlays; it does **not** by itself add `position_snapshots`. The snapshot ledger is the **explicit** per-turn record for consumers that need layout on the payload; end-of-turn sync keeps sim state aligned for the next turn (see §9).

---

## 13. Document history

| Date | Change |
|------|--------|
| 2025-03-24 | Initial working spec: checkpoint model, `fast_break_phase` enum v0, snapshot schema v1. |
| 2025-03-24 | §6.2 rewritten: `fast_break_phase` IDs aligned to `resolve_fast_break_logic` vs `resolve_rim_runner_fast_break` (anchors, `fb_roles` keys). |
| 2025-03-24 | §11 added: implementation phases (v1–v3+), acceptance criteria for v1. |
| 2025-03-24 | v1 implemented: `position_snapshot_ledger.py`, HCO `position_snapshots` hook, tests. |
| 2025-03-24 | Broad coverage: FCP/HCT, FB + Rim Runner, FT, OREB, BIP/SIP, quarter-start BIP, Final Turn, shot clock. |
| 2026-03-24 | §8 replaced: full coverage matrix, §8.2 known gaps (e.g. FB `DEFENSIVE_STOP`), §8.3 maintenance process; non-shooting fouls explicitly listed in §8.1; `scripts/audit_position_snapshots.py`. |
| 2026-03-24 | **§12 added:** implementation reference (helpers, file wiring, `source` strings, force-foul paths, tests/audit); §12 Document history renumbered to §13. |
| 2026-06-13 | **Status banner reconciled** with §8/§12: emission side is implemented and broadly wired (with tests + audit script); reframed remaining work as consumer adoption (§9, §11.2–11.3) and the §8.2 coverage gaps, rather than "engine work in progress." |
