"""
Team Builder replaced-name leak detector.

Invariant: in a Team Builder franchise, the replaced program's core name must
never appear as *rendered* text in response payloads or DOM (except allowlisted
metadata / orientation). Dict keys and lookup identifiers (score maps,
possession, home_team/away_team) are identity — not leaks.

Server: optional middleware scans outgoing JSON on franchise-scoped requests.
Client: ``FrontEnd/static/js/shared/teamBuilderLeakDetector.js`` scans the DOM.

This module is the shared scanner + middleware factory. Fixes belong elsewhere —
use reports from this detector to drive sweeps.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Iterable, Optional

from bson import ObjectId
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from BackEnd.utils.franchise_team_display import TEAM_BUILDER_FIELD, get_team_builder_overlay

logger = logging.getLogger(__name__)

# Field-path suffixes that intentionally carry the replaced core name / palette.
ALLOWLISTED_PATH_SUFFIXES: tuple[str, ...] = (
    "replaced_name",
    "team_builder_replaced_name",
    "team_builder_replaced_primary_color",
    "team_builder_replaced_secondary_color",
    "replaced_primary_color",
    "replaced_secondary_color",
)

# Chrome color leaves — core replaced palette here is a leak when overlay differs.
COLOR_CHROME_LEAVES: frozenset[str] = frozenset(
    {
        "primary_color",
        "secondary_color",
        "winner_primary_color",
        "loser_primary_color",
    }
)

# Leaf field names that hold matchup / score *lookup identifiers*, not chrome.
# Core team names here are deliberate (Phase 0); flagging them is a false positive.
LOOKUP_IDENTIFIER_LEAVES: frozenset[str] = frozenset(
    {
        "possession",
        "opening_tip_winner",
        "timeout_offense_team_id",
        "home_team",  # identity in sim/init bodies
        "away_team",
        "home",  # play-next identity
        "away",
        # Wire identity field (§3.1a): core name for score/matchup lookup.
        # Chrome is additive on display_name / team_name / labels — never ``name``.
        "name",
        # Canonical slugs / ObjectId keys — identity, not chrome. Casefold can
        # match replaced_name (e.g. PROVIDENCE ≈ Providence); still not a leak.
        "team_id",
        "home_team_id",
        "away_team_id",
        "opponent_team_id",
        "user_team_object_id",
    }
)

# DOM / HTML allowlist (client mirrors these selectors).
ALLOWLISTED_DOM_SELECTORS: tuple[str, ...] = (
    "#tb-orientation",
)

# Orientation copy pattern (deliberate mention of the replaced program).
_ORIENTATION_COPY_RE = re.compile(
    r"replacing\s+.+\s+in\s+this\s+franchise",
    re.IGNORECASE,
)

# Escape hatch only — prefer tightening match rules over growing this set.
ALLOWLISTED_DERIVED_NEEDLES: frozenset[str] = frozenset()

# Non-alnum split for whole-token short-needle matching (abbr / initials).
_TOKEN_SPLIT_RE = re.compile(r"[^A-Za-z0-9]+")


class TeamBuilderNameLeak(Exception):
    """Raised in development when a response payload leaks replaced_name."""

    def __init__(self, route: str, replaced_name: str, paths: list[str]):
        self.route = route
        self.replaced_name = replaced_name
        self.paths = paths
        super().__init__(
            f"Team Builder leak: {replaced_name!r} in {route} at {', '.join(paths)}"
        )


def detector_enabled() -> bool:
    """Dev/staging on by default; production off unless TB_LEAK_DETECTOR=1."""
    flag = (os.getenv("TB_LEAK_DETECTOR") or "").strip().lower()
    if flag in ("0", "false", "off", "no"):
        return False
    if flag in ("1", "true", "on", "yes"):
        return True
    env = (
        os.getenv("ENVIRONMENT")
        or os.getenv("ENV")
        or os.getenv("RAILWAY_ENVIRONMENT")
        or ""
    ).lower()
    if env in ("production", "prod"):
        return False
    # Local / staging / unset → enabled (safe: only acts when franchise has overlay).
    return True


def detector_throws() -> bool:
    """Throw on leak only in local/dev (staging logs)."""
    flag = (os.getenv("TB_LEAK_DETECTOR_THROW") or "").strip().lower()
    if flag in ("0", "false", "off", "no"):
        return False
    if flag in ("1", "true", "on", "yes"):
        return True
    env = (
        os.getenv("ENVIRONMENT")
        or os.getenv("ENV")
        or os.getenv("RAILWAY_ENVIRONMENT")
        or ""
    ).lower()
    return env in ("", "development", "dev", "local", "test")


def _path_leaf(path: str) -> str:
    if not path:
        return ""
    leaf = path.rsplit(".", 1)[-1]
    return re.sub(r"\[\d+\]$", "", leaf)


def path_is_allowlisted(path: str) -> bool:
    if not path:
        return False
    return _path_leaf(path) in ALLOWLISTED_PATH_SUFFIXES


def path_is_lookup_identifier(path: str) -> bool:
    """True when the leaf is a matchup/score lookup field, not rendered chrome."""
    return _path_leaf(path) in LOOKUP_IDENTIFIER_LEAVES


def short_derived_needles_for_replaced_name(replaced_name: str) -> frozenset[str]:
    """
    3-char abbreviation and multi-word initials (uppercase).

    These match whole-token + case-sensitive only — substring would flag
    ``Conference`` / ``Content`` for Concord's ``CON``.
    """
    raw = (replaced_name or "").strip()
    if not raw:
        return frozenset()
    out: set[str] = set()
    alnum = re.sub(r"[^A-Za-z0-9]", "", raw)
    if len(alnum) >= 2:
        out.add(alnum[:3].upper())
    words = [w for w in re.split(r"[\s\-_]+", raw) if w]
    if len(words) >= 2:
        initials = "".join(w[0] for w in words).upper()
        if initials:
            out.add(initials)
    return frozenset(n for n in out if n and n not in ALLOWLISTED_DERIVED_NEEDLES)


def _string_contains_needle(
    value: str,
    needle: str,
    *,
    short: bool = False,
) -> bool:
    if not value or not needle:
        return False
    if short:
        # Whole-token, case-sensitive: "CON" badge is a leak; "Conference" is not.
        return any(part == needle for part in _TOKEN_SPLIT_RE.split(value) if part)
    return needle.casefold() in value.casefold()


def leak_needles_for_replaced_name(replaced_name: str) -> tuple[str, ...]:
    """
    Literal replaced_name plus derived chrome forms (slice / slug / initials).

    Short derived needles (abbr / initials) are included here but matched with
    whole-token case-sensitive rules via ``short_derived_needles_for_replaced_name``.
    Full name and slug variants stay case-insensitive substring.
    """
    raw = (replaced_name or "").strip()
    if not raw:
        return ()
    needles: list[str] = [raw]
    needles.extend(sorted(short_derived_needles_for_replaced_name(raw)))
    slug = re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_")
    if slug:
        needles.extend((slug, slug.upper(), slug.lower()))
    # Exact-string dedupe only — keep case/slug variants (PROVIDENCE vs providence).
    out: list[str] = []
    seen: set[str] = set()
    for n in needles:
        if not n or n in ALLOWLISTED_DERIVED_NEEDLES:
            continue
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
    return tuple(out)


def _string_contains_any_needle(
    value: str,
    needles: Iterable[str],
    short_needles: frozenset[str] | None = None,
) -> bool:
    if not value:
        return False
    short = short_needles or frozenset()
    for needle in needles:
        if _string_contains_needle(value, needle, short=needle in short):
            return True
    return False


def _orientation_allowlisted_text(value: str) -> bool:
    return bool(_ORIENTATION_COPY_RE.search(value or ""))


def scan_json_for_replaced_name(
    payload: Any,
    replaced_name: str,
    *,
    path: str = "",
    needles: tuple[str, ...] | None = None,
    short_needles: frozenset[str] | None = None,
) -> list[str]:
    """
    Return dotted field paths where ``replaced_name`` (or a derived form)
    appears as *rendered* text.

    Not a leak (Phase 0 identity):
      - dict keys (score / points_by_quarter / box_score lookup maps)
      - lookup-identifier leaves (possession, home_team, away_team, …)
      - allowlisted metadata (replaced_name) and orientation copy
    """
    hits: list[str] = []
    if not replaced_name:
        return hits
    active = needles if needles is not None else leak_needles_for_replaced_name(replaced_name)
    if not active:
        return hits
    short = (
        short_needles
        if short_needles is not None
        else short_derived_needles_for_replaced_name(replaced_name)
    )

    if isinstance(payload, dict):
        for key, value in payload.items():
            child = f"{path}.{key}" if path else str(key)
            if path_is_allowlisted(child):
                # Leaf value is intentional metadata; skip the whole node.
                continue
            # Keys are lookup identifiers — never chrome. Recurse into values only.
            hits.extend(
                scan_json_for_replaced_name(
                    value,
                    replaced_name,
                    path=child,
                    needles=active,
                    short_needles=short,
                )
            )
        return hits

    if isinstance(payload, list):
        for i, value in enumerate(payload):
            child = f"{path}[{i}]"
            hits.extend(
                scan_json_for_replaced_name(
                    value,
                    replaced_name,
                    path=child,
                    needles=active,
                    short_needles=short,
                )
            )
        return hits

    if isinstance(payload, str):
        if path_is_allowlisted(path):
            return hits
        if path_is_lookup_identifier(path):
            return hits
        if _orientation_allowlisted_text(payload):
            return hits
        if _string_contains_any_needle(payload, active, short):
            hits.append(path or "<root>")
        return hits

    return hits


def extract_franchise_id_from_request(
    query: dict[str, Any] | None = None,
    body: Any = None,
    path_params: dict[str, Any] | None = None,
) -> Optional[str]:
    """Best-effort franchise_id from query / JSON body / path."""
    if query:
        raw = query.get("franchise_id")
        if raw:
            return str(raw)
    if path_params:
        raw = path_params.get("franchise_id")
        if raw:
            return str(raw)
    if isinstance(body, dict):
        raw = body.get("franchise_id")
        if raw:
            return str(raw)
    return None


def franchise_id_from_game_doc(game_id: str) -> Optional[str]:
    """Load franchise_id from a games collection document (box-score /api/game path)."""
    if not game_id:
        return None
    try:
        from BackEnd.db import games_collection
        from BackEnd.utils.game_id_utils import normalize_game_id

        gid = normalize_game_id(game_id)
        doc = games_collection.find_one({"_id": gid}, {"franchise_id": 1})
        if not doc:
            try:
                from bson import ObjectId

                doc = games_collection.find_one({"_id": ObjectId(str(game_id))}, {"franchise_id": 1})
            except Exception:
                doc = None
        if not doc:
            return None
        raw = doc.get("franchise_id")
        return str(raw) if raw else None
    except Exception as e:
        logger.debug("[TB-LEAK] franchise_id_from_game_doc failed: %s", e)
        return None


def resolve_franchise_id_for_leak_scan(
    request: Request,
    *,
    body_json: Any = None,
    response_payload: Any = None,
) -> Optional[str]:
    """
    Franchise scope for leak scanning.

    Prefer explicit franchise_id on the request; else response payload; else
    resolve from the game document for ``/api/game/{game_id}``.
    """
    path_params = getattr(request, "path_params", None) or {}
    if not path_params and getattr(request, "scope", None):
        path_params = request.scope.get("path_params") or {}

    fid = extract_franchise_id_from_request(
        query=dict(request.query_params),
        body=body_json,
        path_params=path_params,
    )
    if fid:
        return fid

    if isinstance(response_payload, dict):
        raw = response_payload.get("franchise_id")
        if raw:
            return str(raw)

    path = request.url.path or ""
    if "/api/game/" in path:
        game_id = path_params.get("game_id") if isinstance(path_params, dict) else None
        if not game_id:
            # /api/game/<id> or /api/game/<id>/...
            parts = [p for p in path.split("/") if p]
            try:
                idx = parts.index("game")
                if idx + 1 < len(parts):
                    game_id = parts[idx + 1]
            except ValueError:
                game_id = None
        if game_id:
            return franchise_id_from_game_doc(str(game_id))
    return None


def overlay_replaced_name(franchise_id: str) -> Optional[str]:
    """Return overlay.replaced_name for a TB franchise, else None."""
    try:
        overlay = get_team_builder_overlay(franchise_id)
    except Exception:
        return None
    if not overlay:
        return None
    name = str(overlay.get("replaced_name") or "").strip()
    return name or None


def normalize_hex_color(value: Any) -> Optional[str]:
    """Normalize #RGB / #RRGGBB (and bare hex) to lowercase #rrggbb."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.startswith("#"):
        raw = raw[1:]
    if len(raw) == 3 and all(c in "0123456789abcdefABCDEF" for c in raw):
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6 or any(c not in "0123456789abcdefABCDEF" for c in raw):
        return None
    return "#" + raw.lower()


