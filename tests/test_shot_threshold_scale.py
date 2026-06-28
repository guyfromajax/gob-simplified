"""Tests for centralized shot_threshold scale and frontend parity."""
from pathlib import Path
import re

import pytest

from BackEnd.constants import TEAM_ATTR_RANGES
from BackEnd.constants.shot_threshold_scale import (
    BALANCING_LEADING,
    BALANCING_TRAILING,
    FRANCHISE_INIT_HI,
    FRANCHISE_INIT_LO,
    HALF_SPAN,
    MAX,
    MID,
    MIN,
    SPAN,
    TOURNAMENT_SEED_ST_RANGES,
    clamp,
    pill_deviation,
    team_attr_range,
    to_public_dict,
)


def test_scale_invariants():
    assert SPAN == 200
    assert HALF_SPAN == 100
    assert MAX - MIN == SPAN
    assert MID == MIN + HALF_SPAN == MAX - HALF_SPAN
    assert BALANCING_TRAILING == MIN - 20
    assert BALANCING_LEADING == MAX - 20
    assert FRANCHISE_INIT_LO == MID - 20
    assert FRANCHISE_INIT_HI == MID - 10


def test_team_attr_range_wired_to_constants():
    assert team_attr_range() == (MIN, MAX)
    assert TEAM_ATTR_RANGES["shot_threshold"] == (MIN, MAX)


def test_clamp_and_pill_deviation():
    assert clamp(MIN - 50) == MIN
    assert clamp(MAX + 50) == MAX
    assert pill_deviation(MID) == 0
    assert pill_deviation(MIN) == HALF_SPAN
    assert pill_deviation(MAX) == -HALF_SPAN


def test_tournament_seed_ranges_within_bounds():
    for seed, (lo, hi) in TOURNAMENT_SEED_ST_RANGES.items():
        assert MIN <= lo <= hi <= MAX, f"seed {seed}: {(lo, hi)}"


def test_frontend_js_matches_backend():
    js_path = Path(__file__).resolve().parents[1] / "FrontEnd/static/js/shared/teamShotThresholdScale.js"
    content = js_path.read_text(encoding="utf-8")
    public = to_public_dict()
    for key, py_val in public.items():
        js_key = key.upper() if key != "half_span" else "HALF_SPAN"
        if js_key == "HALF_SPAN":
            pattern = rf"const HALF_SPAN = {py_val}|HALF_SPAN = SPAN / 2"
            assert re.search(pattern, content), f"HALF_SPAN mismatch"
        else:
            assert re.search(rf"const {js_key} = {py_val}\b", content), f"{js_key} != {py_val} in JS"
