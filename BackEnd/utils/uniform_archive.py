"""Cross-franchise archive of painted uniform portraits.

WHY THIS EXISTS
---------------
``make_signed_master(kit, mask, primary, secondary, mascot)`` is a pure function.
Its output is fully determined by the portrait (``image_id`` -> kit + tank mask) and
the team's *look* (primary colour, secondary colour, mascot wordmark). ``player_id``
is NOT an input.

The original implementation nonetheless keyed the painted result by
``players/master/<player_id>.png``. A signed player's ``player_id`` is a fresh UUID
minted per signing per franchise, so the SAME recruit signing to the SAME team was
repainted from scratch for every user, forever — ~1s of CPU and 10.5 MB of storage
each time, for a byte-identical image.

This module keys the paint by what actually determines the pixels:

    uniforms/<image_id>__<color_key>.png

so a portrait is painted at most once per distinct team look (~128 across the whole
league, plus one per Team Builder rebrand) rather than once per player. Every
assignment after the first is an ``exists()`` hit costing nothing.

MASCOT IS PART OF THE KEY. Some teams share a colour palette but never a mascot, and
the mascot is stamped into the jersey as a wordmark — so colour alone would collide
and serve the wrong wordmark.

REBRANDS FALL OUT FOR FREE. Different colours (or mascot) produce a different key and
therefore a different object. The legacy per-player scheme could not express this: it
skipped on ``exists(players/master/<player_id>.png)``, whose key has no colour
component, so a rebranded team kept its stale masters permanently.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Mapping

logger = logging.getLogger(__name__)

# Hex characters of the colour hash retained in the object key. 12 keeps keys short
# and readable in the bucket listing while leaving collision probability negligible
# for a space bounded by (teams x rebrands), which is thousands, not billions.
UNIFORM_KEY_LEN = 12

UNIFORM_PREFIX = "uniforms"

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _norm_color(value: Any) -> str:
    """Normalise a colour to bare lowercase 6-digit hex.

    Colours reach us from several places (core team docs, Team Builder overlays,
    franchise display resolution) with inconsistent casing and an optional leading
    '#'. Normalising here means '#1C2A44' and '1c2a44' cannot produce two archive
    entries for one visual result.
    """
    m = _HEX_RE.match(str(value or "").strip())
    if not m:
        return ""
    return m.group(1).lower()


def _norm_mascot(value: Any) -> str:
    """Uppercase, collapse whitespace — matching what gets stamped on the jersey.

    ``make_signed_master`` upper-cases the wordmark before stamping, so 'Wildcats'
    and 'WILDCATS' paint identically and must share one key.
    """
    return " ".join(str(value or "").upper().split())


def color_key(primary: Any, secondary: Any, mascot: Any) -> str:
    """Stable short hash of the three inputs that define a team's painted look."""
    basis = "\x1f".join((_norm_color(primary), _norm_color(secondary), _norm_mascot(mascot)))
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:UNIFORM_KEY_LEN]


def uniform_key(image_id: Any, primary: Any, secondary: Any, mascot: Any) -> str | None:
    """``<image_id>__<color_key>`` — the archive identity, or None when unpaintable.

    Returns None when there is no ``image_id`` (a player outside the portrait
    pipeline) or no usable primary colour, because neither can produce a determinate
    image. Callers fall back to the generic headshot.
    """
    iid = str(image_id or "").strip()
    if not iid:
        return None
    if not _norm_color(primary):
        return None
    return f"{iid}__{color_key(primary, secondary, mascot)}"


def uniform_object_key(uniform_key_value: str) -> str:
    """R2 object key for an archive entry."""
    return f"{UNIFORM_PREFIX}/{uniform_key_value}.png"


def uniform_key_for_player(
    player_meta: Mapping[str, Any] | None,
    team_display: Mapping[str, Any] | None,
) -> str | None:
    """Convenience: derive the archive identity from an FPD ``meta`` + team display.

    ``team_display`` is a ``resolve_team_display()`` result (or any mapping carrying
    primary_color / secondary_color / mascot).
    """
    meta = player_meta or {}
    disp = team_display or {}
    return uniform_key(
        meta.get("image_id"),
        disp.get("primary_color"),
        disp.get("secondary_color"),
        disp.get("mascot"),
    )


def ensure_uniform(
    *,
    image_id: Any,
    primary: Any,
    secondary: Any,
    mascot: Any,
) -> dict[str, Any]:
    """Paint the archive entry if absent. Returns {status, uniform_key, object_key}.

    status: 'exists' | 'painted' | 'no_image_id' | 'no_kit' | 'unconfigured' | 'error'

    'exists' is the expected steady state and the entire point of the archive — it
    costs one R2 HEAD and no CPU. Never raises: a portrait must never take down the
    caller, and every failure degrades to the generic headshot at the view layer.
    """
    from BackEnd.services import r2_images, recruit_image
    from BackEnd.utils.team_builder_portraits import resolve_kit_keys

    ukey = uniform_key(image_id, primary, secondary, mascot)
    if not ukey:
        return {"status": "no_image_id", "uniform_key": None, "object_key": None}

    okey = uniform_object_key(ukey)
    if not r2_images.is_configured():
        return {"status": "unconfigured", "uniform_key": ukey, "object_key": okey}

    try:
        if r2_images.exists(okey):
            return {"status": "exists", "uniform_key": ukey, "object_key": okey}

        keys = resolve_kit_keys(image_id)
        if not keys:
            return {"status": "no_kit", "uniform_key": ukey, "object_key": okey}
        kit_key, mask_key = keys
        if not (r2_images.exists(kit_key) and r2_images.exists(mask_key)):
            return {"status": "no_kit", "uniform_key": ukey, "object_key": okey}

        master = recruit_image.make_signed_master(
            r2_images.get(kit_key),
            r2_images.get(mask_key),
            _fmt_hex(primary),
            _fmt_hex(secondary) or "#ffffff",
            _norm_mascot(mascot),
        )
        r2_images.put(okey, master)
        return {"status": "painted", "uniform_key": ukey, "object_key": okey}
    except Exception as exc:  # noqa: BLE001 — never 500 a portrait
        logger.exception("[UNIFORM-ARCHIVE] paint failed image_id=%s key=%s", image_id, ukey)
        return {
            "status": "error",
            "uniform_key": ukey,
            "object_key": okey,
            "detail": f"{type(exc).__name__}: {str(exc)[:160]}",
        }


def _fmt_hex(value: Any) -> str:
    """'#rrggbb' for make_signed_master, or '' when unusable."""
    h = _norm_color(value)
    return f"#{h}" if h else ""
