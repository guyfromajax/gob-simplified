"""Steal → FAST_BREAK vs HCO routing (path-count × aggression).

Called at the end of the steal turn (HCO turnover / FCP / HCT), before the next
possession runs. Potential challengers are the victim team's five on-floor
players who can win an AG sprint race to a meet on stealer → after-steal shot
spot that is x-ahead of the stealer. No path-corridor pre-filter.
"""

from __future__ import annotations

from BackEnd.utils.sim_random import sim_rng as random
from typing import Any, Dict

from BackEnd.constants.fast_break_constants import STEAL_FB_PROB_BY_POTENTIAL_CUTOFFS
from BackEnd.engine.cutoff_resolution import POSITIONS, cutoff_meet_point
from BackEnd.utils.animation_step_helpers import _ag_grid_per_game_sec
from BackEnd.utils.fb_geo_helpers import steal_meet_x_ahead_valid
from BackEnd.utils.situational_logic import slow_it_down_defense_setting


def sample_after_steal_shot_spot(is_away_offense: bool) -> Dict[str, float]:
    """Same rim-band sample as the after-steal drive BH target."""
    distance = random.randint(2, 4)
    if is_away_offense:
        x = 9.0 + distance
    else:
        x = 91.0 - distance
    y = float(random.randint(19, 31))
    return {"x": x, "y": y}


def _coord_of(player: Any) -> Dict[str, float]:
    raw = getattr(player, "coords", None) or {}
    x = raw.get("x", 50.0) if isinstance(raw, dict) else 50.0
    y = raw.get("y", 25.0) if isinstance(raw, dict) else 25.0
    return {"x": float(x), "y": float(y)}


def count_potential_steal_cutoff_defenders(
    *,
    bh_start: Dict[str, float],
    shot_spot: Dict[str, float],
    bh: Any,
    new_def_lineup: Dict[str, Any],
    is_away_offense: bool,
) -> int:
    """How many new-defense players can cut off stealer → shot_spot in time."""
    bh_rate = _ag_grid_per_game_sec(bh, "sprint")
    if bh_rate <= 0:
        return 0
    count = 0
    for pos in POSITIONS:
        defender = new_def_lineup.get(pos)
        if defender is None:
            continue
        dxy = _coord_of(defender)
        def_rate = _ag_grid_per_game_sec(defender, "sprint")
        meet = cutoff_meet_point(
            bh_start,
            shot_spot,
            bh_rate,
            dxy,
            def_rate,
            defender_time_slack=1.0,
        )
        if meet is None:
            continue
        if steal_meet_x_ahead_valid(meet, bh_start, is_away_offense=is_away_offense):
            count += 1
    return count


def steal_fast_break_probability(
    aggression_level: Any,
    potential_cutoff_count: int,
) -> float:
    """P(FAST_BREAK) from the confirmed 0 / 1 / 2+ × aggression 0–4 table."""
    try:
        agg = int(aggression_level)
    except (TypeError, ValueError):
        agg = 2
    agg = max(0, min(4, agg))
    if potential_cutoff_count <= 0:
        bucket = 0
    elif potential_cutoff_count == 1:
        bucket = 1
    else:
        bucket = 2
    return float(STEAL_FB_PROB_BY_POTENTIAL_CUTOFFS[bucket][agg])


def choose_steal_next_offensive_state(
    game: Any,
    stealer: Any,
) -> str:
    """Roll FAST_BREAK vs HCO after a steal. Does not mutate ``game``.

    At resolution time ``game.defense_team`` is still the stealing team and
    ``game.offense_team`` is the victim (new defense for the break).
    """
    game_state = game.game_state
    stealing_team = game.defense_team
    victim_team = game.offense_team
    aggression = slow_it_down_defense_setting(
        game_state,
        stealing_team,
        "aggression",
        (getattr(stealing_team, "strategy_settings", None) or {}).get("aggression", 2),
    )
    if isinstance(game_state.get("last_stealer_coords"), dict):
        bh_start = {
            "x": float(game_state["last_stealer_coords"].get("x", 50.0)),
            "y": float(game_state["last_stealer_coords"].get("y", 25.0)),
        }
    else:
        bh_start = _coord_of(stealer)

    is_away_offense = bool(
        getattr(stealing_team, "team_id", None)
        == getattr(game.away_team, "team_id", None)
    )
    shot_spot = sample_after_steal_shot_spot(is_away_offense)
    potential = count_potential_steal_cutoff_defenders(
        bh_start=bh_start,
        shot_spot=shot_spot,
        bh=stealer,
        new_def_lineup=getattr(victim_team, "lineup", None) or {},
        is_away_offense=is_away_offense,
    )
    p_fb = steal_fast_break_probability(aggression, potential)
    return "FAST_BREAK" if random.random() < p_fb else "HCO"
