"""Practice Squad orchestration — init, weekly sims, standings, news."""

from __future__ import annotations

import hashlib
import logging
import random
import time
import uuid
from datetime import datetime
from typing import Any
from urllib.parse import quote

from bson import ObjectId

from BackEnd.db import (
    db,
    franchise_players_data_collection,
    franchise_recruits_data_collection,
    franchise_team_data_collection,
)
from BackEnd.practice_squad.constants import (
    PS_ACTIVE_WEEKS,
    PS_CHAMPIONSHIP_WEEK,
    PS_REGULAR_WEEKS,
    PS_TOURNAMENT_WEEKS,
    REGION_LETTERS,
    SCRUBS_MIN_PLAYERS_TO_COMPETE,
    TIER_NAMES,
)
from BackEnd.practice_squad.roster import (
    build_all_region_rosters,
    build_scrubs_week_roster,
    ps_display_name,
    ps_team_id,
)
from BackEnd.practice_squad.schedule import (
    build_regular_season_schedule,
    championship_game_slot,
    init_tier_tournaments,
    tournament_games_for_week,
)
from BackEnd.practice_squad.sim import run_ps_full_simulation
from BackEnd.practice_squad.stats import apply_ps_game_stats, ensure_ps_season_stats_backfilled
from BackEnd.tournament import bracket_engine
from BackEnd.utils.game_id_utils import generate_game_id

logger = logging.getLogger(__name__)
PS_RUNNING_GAME_STALE_SECONDS = 60
PS_FULL_ENGINE_MAX_ATTEMPTS = 3
PS_TERMINAL_GAME_STATUSES = ("completed", "fallback_completed", "forfeit", "skipped")


def _running_game_is_stale(game: dict) -> bool:
    if game.get("status") != "running":
        return False
    raw = game.get("started_at")
    if not raw:
        return True
    try:
        started = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        now = datetime.now(started.tzinfo) if started.tzinfo else datetime.utcnow()
        return (now - started).total_seconds() >= PS_RUNNING_GAME_STALE_SECONDS
    except (TypeError, ValueError):
        return True


def _training_game_key(game: dict) -> str:
    return "|".join(
        [
            str(game.get("phase") or "regular"),
            str(game.get("tier") or 0),
            str(game.get("round") or 0),
            str(game.get("match_index") or 0),
            str(game.get("away_team_id") or ""),
            str(game.get("home_team_id") or ""),
        ]
    )


def _advance_ps_result(
    game: dict,
    ps_state: dict,
    *,
    home_score: int,
    away_score: int,
    status: str,
) -> None:
    """Apply one terminal result to standings and any bracket exactly once."""
    home_id = str(game.get("home_team_id") or "")
    away_id = str(game.get("away_team_id") or "")
    tier = int(
        game.get("tier")
        or (ps_state.get("teams") or {}).get(home_id, {}).get("tier")
        or 1
    )
    winner = home_id if home_score > away_score else away_id
    loser = away_id if winner == home_id else home_id
    _apply_standings(ps_state, winner, loser, tier)
    _record_h2h(ps_state, winner, loser)
    game.update(
        {
            "status": status,
            "home_score": home_score,
            "away_score": away_score,
            "winner": winner,
        }
    )

    phase = game.get("phase")
    if phase == "tournament":
        tier_key = str(game.get("tier"))
        tstate = (ps_state.get("tournaments") or {}).get(tier_key)
        if tstate:
            round_num = int(game.get("round") or 1)
            idx = int(game.get("match_index") or 0)
            bracket = tstate.get("bracket") or {}
            bracket_engine.save_game_result(
                bracket,
                round_num,
                idx,
                str(game.get("game_id")),
                winner,
                score={home_id: home_score, away_id: away_score},
            )
            _, next_round, completed, champion = bracket_engine.advance_bracket(
                bracket, round_num
            )
            tstate["bracket"] = bracket
            tstate["current_round"] = next_round
            if completed and champion:
                tstate["champion"] = champion
    elif phase == "championship":
        ps_state["championship"] = {**game, "winner": winner}


