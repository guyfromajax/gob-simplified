# Sim Optimization Phase 3 — Single-core wins + CPU-week process pool

**Date:** 2026-07-20 · **Phase 2 HEAD:** `0567e22bf` · **Phase 3 HEAD:** `10e33867b`
**Reference anchor:** `reports/perf/refstats_postB_20260720_20260720_153720.csv` (seed 20260720)

## Status

| Stage | Item | Outcome | Commit |
|---|---|---|---|
| 3a | Bounding-box reject in `_point_in_polygon` | ✅ byte-identical | `5244efb95` |
| 3a | `convert_players` memoization | investigated, **skipped** (no payoff) | — |
| 3a | Production RNG guard (log-only) | ✅ | `50c1f3d8d` |
| 3b | Process-pool mechanism + failure ladder | ✅ verified | `7c4862be4` |
| 3b | Production wiring, kill switch default OFF | ✅ | `10e33867b` |

---

## Stage 3a — single-core

### `_point_in_polygon` re-measured

The Phase 1 figure (680,558 calls/game) was stale. Post-Phase-2:

> **267,613 calls/game** — a 61% drop, because Phase 2's defender-grid reuse removed a third
> of the builds that fed it.

Origins (all zone-defense assignment, which tests every player against every zone):
`_detect_overlapping_zones` 42% · `_resolve_overlap_assignments` 31% ·
`assign_zone_defender_coords` 14% · `assign_all_zone_defenders` 7% ·
`_position_zone_defenders` 3%.

### Bounding-box reject — committed

**72.3% of calls are points outside the polygon's bounding box**, previously paying for two full
O(n) passes (vertex/edge cross-products + ray casting) to reach a foregone conclusion. A single
inline min/max pass rejects them first.

Exactly equivalent, not approximate: the edge test can only return True inside the polygon's
overall x/y range, and ray casting outside the bbox is False by definition — so the 0.01
tolerance needs no margin. Microbenchmark over the real polygon mix (3–13 vertices): **2.9×
faster**, 0 mismatches across 2,400 combinations. No RNG impact → exact-diff verifiable:
**seeded week byte-identical, 166/166.**

### `convert_players` — investigated, correctly skipped

Asked to check purity first. **It is pure** (no draws, no mutation, builds fresh containers;
`player_to_dict` reads only `{player_id, name, team}`). Purity was not the blocker — payoff was:

> `player_to_dict` runs **339 times/game**; `convert_players` runs **1,089,006 times/game**.
> Player conversion is **0.03%** of the work.

The other 99.97% is recursive descent through freshly-built, unhashable nested structures —
nothing repeats, so nothing is cacheable. Memoizing the leaf would save ~339 calls. Skipped per
instruction (not forced). Also confirmed it is NOT dead work: `result = convert_players(result)`
feeds the object downstream sim logic consumes. Reducing the traversal itself would mean skipping
Player-free subtrees — a correctness risk, not a cache — so it goes on the not-touched list.

### Production RNG guard — committed

`install_global_draw_guard(log_only=True)` at FastAPI startup. The module conversion is only
proven against branches the verification weeks exercised; a rare-branch draw site (overtime,
ejections) that only fires in live play would otherwise surface as an unexplained intermittent
mismatch. Log-only: each offending site logged once at ERROR with `module:function:lineno`, never
raises, never alters a draw — a stray site costs reproducibility, not correctness. Verified it
emits exactly one line for repeated draws and the process survives; the harness keeps strict mode.

## Stage 3b — CPU-week process pool

### Why processes

The sim is CPU-bound pure Python; the GIL capped the ThreadPoolExecutor at ~1.57× on 4 workers
(Phase 1). Separate processes run truly in parallel. Railway Pro is 32 vCPU / 32 GB, usage-billed
per vCPU-second, so compressing wall time across processes costs ~nothing.

### Design

- **Spawn, not fork** — mandatory. pymongo's `MongoClient` is not fork-safe (a child inherits
  live sockets/threads). A spawned worker imports `BackEnd.db` itself and builds its own client;
  per-process Mongo isolation is automatic.
- **Per-process seeding** — each game seeds `sim_rng` with `base + idx`. After Phase 2 the engine
  draws only from `sim_rng`, so a game is a pure function of (DB inputs, seed), independent of
  worker or order. **This retires the `--workers 1` reproducibility limit.**
- **`PYTHONHASHSEED` is part of the determinism contract.** String-hash randomization changes
  set/dict iteration order per process, and some engine code iterates sets while drawing RNG. A
  seeded result is only byte-reproducible when every process shares one hash seed. Workers inherit
  the parent's, so a fixed `PYTHONHASHSEED` in the parent makes workers AND the in-process
  fallback tier agree — the same requirement sequential seeded runs already had (the harness
  re-execs with `PYTHONHASHSEED=0`). The pool warns if seeded without it. *(This was the root
  cause of an initial pooled-vs-sequential mismatch during development — not a pool bug.)*
- **Canonical output** — results keyed by game index; caller consumes `sorted()`. Pooled output
  is byte-identical to sequential regardless of completion order.
- **Worker count** — `FRANCHISE_CPU_SIM_POOL_WORKERS`, default 8, leaving headroom on 32 vCPU so
  live user-game requests never contend with a background week.

### Failure ladder

A game is retryable because it is a pure function of (inputs, seed). On worker death:

