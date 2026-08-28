"""
🔎 MEMORY LEAK PROBE — DIAGNOSTIC ONLY. Safe to delete wholesale.

Drop at BackEnd/utils/memory_probe.py and mount the router in api.py:

    from BackEnd.utils.memory_probe import router as _mem_router
    app.include_router(_mem_router)

Inert unless GOB_MEM_PROBE=1. Guarded by GOB_MEM_PROBE_TOKEN so the endpoint
cannot be scraped on a public deploy.

WHAT IT ANSWERS
---------------
RSS climbing does NOT by itself mean a leak. Two very different causes produce
the same Railway chart:

  (a) REAL LEAK        — reachable objects accumulate. tracemalloc total grows
                         and stays grown. The traceback names the file/line.
  (b) HWM / ARENA HOLD — objects are freed, but glibc never returns the arena
                         to the OS, so RSS ratchets to a high-water mark.
                         tracemalloc stays flat while RSS climbs.

The fixes are completely different, so measure before changing anything.

USAGE
-----
  1. GET /debug/memory?token=...&mark=1     <- baseline, arms a tracemalloc snapshot
  2. Advance one franchise week in the app
  3. GET /debug/memory?token=...            <- read the diff

  Then read `verdict` in the response.
"""

from __future__ import annotations

import gc
import os
import sys
import tracemalloc

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

ENABLED = os.environ.get("GOB_MEM_PROBE") == "1"
_TOKEN = os.environ.get("GOB_MEM_PROBE_TOKEN", "")

_baseline: tracemalloc.Snapshot | None = None
_baseline_rss: int = 0


def _rss_bytes() -> int:
    """Resident set size — the number Railway actually bills."""
    try:
        with open("/proc/self/statm", "r") as fh:
            return int(fh.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except Exception:
        import resource
        ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return ru * (1 if sys.platform == "darwin" else 1024)


def _mb(n: float) -> float:
    return round(n / (1024 * 1024), 1)


def _malloc_trim() -> bool:
    """Ask glibc to hand freed arenas back to the OS. No-op off glibc."""
    try:
        import ctypes
        return bool(ctypes.CDLL("libc.so.6").malloc_trim(0))
    except Exception:
        return False


@router.get("/debug/memory")
def memory_probe(
    token: str = Query(""),
    mark: int = Query(0, description="1 = set this reading as the baseline"),
    trim: int = Query(0, description="1 = malloc_trim(0) and report RSS before/after"),
    top: int = Query(15, description="how many allocation sites to return"),
):
    if not ENABLED:
        raise HTTPException(404, "probe disabled")
    if not _TOKEN or token != _TOKEN:
        raise HTTPException(403, "bad token")

    global _baseline, _baseline_rss

    if not tracemalloc.is_tracing():
        # 25 frames is enough to see through pymongo/pydantic into your own code
        tracemalloc.start(25)

    gc.collect()
    rss = _rss_bytes()
    traced_cur, traced_peak = tracemalloc.get_traced_memory()

    out: dict = {
        "rss_mb": _mb(rss),
        "traced_mb": _mb(traced_cur),
        "traced_peak_mb": _mb(traced_peak),
        # The gap is the tell. Large and growing => allocator retention, not a leak.
        "untraced_gap_mb": _mb(rss - traced_cur),
        "gc_objects": len(gc.get_objects()),
        "gc_counts": gc.get_count(),
        "gc_uncollectable": len(gc.garbage),
    }

    if trim:
        before = rss
        did = _malloc_trim()
        after = _rss_bytes()
        out["trim"] = {
            "ran": did,
            "rss_before_mb": _mb(before),
            "rss_after_mb": _mb(after),
            "released_mb": _mb(before - after),
        }

    snap = tracemalloc.take_snapshot().filter_traces((
        tracemalloc.Filter(False, tracemalloc.__file__),
        tracemalloc.Filter(False, __file__),
    ))

    if mark or _baseline is None:
        _baseline = snap
        _baseline_rss = rss
        out["marked"] = True
        out["note"] = "Baseline set. Advance a week, then call again without mark=1."
        return out

    stats = snap.compare_to(_baseline, "traceback")[:top]
    out["rss_growth_since_mark_mb"] = _mb(rss - _baseline_rss)
    out["top_growth"] = [
        {
            "size_diff_mb": _mb(s.size_diff),
            "count_diff": s.count_diff,
            "total_mb": _mb(s.size),
            "traceback": s.traceback.format()[-4:],
        }
        for s in stats
    ]

    traced_growth = sum(s.size_diff for s in stats)
    rss_growth = rss - _baseline_rss
    if rss_growth < 32 * 1024 * 1024:
        out["verdict"] = "No meaningful RSS growth over this interval."
    elif traced_growth > 0.5 * rss_growth:
        out["verdict"] = (
            "REAL LEAK. Python-tracked allocations account for most of the RSS "
            "growth — read top_growth[0].traceback, that is your culprit."
        )
    else:
        out["verdict"] = (
            "ALLOCATOR RETENTION, not an object leak. RSS grew but tracked "
            "allocations did not. Try MALLOC_ARENA_MAX=2 and a malloc_trim(0) "
            "after the persist loop before hunting for a leak."
        )
    return out
