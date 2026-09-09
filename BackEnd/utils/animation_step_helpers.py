"""Shared helpers for animation step emitters.

Consolidates math + lookup helpers that multiple emitters (CR FB, RR FB,
HCT, HCO/skeleton, DREB) would otherwise duplicate. New emitters should
import from here; existing emitters (CR, RR) currently keep local copies
of the underlying helpers (``_safe_id``, ``_euclid``, etc.) and only
import the cross-cutting writers like ``stamp_tween_durations`` — full
consolidation of the older emitters is a separate cleanup pass.

Currently provides ``stamp_tween_durations`` — the per-player duration
computation that ensures fast-finishing players don't get their tweens
stretched across the gating player's step duration. See
``UESS_System.md`` §3 (``tween_durations`` / ``stamp_tween_durations``).
"""

from BackEnd.utils.sim_random import sim_rng as random
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from BackEnd.constants.announcement_constants import ANNOUNCEMENT_FREEZE_HOLD_MS
from BackEnd.utils.animation_step_schema import GridCoord, PlayerAction, PlayerArchetype


# --- Universal foul-contact rattle -----------------------------------------
# On a hard collision that draws a foul (D_FOUL / O_FOUL / charge / blocking), BOTH involved sprites
# shake. The FE already renders a `rattle` flourish (flourishes.js `runRattle`) with a `foul_rattle_mult`
# that scales it above a normal shot-contest rattle. This is the ONE turn-type-agnostic writer — call it
# from any foul finalization (HCO drive, FB/HCT cutoff, shot foul, …) instead of each stamping its own.
FOUL_CONTACT_RATTLE_MULT = 1.6      # foul rattle amplitude vs a shot-contest rattle (× on the FE)
FOUL_CONTACT_RATTLE_CYCLES = 4


def stamp_foul_contact_rattle(
    step: Optional[Dict[str, Any]],
    player_ids,
    *,
    mult: float = FOUL_CONTACT_RATTLE_MULT,
    cycles: int = FOUL_CONTACT_RATTLE_CYCLES,
) -> None:
    """Stamp a `rattle` flourish on EACH of ``player_ids`` (the fouler + the fouled) on
    ``step.start.flourish`` so both sprites shake on a foul collision. Turn-type agnostic. Render-only
    + UESS-safe (never mutates gameplay coords). Wrapped so a stamping error can never break a turn."""
    try:
        if step is None:
            return
        flourish = step.setdefault("start", {}).setdefault("flourish", {})
        for pid in player_ids:
            if pid is None:
                continue
            flourish[str(pid)] = {
                "kind": "rattle",
                "cycles": int(cycles),
                "foul_rattle_mult": float(mult),
            }
    except Exception:
        pass


# --- Idle wander on STILL players ------------------------------------------
# Measured on the played arm, 8 games: 45.6% of player-steps are STILL (start coords == end
# coords), against the 16.3% whole-step freeze rate Defect 4 was framed around. The whole-step
# framing counted a step where three players move and seven stand around as "not frozen"; the eye
# sees seven dead players. This is the writer that puts a render-space idle on those players.
#
# It runs as a POST-PASS over a fully assembled step list, not inside an emitter's build loop,
# because stillness is a property of `start.coords` vs `end.coords` and the end coords are not
# settled until post-shot sub-steps and overlays have been applied.
#
# UESS-safe: only ever writes `step.start.flourish`. Never touches coords, step count, or
# sim_rng — every random-looking value here is a crc32 of the player id, so the draw stream is
# untouched and the emitted-step diff can carry nothing but `flourish`.
IDLE_STILL_MIN_STEP_MS = 60.0          # deadAirLedger.js:87 MIN_RECORDED_MS — below this nobody
                                       # perceives motion, so a still player needs no idle.
IDLE_STILL_DENSITY_CAP = 6             # Max players given an idle on one step, of ten.
# NOTE ON AMPLITUDE. This writer stamps the style's UNSCALED amplitude. The reduction for still
# players (ship default -40%) lives in animation_config.js `flourish.idleWander.byFamily[*]
# .amplitudeScale`, deliberately, so the number a human turns is the number he is thinking about
# rather than a multiplier on a multiplier. Do not add a second scale here.
IDLE_CLOCK_MS_PER_GAME_SEC = 350.0     # mirrors FE gameClock.tickMs default
IDLE_STILL_DEFAULT_STYLE = "survey_rock"


def _idle_crc(*parts: Any) -> int:
    """Stable non-sim_rng integer from arbitrary parts. crc32, NOT ``hash()`` — Python's hash is
    salted per process unless PYTHONHASHSEED is pinned, and this has to reproduce in production."""
    import zlib

    return zlib.crc32("|".join(str(p) for p in parts).encode()) & 0x7FFFFFFF


def idle_step_duration_ms(step: Optional[Dict[str, Any]]) -> float:
    """Wall-clock duration of a step, resolved the way the FE resolves it: an explicit
    ``advance_trigger.metadata.wall_clock_hold_ms`` wins, else the clock burn scaled by
    ms-per-game-second."""
    if not isinstance(step, dict):
        return 0.0
    meta = ((step.get("start") or {}).get("advance_trigger") or {}).get("metadata") or {}
    hold = meta.get("wall_clock_hold_ms")
    if isinstance(hold, (int, float)) and hold > 0:
        return float(hold)
    try:
        return float((step.get("end") or {}).get("time_elapsed")) * IDLE_CLOCK_MS_PER_GAME_SEC
    except (TypeError, ValueError):
        return 0.0


def _idle_is_still(a: Any, b: Any) -> bool:
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    try:
        return abs(float(b["x"]) - float(a["x"])) < 1e-6 and abs(float(b["y"]) - float(a["y"])) < 1e-6
    except (KeyError, TypeError, ValueError):
        return False


