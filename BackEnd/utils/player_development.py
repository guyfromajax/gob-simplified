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

import logging
import random
from typing import Dict, List, Optional

from BackEnd.utils.position_ratings import POSITION_WEIGHTS, compute_position_ratings, height_fitness
from BackEnd.utils.player_generation import (
    JH_ANCHOR_BY_TIER,
    RT_ATTRS,
    RUNG_MULTIPLIERS,
    generate_player,
    position_profile,
    HT_TOTAL_MEAN,
    HT_TOTAL_SD,
    HT_TOTAL_MIN,
    HT_TOTAL_MAX,
)

logger = logging.getLogger(__name__)

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
# Flattened from the original .17/.26/.07/.20 (Σ .70) so no rung is dead (JR was
# .07 → a non-peaking junior gained ~2 RT, invisible). §4.2's SO/JR shape shifts a
# couple of points, accepted. The offseason event delivers the FULL ladder
# (Σ .70 → 1.7x at 0 peaks); career growth is modulated by the bounded
# coaching-quality factor f (below), NOT split with in-season. A reference-coached
# player (f = 1.0) lands exactly on this ladder.
STD_RUNG_INCREMENT = {"FR": 0.17, "SO": 0.20, "JR": 0.15, "SR": 0.18}  # Σ .70
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
# RT the growth actually carries. The "physical" family here is ST/AG only (HT/WT
# have their own curves below). Physical is front-loaded but keeps a real JR/SR
# tail so a LATE-physical bloomer grows strength as an upperclassman (bounded by
# magnitude, not locked out by rung — the earlier rung-lock was rejected).
FAMILY_CURVES = {
    "FR": {"physical": 3.0, "skill": 1.0, "mental": 0.30},
    "SO": {"physical": 2.0, "skill": 1.2, "mental": 0.60},
    "JR": {"physical": 0.60, "skill": 1.3, "mental": 2.2},
    "SR": {"physical": 0.35, "skill": 1.2, "mental": 3.2},
}

# ── Offseason distribution blend (§7.2-7.3) ───────────────────────────────────
# NOT a magnitude split — there is no offseason/in-season magnitude split; the
# offseason delivers the whole ladder (modulated by coaching-quality f) and
# in-season nets ~zero. This is purely the DISTRIBUTION blend it was fitted as:
# the offseason budget lands 70% by the age-shaped family curve and 30% by the
# position-shaped accumulator. (Renamed from OFFSEASON_SPLIT, which misread as a
# magnitude split.)
OFFSEASON_DISTRIBUTION_BLEND = 0.70
# Non-core attributes grow at a low but never-zero rate (§7.1) — a floor on the
# per-attribute weight used for within-family distribution.
NON_CORE_GROWTH_MULTIPLIER = 0.06

# Part B (Direction 1): per-rollover strength of the offseason shape-and-level attractor.
# The offseason pulls each attribute this fraction of the way toward its tier/year/position
# PROFILE value scaled to the ladder RT. α<1 ⇒ attractor, not clamp: in-season focus
# survives as a spike (α=1 would erase all deviation). Tuned against the faithful in-season
# +offseason career: reference-developed Average C SC → ~52 (near the honest generation
# value 58.5, below it because development is partial by design), with a visible focus spike
# (+8). Raising it trades spike for shape; see the α frontier in the design notes.
OFFSEASON_ATTRACTOR_ALPHA = 0.55
# Intra-family concentration exponent on the position weights. 1.0 puts almost
# all of a family's growth on its highest-weight attribute (which then must
# exceed 100 to carry a high RT — an above-100 rate of ~30%). The DEFAULT policy
# should grow broadly; concentrated spikes (§4.3's 140-150) are meant to come
# from focused in-season play, not the default distribution. Fitted to the ~5.5%
# above-100 target (§3.6.4).
INTRA_FAMILY_GAMMA = 0.20

