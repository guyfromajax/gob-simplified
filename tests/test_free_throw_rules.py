"""The shooting-foul free-throw rule, pinned where it now lives.

Two halves.

**Unit tests** fix the rule itself. Before consolidation the count was decided
independently at each foul branch and only two of the five asked ``is_three``, so a
fouled missed three awarded two free throws instead of three on 16.9% of fouled 3PT
attempts (played) and 23.8% (sim), measured over 12 seeded games per arm. The
classification was never wrong — ``is_three`` was True and ``shot_value`` was 3 — the
branch simply never asked. These tests make the rule's shape a fact rather than a
convention, including the two cases most at risk of being "tidied" later: the and-one
that awards 1 regardless of shot value, and the 1-and-1 front end whose
``free_throws=2`` / ``remaining=1`` split is deliberate.

**A guard** in the shape of tests/test_uess_coord_contract.py and
tests/test_fb_step_builder_call_sites.py: no shot-resolution branch may set a
free-throw count without going through the helper. Consolidating the rule is only
worth doing if nothing can reintroduce a sixth hardcoded branch, and the history says
something will try — the same clause was already fixed once, at
``dynamic_hct_shot.py:832`` in 4690c97506 (2026-06-21), and never swept to the others.
That fix was invisible: it lived inside a 22-file feature commit, and the branch it
missed was three functions away in the same file.

WHAT THIS GUARD DOES NOT COVER — read before trusting it
--------------------------------------------------------
- **Non-shooting fouls.** ``phase_resolution`` decides team-foul bonus counts at ~16
  sites. ``is_three`` is meaningless there, so they are a different family and are out
  of scope by module, not by oversight. If they are ever consolidated they want their
  own census. Guard A claims nothing about any file outside
  ``_SHOT_RESOLUTION_MODULES``.
- **A count laundered through a variable.** ``n = 3 if is_three else 2`` assigned to a
  local and then handed to the applier would pass. Guard C catches the one shape that
  actually occurred (a ternary on ``made``/``is_three``), not the general case.
- **Runtime arguments.** Guard B pins that a branch calls the rule, not that it passes
  the right ``is_three``. Passing a stale or wrong ``is_three`` is a live bug this file
  cannot see; that is what the per-shot branch join in ``scratch_ft3.py`` measures.
- **Whether a branch awards anything at all.** A new shooting foul that sets no count
  is invisible here. Guard B's exact counts are the partial answer: a new branch that
  does call the rule must be classified, which puts it in front of a reviewer.

Chasing the rest with static analysis produces false positives, and a guard that cries
wolf gets deleted — which is strictly worse than this one. The residual is accepted and
belongs to review.
"""
from __future__ import annotations

import ast
import collections
import pathlib

import pytest

from BackEnd.utils.free_throw_rules import (
    BONUS_TEAM_FOULS,
    DOUBLE_BONUS_TEAM_FOULS,
    FreeThrowAward,
    apply_free_throw_award,
    bonus_foul,
    fixed_two,
    shooting_foul,
)

_REPO = pathlib.Path(__file__).resolve().parents[1]

# The three game_state keys that together describe a free-throw trip. They are one
# fact, which is why the applier writes them together.
_FT_KEYS = ("free_throws", "free_throws_remaining", "one_and_one")

# Modules that resolve a shot and can therefore see a shooting foul. Every one of
# them used to hardcode a count. This is the guard's scope.
_SHOT_RESOLUTION_MODULES = (
    "BackEnd/models/shot_manager.py",
    "BackEnd/engine/dynamic_hct_shot.py",
    "BackEnd/engine/after_steal_fast_break.py",
    "BackEnd/engine/after_steal_drive_integration.py",
)

_RULES = ("shooting_foul", "bonus_foul", "fixed_two")

