import pytest
from bson import ObjectId

from BackEnd.models.franchise_manager import FranchiseManager
from BackEnd.db import db, franchise_team_data_collection


def insert_mock_teams():
    # Conference 1 required so ScheduleManager gets exactly 8 teams for round-robin
    teams = [{"_id": f"T{i}", "name": f"Team{i}", "conference": 1} for i in range(8)]
    db.teams.insert_many(teams)


def test_initialize_season_clears_old_games():
    # Prepopulate games to mimic previous season results
    db.games.insert_many([
        {"team1_id": "T0", "team2_id": "T1", "week": 1, "team1_score": 80, "team2_score": 70},
        {"team1_id": "T2", "team2_id": "T3", "week": 1, "team1_score": 90, "team2_score": 60},
    ])
    assert db.games.count_documents({}) == 2

    insert_mock_teams()
    manager = FranchiseManager(db)
    manager.initialize_season()

    # All previous game docs should be removed
    assert db.games.count_documents({}) == 0
    # Schedule should contain 14 weeks of 4 games each
    assert len(manager.schedule) == 14
    assert all(len(week) == 4 for week in manager.schedule)


def test_initialize_season_with_many_teams_only_conference_1_in_schedule():
    """
    Regression: init with >8 teams must use only Conference 1 (8 teams) for schedule.
    Catches bugs like ScheduleManager receiving all 128 teams and raising.
    """
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})
    franchise_team_data_collection.delete_many({})
    db.players.delete_many({})

    # 128 teams: first 8 conference 1 (schedule), rest conference 2+
    team_ids = [ObjectId() for _ in range(128)]
    teams = []
    for i in range(128):
        teams.append({
            "_id": team_ids[i],
            "name": f"Team{i}",
            "conference": 1 if i < 8 else (2 + (i // 8)),
            "prestige": 500,
            "player_ids": [],
        })
    db.teams.insert_many(teams)

    # One player so FPD has at least one doc (optional but avoids empty inserts)
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

    # Schedule is for 8 conference-1 teams only: 14 weeks, 4 games per week
    assert len(manager.schedule) == 14, "Schedule should have 14 weeks (round-robin for 8 teams)"
    assert all(len(week) == 4 for week in manager.schedule), "Each week should have 4 games"

    # FTD should have one doc per team (128 total)
    assert manager.franchise_id is not None
    ftd_count = franchise_team_data_collection.count_documents({"franchise_id": manager.franchise_id})
    assert ftd_count == 128, f"FTD should have 128 docs, got {ftd_count}"
