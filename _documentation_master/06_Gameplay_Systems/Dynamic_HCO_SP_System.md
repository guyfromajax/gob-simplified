## Dynamic HCO Set Plays System ✅ **SHIPPING (flagged)** (June 2026)

**Feature gate:** env var `GOB_DYNAMIC_HCO_SETPLAY` (`1`/`true`/`yes`/`on`), independent of motion's `GOB_DYNAMIC_HCO_MOTION`. Off → legacy set-play path (up-front outcome tables + static variant skeleton). This doc describes the ON path. Companion brief: [projects/Dynamic_HCO_SP_Brief.md](../projects/Dynamic_HCO_SP_Brief.md). Sibling system: [Dynamic_HCO_System.md](Dynamic_HCO_System.md) — set plays **reuse motion's machinery**; only the differences below are new.

---

### Model: OVERLAY

The up-front **variant roll** (`successful` / `mid_play_change` / `contested` / `broken`) STILL selects the skeleton. The dynamic per-step layer overlays on the chosen variant skeleton. `get_hco_skeleton` runs `_apply_set_play_runtime_position_mapping`, so the variant skeleton arrives **position-keyed** (PG/SG/…) just like motion's `base_loop` — the motion helpers walk it directly, no slot mapping.

**Scope:** half-court offense, set plays, **man + zone** defense.

---

### Where it hooks in

`resolve_half_court_offense_logic` (BackEnd/engine/phase_resolution.py):

```
resolve_hco_outcome(game, skeleton)              # set_play + flag → skips up-front event tables (skip_upfront_events); variant STILL chosen
  ↓ result == "SHOT"
final_skeleton = get_hco_skeleton(variant)       # executed variant skeleton, then deepcopy
_resolve_hco_moment_walk(final_skeleton, …)      # STAGE C: per-step steal/foul/TO (man+zone); hard outcome → overrides result, pre-empts shot
  ↓ result still "SHOT"
_resolve_setplay_offense_shot_dynamic(…)         # STAGE B: the per-step offense walk (routed in the SHOT path via the shared motion block)
  ↓ result != "SHOT": existing non-shot resolution + apply_stopper_system_to_skeleton
skeleton_step_emitter.build_skeleton_animation_steps(…)   # UESS render
```

The moment walk runs **after** the variant skeleton is chosen + deep-copied (so it reads the actual play and reach-in indices align) and **before** the shot-clock block (so a hard outcome correctly pre-empts the would-be shot). Routing reuses the motion roles-update block: the set-play result has the same contract, so `roles["shooter"/"motion_shot_type"/"motion_playcall"]` + passer re-derivation + dish-interception finalize all apply unchanged.

---

### The three differences from motion

| | Motion | Set play |
|---|---|---|
| **offense_reads** | rolled per turn from `alterations` | **forced `False`** — offense never proactively subtle-moves; only the defense can force one |
| **post-forced-subtle** | resume skeleton silently | BH reads shoot / hot-read pass / **hold** → `_setplay_recovery_roll` |
| **events** | per-step moment (Dynamic Motion) | same per-step moment, replacing the set-play up-front tables |

With `offense_reads=False`, `decide_step_action` only acts under defense pressure (Condition 3, ball-handling battle): defense wins → `_disruption_branch` (subtle / freelance / advance); else advance. The **universal `should_shoot`** hot read still runs every step (not only after a subtle).

**Forced-subtle progression:** defense forces a subtle → `build_subtle_beat` (BH + non-BH reads) → shot-clock-expiry backstop → post-subtle `should_shoot` (shoot **or** hot-read dish). If no shot, the BH holds and rolls recovery:

```
offense_score = (team_chemistry + offensive_efficiency) × randint(1,6)   # offense team
defense_score = (team_chemistry + defensive_efficiency) × randint(1,6)   # defense team
offense_score > defense_score → re-enter skeleton at next defined step (players pop back to spots)
                         else → forced freelance (_resolve_freelance)
```

A direct `FREELANCE_FORCED` from the disruption branch (no subtle) goes straight to freelance.

---

### Reused from motion (no rebuild)

`should_shoot` + truly-open gate (`_hco_blocked_dish_targets`) + dish interception · `decide_step_action`/`_disruption_branch` · `build_subtle_beat` (non-BH reads) · `_execute_motion_decision` · `_resolve_freelance` · `_resolve_hco_moment_walk` (man + zone). New code is only `_resolve_setplay_offense_shot_dynamic` (the walk with the two deltas above), `_setplay_recovery_roll`, the flag gate, and the routing branches.

---

### Constraints

Behind the flag (default off). UESS: backend authoritative, FE pure renderer (all logic + RNG backend-side, SS&S-reproducible). The dynamic resolver appends base step dicts verbatim, so custom keys (`_subtle_movement`, `reach_in_def_id`, `_hot_read_sfx`) survive into the emitted skeleton.

---

### Tests + prototype

- `tests/test_setplay_dynamic_gate.py` — flag gate + recovery-roll formula (Stage A).
- `tests/test_setplay_dynamic_resolver.py` — the walk: offense_reads forced False, universal hot read, forced-subtle → re-enter vs freelance, FREELANCE_FORCED, shot-clock backstop (Stage B/C).
- `dynamic_setplay_prototype.py` — seeded Monte-Carlo: recovery-roll grid (monotonic) + walk path distribution (validates the offense never self-initiates a subtle). Run: `MONGO_URI="" MONGO_DB_NAME="gob-test" python3 dynamic_setplay_prototype.py`.

Run tests: `MONGO_URI="" MONGO_DB_NAME="gob-test" python3 -m pytest tests/test_setplay_dynamic_*.py -q -o addopts=""`.
