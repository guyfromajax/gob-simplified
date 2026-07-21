# Sim Performance Baseline — Full Turn-by-Turn (CPU + Practice Squad)

**Measured:** 2026-07-20 · **Commit:** `dbb82a32d` (develop) · **DB:** `gob-staging` (Atlas)
**Host:** macOS x86_64, Python 3.13.5 · **Measurement only — no optimization applied.**

---

## Reading this bundle

```
README.md                        <- this report; start here
data/
  phase_breakdown_week_seq_*.json   63-game CPU week + 20 PS games, sequential (main result)
  phase_breakdown_week_par4_*.json  same week at 4 workers (production parallelism)
  refstats_week_seq_*.csv/.json     reference stat set, 166 rows (126 CPU + 40 PS)
profiles/
  cprofile_uninstrumented_single_game.txt   use THIS for caller graphs (no wrappers in chain)
  cprofile_instrumented_single_game.txt     same game with phase probes installed
methodology/
  sim_profiler.py                  the instrumentation (pure monkeypatch, no sim-file edits)
  perf_sim_baseline.py             the headless week runner
```

**Three things to know before interpreting the numbers:**

1. **`self_s` is exclusive time, not inclusive.** Phases nest; each records elapsed minus time in
   child spans, so the phase table sums to 100% with no double counting. `incl_s` is also present
   but a recursive phase over-counts there — rank by `self_s`.
2. **Database time is inflated ~10× vs production.** Measured from a laptop at 26.9 ms Atlas RTT;
   Railway is colocated at 1–3 ms. The 37% DB row is ~4% in production. See the Railway
   adjustment table — it changes which bottleneck is #1.
3. **Sims are not seeded.** The reference stat set is a *distributional* anchor (compare means
   and spreads across the 126 CPU rows), not row-by-row diffable.

Binary `.prof` files are omitted (unreadable as attachments); they live in `reports/perf/` in the
repo if function-level re-analysis is needed.

## How to re-run

```bash
# full week, sequential (clean phase attribution) + cProfile
python3 scripts/perf_sim_baseline.py --franchise 6a28436c98dbd04e902eee09 --week 7 \
  --games 63 --mode both --ps-franchise 6a5e1f0e517ebcc58d981675 --ps-week 3 \
  --workers 1 --cprofile --tag week_seq

# production-shaped parallelism
python3 scripts/perf_sim_baseline.py --franchise 6a28436c98dbd04e902eee09 --week 7 \
  --games 63 --workers 4 --tag week_par4
```

Instrumentation is **pure monkeypatch** — no probe code in any sim file. Inert unless
`GOB_SIM_PROFILE=1`. To remove entirely: delete `BackEnd/utils/sim_profiler.py` and
`scripts/perf_sim_baseline.py`.

## Wall clock — 63-game CPU week

| Run | Wall | per-game min / median / mean / p90 / max |
|---|---|---|
| Sequential (1 worker) | **295.9 s** (4.9 min) | 4.03 / 4.71 / 4.70 / 5.16 / 5.63 s |
| Parallel (4 workers = prod default) | **189.0 s** (3.2 min) | 6.13 / 11.67 / 11.80 / 13.34 / 16.17 s |

Distribution is tight — no outlier game type. Sum of per-game CPU at 4 workers is 743.6 s
vs 295.9 s sequential: the same work takes **2.5× longer per game** under threading.

## Phase breakdown — CPU week, sequential (295.9 s total)

| Phase | Self s | % |
|---|---|---|
| Animation + defender geometry | 111.5 | **37.7%** |
| Database (reads) | 109.6 | **37.0%** |
| Core possession / game logic | 56.6 | 19.1% |
| Serialization / response | 10.5 | 3.5% |
| Schema step emission | 4.3 | 1.5% |
| Per-game setup | 3.0 | 1.0% |
| Other / unprofiled | 0.5 | 0.2% |

Top individual phases: `anim.position_defenders` 103.8 s (35.1%) · `db.read.plays` 71.1 s
(24.0%) · `core.micro_turn` 31.6 s (10.7%) · `core.hco` 17.0 s (5.8%) · `serialize.summary`
10.5 s (3.5%).

### Railway adjustment (important)

Atlas RTT from this laptop: **median 26.9 ms** (min 23.1). A Railway deploy colocated with
Atlas is typically 1–3 ms, so DB time here is inflated **~10×**. Normalizing to 2 ms RTT:

| Phase | % local | % Railway-adjusted |
|---|---|---|
| Animation + defender geometry | 37.7% | **57.3%** |
| Core possession / game logic | 19.1% | **29.1%** |
| Database | 37.0% | ~4% |
| Serialization | 3.5% | 5.4% |

Estimated Railway sequential week: **~195 s (3.09 s/game)**. Relative ordering of the
non-DB phases holds; the DB row is the only one that moves materially.

## Bottlenecks (ranked)

**1. Defender-grid geometry is computed twice per turn — 37.7% local / ~57% adjusted.**
Animation *packets* are already correctly skipped in full sim (`capture_halfcourt_animation`
et al. early-return at `animator.py:829` etc. — all measured at ~0.00 s). The cost is
`compute_defender_grid`, which deliberately bypasses the full-sim skip because interception
geometry is an outcome, not a render. cProfile confirms **two independent callers per turn**:

