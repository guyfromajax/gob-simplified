"""Quick Foul (situational Force Foul): detection, participant selection,
BIP/SIP setup coordinates, and the UESS step emitter for the foul itself.

A "quick foul" is the situational Force Foul: a trailing/close defense that is
Slow-It-Down + Force-Foul intentionally fouls the offense to stop the clock and
send them to the line. Design and rules live in
_documentation_master/06_Gameplay_Systems/Situational_Logic_System.md
§Force Foul Execution.

Flow (all Q4/OT):
- ``quick_foul_in_play`` is a pure function of game state and can be evaluated at
  any point (BIP/SIP setup, HCO turn start).
- On a BIP/SIP that leads into a quick foul, ``build_quick_foul_inbound_setup``
  produces the bespoke setup formation: SF inbounds to one of two candidate
  receivers; the paired fouling defender is pre-positioned within
  ``QUICK_FOUL_APPROACH_RADIUS_GRID`` of that receiver. No foul executes on the
  inbound turn.
- The foul itself executes at the START of the following HCO turn (universal
  hook), on the current ball handler (= the inbound receiver), via
  ``build_quick_foul_animation_steps``: a converge (sprint) step then a reach-in
  micro. The same HCO-start hook also covers DREB / OREB-kickout / Final Turn
  entries where there is no setup step (the converge sprint carries the fouler
  in).
"""

import math
import random
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.constants import (
    HCO_STRING_SPOTS,
    QUICK_FOUL_APPROACH_RADIUS_GRID,
    QUICK_FOUL_RECEIVER_MAX_DIST_GRID,
    QUICK_FOUL_RECEIVER_MIN_SEPARATION_GRID,
    QUICK_FOUL_INBOUND_GUARD_OFFSET_GRID,
    QUICK_FOUL_SCATTER_OFFSET_GRID,
    QUICK_FOUL_TIME_ELAPSED_FLOOR,
    QUICK_FOUL_REACHIN_GAME_SECONDS,
    QUICK_FOUL_CHEMISTRY_ROLL_MIN,
    QUICK_FOUL_CHEMISTRY_ROLL_MAX,
    QUICK_FOUL_OFFENSE_SCATTER_SPOTS,
    QUICK_FOUL_DEFENSE_SCATTER_SPOTS,
    QUICK_FOUL_DEFENSE_SHARED_SPOTS,
)
from BackEnd.utils import situational_logic as sl

GridCoord = Dict[str, float]

# Court playable bounds (grid). y=50/x=0/x=100 are the OOB lines.
_MIN_X, _MAX_X = 1.0, 99.0
_MIN_Y, _MAX_Y = 1.0, 49.0

_LINEUP_POSITIONS = ("PG", "SG", "SF", "PF", "C")


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #
def quick_foul_in_play(game, time_remaining=None) -> bool:
    """True when the defense should intentionally foul this possession (Q4/OT).

    Pure function of game state (quarter, time band, score delta) — safe to call
    at BIP/SIP setup time or at HCO turn start.
    """
    if time_remaining is None:
        time_remaining = (getattr(game, "game_state", None) or {}).get("time_remaining")
    return (
        sl.is_situational_active(getattr(game, "quarter", None))
        and sl.is_slow_it_down(game, time_remaining)
        and sl.should_force_foul(game, time_remaining)
    )


# --------------------------------------------------------------------------- #
# Small attribute / geometry helpers
# --------------------------------------------------------------------------- #
def _team_chemistry(team) -> int:
    attrs = getattr(team, "team_attributes", None) or {}
    try:
        c = int(attrs.get("team_chemistry", 15) or 15)
    except (TypeError, ValueError):
        c = 15
    return max(7, min(25, c))


def _ft_rating(player) -> float:
    attrs = getattr(player, "attributes", None) or {}
    try:
        return float(attrs.get("FT", 50) or 50)
    except (TypeError, ValueError):
        return 50.0