# Local aliases the modules import the rule under, so the detector sees the call
# whichever spelling is used.
_RULE_ALIASES = {
    "shooting_foul": "shooting_foul",
    "ft_shooting_foul": "shooting_foul",
    "bonus_foul": "bonus_foul",
    "ft_bonus_foul": "bonus_foul",
    "fixed_two": "fixed_two",
    "ft_fixed_two": "fixed_two",
}

# ---------------------------------------------------------------------------
# Guard B allowlist: every branch that decides a free-throw count, keyed by
# (file, function, rule) -> (exact number of call sites, which branch).
#
# Counts are exact ON PURPOSE. All four shot_manager branches live inside the one
# 1,000-line resolve_shot, so keying by function alone cannot tell them apart — and a
# sixth branch added next to an existing one is precisely how this defect would come
# back. An extra call here fails and has to be classified.
# ---------------------------------------------------------------------------
_AWARD_ALLOWLIST: dict[tuple[str, str, str], tuple[int, str]] = {
    ("BackEnd/models/shot_manager.py", "ShotManager.resolve_shot", "shooting_foul"): (
        3,
        "Three shooting-foul branches: block-reconciliation (THE original defect — "
        "hardcoded 2 on a miss, ignoring is_three), and-one on the make path, and the "
        "missed-shot foul on the main HCO path.",
    ),
    ("BackEnd/models/shot_manager.py", "ShotManager.resolve_shot", "bonus_foul"): (
        1,
        "BLOCKING_FOUL. Penalised under the team-foul bonus rather than as a shot, so "
        "it carries the 1-and-1 split; below the bonus it awards nothing and the "
        "possession becomes a side inbound.",
    ),
    ("BackEnd/models/shot_manager.py", "ShotManager.resolve_shot", "fixed_two"): (
        1,
        "Final Turn attack blocking foul. Deliberately 2 regardless of shot value and "
        "with no and-one — named rather than hardcoded so it stays distinguishable "
        "from the oversight this file exists to prevent.",
    ),
    (
        "BackEnd/engine/dynamic_hct_shot.py",
        "resolve_hct_fast_break_shot",
        "shooting_foul",
    ): (
        1,
        "HCT fast break, at-the-rim attack. is_three is a literal False in this "
        "function and never reassigned, so a three cannot reach it; routed through the "
        "rule anyway so the count is right BECAUSE of the rule, not because a literal "
        "happens to match.",
    ),
    ("BackEnd/engine/dynamic_hct_shot.py", "_finalize_ab_shot", "shooting_foul"): (
        1,
        "Procedural attack-basket shot — the ONE path that classified correctly before "
        "this consolidation (fixed in 4690c97506, never swept). Real is_three here, "
        "from shot_classification.",
    ),
    (
        "BackEnd/engine/after_steal_fast_break.py",
        "_resolve_after_steal_legacy",
        "shooting_foul",
    ): (
        1,
        "After-steal fast break, drive-to-the-rim finish. is_three is a literal False "
        "in this function and never reassigned.",
    ),
    (
        "BackEnd/engine/after_steal_drive_integration.py",
        "_resolve_shot_attempt",
        "shooting_foul",
    ): (
        1,
        "After-steal drive finish. is_three is a literal False in this function and "
        "never reassigned.",
    ),
}


# ---------------------------------------------------------------------------
# Unit tests — the rule itself
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("is_three, made, expected", [
    (True, False, 3),      # THE defect: this returned 2 at three of five branches
    (False, False, 2),
    (True, True, 1),       # and-one, behind the arc
    (False, True, 1),      # and-one, inside the arc
])
def test_shooting_foul_count(is_three, made, expected):
    """A miss is worth as many free throws as the attempt was worth in points.

    The ``(True, False) -> 3`` row is the bug. Both and-one rows are asserted because
    "1 regardless of shot value" is the clause someone would plausibly "correct" to 3
    for a made three.
    """
    award = shooting_foul(is_three=is_three, made=made)
    assert award.free_throws == expected
    assert award.remaining == expected, "a shooting foul is shot in full, not in stages"
    assert award.one_and_one is False, "a shooting foul is never a 1-and-1"


