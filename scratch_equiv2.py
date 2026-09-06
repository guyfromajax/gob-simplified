"""equiv-v2 — sim-vs-played divergence, animation isolated WITHOUT replacing game_state.

WHY V2 EXISTS. equiv-v1 built its played arm by assigning a dict subclass over
``gm.game_state``. ``game_manager.py:78-79`` constructs ``ShotManager(self)`` and
``shot_manager.py:286`` captures ``self.game_state = game.game_state`` BY REFERENCE at
that moment, so the swap orphaned ShotManager on the pre-swap dict. Every award
ShotManager wrote — which is every shooting foul — landed in the orphan and was
invisible to the dispatcher reading ``gm.game_state``. That produced a fake 66% collapse
in free throws. EVERY equiv-v1 FIGURE IS VOID, and none is carried forward here.

V2 ARM DEFINITION. The dict object is never replaced. The played arm wraps the four
gated Animator entry points and sets ``_is_full_simulation = False`` on the LIVE dict for
the duration of each call, restoring it on the way out (depth-counted, because these
nest). The sim arm patches nothing. So the only delta is whether animation runs.

REQUIRED SANITY INVARIANT (not optional). Free-throw awards honoured must be high and
approximately equal across arms. A healthy run is ~97%. If the arms disagree, the harness
is lying and NO number from that run is reportable — the run self-voids rather than
printing a divergence table.

LEAKAGE. Flipping the flag in place means anything the animator's call tree reaches also
reads False for the duration. LEAK=1 measures that directly: it counts every
``_is_full_simulation`` read inside a flip window and attributes it to the calling module.
To intercept reads it must subclass the dict, so it ALSO re-points
``gm.shot_manager.game_state`` at the same object; the invariant above is what proves the
re-point worked.
"""
import os, sys, random as _stdlib
from collections import Counter

os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_DB_NAME", "gob-test")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("PYTHONHASHSEED") != "0":
    raise SystemExit("run with PYTHONHASHSEED=0 (SPC determinism contract clause 3)")

from BackEnd.db import players_collection, teams_collection
from tests.roster_fixtures import seed_universal_rosters
seed_universal_rosters(teams_collection, players_collection)

from BackEnd.utils import sim_random, training_random
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter

GAMES = int(os.environ.get("PROBE_GAMES", "20"))
LEAK = os.environ.get("LEAK") == "1"

GATED_METHODS = (
    "capture_fast_break_animation",     # gate at animator.py:93
    "capture_free_throw_animation",     # gate at animator.py:572
    "capture_halfcourt_animation",      # gate at animator.py:777
    "skeleton_to_animations",           # gate at animator.py:1213
)
PLACEMENT_MODULES = {"BackEnd.models.animator", "BackEnd.engine.defender_placement"}

C = Counter()
DROP_REASONS = Counter()
DEPTH = [0]              # flip nesting depth; restore only when it returns to 0
LEAK_READS = Counter()   # (module, inside_flip) -> count
_MAXDEPTH = 40


def _in_placement():
    f = sys._getframe(2)
    d = 0
    while f is not None and d < _MAXDEPTH:
        if f.f_globals.get("__name__") in PLACEMENT_MODULES:
            return True
        f = f.f_back
        d += 1
    return False


def _install_draw_attribution():
    rng = sim_random.sim_rng
    for name in ("random", "randint", "choice", "choices", "shuffle", "uniform",
                 "sample", "gauss", "normalvariate", "betavariate", "triangular",
                 "randrange", "getrandbits", "expovariate", "lognormvariate",
                 "vonmisesvariate", "paretovariate", "weibullvariate", "randbytes"):
        orig = getattr(rng, name, None)
        if orig is None:
            continue

        def make(orig=orig):
            def wrapped(*a, **k):
                C["draws_total"] += 1
                if _in_placement():
                    C["draws_placement"] += 1
                return orig(*a, **k)
            return wrapped
        setattr(rng, name, make())


def _install_call_counters():
    from BackEnd.utils import shared_defense as SD
    _gdc = SD.get_defender_coords

    def gdc(*a, **k):
        C["get_defender_coords"] += 1
        return _gdc(*a, **k)
    SD.get_defender_coords = gdc


_PATCHED = {}


