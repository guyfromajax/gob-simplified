"""Guards for unrendered tails (item 42) and ball-owner seams (UESS §8.4 / item 47).

Both are log-and-assert. They do not rewrite steps or owner ids. A silent
repair is the item 41 failure mode and is the thing these tests exist to
refuse: the poison must still be *visible* after the guard runs.
"""

from unittest.mock import MagicMock

import pytest

from BackEnd.utils.animation_step_helpers import (
    announce_ball_owner_seam,
    announce_unrendered_tail,
    attached_owner_id,
    build_final_ball_coords,
    build_final_ball_handler_id,
    last_rendered_step_index,
    rendered_step_indices,
)
from BackEnd.utils.shared import sync_lineup_coords_from_turn


def _coord(x, y):
    return {"x": float(x), "y": float(y)}


def _step(start_owner, end_owner, *, next_kind="next_step", next_index=None,
          start_coords=None, end_coords=None, flourish=None):
    start = {
        "coords": start_coords or {},
        "ball": {"owner_player_id": start_owner} if start_owner is not None else {},
    }
    if flourish is not None:
        start["flourish"] = flourish
    end = {
        "coords": end_coords or {},
        "ball": {"owner_player_id": end_owner} if end_owner is not None else {},
        "next": {"kind": next_kind, **({"index": next_index} if next_index is not None else {})},
    }
    if next_kind == "turn_stop":
        end["next"] = {"kind": "turn_stop", "event": "DEAD_BALL_TURNOVER"}
    return {"start": start, "end": end}


def _player(pid, x, y):
    p = MagicMock()
    p.player_id = pid
    p.coords = {"x": float(x), "y": float(y)}
    return p


def _game(pids):
    gm = MagicMock()
    gm.home_team = MagicMock()
    gm.away_team = MagicMock()
    gm.home_team.lineup = {f"P{i}": _player(pid, 10.0 + i, 10.0) for i, pid in enumerate(pids)}
    gm.away_team.lineup = {}
    gm.away_team.team_id = "AWAY"
    gm.offense_team = gm.home_team
    return gm


class TestRenderedWalk:
    def test_stops_at_turn_stop_and_ignores_the_tail(self):
        steps = [
            _step("A", "A", next_kind="next_step", next_index=1),
            _step("A", "A", next_kind="turn_stop"),
            _step("GHOST", "GHOST", next_kind="next_step", next_index=3),
        ]
        assert rendered_step_indices(steps) == [0, 1]
        assert last_rendered_step_index(steps) == 1

    def test_follows_an_index_pointer_not_array_order(self):
        steps = [
            _step("A", "A", next_kind="next_step", next_index=2),
            _step("SKIP", "SKIP", next_kind="turn_stop"),
            _step("A", "A", next_kind="turn_stop"),
        ]
        assert rendered_step_indices(steps) == [0, 2]
        assert last_rendered_step_index(steps) == 2


class TestUnrenderedTail:
    def test_clean_chain_is_silent(self, caplog):
        steps = [
            _step("A", "A", next_kind="next_step", next_index=1),
            _step("A", "A", next_kind="turn_stop"),
        ]
        assert announce_unrendered_tail(steps, context="unit") == 0
        assert "[UESS UNRENDERED]" not in caplog.text

    def test_poison_appended_after_turn_stop_is_named(self, caplog):
        """POISON — the item 41 shape: a ghost step after the terminal turn_stop."""
        drawn = {"p": _coord(50, 25)}
        ghost = {"p": _coord(62, 25)}
        steps = [
            _step("A", "A", next_kind="turn_stop", start_coords=drawn, end_coords=drawn),
            _step("A", "A", next_kind="next_step", start_coords=ghost, end_coords=ghost),
        ]
        assert announce_unrendered_tail(steps, context="HCO/DEAD BALL") == 1
        assert "[UESS UNRENDERED] emitter produced steps after turn_stop HCO/DEAD BALL" in caplog.text
        assert "last_rendered=0" in caplog.text
        assert "array_tail=1" in caplog.text
        assert "worst_delta=12.00 ft" in caplog.text

    def test_poison_does_not_delete_the_tail(self):
        steps = [
            _step("A", "A", next_kind="turn_stop"),
            _step("GHOST", "GHOST", next_kind="next_step"),
        ]
        announce_unrendered_tail(steps)
        assert len(steps) == 2
        assert attached_owner_id(steps[1]["start"]["ball"]) == "GHOST"


