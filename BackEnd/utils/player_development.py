"""Player growth model — the offseason development event and the growth profile.

Design §4-§8. This is the REAL, importable, pure, RNG-injectable implementation;
the Monte Carlo harness (scripts/mc_growth_fit.py) is a thin driver over it, and
production season-rollover will call the same `develop_one_offseason`. There is
no separate harness model of the growth math — a throwaway would diverge from
production and void the fitted constants.

NOT wired into any live path in this pass (do not call from
complete_season_transition). Fit first, wire later. No DB, no possessions.

Two independent systems rolled once at generation and frozen (§5):
  - peak_count (0-3), CH-driven → HOW MUCH total career growth (§5.1)
  - family_timing (physical/skill/mental ∈ early/standard/late) → WHEN each
    family arrives (§5.2)
They must stay orthogonal: peaks scale magnitude, timing shifts schedule.

Growth is measured against the training position (§9.1); here that is the
generated position intent.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional

from BackEnd.utils.position_ratings import POSITION_WEIGHTS, compute_position_ratings, height_fitness
from BackEnd.utils.player_generation import (
    JH_ANCHOR_BY_TIER,
    RT_ATTRS,
    generate_player,
)

# ── Families (§6) — an axis independent of the malleable/static fatigue split ──
PHYSICAL_ATTRS = ("ST", "AG")            # + HT/WT, rolled separately
SKILL_ATTRS = ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "FT")
MENTAL_ATTRS = ("IQ", "ND")
GROWTH_ATTRS = PHYSICAL_ATTRS + SKILL_ATTRS + MENTAL_ATTRS  # 12 core (RT_ATTRS + ND)
FAMILY_OF = ({a: "physical" for a in PHYSICAL_ATTRS}
             | {a: "skill" for a in SKILL_ATTRS}
             | {a: "mental" for a in MENTAL_ATTRS})

RUNG_TRANSITIONS = ("FR", "SO", "JR", "SR")  # four offseason events from JH

# ── Rung increments (§4.2) — fractions of the JH anchor, as RT ────────────────
# 0-peak path sums to 0.70 (→ 1.7x career). A peak adds a FIXED bonus at whichever
# rung it lands on (see PEAK_BONUS). The canonical 1-peak-at-SO_JR path then
# reproduces §4.2 exactly: FR 1.17 / SO 1.43 / JR 1.80 / SR 2.00.
STD_RUNG_INCREMENT = {"FR": 0.17, "SO": 0.26, "JR": 0.07, "SR": 0.20}
# A peak adds +0.30x the JH anchor. This makes the career multiple 1.7 + 0.30·k
# (→ 1.7/2.0/2.3/2.6 for k=0..3), independent of WHICH rung peaks — placement is
# timing, not magnitude. (See FIT NOTES: §12's "PEAK_MULTIPLIER ~1.9x a standard
# rung" cannot hit both the career multiples and §4.2; a fixed bonus does.)
PEAK_BONUS = 0.30

# ── Ceiling (§4.3) ────────────────────────────────────────────────────────────
RT_COMPRESSION_THRESHOLD = 95
RT_SOFT_CAP = 130

# ── Peak-count distribution vs CH (§5.1 / §8) ─────────────────────────────────
# CH is FLAT 1-100 (§8). The per-player peak-count distribution is a linear
# interpolation between a low-CH and a high-CH endpoint by CH; the endpoints are
# chosen so the CH-uniform AVERAGE equals PEAK_COUNT_DISTRIBUTION (§12) exactly
# (midpoint of a linear interp = mean over uniform CH). High CH still permits 0
# peaks (the bust, §5.1); low CH still permits a peak.
PEAK_COUNT_DISTRIBUTION = (0.20, 0.55, 0.22, 0.03)   # aggregate target
CH_PEAK_LOW = (0.38, 0.52, 0.10, 0.00)               # CH → 1
CH_PEAK_HIGH = (0.02, 0.58, 0.34, 0.06)              # CH → 100
# (CH_PEAK_LOW + CH_PEAK_HIGH)/2 == PEAK_COUNT_DISTRIBUTION.

# Where a single peak lands (§5.1 / §12): SO_JR > FR_SO > JR_SR > JH_FR. Keyed by
# destination rung: JR=SO→JR, SO=FR→SO, SR=JR→SR, FR=JH→FR.
PEAK_RUNG_WEIGHTS = {"JR": 0.42, "SO": 0.28, "SR": 0.20, "FR": 0.10}

# ── Family timing (§5.2) ──────────────────────────────────────────────────────
FAMILY_TIMING_WEIGHTS = {
    "physical": {"early": 0.30, "standard": 0.55, "late": 0.15},
    "skill":    {"early": 0.25, "standard": 0.50, "late": 0.25},
    "mental":   {"early": 0.20, "standard": 0.50, "late": 0.30},
}
# How strongly 'early'/'late' shift a family's share between rungs.
FAMILY_TIMING_SHIFT = 0.40

# ── Family curves (§6) — per-rung MULTIPLIER on each family's attribute weights ─
# NOT absolute budget shares. A share formulation dumps a big fraction of the
# budget into the mental family, but ND has zero RT weight everywhere and IQ is
# near-zero off PG, so hitting the RT ladder then needs a runaway budget that
# balloons ND. As weight multipliers they shift WHICH RT-relevant attributes
# grow by age — physical early, mental late — while the budget stays sized to the
# RT the growth actually carries. Physical is driven to ~0 at JR/SR (§6: physical
# locked to early rungs; a late peak expresses in skill/mental, not HT).
FAMILY_CURVES = {
    "FR": {"physical": 3.0, "skill": 1.0, "mental": 0.30},
    "SO": {"physical": 2.0, "skill": 1.2, "mental": 0.60},
    "JR": {"physical": 0.25, "skill": 1.3, "mental": 2.2},
    "SR": {"physical": 0.12, "skill": 1.2, "mental": 3.2},
}
PHYSICAL_LOCKED_RUNGS = ("JR", "SR")  # physical multiplier held at its floor here

# ── In-season / accumulator (§7.2-7.3) ────────────────────────────────────────
# The offseason delivers OFFSEASON_SPLIT of each rung's growth via the family
# curve (age-shaped); in-season delivers the rest via the accumulator, which in
# the default policy aims at the training-position weights (position-shaped).
OFFSEASON_SPLIT = 0.70
# Non-core attributes grow at a low but never-zero rate (§7.1) — a floor on the
# per-attribute weight used for within-family distribution.
NON_CORE_GROWTH_MULTIPLIER = 0.06
# Intra-family concentration exponent on the position weights. 1.0 puts almost
# all of a family's growth on its highest-weight attribute (which then must
# exceed 100 to carry a high RT — an above-100 rate of ~30%). The DEFAULT policy
# should grow broadly; concentrated spikes (§4.3's 140-150) are meant to come
# from focused in-season play, not the default distribution. Fitted to the ~5.5%
# above-100 target (§3.6.4).
INTRA_FAMILY_GAMMA = 0.20

# ── HT/WT (§6, physical) ──────────────────────────────────────────────────────
HT_GROWTH_BY_RUNG = {"FR": (0, 2), "SO": (0, 1), "JR": (0, 0), "SR": (0, 0)}


def _cat(rng: random.Random, dist) -> int:
    r = rng.random()
    acc = 0.0
    for i, p in enumerate(dist):
        acc += p
        if r < acc:
            return i
    return len(dist) - 1


def roll_growth_profile(ch_seed: int, rng: random.Random) -> dict:
    """Roll the frozen growth profile from a flat CH seed (§5, §8)."""
    t = (ch_seed - 1) / 99.0
    peak_dist = [CH_PEAK_LOW[i] + (CH_PEAK_HIGH[i] - CH_PEAK_LOW[i]) * t for i in range(4)]
    peak_count = _cat(rng, peak_dist)

    rungs = list(PEAK_RUNG_WEIGHTS)
    weights = [PEAK_RUNG_WEIGHTS[r] for r in rungs]
    peak_rungs: List[str] = []
    for _ in range(peak_count):
        pick = rng.choices(rungs, weights=weights, k=1)[0]
        peak_rungs.append(pick)
        idx = rungs.index(pick)
        rungs.pop(idx); weights.pop(idx)  # no rung peaks twice

    family_timing = {
        fam: ["early", "standard", "late"][_cat(rng, tuple(FAMILY_TIMING_WEIGHTS[fam][k]
                                                            for k in ("early", "standard", "late")))]
        for fam in ("physical", "skill", "mental")
    }
    return {"ch_seed": ch_seed, "peak_count": peak_count,
            "peak_rungs": peak_rungs, "family_timing": family_timing}


def _compress_rt(raw: float) -> float:
    """Soft ceiling near RT_SOFT_CAP (§4.3). Near-identity below the cap — the
    fitted increments already bound elite+3-peak at 50·2.6 = 130, so this is a
    guard against focused-play overshoot rather than a load-bearing curve; it
    only bends above the cap. (§4.3's "reduced efficiency above 95" is expressed
    as attribute inflation — RT still reaches its tier target, but it costs more
    attribute points as RT climbs, which is what INTRA_FAMILY_GAMMA governs.)"""
    if raw <= RT_SOFT_CAP:
        return raw
    over = raw - RT_SOFT_CAP
    return RT_SOFT_CAP + 8.0 * (1.0 - pow(2.71828, -over / 8.0))


def _family_multipliers_for_player(rung: str, timing: dict) -> Dict[str, float]:
    """Per-family weight multipliers at ``rung`` after the player's timing."""
    base = dict(FAMILY_CURVES[rung])
    early_half = RUNG_TRANSITIONS.index(rung) <= 1  # FR/SO are the "early" rungs
    out = {}
    for fam, mult in base.items():
        tm = timing.get(fam, "standard")
        factor = 1.0
        if tm == "early":
            factor = 1.0 + FAMILY_TIMING_SHIFT if early_half else 1.0 - FAMILY_TIMING_SHIFT
        elif tm == "late":
            factor = 1.0 - FAMILY_TIMING_SHIFT if early_half else 1.0 + FAMILY_TIMING_SHIFT
        out[fam] = max(0.0, mult * factor)
    if rung in PHYSICAL_LOCKED_RUNGS:  # physical stays locked out of late rungs (§6)
        out["physical"] = min(out["physical"], FAMILY_CURVES[rung]["physical"])
    return out


