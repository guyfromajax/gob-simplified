from BackEnd.api.franchise_routes import _zero_stats_block
from BackEnd.constants import BOX_SCORE_KEYS


def test_zero_stats_block_includes_all_box_score_keys():
    zero_stats = _zero_stats_block()

    for key in BOX_SCORE_KEYS:
        assert key in zero_stats
        expected = [] if key == "Outlet_Score_List" else 0
        assert zero_stats[key] == expected

    assert zero_stats["Outlet_Score_List"] == []
