#!/usr/bin/env python3
"""
Offline EOG band-tuning harness.

The season log carries every raw input for all 3,328 team-games, so the expected drift
under ANY candidate band configuration is computable directly — no re-simulation. Seconds
per iteration instead of two hours.

It mirrors BackEnd/eog_attr_rules.py exactly. `--validate` proves that: it runs the CURRENT
constants over the log and compares the recomputed band label to the one production actually
emitted, per row. Anything less than 100% means the mirror has drifted and no tuning result
from it can be trusted.

E[Δ]/game is computed as the mean band MIDPOINT (bands are uniform integer rolls, so the
midpoint is the expectation). Season EOG drift = E[Δ]/game x 26. Training drift is taken as
a FIXED measured input — we tune EOG against it.

usage:
  eog_band_tuner.py <log.jsonl> --validate
  eog_band_tuner.py <log.jsonl> [--config candidate]
"""

from __future__ import annotations

# Pin PYTHONHASHSEED before anything else: unpinned runs are not reproducible and
# have produced false measurement conclusions. See BackEnd/utils/repro.
# Loaded BY PATH so this does not import the BackEnd.utils package, whose __init__
# pulls in stat_updater -> db and would open a Mongo connection twice across the
# re-exec.
import os as _os, sys as _sys, importlib.util as _ilu
_GOB_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _GOB_ROOT)
_spec = _ilu.spec_from_file_location(
    "_gob_repro", _os.path.join(_GOB_ROOT, "BackEnd", "utils", "repro.py"))
_repro = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_repro)
_repro.pin_hash_seed()

import argparse
import copy
import json
from collections import Counter, defaultdict

TAG = "[EOG-BAND] "
CLAMP_RATES: dict = {}

# Season training drift per attribute, MEASURED directly from the CPU reference plan
# (auto_train_one_cpu_team, dry_run, 12 seeds x 64 teams, post-gating) with every attribute reset to
# MID-RANGE first. Fixed input: we tune EOG against it, not the other way round.
#
# ⚠️ DO NOT source these from the report's §2b column. That estimator conditions on both
# endpoints being unclamped, so for an attribute whose population is pressed against a clamp
# it measures only the SURVIVORS — the teams that have not yet railed, i.e. exactly those
# with the smallest deltas. Measured gap: team_chemistry -93.6 true vs -10.2 inferred (9.2x),
# discipline -91.6 vs -48.1 (1.9x). Unconstrained attributes agreed within 10%. Tuning EOG
# against the censored column silently under-corrects the attributes that need it most.
TRAINING_PER_SEASON = {
    "shot_threshold": +56.4,
    "pt_opp_modifier": +7.9,
    "offensive_efficiency": +7.8,
    "defensive_efficiency": +7.8,
    "fb_opp_modifier": +7.8,
    "pt_efficiency": +7.7,
    "fb_efficiency": +7.1,
    "discipline": -6.0,
    "team_chemistry": -5.3,
    "fight": +3.3,
    "rebound_modifier": +0.2,
}

