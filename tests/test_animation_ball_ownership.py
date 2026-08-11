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


def test_ball_ownership_transitions():
    game = build_mock_game()
    # Animation ownership is keyed by player_id.  The shared legacy mock leaves
    # every id as None, which collapses all five players into one identity and
    # makes the final lineup position appear to own every step.
    for team in (game.home_team, game.away_team):
        for pos, player in team.lineup.items():
            player.player_id = f"{team.name}-{pos}"

    tm = game.turn_manager
    roles = tm.assign_roles()
    animator = Animator(game)
    animations = animator.capture_halfcourt_animation(roles)
    steps_len = len(roles["steps"])
    owners = extract_ball_owners(animations, steps_len)

    offense_lineup = game.offense_team.lineup
    pos_by_id = {p.player_id: pos for pos, p in offense_lineup.items()}
    owner_positions = [pos_by_id.get(o) for o in owners]

    assert owner_positions[0] == "PG"
    # Expect at least one change away from PG
    assert "PF" in owner_positions or "C" in owner_positions
