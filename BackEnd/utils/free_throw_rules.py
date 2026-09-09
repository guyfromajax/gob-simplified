"""Single source of truth for how many free throws a foul awards.

Why this exists: the count used to be decided independently at each foul branch, and only two
of them consulted ``is_three``. ``shot_manager.py``'s block-reconciliation shooting foul
hardcoded 2, so a fouled missed three awarded two free throws instead of three on 17.9% of
fouled missed threes (measured, 12 games per arm). The classification was correct in every
case — ``shot_value`` came back 3 — the branch simply never asked.

The fix is structural rather than a corrected literal: no branch computes its own count.
Every foul site builds a :class:`FreeThrowAward` here and applies it with
:func:`apply_free_throw_award`, which writes all three game_state keys together so
``free_throws`` and ``free_throws_remaining`` cannot drift apart.

Scope: this covers SHOOTING fouls (where ``is_three`` matters) and the bonus/1-and-1 shape
used by blocking fouls. Non-shooting team-foul bonus logic in ``phase_resolution`` is a
separate family — ``is_three`` is meaningless there — and is deliberately not routed here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, MutableMapping

# Team-foul thresholds at which the bonus and double bonus apply.
BONUS_TEAM_FOULS = 5
DOUBLE_BONUS_TEAM_FOULS = 10


@dataclass(frozen=True)
class FreeThrowAward:
    """A free-throw trip.

    ``free_throws`` is the most the trip can produce and ``remaining`` is how many the shooter
    steps up to shoot now. They are equal except on the front end of a 1-and-1, where the
    second shot is only earned by making the first — see :func:`bonus_foul`.
    """

    free_throws: int
    remaining: int
    one_and_one: bool = False


def shooting_foul(*, is_three: bool, made: bool) -> FreeThrowAward:
    """Free throws for a shooting foul.

    A make is an and-one worth a single free throw regardless of shot value. A miss is worth
    as many free throws as the attempt was worth in points, which is the clause every buggy
    branch was missing.
    """
    if made:
        return FreeThrowAward(1, 1)
    return FreeThrowAward(3, 3) if is_three else FreeThrowAward(2, 2)


def bonus_foul(team_fouls: int) -> FreeThrowAward:
    """Free throws for a foul penalised under the team-foul bonus rather than as a shot.

    Preserves the deliberate 1-and-1 split: in the 5-9 foul band the trip is worth up to two
    but only one is shot up front, flagged by ``one_and_one`` so the second is awarded only
    on a make. Below the bonus there are no free throws at all.
    """
    if team_fouls >= DOUBLE_BONUS_TEAM_FOULS:
        return FreeThrowAward(2, 2)
    if team_fouls >= BONUS_TEAM_FOULS:
        return FreeThrowAward(2, 1, one_and_one=True)
    return FreeThrowAward(0, 0)


def fixed_two() -> FreeThrowAward:
    """Exactly two free throws, ignoring shot value and and-one.

    Used only where that is the intended rule rather than an oversight, so the two cases stay
    distinguishable: the Final Turn attack blocking foul deliberately awards two.
    """
    return FreeThrowAward(2, 2)


def apply_free_throw_award(
    game_state: MutableMapping[str, Any], award: FreeThrowAward
) -> FreeThrowAward:
    """Write the award to ``game_state``, keeping the three keys consistent by construction."""
    game_state["free_throws"] = award.free_throws
    game_state["free_throws_remaining"] = award.remaining
    game_state["one_and_one"] = award.one_and_one
    return award