- `phase_resolution.py:5618` `_stamp_contest_defender_grid` — 216 calls/game
- `step_state.py:22` `build_step_states` — 121 calls/game

Each does a `deepcopy` of the skeleton then a full `_build_all_animations`. Leaf cost is zone
geometry: `_point_in_polygon` (`shared_defense.py:390`) at **680,558 calls/game**, 1.77 s self /
2.38 s cumulative, reached via `assign_all_zone_defenders` → `_point_in_zone`.
This duplication is already flagged on the StepState roadmap as the Stage-2 residual
("consolidate walk-time contest → retire `_hco_contest_final_skeleton`").

**2. `plays` collection reads — 71.1 s local (24.0%), ~7 s Railway-adjusted.**
1,609 cursor fetches / 63 games ≈ 26 round trips per game. The per-game memo
(`_playcall_memo`, `phase_resolution.py:9632`) already cut this from ~430; what remains is one
lookup per *distinct* playcall per game, and it is deliberately per-game (not process-wide) so a
mid-season play rename is noticed. Mostly a local-latency artifact — real but much smaller on Railway.

**3. Threading returns far less than it looks — 4 workers buy 1.57×, not 4×.**
295.9 s → 189.0 s at `FRANCHISE_CPU_SIM_MAX_WORKERS=4` = **39% parallel efficiency**. The sim is
CPU-bound pure Python (polygon math, deepcopy), so the GIL serializes it; only DB waits overlap.
Adding workers will not help much, and removing DB latency (Railway) makes it *worse*, since the
overlappable fraction shrinks.

## Surprises

- **Animation packet construction is not the bottleneck** — it is already fully skipped. The
  expensive thing wearing its name is sim-required contest geometry.
- **Dead work in serialization.** `summarize_game_state` unconditionally runs
  `_collect_player_ids(game.turns, …)` (`shared.py:2426`) — **1,245,210 recursive calls/game** —
  but the result is only consumed under `has_fresh_turns = len(game.turns) > 0 and not
  exclude_animations` (`shared.py:2468`). Sims always pass `exclude_animations=True`, so the
  traversal is **100% discarded**. That is most of the 10.5 s (3.5%) serialization row.
- **`convert_players`** (`turn_manager.py:1442`) — 1,176,221 calls/game.
- **PS writes to Mongo mid-sim**, contrary to "no DB writes": `GameManager.__init__`
  (`game_manager.py:114`) calls `players_collection.bulk_write` when `not is_franchise`. PS uses
  `mode="single"` so it fires (20/20 games); CPU uses `mode="franchise"` and skips it. Verified
  **0 of 12 PS roster IDs exist in `players`** — the writes match nothing and the value is
  deterministically recomputed, so impact is a wasted round trip, not data change.

## CPU vs Practice Squad delta

| | CPU full | Practice Squad |
|---|---|---|
| Games measured | 63 | 20 |
| Mean / median per game | 4.70 / 4.71 s | **5.20 / 5.15 s** |
| Animation + defender geometry | 37.7% | 43.1% |
| Database reads | 37.0% | 34.3% |
| Core possession logic | 19.1% | 17.2% |
| Database writes | 0% | 0.8% (bulk_write) |

**PS is ~11% slower per game** with the same phase shape — same engine, same `simulate_quarter`
loop. The gap is more possessions/turns per game (202 vs 194 micro-turns) and more defender-grid
builds, not a different code path. **Conclusion: no separate optimization track needed.** Any fix
to the defender-grid duplication benefits both roughly equally.

Note PS runs **sequentially, one game per HTTP call** (`max_games=1`), so it never contends with
the CPU week's thread pool — but it does run concurrently with user training requests.

### Basketball delta (not perf, but visible in the reference set)

| Mean per team | CPU | PS |
|---|---|---|
| Score | 86.9 | 57.5 |
| FG% | 53.1 | 30.3 |
| 3P% | 50.0 | 16.5 |
| FTA | 10.0 | 20.4 |
| REB | 28.4 | 48.0 |

CPU FG% 53.1 / 3P% 50.0 remains well above target (known open issue). PS synthetic teams produce
very different basketball — worth a separate look.

## Artifacts

| File | What |
|---|---|
| `reports/perf/phase_breakdown_week_seq_20260720_102023.json` | Phase timings, sequential week + PS |
| `reports/perf/phase_breakdown_week_par4_20260720_*.json` | 4-worker week |
| `reports/perf/refstats_week_seq_20260720_102023.csv` / `.json` | **Reference stat set** — 166 rows (126 CPU + 40 PS), 2/game |
| `reports/perf/cprofile_week_seq_20260720_102023.prof` / `.txt` | cProfile, instrumented |
| `reports/perf/cprofile_clean_20260720_103044.prof` / `.txt` | cProfile, **uninstrumented** — use for caller graphs |

Reference stat set columns: `final_score, possessions, FGM/FGA/FG_pct, TPM/TPA/TP_pct,
FTM/FTA/FT_pct, TO, OREB/DREB/REB, AST, STL, BLK, PF` per team per game, tagged with commit +
timestamp. Diff future runs against it to confirm the basketball didn't change.

**Caveat:** sims are RNG-driven and not seeded, so the reference set is a *distributional* anchor
(means, spreads), not row-by-row identical. Compare aggregates across the 126 CPU rows.
