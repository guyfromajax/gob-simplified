"""The exceptional-gain rule: parity with the client threshold, and the digest flag."""

import pytest

from BackEnd.utils.attribute_gain import (
    exceptional_attributes,
    exceptional_gain_rows,
    exceptional_gain_threshold,
    is_exceptional_gain,
    raw_player_gains,
)
from BackEnd.utils.office_digest import attribute_changes_from_report


def js_threshold(week):
    """training-report.js::getExceptionalGainThreshold, transcribed.

        return getReportWeekNumber() === 1 ? 10 : 5;
    """
    return 10 if week == 1 else 5


@pytest.mark.parametrize("week", [0, 1, 2, 5, 26, 35, 36])
def test_threshold_matches_the_client_rule_week_for_week(week):
    assert exceptional_gain_threshold(week) == js_threshold(week)


# (delta, week, expected). Camp needs 10, every other week needs 5.
PARITY_CASES = [
    (10, 1, True),
    (9.99, 1, False),
    (12, 1, True),
    (5, 1, False),
    (5, 2, True),
    (4.99, 2, False),
    (6.5, 14, True),
    (0, 2, False),
    (-7, 2, False),
    (-12, 1, False),
    (5, 26, True),
    (100, 36, True),
]


@pytest.mark.parametrize("delta,week,expected", PARITY_CASES)
def test_rule_parity_on_a_table_of_cases(delta, week, expected):
    assert is_exceptional_gain(delta, week) is expected
    # The same answer the client would reach from the same two inputs.
    assert (float(delta) >= js_threshold(week)) is expected


def test_a_missing_or_unparseable_delta_is_never_exceptional():
    for delta in (None, "", "abc", True, False, float("nan")):
        assert is_exceptional_gain(delta, 1) is False


def test_an_unknown_week_uses_the_in_season_threshold():
    assert exceptional_gain_threshold(None) == 5
    assert exceptional_gain_threshold("camp") == 5
    assert is_exceptional_gain(5, None) is True


def _report(week=14):
    return {
        "week": week,
        # Raw deltas, keyed by display name, as training_execution_v2 writes them.
        "player_logs": {
            "Ada Hall": {"shooting": 6.2, "passing": 1.0, "year": "jr"},
            "Bea Hall": {"shooting": 4.9},
        },
        "player_attribute_display_movements": {
            "p1": {"name": "Ada Hall",
                   "shooting": {"from": 6, "to": 7},
                   "passing": {"from": 5, "to": 6}},
            "p2": {"name": "Bea Hall", "shooting": {"from": 4, "to": 5}},
        },
    }


def test_raw_gains_skip_the_year_tag_and_accept_the_legacy_key():
    gains = raw_player_gains(_report())
    assert gains["Ada Hall"] == {"shooting": 6.2, "passing": 1.0}
    legacy = raw_player_gains({"week": 2, "player_changes": {"Cy": {"speed": 7}}})
    assert legacy == {"Cy": {"speed": 7.0}}
    assert raw_player_gains(None) == {}


def test_exceptional_pairs_and_rows():
    assert exceptional_attributes(_report()) == {("Ada Hall", "shooting")}
    assert exceptional_gain_rows(_report()) == [{"name": "Ada Hall", "attribute": "shooting"}]
    # At camp the same +6.2 is not exceptional: the threshold is 10.
    assert exceptional_attributes(_report(week=1)) == set()
    assert exceptional_gain_rows(_report(week=1)) == []


def test_the_digest_flags_only_the_qualifying_row():
    rows = attribute_changes_from_report(_report())

    flagged = [(row["name"], row["attribute"]) for row in rows if row.get("exceptional")]
    assert flagged == [("Ada Hall", "shooting")]
    # The key is absent rather than false on every other row.
    for row in rows:
        if (row["name"], row["attribute"]) != ("Ada Hall", "shooting"):
            assert "exceptional" not in row
    # The rest of the row shape is unchanged.
    assert rows[0]["from"] == 5 and rows[0]["to"] == 6


def test_the_flag_survives_a_loss_week_and_a_camp_report():
    # The marker is about the gain, not the result, so nothing about the game matters.
    camp = _report(week=1)
    camp["player_logs"]["Ada Hall"]["shooting"] = 11
    rows = attribute_changes_from_report(camp)
    assert [row.get("exceptional") for row in rows if row["attribute"] == "shooting"] == [True, None]