def _distribution_fractions(position: str, rung: str, timing: dict,
                            accumulator: Optional[Dict[str, float]]) -> Dict[str, float]:
    """Per-attribute growth fractions (sum 1): a 70/30 blend of the age-shaped
    offseason distribution and the position-shaped in-season accumulator
    (§7.2-7.3). Offseason weight for attribute a = floored_position_weight^GAMMA ×
    family_multiplier(family, rung). Weight-dominated, so the budget stays sized
    to the RT the growth carries and no zero-weight attribute balloons."""
    weights = POSITION_WEIGHTS[position]

    def floored(a):
        return max(weights.get(a, 0.0), NON_CORE_GROWTH_MULTIPLIER)

    fam_mult = _family_multipliers_for_player(rung, timing)
    offseason = {a: (floored(a) ** INTRA_FAMILY_GAMMA) * fam_mult[FAMILY_OF[a]] for a in GROWTH_ATTRS}
    off_tot = sum(offseason.values()) or 1.0
    offseason = {a: v / off_tot for a, v in offseason.items()}

    # In-season accumulator: default policy aims at the position weights.
    acc = accumulator or {a: floored(a) for a in GROWTH_ATTRS}
    acc_denom = sum(acc.get(a, 0.0) for a in GROWTH_ATTRS) or 1.0
    inseason = {a: acc.get(a, 0.0) / acc_denom for a in GROWTH_ATTRS}

    blend = {a: OFFSEASON_SPLIT * offseason.get(a, 0.0)
                + (1 - OFFSEASON_SPLIT) * inseason.get(a, 0.0) for a in GROWTH_ATTRS}
    tot = sum(blend.values()) or 1.0
    return {a: v / tot for a, v in blend.items()}


