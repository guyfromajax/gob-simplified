"""Spatial screens, Stage A: aim the screener at the receiver's DEFENDER.

WHAT IS WRONG TODAY
-------------------
``defender_placement.build_all_animations`` sends a screener to
``OFFSET_SPOTS[location]`` — a fixed per-spot nudge off the *receiver's own named
spot*. It is a cosmetic anti-overlap table (``constants/__init__.py:600``, comment:
"Offset positions for collision handling"), and it knows nothing about any defender.

Measured over 6 games at production footing (3,162 screen ``pos_action``s,
``reports/spatial-screens-phase2.md``):

  * screener → receiver            p50 **4.0** grid  (p25 3.0, p90 4.0 — a fixed nudge)
  * screener → receiver's DEFENDER p50 **8.5** grid  (p25 6.0, p90 13.0)

So the screener is planted beside the man he is screening *for*, roughly two sprite
widths from the man he is supposed to be screening. Nothing is in anybody's way.

WHAT STAGE A DOES
-----------------
Put the screener on the segment from the receiver's defender toward where the receiver
is heading, one contact-distance in front of the defender — i.e. in the defender's path,
body-to-body, which is what setting a screen is.

NOT CLAIRVOYANT. Everything read is known when placement runs: the receiver's *authored*
next destination in the skeleton (the play's intent, which the screener is running too),
and the defender's coordinate at this step. It never reads the step's outcome — not the
shot, not the contest, not who ends up with the ball. The play call is knowledge the
screener has; the outcome is not.

NO NEW TUNING CONSTANT. The stand-off is ``collision_separation.separation_threshold``,
the Phase 1 per-pair contact distance already derived from the frontend's
``headRadiusForHeight`` sprite geometry. Two median players → 2.62 grid.

NO RNG. Pure geometry, no draw, on either side of the flag.

WHY IT IS A POST-PASS AND NOT AN EDIT AT defender_placement.py:223
------------------------------------------------------------------
Line 223 sits in the OFFENSE loop, which runs to completion before any defender is
placed — so at that line the receiver's defender does not have a coordinate yet. It
cannot: defenders are placed *against* the offence.

Running afterwards also keeps the dependency one-way. Defender placement reads the
offence; this reads the placed defenders. If the screen point fed back into defender
placement the two would be mutually recursive.

It must run BEFORE ``collision_separation``: that pass reads offensive coordinates to
decide which defenders are pinned on deliberate coverage, so it has to see the final
offence. And both must run before ``build_all_animations`` returns, because the freeze
stamp reads these coordinates back out — see the Phase 1 comment at the hook.

CONSEQUENCE, MEASURED NOT ASSUMED: the screener's OWN defender was placed against the
screener's pre-screen coordinate and is not re-placed. That is what Stage B's SWITCH /
FIGHT THROUGH / GO AROUND is for. The distribution is reported rather than papered over.

``GOB_SCREEN_TARGETING`` gates it, default OFF.
"""

from __future__ import annotations

import logging
import math
import os
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.utils.collision_separation import separation_threshold
from BackEnd.utils.screen_contest import (
    FIGHT_THROUGH, GO_AROUND, SWITCH, resolve_screen_contest, screen_contest_enabled,
    warn_if_contest_without_targeting,
)

#: The flag. Unset or anything other than "1" means OFF. Read at CALL time, not captured at
#: import: an import-time constant cannot be monkeypatched, and this is not a hot path.
SCREEN_TARGETING_FLAG = "GOB_SCREEN_TARGETING"

