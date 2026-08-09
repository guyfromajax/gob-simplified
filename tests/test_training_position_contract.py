from pathlib import Path

from BackEnd.constants import training_shape


ROOT = Path(__file__).resolve().parents[1]


def _player(**overrides):
    player = {
        "training_position": "C",
        "position_intent": "PG",
        "position_ratings": {"SF": 90, "PG": 70, "C": 40},
        "attributes": {a: 50 for a in training_shape.CORE_12},
    }
    player.update(overrides)
    return player


def test_one_training_position_priority_contract():
    assert training_shape.resolve_training_position(_player()) == "C"
    assert training_shape.resolve_training_position(
        _player(training_position=None)
    ) == "PG"
    assert training_shape.resolve_training_position(
        _player(training_position=None, position_intent=None)
    ) == "SF"
    assert training_shape.resolve_training_position(
        _player(training_position=None, position_intent=None, position_ratings={})
    ) == "SF"


def test_producer_projection_and_floors_use_the_same_resolver(monkeypatch):
    player = _player()
    projection = training_shape.training_position_projection(player)
    assert projection == {
        "training_position": "C",
        "position_intent": "PG",
        "resolved_training_position": "C",
    }

    seen = []
    monkeypatch.setattr(
        training_shape,
        "floor_need",
        lambda position, _attr, _mean: seen.append(position) or 0,
    )
    training_shape.apply_floor_clamp_to_anchors(player)
    assert seen and set(seen) == {projection["resolved_training_position"]}


def test_all_position_consumers_use_the_canonical_resolver_or_projection():
    api = (ROOT / "BackEnd/api/franchise_routes.py").read_text(encoding="utf-8")
    team_builder = (ROOT / "BackEnd/utils/team_builder_roster.py").read_text(encoding="utf-8")
    frontend = (ROOT / "FrontEnd/static/training.js").read_text(encoding="utf-8")

    # User/CPU producers and the client payload originate from one projection.
    assert api.count("training_position_projection(") >= 3
    # User budget validation and CPU grouping consume the same resolved player shape.
    assert "pos = resolve_training_position(player)" in api
    assert "pos = resolve_training_position(p)" in api
    # Team Builder already used the canonical resolver.
    assert "pos = resolve_training_position({" in team_builder
    # Browser pricing consumes the server result; it has no independent fallback chain.
    start = frontend.index("function rosterRowPosition")
    end = frontend.index("\n}", start)
    resolver_body = frontend[start:end]
    assert "resolved_training_position" in resolver_body
    assert "position_intent" not in resolver_body
    assert "position_ratings" not in resolver_body
