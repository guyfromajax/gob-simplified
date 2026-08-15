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


def _normalize_team_name_key(name: str | None) -> str | None:
    if not name:
        return None
    return str(name).replace("-", "_").replace(" ", "_").upper()


def _aggregate_from_box(team_box_score: dict) -> dict:
    out = {"FGM": 0, "FGA": 0, "TO": 0, "STL": 0, "DREB": 0, "OREB": 0, "F": 0}
    if isinstance(team_box_score, dict):
        for player_stats in team_box_score.values():
            if isinstance(player_stats, dict):
                out["FGM"] += player_stats.get("FGM", 0)
                out["FGA"] += player_stats.get("FGA", 0)
                out["TO"] += player_stats.get("TO", 0)
                out["STL"] += player_stats.get("STL", 0)
                out["DREB"] += player_stats.get("DREB", 0)
                out["OREB"] += player_stats.get("OREB", 0)
                out["F"] += player_stats.get("F", 0)
    return out


# NOTE: the old standalone calculate_fb_opp_modifier_change / calculate_pt_opp_modifier_change
# were drifted duplicates (older -3..-2 bands, read fb_entries) that production never ran.
# They are replaced by the extracted band functions below (§ EOG band logic), which are the
# SINGLE implementation that calculate_attr_changes calls and the tests validate (Task 7).


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
        "fb_success": fb_success,
        "hct_used": hct_used,
        "hct_success": hct_success,
        "fcp_used": fcp_used,
        "fcp_success": fcp_success,
        "pt_combined_rate": pt_combined_rate,
        "pt_total_attempts": pt_total_attempts,
        "pt_total_successes": pt_total_successes,
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
            "F": totals.get("F", 0),
        }

    from_box = _aggregate_from_box((box_score_obj or {}).get(team_id_label, {}))
    if not from_box.get("FGA"):
        from_box = _aggregate_from_box((box_score_obj or {}).get(team_name, {}))
    if not from_box.get("FGA"):
        from_box = _aggregate_from_box((box_score_obj or {}).get(_normalize_team_name_key(team_name), {}))
    if not from_box.get("FGA") and team_name:
        # Display→stored team_id at this boundary (lookup, not derive).
        # Do not change _normalize_team_name_key to strip punctuation.
        from BackEnd.utils.team_slug import identity_slugs_for_display_name

        for slug in identity_slugs_for_display_name(team_name):
            from_box = _aggregate_from_box((box_score_obj or {}).get(slug, {}))
            if from_box.get("FGA"):
                break
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
        "fb_success": fb_success,
        "hct_used": hct_used,
        "hct_success": hct_success,
        "fcp_used": fcp_used,
        "fcp_success": fcp_success,
        "pt_combined_rate": pt_combined_rate,
        "pt_total_attempts": pt_total_attempts,
        "pt_total_successes": pt_total_successes,
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
    team_stats_obj = (game_doc or {}).get("team_stats", {})

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

    home_totals = {}
    away_totals = {}
    home_totals_source = "none"
    away_totals_source = "none"

    # Primary source: unified teams object persisted by summarize_game_state.
    home_team_totals = (home_team_obj or {}).get("totals", {})
    if isinstance(home_team_totals, dict) and home_team_totals.get("FGA", 0) > 0:
        home_totals = {
            "FGM": home_team_totals.get("FGM", 0),
            "FGA": home_team_totals.get("FGA", 0),
            "TO": home_team_totals.get("TO", 0),
            "STL": home_team_totals.get("STL", 0),
            "DREB": home_team_totals.get("DREB", 0),
            "OREB": home_team_totals.get("OREB", 0),
            "F": home_team_totals.get("F", 0),
        }
        home_totals_source = "teams.totals"
    else:
        home_team_box = (home_team_obj or {}).get("box_score", {})
        home_team_box_totals = _aggregate_from_box(home_team_box)
        if home_team_box_totals.get("FGA", 0) > 0:
            home_totals = home_team_box_totals
            home_totals_source = "teams.box_score"

    away_team_totals = (away_team_obj or {}).get("totals", {})
    if isinstance(away_team_totals, dict) and away_team_totals.get("FGA", 0) > 0:
        away_totals = {
            "FGM": away_team_totals.get("FGM", 0),
            "FGA": away_team_totals.get("FGA", 0),
            "TO": away_team_totals.get("TO", 0),
            "STL": away_team_totals.get("STL", 0),
            "DREB": away_team_totals.get("DREB", 0),
            "OREB": away_team_totals.get("OREB", 0),
            "F": away_team_totals.get("F", 0),
        }
        away_totals_source = "teams.totals"
    else:
        away_team_box = (away_team_obj or {}).get("box_score", {})
        away_team_box_totals = _aggregate_from_box(away_team_box)
        if away_team_box_totals.get("FGA", 0) > 0:
            away_totals = away_team_box_totals
            away_totals_source = "teams.box_score"

    # Fallback sources for legacy documents.
    if not home_totals.get("FGA"):
        home_totals = calculate_team_totals_from_sources(home_team_id, home_team_name, team_totals_obj, box_score)
        if home_totals.get("FGA"):
            home_totals_source = "team_totals_or_box_score"
    if not away_totals.get("FGA"):
        away_totals = calculate_team_totals_from_sources(away_team_id, away_team_name, team_totals_obj, box_score)
        if away_totals.get("FGA"):
            away_totals_source = "team_totals_or_box_score"

    # Fallback for legacy/nested saves where top-level totals/box_score may be missing.
    if not home_totals.get("FGA"):
        nested_home_box = ((game_doc or {}).get("home_team") or {}).get("box_score", {})
        nested_home_totals = _aggregate_from_box(nested_home_box)
        if nested_home_totals.get("FGA"):
            home_totals = nested_home_totals
            home_totals_source = "home_team.box_score"
    if not away_totals.get("FGA"):
        nested_away_box = ((game_doc or {}).get("away_team") or {}).get("box_score", {})
        nested_away_totals = _aggregate_from_box(nested_away_box)
        if nested_away_totals.get("FGA"):
            away_totals = nested_away_totals
            away_totals_source = "away_team.box_score"

    home_scouting = _calculate_special_situations_from_team_scouting(home_team_obj)
    away_scouting = _calculate_special_situations_from_team_scouting(away_team_obj)
    home_scouting_source = "teams.scouting"
    away_scouting_source = "teams.scouting"

    # If canonical teams.scouting is empty, fallback to team_stats keyed by team_id/name.
    if not home_scouting.get("fb_entries") and not home_scouting.get("pt_total_attempts"):
        home_fallback = calculate_special_situations_from_sources(
            home_team_name, home_team_obj, team_stats_obj, team_id_label=home_team_id
        )
        if home_fallback.get("fb_entries") or home_fallback.get("pt_total_attempts"):
            home_scouting = home_fallback
            home_scouting_source = "team_stats_fallback"
    if not away_scouting.get("fb_entries") and not away_scouting.get("pt_total_attempts"):
        away_fallback = calculate_special_situations_from_sources(
            away_team_name, away_team_obj, team_stats_obj, team_id_label=away_team_id
        )
        if away_fallback.get("fb_entries") or away_fallback.get("pt_total_attempts"):
            away_scouting = away_fallback
            away_scouting_source = "team_stats_fallback"

    return {
        "home": {
            "team_id": home_team_id,
            "team_name": home_team_name,
            "totals": home_totals,
            "scouting": home_scouting,
            "totals_source": home_totals_source,
            "scouting_source": home_scouting_source,
        },
        "away": {
            "team_id": away_team_id,
            "team_name": away_team_name,
            "totals": away_totals,
            "scouting": away_scouting,
            "totals_source": away_totals_source,
            "scouting_source": away_scouting_source,
        },
        "source": "multi_source_snapshot",
    }


