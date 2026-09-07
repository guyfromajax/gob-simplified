"""Fouled-3PT free-throw misaward probe. ONE arm, ONE seed, ONE process.

Measures the SYMPTOM as the user sees it -- how many free throws the shooter actually shot --
rather than which branch set the count. Walking the turn stream sidesteps the path question
entirely: for every shot turn that hands off to FREE_THROW, count the consecutive FREE_THROW
turns that follow and compare against the rule (made -> 1 and-one; missed -> 3 if the attempt
was a three, else 2).

Also records whether the [3PT-READ] diagnostic fired for each fouled shot, to settle whether
a foul short-circuits before it logs.
"""
import os, sys, json, logging, random as _stdlib
from collections import Counter

os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_DB_NAME", "gob-test")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("PYTHONHASHSEED") != "0":
    raise SystemExit("run with PYTHONHASHSEED=0")
ARM, SEED, OUT = os.environ.get("ARM", "played"), int(os.environ["SEED"]), os.environ["OUT"]

from BackEnd.db import players_collection, teams_collection
from tests.roster_fixtures import seed_universal_rosters
seed_universal_rosters(teams_collection, players_collection)
from BackEnd.utils import sim_random, training_random
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter
import BackEnd.models.shot_manager as SM
import BackEnd.engine.phase_resolution as PR

# Each shooting-foul branch calls check_and_handle_foul_out on its own line, so the CALLER's
# line number names the branch that fired. Cheap, and needs no line tracing.
FOUL_SITE = Counter()
PENDING = []


def _install_branch_probe():
    orig = PR.check_and_handle_foul_out

    def wrapped(*a, **k):
        try:
            ln = sys._getframe(1).f_lineno
            fn = os.path.basename(sys._getframe(1).f_code.co_filename)
            FOUL_SITE[f"{fn}:{ln}"] += 1
            PENDING.append(f"{fn}:{ln}")
        except Exception:
            pass
        return orig(*a, **k)
    PR.check_and_handle_foul_out = wrapped


def _install_shot_join():
    """Join the branch that fired to the shot's own classification, per shot."""
    orig = SM.ShotManager.resolve_shot

    def resolve_shot(self, roles, *a, **k):
        PENDING.clear()
        out = orig(self, roles, *a, **k)
        if isinstance(out, dict) and PENDING:
            is3 = bool(out.get("is_three_point_shot"))
            made = str(out.get("result_type") or "").upper() == "MAKE" or bool(out.get("made"))
            ft = self.game_state.get("free_throws")
            JOIN[f"{PENDING[-1]} | {'3PT' if is3 else '2PT'} | {'made' if made else 'missed'} | free_throws={ft}"] += 1
        return out
    SM.ShotManager.resolve_shot = resolve_shot


JOIN = Counter()

READ_LINES = [0]
FT_SET = []          # every free_throws write seen, with the caller site
DEPTH, _FLAG = [0], {}


class Capture(logging.Handler):
    def emit(self, record):
        pass

    def handle(self, record):
        m = record.msg
        if isinstance(m, str) and m.startswith("[3PT-READ]"):
            READ_LINES[0] += 1
        return True


def _install_diag_gate():
    """Force ONLY the [3PT-READ] gate's own call (line 1027) true; leaves the arm alone."""
    orig = SM.calibration_diagnostics_enabled

    def gate(x):
        try:
            if sys._getframe(1).f_lineno == 1027:
                return True
        except Exception:
            pass
        return orig(x)
    SM.calibration_diagnostics_enabled = gate


AWARD = Counter()
OAO_PRIOR = Counter()


def _install_award_probe():
    """Audit every apply_free_throw_award call: caller site, award, and the PRIOR one_and_one.

    The prior value settles whether routing the two shooting-foul branches that never wrote
    one_and_one through the shared applier changes behaviour. If it is already False at every
    shooting-foul site, writing False is provably a no-op rather than a bundled change.
    """
    import BackEnd.utils.free_throw_rules as FTR
    import BackEnd.engine.after_steal_fast_break as ASFB
    import BackEnd.engine.after_steal_drive_integration as ASDI
    import BackEnd.engine.dynamic_hct_shot as DHS
    orig = FTR.apply_free_throw_award

    def wrapped(game_state, award):
        try:
            ln = sys._getframe(1).f_lineno
            fn = os.path.basename(sys._getframe(1).f_code.co_filename)
            site = f"{fn}:{ln}"
            AWARD[f"{site} | ft={award.free_throws} rem={award.remaining} oao={award.one_and_one}"] += 1
            OAO_PRIOR[f"{site} | prior_one_and_one={game_state.get('one_and_one')}"] += 1
        except Exception:
            pass
        return orig(game_state, award)

    for mod in (FTR, SM, ASFB, ASDI, DHS):
        if getattr(mod, "apply_free_throw_award", None) is not None:
            mod.apply_free_throw_award = wrapped


