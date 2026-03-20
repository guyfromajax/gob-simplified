"""Tests for scouting report projected starting five (greedy RT assignment)."""
from BackEnd.utils.scouting_utils import compute_projected_starting_five


def _p(pid, ratings: dict, attrs=None):
    base_attrs = {k: 50 for k in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]}
    if attrs:
        base_attrs.update(attrs)
    return {
        "_id": pid,
        "first_name": "F",
        "last_name": pid,
        "name": f"F {pid}",
        "jersey": int(pid) if pid.isdigit() else 0,
        "year": "junior",
        "height": 78,
        "weight": 200,
        "attributes": base_attrs,
        "position_ratings": ratings,
    }


def test_greedy_assigns_each_player_once():
    """Descending RT specialists each get their slot."""
    players = [
        _p("1", {"PG": 99, "SG": 10}),
        _p("2", {"SG": 98, "PG": 10}),
        _p("3", {"SF": 97}),
        _p("4", {"PF": 96}),
        _p("5", {"C": 95}),
    ]
    rows = compute_projected_starting_five(players)
    by_pos = {r["position"]: r for r in rows}
    assert by_pos["PG"]["player_id"] == "1"
    assert by_pos["SG"]["player_id"] == "2"
    assert by_pos["SF"]["player_id"] == "3"
    assert by_pos["PF"]["player_id"] == "4"
    assert by_pos["C"]["player_id"] == "5"
    assert by_pos["PG"]["rt"] == 99.0


def test_star_player_fills_pg_first_highest_global_rt():
    """Player with two high RTs occupies the globally best (position, player) pair first (PG)."""
    players = [
        _p("1", {"PG": 100, "SG": 99}),
        _p("2", {"SG": 98}),
        _p("3", {"SF": 97}),
        _p("4", {"PF": 96}),
        _p("5", {"C": 95}),
    ]
    rows = compute_projected_starting_five(players)
    by_pos = {r["position"]: r for r in rows}
    assert by_pos["PG"]["player_id"] == "1"
    assert by_pos["SG"]["player_id"] == "2"
    assert by_pos["SF"]["player_id"] == "3"
    assert by_pos["PF"]["player_id"] == "4"
    assert by_pos["C"]["player_id"] == "5"


def test_attributes_floor_ten_in_output():
    row = compute_projected_starting_five(
        [
            _p(
                "1",
                {"PG": 80},
                {"SC": 87, "SH": 73},
            )
        ]
    )
    assert len(row) == 1
    assert row[0]["attributes"]["SC"] == 8
    assert row[0]["attributes"]["SH"] == 7
