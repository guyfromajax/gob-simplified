"""
⏱️ SIM PERF INSTRUMENTATION — MEASUREMENT ONLY. Safe to delete wholesale.

Nothing in the sim path imports this module. It is installed from the outside
(scripts/perf_sim_baseline.py) by calling `install()`, which monkeypatches a
fixed list of functions with timing spans. That means:

  * zero probe code lives in main.py / game_manager.py / turn_manager.py / animator.py
  * removing the instrumentation = deleting this file + the harness script
  * it is inert unless GOB_SIM_PROFILE=1 is set BEFORE install() is called

Accounting model
----------------
Spans nest. Each span records EXCLUSIVE (self) time: elapsed minus the time
spent inside child spans. Exclusive times across all phases therefore sum to
the wall time of the outermost span, so the phase table adds to 100% with no
double counting. Inclusive time is also tracked for context (a recursive phase
will over-count inclusively; exclusive stays correct).

State is thread-local because the CPU week runs games in a ThreadPoolExecutor.
Per-thread tables are merged at report time.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from contextlib import contextmanager

ENABLED = os.environ.get("GOB_SIM_PROFILE") == "1"

_local = threading.local()
_tables: list[dict] = []
_tables_lock = threading.Lock()
_installed = False


def _state():
    st = getattr(_local, "st", None)
    if st is None:
        st = {"stack": [], "totals": {}}
        _local.st = st
        with _tables_lock:
            _tables.append(st["totals"])
    return st


@contextmanager
def span(name: str):
    """Time a named phase. No-op (a bare yield) when profiling is disabled."""
    if not ENABLED:
        yield
        return
    st = _state()
    stack = st["stack"]
    frame = [name, time.perf_counter(), 0.0]  # name, start, child_time
    stack.append(frame)
    try:
        yield
    finally:
        elapsed = time.perf_counter() - frame[1]
        excl = elapsed - frame[2]
        row = st["totals"].setdefault(name, [0.0, 0.0, 0])
        row[0] += excl
        row[1] += elapsed
        row[2] += 1
        stack.pop()
        if stack:
            stack[-1][2] += elapsed


def reset():
    """Clear all accumulated timings across every thread."""
    with _tables_lock:
        for t in _tables:
            t.clear()


def snapshot() -> dict:
    """Merge per-thread tables -> {phase: {"self_s","incl_s","calls"}}."""
    merged: dict[str, list] = {}
    with _tables_lock:
        tables = list(_tables)
    for t in tables:
        for name, (self_s, incl_s, calls) in list(t.items()):
            row = merged.setdefault(name, [0.0, 0.0, 0])
            row[0] += self_s
            row[1] += incl_s
            row[2] += calls
    return {
        k: {"self_s": v[0], "incl_s": v[1], "calls": v[2]}
        for k, v in sorted(merged.items(), key=lambda kv: -kv[1][0])
    }


# ---------------------------------------------------------------------------
# patching helpers
# ---------------------------------------------------------------------------

def _wrap_callable(fn, name):
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with span(name):
            return fn(*args, **kwargs)

    wrapper.__gob_profiled__ = True
    return wrapper


def _patch_method(cls, attr, name):
    fn = getattr(cls, attr, None)
    if fn is None or getattr(fn, "__gob_profiled__", False):
        return False
    setattr(cls, attr, _wrap_callable(fn, name))
    return True


def _patch_db_method(cls, attr, prefix, coll_of):
    """
    Like _patch_method but names the span per collection, e.g.
    `db.read.plays.find_one` — so the breakdown names the exact query, not just
    a lump "database" number.
    """
    import functools

    fn = getattr(cls, attr, None)
    if fn is None or getattr(fn, "__gob_profiled__", False):
        return False

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            coll = coll_of(self)
        except Exception:
            coll = "?"
        with span(f"{prefix}.{coll}.{attr}"):
            return fn(self, *args, **kwargs)

    wrapper.__gob_profiled__ = True
    setattr(cls, attr, wrapper)
    return True


def _patch_function(module_path, attr, name):
    """
    Patch a module-level function AND rebind every other module that imported
    it by value (`from x import y`), which is how most of this codebase imports.
    """
    import importlib

    try:
        mod = importlib.import_module(module_path)
    except Exception:
        return False
    orig = getattr(mod, attr, None)
    if orig is None or getattr(orig, "__gob_profiled__", False):
        return False
    wrapped = _wrap_callable(orig, name)
    setattr(mod, attr, wrapped)
    # rebind aliases already imported elsewhere
    for m in list(sys.modules.values()):
        if m is None or m is mod:
            continue
        try:
            if getattr(m, attr, None) is orig:
                setattr(m, attr, wrapped)
        except Exception:
            pass
    return True


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------

_DB_READ = ("find_one", "find", "count_documents", "aggregate", "distinct")
_DB_WRITE = (
    "update_one", "update_many", "insert_one", "insert_many",
    "bulk_write", "replace_one", "delete_one", "delete_many",
    "find_one_and_update", "create_index",
)

_ANIM_METHODS = [
    ("capture_halfcourt_animation", "anim.capture_halfcourt"),
    ("capture_fast_break_animation", "anim.capture_fast_break"),
    ("capture_free_throw_animation", "anim.capture_free_throw"),
    ("skeleton_to_animations", "anim.skeleton_to_animations"),
    ("_build_all_animations", "anim.build_all_animations"),
    ("compute_defender_grid", "anim.compute_defender_grid"),
    ("_position_fcp_defenders", "anim.position_defenders"),
    ("_position_hct_zone_defenders", "anim.position_defenders"),
    ("_position_zone_defenders", "anim.position_defenders"),
    ("_position_standard_defenders", "anim.position_defenders"),
]

_STEP_EMITTERS = [
    ("BackEnd.engine.skeleton_step_emitter", "build_skeleton_animation_steps"),
    ("BackEnd.engine.hct_step_emitter", "build_hct_animation_steps"),
    ("BackEnd.engine.dynamic_hct_step_emitter", "build_dynamic_hct_animation_steps"),
    ("BackEnd.engine.dynamic_fcp_step_emitter", "build_dynamic_fcp_animation_steps"),
    ("BackEnd.engine.rim_runner_step_emitter", "build_rim_runner_animation_steps"),
    ("BackEnd.engine.triangle_step_emitter", "build_triangle_animation_steps"),
    ("BackEnd.engine.dreb_step_emitter", "build_dreb_animation_steps"),
    ("BackEnd.engine.oreb_step_emitter", "build_oreb_animation_steps"),
    ("BackEnd.engine.ft_step_emitter", "build_ft_animation_steps"),
    ("BackEnd.engine.covert_release_step_emitter", "build_covert_release_animation_steps"),
    ("BackEnd.engine.fb_drive_step_emitter", "build_fb_drive_resolution_steps"),
    ("BackEnd.engine.fb_outlet_pass_step_emitter", "build_fb_outlet_pass_step"),
    ("BackEnd.engine.after_steal_fast_break_step_emitter",
     "build_after_steal_fast_break_animation_steps"),
]

_TURN_HANDLERS = [
    ("resolve_half_court_offense", "core.hco"),
    ("resolve_fast_break", "core.fast_break"),
    ("resolve_free_throw", "core.free_throw"),
    ("resolve_turnover", "core.turnover"),
    ("resolve_final_turn_shot", "core.final_turn_shot"),
    ("resolve_offensive_rebound_turn", "core.oreb_turn"),
    ("update_clock_and_possession", "core.clock"),
]


def install(verbose: bool = True) -> list[str]:
    """Monkeypatch the sim path. Idempotent. Returns the list of applied probes."""
    global _installed
    if _installed or not ENABLED:
        return []
    _installed = True
    applied: list[str] = []

    def note(ok, label):
        if ok:
            applied.append(label)

    # --- database (pymongo, synchronous) -----------------------------------
    import pymongo.collection
    import pymongo.cursor

    _coll_name = lambda c: c.name
    for m in _DB_READ:
        note(_patch_db_method(pymongo.collection.Collection, m, "db.read", _coll_name),
             f"db.read.*.{m}")
    for m in _DB_WRITE:
        note(_patch_db_method(pymongo.collection.Collection, m, "db.write", _coll_name),
             f"db.write.*.{m}")
    # Collection.find() only builds a lazy cursor; the network round trips
    # happen in Cursor._refresh, so time that separately or find() reads ~0.
    note(_patch_db_method(pymongo.cursor.Cursor, "_refresh", "db.read",
                          lambda cur: cur.collection.name), "db.read.*.cursor_fetch")

    # --- core possession / turn logic --------------------------------------
    from BackEnd.models.game_manager import GameManager
    from BackEnd.models.turn_manager import TurnManager

    note(_patch_method(GameManager, "simulate_macro_turn", "core.macro_turn"), "core.macro_turn")
    note(_patch_method(GameManager, "determine_next_turn", "core.determine_next_turn"),
         "core.determine_next_turn")
    note(_patch_method(GameManager, "_append_turn", "core.append_turn"), "core.append_turn")
    note(_patch_method(TurnManager, "run_micro_turn", "core.micro_turn"), "core.micro_turn")
    for attr, label in _TURN_HANDLERS:
        note(_patch_method(TurnManager, attr, label), label)

    # shot / rebound resolution
    try:
        from BackEnd.models.shot_manager import ShotManager
        note(_patch_method(ShotManager, "resolve_shot", "core.shot_resolution"),
             "core.shot_resolution")
    except Exception:
        pass

    # --- animation packet construction -------------------------------------
    from BackEnd.models.animator import Animator

    for attr, label in _ANIM_METHODS:
        note(_patch_method(Animator, attr, label), f"{label}:{attr}")

    # --- schema step emission ----------------------------------------------
    for mod_path, fn in _STEP_EMITTERS:
        note(_patch_function(mod_path, fn, "emit.animation_steps"), f"emit:{fn}")

    # --- per-game setup ----------------------------------------------------
    note(_patch_method(GameManager, "__init__", "setup.gm_init"), "setup.gm_init")
    note(_patch_method(GameManager, "setup_opening_tip", "setup.opening_tip"),
         "setup.opening_tip")
    note(_patch_function("BackEnd.utils.franchise_ftd_game_seed",
                         "prepare_ftd_for_new_game", "setup.ftd_prepare"),
         "setup.ftd_prepare")
    note(_patch_function("BackEnd.utils.db_utils",
                         "build_lineup_from_mongo", "setup.lineup"), "setup.lineup")

    # --- serialization / response building ---------------------------------
    note(_patch_function("BackEnd.utils.shared",
                         "summarize_game_state", "serialize.summary"), "serialize.summary")

    if verbose:
        print(f"⏱️  [sim_profiler] installed {len(applied)} probes", file=sys.stderr)
    return applied


def format_table(snap: dict, total_wall_s: float) -> str:
    """Render the phase breakdown as a fixed-width table."""
    lines = []
    hdr = f"{'phase':<34}{'self_s':>11}{'% total':>10}{'incl_s':>11}{'calls':>12}"
    lines.append(hdr)
    lines.append("-" * len(hdr))
    accounted = 0.0
    for name, v in sorted(snap.items(), key=lambda kv: -kv[1]["self_s"]):
        accounted += v["self_s"]
        pct = 100.0 * v["self_s"] / total_wall_s if total_wall_s else 0.0
        lines.append(
            f"{name:<34}{v['self_s']:>11.2f}{pct:>9.1f}%{v['incl_s']:>11.2f}{v['calls']:>12,}"
        )
    unaccounted = total_wall_s - accounted
    lines.append("-" * len(hdr))
    pct = 100.0 * unaccounted / total_wall_s if total_wall_s else 0.0
    lines.append(f"{'(unprofiled / harness overhead)':<34}{unaccounted:>11.2f}{pct:>9.1f}%")
    lines.append(f"{'TOTAL WALL':<34}{total_wall_s:>11.2f}{100.0:>9.1f}%")
    return "\n".join(lines)
