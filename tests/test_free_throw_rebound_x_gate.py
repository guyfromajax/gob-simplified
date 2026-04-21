"""Free throw miss rebound: x-distance gate from bounce (see FREE_THROW_REBOUND_MAX_X_DELTA)."""

from BackEnd.utils.shared import determine_rebounder, FREE_THROW_REBOUND_MAX_X_DELTA


class _P:
    def __init__(self, pid, tid, x):
        self.player_id = pid
        self.team_id = tid
        self.coords = {"x": x, "y": 25}
        self.attributes = {"RB": 50, "ST": 50, "IQ": 50}
        self.stats = {"game": {}}

    def record_stat(self, k):
        g = self.stats.setdefault("game", {})
        g[k] = g.get(k, 0) + 1


class _T:
    def __init__(self, tid, lineup):
        self.team_id = tid
        self.lineup = lineup
        self.team_attributes = {"rebound_modifier": 0}
        self.name = tid


class _G:
    def __init__(self, off, deff):
        self.game_state = {}
        self.offense_team = off
        self.defense_team = deff


def test_free_throw_rebound_x_gate_excludes_players_far_from_bounce_x():
    """Only players with |x - bounce_x| <= 20 are eligible; others cannot win the board."""
    assert FREE_THROW_REBOUND_MAX_X_DELTA == 20

    home_tid = "home"
    away_tid = "away"
    # Bounce near home rim (away team FT attacking home basket in this orientation).
    bounce_spot = {"x": 91.0, "y": 25.0}

    off = _T(
        home_tid,
        {
            "PG": _P("o_pg", home_tid, 40),
            "SG": _P("o_sg", home_tid, 42),
            "SF": _P("o_sf", home_tid, 88),
            "PF": _P("o_pf", home_tid, 45),
            "C": _P("o_c", home_tid, 50),
        },
    )
    # Entire defense beyond x gate — only offense SF is eligible to rebound.
    deff = _T(
        away_tid,
        {
            "PG": _P("d_pg", away_tid, 35),
            "SG": _P("d_sg", away_tid, 38),
            "SF": _P("d_sf", away_tid, 40),
            "PF": _P("d_pf", away_tid, 42),
            "C": _P("d_c", away_tid, 41),
        },
    )
    game = _G(off, deff)

    reb, team, stat = determine_rebounder(
        game,
        bounce_spot,
        max_x_delta_from_bounce=FREE_THROW_REBOUND_MAX_X_DELTA,
    )

    assert stat == "OREB"
    assert team.team_id == home_tid
    assert reb.player_id == "o_sf"


def test_free_throw_rebound_x_gate_fallback_when_all_filtered():
    """If everyone is beyond x threshold, fall back to full lineups (warning path)."""
    bounce_spot = {"x": 91.0, "y": 25.0}
    home_tid = "home"
    away_tid = "away"

    off = _T(
        home_tid,
        {"PG": _P("o_pg", home_tid, 10)},
    )
    deff = _T(
        away_tid,
        {"PG": _P("d_pg", away_tid, 12)},
    )
    game = _G(off, deff)

    reb, team, stat = determine_rebounder(
        game,
        bounce_spot,
        max_x_delta_from_bounce=FREE_THROW_REBOUND_MAX_X_DELTA,
    )

    assert reb.player_id in ("o_pg", "d_pg")
    assert stat in ("OREB", "DREB")
