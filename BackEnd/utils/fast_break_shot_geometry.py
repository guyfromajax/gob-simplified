"""Universal Fast Break shot geometry + contested-decision helper.

Used by all FB resolvers (Rim Runner, Covert Release, Steal-FB) to
compute a consistent shooter target, defender single target, race
outcome, and contested decision for the FB shot step.

Triangle is intentionally untouched — see Fast_Break_System.md.

UESS contract
-------------
Pure function. No side effects on game state. Returns geometry + a
contested decision. The caller (FB resolver) uses the returned
``shot_defender_id`` + ``contested`` flag to call
``shot_manager.calculate_shot_score`` and stamps the returned
``defender_end_coords`` onto the turn_result for the schema emitter to
render. Schema emitters remain pure renderers.

Spec (mirrors Steal-FB, per discussion 2026-05-27)
--------------------------------------------------
- **Shooter target**: ``basket_x ± random.randint(2, 4)`` toward center,
  ``y = random.randint(19, 31)``.
- **Defender single target**: ``shooter_x ± 2`` toward basket (one
  point all racing defenders converge on); same y as shooter.
- **Race**: each available defender traverses ``start → defender_target``
  at AG-based sprint rate. First arriver (smallest traversal time)
  occupies the target. Other available defenders freeze at their
  interpolated position at first-arrival time, clamped no closer than
  6 grid spots from basket. **Edge case**: defenders whose start is
  already inside the 6-spot zone are not pulled backward.
- **Race pool ("available defenders")**: caller's responsibility.
    - RR: exclude Stopper AND Outlet defender; race pool = Trail +
      Get-back defenders.
    - CR: exclude Stopper; race pool = Trail + Get-back defenders.
    - Steal-FB: no exclusions; all 5 defenders race.
- **Contested decision** (at t_shooter): among racing defenders at their
  end positions, any defender within ``CONTEST_EUCLIDEAN_RADIUS`` (11)
  grid spots of the shooter **and** trailing the shooter on x by at most
  ``FB_CONTEST_MAX_X_TRAIL`` (3) spots counts as a contest. Nearest
  qualifying defender is the shot defender; else uncontested.
- **Shot resolution** (caller does this): uncontested → automatic MAKE
  (apply_defense=False); contested → ``calculate_shot_score``
  threshold check.

Inputs / outputs
----------------
Function ``compute_fb_shot_geometry(...)`` takes the shooter, the
shooter's start coord, a list of available-defender player objects,
their start coords, and ``is_away_offense``. Returns a dict whose
shape is documented on the function below.
"""

from __future__ import annotations

from BackEnd.utils.sim_random import sim_rng as random
from typing import Any, Dict, List, Optional

from BackEnd.constants import CONTEST_EUCLIDEAN_RADIUS
from BackEnd.utils.animation_step_helpers import (
    _ag_grid_per_game_sec,
    _euclid,
)
from BackEnd.utils.animation_step_schema import GridCoord


# Defender freeze clamp: no closer than this many grid spots from basket
# (but never pulled backward from start_x). Matches Steal-FB constant.
DEFENDER_FREEZE_CLAMP_GRID_SPOTS: int = 6

# Basket x coords (mirror of HOME/AWAY_RIM_COORDS without the import dep).
_HOME_BASKET_X: float = 91.0
_AWAY_BASKET_X: float = 9.0

# Shooter lands basket_x ± uniform integer in [FB_SHOOTER_X_OFFSET_MIN, FB_SHOOTER_X_OFFSET_MAX].
FB_SHOOTER_X_OFFSET_MIN = 2
FB_SHOOTER_X_OFFSET_MAX = 4
# Defender may trail the shooter on x by up to this many grid spots and still contest.
FB_CONTEST_MAX_X_TRAIL = 3


