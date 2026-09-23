#!/usr/bin/env python3
"""Export the four catalog collections into the desktop sidecar.

READ-ONLY against Atlas. This process must start with GOB_DB_ACCESS=read and
never opens a write connection. The prod/staging guard in script_db enforces
the same on the client.

Canonical source is production (``gob``): that is the rulebook hosted players
already run. Staging can hold unpublished play-builder work. FCP/HCT are
published staging→production; production is the last published snapshot.

  GOB_DB_ACCESS=read python scripts/export_catalog_sidecar.py
  GOB_DB_ACCESS=read python scripts/export_catalog_sidecar.py --from-repo-fixtures

Production read (Jamie). Scratch paths only — never the committed sidecar::

  GOB_DB_ACCESS=read ENVIRONMENT=production MONGO_DB_NAME=gob \\
    MONGO_URI='mongodb+srv://…/dbname' \\
    python scripts/export_catalog_sidecar.py --target gob \\
      --output /tmp/catalog-prod.sqlite --json-output /tmp/catalog-prod.json

Compare printed ``version=`` to ``c4dcc375ce01f3b7fd89cf29b8d0db949f6bcf4da4a22763e1ebca072998be8c``.

Two exports of the same documents produce byte-identical ``catalog.sqlite``
and ``catalog.json`` files (stable ordering, fixed exported_at).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.persistence.catalog import (  # noqa: E402
    CATALOG_COLLECTIONS,
    assert_export_is_read_only,
    load_repo_fixture_docs,
    write_catalog_json,
    write_catalog_sqlite,
)
from BackEnd.runtime_paths import bundle_path  # noqa: E402
from BackEnd.script_db import (  # noqa: E402
    PRODUCTION_DB,
    STAGING_DB,
    ScriptDatabaseError,
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
        help="Build from play_skeletons_export.json / defenses_export.json / in-repo FCP-HCT.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=bundle_path("catalog.sqlite"),
        help="Sidecar sqlite path (default: bundle_root/catalog.sqlite).",
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
    return parser.parse_args()


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
        docs = {}
        for name in CATALOG_COLLECTIONS:
            docs[name] = list(connection.database[name].find({}))
        return docs
    finally:
        connection.close()


def main() -> int:
    args = _parse_args()
    if args.from_repo_fixtures:
        docs = load_repo_fixture_docs()
        source = "repo-fixtures"
    else:
        docs = _load_from_atlas(args.target, args.repo_root)
        source = args.target
    meta = write_catalog_sqlite(docs, args.output, source=source)
    json_path = args.json_output
    if json_path is None:
        json_path = args.output.with_suffix(".json")
    write_catalog_json(docs, json_path, source=source)
    print(
        f"CATALOG_SIDECAR path={args.output} source={source} version={meta['version']} "
        f"plays={meta['counts']['plays']} defenses={meta['counts']['defenses']} "
        f"fcp={meta['counts']['fcp_skeletons']} hct={meta['counts']['hct_skeletons']} "
        f"bytes={args.output.stat().st_size}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