def stamp_idle_wander_on_still_players(
    steps: Optional[List[Dict[str, Any]]],
    *,
    family: str,
    exclude=(),
    on_court=None,
    only_step_kinds=None,
    cap: int = IDLE_STILL_DENSITY_CAP,
    min_step_ms: float = IDLE_STILL_MIN_STEP_MS,
    default_style: str = IDLE_STILL_DEFAULT_STYLE,
) -> int:
    """Give every STILL player on ``steps`` a render-space ``idle_wander`` flourish. Returns the
    number of player-stamps written.

    ``family`` is stamped onto each flourish so ``animation_config.js`` can override style and
    amplitude per family without a backend round-trip.

    ``exclude`` skips players with a real job (the inbounding passer, the free-throw shooter).
    ``on_court`` restricts stamping to a known lineup — BASELINE_INBOUND steps carry 16-20 player
    ids in ``start.coords``, so without this the renderer is handed sprites for players who are
    not in the game. ``only_step_kinds`` restricts to specific ``advance_trigger.metadata.kind``
    values (used to hit ``make_hold`` without touching the rest of a MAKE turn).

    SELECTION UNDER THE CAP is ordered by how long the player has been still, then by a crc32 of
    his player id. Run length first is both better aimed and MORE stable than a plain hash: a
    selected player's run only ever lengthens, so he keeps his slot for as long as he stands
    there, and a newly-still player starts at the back and cannot displace him. That avoids the
    flicker failure — players popping in and out of idling between steps reads as broken in a way
    that uniform stillness does not.
    """
    if not steps:
        return 0
    try:
        from BackEnd.engine.motion_step_decision import SUBTLE_IDLE_STYLE_AMPLITUDE_GRID
    except Exception:  # pragma: no cover - amplitude table is advisory
        SUBTLE_IDLE_STYLE_AMPLITUDE_GRID = {}

    excluded = {str(p) for p in (exclude or ()) if p is not None}
    allowed = {str(p) for p in on_court} if on_court is not None else None
    kinds = {str(k) for k in only_step_kinds} if only_step_kinds else None
    still_runs: Dict[str, int] = {}
    written = 0

    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        # Params the HCO resolver already rolled for this beat (geography-aware style +
        # direction). Popped, not read: it must never reach the emitted payload, because the gate
        # permits `flourish` and nothing else to differ.
        rolled = step.pop("_idle_rolled", None) or {}
        start = step.get("start") or {}
        start_coords = start.get("coords") or {}
        end_coords = (step.get("end") or {}).get("coords") or {}

        still_now = []
        for pid, start_coord in start_coords.items():
            end_coord = end_coords.get(pid)
            if end_coord is None:
                continue
            if _idle_is_still(start_coord, end_coord):
                key = str(pid)
                still_runs[key] = still_runs.get(key, 0) + 1
                still_now.append(key)
            else:
                still_runs.pop(str(pid), None)

        if kinds is not None:
            meta = (start.get("advance_trigger") or {}).get("metadata") or {}
            if str(meta.get("kind")) not in kinds:
                continue
        # A still player in a sub-perceptible step does not need an idle. His run length still
        # accrues above, so he keeps his priority once a longer step comes along.
        if idle_step_duration_ms(step) < min_step_ms:
            continue

        flourish = start.get("flourish") or {}
        candidates = [
            pid for pid in still_now
            if pid not in excluded
            and pid not in flourish          # never clobber a reach_in / rattle / dunk
            and (allowed is None or pid in allowed)
        ]
        if not candidates:
            continue
        candidates.sort(key=lambda pid: (-still_runs.get(pid, 0), _idle_crc(pid)))
        if cap is not None and cap >= 0:
            candidates = candidates[:cap]

        target = step.setdefault("start", {}).setdefault("flourish", {})
        for pid in candidates:
            params = rolled.get(pid) or {}
            style = str(params.get("style") or default_style)
            base_amplitude = params.get("amplitude_grid", params.get("radius_grid"))
            if not isinstance(base_amplitude, (int, float)):
                base_amplitude = SUBTLE_IDLE_STYLE_AMPLITUDE_GRID.get(style, 0.8)
            dir_x, dir_y = params.get("dir_x"), params.get("dir_y")
            if not isinstance(dir_x, (int, float)) or not isinstance(dir_y, (int, float)):
                # No rolled direction (the widened families never had one). Derive a stable
                # per-player bearing from the id so each man sways his own way.
                angle = (_idle_crc(pid, family, "dir") % 3600) / 3600.0 * 6.283185307
                import math

                dir_x, dir_y = math.cos(angle), math.sin(angle)
            target[pid] = {
                "kind": "idle_wander",
                "family": family,
                "style": style,
                # crc32, not rng.randint: phase_resolution.py:4811 draws its seed from sim_rng,
                # and any new stamp doing that would consume draws and move the draw count.
                "seed": _idle_crc(pid, family, index),
                "dir_x": round(float(dir_x), 3),
                "dir_y": round(float(dir_y), 3),
                "amplitude_grid": round(float(base_amplitude), 3),
            }
            written += 1

    return written


# --- Arrival-tail fill (defect 2) ----------------------------------------------------------
#
# A player who reaches his target before the step ends stands dead for the remainder. Measured
# on 8 played games with a seeded plays catalogue: 703.4 s per game, 31.7% of the wall time
# moving sprites are on screen, 51.5% of moving player-steps affected.
#
# THE TAIL IS A DELIBERATE DECISION, NOT A BUG. `stamp_tween_durations` caps each tween at the
# player's natural travel time precisely so he does not glide slower than his attributes justify
# — the docstring names "lazy drift" as the anti-pattern it is avoiding, and that judgement was
# correct. A court of players moving at wrong speeds reads worse than a court of players
# standing still. What the author lacked was anything to put in the gap. So this FILLS the tail
# instead of stretching the tween: no duration changes anywhere, no timing blast radius.
#
# THE GATE IS ONE LINE — tail over a threshold — not a list of continuity classes. The classes
# were for sizing: 71.4% of all dead time sits in one-step journeys and only 13.0% in pure
# arrivals, so a rule keyed on "ARRIVING" would reach an eighth of the problem. Tail size is the
# thing that decides whether a human can see it.
ARRIVAL_SETTLE_FAMILY = "arrival_settle"
ARRIVAL_SETTLE_HARD_FLOOR_MS = IDLE_STILL_MIN_STEP_MS   # 60ms; 24.7% of tails, never stamped
ARRIVAL_SETTLE_DEFAULT_STYLE = "jockey"
ARRIVAL_SETTLE_CLOCK_MS_PER_GAME_SEC = IDLE_CLOCK_MS_PER_GAME_SEC


def _arrival_tail_ms(step: Dict[str, Any], pid: str, step_wall_ms: float) -> float:
    """Wall-clock ms this player spends standing at his destination after arriving.

    Mirrors the frontend exactly, floors included, because a max(50, ...) on both sides changes
    the answer for short steps:
      animationPlayback.js:1307-1310  playerMs = max(50, round(tween_durations[pid] * 350))
                                      ... falling back to the STEP duration when absent
    A player with no `tween_durations` entry tweens for the whole step, so his tail is zero by
    construction and he is not a candidate.
    """
    tw = ((step.get("start") or {}).get("tween_durations") or {}).get(pid)
    if not isinstance(tw, (int, float)) or tw <= 0:
        return 0.0
    player_ms = max(50.0, round(float(tw) * ARRIVAL_SETTLE_CLOCK_MS_PER_GAME_SEC))
    return max(0.0, step_wall_ms - player_ms)


def stamp_arrival_settle(
    steps: Optional[List[Dict[str, Any]]],
    *,
    cap: int = IDLE_STILL_DENSITY_CAP,
    min_tail_ms: float = ARRIVAL_SETTLE_HARD_FLOOR_MS,
    default_style: str = ARRIVAL_SETTLE_DEFAULT_STYLE,
) -> int:
    """Fill arrival tails with a delayed ``idle_wander``. Returns player-stamps written.

    Reuses the shipped wander mechanism rather than inventing a second one; the only new fields
    are ``family="arrival_settle"``, ``delay_ms`` and ``tail_ms``.

    ONE DENSITY CAP, SHARED. The cap counts idlers ALREADY stamped on the step by the
    still-player pass and only fills the headroom that is left. Two independent caps would let a
    step carry the cap twice over, and a court with twice the intended number of men shifting
    about is the "busy" failure this cap exists to prevent. Because the still-player pass runs
    inside the emitters and this runs at the end of the turn, "already stamped" is simply
    whatever is in ``start.flourish`` by the time we get here.

    ``delay_ms`` is the player's own tween duration, so the wander starts as he stops.
    ``tail_ms`` is carried so the FRONTEND can raise the threshold without a backend round-trip
    — the floor here is a hard perceptibility limit, not Jamie's tuning knob.
    """
    if not steps:
        return 0
    try:
        from BackEnd.engine.motion_step_decision import SUBTLE_IDLE_STYLE_AMPLITUDE_GRID
    except Exception:  # pragma: no cover - amplitude table is advisory
        SUBTLE_IDLE_STYLE_AMPLITUDE_GRID = {}
    import math

    floor = max(float(min_tail_ms), ARRIVAL_SETTLE_HARD_FLOOR_MS)
    written = 0
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        start = step.get("start")
        if not isinstance(start, dict):
            continue
        coords = start.get("coords")
        if not isinstance(coords, dict):
            continue
        step_wall_ms = idle_step_duration_ms(step)
        if step_wall_ms <= floor:
            continue
        existing = start.get("flourish") or {}
        # Shared-cap headroom. Any flourish already on the step owns that sprite — a reach_in or
        # a rattle must never be clobbered, and a still-player wander already counts as an idler.
        headroom = cap - sum(1 for f in existing.values()
                             if (f or {}).get("kind") == "idle_wander")
        if cap is not None and cap >= 0 and headroom <= 0:
            continue

        candidates = []
        for pid in coords:
            if pid in existing:
                continue
            tail = _arrival_tail_ms(step, pid, step_wall_ms)
            if tail < floor:
                continue
            candidates.append((pid, tail))
        if not candidates:
            continue
        # Longest dead gap first, then a stable crc32 tiebreak. Ranking by tail is both better
        # aimed than a hash and stable for the same reason run-length is in the still-player
        # pass: it is a property of the step, not of a shuffle.
        candidates.sort(key=lambda c: (-c[1], _idle_crc(c[0], ARRIVAL_SETTLE_FAMILY)))
        if cap is not None and cap >= 0:
            candidates = candidates[:headroom]

        target = start.setdefault("flourish", {})
        for pid, tail in candidates:
            angle = (_idle_crc(pid, ARRIVAL_SETTLE_FAMILY, "dir") % 3600) / 3600.0 * 6.283185307
            target[pid] = {
                "kind": "idle_wander",
                "family": ARRIVAL_SETTLE_FAMILY,
                "style": default_style,
                # crc32 of the player id, never rng.randint: a sim_rng draw here would move the
                # draw count and fail the gate.
                "seed": _idle_crc(pid, ARRIVAL_SETTLE_FAMILY, index),
                "dir_x": round(math.cos(angle), 3),
                "dir_y": round(math.sin(angle), 3),
                "amplitude_grid": round(
                    float(SUBTLE_IDLE_STYLE_AMPLITUDE_GRID.get(default_style, 0.8)), 3),
                "delay_ms": round(step_wall_ms - tail, 1),
                "duration_ms": round(tail, 1),
                "tail_ms": round(tail, 1),
            }
            written += 1
    return written