#: Stage A's proximity cap, its OWN flag, default OFF and NOT folded into Stage A.
#:
#: Stage A aims the screener at the receiver's DEFENDER. In sag and help defences that
#: defender is nowhere near the receiver, so the "screen" is dragged away from the play:
#: measured, screener -> receiver reaches p90 17.0 grid uncapped. A screen 17 units from
#: the man you are screening for is not a screen.
#:
#: With this on, a targeted point further than ``proximity_cap_distance()`` from the
#: receiver is REFUSED and that screen keeps today's OFFSET_SPOTS placement, counted. It
#: is not clamped onto the line: a clamped point is neither on the defender (so it screens
#: nobody) nor near the receiver (so it is not his screen) — it would be a third position
#: that is not a screen at all, and inventing one is worse than declining.
SCREEN_PROXIMITY_CAP_FLAG = "GOB_SCREEN_PROXIMITY_CAP"

#: Court bounds, in grid units. The 100x50 playing grid itself (``gridToPixels.js``), not a
#: chosen margin — a screen point outside it is off the floor.
COURT_MAX_X = 100.0
COURT_MAX_Y = 50.0

#: pos_action action label for a screen. Both spellings appear; ``ACTIONS["SCREEN"]`` is
#: itself the literal "screen" (constants/__init__.py:118).
SCREEN_ACTION = "screen"


def screen_targeting_enabled() -> bool:
    return os.environ.get(SCREEN_TARGETING_FLAG, "") == "1"


def screen_proximity_cap_enabled() -> bool:
    return os.environ.get(SCREEN_PROXIMITY_CAP_FLAG, "") == "1"


def proximity_cap_distance() -> float:
    """The house's EXISTING "close enough to contest" spatial gate, resolved at call time
    and never inlined: ``pass_contest.PASS_LANE_DIST`` = 8.0, which ``boxout_contest``
    already reused as ``BOXOUT_PAIR_RADIUS`` after deriving the same number independently
    from the pooled median shot-moment distance. No new tuning number is introduced here,
    and this one is not tuned."""
    from BackEnd.engine.pass_contest import PASS_LANE_DIST
    return float(PASS_LANE_DIST)


def _loc(action_info: Dict[str, Any]) -> Optional[str]:
    """Authored spot name. HCO/FCP author it under "location", HCT under "spot"."""
    if not isinstance(action_info, dict):
        return None
    return action_info.get("location") or action_info.get("spot") or None


def _action(action_info: Dict[str, Any]) -> str:
    if not isinstance(action_info, dict):
        return ""
    return (action_info.get("action") or "").lower().strip()


def derive_receiver(pos_actions: Dict[str, Any], screener_pos: str) -> Tuple[Optional[str], str]:
    """Who is this screen FOR?

    The playbook says so explicitly — ``{"type": "screen", "by": X, "for": Y}`` — but those
    events do NOT survive to the executed skeleton (audit:
    ``reports/overlap-and-screens-audit-2026-09-24.md``). What does survive is that the
    screener is authored to the receiver's OWN named spot, so the receiver is the other
    offensive position standing on the same ``location`` at this step.

    Measured: unique match on **87.3%** of screens (2,760 / 3,162). Ambiguity never
    occurred in 6 games but is handled anyway, by lineup-slot order, so the answer can
    never depend on dict iteration order.
    """
    loc = _loc(pos_actions.get(screener_pos))
    if not loc:
        return None, "no_location_on_screener"
    same = [p for p in sorted(pos_actions, key=str)
            if p != screener_pos and _loc(pos_actions.get(p)) == loc]
    if not same:
        return None, "none_same_location"
    if len(same) > 1:
        return same[0], "ambiguous_same_location"
    return same[0], "unique_same_location"


def receiver_next_location(steps: List[Dict[str, Any]], step_idx: int,
                           receiver_pos: str, screen_loc: str) -> Optional[str]:
    """Where the receiver is heading: his next AUTHORED spot after this step that differs
    from the screen spot. Play intent, not outcome — see the module docstring."""
    for later in steps[step_idx + 1:]:
        info = (later.get("pos_actions") or {}).get(receiver_pos)
        if not info:
            continue
        nxt = _loc(info)
        if nxt and nxt != screen_loc:
            return nxt
    return None


