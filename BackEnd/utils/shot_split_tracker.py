"""Shot diagnostics tracker (per-game, both teams combined).

Three independent per-game tallies, stored on ``game.game_state`` and rendered
as end-of-game charts:

1. ``shot_split_tracking`` — every field-goal attempt across three binary
   dimensions: 2pt/3pt × defended/undefended × make/miss.

2. ``fga_by_turn_type`` — total field-goal attempts bucketed by the turn
   type that generated them: HCO, HCT, FCP, Fast Break, OREB. (Final Shot /
   FLSS buzzer attempts are intentionally omitted from this breakdown.)

   ``undefended_by_turn_type`` — of those same per-turn-type attempts, the
   make/miss of the ones that were undefended (``not defended``). Same buckets
   and same Final-Shot/FLSS exclusion as ``fga_by_turn_type``.

3. ``hco_shot_tier_counts`` — HCO field-goal attempts by shot-clock tier at
   attempt time. Every HCO FGA via ``record_shot_split`` increments this tally.
   Clock at attempt (in priority order):
   (1) dynamic-walk ``_hco_shot_clock_est`` when stamped;
   (2) ``shot_at_one_second`` → 1s;
   (3) ``shot_clock_remaining − elapsed_to_shot_step`` via
   ``calc_skeleton_step_timing_contract`` (same detach math as ``turn_manager``).

Coverage (all tallies where applicable): HCO, FCP, Final Shot, and regular Fast Break via
``ShotManager.resolve_shot``; Dynamic HCT via ``resolve_hct_fast_break_shot``
+ ``_finalize_ab_shot``; After-Steal Fast Break via
``resolve_after_steal_fast_break``; OREB putbacks via
``resolve_offensive_rebound``. Free throws are not field-goal attempts and
are not counted.

"defended" mirrors the engine's ``has_contest`` / ``contested`` flag
(= ``apply_defense``). Turn type for the shared ``resolve_shot`` path is
classified from ``game_state["offensive_state"]`` (set to the pressure type
at turn start) + the fast-break / final-turn flags.
"""

# --- shot_split_tracking (2/3 × def/undef × make/miss) ---------------------

# Display label → tracking key. Order is the chart's row order.
_ROWS = (
    ("3 pt defended", "3pt_def"),
    ("3 pt undefended", "3pt_undef"),
    ("2 pt defended", "2pt_def"),
    ("2 pt undefended", "2pt_undef"),
)

_KEYS = tuple(key for _label, key in _ROWS)

# --- fga_by_turn_type ------------------------------------------------------

# Turn-type buckets, in report order. Final Shot / FLSS deliberately excluded.
_TURN_TYPES = ("HCO", "HCT", "FCP", "Fast Break", "OREB")


def _empty_tracking():
    return {key: {"make": 0, "miss": 0} for key in _KEYS}


def _empty_fga_by_turn_type():
    return {tt: 0 for tt in _TURN_TYPES}


def _empty_undefended_by_turn_type():
    return {tt: {"make": 0, "miss": 0} for tt in _TURN_TYPES}


def classify_resolve_shot_turn_type(game_state, roles):
    """Classify a ``resolve_shot`` FGA into a turn-type bucket.

    Returns one of HCO / HCT / FCP / "Fast Break", or ``None`` for a Final
    Shot / FLSS attempt (which the turn-type FGA report omits). Relies on
    ``offensive_state`` being the live pressure/state value at shot time
    (set to ``pressure_type`` at turn start, only reassigned after the shot
    resolves).
    """
    gs = game_state if isinstance(game_state, dict) else {}
    rl = roles if isinstance(roles, dict) else {}
    if gs.get("final_turn") or rl.get("final_turn") or rl.get("flss"):
        return None
    if rl.get("is_fast_break") or gs.get("offensive_state") == "FAST_BREAK":
        return "Fast Break"
    state = gs.get("offensive_state")
    if state == "FCP":
        return "FCP"
    if state == "HCT":
        return "HCT"
    return "HCO"


