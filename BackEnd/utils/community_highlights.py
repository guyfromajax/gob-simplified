"""
Universal Community Highlights feed (Mode Select). Max 20 entries; oldest dropped on push.

Pending payload is set after phase A (GP delta = users.geek_points after user-game awards minus before).
The public row is appended after phase B completes (when FTD natl_rank is updated for the week).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from BackEnd.db import (
    community_highlights_collection,
    franchise_state_collection,
    franchise_team_data_collection,
    franchises_collection,
    games_collection,
    teams_collection,
    users_collection,
)
from BackEnd.utils.franchise_geek_points import teams_match_for_franchise
from BackEnd.utils.franchise_standings import calculate_franchise_standings

logger = logging.getLogger(__name__)

FEED_DOC_ID = "global_feed"
REGULAR_SEASON_LAST_WEEK = 26
TOP_DEFENDER_MIN_DEFA_SEASON = 156  # 26 games × 6 DEFA / game


def _display_username_for_highlight(user_doc: dict | None) -> str:
    """Match leaderboard naming: users.username, else email local-part, else Coach."""
    if not user_doc:
        return "Coach"
    username = str(user_doc.get("username") or "").strip()
    if username:
        return username
    email = str(user_doc.get("email") or "").strip()
    return email.split("@", 1)[0].strip() if email else "Coach"


def get_user_team_from_franchise_doc(franchise_doc: dict) -> tuple[str | None, str | None]:
    """Same behavior as franchise_routes.get_user_team_from_franchise (no import cycle)."""
    user_team_id = franchise_doc.get("user_team_id")
    user_team_object_id = franchise_doc.get("user_team_object_id")
    if user_team_id and user_team_object_id:
        return (str(user_team_id), str(user_team_object_id))
    try:
        state = franchise_state_collection.find_one({"_id": "state"}) or {}
        team_name = state.get("team")
        if team_name:
            logger.warning(
                "[COMMUNITY_HIGHLIGHTS] franchise_state fallback for team=%s; migrate user_team fields",
                team_name,
            )
            team_doc = teams_collection.find_one({"name": team_name})
            if team_doc:
                return (str(team_name), str(team_doc["_id"]))
    except Exception as e:
        logger.debug("franchise_state not available: %s", e)
    return (None, None)


def _user_geek_points_total(owner_user_id: Any) -> int:
    if not owner_user_id:
        return 0
    try:
        oid = ObjectId(str(owner_user_id))
    except Exception:
        return 0
    u = users_collection.find_one({"_id": oid}, {"geek_points": 1})
    if not u:
        return 0
    return int(u.get("geek_points") or 0)


def user_geek_points_delta_for_user_game_block(
    franchise_doc: dict,
    gp_before: int,
) -> int:
    gp_after = _user_geek_points_total(franchise_doc.get("user_id"))
    return int(gp_after) - int(gp_before)


def user_geek_points_snapshot_for_franchise(franchise_doc: dict) -> int:
    return _user_geek_points_total(franchise_doc.get("user_id"))


# Marker stashed on the franchise doc by the complete-week user-game block (and
# the legacy save_result endpoint) when the user's just-played game changed their
# lead coaching archetype; consumed by the phase-B flush.
ARCHETYPE_PENDING_FIELD = "post_game_status.community_highlight_archetype_pending"


def lead_archetype_for_user(owner_user_id: Any) -> str:
    """Current denormalized lead_archetype key for a user ('' when none/no games)."""
    if not owner_user_id:
        return ""
    try:
        oid = ObjectId(str(owner_user_id))
    except Exception:
        return ""
    u = users_collection.find_one({"_id": oid}, {"lead_archetype": 1})
    return str((u or {}).get("lead_archetype") or "")


def _lead_archetype_for_display_username(display_username: str) -> str:
    """Best-effort backfill for older stored feed rows that predate lead_archetype."""
    username = str(display_username or "").strip()
    if not username:
        return ""
    user_doc = users_collection.find_one(
        {"username": username},
        {"lead_archetype": 1},
    )
    return str((user_doc or {}).get("lead_archetype") or "")


def record_archetype_change_if_any(
    franchise_id: ObjectId,
    owner_user_id: Any,
    lead_before: str,
) -> None:
    """After the user's game commits a new lead_archetype, stash a from/to marker
    on the franchise when it changed. The phase-B flush turns this into a feed row.
    Called right after finalize_game in the complete-week user-game block (and the
    legacy save_result endpoint) so a genuine first-time establishment fires while
    pre-existing archetypes do not."""
    lead_after = lead_archetype_for_user(owner_user_id)
    if not lead_after or lead_after == (lead_before or ""):
        return
    try:
        franchises_collection.update_one(
            {"_id": franchise_id},
            {"$set": {ARCHETYPE_PENDING_FIELD: {"from": lead_before or "", "to": lead_after}}},
        )
    except Exception:
        logger.exception("[COMMUNITY_HIGHLIGHTS] Failed to record archetype change marker")

    # A true *evolution* (changed from a prior archetype, not first-time
    # establishment) also queues the FCC "you have evolved" modal. First-time
    # establishment (lead_before empty) stays with the existing first-reveal modal.
    if lead_before and owner_user_id:
        try:
            users_collection.update_one(
                {"_id": ObjectId(str(owner_user_id))},
                {"$set": {"archetype_evolution_pending": lead_after}},
            )
        except Exception:
            logger.exception("[COMMUNITY_HIGHLIGHTS] Failed to set archetype_evolution_pending")


def _user_scores_from_row(user_team_id_str: Any, user_row: dict) -> tuple[int, int]:
    ut = str(user_team_id_str or "").strip()
    away_id = str(user_row.get("away_id") or "")
    home_id = str(user_row.get("home_id") or "")
    away_score = int(user_row.get("away_score") or 0)
    home_score = int(user_row.get("home_score") or 0)
    if teams_match_for_franchise(away_id, ut):
        return away_score, home_score
    if teams_match_for_franchise(home_id, ut):
        return home_score, away_score
    return away_score, home_score


def _scores_from_franchise_week_results(
    franchise_doc: dict,
    week: int,
    user_team_id_str: str,
) -> tuple[int, int] | None:
    """Recover user vs opponent scores from franchise.results[week] when pending lacks them."""
    wk = str(int(week))
    rows = franchise_doc.get("results", {}).get(wk)
    if not isinstance(rows, list):
        return None
    ut = str(user_team_id_str or "").strip()
    for r in rows:
        if not isinstance(r, dict):
            continue
        away_id = str(r.get("away_id") or "")
        home_id = str(r.get("home_id") or "")
        if teams_match_for_franchise(away_id, ut) or teams_match_for_franchise(home_id, ut):
            return _user_scores_from_row(ut, r)
    return None


def _eos_championship_kind(user_won: bool, eos_game_meta: dict | None) -> str | None:
    """Mirror maybe_award_franchise_eos_title_championship title rounds."""
    if not user_won or not eos_game_meta:
        return None
    phase = eos_game_meta.get("phase")
    rnd = int(eos_game_meta.get("round") or 0)
    if phase == "conference" and rnd == 3:
        return "conf_tournament"
    if phase == "region" and rnd == 2:
        return "region_tournament"
    if phase == "national" and rnd == 3:
        return "national_tournament"
    return None


def build_community_highlight_pending(
    *,
    week: int,
    user_team_id_str: Any,
    user_row: dict,
    gp_delta: int,
    game_id: str | None = None,
    eos_game_meta: dict | None = None,
) -> dict[str, Any]:
    ut = str(user_team_id_str or "").strip()
    away_id = str(user_row.get("away_id") or "")
    home_id = str(user_row.get("home_id") or "")
    away_score = int(user_row.get("away_score") or 0)
    home_score = int(user_row.get("home_score") or 0)
    if teams_match_for_franchise(away_id, ut):
        opp = home_id
        user_won = away_score > home_score
    elif teams_match_for_franchise(home_id, ut):
        opp = away_id
        user_won = home_score > away_score
    else:
        logger.warning(
            "[COMMUNITY_HIGHLIGHTS] user team not in saved row away=%s home=%s user=%s",
            away_id,
            home_id,
            ut,
        )
        opp = home_id or away_id
        user_won = False

    user_score, opp_score = _user_scores_from_row(ut, user_row)
    out: dict[str, Any] = {
        "week": int(week),
        "gp_delta": int(gp_delta),
        "opponent_team_id_str": str(opp),
        "user_won": bool(user_won),
        "user_score": int(user_score),
        "opponent_score": int(opp_score),
    }
    if game_id:
        out["game_id"] = str(game_id).strip()
    kind = _eos_championship_kind(user_won, eos_game_meta)
    if kind:
        out["eos_championship"] = {
            "kind": kind,
            "conference": eos_game_meta.get("conference"),
            "region": eos_game_meta.get("region"),
        }
    return out


def _ftd_team_display(franchise_id: ObjectId, team_id_str: str) -> tuple[str, str, str, int]:
    """team_name, primary_hex, secondary_hex, natl_rank from FTD with teams fallback."""
    try:
        tid = ObjectId(str(team_id_str).strip())
    except Exception:
        return "?", "#27408E", "#15181f", 999
    ftd = franchise_team_data_collection.find_one(
        {"franchise_id": franchise_id, "team_id": tid},
        {"team_name": 1, "primary_color": 1, "secondary_color": 1, "natl_rank": 1},
    )
    core = teams_collection.find_one({"_id": tid}, {"name": 1, "primary_color": 1, "secondary_color": 1})
    name = (ftd or {}).get("team_name") or (core or {}).get("name") or "?"
    primary = (ftd or {}).get("primary_color") or (core or {}).get("primary_color") or "#27408E"
    secondary = (ftd or {}).get("secondary_color") or (core or {}).get("secondary_color") or "#15181f"
    raw_nr = (ftd or {}).get("natl_rank")
    try:
        nr = int(raw_nr) if raw_nr is not None and str(raw_nr).strip() != "" else 999
    except (TypeError, ValueError):
        nr = 999
    return str(name), str(primary), str(secondary), nr


def _natl_rank_now_ranked_label(natl_rank: int) -> str:
    """Always `#n` or `#--` for copy 'now ranked …'."""
    if natl_rank is None or natl_rank <= 0 or natl_rank >= 999:
        return "#--"
    return f"#{int(natl_rank)}"


def _ftd_team_id_map(franchise_id: ObjectId) -> dict[str, dict]:
    docs = list(
        franchise_team_data_collection.find({"franchise_id": franchise_id}, {"team_id": 1})
    )
    return {str(d["team_id"]): {} for d in docs if d.get("team_id")}


def _user_regular_season_record(franchise_doc: dict, user_team_id_str: str) -> str:
    results = franchise_doc.get("results") or {}
    filtered: dict[str, Any] = {}
    for k, v in results.items():
        if not str(k).isdigit():
            continue
        wk = int(k)
        if 1 <= wk <= REGULAR_SEASON_LAST_WEEK and isinstance(v, list):
            filtered[k] = v
    team_map = _ftd_team_id_map(ObjectId(str(franchise_doc["_id"])))
    st = calculate_franchise_standings(filtered, team_map)
    row = st.get(str(user_team_id_str).strip()) or st.get(str(ObjectId(str(user_team_id_str).strip())))
    if not row:
        for tid_key, rec in st.items():
            if teams_match_for_franchise(tid_key, user_team_id_str):
                row = rec
                break
    if not row:
        return "0-0"
    return f"{int(row.get('W', 0))}-{int(row.get('L', 0))}"


def _user_conference_rs_champion(franchise_doc: dict, user_team_id_str: str) -> bool:
    """User's team is #1 seed in their conference bracket (regular-season conference title)."""
    ct_all = franchise_doc.get("conference_tournaments") or {}
    if not ct_all:
        return False
    try:
        tid = ObjectId(str(user_team_id_str).strip())
    except Exception:
        return False
    team_doc = teams_collection.find_one({"_id": tid}, {"conference": 1})
    if not team_doc:
        return False
    conf = team_doc.get("conference")
    if conf is None or not (1 <= int(conf) <= 16):
        return False
    ct = ct_all.get(str(int(conf))) or ct_all.get(conf)
    if not isinstance(ct, dict):
        return False
    seeds = ct.get("seeds") or {}
    if not isinstance(seeds, dict):
        return False
    uid_str = str(tid)
    seed = seeds.get(uid_str)
    if seed is None:
        seed = seeds.get(user_team_id_str)
    if seed is None:
        for k, v in seeds.items():
            if teams_match_for_franchise(k, user_team_id_str) and isinstance(v, int):
                seed = v
                break
    return seed == 1


