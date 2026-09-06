"""Guard: the UESS coord contract is executable, not just documented.

Motivated by a documented rule that lost ground while being documented.
`UESS_Backlog` item 7 catalogued `apply_coords_from_animations_list` as "a known
violation under remediation" at **18 sites**. It is now at **22**. The antipattern
grew *after* it was written up with a remediation plan, because the write-up
found the instances of the day and nothing stopped the next one.

This is the same lesson as §17 (see test_fb_step_builder_call_sites.py, the
template for this module): an unenforced rule gets broken on a rare branch and
hides. So the frontcourt/backcourt findings in
`projects/UESS Audits/Coord_Consumer_UESS_Audit.md` are encoded here as
assertions rather than prose.

Two guards:

**A. The half-court predicate has one implementation.** The audit found it
hand-written five times — three of those inline against the literal 50, so no
name-based search finds them — and load-bearing in four. dynamic_hct.py:819/823
holds private copies whose only importer is tests/test_dynamic_hct_violations.py:
the canonical pair in over_and_back.py:27,31 could change semantics while the
duplicate and its own green tests sat there looking maintained. Every existing
copy is allowlisted below with the audit's reason for it. A sixth fails.

**B. Audited sites keep the provenance the audit recorded.** §9.5 requires game
logic to decide from the emitter's interrupted `end.coords[p]`, never from a
`destination`/`targets` entry or a parallel positioning source. The audit
classified every frontcourt/backcourt consumer one way or the other; that table
is encoded below. A site that changes provenance fails, and so does a new
`targets[...]`/`.coords` read inside a decision in the audited modules.

F1 and F2 are in the allowlist as KNOWN, measured violations. That is deliberate:
fixing them later flips this module from allowlisted to clean by deleting an
entry, instead of requiring a rewrite.

WHAT THIS GUARD DOES NOT COVER — read before trusting it
--------------------------------------------------------
This is deliberately a *direct, greppable* check, because that is the shape the
22 sites actually accumulated in. It will not catch:

- a coord **laundered through a variable**: `spot = targets[pos]` on one line and
  `in_backcourt(spot["x"])` twenty lines later reads a destination and passes;
- a coord laundered through a **helper two frames down**, where the violating
  read lives in a callee this module never inspects;
- provenance that is only wrong at **runtime** — e.g. an `off_coords` entry that
  a *caller* populated from a destination. Guard B pins the expression, not the
  value's history;
- the `apply_coords_from_animations_list` family itself (item 7's 22 sites).
  Those are assignments, not decision reads, and want their own census;
- anything outside the audited modules listed in `_AUDITED_MODULES`.

Chasing those with static analysis produces false positives, and a guard that
cries wolf gets deleted — which is strictly worse than this one. The residual is
accepted and belongs to review, not to this file.
"""
from __future__ import annotations

import ast
import collections
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[1]

# The half-court line. `crossed_half_court` is `x <= 50 if away else x >= 50`;
# inline copies write the same comparison against 50 or 50.0.
_HALF_COURT_VALUES = (50, 50.0)
_ORDER_OPS = (ast.Lt, ast.Gt, ast.LtE, ast.GtE)

_CANONICAL = ("BackEnd/engine/over_and_back.py", "crossed_half_court")

# The private duplicate the audit flagged as dead-but-test-pinned (F3).
_DEAD_DUPLICATE = ("_crossed_half_court", "_in_backcourt")

