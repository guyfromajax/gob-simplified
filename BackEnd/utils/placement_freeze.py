"""Stage 2a — ONE placement draw per step, written once, never redrawn.

``GOB_PLACEMENT_FREEZE`` (default ``"0"``). Every helper here returns early when the
flag is off, so flag-off is byte-identical by construction rather than by parity.

WHAT THE FLAG CHANGES
  * ``_stamp_contest_defender_grid`` becomes WRITE-ONCE: it still runs at all three
    call sites and still fills gaps, it just stops overwriting a step that already
    carries a defender row.
  * ``build_step_states`` becomes a READ.
  * the HCO emit renders the frozen row instead of its own fresh draw, and the
    ``_hco_render_animations`` stash (which piped the render's draw BACKWARDS into
    StepState) is no longer written.

THE INVARIANT IS "ONE DRAW PER STEP", NOT "ONE PRODUCER".
Measured in reports/placement-freeze-2a-2026-09-21.md: 15-22% of post-subtle beats
(``phase_resolution.py`` :7683) are NEVER covered by any stamp, and that pre-seed is
consumed synchronously by ``_hco_step_def_xy`` in the same block that writes it,
before any stamp can run. A step's row therefore belongs to whoever CREATES the step;
the stamp is a gap-filler for everyone else. ``announce_blocked_write`` exists to keep
that honest — every producer that got there first is named.

RULE 26b — a guard that corrects must announce. A consumer reaching a step with no
frozen row falls back to a legacy reconstruction, which is a fresh ``get_defender_coords``
draw, i.e. the exact defect this stage removes. That fallback is never silent here:
``announce_freeze_miss`` logs every occurrence with the consumer, the step and the
reason, and the counter is this stage's acceptance test.
"""

import logging
import os

FLAG = "GOB_PLACEMENT_FREEZE"
FLAG_SINGLE_BUILD = "GOB_PLACEMENT_SINGLE_BUILD"

# Reasons a consumer can reach a step with no frozen row. Truncation is deliberately
# NOT among them: truncation removes steps, it cannot leave one unstamped.
REASON_NEVER_STAMPED = "appended_after_last_stamp"   # no _step_state at all
REASON_STAMPED_EMPTY = "stamped_empty"               # a stamp ran and produced no row
REASON_UNKNOWN = "unknown"

_COUNTERS = {
    "freeze_miss": {},          # consumer -> count
    "freeze_miss_reason": {},   # reason -> count
    "blocked_write": {},        # producer -> count
    "blocked_steps": 0,         # steps whose row a stamp declined to overwrite
    "frozen_applied": 0,        # defender rows the emit rendered from the freeze
    "frozen_absent": 0,         # emit steps with no frozen row (rendered its own draw)
    "builds_total": 0,          # Stage 3: stamp calls seen
    "builds_skippable": 0,      # Stage 3: whose build would be discarded in full (the ceiling)
    "builds_skipped": 0,        # Stage 3: whose build was actually not run
}

_log = logging.getLogger(__name__)


def enabled():
    """True when the stage is switched on. Default OFF."""
    return os.environ.get(FLAG, "0") == "1"


def single_build_enabled():
    """Stage 3. Default OFF, and **inert unless the freeze is also on** — the dependency
    is enforced here, in one place, by conjunction rather than by documentation: with
    write-once off, every build's result is still consumed, so nothing is discardable
    and skipping one would change what consumers read."""
    return enabled() and os.environ.get(FLAG_SINGLE_BUILD, "0") == "1"


def stamp_build_is_discardable(steps):
    """Stage 3 — would this stamp's build be thrown away in its entirety?

    True only when EVERY step already carries both a defender row and an offense row.
    Defence alone is not enough: a post-subtle beat (phase_resolution.py:7683) arrives
    pre-seeded with `defense` and no `offense`, and skipping the build there would
    strip the offense row the SIM arm's coord write scans for at :5030.

    Placement is SEQUENTIAL — ``position_standard_defenders`` seeds step N from
    ``def_movement[-1]`` (defender_placement.py:1219) — so a build can only be skipped
    WHOLE. There is no correct partial build here, and this function deliberately does
    not pretend otherwise.
    """
    if not steps:
        return False
    for step in steps:
        if not isinstance(step, dict):
            return False
        ss = step.get("_step_state") or {}
        if not (ss.get("defense") or {}) or not (ss.get("offense") or {}):
            return False
    return True


def frozen_defense(step):
    """The frozen defender row on a step, or ``{}``. Never invents one (rule 26)."""
    if not isinstance(step, dict):
        return {}
    return ((step.get("_step_state") or {}).get("defense")) or {}


def miss_reason(step):
    """Why this step has no frozen row. Observable, not guessed."""
    if not isinstance(step, dict):
        return REASON_UNKNOWN
    ss = step.get("_step_state")
    if not ss:
        return REASON_NEVER_STAMPED
    if not (ss.get("defense") or {}):
        return REASON_STAMPED_EMPTY
    return REASON_UNKNOWN


