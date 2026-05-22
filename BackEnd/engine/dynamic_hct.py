"""
Dynamic HCT (Half Court Trap) turn resolution.

Spec: ``_documentation_master/projects/Dynamic_HCT_Turns.md``.

First-cut scope (per project doc):
  - Step 1: ball handler advances from BIP receive coords to ``(44, target_y)``
    with ``target_y`` random in [21, 29]. The 9 other players begin moving
    toward their own targets at the standard challenged-open-floor pace
    (16 units / game-second). Step 1 ends the moment the BH arrives at his
    target — at that instant the 9 movers freeze wherever they are.
  - Step 2 (instigation point 1): defensive PG converges to ``(46, BH_y)``;
    the other 9 hold. The "read" branch (attack vs. pass-to-side) is deferred
    for first cut — we always execute the attack branch.
  - Step 3 (attack branch): compute the contested score per spec:
        outside_d_score = calculate_defender_pressure_score
                          + (def_team.pt_efficiency * randint(1, 6))
        ball_handling_score = calculate_ball_handling_score
                              * (off_team.pt_opp_modifier * randint(1, 6))
    If d > o → BH animates partway along his path toward deep key (57, 25),
        defender follows; result_type = "DEAD BALL".
    Else  → BH dribbles all the way to deep key; result_type = "HCO".

Output shape mirrors the skeleton-driven HCT path: per-player animation dicts
with ``movement`` waypoint arrays, plus turn-level metadata
(``result_type``, ``time_elapsed``, ``ball_handler``, ``defender``,
``step_clock_seconds``) consumed by ``resolve_half_court_trap_logic``.

Pass-to-side branch, x=64 transition / shoot logic, fouls/steals/violations,
and stat-tracking expansions are deferred to subsequent cuts.
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
)
from BackEnd.utils.shared import (
    ag_to_grid_per_game_sec,
    calc_ag_segment_seconds,
    calculate_ball_handling_score,
    calculate_defender_pressure_score,
    get_away_player_coords,
)
from BackEnd.utils.shared_defense import HCT_STANDARD_NORMAL


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


def _resolve_step_3_attack_outcome(
    off_team,
    def_team,
    ball_handler,
    defender,
) -> Tuple[str, float]:
    """
    Compute the step-3 attack outcome per the project spec.

    Returns ``(result_type, score_ratio)`` where:
      - ``result_type`` ∈ {"DEAD BALL", "HCO"}
      - ``score_ratio`` is a 0..1 float locating the random turnover point
        along the BH's path to deep key (used to draw the dead-ball stop).
    """
    off_attrs = getattr(off_team, "team_attributes", {}) or {}
    def_attrs = getattr(def_team, "team_attributes", {}) or {}

    pt_eff = float(def_attrs.get("pt_efficiency", 0) or 0)
    pt_opp = float(off_attrs.get("pt_opp_modifier", 0) or 0)

    base_def = calculate_defender_pressure_score(defender, "man")
    outside_d_score = base_def + (pt_eff * random.randint(1, 6))

    base_handling = calculate_ball_handling_score(ball_handler)
    # Spec uses ``*`` — multiplicative team modifier on the handling roll.
    # When pt_opp_modifier is 0 we'd zero out the handling score; treat 0 as a
    # no-op (multiplier 1) so an unset team attribute doesn't auto-turnover.
    if pt_opp > 0:
        ball_handling_score = base_handling * (pt_opp * random.randint(1, 6))
    else:
        ball_handling_score = base_handling

    if outside_d_score > ball_handling_score:
        # Random midpoint of the BH's path to deep key (exclusive of endpoints).
        return "DEAD BALL", random.uniform(0.2, 0.8)
    return "HCO", 1.0


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

    # --- Resolve PG defender (the trapper in steps 2 & 3) ---
    pg_def = def_lineup.get("PG")

    # --- Converge target (PG defender end coord at end of step 2) ---
    converge_x = bh_target["x"] + STEP_2_DEFENDER_X_OFFSET
    if is_away_offense:
        # Defender is between BH and the away basket (lower x).
        converge_x = bh_target["x"] - STEP_2_DEFENDER_X_OFFSET
    converge_target = {"x": int(converge_x), "y": int(bh_target["y"])}

    # Converge duration: PG defender's AG-driven travel from initial centroid
    # (50, 25) to converge_target. At AG=50 this matches the legacy COF=16 rate.
    pg_def_initial = def_targets["PG"]
    converge_seconds = max(
        0.4,  # floor — short visible converge
        calc_ag_segment_seconds(pg_def_initial, converge_target, pg_def, archetype="standard"),
    )

    # --- Step 3 (attack branch) ---
    result_type, score_ratio = _resolve_step_3_attack_outcome(
        off_team, def_team, ball_handler, defender
    )

    # AG-driven drive rate (Phase 4b). At AG=50 this resolves to 16×0.75 = 12,
    # exactly matching the legacy ATTACK_DRIVE_GRID_SPOTS_PER_GAME_SECOND, so
    # average-AG ball handlers produce identical timing to pre-migration.
    bh_attrs = getattr(ball_handler, "attributes", None) or {}
    bh_drive_rate = ag_to_grid_per_game_sec(bh_attrs.get("AG", 50))

    deep_key = DEEP_KEY_SPOT if not is_away_offense else _flip(DEEP_KEY_SPOT)
    path_distance = _euclid(bh_target, deep_key)
    if result_type == "DEAD BALL":
        # BH animates partway along path to deep key; defender follows.
        partial_distance = path_distance * score_ratio
        partial_elapsed = partial_distance / bh_drive_rate
        attack_bh_target = _move_at_pace(
            bh_target, deep_key, partial_elapsed, bh_drive_rate,
        )
        attack_seconds = max(0.3, partial_elapsed)
    else:
        # HCO transition: BH dribbles all the way to deep key.
        attack_bh_target = dict(deep_key)
        attack_seconds = max(0.3, path_distance / bh_drive_rate)

    # PG defender follows BH at the same x-offset used in step 2.
    attack_def_target = {
        "x": int(attack_bh_target["x"] + (
            -STEP_2_DEFENDER_X_OFFSET if is_away_offense else STEP_2_DEFENDER_X_OFFSET
        )),
        "y": int(attack_bh_target["y"]),
    }

    text_suffix = (
        " they break the trap & establish their half court offense"
        if result_type == "HCO"
        else " they force a turnover!"
    )

    # Engine returns intermediate data only — no animation steps. The emitter
    # (``dynamic_hct_step_emitter.build_dynamic_hct_animation_steps``) consumes
    # this dict + ``prior_turn.final_coords`` to assemble three schema steps:
    # entry walk-up (universal primitive), converge, attack.
    return {
        "result_type": result_type,
        "ball_handler": ball_handler,
        "defender": defender,
        "text_suffix": text_suffix,
        # Step 1 (entry walk-up) targets — emitter builds the walk-up step.
        "bh_pos": bh_pos,
        "bh_target": bh_target,
        "other_offense_targets": {
            pos: off_targets[pos] for pos in ("PG", "SG", "SF", "PF", "C") if pos != bh_pos
        },
        "def_initial_targets": def_targets,
        # Step 2 (converge) targets.
        "converge_target": converge_target,
        "converge_seconds": round(converge_seconds, 2),
        # Step 3 (attack) targets.
        "attack_bh_target": attack_bh_target,
        "attack_def_target": attack_def_target,
        "attack_seconds": round(attack_seconds, 2),
    }
