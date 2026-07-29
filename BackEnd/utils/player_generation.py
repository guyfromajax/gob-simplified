"""Position-intent-first player generation (design §11.2, interim form §11.1).

The old generator drew height and attributes independently and let RT sort
players into positions afterward, which left position *supply* at the mercy of
whatever distribution fell out (centres at 10.9%). This inverts the order:

    1. position intent   (~20% each)
    2. height            drawn from that position's distribution (§11.2)
    3. tier              from the §4.1 frequency table
    4. attributes        drawn from the position's profile, then scaled so that
                         RT at the intended position hits the class-year target
                         on the §4.2 ladder (interim "generate directly at the
                         class-year target" form, §11.1)

Argmax balance and the class-year RT ladder then hold *by construction*; the
weight vectors only need to be consistent with intent, not manufacture balance
out of an unbalanced population.

This module is the single generator shared by franchise recruit generation
(Phase 3) and the universal-pool remap (Phase 4). It is RNG-injectable so each
caller can drive it from its own stream.

NOTE — out of scope for this pass: the `development` subdocument (entry_tier,
peak_count, family_timing, ch_seed, training_position). This interim generator
produces attributes/height/tier directly at the class-year target; the offseason
development event and the persisted development profile are later tasks.
"""

from __future__ import annotations

import random
from typing import Dict, Optional

from BackEnd.utils.position_ratings import (
    HEIGHT_FITNESS,
    POSITION_WEIGHTS,
    compute_position_ratings,
    height_fitness,
)

POSITIONS = ("PG", "SG", "SF", "PF", "C")

# ── Position intent ──────────────────────────────────────────────────────────
POSITION_INTENT_SHARE = 0.20  # roughly even; balance follows by construction

# ── Height distribution per position (design §11.2) ──────────────────────────
# Ideals mirror the height-fitness peaks; sd ≈ 2.0-2.2 gives a league aggregate
# near mean 78, sd 3.6.
HEIGHT_IDEAL_IN = {pos: ideal for pos, (ideal, _short, _tall) in HEIGHT_FITNESS.items()}
HEIGHT_SD_IN = 2.1
HEIGHT_MIN_IN = 64
HEIGHT_MAX_IN = 92

# ── Entry tiers (design §4.1) ────────────────────────────────────────────────
# Six tiers. JH RT anchor and share-of-generated-players. (Supersedes the
# four-value TIER_FREQUENCY in design §12, which predates the six-tier table.)
JH_ANCHOR_BY_TIER = {
    "Poor": 20,
    "BelowAverage": 25,
    "Average": 30,
    "Good": 35,
    "Great": 40,
    "Elite": 50,
}
TIER_FREQUENCY = {
    "Poor": 0.07,
    "BelowAverage": 0.20,
    "Average": 0.40,
    "Good": 0.20,
    "Great": 0.11,
    "Elite": 0.02,
}

# ── Rung multipliers (design §4.2, one-peak path) ────────────────────────────
# Interim generation multiplies the JH anchor by the rung directly.
RUNG_MULTIPLIERS = {"JH": 1.00, "FR": 1.17, "SO": 1.43, "JR": 1.80, "SR": 2.00}
CLASS_YEARS = ("FR", "SO", "JR", "SR")  # rostered pool years (JH = recruit entrant)

_YEAR_ALIASES = {
    "jh": "JH", "junior high": "JH",
    "fr": "FR", "freshman": "FR", "frosh": "FR",
    "so": "SO", "sophomore": "SO",
    "jr": "JR", "junior": "JR",
    "sr": "SR", "senior": "SR",
}

# ── Attribute profile shape ──────────────────────────────────────────────────
# A position's baseline attribute magnitudes are proportional to its RT weights:
# the top-weighted (signature) attribute sits at 1.0, an unweighted attribute at
# PROFILE_FILLER. This is what makes "a shooter a shooter" — identity comes from
# the weight table itself, kept self-consistent with the RT formula rather than a
# second hand-maintained archetype table.
PROFILE_FILLER = 0.45          # unweighted attr baseline, as a fraction of signature
PROFILE_ND_BASE = 0.60         # ND is not in any RT vector; give it a moderate level
ATTR_NOISE_SD = 0.13           # per-attribute multiplicative spread → tweeners

# RT-relevant attributes (union of all weight vectors) plus ND (mental, no RT).
RT_ATTRS = tuple(sorted({a for w in POSITION_WEIGHTS.values() for a in w}))
CORE_ATTRS = RT_ATTRS + ("ND",)

# ── Weight from height (design §11.2 / Phase 5 re-band) ──────────────────────
# Re-banded for the new distribution (median ~78). Bands shifted up by ~6 inches
# from the old <72/72-75/76-80/>80 split so a median player is not "light".
WEIGHT_BY_HEIGHT_BANDS = (
    (74, (170, 200)),   # < 74 in
    (78, (190, 225)),   # 74-77
    (82, (215, 255)),   # 78-81
    (999, (240, 290)),  # >= 82
)


def normalize_year(year: Optional[str]) -> str:
    """Map any spelling of a class year to one of JH/FR/SO/JR/SR (default FR)."""
    if not year:
        return "FR"
    return _YEAR_ALIASES.get(str(year).strip().lower(), "FR")


def draw_tier(rng: random.Random) -> str:
    tiers = list(TIER_FREQUENCY)
    return rng.choices(tiers, weights=[TIER_FREQUENCY[t] for t in tiers], k=1)[0]


def draw_position_intent(rng: random.Random) -> str:
    return rng.choice(POSITIONS)


