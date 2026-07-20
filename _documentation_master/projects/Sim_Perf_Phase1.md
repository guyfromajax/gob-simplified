# Sim Optimization Phase 1 — Seed, Dead Code, Defender-Grid Reuse

**Date:** 2026-07-20 · **Baseline commit:** `dbb82a32d` · **Phase 1 HEAD:** `ef9339e5a`
**Reference:** `reports/perf/refstats_baseA_20260720_110755.csv` (seed 20260720, md5 `90ac5fc0…`)

## Status

| Step | Outcome |
|---|---|
| 1 — Seed the RNG | ✅ done, verified, committed `22e67e792` |
| 2 — Seeded reference set | ✅ done, committed `22e67e792` |
| 3 — Dead `_collect_player_ids` traversal | ✅ EXACT MATCH 166/166, committed `ef9339e5a` |
| 4a — 216-stamps investigation | ✅ answered (premise disproved) |
| 4b/4c — Defender-grid reuse | ⛔ **STOPPED** — failed exact diff, root-caused |
| Side item — stray `bulk_write` | ⛔ **STOPPED** — failed exact diff, same root cause |
| 5 — Re-measure | ⚠️ partial (Step 3 only is committed) |

---

## 1. Seeding

All sim RNG flows through the **global `random` module** (80 `import random` sites). numpy is
not in the sim path (only `services/recruit_image.py`); `secrets` is auth-only. No per-instance
`Random` objects. `random.choice(list(...))` sites iterate dicts (insertion-ordered), not sets.

Optional `seed` param added to both entry points, defaulting to `None` so production is
unchanged:
- `_run_franchise_cpu_full_simulation_core(..., seed=None)`
- `run_ps_full_simulation(..., seed=None)`

The harness derives `seed = base + index` per game, so a game reproduces independently of batch
size, and re-execs with `PYTHONHASHSEED=0` so string-hash-dependent set iteration is stable
across processes.

**Proof:** full seeded 63 CPU + 20 PS week run twice → byte-identical, md5
`90ac5fc00862a22f9a031d560f05f3d2`.

**Controls** (a passing diff is meaningless without these):
| Control | Result |
|---|---|
| Different seed (999 vs 12345) | ✅ diverges — seed is live |
| 2-game run vs first 2 rows of 4-game run | ✅ matches — per-game seeds order-independent |
| `wall_s` removed from refstats | timing noise can't mask a real diff |

**Caveat:** `--seed` with `--workers > 1` is NOT reproducible (global RNG shared across threads);
the harness warns. Exact diffs require `--workers 1`.

## 2. Reference set

`reports/perf/refstats_baseA_20260720_110755.csv` — 166 rows (126 CPU + 40 PS), 2 per game,
tagged with seed + commit, no timing columns. Replaces the distributional anchor with an exact
one.

## 3. Dead traversal — VERIFIED

`summarize_game_state` unconditionally ran `_collect_player_ids(game.turns, …)` — **1,245,210
recursive calls/game** — but its only consumer is guarded by
`has_fresh_turns = len(game.turns) > 0 and not exclude_animations`. Sims always pass
`exclude_animations=True`. Guarded on exactly that condition.

**Verified: EXACT MATCH, 166/166 rows.** Phase effect: `serialize.summary` **10.47s → 0.11s**
(−99%) over the week.

## 4a. The 216 stamps — the premise was wrong

Instrumented all four build sites over 2 games (623 builds / 331 turns = **1.88/turn**):

| Call site | Builds/turn | Redundant |
|---|---|---|
| `phase_resolution.py:6242` (pre-walk) | 0.75 | 0% |
| `step_state.build_step_states` (post-emit) | 0.65 | **59.6%** |
| `phase_resolution.py:5675` (coverage pass) | 0.44 | 0% |
| `phase_resolution.py:6872` (recalibration) | 0.04 | 0% |

**Execution order** (BSS is last in 100% of observed turns):
```
 106x  pr:6242 -> pr:5675 -> BSS
  72x  pr:6242 -> BSS
  25x  pr:6242 -> pr:6242 -> BSS
  14x  pr:6242 -> pr:6242 -> pr:5675 -> BSS
```

