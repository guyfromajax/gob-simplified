"""Player-development shape constants — gain percentages, floors, camp (§10).

Position fit and class are stored directly as gain percentages. Shape-P6 bases are frozen from the
pre-development t0 league export (seed 202608061); never re-derive from a
developed snapshot.
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

# ── Core-12 (growth attrs used for shape / floors) ──────────────────────────
CORE_12: Tuple[str, ...] = (
    "ST", "AG", "SC", "SH", "ID", "OD", "PS", "BH", "RB", "FT", "IQ", "ND",
)
POSITIONS: Tuple[str, ...] = ("PG", "SG", "SF", "PF", "C")

# ── Direct gain percentages ─────────────────────────────────────────────────
TRAINING_GAIN_UNIVERSALS = frozenset({"ND", "FT", "IQ"})
TRAINING_PHYSICAL_WALLS: Dict[str, frozenset] = {
    "PG": frozenset({"RB", "ID"}), "SG": frozenset({"RB", "ID"}),
    "SF": frozenset(), "PF": frozenset(), "C": frozenset({"AG"}),
}

# Direct authored percentages; there is no cost or reciprocal calculation.
TRAINING_GAIN_PERCENTAGES: Dict[str, Dict[str, float]] = {
    "PG": {"ST": 35, "AG": 83, "SC": 40, "SH": 45, "ID": 25, "OD": 70, "PS": 85, "BH": 100, "RB": 25, "FT": 100, "IQ": 100, "ND": 100},
    "SG": {"ST": 35, "AG": 68, "SC": 55, "SH": 100, "ID": 25, "OD": 60, "PS": 70, "BH": 70, "RB": 25, "FT": 100, "IQ": 100, "ND": 100},
    "SF": {"ST": 40, "AG": 53, "SC": 82, "SH": 64, "ID": 50, "OD": 91, "PS": 39, "BH": 39, "RB": 50, "FT": 100, "IQ": 100, "ND": 100},
    "PF": {"ST": 99, "AG": 45, "SC": 55, "SH": 47, "ID": 67, "OD": 35, "PS": 35, "BH": 25, "RB": 100, "FT": 100, "IQ": 100, "ND": 100},
    "C": {"ST": 77, "AG": 25, "SC": 68, "SH": 40, "ID": 100, "OD": 40, "PS": 33, "BH": 25, "RB": 100, "FT": 100, "IQ": 100, "ND": 100},
}

# Per-point gain multiplier by class year. Upperclassmen raised 2026-08-14 (JR 80→95,
# SR 71→100): under free-will the flat pre-training decay outran their discounted gains,
# so a reference-coached JR barely held and a SR REGRESSED in-season (net ~−2 RT/yr).
# Bumping only JR/SR flips their in-season net positive (JR +0.8→+3.1, SR −2.3→+0.7)
# without touching FR/SO (already healthy) or removing decay — the surgical fix from the
# free-will work plan. Reference career arc rises modestly (~+27→+32), no runaway.
CLASS_GAIN_PERCENTAGES: Dict[str, float] = {
    "freshman": 100, "sophomore": 91, "junior": 95, "senior": 100,
    "Freshman": 100, "Sophomore": 91, "Junior": 95, "Senior": 100,
    "FR": 100, "SO": 91, "JR": 95, "SR": 100,
}

# Named exceptions to table invariants. Tests assert this exact list so an
# exception cannot be added silently.
TRAINING_GAIN_INVARIANT_EXCEPTIONS = {
    "strength_ordering": {
        ("PF", "C"): "PF strength 99% intentionally exceeds C 77% for prototype feel testing.",
    },
    "nonphysical_25_percent": {
        ("PF", "BH"): "Low handling value under review; not a documented physical wall.",
        ("C", "BH"): "Low handling value under review; not a documented physical wall.",
    },
}

# ── Floors (weight-scaled shape-P6) ─────────────────────────────────────────
# Direct floor multipliers preserve the former weight-derived floor behavior.
SHAPE_FLOOR_MULTIPLIERS: Dict[str, Dict[str, float]] = {
    "PG": {"ST": .4999999999999999, "AG": 1.0, "SC": .6666666666666667, "SH": .8333333333333336, "ID": 0.0, "OD": 1.0, "PS": 1.0, "BH": 1.0, "RB": 0.0, "FT": 1.0, "IQ": 1.0, "ND": 1.0},
    "SG": {"ST": .4999999999999999, "AG": 1.0, "SC": 1.0, "SH": 1.0, "ID": 0.0, "OD": 1.0, "PS": .6666666666666667, "BH": .6666666666666667, "RB": 0.0, "FT": 1.0, "IQ": 1.0, "ND": 1.0},
    "SF": {"ST": .7999999999999998, "AG": 1.0, "SC": 1.0, "SH": 1.0, "ID": 1.0, "OD": 1.0, "PS": .62, "BH": .62, "RB": 1.0, "FT": 1.0, "IQ": 1.0, "ND": 1.0},
    "PF": {"ST": 1.0, "AG": .8488888888888889, "SC": 1.0, "SH": .8888888888888891, "ID": 1.0, "OD": .4999999999999999, "PS": .4999999999999999, "BH": .44444444444444453, "RB": 1.0, "FT": 1.0, "IQ": 1.0, "ND": 1.0},
    "C": {"ST": 1.0, "AG": 0.0, "SC": 1.0, "SH": .6666666666666667, "ID": 1.0, "OD": .6666666666666667, "PS": .44479166666666664, "BH": .44479166666666664, "RB": 1.0, "FT": 1.0, "IQ": 1.0, "ND": 1.0},
}

# Frozen t0 shape-P6 (attr / mean) by position — pre-development population only.
SHAPE_P6_FLOOR_BASE: Dict[str, Dict[str, float]] = {
    "PG": {
        "ST": 0.221394, "AG": 0.188518, "SC": 0.231709, "SH": 0.230758,
        "ID": 0.234538, "OD": 0.415667, "PS": 0.670059, "BH": 0.822897,
        "RB": 0.216420, "FT": 0.253244, "IQ": 0.766798, "ND": 0.223072,
    },
    "SG": {
        "ST": 0.347130, "AG": 0.356016, "SC": 0.321773, "SH": 0.945073,
        "ID": 0.309123, "OD": 0.446769, "PS": 0.307696, "BH": 0.270864,
        "RB": 0.318328, "FT": 0.280383, "IQ": 0.239857, "ND": 0.276485,
    },
    "SF": {
        "ST": 0.515187, "AG": 1.090840, "SC": 0.339775, "SH": 0.377288,
        "ID": 0.442222, "OD": 0.339968, "PS": 0.283447, "BH": 0.336559,
        "RB": 0.215242, "FT": 0.244968, "IQ": 0.316350, "ND": 0.322508,
    },
    "PF": {
        "ST": 1.099621, "AG": 0.260664, "SC": 0.332138, "SH": 0.268255,
        "ID": 0.514498, "OD": 0.219314, "PS": 0.273243, "BH": 0.210067,
        "RB": 0.708491, "FT": 0.248596, "IQ": 0.262590, "ND": 0.300581,
    },
    "C": {
        "ST": 0.585041, "AG": 0.212091, "SC": 0.527936, "SH": 0.264143,
        "ID": 0.627310, "OD": 0.251685, "PS": 0.250732, "BH": 0.221346,
        "RB": 0.481266, "FT": 0.253794, "IQ": 0.260116, "ND": 0.239051,
    },
}

# ── Camp ────────────────────────────────────────────────────────────────────
CAMP_WEEKS = 1
CAMP_GAIN_SCALE = 0.70   # free-will recalibration (2026-08): halved from 1.4. Under the
                         # additive offseason, camp gains PERSIST into the career, so the
                         # burst is scaled down; camp + in-season + reduced offseason land
                         # career RT ≈ 21 (the pre-free-will arc). See free_will_offseason_work_plan.
CAMP_POINT_BUDGET = 30
IN_SEASON_POINT_BUDGET = 24


def is_camp_week(week: int) -> bool:
    try:
        w = int(week)
    except (TypeError, ValueError):
        return False
    return 1 <= w <= CAMP_WEEKS


def class_gain_multiplier(year: Optional[str]) -> float:
    if not year:
        return 1.0
    key = str(year).strip()
    pct = CLASS_GAIN_PERCENTAGES.get(key, CLASS_GAIN_PERCENTAGES.get(key.lower(), 100.0))
    return float(pct / 100)


def training_attr_gain_multiplier(position: str, attr: str) -> float:
    """Fraction of raw gain retained from the direct percentage table."""
    pos = position if position in TRAINING_GAIN_PERCENTAGES else "SF"
    return float(TRAINING_GAIN_PERCENTAGES[pos].get(attr, 100) / 100)


def player_attr_gain_multiplier(player: Mapping, attr: str) -> float:
    """Combined position-fit and class-year multiplier for one player's gain."""
    position = resolve_training_position(player)
    year = player.get("year") or ((player.get("meta") or {}).get("year"))
    return training_attr_gain_multiplier(position, attr) * class_gain_multiplier(year)


