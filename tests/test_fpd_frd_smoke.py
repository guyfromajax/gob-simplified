"""
Smoke test for FPD/FRD migration: create a new franchise via API and hit
state, recruits, roster, and team-stats to ensure data is read from
franchise_players_data and franchise_recruits_data (not franchise.players/recruits).
"""
import pytest
from fastapi.testclient import TestClient
from bson import ObjectId

from BackEnd.api.api import app
from BackEnd.db import (
    db,
    franchise_players_data_collection,
    franchise_recruits_data_collection,
    franchise_team_data_collection,
)

client = TestClient(app)


def _setup_teams_and_players():
    """Insert the canonical 128-team league and a few players for FPD."""
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})
    franchise_players_data_collection.delete_many({})
    franchise_recruits_data_collection.delete_many({})
    franchise_team_data_collection.delete_many({})
    db.players.delete_many({})

    # Franchise scheduling requires 16 conferences of eight teams, paired into
    # eight regions (two conferences / 16 teams per region).
    team_ids = [ObjectId() for _ in range(128)]
    teams = [
        {
            "_id": team_ids[i],
            "name": f"Team{i}",
            "record": {"W": 0, "L": 0},
            "PF": 0,
            "PA": 0,
            "conference": (i % 16) + 1,
            "region": chr(ord("A") + ((i % 16) // 2)),
            "prestige": 500,
            "player_ids": [] if i > 0 else ["p1", "p2"],
        }
        for i in range(128)
    ]
    db.teams.insert_many(teams)

    attrs = {k: 1 for k in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "NG"]}
    players = [
        {"_id": "p1", "first_name": "Alice", "last_name": "One", "team": "Team0", "team_id": team_ids[0], "attributes": attrs.copy(), "position_ratings": {}},
        {"_id": "p2", "first_name": "Bob", "last_name": "Two", "team": "Team0", "team_id": team_ids[0], "attributes": attrs.copy(), "position_ratings": {}},
    ]
    db.players.insert_many(players)
    return teams[0]["name"]


@pytest.mark.order("last")
def test_fpd_frd_smoke_create_franchise_and_read_paths():
    """Create franchise via select-team, then GET state, recruits, roster, team-stats."""
    user_team_name = _setup_teams_and_players()

    # 1) Create franchise (writes FPD + FRD)
    res = client.post("/franchise/select-team", json={"team_name": user_team_name})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data.get("status") == "ok"
    franchise_id = data["franchise_id"]
    assert franchise_id

    # 2) FPD/FRD should be populated
    fpd_count = franchise_players_data_collection.count_documents({"franchise_id": franchise_id})
    frd_count = franchise_recruits_data_collection.count_documents({"franchise_id": franchise_id})
    assert fpd_count >= 2, "FPD should have at least 2 players (p1, p2)"
    assert frd_count >= 1, "FRD should have at least 1 recruit"

    # 3) GET /franchise/state — builds players from FPD
    res_state = client.get(f"/franchise/state?franchise_id={franchise_id}")
    assert res_state.status_code == 200, res_state.text
    state = res_state.json()
    assert "players" in state
    assert len(state["players"]) >= 2
    assert "p1" in state["players"] and "p2" in state["players"]

    # 4) GET /franchise/recruits — from FRD
    res_recruits = client.get(f"/franchise/recruits?franchise_id={franchise_id}")
    assert res_recruits.status_code == 200, res_recruits.text
    recruits_data = res_recruits.json()
    assert "recruits" in recruits_data
    assert len(recruits_data["recruits"]) >= 1
    for r in recruits_data["recruits"]:
        assert "recruit_id" in r or "name" in r

    # 5) GET /franchise/roster — FPD + team player_ids
    res_roster = client.get(f"/franchise/roster?franchise_id={franchise_id}&team_name={user_team_name}")
    assert res_roster.status_code == 200, res_roster.text
    roster = res_roster.json()
    assert "players" in roster
    assert len(roster["players"]) >= 2

    # 6) GET /franchise/team-stats — aggregates from FPD
    res_stats = client.get(f"/franchise/team-stats?franchise_id={franchise_id}")
    assert res_stats.status_code == 200, res_stats.text
    stats = res_stats.json()
    assert "teams" in stats