def draw_height(position: str, rng: random.Random) -> int:
    ideal = HEIGHT_IDEAL_IN[position]
    h = round(rng.gauss(ideal, HEIGHT_SD_IN))
    return max(HEIGHT_MIN_IN, min(HEIGHT_MAX_IN, h))


def weight_from_height(height: float, rng: random.Random) -> int:
    for ceil_in, (lo, hi) in WEIGHT_BY_HEIGHT_BANDS:
        if height < ceil_in:
            return rng.randint(lo, hi)
    return rng.randint(*WEIGHT_BY_HEIGHT_BANDS[-1][1])


def target_rt(tier: str, year: str) -> float:
    """Ladder target RT for a player of ``tier`` at class ``year`` (§4.1 × §4.2)."""
    return JH_ANCHOR_BY_TIER[tier] * RUNG_MULTIPLIERS[normalize_year(year)]


def position_profile(position: str) -> Dict[str, float]:
    """Baseline (noise-free) relative magnitude per attribute for ``position``.

    Signature attribute → 1.0, unweighted attribute → PROFILE_FILLER, others
    interpolated by their share of the position's max weight.
    """
    weights = POSITION_WEIGHTS[position]
    max_w = max(weights.values())
    profile = {}
    for attr in RT_ATTRS:
        w = weights.get(attr, 0.0)
        profile[attr] = PROFILE_FILLER + (1.0 - PROFILE_FILLER) * (w / max_w)
    profile["ND"] = PROFILE_ND_BASE
    return profile


def generate_core_attributes(
    position: str, height: float, target: float, rng: random.Random,
    relative_order: Optional[Dict[str, float]] = None,
) -> Dict[str, int]:
    """Attributes scaled so RT at ``position`` equals ``target`` (given height).

    ``relative_order`` optionally overrides the position profile with a caller-
    supplied per-attribute ranking (used by the Phase 4 remap to preserve each
    real player's relative attribute ordering — "a shooter stays a shooter").
    Values are treated as relative magnitudes, not final numbers.
    """
    base = relative_order if relative_order is not None else position_profile(position)
    # Apply per-attribute multiplicative noise → identity spread (tweeners).
    profile = {a: max(0.01, base.get(a, PROFILE_FILLER) * rng.gauss(1.0, ATTR_NOISE_SD))
               for a in CORE_ATTRS}

    fit = height_fitness(position, height)
    weighted_mean = sum(POSITION_WEIGHTS[position].get(a, 0.0) * profile[a] for a in CORE_ATTRS)
    if fit <= 0 or weighted_mean <= 0:
        k = 0.0
    else:
        k = target / (fit * weighted_mean)

    attrs = {a: max(1, int(round(k * profile[a]))) for a in CORE_ATTRS}
    return attrs


def generate_player(
    position: str, year: str, tier: str, rng: random.Random,
    *, height: Optional[int] = None, name: str = "",
    relative_order: Optional[Dict[str, float]] = None,
    preserve_ch: Optional[int] = None,
) -> Dict[str, object]:
    """Generate one player at the class-year ladder target for ``position``.

    Returns a dict with ``attributes`` (core + anchor_ + CH/EM/MO/NG),
    ``height``, ``weight``, ``position_ratings``, ``position`` (intent),
    ``tier`` and ``year``. Identity fields (name) are pass-through.
    """
    if height is None:
        height = draw_height(position, rng)
    target = target_rt(tier, year)
    core = generate_core_attributes(position, height, target, rng, relative_order=relative_order)

    attributes: Dict[str, object] = dict(core)
    # Anchors mirror live values for every malleable/static attribute.
    for a in CORE_ATTRS:
        attributes[f"anchor_{a}"] = attributes[a]
    # CH: flat randint(1,100) per §8 (or preserved for a remapped real player).
    ch = preserve_ch if preserve_ch is not None else rng.randint(1, 100)
    attributes["CH"] = ch
    attributes["anchor_CH"] = ch
    attributes["EM"] = rng.randint(1, 100)
    attributes["anchor_EM"] = attributes["EM"]
    attributes["MO"] = 0
    attributes["anchor_MO"] = 0
    attributes["NG"] = 1.0
    attributes["anchor_NG"] = 1.0

    weight = weight_from_height(height, rng)
    ratings = compute_position_ratings({"attributes": attributes, "height": height, "name": name})
    return {
        "name": name,
        "attributes": attributes,
        "height": height,
        "weight": weight,
        "position": position,
        "tier": tier,
        "year": normalize_year(year),
        "position_ratings": ratings,
    }


def balanced_class_years(count: int, rng: random.Random) -> list[str]:
    """~25% each of FR/SO/JR/SR, shuffled (design §11 class-size balance)."""
    per = count // len(CLASS_YEARS)
    years = [y for y in CLASS_YEARS for _ in range(per)]
    years += [rng.choice(CLASS_YEARS) for _ in range(count - len(years))]
    rng.shuffle(years)
    return years


__all__ = [
    "POSITIONS", "JH_ANCHOR_BY_TIER", "TIER_FREQUENCY", "RUNG_MULTIPLIERS",
    "HEIGHT_IDEAL_IN", "HEIGHT_SD_IN", "CLASS_YEARS", "CORE_ATTRS", "RT_ATTRS",
    "normalize_year", "draw_tier", "draw_position_intent", "draw_height",
    "weight_from_height", "target_rt", "position_profile",
    "generate_core_attributes", "generate_player", "balanced_class_years",
]
