"""Defender placement — the movement-model producer.

Extracted verbatim from ``BackEnd/models/animator.py`` (commit 1 of 2: PURE
RELOCATION, no behaviour change). ``Animator`` now imports and delegates here;
this module must never import ``Animator`` back.

WHY THIS IS THE WHOLE MOVEMENT MODEL AND NOT JUST "PLACE DEFENDERS": the four
``position_*_defenders`` functions take ``offensive_animations`` as their
primary input — they read the per-step offensive coordinate track and
``hasBallAtStep`` to find the ball handler at each step. The offense build is
therefore placement's input, not a separable sibling, which is why
``build_all_animations`` comes along.

Commit 2 makes this the single producer consumed by contest, emitter and
renderer, and deletes the ``_hco_render_animations`` stash that currently pipes
the render's draw backwards into ``StepState``. Nothing about ownership changes
here: same call sites, same order, same number of computations.
"""
import logging
import os

from BackEnd.constants import (
    HCO_STRING_SPOTS,
    OFFSET_SPOTS,
    ACTIONS,
)
from BackEnd.utils.shared import get_away_player_coords

# Dynamic HCO Defense — S1 Part B (Dynamic_MM_Brief §7). A beaten defender LAGS instead of tracking:
# he ends a fraction of the way from his prior spot toward his tracked (man-following) spot, opening
# the gap to his man — the openness primitive the shot contest + dish gate read. Lag scales with how
# badly he lost the read (|margin|; owner-locked option a). A beaten score ≤ MOTION_READ_THRESHOLD, so
# the beat margin ∈ [−110, 0] → |margin| ∈ [0, 110]: a full beat lags OPENNESS_LAG_MAX toward-freeze,
# a marginal miss barely lags. A defender whose man DIDN'T move never lags (no space to open).
#
# These moved here from ``animator.py`` with the code that reads them.
# ``scripts/s1_openness_monte_carlo.py`` overrides OPENNESS_LAG_MAX by module attribute, so it
# patches THIS module now — a stale patch on animator would have been silently ignored.
OPENNESS_LAG_MAX = 0.8              # worst beat → defender tracks only (1 − 0.8) = 20% toward his man
OPENNESS_LAG_MARGIN_SCALE = 110.0  # |margin| at which lag saturates (= MOTION_READ_THRESHOLD)
OPENNESS_ANCHOR_MOVE_EPS = 1.0     # guarded man must travel > this many grid for a beat to open space


def _attack_drive_defender_override(skeleton_step, def_pos):
    """Return a per-defender coord/action override for this step, if present. Two producers:
    an attack-drive beat (``_attack_drive.defender_overrides``) or an altered-action subtle beat
    (``_subtle_movement.defender_overrides`` — e.g. a jab-step defender biting inward). Honored in
    both the man and zone placement paths; skips the S1 lag so the defender renders AT the override."""
    if not skeleton_step:
        return None
    for _key in ("_attack_drive", "_subtle_movement"):
        ov = ((skeleton_step.get(_key) or {}).get("defender_overrides") or {}).get(def_pos)
        if ov:
            return ov
    return None


def _strict_pos_action_keys() -> bool:
    """Whether an unresolvable ``pos_action`` should raise instead of being skipped.

    ON in tests and local development, OFF in production. The asymmetry is deliberate:
    a skeleton that names no position for a player is a data defect we want to hear
    about immediately while someone can fix it, and something we must not crash a
    paying player's game over. See the key-dispatch else branch for the full reasoning.

    ``GOB_STRICT_POS_ACTION_KEYS`` overrides in either direction; absent that, strict
    is on under pytest only.
    """
    flag = os.getenv("GOB_STRICT_POS_ACTION_KEYS", "").strip().lower()
    if flag in ("true", "1", "yes"):
        return True
    if flag in ("false", "0", "no"):
        return False
    return "PYTEST_CURRENT_TEST" in os.environ


def _subtle_defender_should_freeze(skeleton_step, def_pos, anchor_off_pos):
    """Dynamic HCO subtle beat: should this defender FREEZE (hold prior coords) instead of
    tracking his man / re-placing? Returns False for non-subtle steps.

    An EXPLICIT per-defender read on the beat (``_subtle_movement.defender_reads[def_pos]``) is
    AUTHORITATIVE: True → track/adjust (do the proper thing), False → freeze (hold prior). This holds
    even when his anchor didn't move, so a ZONE defender reacting to a VACATED zone (good read) can drop
    off / re-anchor instead of being force-frozen by the anchor-moved heuristic. (Man is unaffected: a
    read that passed on a stationary man tracks to the same spot he'd hold anyway.)

    With NO explicit read (unchanged-occupancy zone defenders; non-dynamic beats) it falls back to the
    legacy heuristic: freeze when the guarded man did NOT move (brief: Updated Subtle Movement Logic —
    Defense Behavior). Works for man (anchor = matchup) and zone (anchor = assigned zone offender)."""
    sm = skeleton_step.get("_subtle_movement") if skeleton_step else None
    if not sm:
        return False
    reads = sm.get("defender_reads") or {}
    if def_pos in reads:
        return not reads[def_pos]                       # explicit read governs (True → move, False → hold)
    anchor_moved = anchor_off_pos in (sm.get("movers") or [])
    return not anchor_moved


def _defender_lag_fraction(skeleton_step, def_pos, anchor_off_pos, anchor_moved):
    """S1 Part B: how much this defender TRACKS his man this step, in [0,1]. 1.0 = full track;
    lower = lagged (beaten → space opens). Reads the GRADED per-step reads Part A stamps on
    ``step["_defender_reads"]`` (``{def_pos: {follows, margin}}``): a beaten defender whose man moved
    lags by |margin|. When no graded reads exist on the step (SM beats carry bool reads on
    ``_subtle_movement``; non-dynamic turns carry none) it delegates to the legacy
    ``_subtle_defender_should_freeze`` → binary full-freeze / track, so those paths are UNCHANGED."""
    reads = (skeleton_step or {}).get("_defender_reads") or {}
    r = reads.get(def_pos)
    if isinstance(r, dict):
        if r.get("follows", True) or not anchor_moved:
            return 1.0
        beat = min(1.0, abs(float(r.get("margin", 0.0))) / OPENNESS_LAG_MARGIN_SCALE)
        return max(0.0, 1.0 - OPENNESS_LAG_MAX * beat)
    return 0.0 if _subtle_defender_should_freeze(skeleton_step, def_pos, anchor_off_pos) else 1.0