1. Pooled run.
2. `BrokenProcessPool` → rebuild the pool **once**, re-run only incomplete games.
3. Still broken → run the remainder **sequentially in-process** (correct + seeded, slower).
4. Only past that does a game reach the caller's **random-score last resort**, logged as an
   integrity event.

The week-complete gate fires only when all games resolve; a dead worker becomes a reported
failure, never a hung gate.

### Verification

| Check | Result |
|---|---|
| pooled (4w) vs sequential, seeded | ✅ byte-identical |
| pooled twice, same seed | ✅ byte-identical |
| RNG guard: global-module draws per worker | ✅ 0 (each worker reports its own tally) |
| **worker-kill recovery** | ✅ SIGKILL mid-game worker → `BrokenProcessPool` → tier-2 rebuild → week completes 8/8, byte-identical to clean seeded reference |

The kill test confirms amendment 2: killed games recover to **correct, seeded** results, not
random fallback. Log excerpt: `BrokenProcessPool (worker died)` → `rebuilding pool once for 8
incomplete game(s)` → PASS.

### Production wiring — kill switch DEFAULT OFF

`FRANCHISE_CPU_SIM_USE_POOL` (default `0`) selects pool vs thread path. Both call the same core
function and produce the same `sim_ok[idx]=(away,home,summary)` / `sim_err[idx]=exception`, so
downstream persistence, fallback, and EOS-bracket logic is untouched. Production stays unseeded
(`seed_base=None`), matching thread behavior statistically.

### Rollout plan (staging-first)

The mechanism is fully exercised via the harness (the real sim function), but the **FastAPI /
uvicorn / Railway spawn path was not run locally**. Rollout:

1. Merge with the kill switch OFF — zero production change.
2. On the Railway **staging** service, set `FRANCHISE_CPU_SIM_USE_POOL=1` (+ tune
   `FRANCHISE_CPU_SIM_POOL_WORKERS`). Run advance-week and watch: worker spawn under uvicorn,
   per-worker memory, the RNG-leak log line, and the failure-ladder log lines.
3. Confirm league pages unblock (gate fires) and results look sane.
4. Only then enable on production, starting at a conservative worker count.

Kill switch is env-only, so disabling needs no code deploy.

## Timing

> **Measurement caveat.** The local box was contended throughout by an unrelated app
> (OOTP Baseball, intermittent ~210% CPU bursts on the 14-core machine). Wall-clock runs inflated
> 1.5–2× and varied run-to-run, so wall numbers below are **not** reliable and a clean pool
> scaling curve could not be produced here. Contention-**immune** measures (CPU-time via
> `getrusage`, cProfile `tottime`, RSS) are reported instead; the authoritative wall-clock scaling
> curve is deferred to the Railway staging run — the real 32-vCPU target anyway.

### Stage 3a — single-core (contention-immune)

Per-game CPU-time (user+sys — counts only cycles the process received):

> **2.19 s CPU/game → ~138 s CPU for a 63-game week**, single-core.

The bbox change is a clean per-call win (2.9× on `_point_in_polygon`, 72% reject, byte-identical),
but the function is ~13% of a game's cumtime and the win is a fraction of that, so its
**week-level contribution is single-digit % — below this box's noise floor.** The large
single-core wins were already taken in Phases 1–2; 3a's role was to clear the hottest leaf cheaply
and safely, which it did.

### Stage 3b — pool scaling

- **Per-worker peak RSS ~200 MB** (contention-independent). At 8 workers ≈ 1.6 GB + parent — a
  small fraction of Railway's 32 GB, so **memory is not a constraint** at the default worker count.
- **Correctness at scale:** the pool completed the full 63/64-game week with **zero errors at 1, 4,
  8, and 12 workers**.
- **Wall (indicative only, contended):** one pass caught the box briefly idle and did 64 games in
  **25.7 s at 12 workers** (~0.4 s/game effective) — ~11.7 s of pure compute (2.19 s × 64 ÷ 12)
  plus spawn/import and DB. Consistent with near-linear scaling, but a single data point, not a
  curve. The 1/4/8-worker passes were caught mid-contention and discarded.
- **Cold pool creation** (spawn + per-worker app import) is included in all pool wall times, since
  production pays it per advance-week. It is the dominant fixed cost at high worker counts on a
  short week — one reason the default is 8, not the max.

### Railway projection

Deferred to staging. The local box is doubly unrepresentative: contended, AND its ~27 ms Atlas RTT
is ~10× Railway's colocated latency, so the DB-wait fraction the pool overlaps differs. Staging
(32 vCPU, colocated Atlas) is where the 90 s-target math should be settled. Order-of-magnitude:
single-core CPU is ~138 s/week and the work is embarrassingly parallel across games, so 8 workers
should bring the compute portion comfortably under target; the open question staging answers is
how DB and spawn/import overhead land on real hardware.

## Found but NOT touched (Phase 4 candidates)

| Finding | Note |
|---|---|
| `_point_in_polygon` still 267k calls/game | bbox cut the cost per call; the call COUNT (zone-overlap detection is O(players×zones)) is a separate algorithmic target |
| `convert_players` traversal — 1.09M calls/game | reducing needs skipping Player-free subtrees (correctness risk), not a cache |
| Thread-shared sim stream within a process | pool gives per-process streams; a single process still needs `--workers 1` for seeded threads |
| RNG guard armed in harness + prod-log-only | not a hard failure in production by design |
| `_diagnose` full redraw per live HCO turn | live-path only, observability |
| CPU FG% ~52 / 3P% ~48, BLK 0.21/game | basketball tuning, out of scope |
