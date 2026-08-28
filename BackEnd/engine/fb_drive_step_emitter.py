"""Universal Fast Break drive-resolution step emitter.

Single source of truth (SS&S) for the drive-resolution animation steps shared
by **all four** FB play types — Rim Runner, Triangle, After-Steal, and Covert
Release. Each play's emitter builds its own preamble (burst / outlet / lane
pass, or a standalone start-coord snapshot), derives ``stealer_id`` +
``start_coords`` + ``end_coords``, then delegates the meet / neutral-shoot /
neutral-pass / NO_MEET-POS_O drive + post-shot chain to
``build_fb_drive_resolution_steps`` here.

Previously this ~250-line orchestration was copy-pasted into three emitters
(`rim_runner_step_emitter._build_finisher_drive_resolution_steps`,
`after_steal_fast_break_step_emitter._build_drive_resolution_animation_steps`,
`covert_release_step_emitter._build_cr_drive_resolution_animation_steps`) and
had drifted (e.g. the ``t_drive`` traversal floor + crash-to-basket lived only
in the RR/Triangle copy). Centralizing keeps every drive fix landing in one
place for all four types.

Per-play divergences are carried as parameters:
  * ``kind_prefix`` — advance-trigger metadata ``kind`` (``rim_runner`` etc.)
  * ``stamp_fb_start_announcement`` — whether the drive/meet step stamps the
    "Fast Break!" secondary callout (RR/Triangle announce it earlier on the
    burst/lane pass, so they pass ``False``).
  * ``suppress_stinger`` — After-Steal shows the FB banner but suppresses the
    braddock court stinger.

Universal behavior (per product decision, July 2026):
  * Driver + cutoff defenders use ``finisher_pace`` (standard/HCO) on all types.
  * NO_MEET/POS_O drive floors ``t_drive`` to the shooter's real catch→rim
    traversal (POS_O against the knot-path length) so he never finishes short.
  * NO_MEET/POS_O drive crashes the off-ball cast toward ``basketSpot`` at
    sprint so they advance in stride instead of parking on short-budget spots.
  * DEFENSIVE_STOP uses the named-defender "Nice stop" announcement everywhere.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from BackEnd.constants import HCO_STRING_SPOTS, PASS_GRID_SPOTS_PER_GAME_SECOND
from BackEnd.utils.animation_step_helpers import (
    _ag_grid_per_game_sec,
    _euclid,
    _player_lookup_by_id,
    floor_step_t_to_traversal,
)
from BackEnd.utils.animation_step_schema import AnimationStep, GridCoord, PlayerArchetype
from BackEnd.utils.shared import get_away_player_coords


def _safe_id(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    pid = getattr(obj, "player_id", None)
    return str(pid) if pid is not None else None


def _derive_transition_outcome_kind(
    fb_drive: Dict[str, Any], turn_result: Dict[str, Any]
) -> str:
    """Map the ``fb_drive_resolution`` outcome to a planner ``outcome_kind``.

    terminal (foul/charge/dead-ball) → ``terminal``; a NEUTRAL stop → ``hco`` /
    ``pass`` / ``pull_up`` by the BH's stop decision; otherwise the BH shoots at
    the rim → ``rim_finish``.
    """
    outcome = fb_drive.get("outcome")
    if outcome in ("DEAD BALL", "O_FOUL", "D_FOUL", "CHARGE", "BLOCKING_FOUL"):
        return "terminal"
    if outcome == "NEUTRAL":
        action = (
            turn_result.get("stop_decision_action")
            or (fb_drive.get("stop_decision") or {}).get("action")
        )
        if action == "HCO":
            return "hco"
        if action == "pass":
            return "pass"
        return "pull_up"
    return "rim_finish"


def derive_transition_author_inputs(
    *,
    turn_result: Dict[str, Any],
    fb_drive: Dict[str, Any],
    stealer_id: str,
    off_start_by_id: Dict[str, GridCoord],
    def_start_by_id: Dict[str, GridCoord],
    bh_start: GridCoord,
    bh_end: GridCoord,
    is_away_offense: bool,
) -> Dict[str, Any]:
    """Derive the ``author_transition_end_coords`` kwargs from a resolved
    ``fb_drive_resolution`` payload — the SINGLE derivation shared by the emitter
    (render) and the resolver-side contest read, so the two can never drift.

    Callers supply the id-keyed offense/defense start coords and the BH's
    ``bh_start`` / ``bh_end`` (the emitter uses the meet coord or ``bh_target``;
    the resolver's rim-finish read uses the shot spot). Everything else — the
    stopper matchup, ``meet``, ``outcome_kind``, ``bh_reaches_rim``, beaten
    trailers, and the reachable defender ends — is read straight off the payload.

    ``reachable_ends`` (the resolver's ``defender_end_coords``, each defender
    sprint-clamped from their real start by the drive time) is passed so the BH
    defender / beaten stoppers render WHERE THEY ACTUALLY GET TO, not a fixed
    chase spot behind the finish — a clean breakaway then reads as uncontested,
    a hustled-back defender as a contest (single-coord-source, reachable).
    """
    planner_meet = (
        {"x": float(fb_drive["meet_x"]), "y": float(fb_drive["meet_y"])}
        if fb_drive.get("meet_x") is not None
        else None
    )
    return dict(
        bh_id=stealer_id,
        bh_start={"x": float(bh_start["x"]), "y": float(bh_start["y"])},
        bh_end={"x": float(bh_end["x"]), "y": float(bh_end["y"])},
        off_start_coords=off_start_by_id,
        def_start_coords=def_start_by_id,
        bh_defender_id=fb_drive.get("stopper_id"),
        meet=planner_meet,
        outcome_kind=_derive_transition_outcome_kind(fb_drive, turn_result),
        bh_reaches_rim=fb_drive.get("outcome") in ("NO_MEET", "POS_O"),
        beaten_stopper_ids=fb_drive.get("cascade_beaten_stopper_ids"),
        is_away_offense=is_away_offense,
        reachable_ends=fb_drive.get("defender_end_coords"),
    )


def _author_offball_spread_end_coords(
    *,
    turn_result: Dict[str, Any],
    fb_drive: Dict[str, Any],
    start_coords: Dict[str, GridCoord],
    stealer_id: str,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    is_away_offense: bool,
    uses_meet_step: bool,
    meet_coords: Optional[Dict[str, Any]],
) -> Dict[str, GridCoord]:
    """Author the coordinated all-ten transition spread at emit time.

    Slices the offense/defense start coords out of ``start_coords`` (keyed by the
    lineup player ids), derives the ball handler's finish + ``outcome_kind`` +
    matchup inputs from the ``fb_drive_resolution`` payload (via
    ``derive_transition_author_inputs``), then delegates to the shared planner.
    Returns a full ``{pid: {x, y}}`` map (start-coord fallback for any uncovered
    id) that replaces the caller's off-ball ``end_coords``.
    """
    from BackEnd.engine.after_steal_transition_positioning import (
        author_transition_end_coords,
    )

    off_ids = {sid for p in off_lineup.values() if (sid := _safe_id(p))}
    def_ids = {sid for p in def_lineup.values() if (sid := _safe_id(p))}
    off_start = {
        pid: {"x": float(c["x"]), "y": float(c["y"])}
        for pid, c in start_coords.items()
        if pid in off_ids
    }
    def_start = {
        pid: {"x": float(c["x"]), "y": float(c["y"])}
        for pid, c in start_coords.items()
        if pid in def_ids
    }
    bh_start = start_coords.get(stealer_id) or {"x": 50.0, "y": 25.0}

    if uses_meet_step and meet_coords:
        bh_end = {"x": float(meet_coords["x"]), "y": float(meet_coords["y"])}
    else:
        raw = (
            turn_result.get("bh_target")
            or start_coords.get(stealer_id)
            or {"x": 50.0, "y": 25.0}
        )
        bh_end = {"x": float(raw["x"]), "y": float(raw["y"])}

    coordinated = author_transition_end_coords(
        **derive_transition_author_inputs(
            turn_result=turn_result,
            fb_drive=fb_drive,
            stealer_id=stealer_id,
            off_start_by_id=off_start,
            def_start_by_id=def_start,
            bh_start=bh_start,
            bh_end=bh_end,
            is_away_offense=is_away_offense,
        )
    )
    full: Dict[str, GridCoord] = {
        pid: {"x": float(c["x"]), "y": float(c["y"])}
        for pid, c in start_coords.items()
    }
    for pid, c in coordinated.items():
        full[pid] = {"x": float(c["x"]), "y": float(c["y"])}
    return full


def _fb_basket_spot(is_away_offense: bool) -> GridCoord:
    """The ``basketSpot`` HCO string spot, mirrored for the away offense.

    Mirrors ``rim_runner_step_emitter._fb_spot_coords("basketSpot", ...)`` so
    the crash-to-basket target matches the lane-pass off-ball target.
    """
    coords = dict(HCO_STRING_SPOTS.get("basketSpot", {"x": 50, "y": 25}))
    if is_away_offense:
        coords = get_away_player_coords(coords)
    return {"x": float(coords["x"]), "y": float(coords["y"])}


def build_fb_drive_resolution_steps(
    *,
    turn_result: Dict[str, Any],
    game: Any,
    start_coords: Dict[str, GridCoord],
    end_coords: Dict[str, GridCoord],
    stealer_id: str,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    is_away_offense: bool,
    clock_remaining: float,
    shot_clock_remaining: float,
    fb_roles: Dict[str, Any],
    kind_prefix: str,
    stamp_fb_start_announcement: bool = True,
    suppress_stinger: bool = False,
    crash_off_ball_to_basket: bool = True,
    author_offball_spread: bool = False,
) -> Optional[List[AnimationStep]]:
    """Build the drive-resolution ``AnimationStep[]`` (meet / neutral / NO_MEET
    drive + post-shot chain) from the ``fb_drive_resolution`` payload.

    Returns a **fresh, 0-based** step list (the caller rebases + extends it onto
    any preamble steps). Returns ``None`` for unsupported ``result_type`` or a
    missing/unseated ``stealer_id``.

    ``crash_off_ball_to_basket`` (default ``True``) controls the NO_MEET/POS_O
    drive's blanket off-ball crash: every non-finisher, non-cutoff player is
    re-targeted to ``basketSpot`` at sprint.

    ``author_offball_spread`` (default ``False``) makes the emitter author the
    coordinated transition spread here (leads/trailers + defensive matchups/help
    spots via ``after_steal_transition_positioning.author_transition_end_coords``)
    from the ``fb_drive_resolution`` payload, replacing the passed-in off-ball
    ``end_coords`` for every branch and disabling the blanket crash. RR/Triangle/
    CR pass ``True`` so every FB type spreads the cast instead of clustering at
    the rim. After-Steal instead pre-authors the identical spread in its resolver
    and passes it in via ``end_coords`` (``author_offball_spread=False``,
    ``crash_off_ball_to_basket=False``).
    """
    from BackEnd.engine.after_steal_fast_break_step_emitter import (
        _build_drive_step,
        _build_meet_drive_step,
        _override_fb_make_announcement,
        _suppress_fast_break_stinger,
    )
    from BackEnd.engine.covert_release_step_emitter import _build_nice_stop_announcement
    from BackEnd.engine.dead_ball_fumble import inject_dead_ball_fumble_before_turn_stop
    from BackEnd.engine.fb_terminal_announce import stamp_fb_terminal_freeze
    from BackEnd.engine.shot_micro_movements import inject_shot_micro_before_post_shot
    from BackEnd.engine.skeleton_step_emitter import _build_post_shot_sub_steps
    from BackEnd.utils.transition_bridge import build_pass_step

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
        logging.debug(
            "🧩 [FB_DR] skip prefix=%s: result_type=%s not in allowed set",
            kind_prefix, result_type,
        )
        return None

    fb_drive = turn_result.get("fb_drive_resolution") or {}
    if not stealer_id or stealer_id not in start_coords:
        logging.debug(
            "🧩 [FB_DR] EARLY-None prefix=%s stealer_id=%s in_start=%s "
            "(result_type=%s outcome=%s)",
            kind_prefix, stealer_id,
            bool(stealer_id and stealer_id in start_coords),
            result_type, fb_drive.get("outcome"),
        )
        return None

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

    if author_offball_spread:
        end_coords = _author_offball_spread_end_coords(
            turn_result=turn_result,
            fb_drive=fb_drive,
            start_coords=start_coords,
            stealer_id=stealer_id,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            is_away_offense=is_away_offense,
            uses_meet_step=uses_meet_step,
            meet_coords=meet_coords,
        )
        crash_off_ball_to_basket = False

    steps: List[AnimationStep] = []
    clock_r = float(clock_remaining)
    shot_r = float(shot_clock_remaining)
    step_start_coords = dict(start_coords)

    if uses_meet_step and meet_coords:
        t_meet = float(
            turn_result.get("t_meet_game_seconds")
            or fb_drive.get("t_meet_game_seconds")
            or 1.0
        )
        meet_target = {"x": float(meet_coords["x"]), "y": float(meet_coords["y"])}
        # Floor t_meet at the stealer's real traversal to the meet — a short
        # backend meet time (computed off a different reference than the
        # rendered sprite) would under-move him and jet the following shot step.
        stealer_start = step_start_coords.get(stealer_id)
        if stealer_start:
            stealer_rate = _ag_grid_per_game_sec(
                _player_lookup_by_id(off_lineup, def_lineup, stealer_id), "standard"
            )
            t_meet = floor_step_t_to_traversal(
                t_meet, stealer_start, meet_target, stealer_rate
            )
        end_ann = None
        if result_type == "DEFENSIVE_STOP":
            # Gate the "Great Stop!" callout on the ball handler's stop spot
            # (meet_target) crossing midcourt (x=50) toward the basket.
            end_ann = _build_nice_stop_announcement(
                turn_result, fb_roles, def_lineup, is_away_offense,
                ball_spot=meet_target,
            )
        meet_step = _build_meet_drive_step(
            start_coords=step_start_coords,
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
            finisher_pace=True,
            stamp_start_announcement=stamp_fb_start_announcement,
        )
        if meet_step["start"].get("advance_trigger"):
            meet_step["start"]["advance_trigger"]["metadata"]["kind"] = f"{kind_prefix}_meet"
        if result_type == "DEFENSIVE_STOP":
            meet_step["end"]["next"] = {"kind": "end_of_turn"}
        elif is_terminal:
            if result_type in ("DEAD BALL", "TURNOVER"):
                meet_step["end"]["next"] = {
                    "kind": "turn_stop",
                    "event": "DEAD_BALL_TURNOVER",
                    "payload": {
                        "victim_id": turn_result.get("victim_id") or stealer_id,
                    },
                }
            else:
                meet_step["end"]["next"] = {"kind": "end_of_turn"}
        steps.append(meet_step)
        clock_r -= t_meet
        shot_r -= t_meet
        # Advance off the meet step's RENDERED end coords, not the semantic
        # end_coords — otherwise the shot step assumes the shooter is already on
        # his full spot while the sprite is still en route → snap/jet.
        step_start_coords = dict(meet_step["end"]["coords"])

    if result_type in ("MAKE", "MISS", "BLOCK"):
        if is_neutral and stop_action in ("shoot", "pass"):
            if stop_action == "pass":
                recv_id = turn_result.get("pass_receiver_id")
                recv_id = str(recv_id) if recv_id else ""
                # Self-pass is degenerate (0-distance + pass SFX). Skip it and
                # let the original ball handler take the shot.
                if recv_id and recv_id != stealer_id and recv_id in step_start_coords:
                    try:
                        pass_step = build_pass_step(
                            off_lineup=off_lineup,
                            def_lineup=def_lineup,
                            start_coords=step_start_coords,
                            passer_id=stealer_id,
                            receiver_id=recv_id,
                            clock_remaining_at_start=clock_r,
                            shot_clock_remaining_at_start=shot_r,
                            # Point at the shot-drive step that is appended next
                            # (this pass is not yet in ``steps``).
                            next_step_index=len(steps) + 1,
                            pass_speed_grid_per_game_sec=float(
                                PASS_GRID_SPOTS_PER_GAME_SECOND
                            ),
                            metadata_reason=f"{kind_prefix}_stop_pass",
                        )
                        steps.append(pass_step)
                        clock_r = pass_step["end"]["clock"]["clock_remaining"]
                        shot_r = pass_step["end"]["clock"]["shot_clock_remaining"]
                        step_start_coords = dict(pass_step["end"]["coords"])
                        stealer_id = recv_id
                    except ValueError:
                        pass

            bh_target_raw = turn_result.get("bh_target") or step_start_coords.get(
                stealer_id, meet_coords or {}
            )
            bh_target = {"x": float(bh_target_raw["x"]), "y": float(bh_target_raw["y"])}
            t_shot = float(turn_result.get("t_shooter_game_seconds") or 0.5)
            shot_end_coords = dict(step_start_coords)
            shot_end_coords[stealer_id] = dict(bh_target)
            # Gather beat assumes the shooter is on his spot; if real ground
            # remains to bh_target (meet ≠ shot spot), extend T to his natural
            # travel so he drives in rather than jetting.
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
                finisher_pace=True,
                stamp_start_announcement=stamp_fb_start_announcement,
                fb_drive=fb_drive,
            )
            shot_drive["start"]["action"][stealer_id] = "shoot"
            if shot_drive["start"].get("advance_trigger"):
                shot_drive["start"]["advance_trigger"]["metadata"]["kind"] = (
                    f"{kind_prefix}_drive"
                )
            steps.append(shot_drive)
        else:
            bh_target_raw = turn_result.get("bh_target") or end_coords.get(stealer_id)
            bh_target = {"x": float(bh_target_raw["x"]), "y": float(bh_target_raw["y"])}
            t_drive = float(
                turn_result.get("t_shooter_game_seconds")
                or fb_drive.get("t_drive_game_seconds")
                or 1.0
            )
            trigger_meta = {
                "target_player_id": stealer_id,
                "target_coords": dict(bh_target),
                "kind": f"{kind_prefix}_drive",
            }
            knots = fb_drive.get("bh_path_knots")
            if knots and fb_drive.get("outcome") == "POS_O":
                trigger_meta["path_knots"] = knots
                segs = fb_drive.get("path_segment_game_seconds")
                if segs:
                    trigger_meta["path_segment_game_seconds"] = segs
            # Floor the drive duration to the shooter's real traversal so a short
            # backend t_drive can't bake his end.coords short of the rim (pull-up
            # inside the arc). POS_O is a curved knot path → floor against the
            # longer knot-path length so the curve isn't jetted to hit the rim.
            shooter_start = start_coords.get(stealer_id)
            if shooter_start:
                shooter_rate = _ag_grid_per_game_sec(
                    _player_lookup_by_id(off_lineup, def_lineup, stealer_id), "standard"
                )
                t_drive = floor_step_t_to_traversal(
                    t_drive, shooter_start, bh_target, shooter_rate
                )
                if (
                    knots
                    and fb_drive.get("outcome") == "POS_O"
                    and shooter_rate > 0
                ):
                    path_len = 0.0
                    prev = shooter_start
                    for knot in knots:
                        if isinstance(knot, dict) and "x" in knot and "y" in knot:
                            path_len += _euclid(prev, knot)
                            prev = knot
                    if path_len > 1e-6:
                        t_drive = max(t_drive, path_len / shooter_rate)
            # Full-break budget: keep the off-ball cast crashing toward the rim
            # through the finish. Every non-finisher, non-cutoff player is
            # re-targeted to basketSpot at sprint (interrupted-coord math still
            # freezes each mid-run at T, so they advance in stride rather than
            # parking on their short-budget end coords). The finisher keeps
            # bh_target; cutoff defenders keep their resolver contest coords +
            # finisher-pace standard.
            #
            # After-Steal passes ``crash_off_ball_to_basket=False``: its resolver
            # authors coordinated spread destinations (leads/trailers + defensive
            # matchups/help spots) in ``end_coords``, so the blanket crash is
            # skipped to avoid clustering the whole cast at the rim.
            crash_archetypes: Dict[str, PlayerArchetype] = dict(
                fb_drive.get("defender_archetypes") or {}
            )
            if crash_off_ball_to_basket:
                crash_basket = _fb_basket_spot(is_away_offense)
                cutoff_ids = {
                    str(fb_drive.get(k))
                    for k in ("stopper_id", "d8_credited_player_id", "shot_defender_id")
                    if fb_drive.get(k) is not None
                }
                for pid in start_coords:
                    if pid == stealer_id or pid in cutoff_ids:
                        continue
                    end_coords[pid] = dict(crash_basket)
                    crash_archetypes[pid] = "sprint"
            drive_step = _build_drive_step(
                start_coords=start_coords,
                end_coords=end_coords,
                stealer_id=stealer_id,
                bh_target=bh_target,
                is_away_offense=is_away_offense,
                clock_remaining=clock_r,
                shot_clock_remaining=shot_r,
                t_game_seconds=t_drive,
                next_step_index=len(steps) + 1,
                off_lineup=off_lineup,
                def_lineup=def_lineup,
                archetypes_override=crash_archetypes,
                finisher_pace=True,
                stamp_start_announcement=stamp_fb_start_announcement,
                fb_drive=fb_drive,
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

    # Dead-ball fumble owns the terminal Travel/Double Dribble announcement
    # when it can inject. Run it before fb_terminal_announce so the terminal
    # freeze helper sees the fumble announcement on the final step and no-ops,
    # avoiding duplicate dead-ball headlines. Foul/charge freezes are unchanged.
    inject_dead_ball_fumble_before_turn_stop(
        steps, turn_result, away_offense=is_away_offense,
    )
    stamp_fb_terminal_freeze(turn_result, steps, is_away_offense=is_away_offense)
    if suppress_stinger:
        _suppress_fast_break_stinger(steps)

    try:
        from BackEnd.engine.fb_step_state import (
            project_animation_step_through_fast_break_state,
        )

        fb_state_result = {
            "current_turn": "FAST_BREAK",
            "fast_break_play": turn_result.get("fast_break_play")
            or (fb_roles or {}).get("fast_break_play")
            or kind_prefix,
            "result_type": turn_result.get("result_type"),
        }
        projected_steps = [
            project_animation_step_through_fast_break_state(
                step,
                index=index,
                result=fb_state_result,
            )
            for index, step in enumerate(steps)
        ]
        if projected_steps:
            steps = projected_steps
    except Exception as e:
        logging.debug(
            "🧩 [FB_DR] StepState projection failed prefix=%s result_type=%s: %s",
            kind_prefix,
            result_type,
            e,
        )

    logging.debug(
        "🧩 [FB_DR] prefix=%s result_type=%s outcome=%s uses_meet=%s "
        "stealer_id=%s n_steps=%d",
        kind_prefix, result_type, outcome, uses_meet_step, stealer_id, len(steps),
    )
    return steps or None