def test_shooting_foul_is_keyword_only():
    """``is_three`` and ``made`` are both booleans in the same position-adjacent role.

    Positional calls would let the two be swapped silently, which turns every fouled
    make into a 2 or 3 and every fouled miss into a 1.
    """
    with pytest.raises(TypeError):
        shooting_foul(True, False)  # type: ignore[misc]


def test_bonus_foul_below_the_bonus_awards_nothing():
    """Below the bonus there are no free throws; the possession is a side inbound."""
    for team_fouls in range(0, BONUS_TEAM_FOULS):
        award = bonus_foul(team_fouls)
        assert award == FreeThrowAward(0, 0, False), f"team_fouls={team_fouls}"


@pytest.mark.parametrize("team_fouls", list(range(BONUS_TEAM_FOULS, DOUBLE_BONUS_TEAM_FOULS)))
def test_bonus_foul_one_and_one_front_end_is_preserved(team_fouls):
    """The 5-9 band is a 1-and-1, and the 2/1 split is deliberate.

    ``free_throws`` is the most the trip can produce and ``remaining`` is how many are
    shot now; the second is earned by making the first. This asymmetry is the one thing
    in the module most likely to be "cleaned up" into 2/2 or 1/1, either of which
    silently changes scoring. Hence a test per foul count in the band.
    """
    award = bonus_foul(team_fouls)
    assert award.free_throws == 2
    assert award.remaining == 1
    assert award.one_and_one is True


@pytest.mark.parametrize("team_fouls", [DOUBLE_BONUS_TEAM_FOULS, DOUBLE_BONUS_TEAM_FOULS + 5])
def test_bonus_foul_double_bonus_awards_two_straight(team_fouls):
    """At the double bonus both are shot outright — no front end to earn."""
    award = bonus_foul(team_fouls)
    assert award == FreeThrowAward(2, 2, False)


def test_fixed_two_is_two_and_distinguishable_from_an_oversight():
    """``fixed_two`` is 2 by intent, which is why it is not spelled ``2``.

    The Final Turn attack blocking foul ignores shot value and and-one. Written as a
    literal it is indistinguishable from the hardcoded 2 that caused the defect; named,
    a reader can tell "deliberately two" from "never asked".
    """
    assert fixed_two() == FreeThrowAward(2, 2, False)
    # It must NOT track is_three, or it is just shooting_foul with extra steps.
    assert fixed_two() == fixed_two()
    assert fixed_two().free_throws != shooting_foul(is_three=True, made=False).free_throws


def test_apply_free_throw_award_writes_all_three_keys_together():
    """The applier writes the whole trip, so the keys cannot drift apart.

    Before consolidation each branch set ``free_throws`` and ``free_throws_remaining``
    on separate lines, so the two could disagree — a latent second defect alongside the
    count itself.
    """
    game_state: dict = {}
    returned = apply_free_throw_award(game_state, shooting_foul(is_three=True, made=False))
    assert game_state == {"free_throws": 3, "free_throws_remaining": 3, "one_and_one": False}
    assert returned.remaining == 3, "returns the award so callers need not re-read the dict"


def test_apply_free_throw_award_clears_a_stale_one_and_one():
    """A new trip overwrites the previous trip's flag rather than inheriting it.

    ``one_and_one`` is read at free-throw resolution (phase_resolution.py), so a stale
    True would hand out a free throw nobody earned.
    """
    game_state = {"free_throws": 2, "free_throws_remaining": 1, "one_and_one": True}
    apply_free_throw_award(game_state, shooting_foul(is_three=False, made=True))
    assert game_state == {"free_throws": 1, "free_throws_remaining": 1, "one_and_one": False}


