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
from BackEnd.utils.jwt_config import resolve_jwt_secret

# Refuse to start with the public dev JWT secret outside local dev/test. This runs
# before api.py's guarded import block, so it stops the process instead of leaving
# a half-started app behind /health.
resolve_jwt_secret()


def _docs_kwargs(environ=os.environ) -> dict:
    """No public OpenAPI/Swagger/ReDoc in production; on everywhere else.

    Same ENVIRONMENT resolution as ``BackEnd.utils.auth._is_production`` (not
    imported: auth opens the store, and this module must load without a DB).
    """
    env = (environ.get("ENVIRONMENT") or environ.get("ENV") or environ.get("RAILWAY_ENVIRONMENT") or "").lower()
    if env == "production":
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}


app = FastAPI(**_docs_kwargs())


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


# --- readiness ------------------------------------------------------------------
# /health stays a dependency-free liveness check (Railway's healthcheck). /health/ready
# is for uptime monitors: 200 only once app startup finished AND the database answers
# a ping within READY_PING_TIMEOUT_S. No internal details in either body.
READY_PING_TIMEOUT_S = 2.0
_readiness = {"startup_complete": False, "ping": None}


def mark_startup_complete(ping) -> None:
    """Called at the end of api.py's startup with a zero-arg DB ping callable."""
    _readiness["ping"] = ping
    _readiness["startup_complete"] = True


def _db_answers() -> bool:
    ping = _readiness.get("ping")
    if ping is None:
        return False
    import concurrent.futures

    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        ex.submit(ping).result(timeout=READY_PING_TIMEOUT_S)
        return True
    except Exception:
        return False
    finally:
        ex.shutdown(wait=False, cancel_futures=True)


@app.get("/health/ready")
def health_ready():
    from fastapi.responses import JSONResponse

    if _readiness.get("startup_complete") and _db_answers():
        return JSONResponse({"status": "ready"}, status_code=200)
    return JSONResponse({"status": "not_ready"}, status_code=503)