def _is_hco_skeleton_shot(game_state, roles) -> bool:
    """True when roles carry a half-court skeleton shot (not FB/FCP/HCT)."""
    if not isinstance(roles, dict):
        return False
    if roles.get("is_fast_break"):
        return False
    if not roles.get("steps"):
        return False
    gs = (game_state or {}).get("offensive_state")
    if gs in ("FAST_BREAK", "FCP", "HCT"):
        return False
    return True


def _elapsed_seconds_to_shot_step(step_clock_seconds, resolution_step_index) -> int:
    """Mirror ``turn_manager._shot_detach_elapsed_seconds`` (diagnostics only)."""
    if not isinstance(step_clock_seconds, list) or not step_clock_seconds:
        return 0
    try:
        secs = [max(0, int(s or 0)) for s in step_clock_seconds]
    except (TypeError, ValueError):
        return 0
    max_index = len(secs) - 1
    try:
        idx = int(resolution_step_index)
    except (TypeError, ValueError):
        idx = max_index
    idx = max(0, min(max_index, idx))
    return int(sum(secs[: idx + 1]))


def resolve_hco_shot_clock_at_attempt(
    game_state,
    roles,
    *,
    shot_step_index=None,
    off_lineup=None,
) -> float | None:
    """Shot clock (game seconds) at HCO FGA time for tier diagnostics.

    Priority:
    1. ``_hco_shot_clock_est`` from dynamic motion/set-play walk (popped once).
    2. Shot-at-1 path (``shot_at_one_second`` on game_state).
    3. Possession-start ``shot_clock_remaining`` minus skeleton elapsed through
       ``shot_step_index`` (same source as turn-end shot-clock detach).
    """
    if not isinstance(game_state, dict):
        return None

    est = game_state.pop("_hco_shot_clock_est", None)
    if est is not None:
        return max(0.0, float(est))

    if game_state.get("shot_at_one_second"):
        return 1.0

    if not _is_hco_skeleton_shot(game_state, roles):
        raw = game_state.get("shot_clock_remaining")
        return float(raw) if raw is not None else None

    steps = roles.get("steps") or []
    from BackEnd.utils.shared import calc_skeleton_step_timing_contract

    timing = calc_skeleton_step_timing_contract(
        steps,
        resolution_step_index=shot_step_index,
        include_hco_step1_bringup=True,
        prev_offense_positions=game_state.get("_prev_offense_positions_for_hco"),
        phase_type="HCO",
        off_lineup=off_lineup,
    )
    elapsed = _elapsed_seconds_to_shot_step(
        timing.get("step_clock_seconds") or [],
        timing.get("resolution_step_index"),
    )
    start = float(game_state.get("shot_clock_remaining", 30) or 30)
    return max(0.0, start - elapsed)