def _safe_id(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    pid = getattr(obj, "player_id", None)
    return str(pid) if pid is not None else None


def _compute_shooter_target(is_away_offense: bool) -> GridCoord:
    """Shooter target: 2-4 spots out from basket on x, y ∈ [19, 31]."""
    distance = random.randint(FB_SHOOTER_X_OFFSET_MIN, FB_SHOOTER_X_OFFSET_MAX)
    if is_away_offense:
        x = _AWAY_BASKET_X + distance  # AWAY shoots at x=9 → out from x=9
    else:
        x = _HOME_BASKET_X - distance  # HOME shoots at x=91 → out from x=91
    y = float(random.randint(19, 31))
    return {"x": float(x), "y": y}


def _compute_defender_target(
    shooter_target: GridCoord, is_away_offense: bool
) -> GridCoord:
    """Defender single target: 2 spots closer to basket than shooter, same y."""
    if is_away_offense:
        x = shooter_target["x"] - 2.0
    else:
        x = shooter_target["x"] + 2.0
    return {"x": float(x), "y": float(shooter_target["y"])}


def _interpolated_position(
    start: GridCoord, target: GridCoord, rate: float, elapsed: float
) -> GridCoord:
    """Position after ``elapsed`` game-seconds at ``rate`` grid/game-sec."""
    dx = target["x"] - start["x"]
    dy = target["y"] - start["y"]
    dist = (dx * dx + dy * dy) ** 0.5
    if dist < 1e-6 or rate <= 0:
        return dict(start)
    traverse_t = dist / rate
    if elapsed >= traverse_t:
        return dict(target)
    frac = elapsed / traverse_t
    return {
        "x": start["x"] + dx * frac,
        "y": start["y"] + dy * frac,
    }


def _clamp_defender_freeze(
    pos: GridCoord,
    start_x: float,
    is_away_offense: bool,
) -> GridCoord:
    """Clamp a frozen (non-first-arriver) defender's x: no closer than
    ``DEFENDER_FREEZE_CLAMP_GRID_SPOTS`` from basket, but never pulled
    backward from start_x (edge case: defender starting inside the clamp
    zone stays at start instead of teleporting back).
    """
    if is_away_offense:
        # AWAY basket at x=9. Closer-than-6 means x<15. Allowed minimum =
        # min(start_x, 15) — never pulled backward from start.
        allowed_min = min(start_x, 15.0)
        clamped_x = max(pos["x"], allowed_min)
    else:
        # HOME basket at x=91. Closer-than-6 means x>85. Allowed maximum =
        # max(start_x, 85) — never pulled backward from start.
        allowed_max = max(start_x, 85.0)
        clamped_x = min(pos["x"], allowed_max)
    return {"x": clamped_x, "y": pos["y"]}


def _defender_x_trail_spots(
    defender_x: float, shooter_x: float, is_away_offense: bool
) -> float:
    """How many x grid spots the defender trails the shooter (0 if even or ahead)."""
    if is_away_offense:
        return max(0.0, float(defender_x) - float(shooter_x))
    return max(0.0, float(shooter_x) - float(defender_x))


def _defender_contests_fb_shot(
    defender_pos: GridCoord,
    shooter_target: GridCoord,
    is_away_offense: bool,
) -> bool:
    """True when defender is within contest radius and x-trail is ≤ max trail."""
    if _euclid(defender_pos, shooter_target) > CONTEST_EUCLIDEAN_RADIUS:
        return False
    trail = _defender_x_trail_spots(
        defender_pos["x"], shooter_target["x"], is_away_offense
    )
    return trail <= FB_CONTEST_MAX_X_TRAIL


def _pick_fb_shot_defender(
    traversals: List[Dict[str, Any]],
    defender_end_coords: Dict[str, GridCoord],
    shooter_target: GridCoord,
    is_away_offense: bool,
) -> tuple[bool, Optional[str]]:
    """Nearest qualifying defender at t_shooter, or uncontested."""
    best_id: Optional[str] = None
    best_dist: Optional[float] = None
    for t in traversals:
        d_id = t["id"]
        end = defender_end_coords.get(d_id, t["start"])
        if not _defender_contests_fb_shot(end, shooter_target, is_away_offense):
            continue
        dist = _euclid(end, shooter_target)
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_id = d_id
    return best_id is not None, best_id


def compute_fb_shot_geometry(
    *,
    shooter: Any,
    shooter_start: GridCoord,
    available_defenders: List[Any],
    defender_starts: Dict[str, GridCoord],
    is_away_offense: bool,
) -> Dict[str, Any]:
    """Universal FB shot geometry + contested decision.

    Args
    ----
    shooter
        The ball-handler player object (used for AG-based sprint rate).
    shooter_start
        The shooter's coord at the start of the shot step (= end of the
        preceding step). The caller is responsible for sourcing this
        from the right place (typically ``prior_step.end.coords[shooter_id]``
        for RR/CR, or ``prior_turn.final_coords[stealer_id]`` for Steal-FB).
    available_defenders
        Defender player objects participating in the race. Caller is
        responsible for excluding committed defenders (Stopper for CR,
        Stopper + Outlet defender for RR, none for Steal-FB).
    defender_starts
        Mapping of ``{player_id: GridCoord}`` for the available defenders
        — their position at the start of the shot step.
    is_away_offense
        ``True`` if the new offense (shooter's team) is the away team.
        Determines basket x (AWAY=9, HOME=91) and direction conventions.

    Returns
    -------
    A dict with:
        - ``shooter_target``: GridCoord — where the shooter ends up.
        - ``defender_target``: GridCoord — the single point defenders
          race to.
        - ``defender_end_coords``: ``Dict[str, GridCoord]`` — end positions
          for each available defender (first arriver at defender_target;
          others at clamped freeze positions OR at interpolated t_shooter
          if no defender arrived in time).
        - ``first_arriver_id``: Optional[str] — defender who reached the
          defender_target first, or ``None`` if no defender arrived
          before ``t_shooter``.
        - ``contested``: bool — True if a qualifying defender is within
          ``CONTEST_EUCLIDEAN_RADIUS`` of the shooter and trails on x by
          at most ``FB_CONTEST_MAX_X_TRAIL`` at t_shooter.
        - ``shot_defender_id``: Optional[str] — nearest qualifying defender
          for ``calculate_shot_score``, or None if uncontested.
        - ``t_shooter_game_seconds``: float — shooter's traversal time to
          shot spot. Schema emitter can use this for the shot step's
          ``advance_trigger.T_game_seconds``.
    """
    # --- Geometry: shooter target + defender single target ----------------
    shooter_target = _compute_shooter_target(is_away_offense)
    defender_target = _compute_defender_target(shooter_target, is_away_offense)

    # --- Shooter traversal time (gates the step) --------------------------
    shooter_rate = _ag_grid_per_game_sec(shooter, "sprint")
    shooter_dist = _euclid(shooter_start, shooter_target)
    t_shooter = (
        max(0.1, shooter_dist / shooter_rate)
        if shooter_rate > 0
        else 0.5
    )

    # --- Per-defender traversal ------------------------------------------
    traversals: List[Dict[str, Any]] = []
    for d in available_defenders:
        d_id = _safe_id(d)
        if not d_id:
            continue
        d_start = defender_starts.get(d_id)
        if d_start is None:
            continue
        d_rate = _ag_grid_per_game_sec(d, "sprint")
        d_dist = _euclid(d_start, defender_target)
        d_time = (d_dist / d_rate) if d_rate > 0 else float("inf")
        traversals.append({
            "id": d_id,
            "player": d,
            "start": d_start,
            "rate": d_rate,
            "dist": d_dist,
            "time": d_time,
        })

    # --- First arriver -----------------------------------------------------
    first_arriver_entry = (
        min(traversals, key=lambda t: t["time"]) if traversals else None
    )
    t_first = first_arriver_entry["time"] if first_arriver_entry else float("inf")

    # --- End positions for racing defenders -------------------------------
    defender_end_coords: Dict[str, GridCoord] = {}
    if t_first < t_shooter:
        # Case A: first defender reached spot. Others freeze at t_first
        # interpolated positions, clamped.
        for t in traversals:
            if t is first_arriver_entry:
                defender_end_coords[t["id"]] = dict(defender_target)
            else:
                interp = _interpolated_position(
                    t["start"], defender_target, t["rate"], t_first
                )
                defender_end_coords[t["id"]] = _clamp_defender_freeze(
                    interp, t["start"]["x"], is_away_offense
                )
    else:
        # Case B: no defender reached spot by t_shooter. All at
        # interpolated t_shooter positions (no clamp — freeze never fired).
        for t in traversals:
            defender_end_coords[t["id"]] = _interpolated_position(
                t["start"], defender_target, t["rate"], t_shooter
            )

    # --- Contested decision: Euclidean + x-trail gate ---------------------
    contested, shot_defender_id = _pick_fb_shot_defender(
        traversals, defender_end_coords, shooter_target, is_away_offense
    )

    return {
        "shooter_target": shooter_target,
        "defender_target": defender_target,
        "defender_end_coords": defender_end_coords,
        "first_arriver_id": (
            first_arriver_entry["id"] if (first_arriver_entry and t_first < t_shooter) else None
        ),
        "contested": contested,
        "shot_defender_id": shot_defender_id,
        "t_shooter_game_seconds": float(t_shooter),
    }
