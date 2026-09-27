"""League ranks for Team Attributes measures. Runs on mongomock and on SQLite."""

from bson import ObjectId
from fastapi.testclient import TestClient

from BackEnd.api.api import app
from BackEnd.db import db, franchise_team_data_collection
from BackEnd.utils.team_measure_ranks import (
    MEASURE_SPECS,
    build_measures,
    competition_ranks,
    measures_for_team,
    percentile,
)

client = TestClient(app)

USER = ObjectId()
OTHER = ObjectId()
THIRD = ObjectId()
FOURTH = ObjectId()


def setup_function(_fn):
    db.franchises.delete_many({})
    franchise_team_data_collection.delete_many({})


def _row(team_id, **values):
    stored = {spec["key"]: None for spec in MEASURE_SPECS}
    stored.update(values)
    return {"team_id": str(team_id), "values": stored}


def _by_key(measures):
    return {row["key"]: row for row in measures}


def test_direction_table():
    directions = {spec["key"]: spec["direction"] for spec in MEASURE_SPECS}
    assert directions == {
        "team_chemistry": "higher_better",
        "fight": "higher_better",
        "discipline": "higher_better",
        "shot_threshold": "lower_better",
        "rebound_modifier": "higher_better",
        "defensive_efficiency": "higher_better",
    }
    chemistry = next(spec for spec in MEASURE_SPECS if spec["key"] == "team_chemistry")
    assert chemistry["scale_max"] == 25


def test_ties_share_a_rank_and_the_next_place_skips():
    ranks = competition_ranks(
        {"a": 10, "b": 8, "c": 8, "d": 5},
        higher_better=True,
    )
    assert ranks == {"a": 1, "b": 2, "c": 2, "d": 4}


def test_lower_better_ranks_the_smallest_value_first():
    rows = [
        _row("a", shot_threshold=90),
        _row("b", shot_threshold=70),
        _row("c", shot_threshold=110),
    ]
    ranked = _by_key(build_measures(rows, "b"))
    assert ranked["shot_threshold"]["direction"] == "lower_better"
    assert ranked["shot_threshold"]["rank"] == 1
    assert _by_key(build_measures(rows, "a"))["shot_threshold"]["rank"] == 2
    assert _by_key(build_measures(rows, "c"))["shot_threshold"]["rank"] == 3


def test_percentile_ends_are_best_100_and_worst_0():
    values = [10.0, 8.0, 5.0]
    assert percentile(10.0, values, higher_better=True) == 100
    assert percentile(5.0, values, higher_better=True) == 0
    # Tied for best and tied for worst share those ends.
    tied = [10.0, 10.0, 1.0, 1.0]
    assert percentile(10.0, tied, higher_better=True) == 100
    assert percentile(1.0, tied, higher_better=True) == 0
    # lower_better: the small number is the best end.
    shooting = [70.0, 90.0, 110.0]
    assert percentile(70.0, shooting, higher_better=False) == 100
    assert percentile(110.0, shooting, higher_better=False) == 0


def test_rank_delta_from_a_snapshot_is_positive_when_the_team_climbs():
    rows = [
        _row("user", defensive_efficiency=4, shot_threshold=80),
        _row("b", defensive_efficiency=1, shot_threshold=100),
        _row("c", defensive_efficiency=8, shot_threshold=70),
    ]
    # User was last in defensive efficiency (0) and last in shooting (120).
    prior = {"defensive_efficiency": 0, "shot_threshold": 120, "team_chemistry": 5}
    ranked = _by_key(build_measures(rows, "user", prior))
    defense = ranked["defensive_efficiency"]
    assert defense["rank"] == 2
    assert defense["rank_delta"] == 1
    shooting = ranked["shot_threshold"]
    assert shooting["rank"] == 2
    assert shooting["rank_delta"] == 1
    # Chemistry is not a snapshot key, even when the dict carries one.
    assert ranked["team_chemistry"]["rank_delta"] is None


def test_missing_values_are_excluded_from_rank_of():
    rows = [
        _row("a", rebound_modifier=0.2),
        _row("b", rebound_modifier=0.8),
        _row("c"),
    ]
    present = _by_key(build_measures(rows, "b"))["rebound_modifier"]
    assert present["rank"] == 1
    assert present["rank_of"] == 2
    missing = _by_key(build_measures(rows, "c"))["rebound_modifier"]
    assert missing["value"] is None
    assert missing["rank"] is None
    assert missing["rank_of"] is None
    assert missing["percentile"] is None


