"""Measure player-development baseline vs player-development-framework.md §4/§10.

Offline (no DB). Uses production training + develop_rollover against the post-§10
build. Two close-out questions:

1. Strategy spread — retention across reference / mild / moderate / extreme.
   The CPU reference is a "reinforce strengths" policy; it should retain high.
2. In-season decomposition — gain-driven vs decay-driven shape L1.
   Camp skips decay; if decay dominates in-season, gain scales are the wrong knob.

Writes JSON under tmp/s11_framework_baseline/.
"""
from __future__ import annotations

import contextlib
import json
import logging
import math
import os
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

logging.disable(logging.CRITICAL)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.utils import player_development as dev  # noqa: E402
from BackEnd.utils import player_generation as gen  # noqa: E402
from BackEnd.utils.player_generation import position_profile  # noqa: E402
from BackEnd.utils.position_ratings import POSITION_WEIGHTS, compute_position_ratings  # noqa: E402
from BackEnd.models.training_execution_v2 import (  # noqa: E402
    apply_pre_training_conditions,
    execute_training,
)
from BackEnd.api.franchise_routes import (  # noqa: E402
    _cpu_reference_allocation,
    _cpu_reference_top3,
)
from BackEnd.constants.training_shape import (  # noqa: E402
    CAMP_GAIN_SCALE,
    CAMP_WEEKS,
    is_camp_week,
)
from BackEnd.utils.shape_movement import decompose_shape_delta  # noqa: E402

GROWTH = list(dev.GROWTH_ATTRS)
POSITIONS = ("PG", "SG", "SF", "PF", "C")
YEARS = ("freshman", "sophomore", "junior", "senior")
SEASON_WEEKS = 26
N_CAREERS = 150
_NULL = open(os.devnull, "w")

# Anti-archetype all-in (walls / near-walls) — "reshape hard."
_EXTREME_ATTR = {"PG": "ST", "SG": "RB", "SF": "BH", "PF": "BH", "C": "BH"}
# Plausible conversion targets (mid-band off-role, not walls).
_CONVERSION_ATTR = {"PG": "SC", "SG": "BH", "SF": "ID", "PF": "SH", "C": "SH"}

OUT = ROOT / "tmp" / "s11_framework_baseline"
STRATEGIES = ("reference", "mild", "moderate", "extreme")


def _vec(attrs):
    return [float(attrs.get(a, attrs.get(f"anchor_{a}", 0)) or 0) for a in GROWTH]


def _shape(v):
    m = sum(v) / len(v)
    return [x / m for x in v] if m > 0 else [1.0 / len(v)] * len(v)


def _l1(a, b):
    return sum(abs(x - y) for x, y in zip(a, b))


def _profile_shape(pos):
    p = position_profile(pos)
    return _shape([float(p.get(a, 0)) for a in GROWTH])


def _proj_scalar(delta, direction):
    nd = math.sqrt(sum(x * x for x in direction)) or 1.0
    u = [x / nd for x in direction]
    return sum(d * u_i for d, u_i in zip(delta, u))


def _cosine_sim(a, b):
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def _fresh(pos, tier, seed):
    rng = random.Random(seed)
    jh = gen.generate_player(pos, "JH", tier, rng)
    return {
        "player_id": f"{pos}-{seed}",
        "meta": {"year": "JH", "height": jh["height"], "weight": jh["weight"]},
        "attributes": dict(jh["attributes"]),
        "position_ratings": dict(jh["position_ratings"]),
        "entry_tier": tier,
        "position_intent": pos,
        "training_position": pos,
        "potential_factor": 1.0,
    }, rng


def _units_to_alloc(units: dict) -> dict:
    b = {a: int(units.get(a, 0) or 0) for a in GROWTH}
    return {
        "player_drills": {
            "offense": {"inside": b["SC"], "outside": b["SH"]},
            "defense": {"inside": b["ID"], "outside": b["OD"]},
            "technical": {
                "passing": b["PS"],
                "ball_handling": b["BH"],
                "rebounding": b["RB"],
            },
            "weight_room": {"strength": b["ST"], "agility": b["AG"]},
        },
        "general": {
            "conditioning": b["ND"],
            "free_throws": b["FT"],
            "film_study": b["IQ"],
            "breaks": 1,
        },
        "team_drills": {},
    }