def record_shot_split(
    game,
    *,
    is_three: bool,
    defended: bool,
    made: bool,
    turn_type=None,
    hco_shot_clock=None,
    roles=None,
    shot_step_index=None,
    off_lineup=None,
) -> None:
    """Register one field-goal attempt.

    Always updates ``shot_split_tracking``. When ``turn_type`` is one of the
    tracked buckets (HCO/HCT/FCP/Fast Break/OREB), also increments
    ``fga_by_turn_type`` — pass ``None`` (e.g. Final Shot / FLSS) to count the
    attempt in the split chart but not the turn-type breakdown.

    No-op when ``game`` has no usable ``game_state`` dict (defensive — never
    breaks a shot resolution for the sake of a diagnostic).
    """
    state = getattr(game, "game_state", None)
    if not isinstance(state, dict):
        return

    tracking = state.get("shot_split_tracking")
    if not isinstance(tracking, dict):
        tracking = _empty_tracking()
        state["shot_split_tracking"] = tracking
    key = f"{'3pt' if is_three else '2pt'}_{'def' if defended else 'undef'}"
    bucket = tracking.setdefault(key, {"make": 0, "miss": 0})
    bucket["make" if made else "miss"] += 1

    if turn_type:
        by_turn = state.get("fga_by_turn_type")
        if not isinstance(by_turn, dict):
            by_turn = _empty_fga_by_turn_type()
            state["fga_by_turn_type"] = by_turn
        by_turn[turn_type] = int(by_turn.get(turn_type, 0) or 0) + 1

        if not defended:
            undef_by_turn = state.get("undefended_by_turn_type")
            if not isinstance(undef_by_turn, dict):
                undef_by_turn = _empty_undefended_by_turn_type()
                state["undefended_by_turn_type"] = undef_by_turn
            ub = undef_by_turn.setdefault(turn_type, {"make": 0, "miss": 0})
            ub["make" if made else "miss"] += 1

    if turn_type == "HCO":
        shot_clock = hco_shot_clock
        if shot_clock is None and roles is not None:
            shot_clock = resolve_hco_shot_clock_at_attempt(
                state,
                roles,
                shot_step_index=shot_step_index,
                off_lineup=off_lineup,
            )
        if shot_clock is not None:
            record_hco_shot_tier(game, shot_clock)


def restore_shot_split_from_saved(game_state, saved) -> None:
    """Reapply the cumulative shot-split counts from a loaded game document.

    Called on quarter load (mirrors ``restore_home_crowd_from_saved``) so the
    per-game running total survives across the quarter-by-quarter / DB round
    trip. The freshly-built ``game_state`` starts at zero; this seeds it with
    the prior quarters' totals so the current quarter adds to them. Defensive:
    no-op on missing / malformed input, and only keeps the known buckets.
    """
    if not isinstance(game_state, dict) or not isinstance(saved, dict):
        return
    prior = saved.get("shot_split_tracking")
    if not isinstance(prior, dict):
        return
    restored = _empty_tracking()
    for key in _KEYS:
        bucket = prior.get(key)
        if isinstance(bucket, dict):
            restored[key] = {
                "make": int(bucket.get("make", 0) or 0),
                "miss": int(bucket.get("miss", 0) or 0),
            }
    game_state["shot_split_tracking"] = restored


def restore_fga_by_turn_type_from_saved(game_state, saved) -> None:
    """Reapply cumulative per-turn-type FGA from a loaded game document
    (quarter-by-quarter persistence; mirrors ``restore_shot_split_from_saved``).
    """
    if not isinstance(game_state, dict) or not isinstance(saved, dict):
        return
    prior = saved.get("fga_by_turn_type")
    if not isinstance(prior, dict):
        return
    restored = _empty_fga_by_turn_type()
    for tt in _TURN_TYPES:
        restored[tt] = int(prior.get(tt, 0) or 0)
    game_state["fga_by_turn_type"] = restored


def restore_undefended_by_turn_type_from_saved(game_state, saved) -> None:
    """Reapply cumulative per-turn-type undefended make/miss from a loaded game
    document (quarter-by-quarter persistence; mirrors
    ``restore_fga_by_turn_type_from_saved``)."""
    if not isinstance(game_state, dict) or not isinstance(saved, dict):
        return
    prior = saved.get("undefended_by_turn_type")
    if not isinstance(prior, dict):
        return
    restored = _empty_undefended_by_turn_type()
    for tt in _TURN_TYPES:
        bucket = prior.get(tt)
        if isinstance(bucket, dict):
            restored[tt] = {
                "make": int(bucket.get("make", 0) or 0),
                "miss": int(bucket.get("miss", 0) or 0),
            }
    game_state["undefended_by_turn_type"] = restored


