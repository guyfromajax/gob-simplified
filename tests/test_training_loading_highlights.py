from BackEnd.utils.training_loading_highlights import build_training_loading_highlights


def test_sh_deltas_produce_shooting_copy():
    report = {
        "player_logs": {
            "Alex Smith": {"SH": 2, "SC": 1},
            "Jordan Lee": {"SH": -1},
            "No Shooter": {"SC": 3},
        }
    }
    lines = build_training_loading_highlights(report)
    assert "Alex Smith is shooting well in practice" in lines
    assert "Jordan Lee is shooting poorly in practice" in lines
    assert not any("No Shooter" in ln and "shooting" in ln for ln in lines)


def test_player_changes_alias():
    report = {"player_changes": {"Pat Jones": {"SH": 1}}}
    lines = build_training_loading_highlights(report)
    assert "Pat Jones is shooting well in practice" in lines
