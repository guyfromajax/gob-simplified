"""
FTE Tutorial Game — engine state injection orchestrator.

Wires the values from `_documentation_master/projects/fte_inject_state.md`
into a freshly created GameManager so the tutorial boots into
"Q4, 4:00 remaining, 60-60, post-timeout SIP."

Public entry points:
- prepare_tutorial_team_attributes(user_team_side) → (home_attrs, away_attrs)
- TUTORIAL_STRATEGY_SETTINGS → dict used for both home and away strategy_settings
- apply_tutorial_initial_state(gm, summary, user_team_side) → mutates both

Called from BackEnd/api/api.py::init_game() when mode == "tutorial". All
other modes (single, franchise, tournament) follow their existing code
paths untouched.

Companion docs:
- fte_inject_state.md §1-§6 — every value sourced here
- fte_implementation_plan.md §4.2-§4.4
"""

from __future__ import annotations

import logging
from typing import Optional

from BackEnd.data.tutorial_rosters import (
    ROSTER_SLOTS,
    rank_roster,
    stat_overlay_for,
)
from BackEnd.models.team_manager import TeamManager


logger = logging.getLogger(__name__)


# fte_inject_state.md §3 — opponent nerf via forced make/miss shot_threshold.
USER_SHOT_THRESHOLD = 10
COMPUTER_SHOT_THRESHOLD = 210


# fte_inject_state.md §2 — strategy_settings: all keys = 2 except fc_press / hc_trap = 1.
TUTORIAL_STRATEGY_SETTINGS = {
    "offense": 2,
    "inside": 2,
    "attack": 2,
    "outside": 2,
    "aggression": 2,
    "fast_breaks": 2,
    "defense": 2,
    "rebounding": 2,
    "hc_trap": 1,
    "fc_press": 1,
    "tempo": 2,
}


# fte_inject_state.md §1 — clock and score at boot.
TUTORIAL_QUARTER = 4
TUTORIAL_TIME_REMAINING = 240  # 4:00
TUTORIAL_CLOCK_DISPLAY = "4:00"
TUTORIAL_SHOT_CLOCK = 30
TUTORIAL_SCORE = 60  # each team
TUTORIAL_OFFENSIVE_STATE = "HCO"
TUTORIAL_DEFENSE_PLAYCALL = ""  # empty → engine picks


# fte_inject_state.md §2 — per-team mid-game state.
TUTORIAL_TEAM_FOULS = 3
TUTORIAL_TIMEOUTS_REMAINING = 1
TUTORIAL_HOME_CROWD_FACTOR = 4


# fte_inject_state.md §4 — per-quarter score breakdown summing to 60 each.
TUTORIAL_POINTS_BY_QUARTER_USER = [14, 18, 28, 0]
TUTORIAL_POINTS_BY_QUARTER_OPPONENT = [18, 15, 27, 0]


# fte_inject_state.md §6 — per-player runtime attributes.
TUTORIAL_NG_AT_BOOT = 0.95


def _side_for(user_team_side: str, team_role: str) -> str:
    """Return 'user' or 'computer' for a team given which side the user controls.

    user_team_side: "home" | "away"
    team_role:      "home" | "away"
    """
    if user_team_side == team_role:
        return "user"
    return "computer"


def prepare_tutorial_team_attributes(user_team_side: Optional[str]):
    """Return (home_attrs, away_attrs) with shot_threshold pinned per-side.

    All other team_attributes are randomized via the standard
    TeamManager.init_team_attributes path; only shot_threshold is overridden.
    """
    home_side = _side_for(user_team_side or "home", "home")
    away_side = _side_for(user_team_side or "home", "away")
    home_attrs = TeamManager.init_team_attributes(
        mode="tutorial",
        shot_threshold_override=(USER_SHOT_THRESHOLD if home_side == "user" else COMPUTER_SHOT_THRESHOLD),
    )
    away_attrs = TeamManager.init_team_attributes(
        mode="tutorial",
        shot_threshold_override=(USER_SHOT_THRESHOLD if away_side == "user" else COMPUTER_SHOT_THRESHOLD),
    )
    return home_attrs, away_attrs


