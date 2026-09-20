"""A player's position is the lineup slot they occupy, not an attribute they carry.

``Player`` has no ``position`` (or ``pos``) attribute and nothing in the backend ever
assigns one, so every ``getattr(player, "position", None)`` read in the engine returned
``None`` and whatever constant followed the ``or`` was taken unconditionally. See
``reports/position-lookup-2026-09-19.md`` and ``reports/position-lookup-2-2026-09-19.md``.

Everything here is gated on ``GOB_LINEUP_POSITION_LOOKUP`` (default ON) so a single kill
switch reverts every site to its legacy read.

Deliberately a leaf module: only ``os`` and ``logging``, so the engine, the models and
``utils.shared`` can all import it without a cycle.
"""
import logging
import os
from typing import Any, Dict, Optional

__all__ = [
    "sim_build_anim_for_emitter_enabled",
    "lineup_position_lookup_enabled",
    "lineup_slot",
    "resolve_lineup_position",
    "warn_position_unresolved",
    "POS_LOOKUP_WARNED",
    "POS_LOOKUP_WARNED_MAX_GAMES",
]


def sim_build_anim_for_emitter_enabled() -> bool:
    """``GOB_SIM_BUILD_ANIM_FOR_EMITTER`` - **default ON** (B1-A, adopted 2026-09-20).

    ON lets ``Animator.skeleton_to_animations`` build on the SIM arm when the caller is
    part of the coordinate pipeline (``for_emitter=True``), so the HCO schema emitter and
    ``_uess_sync_emitted_shot_coords`` see the same animations the played arm sees. The
    FE animation packet stays unbuilt for sims: the three ``capture_*`` methods keep their
    own gates, and ``turn_manager``'s ``result["animations"]`` write is NOT marked
    ``for_emitter``.

    OFF is the kill switch and reproduces equiv_v3_reference_ec4f5acfc_poslookup2.json.
    It is also the configuration ``GOB_SIM_HCO_COORD_WRITE`` and ``GOB_SIM_CRASH_APPLY``
    exist for: with B1-A ON the sim arm carries real ``animation_steps``, so both of those
    substitutes are dormant on the HCO path. They are KEPT as B1-A's kill-switch partners.

    Measured in reports/coord-parity-spike-2026-09-20.md and
    reports/b1a-adopt-2026-09-20.md: ~+7% engine-sim CPU, written document +0.45%,
    and the sim arm's shot geometry becomes the played arm's.
    """
    return os.environ.get("GOB_SIM_BUILD_ANIM_FOR_EMITTER", "1") == "1"


def lineup_position_lookup_enabled() -> bool:
    """``GOB_LINEUP_POSITION_LOOKUP`` - **default ON**.

    ON resolves a player's lineup slot by identity lookup in the lineup dict that owns
    them. OFF reproduces the legacy reads exactly: ``getattr(player, 'position', None)``
    falling back to a hard-coded constant.
    """
    return os.environ.get("GOB_LINEUP_POSITION_LOOKUP", "1") == "1"


def lineup_slot(lineup: Optional[Dict[str, Any]], player: Any) -> Optional[str]:
    """The slot ``player`` occupies in ``lineup``, by identity, else ``None``.

    Identity (``is``), not equality: ``Player`` does not define ``__eq__`` today, but a
    lookup that would silently return the wrong slot if it ever did is not worth having.
    """
    if not isinstance(lineup, dict) or player is None:
        return None
    return next((pos for pos, p in lineup.items() if p is player), None)


# One warning per (game, site). Bounded so a long-lived process cannot grow it without limit.
POS_LOOKUP_WARNED: Dict[str, set] = {}
POS_LOOKUP_WARNED_MAX_GAMES = 8


def warn_position_unresolved(site: str, player: Any, game: Any = None) -> None:
    key = str(getattr(game, "game_id", None) or id(getattr(game, "game_state", None)))
    seen = POS_LOOKUP_WARNED.get(key)
    if seen is None:
        if len(POS_LOOKUP_WARNED) >= POS_LOOKUP_WARNED_MAX_GAMES:
            POS_LOOKUP_WARNED.pop(next(iter(POS_LOOKUP_WARNED)), None)
        seen = POS_LOOKUP_WARNED[key] = set()
    if site in seen:
        return
    seen.add(site)
    logging.warning(
        "[POS LOOKUP] %s: player %s is not in the lineup dict; leaving the position "
        "unresolved rather than guessing a constant",
        site, getattr(player, "player_id", None),
    )


def resolve_lineup_position(player, lineup, site, legacy_constant, game=None):
    """The lineup slot ``player`` occupies in ``lineup``, by identity.

    Returns ``None`` when the player is not in the lineup. That is deliberate: every
    caller already guards on a falsy position, and a wrong constant is worse than no
    position - it silently credits the wrong player. The kill switch
    ``GOB_LINEUP_POSITION_LOOKUP=0`` restores the constant.
    """
    if not lineup_position_lookup_enabled():
        return getattr(player, "position", None) or legacy_constant
    pos = lineup_slot(lineup, player)
    if pos is None:
        warn_position_unresolved(site, player, game)
    return pos
