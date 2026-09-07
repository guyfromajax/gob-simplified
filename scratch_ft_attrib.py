"""Attribute the played arm's +52% free-throw AWARDS. equiv-v2 arm definition.

THE CHAIN, verified at file:line (not assumed):
  defender placement
    -> distance to the shot
    -> _proximity_contest_factor(dist)            shot_manager.py:235-246, in [FLOOR, 1.0]
    -> defense_score *= proximity_factor          shot_manager.py:3018
    -> check_defensive_foul_on_shot(defense_score) shot_manager.py:3025 -> 3170-3175
    -> shooting foul -> free throws

DIRECTION MATTERS AND IT IS INVERSE TO THE OBVIOUS GUESS. The foul fires when defense_score
is BELOW a threshold, and proximity SCALES defense_score DOWN as the defender gets farther.
So a FARTHER defender fouls MORE. "Tighter defenders producing more contact" predicts the
wrong sign here. More free throws in the played arm implies LOOSER coverage at the shot.

THREE CHANNELS, all live, which is why this is a decomposition and not a single number:
  A. PLACEMENT VALUES  - proximity distribution differs between arms.
  B. VOLUME            - more entries into the foul check (more contested shots).
  C. STREAM DISPLACEMENT - shot_manager.py:1 aliases sim_rng as `random`, so the foul roll
     AND the randint(1,6) in defense_score are both on-stream. The animator's ~6k extra
     sim_rng draws per half displace every subsequent roll, so rolls differ arbitrarily.
     This is the null hypothesis. It is NOT ruled out by counting, only bounded.

FT awards decompose exactly as  entries x foul-rate-per-entry.  Channel B is the entries
term. Whether the foul-rate term is A or C is read off the proximity distribution: if the
arms' proximity distributions match but the foul rate diverges, it is C.
"""
import os, sys, statistics as st, random as _stdlib
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
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter
import BackEnd.models.shot_manager as SM

GATED_METHODS = ("capture_fast_break_animation", "capture_free_throw_animation",
                 "capture_halfcourt_animation", "skeleton_to_animations")
DEPTH = [0]
_PATCHED = {}
OBS = {}


def _reset():
    OBS.clear()
    OBS.update(dists=[], factors=[], scores=[], entries=0, fouls=0,
               bucket=Counter(), floor=0, tight=0, prox_calls=0, prox_none=0, shots=0)


def _install_instruments():
    """Wrap the two chain links. Both arms get the SAME instruments, so any asymmetry
    in the numbers is the arms, not the probe."""
    orig_prox = SM._proximity_contest_factor

    def prox(dist):
        f = orig_prox(dist)
        OBS["prox_calls"] += 1
        if dist is None:
            OBS["prox_none"] += 1
        else:
            d = float(dist)
            OBS["dists"].append(d)
            OBS["factors"].append(f)
            if d <= 3.0:
                OBS["tight"] += 1
            if f <= min(orig_prox(99.0), 1.0):
                OBS["floor"] += 1
        return f
    SM._proximity_contest_factor = prox

    # The entries term dominates the decomposition, and "more entries" has two very
    # different readings: more shots taken, or the same shots more often CONTESTED. Only
    # the second is placement-attributable, so count the denominator too.
    orig_score = SM.ShotManager.calculate_shot_score

    def score(self, *a, **k):
        OBS["shots"] += 1
        return orig_score(self, *a, **k)
    SM.ShotManager.calculate_shot_score = score

    orig_foul = SM.ShotManager.check_defensive_foul_on_shot

    def foul(self, defender, defense_score, shot_type, shooter=None, shooter_location=None):
        out = orig_foul(self, defender, defense_score, shot_type, shooter, shooter_location)
        if defender:
            OBS["entries"] += 1
            OBS["scores"].append(float(defense_score or 0))
            OBS["bucket"][str(shot_type)] += 1
            if out[0]:
                OBS["fouls"] += 1
        return out
    SM.ShotManager.check_defensive_foul_on_shot = foul


def _install_played_arm():
    import BackEnd.models.animator as AN
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
    import BackEnd.models.animator as AN
    for meth in GATED_METHODS:
        if meth in _PATCHED:
            setattr(AN.Animator, meth, _PATCHED[meth])


