"""Spawn-pool proof with FastAPI and pymongo already in the import graph.

The Nuitka spike proved the mechanism on a trivial worker. This is the full-app
question: children re-executing the binary still return after those imports.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import sys
from concurrent.futures import ProcessPoolExecutor


def _worker(n: int) -> tuple[int, int, bool, bool]:
    import fastapi
    import pymongo

    return os.getpid(), n * 2, bool(fastapi.__name__), bool(pymongo.__name__)


def main() -> int:
    print(f"executable={sys.executable} compiled={getattr(sys, 'frozen', False)}", flush=True)
    ctx = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=2, mp_context=ctx) as pool:
        results = list(pool.map(_worker, range(4)))
    pids = {row[0] for row in results}
    print(f"pids={sorted(pids)} results={results}", flush=True)
    if len(results) != 4:
        print("STATUS=FAIL missing results", flush=True)
        return 1
    if {row[1] for row in results} != {0, 2, 4, 6}:
        print("STATUS=FAIL bad payloads", flush=True)
        return 1
    print("STATUS=OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