# --- Continuity-aware movement curves (defect 1) -------------------------------------------
#
# Easing a player tween per STEP is worse than linear. A player crossing the floor over four
# steps toward one destination would decelerate and re-accelerate at every boundary — four
# pulses instead of one movement. Measured on the played arm, 28.9% of moving player-steps are
# mid-journey and 48.2% of journeys span more than one step, so that is not a corner case.
#
# So the curve is a property of the JOURNEY, not the step, and the only fact needed to pick it
# is whether the player was moving in the neighbouring steps. The backend authors that fact —
# it holds the whole step list at emit time — and stamps an INTENT name. The frontend maps the
# name to a Phaser curve via animation_config.js. Deliberately not a Phaser easing string here:
# the backend should not know what a renderer calls its curves, and Jamie retunes the mapping
# without a backend round-trip.
#
# Linear is the default and is NOT stamped. A step with no entry renders linear, so mid-journey
# and still players cost nothing in payload — only the three eased cases are written.
MOVEMENT_CURVE_KEY = "movement_curve"
MOVEMENT_CURVE_DEPART = "ease_in"       # leaves rest, keeps going next step
MOVEMENT_CURVE_ARRIVE = "ease_out"      # was moving, comes to rest after this step
MOVEMENT_CURVE_SINGLE = "ease_in_out"   # the whole journey is this one step


def _curve_moves(step: Any, pid: str) -> bool:
    """Does this player move on this step? The defect-4 stillness test, inverted.

    Reuses ``_idle_is_still`` rather than restating the comparison. Five instruments in this
    workstream have been wrong; this one is shipped and has a poisoned guard over it.
    """
    if not isinstance(step, dict):
        return False
    start = ((step.get("start") or {}).get("coords") or {}).get(pid)
    end = ((step.get("end") or {}).get("coords") or {}).get(pid)
    if not isinstance(start, dict) or not isinstance(end, dict):
        return False
    return not _idle_is_still(start, end)


def stamp_movement_curves(steps: Optional[List[Dict[str, Any]]]) -> int:
    """Stamp a per-player movement-curve intent on ``steps``. Returns entries written.

    Writes ``step["start"]["movement_curve"][player_id]`` for the three eased cases only.

    A neighbour that is missing — the first or last step of the turn, or a player absent from
    the adjacent step's coord map — counts as REST. The emitted payload does not show the
    journey continuing, and assuming continuation across a boundary we cannot see is the
    mistake that made CONTINUE_FROM_PREVIOUS unshippable. A player who really does carry on
    into the next turn gets one extra deceleration at the seam, which is the conservative
    failure: a stop that should have been smooth, not a pulse that should not exist.

    No duration floor, unlike the idle stamp. The 60ms perceptibility floor exists there
    because an idle wander ADDS motion that nobody can see; a curve only reshapes motion that
    is already happening and costs nothing extra to evaluate. Flooring it would make a journey
    whose last step is short snap to a halt, which is the defect being removed.
    """
    if not steps:
        return 0
    written = 0
    n = len(steps)
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        start_block = step.get("start")
        if not isinstance(start_block, dict):
            continue
        coords = start_block.get("coords")
        if not isinstance(coords, dict):
            continue
        prev_step = steps[i - 1] if i > 0 else None
        next_step = steps[i + 1] if i + 1 < n else None
        curves: Dict[str, str] = {}
        for pid in coords:
            if not _curve_moves(step, pid):
                continue
            came_from_rest = not _curve_moves(prev_step, pid)
            goes_to_rest = not _curve_moves(next_step, pid)
            if came_from_rest and goes_to_rest:
                curves[pid] = MOVEMENT_CURVE_SINGLE
            elif came_from_rest:
                curves[pid] = MOVEMENT_CURVE_DEPART
            elif goes_to_rest:
                curves[pid] = MOVEMENT_CURVE_ARRIVE
            # else: mid-journey. Left unstamped so it renders linear.
        if curves:
            existing = start_block.get(MOVEMENT_CURVE_KEY)
            if isinstance(existing, dict):
                existing.update(curves)
            else:
                start_block[MOVEMENT_CURVE_KEY] = curves
            written += len(curves)
    return written


def build_final_coords(game: Any) -> Dict[str, GridCoord]:
    """Snapshot every on-court player's current ``player.coords`` as a flat
    ``{player_id: {x, y}}`` dict. Stamped on each turn_result after
    ``sync_lineup_coords_from_turn`` so cross-turn bridges can read the
    prior turn's end coords from a single canonical source — rather than
    parsing turn-type-specific animation shapes (OT ``animations[].end``,
    HCO ``movement[N]``, FB ``coords``, etc.).
    """
    out: Dict[str, GridCoord] = {}
    for team in (getattr(game, "offense_team", None), getattr(game, "defense_team", None)):
        lineup = getattr(team, "lineup", {}) if team else {}
        for player in lineup.values():
            if player is None:
                continue
            pid = getattr(player, "player_id", None)
            coords = getattr(player, "coords", None)
            if pid is None or not isinstance(coords, dict):
                continue
            x = coords.get("x")
            y = coords.get("y")
            if x is None or y is None:
                continue
            out[str(pid)] = {"x": float(x), "y": float(y)}
    return out


