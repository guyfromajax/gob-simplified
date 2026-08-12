"""Tests for the projected starting five shown on the FCC Scouting Report tab, the team
roster pages and the training report.

Selection is delegated to ``db_utils.projected_starting_five_from_payload`` — the same
eligibility waterfall, exact max-weight DP and energy-aware objective the game runs at tip.
The parity tests at the bottom are the ones that matter; the display-shape tests above them
predate the change and still hold.
"""
from BackEnd.utils.scouting_utils import compute_projected_starting_five


def _p(pid, ratings: dict, attrs=None, potential_rt=None):
    base_attrs = {k: 50 for k in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]}
    if attrs:
        base_attrs.update(attrs)
    player = {
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
    if potential_rt is not None:
        player["potential_rt_ratcheted"] = potential_rt
    return player


def test_assigns_each_player_once():
    """Descending RT specialists each get their slot; nobody is seated twice."""
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


def test_two_slot_star_takes_the_slot_that_maximises_the_pair():
    """P1 rates at both PG and SG, but P2 can only play SG — so seating P1 at PG is the
    higher-scoring pair, not merely the greedier first pick."""
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


def test_projected_five_preserves_ratcheted_potential_rt():
    row = compute_projected_starting_five(
        [_p("1", {"PG": 36}, potential_rt=61)]
    )
    assert row[0]["rt"] == 36.0
    assert row[0]["potential_rt_ratcheted"] == 61


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


# ── Parity with the floor ────────────────────────────────────────────────────────────────
# The projected five must be the five autoset would actually field at tip. These guard the
# three properties that make that true: same selector, same NG gate, and no sim-RNG coupling.

def _game_autoset_at_tip(players_payload):
    """Run the GAME's selection path over the same roster, exactly as tip-off does."""
    from BackEnd.models.player import Player
    from BackEnd.utils.db_utils import (
        PREGAME_STATE,
        _waterfall_eligibility,
        build_unified_autoset_lineup_from_eligible,
        is_player_eligible_for_lineup,
    )

    objs = [Player({**dict(p), "player_id": str(p["_id"])}) for p in players_payload]
    eligible = []
    for ng_min, foul_limits in _waterfall_eligibility(PREGAME_STATE):
        eligible = [
            o for o in objs
            if is_player_eligible_for_lineup(
                o, PREGAME_STATE, ng_min=ng_min, foul_limits_by_quarter=foul_limits
            )
        ]
        if len(eligible) >= 5:
            break
    seated = build_unified_autoset_lineup_from_eligible(eligible, 15.0)
    return {pos: pl.player_id for pos, pl in seated.items()}


def _deep_roster():
    """Eight players, distinct ratings, no ties to resolve."""
    return [
        _p("1", {"PG": 91, "SG": 84, "SF": 60, "PF": 40, "C": 30}),
        _p("2", {"PG": 88, "SG": 79, "SF": 55, "PF": 38, "C": 28}),
        _p("3", {"PG": 52, "SG": 86, "SF": 81, "PF": 44, "C": 33}),
        _p("4", {"PG": 35, "SG": 50, "SF": 83, "PF": 77, "C": 58}),
        _p("5", {"PG": 30, "SG": 42, "SF": 66, "PF": 85, "C": 74}),
        _p("6", {"PG": 25, "SG": 36, "SF": 48, "PF": 71, "C": 87}),
        _p("7", {"PG": 47, "SG": 45, "SF": 43, "PF": 41, "C": 39}),
        _p("8", {"PG": 33, "SG": 31, "SF": 29, "PF": 27, "C": 26}),
    ]


def test_projection_matches_game_autoset_at_tip():
    """The whole point: display and floor agree, slot for slot."""
    from BackEnd.utils.db_utils import projected_starting_five_from_payload

    players = _deep_roster()
    assert projected_starting_five_from_payload(players) == _game_autoset_at_tip(players)


def test_projection_beats_greedy_where_greedy_fails():
    """The canonical assignment counterexample: a star's best slot is not always his slot.

    Greedy takes the globally-best pair first (P1 at PG, 91) and strands P2 at SG (12).
    The exact solve seats P1 at SG and P2 at PG for a far better pair.
    """
    from BackEnd.utils.db_utils import projected_starting_five_from_payload

    players = [
        _p("1", {"PG": 91, "SG": 89, "SF": 20, "PF": 15, "C": 10}),
        _p("2", {"PG": 87, "SG": 12, "SF": 18, "PF": 14, "C": 11}),
        _p("3", {"PG": 20, "SG": 22, "SF": 70, "PF": 25, "C": 20}),
        _p("4", {"PG": 18, "SG": 20, "SF": 30, "PF": 68, "C": 35}),
        _p("5", {"PG": 15, "SG": 18, "SF": 25, "PF": 33, "C": 66}),
    ]
    seated = projected_starting_five_from_payload(players)
    assert seated["PG"] == "2"
    assert seated["SG"] == "1"


def test_tired_player_drops_out_of_projection():
    """NG below the 0.80 tip gate means autoset will not field him, so neither do we."""
    from BackEnd.utils.db_utils import projected_starting_five_from_payload

    players = _deep_roster()
    for p in players:
        if p["_id"] == "1":
            p["attributes"]["NG"] = 0.5      # training left the best PG gassed

    seated = projected_starting_five_from_payload(players)
    assert "1" not in seated.values()
    assert seated == _game_autoset_at_tip(players)


def test_projection_is_deterministic_and_draws_no_sim_rng():
    """Display runs on page loads, outside the sim. It must not touch the sim stream, and it
    must not flip between loads."""
    from BackEnd.utils.db_utils import projected_starting_five_from_payload
    from BackEnd.utils.sim_random import sim_rng

    players = _deep_roster()
    before = sim_rng.getstate()
    first = projected_starting_five_from_payload(players)
    assert sim_rng.getstate() == before, "projection consumed sim RNG draws"

    for _ in range(10):
        assert projected_starting_five_from_payload(players) == first


def test_short_roster_renders_a_partial_five():
    """A display surface must still render; it must not raise the way autoset does."""
    from BackEnd.utils.db_utils import projected_starting_five_from_payload

    players = [_p("1", {"PG": 80}), _p("2", {"SG": 78}), _p("3", {"SF": 76})]
    seated = projected_starting_five_from_payload(players)
    assert len(seated) == 3
    assert len(compute_projected_starting_five(players)) == 3