**The three `_stamp_contest_defender_grid` sites are behaviorally distinct** — each sees a
different skeleton state (pre-walk / post-expansion / post-recalibration), exactly as the
docstring claims. Consolidating them would change behavior. Not touched.

> **Methodology note:** the first pass reported "100% distinct inputs," which was wrong. The hash
> included `step["_step_state"]` — the stamp's *own output*, written into its input skeleton — so
> every re-stamp looked different by construction. Stripping that field produced the table above.

## 4b/4c. Grid reuse — STOPPED, not tuned

**Change (parked, not committed):** in `build_step_states`, when there is no render stash and
`_is_full_simulation`, reuse the grid already stamped on the steps instead of rebuilding.

**Result: FAILED — 166/166 rows differ, every column.** Stopped per instruction; reference
untouched, nothing tuned.

### Root cause: RNG-stream displacement, not a hidden consumer

> `Animator.compute_defender_grid` consumes RNG on **100% of calls (234/234 measured)**.

Defender placement uses RNG (the documented ~2px shade). Removing one call per HCO turn shifts
the global stream for everything downstream, so under a fixed seed **total divergence is
guaranteed regardless of whether the removed work mattered.** Step 3 passed only because
`_collect_player_ids` consumes no RNG.

**⚠️ The exact-diff test cannot distinguish "removed dead work" from "changed behavior" for any
change that removes RNG-consuming work.** This affects most remaining targets, including
`_point_in_polygon`.

Independent evidence the work is dead (unchanged by the diff failure):
- `build_step_states` runs **last** — empirically last in 100% of turn sequences
- its only reader, `_hco_step_def_xy`, runs **earlier** in the turn
- the return value is **discarded** at the call site (`turn_manager.py:3935`)
- sim summaries contain no `turns`, no `skeleton`, no `_step_state`

Supporting (not proof): aggregate distributions over 126 team-rows are statistically
indistinguishable — all |z| < 1.05 (`final_score` +0.76, `FG_pct` +0.67, `TO` −0.83).

### What it would buy

| | baseline | step 3 only | step 3 + 4b |
|---|---|---|---|
| `serialize.summary` | 10.47s | 0.11s | 0.11s |
| `anim.position_defenders` | 103.81s | 110.97s | **83.35s** (−24.9%) |
| grid build calls | 24,470 | 24,523 | **16,490** (−32.8%) |
| total wall | 295.9s | 301.7s | 266.5s |

**Wall-clock caveat:** step-3-only measured *slower* than baseline despite doing strictly less
work. Run-to-run variance on this host is ~±5%; **wall deltas under ~15s are not meaningful.**
Trust the phase and call-count rows.

## Side item — stray `bulk_write` — STOPPED

`GameManager._update_position_ratings` writes `position_ratings` to `players_collection` when
`not is_franchise`. PS uses `mode="single"` so it fires, but PS rosters come from FPD/FRD docs —
**0 of 12 sampled roster IDs exist in `players`**, so the write matches nothing. Guard added via
a new `TeamManager.is_synthetic_roster` (`roster_override is not None`).

**Result: FAILED — 38/166 rows differ.** The scope is a perfect diagnostic: **0/126 CPU rows
changed, 38/40 PS rows changed** — exactly the affected population.

### Root cause: the Mongo driver is in the sim's RNG stream

> `pymongo`'s `bulk_write` **consumes the global `random` module**. `find_one` does not.
> Consumption is deterministic in amount (same seed → same subsequent draw across trials), which
> is why the determinism proof still passed.

This is a correctness concern beyond verification: **sim outcomes currently depend on database
write activity.** Any change to how many writes occur shifts the basketball. It also means
determinism is hostage to driver internals (retries, server selection, topology changes).

## PS roster resolution (deliverable 5)

PS rosters resolve from `franchise_players_data` / `franchise_recruits_data` via
`_player_payload_from_roster_slot` — **never** from `players_collection`, which is why 0 IDs
matched. Attributes populate correctly (20 keys/player, 0 empty). The sampled roster was entirely
`frd` (recruits) with `ST` spanning 11–69.

Team attributes are fixed constants (`ps_team_attributes`): `team_chemistry=20`,
`shot_threshold=50`, `rebound_modifier=0.2`, and eight `randint(-5,5)` rolls.

