"""Covert Release Fast Break animation step emitter.

Converts a Covert Release FB turn_result into the unified AnimationStep[]
payload defined in ``BackEnd/utils/animation_step_schema.py``.

Covert Release shape:
- DREB-initiated FB. The rebounder (outlet passer) outlets to a release
  player (outlet receiver = ball handler).
- Step 0: outlet pass (ball flies passer → receiver; per current frontend
  ``animateOutletPhase``, no players move during this step).
- Step 1: outcome
  - Shot Attempt (MAKE / MISS / BLOCK): shooter (BH) runs to shot spot,
    `next: turn_stop SHOT_ATTEMPT`. HCT pattern — no separate shot
    resolution step.
  - Defensive Stop: BH and defensive stopper both run to their stop
    spots. Slower of the two is the gate. ``step.end.announcement`` =
    "Nice Stop!" plays after the move; ``next`` points to step 2.
  - FOUL / STEAL / DEAD_BALL_TURNOVER: BH runs to outcome spot,
    `next: turn_stop` for the corresponding event.
- Step 2 (DEFENSIVE_STOP only): step-back / HCO setup. FB BH retreats to
  a deep frontcourt spot; HCO BH (default = team's PG) takes a position
  near FB BH on the same horizontal half (avoiding over-and-back); the
  remaining players take HCO setup positions per the standard pos1..pos4
  alias mapping. Defenders mirror with same-lineup-position matchup,
  forming a 2-3 zone footprint by construction. Ends with
  `next: next_step` past the array (implicit end → next turn is HCO).

Edge case: when the rebounder == release player (no distinct outlet passer),
the outlet pass step is skipped.

See ``_documentation_master/00_General_Systems/Step_By_Step_System.md`` —
"Covert Release" — for the per-step trigger spec.
"""

import math
import random
from typing import Any, Dict, List, Optional

from BackEnd.constants import (
    AWAY_RIM_COORDS,
    HCO_SETUP_HCO_BH_RADIUS,
    HCO_SETUP_OFFENSE_BH_DEEP_SPOTS,
    HCO_SETUP_OFFENSE_POS_SPOTS,
    HCO_STRING_SPOTS,
    HOME_RIM_COORDS,
    PASS_GRID_SPOTS_PER_GAME_SECOND,
)
from BackEnd.utils.animation_step_schema import (
    AdvanceTrigger,
    AnimationStep,
    Announcement,
    BallInFlight,
    BallState,
    ClockState,
    GridCoord,
    NextStep,
    PlayerAction,
    PlayerArchetype,
    StepEnd,
    StepStart,
)


# --- Vocabulary helpers ----------------------------------------------------


_OFFENSE_POSITIONS = ["PG", "SG", "SF", "PF", "C"]


