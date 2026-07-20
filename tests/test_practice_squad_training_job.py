from types import SimpleNamespace
from datetime import datetime, timedelta

from BackEnd.practice_squad import manager
from BackEnd.models.game_manager import GameManager


def _ps_state(games):
    return {
        "initialized": True,
        "schedule": {"2": games},
        "teams": {},
        "scrubs_pools": {},
    }


def test_practice_squad_week_processes_one_game_and_persists(monkeypatch):
    games = [
        {"home_team_id": "h1", "away_team_id": "a1", "status": "scheduled"},
        {"home_team_id": "h2", "away_team_id": "a2", "status": "scheduled"},
    ]
    state = _ps_state(games)
    writes = []
    simulated = []

    monkeypatch.setattr(manager, "PS_ACTIVE_WEEKS", {2})
    monkeypatch.setattr(manager, "ensure_ps_season_stats_backfilled", lambda _fid, ps: ps)
    monkeypatch.setattr(manager, "_update_scrubs_rosters", lambda *_a, **_k: None)
    monkeypatch.setattr(manager, "_games_for_week", lambda *_a, **_k: games)
    monkeypatch.setattr(manager.franchise_players_data_collection, "find", lambda *_a, **_k: [])
    monkeypatch.setattr(manager.franchise_recruits_data_collection, "find", lambda *_a, **_k: [])
    monkeypatch.setattr(
        manager.db,
        "franchises",
        SimpleNamespace(update_one=lambda *a, **k: writes.append((a, k))),
    )

    def fake_sim(game, *_a, **_k):
        simulated.append(game["game_id"])
        game["status"] = "completed"
        return game

    monkeypatch.setattr(manager, "_sim_one_game", fake_sim)

    result = manager.run_practice_squad_week(
        "franchise-id", {"practice_squad": state}, 2, max_games=1
    )

    assert len(simulated) == 1
    assert games[0]["status"] == "completed"
    assert games[1]["status"] == "scheduled"
    assert result["training_job"]["status"] == "processing"
    assert result["training_job"]["completed_games"] == 1
    assert len(writes) == 2  # running checkpoint + completion checkpoint


def test_interrupted_running_game_restarts_from_tip(monkeypatch):
    games = [
        {
            "home_team_id": "h1",
            "away_team_id": "a1",
            "status": "running",
            "game_id": "stable-game-id",
            "attempts": 1,
        }
    ]
    state = _ps_state(games)

    monkeypatch.setattr(manager, "PS_ACTIVE_WEEKS", {2})
    monkeypatch.setattr(manager, "_running_game_is_stale", lambda _game: True)
    monkeypatch.setattr(manager, "ensure_ps_season_stats_backfilled", lambda _fid, ps: ps)
    monkeypatch.setattr(manager, "_update_scrubs_rosters", lambda *_a, **_k: None)
    monkeypatch.setattr(manager, "_games_for_week", lambda *_a, **_k: games)
    monkeypatch.setattr(manager.franchise_players_data_collection, "find", lambda *_a, **_k: [])
    monkeypatch.setattr(manager.franchise_recruits_data_collection, "find", lambda *_a, **_k: [])
    monkeypatch.setattr(
        manager.db,
        "franchises",
        SimpleNamespace(update_one=lambda *_a, **_k: None),
    )

    def fake_sim(game, *_a, **_k):
        assert game["game_id"] == "stable-game-id"
        game["status"] = "completed"
        return game

    monkeypatch.setattr(manager, "_sim_one_game", fake_sim)

    result = manager.run_practice_squad_week(
        "franchise-id", {"practice_squad": state}, 2, max_games=1
    )

    assert games[0]["attempts"] == 2
    assert games[0]["status"] == "completed"
    assert result["trained_week"] == 2
    assert result["training_job"]["status"] == "complete"


def test_fresh_running_game_is_not_started_by_a_second_poll(monkeypatch):
    games = [
        {
            "home_team_id": "h1",
            "away_team_id": "a1",
            "status": "running",
            "game_id": "active-game-id",
            "started_at": "2099-01-01T00:00:00Z",
        }
    ]
    state = _ps_state(games)
    monkeypatch.setattr(manager, "PS_ACTIVE_WEEKS", {2})
    monkeypatch.setattr(manager, "ensure_ps_season_stats_backfilled", lambda _fid, ps: ps)
    monkeypatch.setattr(manager, "_update_scrubs_rosters", lambda *_a, **_k: None)
    monkeypatch.setattr(manager, "_games_for_week", lambda *_a, **_k: games)
    monkeypatch.setattr(manager, "_running_game_is_stale", lambda _game: False)
    monkeypatch.setattr(manager.franchise_players_data_collection, "find", lambda *_a, **_k: [])
    monkeypatch.setattr(manager.franchise_recruits_data_collection, "find", lambda *_a, **_k: [])
    monkeypatch.setattr(
        manager.db,
        "franchises",
        SimpleNamespace(update_one=lambda *_a, **_k: None),
    )
    monkeypatch.setattr(
        manager,
        "_sim_one_game",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("duplicate start")),
    )

    result = manager.run_practice_squad_week(
        "franchise-id", {"practice_squad": state}, 2, max_games=1
    )

    assert result["training_job"]["status"] == "processing"
    assert games[0].get("attempts", 0) == 0


def test_running_game_timestamp_becomes_stale_after_lease():
    old = (datetime.utcnow() - timedelta(seconds=manager.PS_RUNNING_GAME_STALE_SECONDS + 1)).isoformat() + "Z"
    fresh = datetime.utcnow().isoformat() + "Z"

    assert manager._running_game_is_stale({"status": "running", "started_at": old}) is True
    assert manager._running_game_is_stale({"status": "running", "started_at": fresh}) is False