def resolve_receiver_guard(receiver_pos: str, step_idx: int, *, zone: bool,
                           guard_of: Dict[str, str], zone_assignments: Dict[Any, Any],
                           off_lineup: Dict[str, Any]) -> Optional[str]:
    """The defensive position guarding the receiver at this step, or None.

    Man reads the matchup map (100% resolved, 1,348 / 1,348). Zone reads
    ``zone_defender_assignments_by_step`` — the guard map the zone placement actually
    wrote — and legitimately resolves nothing when the receiver stands in an area no
    defender was assigned to. Measured: zone resolves **51.8%** (731 / 1,412). The man
    matchup dict is NOT a substitute in zone; nobody is playing man.
    """
    if not zone:
        return guard_of.get(receiver_pos)
    rpid = getattr((off_lineup or {}).get(receiver_pos), "player_id", None)
    if not rpid:
        return None
    row = (zone_assignments or {}).get(step_idx)
    if row is None:
        row = (zone_assignments or {}).get(str(step_idx)) or {}
    for dpos in sorted(row, key=str):          # sorted: never dict order
        opid = row.get(dpos)
        if opid and str(opid) == str(rpid):
            return dpos
    return None


def screen_point(defender_coord: Dict[str, float], receiver_dest: Dict[str, float],
                 screener: Any, defender: Any) -> Optional[Dict[str, float]]:
    """One contact-distance in front of the defender, along defender → receiver's
    destination. Returns None when the defender is already standing on that destination
    (no path, so no path to block) — the caller then falls back to today's placement.
    """
    vx = float(receiver_dest["x"]) - float(defender_coord["x"])
    vy = float(receiver_dest["y"]) - float(defender_coord["y"])
    length = math.hypot(vx, vy)
    if length < 1e-6:
        return None
    standoff = separation_threshold(screener, defender)
    return {
        "x": max(0.0, min(COURT_MAX_X, float(defender_coord["x"]) + vx / length * standoff)),
        "y": max(0.0, min(COURT_MAX_Y, float(defender_coord["y"]) + vy / length * standoff)),
    }


def _new_stats() -> Dict[str, Any]:
    return {
        "enabled": True,
        "screens": 0,
        "applied": 0,
        "fallback": Counter(),      # why today's OFFSET_SPOTS placement was kept
        "displacement": Counter(),  # how far the screener moved, 0.5 grid buckets
        # proximity cap (GOB_SCREEN_PROXIMITY_CAP)
        "cap_enabled": screen_proximity_cap_enabled(),
        "cap_refused": 0,
        "cap_gap": Counter(),       # target -> receiver gap, every screen the cap judged
        # Stage B (GOB_SCREEN_CONTEST)
        "contested": 0,
        "outcome": Counter(),
        "contest_skipped": Counter(),
        "switches_applied": 0,
    }


