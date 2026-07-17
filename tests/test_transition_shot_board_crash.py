"""Unit tests for FB/HCT/FCP transition shot board-crash overlays."""

from __future__ import annotations

from BackEnd.constants import CONTEST_EUCLIDEAN_RADIUS, HOME_RIM_COORDS
from BackEnd.utils.transition_shot_board_crash import (
    compute_fb_neutral_board_crash_hold_ids,
    maybe_stamp_transition_shot_board_crash_overlays,
    sample_coord_within_basket_radius,
)


class _P:
    def __init__(self, pid):
        self.player_id = pid


def _lineup(*pids):
    # Position keys unused by the helper; values are players.
    return {f"P{i}": _P(pid) for i, pid in enumerate(pids)}


def test_sample_coord_within_basket_radius_stays_in_disk():
    basket = {"x": 91.0, "y": 25.0}
    for seed in range(20):
        class _R:
            def __init__(self, s):
                self._i = s

            def uniform(self, a, b):
                # Deterministic walk across the square.
                self._i += 1
                t = (self._i % 17) / 16.0
                return a + (b - a) * t

        coord = sample_coord_within_basket_radius(
            basket, radius=float(CONTEST_EUCLIDEAN_RADIUS), rng=_R(seed)
        )
        dist = (
            (coord["x"] - basket["x"]) ** 2 + (coord["y"] - basket["y"]) ** 2
        ) ** 0.5
        assert dist <= float(CONTEST_EUCLIDEAN_RADIUS) + 1e-6


def test_hco_turn_is_noop():
    turn = {
        "current_turn": "HCO",
        "result_type": "MISS",
        "shooter_id": "1",
    }
    shoot = {
        "start": {
            "coords": {
                "1": {"x": 80.0, "y": 25.0},
                "2": {"x": 40.0, "y": 25.0},
            },
            "destination": {
                "1": {"x": 80.0, "y": 25.0},
                "2": None,
            },
        },
        "end": {"coords": {}},
    }
    maybe_stamp_transition_shot_board_crash_overlays(
        turn, shoot, _lineup("1", "2"), _lineup("3"), away_offense=False
    )
    assert "offense_rebounder_coords" not in turn
    assert "defense_rebounder_coords" not in turn


def test_hct_stamps_idle_far_offense_and_defense():
    turn = {
        "current_turn": "HCT",
        "result_type": "MISS",
        "shooter_id": "1",
        "shot_defender_id": "10",
    }
    shoot = {
        "start": {
            "coords": {
                "1": {"x": 85.0, "y": 25.0},  # shooter
                "2": {"x": 40.0, "y": 20.0},  # idle far O
                "10": {"x": 88.0, "y": 25.0},  # shot D — hold
                "11": {"x": 35.0, "y": 30.0},  # idle far D
            },
            "destination": {
                "1": {"x": 85.0, "y": 25.0},
                "2": None,
                "10": {"x": 88.0, "y": 25.0},
                "11": None,
            },
        },
        "end": {"coords": {}},
    }
    maybe_stamp_transition_shot_board_crash_overlays(
        turn,
        shoot,
        _lineup("1", "2"),
        _lineup("10", "11"),
        away_offense=False,
        rng=random_module_stub(0.0),
    )
    off = turn.get("offense_rebounder_coords") or {}
    deff = turn.get("defense_rebounder_coords") or {}
    assert "2" in off
    assert "11" in deff
    assert "1" not in off and "1" not in deff
    assert "10" not in off and "10" not in deff
    basket = HOME_RIM_COORDS
    for coord in (off["2"], deff["11"]):
        dist = (
            (coord["x"] - basket["x"]) ** 2 + (coord["y"] - basket["y"]) ** 2
        ) ** 0.5
        assert dist <= float(CONTEST_EUCLIDEAN_RADIUS) + 1e-6


