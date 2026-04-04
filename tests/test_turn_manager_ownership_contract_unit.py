from BackEnd.models.turn_manager import TurnManager


def _make_tm():
    return object.__new__(TurnManager)


def test_ownership_contract_marks_valid_pass_lifecycle_with_receipt():
    tm = _make_tm()
    result = {
        "result_type": "HCO",
        "next_play_type": "HCO",
        "steps": [
            {"events": [{"type": "pass", "by": "PG", "to": "SG"}]},
            {"events": []},
        ],
        "ball_owner_by_step": ["PG", "SG"],
    }

    tm._attach_uess_ownership_contract(result)
    contract = result["uess_ownership_contract"]

    assert result["uess_ownership_contract_mode"] == "warn"
    assert contract["applicable"] is True
    assert contract["pass_event_count"] == 1
    assert contract["pass_receipt_valid_count"] == 1
    assert contract["pass_lifecycle_valid"] is True
    assert contract["terminal_owner_pos"] == "SG"
    assert contract["mode"] == "warn"


def test_ownership_contract_marks_invalid_when_pass_receipt_missing():
    tm = _make_tm()
    result = {
        "result_type": "HCO",
        "next_play_type": "HCO",
        "steps": [
            {"events": [{"type": "pass", "by": "PG", "to": "SG"}]},
            {"events": []},
        ],
        "ball_owner_by_step": ["PG", "PG"],
    }

    tm._attach_uess_ownership_contract(result)
    contract = result["uess_ownership_contract"]

    assert result["uess_ownership_contract_mode"] == "warn"
    assert contract["applicable"] is True
    assert contract["pass_event_count"] == 1
    assert contract["pass_receipt_valid_count"] == 0
    assert contract["pass_lifecycle_valid"] is False
    assert contract["terminal_owner_pos"] == "PG"
    assert contract["mode"] == "warn"


def test_ownership_contract_non_applicable_without_steps():
    tm = _make_tm()
    result = {
        "result_type": "TIMEOUT",
        "next_play_type": "SIDE_INBOUND",
    }

    tm._attach_uess_ownership_contract(result)
    contract = result["uess_ownership_contract"]

    assert result["uess_ownership_contract_mode"] == "warn"
    assert contract["applicable"] is False
    assert contract["pass_event_count"] == 0
    assert contract["pass_lifecycle_valid"] is True
    assert contract["terminal_owner_pos"] is None
    assert contract["mode"] == "warn"


def test_ownership_contract_warn_mode_emits_warning(caplog):
    tm = _make_tm()
    tm.game = type("G", (), {"game_state": {"uess_ownership_contract_mode": "warn"}})()
    result = {
        "result_type": "HCO",
        "next_play_type": "HCO",
        "steps": [{"events": [{"type": "pass", "by": "PG", "to": "SG"}]}],
        "ball_owner_by_step": ["PG"],
    }

    with caplog.at_level("WARNING"):
        tm._attach_uess_ownership_contract(result)

    assert any("UESS ownership contract" in rec.message for rec in caplog.records)


def test_ownership_contract_observe_mode_suppresses_warning(caplog):
    tm = _make_tm()
    tm.game = type("G", (), {"game_state": {"uess_ownership_contract_mode": "observe"}})()
    result = {
        "result_type": "HCO",
        "next_play_type": "HCO",
        "steps": [{"events": [{"type": "pass", "by": "PG", "to": "SG"}]}],
        "ball_owner_by_step": ["PG"],
    }

    with caplog.at_level("WARNING"):
        tm._attach_uess_ownership_contract(result)

    assert not any("UESS ownership contract" in rec.message for rec in caplog.records)


def test_ownership_contract_tracks_multiple_passes_and_partial_receipts():
    tm = _make_tm()
    result = {
        "result_type": "HCO",
        "next_play_type": "HCO",
        "steps": [
            {"events": [{"type": "pass", "by": "PG", "to": "SG"}]},
            {"events": [{"type": "pass", "by": "SG", "to": "SF"}]},
            {"events": []},
        ],
        "ball_owner_by_step": ["PG", "SG", "SG"],
    }

    tm._attach_uess_ownership_contract(result)
    contract = result["uess_ownership_contract"]

    assert contract["applicable"] is True
    assert contract["pass_event_count"] == 2
    assert contract["pass_receipt_valid_count"] == 1
    assert contract["pass_lifecycle_valid"] is False
    assert contract["terminal_owner_pos"] == "SG"
    assert len(contract.get("pass_events", [])) == 2


def test_ownership_contract_marks_non_applicable_when_owner_sequence_missing():
    tm = _make_tm()
    result = {
        "result_type": "SIDE_INBOUND",
        "next_play_type": "HCO",
        "steps": [{"events": [{"type": "pass", "by": "SF", "to": "PG"}]}],
        "ball_owner_by_step": None,
    }

    tm._attach_uess_ownership_contract(result)
    contract = result["uess_ownership_contract"]

    assert contract["applicable"] is False
    assert contract["pass_event_count"] == 1
    assert contract["pass_receipt_valid_count"] == 0
    assert contract["pass_lifecycle_valid"] is False


def test_ownership_contract_side_inbound_receipt_path_is_valid():
    tm = _make_tm()
    result = {
        "result_type": "SIDE_INBOUND",
        "next_play_type": "HCO",
        "steps": [{"events": [{"type": "pass", "by": "SF", "to": "PG"}]}],
        "ball_owner_by_step": ["SF", "PG"],
    }

    tm._attach_uess_ownership_contract(result)
    contract = result["uess_ownership_contract"]

    assert contract["applicable"] is True
    assert contract["pass_event_count"] == 1
    assert contract["pass_receipt_valid_count"] == 1
    assert contract["pass_lifecycle_valid"] is True
    assert contract["terminal_owner_pos"] == "PG"
