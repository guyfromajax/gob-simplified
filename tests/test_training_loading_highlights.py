"""Tests for archetyped franchise training loading highlights."""

from __future__ import annotations

from unittest.mock import patch

from BackEnd.utils.training_loading_highlights import build_training_loading_highlights


def _ftd(**kwargs: int) -> dict:
    base = {
        "authoritarian": 0,
        "systems_coach": 0,
        "player_maximizer": 0,
        "culture_builder": 0,
    }
    base.update(kwargs)
    return base


def test_delta_three_does_not_fire_player_line():
    report = {
        "coaching_focus": {"archetype": "authoritarian"},
        "ftd_coaching_focus": _ftd(authoritarian=5),
        "player_logs": {"Alex Smith": {"SH": 3}},
    }
    with patch(
        "BackEnd.utils.training_loading_highlights.random.choice",
        lambda seq: seq[0],
    ):
        with patch(
            "BackEnd.utils.training_loading_highlights.random.random",
            return_value=0.99,
        ):
            with patch(
                "BackEnd.utils.training_loading_highlights.random.shuffle",
                lambda x: None,
            ):
                lines = build_training_loading_highlights(report)
    assert not any("Alex Smith" in ln for ln in lines)
    assert len(lines) >= 1


def test_strict_positive_four_fires_sc_line():
    report = {
        "coaching_focus": {"archetype": "authoritarian"},
        "ftd_coaching_focus": _ftd(authoritarian=5),
        "player_logs": {"Alex Smith": {"SC": 4}},
    }
    with patch(
        "BackEnd.utils.training_loading_highlights.random.choice",
        lambda seq: seq[0],
    ):
        with patch(
            "BackEnd.utils.training_loading_highlights.random.random",
            return_value=0.99,
        ):
            with patch(
                "BackEnd.utils.training_loading_highlights.random.shuffle",
                lambda x: None,
            ):
                lines = build_training_loading_highlights(report)
    assert any("Alex Smith" in ln for ln in lines)
    assert lines[0]  # flavor line


def test_player_changes_alias():
    report = {
        "coaching_focus": {"archetype": "authoritarian"},
        "ftd_coaching_focus": _ftd(authoritarian=1),
        "player_changes": {"Pat Jones": {"SC": 5}},
    }
    with patch(
        "BackEnd.utils.training_loading_highlights.random.choice",
        lambda seq: seq[0],
    ):
        with patch(
            "BackEnd.utils.training_loading_highlights.random.random",
            return_value=0.99,
        ):
            with patch(
                "BackEnd.utils.training_loading_highlights.random.shuffle",
                lambda x: None,
            ):
                lines = build_training_loading_highlights(report)
    assert any("Pat Jones" in ln for ln in lines)


def test_no_play_effectiveness_lines():
    report = {
        "plays_effectiveness_changes": {"507f1f77bcf86cd799439011": 3},
        "plays_data": {
            "507f1f77bcf86cd799439011": {
                "play_id": "507f1f77bcf86cd799439011",
                "name": "Horns Flare",
                "effectiveness": 100,
            },
        },
        "coaching_focus": {"archetype": "authoritarian"},
        "ftd_coaching_focus": _ftd(),
    }
    with patch(
        "BackEnd.utils.training_loading_highlights.random.choice",
        lambda seq: seq[0],
    ):
        with patch(
            "BackEnd.utils.training_loading_highlights.random.random",
            return_value=0.99,
        ):
            with patch(
                "BackEnd.utils.training_loading_highlights.random.shuffle",
                lambda x: None,
            ):
                lines = build_training_loading_highlights(report)
    assert not any("Play effectiveness" in ln for ln in lines)


def test_ftd_kwarg_overrides_report():
    report = {
        "coaching_focus": {"archetype": "authoritarian"},
        "ftd_coaching_focus": _ftd(authoritarian=1),
        "player_logs": {"X": {"SC": 5}},
    }
    with patch(
        "BackEnd.utils.training_loading_highlights.random.choice",
        lambda seq: seq[0],
    ):
        with patch(
            "BackEnd.utils.training_loading_highlights.random.random",
            return_value=0.99,
        ):
            with patch(
                "BackEnd.utils.training_loading_highlights.random.shuffle",
                lambda x: None,
            ):
                lines = build_training_loading_highlights(
                    report,
                    ftd_coaching_focus=_ftd(systems_coach=99, authoritarian=0),
                )
    assert any("X" in ln for ln in lines)
