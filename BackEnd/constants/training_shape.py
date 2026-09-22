"""Player-development shape constants — gain percentages, floors, camp (§10).

Position fit and class are stored directly as gain percentages. Shape-P6 bases are frozen from the
pre-development t0 league export (seed 202608061); never re-derive from a
developed snapshot.
"""
from __future__ import annotations

import math
import random
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



# ── Development Focus (GOB_DEVELOPMENT_FOCUS_PLAN.md) ────────────────────────
# A per-player training profile selected by POSITION + FOCUS. The focus redistributes the
# same cumulative budget as the position profile — every profile totals 808 and FT/IQ/ND stay
# at 100 — so a focus changes WHERE a trained point lands, never how much development the
# roster receives in aggregate.
#
# `standard` is NOT authored here: it is the live position table above, aliased in below, so
# the two can never drift and a standard-focus player trains exactly as he did before this
# feature existed.
#
# Focus profiles may break the TRAINING_PHYSICAL_WALLS quarter-value floors ON PURPOSE
# (Rebounding lifts PG/SG rebounding from 25 to 75). That is the coach converting a player,
# and it is why the locked wall/ordering invariants stay strict for `standard` and carry a
# separate, looser rule for focus profiles (tests/test_training_shape_framework.py).
TRAINING_FOCUSES: Tuple[str, ...] = (
    "standard", "offensive", "defensive", "athletic", "fundamentals", "rebounding",
)
DEFAULT_TRAINING_FOCUS = "standard"

