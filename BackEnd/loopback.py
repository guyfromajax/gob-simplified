"""Local loopback entry. The shell (WS-4) launches this process.

The app is assembled in BackEnd.api.api, not BackEnd.main. This module only
sets the profile, injects the local principal, binds 127.0.0.1, and writes a
ready file the shell can wait on.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys

from BackEnd.loopback_env import apply_loopback_env

apply_loopback_env()

from BackEnd.api.api import app  # noqa: E402
from BackEnd.loopback_app import write_ready_file  # noqa: E402
from BackEnd.runtime_paths import bundle_root  # noqa: E402


def _pick_port(requested: int) -> int:
    if requested:
        return requested
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _prove_pool_worker(n: int) -> tuple[int, int, bool, bool]:
    """Module-level so spawn can pickle it. FastAPI and pymongo are already in the parent graph."""
    import fastapi
    import pymongo

    return os.getpid(), n * 2, bool(fastapi.__name__), bool(pymongo.__name__)


def prove_pool() -> int:
    """Answer the spike residual: spawn children after the full-app import surface."""
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor

    compiled = bool(
        getattr(sys, "frozen", False)
        or hasattr(sys, "__compiled__")
        or globals().get("__compiled__")
    )
    parent = os.getpid()
    print(f"executable={sys.executable} compiled={compiled} parent={parent}", flush=True)
    ctx = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=2, mp_context=ctx) as pool:
        results = list(pool.map(_prove_pool_worker, range(4)))
    pids = {row[0] for row in results}
    print(f"pids={sorted(pids)} results={results}", flush=True)
    if len(results) != 4:
        print("STATUS=FAIL missing results", flush=True)
        return 1
    if {row[1] for row in results} != {0, 2, 4, 6}:
        print("STATUS=FAIL bad payloads", flush=True)
        return 1
    if parent in pids:
        print("STATUS=FAIL worker ran in parent", flush=True)
        return 1
    print("STATUS=OK", flush=True)
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="GOB local loopback engine")
    parser.add_argument("--host", default=os.environ.get("GOB_LOOPBACK_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("GOB_LOOPBACK_PORT") or os.environ.get("PORT") or 8765),
    )
    parser.add_argument("--reload", action="store_true")
    parser.add_argument(
        "--prove-pool",
        action="store_true",
        help="Spawn two workers after FastAPI/pymongo import, then exit.",
    )
    args = parser.parse_args(argv)

    if args.prove_pool:
        raise SystemExit(prove_pool())

    os.environ.setdefault("GOB_BUNDLE_ROOT", str(bundle_root()))
    port = _pick_port(args.port)
    ready = write_ready_file(args.host, port)
    print(
        f"LOOPBACK_READY host={args.host} port={port} ready_file={ready}",
        file=sys.stderr,
        flush=True,
    )

    import uvicorn

    uvicorn.run(app, host=args.host, port=port, reload=args.reload, log_level="info")


if __name__ == "__main__":
    main()
