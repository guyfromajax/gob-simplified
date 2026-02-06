"""
Minimal app with /health only. Imported first so the app exists even if
the rest of the API fails to load (e.g. DB, routers). Used by api.py.
"""
import os
import sys
from fastapi import FastAPI, Response

app = FastAPI()


@app.get("/health")
def health_check():
    """No dependencies - always works. Railway healthcheck hits this."""
    print("🔵 [HEALTH] GET /health", file=sys.stderr, flush=True)
    return {"status": "healthy", "port": os.getenv("PORT", "?")}


@app.head("/health")
def health_check_head():
    return Response(status_code=200)
