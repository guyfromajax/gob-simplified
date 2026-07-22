from types import SimpleNamespace

from BackEnd.utils.shot_split_tracker import (
    format_week_aggregate_report,
    merge_shot_diagnostics,
    record_shot_split,
    restore_shot_distance_bands_from_saved,
)


def _game():
    return SimpleNamespace(game_state={})


def test_distance_bands_use_expected_boundaries_and_preserve_unknown_attempts():
    game = _game()
    samples = (
        (False, True, 3.0, 1.0, "0-3"),
        (False, False, 6.0, 0.58, "3-6"),
        (True, True, 9.0, 0.15, "6-9"),
        (True, False, 11.0, 0.15, "9-11"),
        (True, True, 11.01, 0.0, ">11"),
        (False, False, None, None, "unknown"),
    )
    for is_three, made, distance, factor, _band in samples:
        record_shot_split(
            game,
            is_three=is_three,
            defended=bool(factor),
            made=made,
            defender_distance=distance,
            contest_factor=factor,
        )

    tracking = game.game_state["shot_distance_bands"]
    for is_three, made, _distance, _factor, band in samples:
        bucket = tracking["3pt" if is_three else "2pt"][band]
        assert bucket["make" if made else "miss"] == 1


def test_distance_bands_restore_merge_and_render_contest_factor():
    game = _game()
    record_shot_split(
        game,
        is_three=False,
        defended=True,
        made=True,
        defender_distance=5,
        contest_factor=0.6,
    )
    saved = {"shot_distance_bands": game.game_state["shot_distance_bands"]}

    restored = {}
    restore_shot_distance_bands_from_saved(restored, saved)
    bucket = restored["shot_distance_bands"]["2pt"]["3-6"]
    assert bucket == {"make": 1, "miss": 0, "contest_factor_total": 0.6}

    summary = {
        "shot_split_tracking": game.game_state["shot_split_tracking"],
        "shot_distance_bands": restored["shot_distance_bands"],
    }
    merged, games = merge_shot_diagnostics([summary, summary])
    assert games == 2
    merged_bucket = merged["shot_distance_bands"]["2pt"]["3-6"]
    assert merged_bucket["make"] == 2
    assert merged_bucket["contest_factor_total"] == 1.2
    report = format_week_aggregate_report(merged, games)
    assert "Nearest-defender distance bands" in report
    assert "100.0% make, 2 att  | factor 0.60" in report
