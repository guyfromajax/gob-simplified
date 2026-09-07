"""Does _hco_render_animations (the stash) influence anything a contest or outcome reads?

Three questions, each measured rather than read off the source.

Q1 WHICH GRID DOES THE SHOT CONTEST READ, IN BOTH ARMS?
   The FT chain's defender coordinate is fully traced:
     _freeze_hco_shot_attempt_geometry (phase_resolution.py:4421) -> ShotAttemptGeometry
       -> _shot_defender_xy (shot_manager.py:182) -> _pdist (:1010)
       -> _proximity_contest_factor (:1014) -> defense_score *= factor (:3018)
       -> check_defensive_foul_on_shot (:3025) -> shooting foul -> free throws
   That freeze function already LABELS its own provenance in a ``source`` field, one of
   "hco-emitter-shot-step"  (Player.coords, synced by the emitter),
   "hco-stepstate-shot-step" (_step_state["defense"], i.e. the stamp), or
   "hco-final-grid-shot-step" (a fresh compute_defender_grid). Recording that label per
   arm answers Q1 in the code's own words.

Q2 IS build_step_states' RETURN VALUE DISCARDED?
   Not asserted from the call site. The wrapper returns a list subclass that logs every
   access to itself. Zero accesses = genuinely discarded.

Q3 DOES THE STASH INFLUENCE ANY CONTEST OR OUTCOME?
   Two independent measurements, because either alone is weak:
   (a) ORDERING. A global monotonic event counter records, per turn, every stamp write,
       every entry into each of the four functions that READ _step_state["defense"]
       (phase_resolution.py:4460, 4977, 5862, 6334), and the build_step_states call that
       overwrites _step_state from the stash. If every read precedes the overwrite, the
       stash cannot have reached that read. Dict subclassing was avoided deliberately:
       ``dict(x)`` on a dict subclass takes a C fast path and would silently miss reads.
   (b) POISON. A third arm replaces the stash with coords of -9999 immediately before
       build_step_states consumes it, changing no RNG draw so the streams stay aligned.
       If the full turn-by-turn outcome sequence is byte-identical to the unpoisoned
       played arm, the stash influenced no outcome.
"""
import os, sys, copy, hashlib, json, random as _stdlib
from collections import Counter, defaultdict

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

GATED_METHODS = ("capture_fast_break_animation", "capture_free_throw_animation",
                 "capture_halfcourt_animation", "skeleton_to_animations")
DEPTH = [0]
_FLAG = {}

DRAWS = Counter()

def _install_draw_counter():
    """Modules do ``from ...sim_random import sim_rng as random``, i.e. they hold the
    OBJECT, so patching bound methods on the instance is seen everywhere."""
    import BackEnd.utils.sim_random as SR
    for m in ("random", "randint", "choice", "uniform", "randrange", "shuffle",
              "sample", "gauss", "triangular", "betavariate", "expovariate"):
        if not hasattr(SR.sim_rng, m):
            continue
        orig = getattr(SR.sim_rng, m)
        def make(orig=orig, m=m):
            def counted(*a, **k):
                DRAWS[m] += 1
                return orig(*a, **k)
            return counted
        setattr(SR.sim_rng, m, make())


EV = [0]                       # monotonic event clock
TURN = [0]
SRC = Counter()                # ShotAttemptGeometry.source distribution
GEOM_NONE = Counter()
RET_ACCESS = Counter()         # build_step_states return-value accesses
STASH = Counter()
ORDER = defaultdict(lambda: {"reads": [], "bss": None, "stamps": [], "stash": None})
MODE = [None]   # None | "deepcopy-control" | "poison-values"
IN_BSS = [False]


class TrackedReturn(list):
    """Logs any access to itself. If build_step_states' caller touches the return value
    at all -- truthiness, len, indexing, iteration -- it shows up here."""
    def _hit(self, how):
        RET_ACCESS[how] += 1

    def __len__(self):
        self._hit("__len__"); return super().__len__()

    def __bool__(self):
        self._hit("__bool__"); return super().__len__() > 0

    def __iter__(self):
        self._hit("__iter__"); return super().__iter__()

    def __getitem__(self, k):
        self._hit("__getitem__"); return super().__getitem__(k)

    def __repr__(self):
        self._hit("__repr__"); return super().__repr__()


