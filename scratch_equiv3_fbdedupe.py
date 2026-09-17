"""equiv-v3 worker — one (COND, ARM, seed-range) per process.

Output shape expected by /tmp/refcut_equivv3.py:
  {"rows": {"after_played": [row, ...]}}
"""
import os
import sys
import json
import random as _stdlib

os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_DB_NAME", "gob-test")
os.environ["GOB_STRICT_POS_ACTION_KEYS"] = "false"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("PYTHONHASHSEED") != "0":
    raise SystemExit("run with PYTHONHASHSEED=0")

from BackEnd.db import (
    players_collection, teams_collection, plays_collection, defenses_collection,
)
from tests.roster_fixtures import (
    seed_universal_rosters, seed_universal_plays, seed_universal_defenses,
)

if os.environ.get("SEED_PLAYS", "1") == "1":
    seed_universal_rosters(teams_collection, players_collection)
    seed_universal_plays(plays_collection)
else:
    seed_universal_rosters(teams_collection, players_collection)

# SEED_DEFENSES=1 seeds the six real defenses (defenses_export.json). Default 0 keeps the
# Phase 6 footing (b2982fce1), where the catalogue was empty and every zone call played man.
SEED_DEFENSES = os.environ.get("SEED_DEFENSES", "0") == "1"
if SEED_DEFENSES:
    seed_universal_defenses(defenses_collection)

from BackEnd.utils import sim_random, training_random
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter

# Harness-only: match api.py:5741-5785. simulate_quarter never consumes
# pending_computer_timeout. The live turn-by-turn API does, on the next
# request, instead of calling simulate_macro_turn. Without this wrap the
# PlayedState harvest leaves pending set and Pattern A skips BIP.
PENDING_CONSUMED = [0]
_ORIG_MACRO = GameManager.simulate_macro_turn


def consume_pending_computer_timeout_like_api(gm):
    """Same consume as api.py:5741-5785. Returns True if a timeout was created."""
    pending = (getattr(gm, "game_state", None) or {}).get("pending_computer_timeout")
    if not pending:
        return False
    gm.call_timeout(
        calling_team=pending["calling_team"],
        timeout_reason="COMPUTER",
        rebuild_both_lineups=True,
        game_id=getattr(gm, "game_id", None),
    )
    gm.game_state.pop("pending_computer_timeout", None)
    PENDING_CONSUMED[0] += 1
    return True


def install_api_pending_timeout_consumption():
    if getattr(GameManager.simulate_macro_turn, "_api_pending_consume", False):
        return

    def wrapped(self, *a, **k):
        if consume_pending_computer_timeout_like_api(self):
            return None
        return _ORIG_MACRO(self, *a, **k)

    wrapped._api_pending_consume = True
    GameManager.simulate_macro_turn = wrapped

GAMES = int(os.environ.get("PROBE_GAMES", "1"))
SEED_BASE = int(os.environ.get("SEED_BASE", "8000"))
OUT = os.environ["OUT"]
COND = os.environ.get("COND", "after")
ARM = os.environ.get("ARM", "sim")

GATED_METHODS = (
    "capture_fast_break_animation",
    "capture_free_throw_animation",
    "capture_halfcourt_animation",
    "skeleton_to_animations",
)
_PATCHED = {}
DEPTH = [0]


def _install_played_arm():
    from BackEnd.models import animator as AN
    for meth in GATED_METHODS:
        orig = getattr(AN.Animator, meth)
        _PATCHED[meth] = orig

        def make(orig=orig):
            def wrapped(self, *a, **k):
                gs = self.game.game_state
                if DEPTH[0] == 0:
                    _PATCHED["_had"] = "_is_full_simulation" in gs
                    _PATCHED["_prev"] = gs.get("_is_full_simulation")
                gs["_is_full_simulation"] = False
                DEPTH[0] += 1
                try:
                    return orig(self, *a, **k)
                finally:
                    DEPTH[0] -= 1
                    if DEPTH[0] == 0:
                        if _PATCHED["_had"]:
                            gs["_is_full_simulation"] = _PATCHED["_prev"]
                        else:
                            gs.pop("_is_full_simulation", None)
            return wrapped
        setattr(AN.Animator, meth, make())


