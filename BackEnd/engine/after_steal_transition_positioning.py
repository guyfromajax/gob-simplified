"""Coordinated transition positioning for Fast Break drive resolution.

Fast breaks used to park every off-ball player on the basket (the universal
drive helper's blanket rim-crash) — an unrealistic cluster, especially on steal
FBs where the whole cast starts bunched on the x-grid. This module is the
planner that authors *coordinated* destinations instead: the ball handler
drives, the two teammates closest to the attacking basket ("leads") fan out to
the lower/upper spacing tiers, and the two "trailers" spread to the 3-point arc
(or hold on a stop). The defense mirrors it with matchups + help spots.

Originally built for After-Steal, this is now applied to **all** FB play types
(Rim Runner, Triangle, Covert Release, After-Steal) via
``author_transition_end_coords`` — the single entry point that authors the
all-ten end coords (offense spread + defense matchups). Callers derive the
``outcome_kind`` + role inputs from the ``fb_drive_resolution`` payload.

Pure + unit-testable: functions take/return plain ``{player_id: {x, y}}`` dicts
(HOME orientation, mirrored for the away offense) and never mutate game state.

See ``Fast_Break_System.md`` §Coordinated Transition.
"""

from __future__ import annotations

from BackEnd.utils.sim_random import sim_rng as _random_module
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.constants import HCO_STRING_SPOTS
from BackEnd.constants.fast_break_constants import (
    FB_AS_ARC_SPOTS_LOWER,
    FB_AS_ARC_SPOTS_UPPER,
    FB_AS_HELP_SPOTS_LOWER,
    FB_AS_HELP_SPOTS_UPPER,
    FB_AS_LEAD_DEF_X_OFFSET,
    FB_AS_LEAD_HCO_SPOTS,
    FB_AS_NO_MEET_CHASE_X_BEHIND,
    FB_AS_TIER_LOWER_Y,
    FB_AS_TIER_UPPER_Y,
    FB_AS_TIER_Y_JITTER,
)

Coord = Dict[str, float]

# Outcome kinds the offense planner understands.
SHOT_KINDS = frozenset({"rim_finish", "pull_up", "pass"})
HCO_KIND = "hco"
TERMINAL_KIND = "terminal"

_HALF_COURT_Y = 25.0


def _clamp(coord: Coord) -> Coord:
    return {
        "x": float(max(4, min(97, round(float(coord["x"]))))),
        "y": float(max(1, min(49, round(float(coord["y"]))))),
    }


def _mirror_x(home_x: float) -> float:
    return 100.0 - float(home_x)


def _spot_coords(name: str, is_away_offense: bool) -> Coord:
    raw = HCO_STRING_SPOTS.get(name, {"x": 50, "y": 25})
    x, y = float(raw["x"]), float(raw["y"])
    if is_away_offense:
        x = _mirror_x(x)
    return {"x": x, "y": y}


def _x_progress_toward_basket(x: float, is_away_offense: bool) -> float:
    """Higher = closer to the attacking basket. Away attacks low x, so progress
    is mirrored."""
    return _mirror_x(x) if is_away_offense else float(x)


def classify_offense_roles(
    *,
    stealer_id: str,
    off_start_coords: Dict[str, Coord],
    is_away_offense: bool,
) -> Tuple[List[str], List[str]]:
    """Split the four non-BH offenders into (lead_ids, trailer_ids).

    Leads = the two teammates with the greatest x-progress toward the attacking
    basket (i.e. closest to the rim at the moment of the steal); trailers = the
    other two. Ties broken by player_id for determinism.
    """
    others = [
        pid for pid in off_start_coords if pid != stealer_id
    ]
    others.sort(
        key=lambda pid: (
            -_x_progress_toward_basket(off_start_coords[pid]["x"], is_away_offense),
            pid,
        )
    )
    leads = others[:2]
    trailers = others[2:4]
    return leads, trailers