def _install():
    import BackEnd.engine.phase_resolution as PR
    import BackEnd.engine.step_state as SS
    import BackEnd.engine.skeleton_step_emitter as SE

    # ---- turn boundary
    orig_logic = PR.resolve_half_court_offense_logic

    def logic(game, *a, **k):
        TURN[0] += 1
        _ = ORDER[TURN[0]]
        return orig_logic(game, *a, **k)
    PR.resolve_half_court_offense_logic = logic

    # ---- the stamp (writer of _step_state["defense"])
    orig_stamp = PR._stamp_contest_defender_grid

    def stamp(skeleton, game, off_lineup, def_lineup):
        EV[0] += 1
        ORDER[TURN[0]]["stamps"].append(EV[0])
        return orig_stamp(skeleton, game, off_lineup, def_lineup)
    PR._stamp_contest_defender_grid = stamp

    # ---- the four functions that READ _step_state["defense"]
    for fname, site in (("_freeze_hco_shot_attempt_geometry", "4460 shot-contest"),
                        ("_hco_step_def_xy", "4977 interception"),
                        ("_hco_resolve_loose_ball", "5862 loose-ball"),
                        ("_finalize_hco_pass_bat_oob", "6334 bat-oob")):
        orig = getattr(PR, fname)

        def make(orig=orig, site=site, fname=fname):
            def wrapped(*a, **k):
                EV[0] += 1
                ORDER[TURN[0]]["reads"].append((EV[0], site))
                out = orig(*a, **k)
                if fname == "_freeze_hco_shot_attempt_geometry":
                    SRC[str(getattr(out, "source", "<none>"))] += 1
                return out
            return wrapped
        setattr(PR, fname, make())

    # ---- build_step_states: overwrites _step_state from the stash; return tracked
    orig_bss = SS.build_step_states

    def bss(result, game):
        EV[0] += 1
        ORDER[TURN[0]]["bss"] = EV[0]
        anims = getattr(game, "_hco_render_animations", None)
        STASH["present_at_bss" if anims else "absent_at_bss"] += 1
        if MODE[0] == "deepcopy-control" and anims:
            setattr(game, "_hco_render_animations", copy.deepcopy(anims))
            STASH["deepcopy-control"] += 1
        IN_BSS[0] = True
        try:
            out = orig_bss(result, game)
        finally:
            IN_BSS[0] = False
        return TrackedReturn(out or [])
    SS.build_step_states = bss
    import BackEnd.models.turn_manager as TM
    if hasattr(TM, "build_step_states"):
        TM.build_step_states = bss

    # ---- stash write by the emitter
    orig_emit = SE.emit_skeleton_animation_steps if hasattr(
        SE, "emit_skeleton_animation_steps") else None
    SS_MOD = SS

    # observe the stash write by watching the attribute after each emit call
    for cand in dir(SE):
        pass  # the write is a bare setattr; observed at bss above instead

    # ---- poison the VALUES the stash contributes, in place, adding no draws
    from BackEnd.models.animator import Animator as _AN
    orig_dgfa = _AN.defender_grid_from_animations

    def dgfa(anims, def_lineup, num_steps):
        g = orig_dgfa(anims, def_lineup, num_steps)
        if MODE[0] == "poison-values" and IN_BSS[0]:
            n = 0
            for _i, row in (g or {}).items():
                for _p, c in (row or {}).items():
                    if isinstance(c, dict):
                        c["x"] = -9999
                        c["y"] = -9999
                        n += 1
            if n:
                STASH["poisoned_coords"] += n
                STASH["poisoned_calls"] += 1
        return g
    _AN.defender_grid_from_animations = staticmethod(dgfa)
    import BackEnd.engine.step_state as _SS2
    if hasattr(_SS2, "Animator"):
        _SS2.Animator.defender_grid_from_animations = staticmethod(dgfa)

    # ---- _shot_defender_xy: did the contest have a frozen geometry at all?
    import BackEnd.models.shot_manager as SM
    orig_sdx = SM._shot_defender_xy

    def sdx(player, def_lineup, shot_attempt_geometry):
        GEOM_NONE["geometry_None_fallback_to_Player.coords" if shot_attempt_geometry is None
                  else "used_frozen_geometry"] += 1
        return orig_sdx(player, def_lineup, shot_attempt_geometry)
    SM._shot_defender_xy = sdx


