"""Shot diagnostics tracker (per-game, both teams combined).

Two independent per-game tallies, both stored on ``game.game_state`` and
rendered as end-of-game charts:

1. ``shot_split_tracking`` — every field-goal attempt across three binary
   dimensions: 2pt/3pt × defended/undefended × make/miss.

2. ``fga_by_turn_type`` — total field-goal attempts bucketed by the turn
   type that generated them: HCO, HCT, FCP, Fast Break, OREB. (Final Shot /
   FLSS buzzer attempts are intentionally omitted from this breakdown.)

Coverage (both tallies): HCO, FCP, Final Shot, and regular Fast Break via
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


def record_shot_split(game, *, is_three: bool, defended: bool, made: bool,
                      turn_type=None) -> None:
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


# --- master end-of-game report ---------------------------------------------


def format_master_eog_report(game) -> str:
    """One consolidated end-of-game shot-diagnostics report — all tallies in a
    single block. Grep ``END-OF-GAME SHOT DIAGNOSTICS`` to find it in stdout."""
    return "\n".join([
        "",
        "################# END-OF-GAME SHOT DIAGNOSTICS #################",
        format_shot_split_summary(game),
        format_turn_type_fga_summary(game),
        format_hco_shot_tier_summary(game),
        "###############################################################",
        "",
    ])