def test_fight_and_discipline_rank_higher_better_and_mark_ties():
    rows = [
        _row("a", fight=2, discipline=4),
        _row("b", fight=6, discipline=4),
        _row("c", fight=0, discipline=-2),
        _row("d", fight=6, discipline=1),
    ]
    fight = _by_key(build_measures(rows, "a", {"fight": -1}))["fight"]
    discipline = _by_key(build_measures(rows, "b"))["discipline"]
    assert fight["direction"] == "higher_better"
    assert fight["value"] == 2
    assert fight["rank"] == 3
    assert fight["rank_of"] == 4
    assert fight["rank_delta"] == 1
    assert fight["tied"] is False
    tied = _by_key(build_measures(rows, "b"))["fight"]
    assert tied["rank"] == 1
    assert tied["tied"] is True
    assert discipline["direction"] == "higher_better"
    assert discipline["rank"] == 1
    assert discipline["tied"] is True


def test_team_data_route_attaches_ranks_and_the_user_delta():
    fid = db.franchises.insert_one({
        "user_team_id": "Lancaster",
        "user_team_object_id": str(USER),
        "week": 3,
        "current_season": 1,
        "office_week_snapshots": {
            "1": {
                "2": {
                    "team_measures": {
                        "shot_threshold": 120,
                        "defensive_efficiency": 0,
                        "rebound_modifier": 0.1,
                        "fight": 3,
                        "team_chemistry": 10,
                    },
                },
            },
        },
    }).inserted_id
    boards = [
        (USER, {"team_chemistry": 18, "fight": -1, "shot_threshold": 80, "rebound_modifier": 0.48, "defensive_efficiency": 4}),
        (OTHER, {"team_chemistry": 10, "fight": 2, "shot_threshold": 70, "rebound_modifier": 0.2, "defensive_efficiency": 8}),
        (THIRD, {"team_chemistry": 22, "fight": 5, "shot_threshold": 100, "rebound_modifier": None, "defensive_efficiency": 1}),
        (FOURTH, {"team_chemistry": 12, "fight": 0, "discipline": 3, "shot_threshold": 90, "rebound_modifier": 0.6, "defensive_efficiency": -2}),
    ]
    for team_id, attrs in boards:
        franchise_team_data_collection.insert_one({
            "franchise_id": fid,
            "team_id": team_id,
            "team_attributes": attrs,
            "plays": {},
            "scouting_data": {},
        })

    response = client.get(f"/franchise/team-data?franchise_id={fid}&team_id={USER}")
    assert response.status_code == 200
    body = response.json()
    measures = _by_key(body["measures"])
    assert list(measures) == [spec["key"] for spec in MEASURE_SPECS]

    assert body["updated_after_week"] == 2
    chemistry = measures["team_chemistry"]
    assert chemistry["family"] == "character"
    assert chemistry["family_label"] == "Character"
    assert chemistry["label"] == "Chemistry"
    assert chemistry["value"] == 18
    assert chemistry["scale_max"] == 25
    assert chemistry["meter_pct"] == 72
    assert chemistry["description"] is None
    assert chemistry["direction"] == "higher_better"
    assert chemistry["rank"] == 2
    assert chemistry["rank_of"] == 4
    assert chemistry["percentile"] == 66.7
    assert chemistry["rank_delta"] is None

    shooting = measures["shot_threshold"]
    assert shooting["family"] == "floor"
    assert shooting["label"] == "Shooting"
    assert shooting["direction"] == "lower_better"
    assert shooting["meter_pct"] is None
    assert shooting["rank"] == 2
    assert shooting["rank_of"] == 4
    assert shooting["rank_delta"] == 2

    rebounding = measures["rebound_modifier"]
    assert rebounding["label"] == "Rebounding"
    assert rebounding["meter_pct"] is None
    assert rebounding["rank_of"] == 3
    assert rebounding["value"] == 0.48

    fight = measures["fight"]
    assert fight["value"] == -1
    assert fight["direction"] == "higher_better"
    assert fight["meter_pct"] is None
    assert fight["rank"] == 4
    assert fight["rank_of"] == 4
    assert fight["percentile"] == 0
    assert fight["rank_delta"] == -2
    assert measures["discipline"]["value"] is None
    assert measures["discipline"]["rank"] is None
    assert measures["discipline"]["meter_pct"] is None

    other = client.get(f"/franchise/team-data?franchise_id={fid}&team_id={OTHER}")
    assert other.status_code == 200
    other_shooting = _by_key(other.json()["measures"])["shot_threshold"]
    assert other_shooting["rank"] == 1
    assert other_shooting["percentile"] == 100
    assert other_shooting["rank_delta"] is None

    # The projected reader and the route agree.
    direct = _by_key(measures_for_team(
        franchise_team_data_collection,
        fid,
        USER,
        prior_measures={"shot_threshold": 120},
    ))
    assert direct["shot_threshold"]["rank"] == shooting["rank"]
    assert direct["shot_threshold"]["rank_of"] == 4