def _height(player) -> float:
    try:
        return float(getattr(player, "height", 75) or 75)
    except (TypeError, ValueError):
        return 75.0


def _foul_count(player) -> int:
    try:
        return int(player.stats["game"].get("F", 0))
    except Exception:
        return 0


def _clamp_point(x: float, y: float) -> GridCoord:
    return {
        "x": round(min(_MAX_X, max(_MIN_X, x)), 2),
        "y": round(min(_MAX_Y, max(_MIN_Y, y)), 2),
    }


def _rand_point_within(
    anchor: GridCoord,
    radius: float,
    rng,
    *,
    min_sep_from: Optional[GridCoord] = None,
    min_sep: float = 0.0,
    tries: int = 60,
) -> GridCoord:
    """Random in-bounds point within ``radius`` of ``anchor`` (uniform in disk).

    If ``min_sep_from``/``min_sep`` are given, retries until the point is at
    least ``min_sep`` from that reference; falls back to the last candidate.
    """
    ax, ay = float(anchor["x"]), float(anchor["y"])
    fallback: Optional[GridCoord] = None
    for _ in range(max(1, tries)):
        r = radius * math.sqrt(rng.random())
        theta = rng.random() * 2.0 * math.pi
        pt = _clamp_point(ax + r * math.cos(theta), ay + r * math.sin(theta))
        if min_sep_from is not None:
            d = math.hypot(pt["x"] - float(min_sep_from["x"]), pt["y"] - float(min_sep_from["y"]))
            if d < min_sep:
                fallback = pt
                continue
        return pt
    return fallback or _clamp_point(ax, ay)


def _offset_toward(coord: GridCoord, target: GridCoord, dist: float) -> GridCoord:
    dx = float(target["x"]) - float(coord["x"])
    dy = float(target["y"]) - float(coord["y"])
    d = math.hypot(dx, dy) or 1.0
    return _clamp_point(float(coord["x"]) + dx / d * dist, float(coord["y"]) + dy / d * dist)


def _pick_two(positions: List[str], keyfn, reverse: bool, rng) -> List[str]:
    """Two positions by ``keyfn`` (reverse=True → highest), ties broken randomly."""
    shuffled = list(positions)
    rng.shuffle(shuffled)
    ordered = sorted(shuffled, key=keyfn, reverse=reverse)
    return ordered[:2]


