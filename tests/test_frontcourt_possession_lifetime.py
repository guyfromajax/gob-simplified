"""Guard: frontcourt state lives for the POSSESSION, not the turn.

`frontcourt_established` used to be a `compute_dynamic_hct_turn` local. It came
back False on every turn after the one that crossed half court, which meant:

- the 10-second rule re-armed mid-possession, and
- an over-and-back was undetectable once the establishing turn ended, because
  the only `turnover_type = "OVER_BACK"` in the backend (dynamic_hct.py, pass
  branch) is gated on the flag being True.

The flag is now carried on `game_state` the way `shot_clock_remaining` already
was: read once at the top of the engine, written back at its single exit, and
cleared ONLY at a possession boundary via `GameManager.reset_frontcourt_state`.

Two boundaries call that reset, and both are real possession changes:
`switch_possession` (the live-play flip) and the quarter-start possession
assignment in `main.simulate_quarter`, which sets `offense_team` directly on
eight branches and never routes through `switch_possession`.

The static test at the bottom is the load-bearing one. The carry is only as good
as the promise that nothing ELSE clears the flag, and that promise is not
something a sim-level test can hold down — a new `game_state[...] = False`
anywhere in the backend would silently restore the original bug on whatever
branch it sits on. So it is pinned by enumeration instead.

DURABILITY (phase 1b)
---------------------
An in-memory carry is not enough. `game_state` is rebuilt on load and restored
KEY BY KEY — `refresh_game_cache_from_db` names ~20 keys one at a time, and
another dozen concerns ride in via `restore_*_from_saved` helpers. A key with no
line in a restore path is silently dropped on every reload, and the original
Phase 1 seam test could never have caught it because it reused one live
`GameManager` and never went through a document.

So the round-trip tests below go `summarize_game_state` → dict → a FRESH
`GameManager` → the real restore function. `apply_timeout_resume_state_to_gm`
matters most: a timeout is a MID-POSSESSION boundary, so a timeout called after
crossing half court must not hand the offense a fresh 10-second count.

`test_every_possession_scoped_init_key_has_a_restore_entry` is the systemic
version. Rather than pinning today's key list, it forces every key seeded in
`_init_game_state` to be classified — so the NEXT key someone adds fails the
test until its lifetime is stated and, if it is possession-scoped, wired into a
restore path.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]

_STATE_KEYS = ("frontcourt_established", "frontcourt_ratcheted")

# The only production sites allowed to ASSIGN game_state["frontcourt_*"], as
# (file, enclosing function) -> reason.
_ALLOWED_WRITERS = {
    ("BackEnd/engine/dynamic_hct.py", "compute_dynamic_hct_turn"): (
        "The carry-out. Single write-back at the engine's one exit; every "
        "terminal reaches it via `break`."
    ),
    ("BackEnd/models/game_manager.py", "GameManager.reset_frontcourt_state"): (
        "The only clearer. Called from switch_possession and from the "
        "quarter-start possession assignment in main.simulate_quarter."
    ),
    # Restore paths. These write the flag FROM a saved document, so they carry
    # the possession's own state forward rather than resetting it. Each sits
    # beside that function's shot_clock_remaining restore.
    ("BackEnd/api/api.py", "refresh_game_cache_from_db"): (
        "Reload restore, beside shot_clock_remaining."
    ),
    ("BackEnd/api/api.py", "apply_timeout_resume_state_to_gm"): (
        "Timeout-resume restore. A timeout is a MID-POSSESSION boundary, so "
        "this must restore, never clear."
    ),
    ("BackEnd/api/api.py", "simulate_turn_endpoint"): (
        "Inline computer-timeout clock restore, beside shot_clock_remaining."
    ),
}


def _hct_game():
    """A game with real seeded rosters, ready for an HCT turn."""
    from BackEnd.models.game_manager import GameManager
    from BackEnd.utils.db_utils import build_lineup_from_mongo

    gm = GameManager("Lancaster", "Bentley-Truman")
    settings = {
        "defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2,
        "hc_trap": 5, "fc_press": 5,
    }
    gm.home_team.strategy_settings = settings.copy()
    gm.away_team.strategy_settings = settings.copy()
    gm.home_team.lineup = build_lineup_from_mongo(gm.home_team, gm.game_state)
    gm.away_team.lineup = build_lineup_from_mongo(gm.away_team, gm.game_state)
    return gm


def _hct_turn_that_establishes_frontcourt(max_seeds=24):
    """Run seeded HCT turns until one crosses half court and ends in HCO.

    Scans seeds rather than hard-coding one: the specific seed that produces an
    establishing turn is an implementation detail of the loop, and pinning it
    would make this file fail for reasons that have nothing to do with the carry.
    """
    from BackEnd.engine.dynamic_hct import compute_dynamic_hct_turn
    from BackEnd.utils import sim_random

    for seed in range(max_seeds):
        sim_random.seed(seed)
        gm = _hct_game()
        out = compute_dynamic_hct_turn(gm)
        if out.get("bail"):
            continue
        if gm.game_state.get("frontcourt_established") and out.get("result_type") == "HCO":
            return seed, gm, out
    pytest.fail(
        f"no seed in 0..{max_seeds - 1} produced an HCT turn that established "
        "frontcourt and resolved to HCO — the fixture can no longer reach the "
        "state this file exists to test"
    )


def test_hct_turn_carries_frontcourt_state_onto_game_state():
    """The establishing turn must leave the flag on game_state, not in a local."""
    seed, gm, out = _hct_turn_that_establishes_frontcourt()

    assert gm.game_state["frontcourt_established"] is True, (
        f"seed {seed}: HCT turn crossed half court and resolved to HCO but "
        "game_state['frontcourt_established'] is not True — the carry-out at "
        "dynamic_hct.py's single exit did not run"
    )
    assert gm.game_state["frontcourt_ratcheted"], (
        f"seed {seed}: offenders were ratcheted at the half-court line during the "
        "turn but the set did not survive onto game_state"
    )
    # JSON-safe: game_state is a plain dict other layers copy and hand around.
    assert isinstance(gm.game_state["frontcourt_ratcheted"], list), (
        "frontcourt_ratcheted must leave the engine as a list, not a set"
    )


def test_flag_survives_the_hct_to_hco_seam():
    """The HCT→HCO seam inside one possession must not clear the flag.

    An HCT turn resolving to `result_type == "HCO"` IS the seam: the possession
    continues, and the next turn is an HCO turn. Nothing between the two may
    reset the flag, or over-and-back detection dies exactly where it used to.
    """
    seed, gm, out = _hct_turn_that_establishes_frontcourt()
    assert out["result_type"] == "HCO"

    # The possession has NOT changed, so the flag must still be readable by
    # whatever resolves next.
    assert gm.game_state["frontcourt_established"] is True, (
        f"seed {seed}: flag lost across the HCT→HCO seam"
    )
    ratcheted_at_seam = list(gm.game_state["frontcourt_ratcheted"])
    assert ratcheted_at_seam, "ratchet emptied at the seam"

    # And a second engine invocation in the same possession must READ it back,
    # not start from False. This is the half a turn-local could never do.
    from BackEnd.engine.dynamic_hct import compute_dynamic_hct_turn

    compute_dynamic_hct_turn(gm)
    assert gm.game_state["frontcourt_established"] is True, (
        "a second HCT turn in the same possession reset the flag to False — "
        "carry-IN is not being read"
    )


def test_switch_possession_clears_frontcourt_state():
    """The live-play possession flip is a boundary; the flag must not cross it."""
    gm = _hct_game()
    gm.game_state["frontcourt_established"] = True
    gm.game_state["frontcourt_ratcheted"] = ["C", "PF", "SF", "SG"]

    gm.switch_possession()

    assert gm.game_state["frontcourt_established"] is False, (
        "switch_possession left frontcourt_established set — the new offense "
        "would start already established, with no 10-second rule and an "
        "instant over-and-back on its first backcourt pass"
    )
    assert gm.game_state["frontcourt_ratcheted"] == [], (
        "switch_possession left the ratchet populated — the new offense's "
        "off-ball players would be gated at the half-court line"
    )


def test_quarter_start_clears_frontcourt_state():
    """`main.simulate_quarter` must clear at the quarter-start possession block.

    Every branch there assigns `offense_team` directly and bypasses
    `switch_possession`, so without this call a quarter that ended with the ball
    in the frontcourt starts the next one already established.
    """
    src = (_REPO / "BackEnd" / "main.py").read_text()
    tree = ast.parse(src)

    calls = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", None) == "reset_frontcourt_state"
    ]
    assert calls, (
        "main.py no longer calls reset_frontcourt_state(). The quarter-start "
        "possession assignment sets offense_team directly on every branch and "
        "never reaches switch_possession, so the flag leaks across quarters."
    )


def test_reset_frontcourt_state_is_idempotent_and_safe_on_a_clean_state():
    gm = _hct_game()
    gm.reset_frontcourt_state()
    gm.reset_frontcourt_state()
    assert gm.game_state["frontcourt_established"] is False
    assert gm.game_state["frontcourt_ratcheted"] == []


def test_game_state_is_initialised_with_the_frontcourt_keys():
    """Present from construction, so a reader never depends on a .get default."""
    gm = _hct_game()
    for key in _STATE_KEYS:
        assert key in gm.game_state, f"game_state missing {key} at construction"
    assert gm.game_state["frontcourt_established"] is False
    assert gm.game_state["frontcourt_ratcheted"] == []


def _game_state_writers():
    """(file, function, line) for every `game_state[...]["frontcourt_*"] = ...`."""

    def owner_map(tree):
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

    for path in sorted((_REPO / "BackEnd").rglob("*.py")):
        src = path.read_text()
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        owner = owner_map(tree)
        rel = path.relative_to(_REPO).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AugAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if not isinstance(target, ast.Subscript):
                    continue
                key = target.slice
                if not (isinstance(key, ast.Constant) and key.value in _STATE_KEYS):
                    continue
                yield rel, owner.get(id(node), "<module>"), node.lineno


def test_only_possession_boundaries_write_the_frontcourt_flags():
    """Nothing may clear the flag except a possession boundary.

    This is what keeps the fix from decaying. The carry is worthless if a future
    turn-seam handler sets `game_state["frontcourt_established"] = False`; that
    reintroduces the exact original defect on whatever branch it sits on, and no
    sim-level assertion would notice until an over-and-back went uncalled.
    """
    unlisted = [
        f"{rel}:{lineno} [{fn}]"
        for rel, fn, lineno in _game_state_writers()
        if (rel, fn) not in _ALLOWED_WRITERS
    ]
    assert not unlisted, (
        "unrecorded write to the possession-scoped frontcourt flags:\n  "
        + "\n  ".join(unlisted)
        + "\n\nfrontcourt state is POSSESSION-scoped. Clear it only at a "
        "possession boundary, via GameManager.reset_frontcourt_state. If this "
        "write is legitimate, add (file, function) to _ALLOWED_WRITERS with a "
        "reason."
    )


# --- durability across a real reload (phase 1b) ---------------------------

def _saved_doc_with_frontcourt_established():
    """Run an establishing HCT turn, then SAVE through the real builder."""
    from BackEnd.utils.shared import summarize_game_state

    seed, gm, _out = _hct_turn_that_establishes_frontcourt()
    saved = summarize_game_state(gm, exclude_animations=True)
    return seed, gm, saved


def test_summarize_game_state_persists_the_frontcourt_keys():
    """The save side. Restoring a key the save never wrote is a no-op."""
    seed, gm, saved = _saved_doc_with_frontcourt_established()

    assert saved.get("frontcourt_established") is True, (
        f"seed {seed}: summarize_game_state did not persist "
        "frontcourt_established, so no restore path can recover it"
    )
    assert saved.get("frontcourt_ratcheted") == gm.game_state["frontcourt_ratcheted"], (
        "the persisted ratchet does not match live game_state"
    )
    # Must be BSON/JSON-encodable to survive the round trip through Mongo.
    assert isinstance(saved["frontcourt_ratcheted"], list)
    assert all(isinstance(p, str) for p in saved["frontcourt_ratcheted"])


def test_refresh_game_cache_from_db_restores_frontcourt_state():
    """Reload path: fresh GameManager + saved doc, through the real restore."""
    from BackEnd.api.api import refresh_game_cache_from_db

    seed, _gm, saved = _saved_doc_with_frontcourt_established()

    # A GENUINELY fresh game — this is the half the Phase 1 seam test skipped by
    # reusing `gm`, and the reason a lost key went unnoticed.
    reloaded = _hct_game()
    assert reloaded.game_state["frontcourt_established"] is False, (
        "fixture error: the fresh game must start unestablished, or the "
        "assertion below proves nothing"
    )

    refresh_game_cache_from_db(reloaded, saved)

    assert reloaded.game_state["frontcourt_established"] is True, (
        f"seed {seed}: frontcourt_established was LOST across the reload. "
        "game_state is restored key-by-key; this key needs its own line in "
        "refresh_game_cache_from_db."
    )
    assert reloaded.game_state["frontcourt_ratcheted"] == saved["frontcourt_ratcheted"], (
        "the ratchet was lost or altered across the reload"
    )


def test_timeout_resume_keeps_frontcourt_state_mid_possession():
    """A timeout is a MID-POSSESSION boundary — the flag must survive it.

    This is the sharpest case. The same team keeps the ball, so resetting here
    would let an offense wipe its own over-and-back exposure and win a fresh
    10-second count by calling timeout after crossing half court.
    """
    from BackEnd.api.api import apply_timeout_resume_state_to_gm

    seed, _gm, saved = _saved_doc_with_frontcourt_established()

    reloaded = _hct_game()
    assert reloaded.game_state["frontcourt_established"] is False

    apply_timeout_resume_state_to_gm(reloaded, saved)

    assert reloaded.game_state["frontcourt_established"] is True, (
        f"seed {seed}: a timeout reset frontcourt state mid-possession. The "
        "offense keeps the ball across a timeout, so the flag must be restored, "
        "not cleared."
    )
    assert reloaded.game_state["frontcourt_ratcheted"] == saved["frontcourt_ratcheted"]


def test_restore_tolerates_a_legacy_document_without_the_keys():
    """Docs saved before this change have neither key; that must not raise."""
    from BackEnd.api.api import refresh_game_cache_from_db

    _seed, _gm, saved = _saved_doc_with_frontcourt_established()
    legacy = {k: v for k, v in saved.items() if not k.startswith("frontcourt_")}

    reloaded = _hct_game()
    refresh_game_cache_from_db(reloaded, legacy)

    # Falls back to the init default rather than KeyError-ing or going None.
    assert reloaded.game_state["frontcourt_established"] is False
    assert reloaded.game_state["frontcourt_ratcheted"] == []


# --- the systemic guard: no possession-scoped key without a restore -------

# Keys whose value must survive a reload, i.e. the ones a restore path owns.
_MUST_BE_RESTORED = {
    "frontcourt_established": "possession-scoped; gates over-and-back + the 10s rule",
    "frontcourt_ratcheted": "possession-scoped; gates off-ball backcourt re-entry",
    "shot_clock_remaining": "possession-scoped clock",
    "clock": "game clock",
    "time_remaining": "game clock",
    "offensive_state": "which offense is live (HCO/HCT/FCP) for the possession",
    "free_throws": "mid-possession FT sequence",
    "free_throws_remaining": "mid-possession FT sequence",
    "one_and_one": "mid-possession FT sequence",
    "shooter": "mid-possession FT sequence",
    "man_defense_matchups": "user matchups chosen at a break",
    "man_defense_matchups_computer": "computer matchups chosen at a break",
    "rim_runner_by_team_id": "per-team assignment that outlives a turn",
}

# Keys that legitimately need no game_state restore, each with the reason.
_NO_RESTORE_NEEDED = {
    # Restored, but onto a different attribute than game_state.
    "offense_team": "restored via gm.offense_team (api.py, timeout resume)",
    "defense_team": "restored via gm.defense_team (api.py, timeout resume)",
    "score": "restored onto gm.score",
    "points_by_quarter": "restored onto the TeamManagers",
    "quarter": "restored onto gm.quarter",
    "team_fouls": "restored onto the TeamManagers",
    "team_timeouts": "restored onto the TeamManagers",
    "box_score": "rebuilt from player stats by get_box_score()",
    "turns": "aliases gm.turns, restored as the turn list",
    # Per-turn scratch, overwritten by the next turn that sets it.
    "foul_team": "per-turn scratch",
    "foul_type": "per-turn scratch",
    "foul_player": "per-turn scratch",
    "last_ball_handler": "per-turn scratch",
    "last_rebounder": "per-turn scratch",
    "last_rebound": "per-turn scratch",
    "last_stealer": "per-turn scratch",
    "last_turnover_player": "per-turn scratch",
    # Cumulative diagnostics. Losing one skews a calibration read-out, never a
    # basketball decision; several DO have restore_*_from_saved helpers.
    "shot_split_tracking": "diagnostic (has a restore helper)",
    "fga_by_turn_type": "diagnostic (has a restore helper)",
    "undefended_by_turn_type": "diagnostic (has a restore helper)",
    "shot_distance_bands": "diagnostic (has a restore helper)",
    "block_funnel_tracking": "diagnostic (has a restore helper)",
    "hco_shot_tier_counts": "diagnostic (has a restore helper)",
    "motion_attack_shot_tracker": "diagnostic, no restore",
    "no_defender_shots": "diagnostic, no restore",
    "no_defender_shots_breakdown": "diagnostic, no restore",
    "time_elapsed": "diagnostic counter, no decision reads it",
    # Static config, re-seeded identically on every construction.
    "uess_clock_authority_mode": "static config",
    "uess_clock_elapsed_authority": "static config",
    "uess_ownership_contract_mode": "static config",
    # Re-derived every turn before use.
    "current_playcall": "cleared by switch_possession, re-set by set_strategy_calls()",
    "defense_playcall": "cleared by switch_possession, re-set by set_strategy_calls()",
}

_SAVED_DOC_NAMES = {"saved", "_saved"}


def _init_game_state_keys():
    tree = ast.parse((_REPO / "BackEnd" / "models" / "game_manager.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_init_game_state":
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Dict):
                    return {
                        k.value
                        for k in stmt.value.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)
                    }
    raise AssertionError("could not locate the _init_game_state return dict")


def _restored_game_state_keys():
    """Keys written into game_state FROM a persisted document.

    A write counts when it sits in a function that takes a `saved` parameter
    (every `restore_*_from_saved` helper plus the two api.py restore functions)
    or when the value expression names the saved doc directly (the inline block
    in `simulate_turn_endpoint`). Constant-keyed writes are resolved, because
    the matchup keys are written as `game_state[USER_MATCHUPS_KEY]`.
    """
    trees = {}
    for path in sorted((_REPO / "BackEnd").rglob("*.py")):
        try:
            trees[path] = ast.parse(path.read_text())
        except SyntaxError:
            continue

    consts: dict[str, str] = {}
    for tree in trees.values():
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                    and isinstance(node.value.value, str):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        consts.setdefault(tgt.id, node.value.value)

    found: dict[str, list[str]] = {}
    for path, tree in trees.items():
        rel = path.relative_to(_REPO).as_posix()
        for fn in [n for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            params = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.kwonlyargs}
            from_saved_fn = bool(params & _SAVED_DOC_NAMES)
            for node in ast.walk(fn):
                if not isinstance(node, ast.Assign):
                    continue
                for tgt in node.targets:
                    if not isinstance(tgt, ast.Subscript):
                        continue
                    base = tgt.value
                    if (getattr(base, "attr", None) or getattr(base, "id", None)) != "game_state":
                        continue
                    slot = tgt.slice
                    if isinstance(slot, ast.Constant) and isinstance(slot.value, str):
                        key = slot.value
                    elif isinstance(slot, ast.Name) and slot.id in consts:
                        key = consts[slot.id]
                    else:
                        continue
                    names = {getattr(x, "id", None)
                             for x in ast.walk(node.value) if isinstance(x, ast.Name)}
                    if from_saved_fn or (names & _SAVED_DOC_NAMES):
                        found.setdefault(key, []).append(f"{rel}:{node.lineno} [{fn.name}]")
    return found


def test_every_init_game_state_key_is_classified():
    """A new key must declare its lifetime before it can ship.

    This is the systemic half. Without it, the next possession-scoped key added
    to `_init_game_state` is silently dropped on reload — exactly what happened
    to the two frontcourt keys, and to nothing else only by luck.
    """
    classified = set(_MUST_BE_RESTORED) | set(_NO_RESTORE_NEEDED)
    unclassified = sorted(_init_game_state_keys() - classified)
    assert not unclassified, (
        "new game_state key(s) with no declared lifetime:\n  "
        + "\n  ".join(unclassified)
        + "\n\ngame_state is restored KEY BY KEY, so a key nobody classified is "
        "a key silently lost on every reload. Add it to _MUST_BE_RESTORED (and "
        "wire a restore path) if its value must survive a reload, or to "
        "_NO_RESTORE_NEEDED with the reason it need not."
    )


def test_every_possession_scoped_init_key_has_a_restore_entry():
    """Declared possession-scoped ⇒ some restore path must actually write it."""
    restored = _restored_game_state_keys()
    seeded = _init_game_state_keys()

    missing = sorted(
        key for key in _MUST_BE_RESTORED
        if key in seeded and key not in restored
    )
    assert not missing, (
        "possession-scoped key(s) with NO restore entry — lost on every "
        "reload:\n  " + "\n  ".join(missing)
        + "\n\nAdd a line beside shot_clock_remaining in "
        "refresh_game_cache_from_db / apply_timeout_resume_state_to_gm, and "
        "persist it in summarize_game_state."
    )


def test_frontcourt_keys_are_restored_on_every_shot_clock_restore_path():
    """Wherever shot_clock_remaining is restored, frontcourt must be too.

    Same lifetime, same reset boundary. `apply_timeout_resume_state_to_gm` is
    the one that made this urgent: it restores the shot clock across a
    timeout — a mid-possession boundary — and dropped the frontcourt flag.
    """
    restored = _restored_game_state_keys()
    shot_clock_fns = {
        entry.split("[", 1)[1].rstrip("]")
        for entry in restored.get("shot_clock_remaining", [])
    }
    assert shot_clock_fns, "no restore site found for shot_clock_remaining"

    for key in ("frontcourt_established", "frontcourt_ratcheted"):
        fns = {entry.split("[", 1)[1].rstrip("]") for entry in restored.get(key, [])}
        missing = sorted(shot_clock_fns - fns)
        assert not missing, (
            f"{key} is not restored in: {', '.join(missing)} — "
            "these restore shot_clock_remaining, which has the same lifetime. "
            "A reload there silently clears the flag mid-possession."
        )


def test_allowed_writer_list_has_no_stale_entries():
    """A writer that moved must be re-verified, not left asserted-about."""
    live = {(rel, fn) for rel, fn, _lineno in _game_state_writers()}
    stale = sorted(key for key in _ALLOWED_WRITERS if key not in live)
    assert not stale, (
        "recorded frontcourt writer(s) no longer exist — re-verify the carry "
        "still happens, then prune:\n  "
        + "\n  ".join(f"{rel} [{fn}]" for rel, fn in stale)
    )
