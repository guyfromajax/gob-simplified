"""StepState — Dynamic HCO turn engine, per-step state producer.

Governing law (see _documentation_master/projects/StepState.md):
    resolve once → freeze into StepState → project to the emitter → draw.

**Stage 1 (extract, not replicate):** `StepState.defense` is the **rendered** defender grid — the
exact coords `skeleton_to_animations` produces and the emitter serializes (ground truth = what the
player sees). We *extract* that value rather than reconstructing it, so there is no lookalike to
drift from it. The contest will be routed to read this (replacing `_hco_step_def_xy`), making
contest == render by construction.

Still **additive** here: no consumer reads `StepState.defense` yet (zero behavior change). A
diagnostic logs the OLD contest reconstruction (`_hco_step_def_xy`) vs this canonical grid — the
per-step, per-defender gap that routing the contest to StepState will close. Wrapped so it can never
break a turn.
"""

import logging


def _render_defender_grid(skeleton, game, off_lineup, def_lineup):
    """Extract the RENDERED per-step defender grid (the coords the emitter serializes). Returns
    ``{step_index: {def_pos: {x, y}}}``. Defenders get a coord every step, so ``movement[i]`` aligns
    with skeleton step ``i``. This is the canonical grid — the render is ground truth."""
    from BackEnd.models.animator import Animator

    anims = Animator(game).skeleton_to_animations(
        skeleton, off_lineup, def_lineup, add_defenders=True, is_fcp=False, is_hct=False)
    move_by_pid = {
        a.get("playerId"): (a.get("movement") or [])
        for a in (anims or []) if a.get("playerId")
    }
    pid_by_dpos = {dp: getattr(p, "player_id", None) for dp, p in def_lineup.items()}

    steps = (skeleton or {}).get("steps") or []
    grid = {}
    for i in range(len(steps)):
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


def build_step_states(result, game):
    """Compute + stamp per-step ``StepState`` for a resolved HCO turn. Stage 1: ``defense`` = the
    rendered defender grid (canonical). Additive — no behavior change."""
    from BackEnd.engine.phase_resolution import _dynamic_hco_defense_enabled
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
    zone = is_zone_defense(game_state.get("defense_playcall"))
    posture = game_state.get("_hco_defense_posture")
    off_to_def = {}
    if not zone:
        matchups = get_matchups_for_defending_team(
            game_state, getattr(def_team, "is_user_team", False))
        off_to_def = {o: d for d, o in matchups.items()}

    try:
        render_grid = _render_defender_grid(skeleton, game, off_lineup, def_lineup)
    except Exception:
        render_grid = {}

    step_states = []
    stamped = 0
    for i, step in enumerate(steps):
        defense = render_grid.get(i) or {}
        if defense:
            stamped += 1
        step_state = {"index": i, "defense": defense}
        step["_step_state"] = step_state
        step_states.append(step_state)

    logging.warning(
        "🔬 [STEPSTATE] stamped defense grid on %d/%d steps (posture=%s zone=%s) [is_full_sim=%s]",
        stamped, len(steps), posture, zone, game_state.get("_is_full_simulation"))

    # Diagnostic — OLD contest reconstruction (`_hco_step_def_xy`) vs the canonical (render) grid:
    # the per-step gap that routing the contest to StepState will close. Live game only (the contest
    # reconstruction is cheap, but keep noise down). Wrapped.
    if not game_state.get("_is_full_simulation"):
        try:
            _diagnose_contest_gap(step_states, steps, game, off_lineup, def_lineup,
                                  off_to_def, zone, posture)
        except Exception:
            pass
    return step_states


def _step_kind(step):
    """Bucket a skeleton step for gap attribution."""
    if (step or {}).get("_subtle_movement"):
        return "subtle"
    if (step or {}).get("_attack_drive"):
        return "drive"
    pa = (step or {}).get("pos_actions") or {}
    if any(((a or {}).get("action") or "").lower() in ("pass", "receive") for a in pa.values()):
        return "pass"
    return "plain"


def _diagnose_contest_gap(step_states, steps, game, off_lineup, def_lineup, off_to_def, zone, posture):
    """Diff the OLD contest reconstruction (`_hco_step_def_xy`) against the canonical StepState.defense
    (the rendered grid), per step + per defender — the gap Stage 1 closes. Bucketed by step kind.
    Pure observability."""
    from BackEnd.engine.phase_resolution import _hco_step_def_xy, _motion_bh_at_step

    game_state = game.game_state
    is_away_offense = game.offense_team.team_id == game.away_team.team_id
    def_aggr = (getattr(game.defense_team, "strategy_calls", {}) or {}).get("aggression_call", "normal")
    defense_playcall = game_state.get("defense_playcall")
    EPS = 1.5  # grid units

    samples = divergent = 0
    max_delta = 0.0
    worst = None
    by_kind = {"subtle": 0, "drive": 0, "pass": 0, "plain": 0}
    for i, ss in enumerate(step_states):
        canonical = ss.get("defense") or {}
        if not canonical:
            continue
        step = steps[i]
        kind = _step_kind(step)
        try:
            bh_pos, _ = _motion_bh_at_step(step)
            def_xy, _c, _l, _pt = _hco_step_def_xy(
                step, bh_pos, off_lineup, def_lineup, off_to_def, is_away_offense,
                def_aggr, zone, defense_playcall, posture=posture)
        except Exception:
            continue
        for dpos, can in canonical.items():
            cont = (def_xy or {}).get(dpos)
            if not isinstance(cont, dict) or "x" not in cont:
                continue
            samples += 1
            d = ((float(cont["x"]) - float(can["x"])) ** 2
                 + (float(cont["y"]) - float(can["y"])) ** 2) ** 0.5
            if d > EPS:
                divergent += 1
                by_kind[kind] = by_kind.get(kind, 0) + 1
                if d > max_delta:
                    max_delta, worst = d, (i, dpos, kind, cont, can)
    if not samples:
        return
    _w = (f" | worst: step {worst[0]} {worst[1]}({worst[2]}) contest={worst[3]} canonical={worst[4]}"
          if worst else "")
    _bk = " ".join(f"{k}={v}" for k, v in by_kind.items() if v)
    logging.warning(
        "🔬 [STEPSTATE GAP] contest-vs-canonical: %d/%d divergent (%.0f%%) max_delta=%.1f zone=%s | "
        "by-kind: %s%s [is_full_sim=%s]",
        divergent, samples, 100.0 * divergent / samples, max_delta, zone, _bk or "-", _w,
        game_state.get("_is_full_simulation"))