def _top_defender_season_summary(franchise_id_str: str, user_team_id_str: str) -> dict[str, Any] | None:
    from BackEnd.api.franchise_routes import get_team_player_stats

    players = get_team_player_stats(franchise_id_str, user_team_id_str, scope="season", sort=None, limit=None)
    best_pct = -1.0
    best: dict[str, Any] | None = None
    for p in players:
        st = p.get("stats") or {}
        gp = int(st.get("GP", 0) or 0)
        if gp <= 0:
            continue
        def_a = int(st.get("DEF_A", 0) or 0)
        if def_a < TOP_DEFENDER_MIN_DEFA_SEASON:
            continue
        def_s = int(st.get("DEF_S", 0) or 0)
        pct = round((def_s / def_a) * 100) if def_a > 0 else 0
        if pct > best_pct:
            best_pct = float(pct)
            name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or "Unknown"
            best = {"name": name, "def_pct": int(pct)}
    return best


def _potg_from_game_id(game_id: str | None) -> dict[str, Any] | None:
    if not game_id:
        return None
    try:
        from BackEnd.api.franchise_routes import _calculate_potg_summary
    except Exception:
        logger.debug("[COMMUNITY_HIGHLIGHTS] POTG import failed", exc_info=True)
        return None
    doc = games_collection.find_one({"_id": game_id})
    if not doc and len(str(game_id)) == 24:
        try:
            doc = games_collection.find_one({"_id": ObjectId(game_id)})
        except Exception:
            doc = None
    if not doc:
        return None
    return _calculate_potg_summary(doc)


