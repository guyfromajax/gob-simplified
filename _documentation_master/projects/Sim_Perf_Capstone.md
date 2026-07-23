# Sim Performance — Capstone

**The one document to read first.** Covers why the computer-game simulation was slow, what
changed across three phases, how it is verified, and how to finish the rollout. Written 2026-07-21,
at develop HEAD `bb95978ee`. Detailed phase reports and commit hashes are at the bottom.

---

## In plain English

Every in-game week, GOB has to simulate up to 63 computer-vs-computer basketball games with the
full play-by-play engine. That was slow enough to be a problem, and nobody knew where the time
went. We measured it, then made three rounds of improvements: we deleted work that was being done
and thrown away, we fixed a subtle bug where the simulation's randomness was accidentally tangled
up with the database (so a game's result could change based on unrelated database activity), and
we made the games run on multiple CPU cores at once instead of one at a time. A week of games that
took about 5 minutes now takes well under a minute on 8 cores — and every change was checked to
prove the *basketball itself didn't change*, only the speed. The final production numbers get
confirmed on the staging server before this turns on for real players.

---

## Performance history

Local box: 14 cores (10 performance + 4 efficiency), MongoDB Atlas at ~27 ms round-trip. **Local DB
latency is ~10× worse than Railway's colocated Atlas (~1–3 ms), so the "Railway-adjusted" column
normalizes DB wait to 2 ms.** All timing is medians of 3+ runs on a quiet box.

| Stage | Local wall (63-game week) | Railway-adjusted | What bought it |
|---|---|---|---|
| **Phase 1 baseline** | 295.9 s | ~195 s | starting point (commit `dbb82a32d`) |
| **Phase 1** | ~290 s | ~192 s | removed a dead 1.24M-call/game player-id traversal in serialization |
| **Phase 2** | 246.0 s | ~155 s | isolated engine RNG (correctness) + reuse stamped defender grid (−31.5% grid builds) |
| **Phase 3 single-core** | ~138 s **CPU-time**/week | — | bounding-box reject on the hottest leaf; small at week level, the big single-core wins were already taken |

Phase 3 single-core is reported as **CPU-time** (2.19 s/game × 63 ≈ 138 s), because it is immune to
the machine contention that plagued wall-clock measurement this session.

### Phase 3 pooled — the final curve

Process pool, full week, wall **includes cold pool creation** (spawn + per-worker import), median
of 3:

| Workers | Wall | Speedup | Parallel efficiency | RSS/worker |
|--------:|-----:|--------:|--------------------:|-----------:|
| 1  | 224.9 s | 1.00× | 100% | 202 MB |
| 4  | 61.4 s  | 3.66× | 92%  | 197 MB |
| 8  | 34.6 s  | 6.51× | 81%  | 200 MB |
| 12 | 26.4 s  | 8.53× | 71%  | 212 MB |

**Why a process pool, not more threads.** The sim is CPU-bound pure Python; the GIL serializes
threads. The old ThreadPoolExecutor delivered only **1.57× on 4 workers**. The process pool
delivers **3.66× on the same 4** — real parallelism. That gap is the entire rationale for Stage 3b.

**Default is 8 workers** (6.51×, 81% efficiency): near-peak throughput with headroom left so live
user-game requests never contend with a background week. Efficiency decays past 8 because only 10
of 14 local cores are fast and cold-start amortizes worse on a short week.

**At 8 workers the week runs in 34.6 s locally — already under the 90 s target — and the local box
has ~10× worse DB latency than Railway.** The 90 s target looks comfortably reachable; the
authoritative production number is measured on staging (see rollout).

---

## RNG topology

### The engine must never share the global random stream

Before Phase 2 the engine drew from Python's global `random` module — the same stream every other
library in the process uses. That entangled game outcomes with unrelated activity. The proof:

> `pymongo`'s `bulk_write` **consumes the global `random` stream** (`find_one` does not). A Mongo
> write that matched **zero documents** still shifted final scores under a fixed seed.

Evidence, one change measured in both worlds — a guard that skips a no-op position-ratings write
for synthetic Practice-Squad rosters:

| | rows differing (of 166) |
|---|---|
| Phase 1 (shared stream) | **38** — 0/126 CPU, 38/40 PS (exactly the affected population) |
| Phase 2 (isolated stream) | **0 — byte-identical** |

Nothing changed between those runs but the RNG topology.

### The fix — `BackEnd/utils/sim_random.py`

A dedicated `Random` instance. 52 engine modules bind it in place of the stdlib module via a
one-line import swap, so **call sites are unchanged**:

```python
from BackEnd.utils.sim_random import sim_rng as random
```

Scope came from measurement, not grep: an audit counted which modules actually draw during a sim
(214,801 global draws over 2 CPU + 1 PS game), and a re-audit after conversion proved **0** engine
draws remain on the global module — the only survivor is `pymongo.message`, exactly where it
belongs. A **plain instance, not a thread-local proxy**: proxy forwarding cost +30%/draw at ~82k
draws/game; a plain instance is +1.7% (noise).

### Per-process, per-game seeding

Each game seeds `sim_rng` with `base + idx`. Combined with RNG isolation, **a game's result is a
pure function of (DB inputs, its seed)** — independent of which worker runs it, in what order, or
alongside what else. This is what makes the process pool reproducible and retires the old
`--workers 1` limitation. Production passes no seed (each game self-seeds from OS entropy).

### The global-draw guard (two forms)

`install_global_draw_guard()` wraps the stdlib module's draw functions and records any
`BackEnd`-attributed call by `module:function:lineno`.
- **Harness (strict):** the verification harness asserts the tally is empty and exits 1 with the
  offending sites otherwise.
- **Production (`log_only=True`, armed at FastAPI startup):** logs each offending site once at
  ERROR, never raises, never alters a draw. A stray site costs reproducibility, not correctness —
  not worth failing a live game over.

Why it exists: the 52-module conversion is only *proven* against branches the verification weeks
exercised. A draw site on a rare branch (overtime, ejections) would otherwise surface much later as
an unexplained intermittent mismatch. The guard turns that into an immediate, attributed catch. It
was verified to actually fire against a synthetic stray site.

### Determinism contract (all four required for byte-reproducible seeded runs)

1. **RNG isolation** — engine draws only from `sim_rng` (guard-enforced).
2. **Per-game seed** — `seed = base + idx`, applied before the game builds state.
3. **`PYTHONHASHSEED=0`** — string-hash randomization changes set/dict iteration order per process,
   and **some engine code iterates a set while drawing RNG**, so a differing hash seed changes draw
   order and therefore the result. The harness re-execs with `PYTHONHASHSEED=0`; pool workers
   inherit the parent's. *(This was the root cause of an early pooled-vs-sequential mismatch — not
   a pool bug. The pool warns if seeded without it.)*