def replaced_core_only_palette(franchise_id: str) -> frozenset[str]:
    """
    Core primary/secondary of the replaced slot, minus any colors the overlay
    also uses (same color on purpose is not a leak).
    """
    try:
        overlay = get_team_builder_overlay(franchise_id)
    except Exception:
        return frozenset()
    if not overlay:
        return frozenset()
    replaced = overlay.get("replaced_object_id") or overlay.get("object_id")
    if not replaced:
        return frozenset()
    try:
        from BackEnd.db import teams_collection

        core = teams_collection.find_one(
            {"_id": ObjectId(str(replaced))},
            {"primary_color": 1, "secondary_color": 1},
        ) or {}
    except Exception:
        return frozenset()
    core_set = {
        c
        for c in (
            normalize_hex_color(core.get("primary_color")),
            normalize_hex_color(core.get("secondary_color")),
        )
        if c
    }
    overlay_set = {
        c
        for c in (
            normalize_hex_color(overlay.get("primary_color")),
            normalize_hex_color(overlay.get("secondary_color")),
        )
        if c
    }
    return frozenset(core_set - overlay_set)


def scan_json_for_replaced_colors(
    payload: Any,
    core_only_palette: frozenset[str],
    *,
    path: str = "",
) -> list[str]:
    """Flag chrome color leaves whose value is the replaced team's core palette."""
    hits: list[str] = []
    if not core_only_palette:
        return hits

    if isinstance(payload, dict):
        for key, value in payload.items():
            child = f"{path}.{key}" if path else str(key)
            if path_is_allowlisted(child):
                continue
            leaf = _path_leaf(child)
            if leaf in COLOR_CHROME_LEAVES and isinstance(value, str):
                norm = normalize_hex_color(value)
                if norm and norm in core_only_palette:
                    hits.append(child)
            hits.extend(
                scan_json_for_replaced_colors(
                    value, core_only_palette, path=child
                )
            )
        return hits

    if isinstance(payload, list):
        for i, value in enumerate(payload):
            child = f"{path}[{i}]"
            hits.extend(
                scan_json_for_replaced_colors(
                    value, core_only_palette, path=child
                )
            )
        return hits

    return hits