def build_final_ball_handler_id(turn_result: Dict[str, Any]) -> Optional[str]:
    """Resolve who held the ball at the END of this turn. Used by HCO entry
    orchestrator (Handoff / Kickout / Walk Up decisions) to know who the
    "current BH" is at the next turn's start.

    Source priority:
      1. Last step's ``end.ball.owner_player_id`` from ``animation_steps``
         (BallAttached). Definitive — backend-built unified payload.
      2. ``turn_result["ball_handler_id"]`` — top-level stamp used by legacy
         turns (e.g., OPENING_TIP stamps the tip winner here).
      3. ``roles.ball_handler`` (Player object or id) — fallback for legacy
         turns that set roles but not ball_handler_id. NOTE: for HCO shot
         turns this resolves to the SHOOTER, not the step 0 BH — fine for
         "who has the ball at turn end" semantics (shooter just took the
         shot), but means HCO turn won't be a meaningful source on its own
         (next turn after a shot is BIP/DREB which has its own BH stamp).
      4. ``None`` — ambiguous (e.g., HCO MAKE end has ball in flight through
         the net; no clear holder until the next turn establishes one).
    """
    if not isinstance(turn_result, dict):
        return None

    # STEAL: possession flips — the stealer owns the ball at turn end even when
    # the last loop segment still shows the victim holding (dynamic FCP/HCT).
    result_type = str(turn_result.get("result_type") or "").upper()
    if result_type == "STEAL":
        stealer_id = turn_result.get("stealer_id") or turn_result.get("stealerId")
        if stealer_id:
            return str(stealer_id)

    steps = turn_result.get("animation_steps")
    if isinstance(steps, list) and steps:
        drawn_idx, last = last_rendered_step(steps)
        if drawn_idx is not None and drawn_idx != len(steps) - 1:
            logging.warning(
                "[UESS UNRENDERED] final_ball_handler_id skipped undrawn tail: "
                "last_rendered=%d array_tail=%d",
                drawn_idx,
                len(steps) - 1,
            )
        if isinstance(last, dict):
            end_ball = (last.get("end") or {}).get("ball") or {}
            if isinstance(end_ball, dict):
                owner = end_ball.get("owner_player_id")
                if owner:
                    return str(owner)

    top_level_bh = turn_result.get("ball_handler_id")
    if top_level_bh:
        return str(top_level_bh)

    roles = turn_result.get("roles") or {}
    bh = roles.get("ball_handler") if isinstance(roles, dict) else None
    if bh is None:
        return None
    # `roles.ball_handler` appears in three shapes across turn types: a bare id,
    # a Player object, or a serialized dict ({player_id, name, team}). The dict
    # form was previously unhandled — `getattr(dict, "player_id")` is None — so
    # a turn whose only surviving handle was a serialized role resolved to None.
    # That let the HCO entry orchestrator lose `current_bh_id` and cold-start
    # the possession (= teleport). See `_resolve_prior_ball_handler_id`.
    if isinstance(bh, (str, int)):
        pid = bh
    elif isinstance(bh, dict):
        pid = bh.get("player_id") or bh.get("playerId")
    else:
        pid = getattr(bh, "player_id", None)
    return str(pid) if pid else None


def build_final_ball_coords(
    turn_result: Dict[str, Any],
    final_coords: Optional[Dict[str, GridCoord]] = None,
) -> Optional[GridCoord]:
    """Snapshot the ball's actual rendered rest position at turn end, mirroring
    the FE's ``ballCoordFromState``:

      - BallAttached  → the owner's end coord (last step's ``end.coords``,
        falling back to ``final_coords``).
      - BallInFlight  → ``current_coords``.
      - BallLoose     → ``coords``.

    Returns ``{x, y}`` or ``None`` when there is no unified payload to read.
    Stamped alongside ``final_ball_handler_id`` so the next turn's entry
    orchestrator can carry the ball's *true rest position* across the turn seam
    (UESS §8.4 invariant 4) instead of re-deriving it from the owner's coord
    alone — the source of intermittent ball teleports at ownership/turn seams.
    """
    if not isinstance(turn_result, dict):
        return None
    steps = turn_result.get("animation_steps")
    if not (isinstance(steps, list) and steps):
        return None
    drawn_idx, last = last_rendered_step(steps)
    if drawn_idx is not None and drawn_idx != len(steps) - 1:
        logging.warning(
            "[UESS UNRENDERED] final_ball_coords skipped undrawn tail: "
            "last_rendered=%d array_tail=%d",
            drawn_idx,
            len(steps) - 1,
        )
    if not isinstance(last, dict):
        return None
    end = last.get("end") or {}
    ball = end.get("ball") or {}
    if not isinstance(ball, dict):
        return None

    def _xy(c: Any) -> Optional[GridCoord]:
        if not isinstance(c, dict):
            return None
        x, y = c.get("x"), c.get("y")
        if x is None or y is None:
            return None
        return {"x": float(x), "y": float(y)}

    # In-flight / loose carry an explicit ball coord.
    inflight = _xy(ball.get("current_coords"))
    if inflight is not None:
        return inflight
    loose = _xy(ball.get("coords"))
    if loose is not None:
        return loose

    # Attached → owner's end coord (schema keys ball position to the owner).
    owner = ball.get("owner_player_id")
    if owner is not None:
        end_coords = end.get("coords") or {}
        oc = _xy(end_coords.get(str(owner)) if str(owner) in end_coords else end_coords.get(owner))
        if oc is not None:
            return oc
        if isinstance(final_coords, dict):
            fc = _xy(final_coords.get(str(owner)) if str(owner) in final_coords else final_coords.get(owner))
            if fc is not None:
                return fc
    return None


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


def _euclid(a: GridCoord, b: GridCoord) -> float:
    dx = a["x"] - b["x"]
    dy = a["y"] - b["y"]
    return (dx * dx + dy * dy) ** 0.5


def _motion_end_toward_dest(
    start_coord: GridCoord,
    dest_coord: GridCoord,
    rate: float,
    step_t: float,
) -> Tuple[GridCoord, float]:
    """Interrupted end coord + tween duration (UESS §9.5). Mirrors
    ``skeleton_step_emitter._interpolate_step_end``."""
    dist = _euclid(start_coord, dest_coord)
    if dist < 1e-6 or rate <= 0 or step_t <= 0:
        return dict(start_coord), 0.0
    natural_t = dist / rate
    if natural_t <= step_t:
        return dict(dest_coord), float(natural_t)
    frac = (rate * step_t) / dist
    x = start_coord["x"] + (dest_coord["x"] - start_coord["x"]) * frac
    y = start_coord["y"] + (dest_coord["y"] - start_coord["y"]) * frac
    return {"x": float(x), "y": float(y)}, float(step_t)


def floor_step_t_to_traversal(
    step_t: float,
    start_coord: Optional[GridCoord],
    dest_coord: Optional[GridCoord],
    rate: float,
) -> float:
    """Floor a step duration so a mover can actually cover ``start→dest`` at
    ``rate`` without jetting.

    Fast-break meet/shot steps derive their ``T`` from ball-flight or backend
    drive times computed off a different reference position than the sprite's
    rendered spot. When that ``T`` is shorter than the mover's real traversal,
    ``stamp_tween_durations`` caps the tween at ``T`` and the frontend crams the
    full distance into it → a jet. Flooring ``T`` at the natural traversal time
    keeps the mover at his archetype rate. Universal across FB emitters (RR,
    Triangle, after-steal, covert-release) so the timing math has one home.
    """
    if not start_coord or not dest_coord or rate <= 0:
        return float(step_t)
    dist = _euclid(start_coord, dest_coord)
    if dist < 1e-6:
        return float(step_t)
    return max(float(step_t), dist / rate)


def rebound_attemptor_ids(
    offense_rebounders: Optional[List[Any]],
    defense_rebounders: Optional[List[Any]],
    rebounder_id: str,
) -> List[str]:
    """Player IDs who crash the boards (prior MISS turn lists), minus captor."""
    captor = str(rebounder_id)
    seen: set[str] = set()
    out: List[str] = []
    for pid in (offense_rebounders or []) + (defense_rebounders or []):
        if pid is None:
            continue
        sid = str(pid)
        if not sid or sid == captor or sid in seen:
            continue
        seen.add(sid)
        out.append(sid)
    return out


