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


def test_enrich_projected_five_season_avgs():
    from BackEnd.utils.scouting_utils import enrich_projected_starting_five_season_avgs

    rows = [
        {
            "position": "PG",
            "player_id": "p1",
            "name": "Test Player",
            "jersey": 1,
            "year": "junior",
            "height": 74,
            "weight": 190,
            "rt": 55.0,
            "attributes": {},
        }
    ]
    stats = {
        "p1": {
            "GP": 10,
            "PTS": 124,
            "AST": 37,
            "OREB": 5,
            "DREB": 25,
            "DEF_S": 40,
            "DEF_A": 80,
        }
    }
    enrich_projected_starting_five_season_avgs(rows, stats)
    assert rows[0]["ppg"] == 12.4
    assert rows[0]["rpg"] == 3.0
    assert rows[0]["apg"] == 3.7
    assert rows[0]["def_pct"] == 50


def test_enrich_projected_five_zero_gp_and_def():
    from BackEnd.utils.scouting_utils import enrich_projected_starting_five_season_avgs

    rows = [{"player_id": "p2", "ppg": 9}]
    enrich_projected_starting_five_season_avgs(rows, {"p2": {"PTS": 50, "GP": 0, "DEF_A": 0}})
    assert rows[0]["ppg"] == 0.0
    assert rows[0]["rpg"] == 0.0
    assert rows[0]["apg"] == 0.0
    assert rows[0]["def_pct"] == 0


def test_build_enriched_projected_starting_five():
    from BackEnd.utils.scouting_utils import build_enriched_projected_starting_five

    players = [
        _p("1", {"PG": 99}),
        _p("2", {"SG": 98}),
        _p("3", {"SF": 97}),
        _p("4", {"PF": 96}),
        _p("5", {"C": 95}),
    ]
    stats = {
        "1": {"GP": 2, "PTS": 20, "AST": 4, "TREB": 2, "DEF_S": 1, "DEF_A": 2},
    }
    rows = build_enriched_projected_starting_five(players, stats)
    assert len(rows) == 5
    by_pos = {r["position"]: r for r in rows}
    assert by_pos["PG"]["player_id"] == "1"
    assert by_pos["PG"]["ppg"] == 10.0
    assert by_pos["PG"]["def_pct"] == 50
    assert by_pos["SG"]["ppg"] == 0.0
