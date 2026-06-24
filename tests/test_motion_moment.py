"""Dynamic HCO per-step moment (foul/steal/turnover) migrated from HCT — unit tests for the
moment walk's gating (man-only, per-turn defense pressure) and HCT→HCO outcome mapping. The
inner attribute contest (`_resolve_hco_moment` → `_resolve_moment`) is monkeypatched so these
isolate the WALK logic."""
import random
import BackEnd.engine.phase_resolution as PR


class _Team:
    def __init__(self, aggression=4):
        self.strategy_settings = {"aggression": aggression}
        self.is_user_team = False


class _Game:
    def __init__(self, defense_playcall="Man", aggression=4):
        self.game_state = {"defense_playcall": defense_playcall}
        self.defense_team = _Team(aggression)
        self.offense_team = _Team(aggression)


class _P:
    def __init__(self, pid):
        self.player_id = pid
        self.position = pid


def _skel(n=3):
    return {"steps": [{"pos_actions": {"PG": {"location": "key", "action": "handle_ball"}}}
                      for _ in range(n)]}


OFF = {"PG": _P("o_pg")}
DEF = {"PG": _P("d_pg")}


def test_moment_walk_zone_returns_none():
    # v1 is man-only — zone defers (no clean 1:1 defender).
    assert PR._resolve_hco_moment_walk(_skel(), _Game(defense_playcall="2-3 Zone"), OFF, DEF) is None


def test_moment_walk_no_pressure_returns_none(monkeypatch):
    # aggression 0 + max roll (4 > 0) → defense not pressuring this turn → no moment.
    monkeypatch.setattr(random, "randint", lambda a, b: b)
    assert PR._resolve_hco_moment_walk(_skel(), _Game(aggression=0), OFF, DEF) is None


def test_moment_walk_fires_steal(monkeypatch):
    monkeypatch.setattr(random, "randint", lambda a, b: a)  # 0 <= 4 → pressure engaged
    monkeypatch.setattr(PR, "_resolve_hco_moment", lambda *a, **k: ("STEAL", 0.5, _P("d_pg")))
    assert PR._resolve_hco_moment_walk(_skel(), _Game(aggression=4), OFF, DEF) == "STEAL"


def test_moment_walk_dead_ball_maps_to_hco_result_type(monkeypatch):
    monkeypatch.setattr(random, "randint", lambda a, b: a)
    monkeypatch.setattr(PR, "_resolve_hco_moment", lambda *a, **k: ("DEAD BALL", 0.5, None))
    assert PR._resolve_hco_moment_walk(_skel(), _Game(aggression=4), OFF, DEF) == "DEAD_BALL_TURNOVER"


def test_moment_walk_fouls_map(monkeypatch):
    monkeypatch.setattr(random, "randint", lambda a, b: a)
    monkeypatch.setattr(PR, "_resolve_hco_moment", lambda *a, **k: ("O_FOUL", 1.0, None))
    assert PR._resolve_hco_moment_walk(_skel(), _Game(aggression=4), OFF, DEF) == "O_FOUL"
    monkeypatch.setattr(PR, "_resolve_hco_moment", lambda *a, **k: ("D_FOUL", 1.0, _P("d_pg")))
    assert PR._resolve_hco_moment_walk(_skel(), _Game(aggression=4), OFF, DEF) == "D_FOUL"


def test_moment_walk_neutral_returns_none(monkeypatch):
    # POS_O / NEUTRAL → no hard outcome → normal shot resolution proceeds.
    monkeypatch.setattr(random, "randint", lambda a, b: a)
    monkeypatch.setattr(PR, "_resolve_hco_moment", lambda *a, **k: ("NEUTRAL", 1.0, None))
    assert PR._resolve_hco_moment_walk(_skel(), _Game(aggression=4), OFF, DEF) is None
