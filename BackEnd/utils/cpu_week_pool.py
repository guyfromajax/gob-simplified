"""
Process-pool executor for a week of CPU turn-by-turn games.

WHY A PROCESS POOL
------------------
The sim is CPU-bound pure Python; the GIL serializes threads, so the existing
ThreadPoolExecutor bought only ~1.57x on 4 workers (measured Phase 1). Separate
processes each get their own interpreter and run truly in parallel. Railway Pro
gives 32 vCPU on the service, and compute is usage-billed per vCPU-second, so
compressing wall time across processes costs ~nothing extra.

SPAWN IS REQUIRED, NOT OPTIONAL
-------------------------------
pymongo's MongoClient is NOT fork-safe — a forked child inherits sockets and
background threads mid-flight and corrupts. With the "spawn" start method each
worker is a fresh interpreter that imports BackEnd.db itself and so builds its
OWN MongoClient. Per-process Mongo isolation is therefore automatic, not
something the caller wires up.

DETERMINISM AT ANY WORKER COUNT
-------------------------------
Each game is seeded independently (seed = base + game index) and, after Phase 2,
the engine draws only from sim_rng — never the global module that pymongo also
uses. So a game's result is a pure function of (DB inputs, its seed), independent
of which worker runs it, in what order, or alongside what else. This RETIRES the
--workers 1 limitation: a pooled seeded run is byte-identical to a sequential
one after sorting by game index. (Unseeded — production — each game self-seeds
from OS entropy, unchanged.)

The caller keys results by game index and consumes them in sorted order, so the
emitted output is canonical regardless of completion order.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool

logger = logging.getLogger(__name__)

DEFAULT_POOL_WORKERS = 8


def pool_worker_count() -> int:
    """Worker count from FRANCHISE_CPU_SIM_POOL_WORKERS (default 8).

    Default leaves headroom on the 32-vCPU Railway service so live user-game
    requests never contend with a background week.
    """
    try:
        n = int(os.environ.get("FRANCHISE_CPU_SIM_POOL_WORKERS", DEFAULT_POOL_WORKERS))
        return max(1, n)
    except (TypeError, ValueError):
        return DEFAULT_POOL_WORKERS


def _worker(task: tuple) -> tuple:
    """Runs in a spawned worker process. Imports are done here so they happen once
    per process (spawn re-imports from scratch) and so BackEnd.db builds this
    process's own MongoClient."""
    idx, franchise_id, home_id, away_id, home_name, away_name, seed, collect_guard = task

    from BackEnd.utils import sim_random
    if collect_guard:
        # Strict install (records); we only READ the tally to verify isolation
        # held inside the worker. Never asserts here.
        sim_random.install_global_draw_guard()
        sim_random.reset_global_draw_guard()

    from BackEnd.api.franchise_routes import _run_franchise_cpu_full_simulation_core

    away, home, summary = _run_franchise_cpu_full_simulation_core(
        franchise_id, home_id, away_id, home_name, away_name, seed=seed
    )

    leaks = sim_random.global_draw_report() if collect_guard else {}
    return idx, away, home, summary, dict(leaks)


def _task_of(job, seed_base, collect_guard):
    idx, fid, hid, aid, hn, an = job
    seed = None if seed_base is None else seed_base + idx
    return (idx, fid, hid, aid, hn, an, seed, collect_guard)


def _run_one_pool(jobs, seed_base, max_workers, collect_guard, results, leaks):
    """One pool attempt over ``jobs``. Fills ``results``/``leaks`` for games that
    finish. Returns (per_game_errors, pool_broke). A BrokenProcessPool aborts the
    whole pool, so the remaining jobs are neither in results nor per_game_errors —
    the caller retries them."""
    per_game_errors: dict[int, Exception] = {}
    max_workers = max(1, min(max_workers, len(jobs))) if jobs else 1
    ctx = mp.get_context("spawn")
    try:
        with ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx) as ex:
            fut_to_idx = {ex.submit(_worker, _task_of(j, seed_base, collect_guard)): j[0]
                          for j in jobs}
            for fut in as_completed(fut_to_idx):
                idx = fut_to_idx[fut]
                try:
                    ridx, away, home, summary, wleaks = fut.result()
                    results[ridx] = (away, home, summary)
                    if collect_guard:
                        leaks[ridx] = wleaks
                except BrokenProcessPool:
                    raise
                except Exception as ex_:  # noqa: BLE001 — a game-level failure
                    per_game_errors[idx] = ex_
    except BrokenProcessPool as bpp:
        logger.error("[CPU-POOL] BrokenProcessPool (worker died): %s", bpp)
        return per_game_errors, True
    return per_game_errors, False