_FOCUS_OVERRIDES: Dict[str, Dict[str, Dict[str, float]]] = {
    "PG": {
        "offensive": {"SC": 75, "SH": 80, "PS": 70, "BH": 85, "ID": 25, "OD": 60, "RB": 25, "ST": 25, "AG": 63, "FT": 100, "IQ": 100, "ND": 100},
        "defensive": {"SC": 30, "SH": 35, "PS": 75, "BH": 90, "ID": 55, "OD": 100, "RB": 25, "ST": 25, "AG": 73, "FT": 100, "IQ": 100, "ND": 100},
        "athletic": {"SC": 35, "SH": 40, "PS": 68, "BH": 85, "ID": 25, "OD": 60, "RB": 25, "ST": 70, "AG": 100, "FT": 100, "IQ": 100, "ND": 100},
        "fundamentals": {"SC": 35, "SH": 45, "PS": 100, "BH": 100, "ID": 25, "OD": 70, "RB": 25, "ST": 35, "AG": 73, "FT": 100, "IQ": 100, "ND": 100},
        "rebounding": {"SC": 30, "SH": 35, "PS": 70, "BH": 85, "ID": 25, "OD": 55, "RB": 75, "ST": 70, "AG": 63, "FT": 100, "IQ": 100, "ND": 100},
    },
    "SG": {
        "offensive": {"SC": 85, "SH": 100, "PS": 62, "BH": 63, "ID": 25, "OD": 55, "RB": 25, "ST": 30, "AG": 63, "FT": 100, "IQ": 100, "ND": 100},
        "defensive": {"SC": 45, "SH": 90, "PS": 60, "BH": 60, "ID": 55, "OD": 90, "RB": 25, "ST": 25, "AG": 58, "FT": 100, "IQ": 100, "ND": 100},
        "athletic": {"SC": 40, "SH": 85, "PS": 58, "BH": 55, "ID": 25, "OD": 50, "RB": 25, "ST": 70, "AG": 100, "FT": 100, "IQ": 100, "ND": 100},
        "fundamentals": {"SC": 45, "SH": 85, "PS": 100, "BH": 100, "ID": 25, "OD": 50, "RB": 25, "ST": 25, "AG": 53, "FT": 100, "IQ": 100, "ND": 100},
        "rebounding": {"SC": 45, "SH": 85, "PS": 55, "BH": 55, "ID": 25, "OD": 50, "RB": 75, "ST": 70, "AG": 48, "FT": 100, "IQ": 100, "ND": 100},
    },
    "SF": {
        "offensive": {"SC": 100, "SH": 90, "PS": 34, "BH": 34, "ID": 45, "OD": 81, "RB": 45, "ST": 35, "AG": 44, "FT": 100, "IQ": 100, "ND": 100},
        "defensive": {"SC": 72, "SH": 54, "PS": 34, "BH": 34, "ID": 80, "OD": 100, "RB": 50, "ST": 35, "AG": 49, "FT": 100, "IQ": 100, "ND": 100},
        "athletic": {"SC": 65, "SH": 49, "PS": 29, "BH": 34, "ID": 45, "OD": 81, "RB": 40, "ST": 75, "AG": 90, "FT": 100, "IQ": 100, "ND": 100},
        "fundamentals": {"SC": 72, "SH": 54, "PS": 75, "BH": 75, "ID": 40, "OD": 81, "RB": 40, "ST": 30, "AG": 41, "FT": 100, "IQ": 100, "ND": 100},
        "rebounding": {"SC": 67, "SH": 49, "PS": 34, "BH": 34, "ID": 45, "OD": 81, "RB": 90, "ST": 75, "AG": 33, "FT": 100, "IQ": 100, "ND": 100},
    },
    "PF": {
        "offensive": {"SC": 85, "SH": 77, "PS": 30, "BH": 25, "ID": 57, "OD": 30, "RB": 90, "ST": 89, "AG": 25, "FT": 100, "IQ": 100, "ND": 100},
        "defensive": {"SC": 45, "SH": 37, "PS": 30, "BH": 25, "ID": 97, "OD": 65, "RB": 90, "ST": 89, "AG": 30, "FT": 100, "IQ": 100, "ND": 100},
        "athletic": {"SC": 45, "SH": 37, "PS": 30, "BH": 25, "ID": 62, "OD": 30, "RB": 94, "ST": 100, "AG": 85, "FT": 100, "IQ": 100, "ND": 100},
        "fundamentals": {"SC": 45, "SH": 37, "PS": 75, "BH": 65, "ID": 57, "OD": 25, "RB": 90, "ST": 89, "AG": 25, "FT": 100, "IQ": 100, "ND": 100},
        "rebounding": {"SC": 54, "SH": 47, "PS": 35, "BH": 25, "ID": 67, "OD": 35, "RB": 100, "ST": 100, "AG": 45, "FT": 100, "IQ": 100, "ND": 100},
    },
    "C": {
        "offensive": {"SC": 95, "SH": 70, "PS": 25, "BH": 25, "ID": 100, "OD": 25, "RB": 83, "ST": 60, "AG": 25, "FT": 100, "IQ": 100, "ND": 100},
        "defensive": {"SC": 58, "SH": 30, "PS": 28, "BH": 25, "ID": 100, "OD": 80, "RB": 95, "ST": 67, "AG": 25, "FT": 100, "IQ": 100, "ND": 100},
        "athletic": {"SC": 50, "SH": 25, "PS": 25, "BH": 25, "ID": 100, "OD": 28, "RB": 90, "ST": 100, "AG": 65, "FT": 100, "IQ": 100, "ND": 100},
        "fundamentals": {"SC": 48, "SH": 25, "PS": 75, "BH": 65, "ID": 100, "OD": 25, "RB": 80, "ST": 65, "AG": 25, "FT": 100, "IQ": 100, "ND": 100},
        "rebounding": {"SC": 58, "SH": 35, "PS": 28, "BH": 25, "ID": 100, "OD": 37, "RB": 100, "ST": 100, "AG": 25, "FT": 100, "IQ": 100, "ND": 100},
    },
}

TRAINING_FOCUS_PERCENTAGES: Dict[str, Dict[str, Dict[str, float]]] = {
    pos: {"standard": dict(TRAINING_GAIN_PERCENTAGES[pos]), **_FOCUS_OVERRIDES[pos]}
    for pos in TRAINING_GAIN_PERCENTAGES
}


