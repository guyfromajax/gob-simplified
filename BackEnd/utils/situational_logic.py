"""
Situational Logic (Q4/OT): Quick Shot / Slow It Down and Force Foul.
See _documentation_master/05_GP_Supporting_Systems/Situational_Logic_System.md.

All logic applies only when quarter >= 4 (Q4 and OT). Time remaining is in the quarter (seconds).
Temp overrides (Fast Break, FCP, HCT) revert when the situation ends (re-evaluated each turn).
"""

from BackEnd.utils.sim_random import sim_rng as random
import logging
from BackEnd.constants import (
    SITUATIONAL_TIME_BANDS,
    SITUATIONAL_FORCE_FOUL_TIME_ELAPSED_MIN,
    SITUATIONAL_FORCE_FOUL_TIME_ELAPSED_MAX,
    SITUATIONAL_BIP_RECEIVER_POS,
    SITUATIONAL_SIP_RECEIVER_POS,
)


def get_situational_tier(time_remaining_seconds):
    """
    Return the band config for the given time remaining in the quarter (seconds).
    Bands: 2:01-3:00 (121-180), 1:01-2:00 (61-120), 0:31-1:00 (31-60), 0:01-0:30 (0-30).
    Returns the first band where min_sec <= time <= max_sec, or None if time > 180 or None.
    """
    if time_remaining_seconds is None:
        return None
    t = int(time_remaining_seconds)
    if t > 180:
        return None
    for min_sec, max_sec, config in SITUATIONAL_TIME_BANDS:
        if min_sec <= t <= max_sec:
            return config.copy()
    return None


def is_situational_active(quarter):
    """True if situational logic applies (Q4 or OT)."""
    return quarter is not None and quarter >= 4


def get_score_delta(game):
    """Score Delta = Offense Score - Defense Score. Zero on tie."""
    off_name = game.offense_team.name
    def_name = game.defense_team.name
    score = game.score or {}
    off_score = score.get(off_name, 0)
    def_score = score.get(def_name, 0)
    return off_score - def_score


def _player_team_name(game, player):
    if player is None:
        return None
    pid = getattr(player, "player_id", None)
    if pid is None:
        return None
    for team in (getattr(game, "home_team", None), getattr(game, "away_team", None)):
        if team is None:
            continue
        for p in (getattr(team, "lineup", {}) or {}).values():
            if p and getattr(p, "player_id", None) == pid:
                return team.name
    return None


def log_force_foul_debug(game, path, *, time_remaining=None, fouler=None, victim=None, note=None):
    """
    Backend diagnostic for situational force-foul leading/trailing investigations.
    Emits to the Python server log (terminal), not the browser console.
    """
    score = game.score or {}
    off = game.offense_team
    def_ = game.defense_team
    off_score = int(score.get(off.name, 0))
    def_score = int(score.get(def_.name, 0))
    gs = getattr(game, "game_state", None) or {}
    tr = time_remaining if time_remaining is not None else gs.get("time_remaining")
    payload = {
        "path": path,
        "quarter": getattr(game, "quarter", None),
        "time_remaining": tr,
        "offense_team": off.name,
        "defense_team": def_.name,
        "offense_score": off_score,
        "defense_score": def_score,
        "score_delta": off_score - def_score,
        "slow_it_down": is_slow_it_down(game, tr) if tr is not None else None,
        "should_force_foul": should_force_foul(game, tr) if tr is not None else None,
        "fouler_id": getattr(fouler, "player_id", None) if fouler else None,
        "fouler_team": _player_team_name(game, fouler),
        "victim_id": getattr(victim, "player_id", None) if victim else None,
        "victim_team": _player_team_name(game, victim),
    }
    if note:
        payload["note"] = note
    logging.info("[FORCE_FOUL_DEBUG] %s", payload)


def is_slow_it_down(game, time_remaining_seconds):
    """
    True when offense is ahead by at least this band's Slow It Down minimum (Q4/OT).
    Per time-band table: delta >= slow_min for the current band.
    """
    if not is_situational_active(game.quarter):
        return False
    tier = get_situational_tier(time_remaining_seconds)
    if not tier:
        return False
    slow_min = tier.get("slow_min")
    if slow_min is None:
        return False
    delta = get_score_delta(game)
    return delta >= slow_min


