"""Run a callable under cProfile and return top N functions by cumulative time."""
import cProfile
import io
import pstats


def run_profiled(func, top_n: int = 50) -> str:
    """Run func() under cProfile and return a text summary of top N by cumulative time."""
    pr = cProfile.Profile()
    pr.enable()
    try:
        func()
    finally:
        pr.disable()
    stream = io.StringIO()
    pstats.Stats(pr, stream=stream).sort_stats(pstats.SortKey.CUMULATIVE).print_stats(top_n)
    return stream.getvalue()
