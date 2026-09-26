"""Franchise browse cache: ``browse_rev`` and ETag / 304 for browse GETs.

Not used by the sim, ``cpu_week_pool``, end-of-game persistence, or ``sim_rng``.
"""

from __future__ import annotations

import functools
import inspect
from contextvars import ContextVar
from typing import Any
from urllib.parse import urlencode

from bson import ObjectId
from fastapi import Request
from starlette.responses import Response

from BackEnd.api._bootstrap import _deployed_commit

_BUILD = _deployed_commit()
_CACHE_CONTROL = "private, no-cache"
_PROJECTION = {"current_season": 1, "week": 1, "browse_rev": 1}
# Set when this request's handler folds or bumps browse_rev. A writing GET
# computes its tag before the handler; if the handler then increments the
# rev, the response must carry the post-write tag or the next If-None-Match
# would 304 a mutation the client never saw. 304 never enters the handler.
_browse_rev_touched: ContextVar[bool] = ContextVar("browse_rev_touched", default=False)


def franchise_collection():
    from BackEnd.db import db

    return db.franchises


def franchise_key(franchise_id: Any) -> Any:
    if isinstance(franchise_id, ObjectId):
        return franchise_id
    text = str(franchise_id or "").strip()
    if not text:
        return None
    try:
        return ObjectId(text)
    except Exception:
        return text


def _mark_browse_rev_touched() -> None:
    _browse_rev_touched.set(True)


def fold_browse_rev(update: dict) -> dict:
    """Add ``$inc browse_rev`` to an update the caller is about to send.

    Same round trip as the write that already updates the franchise document.
    """
    _mark_browse_rev_touched()
    merged = dict(update)
    inc = dict(merged.get("$inc") or {})
    inc["browse_rev"] = int(inc.get("browse_rev") or 0) + 1
    merged["$inc"] = inc
    return merged


def bump_browse_rev(franchise_id: Any) -> None:
    """Increment ``browse_rev`` when the write did not already update the franchise doc."""
    _mark_browse_rev_touched()
    key = franchise_key(franchise_id)
    if key is None:
        return
    franchise_collection().update_one({"_id": key}, {"$inc": {"browse_rev": 1}})


def route_signature(request: Request) -> str:
    pairs = [(str(key), str(value)) for key, value in request.query_params.multi_items()]
    query = urlencode(sorted(pairs))
    path = request.url.path
    signature = f"{path}?{query}" if query else path
    return signature.replace('"', "%22")


def browse_etag_value(
    *,
    franchise_id: str,
    season: Any,
    week: Any,
    browse_rev: Any,
    signature: str,
) -> str:
    try:
        season_n = int(season or 1)
    except (TypeError, ValueError):
        season_n = 1
    try:
        week_n = int(week or 1)
    except (TypeError, ValueError):
        week_n = 1
    try:
        rev_n = int(browse_rev or 0)
    except (TypeError, ValueError):
        rev_n = 0
    raw = f"{franchise_id}:{season_n}:{week_n}:{rev_n}:{_BUILD}:{signature}"
    return f'W/"{raw}"'


def lookup_browse_etag(franchise_id: str, signature: str) -> str | None:
    """One projected franchise read. None when the id is missing or the doc is absent."""
    key = franchise_key(franchise_id)
    if key is None:
        return None
    doc = franchise_collection().find_one({"_id": key}, _PROJECTION)
    if not doc:
        return None
    return browse_etag_value(
        franchise_id=str(franchise_id),
        season=doc.get("current_season"),
        week=doc.get("week"),
        browse_rev=doc.get("browse_rev"),
        signature=signature,
    )


def _if_none_match(header: str | None, etag: str) -> bool:
    if not header:
        return False
    return any(part.strip() == etag for part in header.split(","))


def _profile_bypass(request: Request) -> bool:
    return str(request.query_params.get("profile") or "") == "1"


def stamp_browse_headers(response: Response, etag: str) -> Response:
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = _CACHE_CONTROL
    return response


def not_modified(etag: str) -> Response:
    return stamp_browse_headers(Response(status_code=304), etag)


def _invoke_and_refresh(fn, args, kwargs, request: Request, franchise_id: str, signature: str):
    """Run the handler. If it folded or bumped, re-read the tag before returning.

    ``finally`` covers handlers that write and then raise (a practice-squad
    backfill that 404s still changed the franchise). The 304 path never calls this.
    """
    try:
        return fn(*args, **kwargs)
    finally:
        if _browse_rev_touched.get():
            fresh = lookup_browse_etag(franchise_id, signature)
            if fresh:
                request.state.browse_etag = fresh


def attach_browse_etag_header(request: Request, response: Response) -> Response:
    etag = getattr(request.state, "browse_etag", None)
    if etag:
        stamp_browse_headers(response, etag)
    return response


def browse_cached(fn):
    """Run the handler only when the browse ETag misses.

    ``profile=1`` always runs the handler. A direct call with no ``request``
    (the profile recursion inside a few handlers) passes through.
    """
    sig = inspect.signature(fn)
    if "request" not in sig.parameters:
        request_param = inspect.Parameter(
            "request",
            inspect.Parameter.KEYWORD_ONLY,
            annotation=Request,
        )
        sig = sig.replace(parameters=[*sig.parameters.values(), request_param])

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        request = kwargs.pop("request", None)
        if not isinstance(request, Request):
            return fn(*args, **kwargs)
        franchise_id = kwargs.get("franchise_id")
        if franchise_id is None:
            franchise_id = request.query_params.get("franchise_id")
        token = _browse_rev_touched.set(False)
        try:
            if not franchise_id:
                return fn(*args, **kwargs)
            signature = route_signature(request)
            etag = lookup_browse_etag(str(franchise_id), signature)
            if etag is None:
                return fn(*args, **kwargs)
            request.state.browse_etag = etag
            if _profile_bypass(request):
                return _invoke_and_refresh(fn, args, kwargs, request, str(franchise_id), signature)
            if _if_none_match(request.headers.get("if-none-match"), etag):
                return not_modified(etag)
            return _invoke_and_refresh(fn, args, kwargs, request, str(franchise_id), signature)
        finally:
            _browse_rev_touched.reset(token)

    wrapper.__signature__ = sig
    return wrapper
