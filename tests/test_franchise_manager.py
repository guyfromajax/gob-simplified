import pytest
from bson import ObjectId

from BackEnd.models.franchise_manager import FranchiseManager, ScheduleManager
from BackEnd.db import db, franchise_team_data_collection
from BackEnd.api.gameplan_routes import (
    USER_FRANCHISE_PC_DEFENSE_ORDER,
    USER_FRANCHISE_PC_OFFENSE_ORDER,
)


def _region_for_conference(c):
    """Region A–H for conference 1–16: A=(1,2), B=(3,4), ..., H=(15,16)."""
    return chr(ord("A") + (c - 1) // 2)


def insert_mock_teams_128():
    """Insert 128 teams with conference 1–16 and region A–H for Phase 1 schedule."""
    teams = []
    for i in range(128):
        conf = (i % 16) + 1
        teams.append({
            "_id": ObjectId(),
            "name": f"Team{i}",
            "conference": conf,
            "region": _region_for_conference(conf),
        })
    db.teams.insert_many(teams)
    return teams


def insert_mock_teams():
    """Legacy 8-team insert; use insert_mock_teams_128() for schedule generation."""
    teams = [{"_id": f"T{i}", "name": f"Team{i}", "conference": 1, "region": "A"} for i in range(8)]
    db.teams.insert_many(teams)


def test_initialize_season_produces_phase1_schedule():
    """With 128 teams (conference + region), init produces 26 weeks, 64 games per week."""
    db.teams.delete_many({})
    db.games.delete_many({})
    insert_mock_teams_128()

    manager = FranchiseManager(db)
    manager.initialize_season()

    # Phase 1: 26 weeks, 64 games per week
    assert len(manager.schedule) == ScheduleManager.REGULAR_SEASON_WEEKS
    assert all(len(week) == 64 for week in manager.schedule)


def test_initialize_season_with_128_teams_generates_26_week_schedule():
    """
    Phase 1: init with 128 teams (conference 1–16, region A–H) produces 26-week schedule, 64 games/week.
    """
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})
    franchise_team_data_collection.delete_many({})
    db.players.delete_many({})

    team_ids = [ObjectId() for _ in range(128)]
    teams = []
    for i in range(128):
        conf = (i % 16) + 1
        region = _region_for_conference(conf)
        teams.append({
            "_id": team_ids[i],
            "name": f"Team{i}",
            "conference": conf,
            "region": region,
            "prestige": 500,
            "player_ids": [],
        })
    db.teams.insert_many(teams)

    db.players.insert_one({
        "_id": "p1",
        "first_name": "A",
        "last_name": "One",
        "team": "Team0",
        "team_id": team_ids[0],
        "attributes": {k: 50 for k in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]},
        "position_ratings": {},
    })

    manager = FranchiseManager(db)
    manager.initialize_season(
        user_team_id="Team0",
        user_team_object_id=str(team_ids[0]),
    )

    assert len(manager.schedule) == ScheduleManager.REGULAR_SEASON_WEEKS, "Schedule should have 26 weeks"
    assert all(len(week) == 64 for week in manager.schedule), "Each week should have 64 games"

    assert manager.franchise_id is not None
    ftd_count = franchise_team_data_collection.count_documents({"franchise_id": manager.franchise_id})
    assert ftd_count == 128, f"FTD should have 128 docs, got {ftd_count}"

    user_ftd = franchise_team_data_collection.find_one(
        {"franchise_id": manager.franchise_id, "team_id": team_ids[0]}
    )
    cpu_ftd = franchise_team_data_collection.find_one(
        {"franchise_id": manager.franchise_id, "team_id": team_ids[1]}
    )
    assert user_ftd["playbook_settings"]["pc_order"] == {
        "offense": USER_FRANCHISE_PC_OFFENSE_ORDER,
        "defense": USER_FRANCHISE_PC_DEFENSE_ORDER,
    }
    assert cpu_ftd["playbook_settings"]["pc_order"] == {
        "offense": [],
        "defense": [],
    }
