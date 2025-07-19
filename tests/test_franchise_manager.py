import pytest

from BackEnd.models.franchise_manager import FranchiseManager
from BackEnd.db import db


def insert_mock_teams():
    teams = [{"_id": f"T{i}", "name": f"Team{i}"} for i in range(8)]
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
