"""
Situational Logic (Q4/OT): Quick Shot / Slow It Down and Force Foul.
See docs/docs_1_systems/05_GP_Supporting_Systems/Situational_Logic_System.md.

All logic applies only when quarter >= 4 (Q4 and OT). Time remaining is in the quarter (seconds).
Temp overrides (Fast Break, FCP, HCT) revert when the situation ends (re-evaluated each turn).
"""

import random
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


def is_quick_shot(game, time_remaining_seconds):
    """
    True when Score Delta is in this band's Quick Shot range (Q4/OT).
    Per time-band table: quick_lo < delta < quick_hi.
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
    When Quick Shot is active, returns (outside_ratio, attack_ratio, inside_ratio) per time-band table.
    Band 0:01-0:30: if Score Delta < -2 → 100% outside; else None (normal playcall). Other bands: fixed ratios.
    """
    if not is_quick_shot(game, time_remaining_seconds):
        return None
    tier = get_situational_tier(time_remaining_seconds)
    if not tier:
        return None
    delta = get_score_delta(game)
    # 0:01-0:30 band: only override when delta < -2 (100% outside); else normal logic
    if tier.get("last_30_quick"):
        below = tier.get("outside_if_delta_below", -2)
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