def _complete_with_deterministic_fallback(
    game: dict,
    ps_state: dict,
    *,
    franchise_id_str: str,
    week: int,
    error: Exception,
) -> dict:
    """Create an auditable terminal result after the bounded engine attempts fail."""
    game_id = str(game.get("game_id") or generate_game_id())
    game["game_id"] = game_id
    seed_material = f"{franchise_id_str}:{week}:{game_id}"
    seed = int(hashlib.sha256(seed_material.encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)
    home_score = rng.randint(50, 80)
    away_score = rng.randint(50, 80)
    if home_score == away_score:
        home_score = home_score + 1 if home_score < 80 else home_score - 1

    now = datetime.utcnow().isoformat() + "Z"
    error_type = type(error).__name__
    error_message = str(error)
    db.games.update_one(
        {"_id": game_id},
        {
            "$set": {
                "franchise_id": franchise_id_str,
                "week": week,
                "mode": "practice_squad",
                "status": "completed",
                "simulation_engine": "practice_squad_fallback",
                "fallback_reason": "full_engine_failed_after_bounded_retries",
                "full_engine_attempts": int(game.get("attempts") or PS_FULL_ENGINE_MAX_ATTEMPTS),
                "last_error_type": error_type,
                "last_error_message": error_message,
                "last_error_at": now,
                "player_stats_status": "skipped_fallback_has_no_box_score",
                "home_team_id": str(game.get("home_team_id") or ""),
                "away_team_id": str(game.get("away_team_id") or ""),
                "home_score": home_score,
                "away_score": away_score,
            }
        },
        upsert=True,
    )
    _advance_ps_result(
        game,
        ps_state,
        home_score=home_score,
        away_score=away_score,
        status="fallback_completed",
    )
    game.update(
        {
            "fallback_reason": "full_engine_failed_after_bounded_retries",
            "last_error_type": error_type,
            "last_error": error_message,
            "last_error_at": now,
            "player_stats_status": "skipped_fallback_has_no_box_score",
        }
    )
    return game


def _empty_standings() -> dict[str, dict[str, dict[str, int]]]:
    standings: dict[str, dict[str, dict[str, int]]] = {}
    for tier in range(1, 7):
        standings[str(tier)] = {}
        for region in REGION_LETTERS:
            tid = ps_team_id(region, tier)
            standings[str(tier)][tid] = {"w": 0, "l": 0}
    return standings


def _format_team_name_map(franchise: dict | None = None) -> dict[str, str]:
    if franchise is not None:
        from BackEnd.utils.franchise_team_display import resolve_team_name_map

        return resolve_team_name_map(franchise)
    return {
        str(team["_id"]): team.get("name", str(team["_id"]))
        for team in db.teams.find({}, {"name": 1})
    }


def _build_region_team_map() -> dict[str, list[str]]:
    region_map = {r: [] for r in REGION_LETTERS}
    for team in db.teams.find({}, {"region": 1}):
        region = str(team.get("region") or "").upper()
        if region in region_map:
            region_map[region].append(str(team["_id"]))
    return region_map


def _player_sources_from_ps_state(ps_state: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for team in (ps_state.get("teams") or {}).values():
        for slot in team.get("roster") or []:
            pid = str(slot.get("player_id") or "")
            src = slot.get("source")
            if pid and src:
                out[pid] = str(src)
    for week_rosters in (ps_state.get("scrubs_rosters") or {}).values():
        for slot in week_rosters or []:
            pid = str(slot.get("player_id") or "")
            src = slot.get("source")
            if pid and src:
                out[pid] = str(src)
    return out


def initialize_practice_squad(
    franchise_id: ObjectId,
    franchise_doc: dict,
) -> dict[str, Any]:
    """Build rosters + schedule after week 1 training camp."""
    fid = str(franchise_id)
    team_name_map = _format_team_name_map(franchise_doc)
    region_team_map = _build_region_team_map()

    ftd_docs = list(franchise_team_data_collection.find({"franchise_id": franchise_id}))
    ftd_by_team = {str(d["team_id"]): d for d in ftd_docs if d.get("team_id") is not None}

    fpd_docs = list(franchise_players_data_collection.find({"franchise_id": fid}))
    fpd_by_player = {str(d["player_id"]): d for d in fpd_docs}

    recruits = list(franchise_recruits_data_collection.find({"franchise_id": fid}))
    recruits_by_region: dict[str, list[dict]] = {r: [] for r in REGION_LETTERS}
    for rec in recruits:
        hr = str(rec.get("Home Region") or "").upper()
        if hr in recruits_by_region:
            recruits_by_region[hr].append(rec)

    teams, scrubs_pools, scrubs_forfeit = build_all_region_rosters(
        region_team_map=region_team_map,
        ftd_by_team=ftd_by_team,
        fpd_by_player=fpd_by_player,
        recruits_by_region=recruits_by_region,
        team_name_map=team_name_map,
    )

    schedule = build_regular_season_schedule(scrubs_forfeit=scrubs_forfeit)

    ps_state: dict[str, Any] = {
        "version": 1,
        "initialized": True,
        "initialized_week": 1,
        "trained_week": None,
        "teams": teams,
        "scrubs_pools": {k: [_roster_slot_ref(p) for p in v] for k, v in scrubs_pools.items()},
        "scrubs_forfeit": scrubs_forfeit,
        "scrubs_rosters": {},
        "schedule": schedule,
        "standings": _empty_standings(),
        "tournaments": {},
        "championship": {},
        "applied_games": [],
        "head_to_head": {},
    }
    return ps_state


def _roster_slot_ref(player: dict) -> dict:
    return {
        "source": player.get("source"),
        "player_id": player.get("player_id"),
        "name": player.get("name"),
        "parent_team_name": player.get("parent_team_name"),
        "best_rt": player.get("best_rt"),
    }


def _resolve_team_roster(ps_state: dict, team_id: str, week: int) -> list[dict]:
    team = (ps_state.get("teams") or {}).get(team_id) or {}
    tier = int(team.get("tier") or 0)
    if tier == 6:
        week_key = str(week)
        return list((ps_state.get("scrubs_rosters") or {}).get(week_key) or [])
    return list(team.get("roster") or [])


def _record_h2h(ps_state: dict, winner_id: str, loser_id: str) -> None:
    h2h = ps_state.setdefault("head_to_head", {})
    key = "|".join(sorted([winner_id, loser_id]))
    rec = h2h.setdefault(key, {})
    rec[winner_id] = int(rec.get(winner_id) or 0) + 1


def _apply_standings(ps_state: dict, winner_id: str, loser_id: str, tier: int) -> None:
    standings = ps_state.setdefault("standings", {})
    tier_key = str(tier if tier else 1)
    tier_standings = standings.setdefault(tier_key, {})
    for tid, delta in ((winner_id, "w"), (loser_id, "l")):
        row = tier_standings.setdefault(tid, {"w": 0, "l": 0})
        row[delta] = int(row.get(delta) or 0) + 1


def _seed_tier_teams(ps_state: dict, tier: int) -> list[str]:
    """Seed 8 regional teams for a tier by W/L, H2H, random."""
    standings = (ps_state.get("standings") or {}).get(str(tier)) or {}
    team_ids = [ps_team_id(r, tier) for r in REGION_LETTERS]
    h2h = ps_state.get("head_to_head") or {}

    def h2h_wins(a: str, b: str) -> int:
        key = "|".join(sorted([a, b]))
        rec = h2h.get(key) or {}
        return int(rec.get(a) or 0)

    def sort_key(tid: str) -> tuple:
        row = standings.get(tid) or {"w": 0, "l": 0}
        w, l = int(row.get("w") or 0), int(row.get("l") or 0)
        return (-w, l, random.random())

    ranked = sorted(team_ids, key=sort_key)
    # Tiebreak pairwise H2H among tied W/L groups
    i = 0
    while i < len(ranked):
        j = i + 1
        wi = standings.get(ranked[i]) or {"w": 0, "l": 0}
        while j < len(ranked):
            wj = standings.get(ranked[j]) or {"w": 0, "l": 0}
            if (wi.get("w"), wi.get("l")) != (wj.get("w"), wj.get("l")):
                break
            j += 1
        if j - i > 1:
            block = ranked[i:j]
            block.sort(key=lambda a: (-sum(h2h_wins(a, b) for b in block if b != a), random.random()))
            ranked[i:j] = block
        i = j
    return ranked


def _maybe_init_tournaments(ps_state: dict, week: int) -> None:
    if week != PS_TOURNAMENT_WEEKS[0]:
        return
    if ps_state.get("tournaments"):
        return
    seed_orders = {tier: _seed_tier_teams(ps_state, tier) for tier in range(1, 6)}
    ps_state["tournaments"] = init_tier_tournaments(seed_orders)


def _games_for_week(ps_state: dict, week: int) -> list[dict]:
    games: list[dict] = []
    if week in PS_REGULAR_WEEKS:
        games.extend(list((ps_state.get("schedule") or {}).get(str(week)) or []))
    if week in PS_TOURNAMENT_WEEKS:
        _maybe_init_tournaments(ps_state, week)
        games.extend(tournament_games_for_week(week, ps_state.get("tournaments") or {}))
    if week == PS_CHAMPIONSHIP_WEEK:
        tourn = ps_state.get("tournaments") or {}
        aa = (tourn.get("1") or {}).get("champion")
        ast = (tourn.get("2") or {}).get("champion")
        slot = championship_game_slot(all_americans_champ=aa, all_stars_champ=ast)
        champ = ps_state.get("championship") or {}
        if slot and not champ.get("game_id"):
            candidates = slot["candidates"]
            home = random.choice(candidates)
            away = candidates[1] if candidates[0] == home else candidates[0]
            slot["home_team_id"] = home
            slot["away_team_id"] = away
            ps_state["championship"] = slot
            games.append(slot)
    return games


def _update_scrubs_rosters(ps_state: dict, week: int) -> None:
    if week not in PS_ACTIVE_WEEKS:
        return
    scrubs_rosters = ps_state.setdefault("scrubs_rosters", {})
    for region in REGION_LETTERS:
        if (ps_state.get("scrubs_forfeit") or {}).get(region):
            continue
        pool = list((ps_state.get("scrubs_pools") or {}).get(region) or [])
        roster = build_scrubs_week_roster(pool)
        tid = ps_team_id(region, 6)
        team = (ps_state.get("teams") or {}).get(tid)
        if team is not None:
            team["roster"] = roster
    # Store combined scrubs snapshot keyed by week (all regions use same week key)
    combined: list[dict] = []
    for region in REGION_LETTERS:
        tid = ps_team_id(region, 6)
        combined.extend(_resolve_team_roster(ps_state, tid, week))
    scrubs_rosters[str(week)] = combined


def _classify_ps_game(
    game: dict, ps_state: dict, week: int
) -> tuple[str, list[dict], list[dict], str | None, str | None]:
    """Resolve rosters and decide how a game terminates WITHOUT simulating.

    Returns ``(kind, home_roster, away_roster, home_name, away_name)`` where kind is
    ``invalid`` | ``forfeit_home`` (home wins) | ``forfeit_away`` (away wins) | ``skip`` |
    ``playable``. Shared by the serial and pooled paths so their forfeit/skip rules can
    never diverge. Names are only resolved for a playable game.
    """
    home_id = game.get("home_team_id")
    away_id = game.get("away_team_id")
    if not home_id or not away_id:
        return ("invalid", [], [], None, None)

    home_roster = _resolve_team_roster(ps_state, str(home_id), week)
    away_roster = _resolve_team_roster(ps_state, str(away_id), week)
    home_team = (ps_state.get("teams") or {}).get(str(home_id)) or {}
    away_team = (ps_state.get("teams") or {}).get(str(away_id)) or {}

    if int(home_team.get("tier") or 0) == 6 and len(home_roster) < SCRUBS_MIN_PLAYERS_TO_COMPETE:
        return ("forfeit_away", home_roster, away_roster, None, None)
    if int(away_team.get("tier") or 0) == 6 and len(away_roster) < SCRUBS_MIN_PLAYERS_TO_COMPETE:
        return ("forfeit_home", home_roster, away_roster, None, None)
    if len(home_roster) < 5 or len(away_roster) < 5:
        return ("skip", home_roster, away_roster, None, None)

    home_name = home_team.get("display_name") or str(home_id)
    away_name = away_team.get("display_name") or str(away_id)
    return ("playable", home_roster, away_roster, home_name, away_name)


def _apply_ps_terminal_kind(game: dict, ps_state: dict, kind: str) -> dict | None:
    """Apply a non-playable outcome (invalid/forfeit/skip) to game + standings."""
    home_id = str(game.get("home_team_id") or "")
    away_id = str(game.get("away_team_id") or "")
    if kind == "invalid":
        return None
    if kind == "forfeit_away":
        _apply_standings(ps_state, away_id, home_id, 6)
        game.update({"status": "forfeit", "home_score": 0, "away_score": 0, "winner": away_id})
    elif kind == "forfeit_home":
        _apply_standings(ps_state, home_id, away_id, 6)
        game.update({"status": "forfeit", "home_score": 0, "away_score": 0, "winner": home_id})
    elif kind == "skip":
        game["status"] = "skipped"
    return game


def _persist_and_apply_ps_result(
    game: dict,
    ps_state: dict,
    week: int,
    franchise_id_str: str,
    *,
    away_score: int,
    home_score: int,
    summary: dict,
) -> None:
    """Serial apply of a completed PS sim: write box score, advance standings/bracket,
    roll up player stats. Shared by the serial and pooled paths."""
    game_id = str(game.get("game_id"))
    summary = dict(summary)
    summary["_id"] = game_id
    summary["franchise_id"] = franchise_id_str
    summary["week"] = week
    summary["mode"] = "practice_squad"
    db.games.update_one({"_id": game_id}, {"$set": summary}, upsert=True)

    _advance_ps_result(
        game,
        ps_state,
        home_score=home_score,
        away_score=away_score,
        status="completed",
    )

    sources = _player_sources_from_ps_state(ps_state)
    try:
        apply_ps_game_stats(str(game_id), franchise_id_str, player_sources=sources)
    except Exception as ex:
        # The full game and its result are already durable. A stats-rollup error
        # must not replay the game or apply standings twice; the existing PS
        # backfill path can rebuild these aggregates from the saved box score.
        logger.error("PS stats rollup error game_id=%s: %s", game_id, ex, exc_info=True)
        game["player_stats_status"] = "rollup_failed_backfill_required"
        game["player_stats_error"] = str(ex)
    else:
        game["player_stats_status"] = "applied"
        applied = ps_state.setdefault("applied_games", [])
        if str(game_id) not in applied:
            applied.append(str(game_id))


def _sim_one_game(
    game: dict,
    ps_state: dict,
    week: int,
    franchise_id_str: str,
    fpd_by_id: dict,
    frd_by_id: dict,
) -> dict | None:
    if game.get("status") in PS_TERMINAL_GAME_STATUSES:
        return game

    kind, home_roster, away_roster, home_name, away_name = _classify_ps_game(game, ps_state, week)
    if kind != "playable":
        return _apply_ps_terminal_kind(game, ps_state, kind)

    home_id = game.get("home_team_id")
    away_id = game.get("away_team_id")
    game_id = str(game.get("game_id") or generate_game_id())
    game["game_id"] = game_id
    away_score, home_score, summary = run_ps_full_simulation(
        home_display_name=home_name,
        away_display_name=away_name,
        home_team_id=str(home_id),
        away_team_id=str(away_id),
        home_roster=home_roster,
        away_roster=away_roster,
        fpd_by_id=fpd_by_id,
        frd_by_id=frd_by_id,
        game_id=game_id,
    )
    _persist_and_apply_ps_result(
        game, ps_state, week, franchise_id_str,
        away_score=away_score, home_score=home_score, summary=summary,
    )
    return game


# Key sets persisted into training_job.games per game (mirror the serial loop's inline dicts).
_PS_RUNNING_KEYS = (
    "status", "game_id", "attempts", "attempt_id", "started_at", "last_error",
    "home_team_id", "away_team_id", "tier", "phase", "round", "match_index",
)
_PS_RESULT_KEYS = (
    "status", "game_id", "attempts", "attempt_id", "started_at", "updated_at",
    "last_error", "last_error_type", "last_error_at", "fallback_reason",
    "player_stats_status", "player_stats_error",
    "home_team_id", "away_team_id", "tier", "phase", "round", "match_index",
)


def _ps_use_pool() -> bool:
    """PS games ride the same pool kill-switch as the CPU-week games."""
    try:
        from BackEnd.api.franchise_routes import _franchise_cpu_use_pool
        return _franchise_cpu_use_pool()
    except Exception:  # noqa: BLE001 — never let a flag lookup break the sim
        return False


def _ps_handle_sim_error(game: dict, ps_state: dict, fid: str, week: int, ex: Exception) -> None:
    """Sentry-report a failed PS game, then either fall back (attempts exhausted) or
    mark it retry_pending. Extracted from the serial loop so the pooled path matches it."""
    logger.error("PS sim error: %s", ex, exc_info=True)
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("simulation_mode", "practice_squad")
            scope.set_tag("practice_squad_game_id", str(game.get("game_id")))
            scope.set_context("practice_squad_job", {
                "franchise_id": fid,
                "week": week,
                "attempt": int(game.get("attempts") or 0),
                "attempt_id": game.get("attempt_id"),
            })
            sentry_sdk.capture_exception(ex)
    except Exception:
        logger.debug("Sentry capture unavailable for PS sim failure", exc_info=True)
    if int(game.get("attempts") or 0) >= PS_FULL_ENGINE_MAX_ATTEMPTS:
        _complete_with_deterministic_fallback(
            game, ps_state, franchise_id_str=fid, week=week, error=ex,
        )
    else:
        # A retry restarts this game from tip-off while retaining its stable id.
        game["status"] = "retry_pending"
        game["last_error"] = str(ex)
        game["last_error_type"] = type(ex).__name__
        game["updated_at"] = datetime.utcnow().isoformat() + "Z"


def _run_ps_pending_pooled(
    pending: list[dict],
    ps_state: dict,
    week: int,
    franchise_id: ObjectId,
    fid: str,
    fpd_by_id: dict,
    frd_by_id: dict,
    existing_job: dict,
    job_games: dict,
) -> None:
    """Batch path: simulate all pending PS games in a spawn pool, then apply results
    SERIALLY (standings/brackets/stats mutate one shared ps_state). Cheap outcomes
    (forfeit/skip) and any game the pool couldn't finish fall to the serial ladder.
    Persists ps_state once up front (all marked running) and once after the batch."""
    from BackEnd.utils.cpu_week_pool import pool_worker_count, simulate_ps_games_pooled

    _t0 = time.time()
    # 1. Mark every pending game running + persist ONCE (resumable checkpoint).
    for g in pending:
        g["status"] = "running"
        g["game_id"] = str(g.get("game_id") or generate_game_id())
        g["attempts"] = int(g.get("attempts") or 0) + 1
        g["attempt_id"] = str(uuid.uuid4())
        g["started_at"] = datetime.utcnow().isoformat() + "Z"
        job_games[_training_game_key(g)] = {k: g.get(k) for k in _PS_RUNNING_KEYS}
    ps_state["training_job"] = {
        **existing_job, "week": week, "status": "processing",
        "games": job_games, "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    db.franchises.update_one({"_id": franchise_id}, {"$set": {"practice_squad": ps_state}})

    # 2. Classify: cheap outcomes applied inline now; playable games go to the pool.
    jobs: list[tuple] = []
    playable: list[tuple[int, dict]] = []
    for g in pending:
        kind, home_roster, away_roster, home_name, away_name = _classify_ps_game(g, ps_state, week)
        if kind != "playable":
            _apply_ps_terminal_kind(g, ps_state, kind)
            job_games[_training_game_key(g)] = {k: g.get(k) for k in _PS_RESULT_KEYS}
            continue
        idx = len(jobs)
        jobs.append((
            idx, fid, g["game_id"], home_name, away_name,
            str(g.get("home_team_id")), str(g.get("away_team_id")),
            home_roster, away_roster,
        ))
        playable.append((idx, g))

    # 3. Parallel sim (sim only — no state mutation in workers).
    results, errors, _leaks = simulate_ps_games_pooled(jobs)

    # 4. Serial apply, in stable order.
    for idx, g in playable:
        res = results.get(idx)
        try:
            if res is not None:
                away_score, home_score, summary = res
                _persist_and_apply_ps_result(
                    g, ps_state, week, fid,
                    away_score=away_score, home_score=home_score, summary=summary,
                )
            else:
                # Pool couldn't finish this game — serial ladder owns retry/fallback + writes.
                _sim_one_game(g, ps_state, week, fid, fpd_by_id, frd_by_id)
        except Exception as ex:  # noqa: BLE001
            _ps_handle_sim_error(g, ps_state, fid, week, ex)
        job_games[_training_game_key(g)] = {k: g.get(k) for k in _PS_RESULT_KEYS}

    db.franchises.update_one({"_id": franchise_id}, {"$set": {"practice_squad": ps_state}})
    logger.warning(
        "[PS-TIMING] franchise=%s week=%s | games=%s pooled=%s errors=%s | "
        "workers=%s | total=%.1fs",
        fid, week, len(pending), len(jobs), len(errors),
        pool_worker_count(), time.time() - _t0,
    )


def run_practice_squad_week(
    franchise_id: ObjectId,
    franchise_doc: dict,
    week: int,
    *,
    max_games: int | None = None,
) -> dict[str, Any]:
    """Sim all PS games for the given week; mutates and returns practice_squad state."""
    ps_state = dict(franchise_doc.get("practice_squad") or {})
    if not ps_state.get("initialized"):
        return ps_state

    if week not in PS_ACTIVE_WEEKS:
        return ps_state

    ps_state = ensure_ps_season_stats_backfilled(str(franchise_id), ps_state)

    if int(ps_state.get("trained_week") or 0) == week:
        return ps_state

    fid = str(franchise_id)
    fpd_by_id = {
        str(d["player_id"]): d
        for d in franchise_players_data_collection.find({"franchise_id": fid})
    }
    frd_by_id = {
        str(d["recruit_id"]): d
        for d in franchise_recruits_data_collection.find({"franchise_id": fid})
    }

    _update_scrubs_rosters(ps_state, week)
    games = _games_for_week(ps_state, week)
    existing_job = dict(ps_state.get("training_job") or {})
    if int(existing_job.get("week") or 0) != week:
        existing_job = {}
    job_games = dict(existing_job.get("games") or {})
    for g in games:
        game_key = _training_game_key(g)
        prior = job_games.get(game_key) or {}
        if prior.get("status") in ("running", "retry_pending"):
            g.update(
                {
                    key: prior[key]
                    for key in ("status", "game_id", "attempts", "attempt_id", "started_at", "last_error")
                    if prior.get(key) is not None
                }
            )
        job_games.setdefault(
            game_key,
            {
                key: g.get(key)
                for key in (
                    "status", "game_id", "attempts", "attempt_id", "started_at", "last_error",
                    "home_team_id", "away_team_id", "tier", "phase", "round", "match_index",
                )
            },
        )

    for g in games:
        if g.get("status") != "forfeit" or g.get("winner"):
            continue
        home_id = str(g.get("home_team_id") or "")
        away_id = str(g.get("away_team_id") or "")
        home_team = (ps_state.get("teams") or {}).get(home_id) or {}
        away_team = (ps_state.get("teams") or {}).get(away_id) or {}
        scrubs_forfeit = ps_state.get("scrubs_forfeit") or {}
        home_ff = int(home_team.get("tier") or 0) == 6 and scrubs_forfeit.get(home_team.get("region"))
        away_ff = int(away_team.get("tier") or 0) == 6 and scrubs_forfeit.get(away_team.get("region"))
        tier = int(g.get("tier") or home_team.get("tier") or 6)
        if home_ff and not away_ff:
            _apply_standings(ps_state, away_id, home_id, tier)
            g.update({"winner": away_id, "home_score": 0, "away_score": 0})
        elif away_ff and not home_ff:
            _apply_standings(ps_state, home_id, away_id, tier)
            g.update({"winner": home_id, "home_score": 0, "away_score": 0})

    for g in games:
        game_key = _training_game_key(g)
        job_games[game_key] = {
            **dict(job_games.get(game_key) or {}),
            **{
                key: g.get(key)
                for key in (
                    "status", "game_id", "attempts", "attempt_id", "started_at", "last_error",
                    "home_team_id", "away_team_id", "tier", "phase", "round", "match_index",
                )
            },
        }

    pending = [
        g for g in games
        if g.get("status") in ("scheduled", "retry_pending") or _running_game_is_stale(g)
    ]
    if max_games is not None:
        pending = pending[:max(0, int(max_games))]

    # Pooled batch path: when the pool is enabled and we're not capped to a single
    # game (the one-game-per-poll UI budget), sim the whole pending batch in parallel
    # and apply serially. Falls through to the serial loop otherwise.
    if pending and max_games is None and _ps_use_pool() and len(pending) > 1:
        _run_ps_pending_pooled(
            pending, ps_state, week, franchise_id, fid, fpd_by_id, frd_by_id,
            existing_job, job_games,
        )
        pending = []

    for g in pending:
        g["status"] = "running"
        g["game_id"] = str(g.get("game_id") or generate_game_id())
        g["attempts"] = int(g.get("attempts") or 0) + 1
        g["attempt_id"] = str(uuid.uuid4())
        g["started_at"] = datetime.utcnow().isoformat() + "Z"
        job_games[_training_game_key(g)] = {
            key: g.get(key)
            for key in (
                "status", "game_id", "attempts", "attempt_id", "started_at", "last_error",
                "home_team_id", "away_team_id", "tier", "phase", "round", "match_index",
            )
        }
        ps_state["training_job"] = {
            **existing_job,
            "week": week,
            "status": "processing",
            "games": job_games,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        db.franchises.update_one(
            {"_id": franchise_id},
            {"$set": {"practice_squad": ps_state}},
        )
        try:
            _sim_one_game(g, ps_state, week, fid, fpd_by_id, frd_by_id)
        except Exception as ex:
            logger.error("PS sim error: %s", ex, exc_info=True)
            try:
                import sentry_sdk

                with sentry_sdk.push_scope() as scope:
                    scope.set_tag("simulation_mode", "practice_squad")
                    scope.set_tag("practice_squad_game_id", str(g.get("game_id")))
                    scope.set_context("practice_squad_job", {
                        "franchise_id": fid,
                        "week": week,
                        "attempt": int(g.get("attempts") or 0),
                        "attempt_id": g.get("attempt_id"),
                    })
                    sentry_sdk.capture_exception(ex)
            except Exception:
                logger.debug("Sentry capture unavailable for PS sim failure", exc_info=True)
            if int(g.get("attempts") or 0) >= PS_FULL_ENGINE_MAX_ATTEMPTS:
                _complete_with_deterministic_fallback(
                    g,
                    ps_state,
                    franchise_id_str=fid,
                    week=week,
                    error=ex,
                )
            else:
                # A retry restarts this game from tip-off while retaining its stable id.
                g["status"] = "retry_pending"
                g["last_error"] = str(ex)
                g["last_error_type"] = type(ex).__name__
                g["updated_at"] = datetime.utcnow().isoformat() + "Z"
        job_games[_training_game_key(g)] = {
            key: g.get(key)
            for key in (
                "status", "game_id", "attempts", "attempt_id", "started_at", "updated_at",
                "last_error", "last_error_type", "last_error_at", "fallback_reason",
                "player_stats_status", "player_stats_error",
                "home_team_id", "away_team_id", "tier", "phase", "round", "match_index",
            )
        }
        db.franchises.update_one(
            {"_id": franchise_id},
            {"$set": {"practice_squad": ps_state}},
        )

    all_done = bool(job_games) and all(
        row.get("status") in PS_TERMINAL_GAME_STATUSES
        for row in job_games.values()
    )
    if all_done:
        ps_state["trained_week"] = week
    ps_state["training_job"] = {
        **existing_job,
        "week": week,
        "status": "complete" if all_done else "processing",
        "total_games": len(job_games),
        "completed_games": sum(
            1
            for row in job_games.values()
            if row.get("status") in PS_TERMINAL_GAME_STATUSES
        ),
        "games": job_games,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    return ps_state


def build_roster_announcement_story(
    ps_state: dict,
    *,
    franchise_id: str,
    team_id: str | None = None,
) -> dict[str, Any]:
    rich_lines: list[dict[str, Any]] = []
    q = f"franchise_id={franchise_id}"
    if team_id:
        q += f"&team_id={team_id}"

    for region in REGION_LETTERS:
        rich_lines.append({"type": "heading", "text": f"Region {region}"})
        for tier in range(1, 6):
            tid = ps_team_id(region, tier)
            team = (ps_state.get("teams") or {}).get(tid) or {}
            display = team.get("display_name") or ps_display_name(region, tier)
            roster = team.get("roster") or []
            parts = [f"{p.get('name')} ({int(p.get('best_rt') or 0)})" for p in roster]
            rich_lines.append(
                {
                    "type": "team_roster",
                    "label": display,
                    "href": f"/team-roster-view.html?mode=practice_squad&ps_team_id={tid}&{q}",
                    "players_line": ", ".join(parts) if parts else "No players assigned.",
                }
            )

    return {
        "story_id": "w1-ps-rosters",
        "week": 1,
        "type": "ps_rosters_announced",
        "headline": "Practice Squad Rosters Announced",
        "rich_lines": rich_lines,
        "created_at": datetime.utcnow(),
    }


def _completed_games_for_week(ps_state: dict, week: int) -> list[dict]:
    games: list[dict] = []
    teams_map = ps_state.get("teams") or {}

    if week in PS_REGULAR_WEEKS:
        for g in (ps_state.get("schedule") or {}).get(str(week)) or []:
            if g.get("status") == "completed" and g.get("game_id"):
                games.append(g)
        return games

    if week in PS_TOURNAMENT_WEEKS:
        round_num = week - PS_TOURNAMENT_WEEKS[0] + 1
        round_key = bracket_engine.get_round_name(round_num)
        for _tier_key, tstate in (ps_state.get("tournaments") or {}).items():
            for m in (tstate.get("bracket") or {}).get(round_key) or []:
                if not m.get("game_id"):
                    continue
                score = m.get("score") or {}
                home_id = str(m.get("home_team") or "")
                away_id = str(m.get("away_team") or "")
                games.append(
                    {
                        "home_team_id": home_id,
                        "away_team_id": away_id,
                        "home_score": score.get(home_id),
                        "away_score": score.get(away_id),
                        "game_id": str(m.get("game_id")),
                        "status": "completed",
                    }
                )
        return games

    if week == PS_CHAMPIONSHIP_WEEK:
        champ = ps_state.get("championship") or {}
        if champ.get("game_id") and champ.get("status") == "completed":
            games.append(champ)
    return games


def build_game_results_story(
    ps_state: dict,
    week: int,
    *,
    franchise_id: str,
    team_id: str | None = None,
) -> dict[str, Any] | None:
    completed = _completed_games_for_week(ps_state, week)
    if not completed:
        return None

    q = f"franchise_id={franchise_id}"
    if team_id:
        q += f"&team_id={team_id}"

    story_id = f"w{week}-ps-game-results"
    news_return = f"/news.html?{q}&story={story_id}"
    return_url = quote(news_return, safe="")

    rich_lines: list[dict[str, Any]] = [
        {
            "type": "link",
            "label": "Practice Squad Standings",
            "href": f"/practice-squad-standings.html?{q}",
        },
        {"type": "gap"},
    ]

    teams_map = ps_state.get("teams") or {}
    for g in completed:
        home_id = str(g.get("home_team_id") or "")
        away_id = str(g.get("away_team_id") or "")
        home_name = (teams_map.get(home_id) or {}).get("display_name") or home_id
        away_name = (teams_map.get(away_id) or {}).get("display_name") or away_id
        hs = g.get("home_score")
        aw = g.get("away_score")
        gid = g.get("game_id")
        rich_lines.append(
            {
                "type": "game_result",
                "text": f"{home_name} {hs}, {away_name} {aw}",
                "box_score_href": f"/box-score.html?game_id={gid}&mode=practice_squad&{q}&return_url={return_url}",
            }
        )

    return {
        "story_id": story_id,
        "week": week,
        "type": "ps_game_results",
        "headline": f"Week {week} Practice Squad Game Results",
        "rich_lines": rich_lines,
        "created_at": datetime.utcnow(),
    }