def _uninstall_played_arm():
    from BackEnd.models import animator as AN
    for meth in GATED_METHODS:
        if meth in _PATCHED and callable(_PATCHED.get(meth)):
            setattr(AN.Animator, meth, _PATCHED[meth])


class PlayedState(dict):
    """game_state that refuses ``_is_full_simulation``: the production turn-by-turn footing.
    ARM=played only clears the flag inside GATED_METHODS; ARM=played_full never sets it."""
    def __setitem__(self, k, v):
        if k == "_is_full_simulation":
            return
        dict.__setitem__(self, k, v)

    def setdefault(self, k, *a):
        if k == "_is_full_simulation":
            return None
        return dict.setdefault(self, k, *a)

    def update(self, *a, **kw):
        src = dict(*a, **kw)
        src.pop("_is_full_simulation", None)
        dict.update(self, src)


# ── ALIGN_RNG=1: arm-gated regions draw from a SIDE stream (harness only) ─────────────────
# Each region below draws sim_rng only when animation is live (a `_is_full_simulation`
# early return, or data that only exists when it is live). Running them on a side stream on
# BOTH arms leaves the main sim_rng stream arm-independent, so the two arms' main streams
# agree until a genuine behavioural difference. The sim arm draws nothing inside them, so
# the wrap is a no-op there. Production draw behaviour is untouched; the ALIGNED played arm
# is a diagnostic footing, not the production one.
ALIGN_RNG = os.environ.get("ALIGN_RNG", "0") == "1"
ALIGN_REGIONS = (
    ("BackEnd.models.animator", "Animator.capture_fast_break_animation"),
    ("BackEnd.models.animator", "Animator.capture_free_throw_animation"),
    ("BackEnd.models.animator", "Animator.capture_halfcourt_animation"),
    ("BackEnd.models.animator", "Animator.skeleton_to_animations"),
    ("BackEnd.engine.skeleton_step_emitter", "build_skeleton_animation_steps"),
    ("BackEnd.engine.step_state", "_diagnose"),
    ("BackEnd.engine.ft_step_emitter", "build_ft_animation_steps"),
    ("BackEnd.engine.triangle_step_emitter", "build_triangle_animation_steps"),
    ("BackEnd.engine.phase_resolution", "get_fcp_skeleton"),
    ("BackEnd.engine.phase_resolution", "get_hct_skeleton"),
)
SIDE = {"state": None, "depth": 0, "draws": 0, "calls": {}}


def _install_align_regions():
    import importlib
    for mod_name, attr in ALIGN_REGIONS:
        owner = importlib.import_module(mod_name)
        name = attr
        if "." in attr:
            cls, name = attr.split(".")
            owner = getattr(owner, cls)
        orig = getattr(owner, name)

        def make(orig=orig, label=attr):
            def wrapped(*a, **k):
                if SIDE["depth"]:
                    return orig(*a, **k)
                rng = sim_random.sim_rng
                main = rng.getstate()
                rng.setstate(SIDE["state"])
                SIDE["depth"] = 1
                box = getattr(rng, "_equiv_draws", None)
                before = box[0] if box else 0
                try:
                    return orig(*a, **k)
                finally:
                    SIDE["draws"] += (box[0] if box else 0) - before
                    SIDE["calls"][label] = SIDE["calls"].get(label, 0) + 1
                    SIDE["state"] = rng.getstate()
                    rng.setstate(main)
                    SIDE["depth"] = 0
            return wrapped
        setattr(owner, name, make())


def ft_invariant(turns, window=3):
    awards = strict = windowed = 0
    for i, t in enumerate(turns):
        if str(t.get("next_turn") or "").upper() != "FREE_THROW":
            continue
        awards += 1
        nxts = [str(turns[j].get("result_type") or "").upper()
                for j in range(i + 1, min(i + 1 + window, len(turns)))]
        if nxts and nxts[0] == "FREE_THROW":
            strict += 1
        if "FREE_THROW" in nxts:
            windowed += 1
    return awards, strict, windowed