def apply_screen_targeting(animations, game, skeleton, off_lineup, def_lineup,
                           zone_assignments=None):
    """Retarget every resolvable screener in ``animations``, in place. Returns stats.

    Writes ONLY offensive screeners' coordinates. Defensive entries are read and never
    modified — Stage A moves no defender (Stage B does not move one either; it changes
    who guards whom). Consumes no RNG.

    Iteration is by step index then by sorted position, so the result cannot depend on
    dict order. Inert and allocation-free when the flag is off.
    """
    if not screen_targeting_enabled():
        # GOB_SCREEN_CONTEST=1 without GOB_SCREEN_TARGETING=1: say so ONCE and do nothing.
        # Stage B contests the screen Stage A places; half-applying it would score a
        # screen that is not where the contest assumes, and move the draws for no
        # modelled reason.
        if screen_contest_enabled():
            warn_if_contest_without_targeting()
        return {"enabled": False, "screens": 0, "applied": 0}

    from BackEnd.engine.defender_placement import (
        defender_grid_from_animations, offense_grid_from_animations)
    from BackEnd.utils.defense_utils import is_zone_defense
    from BackEnd.utils.man_defense_matchups import get_matchups_for_defending_team
    from BackEnd.constants import HCO_STRING_SPOTS

    stats = _new_stats()
    steps = (skeleton or {}).get("steps") or []
    if not steps or not off_lineup or not def_lineup:
        return stats

    anim_by_pid = {a.get("playerId"): a for a in (animations or []) if a.get("playerId")}
    dgrid = defender_grid_from_animations(animations, def_lineup, len(steps))
    # Only the cap needs the offence's own positions, so it is only built when the cap is on.
    cap_on = screen_proximity_cap_enabled()
    ogrid = offense_grid_from_animations(animations, off_lineup, steps) if cap_on else {}
    cap_distance = proximity_cap_distance() if cap_on else 0.0

    game_state = getattr(game, "game_state", {}) or {}
    zone = bool(is_zone_defense(game_state.get("defense_playcall", "man")))
    try:
        defending_is_user = game.defense_team.team_id == game.user_team.team_id
    except Exception:
        defending_is_user = False
    matchups = get_matchups_for_defending_team(game_state, defending_is_user) or {}
    guard_of = {off: dfn for dfn, off in matchups.items()}      # {off_pos: def_pos}

    for step_idx, step in enumerate(steps):
        pos_actions = step.get("pos_actions") or {}
        timestamp = step.get("timestamp", 0)
        # Re-read per step so a Stage B SWITCH earlier in this possession is visible to
        # every later screen. With GOB_SCREEN_CONTEST off no override is ever written, so
        # this returns the same map every step and Stage A's behaviour is unchanged.
        matchups = get_matchups_for_defending_team(game_state, defending_is_user) or {}
        guard_of = {off: dfn for dfn, off in matchups.items()}
        for screener_pos in sorted(pos_actions, key=str):
            if _action(pos_actions.get(screener_pos)) != SCREEN_ACTION:
                continue
            stats["screens"] += 1

            screen_loc = _loc(pos_actions.get(screener_pos))
            receiver_pos, why = derive_receiver(pos_actions, screener_pos)
            if not receiver_pos:
                stats["fallback"][why] += 1
                continue

            guard_pos = resolve_receiver_guard(
                receiver_pos, step_idx, zone=zone, guard_of=guard_of,
                zone_assignments=zone_assignments, off_lineup=off_lineup)
            if not guard_pos:
                stats["fallback"]["no_guard_" + ("zone" if zone else "man")] += 1
                continue
            defender_coord = (dgrid.get(step_idx) or {}).get(guard_pos)
            if not defender_coord:
                stats["fallback"]["guard_has_no_coord"] += 1
                continue

            dest_loc = receiver_next_location(steps, step_idx, receiver_pos, screen_loc)
            if not dest_loc:
                stats["fallback"]["receiver_not_heading_anywhere"] += 1
                continue
            dest_coord = HCO_STRING_SPOTS.get(dest_loc)
            if not dest_coord:
                stats["fallback"]["dest_spot_unknown"] += 1
                continue
            # The defender grid is in PLAYED orientation; the authored spot table is in home
            # orientation. Flip the destination to match before taking the direction.
            if _is_away_offense(game):
                from BackEnd.utils.shared import get_away_player_coords
                dest_coord = get_away_player_coords(dest_coord)

            screener = (off_lineup or {}).get(screener_pos)
            defender = (def_lineup or {}).get(guard_pos)
            entry = _movement_entry(anim_by_pid, screener, timestamp)
            if entry is None:
                stats["fallback"]["screener_has_no_movement_entry"] += 1
                continue

            target = screen_point(defender_coord, dest_coord, screener, defender)
            if target is None:
                stats["fallback"]["defender_already_at_destination"] += 1
                continue

            # ── Proximity cap (GOB_SCREEN_PROXIMITY_CAP, default OFF) ─────────────────
            # Refuse a "screen" that would land further than the house's contest radius
            # from the man it is supposedly for. Falls back to today's placement and is
            # counted, exactly like every other Stage A fallback. Unreachable with
            # targeting off, because the function has already returned by then.
            if cap_on:
                receiver_coord = (ogrid.get(step_idx) or {}).get(receiver_pos)
                if receiver_coord is None:
                    stats["fallback"]["cap_receiver_has_no_coord"] += 1
                    continue
                gap = math.hypot(float(target["x"]) - float(receiver_coord["x"]),
                                 float(target["y"]) - float(receiver_coord["y"]))
                stats["cap_gap"][round(round(gap / 0.5) * 0.5, 2)] += 1
                if gap > cap_distance:
                    stats["fallback"]["cap_too_far_from_receiver"] += 1
                    stats["cap_refused"] += 1
                    continue

            before = entry["coords"]
            moved = math.hypot(float(target["x"]) - float(before["x"]),
                               float(target["y"]) - float(before["y"]))
            entry["coords"] = target
            _resync_start_end(anim_by_pid.get(getattr(screener, "player_id", None)))
            stats["applied"] += 1
            stats["displacement"][round(round(moved / 0.5) * 0.5, 2)] += 1

            # ── Stage B: contest the screen that was just placed ──────────────────────
            # Only reachable from inside this branch, so the draw cannot happen for a
            # screen that was never placed — the flag gates the DRAW, not just its effect.
            if screen_contest_enabled():
                _contest_one(stats, game, game_state, step_idx, dgrid, anim_by_pid,
                             screener_pos=screener_pos, receiver_pos=receiver_pos,
                             guard_pos=guard_pos, screener=screener, defender=defender,
                             zone=zone, matchups=matchups, guard_of=guard_of,
                             off_lineup=off_lineup, def_lineup=def_lineup,
                             screen_coord=target)

    stats["fallback"] = dict(stats["fallback"])
    stats["displacement"] = dict(stats["displacement"])
    stats["outcome"] = dict(stats["outcome"])
    stats["contest_skipped"] = dict(stats["contest_skipped"])
    stats["cap_gap"] = dict(stats["cap_gap"])
    return stats


