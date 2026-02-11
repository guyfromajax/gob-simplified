import random


def _resolve_keyed_entry(source_obj: dict, candidates: list[str]) -> dict:
    """
    Resolve a dict entry from source_obj by trying multiple key candidates.
    Tries exact keys first, then case-insensitive string matching.
    """
    if not isinstance(source_obj, dict):
        return {}

    for key in candidates:
        if key and key in source_obj and isinstance(source_obj.get(key), dict):
            return source_obj.get(key, {})

    lowered = {str(k).lower(): v for k, v in source_obj.items()}
    for key in candidates:
        if key:
            val = lowered.get(str(key).lower())
            if isinstance(val, dict):
                return val
    return {}


def calculate_fb_opp_modifier_change(opponent_scouting: dict) -> int:
    """Calculate EOG fb_opp_modifier change from opponent fast-break performance."""
    opponent_fb_rate = opponent_scouting.get("fb_rate", 0)
    opponent_fb_entries = opponent_scouting.get("fb_entries", 0)
    if opponent_fb_rate < 20:
        return random.randint(0, 2)
    if opponent_fb_rate > 55 or opponent_fb_entries > 12:
        return random.randint(-3, -2)
    return random.randint(-1, 0)


def calculate_pt_opp_modifier_change(opponent_scouting: dict) -> int:
    """Calculate EOG pt_opp_modifier change from opponent press/trap performance."""
    opponent_pt_rate = opponent_scouting.get("pt_combined_rate", 0)
    opponent_pt_attempts = opponent_scouting.get("pt_total_attempts", 0)
    if opponent_pt_rate < 20:
        return random.randint(1, 2)
    if opponent_pt_rate > 50 or opponent_pt_attempts > 12:
        return random.randint(-3, -2)
    return random.randint(-2, -1)


def _calculate_special_situations_from_team_scouting(team_obj: dict) -> dict:
    """
    Build FB/PT special-situations metrics from teams[team_id].scouting only.
    This is the canonical source for finalized game performance metrics.
    """
    offense = (team_obj or {}).get("scouting", {}).get("offense", {})
    defense = (team_obj or {}).get("scouting", {}).get("defense", {})

    fb_entries = offense.get("Fast_Break_Entries", 0)
    fb_success = offense.get("Fast_Break_Success", 0)
    fb_rate = (fb_success / fb_entries * 100) if fb_entries > 0 else 0

    hct = defense.get("HCT", {})
    hct_used = hct.get("used", 0)
    hct_success = hct.get("success", 0)

    fcp = defense.get("FCP", {})
    fcp_used = fcp.get("used", 0)
    fcp_success = fcp.get("success", 0)

    pt_total_attempts = hct_used + fcp_used
    pt_total_successes = hct_success + fcp_success
    pt_combined_rate = (pt_total_successes / pt_total_attempts * 100) if pt_total_attempts > 0 else 0

    return {
        "fb_rate": fb_rate,
        "fb_entries": fb_entries,
        "pt_combined_rate": pt_combined_rate,
        "pt_total_attempts": pt_total_attempts,
    }


def calculate_team_totals_from_sources(
    team_id_label: str,
    team_name: str,
    team_totals_obj: dict,
    box_score_obj: dict,
) -> dict:
    """
    Resolve canonical team totals for EOG.
    Priority:
    1) team_totals[team_name]
    2) team_totals[team_id_label]
    3) aggregate from box_score[team_id_label] / box_score[team_name]
    """
    totals = {}
    if isinstance(team_totals_obj, dict):
        totals = team_totals_obj.get(team_name) or team_totals_obj.get(team_id_label) or {}

    if totals:
        return {
            "FGM": totals.get("FGM", 0),
            "FGA": totals.get("FGA", 0),
            "TO": totals.get("TO", 0),
            "STL": totals.get("STL", 0),
            "DREB": totals.get("DREB", 0),
            "OREB": totals.get("OREB", 0),
        }

    def _aggregate_from_box(team_box_score):
        out = {"FGM": 0, "FGA": 0, "TO": 0, "STL": 0, "DREB": 0, "OREB": 0}
        if isinstance(team_box_score, dict):
            for player_stats in team_box_score.values():
                if isinstance(player_stats, dict):
                    out["FGM"] += player_stats.get("FGM", 0)
                    out["FGA"] += player_stats.get("FGA", 0)
                    out["TO"] += player_stats.get("TO", 0)
                    out["STL"] += player_stats.get("STL", 0)
                    out["DREB"] += player_stats.get("DREB", 0)
                    out["OREB"] += player_stats.get("OREB", 0)
        return out

    from_box = _aggregate_from_box((box_score_obj or {}).get(team_id_label, {}))
    if not from_box.get("FGA"):
        from_box = _aggregate_from_box((box_score_obj or {}).get(team_name, {}))
    return from_box