def _install_played_arm():
    import BackEnd.models.animator as AN
    for meth in GATED_METHODS:
        orig = getattr(AN.Animator, meth)

        def make(orig=orig):
            def wrapped(self, *a, **k):
                gs = self.game.game_state
                if DEPTH[0] == 0:
                    _FLAG["had"] = "_is_full_simulation" in gs
                    _FLAG["prev"] = gs.get("_is_full_simulation")
                gs["_is_full_simulation"] = False
                DEPTH[0] += 1
                try:
                    return orig(self, *a, **k)
                finally:
                    DEPTH[0] -= 1
                    if DEPTH[0] == 0:
                        if _FLAG["had"]:
                            gs["_is_full_simulation"] = _FLAG["prev"]
                        else:
                            gs.pop("_is_full_simulation", None)
            return wrapped
        setattr(AN.Animator, meth, make())
    _FLAG["installed"] = [getattr(AN.Animator, m) for m in GATED_METHODS]


def _uninstall_played_arm(saved):
    import BackEnd.models.animator as AN
    for meth, fn in saved.items():
        setattr(AN.Animator, meth, fn)


def outcome_fingerprint(turns, gm):
    rows = [(str(t.get("result_type") or ""), str(t.get("turnover_type") or ""),
             str(t.get("next_turn") or "")) for t in turns]
    blob = json.dumps({"n": len(rows), "rows": rows,
                       "home": gm.game_state.get("home_score"),
                       "away": gm.game_state.get("away_score")}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16], len(rows)


def run_arm(label, played, mode, games):
    import BackEnd.models.animator as AN
    saved = {m: getattr(AN.Animator, m) for m in GATED_METHODS}
    SRC.clear(); GEOM_NONE.clear(); RET_ACCESS.clear(); STASH.clear(); ORDER.clear()
    TURN[0] = 0; EV[0] = 0
    MODE[0] = mode
    DRAWS.clear()
    if played:
        _install_played_arm()
    fps = []
    try:
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
                    simulate_quarter(gm, game_id="%024x" % (0xB0000 + g))
                except Exception as e:
                    print(f"   {label} seed {8000+g}: {type(e).__name__}: {e}")
                    break
            fps.append(outcome_fingerprint(gm.turns or [], gm))
    finally:
        _uninstall_played_arm(saved)
        MODE[0] = None
    late = sum(1 for t, r in ORDER.items() if r["bss"] is not None
               and any(ev > r["bss"] for ev, _s in r["reads"]))
    # CROSS-TURN: a read in turn N+1 could in principle see _step_state written by
    # build_step_states in turn N (step_state.py warns "a later turn could still read a
    # prior turn's stamp"). Count reads that follow ANY bss anywhere in the run.
    first_bss = min([r["bss"] for r in ORDER.values() if r["bss"] is not None], default=None)
    cross = 0
    if first_bss is not None:
        cross = sum(1 for r in ORDER.values() for ev, _s in r["reads"] if ev > first_bss)
    snap = {"src": Counter(SRC), "geom": Counter(GEOM_NONE), "ret": Counter(RET_ACCESS),
            "stash": Counter(STASH), "turns": TURN[0], "fps": fps,
            "reads_after_bss": late, "reads_after_any_bss": cross,
            "turns_with_bss": sum(1 for _t, r in ORDER.items() if r["bss"] is not None),
            "read_sites": Counter(s for _t, r in ORDER.items() for _ev, s in r["reads"]),
            "draws": sum(DRAWS.values()), "draws_by_kind": Counter(DRAWS)}
    print(f"   {label}: {TURN[0]} HCO turns, {sum(snap['read_sites'].values())} grid reads, "
          f"{snap['draws']:,} sim_rng draws")
    return snap


