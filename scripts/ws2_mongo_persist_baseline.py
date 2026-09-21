#!/usr/bin/env python3
"""Same finalize+EOG persist path on the Mongo adapter (mongomock).

Loads the 4-week catalog save into mongomock, re-opens the finalize claim,
runs finalize_game + team-attr EOG, and reports wall / writes / bytes decoded
in the same shape as the SQLite measurement. Does not touch Atlas.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SRC = Path("/tmp/ws2-catalog-season.sqlite")
FID = "6aaff7b8f37ac3a890ef6093"
WEEK_GAMES = 63
HOT = (
    "games",
    "franchises",
    "franchise_team_data",
    "franchise_players_data",
    "teams",
    "defenses",
    "players",
    "plays",
)


class Counters:
    def __init__(self) -> None:
        self.api = Counter()
        self.writes = 0
        self.reads = 0
        self.docs_decoded = Counter()
        self.decode_bytes = Counter()
        self.bulk_ops = 0


def _load_sqlite_docs(path: Path) -> dict[str, list[dict]]:
    from BackEnd.persistence.sqlite_collection import decode_doc
    from BackEnd.persistence.sqlite import LOCAL_COLLECTIONS

    con = sqlite3.connect(str(path))
    out: dict[str, list[dict]] = {}
    names = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for name in LOCAL_COLLECTIONS:
        if name not in names:
            continue
        rows = con.execute(f'SELECT doc FROM "{name}"').fetchall()
        out[name] = [decode_doc(raw) for (raw,) in rows]
    con.close()
    return out


def _instrument(c: Counters) -> None:
    import mongomock.collection

    methods = (
        "find",
        "insert_one",
        "insert_many",
        "update_one",
        "update_many",
        "replace_one",
        "delete_one",
        "delete_many",
        "bulk_write",
        "count_documents",
        "find_one_and_update",
    )
    writes = {
        "insert_one",
        "insert_many",
        "update_one",
        "update_many",
        "replace_one",
        "delete_one",
        "delete_many",
        "bulk_write",
        "find_one_and_update",
    }

    def _count_docs(name: str, docs) -> None:
        n = 0
        for doc in docs:
            if isinstance(doc, dict):
                n += 1
                c.decode_bytes[name] += len(json.dumps(doc, default=str))
        c.docs_decoded[name] += n

    class WrappedCursor:
        def __init__(self, cursor, name: str):
            self._cursor = cursor
            self._name = name
            self._listed = None

        def _materialize(self):
            if self._listed is None:
                self._listed = list(self._cursor)
                _count_docs(self._name, self._listed)
            return self._listed

        def sort(self, *a, **k):
            self._cursor = self._cursor.sort(*a, **k)
            return self

        def limit(self, n):
            self._cursor = self._cursor.limit(n)
            return self

        def skip(self, n):
            self._cursor = self._cursor.skip(n)
            return self

        def __iter__(self):
            return iter(self._materialize())

        def __next__(self):
            if not hasattr(self, "_it"):
                self._it = iter(self._materialize())
            return next(self._it)

        def __len__(self):
            return len(self._materialize())

    Coll = mongomock.collection.Collection
    saved = {name: getattr(Coll, name) for name in methods if hasattr(Coll, name)}

    def wrap(name: str, fn):
        def wrapped(self, *a, **k):
            c.api[f"{self.name}.{name}"] += 1
            if name in writes:
                c.writes += 1
                if name == "bulk_write" and a:
                    c.bulk_ops += len(a[0] or [])
            else:
                c.reads += 1
            result = fn(self, *a, **k)
            if name == "find":
                return WrappedCursor(result, self.name)
            if name == "find_one" and isinstance(result, dict):
                _count_docs(self.name, [result])
            return result

        return wrapped

    for method_name, orig in saved.items():
        setattr(Coll, method_name, wrap(method_name, orig))


def _reset(c: Counters) -> None:
    c.api.clear()
    c.writes = 0
    c.reads = 0
    c.docs_decoded.clear()
    c.decode_bytes.clear()
    c.bulk_ops = 0


def _pick_target(store):
    games = list(store.games_collection.find({}))
    target = None
    for doc in games:
        if doc.get("week") == 4 or (isinstance(doc.get("score"), dict) and "Team002" in (doc.get("score") or {})):
            if (doc.get("home_team_id") or "") in {"LANCASTER", "TEAM002"} or (
                doc.get("away_team_id") or ""
            ) in {"LANCASTER", "TEAM002"}:
                target = doc
                break
    if target is None:
        target = max(games, key=lambda d: len(json.dumps(d, default=str)))
    return target


def main() -> int:
    if not SRC.exists():
        raise SystemExit(f"missing save {SRC}")

    os.environ["ENVIRONMENT"] = "test"
    os.environ["GOB_PERSISTENCE"] = "mongo"
    os.environ["GOB_DB_MODE"] = "mongomock"
    os.environ["MONGO_URI"] = "mongodb://127.0.0.1:27017/gob-test"
    os.environ["MONGO_DB_NAME"] = "gob-test"
    os.environ.pop("GOB_LOOPBACK", None)
    os.environ.pop("GOB_BUILD_PROFILE", None)
    os.environ.pop("GOB_SQLITE_PATH", None)

    docs = _load_sqlite_docs(SRC)
    from BackEnd.persistence import create_store
    from BackEnd.env_config import resolve_database_environment

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

    # Bind module-level stores used by persist callers before they import.
    import BackEnd.persistence.store as store_mod

    store_mod._STORE = store

    from bson import ObjectId
    from BackEnd.utils.game_id_utils import franchise_matchup_claim_key
    from BackEnd.api.franchise_routes import _finalize_team_attributes_for_game
    from BackEnd.utils import stat_updater

    stat_updater._store = store
    import BackEnd.api.franchise_routes as fr

    fr._store = store
    fr.games_collection = store.games_collection
    fr.franchises_collection = store.franchises_collection
    fr.franchise_team_data_collection = store.franchise_team_data_collection
    fr.franchise_players_data_collection = store.franchise_players_data_collection
    fr.teams_collection = store.teams_collection
    fr.players_collection = store.players_collection
    fr.db = store.db

    counts = Counters()
    _instrument(counts)

    target = _pick_target(store)
    gid = target.get("_id") or target.get("game_id")
    home = target.get("home_team_id") or "LANCASTER"
    away = target.get("away_team_id") or "TEAM002"
    store.games_collection.update_one({"_id": gid}, {"$unset": {"player_em_eog_applied": ""}})
    claim_token = str(gid)
    matchup_key = franchise_matchup_claim_key(target)
    pull: dict = {"applied_games": claim_token}
    if matchup_key:
        pull["applied_matchups"] = matchup_key
    store.franchises_collection.update_one({"_id": ObjectId(FID)}, {"$pull": pull})
    _reset(counts)

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
        week=4,
    )
    wall_s = time.perf_counter() - t0

    # Capstone colocated Atlas is ~1–3 ms per round trip. Midpoint 2 ms.
    round_trips = counts.writes + counts.reads
    hosted_rtt_s = round_trips * 0.002
    out = {
        "adapter": "mongo/mongomock",
        "hosted": False,
        "games": loaded.get("games"),
        "loaded": loaded,
        "target": {
            "game": str(gid),
            "week": target.get("week"),
            "home": home,
            "away": away,
            "doc_bytes": len(json.dumps(target, default=str)),
        },
        "writes": counts.writes,
        "reads": counts.reads,
        "round_trips": round_trips,
        "writes_per_week": counts.writes * WEEK_GAMES,
        "round_trips_per_week": round_trips * WEEK_GAMES,
        "bulk_ops": counts.bulk_ops,
        "wall_s": round(wall_s, 3),
        "wall_s_per_week": round(wall_s * WEEK_GAMES, 1),
        "hosted_rtt_estimate_s_per_game": round(hosted_rtt_s, 3),
        "hosted_rtt_estimate_s_per_week": round(hosted_rtt_s * WEEK_GAMES, 1),
        "hosted_wall_estimate_s_per_week": round((wall_s + hosted_rtt_s) * WEEK_GAMES, 1),
        "docs_decoded": dict(counts.docs_decoded),
        "decode_bytes": dict(counts.decode_bytes),
        "decode_bytes_per_week": {name: n * WEEK_GAMES for name, n in counts.decode_bytes.items()},
        "decode_bytes_total_per_week": sum(counts.decode_bytes.values()) * WEEK_GAMES,
        "api": dict(counts.api.most_common()),
        "hot_tables": {name: loaded.get(name) for name in HOT},
    }
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
