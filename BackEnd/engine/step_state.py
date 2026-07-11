"""StepState — Dynamic HCO turn engine, per-step state producer.

Governing law (see _documentation_master/projects/StepState.md):
    resolve once → freeze into StepState → project to the emitter → draw.

**Stage 1 — the pure defender-grid primitive.** `StepState.defense` is computed by
`_compute_man_defender_grid`, a **pure** (animation-free) replication of the render's man defender
placement (`animator._position_standard_defenders`). It runs identically for animated *and* sim'd
games — required because an interception is an OUTCOME and must not depend on whether a game is
drawn. Both the contest and the render will be routed to it, making contest == render by
construction.

Still **additive**: no consumer reads `StepState.defense` yet (zero behavior change). Two
diagnostics log the primitive's fidelity vs the actual render, and the gap vs the old contest
reconstruction. Wrapped so it can never break a turn. (Zone still uses the render grid pending its
own extract.)
"""

import logging

_OFF = ["PG", "SG", "SF", "PF", "C"]
_BALL_ACTIONS = {"handle_ball", "receive", "shoot", "drive"}


def _off_coord(step, pos, is_away_offense):
    """Offense display coord for a position at a step — mirrors the animator's offense build:
    explicit ``coords`` as-is (already display), else spot → HCO_STRING_SPOTS, flipped for away."""
    from BackEnd.constants import HCO_STRING_SPOTS
    from BackEnd.utils.shared import get_away_player_coords
    pa = (step.get("pos_actions") or {}).get(pos) or {}
    if pa.get("coords"):
        return {"x": float(pa["coords"]["x"]), "y": float(pa["coords"]["y"])}
    loc = pa.get("location") or pa.get("spot") or "key"
    c = HCO_STRING_SPOTS.get(loc, {"x": 50, "y": 25})
    c = {"x": float(c["x"]), "y": float(c["y"])}
    return get_away_player_coords(c) if is_away_offense else c


def _bh_at_step(step):
    """Ball handler at a step by the render's rule: first offense pos whose action is a ball action
    (handle_ball / receive / shoot / drive) — the `hasBallAtStep` rule. None if nobody holds."""
    pa = step.get("pos_actions") or {}
    for p in _OFF:
        if ((pa.get(p) or {}).get("action") or "").lower() in _BALL_ACTIONS:
            return p
    return None


def _spot_of(step, pos):
    a = (step.get("pos_actions") or {}).get(pos) or {}
    return a.get("location") or a.get("spot") or "key"


def _compute_man_defender_grid(skeleton_steps, off_lineup, def_lineup, matchups,
                               is_away_offense, aggression, posture):
    """PURE man defender grid — faithful animation-free copy of `_position_standard_defenders`.
    Returns ``{def_pos: {step_idx: {x, y}}}``. Base grid only (no override / subtle-freeze /
    pass-hold — those are render cosmetics layered on top, and don't affect the interception).
    Offense coords from `pos_actions`; BH per step via `hasBallAtStep` rule with a step-0 fallback."""
    from BackEnd.utils.shared_defense import get_defender_coords

    step0_bh = _bh_at_step(skeleton_steps[0]) if skeleton_steps else None
    step0_bh = step0_bh or "PG"

    grid = {}
    for def_pos in _OFF:
        if not def_lineup.get(def_pos):
            continue
        off_to_guard = matchups.get(def_pos, def_pos)
        per_step = {}
        for i, step in enumerate(skeleton_steps):
            if off_to_guard not in (step.get("pos_actions") or {}):
                continue
            off_c = _off_coord(step, off_to_guard, is_away_offense)
            cur_bh = _bh_at_step(step) or step0_bh
            if off_to_guard == cur_bh:
                dc = get_defender_coords(
                    off_c, is_away_offense, aggression, _spot_of(step, cur_bh),
                    None, is_ball_handler=True, posture=posture)
            else:
                bh_c = (_off_coord(step, cur_bh, is_away_offense)
                        if cur_bh in (step.get("pos_actions") or {}) else {"x": 50, "y": 25})
                dc = get_defender_coords(
                    off_c, is_away_offense, aggression, _spot_of(step, off_to_guard),
                    bh_c, is_ball_handler=False, ball_spot=_spot_of(step, cur_bh), posture=posture)
            if isinstance(dc, dict) and "x" in dc:
                per_step[i] = {"x": float(dc["x"]), "y": float(dc["y"])}
        grid[def_pos] = per_step
    return grid