def format_shot_split_summary(game) -> str:
    """Render the end-of-game shot-split chart as a printable string."""
    state = getattr(game, "game_state", None) or {}
    tracking = state.get("shot_split_tracking") or {}

    lines = [
        "",
        "================= SHOT SPLIT (make / miss) =================",
    ]
    for label, key in _ROWS:
        bucket = tracking.get(key) or {"make": 0, "miss": 0}
        make = int(bucket.get("make", 0))
        miss = int(bucket.get("miss", 0))
        att = make + miss
        pct = (make / att * 100.0) if att else 0.0
        lines.append(
            f"{label:<16}: {make:>3} / {miss:<3} make/miss  "
            f"({pct:5.1f}%)  [{att} att]"
        )
    lines.append("===========================================================")
    return "\n".join(lines)


def format_turn_type_fga_summary(game) -> str:
    """Render the end-of-game FGA-by-turn-type report (both teams combined)."""
    state = getattr(game, "game_state", None) or {}
    by_turn = state.get("fga_by_turn_type") or {}

    total = sum(int(by_turn.get(tt, 0) or 0) for tt in _TURN_TYPES)
    lines = [
        "",
        "============== FGA BY TURN TYPE (both teams) ==============",
    ]
    for tt in _TURN_TYPES:
        fga = int(by_turn.get(tt, 0) or 0)
        share = (fga / total * 100.0) if total else 0.0
        lines.append(f"{tt:<12}: {fga:>4} FGA  ({share:5.1f}%)")
    lines.append(f"{'TOTAL':<12}: {total:>4} FGA")
    lines.append("==========================================================")
    return "\n".join(lines)


def format_undefended_by_turn_type_summary(game) -> str:
    """Render the end-of-game undefended-FGA-by-turn-type report: for each turn
    type, how many of its attempts were undefended and the make/miss on them.
    Undefended share is vs that turn type's total FGA (``fga_by_turn_type``)."""
    state = getattr(game, "game_state", None) or {}
    undef = state.get("undefended_by_turn_type") or {}
    by_turn = state.get("fga_by_turn_type") or {}

    lines = [
        "",
        "========= UNDEFENDED SHOTS BY TURN TYPE =========",
    ]
    tot_undef = tot_make = tot_fga = 0
    for tt in _TURN_TYPES:
        bucket = undef.get(tt) or {"make": 0, "miss": 0}
        make = int(bucket.get("make", 0) or 0)
        miss = int(bucket.get("miss", 0) or 0)
        att = make + miss
        fga = int(by_turn.get(tt, 0) or 0)
        share = (att / fga * 100.0) if fga else 0.0
        pct = (make / att * 100.0) if att else 0.0
        tot_undef += att
        tot_make += make
        tot_fga += fga
        lines.append(
            f"{tt:<12}: {att:>3} undef / {fga:<3} FGA  ({share:5.1f}%)  "
            f"| {make:>2}-{miss:<2} make/miss ({pct:5.1f}%)"
        )
    all_share = (tot_undef / tot_fga * 100.0) if tot_fga else 0.0
    all_pct = (tot_make / tot_undef * 100.0) if tot_undef else 0.0
    lines.append(
        f"{'TOTAL':<12}: {tot_undef:>3} undef / {tot_fga:<3} FGA  ({all_share:5.1f}%)  "
        f"| {all_pct:5.1f}% make"
    )
    lines.append("=================================================")
    return "\n".join(lines)


# --- hco_shot_tier_counts (HCO shot attempts by shot-clock tier) ------------

# Display label → tier key, in report order.
_HCO_TIER_ROWS = (
    ("Early (23-30s)", "early"),
    ("Mid (15-22s)", "mid"),
    ("Late (6-14s)", "late"),
    ("Very late (1-5s)", "very_late"),
    ("Forced (<1s)", "forced"),
)
_HCO_TIERS = tuple(key for _label, key in _HCO_TIER_ROWS)