def _install_played_arm():
    """Wrap the four gates; flip the flag on the LIVE dict, never replace it."""
    from BackEnd.models import animator as AN
    for meth in GATED_METHODS:
        orig = getattr(AN.Animator, meth)
        _PATCHED[meth] = orig

        def make(orig=orig, meth=meth):
            def wrapped(self, *a, **k):
                gs = self.game.game_state
                if DEPTH[0] == 0:
                    _PATCHED["_had"] = "_is_full_simulation" in gs
                    _PATCHED["_prev"] = gs.get("_is_full_simulation")
                gs["_is_full_simulation"] = False
                DEPTH[0] += 1
                C[f"call_{meth}"] += 1
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
        if meth in _PATCHED:
            setattr(AN.Animator, meth, _PATCHED[meth])


class LeakTracingGameState(dict):
    """Read-tracing ONLY. Never used for the arm split; used to measure leakage."""

    def get(self, key, default=None):
        if key == "_is_full_simulation":
            f = sys._getframe(1)
            LEAK_READS[(f.f_globals.get("__name__", "?"), DEPTH[0] > 0)] += 1
        return super().get(key, default)


def ft_invariant(turns, window=3):
    """Awards honoured. The harness's own truth serum.

    STRICT counts only awards whose very next turn is the free throw. That has a KNOWN
    false negative: a TIMEOUT legitimately interposes and the trip resumes after it, which
    is why even a healthy arm scores ~97% rather than 100%. WINDOWED allows the free throw
    to arrive within the next few turns, which removes that false negative without
    forgiving a genuinely lost award. Both are reported, plus what actually intervened, so
    the choice of metric is visible rather than convenient.
    """
    awards = strict = windowed = 0
    reasons = Counter()
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
        else:
            reasons[f"{str(t.get('result_type') or '').upper()} -> "
                    f"{nxts[0] if nxts else '<END>'}"] += 1
    return awards, strict, windowed, reasons


def run_arm(label, played, games):
    rows = []
    if played:
        _install_played_arm()
    try:
        for g in range(games):
            C.clear()
            sim_random.seed(8000 + g)
            training_random.seed(8000 + g)
            _stdlib.seed(8000 + g)
            gm = GameManager("Lancaster", "Bentley-Truman")
            if LEAK:
                # Swap for read-tracing, then REPAIR the only construction-time alias.
                gs = LeakTracingGameState(gm.game_state)
                gm.game_state = gs
                gm.shot_manager.game_state = gs
                assert gm.shot_manager.game_state is gm.game_state
            d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2,
                 "hc_trap": 5, "fc_press": 5}
            gm.home_team.strategy_settings = d.copy()
            gm.away_team.strategy_settings = d.copy()
            gid = "%024x" % (0xE0000 + g)
            for _q in range(4):
                try:
                    simulate_quarter(gm, game_id=gid)
                except Exception as e:
                    print(f"  [{label} {8000+g}] {type(e).__name__}: {e}")
                    break
            rt, tt = Counter(), Counter()
            for t in (gm.turns or []):
                if t.get("result_type"):
                    rt[str(t["result_type"]).upper()] += 1
                if t.get("turnover_type"):
                    tt[str(t["turnover_type"]).upper()] += 1
            aw, ho, hw, rs = ft_invariant(gm.turns or [])
            DROP_REASONS.update(rs)
            rows.append({
                "seed": 8000 + g, "turns": len(gm.turns or []),
                "points": sum((gm.score or {}).values()), "rt": rt, "tt": tt,
                "awards": aw, "honoured": ho, "honoured_win": hw,
                "draws_total": C["draws_total"],
                "draws_placement": C["draws_placement"],
                "gdc": C["get_defender_coords"],
                "gates": sum(C[f"call_{m}"] for m in GATED_METHODS),
            })
            pct = 100.0 * ho / aw if aw else float("nan")
            print(f"  [{label}] {8000+g}: turns={rows[-1]['turns']:>4} pts={rows[-1]['points']:>4} "
                  f"draws={rows[-1]['draws_total']:>7} placement={rows[-1]['draws_placement']:>7} "
                  f"gdc={rows[-1]['gdc']:>6} FT {ho}/{aw} ({pct:.0f}%)")
    finally:
        if played:
            _uninstall_played_arm()
    return rows


