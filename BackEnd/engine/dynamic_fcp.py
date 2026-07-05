"""
Dynamic Full Court Press (FCP) turn engine.

Delegates to the shared pressure loop in ``dynamic_hct`` with ``turn_mode="fcp"``.
See ``_documentation_master/projects/Z-Completed/Dynamic_FCP_Brief.md`` §11 Step 2.
"""

from __future__ import annotations

from typing import Any, Dict


def compute_dynamic_fcp_turn(game, play: Any = None) -> Dict[str, Any]:
    """
    Build the dynamic FCP turn for this engine state.

    ``play`` is the selected ``FCPPlay`` (Straight Pressure for PR1). Returns the
    same intermediate dict shape as ``compute_dynamic_hct_turn``, plus
    ``skip_walk_up=True``.
    """
    from BackEnd.engine.dynamic_hct import compute_dynamic_hct_turn

    return compute_dynamic_hct_turn(game, play, turn_mode="fcp")
