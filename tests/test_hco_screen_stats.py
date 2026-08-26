from BackEnd.engine.phase_resolution import record_hco_screen_stats
from BackEnd.models.shot_manager import ShotManager
from tests.test_utils import build_mock_game


class RecordingPlayer:
    def __init__(self):
        self.recorded = []

    def record_stat(self, stat):
        self.recorded.append(stat)


def _skeleton(*step_actions):
    return {
        "steps": [
            {
                "pos_actions": {
                    pos: {"action": action} for pos, action in actions.items()
                },
                "events": [],
            }
            for actions in step_actions
        ]
    }


def test_screen_actions_credit_the_players_who_screened():
    pg = RecordingPlayer()
    pf = RecordingPlayer()
    c = RecordingPlayer()
    off_lineup = {"PG": pg, "PF": pf, "C": c}

    record_hco_screen_stats(
        _skeleton(
            {"PG": "screen", "SG": "handle_ball", "C": "get_open"},
            {"PG": "stationary", "C": "screen"},
        ),
        off_lineup,
        shot_made=False,
    )

    assert pg.recorded == ["SCR_A"]
    assert c.recorded == ["SCR_A"]
    assert pf.recorded == []


def test_made_shot_credits_success_for_each_screen_attempt():
    pg = RecordingPlayer()
    sf = RecordingPlayer()
    off_lineup = {"PG": pg, "SF": sf}

    record_hco_screen_stats(
        _skeleton(
            {"PG": "screen"},
            {"SF": "screen"},
            {"PG": "screen"},
        ),
        off_lineup,
        shot_made=True,
    )

    assert pg.recorded == ["SCR_A", "SCR_S", "SCR_A", "SCR_S"]
    assert sf.recorded == ["SCR_A", "SCR_S"]


def test_missed_or_non_shot_does_not_credit_success():
    pf = RecordingPlayer()

    record_hco_screen_stats(
        _skeleton({"PF": "screen"}),
        {"PF": pf},
        shot_made=False,
    )

    assert pf.recorded == ["SCR_A"]


def test_empty_events_do_not_invent_a_pf_screener():
    pf = RecordingPlayer()
    sg = RecordingPlayer()

    record_hco_screen_stats(
        {
            "steps": [
                {
                    "pos_actions": {"SG": {"action": "shoot"}, "PF": {"action": "stationary"}},
                    "events": [],
                }
            ]
        },
        {"SG": sg, "PF": pf},
        shot_made=True,
    )

    assert pf.recorded == []
    assert sg.recorded == []


def test_missing_lineup_slot_is_skipped():
    record_hco_screen_stats(
        _skeleton({"PG": "screen"}),
        {},
        shot_made=True,
    )


def test_shot_score_no_longer_writes_screen_stats():
    game = build_mock_game()
    shot_manager = ShotManager(game)
    shooter = game.offense_team.lineup["PG"]
    screener = game.offense_team.lineup["PF"]
    defender = game.defense_team.lineup["PG"]

    shot_manager.calculate_shot_score(
        shooter, None, screener, defender, "inside", "man", False, True
    )

    assert screener.stats["game"]["SCR_A"] == 0
    assert screener.stats["game"]["SCR_S"] == 0