def _safe_id(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    pid = getattr(obj, "player_id", None)
    return str(pid) if pid is not None else None


def _coord(obj: Any, fallback: Optional[GridCoord] = None) -> Optional[GridCoord]:
    """Read ``{x, y}`` off a player object or dict; return None if missing."""
    if obj is None:
        return fallback
    coords = getattr(obj, "coords", None) if not isinstance(obj, dict) else obj
    if not coords or "x" not in coords or "y" not in coords:
        return fallback
    return {"x": float(coords["x"]), "y": float(coords["y"])}


def _player_lookup_by_id(
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    player_id: Optional[str],
) -> Optional[Any]:
    if not player_id:
        return None
    target = str(player_id)
    for lineup in (off_lineup, def_lineup):
        for player in lineup.values():
            if player is None:
                continue
            pid = getattr(player, "player_id", None)
            if pid is not None and str(pid) == target:
                return player
    return None


def _all_player_start_coords(
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> Dict[str, GridCoord]:
    """Per-player start coords for step 0. Reads ``player.coords`` for every
    player in both lineups. Skips players without coords (defensive)."""
    out: Dict[str, GridCoord] = {}
    for lineup in (off_lineup, def_lineup):
        for player in lineup.values():
            if player is None:
                continue
            pid = getattr(player, "player_id", None)
            if pid is None:
                continue
            c = _coord(player)
            if c is None:
                continue
            out[str(pid)] = c
    return out


def _movement_end_coord(
    animations: List[Dict[str, Any]],
    player_id: str,
) -> Optional[GridCoord]:
    """Read ``animations[i].movement[-1].coords`` for the given player_id.
    Returns None if the player has no animation entry or no movement."""
    target = str(player_id)
    for anim in animations:
        if str(anim.get("playerId")) != target:
            continue
        movement = anim.get("movement") or []
        if not movement:
            return None
        last = movement[-1] or {}
        coords = last.get("coords") or {}
        if "x" not in coords or "y" not in coords:
            return None
        return {"x": float(coords["x"]), "y": float(coords["y"])}
    return None


def _euclid(a: GridCoord, b: GridCoord) -> float:
    dx = a["x"] - b["x"]
    dy = a["y"] - b["y"]
    return (dx * dx + dy * dy) ** 0.5


def _order_defenders_for_stop(
    defender_ids: List[str],
    all_start_coords: Dict[str, GridCoord],
    receiver_coord: GridCoord,
    is_away_offense: bool,
) -> tuple:
    """Order get-back defenders for the read-to-stop attempt sequence.

    A defender is **eligible** to attempt the stop if their x is at-or-past
    the receiver's x in the attacking direction:
      - Home offense (attacks x=91): eligible iff defender.x >= receiver.x
      - Away offense (attacks x=9):  eligible iff defender.x <= receiver.x

    Defenders behind the receiver auto-retreat to basket defense (ineligible).

    Among eligible defenders, the closest to the receiver (Euclidean) goes
    first. Exact ties → random choice. Returns
    ``(ordered_eligible_ids, ineligible_ids)``.
    """
    eligible: List[tuple] = []
    ineligible: List[str] = []
    for d_id in defender_ids:
        start = all_start_coords.get(d_id)
        if start is None:
            ineligible.append(d_id)
            continue
        if is_away_offense:
            is_eligible = float(start["x"]) <= float(receiver_coord["x"])
        else:
            is_eligible = float(start["x"]) >= float(receiver_coord["x"])
        if is_eligible:
            eligible.append((d_id, _euclid(start, receiver_coord)))
        else:
            ineligible.append(d_id)

    if len(eligible) == 2 and abs(eligible[0][1] - eligible[1][1]) < 1e-3:
        random.shuffle(eligible)
    else:
        eligible.sort(key=lambda x: x[1])
    return [d[0] for d in eligible], ineligible


def _basket_defense_spot(
    is_away_offense: bool,
    exclude_spot: Optional[GridCoord] = None,
) -> GridCoord:
    """Pick a random spot in front of the attacking team's rim for a defender
    protecting the basket on a CR FB.

    - Home offense (attacks x=91): defender box (87, 91) × (20, 30).
    - Away offense (attacks x=9):  defender box (9, 13) × (20, 30).

    When two defenders both retreat to the basket, pass the first defender's
    spot as ``exclude_spot`` to enforce a ≥2 grid offset on BOTH axes so the
    two defenders don't stack at the same spot. Falls back to a deterministic
    nearby offset after a few retries if the random box is too small.
    """
    if is_away_offense:
        x_lo, x_hi = 9, 13
    else:
        x_lo, x_hi = 87, 91
    y_lo, y_hi = 20, 30

    for _ in range(5):
        x = float(random.randint(x_lo, x_hi))
        y = float(random.randint(y_lo, y_hi))
        if exclude_spot is None:
            return {"x": x, "y": y}
        if (
            abs(x - float(exclude_spot["x"])) >= 2.0
            and abs(y - float(exclude_spot["y"])) >= 2.0
        ):
            return {"x": x, "y": y}

    # Fallback: deterministic offset from the excluded spot, clamped to box.
    ex_x = float(exclude_spot["x"]) if exclude_spot else float(x_lo)
    ex_y = float(exclude_spot["y"]) if exclude_spot else float(y_lo)
    nx = ex_x + 2.0 if ex_x + 2.0 <= x_hi else ex_x - 2.0
    ny = ex_y + 2.0 if ex_y + 2.0 <= y_hi else ex_y - 2.0
    return {
        "x": float(max(x_lo, min(x_hi, nx))),
        "y": float(max(y_lo, min(y_hi, ny))),
    }


# --- Outcome → next pointer ------------------------------------------------


def _ball_bounce_coords(turn_result: Dict[str, Any]) -> Optional[GridCoord]:
    bx = turn_result.get("ball_bounce_x")
    by = turn_result.get("ball_bounce_y")
    if bx is None or by is None:
        return None
    return {"x": float(bx), "y": float(by)}


def _resolve_outcome_next(turn_result: Dict[str, Any]) -> NextStep:
    """Map the FB result_type to the outcome step's ``next`` pointer."""
    result_type = (turn_result.get("result_type") or "").upper()

    if result_type in ("MAKE", "MISS", "BLOCK"):
        return {
            "kind": "turn_stop",
            "event": "SHOT_ATTEMPT",
            "payload": {
                "result": result_type,
                "shooter_id": _safe_id(turn_result.get("shooter")),
                "defender_id": _safe_id(turn_result.get("defender")),
                "ball_bounce_coords": _ball_bounce_coords(turn_result),
            },
        }

    if result_type == "FOUL":
        return {
            "kind": "turn_stop",
            "event": "FOUL",
            "payload": {
                "foul_team": turn_result.get("foul_team"),
                "fouler_id": turn_result.get("foul_player_id"),
                "victim_id": turn_result.get("victim_id"),
            },
        }

    if result_type == "STEAL":
        return {
            "kind": "turn_stop",
            "event": "STEAL",
            "payload": {
                "stealer_id": turn_result.get("stealer_id"),
                "victim_id": turn_result.get("victim_id"),
            },
        }

    if result_type in ("DEAD_BALL", "DEAD BALL", "DEAD_BALL_TURNOVER", "TURNOVER"):
        return {
            "kind": "turn_stop",
            "event": "DEAD_BALL_TURNOVER",
            "payload": {"victim_id": turn_result.get("victim_id")},
        }

    # DEFENSIVE_STOP and any unrecognized: implicit end of turn (HCT
    # "continue to HCO" pattern). Caller transitions to next turn (HCO).
    return {"kind": "next_step", "index": 999}


# --- Step builders ---------------------------------------------------------


def _build_outlet_pass_step(
    *,
    passer_id: str,
    receiver_id: str,
    passer_coord: GridCoord,
    receiver_coord: GridCoord,
    all_start_coords: Dict[str, GridCoord],
    fb_roles: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    is_away_offense: bool,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    is_first_step: bool,
    next_step_index: int,
) -> AnimationStep:
    """Step 0: outlet pass with parallel transition movement.

    Step duration is the Euclidean ball-flight time at
    ``FB_PASS_GRID_SPOTS_PER_GAME_SECOND`` (slower than HCO's canonical pass
    rate so the outlet pass reads visually alongside the parallel cutters).
    Floored at 0.5 game-sec so the beat registers for very short passes.

    Per-player movement during the step:
      - Outlet passer / receiver: stationary.
      - Get-back defenders (from prior shot's ``offense_getback`` list) —
        behavior depends on outlet pass quality:
          * **Sharp outlet** (``outlet_score >= 50``): defenders must make a
            read (``player_read``: IQ × 0.8 + CH × 0.2 × 1d6) vs threshold
            ``outlet_score × 3`` to attempt the stop. Closest eligible
            defender goes first; if their read passes, they take the cut-off
            stop position and the other defender retreats to defend the
            basket. If they fail, the second eligible defender attempts the
            read. Defenders behind the receiver in the attacking direction
            are ineligible and auto-retreat to basket defense.
          * **Sloppy outlet** (``outlet_score < 50``): legacy behavior —
            defender 1 takes the cut-off, defender 2 takes the same-side
            lowPost spot.
        See ``Fast_Break_System.md`` — Covert Release — for full spec.
      - All other players (non-passer, non-receiver, non-getback): drift a
        random 1-6 grid spots toward the attacking basket along x (y held)
        at ``standard`` rate. The small drift keeps the visual focus on the
        pass + receiver; they ramp up to sprint on step 1 once the receiver
        has caught the ball.

    Ball tweens passer → receiver over the full step T.
    """
    # Outlet pass T: Euclidean ball-flight time at FB pass rate, varied by
    # outlet quality. Good outlets (`outlet_score >= FB_OUTLET_QUALITY_THRESHOLD`)
    # zip at FB_PASS_GRID_SPOTS_PER_GAME_SECOND; poor outlets use the slower
    # FB_PASS_GRID_SPOTS_PER_GAME_SECOND_SLOPPY so the ball hangs in the air
    # and the play feels sloppier.
    # Floor at FB_PASS_MIN_GAME_SECONDS so the beat is perceptible for short passes.
    from BackEnd.constants import (
        FB_OUTLET_QUALITY_THRESHOLD,
        FB_PASS_GRID_SPOTS_PER_GAME_SECOND,
        FB_PASS_GRID_SPOTS_PER_GAME_SECOND_SLOPPY,
        FB_PASS_MIN_GAME_SECONDS,
    )
    _outlet_score = fb_roles.get("outlet_score")
    _pass_rate = (
        float(FB_PASS_GRID_SPOTS_PER_GAME_SECOND)
        if _outlet_score is not None and _outlet_score >= FB_OUTLET_QUALITY_THRESHOLD
        else float(FB_PASS_GRID_SPOTS_PER_GAME_SECOND_SLOPPY)
    )
    _dx = float(receiver_coord.get("x", 0)) - float(passer_coord.get("x", 0))
    _dy = float(receiver_coord.get("y", 0)) - float(passer_coord.get("y", 0))
    _grid_dist = (_dx * _dx + _dy * _dy) ** 0.5
    t = max(FB_PASS_MIN_GAME_SECONDS, _grid_dist / _pass_rate)

    x_dir = -1 if is_away_offense else 1
    attacking_basket = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
    attacking_basket_coord: GridCoord = {
        "x": float(attacking_basket["x"]),
        "y": float(attacking_basket["y"]),
    }

    # Get-back defender IDs, normalized to strings.
    getback_ids = [str(pid) for pid in (fb_roles.get("getback_player_ids") or []) if pid is not None]

    actions: Dict[str, PlayerAction] = {}
    archetype: Dict[str, PlayerArchetype] = {}
    destinations: Dict[str, Optional[GridCoord]] = {}
    end_coords: Dict[str, GridCoord] = {}
    for pid, coord in all_start_coords.items():
        actions[pid] = "stationary"
        archetype[pid] = "stationary"
        destinations[pid] = coord
        end_coords[pid] = dict(coord)  # Default: no movement.
    actions[passer_id] = "pass"
    actions[receiver_id] = "receive"

    # Targets per role: (player_id, target_coord, archetype).
    targets: List[tuple] = []

    # Get-back defenders: on a SHARP outlet (`outlet_score >= 50`), defenders
    # must make a read (`player_read`) to attempt the stop. On a SLOPPY outlet
    # they automatically get into position. See `Fast_Break_System.md`
    # — Covert Release — for the full design spec.
    cutoff_x_for_stop = max(4.0, min(97.0, receiver_coord["x"] + (2.0 * x_dir)))
    cutoff_target_for_stop: GridCoord = {
        "x": cutoff_x_for_stop,
        "y": float(receiver_coord["y"]),
    }
    outlet_score = fb_roles.get("outlet_score")
    valid_getback_ids = [
        d_id for d_id in getback_ids
        if d_id in all_start_coords and d_id not in (passer_id, receiver_id)
    ]
    from BackEnd.constants import FB_OUTLET_QUALITY_THRESHOLD as _SHARP_OUTLET_THRESHOLD
    use_read_system = (
        outlet_score is not None
        and outlet_score >= _SHARP_OUTLET_THRESHOLD
        and 1 <= len(valid_getback_ids) <= 2
    )

    if use_read_system:
        # Sharp outlet → defenders read to attempt the stop. Only the FIRST
        # eligible defender (closest to receiver, on the basket-side of the
        # receiver's x) attempts the read; if they pass, they take the stop
        # and the other defender retreats to defend the basket. If they
        # fail, the second eligible defender gets a read attempt.
        ordered_eligible, ineligible_ids = _order_defenders_for_stop(
            valid_getback_ids, all_start_coords, receiver_coord, is_away_offense
        )
        threshold = int(outlet_score) * 3
        stop_claimed = False
        basket_spots_taken: List[GridCoord] = []

        for d_id in ordered_eligible:
            if not stop_claimed:
                defender = _player_lookup_by_id(off_lineup, def_lineup, d_id)
                from BackEnd.utils.shared import player_read as _player_read_score
                score = _player_read_score(defender) if defender else 0
                if score >= threshold:
                    targets.append((d_id, cutoff_target_for_stop, "sprint"))
                    stop_claimed = True
                    continue
            # Read failed OR stop already claimed → retreat to basket.
            exclude = basket_spots_taken[0] if basket_spots_taken else None
            bd_spot = _basket_defense_spot(is_away_offense, exclude)
            basket_spots_taken.append(bd_spot)
            targets.append((d_id, bd_spot, "sprint"))

        # Ineligible defenders (behind the receiver in the attacking dir)
        # auto-retreat to basket without attempting a read.
        for d_id in ineligible_ids:
            exclude = basket_spots_taken[0] if basket_spots_taken else None
            bd_spot = _basket_defense_spot(is_away_offense, exclude)
            basket_spots_taken.append(bd_spot)
            targets.append((d_id, bd_spot, "sprint"))
    else:
        # Sloppy outlet (or no defenders): legacy behavior — gb1 takes the
        # cut-off near the receiver, gb2 (if present) takes the lowPost
        # spot on the same vertical half.
        if len(valid_getback_ids) >= 1:
            gb1_id = valid_getback_ids[0]
            targets.append((gb1_id, cutoff_target_for_stop, "sprint"))
        if len(valid_getback_ids) >= 2:
            gb2_id = valid_getback_ids[1]
            spot_name = "upper lowPost" if receiver_coord["y"] > 24 else "lower lowPost"
            spot_home = HCO_STRING_SPOTS[spot_name]
            if is_away_offense:
                gb2_target = {"x": float(100 - spot_home["x"]), "y": float(spot_home["y"])}
            else:
                gb2_target = {"x": float(spot_home["x"]), "y": float(spot_home["y"])}
            targets.append((gb2_id, gb2_target, "sprint"))

    # All others (non-passer, non-receiver, non-getback): drift a random 1–6
    # grid spots toward the attacking basket along x, holding y. Archetype
    # `standard` (transition pace). Keeps step 0 visually focused on
    # the pass + receiver rather than 6+ sprinters racing the BH; they
    # ramp up to sprint on step 1 once the receiver has caught the ball.
    excluded = {passer_id, receiver_id, *getback_ids}
    for pid in all_start_coords:
        if pid in excluded:
            continue
        start = all_start_coords[pid]
        drift = random.randint(1, 6)
        drift_x = max(4.0, min(97.0, float(start["x"]) + drift * x_dir))
        drift_target: GridCoord = {"x": drift_x, "y": float(start["y"])}
        targets.append((pid, drift_target, "standard"))

    # Compute interrupted end coords: start + (rate × T) along start→target.
    for pid, target, arch in targets:
        start = all_start_coords[pid]
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, arch) if player else 12.0
        max_traversal = rate * t
        dist = _euclid(start, target)
        if dist <= max_traversal or dist == 0.0:
            end_coords[pid] = {"x": float(target["x"]), "y": float(target["y"])}
        else:
            ratio = max_traversal / dist
            end_coords[pid] = {
                "x": start["x"] + (target["x"] - start["x"]) * ratio,
                "y": start["y"] + (target["y"] - start["y"]) * ratio,
            }
        destinations[pid] = {"x": float(target["x"]), "y": float(target["y"])}
        actions[pid] = "cut"
        archetype[pid] = arch

    # `outlet_score` is exposed on the step's advance_trigger metadata so the
    # frontend can render quality-gated visual effects (e.g., the high-score
    # ball-trail in `createBallTrail.js`) without needing a separate channel.
    _outlet_score_for_meta = fb_roles.get("outlet_score")
    advance_trigger: AdvanceTrigger = {
        "condition": "ball_reaches_player",
        "T_game_seconds": float(t),
        "metadata": {
            "from_player_id": passer_id,
            "to_player_id": receiver_id,
            "target_coords": dict(receiver_coord),
            "outlet_score": (
                int(_outlet_score_for_meta)
                if _outlet_score_for_meta is not None
                else None
            ),
        },
    }

    ball_start: BallState = {"owner_player_id": passer_id}
    ball_end: BallState = {"owner_player_id": receiver_id}

    clock_start: ClockState = {
        "clock_remaining": clock_remaining_at_start,
        "shot_clock_remaining": shot_clock_remaining_at_start,
    }
    clock_end: ClockState = {
        "clock_remaining": clock_remaining_at_start - t,
        "shot_clock_remaining": shot_clock_remaining_at_start - t,
    }

    start: StepStart = {
        "coords": dict(all_start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball_start,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_end,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": next_step_index},
    }
    _stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def _build_simplified_outlet_pass_step(
    *,
    passer_id: str,
    receiver_id: str,
    passer_coord: GridCoord,
    receiver_coord: GridCoord,
    all_start_coords: Dict[str, GridCoord],
    fb_roles: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    is_away_offense: bool,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
) -> AnimationStep:
    """Phase 3 outlet step: passer/receiver stationary; no outlet-phase cutoff."""
    from BackEnd.constants import (
        FB_OUTLET_QUALITY_THRESHOLD,
        FB_PASS_GRID_SPOTS_PER_GAME_SECOND,
        FB_PASS_GRID_SPOTS_PER_GAME_SECOND_SLOPPY,
        FB_PASS_MIN_GAME_SECONDS,
    )

    _outlet_score = fb_roles.get("outlet_score")
    _pass_rate = (
        float(FB_PASS_GRID_SPOTS_PER_GAME_SECOND)
        if _outlet_score is not None and _outlet_score >= FB_OUTLET_QUALITY_THRESHOLD
        else float(FB_PASS_GRID_SPOTS_PER_GAME_SECOND_SLOPPY)
    )
    _dx = float(receiver_coord.get("x", 0)) - float(passer_coord.get("x", 0))
    _dy = float(receiver_coord.get("y", 0)) - float(passer_coord.get("y", 0))
    _grid_dist = (_dx * _dx + _dy * _dy) ** 0.5
    t = max(FB_PASS_MIN_GAME_SECONDS, _grid_dist / _pass_rate)

    x_dir = -1 if is_away_offense else 1

    actions: Dict[str, PlayerAction] = {}
    archetype: Dict[str, PlayerArchetype] = {}
    destinations: Dict[str, Optional[GridCoord]] = {}
    end_coords: Dict[str, GridCoord] = {}
    for pid, coord in all_start_coords.items():
        actions[pid] = "stationary"
        archetype[pid] = "stationary"
        destinations[pid] = coord
        end_coords[pid] = dict(coord)
    actions[passer_id] = "pass"
    actions[receiver_id] = "receive"

    targets: List[tuple] = []
    excluded = {passer_id, receiver_id}
    for pid in all_start_coords:
        if pid in excluded:
            continue
        start = all_start_coords[pid]
        drift = random.randint(1, 6)
        drift_x = max(4.0, min(97.0, float(start["x"]) + drift * x_dir))
        drift_target: GridCoord = {"x": drift_x, "y": float(start["y"])}
        targets.append((pid, drift_target, "standard"))

    for pid, target, arch in targets:
        start = all_start_coords[pid]
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, arch) if player else 12.0
        max_traversal = rate * t
        dist = _euclid(start, target)
        if dist <= max_traversal or dist == 0.0:
            end_coords[pid] = {"x": float(target["x"]), "y": float(target["y"])}
        else:
            ratio = max_traversal / dist
            end_coords[pid] = {
                "x": start["x"] + (target["x"] - start["x"]) * ratio,
                "y": start["y"] + (target["y"] - start["y"]) * ratio,
            }
        destinations[pid] = {"x": float(target["x"]), "y": float(target["y"])}
        actions[pid] = "cut"
        archetype[pid] = arch

    _outlet_score_for_meta = fb_roles.get("outlet_score")
    advance_trigger: AdvanceTrigger = {
        "condition": "ball_reaches_player",
        "T_game_seconds": float(t),
        "metadata": {
            "from_player_id": passer_id,
            "to_player_id": receiver_id,
            "target_coords": dict(receiver_coord),
            "outlet_score": (
                int(_outlet_score_for_meta)
                if _outlet_score_for_meta is not None
                else None
            ),
        },
    }

    start: StepStart = {
        "coords": dict(all_start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": {"owner_player_id": passer_id},
        "clock": {
            "clock_remaining": clock_remaining_at_start,
            "shot_clock_remaining": shot_clock_remaining_at_start,
        },
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": {"owner_player_id": receiver_id},
        "time_elapsed": t,
        "clock": {
            "clock_remaining": clock_remaining_at_start - t,
            "shot_clock_remaining": shot_clock_remaining_at_start - t,
        },
        "next": {"kind": "next_step", "index": next_step_index},
    }
    _stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def _build_cr_drive_resolution_animation_steps(
    turn_result: Dict[str, Any],
    game: Any,
) -> Optional[List[AnimationStep]]:
    """Phase 3: outlet (optional) + unified ``fb_drive_resolution`` drive steps."""
    import logging

    from BackEnd.engine.after_steal_fast_break_step_emitter import (
        _build_drive_step,
        _build_meet_drive_step,
        _override_fb_make_announcement,
    )
    from BackEnd.utils.animation_step_helpers import floor_step_t_to_traversal
    from BackEnd.engine.skeleton_step_emitter import _build_post_shot_sub_steps
    from BackEnd.engine.shot_micro_movements import inject_shot_micro_before_post_shot

    result_type = (turn_result.get("result_type") or "").upper()
    allowed = {
        "MAKE",
        "MISS",
        "BLOCK",
        "DEFENSIVE_STOP",
        "FOUL",
        "CHARGE",
        "DEAD BALL",
        "TURNOVER",
    }
    if result_type not in allowed:
        logging.warning(
            "🐛 [CR_DR] unsupported result_type=%s", result_type
        )
        return None

    fb_roles: Dict[str, Any] = turn_result.get("roles") or {}
    fb_drive = turn_result.get("fb_drive_resolution") or {}
    bh_id = (
        _safe_id(fb_roles.get("ball_handler"))
        or _safe_id(turn_result.get("ball_handler"))
        or _safe_id(turn_result.get("shooter_id"))
    )
    if not bh_id:
        return None

    off_team = getattr(game, "offense_team", None)
    def_team = getattr(game, "defense_team", None)
    off_lineup = getattr(off_team, "lineup", {}) if off_team else {}
    def_lineup = getattr(def_team, "lineup", {}) if def_team else {}
    is_away_offense = bool(fb_roles.get("is_away_offense"))

    all_start_coords = _all_player_start_coords(off_lineup, def_lineup)
    if bh_id not in all_start_coords:
        return None

    raw_end_coords = turn_result.get("cr_end_coords") or {}
    end_coords: Dict[str, GridCoord] = {}
    for pid, coord in raw_end_coords.items():
        if isinstance(coord, dict) and "x" in coord and "y" in coord:
            end_coords[str(pid)] = {"x": float(coord["x"]), "y": float(coord["y"])}
    for pid, sc in all_start_coords.items():
        end_coords.setdefault(pid, dict(sc))

    game_state = getattr(game, "game_state", {}) or {}
    clock_remaining = float(game_state.get("time_remaining", 0) or 0)
    shot_clock_remaining = float(game_state.get("shot_clock_remaining", 0) or 0)

    outlet_passer_id = fb_roles.get("outlet_passer")
    outlet_receiver_id = fb_roles.get("outlet_receiver")
    has_outlet_pass = bool(
        outlet_passer_id
        and outlet_receiver_id
        and str(outlet_passer_id) != str(outlet_receiver_id)
    )

    steps: List[AnimationStep] = []
    elapsed = 0.0
    clock_r = clock_remaining
    shot_r = shot_clock_remaining
    start_coords = dict(all_start_coords)

    if has_outlet_pass:
        passer_id = str(outlet_passer_id)
        receiver_id = str(outlet_receiver_id)
        passer_coord = all_start_coords.get(passer_id)
        receiver_coord = all_start_coords.get(receiver_id)
        if passer_coord is None or receiver_coord is None:
            return None
        outlet_step = _build_simplified_outlet_pass_step(
            passer_id=passer_id,
            receiver_id=receiver_id,
            passer_coord=passer_coord,
            receiver_coord=receiver_coord,
            all_start_coords=all_start_coords,
            fb_roles=fb_roles,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            is_away_offense=is_away_offense,
            clock_remaining_at_start=clock_r,
            shot_clock_remaining_at_start=shot_r,
            next_step_index=1,
        )
        steps.append(outlet_step)
        elapsed += float(outlet_step["end"]["time_elapsed"])
        clock_r = float(outlet_step["end"]["clock"]["clock_remaining"])
        shot_r = float(outlet_step["end"]["clock"]["shot_clock_remaining"])
        start_coords = dict(outlet_step["end"]["coords"])

    meet_coords = turn_result.get("meet_coords")
    outcome = fb_drive.get("outcome")
    stop_action = turn_result.get("stop_decision_action")
    is_neutral = outcome == "NEUTRAL"
    is_terminal = outcome in (
        "DEAD BALL",
        "O_FOUL",
        "D_FOUL",
        "CHARGE",
        "BLOCKING_FOUL",
    )
    uses_meet_step = is_neutral or is_terminal
    stealer_id = str(bh_id)

    if uses_meet_step and meet_coords:
        t_meet = float(
            turn_result.get("t_meet_game_seconds")
            or fb_drive.get("t_meet_game_seconds")
            or 1.0
        )
        meet_target = {
            "x": float(meet_coords["x"]),
            "y": float(meet_coords["y"]),
        }
        # Floor t_meet at the ball handler's real traversal to the meet so a
        # short backend meet time doesn't clamp him short and force the next
        # step to cover the residual instantly → jet.
        stealer_start = start_coords.get(stealer_id)
        if stealer_start:
            stealer_rate = _ag_grid_per_game_sec(
                _player_lookup_by_id(off_lineup, def_lineup, stealer_id), "standard"
            )
            t_meet = floor_step_t_to_traversal(
                t_meet, stealer_start, meet_target, stealer_rate
            )
        end_ann = None
        if result_type == "DEFENSIVE_STOP":
            end_ann = _build_nice_stop_announcement(
                turn_result, fb_roles, def_lineup, is_away_offense
            )
        meet_step = _build_meet_drive_step(
            start_coords=start_coords,
            end_coords=end_coords,
            stealer_id=stealer_id,
            meet_target=meet_target,
            is_away_offense=is_away_offense,
            clock_remaining=clock_r,
            shot_clock_remaining=shot_r,
            t_game_seconds=t_meet,
            next_step_index=len(steps) + (1 if result_type in ("MAKE", "MISS") else 0),
            fb_drive=fb_drive,
            end_announcement=end_ann,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
        )
        if result_type == "DEFENSIVE_STOP" or is_terminal:
            meet_step["end"]["next"] = {"kind": "end_of_turn"}
        if meet_step["start"].get("advance_trigger"):
            meet_step["start"]["advance_trigger"]["metadata"]["kind"] = (
                "covert_release_meet"
            )
        steps.append(meet_step)
        clock_r -= t_meet
        shot_r -= t_meet
        # Carry the meet step's RENDERED end coords forward, not the semantic
        # ``end_coords`` — otherwise the shot step assumes the shooter is already
        # on his full spot while the sprite is still en route → snap/jet.
        step_start_coords = dict(meet_step["end"]["coords"])
    else:
        step_start_coords = dict(start_coords)

    if result_type in ("MAKE", "MISS", "BLOCK"):
        if is_neutral and stop_action in ("shoot", "pass"):
            if stop_action == "pass":
                recv_id = turn_result.get("pass_receiver_id")
                if recv_id and recv_id in step_start_coords:
                    from BackEnd.utils.transition_bridge import build_pass_step

                    try:
                        pass_step = build_pass_step(
                            off_lineup=off_lineup,
                            def_lineup=def_lineup,
                            start_coords=step_start_coords,
                            passer_id=stealer_id,
                            receiver_id=str(recv_id),
                            clock_remaining_at_start=clock_r,
                            shot_clock_remaining_at_start=shot_r,
                            next_step_index=len(steps),
                            pass_speed_grid_per_game_sec=float(
                                PASS_GRID_SPOTS_PER_GAME_SECOND
                            ),
                            metadata_reason="covert_release_stop_pass",
                        )
                        steps.append(pass_step)
                        clock_r = pass_step["end"]["clock"]["clock_remaining"]
                        shot_r = pass_step["end"]["clock"]["shot_clock_remaining"]
                        step_start_coords = dict(pass_step["end"]["coords"])
                        stealer_id = str(recv_id)
                    except ValueError:
                        pass

            bh_target_raw = turn_result.get("bh_target") or step_start_coords.get(
                stealer_id, meet_coords or {}
            )
            bh_target = {
                "x": float(bh_target_raw["x"]),
                "y": float(bh_target_raw["y"]),
            }
            t_shot = float(turn_result.get("t_shooter_game_seconds") or 0.5)
            shot_end_coords = dict(step_start_coords)
            shot_end_coords[stealer_id] = dict(bh_target)
            # Extend the gather beat if the shooter still has real ground to
            # cover to ``bh_target`` (meet ≠ shot spot) so he drives in at his
            # natural rate instead of jetting.
            gather_t = max(0.35, t_shot * 0.15)
            shooter_now = step_start_coords.get(stealer_id)
            if shooter_now:
                shooter_rate = _ag_grid_per_game_sec(
                    _player_lookup_by_id(off_lineup, def_lineup, stealer_id), "standard"
                )
                gather_t = floor_step_t_to_traversal(
                    gather_t, shooter_now, bh_target, shooter_rate
                )
            shot_drive = _build_drive_step(
                start_coords=step_start_coords,
                end_coords=shot_end_coords,
                stealer_id=stealer_id,
                bh_target=bh_target,
                is_away_offense=is_away_offense,
                clock_remaining=clock_r,
                shot_clock_remaining=shot_r,
                t_game_seconds=gather_t,
                next_step_index=len(steps) + 1,
                off_lineup=off_lineup,
                def_lineup=def_lineup,
            )
            shot_drive["start"]["action"][stealer_id] = "shoot"
            if shot_drive["start"].get("advance_trigger"):
                shot_drive["start"]["advance_trigger"]["metadata"]["kind"] = (
                    "covert_release_drive"
                )
            steps.append(shot_drive)
        else:
            bh_target_raw = turn_result.get("bh_target") or end_coords.get(stealer_id)
            bh_target = {
                "x": float(bh_target_raw["x"]),
                "y": float(bh_target_raw["y"]),
            }
            t_drive = float(
                turn_result.get("t_shooter_game_seconds")
                or fb_drive.get("t_drive_game_seconds")
                or 1.0
            )
            trigger_meta = {
                "target_player_id": stealer_id,
                "target_coords": dict(bh_target),
                "kind": "covert_release_drive",
            }
            knots = fb_drive.get("bh_path_knots")
            if knots and fb_drive.get("outcome") == "POS_O":
                trigger_meta["path_knots"] = knots
                segs = fb_drive.get("path_segment_game_seconds")
                if segs:
                    trigger_meta["path_segment_game_seconds"] = segs
            drive_step = _build_drive_step(
                start_coords=start_coords,
                end_coords=end_coords,
                stealer_id=stealer_id,
                bh_target=bh_target,
                is_away_offense=is_away_offense,
                clock_remaining=clock_r if has_outlet_pass else clock_remaining,
                shot_clock_remaining=shot_r if has_outlet_pass else shot_clock_remaining,
                t_game_seconds=t_drive,
                next_step_index=len(steps) + 1,
                off_lineup=off_lineup,
                def_lineup=def_lineup,
                archetypes_override=fb_drive.get("defender_archetypes"),
            )
            drive_step["start"]["advance_trigger"]["metadata"] = trigger_meta
            steps.append(drive_step)

        inject_shot_micro_before_post_shot(
            steps, turn_result, off_lineup, def_lineup, is_away_offense
        )
        _build_post_shot_sub_steps(
            steps, turn_result, off_lineup, def_lineup, is_away_offense
        )
        if result_type == "MAKE":
            _override_fb_make_announcement(steps)

    return steps or None


def _ag_grid_per_game_sec(player: Any, archetype: PlayerArchetype) -> float:
    """Look up grid/game-sec rate for the given player + archetype.

    ``ag_to_grid_per_game_sec`` is the base AG curve (AG=50 → 16). Archetype
    multipliers come from constants (sprint=14/12, drive=1.0, shot_motion=10/12).
    Matches the rate calculation in ``calc_ag_segment_seconds``.
    """
    try:
        from BackEnd.utils.shared import ag_to_grid_per_game_sec
        from BackEnd.constants import (
            BURST_GRID_PER_GAME_SEC,
            CRUISE_GRID_PER_GAME_SEC,
            STANDARD_GRID_PER_GAME_SEC,
            SHOT_MOTION_GRID_PER_GAME_SEC,
            SPRINT_GRID_PER_GAME_SEC,
        )
    except Exception:
        # Test-context fallback: AG=50 sprint ≈ 18.67 grid/sec.
        return 18.67

    if player is None:
        ag = 50
    else:
        attrs = getattr(player, "attributes", None) or {}
        ag = attrs.get("AG", 50) if isinstance(attrs, dict) else 50
    ag_scale = float(ag_to_grid_per_game_sec(ag)) / float(STANDARD_GRID_PER_GAME_SEC)
    if archetype == "standard":
        return STANDARD_GRID_PER_GAME_SEC * ag_scale
    if archetype in ("shot_motion", "compressed_hco"):
        return SHOT_MOTION_GRID_PER_GAME_SEC * ag_scale
    if archetype == "sprint":
        return SPRINT_GRID_PER_GAME_SEC * ag_scale
    if archetype == "burst":
        return BURST_GRID_PER_GAME_SEC * ag_scale
    if archetype == "cruise":
        return CRUISE_GRID_PER_GAME_SEC * ag_scale
    # default / stationary / unknown → base AG rate.
    return STANDARD_GRID_PER_GAME_SEC * ag_scale


def _traversal_seconds(start: GridCoord, end: GridCoord, rate: float) -> float:
    """Time to traverse start→end at a given grid/game-sec rate."""
    if rate <= 0:
        return 0.0
    return _euclid(start, end) / rate


def _stamp_tween_durations(
    start: Dict[str, Any],
    end_coords: Dict[str, GridCoord],
    step_t: float,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> None:
    """Stamp per-player tween durations on ``start["tween_durations"]``
    (in game-seconds). Mirrors the helper in ``rim_runner_step_emitter``.

    For each player who moves: ``duration = min(distance / rate, step_t)``.
    Stationary players omitted (no tween fires for zero-distance anyway).
    Without this, the playback engine falls back to step T per player,
    which stretches fast finishers' tweens — visible "lazy drift" feel.
    """
    start_coords = start.get("coords") or {}
    archetype = start.get("archetype") or {}
    durations: Dict[str, float] = {}
    for pid, sc in start_coords.items():
        ec = end_coords.get(pid)
        if ec is None:
            continue
        dist = _euclid(sc, ec)
        if dist < 1e-6:
            continue
        arch = archetype.get(pid, "standard")
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, arch)
        if rate <= 0:
            continue
        durations[pid] = float(min(dist / rate, step_t))
    if durations:
        start["tween_durations"] = durations


def _build_outcome_step(
    *,
    turn_result: Dict[str, Any],
    fb_roles: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    animations: List[Dict[str, Any]],
    step_start_coords: Dict[str, GridCoord],
    ball_owner_id: str,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
) -> AnimationStep:
    """Step 1: outcome step. Computes per-player end coords, gating player,
    and outcome `next` pointer based on the FB result_type.
    """
    result_type = (turn_result.get("result_type") or "").upper()
    is_defensive_stop = result_type == "DEFENSIVE_STOP"

    bh = fb_roles.get("ball_handler")
    bh_id = _safe_id(bh)
    stopper_id = turn_result.get("stopper_id") or fb_roles.get("stopper_id")
    stopper = _player_lookup_by_id(off_lineup, def_lineup, stopper_id)

    # End coords: prefer animations[].movement[-1] (already computed by the
    # legacy animator); fall back to player.coords (no movement).
    end_coords: Dict[str, GridCoord] = {}
    for pid, start_coord in step_start_coords.items():
        anim_end = _movement_end_coord(animations, pid)
        end_coords[pid] = anim_end if anim_end is not None else start_coord

    # Per-player action + archetype.
    actions: Dict[str, PlayerAction] = {}
    archetype: Dict[str, PlayerArchetype] = {}
    destinations: Dict[str, Optional[GridCoord]] = {}
    for pid, coord in step_start_coords.items():
        actions[pid] = "stationary"
        archetype[pid] = "stationary"
        destinations[pid] = end_coords.get(pid, coord)

    if bh_id:
        # FB BH is sprinting up the floor; the FB run-up dominates the wind-up
        # even for shot outcomes. AG-scaled via `sprint` multiplier to match
        # RR/Triangle FB pacing.
        if is_defensive_stop:
            actions[bh_id] = "handle_ball"
            archetype[bh_id] = "sprint"
        elif result_type in ("MAKE", "MISS", "BLOCK"):
            actions[bh_id] = "shoot"
            archetype[bh_id] = "sprint"
        else:
            # FOUL / STEAL / DEAD_BALL — BH still sprints toward outcome spot.
            actions[bh_id] = "handle_ball"
            archetype[bh_id] = "sprint"

    if stopper_id:
        sid = str(stopper_id)
        if sid in actions:
            actions[sid] = "guard_ball"
            archetype[sid] = "standard"

    # Defenders default to guard_offball (overrides "stationary" only when
    # they have a movement end recorded by the animator).
    for player in def_lineup.values():
        if player is None:
            continue
        pid = _safe_id(player)
        if pid is None or pid not in actions:
            continue
        if pid == str(stopper_id) if stopper_id else False:
            continue
        if pid == bh_id:
            continue
        if _movement_end_coord(animations, pid) is not None:
            actions[pid] = "guard_offball"
            archetype[pid] = "standard"

    # Non-BH offensive players: when the animator gives them a movement end
    # (i.e. they're not actually stationary), tag them as `cut` / `sprint`
    # so the FE renders them running with the play instead of treating them
    # as stationary and snap-rendering to the end position. Sprint pace
    # matches the BH and RR/Triangle FB offensive runners.
    for player in off_lineup.values():
        if player is None:
            continue
        pid = _safe_id(player)
        if pid is None or pid not in actions:
            continue
        if pid == bh_id:
            continue
        if _movement_end_coord(animations, pid) is not None:
            actions[pid] = "cut"
            archetype[pid] = "sprint"

    # Gating player + T. BH runs at sprint pace (AG-scaled) for the FB attack.
    bh_coord_start = step_start_coords.get(bh_id) if bh_id else None
    bh_coord_end = end_coords.get(bh_id) if bh_id else None
    bh_traversal = (
        _traversal_seconds(bh_coord_start, bh_coord_end, _ag_grid_per_game_sec(bh, "sprint"))
        if bh_coord_start and bh_coord_end and bh
        else 0.0
    )

    if is_defensive_stop and stopper:
        stopper_pid = str(stopper_id)
        st_start = step_start_coords.get(stopper_pid)
        st_end = end_coords.get(stopper_pid)
        st_traversal = (
            _traversal_seconds(st_start, st_end, _ag_grid_per_game_sec(stopper, "standard"))
            if st_start and st_end
            else 0.0
        )
        if st_traversal >= bh_traversal:
            gate_id = stopper_pid
            gate_coord = st_end or step_start_coords[stopper_pid]
            t = st_traversal
        else:
            gate_id = bh_id
            gate_coord = bh_coord_end or bh_coord_start
            t = bh_traversal
    else:
        gate_id = bh_id
        gate_coord = bh_coord_end or bh_coord_start
        t = bh_traversal

    # Defensive fallback if gating data is missing.
    if not gate_id or not gate_coord:
        gate_id = bh_id or ball_owner_id or "unknown"
        gate_coord = bh_coord_end or bh_coord_start or {"x": 50.0, "y": 25.0}
        t = max(t, 0.0)

    # Schema-compliant interrupted-coord clamp: any player whose intended
    # destination (read from legacy animator's animations[].movement[-1])
    # exceeds what they could traverse at their archetype rate × T gets
    # clamped to start + (rate × T) along the path. Without this, non-gate
    # players in step 1 (especially the FB shot path, where multiple
    # players have full destinations near the rim) would appear to teleport
    # because the legacy animator pre-computes full destinations regardless
    # of T. Rebinds end_coords[pid] (does NOT mutate the dict in place) so
    # destinations[pid] retains the original target reference.
    # Per-player archetype is critical: T was computed from the gating
    # player's archetype rate (BH at sprint). If the clamp uses a slower
    # archetype, fast-moving players (BH at sprint) get pulled up short of
    # their target. Using `archetype[pid]` ensures each player's clamp
    # matches their actual movement rate on this step.
    for pid, start_coord in step_start_coords.items():
        target = end_coords.get(pid)
        if target is None or start_coord is None:
            continue
        dx = target["x"] - start_coord["x"]
        dy = target["y"] - start_coord["y"]
        dist = (dx * dx + dy * dy) ** 0.5
        if dist == 0.0:
            continue
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        arch = archetype.get(pid, "standard")
        rate = _ag_grid_per_game_sec(player, arch) if player else 12.0
        max_traversal = rate * t
        if dist > max_traversal:
            ratio = max_traversal / dist
            end_coords[pid] = {
                "x": start_coord["x"] + dx * ratio,
                "y": start_coord["y"] + dy * ratio,
            }

    advance_trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": str(gate_id),
            "target_coords": dict(gate_coord),
        },
    }

    next_step = _resolve_outcome_next(turn_result)

    ball_start: BallState = {"owner_player_id": ball_owner_id}
    ball_end: BallState = {"owner_player_id": ball_owner_id}

    clock_start: ClockState = {
        "clock_remaining": clock_remaining_at_start,
        "shot_clock_remaining": shot_clock_remaining_at_start,
    }
    clock_end: ClockState = {
        "clock_remaining": clock_remaining_at_start - t,
        "shot_clock_remaining": shot_clock_remaining_at_start - t,
    }

    start: StepStart = {
        "coords": dict(step_start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball_start,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_end,
        "time_elapsed": t,
        "clock": clock_end,
        "next": next_step,
    }
    _stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


# --- Step-back step (DEFENSIVE_STOP only) ----------------------------------


_LINEUP_ORDER = ["PG", "SG", "SF", "PF", "C"]


def _resolve_position_from_lineup(
    player_id: Optional[str],
    lineup: Dict[str, Any],
) -> Optional[str]:
    """Find a player's position by matching their player_id against the
    lineup dict's keys. Authoritative — does NOT rely on the Player object's
    `.position` attribute, which is not always populated in real-game
    contexts.
    """
    if not player_id or not lineup:
        return None
    target = str(player_id)
    for pos, player in lineup.items():
        if player is None:
            continue
        pid = getattr(player, "player_id", None)
        if pid is not None and str(pid) == target:
            return pos
    return None


def _flip_x_for_offense(coord: GridCoord, is_away_offense: bool) -> GridCoord:
    """Mirror x around 50 when offense is away (HCO_STRING_SPOTS are stored in
    home orientation)."""
    if not is_away_offense:
        return {"x": float(coord["x"]), "y": float(coord["y"])}
    return {"x": float(100 - coord["x"]), "y": float(coord["y"])}


def _alias_map_excluding(excluded_positions: List[str]) -> Dict[str, str]:
    """Mirror of ``_alias_map`` in dynamic_hct.py / `_build_set_play_alias_map`,
    extended to exclude multiple positions (for the 2-BHs case where both FB
    BH and HCO BH are excluded from the pos slots).
    """
    excluded = {p.upper() for p in excluded_positions if p}
    remaining = [p for p in _LINEUP_ORDER if p not in excluded]
    return {f"pos{i + 1}": pos for i, pos in enumerate(remaining)}


def _hco_bh_position(off_lineup: Dict[str, Any]) -> str:
    """Default HCO BH = team's PG (canonical for the vast majority of HCO
    playcalls). Set-play-specific BH detection is a future enhancement.
    """
    return "PG"


def _pick_hco_bh_target_near_fb_bh(
    fb_bh_coord: GridCoord,
    is_away_offense: bool,
) -> GridCoord:
    """Place the HCO BH within ``HCO_SETUP_HCO_BH_RADIUS`` of the FB BH AND
    on the same horizontal half (home offense → x ≥ 50; away → x ≤ 50). Tries
    a few random offsets, falls back to a deterministic offset if none fit.
    """
    radius = float(HCO_SETUP_HCO_BH_RADIUS)
    for _ in range(20):
        angle = random.uniform(0.0, 2.0 * math.pi)
        dist = random.uniform(0.0, radius)
        tx = fb_bh_coord["x"] + dist * math.cos(angle)
        ty = fb_bh_coord["y"] + dist * math.sin(angle)
        tx = max(4.0, min(97.0, tx))
        ty = max(1.0, min(49.0, ty))
        if (not is_away_offense and tx >= 50.0) or (is_away_offense and tx <= 50.0):
            return {"x": tx, "y": ty}
    # Deterministic fallback: 5 grid units away from the FB BH on the same
    # horizontal half, slight y offset.
    fallback_x = fb_bh_coord["x"] - 5.0 if not is_away_offense else fb_bh_coord["x"] + 5.0
    fallback_x = max(50.0, fallback_x) if not is_away_offense else min(50.0, fallback_x)
    fallback_x = max(4.0, min(97.0, fallback_x))
    fallback_y = max(1.0, min(49.0, fb_bh_coord["y"] + 3.0))
    return {"x": fallback_x, "y": fallback_y}


def _build_step_back_step(
    *,
    turn_result: Dict[str, Any],
    fb_roles: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    step_start_coords: Dict[str, GridCoord],
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
) -> Optional[AnimationStep]:
    """Build the step-back / HCO-setup step (step 2 in the DEFENSIVE_STOP
    branch). See module docstring + Step_By_Step_System.md for the spec.
    """
    import logging
    fb_bh = fb_roles.get("ball_handler")
    if fb_bh is None:
        return None
    fb_bh_id = _safe_id(fb_bh)
    # Resolve position from lineup (authoritative), not from Player.position
    # (which is not always set on real-game Player objects).
    fb_bh_pos = _resolve_position_from_lineup(fb_bh_id, off_lineup)
    if fb_bh_pos is None:
        # Fallback: try Player.position attribute as a last resort.
        attr_pos = (getattr(fb_bh, "position", None) or "").upper()
        if attr_pos in _LINEUP_ORDER:
            fb_bh_pos = attr_pos
    if fb_bh_pos not in _LINEUP_ORDER:
        return None

    is_away_offense = bool(fb_roles.get("is_away_offense"))

    # Determine HCO BH (default = PG) and whether they're the same as FB BH.
    hco_bh_pos = _hco_bh_position(off_lineup)
    same_bh = fb_bh_pos == hco_bh_pos
    hco_bh = off_lineup.get(hco_bh_pos) if not same_bh else fb_bh
    hco_bh_id = _safe_id(hco_bh) if hco_bh is not None else None

    # FB BH → random deep frontcourt spot.
    deep_spot_name = random.choice(HCO_SETUP_OFFENSE_BH_DEEP_SPOTS)
    deep_coord_home = HCO_STRING_SPOTS.get(deep_spot_name)
    if deep_coord_home is None:
        return None
    fb_bh_target = _flip_x_for_offense(deep_coord_home, is_away_offense)

    # Per-offense-position end coords.
    off_pos_to_target: Dict[str, GridCoord] = {fb_bh_pos: fb_bh_target}

    # HCO BH (when different): within HCO_SETUP_HCO_BH_RADIUS of FB BH, same
    # horizontal half.
    if not same_bh and hco_bh is not None:
        off_pos_to_target[hco_bh_pos] = _pick_hco_bh_target_near_fb_bh(
            fb_bh_target, is_away_offense
        )

    # alias_map excludes FB BH's position; also excludes HCO BH's when different.
    excluded = [fb_bh_pos]
    if not same_bh:
        excluded.append(hco_bh_pos)
    alias_map = _alias_map_excluding(excluded)

    for pos_key, off_pos in alias_map.items():
        spot_name = HCO_SETUP_OFFENSE_POS_SPOTS.get(pos_key)
        if spot_name is None:
            # In the 2-BHs case, alias map has only pos1..pos3; pos4 dropped.
            # In the 1-BH case, all 4 should be present. If not, skip.
            continue
        spot_coord_home = HCO_STRING_SPOTS.get(spot_name)
        if spot_coord_home is None:
            continue
        off_pos_to_target[off_pos] = _flip_x_for_offense(spot_coord_home, is_away_offense)

    # Build per-player end coords. Defenders mirror with same-lineup-position
    # matchup (def at pos X goes to where off at pos X goes).
    end_coords: Dict[str, GridCoord] = {}
    for pos in _LINEUP_ORDER:
        target = off_pos_to_target.get(pos)
        if target is None:
            continue
        off_player = off_lineup.get(pos)
        if off_player is not None:
            off_pid = _safe_id(off_player)
            if off_pid:
                end_coords[off_pid] = dict(target)
        def_player = def_lineup.get(pos)
        if def_player is not None:
            def_pid = _safe_id(def_player)
            if def_pid:
                end_coords[def_pid] = dict(target)

    # Players whose target wasn't computed (shouldn't happen in 5v5) hold their
    # step-1 end position.
    for pid, start in step_start_coords.items():
        end_coords.setdefault(pid, dict(start))

    # T = max traversal time at sprint rate, AG-driven where possible.
    t = 0.0
    gate_id: Optional[str] = None
    gate_coord: Optional[GridCoord] = None
    for pid, start in step_start_coords.items():
        end = end_coords.get(pid, start)
        dx = end["x"] - start["x"]
        dy = end["y"] - start["y"]
        dist = (dx * dx + dy * dy) ** 0.5
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, "sprint") if player else 12.0
        traversal = dist / rate if rate > 0 else 0.0
        if traversal > t:
            t = traversal
            gate_id = pid
            gate_coord = end

    # Floor to 0.4 game-seconds so the visual beat is perceptible even if every
    # player happens to barely move (degenerate cases / mocks).
    t = max(t, 0.4)

    if gate_id is None or gate_coord is None:
        gate_id = fb_bh_id or "unknown"
        gate_coord = fb_bh_target

    advance_trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": str(gate_id),
            "target_coords": dict(gate_coord),
        },
    }

    # Per-player action + archetype: FB BH retains ball (handle_ball);
    # everyone else cuts at sprint pace.
    actions: Dict[str, PlayerAction] = {}
    archetype: Dict[str, PlayerArchetype] = {}
    destinations: Dict[str, Optional[GridCoord]] = {}
    for pid, start in step_start_coords.items():
        end = end_coords.get(pid, start)
        destinations[pid] = end
        if fb_bh_id and pid == fb_bh_id:
            actions[pid] = "handle_ball"
        else:
            actions[pid] = "cut"
        archetype[pid] = "standard"

    ball_state: BallState = (
        {"owner_player_id": fb_bh_id} if fb_bh_id else {"owner_player_id": ""}
    )

    clock_start: ClockState = {
        "clock_remaining": clock_remaining_at_start,
        "shot_clock_remaining": shot_clock_remaining_at_start,
    }
    clock_end: ClockState = {
        "clock_remaining": clock_remaining_at_start - t,
        "shot_clock_remaining": shot_clock_remaining_at_start - t,
    }

    start: StepStart = {
        "coords": dict(step_start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball_state,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_state,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": 999},
    }
    _stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def _build_nice_stop_announcement(
    turn_result: Dict[str, Any],
    fb_roles: Dict[str, Any],
    def_lineup: Dict[str, Any],
    is_away_offense: bool,
) -> Announcement:
    """``"Great Stop!"`` announcement payload for the end of the defensive-stop
    motion step. Backend is the single source of truth: stamps the final text,
    resolves the defending team to ``home``/``away`` (so the FE secondary
    overlay can color the stripe via ``gameStore.getColors()``), and carries
    the stinger SFX via ``meta.sfx`` per SFX_System.md §FB Defensive
    Stop Announce. FE drops its legacy "Nice Stop!" text-rewrite branch.
    """
    stopper_id = turn_result.get("stopper_id") or fb_roles.get("stopper_id")
    stopper = _player_lookup_by_id({}, def_lineup, stopper_id) if stopper_id else None
    player_data: Optional[Dict[str, Any]] = None
    if stopper is not None:
        player_data = {
            "playerId": _safe_id(stopper),
            "photo": getattr(stopper, "photo", None),
            "teamName": None,  # populated client-side from team lookup
        }
    elif stopper_id:
        player_data = {
            "playerId": str(stopper_id),
            "photo": None,
            "teamName": None,
        }
    # Defending team relative to offense: opposite of `is_away_offense`.
    defense_team = "home" if is_away_offense else "away"
    return {
        "text": "Great Stop!",
        "team": defense_team,
        "player_data": player_data,
        "meta": {"sfx": "fb_defensive_stop"},
        "style": "secondary",
        "hold_ms": 1000,
    }


# --- Top-level emitter -----------------------------------------------------


def build_covert_release_animation_steps(
    turn_result: Dict[str, Any],
    game: Any,
) -> Optional[List[AnimationStep]]:
    """Convert a Covert Release FB turn_result into AnimationStep[].

    Returns None when required data is missing (graceful degradation
    during parallel-build phase — caller falls back to legacy renderer).
    """
    if turn_result.get("fb_drive_resolution"):
        from BackEnd.constants import USE_FB_DRIVE_RESOLUTION_CR

        if USE_FB_DRIVE_RESOLUTION_CR:
            steps = _build_cr_drive_resolution_animation_steps(turn_result, game)
            if steps is not None:
                from BackEnd.utils.shared import canonicalize_post_shot_overlays

                canonicalize_post_shot_overlays(turn_result)
                return steps

    fb_roles: Dict[str, Any] = turn_result.get("roles") or {}

    fast_break_play = turn_result.get("fast_break_play")
    if fast_break_play != "covert_release":
        import logging
        logging.warning(
            "🚨 [CR EMITTER NULL] guard=fast_break_play_mismatch fast_break_play=%s "
            "result_type=%s — FE will fall to LEGACY_HANDLER",
            fast_break_play, turn_result.get("result_type"),
        )
        return None

    off_team = getattr(game, "offense_team", None)
    def_team = getattr(game, "defense_team", None)
    off_lineup = getattr(off_team, "lineup", {}) if off_team else {}
    def_lineup = getattr(def_team, "lineup", {}) if def_team else {}

    bh = fb_roles.get("ball_handler")
    bh_id = _safe_id(bh)
    if not bh_id:
        import logging
        logging.warning(
            "🚨 [CR EMITTER NULL] guard=missing_bh_id result_type=%s "
            "fb_roles_keys=%s bh_obj=%s — FE will fall to LEGACY_HANDLER",
            turn_result.get("result_type"),
            list(fb_roles.keys()) if isinstance(fb_roles, dict) else None,
            type(bh).__name__ if bh is not None else "None",
        )
        return None

    outlet_passer_id = fb_roles.get("outlet_passer")
    outlet_receiver_id = fb_roles.get("outlet_receiver")
    is_away_offense = bool(fb_roles.get("is_away_offense"))

    # All-player start coords. Per the cross-turn coord contract in
    # `_documentation_master/projects/Animation_System_Updated.md`, step 0
    # START reads `player.coords` (= prior turn's last step end.coords as
    # written by `sync_lineup_coords_from_turn`). `shot_manager` no longer
    # mutates `player.coords` mid-resolution, so live coords are trustworthy.
    all_start_coords = _all_player_start_coords(off_lineup, def_lineup)
    if not all_start_coords:
        import logging
        logging.warning(
            "🚨 [CR EMITTER NULL] guard=empty_all_start_coords result_type=%s "
            "off_lineup_size=%d def_lineup_size=%d — FE will fall to LEGACY_HANDLER",
            turn_result.get("result_type"),
            len(off_lineup or {}), len(def_lineup or {}),
        )
        return None

    game_state = getattr(game, "game_state", {}) or {}
    clock_remaining = float(game_state.get("time_remaining", 0) or 0)
    shot_clock_remaining = float(game_state.get("shot_clock_remaining", 0) or 0)

    steps: List[AnimationStep] = []
    elapsed = 0.0

    # Step 0: outlet pass (skipped when rebounder == release player).
    has_outlet_pass = bool(
        outlet_passer_id
        and outlet_receiver_id
        and str(outlet_passer_id) != str(outlet_receiver_id)
    )

    if has_outlet_pass:
        passer_id = str(outlet_passer_id)
        receiver_id = str(outlet_receiver_id)
        passer_coord = all_start_coords.get(passer_id)
        receiver_coord = all_start_coords.get(receiver_id)
        if passer_coord is None or receiver_coord is None:
            import logging
            logging.warning(
                "🚨 [CR EMITTER NULL] guard=missing_outlet_coords result_type=%s "
                "passer_id=%s passer_coord=%s receiver_id=%s receiver_coord=%s "
                "all_start_coords_size=%d — FE will fall to LEGACY_HANDLER",
                turn_result.get("result_type"),
                passer_id, passer_coord, receiver_id, receiver_coord,
                len(all_start_coords),
            )
            return None

        outlet_step = _build_outlet_pass_step(
            passer_id=passer_id,
            receiver_id=receiver_id,
            passer_coord=passer_coord,
            receiver_coord=receiver_coord,
            all_start_coords=all_start_coords,
            fb_roles=fb_roles,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            is_away_offense=bool(fb_roles.get("is_away_offense")),
            clock_remaining_at_start=clock_remaining,
            shot_clock_remaining_at_start=shot_clock_remaining,
            is_first_step=True,
            next_step_index=1,
        )
        steps.append(outlet_step)
        elapsed += float(outlet_step["end"]["time_elapsed"])

    # Step 1 (or step 0 if no outlet pass): outcome.
    outcome_start_coords = (
        dict(steps[-1]["end"]["coords"]) if steps else dict(all_start_coords)
    )
    ball_owner_for_outcome = str(outlet_receiver_id) if has_outlet_pass else bh_id

    outcome_step = _build_outcome_step(
        turn_result=turn_result,
        fb_roles=fb_roles,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        animations=turn_result.get("animations") or [],
        step_start_coords=outcome_start_coords,
        ball_owner_id=ball_owner_for_outcome,
        clock_remaining_at_start=clock_remaining - elapsed,
        shot_clock_remaining_at_start=shot_clock_remaining - elapsed,
    )
    steps.append(outcome_step)
    elapsed += float(outcome_step["end"]["time_elapsed"])

    # DEFENSIVE_STOP: attach "Nice Stop!" announcement to step 1's end.
    # The FB turn terminates at step 1 via the implicit-end pointer set by
    # `_resolve_outcome_next`. Cross-court HCO setup is handled by the
    # FOLLOWING HCO turn's bring-up tween (populated by game_manager from
    # post-FB `player.coords`), so no step 2 step-back is built here.
    # Other outcomes (MAKE/MISS/BLOCK/FOUL/etc.) terminate via their
    # `turn_stop` next pointer set by `_resolve_outcome_next`.
    result_type = (turn_result.get("result_type") or "").upper()
    if result_type == "DEFENSIVE_STOP":
        outcome_step["end"]["announcement"] = _build_nice_stop_announcement(
            turn_result, fb_roles, def_lineup, is_away_offense
        )

    # Re-canonicalize the post-shot overlay maps now that `fb_roles` (which
    # includes `outlet_passer`) is attached to turn_result. shot_manager
    # already canonicalized at its return point, but it didn't know about
    # the outlet_passer role yet — that comes from the FB caller. See
    # `canonicalize_post_shot_overlays` in shared.py for the role priority
    # rules. Idempotent.
    from BackEnd.utils.shared import canonicalize_post_shot_overlays
    canonicalize_post_shot_overlays(turn_result)

    _bh_id_str = str(bh_id) if bh_id else None

    # Movement #1 (post-shot positioning): split path based on result_type.
    #   - MAKE/MISS/BLOCK: append variant-aware schema-pure post-shot
    #     sub-steps ([ball_flight] → variant → [hold] / [bounce]) via
    #     `_build_post_shot_sub_steps`. The helper rewires outcome_step's
    #     next pointer from `turn_stop SHOT_ATTEMPT` to the new sub-steps
    #     and flags the terminal turn_stop with `schema_rendered_arc:true`
    #     so FE `runShotAttempt` short-circuits (no double arc/hold). SFX,
    #     announcements, and rebound-cluster overlays are handled by the
    #     schema sub-steps and shared.py's overlay-apply chain — NOT by
    #     `_apply_post_shot_overlay` on outcome_step (see shared.py:2982-3004
    #     for why schema MAKE/MISS/BLOCK intentionally suppresses that).
    #   - DEFENSIVE_STOP: no shot resolved, no rebounder placement.
    #   - Other (FOUL / DEAD_BALL_TURNOVER / etc.): keep the legacy overlay
    #     + clamp on outcome_step until those paths migrate.
    if result_type in ("MAKE", "MISS", "BLOCK"):
        try:
            from BackEnd.engine.skeleton_step_emitter import _build_post_shot_sub_steps
            from BackEnd.engine.shot_micro_movements import inject_shot_micro_before_post_shot
            inject_shot_micro_before_post_shot(
                steps, turn_result, off_lineup, def_lineup, is_away_offense,
            )
            _build_post_shot_sub_steps(
                steps, turn_result, off_lineup, def_lineup, is_away_offense,
            )
        except Exception:
            import logging
            logging.exception("CR FB post-shot sub-steps failed")
    elif result_type != "DEFENSIVE_STOP":
        _apply_post_shot_overlay(outcome_step, turn_result)
        # Clamp the overlay-derived end coords to each player's archetype
        # rate × step T so non-gate movers don't appear to teleport from
        # their step 0 drift positions to the rim cluster. Without this,
        # the schema engine tweens linearly start→end over T, which means a
        # support cutter starting at midcourt ends up "sprinting" at
        # 25+ grid/sec to keep up with the BH. The overlay still sets the
        # *intended* destination (sync writes it to player.coords post-turn,
        # so the next turn's DREB / inbound sees the correct positions);
        # the visible step 1 motion just stops where sprint × T would land.
        _clamp_step_end_coords_to_archetype(
            outcome_step, off_lineup, def_lineup
        )

    from BackEnd.engine.dead_ball_fumble import inject_dead_ball_fumble_before_turn_stop

    inject_dead_ball_fumble_before_turn_stop(
        steps, turn_result, away_offense=is_away_offense,
    )

    return steps


def _clamp_step_end_coords_to_archetype(
    step: AnimationStep,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> None:
    """Clamp each player's end coord to start + (archetype rate × T) along the
    path. Reads the archetype label already set on the step and uses the
    matching AG-driven rate. Players whose intended destination is within
    reach are unchanged; over-reaching players are pulled back along the
    start→target line to the rate-limited position.

    Stationary archetype is a no-op (rate-irrelevant). Players missing from
    either coord map are skipped.
    """
    start_coords = step.get("start", {}).get("coords") or {}
    end_coords = step.get("end", {}).get("coords") or {}
    archetypes = step.get("start", {}).get("archetype") or {}
    t = float(step.get("end", {}).get("time_elapsed") or 0.0)
    if t <= 0.0:
        return

    for pid, start in start_coords.items():
        target = end_coords.get(pid)
        if not target or not start:
            continue
        arch = archetypes.get(pid) or "standard"
        if arch == "stationary":
            continue
        dx = float(target["x"]) - float(start["x"])
        dy = float(target["y"]) - float(start["y"])
        dist = (dx * dx + dy * dy) ** 0.5
        if dist == 0.0:
            continue
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, arch) if player else 12.0
        max_traversal = rate * t
        if dist > max_traversal:
            ratio = max_traversal / dist
            end_coords[pid] = {
                "x": float(start["x"]) + dx * ratio,
                "y": float(start["y"]) + dy * ratio,
            }


def _apply_post_shot_overlay(step: AnimationStep, turn_result: Dict[str, Any]) -> None:
    """Override the outcome step's `end.coords` for players in shot_manager's
    post-shot overlay maps. See
    `_documentation_master/projects/Animation_System_Updated.md` cross-turn
    coord contract.

    Exempts the outlet passer (rebounder) from the rebounder-position overlay:
    `shot_manager.offense_rebounders` includes every non-get-back offensive
    player (including the rebounder for FB MAKE/MISS, since shot_manager has
    no concept of "outlet passer"), but per the CR design the rebounder/outlet
    passer stays at their rebound-site / outlet position rather than crashing
    the rim. Without this exemption, the rebounder teleports ~80 grid units
    to (HOME_RIM) on the outcome step.
    """
    # Role-exclusivity is enforced upstream by `canonicalize_post_shot_overlays`
    # (called from shot_manager and again from this emitter before _build_outcome_step).
    # By the time we read the overlay maps here, the shooter / outlet passer /
    # release / get-back players are already in their canonical maps only —
    # no need for per-overlay exemption logic.
    end_coords = step.get("end", {}).get("coords")
    start_actions = step.get("start", {}).get("action")
    start_archetype = step.get("start", {}).get("archetype")
    if not isinstance(end_coords, dict):
        return
    # Order is load-bearing — see TURN_COORDS_OVERLAY_KEYS in shared.py.
    # Rebounder overlays apply FIRST (default), then get-back / release
    # override for designated non-rebounders.
    for overlay_key in (
        "offense_rebounder_coords",
        "defense_rebounder_coords",
        "offense_getback_coords",
        "defense_release_coords",
    ):
        overlay = turn_result.get(overlay_key) or {}
        if not isinstance(overlay, dict):
            continue
        for pid, coord in overlay.items():
            if not isinstance(coord, dict):
                continue
            x = coord.get("x")
            y = coord.get("y")
            if x is None or y is None:
                continue
            pid_str = str(pid)
            end_coords[pid_str] = {"x": float(x), "y": float(y)}
            if isinstance(start_actions, dict):
                # Promote stationary → cut now that the player has a real
                # destination; preserve handle_ball / shoot / pass / receive
                # / guard_* already set by `_build_outcome_step` so role-
                # specific renderer behavior isn't lost.
                if start_actions.get(pid_str) == "stationary":
                    start_actions[pid_str] = "cut"
            if isinstance(start_archetype, dict):
                # Same logic for archetype: only fill in if the emitter left
                # the player as stationary. `_build_outcome_step` has already
                # set sprint for non-BH offense and drive for defenders;
                # don't overwrite those with cruise.
                if start_archetype.get(pid_str) == "stationary":
                    start_archetype[pid_str] = "sprint"