# ---------------------------------------------------------------------------
# Guard A allowlist: every live `<x-expr> <order-op> 50` in BackEnd/, keyed by
# (file, enclosing function) -> (expected number of comparisons, reason).
#
# Counts are exact ON PURPOSE. A ternary predicate is two comparisons, so
# `crossed_half_court` is 2, not 1 — and pinning the count means an extra copy
# added INSIDE an already-allowlisted function fails too, not just a new file.
#
# Reasons are the audit's own classification. The audit says "five copies"; this
# allowlist has seven owners because it counts the two byte-near-identical PG
# clamps as the separate files they are, and because it also has to carry the
# one comparison the audit examined and ruled OUT (shot_micro_movements).
# ---------------------------------------------------------------------------
_HALF_COURT_ALLOWLIST: dict[tuple[str, str], tuple[int, str]] = {
    ("BackEnd/engine/over_and_back.py", "crossed_half_court"): (
        2,
        "CANONICAL. The one implementation every other site should call.",
    ),
    ("BackEnd/engine/dynamic_hct.py", "_crossed_half_court"): (
        2,
        "F3: private duplicate, verified DEAD in production — only importer is "
        "tests/test_dynamic_hct_violations.py. Kept allowlisted, not blessed; "
        "see test_dead_duplicate_predicate_has_no_production_caller.",
    ),
    ("BackEnd/engine/covert_release_step_emitter.py", "_ball_crossed_midcourt_toward_basket"): (
        2,
        "F4: gates the 'Great Stop!' callout. Read itself is COMPLIANT "
        "(outcome_step['end']['coords']); listed only as a duplicate predicate.",
    ),
    ("BackEnd/engine/skeleton_step_emitter.py", "_append_post_steal_hco_transition"): (
        2,
        "Compliant: reads start_coords[stealer_id] (prior emitted end) and clamps "
        "stealer_end_x — the END, not a destination. Inlined per-branch.",
    ),
    ("BackEnd/utils/reset_step_helper.py", "_pick_pg_target"): (
        2,
        "Compliant: reads start_coords[bh_id]; clamps the PG target, which the PG "
        "reaches exactly because he is the step's gate player.",
    ),
    ("BackEnd/utils/transition_bridge.py", "_pick_pg_receive_target"): (
        2,
        "Compliant, and byte-near-identical to _pick_pg_target above — the "
        "duplication the audit flagged, in two files.",
    ),
    ("BackEnd/engine/shot_micro_movements.py", "_infer_away_offense_from_display_coord"): (
        1,
        "RULED OUT by the audit: a tie-breaker used only when the two rim "
        "distances are within 0.5. Infers which FRAME a coord is in, not "
        "frontcourt status. Allowlisted so the detector stays honest, not blessed.",
    ),
}

# ---------------------------------------------------------------------------
# Guard B. Modules whose frontcourt/backcourt consumers the audit enumerated.
# Guard B claims nothing about any file not in this tuple.
# ---------------------------------------------------------------------------
_AUDITED_MODULES = (
    "BackEnd/engine/dynamic_hct.py",
    "BackEnd/engine/over_and_back.py",
    # Added 2026-09-06: HCO freelance became a frontcourt decision site when the
    # avoidance clamp and the half-court-aware collision offset landed. Without
    # it the audit had a blind spot exactly where the new logic lives.
    "BackEnd/engine/motion_freelance.py",
    "BackEnd/engine/fcp_offball_attack.py",
)

# Decision predicates whose coord argument the audit traced.
_PREDICATES = (
    "in_backcourt",
    "crossed_half_court",
    "_in_backcourt",
    "_crossed_half_court",
    "update_frontcourt_established",
    "is_over_and_back_pass",
    "should_hold_instead_of_backcourt_pass",
    "cross_half_urgency_target",
    "gate_offense_backcourt_reentry",
)

# Coord containers, in PRIORITY order: destinations first, so a co-occurring
# compliant read can never mask a destination read in the same expression.
# More specific names precede their substrings (`off_targets` before `targets`).
_PROVENANCE_TOKENS = (
    ("off_targets", "DESTINATION"),
    ("def_targets", "DESTINATION"),
    ("targets", "DESTINATION"),
    ("destination", "DESTINATION"),
    ("off_coords", "LIVE_INTERRUPTED_END"),
    ("def_coords", "LIVE_INTERRUPTED_END"),
    ("start_coords", "EMITTED_STEP_START"),
    ("end_coords", "EMITTED_STEP_END"),
    ("prior_coords", "PRIOR_TURN_FINAL_COORDS"),
    ("bh_xy", "LIVE_INTERRUPTED_END"),
    ("receiver_xy", "CALLER_SUPPLIED_XY"),
    ("xy", "CALLER_SUPPLIED_XY"),
    (".coords", "ANIMATOR_ROW_END"),
)

# ---------------------------------------------------------------------------
# Guard B allowlist: the audit's provenance table, keyed by
# (file, function, predicate, provenance) -> (verdict, reason).
#
# VERDICTS: "OK" satisfies §9.5. "VIOLATION" does not and is knowingly carried.
# "PARAM" is a coord-agnostic primitive whose provenance is the caller's.
# ---------------------------------------------------------------------------
_OK, _VIOLATION, _PARAM = "OK", "VIOLATION", "PARAM"

