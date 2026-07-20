"""Shot make/miss animation variant selection.

The backend picks a `shot_variant` for every resolved non-block shot (free
throws excluded). The variant drives the frontend animation family and the
SFX layer downstream. Selection lives here so the same simulation replays
identically.

Tier definition uses `gap = shot_score - shot_threshold` — closeness to
the outcome threshold, not absolute score.
"""
from BackEnd.utils.sim_random import sim_rng as random

from BackEnd.constants import (
    FLSS_HEAVE_MISS_BACKBOARD_MAX,
    FLSS_HEAVE_MISS_RATTLE_MAX,
    FLSS_HEAVE_MISS_RIM_BOUNCE_MAX,
)


SHOT_VARIANT_SWISH = "SWISH"
SHOT_VARIANT_CLANK = "CLANK"
SHOT_VARIANT_BACK_OF_RIM = "BACK_OF_RIM"
SHOT_VARIANT_LITTLE_RATTLE = "LITTLE_RATTLE"
SHOT_VARIANT_NORMAL_RATTLE = "NORMAL_RATTLE"
SHOT_VARIANT_HEAVY_RATTLE = "HEAVY_RATTLE"
SHOT_VARIANT_BANK_MAKE = "BANK_MAKE"
SHOT_VARIANT_BANK_MISS = "BANK_MISS"
SHOT_VARIANT_AIRBALL = "AIRBALL"
SHOT_VARIANT_FREE_THROW_SWISH = "FREE_THROW_SWISH"
SHOT_VARIANT_FREE_THROW_MISS = "FREE_THROW_MISS"

_RATTLE_VARIANTS = frozenset({
    SHOT_VARIANT_LITTLE_RATTLE,
    SHOT_VARIANT_NORMAL_RATTLE,
    SHOT_VARIANT_HEAVY_RATTLE,
})

_MAKE_TIER_HIGH = 150
_MAKE_TIER_MID = 75
_MISS_TIER_HIGH = -150
_MISS_TIER_MID = -75

_OUTSIDE_SHOT_TYPES = frozenset({"outside"})
_INSIDE_SHOT_TYPES = frozenset({"attack", "inside"})


# Distribution tables: tier -> [(variant, weight), ...]. Weights per tier sum to 100.
_OUTSIDE_MAKE = {
    "high": [
        (SHOT_VARIANT_SWISH, 50),
        (SHOT_VARIANT_BACK_OF_RIM, 25),
        (SHOT_VARIANT_LITTLE_RATTLE, 10),
        (SHOT_VARIANT_NORMAL_RATTLE, 10),
        (SHOT_VARIANT_HEAVY_RATTLE, 5),
    ],
    "mid": [
        (SHOT_VARIANT_SWISH, 35),
        (SHOT_VARIANT_BACK_OF_RIM, 35),
        (SHOT_VARIANT_LITTLE_RATTLE, 10),
        (SHOT_VARIANT_NORMAL_RATTLE, 10),
        (SHOT_VARIANT_HEAVY_RATTLE, 10),
    ],
    "low": [
        (SHOT_VARIANT_SWISH, 15),
        (SHOT_VARIANT_BACK_OF_RIM, 25),
        (SHOT_VARIANT_LITTLE_RATTLE, 19),
        (SHOT_VARIANT_NORMAL_RATTLE, 20),
        (SHOT_VARIANT_HEAVY_RATTLE, 20),
        (SHOT_VARIANT_BANK_MAKE, 1),
    ],
}

