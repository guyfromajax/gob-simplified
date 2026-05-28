"""HCO entry chain → skeleton step 0 ball ownership seam."""

from BackEnd.engine.skeleton_step_emitter import build_skeleton_animation_steps
from BackEnd.models.game_manager import GameManager
from BackEnd.models.player import Player


def _build_game():
    gm = GameManager("Home", "Away")
    positions = ["PG", "SG", "SF", "PF", "C"]
    for team in [gm.home_team, gm.away_team]:
        lineup = {}
        for i, pos in enumerate(positions):
            pdata = {
                "_id": f"{team.name}_{pos}",
                "first_name": team.name,
                "last_name": pos,
                "team": team.name,
                "attributes": {
                    k: 50
                    for k in [
                        "SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST",
                        "ND", "IQ", "FT", "NG",
                    ]
                },
            }
            lineup[pos] = Player(pdata)
        team.lineup = lineup
    gm.offense_team = gm.home_team
    gm.defense_team = gm.away_team
    gm.game_state["time_remaining"] = 600
    gm.game_state["shot_clock_remaining"] = 24
    return gm


def _coord_map_for_all_players(game, x, y):
    coords = {}
    for team in (game.offense_team, game.defense_team):
        for player in team.lineup.values():
            coords[str(player.player_id)] = {"x": float(x), "y": float(y)}
    return coords


def _animations_from_coords(step0_coords, step1_coords):
    animations = []
    for pid, s0 in step0_coords.items():
        s1 = step1_coords.get(pid, s0)
        animations.append(
            {
                "playerId": pid,
                "movement": [
                    {"coords": dict(s0)},
                    {"coords": dict(s1)},
                ],
            }
        )
    return animations


def test_hco_skeleton_step0_inherits_prepended_ball_owner():
    """After Handoff→Walk Up, skeleton step 0 must not re-stamp PG on a pass play."""
    game = _build_game()
    pg_id = str(game.offense_team.lineup["PG"].player_id)
    sg_id = str(game.offense_team.lineup["SG"].player_id)

    # Prior turn ended with PG in the backcourt (typical post-inbound).
    prior_coords = _coord_map_for_all_players(game, 50, 25)
    game.turns = [
        {
            "result_type": "BASELINE_INBOUND",
            "current_turn": "BASELINE_INBOUND",
            "final_ball_handler_id": pg_id,
            "final_coords": prior_coords,
        }
    ]

    step0_coords = dict(prior_coords)
    step1_coords = _coord_map_for_all_players(game, 55, 28)
    animations = _animations_from_coords(step0_coords, step1_coords)

    skeleton_steps = [
        {
            "pos_actions": {
                "PG": {"action": "pass", "location": "key"},
                "SG": {"action": "receive", "location": "wing"},
                "SF": {"action": "cut", "location": "corner"},
                "PF": {"action": "cut", "location": "block"},
                "C": {"action": "cut", "location": "block"},
            }
        },
        {
            "pos_actions": {
                "SG": {"action": "handle_ball", "location": "wing"},
                "PG": {"action": "cut", "location": "key"},
                "SF": {"action": "cut", "location": "corner"},
                "PF": {"action": "cut", "location": "block"},
                "C": {"action": "cut", "location": "block"},
            }
        },
    ]

    turn_result = {
        "current_turn": "HCO",
        "result_type": "MAKE",
        "skeleton": {"steps": skeleton_steps},
        "animations": animations,
        "step_clock_seconds": [1.0, 1.0],
        "roles": {
            "ball_handler": game.offense_team.lineup["SG"],
            "shooter": game.offense_team.lineup["SG"],
        },
    }

    steps = build_skeleton_animation_steps(turn_result, game, turn_type="HCO")
    assert steps, "expected schema steps from HCO emitter"

    prepended = [s for s in steps if (s.get("start") or {}).get("advance_trigger", {}).get("metadata", {}).get("reason", "").startswith("hco_entry")]
    assert prepended, "expected HCO entry handoff/walk-up prepended steps"

    skeleton_step0 = steps[len(prepended)]
    start_ball = (skeleton_step0.get("start") or {}).get("ball") or {}

    assert start_ball.get("owner_player_id") == sg_id
    assert skeleton_step0.get("start", {}).get("ball_motion_style") != "pass"