def _is_away_offense(game) -> bool:
    try:
        return game.offense_team.team_id == game.away_team.team_id
    except Exception:
        return False


def _movement_entry(anim_by_pid, player, timestamp):
    """The screener's movement entry for THIS step.

    An offensive player's ``movement`` only gains an entry on steps where he has a
    ``pos_action``, so ``movement[step_idx]`` is not step ``step_idx`` — the same trap
    ``offense_grid_from_animations`` documents. Match on the entry's own timestamp.
    """
    pid = getattr(player, "player_id", None)
    anim = anim_by_pid.get(pid) if pid else None
    if not anim:
        return None
    for entry in anim.get("movement") or []:
        if entry.get("timestamp") == timestamp:
            coords = entry.get("coords")
            if isinstance(coords, dict) and coords.get("x") is not None:
                return entry
            return None
    return None


def _resync_start_end(anim) -> None:
    """``start``/``end`` are the first/last movement coords, captured during the build. If
    the retargeted step was the first or last, they must follow — otherwise the entry
    disagrees with its own movement list."""
    if not anim:
        return
    movement = anim.get("movement") or []
    if not movement:
        return
    anim["start"] = movement[0]["coords"]
    anim["end"] = movement[-1]["coords"]


# ── Stage B (GOB_SCREEN_CONTEST) ──────────────────────────────────────────────────────