_PROVENANCE_ALLOWLIST: dict[tuple[str, str, str, str], tuple[str, str]] = {
    # --- The one live §9.5 violation, knowingly carried. Do not "fix" by
    # --- editing this entry; fix the call site and delete the entry.
    (
        "BackEnd/engine/dynamic_hct.py",
        "_recover_defense_targets",
        "in_backcourt",
        "DESTINATION",
    ): (
        _VIOLATION,
        "F1 (HIGH). Decides 'stranded in backcourt' from targets[pos]['x'] — the "
        "beat's authored destination from play.defense_targets(...) — while the "
        "render-faithful def_coords[pos] is the function's own second parameter. "
        "MEASURED 4.8% and 4.5% per-defender flip (6-game/1,920-verdict and "
        "12-game/3,550-verdict samples); 18.3% of FC-established recovery calls "
        "compute a different stranded SET. Directional: under-detects backcourt "
        "defenders by ~40%, so the recovery overlay fails to fire for defenders "
        "the FE is showing in the backcourt.",
    ),
    # --- Compliant frontcourt/backcourt consumers.
    (
        "BackEnd/engine/dynamic_hct.py",
        "_apply_cross_half_urgency",
        "in_backcourt",
        "LIVE_INTERRUPTED_END",
    ): (_OK, "Reads off_coords[pos]['x'], the prior beat's interrupted end."),
    (
        "BackEnd/engine/dynamic_hct.py",
        "_apply_cross_half_urgency",
        "cross_half_urgency_target",
        "LIVE_INTERRUPTED_END",
    ): (_OK, "Target generation seeded from the interrupted end."),
    (
        "BackEnd/engine/dynamic_hct.py",
        "compute_dynamic_hct_turn._gate_offense_backcourt",
        "gate_offense_backcourt_reentry",
        "LIVE_INTERRUPTED_END",
    ): (
        _OK,
        "Reads off_coords and mutates it BEFORE _segment serialises it, so the "
        "HALF_COURT_X ratchet becomes the emitted end rather than diverging.",
    ),
    (
        "BackEnd/engine/dynamic_hct.py",
        "compute_dynamic_hct_turn",
        "update_frontcourt_established",
        "LIVE_INTERRUPTED_END",
    ): (
        _OK,
        "Two sites. The BH beat reads bh_xy (= off_coords[bh_pos], written from "
        "_interrupted_coord); the catch-spot beat reads off_coords[receiver_pos] "
        "after _pass_segment is built. The 10-second violation inherits this.",
    ),
    (
        "BackEnd/engine/dynamic_hct.py",
        "compute_dynamic_hct_turn",
        "should_hold_instead_of_backcourt_pass",
        "LIVE_INTERRUPTED_END",
    ): (
        _OK,
        "Reads off_coords[receiver_pos]; the receiver is excluded from the beat's "
        "movement, so his coord IS his rendered end.",
    ),
    (
        "BackEnd/engine/dynamic_hct.py",
        "compute_dynamic_hct_turn",
        "is_over_and_back_pass",
        "LIVE_INTERRUPTED_END",
    ): (
        _OK,
        "The over-and-back TURNOVER. Reads the same off_coords[receiver_pos] the "
        "pass segment serialised; _gate_offense_backcourt skips the receiver so "
        "the ratchet cannot suppress detection.",
    ),
    (
        "BackEnd/engine/fcp_offball_attack.py",
        "FcpOffballAttackState.apply_cross_half_urgency",
        "in_backcourt",
        "LIVE_INTERRUPTED_END",
    ): (_OK, "FCP mirror of _apply_cross_half_urgency; off_coords written via interrupted_fn."),
    (
        "BackEnd/engine/fcp_offball_attack.py",
        "FcpOffballAttackState.apply_cross_half_urgency",
        "cross_half_urgency_target",
        "LIVE_INTERRUPTED_END",
    ): (_OK, "Target generation seeded from the interrupted end."),
    # --- Coord-agnostic primitives: they take x/xy as a parameter and hold no
    # --- coord source, which is why this audit is a CALL-SITE audit.
    (
        "BackEnd/engine/over_and_back.py",
        "in_backcourt",
        "crossed_half_court",
        _PARAM,
    ): (_PARAM, "Canonical complement; provenance belongs to the caller."),
    (
        "BackEnd/engine/over_and_back.py",
        "update_frontcourt_established",
        "crossed_half_court",
        "CALLER_SUPPLIED_XY",
    ): (_PARAM, "Reads the xy dict the caller passed."),
    (
        "BackEnd/engine/over_and_back.py",
        "is_over_and_back_pass",
        "in_backcourt",
        "CALLER_SUPPLIED_XY",
    ): (_PARAM, "Reads the receiver_xy dict the caller passed."),
    (
        "BackEnd/engine/over_and_back.py",
        "should_hold_instead_of_backcourt_pass",
        "is_over_and_back_pass",
        "CALLER_SUPPLIED_XY",
    ): (_PARAM, "Reads the receiver_xy dict the caller passed."),
    (
        "BackEnd/engine/over_and_back.py",
        "gate_offense_backcourt_reentry",
        "in_backcourt",
        _PARAM,
    ): (_PARAM, "Ratchet reads the local x lifted from off_coords[pos]."),
    (
        "BackEnd/engine/motion_freelance.py",
        "_resolve_collisions",
        "in_backcourt",
        _PARAM,
    ): (
        _PARAM,
        "Two sites, same provenance: the group's own collided coord `cx` (lifted "
        "from pos_actions[pos]['coords'], the beat's authored end) and the "
        "derived `rear` offset. Keeps a frontcourt-side collision group from "
        "being offset across the line.",
    ),
    (
        "BackEnd/engine/over_and_back.py",
        "clamp_target_to_frontcourt",
        "in_backcourt",
        "CALLER_SUPPLIED_XY",
    ): (
        _PARAM,
        "Avoidance clamp; reads the mover's CURRENT xy the caller passed. Gates "
        "on current side by design, NOT on frontcourt_established: at "
        "target-selection time he has not crossed back yet, so his side is a "
        "sound proxy. Unsound for detection — see the docstring.",
    ),
    (
        "BackEnd/engine/dynamic_hct.py",
        "_in_backcourt",
        "_crossed_half_court",
        _PARAM,
    ): (_PARAM, "F3's dead private duplicate calling its own dead partner."),
}

