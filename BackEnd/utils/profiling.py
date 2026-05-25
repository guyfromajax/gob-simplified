"""Run a callable under cProfile and return top N functions by cumulative time."""
import cProfile
import io
import pstats


def run_profiled(func, top_n: int = 50) -> str:
    """Run func() under cProfile and return a text summary of top N by cumulative time.

    If another profiler is already active on this interpreter (e.g. a concurrent
    request also passed ?profile=1), fall back to running func() un-profiled so the
    caller still gets its result instead of a 400.
    """
    pr = cProfile.Profile()
    try:
        pr.enable()
    except ValueError as exc:
        if "already active" in str(exc).lower():
            func()
            return "[profile skipped: another profiler already active on this interpreter]"
        raise
    try:
        func()
    finally:
        pr.disable()
    stream = io.StringIO()
    pstats.Stats(pr, stream=stream).sort_stats(pstats.SortKey.CUMULATIVE).print_stats(top_n)
    return stream.getvalue()
