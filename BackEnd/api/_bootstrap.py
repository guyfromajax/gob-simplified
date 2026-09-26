"""
Minimal app with /health only. Imported first so the app exists even if
the rest of the API fails to load (e.g. DB, routers). Used by api.py.
"""
import os
import sys
from fastapi import FastAPI, Response
from BackEnd.env_config import resolve_runtime_db_access
from BackEnd.loopback_env import is_loopback
from BackEnd.runtime_paths import bundle_path, bundle_root

app = FastAPI()


def _read_build_stamp() -> str:
    """One-line id written next to the packaged binary. Absent in a source checkout."""
    try:
        path = bundle_path("BUILD_ID")
        if not path.is_file():
            return ""
        line = path.read_text(encoding="utf-8").strip().splitlines()
        return line[0].strip() if line else ""
    except Exception:
        return ""


def _deployed_commit() -> str:
    """Short id of the running build.

    Railway injects RAILWAY_GIT_COMMIT_SHA. A packaged desktop build has no git
    checkout, so the engine passes GOB_BUILD_ID and ``scripts/compile_loopback.sh``
    stamps ``BUILD_ID`` beside the binary. A source checkout falls back to
    ``git rev-parse``. 'unknown' only when none of those exist — that value must
    not stay constant across shipped versions, or browse ETags never change.
    """
    sha = (
        os.environ.get("RAILWAY_GIT_COMMIT_SHA")
        or os.environ.get("GIT_COMMIT_SHA")
        or os.environ.get("SOURCE_VERSION")
        or os.environ.get("GOB_BUILD_ID")
        or _read_build_stamp()
        or ""
    ).strip()
    if not sha:
        try:
            import subprocess
            sha = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(bundle_root()),
                stderr=subprocess.DEVNULL,
            ).decode().strip()
        except Exception:
            sha = ""
    return sha[:12] if sha else "unknown"


@app.get("/health")
def health_check():
    """No dependencies - always works. Railway healthcheck hits this.

    Reports the RUNNING BUILD so "did the deploy actually take?" is answerable from
    outside. Prod silently diverged from develop by 158 commits once because nothing
    exposed this; scripts/verify_deploy.py reads it."""
    print("🔵 [HEALTH] GET /health", file=sys.stderr, flush=True)
    db_name = os.environ.get("MONGO_DB_NAME", "")
    payload = {
        "status": "healthy",
        "port": os.getenv("PORT") or os.getenv("GOB_LOOPBACK_PORT") or "?",
        "commit": _deployed_commit(),
        "hash_seed": os.environ.get("PYTHONHASHSEED", "unset"),
        "environment": os.environ.get("ENVIRONMENT", "unknown"),
        "database": db_name or "unknown",
        "db_access": resolve_runtime_db_access(db_name, os.environ),
    }
    if is_loopback():
        payload.update(
            {
                "profile": "loopback",
                "ready": True,
                "persistence": os.environ.get("GOB_PERSISTENCE", "sqlite"),
                "host": "127.0.0.1",
            }
        )
    return payload


@app.head("/health")
def health_check_head():
    return Response(status_code=200)