def test_award_is_immutable():
    """An award is a decision, not a scratch pad — no site may edit one in flight."""
    with pytest.raises(Exception):
        shooting_foul(is_three=True, made=False).free_throws = 2  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Static analysis helpers
# ---------------------------------------------------------------------------
def _parse(rel: str):
    src = (_REPO / rel).read_text()
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


def _is_game_state(node) -> bool:
    """True for ``game_state[...]`` and ``self.game_state[...]``, false for ``result[...]``.

    The distinction matters: ``result["one_and_one"] = True`` is a response payload, not
    a rule decision, and flagging it would make this guard cry wolf.
    """
    base = node
    while isinstance(base, ast.Subscript):
        base = base.value
    if isinstance(base, ast.Name):
        return base.id == "game_state"
    if isinstance(base, ast.Attribute):
        return base.attr == "game_state"
    return False


def _direct_ft_key_writes(modules=_SHOT_RESOLUTION_MODULES):
    """Every ``game_state["free_throws"...] = ...`` in the shot-resolution modules."""
    for rel in modules:
        src, tree = _parse(rel)
        owner = _owner_map(tree)
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                targets = [node.target]
            for target in targets:
                if not isinstance(target, ast.Subscript):
                    continue
                key = target.slice
                if not (isinstance(key, ast.Constant) and key.value in _FT_KEYS):
                    continue
                if not _is_game_state(target):
                    continue
                yield (
                    rel,
                    owner.get(id(node), "<module>"),
                    node.lineno,
                    ast.get_source_segment(src, node),
                )


