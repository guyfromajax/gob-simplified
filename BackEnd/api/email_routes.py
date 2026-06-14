"""
Email unsubscribe endpoint (one-click + link).

GET  /api/email/unsubscribe?e=<email>&t=<token>  → records unsubscribe, returns HTML page
POST /api/email/unsubscribe?e=<email>&t=<token>  → RFC 8058 one-click (returns 200)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from BackEnd.utils.email_suppression import record_unsubscribe, verify_unsubscribe_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email", tags=["email"])


def _page(message: str, ok: bool = True) -> str:
    color = "#1a7f37" if ok else "#b3261e"
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Unsubscribe</title></head>"
        "<body style='font-family:system-ui,sans-serif;max-width:520px;margin:80px auto;"
        "padding:0 20px;text-align:center;'>"
        f"<h2 style='color:{color};'>{message}</h2>"
        "<p><a href='https://www.geekedoutbasketball.com'>Return to Geeked Out Basketball</a></p>"
        "</body></html>"
    )


@router.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe(e: str = "", t: str = ""):
    if not e or not verify_unsubscribe_token(e, t):
        return HTMLResponse(_page("Invalid or expired unsubscribe link.", ok=False), status_code=400)
    record_unsubscribe(e, source="link")
    logger.info("[UNSUB] %s unsubscribed via link", e)
    return HTMLResponse(_page("You've been unsubscribed. You won't receive marketing emails from us."))


@router.post("/unsubscribe")
async def unsubscribe_one_click(e: str = "", t: str = ""):
    """RFC 8058 List-Unsubscribe-Post one-click handler."""
    if not e or not verify_unsubscribe_token(e, t):
        return JSONResponse({"ok": False}, status_code=400)
    record_unsubscribe(e, source="one-click")
    logger.info("[UNSUB] %s unsubscribed via one-click", e)
    return JSONResponse({"ok": True})