def calculate_special_situations_from_sources(
    team_name: str,
    team_obj: dict,
    team_stats_obj: dict,
    team_id_label: str | None = None,
) -> dict:
    """
    Resolve canonical FB/PT special-situations metrics for EOG.
    Priority:
    1) team_stats[team_name].offense/defense
    2) teams[team_id].scouting offense/defense
    """
    key_candidates = [team_id_label, team_name]
    stats = _resolve_keyed_entry(team_stats_obj or {}, key_candidates)
    offense = stats.get("offense", {}) if isinstance(stats, dict) else {}
    defense = stats.get("defense", {}) if isinstance(stats, dict) else {}

    if not offense and not defense:
        offense = (team_obj or {}).get("scouting", {}).get("offense", {})
        defense = (team_obj or {}).get("scouting", {}).get("defense", {})

    fb_entries = offense.get("Fast_Break_Entries", 0)
    fb_success = offense.get("Fast_Break_Success", 0)
    fb_rate = (fb_success / fb_entries * 100) if fb_entries > 0 else 0

    hct = defense.get("HCT", {})
    hct_used = hct.get("used", 0)
    hct_success = hct.get("success", 0)

    fcp = defense.get("FCP", {})
    fcp_used = fcp.get("used", 0)
    fcp_success = fcp.get("success", 0)

    pt_total_attempts = hct_used + fcp_used
    pt_total_successes = hct_success + fcp_success
    pt_combined_rate = (pt_total_successes / pt_total_attempts * 100) if pt_total_attempts > 0 else 0

    return {
        "fb_rate": fb_rate,
        "fb_entries": fb_entries,
        "pt_combined_rate": pt_combined_rate,
        "pt_total_attempts": pt_total_attempts,
    }


def build_eog_inputs_from_game_doc(game_doc: dict, home_team_id: str, away_team_id: str) -> dict:
    """
    Build canonical EOG inputs from a single frozen game snapshot.
    Returns:
    {
      "home": {"team_id", "team_name", "totals", "scouting"},
      "away": {"team_id", "team_name", "totals", "scouting"},
      "source": "teams.scouting+team_totals_or_box_score"
    }
    """
    teams_obj = (game_doc or {}).get("teams", {})
    team_totals_obj = (game_doc or {}).get("team_totals", {})
    box_score = (game_doc or {}).get("box_score", {})

    home_team_obj = teams_obj.get(home_team_id, {}) if isinstance(teams_obj, dict) else {}
    away_team_obj = teams_obj.get(away_team_id, {}) if isinstance(teams_obj, dict) else {}

    home_team_name = (
        home_team_obj.get("name")
        or ((game_doc or {}).get("home_team", {}).get("name") if isinstance((game_doc or {}).get("home_team"), dict) else (game_doc or {}).get("home_team"))
        or home_team_id
    )
    away_team_name = (
        away_team_obj.get("name")
        or ((game_doc or {}).get("away_team", {}).get("name") if isinstance((game_doc or {}).get("away_team"), dict) else (game_doc or {}).get("away_team"))
        or away_team_id
    )

    home_totals = calculate_team_totals_from_sources(home_team_id, home_team_name, team_totals_obj, box_score)
    away_totals = calculate_team_totals_from_sources(away_team_id, away_team_name, team_totals_obj, box_score)

    home_scouting = _calculate_special_situations_from_team_scouting(home_team_obj)
    away_scouting = _calculate_special_situations_from_team_scouting(away_team_obj)

    return {
        "home": {
            "team_id": home_team_id,
            "team_name": home_team_name,
            "totals": home_totals,
            "scouting": home_scouting,
        },
        "away": {
            "team_id": away_team_id,
            "team_name": away_team_name,
            "totals": away_totals,
            "scouting": away_scouting,
        },
        "source": "teams.scouting+team_totals_or_box_score",
    }