def sample_rebound_collapse_target(
    bounce_coords: GridCoord,
    *,
    result_type: Optional[str] = "MISS",
) -> GridCoord:
    """Near-bounce spot for a non-captor attemptor (legacy FE: ±4 x, ±6 y)."""
    from BackEnd.utils.shared import clamp_animation_grid_coords

    x = float(bounce_coords["x"]) + random.randint(-4, 4)
    y = float(bounce_coords["y"]) + random.randint(-6, 6)
    clamped = clamp_animation_grid_coords({"x": x, "y": y}, result_type)
    return clamped if clamped else {"x": x, "y": y}


def stamp_rebound_capture_player_motion(
    *,
    start_coords: Dict[str, GridCoord],
    end_coords: Dict[str, GridCoord],
    destinations: Dict[str, Optional[GridCoord]],
    actions: Dict[str, PlayerAction],
    archetypes: Dict[str, PlayerArchetype],
    tween_durations: Dict[str, float],
    rebounder_id: str,
    bounce_coords: GridCoord,
    attemptor_ids: List[str],
    step_t: float,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    attemptor_archetype: PlayerArchetype = "standard",
) -> None:
    """Write rebound-capture motion: captor → bounce; attemptors → bounce±offset."""
    attemptor_set = set(attemptor_ids)
    for pid, start in start_coords.items():
        if pid == rebounder_id:
            end_coords[pid] = {
                "x": float(bounce_coords["x"]),
                "y": float(bounce_coords["y"]),
            }
            destinations[pid] = dict(bounce_coords)
            actions[pid] = "cut"
            archetypes[pid] = "sprint"
            player = _player_lookup_by_id(off_lineup, def_lineup, pid)
            rate = _ag_grid_per_game_sec(player, "sprint")
            ec, dur = _motion_end_toward_dest(start, bounce_coords, rate, step_t)
            end_coords[pid] = ec
            if dur > 0:
                tween_durations[pid] = dur
            continue
        if pid in attemptor_set:
            dest = sample_rebound_collapse_target(bounce_coords)
            player = _player_lookup_by_id(off_lineup, def_lineup, pid)
            rate = _ag_grid_per_game_sec(player, attemptor_archetype)
            ec, dur = _motion_end_toward_dest(start, dest, rate, step_t)
            end_coords[pid] = ec
            destinations[pid] = dest
            actions[pid] = "cut"
            archetypes[pid] = attemptor_archetype
            if dur > 0:
                tween_durations[pid] = dur
            continue
        end_coords[pid] = dict(start)
        destinations[pid] = None
        actions[pid] = "stationary"
        archetypes[pid] = "stationary"


def _ag_grid_per_game_sec(player: Any, archetype: PlayerArchetype) -> float:
    """grid/game-sec rate for a player at a given archetype. Each archetype
    has an absolute rate at AG=50 (see ``CRUISE_GRID_PER_GAME_SEC`` etc.);
    other AG values scale proportionally via the AG curve anchored at
    AG=50 → 14. ``archetype="standard"`` is the unscaled base rate.
    """
    try:
        from BackEnd.utils.shared import ag_to_grid_per_game_sec
        from BackEnd.constants import (
            BURST_GRID_PER_GAME_SEC,
            CRUISE_GRID_PER_GAME_SEC,
            DRIFT_GRID_PER_GAME_SEC,
            STANDARD_GRID_PER_GAME_SEC,
            SHOT_MOTION_GRID_PER_GAME_SEC,
            SPRINT_GRID_PER_GAME_SEC,
        )
    except Exception:
        return 14.0

    if player is None:
        ag = 50
    else:
        attrs = getattr(player, "attributes", None) or {}
        ag = attrs.get("AG", 50) if isinstance(attrs, dict) else 50
    # AG scale factor: at AG=50 → 1.0; scales other AG values proportionally.
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
    if archetype == "drift":
        return DRIFT_GRID_PER_GAME_SEC * ag_scale
    # Unknown / fallback → base rate. The canonical name is "standard"; any
    # unrecognized archetype string defensively resolves here.
    return STANDARD_GRID_PER_GAME_SEC * ag_scale


#: Public alias — **the** archetype rate function. Step emitters must import
#: this rather than keep a local copy.
#:
#: `rim_runner_step_emitter` and `covert_release_step_emitter` each carried a
#: near-identical private copy, and both were missing the ``drift`` branch, so
#: drift silently resolved to ``standard`` (14 instead of 8 — a 75% overspeed)
#: anywhere those emitters ran. Their docstrings had also gone stale, still
#: claiming an AG=50 anchor of 12 after ``STANDARD_GRID_PER_GAME_SEC`` moved to
#: 14. Adding an archetype in one place and not the other three is the failure
#: mode; one implementation removes it.
ag_grid_per_game_sec = _ag_grid_per_game_sec


def drift_or_hold_coord(
    player: Any,
    start: GridCoord,
    basket: GridCoord,
    seconds: float,
    probability: float,
    rng: Any = None,
) -> Tuple[Dict[str, float], bool]:
    """Per-player drift roll for HCT off-ball movement.

    With chance ``probability`` the player **drifts** toward ``basket`` at the
    ``"drift"`` archetype rate (AG-scaled) for ``seconds`` (never overshooting the
    rim); otherwise he **holds** at ``start``. Returns ``(coord, drifted)``.
    """
    r = rng or random
    sx, sy = float(start["x"]), float(start["y"])
    if r.random() >= float(probability):
        return {"x": sx, "y": sy}, False
    rate = _ag_grid_per_game_sec(player, "drift")
    travel = rate * float(seconds)
    dx, dy = float(basket["x"]) - sx, float(basket["y"]) - sy
    dist = (dx * dx + dy * dy) ** 0.5
    if dist <= 1e-9 or travel <= 0:
        return {"x": sx, "y": sy}, False
    f = min(1.0, travel / dist)
    return {"x": sx + dx * f, "y": sy + dy * f}, True


# --- SFX tier helpers ------------------------------------------------------

_SFX_DEFAULT_VOLUME = 0.7


def _player_attr(player: Any, key: str) -> Optional[float]:
    """Return ``player.attributes[key]`` as a float, or None if unavailable."""
    if player is None:
        return None
    attrs = getattr(player, "attributes", None) or {}
    if not isinstance(attrs, dict):
        return None
    val = attrs.get(key)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def pass_release_sfx(passer_player: Any) -> Dict[str, Any]:
    """Pick the pass release SFX based on the passer's PS attribute.

    Tiers per ``SFX_System.md``:
      - PS > 75 → ``pass-strong.wav``
      - PS < 25 → ``pass-weak.wav``
      - else    → ``pass-medium.wav``
    """
    ps = _player_attr(passer_player, "PS")
    if ps is not None and ps > 75:
        tier = "strong"
    elif ps is not None and ps < 25:
        tier = "weak"
    else:
        tier = "medium"
    return {
        "file": f"pass-{tier}.wav",
        "volume": _SFX_DEFAULT_VOLUME,
        "event": "pass_release",
    }


def pass_arrival_sfx(receiver_player: Any) -> Dict[str, Any]:
    """Pick the reception SFX based on the receiver's (IQ + CH) attributes.

    Tiers per ``SFX_System.md``:
      - (IQ + CH) > 130 → ``receive-strong.wav``
      - (IQ + CH) < 50  → ``receive-weak.wav``
      - else            → ``receive-medium.wav``
    """
    iq = _player_attr(receiver_player, "IQ")
    ch = _player_attr(receiver_player, "CH")
    score = (iq or 0.0) + (ch or 0.0)
    if score > 130:
        tier = "strong"
    elif score < 50:
        tier = "weak"
    else:
        tier = "medium"
    return {
        "file": f"receive-{tier}.wav",
        "volume": _SFX_DEFAULT_VOLUME,
        "event": "pass_receive",
    }


