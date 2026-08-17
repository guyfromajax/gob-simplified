"""
Minimal app with /health only. Imported first so the app exists even if
the rest of the API fails to load (e.g. DB, routers). Used by api.py.
"""
import os
import sys
from fastapi import FastAPI, Response
from BackEnd.env_config import resolve_runtime_db_access

app = FastAPI()


def _deployed_commit() -> str:
    """Short SHA of the running build. Railway injects RAILWAY_GIT_COMMIT_SHA; fall back
    to a local `git rev-parse` for dev. 'unknown' if neither is available."""
    sha = (
        os.environ.get("RAILWAY_GIT_COMMIT_SHA")
        or os.environ.get("GIT_COMMIT_SHA")
        or os.environ.get("SOURCE_VERSION")
        or ""
    ).strip()
    if not sha:
        try:
            import subprocess
            sha = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=os.path.dirname(os.path.abspath(__file__)),
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
    return {
        "status": "healthy",
        "port": os.getenv("PORT", "?"),
        "commit": _deployed_commit(),
        "hash_seed": os.environ.get("PYTHONHASHSEED", "unset"),
        "environment": os.environ.get("ENVIRONMENT", "unknown"),
        "database": db_name or "unknown",
        "db_access": resolve_runtime_db_access(db_name, os.environ),
    }


@app.head("/health")
def health_check_head():
    return Response(status_code=200)
