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
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.constants import (
    CRUISE_BASELINE_GRID_PER_GAME_SEC,
    DRIVE_MULTIPLIER,
    HCO_STRING_SPOTS,
    HCT_SETUP_POSITIONS,
)
from BackEnd.utils.shared import (
    ag_to_grid_per_game_sec,
    calc_ag_segment_seconds,
    calc_cruise_segment_seconds,
    calculate_ball_handling_score,
    calculate_defender_pressure_score,
    get_away_player_coords,
    is_user_facing_game,
)
from BackEnd.utils.shared_defense import HCT_STANDARD_NORMAL


# Animation timestamp granularity. Each game-second is scaled to ``ANIM_MS_PER_GAME_SEC``
# milliseconds in the animation array so visible duration tracks game time. Skeletons
# use ~800ms per step at typical ~1 game-second pace, so this gives equivalent feel for
# steady movement and lets longer holds (e.g. the BH 3-second hold at step-1 start)
# get proportionally more anim time.
ANIM_MS_PER_GAME_SEC = 800

# 10-second violation gate (per Dynamic_HCT_Turns.md "Special Situations").
# When the shot clock reaches this threshold and the ball handler has not yet
# crossed half-court, we announce "10-Second Violation" and run the standard
# dead-ball-turnover flow → SIP. NOT WIRED in first cut; constant defined now
# so the next iteration can plug in the runtime check without churn.
HCT_SHOT_CLOCK_VIOLATION_THRESHOLD = 20

# Initial BH hold at the start of step 1. Currently disabled (0.0) — the BH
# advances immediately on receiving the inbound. Kept as a tunable so a brief
# pause can be reintroduced without restructuring waypoint emission.
BH_HOLD_GAME_SECONDS = 0.0

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


def _flip_x(value: int) -> int:
    return 100 - int(value)


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


def _step_1_target(player_pos: str, alias_to_real: Dict[str, str], bh_pos: str, is_away_offense: bool, def_lineup_keys: List[str]):
    """
    Resolve the step-1 movement target for a given lineup position.

    For offensive lineup: BH gets (44, random y in 21–29); pos1..4 get a random
    spot inside their range.
    For defensive lineup: PG gets exact center court override; others get the
    centroid of their HCT_STANDARD_NORMAL polygon.

    Caller distinguishes by lineup membership (this helper handles both).
    """
    raise NotImplementedError("Use _build_step_1_targets instead — kept here to flag intent.")


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


def _start_coords(player) -> Dict[str, int]:
    """Read the player's current coords for step-1 starting point. Used for
    defenders (whose ``player.coords`` is correct post-made-shot). Offense uses
    ``_hct_setup_start_coords`` instead — see that helper for why."""
    coords = getattr(player, "coords", None) or {}
    return {"x": int(coords.get("x", 50) or 50), "y": int(coords.get("y", 25) or 25)}


def _hct_setup_start_coords(pos: str, is_away_offense: bool) -> Dict[str, int]:
    """Offensive start coord for HCT step 1, sourced from HCT_SETUP_POSITIONS.

    BIP places the SPRITE at the authored setup spot but does not write back to
    ``player.coords``. Reading ``player.coords`` for offense here would yield a
    stale value from the prior offensive possession, producing waypoints that
    don't match the sprite's actual screen position — the frontend then tweens
    forward into the wrong spot before snapping back. See Dynamic_HCT_Turns.md.
    """
    location = HCT_SETUP_POSITIONS.get(pos)
    coords = HCO_STRING_SPOTS.get(location, {"x": 50, "y": 25})
    out = {"x": int(coords["x"]), "y": int(coords["y"])}
    if is_away_offense:
        out = _flip(out)
    return out


def _step_1_arrival_time(start: Dict[str, Any], target: Dict[str, Any]) -> float:
    """Game seconds for the BH to reach the step-1 engagement target.

    HCT step 1 is a cruise step (the BH is bringing the ball up, not maxing
    speed). The BH gets a fresh random rate in [BH_CRUISE_MIN, BH_CRUISE_MAX]
    per call, giving each turn organic variation. Other 9 players run at the
    cruise baseline rate in their own waypoint emission below.
    """
    if _euclid(start, target) <= 0:
        return 0.0
    return calc_cruise_segment_seconds(start, target, role="bh")