# --------------------------------------------------------------------------- #
# Participant selection (chemistry-driven)
# --------------------------------------------------------------------------- #
def select_quick_foul_participants(game, off_lineup, def_lineup, rng=random) -> Optional[Dict[str, Any]]:
    """Choose inbound passer, two candidate receivers + their foulers, the
    inbound-guard defender, and the two scatter players per side.

    Offense: SF always inbounds. roll = randint(1,25); if roll < offense
    chemistry → two best FT shooters (of the non-SF four), else SG + PG.

    Defense: tallest defender guards the inbound; from the remaining four,
    roll < defense chemistry → two fewest-fouls, else two at random.

    Foulers are paired to candidate receivers at random; the receiver (foul
    victim) is one of the two candidates chosen 50/50.

    Returns a dict of positions/ids, or None if the lineups are incomplete.
    """
    off_positions = [p for p in _LINEUP_POSITIONS if off_lineup.get(p)]
    def_positions = [p for p in _LINEUP_POSITIONS if def_lineup.get(p)]
    if "SF" not in off_positions or len(off_positions) < 5 or len(def_positions) < 5:
        return None

    # --- Offense: passer + two candidate receivers ---
    non_sf = [p for p in ("PG", "SG", "PF", "C") if p in off_positions]
    off_chem = _team_chemistry(game.offense_team)
    if rng.randint(QUICK_FOUL_CHEMISTRY_ROLL_MIN, QUICK_FOUL_CHEMISTRY_ROLL_MAX) < off_chem:
        candidates = _pick_two(non_sf, keyfn=lambda p: _ft_rating(off_lineup[p]), reverse=True, rng=rng)
        offense_mode = "best_ft"
    else:
        candidates = [p for p in ("SG", "PG") if p in non_sf][:2]
        offense_mode = "sg_pg"
    if len(candidates) < 2:
        return None
    remaining_off = [p for p in non_sf if p not in candidates]

    # --- Defense: inbound guard (tallest) + two foulers ---
    guard_pos = _pick_two(def_positions, keyfn=lambda p: _height(def_lineup[p]), reverse=True, rng=rng)[0]
    rem_def = [p for p in def_positions if p != guard_pos]
    def_chem = _team_chemistry(game.defense_team)
    if rng.randint(QUICK_FOUL_CHEMISTRY_ROLL_MIN, QUICK_FOUL_CHEMISTRY_ROLL_MAX) < def_chem:
        foulers = _pick_two(rem_def, keyfn=lambda p: _foul_count(def_lineup[p]), reverse=False, rng=rng)
        defense_mode = "fewest_fouls"
    else:
        foulers = rng.sample(rem_def, 2)
        defense_mode = "random"
    remaining_def = [p for p in rem_def if p not in foulers]

    # --- Pair foulers to candidates at random; choose the receiver 50/50 ---
    shuffled_foulers = list(foulers)
    rng.shuffle(shuffled_foulers)
    pairs = dict(zip(candidates, shuffled_foulers))  # off_pos -> def_pos
    receiver_pos = rng.choice(candidates)
    fouler_pos = pairs[receiver_pos]

    return {
        "passer_pos": "SF",
        "candidates": candidates,
        "receiver_pos": receiver_pos,
        "receiver_id": getattr(off_lineup[receiver_pos], "player_id", None),
        "fouler_pos": fouler_pos,
        "fouler_id": getattr(def_lineup[fouler_pos], "player_id", None),
        "pairs": pairs,
        "guard_pos": guard_pos,
        "remaining_off": remaining_off,
        "remaining_def": remaining_def,
        "offense_mode": offense_mode,
        "defense_mode": defense_mode,
    }


