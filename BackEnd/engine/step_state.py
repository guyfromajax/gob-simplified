"""StepState — Dynamic HCO turn engine, per-step state producer.

Governing law (see _documentation_master/projects/StepState.md):
    resolve once → freeze into StepState → project to the emitter → draw.

**Option A — share the emitter's one draw.** Defender placement uses RNG (a ~2px shade), so two
*separate* draws never agree. `StepState.defense` therefore comes from the ONE draw that reached the
screen: the HCO emit stashes its exact per-player `animations` on the game, and this module extracts
the defender grid from those (`Animator.defender_grid_from_animations`). Contest == render by
construction — not by faithful re-computation. Sims never stash (no render) → fall back to
`Animator.compute_defender_grid`'s own single draw (nothing to match; just self-consistent).

Still **additive**: no consumer reads `StepState.defense` yet (zero behavior change). Two
diagnostics: REDRAW-SPREAD (canonical vs a fresh redraw — the RNG disagreement Option A eliminates,
should be small) and GAP (canonical vs the OLD `_hco_step_def_xy` contest — the divergence Stage 1
closes). Wrapped so it can never break a turn.
"""

import logging


def build_step_states(result, game):
    """Compute + stamp per-step ``StepState`` for a resolved HCO turn. ``defense`` = the render's
    exact defender grid via ``Animator.compute_defender_grid`` (man + zone, sim-safe). Additive."""
    from BackEnd.engine.phase_resolution import _dynamic_hco_defense_enabled
    from BackEnd.utils.defense_utils import is_zone_defense
    from BackEnd.utils.man_defense_matchups import get_matchups_for_defending_team
    from BackEnd.models.animator import Animator

    if not _dynamic_hco_defense_enabled():
        return []
    game_state = game.game_state
    skeleton = (result or {}).get("skeleton") or {}
    steps = skeleton.get("steps") or []
    if not steps:
        return []

    off_lineup = game.offense_team.lineup
    def_lineup = game.defense_team.lineup
    zone = is_zone_defense(game_state.get("defense_playcall"))
    posture = game_state.get("_hco_defense_posture")

    # Option A: prefer the emitter's ACTUAL draw. build_step_states runs right after the HCO emit,
    # which stashed the exact per-player ``animations`` it drew from on the game. Extract the grid
    # from THOSE so the contest judges against what reached the screen (defender placement is RNG, so
    # a separate draw would disagree by ~2px). Sims never stash (no render) → fall back to
    # compute_defender_grid's own single draw. The stash is transient; clear it after reading.
    render_anims = getattr(game, "_hco_render_animations", None)
    try:
        setattr(game, "_hco_render_animations", None)
    except Exception:
        pass
    # PERF: the compute_defender_grid fallback is a FULL animation build (deepcopy +
    # offense walk + defender placement) and was ~33% of all defender-grid builds in a
    # sim. It is dead work there: build_step_states runs LAST in
    # resolve_half_court_offense — after resolve_half_court_offense_logic (where the
    # interception contest reads `_step_state["defense"]`, stamped by
    # _stamp_contest_defender_grid) and after the emit. Its return value is discarded
    # at the call site, and sims drop turns wholesale
    # (summarize_game_state(exclude_animations=True)).
    #
    # Proven, not assumed: a poison-stash run kept the rebuild executing (identical RNG
    # draw count) but stashed {x:-9999,y:-9999} for every defender. The seeded 63 CPU +
    # 20 PS week came back byte-identical, so nothing reads this grid in a full sim. An
    # exact diff alone cannot establish that — removing the rebuild removes draws from
    # the sim stream, which shifts every downstream result by construction.
    #
    # Animated games are untouched: they take the render-stash branch above, which never
    # called compute_defender_grid.
    is_full_sim = bool(game_state.get("_is_full_simulation"))
    anim_source = ("emitter-draw" if render_anims
                   else ("stamp-reuse-full-sim" if is_full_sim else "compute_grid-fallback"))
    try:
        if render_anims:
            grid_by_step = Animator.defender_grid_from_animations(render_anims, def_lineup, len(steps))
        elif is_full_sim:
            # Reuse the grid _stamp_contest_defender_grid already placed on these steps
            # rather than rebuilding it — and rather than blanking it, since a later turn
            # could still read a prior turn's stamp.
            #
            # ⚠️ SEMANTIC NOTE for whoever adds the first consumer of StepState.defense:
            # on the sim path this records STAMP-TIME geometry, not the post-emit rebuild
            # it used to record. Per step that is the most recent
            # _stamp_contest_defender_grid to touch it — the coverage-pass stamp
            # (phase_resolution.py:5675) where it ran, else the pre-walk stamp (:6242).
            # Steps created AFTER the last stamp (shot-clock recalibration, intra-
            # resolution expansion) carry {} where the old rebuild produced coordinates.
            # Deliberate: stamp-time geometry is what the interception contest actually
            # judged against, i.e. the state that decided the turn. The post-emit rebuild
            # was a fourth snapshot no decision was ever made on.
            grid_by_step = {
                i: ((step.get("_step_state") or {}).get("defense") or {})
                for i, step in enumerate(steps)
            }
        else:
            grid_by_step = Animator(game).compute_defender_grid(skeleton, off_lineup, def_lineup)
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
        "🔬 [STEPSTATE] stamped defense grid on %d/%d steps (posture=%s zone=%s src=%s) [is_full_sim=%s]",
        stamped, len(steps), posture, zone, anim_source, game_state.get("_is_full_simulation"))

    if not game_state.get("_is_full_simulation"):
        matchups = {}
        if not zone:
            matchups = get_matchups_for_defending_team(
                game_state, getattr(game.defense_team, "is_user_team", False))
        try:
            _diagnose(step_states, steps, game, off_lineup, def_lineup, matchups, zone, posture)
        except Exception:
            pass
    return step_states