def _push_entries(entries: list[dict[str, Any]]) -> None:
    if not entries:
        return
    try:
        community_highlights_collection.update_one(
            {"_id": FEED_DOC_ID},
            {
                "$push": {"entries": {"$each": entries, "$position": 0, "$slice": 20}},
                "$setOnInsert": {"_id": FEED_DOC_ID},
            },
            upsert=True,
        )
    except Exception:
        logger.exception("[COMMUNITY_HIGHLIGHTS] Failed to push entries")


def _build_standard_entry(
    *,
    display_username: str,
    lead_archetype: str,
    ut_name: str,
    opp_name: str,
    user_won: bool,
    user_score: int,
    opponent_score: int,
    rank_label: str,
    natl_rank: int,
    user_team_record: str,
    gp_delta: int,
    primary: str,
    secondary: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "at": now.isoformat(),
        "entry_type": "standard",
        "variant": "standard_row",
        "username": display_username,
        "lead_archetype": str(lead_archetype or ""),
        "user_team_name": ut_name,
        "opponent_name": opp_name,
        "user_won": user_won,
        "user_score": int(user_score),
        "opponent_score": int(opponent_score),
        "natl_rank": natl_rank,
        "rank_label": rank_label,
        "user_team_record": str(user_team_record or "0-0"),
        "gp_delta": gp_delta,
        "primary_color": primary,
        "secondary_color": secondary,
    }