def _render_grids(skeleton, game, off_lineup, def_lineup):
    """Actual RENDERED per-step grids (`skeleton_to_animations`) — returns (def_grid, off_grid),
    each ``{step_idx: {pos: {x,y}}}``. Ground truth for animated games; ``({}, {})`` for sims.
    Used only to VERIFY the pure primitive."""
    from BackEnd.models.animator import Animator
    anims = Animator(game).skeleton_to_animations(
        skeleton, off_lineup, def_lineup, add_defenders=True, is_fcp=False, is_hct=False)
    move_by_pid = {a.get("playerId"): (a.get("movement") or [])
                   for a in (anims or []) if a.get("playerId")}
    steps = (skeleton or {}).get("steps") or []

    def _grid(lineup):
        pid_by_pos = {p: getattr(pl, "player_id", None) for p, pl in lineup.items()}
        g = {}
        for i in range(len(steps)):
            row = {}
            for pos, pid in pid_by_pos.items():
                if not pid:
                    continue
                mv = move_by_pid.get(pid) or []
                c = (mv[i] or {}).get("coords") if i < len(mv) else None
                if isinstance(c, dict) and "x" in c and "y" in c:
                    row[pos] = {"x": float(c["x"]), "y": float(c["y"])}
            g[i] = row
        return g
    return _grid(def_lineup), _grid(off_lineup)


def build_step_states(result, game):
    """Compute + stamp per-step ``StepState`` for a resolved HCO turn. Stage 1: ``defense`` = the
    pure man primitive (zone: render grid, pending its extract). Additive — no behavior change."""
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

    off_lineup = game.offense_team.lineup
    def_lineup = game.defense_team.lineup
    is_away_offense = game.offense_team.team_id == game.away_team.team_id
    zone = is_zone_defense(game_state.get("defense_playcall"))
    aggression = (getattr(game.defense_team, "strategy_calls", {}) or {}).get("aggression_call", "normal")
    posture = game_state.get("_hco_defense_posture")
    matchups = {}
    if not zone:
        matchups = get_matchups_for_defending_team(
            game_state, getattr(game.defense_team, "is_user_team", False))

    # Canonical grid: pure primitive for man; render grid for zone (extract pending).
    grid_by_step = {}
    try:
        if zone:
            grid_by_step = _render_grids(skeleton, game, off_lineup, def_lineup)[0]
        else:
            man = _compute_man_defender_grid(steps, off_lineup, def_lineup, matchups,
                                             is_away_offense, aggression, posture)
            grid_by_step = {i: {dp: man[dp][i] for dp in man if i in man[dp]}
                            for i in range(len(steps))}
    except Exception:
        grid_by_step = {}

    step_states = []
    stamped = 0
    for i, step in enumerate(steps):
        defense = grid_by_step.get(i) or {}
        if defense:
            stamped += 1
        step_state = {"index": i, "defense": defense}
        step["_step_state"] = step_state
        step_states.append(step_state)

    logging.warning(
        "🔬 [STEPSTATE] stamped defense grid on %d/%d steps (posture=%s zone=%s) [is_full_sim=%s]",
        stamped, len(steps), posture, zone, game_state.get("_is_full_simulation"))

    if not game_state.get("_is_full_simulation"):
        try:
            _diagnose(step_states, steps, game, off_lineup, def_lineup, matchups, zone, posture)
        except Exception:
            pass
    return step_states


def _step_kind(step):
    if (step or {}).get("_subtle_movement"):
        return "subtle"
    if (step or {}).get("_attack_drive"):
        return "drive"
    pa = (step or {}).get("pos_actions") or {}
    if any(((a or {}).get("action") or "").lower() in ("pass", "receive") for a in pa.values()):
        return "pass"
    return "plain"


def _grid_diff(a_by_step, b_by_step, step_states, steps, EPS=1.5):
    """Compare two {step: {dpos: {x,y}}} grids over the stamped defenders. Returns
    (divergent, samples, max_delta, worst, by_kind)."""
    samples = divergent = 0
    max_delta = 0.0
    worst = None
    by_kind = {"subtle": 0, "drive": 0, "pass": 0, "plain": 0}
    for i, ss in enumerate(step_states):
        a = (a_by_step.get(i) or {})
        b = (b_by_step.get(i) or {})
        kind = _step_kind(steps[i])
        for dpos, av in a.items():
            bv = b.get(dpos)
            if not isinstance(bv, dict) or "x" not in bv:
                continue
            samples += 1
            d = ((float(av["x"]) - float(bv["x"])) ** 2 + (float(av["y"]) - float(bv["y"])) ** 2) ** 0.5
            if d > EPS:
                divergent += 1
                by_kind[kind] = by_kind.get(kind, 0) + 1
                if d > max_delta:
                    max_delta, worst = d, (i, dpos, kind, av, bv)
    return divergent, samples, max_delta, worst, by_kind