def _fit_under_budget(units: dict, pos: str, budget: int = 22) -> dict:
    """Trim units until the flat integer allocation fits (leave room for breaks)."""
    u = {a: int(units.get(a, 0) or 0) for a in GROWTH}
    for _ in range(40):
        if sum(u.values()) <= budget:
            break
        cands = [(a, u[a]) for a in GROWTH if u[a] > 0]
        if not cands:
            break
        cands.sort(key=lambda x: (-x[1], x[0]))
        u[cands[0][0]] -= 1
    return u


def _ranked_on_role(pos: str) -> list[str]:
    w = POSITION_WEIGHTS[pos]
    return sorted(
        (a for a in GROWTH if w.get(a, 0) > 0),
        key=lambda a: (-w.get(a, 0), a),
    )


def _strategy(pos: str, mode: str) -> tuple[dict, str | None, dict | None, list[float]]:
    """Return (alloc, focus, custom, coach_target_shape)."""
    top3 = _cpu_reference_top3(pos)
    conv = _CONVERSION_ATTR[pos]
    extreme = _EXTREME_ATTR[pos]
    ranked = _ranked_on_role(pos)

    if mode == "reference":
        # Reinforce strengths — production CPU path.
        alloc = _cpu_reference_allocation(pos)
        focus = "player-maximizer-custom"
        custom = {"x": list(top3)}
        coach_dir = [3.0 if a in top3 else 1.0 for a in GROWTH]
        return alloc, focus, custom, _shape(coach_dir)

    if mode == "mild":
        # Reference primaries + light secondary specialisation on next on-role attr.
        units = {a: 0 for a in GROWTH}
        for a in top3:
            units[a] = 3
        secondary = next((a for a in ranked if a not in top3), ranked[-1])
        units[secondary] = 2
        for a in ("ND", "FT", "IQ"):
            units[a] = 1
        units = _fit_under_budget(units, pos)
        coach_dir = [
            3.0 if a in top3 else (2.0 if a == secondary else 0.5) for a in GROWTH
        ]
        return (
            _units_to_alloc(units),
            "player-maximizer-custom",
            {"x": list(top3)},
            _shape(coach_dir),
        )

    if mode == "moderate":
        # Real conversion: fund the conversion attr hard; keep one primary for survival.
        units = {a: 0 for a in GROWTH}
        units[conv] = 4
        units[top3[0]] = 2
        for a in ("ND", "FT", "IQ"):
            units[a] = 1
        units = _fit_under_budget(units, pos)
        coach_dir = [0.15] * 12
        coach_dir[GROWTH.index(conv)] = 1.0
        coach_dir[GROWTH.index(top3[0])] = 0.45
        return _units_to_alloc(units), None, None, _shape(coach_dir)

    if mode == "extreme":
        units = {a: 0 for a in GROWTH}
        units[extreme] = 5
        units = _fit_under_budget(units, pos, budget=23.0)
        coach_dir = [0.01] * 12
        coach_dir[GROWTH.index(extreme)] = 1.0
        return _units_to_alloc(units), None, None, _shape(coach_dir)

    raise ValueError(mode)