def _assign_lead_tiers(
    lead_ids: List[str],
    off_start_coords: Dict[str, Coord],
    rng: Any,
) -> Dict[str, float]:
    """Map each lead to a fanned tier y (lower vs upper), keeping geometry true:
    the lead starting lower on the court takes the lower tier."""
    tier_y: Dict[str, float] = {}
    if not lead_ids:
        return tier_y
    ordered = sorted(lead_ids, key=lambda pid: (off_start_coords[pid]["y"], pid))
    anchors = [FB_AS_TIER_LOWER_Y, FB_AS_TIER_UPPER_Y]
    for pid, anchor in zip(ordered, anchors):
        jitter = rng.randint(-FB_AS_TIER_Y_JITTER, FB_AS_TIER_Y_JITTER)
        tier_y[pid] = float(anchor + jitter)
    # Single lead (degenerate lineup) → center-ish.
    if len(ordered) == 1:
        tier_y[ordered[0]] = float(FB_AS_TIER_LOWER_Y)
    return tier_y


def _assign_arc_spots(
    trailer_ids: List[str],
    off_start_coords: Dict[str, Coord],
    is_away_offense: bool,
    rng: Any,
) -> Dict[str, Coord]:
    """Assign each trailer a distinct 3-point arc spot on its vertical half.

    A trailer in the upper half (y >= midcourt) picks from the upper arc pool,
    a lower-half trailer from the lower pool; the two trailers can never share a
    spot (if both would land on ``key`` one is bumped to another spot).
    """
    ends: Dict[str, Coord] = {}
    used: set[str] = set()
    # Deterministic order: upper-half trailers first, then by id.
    ordered = sorted(
        trailer_ids,
        key=lambda pid: (off_start_coords[pid]["y"] < _HALF_COURT_Y, pid),
    )
    for pid in ordered:
        upper = off_start_coords[pid]["y"] >= _HALF_COURT_Y
        pool = list(FB_AS_ARC_SPOTS_UPPER if upper else FB_AS_ARC_SPOTS_LOWER)
        rng.shuffle(pool)
        choice = next((s for s in pool if s not in used), None)
        if choice is None:
            # Both halves exhausted their overlap ("key"); fall back to the
            # other half's pool so the two trailers stay distinct.
            alt = list(FB_AS_ARC_SPOTS_LOWER if upper else FB_AS_ARC_SPOTS_UPPER)
            rng.shuffle(alt)
            choice = next((s for s in alt if s not in used), alt[0])
        used.add(choice)
        ends[pid] = _clamp(_spot_coords(choice, is_away_offense))
    return ends


def author_offense_end_coords(
    *,
    stealer_id: str,
    bh_end: Coord,
    off_start_coords: Dict[str, Coord],
    outcome_kind: str,
    is_away_offense: bool,
    rng: Optional[Any] = None,
) -> Dict[str, Coord]:
    """Author end coords for all five offensive players.

    * ``rim_finish`` / ``pull_up`` / ``pass`` (shot modes): leads pull back to
      the mid-post x keeping their fanned tier y (rebound / dish range); trailers
      spread to distinct 3-point arc spots.
    * ``hco``: leads set up on the low blocks; trailers hold their spots.
    * ``terminal`` (foul / charge / dead ball): everyone holds.

    The ball handler always ends at ``bh_end``.
    """
    rng = rng or _random_module
    leads, trailers = classify_offense_roles(
        stealer_id=stealer_id,
        off_start_coords=off_start_coords,
        is_away_offense=is_away_offense,
    )
    ends: Dict[str, Coord] = {stealer_id: _clamp(dict(bh_end))}

    if outcome_kind == TERMINAL_KIND:
        for pid in off_start_coords:
            if pid == stealer_id:
                continue
            ends[pid] = _clamp(dict(off_start_coords[pid]))
        return ends

    if outcome_kind == HCO_KIND:
        lead_spots = list(FB_AS_LEAD_HCO_SPOTS)
        # Higher-on-court lead → upper lowPost; lower → lower lowPost.
        ordered_leads = sorted(
            leads, key=lambda pid: (off_start_coords[pid]["y"], pid), reverse=True
        )
        upper_first = ["upper lowPost", "lower lowPost"]
        for pid, spot in zip(ordered_leads, upper_first):
            ends[pid] = _clamp(_spot_coords(spot, is_away_offense))
        for pid in trailers:
            ends[pid] = _clamp(dict(off_start_coords[pid]))
        return ends

    # Shot modes: leads → mid-post x @ fanned tier y; trailers → arc. Product
    # (Jul 2026): pull the leads back off the rim to the mid-post (upper/lower
    # midPost x) so they hold rebound/dish range without clogging the restricted
    # area. The fanned tier y (upper ~32 / lower ~18, jittered) keeps them on
    # distinct strings and near the named midPost anchors.
    tier_y = _assign_lead_tiers(leads, off_start_coords, rng)
    midpost_x = _spot_coords("upper midPost", is_away_offense)["x"]
    for pid in leads:
        ends[pid] = _clamp({"x": midpost_x, "y": tier_y.get(pid, _HALF_COURT_Y)})
    ends.update(_assign_arc_spots(trailers, off_start_coords, is_away_offense, rng))
    return ends