4. **Single RNG stream per process** — threads share a process's `sim_rng`, so seeded reproducibility
   with threads still needs `--workers 1`. The **process** pool sidesteps this: one stream per
   worker, seeded per game.

---

## Verification toolkit — which instrument, when

| Instrument | Use when | What it proves |
|---|---|---|
| **Seeded exact-diff** | the change does **not** alter the sim's RNG draw count (pure geometry, dead-code removal, non-drawing work) | byte-identical refstats ⇒ identical basketball |
| **Poison-stash test** | the change **removes or alters draws** from the sim stream | keep the work running (draw count unchanged), replace only its *output* with an absurd sentinel; byte-identical ⇒ nothing reads that output |
| **Balanced multi-seed distributional arms** | the change alters the stream **by construction** (e.g. RNG isolation itself) | N seeds before vs N after, all stat columns, Welch t + F-ratio; no column beyond \|t\|>3 ⇒ same distribution |
| **Worker-kill recovery test** | pool failure semantics | SIGKILL a live worker mid-game; week still completes with correct seeded results |

### The exact-diff's hard limitation (read this before trusting a diff)

> **A change that removes draws from the sim stream cannot be verified by exact diff.** Removing
> draws shifts every downstream result by construction, so the diff shows total divergence whether
> or not the removed work mattered. Phase 1 hit exactly this: a genuinely-dead defender-grid
> rebuild failed at 166/166 rows differing — indistinguishable from a real behavior change. That is
> what the poison-stash test exists to resolve.

