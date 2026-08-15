#!/usr/bin/env python3
"""
Does the optimal lineup objective weight `w` depend on a team's starter/bench gap?

THE QUESTION THIS EXISTS TO ANSWER. `w` blends the selector objective:

    score = w * static_rating + (1 - w) * effective_rating      (db_utils.py:168)

`c2570c5aa` swept w LEAGUE-WIDE and adopted 0.25. Every value below 1.0 beat w=1.0 on
margin (+2.50 to +3.09), and the effective-talent gap fell monotonically as w fell
(>10 gap: 20.8% at w=1.0 -> 0.7% at w=0.25 -> 0.5% at w=0.0).

`cpu_identity_design.md` §B3 wants w to VARY by team: low w for teams with a shallow
starter/bench drop ("sub freely"), high w for top-heavy teams ("ride the starters").
That asks w to move UP for some teams — the direction the league-wide sweep measured as
worse — so it is only defensible if the optimum DIFFERS BY ROSTER SHAPE and the
league-wide sweep averaged that difference away.

That is the hypothesis. A league-wide optimum is not evidence about a specific shape.
If top-heavy teams show no different optimum here, close the surface out the way the NG
pull/return hysteresis pair was closed (projects/bugs.md) rather than shipping plumbing
for a mechanism that does not pay.

DESIGN — WITHIN-GAME PAIRING. Both teams in a game play the same opponent, same venue,
same seed, so assigning home and away DIFFERENT w values makes the point margin a direct
comparison controlled for everything else. Each team's own starter_bench_gap is recorded,
so the analysis can ask "among top-heavy teams, did higher w win?" rather than the
league-average question already answered.

DELIBERATELY DOES NOT MEASURE MINUTES. The rebuild-timeline minutes metric is VOID (it
bucketed by a stale CTX["team"] and merged two teams — see CPU_Team_Rotation_System.md
"READ FIRST"). Margin and the effective-talent gap need no team attribution, so this
sidesteps the defect entirely rather than reimplementing a per-turn sampler.

READ-ONLY. Run with GOB_DB_ACCESS=read.

  GOB_DB_ACCESS=read scripts/lineup_w_conditional_sweep.py --franchise <id> --games 40
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
import json
import statistics
from collections import defaultdict

# ── the definition under test ────────────────────────────────────────────────────────────
# `starter_bench_gap` IS NOT DEFINED ANYWHERE IN THE CODEBASE. It appears only in the
# db_utils comment naming it as the archetype seam. This is the definition this sweep
# assumes, stated here so it can be argued with rather than buried:
#
#   For each of the five lineup slots, take the best available player's STATIC rating at
#   that slot minus the SECOND best's. Average the five.
#
# Three choices worth challenging:
#   * STATIC, not effective. The gap is a property of the ROSTER, not of the current
#     fatigue state; using effective ratings would make it wobble within a game.
#   * SECOND best per slot, not "the bench". The relevant comparison is who actually
#     replaces the starter at that position, which is the same within-team comparison the
#     rotation-size decision landed on (CPU_Team_Identity_System.md, decision #4) —
#     differences travel across pool recalibrations, absolute bars do not.
#   * MEAN over slots, not max. One thin position should not read as a top-heavy roster.
#
# The spec's bands are < 13 / 13-19 / > 19 rating points.
GAP_BANDS = ((13.0, "shallow (<13)"), (19.0, "normal (13-19)"), (float("inf"), "top-heavy (>19)"))


def band_of(gap: float) -> str:
    for edge, label in GAP_BANDS:
        if gap < edge:
            return label
    return GAP_BANDS[-1][1]


def starter_bench_gap(team) -> float:
    """Mean over the five slots of (best static rating - second best) at that slot."""
    from BackEnd.utils.db_utils import _LINEUP_POSITIONS, _player_slot_rating

    players = list(getattr(team, "players", {}).values())
    if len(players) < 6:
        return 0.0
    gaps = []
    for pos in _LINEUP_POSITIONS:
        rated = sorted((_player_slot_rating(p, pos) for p in players), reverse=True)
        if len(rated) >= 2:
            gaps.append(rated[0] - rated[1])
    return statistics.mean(gaps) if gaps else 0.0


# ── per-team w injection ─────────────────────────────────────────────────────────────────
# THE PLUMBING DOES NOT REACH THE SIM. `effective_weight` is a parameter on
# solve_best_assignment, build_unified_autoset_lineup_from_eligible and
# fill_unified_lineup_gaps -- but NOT on build_lineup_from_mongo, which is what
# game_manager actually calls, and which invokes the second of those without passing it.
# So shipping per-team w needs a real (small) source change to thread the parameter one
# more level. This harness bridges the gap with a two-part patch instead, so the
# measurement can happen BEFORE deciding whether the source change is worth making.
#
# Part 1 wraps build_lineup_from_mongo purely to learn WHICH team is being built and
# stash its w; part 2 wraps the inner selector to consume it. A module global is safe
# here because a game sims single-threaded, and the pool runs one game per process.
_W_BY_TEAM: dict[str, float] = {}
_GAP_BY_TEAM: dict[str, float] = {}
_CURRENT_W: list = [None]  # one-element box so the closures share a mutable cell


def install_w_injector() -> None:
    from BackEnd.utils import db_utils

    outer = db_utils.build_lineup_from_mongo
    inner = db_utils.build_unified_autoset_lineup_from_eligible

    def wrapped_outer(team, game_state=None):
        name = str(getattr(team, "name", "") or "")
        if name and name not in _GAP_BY_TEAM:
            try:
                _GAP_BY_TEAM[name] = starter_bench_gap(team)
            except Exception:
                _GAP_BY_TEAM[name] = 0.0
        prev = _CURRENT_W[0]
        _CURRENT_W[0] = _W_BY_TEAM.get(name)
        try:
            return outer(team, game_state)
        finally:
            _CURRENT_W[0] = prev  # restore, so a nested build cannot leak its w outward

    def wrapped_inner(*a, **kw):
        if kw.get("effective_weight") is None and _CURRENT_W[0] is not None:
            kw["effective_weight"] = _CURRENT_W[0]
        return inner(*a, **kw)

    db_utils.build_lineup_from_mongo = wrapped_outer
    db_utils.build_unified_autoset_lineup_from_eligible = wrapped_inner
    # game_manager does `from BackEnd.utils.db_utils import build_lineup_from_mongo` INSIDE
    # the function body, so it resolves the module attribute per call and sees the patch.
    # A module-level import there would bind the original and silently defeat this.


def _precompute_gaps(db, fid, ftds, name_by_oid) -> dict[str, float]:
    """starter_bench_gap for every team, straight from FPD — no sim needed.

    Cheap enough to run before matchmaking, which is what makes band targeting possible.
    """
    from BackEnd.utils.db_utils import _LINEUP_POSITIONS, _player_slot_rating

    fpd = {str(d["player_id"]): d for d in db["franchise_players_data"].find(
        {"franchise_id": {"$in": [fid, str(fid)]}},
        {"player_id": 1, "attributes": 1, "position_ratings": 1})}

    class _P:
        def __init__(self, d):
            self.attributes = d.get("attributes") or {}
            self.position_ratings = d.get("position_ratings") or {}

    out: dict[str, float] = {}
    for d in ftds:
        name = name_by_oid.get(d["team_id"], "")
        players = [_P(fpd[str(p)]) for p in (d.get("players") or []) if str(p) in fpd]
        if not name or len(players) < 6:
            continue
        gaps = []
        for pos in _LINEUP_POSITIONS:
            rated = sorted((_player_slot_rating(p, pos) for p in players), reverse=True)
            if len(rated) >= 2:
                gaps.append(rated[0] - rated[1])
        if gaps:
            out[name] = statistics.mean(gaps)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--franchise", required=True)
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--w-low", type=float, default=0.05)
    ap.add_argument("--w-high", type=float, default=0.60,
                    help="the 'ride the starters' arm the spec wants for top-heavy rosters")
    ap.add_argument("--seed", type=int, default=1234)
    # TARGETING IS NOT OPTIONAL IN PRACTICE. Measured on the week-2 identity league, the
    # gap bands are 96 / 23 / 9 teams (75% / 18% / 7%). Random matchups therefore spend
    # ~93% of their games on bands whose answer the league-wide sweep already gave, and
    # the top-heavy band -- the ONLY band where the spec's "ride the starters" claim is
    # even in question -- gets almost no coverage. Restrict the pool to the band under
    # test so every game buys signal about the actual hypothesis.
    ap.add_argument("--gap-band", choices=["shallow", "normal", "top-heavy"], default=None,
                    help="only match teams whose starter_bench_gap falls in this band")
    ap.add_argument("-o", "--out", default=None, help="write per-team-game rows as JSONL")
    args = ap.parse_args()

    from bson import ObjectId
    from BackEnd.db import db
    from BackEnd.api.franchise_routes import _run_franchise_cpu_full_simulation_core

    install_w_injector()

    fid = ObjectId(str(args.franchise))
    # `players` is REQUIRED here, not incidental: _precompute_gaps needs the roster, and
    # without it every team silently fails the len(players) < 6 check and the band filter
    # matches zero teams while reporting no error.
    ftds = list(db["franchise_team_data"].find(
        {"franchise_id": {"$in": [fid, str(fid)]}}, {"team_id": 1, "players": 1}))
    name_by_oid = {t["_id"]: str(t.get("name") or "") for t in db["teams"].find({}, {"name": 1})}
    teams = [(d["team_id"], name_by_oid.get(d["team_id"], "")) for d in ftds]
    teams = [t for t in teams if t[1]]
    if len(teams) < 2:
        print("not enough teams resolved")
        return 1

    if args.gap_band:
        want = {"shallow": "shallow (<13)", "normal": "normal (13-19)",
                "top-heavy": "top-heavy (>19)"}[args.gap_band]
        gaps_by_id = _precompute_gaps(db, fid, ftds, name_by_oid)
        teams = [t for t in teams if band_of(gaps_by_id.get(t[1], 0.0)) == want]
        _GAP_BY_TEAM.update(gaps_by_id)
        print(f"# gap band '{want}': {len(teams)} eligible teams")
        if len(teams) < 2:
            print("# too few teams in this band to build matchups")
            return 1

    print(f"# {len(teams)} teams | {args.games} games | w arms {args.w_low} vs {args.w_high}")
    print(f"# starter_bench_gap = mean over 5 slots of (best static - second best)\n")

    rows = []
    for i in range(args.games):
        h_id, h_name = teams[(2 * i) % len(teams)]
        a_id, a_name = teams[(2 * i + 1) % len(teams)]
        if h_name == a_name:
            continue
        # Alternate which side gets the high arm so home advantage cannot confound w.
        hi_is_home = (i % 2 == 0)
        _W_BY_TEAM[h_name] = args.w_high if hi_is_home else args.w_low
        _W_BY_TEAM[a_name] = args.w_low if hi_is_home else args.w_high
        try:
            away, home, summary = _run_franchise_cpu_full_simulation_core(
                fid, h_id, a_id, h_name, a_name, seed=args.seed + i)
        except Exception as e:  # noqa: BLE001
            print(f"  game {i}: {type(e).__name__}: {str(e)[:140]}")
            continue
        score = (summary or {}).get("score") or {}
        if len(score) != 2:
            continue
        pts = {k.upper().replace(" ", "_"): v for k, v in score.items()}
        vals = list(pts.values())
        for name, side_pts in zip((h_name, a_name), (vals[0], vals[1])):
            key = name.upper().replace(" ", "_")
            own = pts.get(key, side_pts)
            opp = [v for k, v in pts.items() if k != key]
            rows.append({
                "game": i, "team": name, "w": _W_BY_TEAM[name],
                "gap": round(_GAP_BY_TEAM.get(name, 0.0), 2),
                "pts": own, "margin": own - (opp[0] if opp else own),
            })
        if (i + 1) % 10 == 0:
            print(f"  ...{i + 1}/{args.games} games")

    if not rows:
        print("\nno completed games — nothing to analyse")
        return 1

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        print(f"\nwrote {len(rows)} rows -> {args.out}")

    # ── analysis ────────────────────────────────────────────────────────────────────────
    # ONE OBSERVATION PER GAME, not per team-game. The design is zero-sum: within a game
    # margin(high w) == -margin(low w) EXACTLY, so per-arm means are always perfect
    # negatives and a two-sample SE over them treats perfectly anti-correlated data as
    # independent. That is not a small conservatism -- it is meaningless, and it printed
    # "0.00 / 0.00, no difference" on a sample whose games were +26 and +10 for high w.
    # The real question is a one-sample test: is the high-w team's margin different from 0?
    per_game = defaultdict(list)
    for r in rows:
        if r["w"] == args.w_high:
            per_game[band_of(r["gap"])].append(r["margin"])

    print(f"\n{'=' * 78}\nHIGH-w MARGIN BY GAP BAND  (one observation per game: points scored"
          f" by the\nw={args.w_high} team minus the w={args.w_low} team it played)\n{'=' * 78}")
    print(f"{'gap band':<20}{'games':>7}{'mean':>9}{'SE':>8}{'|t|':>7}   {'verdict'}")
    print("-" * 78)
    for _edge, label in GAP_BANDS:
        ms = per_game.get(label)
        if not ms:
            continue
        if len(ms) < 2:
            print(f"{label:<20}{len(ms):>7}{ms[0]:>9.2f}{'—':>8}{'—':>7}   single game, no test")
            continue
        mean = statistics.mean(ms)
        se = statistics.pstdev(ms) / (len(ms) ** 0.5)
        t = abs(mean) / se if se else 0.0
        verdict = ("HIGH w wins" if mean > 0 and t >= 2 else
                   "LOW w wins" if mean < 0 and t >= 2 else
                   "no difference (|t| < 2)")
        print(f"{label:<20}{len(ms):>7}{mean:>+9.2f}{se:>8.2f}{t:>7.1f}   {verdict}")
    print("\n  Power note: the hysteresis head-to-heads used 32 games per arm and still "
          "carried\n  +/-8.8pp error bars. Treat anything under ~30 games in a band as "
          "directional only.")

    print(f"\nHYPOTHESIS: high w should win ONLY in the top-heavy band. If 'no difference' "
          f"appears\nthere, the spec's gap table has no measured basis and substitution "
          f"should be closed\nout like the NG hysteresis pair rather than built.")
    gaps = [r["gap"] for r in rows]
    print(f"\nstarter_bench_gap observed: min={min(gaps):.1f} max={max(gaps):.1f} "
          f"mean={statistics.mean(gaps):.1f} median={statistics.median(gaps):.1f}")
    print("If the observed range does not straddle the 13/19 band edges, the bands are cut "
          "for\na different population and the conditional question cannot be asked on this "
          "pool.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
