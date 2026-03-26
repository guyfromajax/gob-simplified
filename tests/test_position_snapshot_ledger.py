"""Tests for position snapshot ledger (HCO pre-resolve_shot v1)."""

from types import SimpleNamespace

from BackEnd.models.player import Player
from BackEnd.utils.position_snapshot_ledger import (
    SCHEMA_VERSION,
    PositionSnapshotLedger,
    build_hco_pre_resolve_shot_snapshot,
    build_inbound_destinations_snapshot,
    build_opening_tip_snapshot_from_animations,
    build_phase_post_stopper_snapshot,
    build_positions_from_destinations,
    collect_lineup_positions,
)


def _player(n: int) -> Player:
    p = Player(
        {
            "first_name": "T",
            "last_name": str(n),
            "AG": 50,
            "BH": 50,
            "OD": 50,
            "_id": f"id-{n}",
        }
    )
    p.coords = {"x": float(n * 10), "y": float(n + 1)}
    return p


def test_collect_lineup_positions_ten_players():
    off = {k: _player(i) for i, k in enumerate(["PG", "SG", "SF", "PF", "C"])}
    def_ = {k: _player(i + 5) for i, k in enumerate(["PG", "SG", "SF", "PF", "C"])}
    pos = collect_lineup_positions(off, def_)
    assert len(pos) == 10
    for pid, xy in pos.items():
        assert "x" in xy and "y" in xy
        assert isinstance(xy["x"], float)
        assert isinstance(xy["y"], float)


def test_position_snapshot_ledger_append_and_clear():
    led = PositionSnapshotLedger()
    assert led.snapshots() == []
    led.append({"schema_version": 1})
    assert len(led.snapshots()) == 1
    led.clear()
    assert led.snapshots() == []


def test_build_hco_pre_resolve_shot_snapshot_shape():
    off = {"PG": _player(0)}
    for i, k in enumerate(["SG", "SF", "PF", "C"], start=1):
        off[k] = _player(i)
    def_ = {k: _player(i + 10) for i, k in enumerate(["PG", "SG", "SF", "PF", "C"])}
    game = SimpleNamespace(offense_team=SimpleNamespace(team_id="off-1"))
    skeleton = {
        "steps": [
            {"pos_actions": {}},
            {"pos_actions": {}},
            {"pos_actions": {"PG": {"action": "shoot", "location": "key"}}},
        ]
    }
    roles = {"ball_handler": off["PG"], "shooter": off["PG"], "shooter_pos": "PG"}
    snap = build_hco_pre_resolve_shot_snapshot(game, off, def_, skeleton, roles)
    assert snap["schema_version"] == SCHEMA_VERSION
    assert snap["source"] == "hco_pre_resolve_shot"
    assert len(snap["positions"]) == 10
    assert snap["ball_handler_id"] == off["PG"].player_id
    assert snap["possession_team_id"] == "off-1"
    cp = snap["checkpoint"]
    assert cp["turn_type"] == "HCO"
    assert cp["checkpoint_kind"] == "skeleton_step"
    assert cp["label"] == "pre_resolve_shot"
    assert cp["step_count"] == 3
    assert cp["step_index"] == 2


def test_build_positions_from_destinations_maps_slots():
    off = {"PG": _player(1), "SG": _player(2)}
    def_ = {"PG": _player(3), "SG": _player(4)}
    o_dest = {"PG": {"x": 10.0, "y": 20.0}, "SG": {"x": 30.0, "y": 40.0}}
    d_dest = {"PG": {"x": 50.0, "y": 60.0}, "SG": {"x": 70.0, "y": 80.0}}
    pos = build_positions_from_destinations(off, def_, o_dest, d_dest)
    assert len(pos) == 4
    assert pos[off["PG"].player_id]["x"] == 10.0
    assert pos[def_["SG"].player_id]["y"] == 80.0


def test_build_inbound_destinations_snapshot_shape():
    off = {"PG": _player(0)}
    for i, k in enumerate(["SG", "SF", "PF", "C"], start=1):
        off[k] = _player(i)
    def_ = {k: _player(i + 10) for i, k in enumerate(["PG", "SG", "SF", "PF", "C"])}
    game = SimpleNamespace(offense_team=SimpleNamespace(team_id="off-1"))
    o_dest = {p: {"x": float(i), "y": float(i)} for i, p in enumerate(["PG", "SG", "SF", "PF", "C"])}
    d_dest = {p: {"x": float(i + 10), "y": float(i)} for i, p in enumerate(["PG", "SG", "SF", "PF", "C"])}
    snap = build_inbound_destinations_snapshot(
        game, off, def_, o_dest, d_dest, "SIDE_INBOUND", "test_sip"
    )
    assert snap["checkpoint"]["turn_type"] == "SIDE_INBOUND"
    assert len(snap["positions"]) == 10


def test_build_phase_post_stopper_snapshot_hco_and_fb():
    off = {"PG": _player(0)}
    for i, k in enumerate(["SG", "SF", "PF", "C"], start=1):
        off[k] = _player(i)
    def_ = {k: _player(i + 10) for i, k in enumerate(["PG", "SG", "SF", "PF", "C"])}
    game = SimpleNamespace(offense_team=SimpleNamespace(team_id="off-1"))
    skeleton = {"steps": [{"pos_actions": {}}, {"pos_actions": {}}]}
    roles = {"ball_handler": off["PG"]}
    hco_snap = build_phase_post_stopper_snapshot(
        game, off, def_, skeleton, roles, "HCO", "turnover", "test_hco"
    )
    assert hco_snap["checkpoint"]["turn_type"] == "HCO"
    assert hco_snap["checkpoint"]["label"] == "post_stopper_animation"
    assert hco_snap["checkpoint"]["outcome_kind"] == "turnover"
    assert hco_snap["checkpoint"]["step_count"] == 2
    fb_snap = build_phase_post_stopper_snapshot(
        game, off, def_, None, roles, "FAST_BREAK", "non_shooting_foul", "test_fb"
    )
    assert fb_snap["checkpoint"]["turn_type"] == "FAST_BREAK"
    assert fb_snap["checkpoint"]["custom_id"] == "fb_non_shooting_foul"
    assert len(fb_snap["positions"]) == 10


def test_build_opening_tip_snapshot_from_animations_prefers_end_then_jump_then_start():
    game = SimpleNamespace(offense_team=SimpleNamespace(team_id="off-1"))
    animations = [
        {"playerId": "a", "start": {"x": 1, "y": 2}, "end": {"x": 10, "y": 20}},
        {"playerId": "b", "start": {"x": 3, "y": 4}, "jumpCoords": {"x": 50, "y": 25}},
        {"playerId": "c", "start": {"x": 5, "y": 6}},
    ]
    snap = build_opening_tip_snapshot_from_animations(game, animations)
    assert snap["schema_version"] == SCHEMA_VERSION
    assert snap["source"] == "opening_tip"
    assert snap["possession_team_id"] == "off-1"
    assert snap["checkpoint"]["turn_type"] == "OPENING_TIP"
    assert snap["checkpoint"]["custom_id"] == "opening_tip"
    assert snap["positions"]["a"] == {"x": 10.0, "y": 20.0}
    assert snap["positions"]["b"] == {"x": 50.0, "y": 25.0}
    assert snap["positions"]["c"] == {"x": 5.0, "y": 6.0}