# ── HT (§6) — its OWN declining curve, keyed by the PHYSICAL timing group ─────
# HT is the one attribute whose growth can change a player's best position (a
# couple of inches moves height fitness enough to flip a wing to a four), so it
# gets an explicit curve rather than a family average, and it is NEVER zero at
# JR/SR for anyone — bounded by magnitude, not locked by rung. Shares of career
# HT gain per rung, per physical-timing group:
HT_CURVE_BY_TIMING = {
    "early":    {"FR": 0.55, "SO": 0.30, "JR": 0.12, "SR": 0.03},
    "standard": {"FR": 0.40, "SO": 0.30, "JR": 0.20, "SR": 0.10},
    "late":     {"FR": 0.15, "SO": 0.25, "JR": 0.35, "SR": 0.25},
}
# Career HT gain (inches) ~ Normal, clamped: median ~3, p10 ~1, p90 ~6.
# HT_TOTAL_MEAN/SD/MIN/MAX now live in player_generation (single source of truth, shared with
# grow-into-frame generation) and are imported above.
HT_PER_RUNG_CAP = 2.5  # cap the real-valued per-rung want at 2.5in, then round → dh ∈ {0,1,2,3} with 3 only on the biggest rungs (restores the p90≈6in tail without a systematic +3)
# WT tracks strength: pounds per inch of HT gain, plus muscle with ST growth.
WT_LBS_PER_INCH = (4, 7)
WT_LBS_PER_ST = (0, 1)

# ── Coaching quality → offseason modifier f (Option 3) ────────────────────────
# The offseason target is  jh_anchor × ladder_value × f(coaching_quality).  f is
# bounded; a reference-coached player (f = 1.0) lands exactly on the validated
# ladder, so the league stays where pass 1 put it and the user's edge comes from
# OUT-coaching the reference (which structurally caps user-vs-CPU divergence).
#
# SATURATING-COVERAGE metric, in POINTS (§9.1). An allocation is per-attribute
# TRAINING POINTS PER WEEK (0-5 per the drill sliders), NOT a share of the budget.
# Each attribute contributes  w_a × min(points_a / COACHING_SATURATION_CAP, 1) —
# it stops benefiting past the cap. Because the cap is high in points, saturation
# is EXPENSIVE: spreading a fixed budget thin fails to saturate anything, while
# concentrating points saturates the important attributes. So both FOCUS (spike a
# few attributes) and BROAD coverage are valid, priced against a fixed budget:
#   - fewer total points  → fewer attributes saturated → lower quality. This is why
#     a 2-point customization tax prices itself with no special-casing.
#   - all-in one attribute → covers nothing else → floor.
#   - spraying across all 12 (incl. off-position) → the on-position attributes are
#     starved → below reference.
# Coverage is normalised affinely PER POSITION (reference → 1.0, the budget optimum
# → 1.0 + COACHING_HEADROOM), so coaching matters equally at every position rather
# than 2× at SF vs SG.
#
# REFERENCE — a CALIBRATION ANCHOR, do not change casually. A deliberately MEDIOCRE
# baseline in points: the position's top-COACHING_REFERENCE_BREADTH attributes at
# COACHING_REFERENCE_PRIMARY_PTS/week, every other on-position attribute at
# COACHING_REFERENCE_BASELINE_PTS (token maintenance), off-position at 0 — a coach
# who nudges the primaries and neglects the rest. It scores exactly 1.0 by
# construction; both focused and broad coaching beat it. It is ~what CPU trains, so
# CPU lands on the ladder (f = 1.0); pillar 3 keeps CPU aligned to this constant.
# Changing it (or the cap/budget) re-scales every player's development.
COACHING_F_MIN = 0.85
COACHING_F_MAX = 1.20
# sens=1.0 → f == clamp(quality); the band edges are the real controllers.
COACHING_F_SENSITIVITY = 1.00
COACHING_SATURATION_CAP = 4.0        # points/week past which an attribute stops benefiting
COACHING_SLIDER_MAX = 5.0            # UI cap on a single attribute's weekly points
COACHING_STANDARD_BUDGET = 24.0      # representative weekly growth-point budget (sets the optimum)
COACHING_HEADROOM = 0.25             # quality the budget optimum reaches above reference; >F_MAX-1
                                     # on purpose, so the best few strategies PLATEAU at f 1.20
COACHING_REFERENCE_BREADTH = 3       # reference trains this many primaries
COACHING_REFERENCE_PRIMARY_PTS = 3.0
COACHING_REFERENCE_BASELINE_PTS = 1.0


def _positive_attrs_desc(position: str):
    w = POSITION_WEIGHTS[position]
    return sorted((a for a in w if w[a] > 0), key=lambda a: -w[a])