def _render_grids(skeleton, game, off_lineup, def_lineup):
    """Actual RENDERED per-step grids (`skeleton_to_animations`) — returns (def_grid, off_grid),
    each ``{step_idx: {pos: {x,y}}}``. Ground truth for animated games; ``({}, {})`` for sims. Used
    only to VERIFY `compute_defender_grid` (should be identical — same code, different entry)."""
    import copy
    from BackEnd.models.animator import Animator
    # deep-copy: skeleton_to_animations mutates the skeleton in place (BH coord nudge, coord-flip);
    # the shared object was already drawn by compute_defender_grid + the emitter, so draw on a copy
    # to compare like-for-like (else the second draw sees the first's mutations and falsely diverges).
    anims = Animator(game).skeleton_to_animations(
        copy.deepcopy(skeleton), off_lineup, def_lineup, add_defenders=True, is_fcp=False, is_hct=False)
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
    """Compare two {step: {pos: {x,y}}} grids over the stamped defenders."""
    samples = divergent = 0
    max_delta = 0.0
    worst = None
    by_kind = {"subtle": 0, "drive": 0, "pass": 0, "plain": 0}
    for i, ss in enumerate(step_states):
        a = a_by_step.get(i) or {}
        b = b_by_step.get(i) or {}
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
    """(1) FIDELITY — canonical (compute_defender_grid) vs the actual render (skeleton_to_animations);
    should be ~0 (same code). (2) GAP — canonical vs the OLD `_hco_step_def_xy` contest; the
    divergence Stage 1 closes. Pure observability, live game only."""
    from BackEnd.engine.phase_resolution import _hco_step_def_xy, _motion_bh_at_step

    canonical = {i: (ss.get("defense") or {}) for i, ss in enumerate(step_states)}

    # (1) REDRAW-SPREAD — Option A makes ``canonical`` the emitter's ACTUAL draw, so it equals the
    # render by construction. This compares it against a FRESH redraw of the same code: because
    # defender placement is RNG (a ~2px shade), any nonzero here is exactly the disagreement Option A
    # eliminates by sharing one draw. It should be SMALL (RNG jitter), and it's the reason the contest
    # must NOT recompute. (Not a fidelity defect.)
    try:
        render_def, _off = _render_grids({"steps": steps}, game, off_lineup, def_lineup)
    except Exception:
        render_def = {}
    if render_def:
        dv, sm, mx, w, _bk = _grid_diff(canonical, render_def, step_states, steps)
        if sm:
            _w = f" | worst step {w[0]} {w[1]}({w[2]}) canonical={w[3]} redraw={w[4]}" if w else ""
            logging.warning(
                "🔬 [STEPSTATE REDRAW-SPREAD] canonical-vs-fresh-redraw (RNG, eliminated by Option A): "
                "%d/%d divergent (%.0f%%) max=%.1f zone=%s%s [is_full_sim=%s]",
                dv, sm, 100.0 * dv / sm, mx, zone, _w,
                game.game_state.get("_is_full_simulation"))

    # (2) gap vs old contest reconstruction
    is_away = game.offense_team.team_id == game.away_team.team_id
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
