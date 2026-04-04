from fastapi.testclient import TestClient

from BackEnd.api import api


client = TestClient(api.app)


class _DummyTeam:
    def __init__(self, name: str):
        self.name = name
        self.team_fouls = 0
        self.timeouts = 4
        self.strategy_calls = {}

    def get_team_game_stats(self):
        return {}

    def get_all_players(self):
        return []


class _ClockModeDummyGM:
    def __init__(self):
        self.home_team = _DummyTeam("Home")
        self.away_team = _DummyTeam("Away")
        self.offense_team = self.home_team
        self.defense_team = self.away_team
        self.score = {"Home": 0, "Away": 0}
        self.quarter = 1
        self.game_state = {
            "time_remaining": 600,
            "clock": "10:00",
            "offensive_state": "HCO",
            "free_throws_remaining": 0,
            "shot_clock_remaining": 30,
            "uess_clock_authority_mode": "observe",
            "uess_clock_elapsed_authority": "legacy",
            "uess_ownership_contract_mode": "warn",
            "uess_clock_recon_tolerance_seconds": 0.10,
        }
        self.turns = []

    def simulate_macro_turn(self):
        mode = str(self.game_state.get("uess_clock_authority_mode") or "observe").lower()
        elapsed_authority = str(
            self.game_state.get("uess_clock_elapsed_authority") or "legacy"
        ).lower()
        ownership_mode = str(
            self.game_state.get("uess_ownership_contract_mode") or "warn"
        ).lower()
        tolerance = float(self.game_state.get("uess_clock_recon_tolerance_seconds", 0.10))
        self.turns.append(
            {
                "result_type": "MISS",
                "text": "Clock mode propagation smoke",
                "uess_clock_authority_mode": mode,
                "uess_clock_elapsed_authority": elapsed_authority,
                "uess_ownership_contract_mode": ownership_mode,
                "uess_clock_reconciliation": {
                    "mode": mode,
                    "elapsed_authority": elapsed_authority,
                    "within_tolerance": True,
                    "delta_seconds": 0,
                    "tolerance_seconds": tolerance,
                },
                "uess_ownership_contract": {
                    "mode": ownership_mode,
                    "applicable": False,
                    "pass_event_count": 0,
                    "pass_receipt_valid_count": 0,
                    "pass_lifecycle_valid": True,
                    "terminal_owner_pos": None,
                },
            }
        )
        self.game_state["time_remaining"] = 594
        self.game_state["clock"] = "9:54"
        self.game_state["shot_clock_remaining"] = 24

    def get_box_score(self):
        return {}


class _BatchClockModeDummyGM(_ClockModeDummyGM):
    def simulate_macro_turn(self):
        mode = str(self.game_state.get("uess_clock_authority_mode") or "observe").lower()
        elapsed_authority = str(
            self.game_state.get("uess_clock_elapsed_authority") or "legacy"
        ).lower()
        ownership_mode = str(
            self.game_state.get("uess_ownership_contract_mode") or "warn"
        ).lower()
        turn_a = {
            "result_type": "MISS",
            "text": "Batch turn A",
            "clock_start": 600,
            "clock_end": 596,
            "shot_clock_start": 30,
            "shot_clock_end": 26,
            "real_time_elapsed_ms": 1400,
            "clock_event_ledger": [
                {"event_type": "game_clock_start", "game_clock_before": 600, "game_clock_after": 596},
                {"event_type": "game_clock_stop", "game_clock_before": 600, "game_clock_after": 596},
            ],
            "uess_clock_authority_mode": mode,
            "uess_clock_elapsed_authority": elapsed_authority,
            "uess_clock_elapsed_game_seconds": 4,
            "uess_clock_elapsed_legacy_game_seconds": 4,
            "uess_clock_elapsed_delta_seconds": 0,
            "uess_clock_elapsed_observe_within_tolerance": True,
            "uess_clock_reconciliation": {
                "mode": mode,
                "elapsed_authority": elapsed_authority,
                "within_tolerance": True,
            },
            "uess_ownership_contract": {
                "mode": ownership_mode,
                "applicable": False,
                "pass_lifecycle_valid": True,
            },
        }
        turn_b = {
            "result_type": "BASELINE_INBOUND",
            "text": "Batch turn B",
            "clock_start": 596,
            "clock_end": 596,
            "shot_clock_start": 30,
            "shot_clock_end": 30,
            "real_time_elapsed_ms": 0,
            "clock_event_ledger": [
                {"event_type": "game_clock_stop", "game_clock_before": 596, "game_clock_after": 596},
            ],
            "uess_clock_authority_mode": mode,
            "uess_clock_elapsed_authority": elapsed_authority,
            "uess_clock_elapsed_game_seconds": 0,
            "uess_clock_elapsed_legacy_game_seconds": 0,
            "uess_clock_elapsed_delta_seconds": 0,
            "uess_clock_elapsed_observe_within_tolerance": True,
            "uess_clock_reconciliation": {
                "mode": mode,
                "elapsed_authority": elapsed_authority,
                "within_tolerance": True,
            },
            "uess_ownership_contract_mode": ownership_mode,
            "uess_ownership_contract": {
                "mode": ownership_mode,
                "applicable": False,
                "pass_lifecycle_valid": True,
            },
        }
        self.turns.extend([turn_a, turn_b])
        self.game_state["time_remaining"] = 596
        self.game_state["clock"] = "9:56"
        self.game_state["shot_clock_remaining"] = 30