# ── configuration ────────────────────────────────────────────────────────────────────────
# NOTE: this dict is the tuner's own copy of the band configuration. After the
# 2026-08-11 leveling pass the LIVE values in BackEnd/constants/eog_attr_bands.py
# differ from what produced the identity-season log, so `--validate` against that
# log must use the AS-LOGGED values below, not the live ones. Validate against a
# log captured under the current constants before trusting a new tuning run.
AS_LOGGED = {
    "FG_PCT_HIGH": 50, "FG_PCT_MID": 45,
    "DISCIPLINE_OPP_BUFFER": 8,
    "REBOUND_BIG_MARGIN": 8, "REBOUND_MID_MARGIN": 4, "REBOUND_EVEN_MARGIN": 3,
    "OFF_CONC_REWARD": 0.30, "OFF_CONC_MIDDLE": 0.45,
    "DEF_MAX_SHARE_REWARD": 0.39, "DEF_MAX_SHARE_MIDDLE": 0.49,
    "FB_CONC_REWARD": 0.45, "FB_CONC_MIDDLE": 0.60,
    "PT_CONC_REWARD": 0.50, "PT_CONC_MIDDLE": 0.75,
    "FB_OPP_HEALTHY_BAND": (5, 10),
    "PT_HEALTHY_BAND": (7, 14),
    "CHEM_TOP_RANK": 10, "CHEM_LOW_RANK_MIN": 100, "CHEM_LOW_RANK_MAX": 128,
    # delta ranges
    "ST_FG_GT_50": (-10, -5), "ST_FG_45_TO_50_WIN": (-5, 0),
    "ST_FG_45_TO_50_LOSS": (0, 5), "ST_FG_LE_45": (5, 10),
    "DISC_BELOW": (1, 2), "DISC_ABOVE": (-2, -1), "DISC_EQUAL": (-1, 0),
    "FIGHT_WIN": (0, 2), "FIGHT_LOSS": (-2, 0),
    "REB_OUTREBOUND_GT_8": (2, 12), "REB_OUTREBOUND_4_7": (0, 5),
    "REB_WITHIN_3": (-8, -2), "REB_OUTREBOUNDED_4_7": (-10, -5),
    "REB_OUTREBOUNDED_GT_8": (-25, -15),
    "CONC_REWARD_DELTA": (0, 1), "CONC_MIDDLE_DELTA": (-1, 0),
    "CONC_PENALTY_DELTA": (-2, -1), "CONC_ATROPHY_DELTA": (-1, 0),
    "DEF_REWARD_DELTA": (0, 1), "DEF_MIDDLE_DELTA": (-1, 0),
    "DEF_PENALTY_DELTA": (-2, -1),
    "VOL_ATROPHY_DELTA": (-1, 0), "VOL_UNDER_DELTA": (-1, 0),
    "VOL_HEALTHY_DELTA": (0, 1), "VOL_OVER_DELTA": (-1, 0),
    "CHEM_BEAT_LOWER": (0, 1), "CHEM_BEAT_HIGHER_NON_TOP10": (1, 2),
    "CHEM_BEAT_TOP10": (2, 4), "CHEM_LOSE_TO_TOP10": (-1, 0),
    "CHEM_LOSE_TO_HIGHER_NON_TOP10": (-2, 0), "CHEM_LOSE_TO_100_128": (-5, -3),
    "CHEM_LOSE_TO_OTHER_LOWER": (-3, -2),
}
CURRENT = AS_LOGGED


def mid(rng_pair):
    return (rng_pair[0] + rng_pair[1]) / 2.0


# ── band selection, mirroring BackEnd/eog_attr_rules.py ──────────────────────────────────
def _conc(share, reward, middle, C, labels):
    if share <= reward:
        return labels[0], C["CONC_REWARD_DELTA"]
    if share <= middle:
        return labels[1], C["CONC_MIDDLE_DELTA"]
    return labels[2], C["CONC_PENALTY_DELTA"]


def _vol(volume, band, C, labels):
    lo, hi = band
    if volume <= 0:
        return labels[0], C["VOL_ATROPHY_DELTA"]
    if volume < lo:
        return labels[1], C["VOL_UNDER_DELTA"]
    if volume <= hi:
        return labels[2], C["VOL_HEALTHY_DELTA"]
    return labels[3], C["VOL_OVER_DELTA"]


