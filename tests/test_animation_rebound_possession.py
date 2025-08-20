import pytest
from tests.test_utils import build_mock_game
from BackEnd.models.animator import Animator


def extract_ball_owners(animations, step_count):
    owners = [None] * step_count
    for anim in animations:
        for idx, has in enumerate(anim.get("hasBallAtStep", [])):
            if idx < step_count and has:
                owners[idx] = anim["playerId"]
    return owners


@pytest.mark.parametrize("event_type", ["offReb", "defReb"])
def test_rebounder_holds_ball_final_step(event_type):
    game = build_mock_game()
    off_lineup = game.offense_team.lineup
    def_lineup = game.defense_team.lineup

    pg = off_lineup["PG"]
    pf = off_lineup["PF"]
    def_c = def_lineup["C"]

    rebounder = pf if event_type == "offReb" else def_c

    steps = [
        {"timestamp": 0, "pos_actions": {"PG": {"action": "handle_ball", "spot": "key"}}, "events": []},
        {
            "timestamp": 1,
            "pos_actions": {"PG": {"action": "shoot", "spot": "key"}},
            "events": [{"type": "shot", "by": "PG"}],
        },
        {
            "timestamp": 2,
            "pos_actions": {},
            "events": [
                {
                    "event_type": event_type,
                    "rebounderId": getattr(rebounder, "player_id", None),
                }
            ],
        },
    ]

    action_timeline = {
        pg: [(0, "handle_ball", "key"), (1, "shoot", "key")],
        pf: [
            (0, "move", "block"),
            (2, "rebound", "block"),
            (3, "hold", "block"),
            (4, "hold", "block"),
        ],
    }

    roles = {
        "steps": steps,
        "action_timeline": action_timeline,
        "shooter": pg,
        "ball_handler": pg,
    }

    animator = Animator(game)
    animations = animator.capture_halfcourt_animation(roles)

    max_len = max(len(tl) for tl in action_timeline.values())
    owners = extract_ball_owners(animations, max_len)
    assert owners[-1] == getattr(rebounder, "player_id", None)