# Settings a Slow It Down (leading) team zeroes out for conservative DEFENSE.
# fast_breaks: don't release for a fast break off a rebound/steal.
# hc_trap / fc_press: no half-court trap / full-court press (play straight HCO defense).
# aggression: passive — fewer fouls, less gambling for steals/blocks, no transition push.
SLOW_IT_DOWN_CONSERVATIVE_SETTINGS = ("fast_breaks", "hc_trap", "fc_press", "aggression")


def get_slow_it_down_team_id(game, time_remaining_seconds):
    """
    Return the team_id of the team currently in the macro Slow It Down state, or None.

    Unlike ``is_slow_it_down()`` (evaluated from the current offense's perspective, used
    for offense tempo/playcall), this identifies the LEADING team and checks their margin
    against the time-band Slow It Down threshold **independent of who is on offense**.

    This drives conservative DEFENSE for the leading team (fast_breaks / hc_trap /
    fc_press / aggression → 0) even while that team is on defense. Q4/OT only; reverts
    as soon as the lead no longer meets the current band's threshold.
    """
    if not is_situational_active(game.quarter):
        return None
    tier = get_situational_tier(time_remaining_seconds)
    if not tier:
        return None
    slow_min = tier.get("slow_min")
    if slow_min is None:
        return None
    home = getattr(game, "home_team", None)
    away = getattr(game, "away_team", None)
    if home is None or away is None:
        return None
    score = game.score or {}
    home_score = int(score.get(home.name, 0))
    away_score = int(score.get(away.name, 0))
    if home_score == away_score:
        return None
    if home_score > away_score:
        leader, margin = home, home_score - away_score
    else:
        leader, margin = away, away_score - home_score
    if margin >= slow_min:
        return getattr(leader, "team_id", None)
    return None


def is_team_slow_it_down(game_state, team_id):
    """True if ``team_id`` is currently flagged in the macro Slow It Down state.

    Reads the ``slow_it_down_team_ids`` field maintained on ``game_state`` (refreshed each
    turn); comparison is string-normalized to be robust to int/str team_id representations.
    """
    if team_id is None:
        return False
    ids = (game_state or {}).get("slow_it_down_team_ids") or []
    return str(team_id) in {str(t) for t in ids}


def slow_it_down_defense_setting(game_state, team, key, raw_value):
    """Effective 0-4 strategy_setting value for ``team``, honoring the Slow It Down override.

    Returns 0 when ``team`` is in the macro Slow It Down state and ``key`` is a
    conservative-defense setting (see ``SLOW_IT_DOWN_CONSERVATIVE_SETTINGS``); otherwise
    returns ``raw_value`` unchanged. This is a read-time override only — it never mutates
    the team's stored ``strategy_settings`` (which stay tied to the team/DB doc).
    """
    if key not in SLOW_IT_DOWN_CONSERVATIVE_SETTINGS:
        return raw_value
    if is_team_slow_it_down(game_state, getattr(team, "team_id", None)):
        return 0
    return raw_value


def is_quick_shot(game, time_remaining_seconds):
    """
    True when Score Delta is in this band's Quick Shot range (Q4/OT).
    Per time-band table: quick_lo < delta < quick_hi.
    Last 30 seconds special case: Quick Shot applies whenever the offense is
    trailing by more than 3 (delta < -3), regardless of how large the deficit is.
    """
    if not is_situational_active(game.quarter):
        return False
    tier = get_situational_tier(time_remaining_seconds)
    if not tier:
        return False
    quick_lo = tier.get("quick_lo")
    quick_hi = tier.get("quick_hi")
    if quick_lo is None or quick_hi is None:
        return False
    delta = get_score_delta(game)
    if tier.get("last_30_quick"):
        return delta < quick_hi
    return quick_lo < delta < quick_hi


def should_force_foul(game, time_remaining_seconds):
    """
    True when this band has Force Foul and Score Delta is in the foul range (Q4/OT).
    Per time-band table: 0:31-1:00 → 3 < delta < 12; 0:01-0:30 → 0 < delta < 9; else False.
    """
    if not is_situational_active(game.quarter):
        return False
    tier = get_situational_tier(time_remaining_seconds)
    if not tier:
        return False
    if tier.get("force_foul") is False:
        return False
    force_lo = tier.get("force_foul_lo")
    force_hi = tier.get("force_foul_hi")
    if force_lo is None or force_hi is None:
        return False
    delta = get_score_delta(game)
    return force_lo < delta < force_hi


