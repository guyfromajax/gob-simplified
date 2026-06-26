"""Final Turn entry-pass step chain — no self-loop on ``next`` pointers."""

from types import SimpleNamespace

from BackEnd.engine.skeleton_step_emitter import (
    _append_final_turn_entry_pass_if_needed,
    build_skeleton_animation_steps,
)

POSITIONS = ("PG", "SG", "SF", "PF", "C")


def _coords_map(prefix):
    return {f"{prefix}_{p}": {"x": 50.0 + i, "y": 25.0} for i, p in enumerate(POSITIONS)}


def test_final_turn_entry_pass_next_does_not_self_loop():
    """Inserted entry pass must advance to skeleton step 1 (index 2), not index 1."""
    off_lineup = {
        p: SimpleNamespace(player_id=f"h_{p}", attributes={"AG": 50})
        for p in POSITIONS
    }
    def_lineup = {
        p: SimpleNamespace(player_id=f"a_{p}", attributes={})
        for p in POSITIONS
    }
    steps = [
        {
            "start": {"coords": _coords_map("h")},
            "end": {
                "coords": _coords_map("h"),
                "time_elapsed": 17.0,
            },
        }
    ]
    prior_turn = {"final_ball_handler_id": "h_PG", "result_type": "SIDE_INBOUND"}
    skeleton = {
        "steps": [
            {
                "timestamp": 0,
                "pos_actions": {
                    "SG": {"action": "handle_ball", "location": "key"},
                    **{
                        p: {"action": "stand", "location": "key"}
                        for p in POSITIONS
                        if p != "SG"
                    },
                },
            },
            {
                "timestamp": 300,
                "pos_actions": {
                    "SG": {"action": "pass", "location": "wing"},
                    "PF": {"action": "receive", "location": "wing"},
                },
            },
        ]
    }
    turn = {"final_turn": True, "result_type": "MISS", "skeleton": skeleton}

    _append_final_turn_entry_pass_if_needed(
        steps=steps,
        turn_result=turn,
        prior_turn=prior_turn,
        skeleton_steps=skeleton["steps"],
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        clock_remaining_at_turn_start=21.0,
        shot_clock_remaining_at_turn_start=14.0,
        elapsed_so_far=17.0,
    )

    assert len(steps) == 2
    entry = steps[1]
    assert entry["end"]["next"] == {"kind": "next_step", "index": 2}
    assert entry["start"]["advance_trigger"]["metadata"]["reason"] == "final_turn_entry_pass"


def test_final_turn_emitter_step_chain_indices_with_entry_pass(monkeypatch):
    """Alignment (0) → entry pass (1) → skeleton steps (2+) with monotonic next."""
    off_lineup = {
        p: SimpleNamespace(player_id=f"h_{p}", attributes={"AG": 50, "SH": 10})
        for p in POSITIONS
    }
    def_lineup = {
        p: SimpleNamespace(player_id=f"a_{p}", attributes={})
        for p in POSITIONS
    }
    home = SimpleNamespace(team_id="home", lineup=off_lineup)
    away = SimpleNamespace(team_id="away", lineup=def_lineup)

    prior_turn = {
        "final_ball_handler_id": "h_PG",
        "final_coords": _coords_map("h"),
        "result_type": "SIDE_INBOUND",
    }

    turn = {
        "final_turn": True,
        "result_type": "MISS",
        "roles": {
            "ball_handler": off_lineup["SG"],
            "shooter": off_lineup["PF"],
            "shooter_pos": "PF",
        },
        "skeleton": {
            "steps": [
                {
                    "timestamp": 0,
                    "pos_actions": {
                        p: {
                            "action": "handle_ball" if p == "SG" else "stand",
                            "location": "key",
                        }
                        for p in POSITIONS
                    },
                },
                {
                    "timestamp": 300,
                    "pos_actions": {
                        "SG": {"action": "pass", "location": "deep key"},
                        "PF": {"action": "receive", "location": "upper wing"},
                        **{
                            p: {"action": "stand", "location": "key"}
                            for p in POSITIONS
                            if p not in ("SG", "PF")
                        },
                    },
                },
                {
                    "timestamp": 600,
                    "pos_actions": {
                        "PF": {"action": "shoot", "location": "upper wing"},
                        **{
                            p: {"action": "stand", "location": "key"}
                            for p in POSITIONS
                            if p != "PF"
                        },
                    },
                },
            ]
        },
        "animations": [
            {
                "playerId": f"h_{p}",
                "movement": [
                    {"coords": {"x": 50, "y": 25}},
                    {"coords": {"x": 51, "y": 25}},
                    {"coords": {"x": 52, "y": 25}},
                    {"coords": {"x": 53, "y": 25}},
                ],
            }
            for p in POSITIONS
        ],
        "ball_bounce_x": 84,
        "ball_bounce_y": 28,
    }

    game = SimpleNamespace(
        offense_team=home,
        defense_team=away,
        away_team=away,
        home_team=home,
        game_state={"time_remaining": 21, "shot_clock_remaining": 14},
        turns=[prior_turn],
    )

    monkeypatch.setattr(
        "BackEnd.engine.skeleton_step_emitter._build_post_shot_sub_steps",
        lambda *args, **kwargs: None,
    )

    steps = build_skeleton_animation_steps(turn, game, turn_type="HCO")
    assert steps is not None
    assert len(steps) >= 4

    assert steps[0]["end"]["next"] == {"kind": "next_step", "index": 1}
    assert steps[1]["end"]["next"]["index"] == 2
    assert steps[1]["end"]["next"]["index"] != 1

    visited = []
    idx = 0
    while idx < len(steps) and len(visited) < 20:
        if idx in visited:
            raise AssertionError(f"cycle detected at index {idx}, visited={visited}")
        visited.append(idx)
        nxt = steps[idx]["end"].get("next") or {}
        if nxt.get("kind") != "next_step":
            break
        idx = int(nxt["index"])