def test_simulate_turn_propagates_clock_mode_and_returns_it(monkeypatch):
    gm = _ClockModeDummyGM()
    monkeypatch.setattr(api, "ongoing_games", {"gid-clock-mode-prop": gm})

    response = client.post(
        "/api/simulate-turn",
        json={
            "game_id": "gid-clock-mode-prop",
            "uess_clock_authority_mode": "throw",
        },
    )

    assert response.status_code == 200
    body = response.json()
    turn = body["turn"]

    # API-level propagation: FE request mode updates backend game_state.
    assert gm.game_state["uess_clock_authority_mode"] == "throw"
    # Returned turn payload reflects the same authoritative mode.
    assert turn["uess_clock_authority_mode"] == "throw"
    assert turn["uess_clock_reconciliation"]["mode"] == "throw"


def test_simulate_turn_ignores_invalid_clock_mode(monkeypatch):
    gm = _ClockModeDummyGM()
    gm.game_state["uess_clock_authority_mode"] = "warn"
    monkeypatch.setattr(api, "ongoing_games", {"gid-clock-mode-invalid": gm})

    response = client.post(
        "/api/simulate-turn",
        json={
            "game_id": "gid-clock-mode-invalid",
            "uess_clock_authority_mode": "banana",
        },
    )

    assert response.status_code == 200
    body = response.json()
    turn = body["turn"]

    # Invalid override is ignored; existing mode is preserved.
    assert gm.game_state["uess_clock_authority_mode"] == "warn"
    assert turn["uess_clock_authority_mode"] == "warn"
    assert turn["uess_clock_reconciliation"]["mode"] == "warn"


def test_simulate_turn_propagates_recon_tolerance(monkeypatch):
    gm = _ClockModeDummyGM()
    monkeypatch.setattr(api, "ongoing_games", {"gid-clock-tol-prop": gm})

    response = client.post(
        "/api/simulate-turn",
        json={
            "game_id": "gid-clock-tol-prop",
            "uess_clock_recon_tolerance_seconds": 0.02,
        },
    )

    assert response.status_code == 200
    body = response.json()
    turn = body["turn"]

    assert gm.game_state["uess_clock_recon_tolerance_seconds"] == 0.02
    assert turn["uess_clock_reconciliation"]["tolerance_seconds"] == 0.02


def test_simulate_turn_ignores_invalid_recon_tolerance(monkeypatch):
    gm = _ClockModeDummyGM()
    gm.game_state["uess_clock_recon_tolerance_seconds"] = 0.25
    monkeypatch.setattr(api, "ongoing_games", {"gid-clock-tol-invalid": gm})

    response = client.post(
        "/api/simulate-turn",
        json={
            "game_id": "gid-clock-tol-invalid",
            "uess_clock_recon_tolerance_seconds": -1,
        },
    )

    assert response.status_code == 200
    body = response.json()
    turn = body["turn"]

    assert gm.game_state["uess_clock_recon_tolerance_seconds"] == 0.25
    assert turn["uess_clock_reconciliation"]["tolerance_seconds"] == 0.25