def build_all_animations(game, skeleton, off_lineup, def_lineup, add_defenders=True, is_fcp=False, is_hct=False):
    """Core of ``skeleton_to_animations`` (offense build + defender placement), factored out so
    the contest's defender grid can reuse the EXACT same computation without the full-sim
    early-return. Behavior-preserving — ``skeleton_to_animations`` delegates here after its
    early-returns; ``compute_defender_grid`` calls it directly (sim-safe).

    Returns ``(animations, zone_assignments_by_step)``. The zone guard map used to be written
    straight onto ``game.zone_defender_assignments_by_step`` from inside the zone placement
    loop; it is now threaded in and out explicitly, and the ``Animator`` adapter publishes it.

    ``zone_assignments`` stays **None** unless the zone branch actually writes, because the
    attribute's ABSENCE is load-bearing: ``phase_resolution.py:5314`` reads it with ``hasattr``
    and ``:5336`` ``delattr``s it. Creating it eagerly for man defense would change those.
    """
    animations = []
    steps = skeleton["steps"]
    # Seed from the existing map so the zone loop's own read-back (and accumulation across
    # turns, which test_hco_post_subtle_grid asserts) sees exactly what it sees today.
    zone_assignments = getattr(game, "zone_defender_assignments_by_step", None)
    
    # Determine if away team is on offense ONCE at the start (not inside loops)
    # This ensures consistency when loading saved games where game state may have changed
    is_away_offense = game.offense_team.team_id == game.away_team.team_id
    
    # Group all positions that appear in any step
    all_positions = set()
    for step in steps:
        all_positions.update(step.get("pos_actions", {}).keys())
    
    # Build animation for OFFENSIVE players from skeleton
    offensive_animations = {}  # Store by position for defensive matching
    
    # Build animation for OFFENSIVE players from skeleton
    for position in sorted(all_positions, key=str):  # sorted(): set iteration is hash-ordered; see projects/bugs.md (PYTHONHASHSEED)
        player = off_lineup.get(position)
        if not player:
            continue
        
        player_id = getattr(player, "player_id", None)
        if not player_id:
            continue
        
        # 🔍 DEBUG: Log position to player ID mapping for steps 15, 16, 17 (3-2 Motion bug)
        # Check steps around the problematic pass to identify indexing issue
        for check_step_idx in [15, 16, 17]:
            if len(steps) > check_step_idx and steps[check_step_idx].get("pos_actions", {}).get(position):
                step_action = steps[check_step_idx].get("pos_actions", {}).get(position).get("action")
                step_timestamp = steps[check_step_idx].get("timestamp", 0)
                if step_action in ["pass", "receive"]:
                    player_name = getattr(player, "name", "unknown")
                    # logging.warning(f"🔍 [SKELETON MAPPING] Step {check_step_idx} (timestamp {step_timestamp}) - Position {position} → Player {player_name} (ID: {player_id[:8]}) with action: {step_action}")
        
        # Build movement array from steps
        movement = []
        has_ball_steps = []
        start_coords = None
        end_coords = None
        total_steps = len(steps)
        
        # 🔍 DEBUG: Track which skeleton steps map to which movement array indices
        step_mapping = []  # Will store (skeleton_step_idx, timestamp) for each movement entry
        
        for step_idx, step in enumerate(steps):
            pos_action = step.get("pos_actions", {}).get(position)
            if not pos_action:
                continue
            
            timestamp = step.get("timestamp", 0)
            step_mapping.append((step_idx, timestamp))  # Track mapping
            
            # Get action early to check if we should use offset coords for screeners
            action = pos_action.get("action", "drift")
            
            # Handle both coords and location formats
            has_opp = pos_action.get("opp", False)
            coords_from_location = False
            
            # Opp field handling (debug logs removed)
            
            if "coords" in pos_action:
                coords = pos_action.get("coords", {"x": 50, "y": 25})
                # Coords already exist - these should have been set by apply_opposite_side_logic()
                coords_already_flipped = True
            elif "location" in pos_action or "spot" in pos_action:
                # Convert spot name to coordinates. Skeletons author the name under either
                # key ("location" in the HCO/FCP families, "spot" in HCT), so accept both —
                # the same vocabulary the eleven defender readers below already speak.
                location = pos_action.get("location") or pos_action.get("spot") or "key"
                
                # ✅ SCREEN OFFSET: Use OFFSET_SPOTS for screen actions, otherwise use HCO_STRING_SPOTS
                # This ensures screeners animate to offset positions to avoid visual overlap
                # Check both ACTIONS["SCREEN"] (which is "screen") and literal "screen" for safety
                if action == ACTIONS["SCREEN"] or action == "screen":
                    # Try to use offset coords for screeners, fallback to standard if not available
                    coords = OFFSET_SPOTS.get(location) or HCO_STRING_SPOTS.get(location, {"x": 50, "y": 25})
                else:
                    # Use standard coordinates for non-screen actions
                    coords = HCO_STRING_SPOTS.get(location, {"x": 50, "y": 25})
                
                coords_from_location = True
                coords_already_flipped = False
            else:
                # The pos_action carries none of coords/location/spot, so where this player
                # stands is genuinely unknown.
                #
                # NEVER SUBSTITUTE A COORDINATE. This branch used to answer
                # {"x": 50, "y": 25}, which parked players on the centre logo for two years
                # without anyone noticing, so guessing is not an option.
                #
                # But it must not crash a live game either. Skeletons are authored in MongoDB
                # through the play builder -- ``phase_resolution.get_skeleton_by_lean`` reads
                # ``play_doc["skeletons"]``, and there are fcp_skeletons / hct_skeletons
                # collections -- so BackEnd/playcall_skeletons/ is the FALLBACK, not the only
                # source. Persisted exports audit clean (4,325 offense pos_actions, 100%
                # "location"), but the builder can author a new shape at any time and the live
                # collections have not been inspected.
                #
                # So: raise where a human can act on it, decline where a player is mid-game.
                # Declining is not a new code path -- it is exactly what an ABSENT pos_action
                # already does at the top of this loop, and the emitter then backfills this
                # player from his live ``player.coords`` (his real position, not a default) in
                # ``skeleton_step_emitter._backfill_missing_active_coords``.
                detail = (
                    f"pos_action for {position} at step {step_idx} carries no position key "
                    f"(want one of coords/location/spot, got {sorted(pos_action.keys())})"
                )
                if _strict_pos_action_keys():
                    raise ValueError(detail)
                logging.error(
                    "🚨 [POS_ACTION] %s — declining to place this player for this step "
                    "rather than inventing a coordinate. Skeleton is likely builder-authored "
                    "with an unrecognised shape.", detail,
                )
                # step_mapping is indexed by movement position further down, so it must stay
                # 1:1 with `movement`; this step's entry was appended before the dispatch.
                step_mapping.pop()
                continue
            
            # ✅ FIX: Handle "opp" field for FCP/HCT skeletons when location exists (coords need to be calculated)
            # Players with opp=True should be on the opposite side of the court
            if (is_fcp or is_hct) and has_opp and coords_from_location:
                # Player with opp=True should be on opposite side (defensive side)
                if is_away_offense:
                    # Away team offense - ball handlers go to home side (defensive side)
                    # No coordinate flip needed - they stay on home side (HCO_STRING_SPOTS are in home orientation)
                    pass
                else:
                    # Home team offense - ball handlers go to away side (defensive side)
                    # Flip coordinates to away side
                    coords = get_away_player_coords(coords)
                    coords_already_flipped = True
            elif (is_fcp or is_hct) and not has_opp and coords_from_location:
                # Player without opp field stays on same side as normal offense
                if is_away_offense:
                    # Away team offense - outlet players go to away side (offensive side)
                    # Flip coordinates to away side (normal away team flip)
                    # This will happen in the normal away team flip logic below
                    pass
                else:
                    # Home team offense - outlet players stay on home side (offensive side)
                    # No coordinate flip needed
                    pass
            
            # Apply coordinate flipping for AWAY team (HCO_STRING_SPOTS are in home orientation)
            # Home team uses coords as-is to attack home basket (x=90)
            # Away team needs to flip to attack away basket (x=10)
            # is_away_offense calculated once at function start (line 809) for consistency
            # Only flip if not already flipped by opp logic above
            # ✅ SCREEN OFFSET: Flip offset coords for away team (determine offset first, then flip)
            if is_away_offense and not coords_already_flipped:
                coords = get_away_player_coords(coords)
            
            if start_coords is None:
                start_coords = coords
            end_coords = coords
            
            # Determine if player has ball at this step
            # Note: "pass" means releasing ball, NOT holding it
            has_ball = action in ["handle_ball", "receive", "shoot", "drive"]
            
            movement.append({
                "timestamp": timestamp,
                "coords": coords,
                "action": action
            })
            has_ball_steps.append(has_ball)
        
        if not movement:
            continue
        
        # 🔍 DEBUG: Log movement array mapping for SF and PG at indices 15, 16, 17 (3-2 Motion bug)
        if position in ["SF", "PG"] and len(movement) > 16:
            for check_mov_idx in [15, 16, 17]:
                if check_mov_idx < len(step_mapping):
                    skeleton_idx, timestamp = step_mapping[check_mov_idx]
                    player_name = getattr(player, "name", "unknown")
                    # logging.warning(f"🔍 [MOVEMENT MAPPING] {position} ({player_name}) - movement[{check_mov_idx}] = skeleton step {skeleton_idx} (timestamp {timestamp})")
        
        # Calculate duration (last timestamp)
        duration = movement[-1]["timestamp"] if movement else 0
        
        anim = {
            "playerId": player_id,
            "start": start_coords or {"x": 50, "y": 25},
            "end": end_coords or {"x": 50, "y": 25},
            "movement": movement,
            "hasBallAtStep": has_ball_steps,
            "duration": duration
        }
        
        animations.append(anim)
        offensive_animations[position] = anim  # Store for defensive matching
    
    # Add DEFENSIVE player animations
    if add_defenders and def_lineup:
        if is_fcp:
            # Use FCP-specific defensive positioning
            defensive_anims = position_fcp_defenders(
                game,
                offensive_animations, 
                def_lineup, 
                steps
            )
            animations.extend(defensive_anims)
        elif is_hct:
            # HCT now uses zone-based placement + trap formation (HCT_To_Zone.md /
            # FCP_HCT_System.md). Trap defenders sit on the ball handler in upper /
            # lower shifts; all other defenders run standard zone defender priority
            # logic against the HCT polygon for their position.
            defensive_anims = position_hct_zone_defenders(
                game,
                offensive_animations,
                def_lineup,
                steps,
            )
            animations.extend(defensive_anims)
        else:
            # Check if defense is a zone type (e.g., "2-3 Zone", "3-2 Zone", "1-3-1 Zone")
            from BackEnd.utils.defense_utils import is_zone_defense
            defense_playcall = game.game_state.get("defense_playcall", "man")
            if is_zone_defense(defense_playcall):
                # Use zone defense positioning (currently supports 2-3 zone, will expand for other types)
                defensive_anims, zone_assignments = position_zone_defenders(
                    game,
                    offensive_animations,
                    def_lineup,
                    steps,
                    zone_assignments,
                )
                animations.extend(defensive_anims)
            else:
                # Use standard defensive positioning for HCO (man-to-man)
                defensive_anims = position_standard_defenders(
                    game,
                    offensive_animations, 
                    def_lineup, 
                    steps
                )
                animations.extend(defensive_anims)
    
    return animations, zone_assignments


