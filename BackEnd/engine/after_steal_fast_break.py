"""After-Steal Fast Break resolution.

Replaces the legacy steal-entry path in ``resolve_fast_break_logic`` for
the ``after_steal`` Fast Break play type. Short-circuited at
``fb_play_key == AFTER_STEAL``; the legacy stopper / hold_up / outlet
logic in ``resolve_fast_break_logic`` is bypassed entirely (commented out
upstream for revisit per design).

UESS contract
-------------
All choreography — random target spots, AG-based traversal timing,
contested-vs-uncontested decision — happens here. The schema emitter
(``after_steal_fast_break_step_emitter``) is a pure renderer; it reads
the precomputed end coords from ``turn_result["after_steal_end_coords"]``
and the standard shot/foul/variant fields to build a single drive step
followed by skeleton's ``_build_post_shot_sub_steps``.

Spec (see discussion in Fast_Break_System.md)
---------------------------------------------
- **BH (stealer) target**: ``basket_x ± random(2, 3)`` toward center,
  ``y = random.randint(19, 31)``. AWAY basket at x=9 → target ∈
  ``[(11, 12), 19..31]``; HOME at x=91 → target ∈ ``[(88, 89), 19..31]``.
- **Defender single target** (all 5 defenders sprint to this same spot):
  ``BH_target_x ± 2`` toward basket, same y. AWAY → x ∈ ``[9, 10]``;
  HOME → x ∈ ``[90, 91]``.
- **First-arriver determination**: per-defender traversal time =
  ``euclidean(start, defender_target) / sprint_rate``, where sprint rate
  is AG-based via ``_ag_grid_per_game_sec(defender, "sprint")``. Smallest
  time → first arriver.
- **Shooter traversal time** = ``euclidean(bh_start, bh_target) /
  bh_sprint_rate``. Used to determine whether anyone reaches the spot in
  time and to set the drive step's duration on the schema side.
- **Defender freeze on first-arrival** (only fires if t_first < t_shooter):
  others stop at their t_first interpolated position, clamped no closer
  than 6 grid spots from basket BUT never pulled backward from start
  (edge case: defender starts within the 6-spot zone → stays at start).
- **Contested check**: at t_shooter, find the defender whose x is closest
  to basket. If past shooter's x (closer to basket than the shot spot),
  CONTESTED with that defender as shot defender. Else UNCONTESTED.
  - In the t_first < t_shooter branch this is the first arriver (always
    past shooter since defender_target sits 2 grid spots closer to basket
    than bh_target).
  - In the t_first ≥ t_shooter branch, defenders are en route; only an
    edge-case defender starting near the basket would be past shooter.
- **Shot resolution**:
  - CONTESTED → ``shot_manager.calculate_shot_score(apply_defense=True)``
    with first/closest defender. Made if ``shot_score >= shot_threshold``.
  - UNCONTESTED → ``apply_defense=False``; treat as automatic MAKE
    (matches the OREB-putback uncontested rule).
- **Other 4 offensive players**: sample 4 unique spots without
  replacement from the 11-name HCO setup spot list, mirrored for away.

Outputs stamped on ``turn_result``
----------------------------------
Standard shot turn fields (result_type, shot_variant, points, foul_*,
text, possession_flips, scoring_team, etc.) plus:

- ``turn_result["after_steal_end_coords"]``: ``{player_id: {x, y}}`` for
  all 10 players. The drive step's ``end.coords`` reads from here.
- ``turn_result["after_steal_first_arriver_id"]``: id of the first
  defender to reach the spot, or ``None`` if no defender arrived in time.
- ``turn_result["after_steal_contested"]``: bool — True if shot was
  contested.
- ``turn_result["shot_defender_id"]``: the defender used for the contest
  (or None for uncontested).
- ``turn_result["t_shooter_game_seconds"]``: shooter's traversal time
  (drive step uses this on its advance_trigger).

Legacy stopper / hold_up logic
------------------------------
The shared stopper computation in ``resolve_fast_break_logic`` is left
intact for DREB FBs (RR/CR/Triangle). For AFTER_STEAL the new resolver
here REPLACES that logic; the legacy ``stopper_id`` / ``hold_up`` are NOT
consumed on this path.
"""