def test_continues_existing_shoot_destination():
    turn = {
        "current_turn": "FCP",
        "result_type": "MISS",
        "shooter_id": "1",
        "shot_defender_id": "10",
    }
    shoot = {
        "start": {
            "coords": {
                "1": {"x": 85.0, "y": 25.0},
                "2": {"x": 50.0, "y": 25.0},
                "10": {"x": 88.0, "y": 25.0},
            },
            "destination": {
                "1": {"x": 85.0, "y": 25.0},
                "2": {"x": 90.0, "y": 22.0},  # already crashing
                "10": {"x": 88.0, "y": 25.0},
            },
        },
        "end": {"coords": {}},
    }
    maybe_stamp_transition_shot_board_crash_overlays(
        turn, shoot, _lineup("1", "2"), _lineup("10"), away_offense=False
    )
    off = turn.get("offense_rebounder_coords") or {}
    assert off["2"] == {"x": 90.0, "y": 22.0}


def test_neutral_hold_includes_all_defense_and_leads_not_trailers():
    # Home offense: higher x = closer to basket → leads are 2 and 3.
    off_starts = {
        "1": {"x": 55.0, "y": 25.0},  # BH
        "2": {"x": 80.0, "y": 15.0},
        "3": {"x": 78.0, "y": 35.0},
        "4": {"x": 60.0, "y": 20.0},
        "5": {"x": 58.0, "y": 30.0},
    }
    def_starts = {
        "10": {"x": 70.0, "y": 25.0},
        "11": {"x": 72.0, "y": 20.0},
        "12": {"x": 74.0, "y": 30.0},
        "13": {"x": 50.0, "y": 15.0},
        "14": {"x": 48.0, "y": 35.0},
    }
    hold = compute_fb_neutral_board_crash_hold_ids(
        stealer_id="1",
        off_start_coords=off_starts,
        def_start_coords=def_starts,
        is_away_offense=False,
    )
    assert hold.issuperset({"10", "11", "12", "13", "14", "1", "2", "3"})
    assert "4" not in hold
    assert "5" not in hold


def test_fb_neutral_does_not_crash_help_defenders():
    turn = {
        "current_turn": "FAST_BREAK",
        "result_type": "MISS",
        "shooter_id": "1",
        "shot_defender_id": "10",
        "fb_drive_resolution": {"outcome": "NEUTRAL"},
    }
    shoot = {
        "start": {
            "coords": {
                "1": {"x": 70.0, "y": 25.0},
                "2": {"x": 80.0, "y": 15.0},  # lead
                "3": {"x": 78.0, "y": 35.0},  # lead
                "4": {"x": 40.0, "y": 20.0},  # trailer — may crash
                "5": {"x": 42.0, "y": 30.0},  # trailer
                "10": {"x": 68.0, "y": 25.0},
                "11": {"x": 75.0, "y": 15.0},
                "12": {"x": 74.0, "y": 35.0},
                "13": {"x": 30.0, "y": 10.0},  # help-like far D — hold on NEUTRAL
                "14": {"x": 28.0, "y": 40.0},
            },
            "destination": {str(i): None for i in (1, 2, 3, 4, 5, 10, 11, 12, 13, 14)},
        },
        "end": {"coords": {}},
    }
    maybe_stamp_transition_shot_board_crash_overlays(
        turn,
        shoot,
        _lineup("1", "2", "3", "4", "5"),
        _lineup("10", "11", "12", "13", "14"),
        away_offense=False,
        rng=random_module_stub(0.0),
    )
    off = turn.get("offense_rebounder_coords") or {}
    deff = turn.get("defense_rebounder_coords") or {}
    assert "4" in off or "5" in off
    assert "13" not in deff
    assert "14" not in deff
    assert "10" not in deff


class random_module_stub:
    """Minimal rng: always returns the low end of uniform → near basket center."""

    def __init__(self, _seed=0.0):
        pass

    def uniform(self, a, b):
        return a if a == b else 0.0