def check_payload_for_leaks(
    payload: Any,
    franchise_id: str,
    *,
    route: str = "",
) -> list[str]:
    """Scan a payload for replaced_name / derived forms and core-palette colors."""
    hits: list[str] = []
    replaced = overlay_replaced_name(franchise_id)
    if replaced:
        hits.extend(scan_json_for_replaced_name(payload, replaced))
    core_only = replaced_core_only_palette(franchise_id)
    if core_only:
        hits.extend(scan_json_for_replaced_colors(payload, core_only))
    return hits


async def _read_json_body(request: Request) -> Any:
    try:
        body_bytes = await request.body()
    except Exception:
        return None
    if not body_bytes:
        return None
    try:
        return json.loads(body_bytes.decode("utf-8"))
    except Exception:
        return None


class TeamBuilderLeakMiddleware(BaseHTTPMiddleware):
    """
    Scan JSON responses on franchise-scoped requests for the replaced core name.

    - Logs route + offending field paths always (when enabled).
    - In development (``detector_throws()``), replaces the response with HTTP 500
      detailing ``tb_leak_paths`` so clients/tests fail closed.
    """

    async def dispatch(self, request: Request, call_next):
        if not detector_enabled():
            return await call_next(request)

        # Capture body for franchise_id before the route consumes it.
        body_json = None
        content_type = (request.headers.get("content-type") or "").lower()
        if request.method in ("POST", "PUT", "PATCH") and "application/json" in content_type:
            body_json = await _read_json_body(request)

        response = await call_next(request)

        # Only inspect JSON bodies.
        resp_ct = (response.headers.get("content-type") or "").lower()
        if "application/json" not in resp_ct:
            return response

        try:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk if isinstance(chunk, (bytes, bytearray)) else bytes(chunk)
        except Exception:
            return response

        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        franchise_id = resolve_franchise_id_for_leak_scan(
            request,
            body_json=body_json,
            response_payload=payload,
        )
        if not franchise_id:
            headers = {
                k: v
                for k, v in response.headers.items()
                if k.lower() not in ("content-length", "content-encoding")
            }
            return Response(
                content=body,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type,
            )

        replaced = overlay_replaced_name(franchise_id)
        core_only = replaced_core_only_palette(franchise_id)
        if not replaced and not core_only:
            headers = {
                k: v
                for k, v in response.headers.items()
                if k.lower() not in ("content-length", "content-encoding")
            }
            return Response(
                content=body,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type,
            )

        route = f"{request.method} {request.url.path}"
        hits: list[str] = []
        if replaced:
            hits.extend(scan_json_for_replaced_name(payload, replaced))
        if core_only:
            hits.extend(scan_json_for_replaced_colors(payload, core_only))
        if hits:
            logger.error(
                "[TB-LEAK] franchise_id=%s replaced_name=%r route=%s paths=%s",
                franchise_id,
                replaced,
                route,
                hits,
            )
            if detector_throws():
                from starlette.responses import JSONResponse

                return JSONResponse(
                    status_code=500,
                    content={
                        "detail": (
                            f"Team Builder leak: {replaced!r} in {route} "
                            f"at {', '.join(hits)}"
                        ),
                        "tb_leak_route": route,
                        "tb_leak_replaced_name": replaced,
                        "tb_leak_paths": hits,
                    },
                )

        headers = {
            k: v
            for k, v in response.headers.items()
            if k.lower() not in ("content-length", "content-encoding")
        }
        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )


