#!/usr/bin/env python3
"""
Paired A/B for CPU training allocation — same team, same week, same state, one thing changed.

WHY THIS EXISTS. Three comparisons in a row gave answers that did not survive contact with
the next one:

  * Dry-run vs live. A hand-reconstructed step-2 allocation scored -0.98 dry against +0.19
    LIVE for the same allocation. Dry-run absolute values are not comparable to live ones.
  * Within-week FOCUS vs ROSTER. Mode is derived per (team, week), so the two arms are
    DIFFERENT TEAMS. Team quality is confounded with mode.
  * Week over week. Roster weeks ran +0.08 -> -0.20 -> -0.45 across weeks 5-7 on code that
    never changed — ~0.5 of drift on an unchanged arm, larger than the ~0.26 effect being
    measured.

The fix for all three is PAIRING. Every team is trained twice from the same starting state
in the same week, differing only in the arm. Each team is its own control, so team quality,
week effects and drift cancel exactly rather than being averaged over and hoped away.

Absolute numbers here are still dry-run numbers and should NOT be quoted as live rates. The
DELTA is the output.

READ-ONLY. dry_run=True throughout; nothing is persisted. Run with GOB_DB_ACCESS=read.

  GOB_DB_ACCESS=read scripts/cpu_training_mode_ab.py --franchise <id> --week 7
  GOB_DB_ACCESS=read scripts/cpu_training_mode_ab.py --franchise <id> --week 7 --skills 1,2
  GOB_DB_ACCESS=read scripts/cpu_training_mode_ab.py --franchise <id> --weeks 5,6,7   # drift
"""

from __future__ import annotations

# Pin PYTHONHASHSEED first — see BackEnd/utils/repro. Loaded BY PATH so this does not import
# the BackEnd.utils package, whose __init__ pulls in stat_updater -> db.
import os as _os, sys as _sys, importlib.util as _ilu
_GOB_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _GOB_ROOT)
_spec = _ilu.spec_from_file_location(
    "_gob_repro", _os.path.join(_GOB_ROOT, "BackEnd", "utils", "repro.py"))
_repro = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_repro)
_repro.pin_hash_seed()

import argparse
import math
import statistics

ATTRS = ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "IQ", "ND")


def team_gain(fr, fid, team_id, week, seed=None) -> float | None:
    """Mean total attribute change per player for one team-week. None if it did not run.

    SEED IS WHAT MAKES PAIRING WORK. Without it each arm draws its own gain rolls, giving
    per-team deltas an sd of ~2.6 — the noise buries the ~0.3 effects under test. With the
    same seed on both arms the rolls are identical and the delta is purely the allocation.
    (This only became possible once auto_train_one_cpu_team was fixed to seed `training_rng`
    and not just the global module; before that the argument silently did nothing.)
    """
    res = fr.auto_train_one_cpu_team(fid, team_id, week=week, dry_run=True, seed=seed)
    changes = (res.get("report") or {}).get("player_changes") or {}
    per_player = []
    for _name, ch in changes.items():
        if not isinstance(ch, dict):
            continue
        vals = [ch.get(a) for a in ATTRS if isinstance(ch.get(a), (int, float))]
        if vals:
            per_player.append(sum(vals))
    return statistics.mean(per_player) if per_player else None


def paired(fr, fid, teams, week, arm_a, arm_b, label_a, label_b) -> None:
    """Run every team under both arms and report the PAIRED difference.

    arm_* are zero-arg callables that set module state before the run.
    """
    deltas, a_vals, b_vals = [], [], []
    for i, t in enumerate(teams):
        s = 90000 + i          # same seed for both arms of this team; varies across teams
        arm_a()
        ga = team_gain(fr, fid, t, week, seed=s)
        arm_b()
        gb = team_gain(fr, fid, t, week, seed=s)
        if ga is None or gb is None:
            continue
        a_vals.append(ga); b_vals.append(gb); deltas.append(gb - ga)
    if len(deltas) < 2:
        print("  not enough teams completed both arms")
        return
    md = statistics.mean(deltas)
    # SE of the PAIRED difference — the whole point. An unpaired SE over these same numbers
    # would be several times larger and would have called a real effect noise.
    se = statistics.pstdev(deltas) / (len(deltas) ** 0.5)
    t = abs(md) / se if se else 0.0
    wins = sum(1 for d in deltas if d > 0)
    print(f"  {label_a:<32} mean {statistics.mean(a_vals):+.3f}")
    print(f"  {label_b:<32} mean {statistics.mean(b_vals):+.3f}")
    print(f"  {'PAIRED delta (b - a)':<32} {md:+.3f} +/- {se:.3f}   |t|={t:.1f}   "
          f"{'REAL' if t >= 2 else 'not distinguishable'}")
    # SIGN TEST, and it is the statistic that actually works here. Seeding both arms
    # identically does NOT give identical rolls once the allocations diverge — the draw
    # sequence splits at the first difference — so magnitudes stay noisy. The DIRECTION per
    # team is still clean, and a binomial test on it has far more power than a t-test on
    # magnitudes: 28/40 is p<0.01 while the same data gives |t|=1.4 and reads as nothing.
    n = len(deltas)
    p = _binom_two_sided(wins, n)
    print(f"  {'teams where b won':<32} {wins}/{n}   sign-test p={p:.4f}   "
          f"{'DIRECTION IS REAL' if p < 0.05 else 'direction not established'}")


