"""Free throw shot variant selection."""
import random

from BackEnd.constants.shot_variants import (
    SHOT_VARIANT_AIRBALL,
    SHOT_VARIANT_BANK_MAKE,
    SHOT_VARIANT_FREE_THROW_MISS,
    SHOT_VARIANT_FREE_THROW_SWISH,
    SHOT_VARIANT_HEAVY_RATTLE,
    SHOT_VARIANT_LITTLE_RATTLE,
    select_ft_shot_variant,
)


class _SeqRng:
    """Deterministic rng.choices: always pick the first variant."""

    def choices(self, variants, weights=None, k=1):
        return [variants[0]]


def test_ft_first_roll_make_high_delta_prefers_swish():
    variant = select_ft_shot_variant(
        ft_shot_score=90,
        ft_primary_roll=50,
        makes_shot=True,
        ft_made_on_second_chance=False,
        rng=_SeqRng(),
    )
    assert variant == SHOT_VARIANT_FREE_THROW_SWISH


def test_ft_second_chance_make_uses_second_chance_table():
    variant = select_ft_shot_variant(
        ft_shot_score=50,
        ft_primary_roll=80,
        makes_shot=True,
        ft_made_on_second_chance=True,
        rng=_SeqRng(),
    )
    # The documented second-chance table starts with LITTLE_RATTLE (20%);
    # _SeqRng deliberately selects the first table entry.
    assert variant == SHOT_VARIANT_LITTLE_RATTLE


def test_ft_miss_near_delta_prefers_little_rattle():
    variant = select_ft_shot_variant(
        ft_shot_score=70,
        ft_primary_roll=75,
        makes_shot=False,
        ft_made_on_second_chance=False,
        rng=_SeqRng(),
    )
    assert variant == SHOT_VARIANT_LITTLE_RATTLE


def test_ft_miss_far_delta_can_roll_airball():
    rng = random.Random(0)
    variants = {
        select_ft_shot_variant(50, 95, False, False, rng=rng)
        for _ in range(200)
    }
    assert SHOT_VARIANT_AIRBALL in variants


def test_ft_second_chance_make_ignores_miss_table():
    variant = select_ft_shot_variant(
        ft_shot_score=50,
        ft_primary_roll=99,
        makes_shot=True,
        ft_made_on_second_chance=True,
        rng=_SeqRng(),
    )
    assert variant != SHOT_VARIANT_FREE_THROW_MISS
    assert variant != SHOT_VARIANT_AIRBALL


def test_ft_second_chance_bank_make_in_table():
    variant = select_ft_shot_variant(
        ft_shot_score=50,
        ft_primary_roll=99,
        makes_shot=True,
        ft_made_on_second_chance=True,
        rng=_SeqRng(),
    )
    # First entry in second-chance table is LITTLE_RATTLE; bank is last.
    # Spot-check table includes bank on a full weighted run.
    rng = random.Random(42)
    seen = {
        select_ft_shot_variant(50, 99, True, True, rng=rng)
        for _ in range(500)
    }
    assert SHOT_VARIANT_BANK_MAKE in seen