def _build_conference_rs_entry(
    *,
    display_username: str,
    lead_archetype: str,
    ut_name: str,
    conference_num: int,
    announcement_line: str,
    details_line: str,
    gp_delta: int,
    primary: str,
    secondary: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "at": now.isoformat(),
        "entry_type": "conference_rs_title",
        "variant": "standard_row",
        "username": display_username,
        "lead_archetype": str(lead_archetype or ""),
        "user_team_name": ut_name,
        "conference_num": int(conference_num),
        "announcement_line": announcement_line,
        "details_line": details_line,
        "gp_delta": gp_delta,
        "primary_color": primary,
        "secondary_color": secondary,
    }


def _team_colors_by_name(team_name: str) -> tuple[str, str]:
    """Primary/secondary hex colors for a team looked up by name. Falls back to defaults."""
    doc = teams_collection.find_one(
        {"name": team_name},
        {"primary_color": 1, "secondary_color": 1},
    ) or {}
    primary = str(doc.get("primary_color") or "#27408E")
    secondary = str(doc.get("secondary_color") or "#15181f")
    return primary, secondary


def _build_debut_entry(
    *,
    display_username: str,
    lead_archetype: str,
    user_team_name: str,
    opponent_name: str,
    user_won: bool,
    user_score: int,
    opponent_score: int,
    primary: str,
    secondary: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "at": now.isoformat(),
        "entry_type": "debut",
        "variant": "debut",
        "username": display_username,
        "lead_archetype": str(lead_archetype or ""),
        "user_team_name": user_team_name,
        "opponent_name": opponent_name,
        "user_won": bool(user_won),
        "user_score": int(user_score),
        "opponent_score": int(opponent_score),
        "primary_color": primary,
        "secondary_color": secondary,
    }


