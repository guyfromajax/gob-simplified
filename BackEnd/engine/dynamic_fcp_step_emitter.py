"""Dynamic FCP animation step emitter.

Thin wrapper around ``dynamic_hct_step_emitter.build_dynamic_hct_animation_steps``
that reads ``fcp_*`` intermediate keys and skips the entry walk-up (FCP starts at
BIP-end coords).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from BackEnd.utils.animation_step_schema import AnimationStep


def build_dynamic_fcp_animation_steps(
    turn_result: Dict[str, Any],
    game: Any,
) -> Optional[List[AnimationStep]]:
    """Assemble schema steps for a dynamic FCP turn (no walk-up step 0)."""
    from BackEnd.engine.dynamic_hct_step_emitter import build_dynamic_hct_animation_steps

    payload = dict(turn_result)
    payload.setdefault("fcp_skip_walk_up", True)
    return build_dynamic_hct_animation_steps(payload, game)