def _install_played():
    import BackEnd.models.animator as AN
    for m in ("capture_fast_break_animation", "capture_free_throw_animation",
              "capture_halfcourt_animation", "skeleton_to_animations"):
        o = getattr(AN.Animator, m)

        def mk(o=o):
            def w(self, *a, **k):
                gs = self.game.game_state
                if DEPTH[0] == 0:
                    _FLAG["had"] = "_is_full_simulation" in gs
                    _FLAG["prev"] = gs.get("_is_full_simulation")
                gs["_is_full_simulation"] = False
                DEPTH[0] += 1
                try:
                    return o(self, *a, **k)
                finally:
                    DEPTH[0] -= 1
                    if DEPTH[0] == 0:
                        if _FLAG["had"]:
                            gs["_is_full_simulation"] = _FLAG["prev"]
                        else:
                            gs.pop("_is_full_simulation", None)
            return w
        setattr(AN.Animator, m, mk())


if __name__ == "__main__":
    if ARM == "played":
        _install_played()
    _install_diag_gate()
    _install_branch_probe()
    _install_shot_join()
    _install_award_probe()
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(Capture())
    root.setLevel(logging.DEBUG)

    sim_random.seed(SEED); training_random.seed(SEED); _stdlib.seed(SEED)
    gm = GameManager("Lancaster", "Bentley-Truman")
    d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2, "hc_trap": 5, "fc_press": 5}
    gm.home_team.strategy_settings = d.copy(); gm.away_team.strategy_settings = d.copy()
    err = None
    for _q in range(4):
        try:
            simulate_quarter(gm, game_id="%024x" % (0x30000 + SEED))
        except Exception as e:
            err = f"{type(e).__name__}: {e}"; break

    turns = gm.turns or []
    # Free-throw conversion, straight off the turn stream, so points/game restored is a
    # measured figure rather than an assumed league FT%.
    ft_att = sum(1 for t in turns if str(t.get("result_type") or "").upper() == "FREE_THROW")
    ft_made = sum(1 for t in turns if str(t.get("result_type") or "").upper() == "FREE_THROW"
                  and int(t.get("points") or 0) == 1)
    tally = Counter()
    misaward = []
    for i, t in enumerate(turns):
        rt = str(t.get("result_type") or "").upper()
        if rt not in ("MAKE", "MISS", "BLOCK"):
            continue
        if str(t.get("next_turn") or "").upper() != "FREE_THROW":
            continue
        # how many free throws did he actually shoot?
        n = 0
        for j in range(i + 1, len(turns)):
            if str(turns[j].get("result_type") or "").upper() == "FREE_THROW":
                n += 1
            else:
                break
        if "is_three_point_shot" not in t:
            tally["unstamped-shot"] += 1
            continue
        is3 = bool(t.get("is_three_point_shot"))
        made = rt == "MAKE"
        expected = 1 if made else (3 if is3 else 2)
        ok = (n == expected)
        key = f"{'3PT' if is3 else '2PT'}|{'made' if made else 'missed'}|awarded={n}|expected={expected}"
        tally[key] += 1
        tally[("OK" if ok else "MISAWARD") + f"|{'3PT' if is3 else '2PT'}"] += 1
        if not ok and len(misaward) < 12:
            misaward.append({"turn": i, "result": rt, "is3": is3, "awarded": n,
                             "expected": expected,
                             "current_turn": str(t.get("current_turn")),
                             "src": str(t.get("shot_classification_source")),
                             "value": t.get("shot_value"),
                             "near_quarter_end": (i + n + 1 >= len(turns))
                             or any(str(turns[k].get("result_type") or "").upper() == "RUN_OUT_CLOCK"
                                    for k in range(i, min(i + 4, len(turns))))})

    json.dump({"arm": ARM, "seed": SEED, "error": err, "turns": len(turns),
               "three_pt_read_lines": READ_LINES[0], "ft_att": ft_att, "ft_made": ft_made,
               "tally": dict(tally), "misaward_examples": misaward,
               "foul_sites": dict(FOUL_SITE), "join": dict(JOIN),
               "award": dict(AWARD), "oao_prior": dict(OAO_PRIOR)},
              open(OUT, "w"))