# --------------------------------------------------------------------------- #
# BIP/SIP setup coordinates (home orientation; caller flips for away offense)
# --------------------------------------------------------------------------- #
def build_quick_foul_inbound_setup(
    *,
    game,
    off_lineup,
    def_lineup,
    inbounder_coord: GridCoord,
    basket_coord: GridCoord,
    guard_offset: Tuple[float, float],
    rng=random,
) -> Optional[Dict[str, Any]]:
    """Bespoke quick-foul BIP/SIP formation (home orientation).

    - SF at ``inbounder_coord``.
    - Two candidate receivers within ``QUICK_FOUL_RECEIVER_MAX_DIST_GRID`` of the
      inbounder and >= ``QUICK_FOUL_RECEIVER_MIN_SEPARATION_GRID`` apart.
    - Each fouling defender within ``QUICK_FOUL_APPROACH_RADIUS_GRID`` of his man.
    - Inbound-guard defender at ``inbounder_coord + guard_offset``.
    - The remaining two per side at random distinct named scatter spots; a
      defense bird/apex spot offsets ``QUICK_FOUL_SCATTER_OFFSET_GRID`` toward the
      basket if an offender already occupies that spot.

    Returns ``{"o_dest", "d_dest", "receiver_pos", "receiver_id",
    "fouler_pos", "fouler_id", ...}`` or None if selection fails.
    """
    sel = select_quick_foul_participants(game, off_lineup, def_lineup, rng=rng)
    if not sel:
        return None

    o_dest: Dict[str, GridCoord] = {}
    d_dest: Dict[str, GridCoord] = {}

    # Inbounder (SF).
    o_dest["SF"] = _clamp_point(float(inbounder_coord["x"]), float(inbounder_coord["y"]))

    # Two candidate receivers near the inbounder.
    cand = sel["candidates"]
    c1 = _rand_point_within(o_dest["SF"], QUICK_FOUL_RECEIVER_MAX_DIST_GRID, rng)
    c2 = _rand_point_within(
        o_dest["SF"],
        QUICK_FOUL_RECEIVER_MAX_DIST_GRID,
        rng,
        min_sep_from=c1,
        min_sep=QUICK_FOUL_RECEIVER_MIN_SEPARATION_GRID,
    )
    o_dest[cand[0]] = c1
    o_dest[cand[1]] = c2

    # Foulers within 4 of their paired candidate.
    for off_pos, def_pos in sel["pairs"].items():
        d_dest[def_pos] = _rand_point_within(o_dest[off_pos], QUICK_FOUL_APPROACH_RADIUS_GRID, rng)

    # Inbound-guard defender.
    gdx, gdy = guard_offset
    d_dest[sel["guard_pos"]] = _clamp_point(
        float(inbounder_coord["x"]) + float(gdx),
        float(inbounder_coord["y"]) + float(gdy),
    )

    # Remaining two offense players at random distinct scatter spots.
    occupied_offense_spots: Dict[str, GridCoord] = {}
    off_spot_names = rng.sample(list(QUICK_FOUL_OFFENSE_SCATTER_SPOTS), len(sel["remaining_off"]))
    for pos, spot_name in zip(sel["remaining_off"], off_spot_names):
        coord = dict(HCO_STRING_SPOTS[spot_name])
        o_dest[pos] = {"x": float(coord["x"]), "y": float(coord["y"])}
        occupied_offense_spots[spot_name] = o_dest[pos]

    # Remaining two defense players at random distinct scatter spots; offset a
    # shared bird/apex spot toward the basket if an offender occupies it.
    def_spot_names = rng.sample(list(QUICK_FOUL_DEFENSE_SCATTER_SPOTS), len(sel["remaining_def"]))
    for pos, spot_name in zip(sel["remaining_def"], def_spot_names):
        coord = {"x": float(HCO_STRING_SPOTS[spot_name]["x"]), "y": float(HCO_STRING_SPOTS[spot_name]["y"])}
        if spot_name in QUICK_FOUL_DEFENSE_SHARED_SPOTS and spot_name in occupied_offense_spots:
            coord = _offset_toward(coord, basket_coord, QUICK_FOUL_SCATTER_OFFSET_GRID)
        d_dest[pos] = coord

    return {
        "o_dest": o_dest,
        "d_dest": d_dest,
        "receiver_pos": sel["receiver_pos"],
        "receiver_id": sel["receiver_id"],
        "fouler_pos": sel["fouler_pos"],
        "fouler_id": sel["fouler_id"],
        "guard_pos": sel["guard_pos"],
        "offense_mode": sel["offense_mode"],
        "defense_mode": sel["defense_mode"],
    }