def _emit_animation(
    player_id: str,
    waypoints: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Wrap a list of {timestamp, coords, action} waypoints into the animation
    shape the frontend expects."""
    if not waypoints:
        return None  # type: ignore[return-value]
    return {
        "playerId": player_id,
        "start": waypoints[0]["coords"],
        "end": waypoints[-1]["coords"],
        "movement": waypoints,
        "hasBallAtStep": [False] * len(waypoints),
        "duration": waypoints[-1]["timestamp"],
    }


def _add_waypoint(
    bucket: Dict[str, List[Dict[str, Any]]],
    player_id: str,
    timestamp: int,
    coords: Dict[str, int],
    action: str,
    game_seconds: Optional[float] = None,
) -> None:
    """Append a waypoint. ``game_seconds`` (Phase 3) is the segment game-time
    from the previous waypoint to this one — frontend uses it as the
    authoritative tween duration when present, scaled by clockSecondMs to wall
    time. Omit on start waypoints (no previous segment)."""
    wp: Dict[str, Any] = {
        "timestamp": int(timestamp),
        "coords": {"x": int(coords["x"]), "y": int(coords["y"])},
        "action": action,
    }
    if game_seconds is not None:
        wp["game_seconds"] = float(game_seconds)
    bucket.setdefault(player_id, []).append(wp)


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
        return {
            "animations": [],
            "result_type": "HCO",
            "ball_handler": ball_handler,
            "defender": defender,
            "time_elapsed": 0.0,
            "step_clock_seconds": [0.0],
            "text_suffix": "",
        }

    off_targets, def_targets = _build_step_1_targets(bh_pos, is_away_offense)
    bh_start = _hct_setup_start_coords(bh_pos, is_away_offense)
    bh_target = off_targets[bh_pos]

    # 🔍 [HCT-DIAG] (TEMP) verify setup-spot starts vs stale player.coords.
    # Gate on user-facing game so franchise-mode parallel CPU sims don't multiply
    # log noise. Remove once Dynamic_HCT_Turns.md bug is confirmed fixed.
    if is_user_facing_game(game):
        logging.warning(
            "🔍 [HCT-DIAG] is_away_offense=%s bh_pos=%s",
            is_away_offense,
            bh_pos,
        )
        for _pos in ("PG", "SG", "SF", "PF", "C"):
            _player = off_lineup.get(_pos)
            _stale = (getattr(_player, "coords", None) or {}) if _player else {}
            _setup = _hct_setup_start_coords(_pos, is_away_offense)
            logging.warning(
                "🔍 [HCT-DIAG]   %s: setup=(%s,%s) stale_player_coords=(%s,%s)%s",
                _pos,
                _setup["x"],
                _setup["y"],
                _stale.get("x", "?"),
                _stale.get("y", "?"),
                " [BH]" if _pos == bh_pos else "",
            )

    # ---- Step 1 timing: BH holds 1 sec, then moves at challenged-open-floor pace.
    bh_move_seconds = _step_1_arrival_time(bh_start, bh_target)
    step_1_seconds = BH_HOLD_GAME_SECONDS + bh_move_seconds

    # Animation timestamps in real-time ms; we'll lay down 2-3 waypoints per
    # step to keep the frontend interpolation crisp.
    waypoints: Dict[str, List[Dict[str, Any]]] = {}

    # --- Step 1 ---
    # Animation timestamps scale to game-seconds via ANIM_MS_PER_GAME_SEC so the
    # 3-second hold reads as ~3x longer than a 1-second movement step.
    step_start_ms = 0
    bh_hold_ms = step_start_ms + int(round(BH_HOLD_GAME_SECONDS * ANIM_MS_PER_GAME_SEC))
    bh_arrive_ms = step_start_ms + int(round(step_1_seconds * ANIM_MS_PER_GAME_SEC))

    # BH waypoints. When BH_HOLD_GAME_SECONDS > 0 we emit a hold waypoint so
    # the BH visibly pauses at the inbound spot before advancing — that adds an
    # extra stepIndex iteration to the step loop. When the hold is 0 we omit
    # the hold waypoint entirely so BH has the same waypoint count as the other
    # 9 movers (start + arrive). This avoids a stepIndex misalignment where BH
    # would otherwise stand still during stepIndex=1 (zero-distance hold) while
    # everyone else completes step 1, then BH does the actual move during
    # stepIndex=2 — visually a ~1-second pause for BH in the no-hold path.
    bh_pid = _player_id(ball_handler)
    _add_waypoint(waypoints, bh_pid, step_start_ms, bh_start, "handle_ball")
    if BH_HOLD_GAME_SECONDS > 0:
        _add_waypoint(
            waypoints, bh_pid, bh_hold_ms, bh_start, "handle_ball",
            game_seconds=BH_HOLD_GAME_SECONDS,
        )
        _add_waypoint(
            waypoints, bh_pid, bh_arrive_ms, bh_target, "handle_ball",
            game_seconds=bh_move_seconds,
        )
    else:
        # Single segment: start → arrive over the full step_1_seconds.
        _add_waypoint(
            waypoints, bh_pid, bh_arrive_ms, bh_target, "handle_ball",
            game_seconds=step_1_seconds,
        )

    # Other 4 offensive teammates: move toward pos1-4 targets for the full duration of step 1.
    for pos in ("PG", "SG", "SF", "PF", "C"):
        if pos == bh_pos:
            continue
        player = off_lineup.get(pos)
        if player is None:
            continue
        pid = _player_id(player)
        start = _hct_setup_start_coords(pos, is_away_offense)
        target = off_targets[pos]
        # End coord at the moment BH arrives — may not have reached target.
        end_coords = _move_at_pace(start, target, step_1_seconds, CRUISE_BASELINE_GRID_PER_GAME_SEC)
        _add_waypoint(waypoints, pid, step_start_ms, start, "move")
        _add_waypoint(
            waypoints, pid, bh_arrive_ms, end_coords, "move",
            game_seconds=step_1_seconds,
        )

    # 5 defenders: move toward zone-Normal centroids (PG → center court override).
    def_step_1_end: Dict[str, Dict[str, int]] = {}
    for pos in ("PG", "SG", "SF", "PF", "C"):
        defender_obj = def_lineup.get(pos)
        if defender_obj is None:
            continue
        pid = _player_id(defender_obj)
        start = _start_coords(defender_obj)
        target = def_targets[pos]
        end_coords = _move_at_pace(start, target, step_1_seconds, CRUISE_BASELINE_GRID_PER_GAME_SEC)
        def_step_1_end[pos] = end_coords
        _add_waypoint(waypoints, pid, step_start_ms, start, "guard_offball")
        _add_waypoint(
            waypoints, pid, bh_arrive_ms, end_coords, "guard_offball",
            game_seconds=step_1_seconds,
        )

    # --- Step 2: defensive PG converges to (BH_x + offset, BH_y); others hold.
    # Per spec D: only defensive PG moves in step 2 for the first cut.
    pg_def = def_lineup.get("PG")
    pg_def_start = def_step_1_end.get("PG", _start_coords(pg_def))
    converge_x = bh_target["x"] + STEP_2_DEFENDER_X_OFFSET
    if is_away_offense:
        # Defender is between BH and the away basket (lower x).
        converge_x = bh_target["x"] - STEP_2_DEFENDER_X_OFFSET
    converge_target = {"x": converge_x, "y": bh_target["y"]}
    # AG-driven: defender's AG sets the converge pace (Phase 4b). At AG=50 this
    # matches the legacy COF=16 rate exactly, so average lineups are unchanged.
    step_2_seconds = max(
        0.4,  # floor — short visible converge
        calc_ag_segment_seconds(pg_def_start, converge_target, pg_def, archetype="default"),
    )
    step_2_start_ms = bh_arrive_ms
    step_2_end_ms = step_2_start_ms + int(round(step_2_seconds * ANIM_MS_PER_GAME_SEC))

    # PG defender: converge. (pg_def already resolved above for converge timing.)
    if pg_def is not None:
        pg_pid = _player_id(pg_def)
        _add_waypoint(
            waypoints, pg_pid, step_2_end_ms, converge_target, "guard_ball",
            game_seconds=step_2_seconds,
        )

    # All other players hold at their step-1 end coords.
    bh_step_2_coords = bh_target
    _add_waypoint(
        waypoints, bh_pid, step_2_end_ms, bh_step_2_coords, "handle_ball",
        game_seconds=step_2_seconds,
    )
    for pos in ("PG", "SG", "SF", "PF", "C"):
        if pos == bh_pos:
            continue
        off_player = off_lineup.get(pos)
        if off_player is not None:
            pid = _player_id(off_player)
            last_wp = waypoints[pid][-1]["coords"]
            _add_waypoint(
                waypoints, pid, step_2_end_ms, last_wp, "stand",
                game_seconds=step_2_seconds,
            )
    for pos in ("PG", "SG", "SF", "PF", "C"):
        if pos == "PG":
            continue
        def_player = def_lineup.get(pos)
        if def_player is not None:
            pid = _player_id(def_player)
            last_wp = waypoints[pid][-1]["coords"]
            _add_waypoint(
                waypoints, pid, step_2_end_ms, last_wp, "stand",
                game_seconds=step_2_seconds,
            )

    # --- Step 3 (attack branch — read deferred for first cut).
    result_type, score_ratio = _resolve_step_3_attack_outcome(
        off_team, def_team, ball_handler, defender
    )

    # AG-driven drive rate (Phase 4b). At AG=50 this resolves to 16×0.75 = 12,
    # exactly matching the legacy ATTACK_DRIVE_GRID_SPOTS_PER_GAME_SECOND, so
    # average-AG ball handlers produce identical timing to pre-migration.
    bh_attrs = getattr(ball_handler, "attributes", None) or {}
    bh_drive_rate = ag_to_grid_per_game_sec(bh_attrs.get("AG", 50)) * DRIVE_MULTIPLIER

    if result_type == "DEAD BALL":
        # BH animates partway along path to deep key; defender follows.
        target_for_dribble = DEEP_KEY_SPOT
        if is_away_offense:
            target_for_dribble = _flip(target_for_dribble)
        path_distance = _euclid(bh_step_2_coords, target_for_dribble)
        partial_distance = path_distance * score_ratio
        partial_elapsed = partial_distance / bh_drive_rate
        partial_target = _move_at_pace(
            bh_step_2_coords,
            target_for_dribble,
            partial_elapsed,
            bh_drive_rate,
        )
        step_3_seconds = max(0.3, partial_elapsed)
        step_3_end_ms = step_2_end_ms + int(round(step_3_seconds * ANIM_MS_PER_GAME_SEC))

        # BH dribbles to partial point.
        _add_waypoint(
            waypoints, bh_pid, step_3_end_ms, partial_target, "dribble",
            game_seconds=step_3_seconds,
        )
        # Defender follows BH.
        if pg_def is not None:
            pg_pid = _player_id(pg_def)
            defender_partial = {
                "x": partial_target["x"] + (
                    -STEP_2_DEFENDER_X_OFFSET if is_away_offense else STEP_2_DEFENDER_X_OFFSET
                ),
                "y": partial_target["y"],
            }
            _add_waypoint(
                waypoints, pg_pid, step_3_end_ms, defender_partial, "guard_ball",
                game_seconds=step_3_seconds,
            )

    else:
        # HCO transition: BH dribbles all the way to deep key.
        target_for_dribble = DEEP_KEY_SPOT
        if is_away_offense:
            target_for_dribble = _flip(target_for_dribble)
        path_distance = _euclid(bh_step_2_coords, target_for_dribble)
        step_3_seconds = max(0.3, path_distance / bh_drive_rate)
        step_3_end_ms = step_2_end_ms + int(round(step_3_seconds * ANIM_MS_PER_GAME_SEC))

        _add_waypoint(
            waypoints, bh_pid, step_3_end_ms, target_for_dribble, "dribble",
            game_seconds=step_3_seconds,
        )
        if pg_def is not None:
            pg_pid = _player_id(pg_def)
            defender_follow = {
                "x": target_for_dribble["x"] + (
                    -STEP_2_DEFENDER_X_OFFSET if is_away_offense else STEP_2_DEFENDER_X_OFFSET
                ),
                "y": target_for_dribble["y"],
            }
            _add_waypoint(
                waypoints, pg_pid, step_3_end_ms, defender_follow, "guard_ball",
                game_seconds=step_3_seconds,
            )

    # All other players hold through step 3.
    for pos in ("PG", "SG", "SF", "PF", "C"):
        if pos == bh_pos:
            continue
        off_player = off_lineup.get(pos)
        if off_player is not None:
            pid = _player_id(off_player)
            last_wp = waypoints[pid][-1]["coords"]
            _add_waypoint(
                waypoints, pid, step_3_end_ms, last_wp, "stand",
                game_seconds=step_3_seconds,
            )
    for pos in ("PG", "SG", "SF", "PF", "C"):
        if pos == "PG":
            continue
        def_player = def_lineup.get(pos)
        if def_player is not None:
            pid = _player_id(def_player)
            last_wp = waypoints[pid][-1]["coords"]
            _add_waypoint(
                waypoints, pid, step_3_end_ms, last_wp, "stand",
                game_seconds=step_3_seconds,
            )

    # Compose animations list.
    animations: List[Dict[str, Any]] = []
    for pid, wps in waypoints.items():
        if pid:
            anim = _emit_animation(pid, wps)
            if anim is not None:
                animations.append(anim)

    text_suffix = (
        " they break the trap & establish their half court offense"
        if result_type == "HCO"
        else " they force a turnover!"
    )

    step_clock_seconds = [
        round(step_1_seconds, 2),
        round(step_2_seconds, 2),
        round(step_3_seconds, 2),
    ]
    time_elapsed = sum(step_clock_seconds)

    return {
        "animations": animations,
        "result_type": result_type,
        "ball_handler": ball_handler,
        "defender": defender,
        "time_elapsed": round(time_elapsed, 2),
        "step_clock_seconds": step_clock_seconds,
        "text_suffix": text_suffix,
    }