_OUTSIDE_MISS = {
    "high": [
        (SHOT_VARIANT_CLANK, 49),
        (SHOT_VARIANT_BACK_OF_RIM, 25),
        (SHOT_VARIANT_LITTLE_RATTLE, 9),
        (SHOT_VARIANT_NORMAL_RATTLE, 9),
        (SHOT_VARIANT_HEAVY_RATTLE, 5),
        (SHOT_VARIANT_AIRBALL, 2),
        (SHOT_VARIANT_BANK_MISS, 1),
    ],
    "mid": [
        (SHOT_VARIANT_CLANK, 35),
        (SHOT_VARIANT_BACK_OF_RIM, 35),
        (SHOT_VARIANT_LITTLE_RATTLE, 10),
        (SHOT_VARIANT_NORMAL_RATTLE, 10),
        (SHOT_VARIANT_HEAVY_RATTLE, 10),
    ],
    "low": [
        (SHOT_VARIANT_CLANK, 15),
        (SHOT_VARIANT_BACK_OF_RIM, 15),
        (SHOT_VARIANT_LITTLE_RATTLE, 30),
        (SHOT_VARIANT_NORMAL_RATTLE, 20),
        (SHOT_VARIANT_HEAVY_RATTLE, 20),
    ],
}

_INSIDE_MAKE = {
    "high": [
        (SHOT_VARIANT_SWISH, 25),
        (SHOT_VARIANT_BACK_OF_RIM, 20),
        (SHOT_VARIANT_BANK_MAKE, 30),
        (SHOT_VARIANT_LITTLE_RATTLE, 10),
        (SHOT_VARIANT_NORMAL_RATTLE, 10),
        (SHOT_VARIANT_HEAVY_RATTLE, 5),
    ],
    "mid": [
        (SHOT_VARIANT_SWISH, 20),
        (SHOT_VARIANT_BACK_OF_RIM, 20),
        (SHOT_VARIANT_BANK_MAKE, 30),
        (SHOT_VARIANT_LITTLE_RATTLE, 10),
        (SHOT_VARIANT_NORMAL_RATTLE, 10),
        (SHOT_VARIANT_HEAVY_RATTLE, 10),
    ],
    "low": [
        (SHOT_VARIANT_SWISH, 10),
        (SHOT_VARIANT_BACK_OF_RIM, 15),
        (SHOT_VARIANT_BANK_MAKE, 30),
        (SHOT_VARIANT_LITTLE_RATTLE, 15),
        (SHOT_VARIANT_NORMAL_RATTLE, 15),
        (SHOT_VARIANT_HEAVY_RATTLE, 15),
    ],
}

_INSIDE_MISS = {
    "high": [
        (SHOT_VARIANT_CLANK, 35),
        (SHOT_VARIANT_BACK_OF_RIM, 20),
        (SHOT_VARIANT_BANK_MISS, 19),
        (SHOT_VARIANT_LITTLE_RATTLE, 5),
        (SHOT_VARIANT_NORMAL_RATTLE, 10),
        (SHOT_VARIANT_HEAVY_RATTLE, 10),
        (SHOT_VARIANT_AIRBALL, 1),
    ],
    "mid": [
        (SHOT_VARIANT_CLANK, 30),
        (SHOT_VARIANT_BACK_OF_RIM, 20),
        (SHOT_VARIANT_BANK_MISS, 20),
        (SHOT_VARIANT_LITTLE_RATTLE, 10),
        (SHOT_VARIANT_NORMAL_RATTLE, 10),
        (SHOT_VARIANT_HEAVY_RATTLE, 10),
    ],
    "low": [
        (SHOT_VARIANT_CLANK, 15),
        (SHOT_VARIANT_BACK_OF_RIM, 15),
        (SHOT_VARIANT_BANK_MISS, 20),
        (SHOT_VARIANT_LITTLE_RATTLE, 30),
        (SHOT_VARIANT_NORMAL_RATTLE, 10),
        (SHOT_VARIANT_HEAVY_RATTLE, 10),
    ],
}


def _tier(gap, made):
    if made:
        if gap > _MAKE_TIER_HIGH:
            return "high"
        if gap > _MAKE_TIER_MID:
            return "mid"
        return "low"
    if gap < _MISS_TIER_HIGH:
        return "high"
    if gap < _MISS_TIER_MID:
        return "mid"
    return "low"


