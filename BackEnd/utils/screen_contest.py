"""Spatial screens, Stage B: contest the screen — FIGHT THROUGH / GO AROUND / SWITCH.

Stage A puts the screener in the defender's path. Stage B decides what that defender does
about it. Without Stage B a screen is a cone: it is in the way and nothing happens.

REQUIRES STAGE A. ``GOB_SCREEN_CONTEST=1`` with ``GOB_SCREEN_TARGETING=0`` logs once and
no-ops. It does NOT half-apply: contesting a screen that was never placed anywhere near
the defender would be scoring a fiction, and the draws would move for no modelled reason.

NO EXISTING SETTING TO REUSE. Searched before adding: there is no switch-propensity
control anywhere — not in ``strategy_calls`` (whose eight keys are offense/defense/
aggression/tempo/press/trap/press_trap/aggression_roll), not in ``playbook_settings``,
and the words "fight through", "hedge", "ICE" and "go around" appear nowhere in the
backend. Stage B introduces the concept; the outcome falls out of the two defenders'
attributes rather than a team dial, so nothing is stranded if a dial is added later.

THE MODEL — two stages, the house's own shape
---------------------------------------------
``pass_contest`` and ``boxout_contest`` both split into "pure geometry picks who is
eligible" then "``(weighted attribute composite) x rand(1, 6)`` each side". Stage A is
the geometry; this is the rolls. Jamie's ``randint(1, 6)`` is untouched — same die, new
multiplicand — and it is what keeps an attribute edge a tilt rather than a certainty.

  1. NAVIGATE vs HOLD. The receiver's defender tries to get through; the screener tries
     to hold the screen. Defender wins (ties included) -> **FIGHT THROUGH**: nothing
     changes, he stays with his man.
  2. Only if he lost, the two defenders try to talk their way out of it: their combined
     communication vs the screener's hold, fresh rolls. Pair wins -> **SWITCH** (the
     competent answer, at the price of whatever mismatch it creates). Pair loses ->
     **GO AROUND**: he trails the screen and arrives a body-width late.

A TIE GOES TO THE DEFENDER at stage 1, the same non-RNG tiebreak ``resolve_boxout`` uses
and for the same reason: "nobody wins the leverage" means the position does not change
hands. It gives the defence a structural floor at equal attributes, which is reported in
reports/spatial-screens-phase2.md rather than buried.

DRAWS ARE GATED, NOT JUST THEIR EFFECT. ``resolve_screen_contest`` is never called with
the flag off, so the stream is untouched — proved by the 240/240 flag-off gate, which is
on fingerprint AND draws.

RNG IS ``sim_rng``. Not the global ``random``: ``shared.calculate_screen_score``
(shared.py:1467) draws from the global module, and that is a defect this does not copy —
a Mongo write that matches zero documents can move the global stream.

``GOB_SCREEN_CONTEST`` gates it, default OFF.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from BackEnd.utils.sim_random import sim_rng as _default_rng

#: The flag. Unset or anything other than "1" means OFF. Read at CALL time.
SCREEN_CONTEST_FLAG = "GOB_SCREEN_CONTEST"

FIGHT_THROUGH = "fight_through"
GO_AROUND = "go_around"
SWITCH = "switch"

#: Getting through a screen: quickness and strength in equal measure, awareness to see it
#: coming, and the discipline not to foul on the way through (ND = "No Dumb Fouls",
#: shared.py:3338). Weights sum to 1.0 — the house contract for a composite multiplied by
#: rand(1, 6) (see ``shared.scale_score_to_100``). **This is the place to tune.** NOT TUNED.
NAVIGATE_WEIGHTS = {"AG": 0.35, "ST": 0.35, "IQ": 0.20, "ND": 0.10}

#: Holding a screen: body position first, then timing and the willingness to take contact.
#: Deliberately NOT athletic — a slow strong screener sets a good screen.
SCREEN_HOLD_WEIGHTS = {"ST": 0.50, "IQ": 0.30, "CH": 0.20}

#: Switching is communication: two defenders calling it in the same half-second.
SWITCH_WEIGHTS = {"IQ": 0.70, "CH": 0.30}

_WARNED = [False]


def screen_contest_enabled() -> bool:
    return os.environ.get(SCREEN_CONTEST_FLAG, "") == "1"


def warn_if_contest_without_targeting() -> None:
    """``GOB_SCREEN_CONTEST=1`` without ``GOB_SCREEN_TARGETING=1``. Log ONCE per process and
    do nothing — never silently half-apply."""
    if _WARNED[0]:
        return
    _WARNED[0] = True
    logging.warning(
        "GOB_SCREEN_CONTEST=1 but GOB_SCREEN_TARGETING is off — screen contests are "
        "DISABLED. Stage B contests the screen Stage A places; without the placement "
        "there is no screen to contest and the draws would move for no modelled reason."
    )


def _composite(player: Any, weights: Dict[str, float]) -> float:
    attrs = getattr(player, "attributes", None) or {}
    return sum(float(attrs.get(k, 0) or 0) * w for k, w in weights.items())


def _roll(player: Any, weights: Dict[str, float], rng: Any) -> float:
    return _composite(player, weights) * rng.randint(1, 6)


def resolve_screen_contest(defender: Any, screener: Any, screener_defender: Any,
                           *, rng: Any = None) -> Dict[str, Any]:
    """One screen, resolved. Returns ``{"outcome", "navigate", "hold", ...}``.

    Exactly two rolls when the defender fights through, four when he does not — a fixed,
    branch-determined draw count, so the stream stays reproducible.
    """
    r = _default_rng if rng is None else rng
    navigate = _roll(defender, NAVIGATE_WEIGHTS, r)
    hold = _roll(screener, SCREEN_HOLD_WEIGHTS, r)
    if navigate >= hold:                      # tie goes to the defender
        return {"outcome": FIGHT_THROUGH, "navigate": navigate, "hold": hold,
                "switch_score": None, "hold2": None}
    # He is screened. Can the two of them switch it?
    pair = (_composite(defender, SWITCH_WEIGHTS)
            + _composite(screener_defender, SWITCH_WEIGHTS)) / 2.0
    switch_score = pair * r.randint(1, 6)
    hold2 = _roll(screener, SCREEN_HOLD_WEIGHTS, r)
    outcome = SWITCH if switch_score >= hold2 else GO_AROUND
    return {"outcome": outcome, "navigate": navigate, "hold": hold,
            "switch_score": switch_score, "hold2": hold2}
