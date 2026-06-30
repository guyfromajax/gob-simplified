"""HCT off-ball targets re-key when a new teammate becomes ball handler."""

from BackEnd.engine.dynamic_hct import (
    _build_step_1_targets,
    _refresh_hct_off_targets_for_bh,
)


def test_refresh_keeps_new_bh_at_catch_spot():
    off_coords = {pos: {"x": 40, "y": 25} for pos in ("PG", "SG", "SF", "PF", "C")}
    off_coords["SG"] = {"x": 44, "y": 22}
    off_targets, _ = _build_step_1_targets("PG", is_away_offense=False)
    _refresh_hct_off_targets_for_bh("SG", off_coords, off_targets, is_away_offense=False)
    assert off_targets["SG"] == {"x": 44, "y": 22}


def test_refresh_rekeys_teammates_for_sg_alias_map():
    off_coords = {pos: {"x": 40, "y": 25} for pos in ("PG", "SG", "SF", "PF", "C")}
    off_coords["SG"] = {"x": 44, "y": 22}
    pg_bh_targets, _ = _build_step_1_targets("PG", is_away_offense=False)
    sg_bh_targets, _ = _build_step_1_targets("SG", is_away_offense=False)

    off_targets = dict(pg_bh_targets)
    _refresh_hct_off_targets_for_bh("SG", off_coords, off_targets, is_away_offense=False)

    for pos in ("PG", "SF", "PF", "C"):
        assert off_targets[pos] == sg_bh_targets[pos]
