"""carry_ball_coord_continuity — read of an existing write, no invention."""
from BackEnd.utils.animation_step_helpers import carry_ball_coord_continuity


def _step(idx_next, start_ball, end_ball):
    return {
        "start": {"coords": {}, "ball": start_ball, "advance_trigger": {}},
        "end": {
            "coords": {},
            "ball": end_ball,
            "next": {"kind": "next_step", "index": idx_next},
        },
    }


def test_carries_prior_turn_final_ball_coords_onto_step0():
    steps = [
        _step(1, {"owner_player_id": ""}, {"owner_player_id": ""}),
        {
            "start": {"coords": {}, "ball": {"owner_player_id": "p1"}},
            "end": {
                "coords": {},
                "ball": {"owner_player_id": "p1"},
                "next": {"kind": "turn_stop"},
            },
        },
    ]
    n = carry_ball_coord_continuity(
        steps, prior_final_ball_coords={"x": 12.0, "y": 28.0}, context="HCO/MISS"
    )
    assert n == 2
    assert steps[0]["start"]["ball"] == {"coords": {"x": 12.0, "y": 28.0}}
    assert steps[0]["end"]["ball"] == {"coords": {"x": 12.0, "y": 28.0}}
    assert "owner_player_id" not in steps[0]["start"]["ball"]


def test_does_not_fill_when_next_step_already_loose():
    steps = [
        _step(1, {"owner_player_id": ""}, {"owner_player_id": ""}),
        {
            "start": {"coords": {}, "ball": {"coords": {"x": 17.0, "y": 25.0}}},
            "end": {
                "coords": {},
                "ball": {"coords": {"x": 17.0, "y": 25.0}},
                "next": {"kind": "turn_stop"},
            },
        },
    ]
    n = carry_ball_coord_continuity(
        steps, prior_final_ball_coords={"x": 21.0, "y": 21.0}
    )
    assert n == 0
    assert steps[0]["start"]["ball"] == {"owner_player_id": ""}


def test_authored_coord_survives_attached_step():
    steps = [
        {
            "start": {
                "coords": {},
                "ball": {"current_coords": {"x": 48.0, "y": 29.0}},
            },
            "end": {
                "coords": {},
                "ball": {"owner_player_id": "p1"},
                "next": {"kind": "next_step", "index": 1},
            },
        },
        _step(2, {"owner_player_id": ""}, {"owner_player_id": ""}),
        {
            "start": {"coords": {}, "ball": {"owner_player_id": "p2"}},
            "end": {
                "coords": {},
                "ball": {"owner_player_id": "p2"},
                "next": {"kind": "turn_stop"},
            },
        },
    ]
    n = carry_ball_coord_continuity(steps)
    assert n == 2
    assert steps[1]["start"]["ball"]["coords"] == {"x": 48.0, "y": 29.0}


def test_does_not_invent_after_attached_owner():
    steps = [
        {
            "start": {"coords": {}, "ball": {"owner_player_id": "p1"}},
            "end": {
                "coords": {},
                "ball": {"owner_player_id": "p1"},
                "next": {"kind": "next_step", "index": 1},
            },
        },
        _step(2, {"owner_player_id": ""}, {"owner_player_id": ""}),
        {
            "start": {"coords": {}, "ball": {"owner_player_id": "p2"}},
            "end": {
                "coords": {},
                "ball": {"owner_player_id": "p2"},
                "next": {"kind": "turn_stop"},
            },
        },
    ]
    n = carry_ball_coord_continuity(
        steps, prior_final_ball_coords={"x": 50.0, "y": 25.0}
    )
    assert n == 0
    assert steps[1]["start"]["ball"] == {"owner_player_id": ""}


def test_same_turn_authored_coord_then_no_seam_on_next_unplaced_step():
    steps = [
        {
            "start": {
                "coords": {},
                "ball": {"current_coords": {"x": 48.0, "y": 29.0}},
            },
            "end": {
                "coords": {},
                "ball": {"owner_player_id": "p1"},
                "next": {"kind": "next_step", "index": 1},
            },
        },
        _step(2, {"owner_player_id": ""}, {"owner_player_id": ""}),
        _step(3, {"owner_player_id": ""}, {"owner_player_id": ""}),
        {
            "start": {"coords": {}, "ball": {"owner_player_id": "p2"}},
            "end": {
                "coords": {},
                "ball": {"owner_player_id": "p2"},
                "next": {"kind": "turn_stop"},
            },
        },
    ]
    steps[2]["end"]["next"] = {"kind": "turn_stop"}
    n = carry_ball_coord_continuity(steps)
    assert n == 2
    assert steps[1]["start"]["ball"]["coords"] == {"x": 48.0, "y": 29.0}
    assert steps[1]["end"]["ball"]["coords"] == {"x": 48.0, "y": 29.0}
    # next unplaced step would open a seam-static pair — left unplaced
    assert steps[2]["start"]["ball"] == {"owner_player_id": ""}
    assert steps[2]["end"]["ball"] == {"owner_player_id": ""}