# ── Defense census (observation only: no RNG, return values passed through) ──────────────
# One record per HCO possession, opened by turn_manager's per-possession announce call.
# Placement calls are tagged to the open possession only while its call is still live.
import hashlib
import logging as _logging

_ZONE_SHELL = {"2-3-zone": "2-3", "3-2-zone": "3-2", "1-3-1-zone": "1-3-1"}
DCENSUS = {"poss": [], "final_turn": [], "untagged_placements": 0, "sub_log_lines": 0}


class _SubLogCounter(_logging.Handler):
    def emit(self, record):
        if "[DEFENSE-IDENTITY SUBSTITUTION]" in record.getMessage():
            DCENSUS["sub_log_lines"] += 1


def _install_defense_census():
    from BackEnd.models import turn_manager as TM
    from BackEnd.engine import defender_placement as DP
    from BackEnd.engine import phase_resolution as PR
    from BackEnd.utils import defense_identity as DI

    DI.logger.addHandler(_SubLogCounter(level=_logging.WARNING))
    _announce = TM.announce_zone_played_as_man

    def announce(raw_call, context):
        short = _announce(raw_call, context)
        rec = {"call": raw_call, "substituted": short is not None, "paths": set(),
               "posture": None}
        if context == "HCO possession":
            DCENSUS["poss"].append(rec)
        else:
            DCENSUS["final_turn"].append(rec)
        return short

    TM.announce_zone_played_as_man = announce

    def tag(name):
        orig = getattr(DP, name)

        def wrapped(game, *a, **k):
            cur = DCENSUS["poss"][-1] if DCENSUS["poss"] else None
            live = (game.game_state or {}).get("defense_playcall")
            if cur is not None and cur["call"] == live:
                cur["paths"].add("zone" if name == "position_zone_defenders" else "man")
            else:
                DCENSUS["untagged_placements"] += 1
            return orig(game, *a, **k)
        setattr(DP, name, wrapped)

    tag("position_zone_defenders")
    tag("position_standard_defenders")
    _roll = PR._roll_defense_posture

    def roll(game, rng=None):
        posture = _roll(game, rng)
        if DCENSUS["poss"]:
            DCENSUS["poss"][-1]["posture"] = posture
        return posture

    PR._roll_defense_posture = roll


def defense_census_summary():
    from collections import Counter
    from BackEnd.utils import defense_identity as DI

    poss = DCENSUS["poss"]
    calls = Counter(p["call"] for p in poss)
    zone = [p for p in poss if p["call"] in _ZONE_SHELL]
    return {
        "catalog_status_end": DI.defense_catalog_status(),
        "hco_possessions": len(poss),
        "calls": dict(calls),
        "zone_calls": len(zone),
        "zone_calls_by_shell": dict(Counter(_ZONE_SHELL[p["call"]] for p in zone)),
        "zone_calls_zone_path": sum(1 for p in zone if "zone" in p["paths"]),
        "zone_calls_man_path_only": sum(1 for p in zone if p["paths"] == {"man"}),
        "zone_calls_no_placement": sum(1 for p in zone if not p["paths"]),
        "man_calls_zone_path": sum(1 for p in poss
                                   if p["call"] not in _ZONE_SHELL and "zone" in p["paths"]),
        "postures": dict(Counter(str(p["posture"]) for p in poss)),
        "substitutions_hco": sum(1 for p in poss if p["substituted"]),
        "substitutions_final_turn": sum(1 for p in DCENSUS["final_turn"] if p["substituted"]),
        "final_turn_announces": len(DCENSUS["final_turn"]),
        "substitution_log_lines": DCENSUS["sub_log_lines"],
        "untagged_placements": DCENSUS["untagged_placements"],
    }