# Efficiency floor: keeps the analytic budget bounded when a rung's distribution
# leans on low-RT-weight attributes (e.g. mental IQ/ND late), so those cosmetic
# attributes cannot balloon while chasing the RT target.
_EFFICIENCY_FLOOR = 0.05


def _analytic_budget(attrs: dict, height: float, position: str,
                     fractions: Dict[str, float], target_rt: float) -> float:
    """First-order attribute-point pool B to raise RT to ``target_rt``.

    RT = weighted_mean × height_fitness, so ΔRT ≈ B · (Σ wᵢ·fracᵢ) · fitness.
    Sizing B this way keeps growth proportional to the RT the distribution can
    actually carry — a distribution that leans on zero-weight attributes (ND) is
    inefficient, but B is bounded by the efficiency floor rather than exploding
    to force the target. RT then tracks the ladder to first order (verified in
    the MC) rather than by construction."""
    current = compute_position_ratings({"attributes": attrs, "height": height})[position]
    d_rt = target_rt - current
    if d_rt <= 0:
        return 0.0
    weights = POSITION_WEIGHTS[position]
    efficiency = max(_EFFICIENCY_FLOOR, sum(weights.get(a, 0.0) * fractions[a] for a in GROWTH_ATTRS))
    fitness = height_fitness(position, height) or 1.0
    return d_rt / (efficiency * fitness)


