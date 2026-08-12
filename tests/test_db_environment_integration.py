import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def _run_db_import(extra_env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "MONGO_URI",
            "MONGO_DB_NAME",
            "ENVIRONMENT",
            "GOB_DB_MODE",
            "GOB_DB_ACCESS",
            "RAILWAY_ENVIRONMENT",
        }
        and not key.startswith("RAILWAY_")
    }
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", "import BackEnd.db as d; print(d.DB_NAME, d.USING_MONGOMOCK)"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )


def test_db_import_uses_mongomock_only_when_explicit():
    result = _run_db_import(
        {
            "GOB_DB_MODE": "mongomock",
            "ENVIRONMENT": "test",
            "MONGO_DB_NAME": "gob-test",
        }
    )
    assert result.returncode == 0, result.stderr
    assert "gob-test True" in result.stdout
    assert "explicitly selected mongomock" in result.stderr


def test_production_import_requires_process_authorization():
    result = _run_db_import(
        {
            "ENVIRONMENT": "production",
            "MONGO_URI": "mongodb://example.invalid/gob",
            "MONGO_DB_NAME": "gob",
        }
    )
    assert result.returncode != 0
    assert "Refusing to connect to PRODUCTION" in result.stderr


def test_production_read_authorization_is_accepted_and_reported():
    result = _run_db_import(
        {
            "ENVIRONMENT": "production",
            "MONGO_URI": "mongodb://example.invalid/gob",
            "MONGO_DB_NAME": "gob",
            "GOB_DB_ACCESS": "read",
        }
    )
    assert result.returncode == 0, result.stderr
    assert "PRODUCTION 'gob' opened READ-ONLY" in result.stderr
    assert "gob False" in result.stdout


def test_invalid_real_mongo_configuration_never_falls_back_to_mongomock():
    result = _run_db_import(
        {
            "ENVIRONMENT": "staging",
            "MONGO_URI": "mongodb://localhost:notaport/gob-staging",
            "MONGO_DB_NAME": "gob-staging",
        }
    )
    assert result.returncode != 0
    assert "explicitly selected mongomock" not in result.stderr
    assert "Mongomock collections initialized" not in result.stderr
