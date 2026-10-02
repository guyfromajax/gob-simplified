"""All-American selection: a weekly projection and a post-tournament final.

Selection is by position. Each of the three teams has one player at PG, SG, SF, PF and
C: first team is rank 1 at each position, second team rank 2, third team rank 3. For the
final only, the third team takes rank 3 or rank 4, chosen by a coin that is fixed for a
franchise + season + position (never sim_rng, so recomputing cannot change it).

Score (0-100) = attributes * wa + stats * ws + team * wt, each component 0-100 within
the position:

  attributes  rating at the listed position, min-max scaled across the position
  stats       per-game stats, each scored by distance above the position average
              (average or below = 0, the position leader = 1), weighted STAT_WEIGHTS.
              Needs MIN_GAMES_SHARE of the team's games; DEF% also needs
              DEF_ATTEMPTS_PER_GAME defensive attempts per team game.
  team        national rank (rank 1 = 100, last = 0)

Weights move with the week (WEIGHT_ROWS, straight lines between rows). "Week" here is
weeks completed, and 0 completed weeks is the preseason, scored at the week-1 row.

Timeline:
  weeks 1-26   the projection is rebuilt once per completed week
  weeks 27-34  no updates. The week-26 scores are frozen onto each player's FPD doc
               (``aa_w26``) the first time the franchise is seen after week 26, because
               season stats keep accumulating through the tournaments.
  week 35      final = frozen week-26 score + postseason bonus points

Stored on the franchise under ``awards``:
  all_american_projection   {season, week, label, weights, all_american_teams, ...}
  all_american_teams        the FINAL teams only (first_team / second_team / third_team),
                            the shape trophy_log.py and career_data.py read
  all_american_final        how the final was built

Position ("listed position") is the one the roster page shows: leaders_snapshot's
_roster_position. No position is stored on a franchise player.
"""

from __future__ import annotations

import hashlib
import logging
import math
import time
from datetime import datetime
from typing import Any, Iterable, Mapping

logger = logging.getLogger(__name__)

POSITIONS = ("PG", "SG", "SF", "PF", "C")
TEAM_KEYS = ("first_team", "second_team", "third_team")
AWARDS_FIELD = "awards"
PROJECTION_KEY = "all_american_projection"
TEAMS_KEY = "all_american_teams"
FINAL_KEY = "all_american_final"
SNAPSHOT_FIELD = "aa_w26"

REGULAR_SEASON_WEEKS = 26
FINAL_WEEK = 35

# (week, (attributes, stats, team)). Straight line between rows.
WEIGHT_ROWS = (
    (1, (100.0, 0.0, 0.0)),
    (10, (30.0, 70.0, 0.0)),
    (26, (0.0, 70.0, 30.0)),
)

STAT_WEIGHTS = {
    "PTS": 0.35,
    "REB": 0.15,
    "AST": 0.15,
    "STL": 0.10,
    "BLK": 0.10,
    "DEF%": 0.15,
}
STAT_KEYS = tuple(STAT_WEIGHTS)

# A stats score needs this share of the team's games.
MIN_GAMES_SHARE = 0.70
# The old rule was 130 defensive attempts over the 26-game season: 5 per team game.
DEF_ATTEMPTS_PER_GAME = 5

# Stories publish after these completed weeks; 0 is the preseason (shown as week 1).
NEWS_COMPLETED_WEEKS = (0, 7, 13, 19, 26)
NEWS_TYPE = "all_americans"

# Postseason bonus points, added to the week-26 score.
BONUS_CONFERENCE_CHAMPION = 1
BONUS_REGION_CHAMPION = 2
BONUS_NATIONAL_SEMIFINAL = 2
BONUS_NATIONAL_CHAMPION = 5
# (share of the position's tournament players, points). One tier: the best one applies.
INDIVIDUAL_BONUS_TIERS = ((0.10, 5), (0.25, 3), (0.50, 1))
MIN_TOURNAMENT_GAMES = 2

_TOTAL_KEYS = ("GP", "PTS", "REB", "AST", "STL", "BLK", "DEF_A", "DEF_S")


# ---------------------------------------------------------------------------
# Pure scoring
# ---------------------------------------------------------------------------