def position_fcp_defenders(game, offensive_animations, def_lineup, skeleton_steps):
    """
    Position defensive players for Full Court Press scenarios.
    
    Strategy:
    - Each defender guards the offensive player at their position
    - Defender maintains same Y coordinate as their assignment
    - Defender is positioned 3 grid units closer to the offensive basket
    - Ball handler is determined per step (dynamic) for consistent guard logic
    
    Args:
        offensive_animations: Dict mapping position → offensive player animation
        def_lineup: Dict of defensive players by position
        skeleton_steps: List of skeleton steps for timing
        
    Returns:
        List of defensive player animations
    """
    defensive_animations = []
    
    # Determine which direction is "closer to offensive basket"
    is_away_offense = game.offense_team.team_id == game.away_team.team_id
    
    # For away team offense: offensive basket is on the LEFT (lower x)
    # For home team offense: offensive basket is on the RIGHT (higher x)
    x_offset = -3 if is_away_offense else 3

    # Precompute ball handler per timestamp (dynamic by step)
    ball_handler_by_timestamp = {}
    initial_ball_handler_pos = None
    for pos, off_anim in offensive_animations.items():
        has_ball_list = off_anim.get("hasBallAtStep", [])
        for idx, off_step in enumerate(off_anim.get("movement", [])):
            if idx < len(has_ball_list) and has_ball_list[idx]:
                ts = off_step.get("timestamp")
                if ts is not None:
                    ball_handler_by_timestamp[ts] = pos
                    if initial_ball_handler_pos is None:
                        initial_ball_handler_pos = pos
    if initial_ball_handler_pos is None:
        initial_ball_handler_pos = "PG"
    
    # Match each defensive position to offensive position
    for position, off_anim in offensive_animations.items():
        # Get the defensive player at this position
        def_player = def_lineup.get(position)
        if not def_player:
            continue
        
        def_player_id = getattr(def_player, "player_id", None)
        if not def_player_id:
            continue
        
        # Build defensive movement matching offensive player's path
        def_movement = []
        def_start = None
        def_end = None
        
        for off_step in off_anim["movement"]:
            timestamp = off_step["timestamp"]
            off_coords = off_step["coords"]

            # Determine current ball handler at this timestamp
            current_ball_handler_pos = ball_handler_by_timestamp.get(timestamp, initial_ball_handler_pos)
            is_guarding_ball_handler = position == current_ball_handler_pos
            
            # Defender position: same Y, X offset toward offensive basket
            def_coords = {
                "x": off_coords["x"] + x_offset,
                "y": off_coords["y"]
            }
            
            # Clamp X to valid court bounds (0-100)
            def_coords["x"] = max(0, min(100, def_coords["x"]))
            
            # Determine defensive action based on offensive action
            if is_guarding_ball_handler:
                def_action = "guard_ball"  # Guarding ball handler
            else:
                def_action = "guard_offball"  # Guarding off-ball player
            
            if def_start is None:
                def_start = def_coords
            def_end = def_coords
            
            def_movement.append({
                "timestamp": timestamp,
                "coords": def_coords,
                "action": def_action
            })
        
        if not def_movement:
            continue
        
        # All defenders have ball at no steps
        has_ball_steps = [False] * len(def_movement)
        duration = def_movement[-1]["timestamp"] if def_movement else 0
        
        defensive_animations.append({
            "playerId": def_player_id,
            "start": def_start or {"x": 50, "y": 25},
            "end": def_end or {"x": 50, "y": 25},
            "movement": def_movement,
            "hasBallAtStep": has_ball_steps,
            "duration": duration
        })
    
    return defensive_animations


