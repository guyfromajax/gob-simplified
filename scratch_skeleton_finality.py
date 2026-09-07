"""Is the contest placing defenders against an UNFINISHED skeleton?

THE CLAIM UNDER TEST is compute_defender_grid's own docstring (animator.py:1242-1244):
the contest and the render "compute defender positions from ONE identical" computation.
Two docstrings already hedge it:
  - _stamp_contest_defender_grid (phase_resolution.py:5907-5911): it runs pre-emit because
    "the emit's exact stash isn't available yet -- the contest still truncates the skeleton
    the emit draws; ~2px RNG from the literal draw, IMMATERIAL against the lane band", and
    it is called before the walk AND before the coverage pass "(final skeleton, which may
    carry recalibrated/expanded steps the pre-walk stamp didn't cover)".
  - phase_resolution.py:7418 adds a third stamp because "freelance beats are appended AFTER
    the walk's pre-stamp".
So the code says the inputs differ and asserts the consequence is ~2px. That assertion is
what gets measured here.

WHAT IS MEASURED, per HCO turn, played arm:
  1. INPUT DIFFERENCE. Fingerprint the skeleton at each compute_defender_grid call (the
     contest's producer) and at each skeleton_to_animations call (the render's producer):
     step count, and per-step (pos, action, x, y) signature. Structural and content deltas.
  2. FIT TO FINAL. The render's skeleton is the finished play -- where players actually end
     up. So score BOTH grids against the SAME final offense coords: mean distance from each
     placed defender to the nearest final offensive player. If the contest's grid was built
     against incomplete data its defenders sit FARTHER from where the offense really is.
     Restricted to HOME-offense turns, because away skeletons are x-flipped and mixing
     frames would scramble the distances.
  3. RNG NOISE FLOOR. The separator between "differs because of INPUTS" and "differs
     because of a second draw". sim_rng is a stdlib Random, so the probe snapshots its
     state, re-runs the producer on the IDENTICAL skeleton with the state restored (must be
     bit-identical -> code is deterministic given input), then once more WITHOUT restoring
     (same skeleton, next draw -> pure RNG variation), and finally restores the post-call
     state so the game's own stream is untouched. Any measured gap larger than this floor
     cannot be explained by the second draw.
"""
import os, sys, copy, math, statistics as st, random as _stdlib
from collections import Counter

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
from BackEnd.utils.sim_random import sim_rng
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter
from BackEnd.models.animator import Animator

GATED_METHODS = ("capture_fast_break_animation", "capture_free_throw_animation",
                 "capture_halfcourt_animation", "skeleton_to_animations")
DEPTH = [0]
_PATCHED = {}

TURN = [0]
REC = {}
NOISE = {"checked": 0, "deterministic": 0, "coord_deltas": [], "fit_deltas": []}
SAMPLE_EVERY = 12          # noise-floor probe is 3x the cost of the real call; sample it


def step_sig(step):
    pa = step.get("pos_actions") or {}
    out = []
    for p, a in (pa or {}).items():
        a = a or {}
        c = a.get("coords") or {}
        out.append((str(p), str(a.get("action") or ""),
                    round(float(c.get("x", -999) or -999), 1),
                    round(float(c.get("y", -999) or -999), 1)))
    return tuple(sorted(out))


def fingerprint(skeleton):
    return [step_sig(s) for s in ((skeleton or {}).get("steps") or [])]


def offense_by_step(skeleton):
    out = []
    for s in ((skeleton or {}).get("steps") or []):
        d = {}
        for p, a in (s.get("pos_actions") or {}).items():
            c = ((a or {}).get("coords") or {})
            if "x" in c and "y" in c:
                d[str(p)] = (float(c["x"]), float(c["y"]))
        out.append(d)
    return out


def fit_to_final(grid, final_off):
    """Mean distance from each placed defender to the NEAREST final offensive player.
    Lower = the placement matches where the offense actually ended up."""
    ds = []
    for i, off in enumerate(final_off):
        if not off:
            continue
        row = (grid or {}).get(i) or {}
        for _dpos, c in row.items():
            if not c:
                continue
            try:
                dx, dy = float(c["x"]), float(c["y"])
            except Exception:
                continue
            best = min((math.hypot(dx - ox, dy - oy) for (ox, oy) in off.values()),
                       default=None)
            if best is not None:
                ds.append(best)
    return ds