def _euclid(a: Coord, b: Coord) -> float:
    dx = float(a["x"]) - float(b["x"])
    dy = float(a["y"]) - float(b["y"])
    return (dx * dx + dy * dy) ** 0.5


def _chase_behind(bh_end: Coord, is_away_offense: bool) -> Coord:
    """Trail spot ``FB_AS_NO_MEET_CHASE_X_BEHIND`` x-spots behind the finish
    (goal-side toward midcourt) at the BH's y — a rebound position on a miss."""
    if is_away_offense:
        x = float(bh_end["x"]) + FB_AS_NO_MEET_CHASE_X_BEHIND
    else:
        x = float(bh_end["x"]) - FB_AS_NO_MEET_CHASE_X_BEHIND
    return _clamp({"x": x, "y": float(bh_end["y"])})


def _beaten_trail_spot(bh_end: Coord, index: int, is_away_offense: bool) -> Coord:
    """A defender the BH already beat trails the finish, stacked a little further
    back and fanned in y so multiple beaten defenders don't overlap."""
    extra = FB_AS_NO_MEET_CHASE_X_BEHIND + 2 * (index + 1)
    if is_away_offense:
        x = float(bh_end["x"]) + extra
    else:
        x = float(bh_end["x"]) - extra
    y_off = (index + 1) * 3 * (1 if index % 2 == 0 else -1)
    return _clamp({"x": x, "y": float(bh_end["y"]) + y_off})


def _lead_defender_spot(lead_end: Coord, is_away_offense: bool) -> Coord:
    """A lead defender sits ``FB_AS_LEAD_DEF_X_OFFSET`` x-spots ball-side (toward
    midcourt) of his man, matching his y."""
    if is_away_offense:
        x = float(lead_end["x"]) + FB_AS_LEAD_DEF_X_OFFSET
    else:
        x = float(lead_end["x"]) - FB_AS_LEAD_DEF_X_OFFSET
    return _clamp({"x": x, "y": float(lead_end["y"])})


def _no_retreat_end(end: Coord, start: Coord, is_away_offense: bool) -> Coord:
    """On a rim finish the defense collapses TOWARD the rim, never away — a
    defender must not render farther from the basket than his (fresh) start.
    Returns ``start`` when ``end`` would retreat (e.g. a stale-coord reachable end
    computed from a start-of-break position), else ``end``. Both clamped."""
    if _x_progress_toward_basket(float(end["x"]), is_away_offense) < \
            _x_progress_toward_basket(float(start["x"]), is_away_offense):
        return _clamp(dict(start))
    return _clamp(dict(end))