def ft_awards(turns):
    return sum(1 for t in turns if str(t.get("next_turn") or "").upper() == "FREE_THROW")


def ft_honoured(turns, window=3):
    aw = ho = 0
    for i, t in enumerate(turns):
        if str(t.get("next_turn") or "").upper() != "FREE_THROW":
            continue
        aw += 1
        if any(str(turns[j].get("result_type") or "").upper() == "FREE_THROW"
               for j in range(i + 1, min(i + 1 + window, len(turns)))):
            ho += 1
    return aw, ho


def run_arm(label, played, games):
    rows = []
    if played:
        _install_played_arm()
    try:
        for g in range(games):
            _reset()
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
                    simulate_quarter(gm, game_id="%024x" % (0xF0000 + g))
                except Exception as e:
                    print(f"   {label} seed {8000+g}: {type(e).__name__}: {e}")
                    break
            turns = gm.turns or []
            aw, ho = ft_honoured(turns)
            rows.append({
                "awards": aw, "honoured": ho, "turns": len(turns),
                "entries": OBS["entries"], "fouls": OBS["fouls"], "shots": OBS["shots"],
                "scores": list(OBS["scores"]), "dists": list(OBS["dists"]),
                "factors": list(OBS["factors"]),
                "tight": OBS["tight"], "floor": OBS["floor"],
                "prox_calls": OBS["prox_calls"], "prox_none": OBS["prox_none"],
            })
            print(f"   {label} seed {8000+g}: awards={aw} entries={OBS['entries']} "
                  f"fouls={OBS['fouls']} prox={OBS['prox_calls']}")
    finally:
        if played:
            _uninstall_played_arm()
    return rows


def agg(rows):
    n = len(rows)
    allsc = [s for r in rows for s in r["scores"]]
    alld = [d for r in rows for d in r["dists"]]
    allf = [f for r in rows for f in r["factors"]]
    tot_e = sum(r["entries"] for r in rows)
    return {
        "n": n,
        "awards": sum(r["awards"] for r in rows) / n,
        "honoured": sum(r["honoured"] for r in rows) / n,
        "turns": sum(r["turns"] for r in rows) / n,
        "entries": tot_e / n,
        "shots": sum(r["shots"] for r in rows) / n,
        "contest_share": (tot_e / sum(r["shots"] for r in rows) * 100) if sum(r["shots"] for r in rows) else 0.0,
        "fouls": sum(r["fouls"] for r in rows) / n,
        "foul_rate": (sum(r["fouls"] for r in rows) / tot_e * 100) if tot_e else 0.0,
        "score_mean": st.mean(allsc) if allsc else 0.0,
        "score_med": st.median(allsc) if allsc else 0.0,
        "prox_calls": sum(r["prox_calls"] for r in rows) / n,
        "prox_graded": len(alld) / n,
        "dist_mean": st.mean(alld) if alld else float("nan"),
        "dist_med": st.median(alld) if alld else float("nan"),
        "factor_mean": st.mean(allf) if allf else float("nan"),
        "tight_pct": (sum(r["tight"] for r in rows) / len(alld) * 100) if alld else float("nan"),
        "floor_pct": (sum(r["floor"] for r in rows) / len(alld) * 100) if alld else float("nan"),
    }


def pct(a, b):
    return f"{(b - a) / a * 100:+.1f}%" if a else "n/a"