def push_debut_entry(
    *,
    owner_user_id: Any,
    user_team_name: str,
    opponent_name: str,
    user_won: bool,
    user_score: int,
    opponent_score: int,
) -> None:
    """Append a tutorial-game debut entry to the global community-highlights feed.

    Display username and user-team colors are resolved server-side from the
    canonical users / teams collections. Opponent colors are not surfaced on
    debut rows (the row is framed around the new coach's arrival, not the
    matchup).
    """
    user_doc = None
    if owner_user_id:
        try:
            user_doc = users_collection.find_one(
                {"_id": ObjectId(str(owner_user_id))},
                {"username": 1, "email": 1, "lead_archetype": 1},
            )
        except Exception:
            user_doc = None
    display_username = _display_username_for_highlight(user_doc)
    lead_archetype = str((user_doc or {}).get("lead_archetype") or "")

    primary, secondary = _team_colors_by_name(user_team_name)

    entry = _build_debut_entry(
        display_username=display_username,
        lead_archetype=lead_archetype,
        user_team_name=user_team_name,
        opponent_name=opponent_name,
        user_won=user_won,
        user_score=user_score,
        opponent_score=opponent_score,
        primary=primary,
        secondary=secondary,
    )
    _push_entries([entry])


def _build_archetype_entry(
    *,
    display_username: str,
    lead_archetype: str,
    is_first: bool,
    primary: str,
    secondary: str,
) -> dict[str, Any]:
    """Standard-row variant announcing a coach's lead archetype change. The archetype
    display name + badge are resolved on the frontend from the icon manifest."""
    now = datetime.now(timezone.utc)
    return {
        "at": now.isoformat(),
        "entry_type": "archetype_evolution",
        "variant": "standard_row",
        "username": display_username,
        "lead_archetype": str(lead_archetype),
        "is_first": bool(is_first),
        "primary_color": primary,
        "secondary_color": secondary,
    }


