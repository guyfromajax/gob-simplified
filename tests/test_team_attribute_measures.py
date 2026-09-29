"""Team Attributes rows. Scales stay unset where the game does not store one."""

from BackEnd.utils.office_digest import (
    SIGNED_MEASURE_SCALE,
    prior_measure_snapshot,
    team_attribute_measures,
)

# Every stored team measure is a row, in family order.
ALL_KEYS = [
    "team_chemistry", "fight", "discipline", "momentum_score",
    "offensive_efficiency", "defensive_efficiency",
    "pt_opp_modifier", "pt_efficiency",
    "fb_efficiency", "fb_opp_modifier",
    "shot_threshold", "rebound_modifier",
]

# The eight documented at −20…+20. Only these can be drawn as a diverging pill.
SIGNED_KEYS = {
    "fight", "discipline",
    "offensive_efficiency", "defensive_efficiency",
    "pt_opp_modifier", "pt_efficiency",
    "fb_efficiency", "fb_opp_modifier",
}


def test_measures_keep_chemistry_scale_and_omit_unknown_scales():
    attributes = {
        "team_chemistry": 20,
        "fight": 3,
        "discipline": 1,
        "shot_threshold": 90,
        "rebound_modifier": 0.2,
        "defensive_efficiency": 4,
    }
    before = {"fight": 1, "shot_threshold": 88}
    payload = team_attribute_measures(attributes, before, 21)
    rows = {row["key"]: row for row in payload["measures"]}
    assert payload["updated_after_week"] == 21
    assert list(rows) == ALL_KEYS
    assert rows["team_chemistry"]["family"] == "character"
    assert rows["team_chemistry"]["family_label"] == "Character"
    assert rows["team_chemistry"]["label"] == "Chemistry"
    assert rows["team_chemistry"]["scale_max"] == 25
    assert rows["team_chemistry"]["meter_pct"] == 80
    assert rows["team_chemistry"]["delta"] is None
    assert rows["team_chemistry"]["description"] is None
    assert rows["fight"]["delta"] == 2
    assert rows["fight"]["scale_max"] is None
    assert rows["fight"]["meter_pct"] is None
    assert rows["shot_threshold"]["family"] == "floor"
    assert rows["shot_threshold"]["family_label"] == "On the floor"
    assert rows["shot_threshold"]["label"] == "Shooting"
    assert rows["shot_threshold"]["scale_max"] is None
    assert rows["shot_threshold"]["delta"] == 2
    assert rows["rebound_modifier"]["label"] == "Rebounding"
    assert rows["defensive_efficiency"]["label"] == "Defense"
    assert rows["discipline"]["delta"] is None


def test_the_four_paired_labels_the_grid_needs():
    payload = team_attribute_measures({}, None, None)
    labels = {row["key"]: row["label"] for row in payload["measures"]}
    assert labels["offensive_efficiency"] == "Offense"
    assert labels["defensive_efficiency"] == "Defense"
    assert labels["pt_opp_modifier"] == "P/T Offense"
    assert labels["pt_efficiency"] == "P/T Defense"
    assert labels["fb_efficiency"] == "Fast Break"
    assert labels["fb_opp_modifier"] == "Fast Break Defense"
    assert labels["momentum_score"] == "Momentum"


def test_only_the_eight_minus_twenty_to_twenty_measures_carry_a_signed_scale():
    payload = team_attribute_measures({}, None, None)
    signed = {
        row["key"] for row in payload["measures"]
        if row["signed_scale"] is not None
    }
    assert signed == SIGNED_KEYS
    for row in payload["measures"]:
        if row["key"] in SIGNED_KEYS:
            assert row["signed_scale"] == SIGNED_MEASURE_SCALE
    # Chemistry has a scale but it is not signed; Momentum is ±10, not ±20.
    rows = {row["key"]: row for row in payload["measures"]}
    assert rows["team_chemistry"]["scale_max"] == 25
    assert rows["team_chemistry"]["signed_scale"] is None
    assert rows["momentum_score"]["signed_scale"] is None


def test_missing_attribute_stays_on_the_row_with_a_null_value():
    payload = team_attribute_measures({"team_chemistry": 10}, None, None)
    rows = {row["key"]: row for row in payload["measures"]}
    assert list(rows) == ALL_KEYS
    assert rows["team_chemistry"]["value"] == 10
    assert rows["team_chemistry"]["meter_pct"] == 40
    assert rows["fight"]["value"] is None
    assert rows["fight"]["meter_pct"] is None
    assert payload["updated_after_week"] is None


def test_prior_snapshot_returns_the_closed_week():
    franchise = {
        "current_season": 1,
        "office_week_snapshots": {
            "1": {
                "2": {"week": 2, "team_measures": {"fight": 4}},
                "5": {"week": 5, "team_measures": {"fight": 6}},
            }
        },
    }
    measures, week = prior_measure_snapshot(franchise, 8)
    assert week == 5
    assert measures["fight"] == 6
    assert prior_measure_snapshot(franchise, 2) == (None, None)
