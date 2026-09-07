"""Does build_all_animations mutate its skeleton argument, or the spot constants?

This settles a contradiction. The commit-1 ledger found NO in-place skeleton mutation
(zero subscript writes into the skeleton or pos_actions). A later summary of mine offered
that same mutation as a mechanism. Both cannot hold, and a static scan can miss an ALIAS
write: build_all_animations puts coords into animations BY REFERENCE
(defender_placement.py:50 aliases pos_action["coords"]; :62/:65 alias OFFSET_SPOTS /
HCO_STRING_SPOTS), so a write through one of those references would mutate the skeleton or
a module-level constant without ever writing a subscript on the skeleton.

Two runtime checks, played arm, real games:
  1. ARGUMENT IDEMPOTENCE — deep-copy the skeleton on entry to build_all_animations,
     compare after it returns. Any difference means it mutates its argument, which is what
     the deep copy in compute_defender_grid exists to absorb.
  2. CONSTANT INTEGRITY — snapshot HCO_STRING_SPOTS and OFFSET_SPOTS at import, compare at
     the end. A write through the :62/:65 aliases lands here. NOTE the asymmetry: the deep
     copy would NOT protect this half, because it copies the skeleton, not the constants.
"""
import os, sys, copy, random as _stdlib

os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_DB_NAME", "gob-test")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("PYTHONHASHSEED") != "0":
    raise SystemExit("run with PYTHONHASHSEED=0")

from BackEnd.db import players_collection, teams_collection
from tests.roster_fixtures import seed_universal_rosters
seed_universal_rosters(teams_collection, players_collection)

from BackEnd.utils import sim_random, training_random
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter
from BackEnd.constants import HCO_STRING_SPOTS, OFFSET_SPOTS
import BackEnd.engine.defender_placement as DP

CONST_SNAPSHOT = {
    "HCO_STRING_SPOTS": copy.deepcopy(HCO_STRING_SPOTS),
    "OFFSET_SPOTS": copy.deepcopy(OFFSET_SPOTS),
}

STATS = {"calls": 0, "mutated": 0, "examples": []}
GATED = ("capture_fast_break_animation", "capture_free_throw_animation",
         "capture_halfcourt_animation", "skeleton_to_animations")
DEPTH = [0]
_PATCHED = {}


def _wrap_producer():
    orig = DP.build_all_animations

    def wrapped(game, skeleton, *a, **k):
        before = copy.deepcopy(skeleton)
        STATS["calls"] += 1
        out = orig(game, skeleton, *a, **k)
        if skeleton != before:
            STATS["mutated"] += 1
            if len(STATS["examples"]) < 3:
                diffs = []
                for i, (b, aft) in enumerate(zip(before.get("steps", []),
                                                 skeleton.get("steps", []))):
                    if b != aft:
                        for kk in set(b) | set(aft):
                            if b.get(kk) != aft.get(kk):
                                diffs.append(f"step[{i}].{kk}: {b.get(kk)!r} -> {aft.get(kk)!r}")
                STATS["examples"].append(diffs[:6])
        return out
    DP.build_all_animations = wrapped
    # animator.py imported the symbol directly, so rebind there too
    import BackEnd.models.animator as AN
    AN.build_all_animations = wrapped


def _install_played_arm():
    import BackEnd.models.animator as AN
    for meth in GATED:
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


if __name__ == "__main__":
    _wrap_producer()
    _install_played_arm()
    games = int(os.environ.get("PROBE_GAMES", "2"))
    for g in range(games):
        sim_random.seed(8000 + g)
        training_random.seed(8000 + g)
        _stdlib.seed(8000 + g)
        gm = GameManager("Lancaster", "Bentley-Truman")
        d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2,
             "hc_trap": 5, "fc_press": 5}
        gm.home_team.strategy_settings = d.copy()
        gm.away_team.strategy_settings = d.copy()
        for _q in range(4):
            try:
                simulate_quarter(gm, game_id="%024x" % (0xE0000 + g))
            except Exception as e:
                print(f"  seed {8000+g}: {type(e).__name__}: {e}")
                break
        print(f"  seed {8000+g}: {STATS['calls']} producer calls so far, "
              f"{STATS['mutated']} mutated their skeleton argument")

    print("\n" + "=" * 74)
    print("1. ARGUMENT IDEMPOTENCE — does build_all_animations mutate its skeleton?")
    print("=" * 74)
    print(f"  calls            : {STATS['calls']}")
    print(f"  mutated argument : {STATS['mutated']}")
    if STATS["mutated"]:
        print("  ⚠️  MUTATES. Examples:")
        for ex in STATS["examples"]:
            for line in ex:
                print(f"      {line}")
    else:
        print("  ✅ PURE with respect to its skeleton argument across every call.")

    print("\n" + "=" * 74)
    print("2. CONSTANT INTEGRITY — did any alias write reach the spot tables?")
    print("=" * 74)
    bad = False
    for name, snap in CONST_SNAPSHOT.items():
        live = {"HCO_STRING_SPOTS": HCO_STRING_SPOTS, "OFFSET_SPOTS": OFFSET_SPOTS}[name]
        if live != snap:
            bad = True
            print(f"  ⚠️  {name} MUTATED:")
            for k in set(snap) | set(live):
                if snap.get(k) != live.get(k):
                    print(f"      {k}: {snap.get(k)!r} -> {live.get(k)!r}")
        else:
            print(f"  ✅ {name} unchanged ({len(live)} entries)")
    if not bad and not STATS["mutated"]:
        print("\nVERDICT: no in-place mutation and no alias write. The commit-1 ledger stands;")
        print("the deep copy guards READ-ONLY aliasing, not mutation.")
