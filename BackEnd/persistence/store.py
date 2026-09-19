"""Process-wide persistence store singleton."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from BackEnd.env_config import (
    EnvironmentConfigurationError,
    resolve_database_environment,
)
from BackEnd.persistence.protocol import PersistenceStore

# Snapshot the REAL process environment before any dotenv file is loaded. The
# prod-access opt-in and GOB_PERSISTENCE are read from this snapshot only, so
# dropping those keys into .env / .env.local cannot permanently disarm the
# guard for every local script.
_PRISTINE_ENV = dict(os.environ)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_STORE: PersistenceStore | None = None
_STORE_LOCK = threading.Lock()


def create_store(db_env) -> PersistenceStore:
    """Build a store for ``db_env.persistence``. SQLite is not implemented yet."""
    backend = getattr(db_env, "persistence", None) or "mongo"
    if backend == "sqlite":
        raise EnvironmentConfigurationError(
            "SQLite persistence is not implemented yet"
        )
    if backend != "mongo":
        raise EnvironmentConfigurationError(
            f"Unknown persistence backend {backend!r}"
        )
    from BackEnd.persistence.mongo import MongoStore
    return MongoStore(db_env)


def get_store() -> PersistenceStore:
    """Return the process-wide store. Everyone shares one client."""
    global _STORE
    if _STORE is None:
        with _STORE_LOCK:
            if _STORE is None:
                db_env = resolve_database_environment(
                    pristine_env=_PRISTINE_ENV,
                    repo_root=_REPO_ROOT,
                    target_environ=os.environ,
                )
                print(
                    f"🔧 [DB CONFIG] source={db_env.source} environment={db_env.environment} "
                    f"database={db_env.db_name} mode={db_env.db_mode}",
                    file=sys.stderr,
                    flush=True,
                )
                _STORE = create_store(db_env)
    return _STORE