def announce_freeze_miss(consumer, step, step_index=None, game=None, extra=""):
    """Rule 26b. A consumer is about to REDRAW because the freeze did not cover this
    step. Log every occurrence — a silent redraw here is the defect wearing a healthy
    instrument. Counted so a sweep can read the rate."""
    if not enabled():
        return
    reason = miss_reason(step)
    _COUNTERS["freeze_miss"][consumer] = _COUNTERS["freeze_miss"].get(consumer, 0) + 1
    _COUNTERS["freeze_miss_reason"][reason] = _COUNTERS["freeze_miss_reason"].get(reason, 0) + 1
    gid = None
    try:
        gid = (getattr(game, "game_state", None) or {}).get("game_id")
    except Exception:
        pass
    _log.warning(
        "⚠️ [PLACEMENT FREEZE MISS] %s read step i=%s with no frozen grid → "
        "legacy reconstruction (this is a REDRAW, not the frozen draw). "
        "reason=%s game=%s%s",
        consumer, step_index, reason, gid, (" " + extra) if extra else "",
    )


def announce_blocked_write(producer, n_steps, game=None):
    """The weaker announcement: a stamp declined to overwrite rows another producer
    wrote first. Not an error — it is what "one draw per step" means — but it is said
    out loud once per stamp so "single producer" is never claimed by accident."""
    if not enabled() or not n_steps:
        return
    _COUNTERS["blocked_write"][producer] = _COUNTERS["blocked_write"].get(producer, 0) + 1
    _COUNTERS["blocked_steps"] += n_steps
    gid = None
    try:
        gid = (getattr(game, "game_state", None) or {}).get("game_id")
    except Exception:
        pass
    _log.debug(
        "\U0001f9ca [PLACEMENT FREEZE] %s kept %d step row(s) already written by an earlier "
        "producer (write-once). game=%s", producer, n_steps, gid,
    )


def apply_frozen_grid_to_animations(animations, def_lineup, steps, game=None):
    """Render the FROZEN row instead of the emit's own draw.

    The emit still builds (2a keeps the draws; Stage 3 removes them) — this overwrites
    the defenders' ``movement[i].coords`` with the frozen row so what reaches the screen
    is the row the contest already judged against. Offensive rows and every ``action``
    tag are untouched: the divergence measured in
    reports/placement-draw-divergence-2026-09-21.md is positional.

    ``movement[i]`` is step ``i`` for DEFENDERS specifically (see
    ``defender_placement.defender_grid_from_animations``, whose docstring contrasts this
    with the offense, where it is not). A step with no frozen row keeps the emit's own
    draw and is counted — it is a freeze miss, announced by the consumer that reads it.
    """
    if not enabled() or not animations or not steps:
        return animations
    pid_by_dpos = {dp: getattr(p, "player_id", None) for dp, p in (def_lineup or {}).items()}
    move_by_pid = {a.get("playerId"): (a.get("movement") or [])
                   for a in animations if isinstance(a, dict) and a.get("playerId")}
    for i, step in enumerate(steps):
        row = frozen_defense(step)
        if not row:
            _COUNTERS["frozen_absent"] += 1
            continue
        for dpos, pid in pid_by_dpos.items():
            coord = row.get(dpos)
            if not pid or not isinstance(coord, dict) or "x" not in coord or "y" not in coord:
                continue
            mv = move_by_pid.get(pid) or []
            if i >= len(mv) or not isinstance(mv[i], dict):
                continue
            mv[i]["coords"] = {"x": float(coord["x"]), "y": float(coord["y"])}
            _COUNTERS["frozen_applied"] += 1
    return animations


def note_stamp_build(skippable, skipped):
    """Stage 3 tally, recorded on EVERY stamp call in every configuration.

    ``skippable`` is the ceiling — how many builds *could* be skipped — and is counted
    even with the flags off, so an OFF run states the opportunity next to an ON run's
    realised saving instead of leaving it to be inferred."""
    _COUNTERS["builds_total"] += 1
    if skippable:
        _COUNTERS["builds_skippable"] += 1
    if skipped:
        _COUNTERS["builds_skipped"] += 1


def counters():
    """A copy of the running tallies. ``freeze_miss`` reading ~0 is the stage's
    acceptance test: if it is not, the freeze does not cover the steps consumers
    actually read."""
    return {
        "freeze_miss": dict(_COUNTERS["freeze_miss"]),
        "freeze_miss_reason": dict(_COUNTERS["freeze_miss_reason"]),
        "freeze_miss_total": sum(_COUNTERS["freeze_miss"].values()),
        "blocked_write": dict(_COUNTERS["blocked_write"]),
        "blocked_steps": _COUNTERS["blocked_steps"],
        "frozen_applied": _COUNTERS["frozen_applied"],
        "frozen_absent": _COUNTERS["frozen_absent"],
        "builds_total": _COUNTERS["builds_total"],
        "builds_skippable": _COUNTERS["builds_skippable"],
        "builds_skipped": _COUNTERS["builds_skipped"],
    }


def reset_counters():
    _COUNTERS["freeze_miss"] = {}
    _COUNTERS["freeze_miss_reason"] = {}
    _COUNTERS["blocked_write"] = {}
    _COUNTERS["blocked_steps"] = 0
    _COUNTERS["frozen_applied"] = 0
    _COUNTERS["frozen_absent"] = 0
    _COUNTERS["builds_total"] = 0
    _COUNTERS["builds_skippable"] = 0
    _COUNTERS["builds_skipped"] = 0
