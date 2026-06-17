"""
Dynamic HCT (Half Court Trap) turn resolution.

Spec: ``_documentation_master/projects/Dynamic_HCT_Turns.md``.
Build plan: ``_documentation_master/projects/Dynamic_HCT_Cut2_Plan.md``.

Cut 2 / Phase 2A scope — the §4 loop spine:
  - Setup (segment 0): entry walk-up. BH advances from BIP receive coords to
    ``(44, target_y)`` (``target_y`` random in [21, 29]); the 9 others move
    toward their targets. Built by the emitter via the universal walk-up step.
  - Internal loop (variable-length): the engine returns ``loop_segments`` —
    a converge segment (defensive PG slides onto the BH) followed by one
    segment per iteration:
      * Time terminals (shot-clock ≤ 0, or 10-sec while still in backcourt)
        end the possession as a turnover.
      * Zone precedence: BH in the Primary Safe Area (or past it) → HCO.
      * Read (attack / pass / hold). Phase 2A fully resolves **attack** via
        the §5 banded contested formula → DEAD BALL / POS_O / NEUTRAL.
        POS_O and NEUTRAL advance; **pass / hold are placeholder-routed to
        neutral-advance** until Phase 2B/2C.
      * Advance: BH dribbles +rand(6,12) x toward basket, +rand(-6,6) y; the
        PG defender re-poses to stay engaged.
    Every target passes through the universal animation clamp.

The engine returns intermediate data only (targets, per-segment durations,
result type); ``dynamic_hct_step_emitter.build_dynamic_hct_animation_steps``
turns it into the walk-up step + one schema step per segment.

Moment system (pressure vs. trap) and the pass branch landed in Phases 2B–2C.
Phase 2D-1 added the broken-HCT **fast break (D18)**: when the open-floor attack
reaches the topLane spot (perfect-PSA spot behind the BH), the engine emits
``result_type = "FAST_BREAK_SHOT"`` + a ``fb_seed``; the wrapper hands off to
``dynamic_hct_shot.resolve_hct_fast_break_shot`` for a real make/miss rim attempt.
The in-Attack-Basket §7 shot tree, top-level pass, fouls/steals, and remaining
stat parity arrive in Phases 2D-2/2D-3/2F.
"""
from __future__ import annotations

import logging
import math
import random
from typing import Any, Dict, List, Tuple

from BackEnd.constants import (
    STANDARD_GRID_PER_GAME_SEC,
    HCO_STRING_SPOTS,
    HCT_SETUP_POSITIONS,
    RESET_INBOUND_PASS_GRID_PER_GAME_SECOND,
)
from BackEnd.utils.shared import (
    ag_to_grid_per_game_sec,
    calc_ag_segment_seconds,
    calculate_ball_handling_score,
    calculate_defender_pressure_score,
    clamp_animation_grid_coords,
    get_away_player_coords,
)
from BackEnd.utils.shared_defense import HCT_STANDARD_NORMAL, compute_hct_trap_formation


# 10-second violation gate (per Dynamic_HCT_Turns.md "Special Situations").
# When the shot clock reaches this threshold and the ball handler has not yet
# crossed half-court, we announce "10-Second Violation" and run the standard
# dead-ball-turnover flow → SIP. NOT WIRED in first cut; constant defined now
# so the next iteration can plug in the runtime check without churn.
HCT_SHOT_CLOCK_VIOLATION_THRESHOLD = 20

# Step 1 BH target: x = 44, y random in [21, 29].
STEP_1_BH_TARGET_X = 44
STEP_1_BH_TARGET_Y_MIN = 21
STEP_1_BH_TARGET_Y_MAX = 29

# Step 2 defensive PG converge offset: defender x = BH_x + 2 (toward home basket
# in home-defending orientation), same y as BH.
STEP_2_DEFENDER_X_OFFSET = 2

# Step 3 HCO transition target: BH dribbles to deep key spot.
DEEP_KEY_SPOT = HCO_STRING_SPOTS["deep key"]  # (57, 25)

# Defensive PG's step-1 target (override per spec): exact center court spot.
DEFENSIVE_PG_STEP_1_TARGET = HCO_STRING_SPOTS["center court"]  # (50, 25)

# Pos1-4 geometric ranges (home-on-offense orientation; flipped at runtime when
# away is on offense). Each range is (x_min, x_max, y_min, y_max).
POS_TARGET_RANGES = {
    "pos1": (57, 73, 35, 45),  # upper wing region
    "pos2": (57, 73, 5, 15),   # lower wing region
    "pos3": (73, 80, 7, 19),   # lower apex / midPost region
    "pos4": (73, 80, 32, 43),  # upper apex / midPost region
}

# --- Cut 2 / Phase 2A loop parameters (home-on-offense orientation) ---------
POSITIONS = ("PG", "SG", "SF", "PF", "C")