# --------------------------------------------------------------------------- #
# UESS step emitter for the foul itself (executed at HCO turn start)
# --------------------------------------------------------------------------- #
def build_quick_foul_animation_steps(
    *,
    off_lineup,
    def_lineup,
    prior_final_coords: Dict[str, GridCoord],
    victim_id,
    fouler_id,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    announcement: Optional[Dict[str, Any]] = None,
    rng=random,
) -> Tuple[List[Dict[str, Any]], float]:
    """Two-step quick-foul sequence, returned with the game-clock burn (T).

    - Step 1 — converge: the fouler sprints from his current position to a random
      spot within ``QUICK_FOUL_APPROACH_RADIUS_GRID`` of the victim (the ball
      handler, who holds the ball and stays put). Game clock RUNS; step T floored
      to ``QUICK_FOUL_TIME_ELAPSED_FLOOR``. On BIP/SIP the fouler is already
      within 4 (pre-positioned in setup), so this is ~a 1s reach; on DREB /
      OREB-kickout / Final Turn it is a real sprint.
    - Step 2 — reach-in: everyone stationary; the fouler plays the ``reach_in``
      micro toward the ball; the "Quick Foul" announcement mounts. Game clock is
      PINNED here (stops the moment the reach-in begins).

    Returns ``(steps, time_elapsed)`` where ``time_elapsed`` = the converge T
    (the only clock burn) — pass it as ``time_elapsed_override`` to
    ``resolve_non_shooting_foul`` so state and animation agree.
    """
    from BackEnd.utils.transition_bridge import build_walk_up_step

    vid = str(victim_id)
    fid = str(fouler_id)
    victim_coord = prior_final_coords.get(vid)
    fouler_coord = prior_final_coords.get(fid)
    if not victim_coord or not fouler_coord:
        return [], float(QUICK_FOUL_TIME_ELAPSED_FLOOR)

    approach = _rand_point_within(victim_coord, QUICK_FOUL_APPROACH_RADIUS_GRID, rng)

    start_coords = {pid: dict(c) for pid, c in prior_final_coords.items()}
    end_coords = {pid: dict(c) for pid, c in prior_final_coords.items()}
    end_coords[fid] = approach

    converge = build_walk_up_step(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=start_coords,
        end_coords=end_coords,
        bh_id=vid,
        clock_remaining_at_start=float(clock_remaining_at_start),
        shot_clock_remaining_at_start=float(shot_clock_remaining_at_start),
        next_step_index=1,
        bh_archetype="standard",
        other_archetype="sprint",
        gate_player_ids=[fid],
        metadata_reason="quick_foul_converge",
        min_t_game_sec=float(QUICK_FOUL_TIME_ELAPSED_FLOOR),
    )
    converge_t = float(converge["end"]["time_elapsed"])

    reach_step = _build_quick_foul_reach_in_step(
        start_coords=converge["end"]["coords"],
        victim_id=vid,
        fouler_id=fid,
        clock_remaining_at_start=float(converge["end"]["clock"]["clock_remaining"]),
        shot_clock_remaining_at_start=float(converge["end"]["clock"]["shot_clock_remaining"]),
        announcement=announcement,
    )

    return [converge, reach_step], converge_t


def _build_quick_foul_reach_in_step(
    *,
    start_coords: Dict[str, GridCoord],
    victim_id: str,
    fouler_id: str,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    announcement: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Stationary reach-in micro step. Clock PINNED (foul stops the clock);
    the fouler plays the ``reach_in`` flourish toward the ball; announcement
    mounts non-blocking (world keeps rendering, no gameplay freeze)."""
    t = float(QUICK_FOUL_REACHIN_GAME_SECONDS)
    actions: Dict[str, str] = {}
    archetype: Dict[str, str] = {}
    destinations: Dict[str, Optional[GridCoord]] = {}
    end_coords: Dict[str, GridCoord] = {}
    for pid, sc in start_coords.items():
        actions[pid] = "handle_ball" if pid == victim_id else "stationary"
        archetype[pid] = "stationary"
        destinations[pid] = None
        end_coords[pid] = dict(sc)

    # Clock PINNED: start == end (the whistle stops the clock at reach-in).
    clock: Dict[str, float] = {
        "clock_remaining": float(clock_remaining_at_start),
        "shot_clock_remaining": float(shot_clock_remaining_at_start),
    }

    start: Dict[str, Any] = {
        "coords": {pid: dict(c) for pid, c in start_coords.items()},
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": {"owner_player_id": victim_id},
        "clock": dict(clock),
        "advance_trigger": {
            "condition": "fixed_duration",
            "T_game_seconds": t,
            "metadata": {"reason": "quick_foul_reach_in"},
        },
        "flourish": {fouler_id: {"kind": "reach_in", "target": "ball"}},
    }
    end: Dict[str, Any] = {
        "coords": end_coords,
        "ball": {"owner_player_id": victim_id},
        "time_elapsed": t,
        "clock": dict(clock),
        "next": {"kind": "turn_stop", "event": "turn_end", "payload": {}},
    }
    if announcement:
        end["announcement"] = announcement
    return {"start": start, "end": end}
