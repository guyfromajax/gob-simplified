"""Season leader qualification: attempts per completed team game.

A player qualifies for a rate stat when

    attempts >= floor * team games played

Team games are games that player's team has completed in the scope being
read (wins + losses from ``franchise.results``). A tied game does not add a
win or a loss, so it is not a completed decision for this count.

Career leaderboards do not use this helper. FG% and DEF% on career scope
keep the older player-games rule (attempts >= 5 * that player's own GP).
"""

from __future__ import annotations

LEADER_QUALIFICATION_FLOORS: dict[str, int] = {
    "FG%": 5,
    "3PT%": 2,
    "FT%": 2,
    "DEF%": 8,
    "SCR%": 5,
}

ATTEMPT_FIELDS: dict[str, str] = {
    "FG%": "FGA",
    "3PT%": "3PTA",
    "FT%": "FTA",
    "DEF%": "DEF_A",
    "SCR%": "SCR_A",
}


def qualifies(stat: str, attempts, team_games) -> bool:
    """True when ``attempts`` meets ``floor * team_games`` for ``stat``.

    Zero team games never qualifies, including a player with attempts.
    Exactly ``floor * team_games`` qualifies. One attempt below does not.
    """
    floor = LEADER_QUALIFICATION_FLOORS[stat]
    games = int(team_games or 0)
    if games <= 0:
        return False
    return int(attempts or 0) >= floor * games


def team_games_from_record(wins, losses) -> int:
    return int(wins or 0) + int(losses or 0)