def select_shot_variant(shot_score, shot_threshold, shot_type, made, rng=None):
    """Roll the make/miss animation variant for a resolved non-block shot.

    Caller must skip this for BLOCK outcomes and free throws.
    Raises ValueError on unknown shot_type — never silently defaults.
    """
    rng = rng or random
    gap = shot_score - shot_threshold

    if shot_type in _OUTSIDE_SHOT_TYPES:
        table = _OUTSIDE_MAKE if made else _OUTSIDE_MISS
    elif shot_type in _INSIDE_SHOT_TYPES:
        table = _INSIDE_MAKE if made else _INSIDE_MISS
    else:
        raise ValueError(
            f"select_shot_variant: unknown shot_type {shot_type!r}; "
            f"expected 'outside' | 'attack' | 'inside'."
        )

    pairs = table[_tier(gap, made)]
    variants = [v for v, _ in pairs]
    weights = [w for _, w in pairs]
    return rng.choices(variants, weights=weights, k=1)[0]


def _backboard_y_offset(shooter_y, rng):
    """Bank y point is biased by the shooter's vertical position so the ball
    banks toward the side of the backboard near the shooter's lane.

    Boundaries match the brief: the first branch uses strict `<` / `>` and the
    elif chain covers everything else exhaustively.
    """
    if shooter_y is None:
        raise ValueError(
            "roll_shot_variant_extras: shooter_y is required for Bank Off "
            "Backboard variants (BANK_MAKE / BANK_MISS)."
        )
    if 22 < shooter_y < 28:
        return rng.randint(-1, 1)
    if shooter_y > 27:
        return rng.randint(0, 3)
    if shooter_y < 23:
        return rng.randint(-3, 0)
    # Unreachable given the three branches above are exhaustive for all reals,
    # but guard anyway so a future edit can't silently drop a case.
    raise ValueError(f"_backboard_y_offset: shooter_y={shooter_y!r} fell through")


def roll_shot_variant_extras(variant, shooter_y=None, rng=None):
    """Roll variant-specific sub-parameters for replay determinism.

    `shooter_y` is required for the Bank Off Backboard variants — pass the
    shooter's grid y (e.g. from `_shooter_xy_from_roles`). Returns a flat dict
    suitable for stamping onto the result payload; empty when the variant has
    no extras.
    """
    rng = rng or random

    if variant in _RATTLE_VARIANTS:
        return {
            "shot_variant_rattle_start": rng.choice(("MSSS", "RIM")),
            "shot_variant_rattle_progression": rng.choice(("OPT_1", "OPT_2")),
        }
    if variant == SHOT_VARIANT_BANK_MAKE:
        return {
            "shot_variant_backboard_y_offset": _backboard_y_offset(shooter_y, rng),
        }
    if variant == SHOT_VARIANT_BANK_MISS:
        return {
            "shot_variant_backboard_y_offset": _backboard_y_offset(shooter_y, rng),
            "shot_variant_backboard_miss_rim_offset_x": rng.randint(-1, 1),
            "shot_variant_backboard_miss_rim_offset_y": rng.randint(-1, 1),
            # Pre-roll the 50/50 SFX choice so replays stay deterministic
            # (matches the legacy random.random() < 0.5 split in gameSfx.js).
            "shot_variant_bank_miss_sfx_file": rng.choice(
                ("bb-clank.wav", "bb-clank-2.wav"),
            ),
        }
    return {}


