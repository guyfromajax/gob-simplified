"""Team stats reads season lines through a projection, not the whole player document."""

import logging
import os

from bson import ObjectId

from BackEnd.api.franchise_routes import team_stats
from BackEnd.db import db, franchise_players_data_collection, franchise_team_data_collection


def setup_function(_fn):
    db.franchises.delete_many({})
    db.teams.delete_many({})
    franchise_players_data_collection.delete_many({})
    franchise_team_data_collection.delete_many({})


def test_projected_player_scan_keeps_rates_and_skips_full_decode(caplog):
    fid = db.franchises.insert_one({"week": 2, "results": {}}).inserted_id
    team_id = ObjectId()
    db.teams.insert_one({"_id": team_id, "name": "Lancaster", "conference": 1, "region": "A"})
    franchise_team_data_collection.insert_one({
        "franchise_id": fid,
        "team_id": team_id,
        "players": ["shooter"],
        "natl_rank": 4,
    })
    franchise_players_data_collection.insert_one({
        "franchise_id": str(fid),
        "player_id": "shooter",
        "meta": {"team_id": str(team_id), "team": "Lancaster"},
        "attributes": {"blob": "x" * 4000},
        "season": {"FGM": 10, "FGA": 20, "PTS": 22, "FTM": 3, "FTA": 4},
    })
    os.environ["GOB_SQLITE_QUERY_LOG"] = "1"
    with caplog.at_level(logging.WARNING, logger="BackEnd.persistence.sqlite_collection"):
        body = team_stats(str(fid))
    team = next(row for row in body["teams"] if row["team_id"] == str(team_id))
    assert team["stats"]["FGM"] == 10
    assert team["stats"]["FG_PCT"] == 50.0
    assert team["stats"]["FT_PCT"] == 75.0
    assert team["stats"]["PTS"] == 22
    if os.environ.get("GOB_PERSISTENCE") == "sqlite":
        # The SQLite path extracts season scalars. A full decode would log decoded=True.
        player_lines = [
            record.getMessage()
            for record in caplog.records
            if "franchise_players_data" in record.getMessage()
        ]
        assert all("decoded=False" in line for line in player_lines)