def install_team_builder_leak_middleware(app) -> bool:
    """Attach middleware when enabled. Returns True if installed."""
    if not detector_enabled():
        logger.info("[TB-LEAK] detector disabled")
        return False
    app.add_middleware(TeamBuilderLeakMiddleware)
    logger.warning(
        "[TB-LEAK] detector enabled (throw=%s)",
        detector_throws(),
    )
    return True


# Routes the regression test walks (franchise-scoped, team-name surfaces).
# Expand this list when the detector finds a new producer — do not pre-enumerate
# the codebase; let failed sweeps drive coverage.
FRANCHISE_LEAK_SWEEP_GET_ROUTES: tuple[tuple[str, dict[str, str]], ...] = (
    ("/franchise/command-center/data", {"franchise_id": "{fid}"}),
    ("/franchise/standings", {"franchise_id": "{fid}", "scope": "user_region"}),
    ("/franchise/list", {}),
    ("/franchise/current", {}),
    ("/franchise/news", {"franchise_id": "{fid}"}),
    ("/franchise/schedule", {"franchise_id": "{fid}"}),
    ("/franchise/team-data", {"franchise_id": "{fid}"}),
    ("/franchise/roster", {"franchise_id": "{fid}"}),
)

# Direct producers the sweep invokes (not via TestClient).
FRANCHISE_LEAK_SWEEP_PRODUCERS: tuple[str, ...] = (
    "producer:_franchise_summary_for_list",
    "producer:summarize_game_state(exclude_animations=False)",  # API / live chrome
    "producer:summarize_game_state(exclude_animations=True)",  # persist shape (identity OK)
)

