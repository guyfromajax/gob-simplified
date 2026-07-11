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

    # Parity diff vs the render grid — live game only (skeleton_to_animations is heavy; skip
    # background sims). Measures the contest-vs-render defender-position disagreement, incl. the
    # known zone/away frame flip. Pure observability; wrapped so it can never break a turn.
    if not game_state.get("_is_full_simulation"):
        try:
            _stepstate_defense_parity(step_states, result, game, zone, off_to_def)
        except Exception:
            pass
    return step_states


def _step_kind(step):
    """Bucket a skeleton step for divergence attribution."""
    if (step or {}).get("_subtle_movement"):
        return "subtle"
    if (step or {}).get("_attack_drive"):
        return "drive"
    pa = (step or {}).get("pos_actions") or {}
    if any(((a or {}).get("action") or "").lower() in ("pass", "receive") for a in pa.values()):
        return "pass"
    return "plain"


def _stepstate_defense_parity(step_states, result, game, zone, off_to_def):
    """Diff the engine defender grid (``StepState.defense`` via ``_hco_step_def_xy``) against the
    RENDER grid (``skeleton_to_animations`` → the coords the emitter serializes), per step + per
    defender. Defenders get a coord every step, so ``movement[i]`` aligns with skeleton step ``i``.

    ATTRIBUTION (to separate real posture-drift from probe-timing / upstream offense-coord drift):
    each divergent sample is bucketed by step kind (subtle / drive / pass / plain), and we check
    whether the defender's GUARDED offense player *also* diverged between contest and render — if so
    the gap is upstream (offense moved differently), not in defender placement itself.

    Zone/away turns diverge by the HOME-vs-display frame flip (StepState.md §canonical-frame) — that's
    signal, not noise."""
    from BackEnd.models.animator import Animator

    skeleton = (result or {}).get("skeleton") or {}
    steps = skeleton.get("steps") or []
    if not steps or not step_states:
        return
    off_lineup = game.offense_team.lineup
    def_lineup = game.defense_team.lineup
    def_to_off = {d: o for o, d in (off_to_def or {}).items()}
    anims = Animator(game).skeleton_to_animations(
        skeleton, off_lineup, def_lineup, add_defenders=True, is_fcp=False, is_hct=False)
    move_by_pid = {
        a.get("playerId"): (a.get("movement") or [])
        for a in (anims or []) if a.get("playerId")
    }

    def _render_coord(pid, i):
        mv = move_by_pid.get(pid) or []
        return (mv[i] or {}).get("coords") if i < len(mv) else None

    def _delta(a, b):
        return ((float(a["x"]) - float(b["x"])) ** 2 + (float(a["y"]) - float(b["y"])) ** 2) ** 0.5

    EPS = 1.5  # grid units
    samples = divergent = off_also = 0
    max_delta = 0.0
    worst = None
    by_kind = {"subtle": 0, "drive": 0, "pass": 0, "plain": 0}
    for i, ss in enumerate(step_states):
        step = steps[i] if i < len(steps) else {}
        kind = _step_kind(step)
        for dpos, eng in (ss.get("defense") or {}).items():
            pid = getattr(def_lineup.get(dpos), "player_id", None)
            rnd = _render_coord(pid, i) if pid else None
            if not isinstance(rnd, dict) or "x" not in rnd:
                continue
            samples += 1
            d = _delta(eng, rnd)
            if d <= EPS:
                continue
            divergent += 1
            by_kind[kind] = by_kind.get(kind, 0) + 1
            # did the guarded offense player also diverge (contest skeleton coord vs render coord)?
            off_pos = def_to_off.get(dpos, dpos)
            off_pid = getattr(off_lineup.get(off_pos), "player_id", None)
            sk_off = ((step.get("pos_actions") or {}).get(off_pos) or {}).get("coords")
            rnd_off = _render_coord(off_pid, i) if off_pid else None
            if isinstance(sk_off, dict) and isinstance(rnd_off, dict) and _delta(sk_off, rnd_off) > EPS:
                off_also += 1
            if d > max_delta:
                max_delta, worst = d, (i, dpos, kind, eng, rnd)
    if not samples:
        return
    _w = (f" | worst: step {worst[0]} {worst[1]}({worst[2]}) eng={worst[3]} rnd={worst[4]}"
          if worst else "")
    _bk = " ".join(f"{k}={v}" for k, v in by_kind.items() if v)
    logging.warning(
        "🔬 [STEPSTATE PARITY] defense: %d/%d divergent (%.0f%%) max_delta=%.1f zone=%s | "
        "by-kind: %s | off-coord-also-diverged: %d/%d%s [is_full_sim=%s]",
        divergent, samples, 100.0 * divergent / samples, max_delta, zone, _bk or "-",
        off_also, divergent, _w, game.game_state.get("_is_full_simulation"))