def reference_allocation(position: str) -> Dict[str, float]:
    """The frozen mediocre baseline in POINTS/week: top-``COACHING_REFERENCE_BREADTH``
    attributes at the primary level, other on-position attributes at the baseline
    level, off-position 0. Scores exactly 1.0 by construction."""
    ranked = _positive_attrs_desc(position)
    top = set(ranked[:COACHING_REFERENCE_BREADTH])
    return {a: (COACHING_REFERENCE_PRIMARY_PTS if a in top else COACHING_REFERENCE_BASELINE_PTS)
            for a in ranked}


def _coverage(allocation: Dict[str, float], position: str) -> float:
    """Saturating weighted coverage of a points allocation (Σ w_a·min(pts_a/cap,1))."""
    w = POSITION_WEIGHTS[position]
    return sum(wt * min(allocation.get(a, 0.0) / COACHING_SATURATION_CAP, 1.0)
               for a, wt in w.items() if wt > 0)


def _optimum_coverage(position: str) -> float:
    """Best coverage a standard budget can buy: saturate top-weight attributes to
    the cap first (each attribute capped at the slider max)."""
    w = POSITION_WEIGHTS[position]
    rem, cov = COACHING_STANDARD_BUDGET, 0.0
    for a in _positive_attrs_desc(position):
        if rem <= 0:
            break
        spend = min(COACHING_SATURATION_CAP, COACHING_SLIDER_MAX, rem)
        cov += w[a] * min(spend / COACHING_SATURATION_CAP, 1.0)
        rem -= spend
    return cov


def season_coaching_quality(allocation: Dict[str, float], position: str) -> float:
    """Score a season's training allocation (attr → POINTS/week) at ``position``,
    as saturating coverage normalised affinely so the reference → 1.0 and the budget
    optimum → 1.0 + COACHING_HEADROOM (equal headroom at every position). Focused
    and broad on-position coverage beat the reference; all-in and off-position fall
    toward the floor; a smaller total budget saturates fewer attributes → lower."""
    cov_ref = _coverage(reference_allocation(position), position)
    cov_opt = _optimum_coverage(position)
    if cov_opt <= cov_ref:
        return 1.0
    return 1.0 + (_coverage(allocation, position) - cov_ref) * (COACHING_HEADROOM / (cov_opt - cov_ref))


def coaching_f(cumulative_quality: float) -> float:
    """Bounded offseason modifier from cumulative career coaching quality (1.0 =
    reference → f 1.0)."""
    raw = 1.0 + COACHING_F_SENSITIVITY * (cumulative_quality - 1.0)
    return max(COACHING_F_MIN, min(COACHING_F_MAX, raw))


def _cat(rng: random.Random, dist) -> int:
    r = rng.random()
    acc = 0.0
    for i, p in enumerate(dist):
        acc += p
        if r < acc:
            return i
    return len(dist) - 1


