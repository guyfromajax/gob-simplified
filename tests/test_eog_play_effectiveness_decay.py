"""EOG offensive play CMD decay when 4*usage_int < success_rate; defense from used share."""

import pytest

from BackEnd.models.training_execution_v2 import (
    build_eog_defensive_effectiveness_decay_ftd_updates,
    build_eog_offensive_play_effectiveness_decay_ftd_updates,
)
from BackEnd.utils.defense_identity import canonical_scouting_defense_key


def test_decay_truncates_percent_like_user_example():
    """When 4*usage_int < success_rate_pct, decay = usage_int (here p1: 20 off). p2: high share fails condition."""
    game_plays = {
        "p1": {
            "name": "3-2 Motion",
            "play_type": "motion",
            "game_stats": {"times_run": 204, "successes": 164},
        },
        "p2": {
            "name": "Other",
            "play_type": "motion",
            "game_stats": {"times_run": 796, "successes": 400},
        },
    }
    ftd_plays = {
        "p1": {"effectiveness": 80},
        "p2": {"effectiveness": 80},
    }
    out = build_eog_offensive_play_effectiveness_decay_ftd_updates(game_plays, ftd_plays)
    # usage_int=20, sr=164/204*100≈80.39, 4*20=80 < 80.39 → decay 20
    assert out["plays.p1.effectiveness"] == 60
    # usage_int=79, sr≈50.25, 4*79=316 < 50.25 false → no decay
    assert "plays.p2.effectiveness" not in out


def test_no_offensive_decay_when_four_times_usage_not_below_success_rate():
    game_plays = {
        "p1": {
            "name": "A",
            "play_type": "motion",
            "game_stats": {"times_run": 100, "successes": 30},
        },
    }
    ftd_plays = {"p1": {"effectiveness": 80}}
    out = build_eog_offensive_play_effectiveness_decay_ftd_updates(game_plays, ftd_plays)
    assert out == {}


def test_zero_total_times_run_no_change():
    game_plays = {
        "p1": {"name": "A", "play_type": "motion", "game_stats": {"times_run": 0}},
    }
    ftd_plays = {"p1": {"effectiveness": 50}}
    assert build_eog_offensive_play_effectiveness_decay_ftd_updates(game_plays, ftd_plays) == {}


def test_skips_missing_ftd_row():
    """50/50 share gives usage 50; 4*200 < sr impossible, so use 10/90; need sr > 40% for usage 10."""
    game_plays = {
        "p1": {
            "name": "A",
            "play_type": "motion",
            "game_stats": {"times_run": 10, "successes": 5},
        },
        "p2": {
            "name": "B",
            "play_type": "motion",
            "game_stats": {"times_run": 90, "successes": 50},
        },
    }
    ftd_plays = {"p1": {"effectiveness": 40}}
    out = build_eog_offensive_play_effectiveness_decay_ftd_updates(game_plays, ftd_plays)
    assert out["plays.p1.effectiveness"] == 30  # usage 10, sr 50%, 40<50 → decay 10
    assert "plays.p2.effectiveness" not in out


def test_defense_decay_matches_offense_math():
    game_scouting = {
        "defense": {
            "man": {"game_stats": {"used": 25}},
            "2-3-zone": {"game_stats": {"used": 75}},
        }
    }
    ftd_sd = {
        "defense": {
            "man": {"effectiveness": 80},
            "2-3-zone": {"effectiveness": 80},
        }
    }
    out = build_eog_defensive_effectiveness_decay_ftd_updates(game_scouting, ftd_sd)
    assert out["scouting_data.defense.man.effectiveness"] == 55  # 80 - int(25) = 55
    assert out["scouting_data.defense.2-3-zone.effectiveness"] == 5  # 80 - int(75) = 5


def test_defense_decay_zero_total_used_no_change():
    game_scouting = {"defense": {"man": {"game_stats": {"used": 0}}}}
    ftd_sd = {"defense": {"man": {"effectiveness": 50}}}
    assert build_eog_defensive_effectiveness_decay_ftd_updates(game_scouting, ftd_sd) == {}


@pytest.mark.skipif(
    canonical_scouting_defense_key("Man") is None,
    reason="defense identity cache not loaded (no DB / defenses not seeded)",
)
def test_defense_decay_resolves_legacy_game_key_to_canonical_ftd():
    game_scouting = {"defense": {"Man": {"game_stats": {"used": 100}}}}
    ftd_sd = {"defense": {"man": {"effectiveness": 60}}}
    out = build_eog_defensive_effectiveness_decay_ftd_updates(game_scouting, ftd_sd)
    assert out["scouting_data.defense.man.effectiveness"] == 0  # 60 - 100 clamped


def test_defense_decay_when_game_key_matches_ftd_row():
    game_scouting = {"defense": {"man": {"game_stats": {"used": 100}}}}
    ftd_sd = {"defense": {"man": {"effectiveness": 60}}}
    out = build_eog_defensive_effectiveness_decay_ftd_updates(game_scouting, ftd_sd)
    assert out["scouting_data.defense.man.effectiveness"] == 0
