"""Quick Foul coord helpers — live player coords for fouler/victim selection."""

from types import SimpleNamespace

from BackEnd.engine.phase_resolution import (
    defender_coords_by_pos_from_lineup,
    grid_coords_from_player,
    pick_force_foul_defender_spot,
    select_defender_closest_to_victim,
)


def test_grid_coords_from_player_uses_live_coords():
    player = SimpleNamespace(coords={"x": 88, "y": 22})
    assert grid_coords_from_player(player) == {"x": 88.0, "y": 22.0}


def test_grid_coords_from_player_falls_back_to_overlay_map():
    player = SimpleNamespace(coords={})
    fallback = {"x": 12, "y": 31}
    assert grid_coords_from_player(player, fallback) == {"x": 12.0, "y": 31.0}


def test_select_defender_closest_uses_live_defender_coords():
    victim_coords = {"x": 10, "y": 25}
    def_lineup = {
        "PG": SimpleNamespace(player_id="d1", coords={"x": 11, "y": 25}),
        "C": SimpleNamespace(player_id="d2", coords={"x": 40, "y": 25}),
    }
    d_dest = defender_coords_by_pos_from_lineup(def_lineup)
    fouler = select_defender_closest_to_victim(victim_coords, def_lineup, d_dest)
    assert fouler.player_id == "d1"


def test_pick_force_foul_defender_spot_within_radius():
    import random

    from BackEnd.constants import QUICK_FOUL_APPROACH_RADIUS_GRID

    victim = {"x": 50, "y": 25}
    foul_player = SimpleNamespace(player_id="d1", coords={"x": 80, "y": 25})
    def_lineup = {"PG": foul_player}
    # Default radius is now QUICK_FOUL_APPROACH_RADIUS_GRID (4); sample many.
    for seed in range(50):
        spot = pick_force_foul_defender_spot(
            victim, foul_player, def_lineup, {"PG": {"x": 80, "y": 25}}, rng=random.Random(seed)
        )
        dist = ((spot["x"] - 50) ** 2 + (spot["y"] - 25) ** 2) ** 0.5
        assert dist <= QUICK_FOUL_APPROACH_RADIUS_GRID + 0.01