def floor_mult(position: str, attr: str) -> float:
    pos = position if position in SHAPE_FLOOR_MULTIPLIERS else "SF"
    return SHAPE_FLOOR_MULTIPLIERS[pos].get(attr, 0.0)


def floor_need(position: str, attr: str, mean_core12: float) -> int:
    """Minimum absolute attribute value at this mean level."""
    pos = position if position in SHAPE_P6_FLOOR_BASE else "SF"
    s = SHAPE_P6_FLOOR_BASE[pos].get(attr, 0.0)
    m = floor_mult(pos, attr)
    if m <= 0 or mean_core12 <= 0:
        return 1
    return max(1, int(math.ceil(s * mean_core12 * m - 1e-9)))


def core12_mean(attrs: Mapping[str, float]) -> float:
    vals = []
    for a in CORE_12:
        v = attrs.get(a)
        if v is None:
            v = attrs.get(f"anchor_{a}")
        if v is not None:
            vals.append(float(v))
    return sum(vals) / len(vals) if vals else 0.0


def floor_violations(
    position: str,
    attrs: Mapping[str, float],
) -> list[Tuple[str, int, int]]:
    """Return [(attr, have, need), ...] for attrs below the weight-scaled floor."""
    mean = core12_mean(attrs)
    out = []
    for a in CORE_12:
        have = attrs.get(a)
        if have is None:
            have = attrs.get(f"anchor_{a}", 0)
        have_i = int(have or 0)
        need = floor_need(position, a, mean)
        if have_i < need:
            out.append((a, have_i, need))
    return out


