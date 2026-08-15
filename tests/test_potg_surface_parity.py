import json
import subprocess
from pathlib import Path

from BackEnd.api.franchise_routes import _calculate_potg_summary


ROOT = Path(__file__).resolve().parents[1]


def _game_fixture():
    return {
        "_id": "potg-parity-game-17",
        "home_team_id": "home-id",
        "away_team_id": "away-id",
        "teams": {
            "home-id": {"name": "Home"},
            "away-id": {"name": "Away"},
        },
        "score": {"Home": 80, "Away": 76},
        # The player snapshot deliberately has partial stats. The box score must
        # merge over it on both surfaces rather than being discarded by FCC.
        "players": [
            {"playerId": "h1", "name": "Home One", "team": "home", "stats": {"PTS": 12, "REB": 1}},
            {"playerId": "a1", "name": "Away One", "team": "away", "stats": {"PTS": 11, "REB": 1}},
        ],
        "box_score": {
            "Home": {
                "PG": {"playerId": "h1", "name": "Home One", "PTS": 14, "REB": 7, "AST": 4, "STL": 1, "BLK": 0, "DEF_A": 12, "DEF_S": 8},
            },
            "Away": {
                "PG": {"playerId": "a1", "name": "Away One", "PTS": 16, "REB": 5, "AST": 4, "STL": 0, "BLK": 1, "DEF_A": 12, "DEF_S": 7},
            },
        },
    }


def test_fcc_potg_matches_canonical_modal_algorithm():
    game = _game_fixture()
    completed = subprocess.run(
        ["node", str(ROOT / "tests/js/runPotgParity.mjs")],
        input=json.dumps(game),
        capture_output=True,
        text=True,
        check=True,
    )
    modal = json.loads(completed.stdout)
    fcc = _calculate_potg_summary(game)

    assert fcc["player_id"] == modal["playerId"]
    assert fcc["name"] == modal["name"]
    assert fcc["stats"] == {
        "pts": modal["stats"]["pts"],
        "reb": modal["stats"]["reb"],
        "ast": modal["stats"]["ast"],
        "stl": modal["stats"]["stl"],
        "blk": modal["stats"]["blk"],
        "defPct": modal["stats"]["defPct"],
    }
