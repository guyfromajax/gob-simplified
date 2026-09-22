"""Spawn-pool proof with FastAPI and pymongo already in the import graph.

The Nuitka spike proved the mechanism on a trivial worker. This is the full-app
question: children re-executing the binary still return after those imports.
"""

from __future__ import annotations

from BackEnd.loopback import prove_pool


def main() -> int:
    return prove_pool()


if __name__ == "__main__":
    raise SystemExit(main())
