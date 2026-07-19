from types import SimpleNamespace

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


def test_headless_foul_out_skips_interactive_timeout():
    gm = object.__new__(GameManager)
    gm.game_id = "ps-game-id"
    gm.game_state = {"_headless_simulation": True}
    gm.call_timeout = lambda **_kwargs: (_ for _ in ()).throw(
        AssertionError("interactive timeout must not run")
    )

    assert gm._handle_foul_out_timeout({"fouled_out": True}) is None
