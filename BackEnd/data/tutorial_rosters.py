"""
FTE Tutorial Game — universal player stat templates + roster ranking helpers.

Two stat templates only:
- USER_TEAM_STAT_TEMPLATE: applied to whichever team the user picked.
- COMPUTER_TEAM_STAT_TEMPLATE: applied to the opponent (Xavien, or South Lancaster
  if the user picks Xavien).

Each template maps a roster slot identifier to a partial player.stats["game"]
dict. The values pre-populate Q1-Q3 stats so the engine boots at 60-60 with
believable per-player stat lines on the set-lineup screen and in-game scoreboard.

Stat keys here intentionally match BackEnd.constants.BOX_SCORE_KEYS. Keys not
listed (DEF_A, FB_PTS, etc.) retain their zero defaults.

Source of truth: _documentation_master/projects/fte_inject_state.md §5.
Invariants verified at import time: PTS sum = 60, MIN sum = 140, per-player
PTS = 2·FGM + 3PTM + FTM, REB = OREB + DREB.
"""

from typing import Iterable, List, Tuple


# Roster slot identifiers in stack-rank order. Starters first, then bench
# ranked by best-position rating (see rank_roster()).
ROSTER_SLOTS: List[str] = [
    "starting_pg",
    "starting_sg",
    "starting_sf",
    "starting_pf",
    "starting_c",
    "backup_1",
    "backup_2",
    "backup_3",
    "backup_4",
    "backup_5",
    "backup_6",
    "backup_7",
]

# Starting slot -> position string used to index a player's position_ratings dict.
STARTER_POSITION = {
    "starting_pg": "PG",
    "starting_sg": "SG",
    "starting_sf": "SF",
    "starting_pf": "PF",
    "starting_c": "C",
}


def _row(pts, oreb, dreb, ast, stl, blk, to, fgm, fga, tptm, tpta, ftm, fta, f, min_):
    """Build a single stat-line dict matching BOX_SCORE_KEYS naming."""
    return {
        "PTS": pts,
        "OREB": oreb,
        "DREB": dreb,
        "REB": oreb + dreb,
        "AST": ast,
        "STL": stl,
        "BLK": blk,
        "TO": to,
        "FGM": fgm,
        "FGA": fga,
        "3PTM": tptm,
        "3PTA": tpta,
        "FTM": ftm,
        "FTA": fta,
        "F": f,
        "MIN": min_,
    }


# fte_inject_state.md §5 — "User Team Player Stats" block.
# Invariants: PTS sum = 60, MIN sum = 140.
USER_TEAM_STAT_TEMPLATE = {
    #                    PTS OREB DREB AST STL BLK TO  FGM FGA  3PTM 3PTA  FTM FTA  F  MIN
    "starting_pg": _row(   9,   0,   1,  6,  3,  0,  8,  4, 10,    1,   3,   0,  2, 2,  21),
    "starting_sg": _row(  14,   1,   4,  3,  6,  2,  0,  5, 11,    0,   4,   4,  4, 1,  24),
    "starting_sf": _row(  17,   2,   6,  3,  0,  0,  3,  6,  8,    1,   1,   4,  5, 2,  20),
    "starting_pf": _row(   2,   5,   4,  0,  0,  0,  0,  1,  5,    0,   1,   0,  0, 0,  21),
    "starting_c":  _row(   9,   2,   9,  0,  1,  3,  1,  2,  8,    0,   0,   5,  6, 2,  19),
    "backup_1":    _row(   5,   0,   1,  5,  1,  0,  5,  1,  3,    0,   1,   3,  3, 1,  12),
    "backup_2":    _row(   3,   0,   5,  1,  1,  0,  3,  1,  4,    1,   1,   0,  4, 1,  11),
    "backup_3":    _row(   1,   0,   4,  0,  0,  1,  0,  0,  2,    0,   0,   1,  2, 2,   8),
    "backup_4":    _row(   0,   0,   1,  1,  0,  0,  0,  0,  1,    0,   1,   0,  0, 0,   4),
    "backup_5":    _row(   0,   0,   0,  0,  0,  0,  0,  0,  0,    0,   0,   0,  0, 0,   0),
    "backup_6":    _row(   0,   0,   0,  0,  0,  0,  0,  0,  0,    0,   0,   0,  0, 0,   0),
    "backup_7":    _row(   0,   0,   0,  0,  0,  0,  0,  0,  0,    0,   0,   0,  0, 0,   0),
}