def roll_growth_profile(ch_seed: int, rng: random.Random,
                        eligible_peak_rungs: Optional[List[str]] = None) -> dict:
    """Roll the frozen growth profile from a flat CH seed (§5, §8).

    ``eligible_peak_rungs`` restricts where a peak may land — used for lazy
    backfill of a mid-career player so peaks land on his REMAINING rungs only
    (§11.3 past-fixed/future-varies), never on a rung already behind him.
    Peak COUNT still uses the full CH-weighted distribution (a backfilled junior
    is not stunted); only placement is restricted."""
    t = (ch_seed - 1) / 99.0
    peak_dist = [CH_PEAK_LOW[i] + (CH_PEAK_HIGH[i] - CH_PEAK_LOW[i]) * t for i in range(4)]
    peak_count = _cat(rng, peak_dist)

    eligible = list(eligible_peak_rungs) if eligible_peak_rungs is not None else list(PEAK_RUNG_WEIGHTS)
    rungs = [r for r in PEAK_RUNG_WEIGHTS if r in eligible]
    weights = [PEAK_RUNG_WEIGHTS[r] for r in rungs]
    peak_count = min(peak_count, len(rungs))  # can't place more peaks than eligible rungs
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
    # Career HT gain rolled once and frozen; distributed per rung by the physical
    # timing group's HT curve (§6, HT own-curve).
    ht_total = round(min(HT_TOTAL_MAX, max(HT_TOTAL_MIN, rng.gauss(HT_TOTAL_MEAN, HT_TOTAL_SD))))
    return {"ch_seed": ch_seed, "peak_count": peak_count,
            "peak_rungs": peak_rungs, "family_timing": family_timing,
            "ht_total": ht_total}


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

    blend = {a: OFFSEASON_DISTRIBUTION_BLEND * offseason.get(a, 0.0)
                + (1 - OFFSEASON_DISTRIBUTION_BLEND) * inseason.get(a, 0.0) for a in GROWTH_ATTRS}
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
                          accumulator: Optional[Dict[str, float]] = None,
                          coaching_f_value: float = 1.0) -> dict:
    """Apply one offseason development event, moving the player onto ``rung`` (§7.1).

    ``coaching_f_value`` is the bounded coaching-quality modifier on the target
    (1.0 = reference-coached → lands on the validated ladder). Mutates and returns
    ``player`` (dict with 'attributes', 'height', 'weight',
    'position'/'training_position', 'jh_anchor'). Pure given ``rng``.
    """
    attrs = player["attributes"]
    position = player.get("training_position") or player["position"]
    anchor = player["jh_anchor"]

    # 1-2. budget from the rung + CH-seeded peak check → target RT for this rung,
    # scaled by the bounded coaching-quality modifier (Option 3).
    cum = 0.0
    for r in RUNG_TRANSITIONS:
        cum += STD_RUNG_INCREMENT[r] + (PEAK_BONUS if r in profile["peak_rungs"] else 0.0)
        if r == rung:
            break
    target_rt = _compress_rt(anchor * (1.0 + cum) * coaching_f_value)

    # HT first (own declining curve, never rung-locked), magnitude-capped. Each
    # rung gets its curve share of the career HT gain, integer-rounded
    # probabilistically so the per-rung shares hold in expectation without a carry
    # (a fractional carry accumulated into SR and broke the front-loaded shape).
    # HT is applied BEFORE the budget solve so RT is sized at the final height and
    # the ladder holds — growing into one's frame does not silently cost RT.
    # (Ordering note: §7.1 lists HT as step 5; correctness requires it precede the
    # RT solve.)
    ht_timing = profile["family_timing"]["physical"]
    want = min(HT_PER_RUNG_CAP, profile.get("ht_total", 0) * HT_CURVE_BY_TIMING[ht_timing][rung])
    dh = int(want) + (1 if rng.random() < (want - int(want)) else 0)
    if dh:
        player["height"] = player["height"] + dh

    # 3-4. grow attributes toward the rung's profile and RT target (post-HT height).
    #
    # PART A (desync fix): develop from the UN-FATIGUED anchor and write BOTH anchor
    # and live. `execute_training` treats anchor_ as authoritative and resets
    # live = anchor at week 1, so writing only live (the pre-2026-08 behaviour) let
    # every season's first training WIPE the offseason's growth on any attribute it
    # did not itself train — a big's scoring, a wing's shooting. And live may be
    # fatigue-scaled at rollover (_rescale_attributes sets live = anchor × NG), so
    # reading live as the base would bake fatigue permanently into the anchor. The
    # un-fatigued anchor is the input; both fields are written.
    for a in GROWTH_ATTRS:
        av = attrs.get(f"anchor_{a}")
        if av is not None:
            attrs[a] = av
    # PART B (Direction 1): the offseason is an ATTRACTOR toward the tier/year/position
    # PROFILE scaled to the ladder target RT — it targets BOTH a level (target_rt) and a
    # shape (the profile). It replaces the old additive budget (B≥0), which could only add,
    # so in-season growth ratcheted RT above the ladder and the leftover budget starved
    # non-signature attributes (a big's scoring, a wing's shooting). The attractor is
    # bidirectional and NOT budget-gated: it pulls RT down to the ladder when in-season
    # overshot, and fills the starved attributes even at RT-target. α<1 keeps it an
    # attractor, not a clamp — a user's in-season focus survives as a spike he pays for
    # elsewhere. RT lands on the ladder by construction (the target the profile is scaled
    # to), so generation and development describe one league. (`accumulator` no longer
    # shapes the offseason distribution — focus is expressed in-season now; it still drives
    # the QUALITY half → coaching_f → target_rt in develop_rollover.)
    prof = position_profile(position)
    weights = POSITION_WEIGHTS[position]
    fit = height_fitness(position, player["height"]) or 1.0
    denom = sum(weights.get(a, 0.0) * prof.get(a, 0.0) for a in GROWTH_ATTRS) or 1.0
    k = (target_rt / fit) / denom
    st_gain = 0
    for a in GROWTH_ATTRS:
        target_a = prof.get(a, 0.0) * k
        before = attrs.get(a, 0)
        moved = max(1, int(round(before + OFFSEASON_ATTRACTOR_ALPHA * (target_a - before))))
        if a == "ST":
            st_gain = moved - before
        attrs[a] = moved
        attrs[f"anchor_{a}"] = moved           # write both — survives next in-season

    # WT tracks strength: pounds with each inch of HT and with ST muscle gain.
    player["weight"] = player.get("weight", 0) + dh * rng.randint(*WT_LBS_PER_INCH) \
        + int(max(0, st_gain) * rng.randint(*WT_LBS_PER_ST))

    # 6. recompute all five RTs.
    player["position_ratings"] = compute_position_ratings(
        {"attributes": attrs, "height": player["height"]})
    player["class_year"] = rung
    return player