def band_for(attr, rec, C):
    """Return (label, (lo,hi)) or None when the row is not bandable."""
    i = rec.get("inputs") or {}
    win = bool(rec.get("is_winner"))
    if attr == "shot_threshold":
        fg = i.get("fg_pct")
        if fg is None:
            return None
        if fg > C["FG_PCT_HIGH"]:
            return "fg_gt_50", C["ST_FG_GT_50"]
        if fg > C["FG_PCT_MID"]:
            return "fg_45_to_50", (C["ST_FG_45_TO_50_WIN"] if win
                                   else C["ST_FG_45_TO_50_LOSS"])
        return "fg_le_45", C["ST_FG_LE_45"]
    if attr == "discipline":
        t, o = i.get("team_f_plus_to"), i.get("opp_f_plus_to")
        if t is None or o is None:
            return None
        b = o + C["DISCIPLINE_OPP_BUFFER"]
        if t < b:
            return "below_opp_plus_8", C["DISC_BELOW"]
        if t > b:
            return "above_opp_plus_8", C["DISC_ABOVE"]
        return "equal_buffered", C["DISC_EQUAL"]
    if attr == "fight":
        return ("win", C["FIGHT_WIN"]) if win else ("loss", C["FIGHT_LOSS"])
    if attr == "rebound_modifier":
        t, o = i.get("treb"), i.get("opp_treb")
        if t is None or o is None:
            return None
        d = t - o
        if d >= C["REBOUND_BIG_MARGIN"]:
            return "outrebound_gt_8", C["REB_OUTREBOUND_GT_8"]
        if d >= C["REBOUND_MID_MARGIN"]:
            return "outrebound_4_7", C["REB_OUTREBOUND_4_7"]
        if d >= -C["REBOUND_EVEN_MARGIN"]:
            return "within_3", C["REB_WITHIN_3"]
        if d > -C["REBOUND_BIG_MARGIN"]:
            return "outrebounded_4_7", C["REB_OUTREBOUNDED_4_7"]
        return "outrebounded_gt_8", C["REB_OUTREBOUNDED_GT_8"]
    if attr == "offensive_efficiency":
        if (i.get("total_usage") or 0) <= 0:
            return None
        return _conc(i.get("max_share"), C["OFF_CONC_REWARD"], C["OFF_CONC_MIDDLE"], C,
                     ("conc_le_30", "conc_le_45", "conc_gt_45"))
    if attr == "defensive_efficiency":
        if (i.get("total_usage") or 0) <= 0:
            return None
        s = i.get("max_share")
        if s <= C["DEF_MAX_SHARE_REWARD"]:
            return "def_max_le_39", C["DEF_REWARD_DELTA"]
        if s <= C["DEF_MAX_SHARE_MIDDLE"]:
            return "def_max_le_49", C["DEF_MIDDLE_DELTA"]
        return "def_max_gt_49", C["DEF_PENALTY_DELTA"]
    if attr == "fb_efficiency":
        if (i.get("volume") or 0) <= 0:
            return "fb_atrophy", C["CONC_ATROPHY_DELTA"]
        return _conc(i.get("max_share"), C["FB_CONC_REWARD"], C["FB_CONC_MIDDLE"], C,
                     ("fb_conc_le_45", "fb_conc_le_60", "fb_conc_gt_60"))
    if attr == "pt_efficiency":
        if (i.get("volume") or 0) <= 0:
            return "pt_atrophy", C["CONC_ATROPHY_DELTA"]
        return _conc(i.get("max_share"), C["PT_CONC_REWARD"], C["PT_CONC_MIDDLE"], C,
                     ("pt_conc_le_50", "pt_conc_le_75", "pt_conc_gt_75"))
    if attr == "fb_opp_modifier":
        return _vol(i.get("opponent_fb_volume") or 0, C["FB_OPP_HEALTHY_BAND"], C,
                    ("fb_opp_atrophy", "fb_opp_under", "fb_opp_healthy", "fb_opp_over"))
    if attr == "pt_opp_modifier":
        return _vol(i.get("opponent_pt_volume") or 0, C["PT_HEALTHY_BAND"], C,
                    ("pt_opp_atrophy", "pt_opp_under", "pt_opp_healthy", "pt_opp_over"))
    if attr == "team_chemistry":
        tr, orr = i.get("team_rank"), i.get("opponent_rank")
        if tr is None or orr is None:
            return None
        if win:
            if orr > tr:
                return "beat_lower_ranked", C["CHEM_BEAT_LOWER"]
            if orr <= C["CHEM_TOP_RANK"]:
                return "beat_top10", C["CHEM_BEAT_TOP10"]
            return "beat_higher_non_top10", C["CHEM_BEAT_HIGHER_NON_TOP10"]
        if orr < tr and orr <= C["CHEM_TOP_RANK"]:
            return "lose_to_top10", C["CHEM_LOSE_TO_TOP10"]
        if orr < tr:
            return "lose_to_higher_non_top10", C["CHEM_LOSE_TO_HIGHER_NON_TOP10"]
        if C["CHEM_LOW_RANK_MIN"] <= orr <= C["CHEM_LOW_RANK_MAX"]:
            return "lose_to_100_128", C["CHEM_LOSE_TO_100_128"]
        return "lose_to_other_lower", C["CHEM_LOSE_TO_OTHER_LOWER"]
    return None


def clamp_rates(recs):
    """Share of logged rows where EOG's write was clamped. High rates mean any
    drift figure derived from unclamped-only transitions is a SURVIVOR estimate."""
    out = {}
    for attr, rows in recs.items():
        n = len(rows)
        c = sum(1 for r in rows if r.get("clamped"))
        out[attr] = (100.0 * c / n) if n else 0.0
    return out


def load(path):
    out = defaultdict(list)
    for line in open(path):
        line = line.strip()
        if not line.startswith(TAG):
            continue
        r = json.loads(line[len(TAG):])
        if isinstance(r.get("attr"), str):
            out[r["attr"]].append(r)
    return out