def _build_championship_entry(
    *,
    display_username: str,
    lead_archetype: str,
    ut_name: str,
    kind: str,
    scope_label: str,
    announcement_line: str,
    details_line: str,
    gp_delta: int,
    primary: str,
    secondary: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    variant = "national_gold" if kind == "national_tournament" else "standard_row"
    return {
        "at": now.isoformat(),
        "entry_type": "championship",
        "variant": variant,
        "tournament_kind": kind,
        "username": display_username,
        "lead_archetype": str(lead_archetype or ""),
        "user_team_name": ut_name,
        "scope_label": scope_label,
        "announcement_line": announcement_line,
        "details_line": details_line,
        "gp_delta": gp_delta,
        "primary_color": primary,
        "secondary_color": secondary,
    }


def flush_community_highlight_pending_after_week(
    franchise_id: ObjectId,
    completed_week: int,
) -> None:
    """If franchise has community_highlight_pending for this week, append feed row(s) and unset pending."""
    fresh = franchises_collection.find_one({"_id": franchise_id})
    if not fresh:
        return
    pending = (fresh.get("post_game_status") or {}).get("community_highlight_pending")
    if not pending or int(pending.get("week", -1)) != int(completed_week):
        return

    owner_id = fresh.get("user_id")
    user_doc = None
    if owner_id:
        try:
            user_doc = users_collection.find_one(
                {"_id": ObjectId(str(owner_id))},
                {"username": 1, "email": 1, "lead_archetype": 1},
            )
        except Exception:
            user_doc = None
    display_username = _display_username_for_highlight(user_doc)
    lead_archetype = str((user_doc or {}).get("lead_archetype") or "")

    _u_name, user_team_id_str = get_user_team_from_franchise_doc(fresh)
    if not user_team_id_str:
        logger.warning("[COMMUNITY_HIGHLIGHTS] No user team; skip flush franchise=%s", franchise_id)
        franchises_collection.update_one(
            {"_id": franchise_id},
            {"$unset": {
                "post_game_status.community_highlight_pending": "",
                "post_game_status.community_highlight_archetype_pending": "",
            }},
        )
        return

    ut_name, primary, secondary, natl_rank = _ftd_team_display(franchise_id, str(user_team_id_str))

    opp_id = pending.get("opponent_team_id_str")
    opp_name = "?"
    if opp_id:
        opp_name, _, _, _ = _ftd_team_display(franchise_id, str(opp_id))

    user_won = bool(pending.get("user_won"))
    gp_delta = int(pending.get("gp_delta") or 0)
    rank_label = _natl_rank_now_ranked_label(natl_rank)
    user_score = pending.get("user_score")
    opponent_score = pending.get("opponent_score")
    if user_score is None or opponent_score is None:
        recovered = _scores_from_franchise_week_results(fresh, int(completed_week), str(user_team_id_str))
        if recovered:
            user_score, opponent_score = recovered
        else:
            user_score, opponent_score = 0, 0
    user_score = int(user_score)
    opponent_score = int(opponent_score)

    franchise_id_str = str(fresh.get("_id"))
    entries: list[dict[str, Any]] = []

    eos_block = pending.get("eos_championship")
    if isinstance(eos_block, dict) and eos_block.get("kind"):
        kind = str(eos_block["kind"])
        potg = _potg_from_game_id(pending.get("game_id"))
        potg_part = ""
        if potg and isinstance(potg.get("stats"), dict):
            st = potg["stats"]
            potg_part = (
                f"POTG: {potg.get('name', '?')}, "
                f"{st.get('pts', 0)} PTS, {st.get('reb', 0)} REB, {st.get('ast', 0)} AST, "
                f"{st.get('defPct', 0)}% DEF%"
            )
        details_line = (
            f"Championship Game: {ut_name}: {user_score} - {opp_name}: {opponent_score}"
            + (f" -- {potg_part}" if potg_part else "")
        )
        scope_label = ""
        if kind == "conf_tournament":
            c = eos_block.get("conference")
            scope_label = str(int(c)) if c is not None else ""
        elif kind == "region_tournament":
            scope_label = str(eos_block.get("region") or "")
        elif kind == "national_tournament":
            scope_label = "National"
        if kind == "conf_tournament":
            ch_announce = f"{display_username}, coaching {ut_name}, wins the Conference {scope_label} Tournament!"
        elif kind == "region_tournament":
            ch_announce = f"{display_username}, coaching {ut_name}, wins the {scope_label} Regional Tournament!"
        else:
            ch_announce = f"{display_username}, coaching {ut_name}, wins the National Tournament!"
        entries.append(
            _build_championship_entry(
                display_username=display_username,
                lead_archetype=lead_archetype,
                ut_name=ut_name,
                kind=kind,
                scope_label=scope_label,
                announcement_line=ch_announce,
                details_line=details_line,
                gp_delta=gp_delta,
                primary=primary,
                secondary=secondary,
            )
        )
    else:
        user_team_record = _user_regular_season_record(fresh, str(user_team_id_str))
        entries.append(
            _build_standard_entry(
                display_username=display_username,
                lead_archetype=lead_archetype,
                ut_name=ut_name,
                opp_name=opp_name,
                user_won=user_won,
                user_score=user_score,
                opponent_score=opponent_score,
                rank_label=rank_label,
                natl_rank=natl_rank,
                user_team_record=user_team_record,
                gp_delta=gp_delta,
                primary=primary,
                secondary=secondary,
            )
        )

    if int(completed_week) == REGULAR_SEASON_LAST_WEEK and _user_conference_rs_champion(
        fresh, str(user_team_id_str)
    ):
        try:
            tid = ObjectId(str(user_team_id_str).strip())
            team_doc = teams_collection.find_one({"_id": tid}, {"conference": 1})
            conf_num = int(team_doc.get("conference")) if team_doc and team_doc.get("conference") is not None else 0
        except Exception:
            conf_num = 0
        rec = _user_regular_season_record(fresh, str(user_team_id_str))
        from BackEnd.api.franchise_routes import _build_team_leader_summary

        leaders = _build_team_leader_summary(franchise_id, str(user_team_id_str))
        ts = leaders.get("top_scorer") or {}
        tr = leaders.get("top_rebounder") or {}
        td = _top_defender_season_summary(franchise_id_str, str(user_team_id_str))
        def_part = ""
        if td:
            def_part = f" -- Top Defender: {td['name']}: {td['def_pct']}%"
        elif TOP_DEFENDER_MIN_DEFA_SEASON:
            def_part = " -- Top Defender: —"
        details_line = (
            f"Record: {rec} -- Top Scorer: {ts.get('name', '—')}: {ts.get('average', 0)} PPG"
            f" -- Top Rebounder: {tr.get('name', '—')}: {tr.get('average', 0)} RPG"
            f"{def_part}"
        )
        rs_announce = (
            f"{display_username}, coaching {ut_name}, wins the Conference {conf_num} regular season title."
        )
        entries.append(
            _build_conference_rs_entry(
                display_username=display_username,
                lead_archetype=lead_archetype,
                ut_name=ut_name,
                conference_num=conf_num,
                announcement_line=rs_announce,
                details_line=details_line,
                gp_delta=gp_delta,
                primary=primary,
                secondary=secondary,
            )
        )

    # Lead-archetype evolution row: the user's just-played game changed their lead
    # coaching archetype (marker set by record_archetype_change_if_any in the
    # complete-week user-game block). Appended below the game row.
    archetype_pending = (fresh.get("post_game_status") or {}).get(
        "community_highlight_archetype_pending"
    )
    if isinstance(archetype_pending, dict) and archetype_pending.get("to"):
        entries.append(
            _build_archetype_entry(
                display_username=display_username,
                lead_archetype=str(archetype_pending.get("to")),
                is_first=not str(archetype_pending.get("from") or ""),
                primary=primary,
                secondary=secondary,
            )
        )

    try:
        _push_entries(entries)
    except Exception:
        logger.exception("[COMMUNITY_HIGHLIGHTS] Failed to push entry")

    franchises_collection.update_one(
        {"_id": franchise_id},
        {"$unset": {
            "post_game_status.community_highlight_pending": "",
            "post_game_status.community_highlight_archetype_pending": "",
        }},
    )


def list_community_highlight_entries() -> list[dict[str, Any]]:
    doc = community_highlights_collection.find_one({"_id": FEED_DOC_ID})
    if not doc:
        return []
    entries = list(doc.get("entries") or [])
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("lead_archetype"):
            continue
        lead = _lead_archetype_for_display_username(entry.get("username") or entry.get("user_name") or "")
        if lead:
            entry["lead_archetype"] = lead
    return entries
