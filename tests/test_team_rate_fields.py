"""Team stat rates are attached after aggregation. No attempts stays null."""

from BackEnd.utils.team_stats_aggregator import attach_rate_fields


def test_attach_rate_fields_null_without_attempts():
    stats = {
        "FGM": 10,
        "FGA": 0,
        "3PTM": 4,
        "3PTA": 10,
        "FTM": 1,
        "FTA": 2,
        "SCR_S": 0,
        "SCR_A": 0,
        "DEF_S": 3,
        "DEF_A": 6,
    }
    attach_rate_fields(stats)
    assert stats["FG_PCT"] is None
    assert stats["TP_PCT"] == 40.0
    assert stats["FT_PCT"] == 50.0
    assert stats["SCR_PCT"] is None
    assert stats["DEF_PCT"] == 50.0
