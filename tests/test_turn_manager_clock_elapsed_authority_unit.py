from BackEnd.models.turn_manager import TurnManager


def _make_tm_with_ledger_elapsed(ledger_elapsed: int):
    tm = object.__new__(TurnManager)
    tm._derive_elapsed_from_clock_event_ledger = lambda _events: int(ledger_elapsed)
    tm._get_clock_reconciliation_tolerance_seconds = lambda _state: 0.1
    return tm


def test_elapsed_authority_legacy_keeps_time_elapsed():
    tm = _make_tm_with_ledger_elapsed(6)
    result = {"result_type": "MISS", "time_elapsed": 9, "clock_event_ledger": []}

    tm._attach_clock_elapsed_observe_reconciliation(
        result=result,
        game_state={},
        mode="observe",
        elapsed_authority="legacy",
    )

    assert result["time_elapsed"] == 9
    recon = result["uess_clock_reconciliation"]
    assert recon["elapsed_authority"] == "legacy"
    assert recon["ledger_elapsed_game_seconds"] == 6
    assert recon["legacy_elapsed_game_seconds"] == 9


def test_elapsed_authority_ledger_overrides_time_elapsed():
    tm = _make_tm_with_ledger_elapsed(6)
    result = {"result_type": "MISS", "time_elapsed": 9, "clock_event_ledger": []}

    tm._attach_clock_elapsed_observe_reconciliation(
        result=result,
        game_state={},
        mode="observe",
        elapsed_authority="ledger",
    )

    assert result["time_elapsed"] == 6
    recon = result["uess_clock_reconciliation"]
    assert recon["elapsed_authority"] == "ledger"
    assert recon["ledger_elapsed_game_seconds"] == 6
    assert recon["legacy_elapsed_game_seconds"] == 9


def test_elapsed_authority_default_resolves_to_ledger():
    tm = object.__new__(TurnManager)
    assert tm._resolve_clock_elapsed_authority({}) == "ledger"
    assert tm._resolve_clock_elapsed_authority({"uess_clock_elapsed_authority": None}) == "ledger"
    assert tm._resolve_clock_elapsed_authority({"uess_clock_elapsed_authority": "invalid"}) == "ledger"