def test_failed_game_retries_twice_then_uses_terminal_fallback(monkeypatch):
    games = [
        {
            "home_team_id": "h1",
            "away_team_id": "a1",
            "status": "scheduled",
            "tier": 1,
        }
    ]
    state = _ps_state(games)
    game_writes = []

    monkeypatch.setattr(manager, "PS_ACTIVE_WEEKS", {2})
    monkeypatch.setattr(manager, "ensure_ps_season_stats_backfilled", lambda _fid, ps: ps)
    monkeypatch.setattr(manager, "_update_scrubs_rosters", lambda *_a, **_k: None)
    monkeypatch.setattr(manager, "_games_for_week", lambda *_a, **_k: games)
    monkeypatch.setattr(manager.franchise_players_data_collection, "find", lambda *_a, **_k: [])
    monkeypatch.setattr(manager.franchise_recruits_data_collection, "find", lambda *_a, **_k: [])
    monkeypatch.setattr(
        manager.db,
        "franchises",
        SimpleNamespace(update_one=lambda *_a, **_k: None),
    )
    monkeypatch.setattr(
        manager.db,
        "games",
        SimpleNamespace(update_one=lambda *a, **k: game_writes.append((a, k))),
    )
    monkeypatch.setattr(
        manager,
        "_sim_one_game",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("deterministic engine failure")),
    )

    franchise_doc = {"practice_squad": state}
    first = manager.run_practice_squad_week("franchise-id", franchise_doc, 2, max_games=1)
    franchise_doc["practice_squad"] = first
    assert games[0]["status"] == "retry_pending"
    assert first["training_job"]["status"] == "processing"
    assert first["training_job"]["completed_games"] == 0

    second = manager.run_practice_squad_week("franchise-id", franchise_doc, 2, max_games=1)
    franchise_doc["practice_squad"] = second
    assert games[0]["status"] == "retry_pending"
    assert games[0]["attempts"] == 2

    third = manager.run_practice_squad_week("franchise-id", franchise_doc, 2, max_games=1)
    assert games[0]["status"] == "fallback_completed"
    assert games[0]["attempts"] == manager.PS_FULL_ENGINE_MAX_ATTEMPTS
    assert games[0]["player_stats_status"] == "skipped_fallback_has_no_box_score"
    assert third["training_job"]["status"] == "complete"
    assert third["training_job"]["completed_games"] == 1
    assert third["trained_week"] == 2
    assert len(game_writes) == 1
    fallback_doc = game_writes[0][0][1]["$set"]
    assert fallback_doc["simulation_engine"] == "practice_squad_fallback"
    assert fallback_doc["full_engine_attempts"] == 3
    assert fallback_doc["player_stats_status"] == "skipped_fallback_has_no_box_score"


def test_fallback_score_is_deterministic(monkeypatch):
    writes = []
    monkeypatch.setattr(
        manager.db,
        "games",
        SimpleNamespace(update_one=lambda *a, **k: writes.append(a[1]["$set"])),
    )
    base = {
        "home_team_id": "h1",
        "away_team_id": "a1",
        "game_id": "stable-game-id",
        "attempts": 3,
        "tier": 1,
    }

    manager._complete_with_deterministic_fallback(
        dict(base), _ps_state([]), franchise_id_str="franchise-id", week=2, error=RuntimeError("x")
    )
    manager._complete_with_deterministic_fallback(
        dict(base), _ps_state([]), franchise_id_str="franchise-id", week=2, error=RuntimeError("x")
    )

    assert (writes[0]["home_score"], writes[0]["away_score"]) == (
        writes[1]["home_score"], writes[1]["away_score"]
    )
    assert writes[0]["home_score"] != writes[0]["away_score"]


def test_stats_rollup_failure_does_not_replay_completed_game(monkeypatch):
    roster = [{"player_id": f"p{i}", "source": "fpd"} for i in range(5)]
    state = _ps_state([])
    state["teams"] = {
        "h1": {"tier": 1, "display_name": "Home", "roster": roster},
        "a1": {"tier": 1, "display_name": "Away", "roster": roster},
    }
    game = {"home_team_id": "h1", "away_team_id": "a1", "status": "running", "game_id": "g1"}

    monkeypatch.setattr(
        manager,
        "run_ps_full_simulation",
        lambda **_k: (61, 70, {"score": {"Away": 61, "Home": 70}}),
    )
    monkeypatch.setattr(
        manager.db,
        "games",
        SimpleNamespace(update_one=lambda *_a, **_k: None),
    )
    monkeypatch.setattr(
        manager,
        "apply_ps_game_stats",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("rollup failed")),
    )

    result = manager._sim_one_game(game, state, 2, "franchise-id", {}, {})

    assert result["status"] == "completed"
    assert result["winner"] == "h1"
    assert result["player_stats_status"] == "rollup_failed_backfill_required"
    assert state["standings"]["1"]["h1"]["w"] == 1


def test_headless_foul_out_skips_interactive_timeout():
    gm = object.__new__(GameManager)
    gm.game_id = "ps-game-id"
    gm.game_state = {"_headless_simulation": True}
    gm.call_timeout = lambda **_kwargs: (_ for _ in ()).throw(
        AssertionError("interactive timeout must not run")
    )

    assert gm._handle_foul_out_timeout({"fouled_out": True}) is None
