#!/usr/bin/env python3
"""Compare finalize persist at week-4 vs late-season FTD/franchise sizes.

Does not grow the games table. Late arm grafts one real game onto the
finish_season save so FTD/franchise stay live-sized.

  python scripts/ws2_maps_size_compare.py
  python scripts/ws2_maps_size_compare.py --arm mongo --size week4 --sqlite /tmp/ws2-maps-week4.sqlite
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SEASON = Path("/tmp/ws2-catalog-season.sqlite")
WEEK4_SRC = Path("/tmp/ws2-eog-diag-4w.sqlite")
WEEK4 = Path("/tmp/ws2-maps-week4.sqlite")
LATE = Path("/tmp/ws2-maps-late.sqlite")
FID = "6aaff7b8f37ac3a890ef6093"
WEEK_GAMES = 63


def _wipe(path: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(str(path) + suffix).unlink(missing_ok=True)


def _backup(src: Path, dest: Path) -> None:
    _wipe(dest)
    src_con = sqlite3.connect(str(src))
    dst_con = sqlite3.connect(str(dest))
    src_con.backup(dst_con)
    src_con.close()
    dst_con.close()


def _doc_sizes(path: Path) -> dict:
    from BackEnd.persistence.sqlite_collection import decode_doc

    con = sqlite3.connect(str(path))
    out = {}
    for name in ("franchises", "franchise_team_data", "franchise_players_data", "games"):
        rows = con.execute(f'SELECT doc FROM "{name}"').fetchall()
        docs = [decode_doc(raw) for (raw,) in rows]
        raw_lens = [len(raw) for (raw,) in rows]
        out[name] = {
            "n": len(docs),
            "json_bytes": int(sum(raw_lens)),
            "max_bytes": int(max(raw_lens) if raw_lens else 0),
        }
    con.close()
    return out


def _graft_one_game(week4: Path, late: Path) -> None:
    from BackEnd.persistence.sqlite_collection import decode_doc, encode_doc, encode_id

    src = sqlite3.connect(str(week4))
    raws = src.execute("SELECT id, doc FROM games").fetchall()
    src.close()
    if not raws:
        raise SystemExit("week4 save has no games to graft")
    picked = None
    fallback = None
    for row_id, raw in raws:
        doc = decode_doc(raw)
        blob = json.dumps(doc, default=str)
        cand = (row_id, raw, doc)
        if doc.get("is_final") or int(doc.get("quarter") or 0) >= 4:
            if "Lancaster" in blob or "LANCASTER" in blob:
                picked = cand
                break
            fallback = fallback or cand
    if picked is None:
        picked = fallback
    if picked is None:
        row_id, raw = max(raws, key=lambda r: len(r[1]))
        picked = (row_id, raw, decode_doc(raw))
    _row_id, raw, doc = picked
    dst = sqlite3.connect(str(late))
    dst.execute(
        "INSERT OR REPLACE INTO games (id, doc) VALUES (?, ?)",
        (encode_id(doc.get("_id")), encode_doc(doc)),
    )
    dst.commit()
    dst.close()


def _bind_store(store) -> None:
    import BackEnd.persistence.store as store_mod
    from BackEnd.utils import stat_updater
    import BackEnd.api.franchise_routes as fr

    store_mod._STORE = store
    stat_updater._store = store
    stat_updater.db = store.db
    stat_updater.games_collection = store.games_collection
    stat_updater.teams_collection = store.teams_collection
    stat_updater.players_collection = store.players_collection
    stat_updater.franchise_team_data_collection = store.franchise_team_data_collection
    stat_updater.franchise_players_data_collection = store.franchise_players_data_collection
    fr._store = store
    fr.games_collection = store.games_collection
    fr.franchises_collection = store.franchises_collection
    fr.franchise_team_data_collection = store.franchise_team_data_collection
    fr.franchise_players_data_collection = store.franchise_players_data_collection
    fr.teams_collection = store.teams_collection
    fr.players_collection = store.players_collection
    fr.db = store.db


def _open_store(arm: str, sqlite_path: Path):
    if arm == "mongo":
        os.environ["ENVIRONMENT"] = "test"
        os.environ["GOB_PERSISTENCE"] = "mongo"
        os.environ["GOB_DB_MODE"] = "mongomock"
        os.environ["MONGO_URI"] = "mongodb://127.0.0.1:27017/gob-test"
        os.environ["MONGO_DB_NAME"] = "gob-test"
        os.environ.pop("GOB_LOOPBACK", None)
        os.environ.pop("GOB_BUILD_PROFILE", None)
        os.environ.pop("GOB_SQLITE_PATH", None)
        from BackEnd.persistence.sqlite_collection import decode_doc
        from BackEnd.persistence.sqlite import LOCAL_COLLECTIONS
        from BackEnd.persistence import create_store
        from BackEnd.env_config import resolve_database_environment

        con = sqlite3.connect(str(sqlite_path))
        names = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        docs = {}
        for name in LOCAL_COLLECTIONS:
            if name not in names:
                continue
            rows = con.execute(f'SELECT doc FROM "{name}"').fetchall()
            docs[name] = [decode_doc(raw) for (raw,) in rows]
        con.close()
        env = resolve_database_environment(
            pristine_env=dict(os.environ),
            repo_root=ROOT,
            target_environ=os.environ,
        )
        store = create_store(env)
        loaded = {}
        for name, rows in docs.items():
            if not rows:
                continue
            store.db[name].delete_many({})
            store.db[name].insert_many(rows)
            loaded[name] = len(rows)
        _bind_store(store)
        return store, loaded

    os.environ["GOB_SQLITE_PATH"] = str(sqlite_path)
    os.environ["GOB_PERSISTENCE"] = "sqlite"
    os.environ["ENVIRONMENT"] = "test"
    os.environ["GOB_DB_MODE"] = "mongomock"
    os.environ["MONGO_DB_NAME"] = "gob-test"
    from BackEnd.env_config import resolve_database_environment
    from BackEnd.persistence.store import create_store

    env = resolve_database_environment(
        pristine_env={
            "ENVIRONMENT": "test",
            "GOB_DB_MODE": "mongomock",
            "GOB_PERSISTENCE": "sqlite",
            "GOB_SQLITE_PATH": str(sqlite_path),
            "MONGO_DB_NAME": "gob-test",
        },
        repo_root=ROOT,
        target_environ={},
    )
    store = create_store(env)
    _bind_store(store)
    loaded = {
        name: store.db[name].estimated_document_count()
        for name in (
            "games",
            "franchises",
            "franchise_team_data",
            "franchise_players_data",
            "teams",
        )
    }
    return store, loaded


def _pick_target(store):
    games = list(store.games_collection.find({}))
    if not games:
        raise SystemExit("no games in store")
    final = [
        doc
        for doc in games
        if doc.get("is_final") or int(doc.get("quarter") or 0) >= 4
    ]
    pool = final or games
    for doc in pool:
        blob = json.dumps(doc, default=str)
        if "Lancaster" in blob or "LANCASTER" in blob:
            return doc
    return max(pool, key=lambda d: len(json.dumps(d, default=str)))


def _run_arm(arm: str, size: str, sqlite_path: Path) -> dict:
    store, loaded = _open_store(arm, sqlite_path)
    from bson import ObjectId
    from BackEnd.utils.game_id_utils import franchise_matchup_claim_key
    from BackEnd.api.franchise_routes import _finalize_team_attributes_for_game
    from BackEnd.utils import stat_updater

    sizes = _doc_sizes(sqlite_path)
    target = _pick_target(store)
    gid = target.get("_id") or target.get("game_id")
    home = target.get("home_team_id") or "LANCASTER"
    away = target.get("away_team_id") or "TEAM002"
    store.games_collection.update_one({"_id": gid}, {"$unset": {"player_em_eog_applied": ""}})
    claim_token = str(gid)
    matchup_key = franchise_matchup_claim_key(target)
    pull = {"applied_games": claim_token}
    if matchup_key:
        pull["applied_matchups"] = matchup_key
    store.franchises_collection.update_one({"_id": ObjectId(FID)}, {"$pull": pull})
    store.franchises_collection.update_one({"_id": FID}, {"$pull": pull})

    maps_times = []
    for _ in range(5):
        t0 = time.perf_counter()
        stat_updater._build_franchise_team_maps_from_ftd(ObjectId(FID))
        maps_times.append(time.perf_counter() - t0)
    maps_times.sort()

    week = int(target.get("week") or 4)
    setup_times = []
    for _ in range(8):
        t0 = time.perf_counter()
        store.games_collection.find_one(
            {
                "week": week,
                "franchise_id": str(FID),
                "$or": [
                    {"team1_id": away, "team2_id": home},
                    {"team1_id": home, "team2_id": away},
                ],
            }
        )
        setup_times.append(time.perf_counter() - t0)
    setup_times.sort()

    stat_updater.reset_finalize_subtiming()
    t0 = time.perf_counter()
    stat_updater.finalize_game(str(gid), mode="franchise", franchise_id=FID)
    score = target.get("score") or {}
    home_score = int(score.get("Lancaster") or score.get(home) or 0)
    away_score = int(score.get("Team002") or score.get(away) or 0)
    winner = home if home_score >= away_score else away
    loser = away if winner == home else home
    _finalize_team_attributes_for_game(
        gid,
        ObjectId(FID),
        home,
        away,
        winner,
        loser,
        home_score if winner == home else away_score,
        away_score if winner == home else home_score,
        week=week,
    )
    wall_s = time.perf_counter() - t0
    fsub = stat_updater.pop_finalize_subtiming()
    return {
        "arm": arm,
        "size": size,
        "loaded": loaded,
        "doc_sizes": sizes,
        "target": {
            "game": str(gid),
            "week": week,
            "home": home,
            "away": away,
            "doc_bytes": len(json.dumps(target, default=str)),
        },
        "maps_s_median": round(maps_times[len(maps_times) // 2], 4),
        "maps_s_all": [round(x, 4) for x in maps_times],
        "maps_s_per_week_189": round(maps_times[len(maps_times) // 2] * 189, 1),
        "setup_find_one_s_median": round(setup_times[len(setup_times) // 2], 4),
        "setup_find_one_s_per_week_63": round(setup_times[len(setup_times) // 2] * 63, 1),
        "persist_wall_s": round(wall_s, 3),
        "persist_wall_s_per_week": round(wall_s * WEEK_GAMES, 1),
        "finalize_subtiming": {k: round(v, 3) for k, v in fsub.items()},
    }


def _child(args: list[str]) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        raise SystemExit(proc.returncode)
    line = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")][-1]
    return json.loads(line)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=("mongo", "sqlite"))
    parser.add_argument("--size", choices=("week4", "late"))
    parser.add_argument("--sqlite", type=Path)
    args = parser.parse_args()
    if args.arm:
        print(json.dumps(_run_arm(args.arm, args.size or "week4", args.sqlite or WEEK4), default=str))
        return 0

    if not WEEK4_SRC.exists():
        raise SystemExit(f"missing {WEEK4_SRC}")
    if not SEASON.exists():
        raise SystemExit(f"missing {SEASON}")
    _backup(WEEK4_SRC, WEEK4)
    _backup(SEASON, LATE)
    _graft_one_game(WEEK4, LATE)
    results = {}
    for arm in ("mongo", "sqlite"):
        for size, path in (("week4", WEEK4), ("late", LATE)):
            results[f"{arm}_{size}"] = _child(
                ["--arm", arm, "--size", size, "--sqlite", str(path)]
            )
    print(json.dumps(results, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
