#!/usr/bin/env python3
"""Measure EOG persist after the generated-column + transaction fix.

Copies the live 4-week save, times persist at that size, then synthesizes
~1,600 game docs (week-26 scale) and times the same persist again. Also benches
the sim ``find_one`` point path at both sizes.

Does not change the live loopback save. Season stays parked.

  python scripts/ws2_eog_persist_diag.py
  python scripts/ws2_eog_persist_diag.py --week4 /tmp/ws2-eog-diag-4w.sqlite
  python scripts/ws2_eog_persist_diag.py --late /tmp/ws2-eog-diag-late.sqlite
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SRC = Path("/tmp/ws2-catalog-season.sqlite")
COPY_4W = Path("/tmp/ws2-eog-diag-4w.sqlite")
COPY_LATE = Path("/tmp/ws2-eog-diag-late.sqlite")
TARGET_LATE_GAMES = 1600
WEEK_GAMES = 63
FID = "6aaff7b8f37ac3a890ef6093"


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


def _pragmas_and_sizes(path: Path) -> dict:
    con = sqlite3.connect(str(path))
    pragmas = {}
    for name in ("journal_mode", "synchronous", "wal_autocheckpoint"):
        pragmas[name] = con.execute(f"PRAGMA {name}").fetchone()[0]
    tables = {}
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1"):
        n = con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        raw = con.execute(f'SELECT COALESCE(SUM(LENGTH(doc)),0) FROM "{name}"').fetchone()[0]
        tables[name] = {"rows": n, "json_bytes": int(raw or 0)}
    indexes = con.execute(
        "SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
    ).fetchall()
    cols = {}
    for name in ("games", "franchise_players_data", "franchise_team_data"):
        if name in tables:
            cols[name] = [row[1] for row in con.execute(f'PRAGMA table_xinfo("{name}")').fetchall()]
    con.close()
    return {"pragmas": pragmas, "tables": tables, "sql_indexes": indexes, "columns": cols}


class Counters:
    def __init__(self) -> None:
        self.api = Counter()
        self.commits = 0
        self.selects = Counter()
        self.full_scans = Counter()
        self.docs_decoded = Counter()
        self.decode_bytes = Counter()
        self.bulk_ops = 0


def _instrument(store, c: Counters) -> None:
    from contextlib import contextmanager

    from BackEnd.persistence.sqlite_collection import SqliteCollection
    from BackEnd.persistence import sqlite_schema
    from BackEnd.persistence.sqlite_schema import compile_filter

    orig_select = SqliteCollection._select
    orig_commit = SqliteCollection._commit
    orig_tx = sqlite_schema.store_transaction

    def commit(self):
        if self._state is None or self._state.tx_depth == 0:
            c.commits += 1
        return orig_commit(self)

    @contextmanager
    def counted_tx(state):
        outermost = state.tx_depth == 0
        with orig_tx(state):
            yield
            if outermost:
                c.commits += 1

    sqlite_schema.store_transaction = counted_tx
    import BackEnd.persistence.sqlite_collection as sqlite_collection_mod

    sqlite_collection_mod.store_transaction = counted_tx
    store.transaction = lambda: counted_tx(store._state)
    SqliteCollection._commit = commit

    def select(self, filt=None, **kwargs):
        compiled = compile_filter(filt)
        c.selects[self.name] += 1
        if compiled is None:
            c.full_scans[self.name] += 1
        out = orig_select(self, filt, **kwargs)
        c.docs_decoded[self.name] += len(out)
        for _rid, doc in out:
            c.decode_bytes[self.name] += len(json.dumps(doc, default=str))
        return out

    SqliteCollection._select = select

    for name in (
        "find",
        "find_one",
        "insert_one",
        "insert_many",
        "update_one",
        "update_many",
        "replace_one",
        "delete_one",
        "delete_many",
        "bulk_write",
        "count_documents",
    ):
        orig = getattr(SqliteCollection, name)

        def wrap(method_name: str, fn):
            def wrapped(self, *a, **k):
                c.api[f"{self.name}.{method_name}"] += 1
                if method_name == "bulk_write" and a:
                    c.bulk_ops += len(a[0] or [])
                return fn(self, *a, **k)

            return wrapped

        setattr(SqliteCollection, name, wrap(name, orig))


def _reset(c: Counters) -> None:
    c.api.clear()
    c.commits = 0
    c.selects.clear()
    c.full_scans.clear()
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


def _grow_games(store, target_n: int) -> int:
    from bson import ObjectId

    existing = list(store.games_collection.find({}))
    have = len(existing)
    if have >= target_n or not existing:
        return have
    clones = []
    while have + len(clones) < target_n:
        src = existing[(have + len(clones)) % len(existing)]
        clone = copy.deepcopy(src)
        clone["_id"] = ObjectId()
        clones.append(clone)
    store.games_collection.insert_many(clones)
    return have + len(clones)


def _bench_sim_reads(store, gid, n: int = 50) -> dict:
    from BackEnd.persistence.sqlite_collection import SqliteCollection
    from BackEnd.persistence.sqlite_schema import compile_filter

    decoded = []
    orig = SqliteCollection._select

    def counting(self, filt=None, **kwargs):
        rows = orig(self, filt, **kwargs)
        if self.name == "games":
            decoded.append((compile_filter(filt) is not None, len(rows)))
        return rows

    SqliteCollection._select = counting
    t0 = time.perf_counter()
    for _ in range(n):
        store.games_collection.find_one({"_id": gid})
    pk_s = time.perf_counter() - t0
    pk_decoded = decoded[:]
    decoded.clear()
    t0 = time.perf_counter()
    for _ in range(n):
        store.games_collection.find_one({"_id": gid, "players.playerId": "__none__"})
    residual_s = time.perf_counter() - t0
    residual_decoded = decoded[:]
    decoded.clear()
    t0 = time.perf_counter()
    store.games_collection.find_one({"franchise_id": FID})
    fid_s = time.perf_counter() - t0
    fid_decoded = decoded[:]
    SqliteCollection._select = orig
    return {
        "n": n,
        "find_one_by_id_ms": round(1000.0 * pk_s / n, 3),
        "find_one_by_id_docs_decoded": pk_decoded[0][1] if pk_decoded else None,
        "find_one_by_id_used_index": pk_decoded[0][0] if pk_decoded else None,
        "find_one_id_plus_player_ms": round(1000.0 * residual_s / n, 3),
        "find_one_id_plus_player_docs_decoded": residual_decoded[0][1] if residual_decoded else None,
        "find_one_id_plus_player_used_index": residual_decoded[0][0] if residual_decoded else None,
        "find_one_by_franchise_id_ms": round(1000.0 * fid_s, 3),
        "find_one_by_franchise_id_docs_decoded": fid_decoded[0][1] if fid_decoded else None,
        "find_one_by_franchise_id_used_index": fid_decoded[0][0] if fid_decoded else None,
    }


def _run_persist(label: str, sqlite_path: Path, grow_to: int | None = None) -> dict:
    os.environ["GOB_SQLITE_PATH"] = str(sqlite_path)
    from BackEnd.loopback_env import apply_loopback_env

    apply_loopback_env()
    from BackEnd.persistence import get_store
    from bson import ObjectId

    store = get_store()
    grown = None
    if grow_to:
        grown = _grow_games(store, grow_to)
    sizes = _pragmas_and_sizes(sqlite_path)
    counts = Counters()
    _instrument(store, counts)
    target = _pick_target(store)
    gid = target.get("_id") or target.get("game_id")
    home = target.get("home_team_id") or "LANCASTER"
    away = target.get("away_team_id") or "TEAM002"
    store.games_collection.update_one({"_id": gid}, {"$unset": {"player_em_eog_applied": ""}})
    from BackEnd.utils.game_id_utils import franchise_matchup_claim_key

    claim_token = str(gid)
    matchup_key = franchise_matchup_claim_key(target)
    pull: dict = {"applied_games": claim_token}
    if matchup_key:
        pull["applied_matchups"] = matchup_key
    store.franchises_collection.update_one({"_id": ObjectId(FID)}, {"$pull": pull})
    store.franchises_collection.update_one(
        {"_id": FID},
        {"$pull": pull},
    )
    _reset(counts)

    from BackEnd.api.franchise_routes import _finalize_team_attributes_for_game
    from BackEnd.utils import stat_updater

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
    sim_reads = _bench_sim_reads(store, gid)
    games_n = sizes["tables"].get("games", {}).get("rows", 0)
    if grow_to:
        games_n = max(games_n, grown or 0)
    return {
        "label": label,
        "games": games_n,
        "grown_to": grown,
        "target": {
            "game": str(gid),
            "week": target.get("week"),
            "home": home,
            "away": away,
            "doc_bytes": len(json.dumps(target, default=str)),
        },
        "commits": counts.commits,
        "commits_per_week": counts.commits * WEEK_GAMES,
        "bulk_ops": counts.bulk_ops,
        "wall_s": round(wall_s, 3),
        "wall_s_per_week": round(wall_s * WEEK_GAMES, 1),
        "full_scans": dict(counts.full_scans),
        "selects": dict(counts.selects),
        "docs_decoded": dict(counts.docs_decoded),
        "decode_bytes": dict(counts.decode_bytes),
        "decode_bytes_per_week": {
            name: n * WEEK_GAMES for name, n in counts.decode_bytes.items()
        },
        "api": dict(counts.api.most_common()),
        "generated_columns": sizes["columns"],
        "sql_index_count": len(sizes["sql_indexes"]),
        "sim_reads": sim_reads,
        "pragmas": sizes["pragmas"],
        "hot_tables": {
            name: sizes["tables"].get(name)
            for name in ("games", "franchise_players_data", "franchise_team_data")
        },
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
    parser.add_argument("--week4", metavar="SQLITE")
    parser.add_argument("--late", metavar="SQLITE")
    args = parser.parse_args()

    if args.week4:
        print(json.dumps(_run_persist("week4", Path(args.week4)), default=str))
        return 0
    if args.late:
        print(json.dumps(_run_persist("late", Path(args.late), grow_to=TARGET_LATE_GAMES), default=str))
        return 0

    if not SRC.exists():
        raise SystemExit(f"missing save {SRC}")
    _backup(SRC, COPY_4W)
    _backup(SRC, COPY_LATE)
    four = _child(["--week4", str(COPY_4W)])
    late = _child(["--late", str(COPY_LATE)])
    print(json.dumps({"week4": four, "late": late}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