def _hco_shot_clock_tier(shot_clock):
    """Shot-clock → tier. Mirrors motion_step_decision._shot_clock_tier — keep
    the boundaries (23 / 15 / 6 / 1) in sync if they change."""
    c = float(shot_clock or 0)
    if c >= 23:
        return "early"
    if c >= 15:
        return "mid"
    if c >= 6:
        return "late"
    if c >= 1:
        return "very_late"
    return "forced"


def record_hco_shot_tier(game, shot_clock) -> None:
    """Record one HCO shot attempt in the shot-clock-tier tally, by the clock at
    the moment the shot was attempted. No-op without a usable game_state."""
    state = getattr(game, "game_state", None)
    if not isinstance(state, dict):
        return
    counts = state.get("hco_shot_tier_counts")
    if not isinstance(counts, dict):
        counts = {t: 0 for t in _HCO_TIERS}
        state["hco_shot_tier_counts"] = counts
    tier = _hco_shot_clock_tier(shot_clock)
    counts[tier] = int(counts.get(tier, 0) or 0) + 1


def restore_hco_shot_tier_from_saved(game_state, saved) -> None:
    """Reapply cumulative HCO shot-tier counts from a loaded game document
    (quarter-by-quarter persistence)."""
    if not isinstance(game_state, dict) or not isinstance(saved, dict):
        return
    prior = saved.get("hco_shot_tier_counts")
    if not isinstance(prior, dict):
        return
    game_state["hco_shot_tier_counts"] = {t: int(prior.get(t, 0) or 0) for t in _HCO_TIERS}


def format_hco_shot_tier_summary(game) -> str:
    """Render the end-of-game HCO-shots-by-shot-clock-tier report."""
    state = getattr(game, "game_state", None) or {}
    counts = state.get("hco_shot_tier_counts") or {}

    total = sum(int(counts.get(t, 0) or 0) for t in _HCO_TIERS)
    lines = [
        "",
        "======= HCO SHOT ATTEMPTS BY SHOT-CLOCK TIER =======",
    ]
    for label, t in _HCO_TIER_ROWS:
        n = int(counts.get(t, 0) or 0)
        share = (n / total * 100.0) if total else 0.0
        lines.append(f"{label:<18}: {n:>4}  ({share:5.1f}%)")
    lines.append(f"{'TOTAL':<18}: {total:>4}")
    lines.append("====================================================")
    return "\n".join(lines)


# --- subtle movements + altered actions (Dynamic MM / Goal 2) --------------

_ALTERED_ACTIONS = ("backdoor", "jab step", "flash", "post up")


def _empty_altered_team(team):
    return {
        "name": getattr(team, "name", None) or str(getattr(team, "team_id", "?")),
        "subtle_movements": 0,
        "altered_actions": {a: 0 for a in _ALTERED_ACTIONS},
    }


def _altered_bucket(game):
    """The current OFFENSE team's tally bucket in this game's game_state (created on demand), or None.
    Per-game_state → the tracking is naturally contained to this game's two teams."""
    state = getattr(game, "game_state", None)
    team = getattr(game, "offense_team", None)
    if not isinstance(state, dict) or team is None:
        return None
    tid = str(getattr(team, "team_id", "?"))
    return state.setdefault("altered_action_tracking", {}).setdefault(tid, _empty_altered_team(team))


def record_subtle_movement(game) -> None:
    """Count one subtle movement entered by the current offense team."""
    bucket = _altered_bucket(game)
    if bucket is not None:
        bucket["subtle_movements"] = int(bucket.get("subtle_movements", 0) or 0) + 1


def record_altered_action(game, action) -> None:
    """Count one altered action (backdoor / jab step / flash / post up) performed by the offense."""
    bucket = _altered_bucket(game)
    if bucket is None:
        return
    act = action if action in _ALTERED_ACTIONS else "backdoor"
    aa = bucket.setdefault("altered_actions", {a: 0 for a in _ALTERED_ACTIONS})
    aa[act] = int(aa.get(act, 0) or 0) + 1