# ---------------------------------------------------------------------------
# Guard B2 allowlist: destination / animator-row-end reads inside a decision
# expression, in the audited modules. Keyed by (file, function, expression).
# ---------------------------------------------------------------------------
_DESTINATION_READ_ALLOWLIST: dict[tuple[str, str, str], str] = {
    (
        "BackEnd/engine/dynamic_hct.py",
        "_recover_defense_targets",
        'targets[pos]["x"]',
    ): (
        "F1 (HIGH), measured 4.8%/4.5% per-defender flip, 18.3% of calls flip the "
        "stranded SET. Same finding as the _PROVENANCE_ALLOWLIST entry."
    ),
    (
        "BackEnd/engine/dynamic_hct.py",
        "_recover_defense_targets",
        "targets[dpos]",
    ): (
        "F2 (MED-HIGH). The 'covered' inference compares a DESTINATION against a "
        "live off coord inside one expression, while the sibling read 9 lines "
        "below uses def_coords for the same distance question. MEASURED 11.7% of "
        "16,835 defender/offender pairs flip the <= 8.0 radius test."
    ),
}

_DESTINATION_CONTAINERS = ("targets", "off_targets", "def_targets")
_DECISION_CALLS = ("_euclid", "in_backcourt", "crossed_half_court",
                   "_in_backcourt", "_crossed_half_court")


# ---------------------------------------------------------------------------
# Static analysis helpers
# ---------------------------------------------------------------------------
def _backend_files():
    return sorted((_REPO / "BackEnd").rglob("*.py"))


def _parse(path):
    src = path.read_text()
    return src, ast.parse(src)


def _owner_map(tree):
    """node id -> dotted name of the function/class containing it."""
    owner: dict[int, str] = {}

    def walk(node, stack):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                nested = stack + [child.name]
                owner[id(child)] = ".".join(nested)
                walk(child, nested)
            else:
                owner[id(child)] = ".".join(stack) or "<module>"
                walk(child, stack)

    walk(tree, [])
    return owner