**Poison-stash blind spot (documented, not hypothetical):** the test is only as strong as the
sentinel's detectability. `{x: -9999, y: -9999}` catches any consumer doing arithmetic on the
value, but **not** one that merely checks a key's presence. No such consumer exists today (the sole
reader runs earlier in the turn), but the test is not unconditional proof.

**The reference anchor** is `reports/perf/refstats_postB_20260720_20260720_153720.csv` (seed
20260720), cut after RNG isolation. A seeded reference is only valid within an RNG-topology-stable
code state — re-cut it after any intentional stream change.

**The instruments are committed and runnable** in `scripts/sim_verify/` (see its README for a
per-tool map and copy-paste commands). The poison-stash test is a durable harness flag,
`perf_sim_baseline.py --poison-stash`, not just prose. The canonical seeded verification run:

```bash
PYTHONHASHSEED=0 python3 scripts/perf_sim_baseline.py \
  --franchise 6a28436c98dbd04e902eee09 --week 7 --games 63 --mode both \
  --ps-franchise 6a5e1f0e517ebcc58d981675 --ps-week 3 \
  --seed 20260720 --no-profile --workers 1 --tag mychange
python3 scripts/sim_verify/diffstats.py \
  reports/perf/refstats_postB_20260720_20260720_153720.csv \
  reports/perf/refstats_mychange_*.csv
```

Add `--poison-stash` for a draw-count change; swap `--workers 1` for `--pool 8` to exercise the
pool. Fixtures are `gob-staging` docs — swap for any franchise with a populated week-7 schedule +
initialized practice squad.

---

## Standing rules

1. **Draw-count changes → poison test, not exact diff.** (See the limitation above.) Exact diff
   stays valid only for non-drawing changes.
2. **Balance retunes intentionally change basketball → re-cut the reference.** A tuning change is
   *supposed* to move the stats; verify it distributionally and adopt a new anchor, don't diff
   against the old one.
3. **No source edits while a measurement or verification run is in flight.** Python doesn't reload
   imported modules, so an in-flight run is unaffected — but the *next* run in a sequence silently
   picks up the edit and invalidates the comparison. Park edits, `git checkout` clean, re-apply
   after.
4. **Seeded runs pin `PYTHONHASHSEED=0`.** (Determinism contract clause 3.)
5. **Timing claims use medians of 3+ on a quiet box.** Wall-clock is noisy (~±5% even quiet, 1.5–2×
   under a CPU hog). Prefer phase self-times, call counts, and CPU-time (`getrusage`) — all more
   robust than wall. Watch for a background hog before trusting any wall number.

---

## Pool design — `BackEnd/utils/cpu_week_pool.py`

- **Spawn, not fork — mandatory.** pymongo's `MongoClient` is not fork-safe (a forked child
  inherits live sockets/threads and corrupts). A spawned worker imports `BackEnd.db` itself and
  builds its **own** client — per-process Mongo isolation is automatic, not caller-wired.
- **Worker count** — `FRANCHISE_CPU_SIM_POOL_WORKERS`, default **8**. Chosen from the scaling curve:
  6.51× at 81% efficiency, near-peak, while leaving headroom so live user games never contend.
- **Canonical output** — results keyed by game index; caller consumes `sorted()`. Pooled output is
  byte-identical to sequential regardless of completion order.

### Three-tier failure ladder

A game is retryable because it is a pure function of (inputs, seed). On worker death:

1. **Pooled run.**
2. `BrokenProcessPool` → **rebuild the pool once**, re-run only incomplete games.
3. Still broken → **run the remainder sequentially in-process** (correct + seeded, slower).
4. Only past that → the caller's **random-score last resort**, logged loudly as an **integrity
   event**.

The week-complete gate fires only when all games resolve; a dead worker becomes a reported failure,
never a hung gate. **Proven:** SIGKILL a mid-game worker → `BrokenProcessPool` → `rebuilding pool
once` → week completes 8/8, byte-identical to the clean seeded reference, 0 RNG leaks.

### Kill switch

`FRANCHISE_CPU_SIM_USE_POOL`, **default `0` (OFF)** — the ThreadPoolExecutor path stays default
until the pool is exercised on the real FastAPI/uvicorn/Railway spawn path. Env-only; flips
per-service with no code deploy. Both paths call the same core function and produce identical
`sim_ok`/`sim_err` shapes, so downstream persistence/fallback/EOS-bracket logic is untouched.

