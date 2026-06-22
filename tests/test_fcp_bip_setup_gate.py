"""FCP BIP setup step uses a bespoke 4-of-5 offense advance gate."""

from BackEnd.models.player import Player
from BackEnd.utils.transition_bridge import build_bip_animation_steps

POSITIONS = ("PG", "SG", "SF", "PF", "C")


def _player(team_name, position):
    return Player(
        {
            "_id": f"{team_name}_{position}",
            "first_name": team_name,
            "last_name": position,
            "team": team_name,
            "attributes": {key: 50 for key in ("AG", "BH", "PS", "SH", "SC", "ID", "OD", "RB", "ST", "ND", "IQ", "FT", "NG", "CH")},
        }
    )


def _lineups():
    off = {pos: _player("Off", pos) for pos in POSITIONS}
    defn = {pos: _player("Def", pos) for pos in POSITIONS}
    return off, defn


def _ids(lineup):
    return {pos: str(lineup[pos].player_id) for pos in POSITIONS}


def _prior_and_setup(off, defn):
    ids = _ids(off)
    d_ids = _ids(defn)
    prior = {}
    for pos, pid in ids.items():
        prior[pid] = {"x": 80.0, "y": 10.0 + 8.0 * POSITIONS.index(pos)}
    for pos, pid in d_ids.items():
        prior[pid] = {"x": 70.0, "y": 12.0 + 7.0 * POSITIONS.index(pos)}

    setup = {
        ids["SF"]: {"x": 3.0, "y": 25.0},
        ids["PG"]: {"x": 15.0, "y": 20.0},
        ids["SG"]: {"x": 15.0, "y": 30.0},
        ids["PF"]: {"x": 50.0, "y": 25.0},
        ids["C"]: {"x": 65.0, "y": 25.0},
    }
    for pos, pid in d_ids.items():
        setup[pid] = {"x": 25.0 + POSITIONS.index(pos), "y": 25.0}
    return prior, setup, ids


def test_fcp_bip_step2_uses_four_of_five_offense_gate():
    off, defn = _lineups()
    prior, setup, ids = _prior_and_setup(off, defn)

    steps = build_bip_animation_steps(
        off_lineup=off,
        def_lineup=defn,
        prior_final_coords=prior,
        setup_coords=setup,
        sf_id=ids["SF"],
        pg_id=ids["PG"],
        ball_start_coord={"x": 6.0, "y": 25.0},
        fcp_setup=True,
        clock_remaining_at_start=300.0,
        shot_clock_remaining_at_start=20.0,
    )

    assert len(steps) == 4
    step2 = steps[1]
    trigger = step2["start"]["advance_trigger"]
    assert trigger["condition"] == "offense_players_reach_position"
    assert trigger["metadata"]["required_count"] == 4
    assert trigger["metadata"]["total_offense_count"] == 5
    assert trigger["metadata"]["reason"] == "bip_fcp_setup"


def test_non_fcp_bip_step2_still_gates_on_sf_and_pg():
    off, defn = _lineups()
    prior, setup, ids = _prior_and_setup(off, defn)

    steps = build_bip_animation_steps(
        off_lineup=off,
        def_lineup=defn,
        prior_final_coords=prior,
        setup_coords=setup,
        sf_id=ids["SF"],
        pg_id=ids["PG"],
        ball_start_coord={"x": 6.0, "y": 25.0},
        fcp_setup=False,
        clock_remaining_at_start=300.0,
        shot_clock_remaining_at_start=20.0,
    )

    step2 = steps[1]
    trigger = step2["start"]["advance_trigger"]
    assert trigger["condition"] == "player_reaches_position"
    assert trigger["metadata"]["reason"] == "bip_sf_to_inbound"
    assert trigger["metadata"]["target_player_id"] in {ids["SF"], ids["PG"]}


def test_fcp_bip_step3_sf_holds_while_others_continue_to_setup():
    off, defn = _lineups()
    prior, setup, ids = _prior_and_setup(off, defn)

    steps = build_bip_animation_steps(
        off_lineup=off,
        def_lineup=defn,
        prior_final_coords=prior,
        setup_coords=setup,
        sf_id=ids["SF"],
        pg_id=ids["PG"],
        ball_start_coord={"x": 6.0, "y": 25.0},
        fcp_setup=True,
        clock_remaining_at_start=300.0,
        shot_clock_remaining_at_start=20.0,
    )

    step3 = steps[2]
    sf_id = ids["SF"]
    actions = step3["start"]["action"]
    assert actions[sf_id] == "handle_ball"
    assert step3["start"]["archetype"][sf_id] == "stationary"

    movers = [
        pid
        for pid, action in actions.items()
        if pid != sf_id and action in ("cut", "guard_offball")
    ]
    assert len(movers) >= 1
    assert step3["start"]["advance_trigger"]["metadata"]["reason"] == "bip_fcp_passer_hold"


def test_non_fcp_bip_step3_freezes_all_players():
    off, defn = _lineups()
    prior, setup, ids = _prior_and_setup(off, defn)

    steps = build_bip_animation_steps(
        off_lineup=off,
        def_lineup=defn,
        prior_final_coords=prior,
        setup_coords=setup,
        sf_id=ids["SF"],
        pg_id=ids["PG"],
        ball_start_coord={"x": 6.0, "y": 25.0},
        fcp_setup=False,
        clock_remaining_at_start=300.0,
        shot_clock_remaining_at_start=20.0,
    )

    step3 = steps[2]
    for pid, action in step3["start"]["action"].items():
        if pid == ids["SF"]:
            assert action == "handle_ball"
        else:
            assert action == "stationary"
    assert all(arch == "stationary" for arch in step3["start"]["archetype"].values())