def _award_call_sites(modules=_SHOT_RESOLUTION_MODULES):
    """(file, function, rule, line) for every free-throw rule call."""
    for rel in modules:
        _src, tree = _parse(rel)
        owner = _owner_map(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            rule = _RULE_ALIASES.get(name or "")
            if rule is None:
                continue
            yield rel, owner.get(id(node), "<module>"), rule, node.lineno


def _recomputed_remaining(modules=_SHOT_RESOLUTION_MODULES):
    """Local ``free_throws_remaining = <ternary>`` assignments.

    This is the exact second shape the defect took: three branches set the game_state
    count on one line and then recomputed the same number into a local on another,
    e.g. ``free_throws_remaining = 1 if made else 2``. Two independent computations of
    one fact is the defect, whether or not they currently agree. Plain-constant
    initialisers (``free_throws_remaining = 0``) are not flagged.
    """
    for rel in modules:
        src, tree = _parse(rel)
        owner = _owner_map(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.IfExp):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in _FT_KEYS:
                    yield (
                        rel,
                        owner.get(id(node), "<module>"),
                        node.lineno,
                        ast.get_source_segment(src, node),
                    )


# ---------------------------------------------------------------------------
# Guard A — no shot-resolution branch sets a count directly
# ---------------------------------------------------------------------------
def test_no_direct_free_throw_key_writes_in_shot_resolution():
    """A sixth branch hardcoding a free-throw count must fail here.

    The allowlist is deliberately EMPTY. Every one of these modules used to write the
    keys directly, and the fix removed all of them, so there is no legitimate direct
    write left to carry — which makes this the strongest form of the check.
    """
    direct = [
        f"{rel}:{lineno} [{fn}]  {src}"
        for rel, fn, lineno, src in _direct_ft_key_writes()
    ]
    assert not direct, (
        "a shot-resolution branch sets a free-throw count directly. Build a "
        "FreeThrowAward from BackEnd.utils.free_throw_rules and apply it with "
        "apply_free_throw_award() — this is the class of defect that awarded 2 free "
        "throws on a fouled three for months:\n  "
        + "\n  ".join(direct)
        + "\n\nis_three is already in scope at every one of these branches."
    )


def test_no_recomputed_free_throw_count_in_shot_resolution():
    """No branch may derive the count a second time into a local.

    Two computations of one fact is the defect even while they agree, because the next
    edit only moves one of them.
    """
    dupes = [
        f"{rel}:{lineno} [{fn}]  {src}"
        for rel, fn, lineno, src in _recomputed_remaining()
    ]
    assert not dupes, (
        "a free-throw count is computed a second time into a local. Read it off the "
        "award instead — apply_free_throw_award() returns it:\n  "
        + "\n  ".join(dupes)
    )


# ---------------------------------------------------------------------------
# Guard B — every branch that awards free throws is classified
# ---------------------------------------------------------------------------
def test_award_call_sites_match_the_allowlist():
    """A new branch calling the rule must be classified before it ships.

    Guard A stops a new branch hardcoding a count. This one stops a new branch being
    added without anyone stating which foul it represents and why its ``is_three`` is
    trustworthy — the question nobody asked at the block-reconciliation branch.
    """
    counts = collections.Counter(
        (rel, fn, rule) for rel, fn, rule, _lineno in _award_call_sites()
    )
    problems = []
    for key, count in sorted(counts.items()):
        if key not in _AWARD_ALLOWLIST:
            problems.append(f"UNLISTED  {key[0]} [{key[1]}] {key[2]}()  x{count}")
            continue
        expected, reason = _AWARD_ALLOWLIST[key]
        if count != expected:
            problems.append(
                f"DRIFTED   {key[0]} [{key[1]}] {key[2]}() expected {expected}, "
                f"found {count} — {reason}"
            )
    assert not problems, (
        "free-throw award call sites no longer match the recorded branches:\n  "
        + "\n  ".join(problems)
        + "\n\nIf this is a real new foul branch, add it to _AWARD_ALLOWLIST with a "
        "one-line statement of which foul it is and where its is_three comes from."
    )


def test_award_allowlist_has_no_stale_entries():
    """Deleting a branch is fine; it must still prune the allowlist.

    A stale entry is how an allowlist rots into a list of things nobody has looked at
    in a year.
    """
    live = {(rel, fn, rule) for rel, fn, rule, _lineno in _award_call_sites()}
    stale = sorted(key for key in _AWARD_ALLOWLIST if key not in live)
    assert not stale, (
        "allowlisted free-throw branches no longer exist — good, now delete these "
        "entries from _AWARD_ALLOWLIST:\n  "
        + "\n  ".join(f"{rel} [{fn}] {rule}()" for rel, fn, rule in stale)
    )


# ---------------------------------------------------------------------------
# Anti-vacuity — the guards above are trivially true if the detectors go blind
# ---------------------------------------------------------------------------
def test_detectors_are_not_vacuous():
    """If the detectors find nothing, every assertion above passes for free.

    The specific way this would break: a module gets renamed or the rule gets imported
    under a new alias, and Guard A keeps passing because it is looking at nothing.
    """
    for rel in _SHOT_RESOLUTION_MODULES:
        assert (_REPO / rel).exists(), f"{rel} moved — _SHOT_RESOLUTION_MODULES is stale"

    sites = list(_award_call_sites())
    assert len(sites) >= 8, (
        f"expected the known free-throw award sites, found {len(sites)} — either the "
        "rule is imported under an alias missing from _RULE_ALIASES, or branches have "
        "stopped awarding free throws"
    )
    assert {rule for _r, _f, rule, _l in sites} == set(_RULES), (
        "not every rule in the module is reachable from a real branch, so the unit "
        "tests above pin behaviour nothing calls"
    )

    # The write detector must be able to SEE a violation, not merely report none.
    _src, tree = ast.parse("game_state['free_throws'] = 2"), None
    assert isinstance(_src, ast.Module)
    planted = [
        node for node in ast.walk(_src)
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Subscript)
        and _is_game_state(node.targets[0])
    ]
    assert planted, "_is_game_state no longer recognises a game_state subscript write"
    assert not _is_game_state(ast.parse("result['one_and_one'] = True").body[0].targets[0]), (
        "_is_game_state has stopped distinguishing result payloads from game_state"
    )