def _assign_help_spots(
    help_ids: List[str],
    def_start_coords: Dict[str, Coord],
    is_away_offense: bool,
    rng: Any,
) -> Dict[str, Coord]:
    """Distinct, side-biased help spots for the two drop defenders."""
    ends: Dict[str, Coord] = {}
    used: set[str] = set()
    ordered = sorted(
        help_ids,
        key=lambda pid: (def_start_coords[pid]["y"] < _HALF_COURT_Y, pid),
    )
    for pid in ordered:
        upper = def_start_coords[pid]["y"] >= _HALF_COURT_Y
        pool = list(FB_AS_HELP_SPOTS_UPPER if upper else FB_AS_HELP_SPOTS_LOWER)
        rng.shuffle(pool)
        choice = next((s for s in pool if s not in used), None)
        if choice is None:
            alt = list(FB_AS_HELP_SPOTS_LOWER if upper else FB_AS_HELP_SPOTS_UPPER)
            rng.shuffle(alt)
            choice = next((s for s in alt if s not in used), alt[0])
        used.add(choice)
        ends[pid] = _clamp(_spot_coords(choice, is_away_offense))
    return ends


def author_defense_end_coords(
    *,
    def_start_coords: Dict[str, Coord],
    bh_defender_id: Optional[str],
    bh_start: Coord,
    bh_end: Coord,
    meet: Optional[Coord],
    bh_reaches_rim: bool,
    lead_ids: List[str],
    offense_end_coords: Dict[str, Coord],
    is_away_offense: bool,
    beaten_stopper_ids: Optional[List[str]] = None,
    reachable_ends: Optional[Dict[str, Coord]] = None,
    rng: Optional[Any] = None,
) -> Dict[str, Coord]:
    """Author end coords for all five defenders (coordinated matchups).

    Precedence:
      1. **BH defender** = the resolver's (final) cutoff stopper
         (``bh_defender_id``), or — in the NO_MEET case — the defender closest
         to the ball handler. He ends on the meet when he stopped/contested the
         drive, or — when the BH reaches the rim — at his **reachable** end
         (``reachable_ends``: where his sprint from his real start actually got
         him by the drive time), so a clean breakaway reads as uncontested and a
         hustled-back defender as a contest. Falls back to the fixed
         ``FB_AS_NO_MEET_CHASE_X_BEHIND`` chase spot when no reachable end given.
      1b. Any **beaten stoppers** (``beaten_stopper_ids`` — defenders the BH blew
         past during a cutoff cascade) trail at their reachable end (else the
         stacked fixed trail spot).
      2. The **remaining defenders closest to the basket** pick up the two
         leads (paired by basket-proximity), sitting ball-side of their man.
      3. The **last defenders** drop to distinct, side-biased help spots.
    """
    rng = rng or _random_module
    reach = reachable_ends or {}
    beaten = [str(b) for b in (beaten_stopper_ids or []) if b]
    ends: Dict[str, Coord] = {}

    # Rim finish (BH reaches the rim): the defense is SCRAMBLING back toward its
    # own basket, not setting a half-court matchup. Render every defender at his
    # REACHABLE chase end — where his sprint from his real start actually got him
    # by the drive time (``reachable_ends`` = the resolver's ``defender_end_coords``).
    # A clean breakaway then reads uncontested; a hustled-back defender contests —
    # one coord for both decision and render (single-coord-source). The
    # coordinated lead/help matchups below are for the NEUTRAL stop (half-court-
    # like). Falls through to the fixed chase spread when no reachable ends given.
    if bh_reaches_rim and reach:
        # No-retreat: on a rim finish the defense collapses TOWARD the rim, never
        # away from it. ``reachable_ends`` comes from the resolver's ``def_starts``,
        # which for RR/Triangle are start-of-break coords that can differ from the
        # emitter's FRESH render start (``def_start_coords``) — using them verbatim
        # animates a near-basket defender OUT to mid-court (he abandons the basket).
        # Clamp each end so a defender never renders farther from the basket than
        # his fresh render start; a genuinely-far breakaway defender is unaffected.
        return {
            pid: _no_retreat_end(reach[pid], def_start_coords[pid], is_away_offense)
            for pid in def_start_coords
            if pid in reach
        }

    # (1) BH defender.
    if not bh_defender_id or bh_defender_id not in def_start_coords:
        candidates = [pid for pid in def_start_coords if pid not in beaten]
        bh_defender_id = min(
            candidates,
            key=lambda pid: (_euclid(def_start_coords[pid], bh_start), pid),
        ) if candidates else None
    if bh_defender_id:
        if bh_reaches_rim or meet is None:
            ends[bh_defender_id] = _chase_behind(bh_end, is_away_offense)
        else:
            ends[bh_defender_id] = _clamp(dict(meet))

    # (1b) Beaten stoppers trail the finish.
    for j, pid in enumerate(beaten):
        if pid in def_start_coords and pid != bh_defender_id:
            ends[pid] = _beaten_trail_spot(bh_end, j, is_away_offense)

    # (2) Lead matchups — rank remaining defenders + leads by basket-proximity.
    remaining = [
        pid for pid in def_start_coords
        if pid != bh_defender_id and pid not in beaten
    ]
    remaining.sort(
        key=lambda pid: (
            -_x_progress_toward_basket(def_start_coords[pid]["x"], is_away_offense),
            pid,
        )
    )
    lead_defs = remaining[:2]
    help_defs = remaining[2:4]

    ordered_leads = sorted(
        [lid for lid in lead_ids if lid in offense_end_coords],
        key=lambda lid: (
            -_x_progress_toward_basket(offense_end_coords[lid]["x"], is_away_offense),
            lid,
        ),
    )
    for def_id, lead_id in zip(lead_defs, ordered_leads):
        ends[def_id] = _lead_defender_spot(offense_end_coords[lead_id], is_away_offense)
    # Any lead defender without a lead (degenerate lineup) drops to help.
    unpaired = lead_defs[len(ordered_leads):]
    help_defs = list(help_defs) + list(unpaired)

    # (3) Help defenders.
    ends.update(_assign_help_spots(help_defs, def_start_coords, is_away_offense, rng))

    # On a rim finish reached via this coordinated-spread fallback (empty
    # reachable_ends), still forbid any defender from retreating away from the
    # basket — the half-court lead/help matchup only applies to the NEUTRAL stop.
    if bh_reaches_rim:
        ends = {
            pid: _no_retreat_end(e, def_start_coords[pid], is_away_offense)
            if pid in def_start_coords else e
            for pid, e in ends.items()
        }
    return ends


