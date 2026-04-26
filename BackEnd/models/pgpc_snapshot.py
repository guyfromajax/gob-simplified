"""
PGPC (post-game press conference) snapshot types.

Specification: docs/To Do/PGPC_Snapshot_Schema.md
"""

from __future__ import annotations

from typing import Any, TypedDict


class TeamGameSummary(TypedDict, total=False):
    """One side of `game_doc["teams"]` after summarize_game_state."""

    name: str
    team_id: str
    score: int
    points_by_quarter: list[int]
    totals: dict[str, Any]
    attributes: dict[str, Any]
    box_score: dict[str, Any] | list[Any]


class GamePlayerRow(TypedDict, total=False):
    playerId: str
    team: str
    team_id: str
    pos: str | None
    stats: dict[str, Any]
    attributes: dict[str, Any]


class PGPCTierC(TypedDict, total=False):
    """Optional sim counters (assessment §C). Present only when engine persists them."""

    clutch_time_scoring: dict[str, Any]
    unanswered_run: dict[str, Any]
    first_blood: dict[str, Any]
    lead_changes: int
    game_winner_shot: dict[str, Any]
    early_foul_trouble: dict[str, Any]


class GameDocForPGPC(TypedDict, total=False):
    """Finalized game JSON subset used for PGPC qualification."""

    quarter: int
    is_final: bool
    home_team_id: str
    away_team_id: str
    teams: dict[str, TeamGameSummary]
    players: list[GamePlayerRow]
    opening_lineup: dict[str, list[str]]
    pgpc_tier_c: PGPCTierC


class FranchiseContextForPGPC(TypedDict, total=False):
    """Franchise / season context built at PGPC session creation (assessment §B)."""

    franchise_id: str
    user_id: str
    week: int
    user_team_id: str
    opponent_team_id: str
    user_won: bool
    margin_user_minus_opp: int
    overtime: bool
    winning_streak_after_game: int
    losing_streak_after_game: int
    user_natl_rank: int | None
    opponent_natl_rank: int | None
    opponent_is_conference_leader: bool
    season_series_vs_opponent: dict[str, int]
    first_game_of_season: bool
    last_regular_season_game: bool
    must_win_seeding: bool
    clinched_conference_seed: bool
    prestige_new_high: bool
    prestige_drop_streak: int
    entered_top_25_first_time: bool
    fell_out_top_25: bool
    team_chemistry_band: str
    above_500_first_time_season: bool
    fell_below_500: bool
    player_overall_rt: dict[str, float]


class PGPCInputBundle(TypedDict):
    game: GameDocForPGPC
    context: FranchiseContextForPGPC


__all__ = [
    "FranchiseContextForPGPC",
    "GameDocForPGPC",
    "GamePlayerRow",
    "PGPCInputBundle",
    "PGPCTierC",
    "TeamGameSummary",
]
