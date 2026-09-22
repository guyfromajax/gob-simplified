#!/usr/bin/env python3
"""Export the universal teams and players collections into the desktop bundle.

READ-ONLY against Atlas. This process must start with GOB_DB_ACCESS=read and
never opens a write connection. The prod/staging guard in script_db enforces
the same on the client.

Canonical source is production (``gob``): that is the league hosted players
already run. Staging can hold unpublished roster or Team Builder work.

  GOB_DB_ACCESS=read python scripts/export_base_league.py
  GOB_DB_ACCESS=read python scripts/export_base_league.py --from-repo-fixtures

Production read (Jamie). Scratch paths only — never the committed bundle::

  GOB_DB_ACCESS=read ENVIRONMENT=production MONGO_DB_NAME=gob \\
    MONGO_URI='mongodb+srv://…/gob' \\
    python scripts/export_base_league.py --target gob \\
      --output /tmp/base-league-prod.sqlite --json-output /tmp/base-league-prod.json

Compare printed ``version=`` to ``35e43c9a2970cb105fef35505fbc9536d856392ca0bf88e53758856d54a1a63c``.

Two exports of the same documents produce byte-identical ``base_league.sqlite``
and ``base_league.json`` files (stable ordering, fixed exported_at).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.persistence.base_league import (  # noqa: E402
    EXPECTED_TEAM_COUNT,
    LEAGUE_COLLECTIONS,
    assert_export_is_read_only,
    fixture_league_docs,
    write_league_json,
    write_league_sqlite,
)
from BackEnd.runtime_paths import bundle_path  # noqa: E402
from BackEnd.script_db import (  # noqa: E402
    PRODUCTION_DB,
    STAGING_DB,
    connect_script_database,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        choices=(PRODUCTION_DB, STAGING_DB),
        default=PRODUCTION_DB,
        help="Atlas database to read. Default: gob (production).",
    )
    parser.add_argument(
        "--from-repo-fixtures",
        action="store_true",
        help="Build the tiny two-team unit-test fixture (not the shipping 128).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=bundle_path("base_league.sqlite"),
        help="League sqlite path (default: bundle_root/base_league.sqlite).",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Optional canonical JSON dump for release diffs.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help="Root used to resolve .env.local for staging reads.",
    )
    parser.add_argument(
        "--allow-count-mismatch",
        action="store_true",
        help="Do not refuse an export that is not exactly 128 teams.",
    )
    return parser.parse_args()


def _player_belongs(player: dict, team_ids: set[str], player_ids: set[str]) -> bool:
    pid = player.get("_id")
    if pid is not None and str(pid) in player_ids:
        return True
    alt = player.get("player_id")
    if alt is not None and str(alt) in player_ids:
        return True
    tid = player.get("team_id")
    if tid is not None and str(tid) in team_ids:
        return True
    return False


def _select_base_league(raw_teams: list[dict], raw_players: list[dict]) -> dict:
    """Keep the 128-program league; drop orphan / non-league rows if present."""
    with_conference = [
        doc
        for doc in raw_teams
        if doc.get("name")
        and not str(doc.get("name")).startswith("Team")
        and _conference_ok(doc.get("conference"))
    ]
    teams = with_conference if len(with_conference) == EXPECTED_TEAM_COUNT else list(raw_teams)
    team_ids = {str(doc["_id"]) for doc in teams if doc.get("_id") is not None}
    player_ids: set[str] = set()
    for team in teams:
        for pid in team.get("player_ids") or []:
            player_ids.add(str(pid))
    players = [
        doc
        for doc in raw_players
        if _player_belongs(doc, team_ids, player_ids)
    ]
    return {"teams": teams, "players": players}


def _conference_ok(value: object) -> bool:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return False
    return 1 <= number <= 16


def _load_from_atlas(target: str, repo_root: Path) -> dict:
    assert_export_is_read_only()
    connection = connect_script_database(
        target=target,
        access="read",
        pristine_env=dict(os.environ),
        repo_root=repo_root,
        force_local_staging=(target == STAGING_DB),
    )
    try:
        raw = {name: list(connection.database[name].find({})) for name in LEAGUE_COLLECTIONS}
        return _select_base_league(raw["teams"], raw["players"])
    finally:
        connection.close()


def main() -> int:
    args = _parse_args()
    if args.from_repo_fixtures:
        docs = fixture_league_docs()
        source = "repo-fixtures"
    else:
        docs = _load_from_atlas(args.target, args.repo_root)
        source = args.target
    team_count = len(docs.get("teams") or [])
    if team_count != EXPECTED_TEAM_COUNT and not args.allow_count_mismatch:
        names = sorted(str(doc.get("name") or "") for doc in docs.get("teams") or [])
        print(
            f"REFUSED teams={team_count} expected={EXPECTED_TEAM_COUNT} "
            f"names={names[:20]}{'…' if len(names) > 20 else ''}",
            file=sys.stderr,
            flush=True,
        )
        return 2
    meta = write_league_sqlite(docs, args.output, source=source)
    json_path = args.json_output
    if json_path is None:
        json_path = args.output.with_suffix(".json")
    write_league_json(docs, json_path, source=source)
    print(
        f"BASE_LEAGUE path={args.output} source={source} version={meta['version']} "
        f"teams={meta['counts']['teams']} players={meta['counts']['players']} "
        f"bytes={args.output.stat().st_size}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