def turns_fingerprint(turns, score):
    rows = [(str(t.get("result_type") or ""), str(t.get("next_turn") or "")) for t in turns]
    blob = json.dumps({"rows": rows, "score": score}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def run_arm(played: bool):
    rows = []
    if played:
        _install_played_arm()
    try:
        for g in range(GAMES):
            seed = SEED_BASE + g
            sim_random.seed(seed)
            training_random.seed(seed)
            _stdlib.seed(seed)
            if not getattr(sim_random.sim_rng, "_equiv_draws", None):
                _box = [0]
                _gb = sim_random.sim_rng.getrandbits
                _rnd = sim_random.sim_rng.random

                def _gb_c(k, _gb=_gb, _box=_box):
                    _box[0] += 1
                    return _gb(k)

                def _rnd_c(_rnd=_rnd, _box=_box):
                    _box[0] += 1
                    return _rnd()

                sim_random.sim_rng.getrandbits = _gb_c
                sim_random.sim_rng.random = _rnd_c
                sim_random.sim_rng._equiv_draws = _box
            sim_random.sim_rng._equiv_draws[0] = 0
            SIDE.update({"state": _stdlib.Random(seed ^ 0x51DE).getstate(), "depth": 0,
                         "draws": 0, "calls": {}})
            DCENSUS.update({"poss": [], "final_turn": [], "untagged_placements": 0,
                            "sub_log_lines": 0})
            gm = GameManager("Lancaster", "Bentley-Truman")
            if ARM == "played_full":
                gm.game_state = PlayedState(gm.game_state)
            d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2,
                 "hc_trap": 5, "fc_press": 5}
            gm.home_team.strategy_settings = d.copy()
            gm.away_team.strategy_settings = d.copy()
            gid = "%024x" % (0xE0000 + (seed - 8000))
            err = None
            import time as _time
            _t0 = _time.perf_counter()
            for _q in range(4):
                try:
                    simulate_quarter(gm, game_id=gid)
                except Exception as e:  # noqa: BLE001
                    err = "%s: %s" % (type(e).__name__, e)
                    break
            wall_s = _time.perf_counter() - _t0
            turns = gm.turns or []
            score = dict(gm.score or {})
            poss = sum(1 for t in turns if t.get("possession_flips"))
            aw, st, wi = ft_invariant(turns)
            draws = getattr(sim_random.sim_rng, "_equiv_draws", None)
            rows.append({
                "seed": seed, "err": err, "turns": len(turns),
                "points_total": sum(score.values()),
                "points_per_team": sum(score.values()) / 2.0,
                "possessions": poss,
                "draws": draws[0] if draws else None,
                "arm": ARM, "align_rng": ALIGN_RNG, "wall_s": round(wall_s, 3),
                "side_draws": SIDE["draws"], "side_calls": dict(SIDE["calls"]),
                "ft_awards": aw, "ft_strict": st, "ft_windowed": wi,
                "fp": turns_fingerprint(turns, score),
                "defenses_seeded": SEED_DEFENSES,
                "defense": defense_census_summary(),
            })
    finally:
        if played:
            _uninstall_played_arm()
    return rows


def published_ci95(vals):
    """Mean and 1.96 × SEM (sample SD). Published form — never print SEM alone."""
    n = len(vals)
    if n < 2:
        return None, None
    mean = sum(vals) / float(n)
    var = sum((v - mean) ** 2 for v in vals) / (n - 1)
    return mean, 1.96 * ((var ** 0.5) / (n ** 0.5))


if __name__ == "__main__":
    label = "%s_%s" % (COND, ARM)
    _install_defense_census()
    if ALIGN_RNG:
        _install_align_regions()
    rows = run_arm(ARM == "played")
    json.dump({"rows": {label: rows}}, open(OUT, "w"), indent=1)
    pts = [r["points_per_team"] for r in rows if r.get("err") is None]
    mean, ci = published_ci95(pts)
    if mean is None:
        print("  %-16s done (%d games)" % (label, len(rows)))
    else:
        print("  %-16s done (%d games)  pts/team %.2f ±%.2f" % (label, len(rows), mean, ci))