from __future__ import annotations

import logging
import random
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Tuple

from BackEnd.constants import (
    AWAY_RIM_COORDS,
    HCO_STRING_SPOTS,
    HOME_RIM_COORDS,
)
from BackEnd.constants.fast_break_play_types import AFTER_STEAL
from BackEnd.constants.momentum import MO_AND_ONE_DELTA
from BackEnd.utils.animation_step_helpers import (
    _ag_grid_per_game_sec,
    _euclid,
)


# Named HCO setup spots the 4 non-BH offensive players sample from
# (home-oriented coords; mirrored for away offense). 11 spots.
AFTER_STEAL_OFFENSE_SPOT_NAMES: Tuple[str, ...] = (
    "key",
    "upper wing",
    "lower wing",
    "upper apex",
    "lower apex",
    "topLane",
    "upper bird",
    "lower bird",
    "midLane",
    "upper corner",
    "lower corner",
)

# Defender freeze clamp: no closer than this many grid spots from basket
# (but never pulled backward from start — see edge-case A).
DEFENDER_FREEZE_CLAMP_GRID_SPOTS: int = 6


# --- Coord / target helpers ------------------------------------------------


def _mirror_x(home_x: float) -> float:
    """Mirror an x-coord across half-court (x=50) for away orientation."""
    return 100.0 - home_x


def _offense_spot_coords(
    spot_name: str, is_away_offense: bool
) -> Optional[Dict[str, float]]:
    raw = HCO_STRING_SPOTS.get(spot_name)
    if not raw or "x" not in raw or "y" not in raw:
        return None
    x = float(raw["x"])
    y = float(raw["y"])
    if is_away_offense:
        x = _mirror_x(x)
    return {"x": x, "y": y}


def _sample_unique_offense_spots(
    n: int, is_away_offense: bool
) -> List[Dict[str, float]]:
    """Sample n unique HCO setup spots (no collisions among offensive
    players), mirrored for away."""
    pool = [name for name in AFTER_STEAL_OFFENSE_SPOT_NAMES]
    random.shuffle(pool)
    spots: List[Dict[str, float]] = []
    for name in pool:
        if len(spots) >= n:
            break
        coord = _offense_spot_coords(name, is_away_offense)
        if coord is not None:
            spots.append(coord)
    return spots


def _compute_bh_target(is_away_offense: bool) -> Dict[str, float]:
    """BH target: 2-3 grid spots from basket on x, y ∈ [19, 31]."""
    distance = random.randint(2, 3)
    if is_away_offense:
        x = 9.0 + distance  # AWAY basket at x=9 → BH at x=11..12
    else:
        x = 91.0 - distance  # HOME basket at x=91 → BH at x=88..89
    y = float(random.randint(19, 31))
    return {"x": x, "y": y}


def _compute_defender_target(
    bh_target: Dict[str, float], is_away_offense: bool
) -> Dict[str, float]:
    """Defender single target: 2 grid spots closer to basket than BH on
    x, same y."""
    if is_away_offense:
        x = bh_target["x"] - 2.0  # AWAY: defender even closer to x=9
    else:
        x = bh_target["x"] + 2.0  # HOME: defender even closer to x=91
    return {"x": x, "y": bh_target["y"]}


def _interpolated_position(
    start: Dict[str, float],
    target: Dict[str, float],
    rate: float,
    elapsed: float,
) -> Dict[str, float]:
    """Position after ``elapsed`` game-seconds moving at ``rate``
    grid/game-sec from ``start`` toward ``target``. Clamps at target if
    reached."""
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