# ═════════════════════════════════════════════════════════════════════════════
# EOG band logic — the SINGLE implementation production runs (Task 7).
#
# Each function selects a band from its measured input(s) and returns
# (label: str, delta: int | float). Thresholds and band ranges are named
# constants in BackEnd/constants/eog_attr_bands.py (Task 8) — never inline here.
# Measures (max_share, volumes) are computed by the caller and passed in so this
# module stays free of game-doc/scouting structure. `rng` is injectable for tests.
#
# A delta of None means "apply no change" (data-integrity: zero usage where usage
# is mandatory, e.g. offense/defense) — the caller logs it and skips the attribute.
# ═════════════════════════════════════════════════════════════════════════════

from BackEnd.constants import eog_attr_bands as _B


def _roll(rng, band_range):
    lo, hi = band_range
    return rng.randint(lo, hi)


def shot_threshold_change(fg_pct, is_winner, rng=random):
    if fg_pct > _B.FG_PCT_HIGH:
        return "fg_gt_50", _roll(rng, _B.ST_FG_GT_50)
    if fg_pct > _B.FG_PCT_MID:
        band = _B.ST_FG_45_TO_50_WIN if is_winner else _B.ST_FG_45_TO_50_LOSS
        return "fg_45_to_50", _roll(rng, band)
    return "fg_le_45", _roll(rng, _B.ST_FG_LE_45)


