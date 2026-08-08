"""Player-development shape constants — cost curve, floors, camp (§10).

Cost is a budget multiplier (not a gain damper). Floors are weight-scaled from
the same TRAINING_COST_WEIGHTS table. Shape-P6 bases are frozen from the
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

# ── Cost curve ──────────────────────────────────────────────────────────────
TRAINING_COST_GAMMA = 1.0
TRAINING_COST_DERIVED_CAP = 3.0
TRAINING_COST_ZERO = 4.0
TRAINING_COST_UNIVERSALS = frozenset({"ND", "FT", "IQ"})

# Explicit physical zeros — "a body like that can't do this."
TRAINING_COST_PHYSICAL_ZEROS: Dict[str, frozenset] = {
    "PG": frozenset({"RB", "ID"}),
    "SG": frozenset({"RB", "ID"}),
    "SF": frozenset(),
    "PF": frozenset(),
    "C": frozenset({"AG"}),
}

CLASS_COST_MULT: Dict[str, float] = {
    "freshman": 1.0,
    "sophomore": 1.1,
    "junior": 1.25,
    "senior": 1.4,
    "Freshman": 1.0,
    "Sophomore": 1.1,
    "Junior": 1.25,
    "Senior": 1.4,
    "FR": 1.0,
    "SO": 1.1,
    "JR": 1.25,
    "SR": 1.4,
}

# Final locked weights (2026-08-07). Universals omitted → cost 1.
TRAINING_COST_WEIGHTS: Dict[str, Dict[str, float]] = {
    "PG": {
        "BH": 0.30, "AG": 0.25, "PS": 0.15, "OD": 0.15, "SH": 0.135,
        "SC": 0.12, "ST": 0.105, "RB": 0.0, "ID": 0.0,
    },
    "SG": {
        "SH": 0.42, "OD": 0.25, "SC": 0.231, "AG": 0.231, "BH": 0.168,
        "PS": 0.168, "ST": 0.147, "RB": 0.0, "ID": 0.0,
    },
    "SF": {
        "OD": 0.20, "SC": 0.18, "SH": 0.14, "AG": 0.1053, "ID": 0.1099,
        "RB": 0.1099, "PS": 0.0772, "BH": 0.0772, "ST": 0.088,
    },
    "PF": {
        "RB": 0.30, "ST": 0.22, "ID": 0.20, "SC": 0.165, "SH": 0.14,
        "AG": 0.1364, "OD": 0.105, "PS": 0.105, "BH": 0.10,
    },
    "C": {
        "ID": 0.32, "RB": 0.32, "ST": 0.2462, "SC": 0.18, "SH": 0.128,
        "OD": 0.128, "BH": 0.1067, "PS": 0.1067, "AG": 0.0,
    },
}

# ── Floors (weight-scaled shape-P6) ─────────────────────────────────────────
FLOOR_REL_HIGH = 0.50
FLOOR_REL_LOW = 0.20

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
CAMP_WEEKS = 3
CAMP_GAIN_SCALE = 1.4
CAMP_POINT_BUDGET = 30
IN_SEASON_POINT_BUDGET = 24


def is_camp_week(week: int) -> bool:
    try:
        w = int(week)
    except (TypeError, ValueError):
        return False
    return 1 <= w <= CAMP_WEEKS


def class_cost_multiplier(year: Optional[str]) -> float:
    if not year:
        return 1.0
    return CLASS_COST_MULT.get(str(year).strip(), CLASS_COST_MULT.get(str(year).strip().lower(), 1.0))


def training_attr_cost(position: str, attr: str) -> float:
    """Unit cost for one allocation point on ``attr`` at ``position``."""
    if attr in TRAINING_COST_UNIVERSALS:
        return 1.0
    pos = position if position in TRAINING_COST_WEIGHTS else "SF"
    if attr in TRAINING_COST_PHYSICAL_ZEROS.get(pos, ()):
        return TRAINING_COST_ZERO
    weights = TRAINING_COST_WEIGHTS[pos]
    if attr not in weights:
        return 1.0
    wa = float(weights[attr])
    if wa <= 0:
        return TRAINING_COST_ZERO
    wmax = max(v for v in weights.values() if v > 0)
    raw = (wmax / wa) ** TRAINING_COST_GAMMA
    return round(min(TRAINING_COST_DERIVED_CAP, raw), 2)


def allocation_budget_cost(
    units_by_attr: Mapping[str, float],
    position: str,
    year: Optional[str] = None,
) -> float:
    """Σ units × attr_cost × class_mult."""
    mult = class_cost_multiplier(year)
    total = 0.0
    for attr, units in units_by_attr.items():
        if not units:
            continue
        total += float(units) * training_attr_cost(position, attr) * mult
    return total


def _cost_rel(position: str, attr: str) -> float:
    if attr in TRAINING_COST_UNIVERSALS:
        return 1.0
    pos = position if position in TRAINING_COST_WEIGHTS else "SF"
    weights = TRAINING_COST_WEIGHTS[pos]
    if attr not in weights:
        return 0.0
    wa = float(weights[attr])
    if wa <= 0:
        return 0.0
    positives = [v for v in weights.values() if v > 0]
    if not positives:
        return 0.0
    return wa / max(positives)


def floor_mult(position: str, attr: str) -> float:
    rel = _cost_rel(position, attr)
    if attr in TRAINING_COST_UNIVERSALS or rel >= FLOOR_REL_HIGH:
        return 1.0
    if rel <= FLOOR_REL_LOW:
        return 0.0
    return (rel - FLOOR_REL_LOW) / (FLOOR_REL_HIGH - FLOOR_REL_LOW)


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


def _attr_int(attrs: Mapping[str, float] | None, key: str) -> int:
    if not attrs:
        return 0
    have = attrs.get(key)
    if have is None:
        have = attrs.get(f"anchor_{key}", 0)
    return int(have or 0)


def authored_core12_changes(
    final_attrs: Mapping[str, float],
    inherited_attrs: Mapping[str, float] | None,
) -> set[str]:
    """Core-12 keys whose final value differs from the inherited clone."""
    if inherited_attrs is None:
        return set(CORE_12)
    return {
        a
        for a in CORE_12
        if _attr_int(final_attrs, a) != _attr_int(inherited_attrs, a)
    }


def authored_floor_violations(
    position: str,
    final_attrs: Mapping[str, float],
    inherited_attrs: Mapping[str, float] | None,
) -> list[Tuple[str, int, int]]:
    """Floor check scoped to authored attribute changes (Team Builder §4.5b).

    Unedited attributes are legal by definition — they already play in the league.
    Pathology still fails: starving a player means editing those attrs down.
    """
    viols = floor_violations(position, final_attrs)
    if not viols:
        return []
    changed = authored_core12_changes(final_attrs, inherited_attrs)
    if not changed:
        return []
    return [(a, have, need) for a, have, need in viols if a in changed]


def apply_floor_clamp_to_anchors(player: dict, position: Optional[str] = None) -> None:
    """Raise any core-12 anchor (and live) that decayed below the floor. No other writes.

    Needs are recomputed after each raise because ``need`` depends on mean(core-12);
    a single pass can leave a 1pt shortfall when raising one attr lifts the mean.
    """
    attrs = player.get("attributes") or {}
    pos = position or player.get("training_position") or player.get("position_intent")
    if not pos:
        ratings = player.get("position_ratings") or {}
        if ratings:
            pos = max(ratings, key=ratings.get)
    pos = pos or "SF"
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
    if pos in TRAINING_COST_WEIGHTS:
        return pos
    ratings = player.get("position_ratings") or {}
    if ratings:
        best = max(ratings, key=ratings.get)
        if best in TRAINING_COST_WEIGHTS:
            return best
    return "SF"


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


def player_week_spend(
    allocations: Mapping,
    position: str,
    year: Optional[str] = None,
) -> float:
    """Position-priced player units + flat team/breaks share."""
    return allocation_budget_cost(
        units_by_attr_from_allocations(allocations), position, year
    ) + non_player_raw_points(allocations)


def cost_matrix() -> Dict[str, Dict[str, float]]:
    return {pos: {a: training_attr_cost(pos, a) for a in CORE_12} for pos in POSITIONS}