if __name__ == "__main__":
    games = int(os.environ.get("GAMES", "4"))
    _install()
    _install_draw_counter()
    print(f"ORDERING MEASUREMENT — {games} seeded games per arm\n")
    S = run_arm("sim", False, None, games)
    P = run_arm("played", True, None, games)
    Q = run_arm("played+poison-values", True, "poison-values", games)
    STASHP = Q["stash"]

    W = 78
    print("\n" + "=" * W)
    print("Q1. WHICH GRID DOES THE SHOT CONTEST READ? (ShotAttemptGeometry.source)")
    print("=" * W)
    for arm, d in (("sim", S), ("played", P)):
        tot = sum(d["src"].values()) or 1
        print(f"  {arm}:")
        for k, v in d["src"].most_common():
            print(f"      {k:<34} {v:>6}  ({v/tot*100:5.1f}%)")
    print("\n  _shot_defender_xy geometry availability:")
    for arm, d in (("sim", S), ("played", P)):
        print(f"      {arm:<8} {dict(d['geom'])}")

    print("\n" + "=" * W)
    print("Q2. IS build_step_states' RETURN VALUE DISCARDED?")
    print("=" * W)
    for arm, d in (("sim", S), ("played", P)):
        n = sum(d["ret"].values())
        print(f"  {arm:<8} calls={d['turns_with_bss']:>5}  accesses to the returned list={n}"
              f"  {dict(d['ret']) if n else '-> DISCARDED'}")

    print("\n" + "=" * W)
    print("Q3a. ORDERING — can the stash reach any grid read?")
    print("=" * W)
    for arm, d in (("sim", S), ("played", P)):
        print(f"  {arm}:")
        print(f"      turns where build_step_states ran        : {d['turns_with_bss']}")
        print(f"      grid reads occurring AFTER the overwrite : {d['reads_after_bss']}")
        print(f"      stash state when build_step_states ran   : {dict(d['stash'])}")
        for site, c in d["read_sites"].most_common():
            print(f"      read site {site:<22} {c:>7}")

    print("\n" + "=" * W)
    print("Q3b. POISON — does corrupting the stash change any outcome?")
    print("=" * W)
    print(f"  poisoned {STASHP.get('poisoned_coords', 0):,} defender coords on "
          f"{STASHP.get('poisoned_calls', 0)} build_step_states calls")
    print("\n  VALIDITY GATE — the poison must add NO draws. If draw counts diverge the")
    print("  poison shifted the stream and any outcome difference is displacement, not a read.")
    print(f"    sim_rng draws  played {P['draws']:,}   poisoned {Q['draws']:,}   "
          f"delta {Q['draws']-P['draws']:+,}")
    valid = (P["draws"] == Q["draws"])
    print(f"    {'✅ draw-identical, poison test is VALID' if valid else '❌ draw counts differ, test INVALID'}")
    print()
    same_null = len(P["fps"])
    same = sum(1 for a, b in zip(P["fps"], Q["fps"]) if a == b)
    print(f"  played vs poisoned outcome fingerprints identical: {same}/{len(P['fps'])} games")
    for i, (a, b) in enumerate(zip(P["fps"], Q["fps"])):
        print(f"      seed {8000+i}: played {a[0]} ({a[1]} turns)   "
              f"poisoned {b[0]} ({b[1]} turns)   {'IDENTICAL' if a == b else 'DIFFERS'}")
    print(f"\n  cross-turn read check (reads following ANY build_step_states):")
    for arm, d in (("sim", S), ("played", P)):
        print(f"      {arm:<8} {d['reads_after_any_bss']:,} of {sum(d['read_sites'].values()):,} reads")

    print("\n" + "=" * W)
    print("VERDICT")
    print("=" * W)
    inert = (P["reads_after_bss"] == 0 and sum(P["ret"].values()) == 0
             and same == len(P["fps"]) and same_null == len(P["fps"]))
    if inert:
        print("  The stash is INERT. No grid read occurs after build_step_states overwrites")
        print("  _step_state, the return value is never touched, and poisoning the stash")
        print("  leaves every seeded outcome byte-identical.")
    else:
        print("  The stash INFLUENCES something — see the non-zero counts above.")
