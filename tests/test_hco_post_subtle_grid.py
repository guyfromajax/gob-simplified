import copy
from types import SimpleNamespace

import pytest

from BackEnd.engine.phase_resolution import _hco_post_subtle_defender_row
from BackEnd.models.animator import Animator
from BackEnd.utils.sim_random import sim_rng


POSITIONS = ("PG", "SG", "SF", "PF", "C")


def _player(prefix, pos):
    return SimpleNamespace(player_id=f"{prefix}-{pos}")


def _game(defense_playcall, *, away_offense):
    home = SimpleNamespace(
        team_id="home",
        lineup={pos: _player("home", pos) for pos in POSITIONS},
        strategy_calls={"aggression_call": "normal"},
        is_user_team=False,
    )
    away = SimpleNamespace(
        team_id="away",
        lineup={pos: _player("away", pos) for pos in POSITIONS},
        strategy_calls={"aggression_call": "normal"},
        is_user_team=False,
    )
    offense, defense = (away, home) if away_offense else (home, away)
    return SimpleNamespace(
        home_team=home,
        away_team=away,
        offense_team=offense,
        defense_team=defense,
        game_state={
            "defense_playcall": defense_playcall,
            "_hco_defense_posture": "normal",
        },
    )


def _step(timestamp, coords, *, bh="PG", extra=None):
    actions = {}
    for pos, (x, y) in coords.items():
        actions[pos] = {
            "coords": {"x": x, "y": y},
            "action": "handle_ball" if pos == bh else "stationary",
        }
    step = {"timestamp": timestamp, "pos_actions": actions}
    if extra:
        step.update(extra)
    return step


@pytest.mark.parametrize("defense_playcall", ["Man", "2-3 Zone"])
@pytest.mark.parametrize("away_offense", [False, True])
def test_two_step_post_subtle_row_matches_full_prefix(
    defense_playcall,
    away_offense,
    monkeypatch,
):
    # Defender placement intentionally contains harmless jitter. Pin each draw
    # function to a stable value so this test compares coordinate algorithms,
    # independent of the number of discarded prefix draws.
    monkeypatch.setattr(sim_rng, "uniform", lambda low, high: (low + high) / 2)
    monkeypatch.setattr(sim_rng, "randint", lambda low, high: (low + high) // 2)
    monkeypatch.setattr(sim_rng, "choice", lambda values: values[0])

    game = _game(defense_playcall, away_offense=away_offense)
    off_lineup = game.offense_team.lineup
    def_lineup = game.defense_team.lineup

    start = {
        "PG": (78, 25),
        "SG": (72, 10),
        "SF": (72, 40),
        "PF": (84, 17),
        "C": (87, 30),
    }
    reached = {
        "PG": (76, 25),
        "SG": (70, 12),
        "SF": (73, 38),
        "PF": (83, 18),
        "C": (86, 29),
    }
    subtle = {
        "PG": (74, 24),
        "SG": (67, 14),
        "SF": (73, 38),
        "PF": (83, 18),
        "C": (86, 29),
    }
    steps = [
        _step(0, start),
        _step(
            800,
            reached,
            extra={
                "_defender_reads": {
                    pos: {"follows": pos != "SG", "margin": -80}
                    for pos in POSITIONS
                }
            },
        ),
        _step(
            950,
            subtle,
            extra={
                "_subtle_movement": {
                    "bh_pos": "PG",
                    "movers": ["PG", "SG"],
                    "defender_reads": {
                        "PG": True,
                        "SG": False,
                        "SF": True,
                        "PF": True,
                        "C": True,
                    },
                }
            },
        ),
    ]

    full_grid = Animator(game).compute_defender_grid(
        {"steps": copy.deepcopy(steps)},
        off_lineup,
        def_lineup,
    )
    expected = full_grid[2]
    reached_row = full_grid[1]
    expected_assignment = copy.deepcopy(
        getattr(game, "zone_defender_assignments_by_step", {}).get(2)
    )

    # Ensure the incremental call preserves unrelated assignment rows and remaps
    # its local row 1 onto the real output index.
    game.zone_defender_assignments_by_step = {
        0: {"sentinel": "keep"},
        7: {"existing": "keep"},
    }
    actual = _hco_post_subtle_defender_row(
        game,
        steps[1],
        steps[2],
        reached_row,
        off_lineup,
        def_lineup,
        output_step_index=7,
    )

    assert actual == expected
    assert game.zone_defender_assignments_by_step[0] == {"sentinel": "keep"}
    if defense_playcall == "2-3 Zone":
        assert game.zone_defender_assignments_by_step[7] == expected_assignment
    else:
        assert game.zone_defender_assignments_by_step[7] == {"existing": "keep"}
