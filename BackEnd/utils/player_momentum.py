"""Player Momentum (MO) break resets.

Applied at quarter breaks, timeouts, and halftime — NOT at foul-outs.
See _documentation_master/projects/Player_Momentum_System.md. All tunables
live in BackEnd/constants/momentum.py.
"""
import random

from BackEnd.constants.momentum import (
    MO_RESET_REDUCTION_MIN,
    MO_RESET_REDUCTION_MAX,
    MO_HALFTIME_REDUCTION_MIN,
    MO_HALFTIME_REDUCTION_MAX,
    MO_FINAL_SHOT_BONUS,
    MO_DUNK_DELTA,
    MO_SHOT_ROLL_BASE,
    MO_SHOT_ROLL_POSITIVE,
    MO_SHOT_ROLL_NEGATIVE,
    MO_SHOT_IMPACT_PCT_PER_LEVEL,
    MO_SHOTCLOCK_BASE_PCT,
    MO_SHOTCLOCK_OFFENSE_DELTA,
    MO_SHOTCLOCK_DEFENSE_DELTA,
    MO_TEAM_MIN,
    MO_TEAM_MAX,
)


def apply_made_dunk_momentum(player, *, made: bool, dunk_stamp=None, family_id=None) -> None:
    """Made dunk → shooter ``+MO_DUNK_DELTA`` (Player_Momentum_System.md).

    Call after ``select_and_stamp_shot_micro()`` using the stamped
    ``micro_movement_family``, or pass ``dunk_stamp`` from ``prepare_dunk_stamp()``
    when micro stamping has not run yet."""
    if player is None or not made:
        return
    if dunk_stamp is not None:
        if dunk_stamp.get("dunk_miss") or dunk_stamp.get("force_miss"):
            return
        family_id = dunk_stamp.get("family_id")
    from BackEnd.engine.shot_micro_movements import is_dunk_micro_family

    if is_dunk_micro_family(family_id):
        player.add_momentum(MO_DUNK_DELTA)


def mo_shot_roll(attributes) -> int:
    """MO-aware replacement for the base ``random.randint(1, 6)`` shot roll
    (shooter base roll + OREB putback roll). With MO > 0 there is a
    ``|MO| × MO_SHOT_IMPACT_PCT_PER_LEVEL`` % chance to roll the favorable
    range; with MO < 0 the same chance to roll the unfavorable range;
    otherwise the standard base roll. See Player_Momentum_System.md."""
    mo = int((attributes or {}).get("MO", 0) or 0)
    if mo > 0 and random.randint(1, 100) <= min(100, mo * MO_SHOT_IMPACT_PCT_PER_LEVEL):
        return random.randint(*MO_SHOT_ROLL_POSITIVE)
    if mo < 0 and random.randint(1, 100) <= min(100, -mo * MO_SHOT_IMPACT_PCT_PER_LEVEL):
        return random.randint(*MO_SHOT_ROLL_NEGATIVE)
    return random.randint(*MO_SHOT_ROLL_BASE)


def team_momentum(team) -> int:
    """Derived Team Momentum = sum of the team's 5 active (lineup) players'
    MO, clamped to [MO_TEAM_MIN, MO_TEAM_MAX]. Computed on demand — there is
    no stored team-momentum value. See Player_Momentum_System.md."""
    lineup = getattr(team, "lineup", {}) or {}
    total = sum(
        int(p.attributes.get("MO", 0) or 0) for p in lineup.values() if p is not None
    )
    return max(MO_TEAM_MIN, min(MO_TEAM_MAX, total))


def apply_shot_clock_violation_momentum(offense_team, defense_team) -> None:
    """On a shot-clock violation: each active offensive player has a
    ``clamp(BASE − offenseTeamMO, 0, 100)`` % chance of −1 MO; each active
    defensive player a ``clamp(BASE + defenseTeamMO, 0, 100)`` % chance of
    +1 MO. Team MO is snapshotted before any change. See
    Player_Momentum_System.md. Pass the violating offense + its opponent."""
    if offense_team is None or defense_team is None:
        return
    off_mo = team_momentum(offense_team)
    def_mo = team_momentum(defense_team)
    off_pct = max(0, min(100, MO_SHOTCLOCK_BASE_PCT - off_mo))
    def_pct = max(0, min(100, MO_SHOTCLOCK_BASE_PCT + def_mo))
    for p in (getattr(offense_team, "lineup", {}) or {}).values():
        if p is not None and random.randint(1, 100) <= off_pct:
            p.add_momentum(MO_SHOTCLOCK_OFFENSE_DELTA)
    for p in (getattr(defense_team, "lineup", {}) or {}).values():
        if p is not None and random.randint(1, 100) <= def_pct:
            p.add_momentum(MO_SHOTCLOCK_DEFENSE_DELTA)


def _reset_value(mo: int, is_active: bool, red_min: int, red_max: int) -> int:
    # Every break (timeout / Q1→Q2 / Q3→Q4 / OT / halftime) uses one mechanic:
    # bench → 0; active decay toward 0 by randint(red_min, red_max), never
    # crossing 0 — symmetric for + and − MO. The range encodes the break type
    # (timeouts smallest, halftime largest); the caller selects it.
    if not is_active:
        return 0
    if mo > 0:
        return max(0, mo - random.randint(red_min, red_max))
    if mo < 0:
        return min(0, mo + random.randint(red_min, red_max))
    return 0


def reset_all_player_momentum(game) -> None:
    """End of game: zero every player's MO on both teams (so no in-game momentum
    leaks past the game). See Player_Momentum_System.md / End_Of_Game_System.md."""
    for team in (game.home_team, game.away_team):
        for player in team.get_all_players():
            player.attributes["MO"] = 0
    gs = getattr(game, "game_state", None)
    if isinstance(gs, dict):
        gs["mo_final_shot_maker_id"] = None


def apply_player_momentum_resets(
    game,
    is_halftime: bool = False,
    reduction_min: int = MO_RESET_REDUCTION_MIN,
    reduction_max: int = MO_RESET_REDUCTION_MAX,
) -> None:
    """Reset every player's MO for a break. Active = the team's 5 lineup
    players; everyone else is bench (→ 0). Active players decay toward 0 by a
    randint in the break's range (never crossing 0; symmetric for + and − MO):
    quarter/OT breaks use the default range, timeouts pass the smaller
    MO_TIMEOUT_REDUCTION_* range, and ``is_halftime`` selects the larger
    MO_HALFTIME_REDUCTION_* range. Then apply the Final-Shot bonus to the player
    flagged as having made the quarter's final shot (if any)."""
    if is_halftime:
        reduction_min, reduction_max = MO_HALFTIME_REDUCTION_MIN, MO_HALFTIME_REDUCTION_MAX
    for team in (game.home_team, game.away_team):
        lineup = getattr(team, "lineup", {}) or {}
        active_ids = {
            getattr(p, "player_id", None) for p in lineup.values() if p is not None
        }
        for player in team.get_all_players():
            mo = int(player.attributes.get("MO", 0) or 0)
            is_active = getattr(player, "player_id", None) in active_ids
            player.attributes["MO"] = _reset_value(
                mo, is_active, reduction_min, reduction_max
            )

    # Final-Shot bonus: applied AFTER the reset (Player_Momentum_System.md).
    maker_id = game.game_state.get("mo_final_shot_maker_id")
    if maker_id:
        for team in (game.home_team, game.away_team):
            for player in team.get_all_players():
                if getattr(player, "player_id", None) == maker_id:
                    player.add_momentum(MO_FINAL_SHOT_BONUS)
                    break
        game.game_state["mo_final_shot_maker_id"] = None