class TestSyncReadsDrawable:
    def test_sync_reads_the_drawn_step_not_the_ghost(self, caplog):
        gm = _game(["p"])
        drawn = {"p": _coord(50, 25)}
        ghost = {"p": _coord(62, 25)}
        turn = {
            "current_turn": "FAST_BREAK",
            "result_type": "MAKE",
            "animation_steps": [
                _step("A", "A", next_kind="turn_stop", start_coords=drawn, end_coords=drawn),
                _step("A", "A", next_kind="next_step", start_coords=ghost, end_coords=ghost),
            ],
        }
        sync_lineup_coords_from_turn(gm, turn)
        assert gm.home_team.lineup["P0"].coords == {"x": 50.0, "y": 25.0}
        assert "[UESS UNRENDERED] coord sync skipped undrawn tail FAST_BREAK/MAKE" in caplog.text
        assert "last_rendered=0" in caplog.text
        assert "worst_delta=12.00 ft" in caplog.text

    def test_final_ball_helpers_read_drawable(self, caplog):
        steps = [
            {
                "start": {"ball": {"owner_player_id": "drawn"}, "coords": {}},
                "end": {
                    "ball": {"owner_player_id": "drawn"},
                    "coords": {"drawn": _coord(10, 10)},
                    "next": {"kind": "turn_stop", "event": "MAKE"},
                },
            },
            {
                "start": {"ball": {"owner_player_id": "ghost"}, "coords": {}},
                "end": {
                    "ball": {"owner_player_id": "ghost"},
                    "coords": {"ghost": _coord(99, 99)},
                    "next": {"kind": "next_step", "index": 2},
                },
            },
        ]
        turn = {"animation_steps": steps, "result_type": "MAKE"}
        assert build_final_ball_handler_id(turn) == "drawn"
        assert build_final_ball_coords(turn) == {"x": 10.0, "y": 10.0}
        assert "final_ball_handler_id skipped undrawn tail" in caplog.text
        assert "final_ball_coords skipped undrawn tail" in caplog.text


class TestBallOwnerSeam:
    def test_same_owner_across_the_seam_is_silent(self, caplog):
        steps = [
            _step("A", "A", next_kind="next_step", next_index=1),
            _step("A", "A", next_kind="turn_stop"),
        ]
        assert announce_ball_owner_seam(steps, family="HCO/MAKE") == 0
        assert "[UESS 8.4]" not in caplog.text

    def test_within_step_pass_is_accounted_for(self, caplog):
        """start A → end B on ONE step is the authored pass. Not a seam swap."""
        steps = [
            _step("A", "B", next_kind="next_step", next_index=1),
            _step("B", "B", next_kind="turn_stop"),
        ]
        assert announce_ball_owner_seam(steps, family="HCO/MAKE") == 0
        assert "[UESS 8.4]" not in caplog.text

    def test_item_47_poison_names_step_owners_and_family(self, caplog):
        """POISON — item 47: fumble beat starts already attached to a new man."""
        steps = [
            _step("SF", "SF", next_kind="next_step", next_index=1),
            _step(
                "PG",
                "PG",
                next_kind="turn_stop",
                flourish={"PG": {"kind": "fumble"}},
            ),
        ]
        assert announce_ball_owner_seam(steps, context="HCO/DEAD BALL", family="HCO/DEAD BALL") == 1
        msg = caplog.text
        assert "[UESS 8.4] unaccounted owner change HCO/DEAD BALL" in msg
        assert "step 0->1" in msg
        assert "end_owner=SF" in msg
        assert "start_owner=PG" in msg
        assert "family=HCO/DEAD BALL" in msg
        assert "beat=fumble" in msg

    def test_poison_does_not_rewrite_the_owner(self):
        steps = [
            _step("SF", "SF", next_kind="next_step", next_index=1),
            _step("PG", "PG", next_kind="turn_stop"),
        ]
        announce_ball_owner_seam(steps, family="HCO/DEAD BALL")
        assert attached_owner_id(steps[1]["start"]["ball"]) == "PG"
        assert attached_owner_id(steps[0]["end"]["ball"]) == "SF"

    def test_loose_to_attached_is_not_this_invariant(self, caplog):
        """Key absent → attached is a capture, not an attached-owner swap."""
        steps = [
            {
                "start": {"ball": {"coords": _coord(50, 25)}},
                "end": {
                    "ball": {"coords": _coord(50, 25)},
                    "next": {"kind": "next_step", "index": 1},
                },
            },
            _step("PG", "PG", next_kind="turn_stop"),
        ]
        assert announce_ball_owner_seam(steps, family="DREB/DREB") == 0
        assert "[UESS 8.4]" not in caplog.text

    def test_empty_string_owner_is_not_collapsed_to_none(self):
        assert attached_owner_id({"owner_player_id": ""}) == ""
        assert attached_owner_id({}) is None
        assert attached_owner_id(None) is None
