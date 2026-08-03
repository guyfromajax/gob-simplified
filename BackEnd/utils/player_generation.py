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

import hashlib
import logging
import random
from typing import Dict, Optional

logger = logging.getLogger(__name__)

from BackEnd.constants import LEAGUE_MEDIAN_HEIGHT_IN
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

# ── Career height gain (§16.3) — single source of truth, imported by player_development ──
# HEIGHT_IDEAL_IN are MATURE heights (the fitness peaks). A player is generated BELOW his
# adult frame by the REMAINING share of his career HT gain (grow-into-frame, §11.2), so HT
# growth over the career brings him to his adult draw. JH carries the full gain; a senior
# none. Shares are the §16.3 curve: JH→FR 40 / FR→SO 30 / SO→JR 20 / JR→SR 10, so the
# cumulative gain BY a year gives the remaining below.
HT_TOTAL_MEAN = 3.2
HT_TOTAL_SD = 1.9
HT_TOTAL_MIN, HT_TOTAL_MAX = 0, 8
HT_REMAINING_SHARE_BY_YEAR = {"JH": 1.0, "FR": 0.6, "SO": 0.3, "JR": 0.1, "SR": 0.0}

# ── Potential factor (Player Potential Rating, Phase 1) ──────────────────────
# A career-static scalar, uniform in ±POTENTIAL_FACTOR_BAND, drawn independently of entry
# tier and of ch_seed. It scales the RT target the offseason event solves for (wired in a
# later phase), so it is a real development mechanic, and is displayed as a projected letter
# grade alongside the current one. Uniform (not bell-curved) — busts and gems are as common
# as median players. Single source of the draw + the legacy fallback; every generation and
# persistence path calls these two helpers rather than re-implementing the band.
POTENTIAL_FACTOR_BAND = 0.15


def draw_potential_factor(rng: random.Random) -> float:
    """Uniform draw in [1 − BAND, 1 + BAND] from the caller's rng. Independent of tier and
    ch_seed by construction (a separate draw that reads neither)."""
    return round(rng.uniform(1.0 - POTENTIAL_FACTOR_BAND, 1.0 + POTENTIAL_FACTOR_BAND), 4)


def resolve_potential_factor(player_id, stored=None, *, warn=True) -> float:
    """Return ``stored`` when it is a usable number; otherwise DETERMINISTICALLY derive one
    from a hash of ``player_id`` so a legacy player (generated before this field existed)
    yields the SAME value on every read rather than re-rolling per session. This is the
    persistence-side safety net — new players carry a drawn value; only pre-Phase-1 docs
    reach the hash branch.

    ``warn`` gates the fallback log. WRITE/backfill paths (develop_rollover, _build_fpd_doc)
    keep it True so a dropped-field regression surfaces loudly, as entry_tier's does. READ/
    display paths pass warn=False: for a pre-Phase-5 pool roster EVERY player legitimately
    hits the fallback, and one warning per player per page-load would be noise, not signal.
    The Phase-5 backfill persists exactly this hash-derived value, so the displayed ceiling
    does not change when the field lands."""
    if isinstance(stored, (int, float)) and stored > 0:
        return float(stored)
    h = int(hashlib.sha256(str(player_id).encode("utf-8")).hexdigest()[:12], 16)
    u = h / float(16 ** 12)  # deterministic uniform in [0, 1)
    pf = round(1.0 - POTENTIAL_FACTOR_BAND + u * 2.0 * POTENTIAL_FACTOR_BAND, 4)
    if warn:
        logger.warning(
            "potential_factor missing for player %s — derived %.4f deterministically from "
            "player_id (legacy fallback; a generated player should carry a drawn value).",
            player_id, pf,
        )
    return pf

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
# Bands expressed as offsets from the league median so the next distribution
# shift is a one-line change, not another sweep. At median 78: <74 / 74-77 /
# 78-81 / >=82 (was <72/72-75/76-80/>80 pre-recal).
_MED = LEAGUE_MEDIAN_HEIGHT_IN
WEIGHT_BY_HEIGHT_BANDS = (
    (_MED - 4, (170, 200)),   # below median-4
    (_MED,     (190, 225)),   # median-4 .. median-1
    (_MED + 4, (215, 255)),   # median .. median+3
    (10 ** 9,  (240, 290)),   # median+4 and up
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


def draw_height(position: str, rng: random.Random, year: Optional[str] = None) -> int:
    """Draw a height for ``position``. With ``year`` given, apply GROW-INTO-FRAME: the
    adult draw minus the remaining share of a drawn career HT gain (§11.2/§16.3), so a JH
    lands ~3.2in below his frame and a senior at it. Without ``year`` the raw adult draw is
    returned (init_career takes that path and subtracts its own rolled ht_total — passing a
    year here too would double-count the gain)."""
    h = rng.gauss(HEIGHT_IDEAL_IN[position], HEIGHT_SD_IN)
    if year is not None:
        remaining = HT_REMAINING_SHARE_BY_YEAR.get(normalize_year(year), 0.0)
        if remaining:
            gain = max(HT_TOTAL_MIN, min(HT_TOTAL_MAX, rng.gauss(HT_TOTAL_MEAN, HT_TOTAL_SD)))
            h -= remaining * gain
    return max(HEIGHT_MIN_IN, min(HEIGHT_MAX_IN, round(h)))


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
        height = draw_height(position, rng, year)     # grow-into-frame by class year
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
    # Drawn LAST so every prior draw (core/CH/EM/weight) keeps its stream position — only this
    # new trailing field is appended. Independent of tier and ch_seed.
    potential_factor = draw_potential_factor(rng)
    return {
        "name": name,
        "attributes": attributes,
        "height": height,
        "weight": weight,
        "position": position,
        "tier": tier,
        "year": normalize_year(year),
        "position_ratings": ratings,
        "potential_factor": potential_factor,
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
