from types import SimpleNamespace

import BackEnd.db
from BackEnd.models.game_manager import GameManager
import BackEnd.utils.position_ratings


def test_non_persisting_game_manager_rating_refresh_has_no_database_write(monkeypatch):
    player = SimpleNamespace(
        player_id="player-1",
        attributes={"SC": 1},
        height="6'0\"",
        name="Offline Player",
        ratings={},
    )
    team = SimpleNamespace(
        franchise_id=None,
        is_synthetic_roster=False,
        get_all_players=lambda: [player],
    )
    game = GameManager.__new__(GameManager)
    game.home_team = team
    game.away_team = team
    game.persist_position_ratings = False

    monkeypatch.setattr(
        BackEnd.utils.position_ratings,
        "compute_position_ratings",
        lambda _doc: {"PG": 77},
    )
    monkeypatch.setattr(
        BackEnd.db.players_collection,
        "bulk_write",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected write")),
    )

    game._update_position_ratings()
    assert player.ratings == {"PG": 77}
