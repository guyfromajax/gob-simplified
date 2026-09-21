#!/usr/bin/env python3
"""One-arm seeded quarter for WS-2: Lancaster vs Bentley-Truman, seed 20260918.

Run as a subprocess with PYTHONHASHSEED=0. Prints one JSON object.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _configure(arm: str, sqlite_path: Path) -> None:
    if arm == "loopback":
        from BackEnd.loopback_env import apply_loopback_env

        os.environ["GOB_SQLITE_PATH"] = str(sqlite_path)
        apply_loopback_env()
        return
    os.environ["ENVIRONMENT"] = "test"
    os.environ["GOB_DB_MODE"] = "mongomock"
    os.environ["MONGO_URI"] = "mongodb://127.0.0.1:27017/gob-test"
    os.environ["MONGO_DB_NAME"] = "gob-test"
    if arm == "sqlite":
        os.environ["GOB_PERSISTENCE"] = "sqlite"
        os.environ["GOB_SQLITE_PATH"] = str(sqlite_path)
    elif arm == "mongo":
        os.environ["GOB_PERSISTENCE"] = "mongo"
    else:
        raise SystemExit(f"unknown arm {arm}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", required=True, choices=("mongo", "sqlite", "loopback"))
    parser.add_argument("--sqlite-path", default="")
    args = parser.parse_args()
    sqlite_path = Path(args.sqlite_path or f"/tmp/ws2-exact-{args.arm}.sqlite")
    if args.arm != "mongo" and sqlite_path.exists():
        sqlite_path.unlink()
    _configure(args.arm, sqlite_path)

    from BackEnd.utils.sim_random import seed as seed_sim
    from BackEnd.utils.sim_random import sim_rng
    from BackEnd.db import defenses_collection, players_collection, plays_collection, teams_collection
    from BackEnd.main import simulate_quarter
    from BackEnd.models.game_manager import GameManager
    from tests.roster_fixtures import (
        seed_universal_defenses,
        seed_universal_plays,
        seed_universal_rosters,
    )

    DRAW_METHODS = (
        "random",
        "randint",
        "randrange",
        "choice",
        "choices",
        "uniform",
        "shuffle",
        "sample",
        "gauss",
        "getrandbits",
    )
    counts = {name: 0 for name in DRAW_METHODS}
    for name in DRAW_METHODS:
        original = getattr(sim_rng, name)

        def _wrap(method_name: str, fn):
            def wrapped(*a, **k):
                counts[method_name] += 1
                return fn(*a, **k)

            return wrapped

        setattr(sim_rng, name, _wrap(name, original))

    seed_universal_rosters(teams_collection, players_collection, module_name="ws2_exact_diff")
    seed_universal_plays(plays_collection)
    seed_universal_defenses(defenses_collection)
    seed_sim(20260918)
    gm = GameManager("Lancaster", "Bentley-Truman", persist_position_ratings=False)
    simulate_quarter(gm)
    payload = {
        "arm": args.arm,
        "persistence": os.environ.get("GOB_PERSISTENCE"),
        "loopback": os.environ.get("GOB_LOOPBACK"),
        "score": gm.score,
        "totals": gm.team_totals,
        "draw_total": sum(counts.values()),
        "draws": counts,
    }
    print(json.dumps(payload, default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