def _diagnose(step_states, steps, game, off_lineup, def_lineup, matchups, zone, posture):
    """Two checks (live game only): (1) FIDELITY — pure primitive vs the actual render (should be
    ~0 if faithful); (2) GAP — pure primitive vs the OLD contest reconstruction (`_hco_step_def_xy`),
    the divergence Stage 1 closes. Pure observability."""
    from BackEnd.engine.phase_resolution import _hco_step_def_xy, _motion_bh_at_step

    canonical = {i: (ss.get("defense") or {}) for i, ss in enumerate(step_states)}

    is_away = game.offense_team.team_id == game.away_team.team_id
    def_to_off = {d: o for o, d in matchups.items()}

    # (1) fidelity vs render — plus whether the guarded OFFENSE player's coord also diverges
    # (pos_actions vs the render's animation coord) → tells us offense-coord source vs defender-logic.
    try:
        render_def, render_off = _render_grids({"steps": steps}, game, off_lineup, def_lineup)
    except Exception:
        render_def, render_off = {}, {}
    if render_def:
        dv, sm, mx, w, bk = _grid_diff(canonical, render_def, step_states, steps)
        off_also = 0
        for i, ss in enumerate(step_states):
            can = ss.get("defense") or {}
            rnd = render_def.get(i) or {}
            roff = render_off.get(i) or {}
            for dpos, cv in can.items():
                rv = rnd.get(dpos)
                if not isinstance(rv, dict) or "x" not in rv:
                    continue
                if ((cv["x"] - rv["x"]) ** 2 + (cv["y"] - rv["y"]) ** 2) ** 0.5 <= 1.5:
                    continue
                op = def_to_off.get(dpos, dpos)
                mine = _off_coord(steps[i], op, is_away) if op in (steps[i].get("pos_actions") or {}) else None
                rendv = roff.get(op)
                if isinstance(mine, dict) and isinstance(rendv, dict) and \
                        ((mine["x"] - rendv["x"]) ** 2 + (mine["y"] - rendv["y"]) ** 2) ** 0.5 > 1.5:
                    off_also += 1
        if sm:
            _w = f" | worst step {w[0]} {w[1]}({w[2]}) pure={w[3]} render={w[4]}" if w else ""
            logging.warning(
                "🔬 [STEPSTATE FIDELITY] pure-vs-render: %d/%d divergent (%.0f%%) max=%.1f zone=%s | "
                "off-coord-also-diverged: %d/%d%s [is_full_sim=%s]",
                dv, sm, 100.0 * dv / sm, mx, zone, off_also, dv, _w,
                game.game_state.get("_is_full_simulation"))

    # (2) gap vs old contest reconstruction
    def_aggr = (getattr(game.defense_team, "strategy_calls", {}) or {}).get("aggression_call", "normal")
    playcall = game.game_state.get("defense_playcall")
    off_to_def = {o: d for d, o in matchups.items()} if not zone else {}
    contest = {}
    for i, step in enumerate(steps):
        try:
            bh_pos, _ = _motion_bh_at_step(step)
            def_xy, _c, _l, _pt = _hco_step_def_xy(
                step, bh_pos, off_lineup, def_lineup, off_to_def, is_away,
                def_aggr, zone, playcall, posture=posture)
            contest[i] = {dp: {"x": float(v["x"]), "y": float(v["y"])}
                          for dp, v in (def_xy or {}).items()
                          if isinstance(v, dict) and "x" in v}
        except Exception:
            contest[i] = {}
    dv, sm, mx, w, bk = _grid_diff(canonical, contest, step_states, steps)
    if sm:
        _w = f" | worst step {w[0]} {w[1]}({w[2]}) canonical={w[3]} contest={w[4]}" if w else ""
        _bk = " ".join(f"{k}={v}" for k, v in bk.items() if v)
        logging.warning(
            "🔬 [STEPSTATE GAP] canonical-vs-contest: %d/%d divergent (%.0f%%) max=%.1f zone=%s | "
            "by-kind: %s%s [is_full_sim=%s]", dv, sm, 100.0 * dv / sm, mx, zone, _bk or "-", _w,
            game.game_state.get("_is_full_simulation"))
