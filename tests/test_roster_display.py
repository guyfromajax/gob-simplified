"""Roster view fields stamped onto GET /roster rows."""

from BackEnd.utils.roster_display import apply_lineup_roles, stamp_roster_player


def test_stamp_uses_roster_position_and_max_rating():
    row = {
        "_id": "p1",
        "position_ratings": {"PG": 40, "SG": 82, "SF": 60, "PF": 50, "C": 44},
        "training_position": "PF",
        "resolved_training_position": "C",
    }
    stamp_roster_player(row, on_user_team=False, stored_position="")
    assert row["position"] == "SG"
    assert row["rt"] == 82
    assert row["starter"] is False
    assert row["lineup_order"] is None


def test_user_team_training_position_wins_when_stored_position_is_empty():
    row = {
        "position_ratings": {"PG": 90, "SG": 40},
        "resolved_training_position": "PF",
        "training_position": "C",
    }
    stamp_roster_player(row, on_user_team=True, stored_position="--")
    assert row["position"] == "PF"


def test_lineup_order_follows_projected_starting_five():
    players = [
        {"_id": "bench", "name": "Bench"},
        {"_id": "two", "name": "Two"},
        {"_id": "one", "name": "One"},
    ]
    for player in players:
        stamp_roster_player(player, on_user_team=True, stored_position="PG")
    apply_lineup_roles(players, [
        {"player_id": "one"},
        {"player_id": "two"},
    ])
    by_id = {player["_id"]: player for player in players}
    assert by_id["one"]["starter"] is True
    assert by_id["one"]["lineup_order"] == 0
    assert by_id["two"]["lineup_order"] == 1
    assert by_id["bench"]["starter"] is False
    assert by_id["bench"]["lineup_order"] is None
