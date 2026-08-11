"""Single application-runtime environment resolver.

This module owns dotenv selection for the backend application. Maintenance-script
connection policy is intentionally deferred to env_streamlining Task 5.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping, MutableMapping
from urllib.parse import unquote, urlparse

from dotenv import dotenv_values


ALLOWED_ENVIRONMENTS = frozenset({"development", "test", "staging", "production"})
PROTECTED_DOTENV_KEYS = frozenset({"GOB_DB_ACCESS", "GOB_DB_MODE"})
REAL_DB_CONFIG_KEYS = frozenset({"MONGO_URI", "MONGO_DB_NAME"})


class EnvironmentConfigurationError(RuntimeError):
    """Raised before database initialization when environment identity is unsafe."""


@dataclass(frozen=True)
class DatabaseEnvironment:
    environment: str
    db_mode: str
    db_name: str
    mongo_uri: str | None
    source: str
    process_environment: Mapping[str, str]


def database_name_from_uri(uri: str) -> str:
    """Return the decoded database path from a Mongo URI, or fail closed."""
    try:
        parsed = urlparse(uri)
    except Exception as exc:
        raise EnvironmentConfigurationError("MONGO_URI could not be parsed") from exc
    db_name = unquote((parsed.path or "").lstrip("/")).strip()
    if not db_name or "/" in db_name:
        raise EnvironmentConfigurationError(
            "MONGO_URI must include exactly one database name in its path"
        )
    return db_name


def _is_railway(pristine: Mapping[str, str]) -> bool:
    return any(key.startswith("RAILWAY_") for key in pristine)


def _load_local_values(repo_root: Path) -> dict[str, str]:
    path = repo_root / ".env.local"
    if not path.is_file():
        raise EnvironmentConfigurationError(
            f"Local development requires {path}. Copy .env.example to .env.local "
            "and configure staging credentials. No .env fallback is permitted."
        )
    raw = dotenv_values(path)
    protected = sorted(key for key in PROTECTED_DOTENV_KEYS if raw.get(key))
    if protected:
        raise EnvironmentConfigurationError(
            "Production authorization/test mode cannot come from .env.local: "
            + ", ".join(protected)
        )
    return {str(key): str(value) for key, value in raw.items() if value is not None}


def resolve_database_environment(
    *,
    pristine_env: Mapping[str, str] | None = None,
    repo_root: Path | None = None,
    target_environ: MutableMapping[str, str] | None = None,
) -> DatabaseEnvironment:
    """Resolve and validate application database configuration.

    `pristine_env` must be captured before this resolver loads `.env.local`. Values
    loaded by a caller before importing this module cannot be distinguished from shell
    values; Task 5 removes those independent loaders.
    """
    pristine = dict(os.environ if pristine_env is None else pristine_env)
    root = repo_root or Path(__file__).resolve().parent.parent
    target = os.environ if target_environ is None else target_environ
    mode = str(pristine.get("GOB_DB_MODE") or "mongo").strip().lower()

    if mode not in {"mongo", "mongomock"}:
        raise EnvironmentConfigurationError(
            "GOB_DB_MODE must be 'mongo' or 'mongomock'"
        )

    if mode == "mongomock":
        db_name = str(pristine.get("MONGO_DB_NAME") or "gob-test").strip()
        environment = str(pristine.get("ENVIRONMENT") or "test").strip().lower()
        if environment != "test":
            raise EnvironmentConfigurationError(
                "GOB_DB_MODE=mongomock requires ENVIRONMENT=test"
            )
        if db_name in {"gob", "gob-staging"}:
            raise EnvironmentConfigurationError(
                "Mongomock database name must not be gob or gob-staging"
            )
        target.setdefault("ENVIRONMENT", environment)
        target.setdefault("MONGO_DB_NAME", db_name)
        return DatabaseEnvironment(
            environment=environment,
            db_mode=mode,
            db_name=db_name,
            mongo_uri=None,
            source="explicit-mongomock",
            process_environment=pristine,
        )

    if _is_railway(pristine):
        values = pristine
        source = "railway-process"
    elif any(str(pristine.get(key) or "").strip() for key in REAL_DB_CONFIG_KEYS):
        values = pristine
        source = "explicit-process"
    else:
        local_values = _load_local_values(root)
        for key, value in local_values.items():
            target.setdefault(key, value)
        values = {**local_values, **pristine}
        source = str(root / ".env.local")

    environment = str(values.get("ENVIRONMENT") or "").strip().lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise EnvironmentConfigurationError(
            "ENVIRONMENT must be one of development, test, staging, or production"
        )
    uri = str(values.get("MONGO_URI") or "").strip()
    db_name = str(values.get("MONGO_DB_NAME") or "").strip()
    if not uri or not db_name:
        raise EnvironmentConfigurationError(
            "Real Mongo configuration requires both MONGO_URI and MONGO_DB_NAME"
        )
    uri_db_name = database_name_from_uri(uri)
    if uri_db_name != db_name:
        raise EnvironmentConfigurationError(
            f"Database identity mismatch: MONGO_URI names {uri_db_name!r}, "
            f"but MONGO_DB_NAME is {db_name!r}"
        )

    expected = {
        "development": "gob-staging",
        "staging": "gob-staging",
        "production": "gob",
    }.get(environment)
    if expected and db_name != expected:
        raise EnvironmentConfigurationError(
            f"ENVIRONMENT={environment} requires MONGO_DB_NAME={expected}, got {db_name}"
        )
    if environment == "test" and db_name in {"gob", "gob-staging"}:
        raise EnvironmentConfigurationError(
            "ENVIRONMENT=test cannot target gob or gob-staging"
        )

    return DatabaseEnvironment(
        environment=environment,
        db_mode=mode,
        db_name=db_name,
        mongo_uri=uri,
        source=source,
        process_environment=pristine,
    )