def restore_altered_action_tracking_from_saved(game_state, saved) -> None:
    """Reapply the per-team subtle-movement / altered-action tallies from a loaded game document
    (quarter-by-quarter persistence), so the end-of-game report covers the whole game."""
    if not isinstance(game_state, dict) or not isinstance(saved, dict):
        return
    prior = saved.get("altered_action_tracking")
    if isinstance(prior, dict):
        import copy as _copy
        game_state["altered_action_tracking"] = _copy.deepcopy(prior)


def format_altered_action_summary(game) -> str:
    """End-of-game: subtle movements entered + altered actions performed, per team."""
    state = getattr(game, "game_state", None) or {}
    track = state.get("altered_action_tracking") or {}
    lines = ["", "===== SUBTLE MOVEMENTS + ALTERED ACTIONS (per team) ====="]
    if not track:
        lines.append("(none recorded)")
    for tid, d in track.items():
        aa = d.get("altered_actions") or {}
        total = sum(int(v or 0) for v in aa.values())
        sm = int(d.get("subtle_movements", 0) or 0)
        rate = (total / sm * 100.0) if sm else 0.0
        lines.append(
            f"{str(d.get('name', tid)):<22}: {sm:>4} SM  |  {total:>4} altered ({rate:5.1f}% of SM)"
        )
        lines.append(
            f"{'':<22}    bd {aa.get('backdoor', 0)} / jab {aa.get('jab step', 0)} / "
            f"flash {aa.get('flash', 0)} / post {aa.get('post up', 0)}"
        )
    lines.append("=========================================================")
    return "\n".join(lines)


# --- master end-of-game report ---------------------------------------------


def format_master_eog_report(game) -> str:
    """One consolidated end-of-game shot-diagnostics report — all tallies in a
    single block. Grep ``END-OF-GAME SHOT DIAGNOSTICS`` to find it in stdout."""
    return "\n".join([
        "",
        "################# END-OF-GAME SHOT DIAGNOSTICS #################",
        format_shot_split_summary(game),
        format_turn_type_fga_summary(game),
        format_undefended_by_turn_type_summary(game),
        format_hco_shot_tier_summary(game),
        format_altered_action_summary(game),
        "###############################################################",
        "",
    ])


# --- week-level aggregate across multiple games ----------------------------


def merge_shot_diagnostics(summaries):
    """Sum the three tallies across a list of game summaries (or game_state dicts).

    Each summary carries top-level ``shot_split_tracking`` / ``fga_by_turn_type``
    / ``hco_shot_tier_counts`` (as stamped by ``summarize_game_state``). Returns
    ``(merged_dict, num_games)`` — num_games counts only summaries that actually
    carried shot data.
    """
    merged = {
        "shot_split_tracking": _empty_tracking(),
        "fga_by_turn_type": _empty_fga_by_turn_type(),
        "undefended_by_turn_type": _empty_undefended_by_turn_type(),
        "hco_shot_tier_counts": {t: 0 for t in _HCO_TIERS},
    }
    n = 0
    for s in summaries or []:
        if not isinstance(s, dict):
            continue
        sst = s.get("shot_split_tracking")
        fbt = s.get("fga_by_turn_type")
        ubt = s.get("undefended_by_turn_type")
        tier = s.get("hco_shot_tier_counts")
        if not any(isinstance(x, dict) and x for x in (sst, fbt, tier)):
            continue  # no shot data on this summary — don't count it as a game
        n += 1
        for k in _KEYS:
            b = (sst or {}).get(k) or {}
            merged["shot_split_tracking"][k]["make"] += int(b.get("make", 0) or 0)
            merged["shot_split_tracking"][k]["miss"] += int(b.get("miss", 0) or 0)
        for tt in _TURN_TYPES:
            merged["fga_by_turn_type"][tt] += int((fbt or {}).get(tt, 0) or 0)
            ub = (ubt or {}).get(tt) or {}
            merged["undefended_by_turn_type"][tt]["make"] += int(ub.get("make", 0) or 0)
            merged["undefended_by_turn_type"][tt]["miss"] += int(ub.get("miss", 0) or 0)
        for t in _HCO_TIERS:
            merged["hco_shot_tier_counts"][t] += int((tier or {}).get(t, 0) or 0)
    return merged, n