def _run_sequential_inprocess(jobs, seed_base, results, leaks, collect_guard):
    """Last-resort-but-one: run remaining games in THIS process with the real
    engine. Same seed derivation, so results stay seeded-reproducible. Used when
    the pool cannot be kept alive at all."""
    from BackEnd.api.franchise_routes import _run_franchise_cpu_full_simulation_core
    from BackEnd.utils import sim_random
    errs: dict[int, Exception] = {}
    for (idx, fid, hid, aid, hn, an) in jobs:
        try:
            seed = None if seed_base is None else seed_base + idx
            away, home, summary = _run_franchise_cpu_full_simulation_core(
                fid, hid, aid, hn, an, seed=seed)
            results[idx] = (away, home, summary)
            if collect_guard:
                leaks[idx] = {}
        except Exception as ex_:  # noqa: BLE001
            errs[idx] = ex_
    return errs


def simulate_cpu_week_pooled(
    jobs: list[tuple],
    *,
    seed_base: int | None = None,
    max_workers: int | None = None,
    collect_guard: bool = False,
) -> tuple[dict[int, tuple[int, int, dict]], dict[int, Exception], dict[int, dict]]:
    """Run a week of CPU games across a spawn-based process pool, with a failure
    ladder that keeps results correct rather than falling straight to noise.

    ``jobs``: list of ``(idx, franchise_id, home_id, away_id, home_name, away_name)``.
    ``seed_base``: None in production (each game self-seeds); an int for reproducible
    runs, where game ``idx`` uses ``seed_base + idx``.

    Returns ``(results, errors, leaks)`` — ``results[idx] = (away, home, summary)``,
    ``errors[idx] = exception`` for games that failed every tier, ``leaks[idx]`` the
    worker's global-draw tally when ``collect_guard``.

    FAILURE LADDER (a game is retryable because it is a pure function of its DB
    inputs + seed — re-running it yields the identical result):
      1. Pooled run.
      2. If the pool breaks (a worker was OOM/segfault-killed, poisoning the pool),
         rebuild the pool ONCE and re-run only the games that did not complete.
      3. If it breaks again, run the remainder SEQUENTIALLY IN-PROCESS with the real
         engine — slow but correct and still seeded.
      4. Only a game that fails even in-process is left in ``errors`` for the caller's
         random-score last resort, which the caller must log as an integrity event.
    """
    if max_workers is None:
        max_workers = pool_worker_count()
    if not jobs:
        return {}, {}, {}

    # Reproducibility guard. String-hash randomization changes set/dict iteration
    # order per process, and some engine code iterates sets while drawing RNG, so
    # a seeded result is only stable when every process shares one hash seed.
    # Workers inherit the parent's env, so a fixed PYTHONHASHSEED in the parent
    # makes workers AND the in-process fallback tier agree. This is the same
    # requirement sequential seeded runs already have (the harness re-execs with
    # PYTHONHASHSEED=0). Unseeded production does not need it.
    if seed_base is not None and os.environ.get("PYTHONHASHSEED") not in ("0", "1"):
        logger.warning(
            "[CPU-POOL] seed_base set but PYTHONHASHSEED is unset — pooled results "
            "will not be byte-reproducible across processes. Set PYTHONHASHSEED for "
            "reproducible seeded runs.")

    results: dict[int, tuple[int, int, dict]] = {}
    leaks: dict[int, dict] = {}
    errors: dict[int, Exception] = {}

    def _remaining():
        return [j for j in jobs if j[0] not in results]

    # Tier 1 — pooled
    per_game_errors, broke = _run_one_pool(
        _remaining(), seed_base, max_workers, collect_guard, results, leaks)

    # Tier 2 — rebuild the pool once for whatever did not complete
    if broke:
        remaining = _remaining()
        logger.warning("[CPU-POOL] rebuilding pool once for %d incomplete game(s)",
                       len(remaining))
        per_game_errors, broke = _run_one_pool(
            remaining, seed_base, max_workers, collect_guard, results, leaks)

    # Tier 3 — sequential in-process for the remainder
    if broke:
        remaining = _remaining()
        logger.warning("[CPU-POOL] pool unusable; running %d game(s) sequentially "
                       "in-process (correct + seeded, slower)", len(remaining))
        seq_errors = _run_sequential_inprocess(
            remaining, seed_base, results, leaks, collect_guard)
        per_game_errors = seq_errors

    # Tier 4 — genuine per-game failures (bad data, engine bug) survive to the caller
    for idx, ex_ in per_game_errors.items():
        if idx not in results:
            errors[idx] = ex_

    return results, errors, leaks