def derive_training_position(doc: Mapping) -> Optional[str]:
    """The training position a NEW or UNMIGRATED player doc should be given, or None.

    ``position_intent`` (the natural fit drawn at generation) wins; otherwise the highest
    ``position_ratings`` entry. Ties are broken deterministically from the document id, so
    the same doc always resolves the same way — that is what lets the backfill's dry run
    predict its own writes, and what keeps the backfill and the runtime creation paths in
    agreement instead of drifting into two rules.

    Returns None when there is neither an intent nor a usable rating. Callers must NOT
    substitute a position in that case (rule 26): an unknown position stays unknown, and
    ``resolve_training_position`` applies its own read-time fallback.
    """
    intent = doc.get("position_intent")
    if isinstance(intent, str) and intent.strip() in POSITIONS:
        return intent.strip()

    ratings = doc.get("position_ratings")
    if isinstance(ratings, Mapping) and ratings:
        usable = {p: v for p, v in ratings.items() if p in POSITIONS and isinstance(v, (int, float))}
        if usable:
            best = max(usable.values())
            tied = sorted(p for p, v in usable.items() if v == best)
            if len(tied) == 1:
                return tied[0]
            key = doc.get("_id") or doc.get("player_id") or ""
            return random.Random(f"development-focus:{key}").choice(tied)
    return None


def resolve_training_focus(player: Mapping) -> str:
    """The player's Development Focus, or ``standard``.

    Legacy docs carry no ``training_focus``; an unknown or malformed value resolves to
    ``standard`` rather than raising, because a bad stored string must never stop a week of
    training from resolving. API writes validate against ``TRAINING_FOCUSES`` at the edge
    (see the FPD write path) so junk cannot be stored in the first place.
    """
    raw = player.get("training_focus")
    if raw is None and isinstance(player.get("meta"), Mapping):
        raw = player["meta"].get("training_focus")
    focus = str(raw or "").strip().lower()
    return focus if focus in TRAINING_FOCUSES else DEFAULT_TRAINING_FOCUS

def training_attr_gain_multiplier(position: str, attr: str, focus: Optional[str] = None) -> float:
    """Fraction of raw gain retained for one position + Development Focus.

    ``focus=None`` resolves to ``standard``, which IS the position-only table — so every
    pre-Development-Focus caller keeps its exact behaviour.
    """
    pos = position if position in TRAINING_FOCUS_PERCENTAGES else "SF"
    foc = focus or DEFAULT_TRAINING_FOCUS
    if foc not in TRAINING_FOCUSES:
        foc = DEFAULT_TRAINING_FOCUS
    return float(TRAINING_FOCUS_PERCENTAGES[pos][foc].get(attr, 100) / 100)


def player_attr_gain_multiplier(player: Mapping, attr: str) -> float:
    """Combined profile (position + focus) and class-year multiplier for one player's gain.

    This is the ONLY multiplier applied for profile fit: the position + focus profile
    REPLACES the old position-only lookup, it does not stack with it.
    """
    position = resolve_training_position(player)
    focus = resolve_training_focus(player)
    year = player.get("year") or ((player.get("meta") or {}).get("year"))
    return training_attr_gain_multiplier(position, attr, focus) * class_gain_multiplier(year)


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
    # Each candidate is tested in turn rather than `a or b`: an invalid stored
    # training_position used to swallow the fallback chain, so a doc carrying junk in that
    # field skipped its own position_intent and landed on the SF default. Precedence is
    # unchanged for valid data — coach's choice, then natural fit, then best rating.
    for pos in (player.get("training_position"), player.get("position_intent")):
        if pos in TRAINING_GAIN_PERCENTAGES:
            return pos
    ratings = player.get("position_ratings") or {}
    if ratings:
        best = max(ratings, key=ratings.get)
        if best in TRAINING_GAIN_PERCENTAGES:
            return best
    return "SF"


def training_position_projection(player: Mapping) -> dict[str, Optional[str]]:
    """Fields every training-player producer must carry into execution/UI.

    Development Focus rides here for the same reason the position does: the builders that
    assemble training-player dicts (user training, CPU autotrain, the report) cherry-pick
    fields, so a field that is not in this projection is simply absent by the time
    execution reads it — and ``resolve_training_focus`` would then silently see every
    player as ``standard``. Declaring it once means both builders get it.
    """
    return {
        "training_position": player.get("training_position"),
        "position_intent": player.get("position_intent"),
        "resolved_training_position": resolve_training_position(player),
        "training_focus": player.get("training_focus"),
        "resolved_training_focus": resolve_training_focus(player),
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