# Primary Safe Area (§2): x 57-64, y 19-32; perfect spot (60, 25). HCO trigger 1.
PSA_X_MIN, PSA_X_MAX = 57, 64
PSA_Y_MIN, PSA_Y_MAX = 19, 32
PSA_PERFECT_SPOT = {"x": 60, "y": 25}

# §5 broken-HCT topLane spot: the open-floor attack target when the perfect PSA
# spot is *behind* the ball handler. Reaching it triggers the fast break (D18).
TOPLANE_SPOT = HCO_STRING_SPOTS["topLane"]  # (74, 25)

# §4 read thresholds (attack / pass; else hold).
READ_ATTACK_THRESHOLD = 200
READ_PASS_THRESHOLD = 120

# §5 broken-HCT (no defender in range) reduced read thresholds.
BROKEN_READ_ATTACK_THRESHOLD = 175
BROKEN_READ_PASS_THRESHOLD = 110

# §4 neutral-advance: BH moves +rand(ADV_X) toward basket, +rand(ADV_Y) in y.
ADVANCE_X_MIN, ADVANCE_X_MAX = 6, 12
ADVANCE_Y_MIN, ADVANCE_Y_MAX = -6, 6

# §5 moment detection: a defender is "in range" within this euclidean distance.
MOMENT_RANGE = 11

# §6 shift triggers (on ball-handler y): y < 20 → lower; y > 30 → upper; else normal.
SHIFT_LOWER_Y = 20
SHIFT_UPPER_Y = 30

# §5 hold resolution: BH holds the ball for random(1, 3) game seconds.
HOLD_SECONDS_MIN, HOLD_SECONDS_MAX = 1, 3

# §6 pass flight speed (grid spots / game-second). Reuses the universal pass
# primitive's reset-inbound rate so HCT pass timing matches other pass steps.
PASS_GRID_PER_GAME_SEC = float(RESET_INBOUND_PASS_GRID_PER_GAME_SECOND)

# Defensive backstop only — the shot-clock terminal is the real loop bound.
MAX_LOOP_ITERATIONS = 15


def _flip(coords: Dict[str, Any]) -> Dict[str, Any]:
    """Flip a coord dict around x=50 (no-op for y)."""
    return get_away_player_coords({"x": int(coords["x"]), "y": int(coords["y"])})


def _zone_centroid(spot_names: List[str]) -> Dict[str, int]:
    """Average (x, y) for a list of HCO spot names."""
    xs = []
    ys = []
    for name in spot_names:
        spot = HCO_STRING_SPOTS.get(name)
        if not spot:
            continue
        xs.append(spot["x"])
        ys.append(spot["y"])
    if not xs:
        return {"x": 50, "y": 25}
    return {"x": int(round(sum(xs) / len(xs))), "y": int(round(sum(ys) / len(ys)))}


def _alias_map(ball_handler_pos: str) -> Dict[str, str]:
    """
    Map ``pos1..pos4`` → actual position keys (PG/SG/SF/PF/C), excluding the BH
    position. Mirrors ``_build_set_play_alias_map`` in playbook_weights_utils.
    """
    order = ["PG", "SG", "SF", "PF", "C"]
    bh = ball_handler_pos.upper()
    remaining = [p for p in order if p != bh]
    return {f"pos{i + 1}": pos for i, pos in enumerate(remaining)}