def test_simulate_turn_propagates_elapsed_authority(monkeypatch):
    gm = _ClockModeDummyGM()
    monkeypatch.setattr(api, "ongoing_games", {"gid-clock-elapsed-prop": gm})

    response = client.post(
        "/api/simulate-turn",
        json={
            "game_id": "gid-clock-elapsed-prop",
            "uess_clock_elapsed_authority": "ledger",
        },
    )

    assert response.status_code == 200
    body = response.json()
    turn = body["turn"]

    assert gm.game_state["uess_clock_elapsed_authority"] == "ledger"
    assert turn["uess_clock_elapsed_authority"] == "ledger"
    assert turn["uess_clock_reconciliation"]["elapsed_authority"] == "ledger"


def test_simulate_turn_ignores_invalid_elapsed_authority(monkeypatch):
    gm = _ClockModeDummyGM()
    gm.game_state["uess_clock_elapsed_authority"] = "legacy"
    monkeypatch.setattr(api, "ongoing_games", {"gid-clock-elapsed-invalid": gm})

    response = client.post(
        "/api/simulate-turn",
        json={
            "game_id": "gid-clock-elapsed-invalid",
            "uess_clock_elapsed_authority": "invalid",
        },
    )

    assert response.status_code == 200
    body = response.json()
    turn = body["turn"]

    assert gm.game_state["uess_clock_elapsed_authority"] == "legacy"
    assert turn["uess_clock_elapsed_authority"] == "legacy"
    assert turn["uess_clock_reconciliation"]["elapsed_authority"] == "legacy"


def test_simulate_turn_propagates_ownership_contract_mode(monkeypatch):
    gm = _ClockModeDummyGM()
    monkeypatch.setattr(api, "ongoing_games", {"gid-own-mode-prop": gm})

    response = client.post(
        "/api/simulate-turn",
        json={
            "game_id": "gid-own-mode-prop",
            "uess_ownership_contract_mode": "observe",
        },
    )

    assert response.status_code == 200
    body = response.json()
    turn = body["turn"]

    assert gm.game_state["uess_ownership_contract_mode"] == "observe"
    assert turn["uess_ownership_contract_mode"] == "observe"
    assert turn["uess_ownership_contract"]["mode"] == "observe"


def test_simulate_turn_ignores_invalid_ownership_contract_mode(monkeypatch):
    gm = _ClockModeDummyGM()
    gm.game_state["uess_ownership_contract_mode"] = "warn"
    monkeypatch.setattr(api, "ongoing_games", {"gid-own-mode-invalid": gm})

    response = client.post(
        "/api/simulate-turn",
        json={
            "game_id": "gid-own-mode-invalid",
            "uess_ownership_contract_mode": "banana",
        },
    )

    assert response.status_code == 200
    body = response.json()
    turn = body["turn"]

    assert gm.game_state["uess_ownership_contract_mode"] == "warn"
    assert turn["uess_ownership_contract_mode"] == "warn"
    assert turn["uess_ownership_contract"]["mode"] == "warn"


def test_simulate_turn_batch_wrapper_carries_clock_contract_shape(monkeypatch):
    gm = _BatchClockModeDummyGM()
    monkeypatch.setattr(api, "ongoing_games", {"gid-batch-contract-shape": gm})

    response = client.post("/api/simulate-turn", json={"game_id": "gid-batch-contract-shape"})
    assert response.status_code == 200
    turn = response.json()["turn"]

    assert turn["result_type"] == "BATCH"
    assert isinstance(turn.get("batch_turns"), list)
    assert len(turn["batch_turns"]) == 2

    # Wrapper mirrors first sub-turn contract for consistent shape.
    assert turn.get("clock_start") == 600
    assert turn.get("clock_end") == 596
    assert turn.get("shot_clock_start") == 30
    assert turn.get("shot_clock_end") == 26
    assert isinstance(turn.get("clock_event_ledger"), list)
    assert turn.get("uess_clock_authority_mode") == "observe"
    assert turn.get("uess_clock_elapsed_authority") in {"legacy", "ledger"}
    # Wrapper ownership mode should fall back to contract.mode when top-level mode is absent.
    assert turn.get("uess_ownership_contract_mode") == "warn"
    assert isinstance(turn.get("uess_ownership_contract"), dict)
    assert turn["uess_ownership_contract"].get("mode") == "warn"
