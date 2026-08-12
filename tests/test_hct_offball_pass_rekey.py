"""HCT off-ball targets re-key when a new teammate becomes ball handler."""

from unittest.mock import patch

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
    off_targets, _ = _build_step_1_targets("PG", is_away_offense=False)
    target_by_alias = {
        "pos1": {"x": 51, "y": 11},
        "pos2": {"x": 52, "y": 22},
        "pos3": {"x": 53, "y": 33},
        "pos4": {"x": 54, "y": 44},
    }

    # Refresh deliberately rolls fresh spacing. Pin the target generator so the
    # test verifies SG's alias mapping rather than comparing independent RNG draws.
    with patch(
        "BackEnd.engine.dynamic_hct._pos_target",
        side_effect=lambda alias, _away: dict(target_by_alias[alias]),
    ):
        _refresh_hct_off_targets_for_bh(
            "SG", off_coords, off_targets, is_away_offense=False
        )

    assert off_targets["PG"] == target_by_alias["pos1"]
    assert off_targets["SF"] == target_by_alias["pos2"]
    assert off_targets["PF"] == target_by_alias["pos3"]
    assert off_targets["C"] == target_by_alias["pos4"]