# --- Shot SFX helpers (SFX_System.md §Shot Audio) -----------------


def shot_launch_sfx(
    shot_score_pre_defense: Any, result_type: Any = None
) -> Optional[Dict[str, Any]]:
    """Pick the shot-release SFX file from the pre-defense shot score tier.

    Tiers per ``SFX_System.md``:
      - score < 101  → ``three-weak.wav``
      - score > 210  → ``three-strong.wav``
      - else         → ``shot-standard.wav``

    Blocked shots override the score tiers: ``result_type == "BLOCK"`` →
    ``block1.wav`` (SFX_System.md "Blocked Shot Attempts"). The block result is
    already known here because the backend resolves the full turn before
    emitting steps.

    Returns ``None`` when the score is unavailable (and not a block); caller
    omits the cue rather than firing a default file.
    """
    if str(result_type or "").upper() == "BLOCK":
        return {
            "file": "block1.wav",
            "volume": _SFX_DEFAULT_VOLUME,
            "event": "shot_block",
        }
    if shot_score_pre_defense is None:
        return None
    try:
        score = float(shot_score_pre_defense)
    except (TypeError, ValueError):
        return None
    if score < 101:
        file = "three-weak.wav"
        tier = "weak"
    elif score > 210:
        file = "three-strong.wav"
        tier = "strong"
    else:
        file = "shot-standard.wav"
        tier = "medium"
    return {
        "file": file,
        "volume": _SFX_DEFAULT_VOLUME,
        "event": f"shot_release_{tier}",
    }


def shot_launch_sfx_free_throw() -> Dict[str, Any]:
    """FT launch cue — always ``shot-standard.wav`` (SFX_System.md)."""
    return {
        "file": "shot-standard.wav",
        "volume": _SFX_DEFAULT_VOLUME,
        "event": "shot_release_free_throw",
    }


def stamp_hot_shot_trail_metadata(
    metadata: Dict[str, Any],
    shot_score_pre_defense: Any,
) -> None:
    """Flag ``hot_shot_trail`` on step metadata when pre-defense score exceeds
    the strong tier (> 210). FE ``renderBallTransition`` reads this on schema
    ``[ball_flight]`` steps (same threshold as ``three-strong.wav``)."""
    try:
        if shot_score_pre_defense is not None and float(shot_score_pre_defense) > 210:
            metadata["hot_shot_trail"] = True
    except (TypeError, ValueError):
        pass


# Variants whose final result SFX is driven by the variant's own animation
# (per-hop rattles, etc.) rather than a single arrival cue. The
# [ball_flight] step omits ``sfx_on_ball_arrival`` for these; the hop
# sub-steps stamp per-hop cues instead.
_VARIANT_RESULT_SFX_BY_ANIMATION = frozenset(
    {"LITTLE_RATTLE", "NORMAL_RATTLE", "HEAVY_RATTLE"}
)