def _apply_stat_overlay_to_team(team, side: str) -> None:
    """Rank `team.players` by position_ratings, then apply slot stat overlays.

    Mutates each player's stats["game"] and metadata["fouls"] in place.
    Also sets NG (energy) to the tutorial boot value for every player.
    """
    if not getattr(team, "players", None):
        logger.warning("[TUTORIAL] team %s has no players to overlay", getattr(team, "name", "?"))
        return

    # Build the (slot, player_id) ranking list from the team's roster.
    ranking_payload = []
    for pid, player in team.players.items():
        ranking_payload.append({
            "player_id": pid,
            "position_ratings": dict(getattr(player, "position_ratings", {}) or {}),
        })
    ranked = rank_roster(ranking_payload)

    for slot, pid in ranked:
        player = team.players.get(pid)
        if not player:
            continue
        overlay = stat_overlay_for(slot, side)
        if not overlay:
            continue
        if not hasattr(player, "stats") or not isinstance(player.stats, dict):
            player.stats = {}
        if "game" not in player.stats or not isinstance(player.stats["game"], dict):
            player.stats["game"] = {}
        for key, value in overlay.items():
            player.stats["game"][key] = value

        # Mirror personal fouls onto player.metadata["fouls"] (does not reset per Q).
        if "F" in overlay:
            existing_meta = getattr(player, "metadata", None) or {}
            try:
                player.metadata = dict(existing_meta)
                player.metadata["fouls"] = int(overlay["F"])
            except Exception:
                # Player implementation may not allow attribute assignment; skip silently.
                pass

    # Set NG (energy) on every player on this team.
    for player in team.players.values():
        try:
            player.NG = TUTORIAL_NG_AT_BOOT
            if hasattr(player, "anchor_NG"):
                player.anchor_NG = TUTORIAL_NG_AT_BOOT
        except Exception:
            pass