def discipline_change(team_f_plus_to, opp_f_plus_to, rng=random):
    buffered = opp_f_plus_to + _B.DISCIPLINE_OPP_BUFFER
    if team_f_plus_to < buffered:
        return "below_opp_plus_8", _roll(rng, _B.DISC_BELOW)
    if team_f_plus_to > buffered:
        return "above_opp_plus_8", _roll(rng, _B.DISC_ABOVE)
    return "equal_buffered", _roll(rng, _B.DISC_EQUAL)


def fight_change(is_winner, rng=random):
    label, band = _B.FIGHT_BANDS[bool(is_winner)]
    return label, _roll(rng, band)


def rebound_modifier_change(treb, opp_treb, rng=random):
    """5-band ladder (Task 2). Asymmetric on purpose: rebound differential is
    zero-sum between the two teams, so symmetric bands would net exactly zero
    drift. Returns a 2-decimal delta (cents /100)."""
    diff = treb - opp_treb
    # Labels carry no numbers on purpose — the margins below are tuned and the old
    # names (outrebound_gt_8 etc) had drifted to describe thresholds that no longer
    # existed. Comments state the LIVE values; the constants remain the source.
    if diff >= _B.REBOUND_BIG_MARGIN:              # >= +14
        label, band = "reb_dominant", _B.REB_DOMINANT
    elif diff >= _B.REBOUND_MID_MARGIN:            # +7 .. +13
        label, band = "reb_strong", _B.REB_STRONG
    elif diff >= -_B.REBOUND_EVEN_MARGIN:          # -3 .. +6
        label, band = "reb_even", _B.REB_EVEN
    elif diff > -_B.REBOUND_BIG_MARGIN:            # -13 .. -4
        label, band = "reb_weak", _B.REB_WEAK
    else:                                          # <= -14
        label, band = "reb_dominated", _B.REB_DOMINATED
    return label, round(_roll(rng, band) / 100.0, 2)


def _concentration_change(max_share, reward_thr, middle_thr, labels, rng):
    reward_lbl, middle_lbl, penalty_lbl = labels
    if max_share <= reward_thr:
        return reward_lbl, _roll(rng, _B.CONC_REWARD_DELTA)
    if max_share <= middle_thr:
        return middle_lbl, _roll(rng, _B.CONC_MIDDLE_DELTA)
    return penalty_lbl, _roll(rng, _B.CONC_PENALTY_DELTA)


def offensive_efficiency_change(total_usage, max_share, rng=random):
    """Concentration of offensive possessions (Task 3). Zero possessions never
    legitimately happens (every game has offense) → data-integrity, no change."""
    if total_usage <= 0:
        return "data_integrity_no_usage", None
    return _concentration_change(
        max_share, _B.OFF_CONC_REWARD, _B.OFF_CONC_MIDDLE,
        ("conc_le_30", "conc_le_45", "conc_gt_45"), rng)


def defensive_efficiency_change(total_usage, max_share, rng=random):
    """Max HCO-defense-row share (unchanged bands, Task 5). Zero defensive
    possessions is broken data → data-integrity, no change."""
    if total_usage <= 0:
        return "data_integrity_no_usage", None
    if max_share <= _B.DEF_MAX_SHARE_REWARD:
        return "def_max_le_39", _roll(rng, _B.DEF_REWARD_DELTA)
    if max_share <= _B.DEF_MAX_SHARE_MIDDLE:
        return "def_max_le_49", _roll(rng, _B.DEF_MIDDLE_DELTA)
    return "def_max_gt_49", _roll(rng, _B.DEF_PENALTY_DELTA)


