"""Team Attributes rows. Scales stay unset where the game does not store one."""

from BackEnd.utils.office_digest import prior_measure_snapshot, team_attribute_measures


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
    assert list(rows) == [
        "team_chemistry", "fight", "discipline",
        "shot_threshold", "rebound_modifier", "defensive_efficiency",
    ]
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
    assert rows["defensive_efficiency"]["label"] == "Defensive efficiency"
    assert rows["discipline"]["delta"] is None


def test_missing_attribute_is_omitted():
    payload = team_attribute_measures({"team_chemistry": 10}, None, None)
    assert [row["key"] for row in payload["measures"]] == ["team_chemistry"]
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