# Free-throw variant tables (SFX_System.md §Free Throw variant selection).
_FT_MAKE_FIRST_HIGH = [
    (SHOT_VARIANT_FREE_THROW_SWISH, 60),
    (SHOT_VARIANT_BACK_OF_RIM, 30),
    (SHOT_VARIANT_LITTLE_RATTLE, 10),
]
_FT_MAKE_FIRST_MID = [
    (SHOT_VARIANT_FREE_THROW_SWISH, 30),
    (SHOT_VARIANT_BACK_OF_RIM, 30),
    (SHOT_VARIANT_LITTLE_RATTLE, 30),
    (SHOT_VARIANT_NORMAL_RATTLE, 10),
]
_FT_MAKE_FIRST_LOW = [
    (SHOT_VARIANT_FREE_THROW_SWISH, 20),
    (SHOT_VARIANT_BACK_OF_RIM, 20),
    (SHOT_VARIANT_LITTLE_RATTLE, 20),
    (SHOT_VARIANT_NORMAL_RATTLE, 20),
    (SHOT_VARIANT_HEAVY_RATTLE, 20),
]
_FT_MAKE_SECOND_CHANCE = [
    (SHOT_VARIANT_LITTLE_RATTLE, 20),
    (SHOT_VARIANT_NORMAL_RATTLE, 35),
    (SHOT_VARIANT_HEAVY_RATTLE, 40),
    (SHOT_VARIANT_BANK_MAKE, 5),
]
_FT_MISS_NEAR = [
    (SHOT_VARIANT_LITTLE_RATTLE, 40),
    (SHOT_VARIANT_FREE_THROW_MISS, 30),
    (SHOT_VARIANT_CLANK, 20),
    (SHOT_VARIANT_NORMAL_RATTLE, 10),
]
_FT_MISS_MID = [
    (SHOT_VARIANT_NORMAL_RATTLE, 30),
    (SHOT_VARIANT_FREE_THROW_MISS, 35),
    (SHOT_VARIANT_CLANK, 20),
    (SHOT_VARIANT_HEAVY_RATTLE, 10),
    (SHOT_VARIANT_LITTLE_RATTLE, 5),
]
_FT_MISS_FAR = [
    (SHOT_VARIANT_FREE_THROW_MISS, 40),
    (SHOT_VARIANT_CLANK, 40),
    (SHOT_VARIANT_NORMAL_RATTLE, 15),
    (SHOT_VARIANT_BANK_MISS, 3),
    (SHOT_VARIANT_AIRBALL, 2),
]


def _weighted_choice(pairs, rng):
    variants = [v for v, _ in pairs]
    weights = [w for _, w in pairs]
    return rng.choices(variants, weights=weights, k=1)[0]


def select_ft_shot_variant(
    ft_shot_score,
    ft_primary_roll,
    makes_shot,
    ft_made_on_second_chance,
    rng=None,
):
    """Roll the animation variant for a resolved free throw.

    ``delta = ft_shot_score - ft_primary_roll`` always uses the first roll,
    even when a crowd second-chance converts a primary miss to a make.
    """
    rng = rng or random
    delta = float(ft_shot_score) - float(ft_primary_roll)

    if makes_shot:
        if ft_made_on_second_chance:
            pairs = _FT_MAKE_SECOND_CHANCE
        elif delta > 30:
            pairs = _FT_MAKE_FIRST_HIGH
        elif delta > 10:
            pairs = _FT_MAKE_FIRST_MID
        elif delta > 0:
            pairs = _FT_MAKE_FIRST_LOW
        else:
            pairs = _FT_MAKE_FIRST_LOW
    elif delta > -10:
        pairs = _FT_MISS_NEAR
    elif delta > -30:
        pairs = _FT_MISS_MID
    else:
        pairs = _FT_MISS_FAR

    return _weighted_choice(pairs, rng)


def select_flss_heave_miss_variant(miss_margin, rng=None):
    """Pick rim-action variant for a missed FLSS heave from roll proximity.

    ``miss_margin = roll - shot_score`` where ``made`` requires
    ``shot_score > roll``. Bands mirror ``FLSS_HEAVE_MISS_*`` constants in
    ``BackEnd.constants``.
    """
    rng = rng or random
    margin = float(miss_margin)
    if margin <= FLSS_HEAVE_MISS_RATTLE_MAX:
        return rng.choice([
            SHOT_VARIANT_LITTLE_RATTLE,
            SHOT_VARIANT_NORMAL_RATTLE,
            SHOT_VARIANT_HEAVY_RATTLE,
        ])
    if margin <= FLSS_HEAVE_MISS_RIM_BOUNCE_MAX:
        return SHOT_VARIANT_BACK_OF_RIM
    if margin <= FLSS_HEAVE_MISS_BACKBOARD_MAX:
        return SHOT_VARIANT_BANK_MISS
    return SHOT_VARIANT_AIRBALL
