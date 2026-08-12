"""Utility helpers for stats and other shared operations.

Keep this package initializer free of database imports. Scripts commonly import
pure helpers such as ``BackEnd.utils.position_ratings``; importing that module
must not initialize the application's ambient database connection first.
"""

_STAT_UPDATER_EXPORTS = {
    "apply_stats_from_summary",
    "finalize_game",
    "rollup_game_to_franchise",
    "backfill_franchise_player_stats",
    "recompute_tournament_leaders",
    "update_game_stats",
}

__all__ = [
    "apply_stats_from_summary",
    "finalize_game",
    "rollup_game_to_franchise",
    "backfill_franchise_player_stats",
    "recompute_tournament_leaders",
    "update_game_stats",
]


def __getattr__(name: str):
    """Lazily preserve the package-level stat-updater API."""
    if name in _STAT_UPDATER_EXPORTS:
        from . import stat_updater

        return getattr(stat_updater, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
