from pathlib import Path

import pytest

from BackEnd.env_config import (
    EnvironmentConfigurationError,
    database_name_from_uri,
    resolve_database_environment,
)


def _uri(db_name: str) -> str:
    return f"mongodb://example.invalid/{db_name}"


def test_missing_local_env_fails_without_dotenv_fallback(tmp_path: Path):
    (tmp_path / ".env").write_text(
        "ENVIRONMENT=production\nMONGO_URI=mongodb://example.invalid/gob\nMONGO_DB_NAME=gob\n"
    )
    with pytest.raises(EnvironmentConfigurationError, match="No .env fallback"):
        resolve_database_environment(pristine_env={}, repo_root=tmp_path, target_environ={})


def test_local_env_must_be_staging_and_applies_non_secret_identity(tmp_path: Path):
    (tmp_path / ".env.local").write_text(
        "ENVIRONMENT=development\n"
        f"MONGO_URI={_uri('gob-staging')}\n"
        "MONGO_DB_NAME=gob-staging\n"
    )
    target = {}
    config = resolve_database_environment(
        pristine_env={}, repo_root=tmp_path, target_environ=target
    )
    assert config.db_name == "gob-staging"
    assert config.source.endswith(".env.local")
    assert target["ENVIRONMENT"] == "development"


def test_dotenv_cannot_grant_database_access_or_mock_mode(tmp_path: Path):
    (tmp_path / ".env.local").write_text(
        "GOB_DB_ACCESS=write\nGOB_DB_MODE=mongomock\n"
        "ENVIRONMENT=development\n"
        f"MONGO_URI={_uri('gob-staging')}\n"
        "MONGO_DB_NAME=gob-staging\n"
    )
    with pytest.raises(EnvironmentConfigurationError, match="cannot come from .env.local"):
        resolve_database_environment(pristine_env={}, repo_root=tmp_path, target_environ={})


def test_uri_and_explicit_database_name_must_agree(tmp_path: Path):
    with pytest.raises(EnvironmentConfigurationError, match="identity mismatch"):
        resolve_database_environment(
            pristine_env={
                "ENVIRONMENT": "staging",
                "MONGO_URI": _uri("gob"),
                "MONGO_DB_NAME": "gob-staging",
            },
            repo_root=tmp_path,
            target_environ={},
        )


def test_environment_and_database_target_must_agree(tmp_path: Path):
    with pytest.raises(EnvironmentConfigurationError, match="requires MONGO_DB_NAME=gob"):
        resolve_database_environment(
            pristine_env={
                "ENVIRONMENT": "production",
                "MONGO_URI": _uri("gob-staging"),
                "MONGO_DB_NAME": "gob-staging",
            },
            repo_root=tmp_path,
            target_environ={},
        )


def test_explicit_mongomock_requires_test_identity_and_safe_name(tmp_path: Path):
    config = resolve_database_environment(
        pristine_env={
            "GOB_DB_MODE": "mongomock",
            "ENVIRONMENT": "test",
            "MONGO_DB_NAME": "gob-test",
        },
        repo_root=tmp_path,
        target_environ={},
    )
    assert config.db_mode == "mongomock"
    assert config.mongo_uri is None

    with pytest.raises(EnvironmentConfigurationError, match="must not be gob"):
        resolve_database_environment(
            pristine_env={
                "GOB_DB_MODE": "mongomock",
                "ENVIRONMENT": "test",
                "MONGO_DB_NAME": "gob",
            },
            repo_root=tmp_path,
            target_environ={},
        )


def test_railway_uses_process_configuration_without_local_file(tmp_path: Path):
    config = resolve_database_environment(
        pristine_env={
            "RAILWAY_ENVIRONMENT": "staging",
            "ENVIRONMENT": "staging",
            "MONGO_URI": _uri("gob-staging"),
            "MONGO_DB_NAME": "gob-staging",
        },
        repo_root=tmp_path,
        target_environ={},
    )
    assert config.source == "railway-process"
    assert config.db_name == "gob-staging"


def test_railway_production_uses_process_configuration_without_local_file(tmp_path: Path):
    config = resolve_database_environment(
        pristine_env={
            "RAILWAY_ENVIRONMENT": "production",
            "ENVIRONMENT": "production",
            "MONGO_URI": _uri("gob"),
            "MONGO_DB_NAME": "gob",
        },
        repo_root=tmp_path,
        target_environ={},
    )
    assert config.source == "railway-process"
    assert config.environment == "production"
    assert config.db_name == "gob"


@pytest.mark.parametrize(
    ("uri", "expected"),
    [
        ("mongodb://host/gob-staging", "gob-staging"),
        ("mongodb+srv://user:pass@host/gob?retryWrites=true", "gob"),
    ],
)
def test_database_name_from_uri(uri: str, expected: str):
    assert database_name_from_uri(uri) == expected