def shot_result_sfx(
    shot_variant: Optional[str],
    result_type: str,
    bank_miss_sfx_file: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Pick the primary shot-arrival SFX file from the resolved variant.

    Matches the variant → file mapping in ``SFX_System.md``
    §SFX Bindings. Returns ``None`` for RATTLE variants — their per-hop
    cues fire on the hop sub-steps instead.

    ``bank_miss_sfx_file`` is the pre-rolled 50/50 choice (bb-clank.wav vs.
    bb-clank-2.wav) stamped by ``roll_shot_variant_extras`` so replays
    stay deterministic.
    """
    if shot_variant in _VARIANT_RESULT_SFX_BY_ANIMATION:
        return None

    variant = (shot_variant or "").upper()
    rt = (result_type or "").upper()

    file: Optional[str] = None
    if variant == "SWISH":
        file = "swish.wav"
    elif variant == "CLANK":
        file = "clank.wav"
    elif variant == "BACK_OF_RIM":
        file = "back-of-rim.wav"
    elif variant == "BANK_MAKE":
        file = "bb-rim-swish.wav"
    elif variant == "BANK_MISS":
        file = bank_miss_sfx_file or "bb-clank.wav"
    elif variant == "AIRBALL":
        file = "airball.wav"
    elif variant == "FREE_THROW_SWISH":
        file = "free-throw-swish.wav"
    elif variant == "FREE_THROW_MISS":
        file = "free-throw-miss.wav"
    else:
        # Unknown / missing variant — outcome-based fallback so the audio
        # layer never goes silent on a resolved shot.
        if rt == "MAKE":
            file = "swish.wav"
        elif rt in ("MISS", "BLOCK"):
            file = "clank.wav"

    if file is None:
        return None
    return {
        "file": file,
        "volume": _SFX_DEFAULT_VOLUME,
        "event": f"shot_result_{rt.lower() or 'unknown'}",
    }


def dunk_make_sfx() -> Dict[str, Any]:
    """Primary arrival SFX for a made dunk slam (SFX_System.md § Dunk).

    Stamped on the terminal dunk micro beat as ``sfx_on_ball_arrival``; the FE
    plays it at the slam (``dunkPlayback.js``), same schema path as ``swish.wav``
    on a clean make."""
    return {
        "file": "dunk-sfx.wav",
        "volume": _SFX_DEFAULT_VOLUME,
        "event": "shot_result_make_dunk",
    }


def dunk_miss_sfx() -> Dict[str, Any]:
    """Primary arrival SFX for a missed dunk at rim contact.

    Stamped only when the resolved dunk micro beat carries ``dunk_miss: true``.
    The FE plays it at the same slam timing as a made dunk's arrival cue.
    """
    return {
        "file": "missed-dunk.wav",
        "volume": _SFX_DEFAULT_VOLUME,
        "event": "shot_result_miss_dunk",
    }


def shot_followup_timed_sfx(
    shot_variant: Optional[str],
    result_type: str,
    *,
    make_settle_sfx_file: str = "swish.wav",
) -> Optional[list]:
    """Per-variant delayed follow-up cues stamped on ``step.start.timed_sfx``.
    FE schedules each cue at ``delay_ms`` **after ball arrival** (ball tween
    onComplete), not from step start.

      - BANK_MAKE       → settle file at +100 ms after bb-rim-swish.wav
      - BACK_OF_RIM make → settle file at +150 ms after back-of-rim.wav

    ``make_settle_sfx_file`` defaults to ``swish.wav`` for field goals; free
    throws pass ``free-throw-swish.wav``.
    """
    variant = (shot_variant or "").upper()
    rt = (result_type or "").upper()
    settle = make_settle_sfx_file or "swish.wav"
    cues: list = []
    if variant == "BANK_MAKE" and rt == "MAKE":
        cues.append({
            "file": settle,
            "delay_ms": 100.0,
            "volume": _SFX_DEFAULT_VOLUME,
            "event": "shot_result_bank_make_swish",
        })
    elif variant == "BACK_OF_RIM" and rt == "MAKE":
        cues.append({
            "file": settle,
            "delay_ms": 150.0,
            "volume": _SFX_DEFAULT_VOLUME,
            "event": "shot_result_bor_make_swish",
        })
    return cues or None


def rattle_hop_sfx() -> Dict[str, Any]:
    """SFX cue fired when the ball lands on a single rattle hop (arrival)."""
    return {
        "file": "rattle-leather.wav",
        "volume": _SFX_DEFAULT_VOLUME,
        "event": "shot_result_rattle_hop",
    }


def rattle_make_settle_sfx(
    *,
    make_settle_sfx_file: str = "swish.wav",
) -> Dict[str, Any]:
    """Terminal swish on a RATTLE make (fires when ball settles into MSSS
    after the final hop)."""
    return {
        "file": make_settle_sfx_file or "swish.wav",
        "volume": _SFX_DEFAULT_VOLUME,
        "event": "shot_result_rattle_make_swish",
    }


def rebase_animation_step_next_indices(
    steps: List[Any],
    base_index: int,
) -> None:
    """Offset ``next_step`` / branch indices when appending onto a parent sequence.

    Drive-resolution emitters build a local ``steps`` list with indices
    0, 1, …; when that list is ``extend``'d after burst/outlet/setup steps,
    every pointer must shift by ``len(parent_steps)`` or playback loops.
    """
    if base_index <= 0 or not steps:
        return
    for step in steps:
        if not isinstance(step, dict):
            continue
        nxt = (step.get("end") or {}).get("next")
        if not isinstance(nxt, dict):
            continue
        kind = nxt.get("kind")
        if kind == "next_step" and "index" in nxt:
            nxt["index"] = int(nxt["index"]) + base_index
        elif kind == "branch" and "next_step_index" in nxt:
            nxt["next_step_index"] = int(nxt["next_step_index"]) + base_index


def stamp_tween_durations(
    start: Dict[str, Any],
    end_coords: Dict[str, GridCoord],
    step_t: float,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> None:
    """Stamp per-player tween durations (game-seconds) on
    ``start["tween_durations"]``. For each player who moves:
    ``duration = min(distance / rate, step_t)``. Stationary players omitted.

    Without this, the playback engine falls back to step T per player,
    which stretches fast finishers' tweens — the "lazy drift" anti-pattern.
    With this, each player tweens for their natural duration then idles at
    their end coord until step T elapses.
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


# ----------------------------------------------------------------------------
# Step-announcement helpers
# ----------------------------------------------------------------------------
#
# UESS step emitters emit announcement dicts via `step["end"]["announcement"]`
# (or directly on the step) that the frontend's runStepAnnouncement picks up.
# The frontend reads SFX from `announcement.meta.sfx` (architecture comment
# at animationPlayback.js:631 — "SFX comes from announcement.meta.sfx
# (backend-stamped); no FE hardcode."). Building these dicts inline is
# error-prone — the OTB foul on rebound shipped without `meta.sfx` and was
# silent for weeks. Use this helper instead so the whistle SFX is impossible
# to forget.
#
# SFX key resolution lives in gameSfx.js — `"foul"` → `whistle-1-lowervol.wav`
# today. Other foul-type SFX keys can be added there without touching emitters.


def build_foul_announcement(
    text: str,
    team: str,
    fouler_id: Any,
    *,
    hold_ms: int = ANNOUNCEMENT_FREEZE_HOLD_MS,
    style: str = "primary",
    sfx_key: str = "foul",
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Canonical UESS step-announcement dict for any foul event.

    Stamps ``meta.sfx = sfx_key`` (default ``"foul"`` → whistle) so the
    whistle SFX always fires at announcement mount. This is the single
    place foul announcements should be constructed inside UESS step
    emitters; bypassing it risks silent whistles (see dreb_step_emitter
    OTB regression that motivated this helper).

    Args:
        text: Announcement headline (e.g. "Over The Back!",
            "Shooting Foul!", "BLOCKING FOUL!"). Frontend renders verbatim.
        team: Announcement-team key, one of ``"home"`` / ``"away"`` /
            ``"neutral"``. Drives accent color on the overlay card.
        fouler_id: Player ID of the foul committer; coerced to str.
        hold_ms: How long the overlay stays on screen. Defaults to
            ``ANNOUNCEMENT_FREEZE_HOLD_MS``.
            matches existing foul announcements.
        style: ``"primary"`` (default) or ``"shooting_foul"`` — the
            latter triggers the dual-row chrome on the frontend.
        sfx_key: Key resolved by gameSfx.js. Default ``"foul"`` →
            ``whistle-1-lowervol.wav``. Override only if a specific foul
            type wants a different sound (e.g. shot-clock violation uses
            ``"shot_clock_violation"`` → ``whistle-3.mp3``).
        extra_meta: Optional dict merged into ``meta`` alongside the SFX
            key. Use for foul-type-specific metadata (decision pills,
            etc.) without overriding ``meta.sfx``.

    Returns:
        Announcement dict ready to assign to ``step["end"]["announcement"]``
        or used directly as ``announcement`` on a step.
    """
    meta: Dict[str, Any] = {"sfx": sfx_key}
    if extra_meta:
        # Caller-supplied meta is merged last so explicit overrides win, but
        # we re-apply sfx_key at the end so a caller can't accidentally
        # drop the whistle by passing extra_meta={"sfx": None}.
        meta.update(extra_meta)
        meta["sfx"] = sfx_key
    return {
        "text": text,
        "team": team,
        "hold_ms": hold_ms,
        "style": style,
        "player_data": {"playerId": str(fouler_id) if fouler_id is not None else ""},
        "meta": meta,
    }


def enforce_step_start_continuity(
    steps: Optional[List[Dict[str, Any]]],
    *,
    context: str = "",
) -> int:
    """UESS §8.1 guard: step N+1 ``start.coords`` MUST equal step N ``end.coords``
    per player. Returns the number of corrections made.

    Same rule and same mechanism as the HCO skeleton emitter, which enforces it
    inline while building (``skeleton_step_emitter.py:2128-2138``)::

        start_coords = {**anim_start, **prior_end}

    HCO can do it at build time because it owns the whole loop. The fast-break
    emitters assemble their step list from several independent builders, so the
    equivalent point for them is a sweep over the finished list — the merge is
    identical, only its timing differs.

    WHY IT LOGS. A silent repair here would be worse than no guard. The renderer
    never draws ``start.coords`` (it snaps to ``end.coords`` and skips the tween
    when start == end, ``animationPlayback.js:1302``/``:1526``), so a
    discontinuity shows up either as a teleport or as a player sliding along a
    path nobody authored. Quietly rewriting the start coord converts the first
    into the second and buries the cause. This corrects the frame AND says so,
    so the next instance is a log line rather than an archaeology exercise. See
    bugs.md item 40.
    """
    if not steps or len(steps) < 2:
        return 0
    import logging

    fixed = 0
    for i in range(1, len(steps)):
        prev_end = ((steps[i - 1].get("end") or {}).get("coords")) or {}
        cur = steps[i].get("start")
        if not isinstance(cur, dict):
            continue
        cur_coords = cur.get("coords")
        if not isinstance(cur_coords, dict) or not prev_end:
            continue
        for pid, pe in prev_end.items():
            cc = cur_coords.get(pid)
            if not isinstance(pe, dict) or not isinstance(cc, dict):
                continue
            if (abs(float(cc.get("x", 0.0)) - float(pe.get("x", 0.0))) > 1e-6
                    or abs(float(cc.get("y", 0.0)) - float(pe.get("y", 0.0))) > 1e-6):
                logging.warning(
                    "[UESS 8.1] discontinuity corrected%s: step %d player %s "
                    "start=(%.2f,%.2f) prior end=(%.2f,%.2f)",
                    (" " + context) if context else "", i, pid,
                    float(cc.get("x", 0.0)), float(cc.get("y", 0.0)),
                    float(pe.get("x", 0.0)), float(pe.get("y", 0.0)),
                )
                cur_coords[pid] = dict(pe)
                fixed += 1
    return fixed


# --- Unrendered-tail + §8.4 ball-owner seam ---------------------------------
# Both are log-and-assert. They do not rewrite steps. A silent repair here is
# the item 41 failure mode: the defect measures zero and the investigation ends.


def rendered_step_indices(
    steps: Optional[Sequence[Any]],
    *,
    max_guard: int = 200,
) -> List[int]:
    """Mirror ``animationPlayback.js playTurn``: follow ``end.next`` from index 0
    and stop at the first ``turn_stop`` / ``end_of_turn``. Returns the indices
    the renderer actually executes, in order.
    """
    if not isinstance(steps, list) or not steps:
        return []
    i, n, seen, order = 0, 0, set(), []
    while 0 <= i < len(steps) and n < max_guard:
        step = steps[i]
        if not isinstance(step, dict):
            break
        if i in seen:
            break
        seen.add(i)
        order.append(i)
        n += 1
        nxt = (step.get("end") or {}).get("next")
        if not isinstance(nxt, dict):
            break
        kind = nxt.get("kind")
        if kind in ("turn_stop", "end_of_turn"):
            break
        if kind == "next_step":
            j = nxt.get("index")
            if j == i or j is None:
                i = i + 1
            else:
                i = int(j)
        elif kind == "branch":
            i = int(nxt.get("next_step_index", i + 1))
        else:
            break
    return order


def last_rendered_step_index(
    steps: Optional[Sequence[Any]],
    *,
    max_guard: int = 200,
) -> Optional[int]:
    """Index of the last step ``playTurn`` draws, or None if it draws none."""
    order = rendered_step_indices(steps, max_guard=max_guard)
    return order[-1] if order else None


def last_rendered_step(
    steps: Optional[Sequence[Any]],
) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
    """``(index, step)`` for the last drawable step. ``(-1, steps[-1])`` is the
    array tail and is NOT a substitute — that is the item 41/42 defect.
    """
    if not isinstance(steps, list) or not steps:
        return None, None
    idx = last_rendered_step_index(steps)
    if idx is None or not (0 <= idx < len(steps)) or not isinstance(steps[idx], dict):
        return None, None
    return idx, steps[idx]


def _coord_tail_delta_ft(
    drawn: Optional[Dict[str, Any]],
    tail: Optional[Dict[str, Any]],
) -> Tuple[float, int]:
    """Worst per-player end-coord distance (grid-ft) between two steps."""
    if not isinstance(drawn, dict) or not isinstance(tail, dict):
        return 0.0, 0
    rc = (drawn.get("end") or {}).get("coords") or {}
    ac = (tail.get("end") or {}).get("coords") or {}
    worst, moved = 0.0, 0
    if not isinstance(rc, dict) or not isinstance(ac, dict):
        return 0.0, 0
    for pid in set(rc) & set(ac):
        a, b = rc[pid], ac[pid]
        if not (isinstance(a, dict) and isinstance(b, dict)):
            continue
        try:
            dd = (
                (float(a.get("x", 0.0)) - float(b.get("x", 0.0))) ** 2
                + (float(a.get("y", 0.0)) - float(b.get("y", 0.0))) ** 2
            ) ** 0.5
        except (TypeError, ValueError):
            continue
        if dd > 1e-6:
            moved += 1
        worst = max(worst, dd)
    return worst, moved


def announce_unrendered_tail(
    steps: Optional[List[Dict[str, Any]]],
    *,
    context: str = "",
) -> int:
    """Assert no array slot sits after the terminal ``turn_stop``.

    Log only — the extra steps are left in place so a census can still see
    them. Returns the number of undrawn tail slots. Policy 26b: names the
    last drawn index, the array tail, and the coordinate delta the sync
    would have ingested.
    """
    if not isinstance(steps, list) or not steps:
        return 0
    drawn_idx = last_rendered_step_index(steps)
    tail_idx = len(steps) - 1
    if drawn_idx is None or drawn_idx == tail_idx:
        return 0
    extra = tail_idx - drawn_idx
    worst, moved = _coord_tail_delta_ft(steps[drawn_idx], steps[tail_idx])
    logging.warning(
        "[UESS UNRENDERED] emitter produced steps after turn_stop%s: "
        "last_rendered=%d array_tail=%d extra=%d worst_delta=%.2f ft "
        "moved_players=%d",
        (" " + context) if context else "",
        drawn_idx,
        tail_idx,
        extra,
        worst,
        moved,
    )
    return extra


def attached_owner_id(ball: Any) -> Optional[str]:
    """Frontend ``isBallAttached``: the KEY's presence, not its truthiness.

    Returns None when the ball is not attached (key absent / no ball object).
    Returns ``""`` for the empty-string owner (item 44). Those two must not
    collapse — collapsing them is how a comparison becomes a tautology.
    """
    if not isinstance(ball, dict):
        return None
    if "owner_player_id" not in ball:
        return None
    owner = ball.get("owner_player_id")
    if owner is None:
        return ""
    return str(owner)


def _step_transfer_label(step: Optional[Dict[str, Any]]) -> Optional[str]:
    """Name an authored transfer beat, or None. Used in the announcement so a
    seam swap sitting on a fumble/steal/rebound/pass is distinguishable from a
    naked swap — it does NOT exempt the swap. Accounting is a within-step
    owner change or a BallInFlight, per UESS §8.4 invariant 2.
    """
    if not isinstance(step, dict):
        return None
    start = step.get("start") or {}
    end = step.get("end") or {}
    flourish = start.get("flourish") if isinstance(start, dict) else None
    if isinstance(flourish, dict):
        for payload in flourish.values():
            if isinstance(payload, dict) and payload.get("kind") == "fumble":
                return "fumble"
    nxt = end.get("next") if isinstance(end, dict) else None
    if isinstance(nxt, dict) and nxt.get("kind") == "turn_stop":
        event = str(nxt.get("event") or "").upper()
        if event in ("STEAL", "DEAD_BALL_TURNOVER", "DEAD_BALL", "TURNOVER"):
            return event.lower()
        if event in ("SHOT_ATTEMPT", "MAKE", "MISS"):
            return "shot"
    trigger = start.get("advance_trigger") if isinstance(start, dict) else None
    if isinstance(trigger, dict):
        cond = str(trigger.get("condition") or "")
        if cond in ("ball_reaches_player", "player_reaches_position", "dead_ball_fumble"):
            return cond
    actions = start.get("action") if isinstance(start, dict) else None
    if isinstance(actions, dict):
        for act in actions.values():
            if str(act) in ("pass", "pass_ball", "make_pass", "receive"):
                return "pass"
    return None


def announce_ball_owner_seam(
    steps: Optional[List[Dict[str, Any]]],
    *,
    context: str = "",
    family: str = "",
) -> int:
    """UESS §8.4 invariant 2: an attached-owner change across a step seam is a
    teleport. The FE does not tween seams (``setPosition`` snap).

    A change is accounted for only when it happens WITHIN a step (start A,
    end B) or via ``BallInFlight``. A fumble/steal/rebound/pass *label* on
    the later step does not exempt a seam swap — that is item 47: the
    turnover beat starts already attached to the new man.

    Log only. Does not rewrite ``owner_player_id``. Returns the violation count.
    """
    order = rendered_step_indices(steps)
    if len(order) < 2:
        return 0
    fam = family or context or "?"
    violations = 0
    for a_idx, b_idx in zip(order, order[1:]):
        prev_end = attached_owner_id(((steps[a_idx].get("end") or {}).get("ball")))
        cur_start = attached_owner_id(((steps[b_idx].get("start") or {}).get("ball")))
        if prev_end is None or cur_start is None:
            continue
        if prev_end == cur_start:
            continue
        violations += 1
        label = _step_transfer_label(steps[b_idx]) or "none"
        logging.warning(
            "[UESS 8.4] unaccounted owner change%s: step %d->%d "
            "end_owner=%s start_owner=%s family=%s beat=%s",
            (" " + context) if context else "",
            a_idx,
            b_idx,
            json_owner(prev_end),
            json_owner(cur_start),
            fam,
            label,
        )
    return violations


def json_owner(owner: str) -> str:
    """Quote empty-string owners so they do not render as nothing."""
    return '""' if owner == "" else owner