def _train_season(fpd, year, alloc, focus, custom):
    """Camp + in-season with gain/decay split on in-season shape and attr L1.

    Camp weeks: skip decay → all movement is gain-driven.
    In-season weeks: decay first, then gains (gain_scale = IN_SEASON default).
    """
    pl = [{
        "_id": "x",
        "attributes": fpd["attributes"],
        "year": year,
        "height": fpd["meta"]["height"],
        "meta": fpd["meta"],
        "position_intent": fpd["position_intent"],
        "training_position": fpd.get("training_position") or fpd["position_intent"],
        "first_name": "A",
        "last_name": "B",
    }]
    camp_a = camp_s = 0.0
    week_a = week_s = 0.0
    week_gain_a = week_gain_s = 0.0
    week_decay_a = week_decay_s = 0.0

    with contextlib.redirect_stdout(_NULL):
        for week in range(1, SEASON_WEEKS + 1):
            camp = is_camp_week(week)
            if camp:
                vb = _vec(pl[0]["attributes"])
                sb = _shape(vb)
                execute_training(
                    pl, {}, alloc, focus,
                    coaching_focus_custom_by_player=custom,
                    skip_pre_training_depreciation=True,
                    gain_scale=CAMP_GAIN_SCALE,
                )
                va = _vec(pl[0]["attributes"])
                sa = _shape(va)
                camp_a += _l1(vb, va)
                camp_s += _l1(sb, sa)
            else:
                vb = _vec(pl[0]["attributes"])
                sb = _shape(vb)
                apply_pre_training_conditions(pl, {})
                vd = _vec(pl[0]["attributes"])
                sd = _shape(vd)
                week_decay_a += _l1(vb, vd)
                week_decay_s += _l1(sb, sd)
                execute_training(
                    pl, {}, alloc, focus,
                    coaching_focus_custom_by_player=custom,
                    skip_pre_training_depreciation=True,  # already decayed
                    gain_scale=None,  # IN_SEASON_GAIN_SCALE
                )
                va = _vec(pl[0]["attributes"])
                sa = _shape(va)
                week_gain_a += _l1(vd, va)
                week_gain_s += _l1(sd, sa)
                week_a += _l1(vb, va)
                week_s += _l1(sb, sa)

    fpd["attributes"] = pl[0]["attributes"]
    fpd["position_ratings"] = compute_position_ratings(
        {"attributes": fpd["attributes"], "height": fpd["meta"]["height"]}
    )
    return {
        "camp_a": camp_a,
        "camp_s": camp_s,
        "week_a": week_a,
        "week_s": week_s,
        "week_gain_a": week_gain_a,
        "week_gain_s": week_gain_s,
        "week_decay_a": week_decay_a,
        "week_decay_s": week_decay_s,
    }


def _offseason(fpd, new_year, rng):
    v0 = _vec(fpd["attributes"])
    s0 = _shape(v0)
    out = dev.develop_rollover(fpd, new_year, rng, season_allocation=None)
    for k in (
        "attributes", "position_ratings", "development", "entry_tier",
        "training_position", "potential_factor", "coaching_quality",
    ):
        if k in out:
            fpd[k] = out[k]
    fpd["meta"]["height"] = out["height"]
    fpd["meta"]["weight"] = out["weight"]
    fpd["meta"]["year"] = new_year
    v1 = _vec(fpd["attributes"])
    s1 = _shape(v1)
    return _l1(v0, v1), _l1(s0, s1)


