"""
CPU Team Identity — signals, vision selection, and the slider draw.

Thin slice: SLIDERS ONLY. Playbook composition, training allocation and the five-week
re-evaluation are designed but deliberately not built — see
_documentation_master/projects/cpu_team_identity_spec.md.

A team holds a VISION PAIR (one offensive, one defensive). The roster determines which
visions are PLAUSIBLE via eight signals computed from the projected starting five; a softmax
over the surviving pairs picks one. The vision then drives the team's strategy sliders.

EVERYTHING HERE IS FROZEN. The scale constants, the regression coefficients and the fuel
capacity boundaries were calibrated once against 128 measured teams and are NOT recomputed
per league. That is deliberate: a league that trains up should DRIFT against the fixed scale
— that drift is how macro trends become visible. Live z-scores would renormalise the trend
away and make a mid-range programme read as mid-range forever.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

from BackEnd.utils.sim_random import sim_rng as random

POSITIONS = ("PG", "SG", "SF", "PF", "C")

# ── FROZEN SCALE CONSTANTS (mean, sd) ────────────────────────────────────────────────────
# Calibrated against the 128-team measured pool. See spec § Frozen scale constants.
# multiple_signal's constants are DOWNSTREAM of athleticism and intelligence — changing
# either forces re-derivation of multiple_signal's.
SIGNAL_SCALE: Dict[str, tuple] = {
    "fuel":            (33.1641, 4.9118),
    "athleticism":     (84.0266, 10.6469),
    "intelligence":    (29.0469, 4.8520),
    "tempo_tilt":      (-7.1016, 35.6489),
    "scoring_tilt":    (9.0547, 37.0003),
    "inside_peak":     (99.1000, 16.4100),
    "attack_peak":     (193.8289, 20.8603),
    "breadth":         (-0.3085, 0.0427),
    "multiple_signal": (-0.5232, 0.8253),
}

# ── FROZEN RESIDUALISATION COEFFICIENTS ──────────────────────────────────────────────────
# The spec says these signals are "residualized on starter_strength (OLS residual)". At
# runtime we hold ONE team, so the regression cannot be refit — the slope and the predictor
# mean must be frozen too, or a single team would residualise against itself and get zero.
#
#     residual = raw - SLOPE * (predictor - PREDICTOR_MEAN)
#
# (equivalent to the re-centred OLS residual used in calibration, since
#  intercept = mean_y - slope * mean_x cancels).
STARTER_STRENGTH_MEAN = 322.523438
RESIDUAL_SLOPE_VS_STRENGTH: Dict[str, float] = {
    "fuel":         0.10370608,
    "athleticism":  0.24787102,
    "intelligence": 0.07484766,
    "inside_peak":  0.40653478,
    "attack_peak":  0.73765782,
}
# Orthogonalisations (same form; predictor is another signal, not team strength).
INSIDE_PEAK_MEAN = 99.100000
ATTACK_ON_INSIDE_SLOPE = 1.23445389      # attack_peak orthogonalised on inside_peak
TEMPO_TILT_MEAN = -7.101562
SCORING_ON_TEMPO_SLOPE = 0.76073939      # scoring_tilt orthogonalised on tempo_tilt

# ── VISION WEIGHTS ───────────────────────────────────────────────────────────────────────
OFFENSIVE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "Run and Gun": {"fuel": 2.0, "tempo_tilt": -1.0, "breadth": 0.5},
    "Spread":      {"scoring_tilt": 2.0, "inside_peak": -0.5, "breadth": 1.5},
    "Inside-Out":  {"scoring_tilt": -1.0, "inside_peak": 2.0, "breadth": -1.0},
    "Attack":      {"fuel": 0.5, "tempo_tilt": -0.5, "attack_peak": 2.0, "breadth": 0.5},
}
DEFENSIVE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "Full-Court Press": {"fuel": 2.0, "athleticism": 1.5, "tempo_tilt": 1.0},
    "Man Lockdown":     {"fuel": 0.5, "athleticism": 2.0},
    "Zone":             {"fuel": -0.5, "intelligence": 2.0},
    "Multiple":         {"multiple_signal": 2.0},
}
MOTION_FLAT = 0.60          # flat score for the Motion offensive vision
CONTAIN_FLAT = -0.50        # flat score for the Contain defensive vision

OFFENSIVE_VISIONS = tuple(OFFENSIVE_WEIGHTS) + ("Motion",)
DEFENSIVE_VISIONS = tuple(DEFENSIVE_WEIGHTS) + ("Contain",)

# ── FUEL BUDGET ──────────────────────────────────────────────────────────────────────────
VISION_COST: Dict[str, int] = {
    "Run and Gun": 2, "Attack": 1, "Motion": 1, "Spread": 0, "Inside-Out": 0,
    "Full-Court Press": 2, "Man Lockdown": 1, "Multiple": 1, "Zone": 0, "Contain": 0,
}
# FROZEN capacity boundaries — terciles of the measured residualised fuel distribution
# (min ND, residualised: mean 33.1641, sd 4.9118). NOT recomputed per league, so a league
# that trains up genuinely gains capacity rather than being renormalised back to thirds.
#
# NOTE: an earlier draft quoted 221/236 for these. Those belong to the §5 TEMPO-GATE fuel
# (SUM of ND across the five, mean 228.9) — a different signal. Using them here would put
# every team in the top band.
FUEL_CAPACITY_BOUNDS = (30.3209, 35.7506)   # < low | mid | >= high
FUEL_CAPACITY = {"low": 1, "mid": 2, "high": 4}

SOFTMAX_TEMPERATURE = 0.5

# ── SLIDER DRAW TABLES ───────────────────────────────────────────────────────────────────
# Weights over slider values [0,1,2,3,4]. A vision names only the sliders it cares about.
#
# ANY SLIDER A VISION DOES NOT NAME DRAWS FROM ITS OWN LEAGUE BASELINE, never a generic
# neutral. hc_trap/fc_press sit at [34,40,20,5,1] (mean 0.99); handing them a generic 2.0
# would roughly DOUBLE league-wide pressing as a side effect of wiring identity.
LEAGUE_BASELINE: Dict[str, List[int]] = {
    "offense":      [5, 15, 60, 15, 5],
    "inside":       [0, 25, 25, 25, 25],     # legacy: uniform randint(1,4), never 0
    "attack":       [0, 25, 25, 25, 25],
    "outside":      [0, 25, 25, 25, 25],
    "fast_breaks":  [5, 15, 60, 15, 5],
    "play_calling": [5, 15, 60, 15, 5],
    "defense":      [5, 15, 60, 15, 5],
    "aggression":   [10, 20, 40, 20, 10],
    "hc_trap":      [34, 40, 20, 5, 1],
    "fc_press":     [34, 40, 20, 5, 1],
    "rebounding":   [5, 10, 15, 30, 40],
    "tempo":        [10, 20, 50, 20, 10],
    "alterations":  [10, 20, 50, 20, 10],
}

# `offense` is motion(0) <-> set-play(4): 0 = 100% motion, 4 = 100% set plays.
OFFENSIVE_SLIDERS: Dict[str, Dict[str, List[int]]] = {
    "Run and Gun": {"offense": [20, 55, 25, 0, 0], "tempo": [0, 0, 20, 60, 20],
                    "fast_breaks": [0, 5, 20, 55, 20], "inside": [0, 20, 55, 25, 0],
                    "attack": [0, 5, 30, 50, 15], "outside": [0, 15, 50, 30, 5]},
    "Spread":      {"offense": [15, 50, 30, 5, 0], "outside": [0, 0, 15, 55, 30],
                    "inside": [10, 55, 30, 5, 0], "attack": [0, 30, 55, 15, 0]},
    "Inside-Out":  {"offense": [0, 5, 30, 50, 15], "inside": [0, 0, 15, 55, 30],
                    "outside": [5, 45, 45, 5, 0], "attack": [0, 30, 55, 15, 0],
                    "tempo": [10, 40, 45, 5, 0]},
    "Attack":      {"offense": [5, 30, 50, 15, 0], "attack": [0, 0, 15, 55, 30],
                    "inside": [0, 25, 55, 20, 0], "outside": [5, 40, 45, 10, 0],
                    "alterations": [0, 10, 40, 45, 5]},
    "Motion":      {"offense": [10, 40, 45, 5, 0], "inside": [0, 15, 50, 30, 5],
                    "attack": [0, 15, 50, 30, 5], "outside": [0, 15, 50, 30, 5]},
}
# `defense` is man(0) <-> zone(4).
DEFENSIVE_SLIDERS: Dict[str, Dict[str, List[int]]] = {
    "Full-Court Press": {"fc_press": [0, 5, 15, 60, 20], "hc_trap": [0, 10, 30, 50, 10],
                         "aggression": [0, 0, 20, 55, 25]},
    "Man Lockdown":     {"defense": [55, 40, 5, 0, 0], "aggression": [0, 10, 50, 35, 5]},
    "Zone":             {"defense": [0, 0, 20, 55, 25], "aggression": [10, 45, 40, 5, 0]},
    # Multiple's WIDTH is its identity (a team that plays both man and zone), so this is the
    # one deliberately wide vector. Do not narrow it for consistency.
    "Multiple":         {"defense": [5, 25, 40, 25, 5], "aggression": [0, 15, 50, 30, 5]},
    "Contain":          {"defense": [10, 30, 45, 15, 0], "aggression": [30, 50, 20, 0, 0],
                         "hc_trap": [55, 40, 5, 0, 0], "fc_press": [55, 40, 5, 0, 0]},
}


# ── signal computation ───────────────────────────────────────────────────────────────────
def _attr(player, key: str) -> float:
    """Mirrors the Scouting Report / strategy basis: prefer anchor_<attr>, fall back to raw."""
    attrs = getattr(player, "attributes", {}) or {}
    try:
        return float(attrs.get(f"anchor_{key}", attrs.get(key, 0)) or 0)
    except (TypeError, ValueError):
        return 0.0


def _slot_rating(player, pos: str) -> float:
    pr = getattr(player, "position_ratings", None) or {}
    try:
        v = pr.get(pos)
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def projected_starting_five(players: Sequence) -> List:
    """Greedy best (player, open position) by position_ratings — the same projected five the
    Scouting Report and the CPU strategy basis use."""
    assigned, filled, chosen = set(), set(), []
    pool = [p for p in players if p is not None]
    while len(filled) < 5:
        best = None
        for p in pool:
            pid = str(getattr(p, "player_id", "") or "")
            if not pid or pid in assigned:
                continue
            for pos in POSITIONS:
                if pos in filled:
                    continue
                rt = _slot_rating(p, pos)
                if best is None or rt > best[0]:
                    best = (rt, p, pos)
        if best is None:
            break
        _, bp, bpos = best
        chosen.append(bp)
        filled.add(bpos)
        assigned.add(str(getattr(bp, "player_id", "") or ""))
    return chosen


def _p20(values: List[float]) -> float:
    s = sorted(values)
    if not s:
        return 0.0
    i = 0.2 * (len(s) - 1)
    lo = int(i)
    return s[lo] + (i - lo) * (s[min(lo + 1, len(s) - 1)] - s[lo])


def _peak(values: List[float]) -> float:
    """best + 0.3 x second — peak-with-diminishing-second. Peak beats a cumulative sum on
    both spread and confound; see the roster-signal measurement."""
    s = sorted(values, reverse=True)
    if not s:
        return 0.0
    return s[0] + 0.3 * (s[1] if len(s) > 1 else 0.0)


def _z(name: str, value: float) -> float:
    mean, sd = SIGNAL_SCALE[name]
    return (value - mean) / sd if sd else 0.0


def compute_team_signals(players: Sequence) -> Optional[Dict[str, float]]:
    """Eight signals + multiple_signal from the projected five, as FROZEN z-scores.

    Returns None when a five cannot be resolved (caller falls back to legacy rolls).
    """
    five = projected_starting_five(players)
    if len(five) < 5:
        return None

    strength = sum(max((_slot_rating(p, q) for q in POSITIONS), default=0.0) for p in five)
    sc = [_attr(p, "SC") for p in five]
    sh = [_attr(p, "SH") for p in five]
    od = [_attr(p, "OD") for p in five]
    ag = [_attr(p, "AG") for p in five]
    st_ = [_attr(p, "ST") for p in five]

    def resid(name: str, raw: float) -> float:
        return raw - RESIDUAL_SLOPE_VS_STRENGTH[name] * (strength - STARTER_STRENGTH_MEAN)

    fuel = resid("fuel", min(_attr(p, "ND") for p in five))
    ath = resid("athleticism", _p20([a + s for a, s in zip(ag, st_)]))
    iq = resid("intelligence", min(_attr(p, "IQ") for p in five))

    tempo_tilt = sum(od) - sum(sc)                       # NOT residualised: the shared AG
    scoring_raw = sum(sh) - sum(sc)                      # term cancels, so it is confound-free
    scoring_tilt = scoring_raw - SCORING_ON_TEMPO_SLOPE * (tempo_tilt - TEMPO_TILT_MEAN)

    # inside_peak is residualised on strength but deliberately NOT orthogonalised on
    # tempo_tilt: doing so changed what the signal MEANS (it became "post scoring relative to
    # how OD-tilted you are") and put the league's 2nd-best post scorer on Run and Gun.
    inside_peak = resid("inside_peak", _peak(sc))
    attack_resid = resid("attack_peak", _peak([s + a for s, a in zip(sc, ag)]))
    attack_peak = attack_resid - ATTACK_ON_INSIDE_SLOPE * (inside_peak - INSIDE_PEAK_MEAN)

    sh_total = sum(sh)
    breadth = -(max(sh) / sh_total) if sh_total > 0 else -SIGNAL_SCALE["breadth"][0]

    z = {
        "fuel": _z("fuel", fuel),
        "athleticism": _z("athleticism", ath),
        "intelligence": _z("intelligence", iq),
        "tempo_tilt": _z("tempo_tilt", tempo_tilt),
        "scoring_tilt": _z("scoring_tilt", scoring_tilt),
        "inside_peak": _z("inside_peak", inside_peak),
        "attack_peak": _z("attack_peak", attack_peak),
        "breadth": _z("breadth", breadth),
    }
    # multiple_signal is min() of two ALREADY-standardised inputs, then standardised itself.
    # Without that second standardisation it sits ~0.5 sd below the sum-based visions and can
    # never win regardless of roster.
    z["multiple_signal"] = _z("multiple_signal", min(z["athleticism"], z["intelligence"]))
    z["_fuel_raw"] = fuel
    z["_starter_strength"] = strength
    return z


# ── vision scoring & selection ───────────────────────────────────────────────────────────
def score_visions(z: Dict[str, float]) -> Dict[str, Dict[str, float]]:
    off = {v: sum(w * z.get(k, 0.0) for k, w in ws.items()) for v, ws in OFFENSIVE_WEIGHTS.items()}
    off["Motion"] = MOTION_FLAT
    dfn = {v: sum(w * z.get(k, 0.0) for k, w in ws.items()) for v, ws in DEFENSIVE_WEIGHTS.items()}
    dfn["Contain"] = CONTAIN_FLAT
    return {"offense": off, "defense": dfn}


def fuel_capacity(z: Dict[str, float]) -> int:
    f = z.get("_fuel_raw", SIGNAL_SCALE["fuel"][0])
    lo, hi = FUEL_CAPACITY_BOUNDS
    if f < lo:
        return FUEL_CAPACITY["low"]
    if f < hi:
        return FUEL_CAPACITY["mid"]
    return FUEL_CAPACITY["high"]


def select_vision_pair(z: Dict[str, float], rng=None) -> tuple:
    """Score all ten, discard pairs the fuel budget cannot afford, softmax the survivors."""
    rng = rng or random
    scores = score_visions(z)
    cap = fuel_capacity(z)
    pairs = [(o, d, scores["offense"][o] + scores["defense"][d])
             for o in OFFENSIVE_VISIONS for d in DEFENSIVE_VISIONS
             if VISION_COST[o] + VISION_COST[d] <= cap]
    if not pairs:                       # cannot happen at cap >= 1, but never field nothing
        pairs = [(o, d, scores["offense"][o] + scores["defense"][d])
                 for o in OFFENSIVE_VISIONS for d in DEFENSIVE_VISIONS]
    top = max(p[2] for p in pairs)
    weights = [math.exp((p[2] - top) / SOFTMAX_TEMPERATURE) for p in pairs]
    total = sum(weights) or 1.0
    roll = rng.random() * total
    acc = 0.0
    for p, w in zip(pairs, weights):
        acc += w
        if roll <= acc:
            return p[0], p[1]
    return pairs[-1][0], pairs[-1][1]


# ── slider draw ──────────────────────────────────────────────────────────────────────────
def draw_strategy_settings(offensive_vision: str, defensive_vision: str, rng=None) -> Dict[str, int]:
    """Draw all sliders from the vision's tables, falling back PER SLIDER to that slider's own
    league baseline. Drawn once per team per season, not per game."""
    rng = rng or random
    tables = dict(OFFENSIVE_SLIDERS.get(offensive_vision, {}))
    for k, v in DEFENSIVE_SLIDERS.get(defensive_vision, {}).items():
        tables[k] = v                    # defensive vision wins any overlap (none at present)
    out: Dict[str, int] = {}
    for slider, baseline in LEAGUE_BASELINE.items():
        weights = tables.get(slider, baseline)
        out[slider] = rng.choices([0, 1, 2, 3, 4], weights=weights, k=1)[0]
    return out


def assign_identity(players: Sequence, rng=None) -> Optional[Dict]:
    """Full pipeline: signals -> visions -> pair -> sliders. None when no five resolves."""
    z = compute_team_signals(players)
    if z is None:
        return None
    off, dfn = select_vision_pair(z, rng=rng)
    return {
        "offensive_vision": off,
        "defensive_vision": dfn,
        "strategy_settings": draw_strategy_settings(off, dfn, rng=rng),
        "signals": {k: round(v, 4) for k, v in z.items() if not k.startswith("_")},
        "fuel_capacity": fuel_capacity(z),
    }