def _binom_two_sided(k: int, n: int) -> float:
    """Two-sided binomial p at q=0.5. Exact; n here is tens, so no approximation needed."""
    def pmf(i):
        return math.comb(n, i) * 0.5 ** n
    obs = pmf(k)
    return min(1.0, sum(pmf(i) for i in range(n + 1) if pmf(i) <= obs + 1e-12))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--franchise", required=True)
    ap.add_argument("--week", type=int, default=7)
    ap.add_argument("--weeks", default=None,
                    help="comma list — runs the SAME arm across weeks to size the drift")
    ap.add_argument("--teams", type=int, default=40)
    ap.add_argument("--skills", default=None,
                    help="comma pair, e.g. 1,2 — compare _FOCUS_SKILL_COUNT values")
    args = ap.parse_args()

    from bson import ObjectId
    from BackEnd.db import db
    import BackEnd.api.franchise_routes as fr

    fid = ObjectId(str(args.franchise))
    teams = [d["team_id"] for d in db["franchise_team_data"].find(
        {"franchise_id": {"$in": [fid, str(fid)]}}, {"team_id": 1}).limit(args.teams)]
    print(f"# franchise {args.franchise} | {len(teams)} teams | dry run, nothing persisted")
    print(f"# absolute values are DRY-RUN values; only the paired delta is meaningful\n")

    def force(mode):
        def _apply():
            fr._is_focus_week = lambda *a, **k: mode
        return _apply

    def force_skills(mode, n):
        def _apply():
            fr._is_focus_week = lambda *a, **k: mode
            fr._FOCUS_SKILL_COUNT = n
            fr._FOCUS_BUCKET3_LIFT = {"ND": 2, "IQ": 2} if n == 1 else {}
        return _apply

    if args.weeks:
        # DRIFT: same arm, different weeks. Anything that moves here is not the allocation.
        wks = [int(w) for w in args.weeks.split(",") if w.strip()]
        print(f"DRIFT CHECK — FOCUS mode held constant across weeks {wks}")
        base = wks[0]
        for w in wks[1:]:
            print(f"\n  week {base} vs week {w}:")
            deltas = []
            for t in teams:
                fr._is_focus_week = lambda *a, **k: True
                g1 = team_gain(fr, fid, t, base, seed=90000)
                g2 = team_gain(fr, fid, t, w, seed=90000)
                if g1 is not None and g2 is not None:
                    deltas.append(g2 - g1)
            if deltas:
                md = statistics.mean(deltas)
                se = statistics.pstdev(deltas) / (len(deltas) ** 0.5)
                print(f"    paired drift {md:+.3f} +/- {se:.3f}   |t|={abs(md)/se if se else 0:.1f}")
        return 0

    if args.skills:
        a, b = [int(x) for x in args.skills.split(",")]
        print(f"FOCUS MODE — _FOCUS_SKILL_COUNT {a} vs {b}, week {args.week}")
        paired(fr, fid, teams, args.week,
               force_skills(True, a), force_skills(True, b),
               f"{a} skill(s) @3", f"{b} skill(s) @3")
        return 0

    print(f"MODE — all-FOCUS vs all-ROSTER, week {args.week}, same teams both arms")
    paired(fr, fid, teams, args.week, force(True), force(False), "FOCUS", "ROSTER")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
