"""EOG offensive play CMD decay from playcall share (times_run)."""

from BackEnd.models.training_execution_v2 import build_eog_offensive_play_effectiveness_decay_ftd_updates


def test_decay_truncates_percent_like_user_example():
    """20.4% of calls → int 20 points off effectiveness."""
    game_plays = {
        "p1": {
            "name": "3-2 Motion",
            "play_type": "motion",
            "game_stats": {"times_run": 204},
        },
        "p2": {
            "name": "Other",
            "play_type": "motion",
            "game_stats": {"times_run": 796},
        },
    }
    ftd_plays = {
        "p1": {"effectiveness": 80},
        "p2": {"effectiveness": 80},
    }
    out = build_eog_offensive_play_effectiveness_decay_ftd_updates(game_plays, ftd_plays)
    assert out["plays.p1.effectiveness"] == 60  # 80 - int(20.4) = 60
    assert out["plays.p2.effectiveness"] == 1  # 80 - int(79.6) = 1


def test_zero_total_times_run_no_change():
    game_plays = {
        "p1": {"name": "A", "play_type": "motion", "game_stats": {"times_run": 0}},
    }
    ftd_plays = {"p1": {"effectiveness": 50}}
    assert build_eog_offensive_play_effectiveness_decay_ftd_updates(game_plays, ftd_plays) == {}


def test_skips_missing_ftd_row():
    game_plays = {
        "p1": {"name": "A", "play_type": "motion", "game_stats": {"times_run": 50}},
        "p2": {"name": "B", "play_type": "motion", "game_stats": {"times_run": 50}},
    }
    ftd_plays = {"p1": {"effectiveness": 40}}
    out = build_eog_offensive_play_effectiveness_decay_ftd_updates(game_plays, ftd_plays)
    assert "plays.p1.effectiveness" in out
    assert "plays.p2.effectiveness" not in out