def develop_one_offseason(player: dict, rung: str, profile: dict,
                          rng: random.Random,
                          accumulator: Optional[Dict[str, float]] = None) -> dict:
    """Apply one offseason development event, moving the player onto ``rung`` (§7.1).

    Mutates and returns ``player`` (dict with 'attributes', 'height', 'weight',
    'position'/'training_position', 'jh_anchor'). Pure given ``rng``.
    """
    attrs = player["attributes"]
    position = player.get("training_position") or player["position"]
    anchor = player["jh_anchor"]

    # 1-2. budget from the rung + CH-seeded peak check → target RT for this rung.
    cum = 0.0
    for r in RUNG_TRANSITIONS:
        cum += STD_RUNG_INCREMENT[r] + (PEAK_BONUS if r in profile["peak_rungs"] else 0.0)
        if r == rung:
            break
    target_rt = _compress_rt(anchor * (1.0 + cum))

    # 3-4. distribute across attributes by family curve × timing × weights.
    fractions = _distribution_fractions(position, rung, profile["family_timing"], accumulator)
    B = _analytic_budget(attrs, player["height"], position, fractions, target_rt)
    for a in GROWTH_ATTRS:
        attrs[a] = int(round(attrs.get(a, 0) + B * fractions[a]))

    # 5. HT/WT roll (physical family, early rungs only; never for a late peak).
    lo, hi = HT_GROWTH_BY_RUNG[rung]
    if hi > 0 and profile["family_timing"]["physical"] != "late":
        dh = rng.randint(lo, hi)
        if dh:
            player["height"] = player["height"] + dh
            player["weight"] = player.get("weight", 0) + dh * rng.randint(4, 8)

    # 6. recompute all five RTs.
    player["position_ratings"] = compute_position_ratings(
        {"attributes": attrs, "height": player["height"]})
    player["class_year"] = rung
    return player


def simulate_career(position: str, tier: str, ch_seed: int, rng: random.Random,
                    accumulator: Optional[Dict[str, float]] = None) -> dict:
    """Generate a JH player and walk all four offseason rungs to SR (§11.1)."""
    jh = generate_player(position, "JH", tier, rng, preserve_ch=ch_seed)
    player = {
        "attributes": jh["attributes"],
        "height": jh["height"],
        "weight": jh["weight"],
        "position": position,
        "training_position": position,
        "tier": tier,
        "jh_anchor": JH_ANCHOR_BY_TIER[tier],
        "position_ratings": jh["position_ratings"],
        "class_year": "JH",
    }
    profile = roll_growth_profile(ch_seed, rng)
    player["development"] = profile
    snapshots = {"JH": dict(player["position_ratings"])}
    for rung in RUNG_TRANSITIONS:
        develop_one_offseason(player, rung, profile, rng, accumulator=accumulator)
        snapshots[rung] = dict(player["position_ratings"])
    player["snapshots"] = snapshots
    return player


__all__ = [
    "PHYSICAL_ATTRS", "SKILL_ATTRS", "MENTAL_ATTRS", "GROWTH_ATTRS", "FAMILY_OF",
    "RUNG_TRANSITIONS", "STD_RUNG_INCREMENT", "PEAK_BONUS",
    "RT_COMPRESSION_THRESHOLD", "RT_SOFT_CAP", "PEAK_COUNT_DISTRIBUTION",
    "CH_PEAK_LOW", "CH_PEAK_HIGH", "PEAK_RUNG_WEIGHTS", "FAMILY_TIMING_WEIGHTS",
    "FAMILY_CURVES", "OFFSEASON_SPLIT", "NON_CORE_GROWTH_MULTIPLIER",
    "roll_growth_profile", "develop_one_offseason", "simulate_career",
]