def init_career(position: str, tier: str, ch_seed: int, rng: random.Random):
    """Roll the growth profile and generate the JH starting player (§5, §11.1).

    The JH player is generated BELOW his adult frame by his rolled career HT gain,
    so HT growth over the career brings him up to (roughly) the adult height his
    position was drawn at — he grows INTO his frame rather than past it. Attributes
    are sized to the JH anchor at that shorter height. Returns (player, profile)."""
    from BackEnd.utils.player_generation import draw_height, HEIGHT_MIN_IN
    profile = roll_growth_profile(ch_seed, rng)
    adult_height = draw_height(position, rng)
    jh_height = max(HEIGHT_MIN_IN, adult_height - profile["ht_total"])
    jh = generate_player(position, "JH", tier, rng, height=jh_height, preserve_ch=ch_seed)
    player = {
        "attributes": jh["attributes"], "height": jh["height"], "weight": jh["weight"],
        "position": position, "training_position": position, "tier": tier,
        "jh_anchor": JH_ANCHOR_BY_TIER[tier], "position_ratings": jh["position_ratings"],
        "class_year": "JH", "development": profile, "_ht_carry": 0.0,
    }
    return player, profile


def simulate_career(position: str, tier: str, ch_seed: int, rng: random.Random,
                    accumulator: Optional[Dict[str, float]] = None) -> dict:
    """Generate a JH player and walk all four offseason rungs to SR (§11.1)."""
    player, profile = init_career(position, tier, ch_seed, rng)
    snapshots = {"JH": dict(player["position_ratings"])}
    attr_snapshots = {"JH": dict(player["attributes"])}
    height_snapshots = {"JH": player["height"]}
    for rung in RUNG_TRANSITIONS:
        develop_one_offseason(player, rung, profile, rng, accumulator=accumulator)
        snapshots[rung] = dict(player["position_ratings"])
        attr_snapshots[rung] = dict(player["attributes"])
        height_snapshots[rung] = player["height"]
    player["snapshots"] = snapshots
    player["attr_snapshots"] = attr_snapshots
    player["height_snapshots"] = height_snapshots
    return player


# JH → SR ladder in order. A player rolled ONTO `rung` has ratings that still
# reflect the PRECEDING year (develop_one_offseason has not run yet), so his RT must
# be divided by that preceding year's ladder multiplier to recover the JH anchor.
_RATINGS_LADDER = ("JH", "FR", "SO", "JR", "SR")


def _derive_entry_tier_from_rt(position_ratings: dict, rung: str) -> str:
    """Best-effort entry_tier for a player with no stored tier (legacy / edge only).

    YEAR-AWARE (fixed 2026-08-01). Tier anchors are JH-scale (Poor 20 … Elite 50)
    while the ladder multiplies by rung (SR 2.0×), so RT must be divided by the
    multiplier of the year the ratings reflect — the year BEFORE `rung`, since the
    caller rolls the player onto `rung` and has not developed him yet. The prior
    version divided by the cumulative dev increment to `rung` instead, which
    over-divided and down-classified every non-senior by ~1.5 tiers (an Average FR
    at RT 35 read Poor; only seniors derived correctly, by coincidence) — the same
    distortion that, once entry_tier stopped being persisted, silently degraded the
    whole league. This remains a FALLBACK: new recruits carry entry_tier pool→FPD
    and never reach here; a legacy old-scale big whose RT collapsed under height
    gating still misclassifies (documented caveat, new-franchises-only)."""
    idx = _RATINGS_LADDER.index(rung) if rung in _RATINGS_LADDER else 1  # unknown → assume FR
    return entry_tier_at_year(position_ratings, _RATINGS_LADDER[max(0, idx - 1)])