def run_arm(mode: str, n: int = N_CAREERS) -> dict:
    phase_attr = defaultdict(list)
    phase_shape = defaultdict(list)
    retentions = []
    along_vals = []
    across_vals = []
    along_shares = []
    across_shares = []
    coach_share = []
    profile_share = []
    phase_shape_coach_block = []
    phase_shape_off_block = []

    for i in range(n):
        pos = POSITIONS[i % 5]
        fpd, rng = _fresh(pos, "Average", 10000 + i)
        out = dev.develop_rollover(fpd, "freshman", rng, season_allocation=None)
        for k in (
            "attributes", "position_ratings", "development", "entry_tier",
            "training_position", "potential_factor",
        ):
            if k in out:
                fpd[k] = out[k]
        fpd["meta"]["height"] = out["height"]
        fpd["meta"]["weight"] = out["weight"]
        fpd["meta"]["year"] = "freshman"

        s_start = _shape(_vec(fpd["attributes"]))
        prof = _profile_shape(pos)

        if mode == "offseason_only":
            alloc = focus = custom = None
            coach_target = prof
        else:
            alloc, focus, custom, coach_target = _strategy(pos, mode)

        cA = cS = wA = wS = oA = oS = 0.0
        wgA = wgS = wdA = wdS = 0.0
        sum_coach_proj = sum_prof_proj = 0.0

        for yi, year in enumerate(YEARS):
            if mode != "offseason_only":
                s_before = _shape(_vec(fpd["attributes"]))
                tr = _train_season(fpd, year, alloc, focus, custom)
                cA += tr["camp_a"]
                cS += tr["camp_s"]
                wA += tr["week_a"]
                wS += tr["week_s"]
                wgA += tr["week_gain_a"]
                wgS += tr["week_gain_s"]
                wdA += tr["week_decay_a"]
                wdS += tr["week_decay_s"]
                s_after = _shape(_vec(fpd["attributes"]))
                d = [a - b for a, b in zip(s_after, s_before)]
                toward_coach = [a - b for a, b in zip(coach_target, s_before)]
                toward_prof = [a - b for a, b in zip(prof, s_before)]
                sum_coach_proj += max(0.0, _proj_scalar(d, toward_coach))
                sum_prof_proj += max(0.0, _proj_scalar(d, toward_prof))

            if year == "senior":
                continue
            next_y = YEARS[yi + 1]
            s_before = _shape(_vec(fpd["attributes"]))
            oa, os_ = _offseason(fpd, next_y, rng)
            oA += oa
            oS += os_
            s_after = _shape(_vec(fpd["attributes"]))
            d = [a - b for a, b in zip(s_after, s_before)]
            toward_coach = [a - b for a, b in zip(coach_target, s_before)]
            toward_prof = [a - b for a, b in zip(prof, s_before)]
            sum_coach_proj += max(0.0, _proj_scalar(d, toward_coach))
            sum_prof_proj += max(0.0, _proj_scalar(d, toward_prof))

        phase_attr["camp"].append(cA)
        phase_attr["week"].append(wA)
        phase_attr["week_gain"].append(wgA)
        phase_attr["week_decay"].append(wdA)
        phase_attr["offseason"].append(oA)
        phase_shape["camp"].append(cS)
        phase_shape["week"].append(wS)
        phase_shape["week_gain"].append(wgS)
        phase_shape["week_decay"].append(wdS)
        phase_shape["offseason"].append(oS)

        train_s = cS + wS
        tot_s = train_s + oS
        if tot_s > 1e-9:
            phase_shape_coach_block.append(train_s / tot_s)
            phase_shape_off_block.append(oS / tot_s)

        s_end = _shape(_vec(fpd["attributes"]))
        retentions.append(_cosine_sim(s_start, s_end))
        decomp = decompose_shape_delta(s_start, s_end)
        along_vals.append(decomp["along"])
        across_vals.append(decomp["across"])
        along_shares.append(decomp["along_share"])
        across_shares.append(decomp["across_share"])
        tot = sum_coach_proj + sum_prof_proj
        if tot > 1e-9:
            coach_share.append(sum_coach_proj / tot)
            profile_share.append(sum_prof_proj / tot)

    def means(d):
        return {k: statistics.mean(v) for k, v in d.items() if v}

    ma, ms = means(phase_attr), means(phase_shape)

    # Gross phase shares (camp / full week / offseason) — prior readout.
    gross_keys = ("camp", "week", "offseason")
    tot_a_gross = sum(ma.get(k, 0.0) for k in gross_keys) or 1.0
    tot_s_gross = sum(ms.get(k, 0.0) for k in gross_keys) or 1.0

    # Gain-driven phase shares: camp + week_gain + offseason (decay excluded).
    gain_keys = ("camp", "week_gain", "offseason")
    tot_a_gain = sum(ma.get(k, 0.0) for k in gain_keys) or 1.0
    tot_s_gain = sum(ms.get(k, 0.0) for k in gain_keys) or 1.0

    week_s = ms.get("week", 0.0) or 1e-9
    camp_s = ms.get("camp", 0.0)
    week_gain_s = ms.get("week_gain", 0.0)

    return {
        "mode": mode,
        "n": n,
        "mean_individual_shape_cosine_sim_FR_to_SR": statistics.mean(retentions),
        "mean_along_shape": statistics.mean(along_vals) if along_vals else None,
        "mean_across_shape": statistics.mean(across_vals) if across_vals else None,
        "mean_along_share": statistics.mean(along_shares) if along_shares else None,
        "mean_across_share": statistics.mean(across_shares) if across_shares else None,
        "phase_attr_l1_means": ma,
        "phase_shape_l1_means": ms,
        "phase_attr_shares_gross": {k: ma.get(k, 0.0) / tot_a_gross for k in gross_keys},
        "phase_shape_shares_gross": {k: ms.get(k, 0.0) / tot_s_gross for k in gross_keys},
        "phase_attr_shares_gain_driven": {
            k: ma.get(k, 0.0) / tot_a_gain for k in gain_keys
        },
        "phase_shape_shares_gain_driven": {
            k: ms.get(k, 0.0) / tot_s_gain for k in gain_keys
        },
        "in_season_shape_decay_fraction": (
            ms.get("week_decay", 0.0) / week_s if ms.get("week") else None
        ),
        "in_season_shape_gain_fraction": (
            week_gain_s / week_s if ms.get("week") else None
        ),
        "camp_to_inseason_shape_ratio_gross": (
            camp_s / ms["week"] if ms.get("week") else None
        ),
        "camp_to_inseason_shape_ratio_gain_driven": (
            camp_s / week_gain_s if week_gain_s > 1e-9 else None
        ),
        "of_shape_move_share_from_training_phases": (
            statistics.mean(phase_shape_coach_block) if phase_shape_coach_block else None
        ),
        "of_shape_move_share_from_offseason": (
            statistics.mean(phase_shape_off_block) if phase_shape_off_block else None
        ),
        "proj_coach_share": statistics.mean(coach_share) if coach_share else None,
        "proj_profile_share": statistics.mean(profile_share) if profile_share else None,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    for mode in (*STRATEGIES, "offseason_only"):
        print(f"Running {mode}...", flush=True)
        results[mode] = run_arm(mode, N_CAREERS)
        r = results[mode]
        print(
            f"  retention={r['mean_individual_shape_cosine_sim_FR_to_SR']:.3f}  "
            f"along={r['mean_along_shape']}  across={r['mean_across_shape']}  "
            f"coach={r['proj_coach_share']}  "
            f"week_decay_frac={r['in_season_shape_decay_fraction']}  "
            f"camp:week_gain={r['camp_to_inseason_shape_ratio_gain_driven']}",
            flush=True,
        )
        print(json.dumps(r, indent=2), flush=True)

    # Cosine retention conflates sharpening with conversion — report both ladders.
    cosine_ladder = {
        m: results[m]["mean_individual_shape_cosine_sim_FR_to_SR"]
        for m in STRATEGIES
    }
    across_ladder = {m: results[m]["mean_across_shape"] for m in STRATEGIES}
    along_ladder = {m: results[m]["mean_along_shape"] for m in STRATEGIES}
    camp_ratios = {
        m: results[m]["camp_to_inseason_shape_ratio_gain_driven"] for m in STRATEGIES
    }

    payload = {
        "targets": {
            "phase_attribute": {"offseason": 0.35, "camp": 0.35, "in_season": 0.30},
            "phase_shape_camp_to_inseason_gain_driven": 1.0,  # ~half / ~half of coaching shape
            "force_retention": 0.55,
        },
        "strategy_retention_ladder": cosine_ladder,
        "strategy_along_shape_ladder": along_ladder,
        "strategy_across_shape_ladder": across_ladder,
        "camp_to_inseason_shape_ratio_gain_driven_by_arm": camp_ratios,
        "arms": results,
        "build": {
            "OFFSEASON_ATTRACTOR_ALPHA": float(dev.OFFSEASON_ATTRACTOR_ALPHA),
            "CAMP_WEEKS": CAMP_WEEKS,
            "CAMP_GAIN_SCALE": CAMP_GAIN_SCALE,
        },
        "notes": [
            "reference = reinforce strengths (CPU path) — specialisation, not a null.",
            "mild = primaries + light secondary; preserves more than reference sharpening.",
            "moderate = conversion@4 + primary@2 hedge — partial conversion is correct.",
            "extreme = 5 units on anti-archetype wall/near-wall attr.",
            "cosine retention conflates along-shape (sharpening) with across-shape (conversion).",
            "strategy_across_shape_ladder is the conversion-only reading.",
            "In-season decomposed: apply_pre_training_conditions then gains-only execute.",
            "phase_*_shares_gain_driven excludes week_decay from the denominator.",
            "camp_to_inseason_shape_ratio_gain_driven is the fair camp:coach comparison.",
        ],
    }
    out_path = OUT / "baseline_strategy_spread.json"
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {out_path}", flush=True)
    print("COSINE RETENTION:", json.dumps(cosine_ladder, indent=2), flush=True)
    print("ALONG (sharpening):", json.dumps(along_ladder, indent=2), flush=True)
    print("ACROSS (conversion):", json.dumps(across_ladder, indent=2), flush=True)
    print("CAMP:WEEK_GAIN (shape):", json.dumps(camp_ratios, indent=2), flush=True)


if __name__ == "__main__":
    main()