def format_week_aggregate_report(merged, num_games) -> str:
    """Render the per-week aggregate shot-diagnostics report across ``num_games``
    full-game sims (``num_teams = 2 × num_games``): per-team averages plus the
    percentage splits of every tracked dimension. Grep ``WEEK AGGREGATE``."""
    sst = (merged or {}).get("shot_split_tracking") or {}
    fbt = (merged or {}).get("fga_by_turn_type") or {}
    ubt = (merged or {}).get("undefended_by_turn_type") or {}
    tier = (merged or {}).get("hco_shot_tier_counts") or {}
    num_teams = max(0, int(num_games)) * 2

    def _att(key):
        b = sst.get(key) or {}
        return int(b.get("make", 0) or 0) + int(b.get("miss", 0) or 0)

    def _make(key):
        return int((sst.get(key) or {}).get("make", 0) or 0)

    total_fga = sum(_att(k) for k in _KEYS)
    total_fgm = sum(_make(k) for k in _KEYS)
    tpa = _att("3pt_def") + _att("3pt_undef")
    tpm = _make("3pt_def") + _make("3pt_undef")

    def _per_team(x):
        return (x / num_teams) if num_teams else 0.0

    def _pct(num, den):
        return (num / den * 100.0) if den else 0.0

    lines = [
        "",
        f"========= WEEK AGGREGATE — SHOT DIAGNOSTICS ({num_games} games / {num_teams} teams) =========",
        "Per-team averages:",
        f"  FGA  {_per_team(total_fga):5.1f}   FG%  {_pct(total_fgm, total_fga):5.1f}%",
        f"  3PTA {_per_team(tpa):5.1f}   3PT% {_pct(tpm, tpa):5.1f}%",
        "",
        "Shot split (% of all FGA  |  make%):",
    ]
    for label, key in _ROWS:
        att = _att(key)
        lines.append(
            f"  {label:<16}: {_pct(att, total_fga):5.1f}% of FGA  "
            f"({_pct(_make(key), att):5.1f}% make, {att} att)"
        )

    tt_total = sum(int(fbt.get(tt, 0) or 0) for tt in _TURN_TYPES)
    lines.append("")
    lines.append("FGA by turn type (% of turn-type FGA):")
    for tt in _TURN_TYPES:
        v = int(fbt.get(tt, 0) or 0)
        lines.append(f"  {tt:<12}: {_pct(v, tt_total):5.1f}%  ({v})")

    lines.append("")
    lines.append("Undefended by turn type (% of turn-type FGA  |  make%):")
    for tt in _TURN_TYPES:
        b = ubt.get(tt) or {}
        att = int(b.get("make", 0) or 0) + int(b.get("miss", 0) or 0)
        fga = int(fbt.get(tt, 0) or 0)
        lines.append(
            f"  {tt:<12}: {_pct(att, fga):5.1f}% undef  "
            f"({_pct(int(b.get('make', 0) or 0), att):5.1f}% make, {att} att)"
        )

    tier_total = sum(int(tier.get(t, 0) or 0) for t in _HCO_TIERS)
    lines.append("")
    lines.append("HCO shots by shot-clock tier (%):")
    for label, t in _HCO_TIER_ROWS:
        v = int(tier.get(t, 0) or 0)
        lines.append(f"  {label:<18}: {_pct(v, tier_total):5.1f}%  ({v})")

    lines.append("============================================================================")
    return "\n".join(lines)