def entry_tier_at_year(position_ratings: dict, current_year: str) -> str:
    """Best-effort entry_tier from ratings that reflect ``current_year`` (year-aware).

    Divides top RT by that year's ladder multiplier to recover the JH anchor, then
    maps to the nearest tier. PREFER computing-and-STORING this at write time over
    leaving ``develop_rollover`` to re-derive at rollover: once coaching quality
    (pillar 3) drives f ≠ 1.0, RT diverges from the ladder by more than a full senior
    tier-step (a well-coached Average SR ~72 vs a neglected one ~51, against bands
    ~10 RT apart), so a DEFERRED derive silently misclassifies. Any path that writes a
    player doc without an entry_tier should call this and persist the result."""
    from BackEnd.utils.player_generation import normalize_year as _ny
    top_rt = max((v for v in (position_ratings or {}).values() if isinstance(v, (int, float))), default=30)
    mult = RUNG_MULTIPLIERS.get(current_year) or RUNG_MULTIPLIERS.get(_ny(current_year)) or RUNG_MULTIPLIERS["FR"]
    est_anchor = top_rt / mult
    return min(JH_ANCHOR_BY_TIER, key=lambda t: abs(JH_ANCHOR_BY_TIER[t] - est_anchor))


def develop_rollover(fpd_doc: dict, new_year: str, rng: random.Random,
                     season_allocation: Optional[Dict[str, float]] = None) -> dict:
    """Apply the offseason event to an FPD player rolling onto ``new_year`` (§7.1),
    handling the FPD document shape and lazy-backfilling a missing profile.

    ``season_allocation`` is the just-finished season's per-attribute training
    accumulator (attr → points/week, 0-5 per the drill sliders). None means "no
    recorded season" (CPU teams until pillar 3, or a player with no season) → the
    frozen reference → f 1.0 → lands on the validated ladder. It drives BOTH
    accumulator jobs, kept separate in code:

      • QUALITY: scored against ``training_position`` (§9.2 — a designed conversion
        is priced by the weight tables, so a natural SF trained toward PG must not
        also eat a coaching-quality penalty) → cumulative career average → the
        bounded modifier f on the offseason RT target.
      • DISTRIBUTION (§7.3): the same allocation shapes WHERE the offseason budget
        lands (blended in _distribution_fractions), so what was trained aims growth.

    ``training_position`` is a persisted field defaulting to ``position_intent`` and
    forward-copied here. Returns {attributes, height, weight, position_ratings,
    development, entry_tier, position_intent, training_position, coaching_quality,
    backfilled}. The caller persists all of them. Pure given rng.

    Lazy backfill (existing saves, §11.3 rule): a player with no `development` gets
    one rolled ONCE here from his live CH frozen as ch_seed, with peaks restricted
    to his REMAINING rungs, and it is returned for persistence so it never re-rolls.
    entry_tier / position_intent / training_position are derived if absent."""
    from BackEnd.utils.player_generation import normalize_year as _ny
    rung = _ny(new_year)
    if rung not in RUNG_TRANSITIONS:
        rung = "FR"
    meta = fpd_doc.get("meta") or {}
    attrs = dict(fpd_doc.get("attributes") or {})
    height = meta.get("height", attrs.get("height"))
    ratings = fpd_doc.get("position_ratings") or {}

    position_intent = fpd_doc.get("position_intent") or (
        max(ratings, key=ratings.get) if ratings else "SF")
    # training_position: where the player is being coached this cycle. Defaults to
    # position_intent (natural fit) and is forward-copied; a user converting a
    # player sets it explicitly (UI deferred to a later pass).
    training_position = fpd_doc.get("training_position") or position_intent
    entry_tier = fpd_doc.get("entry_tier")
    if not entry_tier:
        # FALLBACK — should fire ONLY for legacy docs. It fired for every new recruit
        # for four seasons (FRD dropped entry_tier) and nobody noticed, so it is loud
        # now: a warning per firing lets a dropped-field regression surface immediately
        # instead of silently down-classifying the league.
        entry_tier = _derive_entry_tier_from_rt(ratings, rung)
        logger.warning(
            "entry_tier missing for player %s (year=%s) — derived %r from RT. This "
            "fallback is for legacy docs only; if it fires for a signed recruit, a "
            "write path is dropping entry_tier.",
            fpd_doc.get("player_id"), new_year, entry_tier,
        )

    profile = fpd_doc.get("development")
    backfilled = False
    if not profile:
        backfilled = True
        ch_seed = int(attrs.get("anchor_CH", attrs.get("CH", rng.randint(1, 100))) or rng.randint(1, 100))
        # remaining rungs = this rung and everything after it
        remaining = list(RUNG_TRANSITIONS[RUNG_TRANSITIONS.index(rung):])
        profile = roll_growth_profile(ch_seed, rng, eligible_peak_rungs=remaining)

    # --- QUALITY half of the accumulator -------------------------------------
    # Score the season's allocation against training_position, fold into the career
    # average, and map to f. No recorded allocation → stays 1.0 → f 1.0 (reference).
    cq = fpd_doc.get("coaching_quality") or {"avg": 1.0, "n": 0}
    if season_allocation:
        season_quality = season_coaching_quality(season_allocation, training_position)
        n2 = cq["n"] + 1
        cq = {"avg": (cq["avg"] * cq["n"] + season_quality) / n2, "n": n2}
    f = coaching_f(cq["avg"])

    # --- DISTRIBUTION half of the accumulator (§7.3) -------------------------
    # The same allocation aims the offseason budget (blended with the age curve in
    # _distribution_fractions). None → the default position-weighted aim.
    distribution_accumulator = season_allocation or None

    player = {
        "attributes": attrs, "height": height, "weight": meta.get("weight", 0),
        "position": position_intent, "training_position": training_position,
        "jh_anchor": JH_ANCHOR_BY_TIER[entry_tier], "position_ratings": dict(ratings),
        "_ht_carry": fpd_doc.get("_ht_carry", 0.0),
    }
    develop_one_offseason(player, rung, profile, rng,
                          accumulator=distribution_accumulator, coaching_f_value=f)
    return {
        "attributes": player["attributes"], "height": player["height"],
        "weight": player["weight"], "position_ratings": player["position_ratings"],
        "development": profile, "entry_tier": entry_tier,
        "position_intent": position_intent, "training_position": training_position,
        "coaching_quality": cq, "backfilled": backfilled,
    }


