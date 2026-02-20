"""
Situational Logic (Q4/OT): Quick Shot / Slow It Down and Force Foul.
See docs/docs_1_systems/05_GP_Supporting_Systems/Situational_Logic_System.md.

All logic applies only when quarter >= 4 (Q4 and OT). Time remaining is in the quarter (seconds).
Temp overrides (Fast Break, FCP, HCT) revert when the situation ends (re-evaluated each turn).
"""

import random
import logging
from BackEnd.constants import (
    SITUATIONAL_TIME_TIERS,
    SITUATIONAL_QUICK_SHOT_ATTACK_RATIO,
    SITUATIONAL_FORCE_FOUL_TIME_ELAPSED_MIN,
    SITUATIONAL_FORCE_FOUL_TIME_ELAPSED_MAX,
    SITUATIONAL_BIP_RECEIVER_POS,
    SITUATIONAL_SIP_RECEIVER_POS,
)


def get_situational_tier(time_remaining_seconds):
    """
    Return the tier dict for the given time remaining in the quarter (seconds).
    Tiers: < 180, < 120, < 60, < 20. Returns the first matching tier (most restrictive first).
    """
    if time_remaining_seconds is None:
        return None
    for threshold_seconds, tier in SITUATIONAL_TIME_TIERS:
        if time_remaining_seconds < threshold_seconds:
            return tier.copy()
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
    True when offense is ahead by at least Slow It Down threshold (Q4/OT).
    Revert when situation ends (no persistent override).
    """
    if not is_situational_active(game.quarter):
        return False
    tier = get_situational_tier(time_remaining_seconds)
    if not tier:
        return False
    threshold = tier.get("slow_threshold")
    if threshold is None:
        return False
    delta = get_score_delta(game)
    return delta >= threshold


def is_quick_shot(game, time_remaining_seconds):
    """
    True when offense is behind by at least Quick Shot threshold (Q4/OT).
    """
    if not is_situational_active(game.quarter):
        return False
    tier = get_situational_tier(time_remaining_seconds)
    if not tier:
        return False
    threshold = tier.get("quick_threshold")
    if threshold is None:
        return False
    delta = get_score_delta(game)
    return delta <= threshold


def should_force_foul(game, time_remaining_seconds):
    """
    True when defense is trailing by <= Slow It Down threshold (0 <= Score Delta <= threshold)
    in the < 1 min or < 20 sec tiers. Never true when defense is leading.
    """
    if not is_situational_active(game.quarter):
        return False
    tier = get_situational_tier(time_remaining_seconds)
    if not tier or not tier.get("force_foul_range"):
        return tier and tier.get("force_foul") is True
    threshold = tier.get("slow_threshold")
    if threshold is None:
        return False
    delta = get_score_delta(game)
    return 0 <= delta <= threshold


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
    When Quick Shot is active, returns weighted focus: (outside_ratio, attack_ratio, inside_ratio)
    for (outside, attack, inside). If not Quick Shot, returns None.
    """
    if not is_quick_shot(game, time_remaining_seconds):
        return None
    tier = get_situational_tier(time_remaining_seconds)
    if not tier:
        return None
    outside_ratio = tier.get("outside_ratio", 0.7)
    # If not outside: 75% attack / 25% inside
    remainder = 1.0 - outside_ratio
    attack_ratio = remainder * SITUATIONAL_QUICK_SHOT_ATTACK_RATIO
    inside_ratio = remainder * (1.0 - SITUATIONAL_QUICK_SHOT_ATTACK_RATIO)
    return (outside_ratio, attack_ratio, inside_ratio)


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