def grid_coord_delta(g1, g2):
    ds = []
    for i in set(g1) & set(g2):
        r1, r2 = g1.get(i) or {}, g2.get(i) or {}
        for p in set(r1) & set(r2):
            a, b = r1.get(p), r2.get(p)
            if not a or not b:
                continue
            ds.append(math.hypot(float(a["x"]) - float(b["x"]),
                                 float(a["y"]) - float(b["y"])))
    return ds


def _install_instruments():
    import BackEnd.engine.phase_resolution as PR

    orig_logic = PR.resolve_half_court_offense_logic

    def logic(game, *a, **k):
        TURN[0] += 1
        REC[TURN[0]] = {"contest": [], "render": [],
                        "away": bool(getattr(game, "offense_team", None) is
                                     getattr(game, "away_team", None))}
        return orig_logic(game, *a, **k)
    PR.resolve_half_court_offense_logic = logic

    orig_cdg = Animator.compute_defender_grid

    def cdg(self, skeleton, off_lineup, def_lineup, is_fcp=False, is_hct=False):
        fp = fingerprint(skeleton)
        off = offense_by_step(skeleton)
        pre = sim_rng.getstate()
        grid = orig_cdg(self, skeleton, off_lineup, def_lineup, is_fcp=is_fcp, is_hct=is_hct)
        post = sim_rng.getstate()

        NOISE["checked"] += 1
        if NOISE["checked"] % SAMPLE_EVERY == 0:
            # same skeleton, same RNG state -> must be bit-identical
            sim_rng.setstate(pre)
            g_same = orig_cdg(self, skeleton, off_lineup, def_lineup,
                              is_fcp=is_fcp, is_hct=is_hct)
            # same skeleton, NEXT RNG state -> pure second-draw variation
            g_next = orig_cdg(self, skeleton, off_lineup, def_lineup,
                              is_fcp=is_fcp, is_hct=is_hct)
            sim_rng.setstate(post)          # game's stream restored; probe is invisible
            if not grid_coord_delta(grid, g_same) or max(grid_coord_delta(grid, g_same)) == 0:
                NOISE["deterministic"] += 1
            NOISE["coord_deltas"].extend(grid_coord_delta(grid, g_next))
            f1, f2 = fit_to_final(grid, off), fit_to_final(g_next, off)
            if f1 and f2:
                NOISE["fit_deltas"].append(st.mean(f2) - st.mean(f1))

        if TURN[0] in REC:
            REC[TURN[0]]["contest"].append(
                {"fp": fp, "off": off, "grid": copy.deepcopy(grid)})
        return grid
    Animator.compute_defender_grid = cdg

    orig_s2a = Animator.skeleton_to_animations

    def s2a(self, skeleton, off_lineup, def_lineup, add_defenders=True,
            is_fcp=False, is_hct=False):
        fp = fingerprint(skeleton)
        off = offense_by_step(skeleton)
        anims = orig_s2a(self, skeleton, off_lineup, def_lineup,
                         add_defenders=add_defenders, is_fcp=is_fcp, is_hct=is_hct)
        try:
            grid = Animator.defender_grid_from_animations(anims, def_lineup, len(fp))
        except Exception:
            grid = {}
        if TURN[0] in REC:
            REC[TURN[0]]["render"].append(
                {"fp": fp, "off": off, "grid": copy.deepcopy(grid)})
        return anims
    Animator.skeleton_to_animations = s2a
    _PATCHED["skeleton_to_animations"] = s2a