if __name__ == "__main__":
    games = int(os.environ.get("GAMES", "8"))
    _install_instruments()
    print(f"FT ATTRIBUTION — equiv-v2 arms, {games} seeded games each\n")
    print(" sim arm:")
    sim = run_arm("sim", False, games)
    print(" played arm:")
    pl = run_arm("played", True, games)
    S, P = agg(sim), agg(pl)

    print("\n" + "=" * 78)
    print("SANITY INVARIANT (required — if this fails no number below is reportable)")
    print("=" * 78)
    hs = S["honoured"] / S["awards"] * 100 if S["awards"] else 0
    hp = P["honoured"] / P["awards"] * 100 if P["awards"] else 0
    print(f"  FT awards honoured   sim {hs:5.1f}%   played {hp:5.1f}%   gap {abs(hs-hp):.1f}pp")
    print("  " + ("✅ arms agree, harness trustworthy" if abs(hs - hp) <= 3.0
                  else "❌ ARMS DISAGREE — harness is lying, discard this run"))

    print("\n" + "=" * 78)
    print("THE THING BEING EXPLAINED")
    print("=" * 78)
    print(f"  {'FT awards/game':<34} {S['awards']:>9.2f} {P['awards']:>9.2f}   {pct(S['awards'],P['awards'])}")
    print(f"  {'turns/game':<34} {S['turns']:>9.2f} {P['turns']:>9.2f}   {pct(S['turns'],P['turns'])}")

    print("\n" + "=" * 78)
    print("EXACT DECOMPOSITION:  shooting fouls = ENTRIES x FOUL-RATE-PER-ENTRY")
    print("=" * 78)
    print(f"  {'   shot-score calls (all shots)':<34} {S['shots']:>9.2f} {P['shots']:>9.2f}   {pct(S['shots'],P['shots'])}")
    print(f"  {'   x contested share (%)':<34} {S['contest_share']:>9.2f} {P['contest_share']:>9.2f}   {pct(S['contest_share'],P['contest_share'])}")
    print(f"  {'B. entries (contested shots)':<34} {S['entries']:>9.2f} {P['entries']:>9.2f}   {pct(S['entries'],P['entries'])}")
    print(f"  {'   foul-rate per entry (%)':<34} {S['foul_rate']:>9.2f} {P['foul_rate']:>9.2f}   {pct(S['foul_rate'],P['foul_rate'])}")
    print(f"  {'   shooting fouls/game':<34} {S['fouls']:>9.2f} {P['fouls']:>9.2f}   {pct(S['fouls'],P['fouls'])}")

    print("\n" + "=" * 78)
    print("WHY THE FOUL RATE MOVED:  defense_score vs the fixed thresholds")
    print("  (foul fires when defense_score is LOW, so a DROP here means MORE fouls)")
    print("=" * 78)
    print(f"  {'defense_score mean':<34} {S['score_mean']:>9.2f} {P['score_mean']:>9.2f}   {pct(S['score_mean'],P['score_mean'])}")
    print(f"  {'defense_score median':<34} {S['score_med']:>9.2f} {P['score_med']:>9.2f}   {pct(S['score_med'],P['score_med'])}")

    print("\n" + "=" * 78)
    print("CHANNEL A vs C:  is the PROXIMITY distribution different, or just the rolls?")
    print("=" * 78)
    print(f"  {'proximity calls/game':<34} {S['prox_calls']:>9.2f} {P['prox_calls']:>9.2f}   {pct(S['prox_calls'],P['prox_calls'])}")
    print(f"  {'graded (dist not None)/game':<34} {S['prox_graded']:>9.2f} {P['prox_graded']:>9.2f}   {pct(S['prox_graded'],P['prox_graded'])}")
    print(f"  {'defender dist mean (grid)':<34} {S['dist_mean']:>9.2f} {P['dist_mean']:>9.2f}   {pct(S['dist_mean'],P['dist_mean'])}")
    print(f"  {'defender dist median':<34} {S['dist_med']:>9.2f} {P['dist_med']:>9.2f}   {pct(S['dist_med'],P['dist_med'])}")
    print(f"  {'proximity factor mean':<34} {S['factor_mean']:>9.3f} {P['factor_mean']:>9.3f}   {pct(S['factor_mean'],P['factor_mean'])}")
    print(f"  {'tight (<=3 grid) %':<34} {S['tight_pct']:>9.2f} {P['tight_pct']:>9.2f}")
    print(f"  {'at open floor (>=9 grid) %':<34} {S['floor_pct']:>9.2f} {P['floor_pct']:>9.2f}")
    print("""
READING IT:
  proximity distribution SHIFTS OUTWARD in played  -> channel A, placement values. Commit 2
      would move this, and the sign tells you which direction convergence goes.
  proximity distribution MATCHES but foul rate moves -> channel C, stream displacement.
      Commit 2 removes the extra draws, so it would also move this — but by re-randomising,
      not by correcting anything. That distinction decides whether convergence is a fix.""")