@contextmanager
def _temporary_lineup_coords(
    game: Any,
    coords_by_player_id: Dict[str, Dict[str, float]],
) -> Iterator[None]:
    """Temporarily apply computed shot-end coords for geography reads.

    The after-steal resolver computes the authoritative shot-moment positions
    in ``after_steal_end_coords`` before rebound resolution, while shared
    rebound helpers read ``player.coords``. Apply the computed frame only for
    the rebound winner / failed-attemptor reads, then restore runtime coords.
    """
    originals: Dict[str, Tuple[Any, Any]] = {}
    for team in (getattr(game, "home_team", None), getattr(game, "away_team", None)):
        for player in (getattr(team, "lineup", None) or {}).values():
            pid = _safe_id(player)
            if pid is None or pid not in coords_by_player_id:
                continue
            originals[pid] = (player, getattr(player, "coords", None))
            player.coords = dict(coords_by_player_id[pid])
    try:
        yield
    finally:
        for player, coords in originals.values():
            if coords is None:
                if hasattr(player, "coords"):
                    delattr(player, "coords")
            else:
                player.coords = coords


def _clamp_defender_freeze(
    pos: Dict[str, float],
    start_x: float,
    is_away_offense: bool,
) -> Dict[str, float]:
    """Clamp a frozen (non-first-arriver) defender's x: no closer than
    ``DEFENDER_FREEZE_CLAMP_GRID_SPOTS`` from basket, but never pulled
    backward from start_x (edge case where defender starts inside the
    clamp zone — leave them at start instead of teleporting back).
    """
    clamp_dist = float(DEFENDER_FREEZE_CLAMP_GRID_SPOTS)
    if is_away_offense:
        # AWAY basket at x=9. "Closer than 6 spots" = x < 15. Boundary = 15.
        # Allowed-closest = min(start_x, 15) — never pulled backward from start.
        boundary = 15.0
        allowed_min_x = min(start_x, boundary)
        clamped_x = max(pos["x"], allowed_min_x)
    else:
        # HOME basket at x=91. "Closer than 6 spots" = x > 85. Boundary = 85.
        # Allowed-closest = max(start_x, 85) — never pulled backward from start.
        boundary = 85.0
        allowed_max_x = max(start_x, boundary)
        clamped_x = min(pos["x"], allowed_max_x)
    return {"x": clamped_x, "y": pos["y"]}


def _coord_of(player: Any) -> Dict[str, float]:
    raw = getattr(player, "coords", None) or {}
    x = raw.get("x", 50.0) if isinstance(raw, dict) else 50.0
    y = raw.get("y", 25.0) if isinstance(raw, dict) else 25.0
    return {"x": float(x), "y": float(y)}


def _safe_id(p: Any) -> Optional[str]:
    if p is None:
        return None
    if isinstance(p, str):
        return p
    pid = getattr(p, "player_id", None)
    return str(pid) if pid is not None else None


def _record_after_steal_fast_break_stats(
    game: Any,
    turn_result: Dict[str, Any],
    stealer: Any,
    defenders: List[Any],
) -> None:
    """Record the completion stats skipped by the After Steal early return."""
    from BackEnd.constants.fast_break_play_types import ensure_fast_break_plays
    from BackEnd.engine.phase_resolution import _record_fast_break_stats

    _record_fast_break_stats(
        {
            "outlet_receiver": None,
            "ball_handler": stealer,
            "defense": defenders,
        },
        turn_result,
        game,
    )

    result_type = turn_result.get("result_type")
    off_scouting = game.offense_team.scouting_data
    def_scouting = game.defense_team.scouting_data

    if result_type == "MAKE":
        off_scouting["offense"]["Fast_Break_Success"] += 1
        ensure_fast_break_plays(off_scouting["offense"])[AFTER_STEAL]["S"] += 1
    elif result_type == "FOUL":
        foul_team = turn_result.get("foul_team") or game.game_state.get("foul_team")
        if foul_team == "DEFENSE":
            off_scouting["offense"]["Fast_Break_Success"] += 1
            ensure_fast_break_plays(off_scouting["offense"])[AFTER_STEAL]["S"] += 1
        elif foul_team == "OFFENSE":
            def_scouting["defense"]["vs_Fast_Break"]["success"] += 1
    elif result_type in ("MISS", "BLOCK", "TURNOVER"):
        def_scouting["defense"]["vs_Fast_Break"]["success"] += 1