def author_transition_end_coords(
    *,
    bh_id: str,
    bh_start: Coord,
    bh_end: Coord,
    off_start_coords: Dict[str, Coord],
    def_start_coords: Dict[str, Coord],
    bh_defender_id: Optional[str],
    meet: Optional[Coord],
    outcome_kind: str,
    bh_reaches_rim: bool,
    beaten_stopper_ids: Optional[List[str]] = None,
    is_away_offense: bool = False,
    reachable_ends: Optional[Dict[str, Coord]] = None,
    rng: Optional[Any] = None,
) -> Dict[str, Coord]:
    """All-ten coordinated end coords for a FB drive resolution.

    The single entry point shared by every FB play type: authors the offense
    spread (leads/trailers per ``outcome_kind``) and the defensive matchups (BH
    defender + lead matchups + help spots), then merges them (offense wins on the
    unlikely id collision). Callers derive ``outcome_kind``/``meet``/
    ``bh_defender_id`` etc. from the ``fb_drive_resolution`` payload.
    """
    leads, _trailers = classify_offense_roles(
        stealer_id=bh_id,
        off_start_coords=off_start_coords,
        is_away_offense=is_away_offense,
    )
    offense = author_offense_end_coords(
        stealer_id=bh_id,
        bh_end=bh_end,
        off_start_coords=off_start_coords,
        outcome_kind=outcome_kind,
        is_away_offense=is_away_offense,
        rng=rng,
    )
    defense = author_defense_end_coords(
        def_start_coords=def_start_coords,
        bh_defender_id=bh_defender_id,
        bh_start=bh_start,
        bh_end=bh_end,
        meet=meet,
        bh_reaches_rim=bh_reaches_rim,
        lead_ids=leads,
        offense_end_coords=offense,
        is_away_offense=is_away_offense,
        beaten_stopper_ids=beaten_stopper_ids,
        reachable_ends=reachable_ends,
        rng=rng,
    )
    merged: Dict[str, Coord] = {}
    merged.update(defense)
    merged.update(offense)
    return merged
