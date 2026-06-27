"""Shot-split diagnostic tracker.

Per-game tally of every field-goal attempt across three binary dimensions:
  - 2-point vs 3-point
  - defended (a defender contested) vs undefended (open)
  - make vs miss

Counts accumulate on ``game.game_state["shot_split_tracking"]`` and are
rendered as an end-of-game chart by ``format_shot_split_summary``.

Coverage: the five shot paths instrumented are HCO, FCP, Final Shot, and
regular Fast Break (all via ``ShotManager.resolve_shot``), Dynamic HCT
(``resolve_hct_fast_break_shot`` + ``_finalize_ab_shot``), and After-Steal
Fast Break (``resolve_after_steal_fast_break``). Free throws and OREB
putbacks are intentionally NOT counted.

Diagnostic instrument for the 3-point make-rate investigation; "defended"
mirrors the engine's ``has_contest`` / ``contested`` flag (= ``apply_defense``).
"""

# Display label → tracking key. Order is the chart's row order.
_ROWS = (
    ("3 pt defended", "3pt_def"),
    ("3 pt undefended", "3pt_undef"),
    ("2 pt defended", "2pt_def"),
    ("2 pt undefended", "2pt_undef"),
)

_KEYS = tuple(key for _label, key in _ROWS)


def _empty_tracking():
    return {key: {"make": 0, "miss": 0} for key in _KEYS}


def record_shot_split(game, *, is_three: bool, defended: bool, made: bool) -> None:
    """Register one field-goal attempt in the per-game shot-split tracker.

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