# fte_inject_state.md §5 — "Computer Team Player Stats" block.
# Invariants: PTS sum = 60, MIN sum = 140.
COMPUTER_TEAM_STAT_TEMPLATE = {
    #                    PTS OREB DREB AST STL BLK TO  FGM FGA  3PTM 3PTA  FTM FTA  F  MIN
    "starting_pg": _row(   5,   0,   2, 10,  2,  0,  4,  2,  3,    1,   3,   0,  2, 1,  21),
    "starting_sg": _row(  20,   1,   4,  3,  6,  2,  4,  7, 14,    2,   5,   4,  7, 1,  23),
    "starting_sf": _row(   3,   0,   5,  5,  0,  0,  2,  1,  9,    1,   3,   0,  1, 0,  23),
    "starting_pf": _row(  11,   1,   2,  0,  1,  0,  0,  4,  7,    0,   0,   3,  3, 3,  18),
    "starting_c":  _row(  16,   1,   7,  0,  1,  3,  0,  6,  9,    0,   0,   4,  4, 3,  16),
    "backup_1":    _row(   0,   0,   1,  5,  1,  0,  0,  0,  5,    0,   1,   0,  4, 1,  12),
    "backup_2":    _row(   3,   0,   5,  1,  1,  0,  4,  1,  4,    0,   0,   1,  1, 1,  11),
    "backup_3":    _row(   2,   0,   4,  0,  0,  1,  0,  1,  1,    0,   0,   0,  4, 2,   8),
    "backup_4":    _row(   0,   0,   3,  0,  0,  1,  2,  0,  1,    0,   1,   0,  0, 0,   5),
    "backup_5":    _row(   0,   0,   0,  0,  0,  0,  0,  0,  0,    0,   0,   0,  0, 0,   3),
    "backup_6":    _row(   0,   0,   0,  0,  0,  0,  0,  0,  0,    0,   0,   0,  0, 0,   0),
    "backup_7":    _row(   0,   0,   0,  0,  0,  0,  0,  0,  0,    0,   0,   0,  0, 0,   0),
}


def _verify_template(template: dict, name: str) -> None:
    """Guard against future edits silently breaking template invariants.

    Raises ValueError immediately at import time if any check fails.
    """
    pts_sum = sum(row["PTS"] for row in template.values())
    min_sum = sum(row["MIN"] for row in template.values())
    if pts_sum != 60:
        raise ValueError(f"{name}: PTS sum is {pts_sum}, expected 60")
    if min_sum != 140:
        raise ValueError(f"{name}: MIN sum is {min_sum}, expected 140")
    for slot, row in template.items():
        expected_pts = 2 * row["FGM"] + row["3PTM"] + row["FTM"]
        if row["PTS"] != expected_pts:
            raise ValueError(
                f"{name} {slot}: PTS={row['PTS']} but 2*FGM+3PTM+FTM={expected_pts}"
            )
        if row["REB"] != row["OREB"] + row["DREB"]:
            raise ValueError(
                f"{name} {slot}: REB={row['REB']} but OREB+DREB={row['OREB'] + row['DREB']}"
            )


_verify_template(USER_TEAM_STAT_TEMPLATE, "USER_TEAM_STAT_TEMPLATE")
_verify_template(COMPUTER_TEAM_STAT_TEMPLATE, "COMPUTER_TEAM_STAT_TEMPLATE")


def _best_position_rating(position_ratings) -> float:
    """Max rating across all positions for a player. 0.0 if unavailable."""
    if not isinstance(position_ratings, dict) or not position_ratings:
        return 0.0
    best = 0.0
    for value in position_ratings.values():
        try:
            v = float(value)
        except (TypeError, ValueError):
            continue
        if v > best:
            best = v
    return best


def rank_roster(players: Iterable[dict]) -> List[Tuple[str, str]]:
    """Stack-rank a team's roster into tutorial roster slots.

    Args:
        players: iterable of dicts with at least 'player_id' (str/ObjectId)
                 and 'position_ratings' (dict[str, float]).

    Returns:
        List of (slot, player_id) tuples in ROSTER_SLOTS order. Slots without
        an available player are omitted (returned list may be shorter than 12).

    Algorithm:
        1. For each starting slot, pick the unassigned player with the highest
           position_ratings[slot_position] value.
        2. Remaining players are ranked by best-position rating descending and
           assigned backup_1..backup_7 in order.
    """
    available = [p for p in players if p.get("player_id") is not None]
    assigned: dict = {}
    used_ids: set = set()

    # Phase 1: starters by per-position rating.
    for slot, pos in STARTER_POSITION.items():
        candidates = [p for p in available if p["player_id"] not in used_ids]
        if not candidates:
            break
        best = max(
            candidates,
            key=lambda p: float((p.get("position_ratings") or {}).get(pos, 0.0) or 0.0),
        )
        assigned[slot] = best["player_id"]
        used_ids.add(best["player_id"])

    # Phase 2: backups by best-position rating.
    remaining = [p for p in available if p["player_id"] not in used_ids]
    remaining.sort(
        key=lambda p: _best_position_rating(p.get("position_ratings")),
        reverse=True,
    )
    for i, p in enumerate(remaining[:7], start=1):
        assigned[f"backup_{i}"] = p["player_id"]

    return [(slot, assigned[slot]) for slot in ROSTER_SLOTS if slot in assigned]


def stat_overlay_for(slot: str, side: str) -> dict:
    """Return the partial player.stats['game'] overlay for a given slot/side.

    side: 'user' or 'computer'. Unknown slots return an empty dict.
    """
    if side == "user":
        return dict(USER_TEAM_STAT_TEMPLATE.get(slot, {}))
    if side == "computer":
        return dict(COMPUTER_TEAM_STAT_TEMPLATE.get(slot, {}))
    return {}
