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
``Animation_System_Updated.md`` for the schema field this writes.
"""

import random
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.utils.animation_step_schema import GridCoord, PlayerAction, PlayerArchetype


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

    steps = turn_result.get("animation_steps")
    if isinstance(steps, list) and steps:
        last = steps[-1]
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
    pid = getattr(bh, "player_id", None) if not isinstance(bh, (str, int)) else bh
    return str(pid) if pid else None


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
    # Unknown / fallback → base rate. The canonical name is "standard"; any
    # unrecognized archetype string defensively resolves here.
    return STANDARD_GRID_PER_GAME_SEC * ag_scale


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

    Tiers per ``Sound_Design_Update.md``:
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

    Tiers per ``Sound_Design_Update.md``:
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


# --- Shot SFX helpers (Sound_Design_Update.md §Shot Audio) -----------------


def shot_launch_sfx(shot_score_pre_defense: Any) -> Optional[Dict[str, Any]]:
    """Pick the shot-release SFX file from the pre-defense shot score tier.

    Tiers per ``Sound_Design_Update.md``:
      - score < 101  → ``three-weak.wav``
      - score > 210  → ``three-strong.wav``
      - else         → ``shot-standard.wav``

    Returns ``None`` when the score is unavailable; caller omits the cue
    rather than firing a default file.
    """
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
    """FT launch cue — always ``shot-standard.wav`` (Sound_Design_Update.md)."""
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

    Matches the variant → file mapping in ``Sound_Design_Update.md``
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

    # 🐌 [TWEEN_DURATIONS] diagnostic — remove once stretching bug is confirmed
    # resolved across CR / RR / HCT / HCO. Logs step T (game-sec) + per-player
    # computed durations so we can verify backend stamping is producing sane
    # values and the field reaches the frontend.
    import logging as _tween_log
    _tween_log.warning(
        "🐌 [TWEEN_DURATIONS] step_t=%.2fs durations=%s",
        step_t,
        {pid: round(d, 2) for pid, d in durations.items()},
    )


_FB_DEBUG_LINEUP_ORDER = ("PG", "SG", "SF", "PF", "C")


def _fb_debug_pid_to_role(
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> Dict[str, Tuple[str, str]]:
    pid_to_role: Dict[str, Tuple[str, str]] = {}
    for pos in _FB_DEBUG_LINEUP_ORDER:
        for team_label, lineup in (("OFF", off_lineup), ("DEF", def_lineup)):
            player = lineup.get(pos) if lineup else None
            if player is None:
                continue
            pid = getattr(player, "player_id", None)
            if pid is not None:
                pid_to_role[str(pid)] = (team_label, pos)
    return pid_to_role


def _fb_debug_fmt_coord(c: Any) -> str:
    if not isinstance(c, dict) or "x" not in c or "y" not in c:
        return "?"
    try:
        return f"({float(c['x']):.1f},{float(c['y']):.1f})"
    except (TypeError, ValueError):
        return "?"


def _fb_debug_sort_key(
    pid: str, pid_to_role: Dict[str, Tuple[str, str]]
) -> Tuple[int, int, str]:
    role = pid_to_role.get(str(pid))
    if role is None:
        return (2, 99, str(pid))
    team_label, pos = role
    team_idx = 0 if team_label == "OFF" else 1
    try:
        pos_idx = _FB_DEBUG_LINEUP_ORDER.index(pos)
    except ValueError:
        pos_idx = 99
    return (team_idx, pos_idx, str(pid))


def log_fb_emitter_entry(
    turn_label: str,
    all_start_coords: Dict[str, GridCoord],
    game: Any,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> None:
    """Cross-turn boundary diff: prior turn's ``final_coords`` vs the FB
    emitter's view of starting coords. Any per-player mismatch is a teleport
    source. Filter Railway logs on ``🚀 [FB_BRIDGE]``.
    """
    import logging

    pid_to_role = _fb_debug_pid_to_role(off_lineup, def_lineup)
    prior_turns = getattr(game, "turns", None) or []
    prior_final: Dict[str, Any] = {}
    prior_label = "?"
    if prior_turns:
        last = prior_turns[-1] if isinstance(prior_turns[-1], dict) else {}
        prior_final = last.get("final_coords") or {}
        prior_label = last.get("current_turn") or "?"

    logging.warning(
        "🚀 [FB_BRIDGE %s] entry: start_coords=%d, prior_turn=%s, prior_final_coords=%d",
        turn_label, len(all_start_coords), prior_label, len(prior_final),
    )

    teleports: List[Tuple[str, Any, Any, float]] = []
    for pid, curr in all_start_coords.items():
        prev = prior_final.get(pid)
        if prev is None:
            prev = prior_final.get(str(pid))
        if not isinstance(prev, dict) or not isinstance(curr, dict):
            continue
        try:
            dx = float(prev.get("x", 0)) - float(curr.get("x", 0))
            dy = float(prev.get("y", 0)) - float(curr.get("y", 0))
        except (TypeError, ValueError):
            continue
        gap = (dx * dx + dy * dy) ** 0.5
        if gap > 0.5:
            teleports.append((str(pid), prev, curr, gap))

    if not teleports:
        logging.warning(
            "🚀 [FB_BRIDGE %s] clean vs %s.final_coords",
            turn_label, prior_label,
        )
        return

    logging.warning(
        "🚀 [FB_BRIDGE %s] ⚠️ %d player(s) teleported between %s.final and FB.step0.start",
        turn_label, len(teleports), prior_label,
    )
    for pid, prev, curr, gap in sorted(
        teleports, key=lambda row: _fb_debug_sort_key(row[0], pid_to_role)
    ):
        team_label, pos = pid_to_role.get(pid, ("?", "?"))
        logging.warning(
            "    %s %s (%s): prior_final=%s → step0_start=%s gap=%.2f",
            team_label, pos, pid,
            _fb_debug_fmt_coord(prev),
            _fb_debug_fmt_coord(curr),
            gap,
        )


def log_fb_animation_steps(
    turn_label: str,
    steps: List[Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    prefix: str = "FB_STEP",
) -> None:
    """Per-step movers-only schema log. Logs a header per step (T, AT, gate,
    ball, next) followed by one line per moving player (start→end,
    destination, action, archetype). Flags step N+1 start vs step N end
    discontinuities >0.5 grid. Filter on ``🛹 [<prefix>]``.

    ``prefix`` defaults to ``FB_STEP`` for legacy FB callers; OREB callers
    pass ``OREB_STEP``.
    """
    import logging

    if not steps:
        logging.warning("🛹 [%s %s] empty steps[]", prefix, turn_label)
        return

    pid_to_role = _fb_debug_pid_to_role(off_lineup, def_lineup)
    logging.warning("🛹 [%s %s] %d steps", prefix, turn_label, len(steps))

    prev_end_coords: Dict[str, Any] = {}
    for i, step in enumerate(steps):
        start = step.get("start") or {}
        end = step.get("end") or {}
        actions = start.get("action") or {}
        archetypes = start.get("archetype") or {}
        start_coords = start.get("coords") or {}
        end_coords = end.get("coords") or {}
        destinations = start.get("destination") or {}
        at = start.get("advance_trigger") or {}
        meta = at.get("metadata") or {}
        ball_start = (start.get("ball") or {}).get("owner_player_id") or "?"
        ball_end = (end.get("ball") or {}).get("owner_player_id") or "?"
        next_ptr = end.get("next") or {}
        t = end.get("time_elapsed")
        t_str = f"{float(t):.2f}" if isinstance(t, (int, float)) else "?"
        gate_id = (
            meta.get("target_player_id")
            or meta.get("to_player_id")
            or "?"
        )
        gate_coord = meta.get("target_coords")

        logging.warning(
            "🛹 [%s %s n=%d] t=%ss AT=%s gate=%s%s ball=%s→%s next=%s",
            prefix, turn_label, i, t_str,
            at.get("condition", "?"),
            gate_id,
            f"@{_fb_debug_fmt_coord(gate_coord)}" if gate_coord else "",
            ball_start, ball_end, next_ptr,
        )

        movers = [
            pid for pid, act in actions.items()
            if act and act != "stationary"
        ]
        movers.sort(key=lambda p: _fb_debug_sort_key(p, pid_to_role))
        for pid in movers:
            team_label, pos = pid_to_role.get(str(pid), ("?", "?"))
            logging.warning(
                "    %s %s (%s): %s→%s dst=%s %s/%s",
                team_label, pos, pid,
                _fb_debug_fmt_coord(start_coords.get(pid)),
                _fb_debug_fmt_coord(end_coords.get(pid)),
                _fb_debug_fmt_coord(destinations.get(pid)),
                actions.get(pid, "?"),
                archetypes.get(pid, "?"),
            )

        if i > 0 and prev_end_coords:
            for pid in sorted(
                start_coords.keys(),
                key=lambda p: _fb_debug_sort_key(p, pid_to_role),
            ):
                cur = start_coords.get(pid)
                prev = prev_end_coords.get(pid)
                if not isinstance(cur, dict) or not isinstance(prev, dict):
                    continue
                try:
                    dx = float(cur.get("x", 0)) - float(prev.get("x", 0))
                    dy = float(cur.get("y", 0)) - float(prev.get("y", 0))
                except (TypeError, ValueError):
                    continue
                gap = (dx * dx + dy * dy) ** 0.5
                if gap > 0.5:
                    team_label, pos = pid_to_role.get(str(pid), ("?", "?"))
                    logging.warning(
                        "    ⚠️ [STEP_DISCONTINUITY] step %d %s %s (%s): "
                        "prev_end=%s ≠ start=%s gap=%.2f",
                        i, team_label, pos, pid,
                        _fb_debug_fmt_coord(prev),
                        _fb_debug_fmt_coord(cur),
                        gap,
                    )
        prev_end_coords = dict(end_coords)