def evaluate(recs, C):
    res = {}
    for attr, rows in recs.items():
        freq = Counter()
        tot = 0.0
        n = 0
        for r in rows:
            b = band_for(attr, r, C)
            if b is None:
                continue
            lbl, rng_pair = b
            m = mid(rng_pair)
            if attr == "rebound_modifier":
                m /= 100.0
            freq[lbl] += 1
            tot += m
            n += 1
        if n:
            res[attr] = {"n": n, "freq": freq, "eog_per_game": tot / n,
                         "eog_season": (tot / n) * 26}
    return res


def validate(recs, C):
    print("VALIDATION — recomputed band label vs the label production emitted\n")
    allok = True
    for attr in sorted(recs):
        ok = bad = 0
        examples = []
        for r in recs[attr]:
            b = band_for(attr, r, C)
            if b is None:
                continue
            if b[0] == r.get("band"):
                ok += 1
            else:
                bad += 1
                if len(examples) < 2:
                    examples.append((r.get("band"), b[0], r.get("inputs")))
        pct = 100 * ok / max(1, ok + bad)
        flag = "" if bad == 0 else "   <<< MISMATCH"
        print(f"  {attr:<24}{ok:>6}/{ok+bad:<6} {pct:>6.2f}%{flag}")
        for e in examples:
            print(f"      logged={e[0]!r} recomputed={e[1]!r} inputs={e[2]}")
        allok &= bad == 0
    print("\n" + ("✅ harness mirrors production exactly"
                  if allok else "❌ harness has drifted — tuning results are NOT trustworthy"))
    return allok


def table(res, label):
    print(f"\n{'='*84}\n{label}\n{'='*84}")
    print(f"  {'attr':<24}{'EOG/g':>8}{'EOG/szn':>9}{'training':>10}{'COMBINED':>10}{'clamp%':>8}   bands")
    rows = []
    for attr, d in res.items():
        tr = TRAINING_PER_SEASON.get(attr, 0.0)
        rows.append((attr, d["eog_per_game"], d["eog_season"], tr, d["eog_season"] + tr, d))
    for attr, pg, sz, tr, comb, d in sorted(rows, key=lambda x: -abs(x[4])):
        top = " ".join(f"{k}={100*v/d['n']:.0f}%" for k, v in d["freq"].most_common(3))
        cr = (CLAMP_RATES or {}).get(attr, 0.0)
        mark = " ⚠" if cr >= 5.0 else "  "
        print(f"  {attr:<24}{pg:>+8.3f}{sz:>+9.1f}{tr:>+10.1f}{comb:>+10.1f}{cr:>7.1f}{mark} {top}")
    hot = [a for a, _p, _s, _t, _c, _d in rows if (CLAMP_RATES or {}).get(a, 0) >= 5.0]
    if hot:
        print("\n  ⚠ CLAMPED IN THE SOURCE LOG (>=5% of rows): " + ", ".join(sorted(hot)))
        print("    Censoring is a property of the METRIC, not this dataset. Any drift figure")
        print("    derived from unclamped-only transitions (e.g. the report's §2b training")
        print("    column) is a SURVIVOR estimate for these attributes and understates the")
        print("    true pressure — by up to 9x when measured. Source training numbers from a")
        print("    direct mid-range dry run instead, never from the log.")
    return {a: c for a, _p, _s, _t, c, _d in rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--config", default=None, help="python file defining CANDIDATE dict")
    args = ap.parse_args()

    recs = load(args.path)
    global CLAMP_RATES
    CLAMP_RATES = clamp_rates(recs)
    print(f"loaded {sum(len(v) for v in recs.values())} band rows, {len(recs)} attributes")

    if args.validate:
        return 0 if validate(recs, CURRENT) else 1

    base = evaluate(recs, CURRENT)
    table(base, "CURRENT configuration")

    if args.config:
        ns = {}
        exec(open(args.config).read(), ns)
        C = copy.deepcopy(CURRENT)
        C.update(ns["CANDIDATE"])
        cand = evaluate(recs, C)
        cb = table(cand, "CANDIDATE configuration")
        print(f"\n{'='*84}\nCOMBINED DRIFT: current -> candidate   (target: small positive)\n{'='*84}")
        print(f"  {'attr':<24}{'current':>10}{'candidate':>11}{'move':>9}")
        for attr in sorted(base, key=lambda a: -abs(base[a]['eog_season']
                                                     + TRAINING_PER_SEASON.get(a, 0))):
            c0 = base[attr]["eog_season"] + TRAINING_PER_SEASON.get(attr, 0)
            c1 = cb[attr]
            print(f"  {attr:<24}{c0:>+10.1f}{c1:>+11.1f}{c1-c0:>+9.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
