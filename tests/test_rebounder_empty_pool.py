import logging
from BackEnd.utils.shared import choose_rebounder, resolve_offensive_rebound
from tests.test_utils import build_mock_game


def test_choose_rebounder_empty_pool_returns_none_and_no_indexerror(caplog):
    rebounders = {"offense": {}, "defense": {}}
    with caplog.at_level(logging.WARNING):
        result = choose_rebounder(rebounders, "offense")
    assert result is None
    assert "empty pool" in caplog.text

    game = build_mock_game()
    event = resolve_offensive_rebound(game, result)
    assert event["event_type"] == "DEFENSIVE_REBOUND"
    assert event["possession_flips"] is True