def _mentions_x(node):
    """True when the expression reads an x coordinate in any of its spellings:
    the bare name `x`, a `["x"]` subscript, or an `.x` attribute."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id == "x":
            return True
        if isinstance(sub, ast.Constant) and sub.value == "x":
            return True
        if isinstance(sub, ast.Attribute) and sub.attr == "x":
            return True
    return False


def _half_court_comparisons():
    """Every `<x-expr> <order-op> 50` in BackEnd/, as (file, function, line, src).

    This is the detector no name-based grep can replace: three of the five copies
    are written inline against the literal, with no `half_court` token anywhere.
    """
    for path in _backend_files():
        try:
            src, tree = _parse(path)
        except SyntaxError:
            continue
        owner = _owner_map(tree)
        rel = path.relative_to(_REPO).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare) or len(node.ops) != 1:
                continue
            if not isinstance(node.ops[0], _ORDER_OPS):
                continue
            right = node.comparators[0]
            if not isinstance(right, ast.Constant) or isinstance(right.value, bool):
                continue
            if right.value not in _HALF_COURT_VALUES:
                continue
            if not _mentions_x(node.left):
                continue
            yield (
                rel,
                owner.get(id(node), "<module>"),
                node.lineno,
                ast.get_source_segment(src, node),
            )


def _provenance_of(segment: str) -> str:
    """Classify which coord container an expression reads.

    Destinations are checked FIRST so that an expression mixing a destination
    with a compliant read (F2's `_euclid(targets[dpos], off_coords[op])`) is
    classified by its worst read, not its best.
    """
    for token, verdict in _PROVENANCE_TOKENS:
        if token in segment:
            return verdict
    return _PARAM


def _predicate_call_sites(modules=_AUDITED_MODULES):
    """(file, function, predicate, provenance, line) for each decision call."""
    for rel in modules:
        path = _REPO / rel
        if not path.exists():
            continue
        src, tree = _parse(path)
        owner = _owner_map(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name not in _PREDICATES:
                continue
            coord_args = " ".join(
                ast.get_source_segment(src, arg) or "" for arg in node.args
            )
            yield (
                rel,
                owner.get(id(node), "<module>"),
                name,
                _provenance_of(coord_args),
                node.lineno,
            )


def _destination_reads(modules=_AUDITED_MODULES):
    """Destination/animator reads that feed a comparison or a distance call.

    Keys on the `targets[...]` subscript node itself, not the enclosing
    expression, so a single read nested inside both a Call and a Compare is
    reported once rather than twice. `targets[pos]["x"]` is likewise reported
    once, at its widest span, rather than as both itself and its `targets[pos]`
    base — they are one read, and reporting the base would make the allowlist
    carry a key nobody would recognise from the audit.
    """
    for rel in modules:
        path = _REPO / rel
        if not path.exists():
            continue
        src, tree = _parse(path)
        owner = _owner_map(tree)

        decision_nodes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                decision_nodes.append(node)
            elif isinstance(node, ast.Call) and getattr(node.func, "id", None) in _DECISION_CALLS:
                decision_nodes.append(node)

        widest: dict[tuple[int, int], ast.AST] = {}
        for decision in decision_nodes:
            for sub in ast.walk(decision):
                if isinstance(sub, ast.Subscript):
                    base = sub.value
                    while isinstance(base, ast.Subscript):
                        base = base.value
                    if not (isinstance(base, ast.Name)
                            and base.id in _DESTINATION_CONTAINERS):
                        continue
                elif isinstance(sub, ast.Attribute) and sub.attr == "coords":
                    pass
                else:
                    continue
                start = (sub.lineno, sub.col_offset)
                prior = widest.get(start)
                if prior is None or sub.end_col_offset > prior.end_col_offset:
                    widest[start] = sub

        for _start, sub in sorted(widest.items()):
            yield (
                rel,
                owner.get(id(sub), "<module>"),
                ast.get_source_segment(src, sub),
                sub.lineno,
            )


# ---------------------------------------------------------------------------
# Guard A — the half-court predicate has one implementation
# ---------------------------------------------------------------------------
def test_no_unlisted_half_court_predicate_implementation():
    """A sixth hand-written copy of the half-court predicate must fail here.

    The audit's five copies are allowlisted with its own classification. This
    is the check that makes "the predicate has one implementation" a fact rather
    than an aspiration: three of the existing copies are inline against the
    literal 50, so nobody was ever going to find the sixth by grepping.
    """
    unlisted = [
        f"{rel}:{lineno} [{fn}]  {src}"
        for rel, fn, lineno, src in _half_court_comparisons()
        if (rel, fn) not in _HALF_COURT_ALLOWLIST
    ]
    assert not unlisted, (
        "new hand-written half-court predicate(s) — call "
        "over_and_back.crossed_half_court() instead of re-deriving `x vs 50`:\n  "
        + "\n  ".join(unlisted)
        + "\n\nIf this really must be its own copy, add (file, function) to "
        "_HALF_COURT_ALLOWLIST with a one-line reason and say why the canonical "
        "predicate cannot be called."
    )


def test_half_court_allowlist_counts_are_exact():
    """An extra copy inside an ALREADY-allowlisted function must fail too.

    Without this, the guard above is bypassed by adding the sixth copy next to
    an existing one — which is exactly how item 7 went from 18 sites to 22.
    """
    counts = collections.Counter(
        (rel, fn) for rel, fn, _lineno, _src in _half_court_comparisons()
    )
    drifted = []
    for owner, (expected, reason) in _HALF_COURT_ALLOWLIST.items():
        actual = counts.get(owner, 0)
        if actual != expected:
            drifted.append(
                f"{owner[0]} [{owner[1]}] expected {expected} comparison(s), "
                f"found {actual} — {reason}"
            )
    assert not drifted, (
        "half-court comparison counts drifted from the audit:\n  "
        + "\n  ".join(drifted)
    )


def test_half_court_allowlist_has_no_stale_entries():
    """Deleting a duplicate is good news; it must still prune the allowlist.

    A stale entry is how an allowlist rots into a list of things nobody has
    looked at in a year.
    """
    live = {(rel, fn) for rel, fn, _lineno, _src in _half_court_comparisons()}
    stale = sorted(owner for owner in _HALF_COURT_ALLOWLIST if owner not in live)
    assert not stale, (
        "allowlisted half-court copies no longer exist — good, now delete these "
        "entries from _HALF_COURT_ALLOWLIST:\n  "
        + "\n  ".join(f"{rel} [{fn}]" for rel, fn in stale)
    )


def test_canonical_half_court_predicate_exists():
    """Sanity: the guards above are vacuous if the canonical pair moved."""
    from BackEnd.engine import over_and_back

    assert callable(over_and_back.crossed_half_court)
    assert callable(over_and_back.in_backcourt)
    # The complement must stay a complement, or the two names diverge silently.
    for away in (False, True):
        for x in (0, 25, 49, 50, 51, 75, 100):
            assert over_and_back.in_backcourt(x, away) != over_and_back.crossed_half_court(x, away)
    live = {(rel, fn) for rel, fn, _lineno, _src in _half_court_comparisons()}
    assert _CANONICAL in live, (
        "the canonical predicate no longer compares against 50 — either it moved "
        "or the detector in _half_court_comparisons() has gone blind."
    )


def test_dead_duplicate_predicate_has_no_production_caller():
    """F3: dynamic_hct's private copies must stay unused by production code.

    The audit's point was not that the duplicate is wrong today — it agrees with
    the canonical pair. It is that its ONLY importer is
    tests/test_dynamic_hct_violations.py, so the duplicate is pinned by its own
    tests and looks maintained. The moment a caller inside that 3,400-line module
    reaches for the local name, the divergence becomes live and silent. This is
    the check that turns "dead code" from an observation into a guarantee.
    """
    callers = []
    for path in _backend_files():
        try:
            src, tree = _parse(path)
        except SyntaxError:
            continue
        owner = _owner_map(tree)
        rel = path.relative_to(_REPO).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Name) or node.id not in _DEAD_DUPLICATE:
                continue
            if not isinstance(node.ctx, ast.Load):
                continue
            # `_in_backcourt` delegating to `_crossed_half_court` is internal.
            if owner.get(id(node)) in _DEAD_DUPLICATE:
                continue
            callers.append(f"{rel}:{node.lineno} [{owner.get(id(node))}] uses {node.id}")
    assert not callers, (
        "production code now calls dynamic_hct's PRIVATE half-court duplicate "
        "instead of over_and_back's canonical pair. Nothing keeps the two in "
        "agreement — the duplicate's only tests test the duplicate:\n  "
        + "\n  ".join(callers)
    )


# ---------------------------------------------------------------------------
# Guard B — audited sites keep the provenance the audit recorded
# ---------------------------------------------------------------------------
def test_frontcourt_decision_sites_keep_recorded_provenance():
    """Every frontcourt/backcourt decision reads the coord the audit recorded.

    Fails two ways, both wanted: an audited site that SWAPS its coord source
    (say `off_coords[receiver_pos]` -> `off_targets[receiver_pos]`, turning the
    over-and-back turnover into a destination read), and a brand-new call site
    nobody classified.
    """
    unlisted = []
    for rel, fn, predicate, provenance, lineno in _predicate_call_sites():
        if (rel, fn, predicate, provenance) not in _PROVENANCE_ALLOWLIST:
            unlisted.append(
                f"{rel}:{lineno} [{fn}] {predicate}(...) reads {provenance}"
            )
    assert not unlisted, (
        "frontcourt/backcourt decision site(s) with unrecorded coord provenance. "
        "UESS §9.5: decide from the emitter's interrupted end.coords[p], never "
        "from a destination or a parallel positioning source:\n  "
        + "\n  ".join(unlisted)
        + "\n\nIf this is correct, add it to _PROVENANCE_ALLOWLIST and update "
        "projects/UESS Audits/Coord_Consumer_UESS_Audit.md to match."
    )


def test_no_unlisted_destination_reads_in_frontcourt_decisions():
    """No new `targets[...]`/`.coords` read may feed a decision in these modules.

    F1 and F2 are allowlisted with their measured flip rates. That is the whole
    design: when someone fixes F1, this test tells them to delete the entry, and
    the module goes from "two known violations" to "clean" without a rewrite.
    """
    unlisted = []
    for rel, fn, expr, lineno in _destination_reads():
        if (rel, fn, expr) not in _DESTINATION_READ_ALLOWLIST:
            unlisted.append(f"{rel}:{lineno} [{fn}]  {expr}")
    assert not unlisted, (
        "a destination/animator coord now feeds a frontcourt decision — §9.5 "
        "requires the emitter's interrupted end.coords[p]:\n  "
        + "\n  ".join(unlisted)
        + "\n\nThe render-faithful coord is usually already in scope (F1's is the "
        "function's own `def_coords` parameter). Fix the read rather than "
        "allowlisting it."
    )


def test_known_violations_are_still_present_or_allowlist_pruned():
    """When F1/F2 get fixed, this fails and tells you to delete the entry.

    Keeps the allowlist from outliving the defect it documents, and makes the
    fix visible here instead of silently loosening the guard.
    """
    live = {(rel, fn, expr) for rel, fn, expr, _lineno in _destination_reads()}
    fixed = sorted(key for key in _DESTINATION_READ_ALLOWLIST if key not in live)
    assert not fixed, (
        "allowlisted §9.5 violation(s) are gone — good. Now delete them from "
        "_DESTINATION_READ_ALLOWLIST (and the matching _PROVENANCE_ALLOWLIST "
        "entry), and mark the finding closed in the audit:\n  "
        + "\n  ".join(f"{rel} [{fn}]  {expr}" for rel, fn, expr in fixed)
    )


def test_provenance_allowlist_has_no_stale_entries():
    """Same rot check for the provenance table."""
    live = {
        (rel, fn, predicate, provenance)
        for rel, fn, predicate, provenance, _lineno in _predicate_call_sites()
    }
    stale = sorted(key for key in _PROVENANCE_ALLOWLIST if key not in live)
    assert not stale, (
        "recorded provenance entries match no live call site — the sites moved "
        "or changed shape. Re-verify against the audit, then prune:\n  "
        + "\n  ".join(f"{rel} [{fn}] {pred}(...) {prov}" for rel, fn, pred, prov in stale)
    )


def test_guard_b_is_not_vacuous():
    """Sanity: if the detectors find nothing, every assertion above is trivially
    true. §17's lesson applies to the guard itself."""
    sites = list(_predicate_call_sites())
    assert len(sites) >= 15, f"expected the audited frontcourt call sites, found {len(sites)}"
    assert any(prov == "DESTINATION" for _r, _f, _p, prov, _l in sites), (
        "F1's destination read vanished from the detector's view — either it was "
        "fixed (delete its allowlist entries) or the detector broke."
    )
    assert list(_destination_reads()), "destination-read census found nothing"