# Known franchise / live-play surfaces NOT in the automated sweep yet.
# Box-score loads via GET /api/game/{game_id} — requires a seeded game doc.
FRANCHISE_LEAK_SWEEP_NOT_WALKED: tuple[str, ...] = (
    "GET /api/game/{game_id}  (box-score data — middleware resolves franchise from game doc; sweep needs seeded game)",
    "POST /api/simulate-quarter",
    "POST /api/init-game",
    "POST /franchise/play-next-game",
    "GET /franchise/lineup-for-matchups",
    "GET /box-score.html (static; DOM detector + banner)",
    "court.html / set-lineup.html (DOM detector + banner)",
)


def format_leak_report(
    *,
    franchise_id: str,
    replaced_name: str,
    findings: list[dict[str, Any]],
) -> str:
    if not findings:
        return (
            f"[TB-LEAK] clean franchise_id={franchise_id} replaced_name={replaced_name!r} "
            f"(0 hits)"
        )
    lines = [
        f"[TB-LEAK] REPORT franchise_id={franchise_id} replaced_name={replaced_name!r} "
        f"hits={len(findings)}"
    ]
    for item in findings:
        lines.append(
            f"  - {item.get('route')}: {', '.join(item.get('paths') or [])}"
        )
    return "\n".join(lines)
