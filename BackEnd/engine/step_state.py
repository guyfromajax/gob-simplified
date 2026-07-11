"""StepState (Stage 0) — Dynamic HCO turn engine, per-step state producer.

Governing law (see _documentation_master/projects/StepState.md):
    resolve once → freeze into StepState → project to the emitter → draw.

Stage 0 is **additive only**: it computes the per-step ``StepState`` and stamps it on the resolved
skeleton steps as ``step["_step_state"]``, but **no consumer reads it yet** (zero behavior change).
It currently populates the DEFENDER GRID (``defense``) — the highest divergence-risk field, since
today the contest (``_hco_step_def_xy``) and the render (``skeleton_to_animations`` →
``get_defender_coords``) reconstruct defender positions *independently* and can disagree.

Later Stage 0 increments extend the shape (ball trajectory, timing, advance-gate) and add the
contest-vs-render parity diff; Stage 1/2 rewire consumers to READ this instead of re-deriving.
Must never mutate a game outcome — the caller wraps it defensively.
"""

import logging


def build_step_states(result, game):
    """Compute + stamp per-step ``StepState`` for a resolved HCO turn.

    Returns the list of StepState dicts (also stamped on each skeleton step as ``_step_state``).
    Stage 0: ``defense`` grid only, computed ONCE via the engine-side reconstruction
    (``_hco_step_def_xy``). Additive — no behavior change.
    """
    from BackEnd.engine.phase_resolution import (
        _dynamic_hco_defense_enabled,
        _hco_step_def_xy,
        _motion_bh_at_step,
    )
    from BackEnd.utils.defense_utils import is_zone_defense
    from BackEnd.utils.man_defense_matchups import get_matchups_for_defending_team

    if not _dynamic_hco_defense_enabled():
        return []
    game_state = game.game_state
    skeleton = (result or {}).get("skeleton") or {}
    steps = skeleton.get("steps") or []
    if not steps:
        return []

    off_team = game.offense_team
    def_team = game.defense_team
    off_lineup = off_team.lineup
    def_lineup = def_team.lineup
    is_away_offense = off_team.team_id == game.away_team.team_id
    zone = is_zone_defense(game_state.get("defense_playcall"))
    def_aggr = (getattr(def_team, "strategy_calls", {}) or {}).get("aggression_call", "normal")
    posture = game_state.get("_hco_defense_posture")
    defense_playcall = game_state.get("defense_playcall")
    off_to_def = {}
    if not zone:
        matchups = get_matchups_for_defending_team(
            game_state, getattr(def_team, "is_user_team", False))
        off_to_def = {o: d for d, o in matchups.items()}

    step_states = []
    stamped = 0
    for i, step in enumerate(steps):
        try:
            bh_pos, _bh_loc = _motion_bh_at_step(step)
            def_xy, _coord, _loc, _pt = _hco_step_def_xy(
                step, bh_pos, off_lineup, def_lineup, off_to_def, is_away_offense,
                def_aggr, zone, defense_playcall, posture=posture)
            defense = {
                dpos: {"x": float(xy["x"]), "y": float(xy["y"])}
                for dpos, xy in (def_xy or {}).items()
                if isinstance(xy, dict) and "x" in xy and "y" in xy
            }
            if defense:
                stamped += 1
        except Exception:
            defense = {}
        step_state = {"index": i, "defense": defense}
        step["_step_state"] = step_state
        step_states.append(step_state)

    logging.warning(
        "🔬 [STEPSTATE] stamped defense grid on %d/%d steps (posture=%s zone=%s) [is_full_sim=%s]",
        stamped, len(steps), posture, zone, game_state.get("_is_full_simulation"))
    return step_states