def position_hct_zone_defenders(game, offensive_animations, def_lineup, skeleton_steps):
    """
    Position defensive players for HCT using zone-based placement + trap formation.

    Per step:
      1. Find current ball handler (per-timestamp; ball can change hands).
      2. Pick shift via ball handler y: ``< 20`` → lower, ``> 30`` → upper, else normal.
      3. Trap defenders (PG+SG upper / PG+SF lower / none normal) are placed via
         trap formation: BH_x + random(1..4) toward basket, ±2 y-offset, paired
         y-shift if either would leave the y-clamp box, distinct x-offsets.
      4. Other defenders run standard zone defender priority logic against the
         HCT polygon (BH-in-zone → 1-player-in-zone → multi-player-closest-to-basket).
         Zones with fewer than 3 vertices fall back to "closest listed spot to BH".

    Coordinate orientation matches the existing HCO zone helper: zone polygons
    are flipped via ``_get_zone_coords`` when the away team is on offense; the
    standard ``assign_zone_defender_coords`` return value is flipped back to
    match offensive coords.
    """
    from BackEnd.utils.shared_defense import (
        _get_hct_standard_zone_boundaries,
        _get_hct_bh_guarders_for_shift,
        compute_hct_trap_formation,
        assign_zone_defender_coords,
        resolve_hct_defender_collisions,
        _point_in_polygon,
    )
    from BackEnd.utils.shared import get_away_player_coords

    defensive_animations = []
    if not offensive_animations or not def_lineup:
        return defensive_animations

    is_away_offense = game.offense_team.team_id == game.away_team.team_id
    aggression = game.defense_team.strategy_calls.get("aggression_call", "normal")

    # Coords-by-step in current orientation (no flipping; mirrors HCO zone path).
    offensive_positions_by_step = {}
    for pos, off_anim in offensive_animations.items():
        offensive_positions_by_step[pos] = [
            step.get("coords", {"x": 50, "y": 25}) for step in off_anim.get("movement", [])
        ]

    max_steps = max(
        (len(off_anim.get("movement", [])) for off_anim in offensive_animations.values()),
        default=1,
    )

    # Initial fallback ball handler (step-0 carrier; rarely needed).
    fallback_bh = "PG"
    for pos, off_anim in offensive_animations.items():
        if off_anim.get("hasBallAtStep", [False])[0]:
            fallback_bh = pos
            break

    per_def_movement = {pos: [] for pos in ["PG", "SG", "SF", "PF", "C"] if def_lineup.get(pos)}

    for step_index in range(max_steps):
        current_bh_pos = None
        for pos, off_anim in offensive_animations.items():
            has_ball_list = off_anim.get("hasBallAtStep", [])
            if step_index < len(has_ball_list) and has_ball_list[step_index]:
                current_bh_pos = pos
                break
        if not current_bh_pos:
            current_bh_pos = fallback_bh

        bh_coords_list = offensive_positions_by_step.get(current_bh_pos, [])
        bh_coords = (
            bh_coords_list[step_index]
            if step_index < len(bh_coords_list)
            else (bh_coords_list[-1] if bh_coords_list else {"x": 50, "y": 25})
        )

        zone_boundaries, shift = _get_hct_standard_zone_boundaries(
            bh_coords.get("y", 25), is_away_offense
        )
        bh_guarders = _get_hct_bh_guarders_for_shift(shift)
        trap_coords = compute_hct_trap_formation(bh_coords, shift, is_away_offense)

        # Skeleton-step ball spot for standard zone priority context.
        ball_spot = "key"
        if step_index < len(skeleton_steps):
            step_data = skeleton_steps[step_index]
            bh_action = step_data.get("pos_actions", {}).get(current_bh_pos, {})
            ball_spot = bh_action.get("location") or bh_action.get("spot") or "key"

        # Build offensive_players for the standard priority logic.
        offensive_players = []
        for off_pos in offensive_animations.keys():
            coords_list = offensive_positions_by_step.get(off_pos, [])
            coords = (
                coords_list[step_index]
                if step_index < len(coords_list)
                else (coords_list[-1] if coords_list else {"x": 50, "y": 25})
            )
            spot = "key"
            if step_index < len(skeleton_steps):
                step_data = skeleton_steps[step_index]
                off_action_data = step_data.get("pos_actions", {}).get(off_pos, {})
                spot = off_action_data.get("location") or off_action_data.get("spot") or "key"
            player_obj = game.offense_team.lineup.get(off_pos)
            offensive_players.append({
                "player_id": getattr(player_obj, "player_id", None) if player_obj else None,
                "coords": coords,
                "is_ball_handler": off_pos == current_bh_pos,
                "spot": spot,
            })

        timestamp = (
            skeleton_steps[step_index].get("timestamp", step_index * 800)
            if step_index < len(skeleton_steps)
            else step_index * 800
        )

        # Compute coords + action for every defender at this step, THEN run the
        # collision pass so any exact (x, y) overlap is resolved before append.
        step_coords = {}
        step_actions = {}
        for def_pos in per_def_movement.keys():
            if def_pos in bh_guarders and def_pos in trap_coords:
                step_coords[def_pos] = dict(trap_coords[def_pos])
                step_actions[def_pos] = "guard_ball"
                continue

            zone_polygon = zone_boundaries.get(def_pos)
            def_coords = None
            def_action = "guard_offball"

            if zone_polygon and len(zone_polygon) >= 3:
                coords = assign_zone_defender_coords(
                    def_pos,
                    zone_boundaries,
                    offensive_players,
                    bh_coords,
                    ball_spot,
                    aggression,
                    is_away_offense,
                )
                if coords:
                    # assign_zone_defender_coords returns HOME orientation; flip
                    # back to current orientation when the away team is on offense.
                    if is_away_offense:
                        coords = get_away_player_coords(coords)
                    def_coords = coords
                    bh_in_zone = _point_in_polygon(
                        bh_coords["x"], bh_coords["y"], zone_polygon
                    )
                    def_action = "guard_ball" if bh_in_zone else "guard_offball"
            elif zone_polygon:
                # 2-vertex (or 1-vertex) zone: place at the listed spot closest to ball.
                closest = min(
                    zone_polygon,
                    key=lambda c: (c[0] - bh_coords["x"]) ** 2
                    + (c[1] - bh_coords["y"]) ** 2,
                )
                def_coords = {"x": int(closest[0]), "y": int(closest[1])}

            if def_coords is None:
                # Last-resort fallback: zone centroid, or court center if even that's missing.
                if zone_polygon:
                    avg_x = sum(c[0] for c in zone_polygon) / len(zone_polygon)
                    avg_y = sum(c[1] for c in zone_polygon) / len(zone_polygon)
                    def_coords = {"x": int(avg_x), "y": int(avg_y)}
                else:
                    def_coords = {"x": 50, "y": 25}

            step_coords[def_pos] = def_coords
            step_actions[def_pos] = def_action

        # Collision pass: any defenders at the exact same (x, y) get split
        # around the ball handler per resolve_hct_defender_collisions.
        step_coords = resolve_hct_defender_collisions(step_coords, bh_coords)

        for def_pos, coords in step_coords.items():
            per_def_movement[def_pos].append(
                {"timestamp": timestamp, "coords": coords, "action": step_actions[def_pos]}
            )

    for def_pos, def_movement in per_def_movement.items():
        if not def_movement:
            continue
        def_player = def_lineup.get(def_pos)
        def_player_id = getattr(def_player, "player_id", None) if def_player else None
        if not def_player_id:
            continue
        defensive_animations.append({
            "playerId": def_player_id,
            "start": def_movement[0]["coords"],
            "end": def_movement[-1]["coords"],
            "movement": def_movement,
            "hasBallAtStep": [False] * len(def_movement),
            "duration": def_movement[-1]["timestamp"],
        })

    return defensive_animations