def fb_efficiency_change(volume, max_share, rng=random):
    """Concentration over CR/RR/Triangle (after_steal excluded). Zero fast-break
    volume is a coaching choice → mild atrophy (Task 4/5)."""
    if volume <= 0:
        return "fb_atrophy", _roll(rng, _B.CONC_ATROPHY_DELTA)
    return _concentration_change(
        max_share, _B.FB_CONC_REWARD, _B.FB_CONC_MIDDLE,
        ("fb_conc_le_45", "fb_conc_le_60", "fb_conc_gt_60"), rng)


def pt_efficiency_change(volume, max_share, rng=random):
    """Concentration over the 4 press/trap plays (3 HCT variant A's + fcp_used;
    fcp_press_plays.A is a dead counter, see caller). Zero P/T volume → atrophy."""
    if volume <= 0:
        return "pt_atrophy", _roll(rng, _B.CONC_ATROPHY_DELTA)
    return _concentration_change(
        max_share, _B.PT_CONC_REWARD, _B.PT_CONC_MIDDLE,
        ("pt_conc_le_50", "pt_conc_le_75", "pt_conc_gt_75"), rng)


def _volume_ladder(volume, healthy_band, labels, rng):
    atrophy_lbl, under_lbl, healthy_lbl, over_lbl = labels
    lo, hi = healthy_band
    if volume <= 0:
        return atrophy_lbl, _roll(rng, _B.VOL_ATROPHY_DELTA)
    if volume < lo:
        return under_lbl, _roll(rng, _B.VOL_UNDER_DELTA)
    if volume <= hi:
        return healthy_lbl, _roll(rng, _B.VOL_HEALTHY_DELTA)
    return over_lbl, _roll(rng, _B.VOL_OVER_DELTA)


def fb_opp_modifier_change(opponent_fb_volume, rng=random):
    """Opponent fast-break VOLUME (after_steal excluded) on the under/healthy/over
    ladder (Task 5). Measures how much transition you were forced to defend."""
    return _volume_ladder(
        opponent_fb_volume, _B.FB_OPP_HEALTHY_BAND,
        ("fb_opp_atrophy", "fb_opp_under", "fb_opp_healthy", "fb_opp_over"), rng)


def pt_opp_modifier_change(opponent_pt_volume, rng=random):
    """Opponent press/trap VOLUME (hct_used + fcp_used) on the ladder (Task 5)."""
    return _volume_ladder(
        opponent_pt_volume, _B.PT_HEALTHY_BAND,
        ("pt_opp_atrophy", "pt_opp_under", "pt_opp_healthy", "pt_opp_over"), rng)


def team_chemistry_change(is_winner, team_rank, opponent_rank, rng=random):
    """Rank-relative result (lower rank int = better). winner_score/loser_score
    are NOT used — margin was the old design; this is rank-driven."""
    if is_winner:
        if opponent_rank > team_rank:
            return "beat_lower_ranked", _roll(rng, _B.CHEM_BEAT_LOWER)
        if opponent_rank <= _B.CHEM_TOP_RANK:
            return "beat_top10", _roll(rng, _B.CHEM_BEAT_TOP10)
        return "beat_higher_non_top10", _roll(rng, _B.CHEM_BEAT_HIGHER_NON_TOP10)
    if opponent_rank < team_rank and opponent_rank <= _B.CHEM_TOP_RANK:
        return "lose_to_top10", _roll(rng, _B.CHEM_LOSE_TO_TOP10)
    if opponent_rank < team_rank:
        return "lose_to_higher_non_top10", _roll(rng, _B.CHEM_LOSE_TO_HIGHER_NON_TOP10)
    if _B.CHEM_LOW_RANK_MIN <= opponent_rank <= _B.CHEM_LOW_RANK_MAX:
        return "lose_to_100_128", _roll(rng, _B.CHEM_LOSE_TO_100_128)
    return "lose_to_other_lower", _roll(rng, _B.CHEM_LOSE_TO_OTHER_LOWER)