__all__ = [
    "PHYSICAL_ATTRS", "SKILL_ATTRS", "MENTAL_ATTRS", "GROWTH_ATTRS", "FAMILY_OF",
    "RUNG_TRANSITIONS", "STD_RUNG_INCREMENT", "PEAK_BONUS",
    "RT_COMPRESSION_THRESHOLD", "RT_SOFT_CAP", "PEAK_COUNT_DISTRIBUTION",
    "CH_PEAK_LOW", "CH_PEAK_HIGH", "PEAK_RUNG_WEIGHTS", "FAMILY_TIMING_WEIGHTS",
    "FAMILY_CURVES", "OFFSEASON_DISTRIBUTION_BLEND", "NON_CORE_GROWTH_MULTIPLIER",
    "OFFSEASON_ATTRACTOR_ALPHA",
    "HT_CURVE_BY_TIMING", "HT_TOTAL_MEAN", "HT_TOTAL_SD", "HT_PER_RUNG_CAP",
    "COACHING_F_MIN", "COACHING_F_MAX", "COACHING_F_SENSITIVITY",
    "COACHING_SATURATION_CAP", "COACHING_SLIDER_MAX", "COACHING_STANDARD_BUDGET",
    "COACHING_HEADROOM", "COACHING_REFERENCE_BREADTH",
    "COACHING_REFERENCE_PRIMARY_PTS", "COACHING_REFERENCE_BASELINE_PTS",
    "reference_allocation", "season_coaching_quality", "coaching_f",
    "roll_growth_profile", "develop_one_offseason", "develop_rollover",
    "init_career", "simulate_career", "entry_tier_at_year",
]
