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

See ``_documentation_master/05_Animation_System/Advance_Triggers.md`` —
"Fast Break / Covert Release" — for the per-step trigger spec.
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

    Step duration is set by outlet pass quality (the ``outlet_score`` on
    ``fb_roles``):
      - ``outlet_score >= 50`` → T = 1 game-sec (snappy, decisive pass)
      - else / missing       → T = 2 game-sec (sloppier pass, more hang time)

    Per-player movement during the step:
      - Outlet passer / receiver: stationary.
      - Get-back defenders (from prior shot's ``offense_getback`` list):
        - Player 1: target = (receiver.x ± 2 toward attacking basket, receiver.y).
        - Player 2 (if present): target = same-side ``lowPost`` from
          ``HCO_STRING_SPOTS`` based on receiver.y > 24.
        Move at ``sprint`` archetype (cutting off the receiver).
      - All other players (non-passer, non-receiver, non-getback): destination
        = attacking basket coord (HOME_RIM_COORDS or AWAY_RIM_COORDS). Move at
        ``default`` archetype (= cruise, AG-driven). Schema interrupted-coord
        semantics handle the case where they don't reach the rim — they end at
        whatever fraction of the path their (rate × T) covers.

    Ball tweens passer → receiver over the full step T (350ms or 700ms
    wall-clock at 350ms-per-game-sec).
    """
    outlet_score = fb_roles.get("outlet_score")
    if outlet_score is not None and outlet_score >= 50:
        t = 1.0
    else:
        # Includes None case (no outlet score available — shouldn't happen
        # in normal CR flow but defensive default).
        t = 2.0

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

    # Get-back Defender 1: cut off the receiver (2 spots ahead in attacking dir, same y).
    if len(getback_ids) >= 1:
        gb1_id = getback_ids[0]
        if gb1_id in all_start_coords and gb1_id not in (passer_id, receiver_id):
            gb1_x = max(4.0, min(97.0, receiver_coord["x"] + (2.0 * x_dir)))
            gb1_target: GridCoord = {"x": gb1_x, "y": float(receiver_coord["y"])}
            targets.append((gb1_id, gb1_target, "sprint"))

    # Get-back Defender 2 (if present): lowPost on the same vertical half as receiver.
    if len(getback_ids) >= 2:
        gb2_id = getback_ids[1]
        if gb2_id in all_start_coords and gb2_id not in (passer_id, receiver_id):
            spot_name = "upper lowPost" if receiver_coord["y"] > 24 else "lower lowPost"
            spot_home = HCO_STRING_SPOTS[spot_name]
            if is_away_offense:
                gb2_target = {"x": float(100 - spot_home["x"]), "y": float(spot_home["y"])}
            else:
                gb2_target = {"x": float(spot_home["x"]), "y": float(spot_home["y"])}
            targets.append((gb2_id, gb2_target, "sprint"))

    # All others: destination = attacking basket; move at default (AG-driven) rate.
    excluded = {passer_id, receiver_id, *getback_ids}
    for pid in all_start_coords:
        if pid in excluded:
            continue
        targets.append((pid, attacking_basket_coord, "default"))

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

    advance_trigger: AdvanceTrigger = {
        "condition": "ball_reaches_player",
        "T_game_seconds": float(t),
        "metadata": {
            "from_player_id": passer_id,
            "to_player_id": receiver_id,
            "target_coords": dict(receiver_coord),
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
    return {"start": start, "end": end}


def _ag_grid_per_game_sec(player: Any, archetype: PlayerArchetype) -> float:
    """Look up grid/game-sec rate for the given player + archetype.

    Defers to ``BackEnd.utils.shared.ag_to_grid_per_game_sec`` when available;
    falls back to a baseline if shared.py is unreachable in test contexts.
    """
    try:
        from BackEnd.utils.shared import ag_to_grid_per_game_sec
        return float(ag_to_grid_per_game_sec(player, archetype=archetype))
    except Exception:
        # Test-context fallback: AG=50, drive baseline ~12 grid/sec
        # (cruise 16 × 0.75 drive multiplier).
        return 12.0


def _traversal_seconds(start: GridCoord, end: GridCoord, rate: float) -> float:
    """Time to traverse start→end at a given grid/game-sec rate."""
    if rate <= 0:
        return 0.0
    return _euclid(start, end) / rate


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
        if is_defensive_stop:
            actions[bh_id] = "handle_ball"
            archetype[bh_id] = "drive"
        elif result_type in ("MAKE", "MISS", "BLOCK"):
            actions[bh_id] = "shoot"
            archetype[bh_id] = "drive"  # FB run-up dominates the wind-up.
        else:
            # FOUL / STEAL / DEAD_BALL — BH still drives toward outcome spot.
            actions[bh_id] = "handle_ball"
            archetype[bh_id] = "drive"

    if stopper_id:
        sid = str(stopper_id)
        if sid in actions:
            actions[sid] = "guard_ball"
            archetype[sid] = "drive"

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
            archetype[pid] = "drive"

    # Gating player + T.
    bh_coord_start = step_start_coords.get(bh_id) if bh_id else None
    bh_coord_end = end_coords.get(bh_id) if bh_id else None
    bh_traversal = (
        _traversal_seconds(bh_coord_start, bh_coord_end, _ag_grid_per_game_sec(bh, "drive"))
        if bh_coord_start and bh_coord_end and bh
        else 0.0
    )

    if is_defensive_stop and stopper:
        stopper_pid = str(stopper_id)
        st_start = step_start_coords.get(stopper_pid)
        st_end = end_coords.get(stopper_pid)
        st_traversal = (
            _traversal_seconds(st_start, st_end, _ag_grid_per_game_sec(stopper, "drive"))
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
    # exceeds what they could traverse at drive rate × T gets clamped to
    # start + (rate × T) along the path. Without this, non-gate players in
    # step 1 (especially the FB shot path, where multiple players have
    # full destinations near the rim) would appear to teleport because
    # the legacy animator pre-computes full destinations regardless of T.
    # Rebinds end_coords[pid] (does NOT mutate the dict in place) so
    # destinations[pid] retains the original target reference.
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
        rate = _ag_grid_per_game_sec(player, "drive") if player else 12.0
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
    branch). See module docstring + Advance_Triggers.md for the spec.
    """
    import logging
    fb_bh = fb_roles.get("ball_handler")
    if fb_bh is None:
        logging.warning("🏀 [CR STEP-BACK] returning None: fb_bh is None")
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
        logging.warning(
            "🏀 [CR STEP-BACK] returning None: could not resolve fb_bh_pos "
            "(fb_bh_id=%s, off_lineup_player_ids=%s)",
            fb_bh_id,
            {k: getattr(v, "player_id", None) for k, v in (off_lineup or {}).items()},
        )
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
        rate = _ag_grid_per_game_sec(player, "drive") if player else 12.0
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
        archetype[pid] = "drive"

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
    return {"start": start, "end": end}


def _build_nice_stop_announcement(
    turn_result: Dict[str, Any],
    fb_roles: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> Announcement:
    """``"Nice Stop by <stopper>!"`` announcement payload for the end of the
    defensive-stop motion step. Mirrors the legacy phrasing.
    """
    stopper_id = turn_result.get("stopper_id") or fb_roles.get("stopper_id")
    stopper = _player_lookup_by_id({}, def_lineup, stopper_id) if stopper_id else None
    text = "Nice Stop!"
    player_data: Optional[Dict[str, Any]] = None
    if stopper is not None:
        player_data = {
            "playerId": _safe_id(stopper),
            "photo": getattr(stopper, "photo", None),
            "teamName": None,  # populated client-side from team lookup
        }
    return {
        "text": text,
        "team": "defense",
        "player_data": player_data,
        "meta": None,
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
    fb_roles: Dict[str, Any] = turn_result.get("roles") or {}

    fast_break_play = turn_result.get("fast_break_play")
    if fast_break_play != "covert_release":
        return None

    off_team = getattr(game, "offense_team", None)
    def_team = getattr(game, "defense_team", None)
    off_lineup = getattr(off_team, "lineup", {}) if off_team else {}
    def_lineup = getattr(def_team, "lineup", {}) if def_team else {}

    bh = fb_roles.get("ball_handler")
    bh_id = _safe_id(bh)
    if not bh_id:
        return None

    outlet_passer_id = fb_roles.get("outlet_passer")
    outlet_receiver_id = fb_roles.get("outlet_receiver")
    is_away_offense = bool(fb_roles.get("is_away_offense"))

    # All-player start coords (every player in both lineups).
    all_start_coords = _all_player_start_coords(off_lineup, def_lineup)
    if not all_start_coords:
        return None

    # Override outlet passer's start coord with fb_roles outlet_passer_x/y
    # when present — the animator stores the canonical pre-pass position
    # there (rebounder coords at the moment of outlet).
    op_x = fb_roles.get("outlet_passer_x")
    op_y = fb_roles.get("outlet_passer_y")
    if outlet_passer_id and op_x is not None and op_y is not None:
        all_start_coords[str(outlet_passer_id)] = {"x": float(op_x), "y": float(op_y)}

    # NOTE: `player.coords` now stores in DISPLAY orientation (real visual
    # coords) — the prior dual-orientation convention was removed by
    # neutralizing `_normalize_animation_coords_to_runtime_home`. So no
    # flip is needed here; `all_start_coords` is already in display
    # orientation matching the rest of the chain.

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

    # DEFENSIVE_STOP only: append step-back step. Other outcomes terminate
    # via their `turn_stop` next pointer set by `_resolve_outcome_next`.
    result_type = (turn_result.get("result_type") or "").upper()
    import logging
    logging.warning(
        "🏀 [CR EMITTER] result_type=%s, has_outlet_pass=%s, steps_so_far=%d",
        result_type, has_outlet_pass, len(steps),
    )
    if result_type == "DEFENSIVE_STOP":
        # Override the outcome step's `next` pointer to point at step 2
        # (was implicit-end via index 999; now linear continuation).
        next_index = len(steps)  # the index step 2 will occupy after append
        outcome_step["end"]["next"] = {"kind": "next_step", "index": next_index}

        # Attach "Nice Stop!" announcement to step 1's end (plays after the
        # confrontation move, before step 2 fires).
        outcome_step["end"]["announcement"] = _build_nice_stop_announcement(
            turn_result, fb_roles, def_lineup
        )

        # Build step 2: step-back / HCO setup.
        step_back_start_coords = dict(outcome_step["end"]["coords"])
        logging.warning(
            "🏀 [CR EMITTER] DEFENSIVE_STOP — calling _build_step_back_step. "
            "fb_bh=%s, fb_bh_pos=%s, off_lineup_keys=%s",
            getattr(fb_roles.get("ball_handler"), "player_id", None),
            getattr(fb_roles.get("ball_handler"), "position", None),
            list(off_lineup.keys()) if off_lineup else None,
        )
        step_back = _build_step_back_step(
            turn_result=turn_result,
            fb_roles=fb_roles,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            step_start_coords=step_back_start_coords,
            clock_remaining_at_start=clock_remaining - elapsed,
            shot_clock_remaining_at_start=shot_clock_remaining - elapsed,
        )
        if step_back is not None:
            steps.append(step_back)
            logging.warning(
                "🏀 [CR EMITTER] step-back appended; total_steps=%d, T=%.3f",
                len(steps), step_back["end"]["time_elapsed"],
            )
        else:
            logging.warning(
                "🏀 [CR EMITTER] _build_step_back_step returned None — "
                "step 1 next pointer still references missing index %d",
                next_index,
            )

    _log_steps_coords(steps, off_lineup, def_lineup)
    return steps


def _log_steps_coords(
    steps: List[AnimationStep],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> None:
    """Per-step, per-player start/end coord log for debugging FB animations.

    Iterates over ``step.start.coords`` (authoritative for which players the
    emitter actually populated). For each player_id, attempts to resolve
    team + position via lineup lookup; falls back to ``?`` placeholders so we
    see SOMETHING per player even when lineup state is unreliable.
    """
    import logging

    pid_to_role: Dict[str, tuple] = {}
    for pos in _LINEUP_ORDER:
        for team_label, lineup in (("OFFENSE", off_lineup), ("DEFENSE", def_lineup)):
            player = lineup.get(pos) if lineup else None
            if player is None:
                continue
            pid = getattr(player, "player_id", None)
            if pid is None:
                continue
            pid_to_role[str(pid)] = (team_label, pos)

    def _fmt(coord: Any) -> str:
        if not isinstance(coord, dict) or "x" not in coord or "y" not in coord:
            return "?"
        try:
            return f"({float(coord['x']):.1f}, {float(coord['y']):.1f})"
        except (TypeError, ValueError):
            return "?"

    for i, step in enumerate(steps):
        t = step.get("end", {}).get("time_elapsed")
        logging.warning(
            "🏀 [CR STEPS] step %d (T=%s game-sec, %d players in coords)",
            i,
            f"{t:.3f}" if isinstance(t, (int, float)) else "?",
            len((step.get("start", {}).get("coords") or {})),
        )
        start_coords = step.get("start", {}).get("coords") or {}
        end_coords = step.get("end", {}).get("coords") or {}

        # Sort player_ids by (team, position) when known; unresolved goes last.
        def _sort_key(pid: str) -> tuple:
            role = pid_to_role.get(pid)
            if role is None:
                return (2, 0, str(pid))
            team_label, pos = role
            team_idx = 0 if team_label == "OFFENSE" else 1
            try:
                pos_idx = _LINEUP_ORDER.index(pos)
            except ValueError:
                pos_idx = 99
            return (team_idx, pos_idx, str(pid))

        for pid in sorted(start_coords.keys(), key=_sort_key):
            team_label, pos = pid_to_role.get(pid, ("?", "?"))
            logging.warning(
                "  %s %s (%s): %s → %s",
                team_label, pos, pid,
                _fmt(start_coords.get(pid)),
                _fmt(end_coords.get(pid)),
            )