### Rollout runbook (checklist)

- [ ] Merge to production with the kill switch **OFF** — zero production change.
- [ ] On the Railway **staging** service, set `FRANCHISE_CPU_SIM_USE_POOL=1` (tune
      `FRANCHISE_CPU_SIM_POOL_WORKERS`).
- [ ] Run **advance-week** on staging and watch: worker **spawn under uvicorn**, per-worker **RSS**,
      the **RNG-leak log line** (should be silent), the **failure-ladder** log lines, and that
      **league pages unblock** (gate fires).
- [ ] Capture the **authoritative Railway scaling number** (the real 32-vCPU, colocated-Atlas
      figure that local measurement can't give).
- [ ] Enable in **production** at a conservative worker count.
- [ ] Progressively **raise the full-sim computer-game count from ~8 toward 63** — today most games
      use the lightweight "distant" statistical model; the pool's headroom is what makes full
      turn-by-turn sim affordable for more of the slate.

---

## Parked — tuning backlog (NOT performance; basketball realism)

These are stat-realism issues surfaced by the multi-seed arms. None were touched — Phase 1–3 were
explicitly perf-only and forbade basketball-logic changes.

- **CPU FG% ~53 / 3P% ~50 run hot** — above target; the shot system was already flagged as an open
  tuning thread before this initiative.
- **BLK ~0.21/game is implausibly low** — also why `BLK` was the one statistically fragile column in
  every distributional comparison.
- **Practice-Squad scrubs are low-rated by design, not a bug** — confirmed with the product owner.
  PS FG% ~30 / 3P% ~16 is the intended consequence of low-rated recruits + fixed team chemistry.
  Their attributes resolve from `franchise_players_data` / `franchise_recruits_data`, never the
  universal `players` collection.

## Parked — found but not touched (perf, out of scope)

- **`convert_players` traversal** — 1.09M calls/game, but `player_to_dict` fires only 339× (0.03%);
  the cost is recursive descent through freshly-built, unhashable structures (nothing to cache). It
  is pure and NOT dead work. A real win would skip Player-free subtrees — a correctness risk, not a
  cache. Left alone.
- **`_point_in_polygon` call count** — bbox cut per-call cost (2.9×), but the *count* (267k/game) is
  driven by zone-overlap detection being O(players × zones). Reducing the count is an algorithmic
  change, a separate target.
- **Set-iteration-while-drawing sites** — the reason `PYTHONHASHSEED` matters. Not enumerated;
  making the engine hash-seed-independent would remove that clause from the determinism contract.
- **Threads share a process's `sim_rng`** — the process pool sidesteps it, but in-process threaded
  seeded runs still need `--workers 1`.
- **RNG guard not a hard failure in production** — log-only by design; making it page/alert is a
  separate decision.
- **`_diagnose` runs a full animation redraw per live HCO turn** — live-path only, pure
  observability; never runs in a sim.

---

## Pointers

### Phase reports (detail behind each summary here)
- `_documentation_master/projects/Sim_Perf_Baseline.md` — original measurement + method
- `_documentation_master/projects/Sim_Perf_Phase1.md` — dead-code removal, the exact-diff limitation discovery
- `_documentation_master/projects/Sim_Perf_Phase2.md` — RNG isolation, poison-stash method
- `_documentation_master/projects/Sim_Perf_Phase3.md` — bbox, process pool, scaling curve, rollout

### Key code
- `BackEnd/utils/sim_random.py` — dedicated RNG + global-draw guard
- `BackEnd/utils/cpu_week_pool.py` — process pool + failure ladder
- `scripts/perf_sim_baseline.py` — verification + benchmark harness (`--seed`, `--pool N`, `--workers`, `--poison-stash`)
- `BackEnd/utils/sim_profiler.py` — pure-monkeypatch phase timer (`GOB_SIM_PROFILE=1`)
- `scripts/sim_verify/` — the verification toolkit (diffstats, distcompare, kill_worker_test, p2_rng_audit, bench_pool) + README mapping each to the toolkit table above

### The substantive commits (git archaeology, one hop away)
| Hash | Change |
|---|---|
| `22e67e792` | instrumentation, baseline, optional RNG seeding |
| `ef9339e5a` | Phase 1 — remove dead player-id traversal (exact-diff 166/166) |
| `b269732fa` | Phase 2 — dedicated engine RNG stream (the correctness fix) |
| `4da067d87` | Phase 2 — reuse stamped defender grid (poison-verified) |
| `b3ae6ad32` | Phase 2 — skip no-op synthetic-roster write (38→0 rows, proves isolation) |
| `5244efb95` | Phase 3 — bounding-box reject in `_point_in_polygon` |
| `50c1f3d8d` | Phase 3 — production RNG guard (log-only at startup) |
| `7c4862be4` | Phase 3 — spawn process pool + three-tier failure ladder |
| `10e33867b` | Phase 3 — wire pool behind kill switch (default OFF) |

Baseline (pre-initiative) state is commit `dbb82a32d`. Docs-only commits (`70c4a49ee`,
`0567e22bf`, `dbafafcf4`, `bb95978ee`) carry the phase reports and are omitted here.

---

## Tactical principles — preserving sim speed when adding features

*Added 2026-07-22 after a regression: a batch of shot-calibration commits slowed an isolated
user-game sim 16→26s, the 63-game week 67→131s, and PS-game sims (training) 12→55s — all from new
gameplay/diagnostic work in the per-step/per-shot engine path. The sim is a top-priority perf
surface; every feature that touches the engine must respect these.*

1. **Know your code's execution granularity before adding to it.** per-step ≫ per-shot ≫ per-turn ≫
   per-possession ≫ per-game. A line in `motion_step_decision` runs *thousands* of times/game; the
   same line at EOG runs once. Always ask "how many times per game does this fire?" — that count is
   the multiplier on your cost.
2. **The sim is CPU-bound pure Python — every added computation is paid in full.** No I/O wait to
   hide work behind. A loop / `hypot` / dict-build in the hot path adds `wall × executions/game ×
   games/week`. Small-looking hot-path additions are not small.
3. **Diagnostics must be near-zero-cost or gated OFF for bulk sims.** Aggregate trackers, geo
   logging, shot-split recorders are debug aids — keep them to trivial counter increments, or put
   them behind a flag that is **OFF during full-sim / CPU-week / PS** (mirror `_is_full_simulation`).
   A "tracking on" flag must never default-on for the 63+24-game bulk path.
4. **Never do a DB write inside the sim loop.** The engine is pure compute; a per-turn/per-shot
   write serializes on Atlas latency × thousands of turns = catastrophic — *and* re-entangles the
   RNG stream (the Phase-2 bug: `pymongo.bulk_write` consumes global `random`). Persist once at game
   end.
5. **Beware eager evaluation in log/diagnostic args.** `logger.debug(f"{build_report()}")` runs
   `build_report()` even when logs are filtered to ERROR (which `quiet_headless` does). Use
   `logger.debug("%s", cheap_value)` and never compute inside a log argument.
6. **Anything in `shared.py`'s shot-resolution path taxes every mode at once.** It is called by user
   games, CPU weeks, and PS games — a cost there has the widest blast radius (exactly this
   regression). Treat it as the most expensive place to add anything.
7. **Measure before AND after every hot-path change.** One profiled game (`GOB_SIM_PROFILE=1` /
   `perf_sim_baseline.py`) shows the phase breakdown in seconds; a moved phase self-time is visible
   immediately. Don't merge hot-path work without a before/after — this regression would have been a
   one-line profile diff.
8. **Draw-count changes follow the determinism contract.** Any engine change that adds/removes RNG
   draws needs the **poison-stash test** (not exact-diff) and a re-cut reference. Balance retunes
   that intentionally move stats get distributional verification + a new anchor. (See *Standing
   rules* and *Verification toolkit* above.)

**Fix strategy when a regression is found:** separate *intentional gameplay* additions (which
legitimately change basketball and may cost some compute — verify distributionally, budget them)
from *pure diagnostics* (gate OFF for bulk sims — free win, no behavior change). Profile to attribute
the cost per phase before touching anything.
