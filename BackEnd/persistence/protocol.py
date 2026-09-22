"""Persistence adapter protocol.

A franchise is a bounded document set keyed on ``franchise_id``. Read, write,
and delete of that set are first-class operations — not something reached
through raw collection handles. See desktop_migration_work_plan_v2.md §1.2.
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict


class FranchiseBundle(TypedDict, total=False):
    """Documents that belong to one franchise.

    ``franchise`` is the ``franchises`` row (or None). Every other key is a
    list of documents from that collection. Keys that carry ``franchise_id``
    with mixed ObjectId/str storage are included so a later hosted→local
    export does not have to rediscover the set.
    """

    franchise: dict[str, Any] | None
    franchise_team_data: list[dict[str, Any]]
    franchise_players_data: list[dict[str, Any]]
    franchise_recruits_data: list[dict[str, Any]]
    games: list[dict[str, Any]]
    press_conference_sessions: list[dict[str, Any]]
    training_sessions: list[dict[str, Any]]
    tournaments: list[dict[str, Any]]
    franchise_state: list[dict[str, Any]]
    eog_band_log: list[dict[str, Any]]


class PersistenceStore(Protocol):
    """Every collection handle the engine and franchise flows use, plus indexes."""

    client: Any
    db: Any
    DB_ENV: Any
    DB_NAME: str
    USING_MONGOMOCK: bool
    DB_ACCESS: str
    EOG_BAND_LOG_TTL_DAYS: int
    TUTORIAL_GAME_TTL_DAYS: int

    players_collection: Any
    teams_collection: Any
    games_collection: Any
    tournaments_collection: Any
    training_log_collection: Any
    franchise_state_collection: Any
    franchises_collection: Any
    franchise_team_data_collection: Any
    franchise_players_data_collection: Any
    franchise_recruits_data_collection: Any
    plays_collection: Any
    defenses_collection: Any
    fcp_skeletons_collection: Any
    hct_skeletons_collection: Any
    alpha_otps_collection: Any
    access_code_requests_collection: Any
    alpha_access_requests_collection: Any
    users_collection: Any
    password_reset_tokens_collection: Any
    press_conference_sessions_collection: Any
    community_highlights_collection: Any
    around_the_league_collection: Any
    alpha_feedback_collection: Any
    eog_band_log_collection: Any
    stripe_events_collection: Any

    def read_franchise(self, franchise_id: Any) -> FranchiseBundle: ...
    def write_franchise(self, franchise_id: Any, bundle: FranchiseBundle) -> None: ...
    def delete_franchise(self, franchise_id: Any) -> None: ...

    def ensure_ftd_index(self) -> None: ...
    def ensure_fpd_index(self) -> None: ...
    def ensure_frd_index(self) -> None: ...
    def ensure_games_franchise_index(self) -> None: ...
    def ensure_franchises_user_id_index(self) -> None: ...
    def ensure_alpha_access_requests_email_index(self) -> None: ...
    def ensure_users_username_index(self) -> None: ...
    def ensure_tutorial_game_ttl_index(self) -> None: ...
    def ensure_eog_band_log_index(self) -> None: ...