def apply_floor_clamp_to_anchors(player: dict, position: Optional[str] = None) -> None:
    """Raise any core-12 anchor (and live) that decayed below the floor. No other writes.

    Needs are recomputed after each raise because ``need`` depends on mean(core-12);
    a single pass can leave a 1pt shortfall when raising one attr lifts the mean.
    """
    attrs = player.get("attributes") or {}
    pos = position or resolve_training_position(player)
    for _ in range(len(CORE_12) + 1):
        mean = core12_mean(attrs)
        raised = False
        for a in CORE_12:
            need = floor_need(pos, a, mean)
            anchor_key = f"anchor_{a}"
            cur = attrs.get(anchor_key, attrs.get(a, 0)) or 0
            if cur < need:
                attrs[anchor_key] = need
                attrs[a] = need
                raised = True
        if not raised:
            break
    player["attributes"] = attrs


def resolve_training_position(player: Mapping) -> str:
    pos = player.get("training_position") or player.get("position_intent")
    if pos in TRAINING_GAIN_PERCENTAGES:
        return pos
    ratings = player.get("position_ratings") or {}
    if ratings:
        best = max(ratings, key=ratings.get)
        if best in TRAINING_GAIN_PERCENTAGES:
            return best
    return "SF"


def training_position_projection(player: Mapping) -> dict[str, Optional[str]]:
    """Fields every training-player producer must carry into execution/UI."""
    return {
        "training_position": player.get("training_position"),
        "position_intent": player.get("position_intent"),
        "resolved_training_position": resolve_training_position(player),
    }


