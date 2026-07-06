"""Rendered-position authority for pre-emit decisions (UESS "emitter as god").

Game logic that runs BEFORE the animation is emitted (shot contest, shot
classification, rebounder selection) must decide from the SAME player positions
the emitter will render — not a parallel re-derivation. This module is the
single seam through which such logic reads those positions, always RNG-isolated
so it never perturbs the make/miss stream.

Phase 1 wires two turn families behind one façade:
  * ``FAST_BREAK`` → ``fb_rendered_defender_ends`` — an isolated re-author of the
    emitter's coordinated transition spread (``author_transition_end_coords``).
    The contesting defender in that spread is deterministic, so the isolated
    re-author reproduces exactly the defender the emitter renders.
  * ``HCO`` / ``FCP`` → the shipped ``_uess_sync_emitted_shot_coords`` throwaway
    emitter pre-pass (unchanged).

Later turns plug new implementations in here; call sites keep reading through
``rendered_positions_for_contest`` and never change.
"""

from __future__ import annotations

import random
from typing import Any, Dict, Optional


def fb_rendered_defender_ends(
    *,
    turn_result: Dict[str, Any],
    fb_drive: Dict[str, Any],
    stealer_id: str,
    off_start_by_id: Dict[str, Dict[str, float]],
    def_start_by_id: Dict[str, Dict[str, float]],
    bh_start: Dict[str, float],
    bh_end: Dict[str, float],
    is_away_offense: bool,
) -> Dict[str, Dict[str, float]]:
    """Return ``{defender_id: {x, y}}`` — the defender ends the FB emitter will
    render for this drive — by re-authoring the coordinated transition spread.

    RNG-isolated (``getstate``/``setstate``): ``author_transition_end_coords``
    draws from the global stream only for the offense leads/trailers and the two
    far help defenders — never the contesting BH defender (deterministic
    ``meet`` / ``_chase_behind``) — so the isolated call reproduces the rendered
    contester while leaving ``resolve_shot``'s make/miss byte-identical.
    """
    from BackEnd.engine.fb_drive_step_emitter import derive_transition_author_inputs
    from BackEnd.engine.after_steal_transition_positioning import (
        author_transition_end_coords,
    )

    kwargs = derive_transition_author_inputs(
        turn_result=turn_result,
        fb_drive=fb_drive,
        stealer_id=stealer_id,
        off_start_by_id=off_start_by_id,
        def_start_by_id=def_start_by_id,
        bh_start=bh_start,
        bh_end=bh_end,
        is_away_offense=is_away_offense,
    )
    state = random.getstate()
    try:
        spread = author_transition_end_coords(**kwargs)
    finally:
        random.setstate(state)
    return {pid: c for pid, c in spread.items() if pid in def_start_by_id}


def rendered_positions_for_contest(
    *,
    turn_type: Optional[str],
    turn_result: Optional[Dict[str, Any]] = None,
    game: Any = None,
    **kw: Any,
) -> Any:
    """Universal entry point: the rendered player positions a pre-emit decision
    should read, always RNG-isolated. Dispatches per turn type.

    - ``FAST_BREAK`` → ``fb_rendered_defender_ends`` (returns defender ends).
    - ``HCO`` / ``FCP`` → ``_uess_sync_emitted_shot_coords`` (syncs every
      ``player.coords`` to the emitted shoot-step and returns the shooter coord).
    """
    tt = (turn_type or "").upper()
    if tt in ("FAST_BREAK", "FB"):
        return fb_rendered_defender_ends(turn_result=turn_result or {}, **kw)
    from BackEnd.engine.phase_resolution import _uess_sync_emitted_shot_coords

    return _uess_sync_emitted_shot_coords(
        game,
        kw.get("skeleton"),
        kw.get("animations"),
        kw.get("roles"),
        tt or "HCO",
    )