def _euclid(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    return math.hypot(b["x"] - a["x"], b["y"] - a["y"])


def _interpolate(start: Dict[str, Any], end: Dict[str, Any], progress: float) -> Dict[str, int]:
    """Linear interpolation; ``progress`` clamped to [0, 1]."""
    p = max(0.0, min(1.0, progress))
    return {
        "x": int(round(start["x"] + (end["x"] - start["x"]) * p)),
        "y": int(round(start["y"] + (end["y"] - start["y"]) * p)),
    }


def _move_at_pace(
    start: Dict[str, Any],
    target: Dict[str, Any],
    elapsed_game_sec: float,
    rate_units_per_sec: float,
) -> Dict[str, int]:
    """
    Where is a mover at ``elapsed_game_sec`` game-seconds in, given they walk in
    a straight line from ``start`` toward ``target`` at ``rate_units_per_sec``?
    """
    distance = _euclid(start, target)
    if distance <= 0 or elapsed_game_sec <= 0:
        return {"x": int(start["x"]), "y": int(start["y"])}
    travel = rate_units_per_sec * elapsed_game_sec
    if travel >= distance:
        return {"x": int(target["x"]), "y": int(target["y"])}
    return _interpolate(start, target, travel / distance)


def _pos_target(pos_key: str, is_away_offense: bool) -> Dict[str, int]:
    """
    Random target for a non-BH offensive teammate inside the geometric range
    for ``pos_key`` ("pos1".."pos4"). Flipped when away is on offense.
    """
    x_min, x_max, y_min, y_max = POS_TARGET_RANGES[pos_key]
    target = {
        "x": random.randint(x_min, x_max),
        "y": random.randint(y_min, y_max),
    }
    if is_away_offense:
        return _flip(target)
    return target


def hct_initial_defender_coords(is_away_offense: bool) -> Dict[str, Dict[str, int]]:
    """Defensive alignment at the start of an HCT possession — also the
    coords BIP plants defenders at on a HCT-next inbound. PG sits at center
    court; the other four occupy the centroid of their HCT_STANDARD_NORMAL
    polygon. Stored in home-defending orientation; flipped for away offense.

    Shared by ``setup_baseline_inbound`` (so BIP-end matches HCT step 0
    movement[0]) and ``compute_dynamic_hct_turn`` (so the start of step 1
    no longer reads stale ``player.coords``).
    """
    out: Dict[str, Dict[str, int]] = {}
    for pos in ("PG", "SG", "SF", "PF", "C"):
        if pos == "PG":
            coord = dict(DEFENSIVE_PG_STEP_1_TARGET)
        else:
            coord = _zone_centroid(HCT_STANDARD_NORMAL.get(pos) or [])
        if is_away_offense:
            coord = _flip(coord)
        out[pos] = coord
    return out


def _build_step_1_targets(
    ball_handler_pos: str,
    is_away_offense: bool,
) -> Tuple[Dict[str, Dict[str, int]], Dict[str, Dict[str, int]]]:
    """
    Produce ``(off_targets, def_targets)`` dicts mapping position → target
    coords (in current orientation) for step 1.
    """
    bh = ball_handler_pos.upper()

    # BH target: (44, random y in 21-29).
    bh_target = {
        "x": STEP_1_BH_TARGET_X,
        "y": random.randint(STEP_1_BH_TARGET_Y_MIN, STEP_1_BH_TARGET_Y_MAX),
    }
    if is_away_offense:
        bh_target = _flip(bh_target)

    off_targets: Dict[str, Dict[str, int]] = {bh: bh_target}
    alias = _alias_map(bh)
    for alias_key, real_pos in alias.items():
        off_targets[real_pos] = _pos_target(alias_key, is_away_offense)

    # Defensive targets: PG → exact center court; others → zone-Normal centroid.
    def_targets: Dict[str, Dict[str, int]] = {}
    for pos in ("PG", "SG", "SF", "PF", "C"):
        if pos == "PG":
            target = dict(DEFENSIVE_PG_STEP_1_TARGET)
        else:
            spots = HCT_STANDARD_NORMAL.get(pos) or []
            target = _zone_centroid(spots)
        if is_away_offense:
            target = _flip(target)
        def_targets[pos] = target

    return off_targets, def_targets


def _player_id(player) -> str:
    return getattr(player, "player_id", str(id(player))) if player is not None else ""


def _player_read(player) -> int:
    """Standard player read (§4 The Read): IQ-weighted with a CH minority and a
    1-6 random multiplier."""
    attrs = getattr(player, "attributes", {}) or {}
    return int(((attrs.get("IQ", 0) * 0.8) + (attrs.get("CH", 0) * 0.2)) * random.randint(1, 6))


def _read_decision(player, broken: bool = False) -> str:
    """Map a read score to attack / pass / hold (§4).

    ``broken=True`` applies the §5 reduced thresholds used when no defender is
    in range (an open floor invites attack).
    """
    score = _player_read(player)
    attack_t = BROKEN_READ_ATTACK_THRESHOLD if broken else READ_ATTACK_THRESHOLD
    pass_t = BROKEN_READ_PASS_THRESHOLD if broken else READ_PASS_THRESHOLD
    if score > attack_t:
        return "attack"
    if score > pass_t:
        return "pass"
    return "hold"


def _resolve_moment(
    off_team,
    def_team,
    ball_handler,
    bh_defender,
    trapper=None,
) -> Tuple[str, float]:
    """§5 Pressure / Trap banded outcome.

    Returns ``(outcome, score_ratio)`` where ``outcome`` ∈
    {"DEAD BALL", "POS_O", "NEUTRAL"}; ``score_ratio`` is the 0..1 turnover
    point along the BH's drive path (only meaningful for DEAD BALL).

    Pressure (``trapper is None``): ``d = pressure(bh_defender) + pt_eff*r``.
    Trap (``trapper`` given): ``d = pressure(bh_defender) + 0.5*pressure(trapper)
    + pt_eff*r`` (§5 Trap Moment).
    """
    off_attrs = getattr(off_team, "team_attributes", {}) or {}
    def_attrs = getattr(def_team, "team_attributes", {}) or {}

    pt_eff = float(def_attrs.get("pt_efficiency", 0) or 0)
    pt_opp = float(off_attrs.get("pt_opp_modifier", 0) or 0)
    off_chem = int((off_attrs.get("team_chemistry", 0) or 0) / 4)
    def_chem = int((def_attrs.get("team_chemistry", 0) or 0) / 4)

    d_score = calculate_defender_pressure_score(bh_defender, "man")
    if trapper is not None:
        d_score += 0.5 * calculate_defender_pressure_score(trapper, "man")
    d_score += pt_eff * random.randint(1, 6)

    base_handling = calculate_ball_handling_score(ball_handler)
    # Spec uses ``*``; treat pt_opp == 0 as a no-op multiplier (1) so an unset
    # team attribute doesn't auto-zero the handling score.
    o_score = base_handling * (pt_opp * random.randint(1, 6)) if pt_opp > 0 else base_handling

    if d_score > o_score + 2 * (off_chem + pt_opp):
        return "DEAD BALL", random.uniform(0.2, 0.8)
    if o_score >= d_score + 2 * (def_chem + pt_eff):
        return "POS_O", 1.0
    return "NEUTRAL", 1.0


def _basket_dir(is_away_offense: bool) -> int:
    """Advance direction in x toward the offense's basket (+1 home, -1 away)."""
    return -1 if is_away_offense else 1


def _crossed_half_court(x: float, is_away_offense: bool) -> bool:
    return x <= 50 if is_away_offense else x >= 50


def _in_primary_safe_area(xy: Dict[str, Any], is_away_offense: bool) -> bool:
    x, y = xy["x"], xy["y"]
    if not (PSA_Y_MIN <= y <= PSA_Y_MAX):
        return False
    if is_away_offense:
        return (100 - PSA_X_MAX) <= x <= (100 - PSA_X_MIN)
    return PSA_X_MIN <= x <= PSA_X_MAX


def _past_primary_safe_area(xy: Dict[str, Any], is_away_offense: bool) -> bool:
    """BH advanced beyond the PSA into the deep front court (Attack Basket band
    + §7 are deferred to Phase 2D; 2A resolves this as an HCO entry)."""
    x = xy["x"]
    return x < (100 - PSA_X_MAX) if is_away_offense else x > PSA_X_MAX


def _clamp_xy(xy: Dict[str, Any]) -> Dict[str, int]:
    """Universal animation clamp (§4) for a single target."""
    clamped = clamp_animation_grid_coords({"x": xy["x"], "y": xy["y"]}, result_type="HCT") or xy
    return {"x": int(round(clamped["x"])), "y": int(round(clamped["y"]))}


def _converge_xy(bh_xy: Dict[str, Any], is_away_offense: bool) -> Dict[str, int]:
    """A defender's spot when engaging the BH: between BH and the basket."""
    offset = -STEP_2_DEFENDER_X_OFFSET if is_away_offense else STEP_2_DEFENDER_X_OFFSET
    return _clamp_xy({"x": int(bh_xy["x"] + offset), "y": int(bh_xy["y"])})


def _is_ahead(def_xy: Dict[str, Any], bh_xy: Dict[str, Any], is_away_offense: bool) -> bool:
    """True if the defender's x is closer to the offense's basket than the BH's."""
    return def_xy["x"] < bh_xy["x"] if is_away_offense else def_xy["x"] > bh_xy["x"]


def _in_range_defenders(
    bh_xy: Dict[str, Any], def_coords: Dict[str, Dict[str, int]]
) -> List[str]:
    """Defender positions within ``MOMENT_RANGE`` euclidean spots of the BH,
    sorted nearest-first."""
    in_range = [
        pos for pos in POSITIONS if _euclid(bh_xy, def_coords[pos]) <= MOMENT_RANGE
    ]
    in_range.sort(key=lambda pos: _euclid(bh_xy, def_coords[pos]))
    return in_range


def _detect_moment(
    bh_xy: Dict[str, Any],
    def_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
) -> Tuple[str, List[str]]:
    """§5 continuous distance detection.

    Returns ``(kind, in_range)`` where ``kind`` ∈ {"none", "pressure", "trap"}
    and ``in_range`` is the nearest-first list of in-range defender positions.
    A trap needs ≥2 in range with ≥1 ahead of the BH; pressure needs ≥1 in
    range that is ahead.
    """
    in_range = _in_range_defenders(bh_xy, def_coords)
    ahead = [p for p in in_range if _is_ahead(def_coords[p], bh_xy, is_away_offense)]
    if len(in_range) >= 2 and ahead:
        return "trap", in_range
    if in_range and ahead:
        return "pressure", in_range
    return "none", in_range


def _select_trappers(
    in_range: List[str],
    pg_in_range: bool,
) -> Tuple[str, str]:
    """§5 trapper selection. Returns ``(bh_defender_pos, trapper_pos)``.

    Defensive PG is always a trapper when in range (the second is the closest
    other in-range defender). Fallback when PG is out of range: the two closest
    in-range defenders. ``in_range`` is nearest-first.
    """
    if pg_in_range and "PG" in in_range:
        others = [p for p in in_range if p != "PG"]
        return "PG", others[0]
    return in_range[0], in_range[1]


def _select_pass_receiver(
    bh_pos: str, off_coords: Dict[str, Dict[str, int]]
) -> str:
    """§6 pass: the ball goes to one of the two teammates closest to the BH
    (chosen at random between those two)."""
    others = [p for p in POSITIONS if p != bh_pos]
    others.sort(key=lambda p: _euclid(off_coords[bh_pos], off_coords[p]))
    return random.choice(others[:2])


def _determine_shift(bh_y: float) -> str:
    """§6 shift trigger on ball-handler y."""
    if bh_y < SHIFT_LOWER_Y:
        return "lower"
    if bh_y > SHIFT_UPPER_Y:
        return "upper"
    return "normal"


def _position_defense(
    bh_xy: Dict[str, Any],
    def_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
) -> None:
    """§6 defensive formation around the BH (in place).

    Upper/lower shift → two designated trappers form the standard HC trap
    (reusing ``compute_hct_trap_formation``) plus a center defender; normal
    shift → the defensive PG pressures the BH. Non-engaged defenders hold.
    """
    shift = _determine_shift(bh_xy["y"])
    if shift in ("upper", "lower"):
        trap = compute_hct_trap_formation(bh_xy, shift, is_away_offense=is_away_offense)
        for pos, xy in trap.items():
            def_coords[pos] = _clamp_xy(xy)
        # Center defender (remaining backcourt guard): y=25, x ±4 toward basket.
        backcourt = {"PG", "SG", "SF"}
        center_candidates = [p for p in backcourt if p not in trap]
        if center_candidates:
            center_pos = center_candidates[0]
            cx = bh_xy["x"] + _basket_dir(is_away_offense) * 4
            def_coords[center_pos] = _clamp_xy({"x": int(cx), "y": 25})
    else:
        def_coords["PG"] = _converge_xy(bh_xy, is_away_offense)


def _segment(
    reason: str,
    off_coords: Dict[str, Dict[str, int]],
    def_coords: Dict[str, Dict[str, int]],
    seconds: float,
    gate: Tuple[str, str],
    ball_owner_pos: str = "PG",
) -> Dict[str, Any]:
    """Snapshot a loop segment's per-player end coords + gate.

    ``gate`` is ``(side, pos)`` where side ∈ {"off", "def"} — the player whose
    arrival ends the step. ``ball_owner_pos`` is the offensive position holding
    the ball at the end of the segment (changes after a pass).
    """
    return {
        "reason": reason,
        "off_end": {p: dict(off_coords[p]) for p in POSITIONS},
        "def_end": {p: dict(def_coords[p]) for p in POSITIONS},
        "seconds": round(float(seconds), 2),
        "gate": list(gate),
        "ball_owner_pos": ball_owner_pos,
    }


def _pass_segment(
    passer_pos: str,
    receiver_pos: str,
    off_coords: Dict[str, Dict[str, int]],
    def_coords: Dict[str, Dict[str, int]],
    seconds: float,
) -> Dict[str, Any]:
    """A ball-in-flight segment (§6 pass). Offense holds while the ball travels
    passer → receiver; the defense moves to ``def_coords``. The emitter renders
    this via the universal ``build_pass_step`` primitive (ball flight + SFX).
    Ball ownership transitions to the receiver at the end of the segment.
    """
    seg = _segment(
        "hct_pass", off_coords, def_coords, seconds, ("off", receiver_pos),
        ball_owner_pos=receiver_pos,
    )
    seg["pass_from_pos"] = passer_pos
    seg["pass_to_pos"] = receiver_pos
    return seg


def _emit_dead_ball_drive(
    bh_xy, score_ratio, is_away_offense, bh_drive_rate, off_coords, def_coords, bh_pos
) -> Tuple[Dict[str, Any], float]:
    """BH drives partway toward the deep key, then commits a dead-ball turnover.
    Mutates ``off_coords``/``def_coords`` and returns ``(segment, seconds)``."""
    deep_key = DEEP_KEY_SPOT if not is_away_offense else _flip(DEEP_KEY_SPOT)
    path_distance = _euclid(bh_xy, deep_key)
    partial_elapsed = (path_distance * score_ratio) / bh_drive_rate
    attack_xy = _clamp_xy(_move_at_pace(bh_xy, deep_key, partial_elapsed, bh_drive_rate))
    off_coords[bh_pos] = attack_xy
    _position_defense(attack_xy, def_coords, is_away_offense)
    seconds = max(0.3, partial_elapsed)
    return (
        _segment("hct_attack", off_coords, def_coords, seconds, ("off", bh_pos), bh_pos),
        seconds,
    )


def _psa_is_behind(bh_xy: Dict[str, Any], is_away_offense: bool) -> bool:
    """§5: is the perfect PSA spot *behind* the BH (away from the basket)?

    If so, driving to it would mean retreating — the BH instead attacks the
    topLane spot and we run a fast break (D18). Home basket is +x (PSA behind
    when ``bh_x > 60``); away basket is -x (PSA behind when ``bh_x < 40``).
    """
    psa = PSA_PERFECT_SPOT if not is_away_offense else _flip(PSA_PERFECT_SPOT)
    return bh_xy["x"] < psa["x"] if is_away_offense else bh_xy["x"] > psa["x"]


def _emit_broken_hct_drive(
    bh_xy, is_away_offense, bh_drive_rate, off_coords, def_coords, bh_pos
) -> Tuple[str, Dict[str, Any], float]:
    """Open-floor attack (§5 broken HCT). Returns ``(mode, segment, seconds)``.

    - PSA perfect spot ahead → BH drives to it → ``mode == "HCO"``.
    - PSA perfect spot behind the BH → BH drives to the topLane spot →
      ``mode == "FAST_BREAK"`` (the caller hands off to the D18 fast-break
      shot resolver from the post-drive state).
    """
    if _psa_is_behind(bh_xy, is_away_offense):
        target = _clamp_xy(TOPLANE_SPOT if not is_away_offense else _flip(TOPLANE_SPOT))
        mode = "FAST_BREAK"
    else:
        target = _clamp_xy(PSA_PERFECT_SPOT if not is_away_offense else _flip(PSA_PERFECT_SPOT))
        mode = "HCO"
    seconds = max(0.3, _euclid(bh_xy, target) / bh_drive_rate)
    off_coords[bh_pos] = target
    _position_defense(target, def_coords, is_away_offense)
    return (
        mode,
        _segment("hct_attack", off_coords, def_coords, seconds, ("off", bh_pos), bh_pos),
        seconds,
    )


def compute_dynamic_hct_turn(game) -> Dict[str, Any]:
    """
    Build the dynamic HCT turn for this engine state.

    Returns a dict shaped for ``resolve_half_court_trap_logic`` to merge into
    its existing turn result:
        {
            "animations": [...],          # frontend animation list
            "result_type": "DEAD BALL" | "HCO",
            "ball_handler": Player,
            "defender": Player,
            "time_elapsed": float,        # game-seconds total
            "step_clock_seconds": [...],  # per-step game-seconds
            "text_suffix": str,           # optional flavor text appended to "TRAP!"
        }
    """
    off_team = game.offense_team
    def_team = game.defense_team
    off_lineup = off_team.lineup
    def_lineup = def_team.lineup

    is_away_offense = off_team.team_id == game.away_team.team_id

    # Per spec K — first cut: BH is always PG (the BIP receiver).
    bh_pos = "PG"
    ball_handler = off_lineup.get(bh_pos)
    defender = def_lineup.get(bh_pos)
    if ball_handler is None or defender is None:
        # Defensive bail; caller will fall back to skeleton behavior if needed.
        # Returning ``bail=True`` keeps the contract simple — the phase
        # resolution wrapper checks this and short-circuits.
        return {
            "bail": True,
            "result_type": "HCO",
            "ball_handler": ball_handler,
            "defender": defender,
            "text_suffix": "",
        }

    off_targets, def_targets = _build_step_1_targets(bh_pos, is_away_offense)
    bh_target = off_targets[bh_pos]

    pg_def = def_lineup.get("PG")

    # AG-driven drive rate. At AG=50 this resolves to 16×0.75 = 12, matching the
    # legacy ATTACK_DRIVE_GRID_SPOTS_PER_GAME_SECOND.
    bh_attrs = getattr(ball_handler, "attributes", None) or {}
    bh_drive_rate = ag_to_grid_per_game_sec(bh_attrs.get("AG", 50))

    # --- Running per-player coords (start of the loop = walk-up end) ----------
    off_coords: Dict[str, Dict[str, int]] = {
        pos: {"x": int(off_targets[pos]["x"]), "y": int(off_targets[pos]["y"])}
        for pos in POSITIONS
    }
    def_coords: Dict[str, Dict[str, int]] = {
        pos: {"x": int(def_targets[pos]["x"]), "y": int(def_targets[pos]["y"])}
        for pos in POSITIONS
    }
    bh_xy = off_coords[bh_pos]

    # Seed the running shot clock once (§4 Time terminals). Decremented per
    # segment so the loop is strictly bounded.
    game_state = getattr(game, "game_state", {}) or {}
    shot_clock = float(game_state.get("shot_clock_remaining", 30) or 30)

    loop_segments: List[Dict[str, Any]] = []
    result_type = "HCO"
    text_suffix = ""
    # Set when a broken-HCT attack reaches the topLane spot → D18 fast break.
    # Carries the post-drive offense/defense coords for the shot resolver.
    fb_seed: Dict[str, Any] = {}

    # --- Initial converge: position the defense around the BH (§6) -----------
    pg_initial = dict(def_coords["PG"])
    _position_defense(bh_xy, def_coords, is_away_offense)
    converge_seconds = max(
        0.4,
        calc_ag_segment_seconds(pg_initial, def_coords["PG"], pg_def, archetype="standard"),
    )
    loop_segments.append(
        _segment("hct_converge", off_coords, def_coords, converge_seconds, ("def", "PG"), bh_pos)
    )
    shot_clock -= converge_seconds

    def _advance() -> None:
        """Neutral / beaten-pressure advance: BH dribbles forward, defense re-poses."""
        nonlocal bh_xy
        adv_x = bh_xy["x"] + _basket_dir(is_away_offense) * random.randint(
            ADVANCE_X_MIN, ADVANCE_X_MAX
        )
        adv_y = bh_xy["y"] + random.randint(ADVANCE_Y_MIN, ADVANCE_Y_MAX)
        new_bh = _clamp_xy({"x": adv_x, "y": adv_y})
        advance_seconds = max(0.3, _euclid(bh_xy, new_bh) / bh_drive_rate)
        off_coords[bh_pos] = new_bh
        bh_xy = off_coords[bh_pos]
        _position_defense(bh_xy, def_coords, is_away_offense)
        loop_segments.append(
            _segment("hct_advance", off_coords, def_coords, advance_seconds, ("off", bh_pos), bh_pos)
        )

    def _do_broken_hct() -> Tuple[str, float]:
        """Append the broken-HCT open-floor drive segment; return (mode, secs).

        ``mode`` is "HCO" (drove to the perfect PSA spot) or "FAST_BREAK"
        (drove to topLane; caller seeds the D18 shot resolver)."""
        mode, seg, sec = _emit_broken_hct_drive(
            bh_xy, is_away_offense, bh_drive_rate, off_coords, def_coords, bh_pos
        )
        loop_segments.append(seg)
        return mode, sec

    def _seed_fast_break() -> None:
        """Snapshot the post-drive offense/defense coords for the FB resolver."""
        nonlocal fb_seed
        fb_seed = {
            "shooter_pos": bh_pos,
            "off_coords": {p: dict(off_coords[p]) for p in POSITIONS},
            "def_coords": {p: dict(def_coords[p]) for p in POSITIONS},
        }

    def _resolve_attack(moment: str, in_range: List[str]) -> Tuple[str, float]:
        """Pick the contesting defender(s) per §5 and resolve the banded outcome."""
        if moment == "trap":
            bh_def_pos, trapper_pos = _select_trappers(in_range, "PG" in in_range)
        else:
            bh_def_pos, trapper_pos = in_range[0], None
        return _resolve_moment(
            off_team,
            def_team,
            ball_handler,
            def_lineup.get(bh_def_pos),
            def_lineup.get(trapper_pos) if trapper_pos else None,
        )

    # --- §4 loop ------------------------------------------------------------
    for _ in range(MAX_LOOP_ITERATIONS):
        # 1) Time terminals (checked at the top of each iteration).
        if shot_clock <= 0:
            result_type = "DEAD BALL"  # shot-clock violation (proper announce: D9)
            text_suffix = " shot clock violation!"
            break
        if shot_clock <= HCT_SHOT_CLOCK_VIOLATION_THRESHOLD and not _crossed_half_court(
            bh_xy["x"], is_away_offense
        ):
            result_type = "DEAD BALL"  # 10-second violation (proper announce: D9)
            text_suffix = " 10-second violation!"
            break

        # 2) Zone precedence (§2 HCO entry triggers; Attack-Basket §7 → 2D).
        if _in_primary_safe_area(bh_xy, is_away_offense) or _past_primary_safe_area(
            bh_xy, is_away_offense
        ):
            result_type = "HCO"
            text_suffix = " they break the trap & establish their half court offense"
            break

        # 3) Detect the moment (§5) and read (reduced thresholds if no defender).
        moment, in_range = _detect_moment(bh_xy, def_coords, is_away_offense)
        decision = _read_decision(ball_handler, broken=(moment == "none"))

        if decision == "attack":
            if moment == "none":
                # Broken-HCT open-floor drive: to the PSA (→ HCO) or, if the
                # PSA is behind the BH, to the topLane spot (→ D18 fast break).
                mode, sec = _do_broken_hct()
                shot_clock -= sec
                if mode == "FAST_BREAK":
                    _seed_fast_break()
                    result_type = "FAST_BREAK_SHOT"
                    text_suffix = " open floor — fast break!"
                else:
                    result_type = "HCO"
                    text_suffix = " open floor — they break the trap & establish their half court offense"
                break
            outcome, score_ratio = _resolve_attack(moment, in_range)
            if outcome == "DEAD BALL":
                seg, sec = _emit_dead_ball_drive(
                    bh_xy, score_ratio, is_away_offense, bh_drive_rate, off_coords, def_coords, bh_pos
                )
                loop_segments.append(seg)
                shot_clock -= sec
                result_type = "DEAD BALL"
                text_suffix = " they force a turnover!"
                break
            # POS_O / NEUTRAL → advance below.
            _advance()
            shot_clock -= loop_segments[-1]["seconds"]
            continue

        if decision == "hold":
            # §5 hold resolution: BH holds the ball for random(1,3)s while the
            # defense keeps closing. Outcome depends on what reaches the BH.
            hold_seconds = float(random.randint(HOLD_SECONDS_MIN, HOLD_SECONDS_MAX))
            _position_defense(bh_xy, def_coords, is_away_offense)
            loop_segments.append(
                _segment("hct_hold", off_coords, def_coords, hold_seconds, ("off", bh_pos), bh_pos)
            )
            shot_clock -= hold_seconds

            moment2, in_range2 = _detect_moment(bh_xy, def_coords, is_away_offense)
            if moment2 == "trap":
                # A second defender arrived during the hold → Trap Moment.
                outcome, score_ratio = _resolve_attack("trap", in_range2)
                if outcome == "DEAD BALL":
                    seg, sec = _emit_dead_ball_drive(
                        bh_xy, score_ratio, is_away_offense, bh_drive_rate, off_coords, def_coords, bh_pos
                    )
                    loop_segments.append(seg)
                    shot_clock -= sec
                    result_type = "DEAD BALL"
                    text_suffix = " they force a turnover!"
                    break
                _advance()
                shot_clock -= loop_segments[-1]["seconds"]
                continue
            if moment2 == "none":
                # No defender reached the BH before the window elapsed → broken-HCT.
                mode, sec = _do_broken_hct()
                shot_clock -= sec
                if mode == "FAST_BREAK":
                    _seed_fast_break()
                    result_type = "FAST_BREAK_SHOT"
                    text_suffix = " open floor — fast break!"
                else:
                    result_type = "HCO"
                    text_suffix = " open floor — they break the trap & establish their half court offense"
                break
            # Pressure (single defender on the BH): 50% steal attempt /
            # 50% pressure-no-steal. Steal + foul outcomes are stubbed (D8) →
            # no stopping action, return to the loop for a fresh read.
            continue

        # decision == "pass" → §6 pass branch. The ball goes to one of the two
        # teammates closest to the BH; the receiver becomes the new ball handler
        # and the loop continues from him (enables a non-PG HCT-end BH → D7).
        receiver_pos = _select_pass_receiver(bh_pos, off_coords)
        passer_pos = bh_pos

        # D19 — compute the pass-defense formation ONCE (around the receiver) and
        # persist it across the flight + reception segments so defenders don't
        # re-randomize/jitter between the two steps.
        pass_def_coords = {p: dict(def_coords[p]) for p in POSITIONS}
        _position_defense(off_coords[receiver_pos], pass_def_coords, is_away_offense)

        # 1) Flight: offense holds, the persisted defense closes, ball travels.
        for p in POSITIONS:
            def_coords[p] = dict(pass_def_coords[p])
        pass_seconds = max(
            0.3, _euclid(off_coords[passer_pos], off_coords[receiver_pos]) / PASS_GRID_PER_GAME_SEC
        )
        loop_segments.append(
            _pass_segment(passer_pos, receiver_pos, off_coords, def_coords, pass_seconds)
        )
        shot_clock -= pass_seconds

        # 2) Reception/hold: receiver holds at the catch spot for random(1,3)s;
        #    the persisted defense holds its formation. Receiver is now the BH.
        bh_pos = receiver_pos
        bh_xy = off_coords[bh_pos]
        recv_hold_seconds = float(random.randint(HOLD_SECONDS_MIN, HOLD_SECONDS_MAX))
        loop_segments.append(
            _segment(
                "hct_reception", off_coords, def_coords, recv_hold_seconds, ("off", bh_pos), bh_pos
            )
        )
        shot_clock -= recv_hold_seconds
    else:
        # Iteration backstop hit without a terminal — settle into HCO.
        result_type = "HCO"
        text_suffix = text_suffix or " they break the trap & establish their half court offense"

    # Engine returns intermediate data only — the emitter assembles the walk-up
    # step plus one schema step per loop segment.
    return {
        "result_type": result_type,
        "ball_handler": ball_handler,
        "defender": defender,
        "text_suffix": text_suffix,
        # Entry walk-up targets (segment 0).
        "bh_pos": bh_pos,
        "bh_target": bh_target,
        "other_offense_targets": {
            pos: off_targets[pos] for pos in POSITIONS if pos != bh_pos
        },
        "def_initial_targets": def_targets,
        # Variable-length loop segments (converge, advances, attack).
        "loop_segments": loop_segments,
        # Set only for result_type == "FAST_BREAK_SHOT" (§5 broken-HCT → D18).
        "fb_seed": fb_seed,
    }