def _install_played_arm():
    import BackEnd.models.animator as AN
    for meth in GATED_METHODS:
        orig = getattr(AN.Animator, meth)

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
    games = int(os.environ.get("GAMES", "4"))
    _install_instruments()
    _install_played_arm()
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
                simulate_quarter(gm, game_id="%024x" % (0xA0000 + g))
            except Exception as e:
                print(f"  seed {8000+g}: {type(e).__name__}: {e}")
                break
        print(f"  seed {8000+g}: {TURN[0]} HCO turns instrumented")

    paired = [(t, r) for t, r in REC.items() if r["contest"] and r["render"]]
    print("\n" + "=" * 78)
    print(f"COVERAGE: {len(REC)} HCO turns, {len(paired)} with BOTH a contest grid and a render grid")
    print("=" * 78)
    print(f"  turns with >1 contest stamp : "
          f"{sum(1 for _t, r in paired if len(r['contest']) > 1)}")
    print(f"  contest stamps per turn     : "
          f"{st.mean([len(r['contest']) for _t, r in paired]):.2f} mean")

    print("\n" + "=" * 78)
    print("1. INPUT DIFFERENCE — is the contest's skeleton the same object of study?")
    print("   (contest = LAST stamp before the render, i.e. its best-informed grid)")
    print("=" * 78)
    step_delta = Counter()
    content_diff_steps = same_steps = 0
    ident_turns = 0
    for _t, r in paired:
        c = r["contest"][-1]
        v = r["render"][-1]
        d = len(v["fp"]) - len(c["fp"])
        step_delta[d] += 1
        n = min(len(c["fp"]), len(v["fp"]))
        this_diff = 0
        for i in range(n):
            if c["fp"][i] == v["fp"][i]:
                same_steps += 1
            else:
                content_diff_steps += 1
                this_diff += 1
        if d == 0 and this_diff == 0:
            ident_turns += 1
    tot = same_steps + content_diff_steps
    print(f"  turns where render skeleton has MORE steps : "
          f"{sum(v for k, v in step_delta.items() if k > 0)}")
    print(f"  turns with the same step count            : {step_delta.get(0, 0)}")
    print(f"  turns where render has FEWER steps        : "
          f"{sum(v for k, v in step_delta.items() if k < 0)}")
    print(f"  step-count delta (render - contest)       : "
          f"{dict(sorted(step_delta.items()))}")
    print(f"  shared steps with IDENTICAL content       : {same_steps}/{tot} "
          f"({same_steps/tot*100:.1f}%)" if tot else "  no shared steps")
    print(f"  shared steps with DIFFERENT content       : {content_diff_steps}/{tot} "
          f"({content_diff_steps/tot*100:.1f}%)" if tot else "")
    print(f"  turns byte-identical on BOTH count+content: {ident_turns}/{len(paired)} "
          f"({ident_turns/len(paired)*100:.1f}%)" if paired else "")

    print("\n" + "=" * 78)
    print("2. FIT TO FINAL — both grids scored against the SAME final offense coords")
    print("   (home-offense turns only; lower = defenders match where offense really is)")
    print("=" * 78)
    cf, vf = [], []
    for _t, r in paired:
        if r["away"]:
            continue
        final_off = r["render"][-1]["off"]
        a = fit_to_final(r["contest"][-1]["grid"], final_off)
        b = fit_to_final(r["render"][-1]["grid"], final_off)
        if a:
            cf.append(st.mean(a))
        if b:
            vf.append(st.mean(b))
    if cf and vf:
        print(f"  contest grid  : {st.mean(cf):6.3f} grid mean nearest-offense distance  (n={len(cf)} turns)")
        print(f"  render  grid  : {st.mean(vf):6.3f} grid mean nearest-offense distance  (n={len(vf)} turns)")
        print(f"  contest is    : {st.mean(cf) - st.mean(vf):+.3f} grid "
              f"({(st.mean(cf)-st.mean(vf))/st.mean(vf)*100:+.1f}%) "
              f"{'LOOSER (worse fit)' if st.mean(cf) > st.mean(vf) else 'TIGHTER'}")
    else:
        print("  insufficient home-offense sample")

    print("\n" + "=" * 78)
    print("2b. DIRECT GRID-vs-GRID — do the two producers place the SAME defender in the")
    print("    SAME place at the SAME step? This is the quantity the contest actually reads.")
    print("    Split by whether that step's offensive content was identical, which is the")
    print("    only way to separate an INPUT effect from a code/draw effect.")
    print("=" * 78)
    same_c, diff_c = [], []
    for _t, r in paired:
        c, v = r["contest"][-1], r["render"][-1]
        for i in set(c["grid"]) & set(v["grid"]):
            if i >= len(c["fp"]) or i >= len(v["fp"]):
                continue
            bucket = same_c if c["fp"][i] == v["fp"][i] else diff_c
            r1, r2 = c["grid"].get(i) or {}, v["grid"].get(i) or {}
            for p in set(r1) & set(r2):
                a, b = r1.get(p), r2.get(p)
                if not a or not b:
                    continue
                bucket.append(math.hypot(float(a["x"]) - float(b["x"]),
                                         float(a["y"]) - float(b["y"])))
    for lbl, ds in (("steps with IDENTICAL content", same_c),
                    ("steps with DIFFERENT content", diff_c)):
        if ds:
            s = sorted(ds)
            print(f"  {lbl:<32} n={len(ds):>6}  mean {st.mean(ds):6.3f}  "
                  f"median {st.median(ds):6.3f}  p95 {s[int(len(s)*0.95)]:6.3f}  "
                  f"max {s[-1]:6.2f}  |  exact match {sum(1 for d in ds if d == 0)/len(ds)*100:5.1f}%")
        else:
            print(f"  {lbl:<32} no samples")

    print("\n" + "=" * 78)
    print("2c. WHICH placement is the incomplete one? Fit-to-final on ONLY the steps that")
    print("    disagree — where the whole effect lives. Away turns INCLUDED: an x-flip")
    print("    inflates both grids' absolute distances identically (they are scored against")
    print("    the SAME reference), so it is common-mode and cancels in the comparison.")
    print("=" * 78)
    cd_, vd_ = [], []
    orphan_steps = 0
    for _t, r in paired:
        c, v = r["contest"][-1], r["render"][-1]
        final_off = v["off"]
        # steps the render draws that the contest NEVER placed against at all
        orphan_steps += max(0, len(v["fp"]) - len(c["fp"]))
        idx = [i for i in set(c["grid"]) & set(v["grid"])
               if i < len(c["fp"]) and i < len(v["fp"]) and c["fp"][i] != v["fp"][i]]
        if not idx:
            continue
        sub_off = [final_off[i] if i < len(final_off) else {} for i in idx]
        a = fit_to_final({j: c["grid"][i] for j, i in enumerate(idx)}, sub_off)
        b = fit_to_final({j: v["grid"][i] for j, i in enumerate(idx)}, sub_off)
        if a:
            cd_.append(st.mean(a))
        if b:
            vd_.append(st.mean(b))
    if cd_ and vd_:
        print(f"  contest grid on differing steps : {st.mean(cd_):6.3f} grid  (n={len(cd_)} turns)")
        print(f"  render  grid on differing steps : {st.mean(vd_):6.3f} grid  (n={len(vd_)} turns)")
        gap = st.mean(cd_) - st.mean(vd_)
        print(f"  contest is {gap:+.3f} grid ({gap/st.mean(vd_)*100:+.1f}%) "
              f"{'WORSE-FITTED (placed against incomplete data)' if gap > 0 else 'BETTER-FITTED'}")
        print(f"  noise band from a second draw is +/-0.104 grid, so this "
              f"{'IS' if abs(gap) > 0.312 else 'is NOT'} outside it")
    else:
        print("  insufficient sample")
    print(f"  steps the render draws that the contest never placed at all: {orphan_steps}")

    print("\n" + "=" * 78)
    print("3. RNG NOISE FLOOR — how much of any gap a SECOND DRAW alone can explain")
    print("=" * 78)
    print(f"  determinism check (same skeleton + same RNG state -> identical grid): "
          f"{NOISE['deterministic']}/{NOISE['checked']//SAMPLE_EVERY} samples identical")
    if NOISE["coord_deltas"]:
        cd = NOISE["coord_deltas"]
        print(f"  same-skeleton second-draw coord delta : mean {st.mean(cd):.3f} grid, "
              f"median {st.median(cd):.3f}, p95 {sorted(cd)[int(len(cd)*0.95)]:.3f} (n={len(cd)})")
        print(f"  docstring asserts this is ~2px. Court is 100 grid wide.")
    if NOISE["fit_deltas"]:
        fd = NOISE["fit_deltas"]
        print(f"  second-draw FIT delta                 : mean {st.mean(fd):+.3f} grid, "
              f"stdev {st.stdev(fd):.3f} (n={len(fd)})")
        print("  ^ this is the noise band. A fit gap in section 2 far outside it is INPUTS.")