def get_situational_tempo_override(game, time_remaining_seconds):
    """
    Returns "slow" if Slow It Down, "fast" if Quick Shot, else None (no override).
    """
    if is_slow_it_down(game, time_remaining_seconds):
        return "slow"
    if is_quick_shot(game, time_remaining_seconds):
        return "fast"
    return None


def get_situational_play_focus_override(game, time_remaining_seconds):
    """
    Deprecated for playcall selection (superseded by set-play-outside-only Quick Shot logic in set_playcalls).
    Retained for reference; time-band outside/attack/inside ratios are no longer used to pick plays.
    """
    if not is_quick_shot(game, time_remaining_seconds):
        return None
    tier = get_situational_tier(time_remaining_seconds)
    if not tier:
        return None
    delta = get_score_delta(game)
    # 0:01-0:30 band: only override when delta < -3 (100% outside); else normal logic
    if tier.get("last_30_quick"):
        below = tier.get("outside_if_delta_below", -3)
        if delta >= below:
            return None
        return (1.0, 0.0, 0.0)
    # Other bands: use explicit outside / attack / inside from band
    o = tier.get("outside", 0.7)
    a = tier.get("attack", 0.2)
    i = tier.get("inside", 0.1)
    return (o, a, i)


def choose_focus_from_override(focus_weights):
    """Given (outside_ratio, attack_ratio, inside_ratio), return "outside" | "attack" | "inside"."""
    r = random.random()
    o, a, i = focus_weights
    if r < o:
        return "outside"
    if r < o + a:
        return "attack"
    return "inside"


def force_foul_time_elapsed():
    """Time elapsed for intentional (force) foul: random 1–3 seconds."""
    return random.randint(
        SITUATIONAL_FORCE_FOUL_TIME_ELAPSED_MIN,
        SITUATIONAL_FORCE_FOUL_TIME_ELAPSED_MAX,
    )


def get_inbound_receiver_pos(inbound_type):
    """Receiver position for BIP/SIP when Force Foul is applied."""
    if inbound_type == "BASELINE_INBOUND":
        return SITUATIONAL_BIP_RECEIVER_POS
    if inbound_type == "SIDE_INBOUND":
        return SITUATIONAL_SIP_RECEIVER_POS
    return "SG"


def should_run_out_clock(game, time_remaining_seconds):
    """
    EOQ Run Out The Clock (Q4/OT only): winning team or blowout loss (>18),
    time <= 30s, and defense is not in force-foul mode.
    """
    if not is_situational_active(game.quarter):
        return False
    if time_remaining_seconds is None or int(time_remaining_seconds) > 30:
        return False
    if should_force_foul(game, time_remaining_seconds):
        return False
    delta = get_score_delta(game)
    return delta >= 1 or delta < -18


def get_eoq_situational_action(game, time_remaining_seconds):
    """Return the authoritative Q4/OT action for a live turn at <=30 seconds.

    Priority is deliberate and shared by HCO, HCT, FCP, and FAST_BREAK:
    Force Foul -> Run Out -> Quick Shot -> Final Shot. ``None`` means the
    Q4/OT late-clock decision layer is not active.
    """
    if not is_situational_active(getattr(game, "quarter", None)):
        return None
    if time_remaining_seconds is None:
        return None
    time_remaining = int(time_remaining_seconds)
    if time_remaining <= 0 or time_remaining > 30:
        return None
    if is_slow_it_down(game, time_remaining) and should_force_foul(game, time_remaining):
        return "FORCE_FOUL"
    if should_run_out_clock(game, time_remaining):
        return "RUN_OUT_CLOCK"
    if is_quick_shot(game, time_remaining):
        return "QUICK_SHOT"
    return "FINAL_SHOT"


def would_take_final_shot(game, time_remaining_seconds):
    """
    True when this possession should attempt a Final Shot (not run-out, force foul, or quick shot).
    Clock-driven: active when Final Turn shot is flagged for this turn, or Q4+ trailing/tied
    end-game branch applies.
    """
    gs = getattr(game, "game_state", None) or {}
    if gs.get("final_shot_possession_active") or gs.get("final_turn_shot_this_turn"):
        return True
    if gs.get("flss_possession_pending"):
        return False
    quarter = getattr(game, "quarter", None)
    if quarter is None or quarter < 4:
        return False
    if should_run_out_clock(game, time_remaining_seconds):
        return False
    if is_slow_it_down(game, time_remaining_seconds) and should_force_foul(game, time_remaining_seconds):
        return False
    if is_quick_shot(game, time_remaining_seconds):
        return False
    return True
