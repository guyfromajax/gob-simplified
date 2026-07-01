"""After-Steal Fast Break animation step emitter.

Pure schema renderer for after-steal FBs. The backend resolver
(``after_steal_fast_break.resolve_after_steal_fast_break``) precomputes
all 10 players' end coords + the contested decision; this emitter just
builds the schema steps.

Step structure
--------------
1. **Drive step** — single step, all 10 players sprint to their backend-
   computed end positions:
   - Stealer (= ball handler) → ``bh_target`` (2-3 grid spots out from
     basket, y ∈ [19, 31])
   - Defenders → either at the defender single target (first arriver) or
     frozen/clamped intermediate positions; or interpolated at t_shooter
     if no defender reached the spot
   - Other 4 offensive players → unique sampled HCO setup spots,
     interpolated at t_shooter
   - Ball stays attached to the stealer
   - "Fast Break!" announcement on ``start``
   - Advance trigger: ``player_reaches_position`` keyed to the stealer
     hitting the BH target; ``T_game_seconds`` from the backend
2. **Post-shot sub-steps** — appended via skeleton's
   ``_build_post_shot_sub_steps`` (shared with HCO / OREB):
   - ball flight (variant-aware launch + arrival SFX)
   - variant sub-steps (RATTLE hops / BANK / etc.)
   - hold-with-"Fast Break Score!" on make, or bounce on miss
   - shooting-foul-on-miss announcement stamped on the terminal step

Make announcement override: skeleton's ``_build_make_hold_sub_step``
emits "It's Good!" by default; post-processing rewrites it to "Fast
Break Score!" (and "Fast Break Score! And 1!" for the and-1 case) per
design.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from BackEnd.engine.skeleton_step_emitter import (
    _build_post_shot_sub_steps,
)
from BackEnd.engine.shot_micro_movements import inject_shot_micro_before_post_shot
from BackEnd.utils.animation_step_schema import (
    AdvanceTrigger,
    AnimationStep,
    Announcement,
    GridCoord,
    NextStep,
    PlayerAction,
    PlayerArchetype,
    StepEnd,
    StepStart,
)
from BackEnd.utils.animation_step_helpers import (
    _ag_grid_per_game_sec,
    _motion_end_toward_dest,
    _player_lookup_by_id,
    stamp_tween_durations,
)


FB_ANNOUNCE_HOLD_MS: float = 1000.0


def _safe_id(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    pid = getattr(obj, "player_id", None)
    return str(pid) if pid is not None else None


def _player_iter(off_lineup: Dict[str, Any], def_lineup: Dict[str, Any]):
    for lineup in (off_lineup, def_lineup):
        for _, player in (lineup or {}).items():
            if player is None:
                continue
            yield player


def _build_start_coords(
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    prior_final_coords: Dict[str, Any],
) -> Dict[str, GridCoord]:
    """Seed all-player start coords from the prior turn's final_coords
    (post-STEAL positions). Falls back to ``player.coords`` if a player
    is missing from the snapshot.
    """
    start: Dict[str, GridCoord] = {}
    for player in _player_iter(off_lineup, def_lineup):
        pid = _safe_id(player)
        if not pid:
            continue
        coord: Optional[GridCoord] = None
        if isinstance(prior_final_coords, dict):
            entry = prior_final_coords.get(pid) or prior_final_coords.get(str(pid))
            if isinstance(entry, dict) and "x" in entry and "y" in entry:
                coord = {"x": float(entry["x"]), "y": float(entry["y"])}
        if coord is None:
            raw = getattr(player, "coords", None) or {}
            if isinstance(raw, dict) and "x" in raw and "y" in raw:
                coord = {"x": float(raw["x"]), "y": float(raw["y"])}
        if coord is not None:
            start[pid] = coord
    return start


def _apply_drive_step_motion(
    *,
    start_coords: Dict[str, GridCoord],
    full_end_coords: Dict[str, GridCoord],
    archetypes: Dict[str, PlayerArchetype],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    step_t: float,
    gate_player_id: str,
    gate_target: GridCoord,
) -> Dict[str, GridCoord]:
    """Interrupted end coords at ``step_t``: gate player → ``gate_target``;
    all others → their semantic destination in ``full_end_coords``."""
    interrupted: Dict[str, GridCoord] = {}
    for pid, sc in start_coords.items():
        arch = archetypes.get(pid, "sprint")
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, arch)
        if pid == gate_player_id:
            target = gate_target
        else:
            target = full_end_coords.get(pid, sc)
        ec, _ = _motion_end_toward_dest(sc, target, rate, step_t)
        interrupted[pid] = ec
    return interrupted


def _fb_secondary_announcement(team: str) -> Announcement:
    """Drive step start announcement: ``Fast Break!`` (secondary tier)."""
    return {
        "text": "Fast Break!",
        "team": team,
        "hold_ms": FB_ANNOUNCE_HOLD_MS,
        "style": "primary",
        "tier": "secondary",
    }


def _apply_finisher_pace_archetypes(
    archetypes: Dict[str, PlayerArchetype],
    start_coords: Dict[str, GridCoord],
    *,
    stealer_id: str,
    fb_drive: Optional[Dict[str, Any]] = None,
) -> None:
    """RR/Triangle finisher: driver + cutoff defenders use HCO ``standard`` pace.

    Trailing offense, get-backs, and other non-cutoff movers keep ``sprint``.
    """
    cutoff_ids: set[str] = set()
    if fb_drive:
        for key in ("stopper_id", "d8_credited_player_id", "shot_defender_id"):
            raw = fb_drive.get(key)
            if raw is not None:
                cutoff_ids.add(str(raw))
    for pid in start_coords:
        if pid == stealer_id or pid in cutoff_ids:
            archetypes[pid] = "standard"
        else:
            archetypes.setdefault(pid, "sprint")


def _build_drive_step(
    *,
    start_coords: Dict[str, GridCoord],
    end_coords: Dict[str, GridCoord],
    stealer_id: str,
    bh_target: GridCoord,
    is_away_offense: bool,
    clock_remaining: float,
    shot_clock_remaining: float,
    t_game_seconds: float,
    next_step_index: int,
    off_lineup: Optional[Dict[str, Any]] = None,
    def_lineup: Optional[Dict[str, Any]] = None,
    archetypes_override: Optional[Dict[str, PlayerArchetype]] = None,
    finisher_pace: bool = False,
    stamp_start_announcement: bool = True,
    fb_drive: Optional[Dict[str, Any]] = None,
) -> AnimationStep:
    """The single drive step: stealer sprints to BH target while defenders
    sprint to defender target (with first-arrival freeze) and other-4
    offensive players sprint to their HCO setup spots. Ball stays with the
    stealer. "Fast Break!" fires on ``start`` when ``stamp_start_announcement``.

    Advance trigger gates on the stealer reaching ``bh_target``. The FE
    tweens each player from their ``start.coords`` to ``end.coords`` over
    the trigger's ``T_game_seconds`` (sprint archetype).
    """
    actions: Dict[str, PlayerAction] = {pid: "sprint" for pid in start_coords}
    archetypes: Dict[str, PlayerArchetype] = dict(archetypes_override or {})
    if finisher_pace:
        _apply_finisher_pace_archetypes(
            archetypes,
            start_coords,
            stealer_id=stealer_id,
            fb_drive=fb_drive,
        )
    else:
        for pid in start_coords:
            archetypes.setdefault(pid, "sprint")
    full_end_coords = {
        pid: dict(end_coords.get(pid, start_coords[pid])) for pid in start_coords
    }
    destinations: Dict[str, Optional[GridCoord]] = dict(full_end_coords)
    step_end_coords = dict(full_end_coords)
    if off_lineup is not None and def_lineup is not None:
        step_end_coords = _apply_drive_step_motion(
            start_coords=start_coords,
            full_end_coords=full_end_coords,
            archetypes=archetypes,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            step_t=float(t_game_seconds),
            gate_player_id=stealer_id,
            gate_target=bh_target,
        )
    # Stealer's archetype for the drive itself is sprint; he ends the drive
    # in shot motion at the BH target. The post-shot sub-step builder
    # transitions the shot animation from there.
    actions[stealer_id] = "shoot"
    if not finisher_pace:
        archetypes[stealer_id] = "sprint"

    trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t_game_seconds),
        "metadata": {
            "target_player_id": stealer_id,
            "target_coords": dict(bh_target),
            "kind": "after_steal_drive",
        },
    }

    team = "away" if is_away_offense else "home"

    start: StepStart = {
        "coords": dict(start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetypes,
        "ball": {"owner_player_id": stealer_id},
        "clock": {
            "clock_remaining": float(clock_remaining),
            "shot_clock_remaining": float(shot_clock_remaining),
        },
        "advance_trigger": trigger,
    }
    if stamp_start_announcement:
        start["announcement"] = _fb_secondary_announcement(team)
    if off_lineup is not None and def_lineup is not None:
        stamp_tween_durations(
            start,
            step_end_coords,
            float(t_game_seconds),
            off_lineup,
            def_lineup,
        )
    end: StepEnd = {
        "coords": step_end_coords,
        "ball": {"owner_player_id": stealer_id},
        "time_elapsed": float(t_game_seconds),
        "clock": {
            "clock_remaining": float(clock_remaining) - float(t_game_seconds),
            "shot_clock_remaining": float(shot_clock_remaining) - float(t_game_seconds),
        },
        "next": {"kind": "next_step", "index": next_step_index},
    }
    return {"start": start, "end": end}


def _nice_stop_announcement(team: str) -> Announcement:
    return {
        "text": "Nice Stop!",
        "team": team,
        "hold_ms": FB_ANNOUNCE_HOLD_MS,
        "style": "secondary",
        "tier": "secondary",
    }


def _build_meet_drive_step(
    *,
    start_coords: Dict[str, GridCoord],
    end_coords: Dict[str, GridCoord],
    stealer_id: str,
    meet_target: GridCoord,
    is_away_offense: bool,
    clock_remaining: float,
    shot_clock_remaining: float,
    t_game_seconds: float,
    next_step_index: int,
    fb_drive: Dict[str, Any],
    end_announcement: Optional[Announcement] = None,
    off_lineup: Optional[Dict[str, Any]] = None,
    def_lineup: Optional[Dict[str, Any]] = None,
    finisher_pace: bool = False,
    stamp_start_announcement: bool = True,
) -> AnimationStep:
    """Drive step gated on BH + stopper reaching the cutoff meet."""
    actions: Dict[str, PlayerAction] = {pid: "sprint" for pid in start_coords}
    archetypes: Dict[str, PlayerArchetype] = dict(
        fb_drive.get("defender_archetypes") or {}
    )
    if finisher_pace:
        _apply_finisher_pace_archetypes(
            archetypes,
            start_coords,
            stealer_id=stealer_id,
            fb_drive=fb_drive,
        )
    else:
        for pid in start_coords:
            archetypes.setdefault(pid, "sprint")
    full_end_coords = {
        pid: dict(end_coords.get(pid, start_coords[pid])) for pid in start_coords
    }
    destinations = dict(full_end_coords)
    step_end_coords = dict(full_end_coords)
    if off_lineup is not None and def_lineup is not None:
        step_end_coords = _apply_drive_step_motion(
            start_coords=start_coords,
            full_end_coords=full_end_coords,
            archetypes=archetypes,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            step_t=float(t_game_seconds),
            gate_player_id=stealer_id,
            gate_target=meet_target,
        )
    actions[stealer_id] = "handle_ball"

    trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t_game_seconds),
        "metadata": {
            "target_player_id": stealer_id,
            "target_coords": dict(meet_target),
            "kind": "after_steal_meet",
        },
    }
    team = "away" if is_away_offense else "home"
    start: StepStart = {
        "coords": dict(start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetypes,
        "ball": {"owner_player_id": stealer_id},
        "clock": {
            "clock_remaining": float(clock_remaining),
            "shot_clock_remaining": float(shot_clock_remaining),
        },
        "advance_trigger": trigger,
    }
    if stamp_start_announcement:
        start["announcement"] = _fb_secondary_announcement(team)
    if off_lineup is not None and def_lineup is not None:
        stamp_tween_durations(
            start,
            step_end_coords,
            float(t_game_seconds),
            off_lineup,
            def_lineup,
        )
    end: StepEnd = {
        "coords": step_end_coords,
        "ball": {"owner_player_id": stealer_id},
        "time_elapsed": float(t_game_seconds),
        "clock": {
            "clock_remaining": float(clock_remaining) - float(t_game_seconds),
            "shot_clock_remaining": float(shot_clock_remaining) - float(t_game_seconds),
        },
        "next": {"kind": "next_step", "index": next_step_index},
    }
    if end_announcement is not None:
        end["announcement"] = end_announcement
    return {"start": start, "end": end}


def _build_drive_resolution_animation_steps(
    turn_result: Dict[str, Any],
    game: Any,
) -> Optional[List[AnimationStep]]:
    """Schema steps for Phase 2 ``fb_drive_resolution`` after-steal turns."""
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
            "🐛 [AFTER_STEAL_DR] unsupported result_type=%s", result_type
        )
        return None

    fb_drive = turn_result.get("fb_drive_resolution") or {}
    stealer_id = (
        _safe_id(turn_result.get("shooter"))
        or _safe_id(turn_result.get("ball_handler"))
        or _safe_id(turn_result.get("shooter_id"))
    )
    if not stealer_id:
        return None

    off_team = getattr(game, "offense_team", None)
    def_team = getattr(game, "defense_team", None)
    off_lineup = getattr(off_team, "lineup", {}) if off_team else {}
    def_lineup = getattr(def_team, "lineup", {}) if def_team else {}
    is_away_offense = bool(
        off_team is not None
        and getattr(off_team, "team_id", None)
        == getattr(getattr(game, "away_team", None), "team_id", None)
    )

    prior_turns = getattr(game, "turns", None) or []
    prior_turn = prior_turns[-1] if prior_turns else None
    prior_final_coords = (
        prior_turn.get("final_coords") if isinstance(prior_turn, dict) else None
    ) or {}
    start_coords = _build_start_coords(off_lineup, def_lineup, prior_final_coords)
    if stealer_id not in start_coords:
        return None

    raw_end_coords = turn_result.get("after_steal_end_coords") or {}
    end_coords: Dict[str, GridCoord] = {}
    for pid, coord in raw_end_coords.items():
        if isinstance(coord, dict) and "x" in coord and "y" in coord:
            end_coords[str(pid)] = {"x": float(coord["x"]), "y": float(coord["y"])}
    for pid, sc in start_coords.items():
        end_coords.setdefault(pid, dict(sc))

    game_state = getattr(game, "game_state", {}) or {}
    clock_remaining = float(game_state.get("time_remaining", 0) or 0)
    shot_clock_remaining = float(game_state.get("shot_clock_remaining", 0) or 0)
    team = "away" if is_away_offense else "home"

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

    steps: List[AnimationStep] = []
    elapsed = 0.0
    clock_r = clock_remaining
    shot_r = shot_clock_remaining

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
        end_ann = None
        if result_type == "DEFENSIVE_STOP":
            end_ann = _nice_stop_announcement(team)
        meet_step = _build_meet_drive_step(
            start_coords=start_coords,
            end_coords=end_coords,
            stealer_id=stealer_id,
            meet_target=meet_target,
            is_away_offense=is_away_offense,
            clock_remaining=clock_r,
            shot_clock_remaining=shot_r,
            t_game_seconds=t_meet,
            next_step_index=1 if result_type in ("MAKE", "MISS") else 0,
            fb_drive=fb_drive,
            end_announcement=end_ann,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
        )
        if result_type == "DEFENSIVE_STOP" or is_terminal:
            meet_step["end"]["next"] = {"kind": "end_of_turn"}
        steps.append(meet_step)
        elapsed += t_meet
        clock_r -= t_meet
        shot_r -= t_meet
        step_start_coords = dict(end_coords)
    else:
        step_start_coords = dict(start_coords)

    if result_type in ("MAKE", "MISS", "BLOCK"):
        if is_neutral and stop_action in ("shoot", "pass"):
            if stop_action == "pass":
                recv_id = turn_result.get("pass_receiver_id")
                if recv_id and recv_id in step_start_coords:
                    from BackEnd.constants import PASS_GRID_SPOTS_PER_GAME_SECOND
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
                            metadata_reason="after_steal_stop_pass",
                        )
                        steps.append(pass_step)
                        elapsed += float(pass_step["end"]["time_elapsed"])
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
            shot_drive = _build_drive_step(
                start_coords=step_start_coords,
                end_coords=shot_end_coords,
                stealer_id=stealer_id,
                bh_target=bh_target,
                is_away_offense=is_away_offense,
                clock_remaining=clock_r,
                shot_clock_remaining=shot_r,
                t_game_seconds=max(0.35, t_shot * 0.15),
                next_step_index=len(steps) + 1,
                off_lineup=off_lineup,
                def_lineup=def_lineup,
            )
            shot_drive["start"]["action"][stealer_id] = "shoot"
            steps.append(shot_drive)
            elapsed += float(shot_drive["end"]["time_elapsed"])
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
                "kind": "after_steal_drive",
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
                clock_remaining=clock_remaining,
                shot_clock_remaining=shot_clock_remaining,
                t_game_seconds=t_drive,
                next_step_index=1,
                off_lineup=off_lineup,
                def_lineup=def_lineup,
                archetypes_override=fb_drive.get("defender_archetypes"),
            )
            drive_step["start"]["advance_trigger"]["metadata"] = trigger_meta
            steps = [drive_step]

        inject_shot_micro_before_post_shot(
            steps, turn_result, off_lineup, def_lineup, is_away_offense
        )
        _build_post_shot_sub_steps(
            steps, turn_result, off_lineup, def_lineup, is_away_offense
        )
        if result_type == "MAKE":
            _override_fb_make_announcement(steps)

    return steps or None


def _override_fb_make_announcement(steps: List[AnimationStep]) -> None:
    """Rewrite the make-hold step's announcement text from
    "It's Good!" → "Fast Break Score!" (and the and-1 variant). The
    shared ``_build_make_hold_sub_step`` (from skeleton) emits HCO
    defaults; we post-process so the after-steal make reads as a fast-
    break score.

    No-op for MISS / BLOCK paths.
    """
    for step in reversed(steps):
        start = step.get("start") if isinstance(step, dict) else None
        if not isinstance(start, dict):
            continue
        ann = start.get("announcement")
        if not isinstance(ann, dict):
            continue
        text = str(ann.get("text") or "")
        style = str(ann.get("style") or "")
        if style == "and_one" or text.startswith("It's Good! And 1!"):
            ann["text"] = "Fast Break Score! And 1!"
            return
        if style == "primary" and text.startswith("It's Good!"):
            ann["text"] = "Fast Break Score!"
            return


# --- Top-level builder -----------------------------------------------------


def build_after_steal_fast_break_animation_steps(
    turn_result: Dict[str, Any],
    game: Any,
) -> Optional[List[AnimationStep]]:
    """Convert an after_steal FB ``turn_result`` (built by the new
    resolver) into AnimationStep[]. Returns ``None`` for unrecognized
    inputs.
    """
    if turn_result.get("fb_drive_resolution"):
        steps = _build_drive_resolution_animation_steps(turn_result, game)
        if steps is not None:
            return steps

    result_type = (turn_result.get("result_type") or "").upper()
    if result_type not in ("MAKE", "MISS", "BLOCK"):
        logging.warning(
            "🐛 [AFTER_STEAL_NONE site=unsupported_result_type] result_type=%s",
            result_type,
        )
        return None

    stealer_id = (
        _safe_id(turn_result.get("shooter"))
        or _safe_id(turn_result.get("ball_handler"))
        or _safe_id(turn_result.get("shooter_id"))
    )
    if not stealer_id:
        logging.warning(
            "🐛 [AFTER_STEAL_NONE site=stealer_id_missing] turn_keys=%s",
            list(turn_result.keys())[:10],
        )
        return None

    off_team = getattr(game, "offense_team", None)
    def_team = getattr(game, "defense_team", None)
    off_lineup = getattr(off_team, "lineup", {}) if off_team else {}
    def_lineup = getattr(def_team, "lineup", {}) if def_team else {}
    is_away_offense = bool(
        off_team is not None
        and getattr(off_team, "team_id", None)
        == getattr(getattr(game, "away_team", None), "team_id", None)
    )

    prior_turns = getattr(game, "turns", None) or []
    prior_turn = prior_turns[-1] if prior_turns else None
    prior_final_coords = (
        prior_turn.get("final_coords")
        if isinstance(prior_turn, dict)
        else None
    ) or {}

    start_coords = _build_start_coords(off_lineup, def_lineup, prior_final_coords)
    if stealer_id not in start_coords:
        logging.warning(
            "🐛 [AFTER_STEAL_NONE site=stealer_not_in_start_coords] stealer_id=%s start_keys=%s",
            stealer_id, list(start_coords.keys()),
        )
        return None

    # Backend-precomputed end coords for all 10 players. The drive step's
    # end.coords reads from here.
    raw_end_coords = turn_result.get("after_steal_end_coords") or {}
    if not isinstance(raw_end_coords, dict) or not raw_end_coords:
        logging.warning(
            "🐛 [AFTER_STEAL_NONE site=end_coords_missing] turn_keys=%s",
            list(turn_result.keys())[:15],
        )
        return None

    end_coords: Dict[str, GridCoord] = {}
    for pid, coord in raw_end_coords.items():
        if not isinstance(coord, dict) or "x" not in coord or "y" not in coord:
            continue
        end_coords[str(pid)] = {"x": float(coord["x"]), "y": float(coord["y"])}

    # Fall back to start coord for any player missing from end_coords (defensive).
    for pid, sc in start_coords.items():
        end_coords.setdefault(pid, dict(sc))

    bh_target_raw = turn_result.get("bh_target") or end_coords.get(stealer_id)
    bh_target: GridCoord = {
        "x": float(bh_target_raw["x"]),
        "y": float(bh_target_raw["y"]),
    }

    game_state = getattr(game, "game_state", {}) or {}
    clock_remaining = float(game_state.get("time_remaining", 0) or 0)
    shot_clock_remaining = float(game_state.get("shot_clock_remaining", 0) or 0)
    t_drive = float(
        turn_result.get("t_shooter_game_seconds")
        or max(0.5, 1.0)  # safety floor if backend didn't stamp
    )

    drive_step = _build_drive_step(
        start_coords=start_coords,
        end_coords=end_coords,
        stealer_id=stealer_id,
        bh_target=bh_target,
        is_away_offense=is_away_offense,
        clock_remaining=clock_remaining,
        shot_clock_remaining=shot_clock_remaining,
        t_game_seconds=t_drive,
        next_step_index=1,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
    )
    steps: List[AnimationStep] = [drive_step]

    # Post-shot sub-steps via the shared skeleton helper: ball flight (variant
    # launch + arrival SFX), variant sub-steps (RATTLE hops / BANK / etc.),
    # then [hold] on make or [bounce] on miss. Shooting-foul-on-miss
    # announcement stamped on the terminal step.
    inject_shot_micro_before_post_shot(
        steps, turn_result, off_lineup, def_lineup, is_away_offense,
    )
    _build_post_shot_sub_steps(
        steps, turn_result, off_lineup, def_lineup, is_away_offense,
    )

    # Override make-hold announcement text from "It's Good!" → "Fast Break
    # Score!" per design.
    if result_type == "MAKE":
        _override_fb_make_announcement(steps)

    return steps