def apply_tutorial_initial_state(
    gm,
    summary: dict,
    user_team_side: Optional[str],
) -> None:
    """Mutate both `gm` and `summary` to boot at Q4, 4:00 remaining, 60-60.

    Must be called AFTER GameManager is constructed and AFTER
    _initialize_game_stats() has run (otherwise stat overlays get zeroed).

    Args:
        gm: GameManager instance from init_game.
        summary: the summarize_game_state(gm) dict that will be persisted.
        user_team_side: "home" or "away".
    """
    home_team = gm.home_team
    away_team = gm.away_team
    home_name = home_team.name
    away_name = away_team.name

    # --- Clock + score ---
    gm.score = {home_name: TUTORIAL_SCORE, away_name: TUTORIAL_SCORE}
    gm.quarter = TUTORIAL_QUARTER
    gm.game_state["quarter"] = TUTORIAL_QUARTER
    gm.game_state["time_remaining"] = TUTORIAL_TIME_REMAINING
    gm.game_state["clock"] = TUTORIAL_CLOCK_DISPLAY
    gm.game_state["shot_clock_remaining"] = TUTORIAL_SHOT_CLOCK

    # --- Possession (user has the ball coming out of timeout) ---
    if user_team_side == "away":
        gm.offense_team = away_team
        gm.defense_team = home_team
    else:
        gm.offense_team = home_team
        gm.defense_team = away_team
    gm.game_state["offense_team"] = gm.offense_team.name
    gm.game_state["defense_team"] = gm.defense_team.name
    gm.game_state["offensive_state"] = TUTORIAL_OFFENSIVE_STATE
    gm.game_state["defense_playcall"] = TUTORIAL_DEFENSE_PLAYCALL

    # --- Per-team mid-game state ---
    for team in (home_team, away_team):
        try:
            team.team_fouls = TUTORIAL_TEAM_FOULS
            team.timeouts = TUTORIAL_TIMEOUTS_REMAINING
        except Exception as e:
            logger.warning("[TUTORIAL] could not set team_fouls/timeouts on %s: %s", team.name, e)

    gm.game_state["team_fouls"] = {
        home_name: TUTORIAL_TEAM_FOULS,
        away_name: TUTORIAL_TEAM_FOULS,
    }
    gm.game_state["team_timeouts"] = {
        home_name: TUTORIAL_TIMEOUTS_REMAINING,
        away_name: TUTORIAL_TIMEOUTS_REMAINING,
    }

    # --- Per-quarter score breakdown (Q1, Q2, Q3 sum to 60 each; Q4 = 0) ---
    user_pbq = list(TUTORIAL_POINTS_BY_QUARTER_USER)
    opp_pbq = list(TUTORIAL_POINTS_BY_QUARTER_OPPONENT)
    if user_team_side == "away":
        home_pbq, away_pbq = opp_pbq, user_pbq
    else:
        home_pbq, away_pbq = user_pbq, opp_pbq
    try:
        home_team.points_by_quarter = list(home_pbq)
        away_team.points_by_quarter = list(away_pbq)
    except Exception as e:
        logger.warning("[TUTORIAL] could not set points_by_quarter: %s", e)

    # --- Home crowd factor (user is home; gets the boost) ---
    gm.game_state["home_crowd_factor"] = TUTORIAL_HOME_CROWD_FACTOR

    # --- Player stat overlays + NG energy ---
    _apply_stat_overlay_to_team(home_team, _side_for(user_team_side or "home", "home"))
    _apply_stat_overlay_to_team(away_team, _side_for(user_team_side or "home", "away"))

    # --- game_stats_initialized: prevent engine from zeroing fabricated stats on first turn ---
    gm.game_state["game_stats_initialized"] = True

    # --- Seed timeout-resume state so first turn emits as SIP ---
    # The simulate-quarter path on the client must send resume_from_timeout=true
    # on the first turn request; that combined with these server-side fields
    # routes through BackEnd/main.py:372 (the SIDE_INBOUND branch).
    gm.game_state["timeout_next_play_type"] = "SIDE_INBOUND"
    gm.game_state["timeout_offense_team_id"] = gm.offense_team.team_id

    # --- Mirror everything back into the summary that gets persisted to mongo ---
    summary["quarter"] = TUTORIAL_QUARTER
    summary["score"] = {home_name: TUTORIAL_SCORE, away_name: TUTORIAL_SCORE}
    if isinstance(summary.get("home_team"), dict):
        summary["home_team"]["score"] = TUTORIAL_SCORE
        summary["home_team"]["points_by_quarter"] = list(home_pbq)
        summary["home_team"]["team_fouls"] = TUTORIAL_TEAM_FOULS
        summary["home_team"]["timeouts"] = TUTORIAL_TIMEOUTS_REMAINING
    if isinstance(summary.get("away_team"), dict):
        summary["away_team"]["score"] = TUTORIAL_SCORE
        summary["away_team"]["points_by_quarter"] = list(away_pbq)
        summary["away_team"]["team_fouls"] = TUTORIAL_TEAM_FOULS
        summary["away_team"]["timeouts"] = TUTORIAL_TIMEOUTS_REMAINING
    summary["game_stats_initialized"] = True

    # game_state is typically nested under summary; sync if present.
    if isinstance(summary.get("game_state"), dict):
        gs = summary["game_state"]
        gs["quarter"] = TUTORIAL_QUARTER
        gs["time_remaining"] = TUTORIAL_TIME_REMAINING
        gs["clock"] = TUTORIAL_CLOCK_DISPLAY
        gs["shot_clock_remaining"] = TUTORIAL_SHOT_CLOCK
        gs["offense_team"] = gm.offense_team.name
        gs["defense_team"] = gm.defense_team.name
        gs["offensive_state"] = TUTORIAL_OFFENSIVE_STATE
        gs["defense_playcall"] = TUTORIAL_DEFENSE_PLAYCALL
        gs["team_fouls"] = {home_name: TUTORIAL_TEAM_FOULS, away_name: TUTORIAL_TEAM_FOULS}
        gs["team_timeouts"] = {home_name: TUTORIAL_TIMEOUTS_REMAINING, away_name: TUTORIAL_TIMEOUTS_REMAINING}
        gs["home_crowd_factor"] = TUTORIAL_HOME_CROWD_FACTOR
        gs["game_stats_initialized"] = True
        gs["timeout_next_play_type"] = "SIDE_INBOUND"
        gs["timeout_offense_team_id"] = gm.offense_team.team_id

    logger.warning(
        "✅ [TUTORIAL] applied initial state: Q%d %s, %s vs %s, offense=%s, user_side=%s",
        TUTORIAL_QUARTER,
        TUTORIAL_CLOCK_DISPLAY,
        home_name,
        away_name,
        gm.offense_team.name,
        user_team_side,
    )