# Drill subtype → growth attribute (player-development cost units).
_DRILL_ATTR_MAP: Dict[str, Dict[str, str]] = {
    "offense": {"inside": "SC", "outside": "SH"},
    "defense": {"inside": "ID", "outside": "OD"},
    "technical": {"passing": "PS", "ball_handling": "BH", "rebounding": "RB"},
    "weight_room": {"strength": "ST", "agility": "AG"},
}
_GENERAL_ATTR_MAP: Dict[str, str] = {
    "conditioning": "ND",
    "free_throws": "FT",
    "film_study": "IQ",
}


def units_by_attr_from_allocations(allocations: Mapping) -> Dict[str, float]:
    """Extract per-attribute allocation units from FE or normalized drill structure."""
    units: Dict[str, float] = {a: 0.0 for a in CORE_12}
    if not allocations:
        return units

    player_drills = allocations.get("player_drills")
    if isinstance(player_drills, Mapping):
        for cat, subtypes in _DRILL_ATTR_MAP.items():
            block = player_drills.get(cat) or {}
            if not isinstance(block, Mapping):
                continue
            for subtype, attr in subtypes.items():
                units[attr] = units.get(attr, 0.0) + float(block.get(subtype, 0) or 0)
    else:
        # Normalized keys from _normalize_allocations
        alias = {
            "offensive_drills": "offense",
            "defensive_drills": "defense",
            "technical_drills": "technical",
            "weight_room": "weight_room",
        }
        for norm_key, cat in alias.items():
            block = allocations.get(norm_key) or {}
            if not isinstance(block, Mapping):
                continue
            for subtype, attr in _DRILL_ATTR_MAP[cat].items():
                units[attr] = units.get(attr, 0.0) + float(block.get(subtype, 0) or 0)

    general = allocations.get("general")
    if isinstance(general, Mapping):
        for key, attr in _GENERAL_ATTR_MAP.items():
            units[attr] = units.get(attr, 0.0) + float(general.get(key, 0) or 0)
    else:
        for key, attr in _GENERAL_ATTR_MAP.items():
            if key in allocations:
                units[attr] = units.get(attr, 0.0) + float(allocations.get(key, 0) or 0)

    return units


def non_player_raw_points(allocations: Mapping) -> float:
    """Team drills + breaks — cost 1:1 from the week pool (not position-priced)."""
    total = 0.0
    if not allocations:
        return total
    team = allocations.get("team_drills") or {}
    if isinstance(team, Mapping):
        for value in team.values():
            if isinstance(value, Mapping):
                total += sum(float(v or 0) for v in value.values())
            elif isinstance(value, (int, float)):
                total += float(value)
    general = allocations.get("general") or {}
    if isinstance(general, Mapping):
        total += float(general.get("breaks", 0) or 0)
    elif "breaks" in allocations:
        total += float(allocations.get("breaks", 0) or 0)
    # Normalized scrimmages etc.
    for key in ("scrimmages", "breaks"):
        if key in allocations and not isinstance(allocations.get("team_drills"), Mapping):
            val = allocations.get(key)
            if isinstance(val, (int, float)):
                total += float(val)
    return total


def training_points_spent(allocations: Mapping) -> int:
    """Flat budget: every allocation leaf is a whole point count.

    Reject fractional API payloads rather than truncating them or allowing two
    fractional leaves to add up to an apparently valid integer budget.
    """
    def _sum_whole(value) -> int:
        if isinstance(value, Mapping):
            return sum(_sum_whole(child) for child in value.values())
        if value is None:
            return 0
        if isinstance(value, bool):
            raise ValueError("training allocations must be whole numbers from 0 to 5")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("training allocations must be whole numbers from 0 to 5") from exc
        if not number.is_integer() or not 0 <= number <= 5:
            raise ValueError("training allocations must be whole numbers from 0 to 5")
        return int(number)

    return _sum_whole(allocations)


def gain_percentage_matrix() -> Dict[str, Dict[str, float]]:
    return {
        pos: {attr: float(pct) for attr, pct in TRAINING_GAIN_PERCENTAGES[pos].items()}
        for pos in POSITIONS
    }
