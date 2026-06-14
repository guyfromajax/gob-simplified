from types import SimpleNamespace

from BackEnd.constants.fast_break_play_types import default_fast_break_plays
from BackEnd.engine.after_steal_fast_break import (
    _record_after_steal_fast_break_stats,
)


class _Player:
    def __init__(self, player_id):
        self.player_id = player_id
        self.stats = {}

    def record_stat(self, stat, amount=1):
        self.stats[stat] = self.stats.get(stat, 0) + amount


def _team():
    return SimpleNamespace(
        scouting_data={
            "offense": {
                "Fast_Break_Success": 0,
                "fast_break_plays": default_fast_break_plays(),
            },
            "defense": {
                "vs_Fast_Break": {"used": 1, "success": 0},
            },
        }
    )


def _game():
    return SimpleNamespace(
        offense_team=_team(),
        defense_team=_team(),
        game_state={},
    )


def test_after_steal_make_records_shared_player_and_team_stats():
    game = _game()
    stealer = _Player("stealer")
    defenders = [_Player(f"defender-{index}") for index in range(5)]

    _record_after_steal_fast_break_stats(
        game,
        {"result_type": "MAKE"},
        stealer,
        defenders,
    )

    assert stealer.stats == {"FB_A": 1, "FB_S": 1}
    assert game.offense_team.scouting_data["offense"]["Fast_Break_Success"] == 1
    assert (
        game.offense_team.scouting_data["offense"]["fast_break_plays"]["after_steal"]["S"]
        == 1
    )
    assert game.defense_team.scouting_data["defense"]["vs_Fast_Break"]["success"] == 0
    for defender in defenders:
        assert defender.stats == {"FB_A_D": 1, "FB_F_D": 1}


def test_after_steal_miss_records_shared_defensive_success_stats():
    game = _game()
    stealer = _Player("stealer")
    defenders = [_Player(f"defender-{index}") for index in range(5)]

    _record_after_steal_fast_break_stats(
        game,
        {"result_type": "MISS"},
        stealer,
        defenders,
    )

    assert stealer.stats == {"FB_A": 1}
    assert game.offense_team.scouting_data["offense"]["Fast_Break_Success"] == 0
    assert (
        game.offense_team.scouting_data["offense"]["fast_break_plays"]["after_steal"]["S"]
        == 0
    )
    assert game.defense_team.scouting_data["defense"]["vs_Fast_Break"]["success"] == 1
    for defender in defenders:
        assert defender.stats == {"FB_A_D": 1, "FB_F_D": 1}
