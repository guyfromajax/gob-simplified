# Sim Optimization Phase 2 — RNG Isolation, Grid Reuse, Write Guard

**Date:** 2026-07-20 · **Phase 1 HEAD:** `70c4a49ee` · **Phase 2 HEAD:** `b3ae6ad32`
**Reference anchor:** `reports/perf/refstats_postB_20260720_20260720_153720.csv` (seed 20260720)

## Status

| Step | Outcome | Commit |
|---|---|---|
| B — dedicated sim RNG | ✅ verified | `b269732fa` |
| Standing global-draw guard | ✅ verified it fires | `b269732fa` |
| New seeded reference anchor | ✅ cut post-B | `b269732fa` |
| Poison-stash test | ✅ 166/166 byte-identical | `4da067d87` |
| Defender-grid reuse (Phase 1's 4b) | ✅ verified | `4da067d87` |
| `bulk_write` guard | ✅ **EXACT MATCH 166/166** | `b3ae6ad32` |

---

## 1. The correctness issue, resolved

**Before:** the engine drew from the global `random` module — the same stream every
other library in the process uses. Measured: `pymongo`'s `bulk_write` consumes the
global stream (`find_one` does not). A Mongo write matching **zero documents** shifted
final scores under a fixed seed.

**After:** engine randomness comes from a dedicated `Random` instance
(`BackEnd/utils/sim_random.py`). 52 modules bind it in place of the stdlib module via a
one-line import swap, so every call site is unchanged:

```python
from BackEnd.utils.sim_random import sim_rng as random
```

Scope came from measurement, not grep — an audit recorded which modules actually draw
during a sim, and a re-audit proves none remain:

| Global-module draws (2 CPU + 1 PS game) | BackEnd | third-party |
|---|---|---|
| before | 214,801 | 1 (`pymongo.message`) |
| after | **0** | 1 (`pymongo.message`) |

### Proof the coupling is gone

The `bulk_write` guard is the same change in both phases:

| | rows differing |
|---|---|
| Phase 1 (shared stream) | **38/166** — 0/126 CPU, 38/40 PS (exactly the affected population) |
| Phase 2 (isolated stream) | **0/166 — EXACT MATCH** |

Nothing changed between those runs but the RNG topology.

### Design note — plain instance, not a thread-local proxy

A `__getattr__`-forwarding proxy would give per-thread streams (making `--workers > 1`
reproducible) but measured **+30% per draw**; the engine makes ~82k draws/game. A plain
instance is **+1.7%** (noise), because the stdlib's module-level functions are themselves
bound methods of a hidden module-level `Random`.

**Consequence:** threads still share the sim stream, exactly as they shared the global
one. Seeded reproducibility still requires `--workers 1`. Unchanged, not improved.

## 2. Standing global-draw guard

`install_global_draw_guard()` wraps the stdlib module's 19 draw functions and records any
call whose immediate caller lives under `BackEnd`, keyed `module:function:lineno`.
`perf_sim_baseline.py` arms it on every run and exits 1 with the offending sites if the
tally is non-empty.

**Why:** the conversion is only proven against branches the verification weeks exercised.
A draw site on a rare branch (overtime, ejections, edge events) would still be on the
global module and would surface later as an intermittent byte-identical failure with no
obvious cause. The guard converts that into an immediate, attributable catch.

Verified the guard *fires* rather than assuming it would: a synthetic stray module was
caught and attributed to `BackEnd.engine.fake_rare_branch:_stray_branch:4`.

`--allow-global-draws` exists solely for pre-isolation comparison arms.

**Not covered:** the guard is armed in the harness, not in production. A rare-branch draw
that only occurs in a live Railway game is caught only if a verification run hits that
branch. Wiring it into app startup would close this — a production behavior change, not
made here.

## 3. Verification method — and its limits

### Poison-stash: the instrument for draw-count changes

An exact diff **cannot** validate a change that removes draws from the sim's own stream:
removing them shifts every downstream result by construction, whether or not the removed
work mattered. Phase 1 saw exactly this (166/166 rows differed for a change that turned
out to be dead work).

The poison test separates the two questions:

1. Keep the work executing → **draw count identical to the reference**
2. Replace only the *stashed value* with a structurally valid but absurd sentinel
   (`{x: -9999, y: -9999}`)
3. Byte-identical output ⇒ nothing reads it

Result for the defender grid: **166/166 byte-identical.**

**Blind spot, recorded deliberately:** the test is only as strong as the sentinel's
detectability. `-9999` catches any consumer doing arithmetic; it would **not** catch one
that merely checks for key presence. No such consumer exists today (the sole reader,
`_hco_step_def_xy`, runs earlier in the turn), and the structural evidence is independent
— but this is not unconditional proof.

### ▶ STANDING RULE

> **A change that alters the number of draws taken from the sim stream cannot be verified
> by exact diff.** Verify it with a poison test (keep the draws, poison the output) plus a
> multi-seed distributional comparison. Exact diff remains valid only for changes that
> remove or alter non-drawing work (e.g. Phase 1 Step 3, the dead traversal).

### Distributional standard

5 seeds per arm, 630 CPU + 200 PS team-rows each, all 19 refstats columns, Welch's t on
means plus F-ratio on variances. Threshold |t| > 3.

| Comparison | Result |
|---|---|
| pre-B vs post-B | ✅ no column beyond \|t\|>3; variance ratios ~1.0 |
| post-B vs +4b | ✅ no column beyond \|t\|>3 |

Largest mover across all comparisons: `BLK`, t = −2.22 (pre-B vs post-B), then flat
(t = 0.00) for 4b. Read as noise — near-zero-mean stat, and one |t|>2 is expected across
38 comparisons. Separately worth noting: CPU teams average **0.21 blocks/game**, which is
not plausible basketball and is why that column is statistically fragile. Tuning issue,
out of scope.

## 4. Timing — old vs new

Median of **3 runs** (host run-to-run variance is ~±5%; single-run wall deltas under
~15s are not meaningful).

| | Phase 1 baseline | Phase 2 | Δ |
|---|---|---|---|
| CPU week (63 games) | 295.9 s | **246.0 s** | **−16.9%** |
| CPU per-game median | 4.71 s | **3.91 s** | −17.0% |
| PS (20 games) | 104.1 s | **78.5 s** | **−24.6%** |
| PS per-game median | 5.15 s | **3.90 s** | −24.3% |

Phase-level (medians, CPU week):

| Phase | Baseline | Phase 2 | % local | % Railway-adj |
|---|---|---|---|---|
| Animation + defender geometry | 111.5 s | **78.2 s** | 31.8% | **50.4%** |
| Database (reads) | 109.6 s | 98.2 s | 39.9% | 4.7% |
| Core possession / game logic | 56.6 s | 57.1 s | 23.2% | 36.8% |
| Serialization | 10.5 s | **0.12 s** | 0.0% | 0.1% |
| Schema step emission | 4.3 s | 4.9 s | 2.0% | 3.2% |
| Per-game setup | 3.0 s | 3.1 s | 1.3% | 2.0% |

Defender-grid builds: **24,470 → 16,770 per week (−31.5%)**.

### Railway projection

Local Atlas RTT is ~26.9 ms median; a colocated Railway deploy is 1–3 ms, so the DB row is
inflated ~10× here. Normalizing to 2 ms:

**Estimated Railway sequential week: ~155 s (2.46 s/game)**, down from ~195 s at the Phase 1
baseline — about **−20%**.

Against the 90 s target, that leaves roughly a **1.7× gap**, and the shape is now clear:
with DB latency normalized away, **animation/defender geometry is 50.4%** and **core
possession logic is 36.8%** — together 87% of adjusted time.

## 5. Found but NOT touched (Phase 3 candidates)

| Finding | Note |
|---|---|
| `_point_in_polygon` — 680,558 calls/game | Explicitly out of scope; the leaf under the 50.4% geometry row |
| Threading at 39% efficiency (4 workers → 1.57×) | Out of scope; GIL-bound. Gets *worse* on Railway as DB waits shrink |
| Thread-shared sim stream | `--workers 1` still required for seeded runs; per-thread streams cost +30%/draw |
| Guard not armed in production | Would catch rare-branch draws in live games; production behavior change |
| `_diagnose` full animation redraw per **live** HCO turn | Live-path only, pure observability |
| `convert_players` — 1,176,221 calls/game | Not investigated |
| `plays` reads ~26 round trips/game | Already memoized once; mostly local-latency artifact |
| Three `_stamp_contest_defender_grid` sites | Phase 1 4a proved them behaviorally distinct |
| CPU FG% ~52 / 3P% ~48 above target; BLK 0.21/game | Basketball tuning, out of scope |

## 6. Re-running

```bash
# verification (seeded, exact diff / distributional)
python3 scripts/perf_sim_baseline.py --franchise 6a28436c98dbd04e902eee09 --week 7 \
  --games 63 --mode both --ps-franchise 6a5e1f0e517ebcc58d981675 --ps-week 3 \
  --seed 20260720 --no-profile --workers 1 --tag <tag>

# timing (profiled; run 3x and take medians)
python3 scripts/perf_sim_baseline.py --franchise 6a28436c98dbd04e902eee09 --week 7 \
  --games 63 --mode both --ps-franchise 6a5e1f0e517ebcc58d981675 --ps-week 3 \
  --workers 1 --tag <tag>
```

Every run asserts RNG isolation and prints
`✅ RNG isolation: 0 engine draws on the global module`, or exits 1 naming the offending
call sites.