**Confirmed with product owner: PS teams are intended to be low-rated synthetic scrubs.** The
CPU-vs-PS gap (FG% 53.1 vs 30.3, 3P% 50.0 vs 16.5, REB 28.4 vs 48.0) is the expected consequence
of low-rated recruits plus fixed low chemistry. **Working as intended — no defect.**

## Additions

### 1. 4b verification blind spot

**(a) Does anything persist sim-path step-state grids?** No. The grid lives only on
`result["skeleton"]["steps"][i]["_step_state"]["defense"]`. `build_step_states`' return value is
discarded; nothing projects it into `animation_steps`; `result["step_states"]` is never set
(unlike `pressure_step_states`). `summarize_game_state(exclude_animations=True)` sets `turns=[]`
before the only DB write. Empirically confirmed: a sim summary contains no `turns`, `skeleton`,
or `_step_state`.

**(b) Does any path read them later?** No current consumer — the module docstring says so
("no consumer reads StepState.defense yet") and the only reader of `_step_state["defense"]`
(`_hco_step_def_xy`) runs earlier in the same turn. Planned consumers exist on the StepState
roadmap, hence the in-code warning.

**Semantic change documented at the reuse site** (parked with the change): sim-path step states
would record **stamp-time** geometry, not the post-emit rebuild — per step, the most recent stamp
that touched it. Steps created *after* the last stamp carry `{}` where the old rebuild produced
coordinates. Deliberate: stamp-time geometry is what the contest actually judged against; the
post-emit rebuild was a fourth snapshot no decision was made on.

### 2. Live-path build counts

Per animated HCO turn **today** (static map + the same per-turn rates):

| Source | Builds |
|---|---|
| 3 × `_stamp_contest_defender_grid` | ~1.23 |
| HCO emit (`skeleton_to_animations`, the real draw) | 1 |
| `build_step_states` — render-stash branch | **0** (extraction, not a build) |
| `_diagnose` → `_render_grids` → `skeleton_to_animations` | **1** (observability only) |

**After 4b: unchanged — zero difference on the live path.** The change touches only the
`elif is_full_sim` branch, which never executes on an animated game.

Worth noting: `_diagnose` performs a **full animation redraw on every live HCO turn** purely for
diagnostics. Not touched (out of scope).

### 3. Which stamp does the reuse stash?

Per **step**, not per turn: the most recent `_stamp_contest_defender_grid` to touch that step
object — the coverage-pass stamp `phase_resolution.py:5675` where it ran (**53.7%** of turns),
otherwise the pre-walk stamp `:6242`. In 46.3% of turns the skeleton changed after the last
stamp, so some steps carry no grid.

**Why that's the right representation:** it is the geometry the interception contest actually
judged against — the state that determined the turn's outcome. The old post-emit rebuild
represented a snapshot no decision was ever made on.

## 6. Found but deliberately NOT touched

| Finding | Why not |
|---|---|
| `_point_in_polygon` — 680,558 calls/game, 1.77s self / 2.38s cumulative | Explicitly out of scope |
| Global RNG shared with pymongo | Needs its own change + verification pass; see recommendation |
| Threading at 39% efficiency (4 workers → 1.57×) | Out of scope |
| `_diagnose` full redraw per live HCO turn | Live-path only; out of scope |
| `convert_players` — 1,176,221 calls/game (`turn_manager.py:1442`) | Not investigated |
| `plays` collection ~26 round trips/game | Already memoized once; mostly local-latency artifact |
| Three stamp sites | 4a proved behaviorally distinct |
| CPU FG% 53.1 / 3P% 50.0 above target | Basketball tuning, explicitly out of scope |

## Recommendation

Both blocked items fail for the same reason: **the sim's RNG stream is shared with everything
else in the process, including the Mongo driver.** Until that is isolated, exact-diff
verification only works for changes that remove non-RNG-consuming work.

Suggested next step (its own phase, its own verification): give the sim a dedicated `Random`
instance so engine randomness is independent of DB activity and of how much geometry gets built.
That restores exact-diff power for all remaining optimization work and removes a real fragility —
sim outcomes should not depend on how many documents the driver wrote.