def position_zone_defenders(game, offensive_animations, def_lineup, skeleton_steps,
                            zone_assignments=None):
    """
    Position defensive players for Zone Defense (2-3 zone).
    
    Strategy:
    - Each defender guards a zone area, not a specific player
    - Zones shift based on ball location
    - Overlapping zones handled with specific logic
    - Priorities: BH in zone → 1 player in zone → >1 player (closest to basket) → 0 players (closest spot to BH)
    
    Args:
        offensive_animations: Dict mapping position → offensive player animation
        def_lineup: Dict of defensive players by position
        skeleton_steps: List of skeleton steps for timing
        
    Returns:
        List of defensive player animations
    """
    from BackEnd.utils.shared_defense import (
        _get_23_zone_boundaries,
        _get_32_zone_boundaries,
        _get_131_zone_boundaries,
        assign_all_zone_defenders,
        _point_in_zone
    )
    from BackEnd.utils.shared import get_away_player_coords
    
    defensive_animations = []
    
    # Determine court orientation
    is_away_offense = game.offense_team.team_id == game.away_team.team_id
    aggression = game.defense_team.strategy_calls.get("aggression_call", "normal")
    
    # Build offensive player positions by step for tracking
    offensive_positions_by_step = {}
    ball_handler_pos = None
    
    for pos, off_anim in offensive_animations.items():
        offensive_positions_by_step[pos] = []
        for step in off_anim.get("movement", []):
            coords = step.get("coords", {"x": 50, "y": 25})
            # ✅ DON'T unflip offensive coords - pass them as-is to zone functions
            # assign_bh_defender_coords and assign_non_bh_defender_coords expect
            # coords in their original flipped state (away orientation if away offense)
            # They will unflip internally, calculate in home orientation, and return home orientation coords
            offensive_positions_by_step[pos].append(coords)
        
        # Check if this is the ball handler (has ball at step 0)
        if off_anim.get("hasBallAtStep", [False])[0]:
            ball_handler_pos = pos
    
    if not ball_handler_pos:
        # Fallback: assume PG is ball handler
        ball_handler_pos = "PG"
    
    # Get ball handler's spot from first skeleton step
    ball_spot = "key"  # Default
    if skeleton_steps and len(skeleton_steps) > 0:
        first_step = skeleton_steps[0]
        bh_action = first_step.get("pos_actions", {}).get(ball_handler_pos, {})
        ball_spot = bh_action.get("location") or bh_action.get("spot") or "key"
    
    # Get zone boundaries based on ball location (applies shifts)
    # ✅ Zone boundaries should be in SAME orientation as offensive coords
    # When away team has ball, offensive coords are in away orientation (flipped)
    # So zone boundaries should also be in away orientation (flipped) to match
    from BackEnd.utils.defense_identity import defense_zone_shell_variant

    defense_playcall = game.game_state.get("defense_playcall", "man")
    zv = defense_zone_shell_variant(defense_playcall) or "23"
    if zv == "32":
        zone_boundaries = _get_32_zone_boundaries(ball_spot, is_away_offense)
    elif zv == "131":
        zone_boundaries = _get_131_zone_boundaries(ball_spot, is_away_offense)
    else:
        zone_boundaries = _get_23_zone_boundaries(ball_spot, is_away_offense)
    
    # Create defensive animations for each position
    for def_pos in ['PG', 'SG', 'SF', 'PF', 'C']:
        def_player = def_lineup.get(def_pos)
        if not def_player:
            continue
        
        def_player_id = getattr(def_player, "player_id", None)
        if not def_player_id:
            continue
        
        def_movement = []
        def_start = None
        def_end = None
        # Prior step's ball handler — used to detect a pass (ownership flip) so the
        # defender's animation holds through the pass step (two-handler model, see below).
        prev_ball_handler_pos = None

        # Process each step
        max_steps = max(
            len(off_anim.get("movement", [])) 
            for off_anim in offensive_animations.values()
        ) if offensive_animations else 1
        
        for step_index in range(max_steps):
            # Dynamically determine who has ball at THIS step (similar to man-to-man)
            current_ball_handler_pos = None
            for pos, off_anim in offensive_animations.items():
                has_ball_list = off_anim.get("hasBallAtStep", [])
                if step_index < len(has_ball_list) and has_ball_list[step_index]:
                    current_ball_handler_pos = pos
                    break
            
            # If no one has ball at this step, use previous ball handler (or fallback)
            if not current_ball_handler_pos:
                current_ball_handler_pos = ball_handler_pos
            
            # Get ball handler coords for this step using CURRENT ball handler position
            bh_coords_list = offensive_positions_by_step.get(current_ball_handler_pos, [])
            ball_handler_coords = bh_coords_list[step_index] if step_index < len(bh_coords_list) else (
                bh_coords_list[-1] if bh_coords_list else {"x": 50, "y": 25}
            )
            
            # Get ball handler's spot for this step using CURRENT ball handler position
            if step_index < len(skeleton_steps):
                step = skeleton_steps[step_index]
                bh_action = step.get("pos_actions", {}).get(current_ball_handler_pos, {})
                current_ball_spot = bh_action.get("location") or bh_action.get("spot") or ball_spot
            else:
                current_ball_spot = ball_spot
            
            # Update zone boundaries if ball spot changed (shift logic)
            # ✅ Zone boundaries should be in SAME orientation as offensive coords
            defense_playcall = game.game_state.get("defense_playcall", "man")
            zv = defense_zone_shell_variant(defense_playcall) or "23"
            if zv == "32":
                zone_boundaries = _get_32_zone_boundaries(current_ball_spot, is_away_offense)
            elif zv == "131":
                zone_boundaries = _get_131_zone_boundaries(current_ball_spot, is_away_offense)
            else:
                zone_boundaries = _get_23_zone_boundaries(current_ball_spot, is_away_offense)
            
            # Build list of offensive players with their coords and ball handler status
            offensive_players = []
            for off_pos, off_anim in offensive_animations.items():
                coords_list = offensive_positions_by_step.get(off_pos, [])
                coords = coords_list[step_index] if step_index < len(coords_list) else (
                    coords_list[-1] if coords_list else {"x": 50, "y": 25}
                )
                
                # Get spot for this player
                if step_index < len(skeleton_steps):
                    step = skeleton_steps[step_index]
                    off_action = step.get("pos_actions", {}).get(off_pos, {})
                    spot = off_action.get("location") or off_action.get("spot") or "key"
                else:
                    spot = "key"
                
                # Get player object to get player_id
                off_player_obj = game.offense_team.lineup.get(off_pos)
                player_id = getattr(off_player_obj, "player_id", None) if off_player_obj else None
                
                offensive_players.append({
                    "player_id": player_id,
                    "coords": coords,
                    "is_ball_handler": off_pos == current_ball_handler_pos,
                    "spot": spot
                })
            
            # Assign defensive coordinates for this defender at this step
            step_override = _attack_drive_defender_override(
                skeleton_steps[step_index] if step_index < len(skeleton_steps) else None,
                def_pos,
            )
            if step_override and step_override.get("coords"):
                def_coords = dict(step_override["coords"])
                is_guarding_bh = step_override.get("action") == "guard_ball"
            else:
                # Use assign_all_zone_defenders which handles overlaps and priorities
                # ✅ Pass is_away_offense as-is - zone functions expect coords in original flipped state
                # They will unflip internally, calculate in home orientation, and return home orientation coords
                defender_coords_dict, defender_to_offensive_player = assign_all_zone_defenders(
                    zone_boundaries,
                    offensive_players,
                    ball_handler_coords,
                    current_ball_spot,
                    aggression,
                    is_away_offense
                )
                
                # Store defender assignments for this step (for shot resolution)
                if zone_assignments is None:
                    zone_assignments = {}
                zone_assignments[step_index] = defender_to_offensive_player
                
                def_coords = defender_coords_dict.get(def_pos)
                if not def_coords:
                    # Fallback: use center of zone
                    zone_coords_list = zone_boundaries.get(def_pos, [])
                    if zone_coords_list:
                        # Average of zone coordinates (zone boundaries are in away orientation if away offense)
                        avg_x = sum(c[0] for c in zone_coords_list) / len(zone_coords_list)
                        avg_y = sum(c[1] for c in zone_coords_list) / len(zone_coords_list)
                        def_coords = {"x": int(avg_x), "y": int(avg_y)}
                    else:
                        def_coords = {"x": 50, "y": 25}
                
                # Check if this defender is guarding the ball handler
                zone_coords_for_check = zone_boundaries.get(def_pos, [])
                is_guarding_bh = ball_handler_coords and _point_in_zone(ball_handler_coords, zone_coords_for_check, False)
                
                # ✅ IMPORTANT: assign_all_zone_defenders returns coords in HOME orientation
                if is_away_offense:
                    def_coords = get_away_player_coords(def_coords)
            
            # Get timestamp
            if step_index < len(skeleton_steps):
                timestamp = skeleton_steps[step_index].get("timestamp", step_index * 800)
            else:
                timestamp = (len(skeleton_steps) - 1) * 800 if skeleton_steps else step_index * 800
            
            if step_index == 0:
                def_start = def_coords

            # Dynamic HCO subtle beat (zone): treat the defender's already-assigned zone
            # offender as "his man" for this step and apply the same read/freeze as man D.
            # Anchor = this step's zone assignment (defender_pos → offender player_id).
            skeleton_step_obj = skeleton_steps[step_index] if step_index < len(skeleton_steps) else None
            if (skeleton_step_obj and skeleton_step_obj.get("_subtle_movement") and def_movement
                    and not (step_override and step_override.get("coords"))):  # override wins over freeze
                assigns = (zone_assignments or {}).get(step_index, {})
                anchor_id = assigns.get(def_pos)
                anchor_off_pos = None
                for _opos, _opl in (game.offense_team.lineup or {}).items():
                    if _opl is not None and getattr(_opl, "player_id", None) == anchor_id:
                        anchor_off_pos = _opos
                        break
                if _subtle_defender_should_freeze(skeleton_step_obj, def_pos, anchor_off_pos):
                    def_coords = dict(def_movement[-1]["coords"])

            # Two-handler pass step (animation-only): the passer owns the START of a pass
            # step and the receiver the END — a single clean handoff. `hasBallAtStep` flips
            # to the receiver instantly, so (via the emitter's end=i+1 read) defenders jump
            # to the post-pass layout a beat EARLY. Hold the defender at his pre-pass
            # (passer-owned) coord for the pass step's start so his rotation to the receiver
            # renders ACROSS the pass step, in unison with the ball. Gameplay-safe: the zone
            # assignment map is stored above at the TRUE (receiver) step, and this never
            # touches the FINAL step's coord (which Player.coords / the attack-drive geometry
            # contest read) — only an intermediate pass-step coord is held.
            if (
                prev_ball_handler_pos
                and current_ball_handler_pos
                and current_ball_handler_pos != prev_ball_handler_pos
                and step_index != max_steps - 1
                and def_movement
            ):
                def_coords = dict(def_movement[-1]["coords"])

            def_end = def_coords

            # Determine action (guard_ball if ball handler in zone, otherwise guard_offball)
            zone_coords = zone_boundaries.get(def_pos, [])
            action = "guard_offball"
            if step_override and step_override.get("action"):
                action = step_override["action"]
            elif ball_handler_coords and _point_in_zone(ball_handler_coords, zone_coords, is_away_offense):
                action = "guard_ball"
            
            def_movement.append({
                "timestamp": timestamp,
                "coords": def_coords,
                "action": action
            })
            prev_ball_handler_pos = current_ball_handler_pos

        if not def_movement:
            continue
        
        # All defenders have ball at no steps (defensive players never have ball)
        has_ball_steps = [False] * len(def_movement)
        duration = def_movement[-1]["timestamp"] if def_movement else 0
        
        defensive_animations.append({
            "playerId": def_player_id,
            "start": def_start or {"x": 50, "y": 25},
            "end": def_end or {"x": 50, "y": 25},
            "movement": def_movement,
            "hasBallAtStep": has_ball_steps,
            "duration": duration
        })
    
    return defensive_animations, zone_assignments