def summarize(rows):
    n = len(rows) or 1
    o = {k: sum(r[k] for r in rows) / n for k in
         ("turns", "points", "draws_total", "draws_placement", "gdc", "gates")}
    for k in ("MAKE", "MISS", "BLOCK", "FOUL", "FREE_THROW"):
        o[k] = sum(r["rt"].get(k, 0) for r in rows) / n
    o["STEAL"] = (sum(r["rt"].get("STEAL", 0) for r in rows)
                  + sum(r["tt"].get("STEAL", 0) for r in rows)) / n
    aw = sum(r["awards"] for r in rows)
    o["ft_awards"] = aw / n
    o["ft_honoured"] = sum(r["honoured"] for r in rows) / n
    o["ft_honoured_win"] = sum(r["honoured_win"] for r in rows) / n
    o["ft_honour_pct"] = 100.0 * sum(r["honoured"] for r in rows) / aw if aw else float("nan")
    o["ft_honour_win_pct"] = 100.0 * sum(r["honoured_win"] for r in rows) / aw if aw else float("nan")
    return o


if __name__ == "__main__":
    _install_draw_attribution()
    _install_call_counters()
    print(f"\nHARNESS equiv-v2  games={GAMES}  seeds 8000-{8000+GAMES-1}  LEAK={LEAK}")
    print("\n--- ARM 1: sim (nothing patched; animation skipped) ---")
    sim = run_arm("sim", False, GAMES)
    print("\n--- ARM 2: played (flag flipped in place for the four gated calls) ---")
    played = run_arm("played", True, GAMES)
    s, p = summarize(sim), summarize(played)

    print("\n" + "=" * 80)
    print("REQUIRED SANITY INVARIANT — free-throw awards honoured")
    print("=" * 80)
    print(f"  {'arm':<8}{'awards':>9}{'strict':>9}{'strict%':>9}{'windowed':>10}{'window%':>9}")
    for nm, o in (("sim", s), ("played", p)):
        print(f"  {nm:<8}{o['ft_awards']:>9.2f}{o['ft_honoured']:>9.2f}{o['ft_honour_pct']:>8.1f}%"
              f"{o['ft_honoured_win']:>10.2f}{o['ft_honour_win_pct']:>8.1f}%")
    gap = abs(s["ft_honour_win_pct"] - p["ft_honour_win_pct"])
    ok = (s["ft_honour_win_pct"] >= 95.0 and p["ft_honour_win_pct"] >= 95.0 and gap <= 3.0)
    print(f"  windowed gap={gap:.1f}pp   -> {'PASS' if ok else 'FAIL'}")
    print("  what intervened on awards with no FT in the window (both arms pooled):")
    for k, c in DROP_REASONS.most_common(12):
        print(f"    {c:>5}x  {k}")

    if LEAK:
        print("\n" + "=" * 80)
        print("LEAKAGE — _is_full_simulation reads that occurred INSIDE a flip window")
        print("=" * 80)
        inside = {m: c for (m, ins), c in LEAK_READS.items() if ins}
        outside = sum(c for (m, ins), c in LEAK_READS.items() if not ins)
        tot_in = sum(inside.values())
        print(f"  reads outside any flip window: {outside}")
        print(f"  reads inside  a flip window  : {tot_in}")
        for m, c in sorted(inside.items(), key=lambda kv: -kv[1]):
            tag = "intended (animator)" if m in PLACEMENT_MODULES else "*** LEAKED ***"
            print(f"    {c:>8}  {m:<45} {tag}")
        leaked = sum(c for m, c in inside.items() if m not in PLACEMENT_MODULES)
        print(f"  LEAKED READS (non-animator, inside window): {leaked}")

    if not ok:
        print("\n❌ INVARIANT FAILED — the harness is lying. No divergence table printed.")
        sys.exit(1)

    print("\n" + "=" * 80)
    print(f"DIVERGENCE  harness=equiv-v2  n={GAMES} per arm  seeds 8000-{8000+GAMES-1}")
    print("=" * 80)
    print(f"{'metric':<20}{'sim':>12}{'played':>12}{'delta':>12}{'pct':>10}")
    for k in ("turns", "points", "MAKE", "MISS", "BLOCK", "FOUL", "FREE_THROW", "STEAL",
              "draws_total", "draws_placement", "gdc", "gates"):
        a, b = s[k], p[k]
        dl = b - a
        pct = (100.0 * dl / a) if a else float("nan")
        print(f"{k:<20}{a:>12.1f}{b:>12.1f}{dl:>+12.1f}{pct:>+9.1f}%")
    # `gates` counts WRAPPER invocations, which exist only in the played arm, so it is a
    # patch-applied check, not an arm comparison. The real evidence the split bit is `gdc`:
    # the sim arm calls the same methods but they early-return before placing anyone.
    print(f"\n  patch applied: {p['gates']:.1f} gated calls/game wrapped in the played arm")
    print(f"  split bit     : get_defender_coords {s['gdc']:.0f} (sim) vs {p['gdc']:.0f} (played)")