# --- Main resolver ---------------------------------------------------------


def resolve_after_steal_fast_break(game: Any) -> Dict[str, Any]:
    """Build the after_steal FB turn_result. See module docstring for spec.

    Caller (``resolve_fast_break_logic``) short-circuits to this function
    when ``fb_play_key == AFTER_STEAL`` and skips the legacy steal-entry
    path. Returns a fully-formed turn_result ready for schema emission.
    """
    from BackEnd.models.shot_manager import ShotManager
    from BackEnd.utils.shared import (
        apply_scoring,
        calculate_bounce_spot,
        collect_near_bounce_rebound_attemptors,
        determine_rebounder,
        get_name_safe,
        increment_no_defender_shot_breakdown,
    )
    from BackEnd.constants.shot_variants import (
        select_shot_variant,
        roll_shot_variant_extras,
    )

    game_state = game.game_state
    off_team = game.offense_team
    def_team = game.defense_team
    off_lineup = off_team.lineup or {}
    def_lineup = def_team.lineup or {}
    is_away_offense = bool(off_team.team_id == game.away_team.team_id)

    # The stealer (now ball handler / shooter) — set by the prior STEAL turn.
    stealer = game_state.get("last_stealer")
    if stealer is None:
        # Defensive fallback: pick the PG of the new offense.
        stealer = off_lineup.get("PG")
        logging.warning(
            "🚨 [AFTER_STEAL] last_stealer missing; falling back to off PG"
        )
    stealer_id = _safe_id(stealer)
    if stealer is None or stealer_id is None:
        # Cannot proceed without a stealer.
        return {
            "result_type": "MISS",
            "fast_break": True,
            "fast_break_play": AFTER_STEAL,
            "text": "Fast Break! Possession lost.",
            "possession_flips": True,
            "current_turn": "FAST_BREAK",
            "next_play_type": "BASELINE_INBOUND",
        }

    bh_start = (
        dict(game_state["last_stealer_coords"])
        if isinstance(game_state.get("last_stealer_coords"), dict)
        else _coord_of(stealer)
    )

    # --- Universal helper: shot geometry + contested decision --------------
    # For Steal-FB, all 5 defenders are in the race pool (no exclusions).
    # The helper returns shooter target, defender target, end coords for
    # all racing defenders, first arriver, contested decision, and t_shooter.
    from BackEnd.utils.fast_break_shot_geometry import compute_fb_shot_geometry

    defenders: List[Any] = [p for p in def_lineup.values() if p is not None]
    defender_starts: Dict[str, Dict[str, float]] = {}
    for d in defenders:
        d_id = _safe_id(d)
        if d_id:
            defender_starts[d_id] = _coord_of(d)

    geometry = compute_fb_shot_geometry(
        shooter=stealer,
        shooter_start=bh_start,
        available_defenders=defenders,
        defender_starts=defender_starts,
        is_away_offense=is_away_offense,
    )
    bh_target = geometry["shooter_target"]
    defender_target = geometry["defender_target"]
    first_arriver_id = geometry["first_arriver_id"]
    contested = geometry["contested"]
    shot_defender_id = geometry["shot_defender_id"]
    t_shooter = geometry["t_shooter_game_seconds"]

    # End-of-step positions for the schema. Helper returned defenders'
    # end coords; we add the shooter and the 4 non-shooter offensive
    # players (sampled HCO setup spots, interpolated at t_shooter).
    end_coords: Dict[str, Dict[str, float]] = dict(geometry["defender_end_coords"])
    end_coords[stealer_id] = dict(bh_target)

    other_off_players: List[Any] = [
        p for p in off_lineup.values() if p is not None and _safe_id(p) != stealer_id
    ]
    sampled_spots = _sample_unique_offense_spots(len(other_off_players), is_away_offense)
    for player, target_spot in zip(other_off_players, sampled_spots):
        p_id = _safe_id(player)
        if p_id is None:
            continue
        p_start = _coord_of(player)
        p_rate = _ag_grid_per_game_sec(player, "sprint")
        end_coords[p_id] = _interpolated_position(
            p_start, target_spot, p_rate, t_shooter
        )

    # Resolve shot defender player object from id for use in calculate_shot_score.
    shot_defender: Optional[Any] = None
    if shot_defender_id:
        for d in defenders:
            if _safe_id(d) == shot_defender_id:
                shot_defender = d
                break

    # --- Shot resolution ----------------------------------------------------
    shot_manager = (
        getattr(game, "shot_manager", None) or ShotManager(game)
    )
    defense_playcall = (
        game_state.get("defense_playcall")
        or game_state.get("defense_call")
        or "man"
    )
    shot_type = "inside"  # at-the-rim shot
    is_three = False

    if contested and shot_defender is not None:
        (
            shot_score,
            shot_score_pre_defense,
            shot_defense_score_for_sfx,
            d_foul,
            foul_player,
        ) = shot_manager.calculate_shot_score(
            stealer,        # shooter
            None,           # passer
            None,           # screener
            shot_defender,  # defender
            shot_type,
            defense_playcall,
            is_three,
            True,           # is_paint
            None,           # second_defender
            bh_target,      # shooter_location
            apply_defense=True,
        )
        shot_threshold = off_team.team_attributes["shot_threshold"]
        made = shot_score >= shot_threshold
    else:
        # Uncontested: skip defense, always make (matches OREB-putback rule).
        (
            shot_score,
            shot_score_pre_defense,
            shot_defense_score_for_sfx,
            d_foul,
            foul_player,
        ) = shot_manager.calculate_shot_score(
            stealer, None, None, None, shot_type, defense_playcall,
            is_three, True, None, bh_target,
            apply_defense=False,
        )
        made = True
        # Track no-defender breakdown for stats parity with OREB putback path.
        game_state["no_defender_shots"] = int(
            game_state.get("no_defender_shots", 0) or 0
        ) + 1
        increment_no_defender_shot_breakdown(
            game_state,
            game_state.get("offensive_state"),
            "after_steal",
        )

    # Foul book-keeping (mirrors OREB putback foul path).
    has_and_one = False
    free_throws_remaining = 0
    fouled_out_info: Dict[str, Any] = {}
    if d_foul and foul_player:
        from BackEnd.engine.phase_resolution import check_and_handle_foul_out

        foul_player.record_stat("F")
        def_team.team_fouls += 1
        game_state["foul_team"] = "DEFENSE"
        game_state["shooter"] = stealer
        game_state["offensive_state"] = "FREE_THROW"
        game_state["free_throws"] = 1 if made else 2
        game_state["free_throws_remaining"] = game_state["free_throws"]
        game_state["one_and_one"] = False
        fouled_out_info = check_and_handle_foul_out(
            foul_player, game_state, def_team
        )
        if made:
            has_and_one = True
            free_throws_remaining = 1
        else:
            free_throws_remaining = 2

    # Player Momentum (Player_Momentum_System.md): this self-contained shot path
    # bypasses ShotManager.resolve_shot, so record the FG attempt for the
    # consecutive-shot streak here (skip a miss that drew a shooting foul) and
    # apply the and-1 bonus on a made foul. Blocks/charges don't occur on this path.
    if made or not d_foul:
        stealer.record_shot_result(made)
    if made and d_foul and foul_player:
        stealer.add_momentum(MO_AND_ONE_DELTA)

    # Variant + extras for the rim animation (RATTLE / BANK / SWISH / etc.).
    shot_threshold_for_variant = off_team.team_attributes.get("shot_threshold", 100)
    try:
        shot_variant = select_shot_variant(
            shot_score=shot_score_pre_defense,
            shot_threshold=shot_threshold_for_variant,
            shot_type=shot_type,
            made=made,
        )
        shot_variant_extras = roll_shot_variant_extras(
            shot_variant, shooter_y=bh_target["y"],
        )
    except Exception:
        shot_variant = None
        shot_variant_extras = {}

    # Stat updates + rebound resolution.
    rebound_type: Optional[str] = None
    rebounder_pid: Optional[str] = None
    rebound_ball_spot: Optional[Dict[str, float]] = None
    rebound_attemptors: Optional[Dict[str, List[str]]] = None
    if made:
        stealer.record_stat("FGA")
        apply_scoring(game, off_team, stealer, 2, ["FGM"])
        # Fast-break make stat policy (parity with shot_manager FB path):
        # FB_PTS for any fast-break make, POT because After Steal is always
        # steal-initiated. PIP is intentionally NOT recorded on fast breaks.
        stealer.record_stat("FB_PTS", amount=2)
        stealer.record_stat("POT", amount=2)
        text_outcome = (
            f"and scores, gets fouled!" if has_and_one else "and finishes!"
        )
        possession_flips = not has_and_one
    else:
        stealer.record_stat("FGA")
        # MISS path. Foul-on-miss goes straight to FT; non-foul miss
        # resolves the rebound chain here so the next turn is a proper
        # OREB (putback / kickout decision made in resolve_offensive_rebound)
        # or HCO transition (DREB). Without this, offensive_state stays at
        # "FAST_BREAK" and the next turn loops back into another FB —
        # mirror of the MAKE bug we fixed.
        possession_flips = False  # default; DREB branch flips below
        if not d_foul:
            rim = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
            basket_x = float(rim["x"])
            bounce_spot = calculate_bounce_spot(game, basket_x=basket_x, basket_y=25)

            # Penalize the shooter by 20% distance (matches OREB putback
            # miss pattern at shared.py:1113-1114); don't exclude anyone.
            penalize_player_ids = {stealer_id} if stealer_id else set()
            exclude_player_ids: set = set()
            with _temporary_lineup_coords(game, end_coords):
                new_rebounder, new_team, new_stat = determine_rebounder(
                    game, bounce_spot, exclude_player_ids, penalize_player_ids,
                )
                rebounder_pid = _safe_id(new_rebounder)
                rebound_attemptors = collect_near_bounce_rebound_attemptors(
                    game,
                    bounce_spot,
                    rebounder_pid,
                    coords_already_display_oriented=True,
                )
            rebound_type = str(new_stat) if new_stat else "DREB"
            rebound_ball_spot = {
                "x": float(bounce_spot["x"]),
                "y": float(bounce_spot["y"]),
            }

            # Stat credit on the canonical roster player (parity with OREB
            # putback miss flow at shared.py:1126-1133).
            if new_rebounder is not None:
                canonical = (
                    new_team.get_player_by_id(rebounder_pid)
                    if rebounder_pid and new_team
                    else None
                )
                (canonical or new_rebounder).record_stat(rebound_type)

            if rebound_type == "OREB" and new_rebounder is not None:
                # Set pending_oreb; game_manager's while loop picks this up
                # and fires resolve_offensive_rebound_turn → 90/10 split
                # between PUTBACK_ATTEMPT and OREB_KICKOUT. offensive_state
                # is intentionally NOT overwritten (pending_oreb is the
                # routing signal; OREB isn't a valid offensive_state).
                game_state["pending_oreb"] = {
                    "rebounder": new_rebounder,
                    "rebounder_id": rebounder_pid,
                    "from_block": False,
                }
                possession_flips = False
            else:
                # DREB: flip possession; route to HCO. Cascade DREB→FB is
                # NOT computed here (the existing FB systems handle this
                # via pending_dreb_fb_play_key on regular shot turns; we
                # keep after-steal-FB-DREB conservative — straight to HCO).
                game_state["offensive_state"] = "HCO"
                game_state["last_rebounder"] = new_rebounder
                possession_flips = True

        text_outcome = (
            "but misses, fouled on the shot."
            if d_foul
            else "but misses."
        )

    stealer_name = get_name_safe(stealer)
    text = f"Fast Break! {stealer_name} takes it the other way, {text_outcome}"

    # --- Pressure-type determination for the NEXT possession ---------------
    # Handlers are source of truth for game_state["offensive_state"] per
    # turn_manager.py:1671-1687. If we don't set it here, it stays at
    # "FAST_BREAK" from the steal resolution and the next turn after BIP
    # gets routed back into another FB (perpetual loop). Mirrors OREB
    # putback's pattern at turn_manager.py:4041-4044.
    #
    # On a MAKE without and-1, possession flips: the team that just scored
    # becomes defense and applies pressure (FCP/HCT/HCO) per their settings.
    # On and-1, offensive_state was already set to FREE_THROW in the foul
    # block. On MISS + foul, same — FREE_THROW. On MISS without foul, the
    # rebound chain (DREB/OREB) handles state in downstream resolution.
    pressure_type: Optional[str] = None
    if made and not has_and_one:
        try:
            pressure_type = game.turn_manager.determine_defensive_pressure_type()
        except Exception as e:
            logging.warning(
                "🚨 [AFTER_STEAL] determine_defensive_pressure_type failed: %s; defaulting to HCO", e
            )
            pressure_type = "HCO"
        game_state["offensive_state"] = pressure_type

    # --- Build the turn_result ---------------------------------------------
    next_play_type: str
    if has_and_one:
        next_play_type = "FREE_THROW"
    elif made:
        next_play_type = "BASELINE_INBOUND"
    elif d_foul and free_throws_remaining > 0:
        next_play_type = "FREE_THROW"
    elif rebound_type == "OREB":
        # Live ball, OREB → game_manager's pending_oreb loop picks up.
        next_play_type = "OREB"
    elif rebound_type == "DREB":
        # DREB → new offense brings up; offensive_state="HCO" already set.
        next_play_type = "HCO"
    else:
        # Defensive fallback (shouldn't reach here in normal flow).
        next_play_type = "HCO"

    # Ball bounce coords for misses (paint shots) — keep close to rim.
    rim = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
    ball_bounce_x = float(rim["x"])
    ball_bounce_y = float(rim["y"])

    result_type = "MAKE" if made else "MISS"
    turn_result: Dict[str, Any] = {
        "result_type": result_type,
        "current_turn": "FAST_BREAK",
        "fast_break": True,
        "fast_break_play": AFTER_STEAL,
        "ball_handler": stealer,
        "shooter": stealer,
        "shooter_id": stealer_id,
        "shooter_team_id": off_team.team_id,
        "defender": shot_defender,
        "text": text,
        "possession_flips": possession_flips,
        "offense_team_id": off_team.team_id,
        "quarter": game.quarter,
        "next_play_type": next_play_type,
        "next_turn": next_play_type,
        "score": dict(game.score),
        "shot_type": shot_type,
        "shot_score": shot_score,
        "shot_score_pre_defense": shot_score_pre_defense,
        "shot_defense_score_for_sfx": shot_defense_score_for_sfx,
        "shot_variant": shot_variant,
        "sfx": {
            "shot_type": shot_type,
            "shot_score_pre_defense": shot_score_pre_defense,
            "shot_defense_score_for_sfx": shot_defense_score_for_sfx,
            "shot_variant": shot_variant,
        },
        # After-steal-specific fields for the schema emitter:
        "after_steal_end_coords": end_coords,
        "after_steal_first_arriver_id": first_arriver_id,
        "after_steal_contested": contested,
        "shot_defender_id": _safe_id(shot_defender),
        "t_shooter_game_seconds": float(t_shooter),
        "bh_target": dict(bh_target),
    }
    if made:
        turn_result["points"] = 2
        turn_result["scoring_team"] = off_team.name
        # Pressure-type carries into the BIP turn so the next defensive
        # setup (FCP/HCT/HCO) is applied when the new offense inbounds.
        # Mirrors OREB putback's pm["next_defensive_setup"] assignment.
        if pressure_type is not None:
            turn_result["next_defensive_setup"] = pressure_type
    else:
        # Use the rebound bounce spot if we computed one; else fall back
        # to rim (foul-on-miss paths don't compute a bounce since FT fires
        # immediately).
        if rebound_ball_spot is not None:
            turn_result["ball_bounce_x"] = rebound_ball_spot["x"]
            turn_result["ball_bounce_y"] = rebound_ball_spot["y"]
        else:
            turn_result["ball_bounce_x"] = ball_bounce_x
            turn_result["ball_bounce_y"] = ball_bounce_y

        # Rebound info on the turn so the schema emitter / downstream
        # systems can animate the bounce and chain the next turn.
        if rebound_type is not None:
            turn_result["rebound_type"] = rebound_type
            turn_result["rebounderId"] = rebounder_pid
            if rebound_ball_spot is not None:
                turn_result["ballSpot"] = dict(rebound_ball_spot)
            if rebound_attemptors is not None:
                turn_result["offense_rebounders"] = rebound_attemptors["offense_rebounders"]
                turn_result["defense_rebounders"] = rebound_attemptors["defense_rebounders"]

    if shot_variant_extras:
        turn_result.update(shot_variant_extras)

    if d_foul and foul_player:
        turn_result["foul_player_id"] = _safe_id(foul_player)
        turn_result["foul_team"] = "DEFENSE"
        turn_result["free_throws_remaining"] = free_throws_remaining
        if has_and_one:
            turn_result["has_and_one"] = True
        if fouled_out_info.get("fouled_out"):
            turn_result["fouled_out"] = True
            turn_result["foul_out_player"] = {
                "player_id": fouled_out_info["foul_player_id"],
                "name": fouled_out_info["foul_player_name"],
                "photo": fouled_out_info["foul_player_photo"],
                "team": fouled_out_info["foul_player_team"],
            }
            turn_result["foul_count"] = fouled_out_info["foul_count"]

    # Roles dict for downstream consumers (parity with other FB paths).
    turn_result["roles"] = {
        "offense": [_safe_id(p) for p in off_lineup.values() if p is not None],
        "defense": [_safe_id(p) for p in def_lineup.values() if p is not None],
        "ball_handler": stealer,
        "ball_handler_id": stealer_id,
        "is_steal_entry": True,
        "fast_break_play": AFTER_STEAL,
    }

    # Attempt aggregates were recorded before the caller short-circuited here.
    # Apply only the completion stats from the shared Fast Break path.
    _record_after_steal_fast_break_stats(game, turn_result, stealer, defenders)

    # time_elapsed: drive step + post-shot sub-step approximations.
    # Schema emitter recomputes precise per-step T; this is for legacy clock
    # bookkeeping at the turn level (matches other FB resolvers).
    turn_result["time_elapsed"] = max(1, int(round(t_shooter + 1.0)))

    # ✅ SS&S: Clear steal-related data after using it.
    game_state.pop("last_stealer_coords", None)
    game_state["last_stealer"] = None

    return turn_result
