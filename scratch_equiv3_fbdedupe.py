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

from BackEnd.db import players_collection, teams_collection, plays_collection
from tests.roster_fixtures import seed_universal_rosters, seed_universal_plays

if os.environ.get("SEED_PLAYS", "1") == "1":
    seed_universal_rosters(teams_collection, players_collection)
    seed_universal_plays(plays_collection)
else:
    seed_universal_rosters(teams_collection, players_collection)

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
            gm = GameManager("Lancaster", "Bentley-Truman")
            d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2,
                 "hc_trap": 5, "fc_press": 5}
            gm.home_team.strategy_settings = d.copy()
            gm.away_team.strategy_settings = d.copy()
            gid = "%024x" % (0xE0000 + (seed - 8000))
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
            draws = getattr(sim_random.sim_rng, "_equiv_draws", None)
            rows.append({
                "seed": seed, "err": err, "turns": len(turns),
                "points_total": sum(score.values()),
                "points_per_team": sum(score.values()) / 2.0,
                "possessions": poss,
                "draws": draws[0] if draws else None,
                "ft_awards": aw, "ft_strict": st, "ft_windowed": wi,
            })
    finally:
        if played:
            _uninstall_played_arm()
    return rows


if __name__ == "__main__":
    label = "%s_%s" % (COND, ARM)
    rows = run_arm(ARM == "played")
    json.dump({"rows": {label: rows}}, open(OUT, "w"), indent=1)
    print("  %-16s done (%d games)" % (label, len(rows)))
