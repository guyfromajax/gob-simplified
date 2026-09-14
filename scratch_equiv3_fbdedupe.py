"""equiv-v3 for the fast-break dedupe (63eb72b6c) — DISTRIBUTIONAL, not per-seed.

WHY DISTRIBUTIONAL. The dedupe moves outcomes by perturbing the coordinates a fast-break
turn hands to the next turn (see the mechanism note in bugs.md item 41). The perturbation
damps out on some seeds and amplifies on others, and it runs BOTH ways — turns 329->319 on
one seed, 333->350 on another. That is stream drift. A per-seed delta is therefore noise and
means nothing; only the distribution over many seeds is readable.

ARM DEFINITION is inherited verbatim from scratch_equiv2.py: the played arm wraps the four
gated Animator entry points and flips ``_is_full_simulation`` on the LIVE game_state dict for
the duration of each call, depth-counted. The dict is never replaced (equiv-v1 did that and
every one of its figures was void).

THE BEFORE/AFTER AXIS is applied IN-PROCESS rather than by editing source, so the two
conditions cannot differ by anything except the one behaviour under test:
``_finalize_rr_steps`` is wrapped to force ``post_shot_already_built=False``, which exactly
reinstates the pre-fix double build.

REQUIRED SANITY INVARIANT, inherited: free-throw awards honoured must be >=95% on both arms
and within 3pp of each other. If not, the harness is lying and no number is reportable.

  PROBE_GAMES=40 PYTHONHASHSEED=0 python scratch_equiv3_fbdedupe.py
"""
import os
import sys
import json
import random as _stdlib
from collections import Counter

os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_DB_NAME", "gob-test")
os.environ["GOB_STRICT_POS_ACTION_KEYS"] = "false"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("PYTHONHASHSEED") != "0":
    raise SystemExit("run with PYTHONHASHSEED=0 (SPC determinism contract clause 3)")

from BackEnd.db import players_collection, teams_collection, plays_collection
from tests.roster_fixtures import seed_universal_rosters, seed_universal_plays

seed_universal_rosters(teams_collection, players_collection)
# The HCO plays catalogue MATERIALLY MOVES SCORING, so whether it is seeded is part of the
# reference's definition and must be recorded with the number, not left implicit.
SEED_PLAYS = os.environ.get("SEED_PLAYS", "1") == "1"
if SEED_PLAYS:
    seed_universal_plays(plays_collection)

from BackEnd.utils import sim_random, training_random
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter
import BackEnd.engine.rim_runner_step_emitter as RR

# Harness-only: match api.py:5741-5785. simulate_quarter (main.py:939) never
# consumes pending_computer_timeout. The live turn-by-turn API does, on the
# next request, instead of calling simulate_macro_turn. Without this wrap the
# PlayedState harvest (flag refused) leaves pending set and Pattern A skips
# BIP for the rest of the game.
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

GAMES = int(os.environ.get("PROBE_GAMES", "40"))
BASE = int(os.environ.get("SEED_BASE", "8000"))
OUT = os.environ.get("OUT", "scratch_equiv3_fbdedupe.json")

GATED_METHODS = (
    "capture_fast_break_animation",
    "capture_free_throw_animation",
    "capture_halfcourt_animation",
    "skeleton_to_animations",
)

C = Counter()
DEPTH = [0]
_PATCHED = {}

# ---- the BEFORE condition: reinstate the double build, in process ------------
_ORIG_FINALIZE = RR._finalize_rr_steps


def _install_prefix_arm():
    def wrapped(turn_result, game, steps, post_shot_already_built=False):
        return _ORIG_FINALIZE(turn_result, game, steps, post_shot_already_built=False)
    RR._finalize_rr_steps = wrapped


def _uninstall_prefix_arm():
    RR._finalize_rr_steps = _ORIG_FINALIZE


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


def run_arm(played: bool, prefix: bool):
    """POSSESSIONS are counted as turns that flip possession — the field the engine itself
    stamps (``possession_flips``), rather than a box-score estimate, so it cannot drift from
    what the sim actually did."""
    rows = []
    if prefix:
        _install_prefix_arm()
    if played:
        _install_played_arm()
    try:
        for g in range(BASE, BASE + GAMES):
            sim_random.seed(g)
            training_random.seed(g)
            _stdlib.seed(g)
            gm = GameManager("Lancaster", "Bentley-Truman")
            d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2,
                 "hc_trap": 5, "fc_press": 5}
            gm.home_team.strategy_settings = d.copy()
            gm.away_team.strategy_settings = d.copy()
            gid = "%024x" % (0xE0000 + g)
            err = None
            for _q in range(4):
                try:
                    simulate_quarter(gm, game_id=gid)
                except Exception as e:  # noqa: BLE001
                    err = "%s: %s" % (type(e).__name__, e)
                    break
            turns = gm.turns or []
            score = dict(gm.score or {})
            poss = sum(1 for t in turns if t.get("possession_flips"))
            aw, st, wi = ft_invariant(turns)
            rows.append({
                "seed": g, "err": err, "turns": len(turns),
                "points_total": sum(score.values()),
                "points_per_team": sum(score.values()) / 2.0,
                "possessions": poss,
                "ft_awards": aw, "ft_strict": st, "ft_windowed": wi,
            })
    finally:
        if played:
            _uninstall_played_arm()
        if prefix:
            _uninstall_prefix_arm()
    return rows


def stats(rows, key):
    vals = sorted(r[key] for r in rows)
    n = len(vals) or 1
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / (n - 1) if n > 1 else 0.0
    sd = var ** 0.5
    return {"mean": mean, "sd": sd, "sem": sd / (n ** 0.5) if n else 0.0,
            "median": vals[n // 2], "min": vals[0], "max": vals[-1], "n": n}


# ONE CONDITION PER PROCESS, non-negotiable. An earlier build ran all four arms
# sequentially in a single process, which puts "after" permanently last in the sequence and
# lets any accumulated state (mongomock writes, module caches, lru_caches) masquerade as an
# effect of the fix. It produced a 31-of-40 one-sided turn increase that did not survive this
# change. Each (condition, arm) now gets a clean interpreter.
if __name__ == "__main__":
    install_api_pending_timeout_consumption()
    COND = os.environ["COND"]      # before | after
    ARM = os.environ["ARM"]        # played | sim
    label = "%s_%s" % (COND, ARM)
    arms = {label: run_arm(ARM == "played", COND == "before")}
    print("  %-16s done (%d games) pending_consumed=%d" % (
        label, len(arms[label]), PENDING_CONSUMED[0],
    ))

    report = {"games_per_arm": GAMES, "seed_base": BASE, "seed_plays": SEED_PLAYS,
              "pending_consumed": PENDING_CONSUMED[0],
              "rows": arms, "arms": {}}
    for k, rows in arms.items():
        aw = sum(r["ft_awards"] for r in rows)
        report["arms"][k] = {
            "points_per_team": stats(rows, "points_per_team"),
            "possessions": stats(rows, "possessions"),
            "turns": stats(rows, "turns"),
            "ft_windowed_pct": 100.0 * sum(r["ft_windowed"] for r in rows) / aw if aw else None,
            "errors": sum(1 for r in rows if r["err"]),
        }
    json.dump(report, open(OUT, "w"), indent=1)
    print("wrote %s" % OUT)