def _contest_one(stats, game, game_state, step_idx, dgrid, anim_by_pid, *,
                 screener_pos, receiver_pos, guard_pos, screener, defender,
                 zone, matchups, guard_of, off_lineup, def_lineup, screen_coord):
    """Resolve one placed screen. See ``screen_contest`` for the model.

    ZONE IS SKIPPED, DELIBERATELY. A switch is a man concept — it swaps two *assignments*,
    and in a zone there are none to swap; the guard map is rebuilt per step from who
    happens to stand in which area. Contesting in zone would roll dice whose SWITCH branch
    has nowhere to write. Counted, not silently dropped.
    """
    if zone:
        stats["contest_skipped"]["zone"] += 1
        return
    screener_guard_pos = guard_of.get(screener_pos)
    if not screener_guard_pos:
        stats["contest_skipped"]["screener_has_no_guard"] += 1
        return
    screener_defender = (def_lineup or {}).get(screener_guard_pos)
    if defender is None or screener_defender is None:
        stats["contest_skipped"]["defender_missing_from_lineup"] += 1
        return

    result = resolve_screen_contest(defender, screener, screener_defender)
    stats["contested"] += 1
    stats["outcome"][result["outcome"]] += 1

    if result["outcome"] == FIGHT_THROUGH:
        return                      # he stays with his man; nothing moves, nothing swaps

    if result["outcome"] == GO_AROUND:
        _detour(dgrid, anim_by_pid, def_lineup, step_idx, guard_pos, screen_coord,
                screener, defender)
        return

    # SWITCH — the two defenders trade assignments for the rest of the possession.
    # The stored map is NOT mutated; this writes the override layer, which
    # get_matchups_for_defending_team lays over the stored map on every read.
    #
    # `matchups` is re-read here rather than reused from the caller: a possession can
    # contain more than one screen, and a second switch must compose with the first
    # instead of overwriting it from a map captured before either happened.
    from BackEnd.utils.man_defense_matchups import set_matchup_override
    current = dict(_current_matchups(game, game_state))
    current[guard_pos], current[screener_guard_pos] = screener_pos, receiver_pos
    set_matchup_override(game_state, current)
    stats["switches_applied"] += 1


def _current_matchups(game, game_state):
    from BackEnd.utils.man_defense_matchups import get_matchups_for_defending_team
    try:
        defending_is_user = game.defense_team.team_id == game.user_team.team_id
    except Exception:
        defending_is_user = False
    return get_matchups_for_defending_team(game_state, defending_is_user) or {}


def _detour(dgrid, anim_by_pid, def_lineup, step_idx, guard_pos, screen_coord,
            screener, defender):
    """GO AROUND: the beaten defender takes the long way and arrives a body-width late.

    He is pushed one contact-distance further from the screen, directly away from it —
    the same derived ``separation_threshold`` Stage A uses for the stand-off, so this
    introduces no constant of its own. He is never teleported to the far side: going
    around is arriving late, not arriving somewhere else.
    """
    coord = (dgrid.get(step_idx) or {}).get(guard_pos)
    if not coord:
        return
    vx = float(coord["x"]) - float(screen_coord["x"])
    vy = float(coord["y"]) - float(screen_coord["y"])
    length = math.hypot(vx, vy)
    if length < 1e-6:
        return
    lag = separation_threshold(screener, defender)
    new_coord = {
        "x": max(0.0, min(COURT_MAX_X, float(coord["x"]) + vx / length * lag)),
        "y": max(0.0, min(COURT_MAX_Y, float(coord["y"]) + vy / length * lag)),
    }
    pid = getattr((def_lineup or {}).get(guard_pos), "player_id", None)
    anim = anim_by_pid.get(pid) if pid else None
    if not anim:
        return
    movement = anim.get("movement") or []
    if step_idx >= len(movement):
        return
    # Defender movement lists ARE step-indexed (one entry per step, unlike the offence) —
    # that is the contract defender_grid_from_animations relies on.
    movement[step_idx]["coords"] = new_coord
    dgrid.setdefault(step_idx, {})[guard_pos] = new_coord
    _resync_start_end(anim)