def weights_for_week(week: Any) -> dict[str, float]:
    """Component weights as fractions that sum to 1, for a week from 1 to 26."""
    try:
        w = float(week)
    except (TypeError, ValueError):
        w = 1.0
    w = max(float(WEIGHT_ROWS[0][0]), min(float(WEIGHT_ROWS[-1][0]), w))
    for (lo_week, lo), (hi_week, hi) in zip(WEIGHT_ROWS, WEIGHT_ROWS[1:]):
        if w <= hi_week:
            t = (w - lo_week) / float(hi_week - lo_week)
            a, s, team = (lo[i] + (hi[i] - lo[i]) * t for i in range(3))
            return {"attributes": a / 100.0, "stats": s / 100.0, "team": team / 100.0}
    a, s, team = WEIGHT_ROWS[-1][1]
    return {"attributes": a / 100.0, "stats": s / 100.0, "team": team / 100.0}


def weights_percent(week: Any) -> dict[str, float]:
    return {key: round(value * 100.0, 1) for key, value in weights_for_week(week).items()}


def _num(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def stat_line(
    totals: Mapping[str, Any],
    games_required: float,
    def_attempts_required: float,
) -> dict[str, float | None] | None:
    """Per-game line for one player, or None when the games rule is not met.

    ``DEF%`` is None inside a line when the defensive attempts floor is not met: the
    player still gets a stats score, without a defensive part.
    """
    games = _num(totals.get("GP"))
    if games <= 0 or games + 1e-9 < games_required:
        return None
    line: dict[str, float | None] = {
        key: _num(totals.get(key)) / games for key in ("PTS", "REB", "AST", "STL", "BLK")
    }
    attempts = _num(totals.get("DEF_A"))
    if attempts > 0 and attempts + 1e-9 >= def_attempts_required:
        line["DEF%"] = _num(totals.get("DEF_S")) / attempts
    else:
        line["DEF%"] = None
    return line


def stat_scores(lines: Mapping[str, dict[str, float | None] | None]) -> dict[str, float]:
    """0-100 stats score per player id, within one position.

    Each stat is the distance above the position average, as a share of the leader's
    distance: the average (or below) scores 0 and the leader scores 1. The six shares
    are weighted by STAT_WEIGHTS. A player with no line scores 0.
    """
    scores = {pid: 0.0 for pid in lines}
    for key, weight in STAT_WEIGHTS.items():
        values = {
            pid: line[key]
            for pid, line in lines.items()
            if line is not None and line.get(key) is not None
        }
        if not values:
            continue
        mean = sum(values.values()) / len(values)
        span = max(values.values()) - mean
        if span <= 0:
            continue
        for pid, value in values.items():
            share = (value - mean) / span
            scores[pid] += 100.0 * weight * max(0.0, min(1.0, share))
    return scores


def min_max_scores(values: Mapping[str, float]) -> dict[str, float]:
    """0-100 by position: the lowest value is 0 and the highest is 100."""
    if not values:
        return {}
    low = min(values.values())
    span = max(values.values()) - low
    if span <= 0:
        return {pid: 100.0 for pid in values}
    return {pid: 100.0 * (value - low) / span for pid, value in values.items()}


def team_score(rank: Any, team_count: int) -> float:
    """National rank on 0-100: rank 1 is 100, the last rank is 0. No rank is 0."""
    try:
        r = int(rank)
    except (TypeError, ValueError):
        return 0.0
    n = max(2, int(team_count or 0))
    if r < 1:
        return 0.0
    return max(0.0, min(100.0, 100.0 * (n - r) / (n - 1)))


def score_players(
    players: Iterable[dict[str, Any]],
    *,
    weights: Mapping[str, float],
    team_games: Mapping[str, int],
    rank_by_team: Mapping[str, Any],
    team_count: int,
) -> list[dict[str, Any]]:
    """Add ``components`` and ``score`` to each player. Returns the same dicts."""
    pool = list(players)
    by_position: dict[str, list[dict[str, Any]]] = {pos: [] for pos in POSITIONS}
    for player in pool:
        if player.get("position") in by_position:
            by_position[player["position"]].append(player)

    for group in by_position.values():
        attribute = min_max_scores({p["player_id"]: _num(p.get("rating")) for p in group})
        lines = {}
        for player in group:
            games = int(team_games.get(str(player.get("team_id") or ""), 0) or 0)
            line = None
            if games > 0:
                line = stat_line(
                    player.get("totals") or {},
                    MIN_GAMES_SHARE * games,
                    DEF_ATTEMPTS_PER_GAME * games,
                )
            player["line"] = line
            lines[player["player_id"]] = line
        stats = stat_scores(lines)
        for player in group:
            pid = player["player_id"]
            components = {
                "attributes": attribute.get(pid, 0.0),
                "stats": stats.get(pid, 0.0),
                "team": team_score(rank_by_team.get(str(player.get("team_id") or "")), team_count),
            }
            player["components"] = {key: round(value, 2) for key, value in components.items()}
            player["score"] = round(
                sum(components[key] * float(weights.get(key, 0.0)) for key in components), 2
            )
    return pool


def rank_by_position(players: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Players at each position, best first. Ties: rating, then name, then id."""
    ranked: dict[str, list[dict[str, Any]]] = {pos: [] for pos in POSITIONS}
    for player in players:
        if player.get("position") in ranked:
            ranked[player["position"]].append(player)
    for group in ranked.values():
        group.sort(
            key=lambda p: (
                -_num(p.get("score")),
                -_num(p.get("rating")),
                str(p.get("name") or ""),
                str(p.get("player_id") or ""),
            )
        )
    return ranked


def third_team_rank(franchise_id: Any, season: Any, position: str) -> int:
    """3 or 4: which rank the final third team takes at this position.

    A hash of franchise + season + position, so the final is the same on every
    recompute and no engine random stream is touched.
    """
    digest = hashlib.sha256(f"all-american:{franchise_id}:{season}:{position}".encode("utf-8")).digest()
    return 3 + (digest[0] & 1)


def _display_stats(line: Mapping[str, float | None] | None) -> dict[str, Any]:
    if not line:
        return {key: None for key in STAT_KEYS}
    out: dict[str, Any] = {}
    for key in ("PTS", "REB", "AST", "STL", "BLK"):
        value = line.get(key)
        out[key] = None if value is None else round(float(value), 1)
    pct = line.get("DEF%")
    out["DEF%"] = None if pct is None else int(round(float(pct) * 100))
    return out


def _pick(player: Mapping[str, Any], rank: int) -> dict[str, Any]:
    pick = {
        "player_id": player.get("player_id"),
        "name": player.get("name") or "",
        "team_id": str(player.get("team_id") or ""),
        "team_name": player.get("team_name") or "",
        "year": player.get("year") or "",
        "position": player.get("position"),
        "rating": round(_num(player.get("rating")), 1),
        "rank": int(rank),
        "score": round(_num(player.get("score")), 2),
        "components": dict(player.get("components") or {}),
        "games": int(_num((player.get("totals") or {}).get("GP"))),
        "stats": _display_stats(player.get("line")),
    }
    if "bonus" in player:
        pick["bonus"] = dict(player["bonus"])
        pick["week26_score"] = round(_num(player.get("week26_score")), 2)
    return pick


def select_teams(
    ranked: Mapping[str, list[dict[str, Any]]],
    *,
    third_ranks: Mapping[str, int] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """One player per position on each team.

    ``third_ranks`` is only passed for the final ({position: 3 or 4}). A projection
    leaves it out and the third team is rank 3.
    """
    teams: dict[str, list[dict[str, Any]]] = {key: [] for key in TEAM_KEYS}
    for position in POSITIONS:
        group = ranked.get(position) or []
        if len(group) >= 1:
            teams["first_team"].append(_pick(group[0], 1))
        if len(group) >= 2:
            teams["second_team"].append(_pick(group[1], 2))
        want = int((third_ranks or {}).get(position, 3))
        if want == 4 and len(group) < 4:
            want = 3
        if len(group) >= want:
            teams["third_team"].append(_pick(group[want - 1], want))
    return teams


def individual_bonus(position_in_field: int, field_size: int) -> int:
    """Bonus points for the ``position_in_field``-th best (1 = best) of ``field_size``."""
    if field_size <= 0 or position_in_field < 1:
        return 0
    for share, points in INDIVIDUAL_BONUS_TIERS:
        if position_in_field <= math.ceil(share * field_size):
            return points
    return 0


def team_bonus_points(franchise_doc: Mapping[str, Any]) -> dict[str, int]:
    """Cumulative postseason team bonus by team id (string).

    Conference tournament champion +1, region tournament champion +2, reached the
    national semifinals +2, national champion +5. The national bracket is eight region
    champions: round1 is the quarterfinal, ROUND2 IS THE SEMIFINAL, then the final.
    """
    points: dict[str, int] = {}

    def add(team_id: Any, value: int) -> None:
        key = str(team_id or "")
        if key and not key.startswith("R1_"):
            points[key] = points.get(key, 0) + value

    for entry in (franchise_doc.get("conference_tournaments") or {}).values():
        if isinstance(entry, Mapping) and entry.get("champion"):
            add(entry.get("champion"), BONUS_CONFERENCE_CHAMPION)

    for entry in (franchise_doc.get("region_tournaments") or {}).values():
        final = (entry or {}).get("final") if isinstance(entry, Mapping) else None
        if final and isinstance(final[0], Mapping) and final[0].get("winner"):
            add(final[0].get("winner"), BONUS_REGION_CHAMPION)

    national = franchise_doc.get("national_tournament") or {}
    bracket = national.get("bracket") or {}
    for matchup in bracket.get("round2") or []:
        if isinstance(matchup, Mapping):
            add(matchup.get("home_team"), BONUS_NATIONAL_SEMIFINAL)
            add(matchup.get("away_team"), BONUS_NATIONAL_SEMIFINAL)
    champion = national.get("champion")
    if not champion:
        final = bracket.get("final") or []
        if final and isinstance(final[0], Mapping):
            champion = final[0].get("winner")
    if champion:
        add(champion, BONUS_NATIONAL_CHAMPION)
    return points


def tournament_bonus_by_player(players: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Individual postseason bonus by player id.

    ``players`` carry ``position`` and ``tournament_totals`` (season totals now minus
    the frozen week-26 totals). A player needs MIN_TOURNAMENT_GAMES tournament games.
    Qualifiers at a position are ranked by the same stats score, on tournament
    per-game numbers, and the tiers are shares of that position's qualifiers.
    """
    bonus: dict[str, int] = {}
    by_position: dict[str, list[dict[str, Any]]] = {pos: [] for pos in POSITIONS}
    for player in players:
        if player.get("position") in by_position:
            by_position[player["position"]].append(player)
    for group in by_position.values():
        lines = {}
        for player in group:
            totals = player.get("tournament_totals") or {}
            games = _num(totals.get("GP"))
            if games < MIN_TOURNAMENT_GAMES:
                continue
            lines[player["player_id"]] = stat_line(totals, MIN_TOURNAMENT_GAMES, DEF_ATTEMPTS_PER_GAME * games)
        if not lines:
            continue
        scores = stat_scores(lines)
        order = sorted(lines, key=lambda pid: (-scores[pid], str(pid)))
        for index, pid in enumerate(order, start=1):
            points = individual_bonus(index, len(order))
            if points:
                bonus[pid] = points
    return bonus


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def _store():
    from BackEnd.persistence import get_store

    return get_store()


def _fpd_projection() -> dict[str, int]:
    projection = {
        "player_id": 1,
        "meta.first_name": 1,
        "meta.last_name": 1,
        "meta.team": 1,
        "meta.team_id": 1,
        "meta.position": 1,
        "meta.year": 1,
        "meta.yr": 1,
        "position_ratings": 1,
        "training_position": 1,
        "position_intent": 1,
        SNAPSHOT_FIELD: 1,
        "season.OREB": 1,
        "season.DREB": 1,
    }
    for key in _TOTAL_KEYS:
        projection[f"season.{key}"] = 1
    return projection


def _season_totals(season: Mapping[str, Any] | None) -> dict[str, float]:
    season = season or {}
    totals = {key: _num(season.get(key)) for key in _TOTAL_KEYS}
    if not totals["REB"]:
        totals["REB"] = _num(season.get("OREB")) + _num(season.get("DREB"))
    return totals


def listed_position(doc: Mapping[str, Any], *, on_user_team: bool) -> str:
    """The position the roster page shows for this player."""
    from BackEnd.utils.leaders_snapshot import _roster_position

    resolved = None
    if on_user_team:
        from BackEnd.constants.training_shape import resolve_training_position

        resolved = resolve_training_position(doc)
    meta = doc.get("meta") or {}
    return _roster_position(
        meta.get("position"),
        doc.get("position_ratings"),
        doc.get("training_position"),
        resolved,
        on_user_team=on_user_team,
    )


def rating_at_position(doc: Mapping[str, Any], position: str) -> float:
    """``position_ratings[position]`` from the franchise player doc (the RT number)."""
    from BackEnd.utils.leaders_snapshot import _ratings_dict

    ratings = _ratings_dict(doc.get("position_ratings"))
    if position in ratings:
        return _num(ratings.get(position))
    return max((_num(v) for v in ratings.values()), default=0.0)


def _regular_season_results(results: Mapping[str, Any] | None) -> dict[str, Any]:
    out = {}
    for week, rows in (results or {}).items():
        try:
            if int(week) <= REGULAR_SEASON_WEEKS:
                out[week] = rows
        except (TypeError, ValueError):
            continue
    return out


def load_league(franchise_doc: Mapping[str, Any]) -> dict[str, Any]:
    """Everything the score needs, in two reads (team data, player data)."""
    from BackEnd.utils.franchise_team_display import resolve_team_name_map
    from BackEnd.utils.leaders_snapshot import team_games_from_results

    store = _store()
    franchise_key = franchise_doc["_id"]
    franchise_id = str(franchise_key)
    user_team_id = str(franchise_doc.get("user_team_object_id") or "")

    rank_by_team: dict[str, Any] = {}
    active: set[str] = set()
    benched: set[str] = set()
    for row in store.franchise_team_data_collection.find(
        {"franchise_id": franchise_key},
        {"team_id": 1, "natl_rank": 1, "players": 1, "training_squad_players": 1},
    ):
        team_id = str(row.get("team_id") or "")
        if team_id:
            rank_by_team[team_id] = row.get("natl_rank")
        active.update(str(pid) for pid in (row.get("players") or []))
        benched.update(str(pid) for pid in (row.get("training_squad_players") or []))
    active -= benched

    try:
        names = resolve_team_name_map(franchise_doc)
    except Exception:
        logger.exception("[ALL-AMERICAN] team names failed franchise_id=%s", franchise_id)
        names = {}

    players: list[dict[str, Any]] = []
    for doc in store.franchise_players_data_collection.find(
        {"franchise_id": franchise_id}, _fpd_projection()
    ):
        player_id = str(doc.get("player_id") or "")
        if not player_id:
            continue
        # The active roster. With no roster lists at all, every franchise player counts.
        if active and player_id not in active:
            continue
        meta = doc.get("meta") or {}
        team_id = str(meta.get("team_id") or "")
        position = listed_position(doc, on_user_team=bool(user_team_id) and team_id == user_team_id)
        if position not in POSITIONS:
            continue
        players.append({
            "player_id": player_id,
            "name": f"{meta.get('first_name', '')} {meta.get('last_name', '')}".strip(),
            "team_id": team_id,
            "team_name": names.get(team_id, meta.get("team", "")),
            "year": meta.get("year") or meta.get("yr") or "",
            "position": position,
            "rating": rating_at_position(doc, position),
            "totals": _season_totals(doc.get("season")),
            "snapshot": doc.get(SNAPSHOT_FIELD) if isinstance(doc.get(SNAPSHOT_FIELD), Mapping) else None,
        })

    return {
        "franchise_id": franchise_id,
        "players": players,
        "rank_by_team": rank_by_team,
        "team_count": len(rank_by_team) or 128,
        "team_games": team_games_from_results(_regular_season_results(franchise_doc.get("results"))),
    }


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------

def completed_weeks(franchise_doc: Mapping[str, Any]) -> int:
    """Regular-season weeks completed: 0 in the preseason, 26 from week 27 on."""
    week = int(franchise_doc.get("week", 1) or 1)
    return max(0, min(REGULAR_SEASON_WEEKS, week - 1))


def projection_label(completed: int) -> str:
    if completed <= 0:
        return "Preseason"
    if completed >= REGULAR_SEASON_WEEKS:
        return "End of regular season"
    return f"After week {completed}"


def _season_number(franchise_doc: Mapping[str, Any]) -> int:
    return int(franchise_doc.get("current_season", 1) or 1)


def build_projection(franchise_doc: Mapping[str, Any], completed: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(projection, every scored player) for ``completed`` regular-season weeks."""
    league = load_league(franchise_doc)
    weights = weights_for_week(max(1, completed))
    scored = score_players(
        league["players"],
        weights=weights,
        team_games=league["team_games"],
        rank_by_team=league["rank_by_team"],
        team_count=league["team_count"],
    )
    projection = {
        "season": _season_number(franchise_doc),
        "week": int(completed),
        "label": projection_label(completed),
        "weights": weights_percent(max(1, completed)),
        "stats_basis": "per_game",
        "frozen": completed >= REGULAR_SEASON_WEEKS,
        TEAMS_KEY: select_teams(rank_by_position(scored)),
        "computed_at": datetime.utcnow(),
    }
    return projection, scored


def _write_week26_snapshots(franchise_id: str, scored: Iterable[dict[str, Any]], *, clean: bool) -> int:
    """Freeze each player's week-26 score and totals on the FPD doc.

    The final reads these: season stats keep accumulating through the tournaments, and
    the difference between then and now is the player's tournament line.
    """
    from pymongo import UpdateOne

    ops = []
    for player in scored:
        ops.append(UpdateOne(
            {"franchise_id": franchise_id, "player_id": player["player_id"]},
            {"$set": {SNAPSHOT_FIELD: {
                "position": player["position"],
                "score": player["score"],
                "rating": player["rating"],
                "components": player["components"],
                "totals": {key: player["totals"].get(key, 0) for key in _TOTAL_KEYS},
                "line": player.get("line"),
                "clean": bool(clean),
            }}},
        ))
    if ops:
        _store().franchise_players_data_collection.bulk_write(ops, ordered=False)
    return len(ops)


def _team_lines(picks: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    from BackEnd.utils.player_year import format_player_year_abbrev

    lines = []
    for pick in picks:
        try:
            year = format_player_year_abbrev(pick.get("year"))
        except Exception:
            year = str(pick.get("year") or "")
        team = pick.get("team_name") or ""
        detail = ", ".join(part for part in (team, year) if part and part != "--")
        lines.append({
            "type": "text",
            "text": f"{pick.get('position')}: {pick.get('name')}" + (f" ({detail})" if detail else ""),
        })
    return lines


# The preseason story's first sentence. Stories written before the formula was hidden
# say the teams were "picked on ratings": the stored story is left as it is and the
# sentence is replaced when the story is read (``public_story``).
PRESEASON_INTRO = "The preseason All-American teams, named before a game has been played."
RETIRED_PRESEASON_INTRO = (
    "The preseason All-American teams, picked on ratings before a game has been played."
)


def public_story(story: Any) -> Any:
    """A stored news story as the player reads it.

    An All-American story that still carries the retired preseason sentence is returned
    as a copy with the current one. Anything else, and the stored story itself, is
    untouched.
    """
    if not isinstance(story, Mapping) or story.get("type") != NEWS_TYPE:
        return story
    lines = story.get("rich_lines")
    if not isinstance(lines, list) or not any(
        isinstance(line, Mapping) and line.get("text") == RETIRED_PRESEASON_INTRO for line in lines
    ):
        return story
    scrubbed = dict(story)
    scrubbed["rich_lines"] = [
        {**line, "text": PRESEASON_INTRO}
        if isinstance(line, Mapping) and line.get("text") == RETIRED_PRESEASON_INTRO
        else line
        for line in lines
    ]
    return scrubbed


def build_news_story(projection: Mapping[str, Any]) -> dict[str, Any] | None:
    """The story for a publishing week, or None on any other week.

    Names only: position, player, team, year. The copy never says how the teams are
    picked (no weights, percentages, scores, ratings or bonus).
    """
    completed = int(projection.get("week", 0) or 0)
    if completed not in NEWS_COMPLETED_WEEKS:
        return None
    teams = projection.get(TEAMS_KEY) or {}
    if not any(teams.get(key) for key in TEAM_KEYS):
        return None
    week = max(1, completed)
    if completed <= 0:
        headline = "Preseason All-Americans announced"
        intro = PRESEASON_INTRO
    elif completed >= REGULAR_SEASON_WEEKS:
        headline = "Projected All-Americans: end of the regular season"
        intro = (
            "These teams are not final. Tournament performance can still change them: "
            "the final All-American teams are named after the National Tournament."
        )
    else:
        headline = f"Projected All-Americans: week {completed}"
        intro = f"Where the All-American race stands after week {completed}."
    rich_lines: list[dict[str, Any]] = [{"type": "text", "text": intro}]
    for key, title in zip(TEAM_KEYS, ("First Team", "Second Team", "Third Team")):
        picks = teams.get(key) or []
        if not picks:
            continue
        rich_lines.append({"type": "gap"})
        rich_lines.append({"type": "heading", "text": title})
        rich_lines.extend(_team_lines(picks))
    return {
        "story_id": f"w{week}-all-americans",
        "week": int(week),
        "type": NEWS_TYPE,
        "headline": headline,
        "rich_lines": rich_lines,
        "created_at": datetime.utcnow(),
    }


def ensure_projection(franchise_doc: dict[str, Any]) -> dict[str, Any] | None:
    """Bring the stored projection up to the last completed week. Cheap when current.

    Runs on the first command-center (or Awards) read after a week advance, so it sees
    that week's stats and the national ranks the advance just wrote. Weeks 27-34 keep
    the frozen week-26 projection. Returns the stored projection.
    """
    if not franchise_doc or franchise_doc.get("_id") is None:
        return None
    week = int(franchise_doc.get("week", 1) or 1)
    awards = dict(franchise_doc.get(AWARDS_FIELD) or {})
    stored = awards.get(PROJECTION_KEY) if isinstance(awards.get(PROJECTION_KEY), Mapping) else None
    if week >= FINAL_WEEK or awards.get(TEAMS_KEY):
        return stored
    completed = completed_weeks(franchise_doc)
    season = _season_number(franchise_doc)
    if stored and int(stored.get("season", 0) or 0) == season and int(stored.get("week", -1)) == completed:
        return stored

    started = time.perf_counter()
    projection, scored = build_projection(franchise_doc, completed)
    franchise_id = str(franchise_doc["_id"])
    if completed >= REGULAR_SEASON_WEEKS:
        # Clean only when no tournament game has been played yet (the franchise is still
        # on week 27). A franchise first seen later freezes what it has.
        clean = week == REGULAR_SEASON_WEEKS + 1
        projection["includes_tournament_games"] = not clean
        _write_week26_snapshots(franchise_id, scored, clean=clean)

    awards[PROJECTION_KEY] = projection
    update: dict[str, Any] = {AWARDS_FIELD: awards}
    # A franchise first seen mid-tournament gets the frozen projection but no late
    # "end of the regular season" story.
    story = None if projection.get("includes_tournament_games") else build_news_story(projection)
    if story is not None:
        existing = list(franchise_doc.get("season_news") or [])
        if story["story_id"] not in {s.get("story_id") for s in existing if isinstance(s, Mapping)}:
            update["season_news"] = [story] + existing

    from BackEnd.utils.browse_cache import fold_browse_rev

    _store().franchises_collection.update_one(
        {"_id": franchise_doc["_id"]}, fold_browse_rev({"$set": update})
    )
    franchise_doc.update(update)
    logger.info(
        "[ALL-AMERICAN] projection franchise_id=%s season=%s week=%s players=%s ms=%.0f",
        franchise_id, season, completed, len(scored), (time.perf_counter() - started) * 1000.0,
    )
    return projection


# ---------------------------------------------------------------------------
# Final
# ---------------------------------------------------------------------------

def compute_final(franchise_doc: Mapping[str, Any]) -> dict[str, Any]:
    """The final teams: frozen week-26 score plus postseason bonus points.

    Returns the keys to merge into ``awards``: ``computed_at``, ``all_american_teams``
    and ``all_american_final``. A franchise with no frozen week-26 scores (it was
    already past week 26 when this shipped and never opened a screen before week 35)
    is scored on its season to date at the week-26 weights, with the team bonus and no
    individual bonus, because its tournament games cannot be told apart.
    """
    league = load_league(franchise_doc)
    players = league["players"]
    frozen = [p for p in players if p.get("snapshot") and p["snapshot"].get("position") in POSITIONS]

    if frozen:
        basis = "week_26"
        pool = []
        for player in frozen:
            snap = player["snapshot"]
            before = snap.get("totals") or {}
            entry = dict(player)
            entry["position"] = snap["position"]
            entry["rating"] = _num(snap.get("rating"))
            entry["components"] = dict(snap.get("components") or {})
            entry["line"] = snap.get("line")
            entry["week26_score"] = _num(snap.get("score"))
            entry["totals"] = {key: _num(before.get(key)) for key in _TOTAL_KEYS}
            entry["tournament_totals"] = {
                key: max(0.0, _num(player["totals"].get(key)) - _num(before.get(key)))
                for key in _TOTAL_KEYS
            }
            pool.append(entry)
        individual = tournament_bonus_by_player(pool)
        clean = all(bool((p["snapshot"] or {}).get("clean")) for p in frozen)
    else:
        basis = "season_to_date"
        pool = score_players(
            players,
            weights=weights_for_week(REGULAR_SEASON_WEEKS),
            team_games=league["team_games"],
            rank_by_team=league["rank_by_team"],
            team_count=league["team_count"],
        )
        for entry in pool:
            entry["week26_score"] = entry["score"]
        individual = {}
        clean = False

    team_points = team_bonus_points(franchise_doc)
    for entry in pool:
        team = int(team_points.get(str(entry.get("team_id") or ""), 0))
        solo = int(individual.get(entry["player_id"], 0))
        entry["bonus"] = {"team": team, "individual": solo, "total": team + solo}
        entry["score"] = round(_num(entry.get("week26_score")) + team + solo, 2)

    franchise_id = league["franchise_id"]
    season = _season_number(franchise_doc)
    third_ranks = {position: third_team_rank(franchise_id, season, position) for position in POSITIONS}
    return {
        "computed_at": datetime.utcnow(),
        TEAMS_KEY: select_teams(rank_by_position(pool), third_ranks=third_ranks),
        FINAL_KEY: {
            "season": season,
            "basis": basis,
            "week26_clean": clean,
            "stats_basis": "per_game",
            "third_team_ranks": third_ranks,
        },
    }


# ---------------------------------------------------------------------------
# API payload
# ---------------------------------------------------------------------------

# What a pick shows the player. The formula stays on the server: the stored pick also
# holds its rank within the position, composite score, component scores and bonus, and
# none of those (nor the week's weights) leave in a response.
PUBLIC_PICK_KEYS = (
    "player_id", "name", "team_id", "team_name", "year", "position", "rating", "games", "stats",
)


def public_teams(teams: Any) -> dict[str, list[dict[str, Any]]] | None:
    """The stored teams with every pick cut down to ``PUBLIC_PICK_KEYS``."""
    if not isinstance(teams, Mapping):
        return None
    out: dict[str, list[dict[str, Any]]] = {}
    for key in TEAM_KEYS:
        picks = teams.get(key) or []
        out[key] = [
            {name: pick[name] for name in PUBLIC_PICK_KEYS if name in pick}
            for pick in picks
            if isinstance(pick, Mapping)
        ]
    return out


def awards_payload(franchise_doc: Mapping[str, Any]) -> dict[str, Any]:
    """What GET /franchise/awards returns: the final when it exists, else the projection.

    Teams and status only. Weights, scores, ranks and bonus stay on the franchise doc.
    """
    awards = franchise_doc.get(AWARDS_FIELD) or {}
    if awards.get(TEAMS_KEY):
        final = awards.get(FINAL_KEY) or {}
        return {
            "status": "final",
            "label": "Final",
            "computed_at": awards.get("computed_at"),
            "stats_basis": final.get("stats_basis"),
            TEAMS_KEY: public_teams(awards.get(TEAMS_KEY)),
        }
    projection = awards.get(PROJECTION_KEY)
    if not isinstance(projection, Mapping) or not projection.get(TEAMS_KEY):
        return {"status": "unavailable", TEAMS_KEY: None}
    return {
        "status": "projected",
        "week": projection.get("week"),
        "label": projection.get("label"),
        "stats_basis": projection.get("stats_basis"),
        "computed_at": projection.get("computed_at"),
        TEAMS_KEY: public_teams(projection.get(TEAMS_KEY)),
    }
