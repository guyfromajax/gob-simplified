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


def test_moment_walk_zone_fires_and_stashes_credited(monkeypatch):
    # Zone is now supported: the on-ball defender is resolved by zone (not a man matchup), the
    # moment fires, and the credited defender is stashed for the non-shot block.
    monkeypatch.setattr(random, "randint", lambda a, b: a)  # engaged
    monkeypatch.setattr(PR, "_zone_bh_defender", lambda *a, **k: _P("d_sf"))
    monkeypatch.setattr(PR, "_resolve_hco_moment", lambda *a, **k: ("STEAL", 0.5, _P("d_sf")))
    g = _Game(defense_playcall="2-3 Zone", aggression=4)
    assert PR._resolve_hco_moment_walk(_skel(), g, OFF, DEF) == "STEAL"
    assert g.game_state["_hco_moment_defender_id"] == "d_sf"


def test_moment_walk_zone_not_engaged_returns_none(monkeypatch):
    # Same per-turn aggression engagement gate applies to zone.
    monkeypatch.setattr(random, "randint", lambda a, b: b)  # 4 > 0 → not engaged
    assert PR._resolve_hco_moment_walk(_skel(), _Game(defense_playcall="2-3 Zone", aggression=0), OFF, DEF) is None


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


# --------------------------------------------------- option B: per-step reach-in tagging

def test_moment_walk_option_b_tags_every_non_terminal_contest(monkeypatch):
    # NEUTRAL/POS_O on each contested step → no hard outcome, but every step records the on-ball
    # defender so the FE renders the (failed) steal-attempt reach-in. _skel(3) → steps 1,2 walked.
    monkeypatch.setattr(random, "randint", lambda a, b: a)
    monkeypatch.setattr(PR, "_resolve_hco_moment", lambda *a, **k: ("POS_O", 1.0, None))
    tags = []
    assert PR._resolve_hco_moment_walk(_skel(3), _Game(aggression=4), OFF, DEF, reach_in_tags=tags) is None
    assert tags == [(1, "d_pg"), (2, "d_pg")]


def test_moment_walk_option_b_no_tags_after_terminal(monkeypatch):
    # A terminal outcome on the first contested step → walk returns immediately; the terminal
    # reach-in comes from the stopper step, so no non-terminal tags are collected.
    monkeypatch.setattr(random, "randint", lambda a, b: a)
    monkeypatch.setattr(PR, "_resolve_hco_moment", lambda *a, **k: ("STEAL", 0.5, _P("d_pg")))
    tags = []
    assert PR._resolve_hco_moment_walk(_skel(3), _Game(aggression=4), OFF, DEF, reach_in_tags=tags) == "STEAL"
    assert tags == []


def test_moment_walk_option_b_inert_when_not_engaged(monkeypatch):
    # Not engaged (aggression 0, max roll) → no contests, no tags.
    monkeypatch.setattr(random, "randint", lambda a, b: b)
    tags = []
    assert PR._resolve_hco_moment_walk(_skel(3), _Game(aggression=0), OFF, DEF, reach_in_tags=tags) is None
    assert tags == []


# --------------------------------------------------- zone on-ball defender resolution

def test_zone_bh_defender_uses_polygon_match(monkeypatch):
    # Primary path: the defender whose zone polygon contains the BH's spot.
    import BackEnd.engine.attack_drive_clearance as ADC
    monkeypatch.setattr(ADC, "_zone_boundaries_for_spot", lambda *a, **k: {"SF": [(0, 0)]})
    monkeypatch.setattr(ADC, "_spot_display_coords", lambda *a, **k: {"x": 50, "y": 25})
    monkeypatch.setattr(ADC, "_defender_for_zone_point", lambda *a, **k: "SF")
    deff = {"SF": _P("d_sf"), "PG": _P("d_pg")}
    assert PR._zone_bh_defender("2-3 Zone", "key", False, deff, "PG").player_id == "d_sf"


def test_zone_bh_defender_falls_back_to_position_match(monkeypatch):
    # No polygon contains the point and no polygons to centroid → position-on-position fallback.
    import BackEnd.engine.attack_drive_clearance as ADC
    monkeypatch.setattr(ADC, "_zone_boundaries_for_spot", lambda *a, **k: {})
    monkeypatch.setattr(ADC, "_spot_display_coords", lambda *a, **k: {"x": 50, "y": 25})
    monkeypatch.setattr(ADC, "_defender_for_zone_point", lambda *a, **k: None)
    deff = {"PG": _P("d_pg")}
    assert PR._zone_bh_defender("2-3 Zone", "key", False, deff, "PG").player_id == "d_pg"


def test_zone_bh_defender_nearest_zone_fallback(monkeypatch):
    # Point in no polygon, but polygons exist → nearest-centroid (here only SF has one).
    import BackEnd.engine.attack_drive_clearance as ADC
    monkeypatch.setattr(ADC, "_zone_boundaries_for_spot", lambda *a, **k: {"SF": [(48, 24), (52, 26)]})
    monkeypatch.setattr(ADC, "_spot_display_coords", lambda *a, **k: {"x": 50, "y": 25})
    monkeypatch.setattr(ADC, "_defender_for_zone_point", lambda *a, **k: None)
    deff = {"SF": _P("d_sf"), "PG": _P("d_pg")}
    assert PR._zone_bh_defender("2-3 Zone", "key", False, deff, "PG").player_id == "d_sf"