def position_standard_defenders(game, offensive_animations, def_lineup, skeleton_steps):
    """
    Position defensive players for standard HCO scenarios.
    
    Strategy:
    - Each defender guards the offensive player at their position
    - Use standard defensive positioning logic from shared_defense
    - Track offensive players dynamically through the play
    
    Args:
        offensive_animations: Dict mapping position → offensive player animation
        def_lineup: Dict of defensive players by position
        skeleton_steps: List of skeleton steps for timing
        
    Returns:
        List of defensive player animations
    """
    from BackEnd.utils.shared_defense import get_defender_coords
    
    defensive_animations = []
    
    # Determine court orientation
    is_away_offense = game.offense_team.team_id == game.away_team.team_id
    aggression = game.defense_team.strategy_calls.get("aggression_call", "normal")
    
    # Build offensive player positions by step for tracking
    # PHASE 6: get_defender_coords handles coordinate orientation automatically
    # Store coords as-is (away orientation if away offense, home orientation if home offense)
    # The wrapper will handle orientation transformation internally
    offensive_positions_by_step = {}
    for pos, off_anim in offensive_animations.items():
        offensive_positions_by_step[pos] = []
        for step in off_anim.get("movement", []):
            coords = step.get("coords", {"x": 50, "y": 25})
            offensive_positions_by_step[pos].append(coords)
    
    # Find ball handler position (player with ball at step 0)
    ball_handler_pos = None
    for pos, off_anim in offensive_animations.items():
        if off_anim.get("hasBallAtStep", [False])[0]:  # Has ball at first step
            ball_handler_pos = pos
            break
    
    if not ball_handler_pos:
        # Fallback: assume PG is ball handler
        ball_handler_pos = "PG"

    # Dynamic HCO Defense (P1): the turn's team posture (tight/normal/loose), or None when the
    # GOB_DYNAMIC_HCO_DEFENSE flag is off → get_defender_coords falls back to legacy placement.
    posture = (game.game_state or {}).get("_hco_defense_posture")

    # Create defensive animations for each position
    for def_pos in ['PG', 'SG', 'SF', 'PF', 'C']:
        def_player = def_lineup.get(def_pos)
        if not def_player:
            continue
        
        def_player_id = getattr(def_player, "player_id", None)
        if not def_player_id:
            continue
        
        
        # Get the offensive player this defender is guarding
        # ✅ MAN DEFENSE MATCHUPS: Use matchups for the defending team (user vs computer)
        from BackEnd.utils.man_defense_matchups import get_matchups_for_defending_team
        defending_team_is_user = getattr(game.defense_team, "is_user_team", False)
        matchups = get_matchups_for_defending_team(game.game_state, defending_team_is_user)
        off_pos_to_guard = matchups.get(def_pos, def_pos)  # Default: position-on-position
        # If no custom matchup, off_pos_to_guard remains def_pos (position-on-position)
        
        off_coords_list = offensive_positions_by_step.get(off_pos_to_guard, [])
        
        def_movement = []
        def_start = None
        def_end = None
        
        # Step 0: Initial defensive position
        if off_coords_list:
            off_coords = off_coords_list[0]
            
            step0_skeleton = skeleton_steps[0] if skeleton_steps else {}
            override0 = _attack_drive_defender_override(step0_skeleton, def_pos)
            if override0 and override0.get("coords"):
                def_coords = dict(override0["coords"])
                def_action = override0.get("action") or "guard_offball"
            elif off_pos_to_guard == ball_handler_pos:
                # Ball handler defender - extract ball handler's spot from first skeleton step
                first_step = skeleton_steps[0] if skeleton_steps else {}
                bh_action = first_step.get("pos_actions", {}).get(ball_handler_pos, {})
                bh_spot = bh_action.get("location") or bh_action.get("spot") or "key"
                
                # PHASE 3: Use new unified defender coordinate system
                # get_defender_coords handles coordinate orientation automatically
                def_coords = get_defender_coords(
                    off_coords,
                    is_away_offense,
                    aggression,
                    bh_spot,
                    None,
                    is_ball_handler=True,
                    posture=posture,
                )
            else:
                # Non-ball handler defender
                bh_coords = offensive_positions_by_step.get(ball_handler_pos, [{}])[0] if ball_handler_pos in offensive_positions_by_step else {"x": 50, "y": 25}
                
                # Extract spots from first skeleton step
                first_step = skeleton_steps[0] if skeleton_steps else {}
                bh_action = first_step.get("pos_actions", {}).get(ball_handler_pos, {})
                bh_spot = bh_action.get("location") or bh_action.get("spot") or "key"
                
                o_action = first_step.get("pos_actions", {}).get(off_pos_to_guard, {})
                o_spot = o_action.get("location") or o_action.get("spot") or "key"
                
                # PHASE 4: Use new unified defender coordinate system
                # get_defender_coords handles coordinate orientation automatically
                # Pass ball_spot for non-BH defenders (required for complex positioning logic)
                def_coords = get_defender_coords(
                    off_coords,
                    is_away_offense,
                    aggression,
                    o_spot,
                    bh_coords,
                    is_ball_handler=False,
                    ball_spot=bh_spot,  # Pass ball handler's spot for non-BH defender logic
                    posture=posture,
                )

            # get_defender_coords returns coords in same orientation as input
            # No need to flip - wrapper handles orientation automatically
            
            def_start = def_coords
            def_movement.append({
                "timestamp": 0,
                "coords": def_coords,
                "action": (
                    def_action
                    if override0 and override0.get("coords")
                    else (
                        "guard_ball"
                        if off_pos_to_guard == ball_handler_pos
                        else "guard_offball"
                    )
                ),
            })
        
        # Step 0's ball handler is the initial ball_handler_pos; track it so the loop can
        # detect a pass (ownership flip) and hold the defender through the pass step.
        prev_ball_handler_pos = ball_handler_pos

        # Subsequent steps: Track offensive player
        for step_idx, skeleton_step in enumerate(skeleton_steps[1:], start=1):
            timestamp = skeleton_step.get("timestamp", step_idx * 800)
            
            if step_idx < len(off_coords_list):
                off_coords = off_coords_list[step_idx]
                
                # Dynamically determine who has ball at THIS step
                current_ball_handler_pos = None
                for pos, off_anim in offensive_animations.items():
                    if off_anim.get("hasBallAtStep", [])[step_idx] if step_idx < len(off_anim.get("hasBallAtStep", [])) else False:
                        current_ball_handler_pos = pos
                        break
                
                # If no one has ball at this step, use previous ball handler
                if not current_ball_handler_pos:
                    current_ball_handler_pos = ball_handler_pos

                override = _attack_drive_defender_override(skeleton_step, def_pos)
                if override and override.get("coords"):
                    def_coords = dict(override["coords"])
                    def_action = override.get("action") or "guard_offball"
                elif off_pos_to_guard == current_ball_handler_pos:
                    # Ball handler defender - extract CURRENT ball handler's spot from skeleton step
                    bh_action = skeleton_step.get("pos_actions", {}).get(current_ball_handler_pos, {})
                    bh_spot = bh_action.get("location") or bh_action.get("spot") or "key"
                    
                    # PHASE 3: Use new unified defender coordinate system
                    # get_defender_coords handles coordinate orientation automatically
                    def_coords = get_defender_coords(
                        off_coords,
                        is_away_offense,
                        aggression,
                        bh_spot,
                        None,
                        is_ball_handler=True,
                        posture=posture,
                    )
                else:
                    # Non-ball handler defender - need CURRENT ball handler position for this step
                    bh_coords_list = offensive_positions_by_step.get(current_ball_handler_pos, [])
                    bh_coords = bh_coords_list[step_idx] if step_idx < len(bh_coords_list) else {"x": 50, "y": 25}
                    
                    # Extract spots from current skeleton step using CURRENT ball handler
                    bh_action = skeleton_step.get("pos_actions", {}).get(current_ball_handler_pos, {})
                    bh_spot = bh_action.get("location") or bh_action.get("spot") or "key"
                    
                    o_action = skeleton_step.get("pos_actions", {}).get(off_pos_to_guard, {})
                    o_spot = o_action.get("location") or o_action.get("spot") or "key"
                    
                    # PHASE 4: Use new unified defender coordinate system
                    # get_defender_coords handles coordinate orientation automatically
                    # Pass ball_spot for non-BH defenders (required for complex positioning logic)
                    def_coords = get_defender_coords(
                        off_coords,
                        is_away_offense,
                        aggression,
                        o_spot,
                        bh_coords,
                        is_ball_handler=False,
                        ball_spot=bh_spot,  # Pass ball handler's spot for non-BH defender logic
                        posture=posture,
                    )
                # For BH defenders, get_defender_coords already returns correct orientation

                # Dynamic HCO Defense — S1 Part B: a beaten defender LAGS toward his man instead
                # of fully tracking, opening the gap the offense reads (the openness primitive).
                # Lag is graded by how badly he lost his read (_defender_reads margin, Part A);
                # legacy SM beats + flag-off keep EXACT behavior via _defender_lag_fraction's
                # fallback. Skipped on attack-drive-override steps (drive beats are S2; S1 is
                # positional-only) and when his man didn't move (nothing to open).
                _drive_override = bool(override and override.get("coords"))
                if def_movement and not _drive_override:
                    _prior = def_movement[-1]["coords"]
                    _man_prev = off_coords_list[step_idx - 1] if step_idx >= 1 else off_coords
                    _moved = (
                        (float(off_coords["x"]) - float(_man_prev["x"])) ** 2
                        + (float(off_coords["y"]) - float(_man_prev["y"])) ** 2
                    ) ** 0.5 > OPENNESS_ANCHOR_MOVE_EPS
                    _frac = _defender_lag_fraction(skeleton_step, def_pos, off_pos_to_guard, _moved)
                    if _frac < 1.0:
                        def_coords = {
                            "x": int(round(float(_prior["x"]) + (float(def_coords["x"]) - float(_prior["x"])) * _frac)),
                            "y": int(round(float(_prior["y"]) + (float(def_coords["y"]) - float(_prior["y"])) * _frac)),
                        }

                # Two-handler pass step (animation-only): hold the defender at his pre-pass
                # (passer-owned) coord for the pass step's start so his rotation renders
                # ACROSS the pass step, in unison with the ball — not a beat early. Man
                # defense stores no gameplay assignment map, and this never touches the
                # FINAL step's coord (read by Player.coords / the geometry contest).
                if (
                    prev_ball_handler_pos
                    and current_ball_handler_pos
                    and current_ball_handler_pos != prev_ball_handler_pos
                    and step_idx != len(skeleton_steps) - 1
                    and def_movement
                ):
                    def_coords = dict(def_movement[-1]["coords"])

                def_end = def_coords
                def_movement.append({
                    "timestamp": timestamp,
                    "coords": def_coords,
                    "action": (
                        def_action
                        if override and override.get("coords")
                        else (
                            "guard_ball"
                            if off_pos_to_guard == current_ball_handler_pos
                            else "guard_offball"
                        )
                    ),
                })
                prev_ball_handler_pos = current_ball_handler_pos
            else:
                # No more offensive movement - stay at last position
                if def_movement:
                    last_coords = def_movement[-1]["coords"]
                    def_movement.append({
                        "timestamp": timestamp,
                        "coords": last_coords,
                        "action": "guard_offball"
                    })
        
        if not def_movement:
            continue
        
        # All defenders have ball at no steps
        has_ball_steps = [False] * len(def_movement)
        duration = def_movement[-1]["timestamp"] if def_movement else 0
        
        defensive_animations.append({
            "playerId": def_player_id,
            "start": def_start or {"x": 50, "y": 25},
            "end": def_end or {"x": 50, "y": 25},
            "movement": def_movement,
            "hasBallAtStep": has_ball_steps,
            "duration": duration
        })
        
    
    return defensive_animations


def defender_grid_from_animations(anims, def_lineup, num_steps):
    """Extract ``{step_idx: {def_pos: {x, y}}}`` from a per-player ``animations`` list (the
    movement[i].coords of each defender). Shared by ``compute_defender_grid`` (its own draw) and
    ``build_step_states`` (the emitter's actual draw, Option A) so both read the grid identically.
    """
    move_by_pid = {a.get("playerId"): (a.get("movement") or [])
                   for a in (anims or []) if a.get("playerId")}
    pid_by_dpos = {dp: getattr(p, "player_id", None) for dp, p in (def_lineup or {}).items()}
    grid = {}
    for i in range(num_steps):
        row = {}
        for dpos, pid in pid_by_dpos.items():
            if not pid:
                continue
            mv = move_by_pid.get(pid) or []
            c = (mv[i] or {}).get("coords") if i < len(mv) else None
            if isinstance(c, dict) and "x" in c and "y" in c:
                row[dpos] = {"x": float(c["x"]), "y": float(c["y"])}
        grid[i] = row
    return grid
