"""Unit tests for FB drive cutoff resolver (Phase 1)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from BackEnd.constants import HCO_STRING_SPOTS
from BackEnd.engine.fb_drive_resolution import resolve_fb_drive_step
from BackEnd.engine.fb_stop_decision import resolve_fb_stop_decision
from BackEnd.utils.fb_geo_helpers import attacking_basket_coord


def _player(player_id: str, **attrs):
    base = {
        "AG": 80,
        "IQ": 80,
        "CH": 80,
        "BH": 80,
        "SH": 80,
        "OD": 80,
        "ID": 80,
        "SC": 80,
        "ST": 80,
    }
    base.update(attrs)
    return SimpleNamespace(player_id=player_id, attributes=base)


def _team(shot_threshold=100):
    return SimpleNamespace(team_attributes={"shot_threshold": shot_threshold, "team_chemistry": 50})


def _lineup(prefix: str = "off"):
    positions = ("PG", "SG", "SF", "PF", "C")
    return {pos: _player(f"{prefix}-{pos}") for pos in positions}


def _flat_starts(lineup, x: float, y: float):
    return {pos: {"x": float(x), "y": float(y)} for pos in lineup}


def _drive_kwargs(**overrides):
    off_lineup = overrides.pop("off_lineup", _lineup("off"))
    def_lineup = overrides.pop("def_lineup", _lineup("def"))
    bh = overrides.pop("bh", off_lineup["PG"])
    defaults = {
        "bh": bh,
        "bh_pos": "PG",
        "bh_start": {"x": 60.0, "y": 25.0},
        "shot_spot": {"x": 88.0, "y": 25.0},
        "off_lineup": off_lineup,
        "off_starts": _flat_starts(off_lineup, 58.0, 25.0),
        "def_lineup": def_lineup,
        "def_starts": _flat_starts(def_lineup, 50.0, 25.0),
        "off_team": _team(),
        "def_team": _team(),
        "is_away_offense": False,
        "steal_entry": False,
    }
    defaults.update(overrides)
    return defaults


def test_no_meet_all_defenders_to_basket_spot():
    kwargs = _drive_kwargs(
        def_starts={
            "PG": {"x": 10.0, "y": 10.0},
            "SG": {"x": 12.0, "y": 40.0},
            "SF": {"x": 15.0, "y": 5.0},
            "PF": {"x": 18.0, "y": 45.0},
            "C": {"x": 20.0, "y": 20.0},
        }
    )
    result = resolve_fb_drive_step(**kwargs)

    assert result["outcome"] == "NO_MEET"
    assert result["bh_path_knots"] == [kwargs["bh_start"], kwargs["shot_spot"]]
    basket = attacking_basket_coord(is_away_offense=False)
    for pid, coord in result["defender_end_coords"].items():
        assert coord["x"] == pytest.approx(HCO_STRING_SPOTS["basketSpot"]["x"])
        assert coord["y"] == pytest.approx(HCO_STRING_SPOTS["basketSpot"]["y"])
    assert basket["x"] == pytest.approx(91.0)


def test_pos_o_path_includes_shimmy_knot(monkeypatch):
    meet = {"x": 75, "y": 25}

    monkeypatch.setattr(
        "BackEnd.engine.fb_drive_resolution.best_cutoff_on_drive",
        lambda *a, **k: ("SF", meet),
    )
    monkeypatch.setattr(
        "BackEnd.engine.fb_drive_resolution.resolve_cutoff_contest",
        lambda *a, **k: ("POS_O", 0.5, None),
    )
    monkeypatch.setattr(
        "BackEnd.engine.fb_drive_resolution.calculate_charge",
        lambda *a, **k: None,
    )

    result = resolve_fb_drive_step(**_drive_kwargs())

    assert result["outcome"] == "POS_O"
    assert len(result["bh_path_knots"]) == 4
    assert result["bh_path_knots"][0] == {"x": 60.0, "y": 25.0}
    assert result["bh_path_knots"][1] == meet
    assert result["bh_path_knots"][3] == {"x": 88.0, "y": 25.0}
    shimmy = result["bh_path_knots"][2]
    assert shimmy["x"] == meet["x"]
    assert abs(shimmy["y"] - meet["y"]) == pytest.approx(2.0)
    assert len(result["path_segment_game_seconds"]) == 3
    assert sum(result["path_segment_game_seconds"]) == pytest.approx(
        result["t_drive_game_seconds"]
    )


def test_d8_foul_skips_charge(monkeypatch):
    meet = {"x": 75, "y": 25}
    charge_called = {"value": False}

    def _charge(*args, **kwargs):
        charge_called["value"] = True
        return None

    monkeypatch.setattr(
        "BackEnd.engine.fb_drive_resolution.best_cutoff_on_drive",
        lambda *a, **k: ("SF", meet),
    )
    monkeypatch.setattr(
        "BackEnd.engine.fb_drive_resolution.resolve_cutoff_contest",
        lambda *a, **k: ("D_FOUL", 0.5, _player("def-SF")),
    )
    monkeypatch.setattr(
        "BackEnd.engine.fb_drive_resolution.calculate_charge",
        _charge,
    )

    result = resolve_fb_drive_step(**_drive_kwargs())

    assert result["outcome"] == "D_FOUL"
    assert charge_called["value"] is False


def test_excluded_stopper_not_selected(monkeypatch):
    meet_early = {"x": 70, "y": 25}
    meet_late = {"x": 80, "y": 25}
    calls = {"positions": []}

    def _fake_best(bh_start, target, bh_rate, def_coords, def_lineup, **kwargs):
        for pos in def_coords:
            calls["positions"].append(pos)
        if "SF" in def_coords:
            return "SF", meet_early
        return "PF", meet_late

    monkeypatch.setattr(
        "BackEnd.engine.fb_drive_resolution.best_cutoff_on_drive",
        _fake_best,
    )
    monkeypatch.setattr(
        "BackEnd.engine.fb_drive_resolution.resolve_cutoff_contest",
        lambda *a, **k: ("NEUTRAL", 0.5, None),
    )
    monkeypatch.setattr(
        "BackEnd.engine.fb_drive_resolution.calculate_charge",
        lambda *a, **k: None,
    )

    off_lineup = _lineup("off")
    def_lineup = _lineup("def")
    shot_manager = MagicMock()
    shot_manager.calculate_shot_score.return_value = (50, 40, 0, False, None, 0)
    kwargs = _drive_kwargs(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        excluded_stopper_ids={def_lineup["SF"].player_id},
        def_starts={
            "PG": {"x": 55.0, "y": 25.0},
            "SG": {"x": 56.0, "y": 30.0},
            "SF": {"x": 57.0, "y": 25.0},
            "PF": {"x": 58.0, "y": 20.0},
            "C": {"x": 59.0, "y": 25.0},
        },
        shot_manager=shot_manager,
    )
    result = resolve_fb_drive_step(**kwargs)

    assert "SF" not in calls["positions"]
    assert result["outcome"] == "NEUTRAL"
    assert result["stopper_pos"] == "PF"


def test_steal_meet_rejected_when_not_x_ahead(monkeypatch):
    meet = {"x": 60, "y": 25}  # same x as bh_start — invalid for steal

    monkeypatch.setattr(
        "BackEnd.engine.fb_drive_resolution.best_cutoff_on_drive",
        lambda *a, **k: ("SF", meet),
    )

    result = resolve_fb_drive_step(**_drive_kwargs(steal_entry=True))

    assert result["outcome"] == "NO_MEET"
    assert result.get("steal_meet_rejected") is True


def test_neutral_stop_decision_optimal_pass():
    off_lineup = _lineup("off")
    off_starts = {
        "PG": {"x": 75.0, "y": 25.0},
        "SG": {"x": 88.0, "y": 25.0},
        "SF": {"x": 50.0, "y": 25.0},
        "PF": {"x": 50.0, "y": 10.0},
        "C": {"x": 50.0, "y": 40.0},
    }
    meet = {"x": 75.0, "y": 25.0}
    stopper = _lineup("def")["SF"]

    decision = resolve_fb_stop_decision(
        off_lineup["PG"],
        meet,
        stopper,
        off_lineup,
        off_starts,
        _team(),
        MagicMock(),
        is_away_offense=False,
        bh_pos="PG",
        read_score=250,
    )

    assert decision["action"] == "pass"
    assert decision["receiver_id"] == off_lineup["SG"].player_id


def test_neutral_stop_decision_safe_read_forces_hco():
    off_lineup = _lineup("off")
    off_starts = _flat_starts(off_lineup, 88.0, 25.0)
    meet = {"x": 88.0, "y": 25.0}
    shot_manager = MagicMock()
    shot_manager.calculate_shot_score.return_value = (500, 400, 0, False, None, 0)

    decision = resolve_fb_stop_decision(
        off_lineup["PG"],
        meet,
        _lineup("def")["SF"],
        off_lineup,
        off_starts,
        _team(shot_threshold=100),
        shot_manager,
        is_away_offense=False,
        bh_pos="PG",
        read_score=150,
    )

    assert decision["action"] == "HCO"
    assert decision["action_source"] == "safe_read"


def test_neutral_resolver_wires_stop_decision(monkeypatch):
    meet = {"x": 75, "y": 25}

    monkeypatch.setattr(
        "BackEnd.engine.fb_drive_resolution.best_cutoff_on_drive",
        lambda *a, **k: ("SF", meet),
    )
    monkeypatch.setattr(
        "BackEnd.engine.fb_drive_resolution.resolve_cutoff_contest",
        lambda *a, **k: ("NEUTRAL", 0.5, None),
    )
    monkeypatch.setattr(
        "BackEnd.engine.fb_drive_resolution.calculate_charge",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "BackEnd.engine.fb_drive_resolution.resolve_fb_stop_decision",
        lambda *a, **k: {"action": "HCO", "contested": False},
    )

    result = resolve_fb_drive_step(**_drive_kwargs(shot_manager=MagicMock()))

    assert result["outcome"] == "NEUTRAL"
    assert result["stop_decision"]["action"] == "HCO"
    assert result["advance_trigger"] == "meet_reached"
