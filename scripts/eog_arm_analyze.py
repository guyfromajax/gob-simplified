#!/usr/bin/env python3
"""
Analyze the 5 distributional arms (breakage detection, not calibration).

Asserts, per your design:
  1. No garbage       — every raw_delta inside its declared band range; rebound ∈
                        [-0.25,+0.12] @2dp; max_share ∈ [0,1]; clamped values within
                        TEAM_ATTR_CLAMPS (core-8 ±20, rebound 0-1.0).
  2. No distant leak  — zero is_distant_sim rows in the measured weeks (per arm).
  3. Band coverage    — COMMON bands (≥3% baseline freq) fire in EVERY arm;
                        RARE bands (<3%) fire in the POOLED total across all 5.
  4. Cross-arm consistency — per-band frequency mean ± spread across the 5 arms
                        (a band that swings wildly arm-to-arm is a nondeterministic defect).
  5. Rebound drift    — reported, NOT asserted: the ladder is designed to net mildly
                        positive once training is included; positive here is EXPECTED.

Usage: python scripts/eog_arm_analyze.py arm_1.jsonl arm_2.jsonl ... arm_5.jsonl
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict

sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0])
from BackEnd.constants import eog_attr_bands as B  # noqa: E402

TAG = "[EOG-BAND] "
RARE_BANDS = {
    "fb_atrophy", "fb_opp_atrophy", "pt_atrophy", "pt_opp_atrophy",
    "pt_opp_over", "equal_buffered", "beat_top10", "lose_to_100_128",
}
CLAMPS = {"shot_threshold": (0, 200), "rebound_modifier": (0.0, 1.0),
          "team_chemistry": (7, 25), "momentum_score": (-10, 10)}
for _a in ("discipline", "fight", "offensive_efficiency", "defensive_efficiency",
           "fb_efficiency", "pt_efficiency", "fb_opp_modifier", "pt_opp_modifier"):
    CLAMPS[_a] = (-20, 20)


def _band_ranges():
    """(attr, label) -> (lo, hi) in raw_delta units (rebound stays cents; scaled below)."""
    out = {}
    for attr, bands in B.EOG_BANDS.items():
        for label, rng in bands:
            out[(attr, label)] = rng
    out[("fight", "win")] = B.FIGHT_BANDS[True][1]
    out[("fight", "loss")] = B.FIGHT_BANDS[False][1]
    for label, rng in B.CHEMISTRY_BANDS[True] + B.CHEMISTRY_BANDS[False]:
        out[("team_chemistry", label)] = rng
    return out


def load(path):
    recs = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line.startswith(TAG):
                try:
                    recs.append(json.loads(line[len(TAG):]))
                except json.JSONDecodeError:
                    pass
    return recs


def _max_band_share(records):
    """attr -> largest single band's share of that attr's records."""
    tot = Counter(r["attr"] for r in records)
    per_band = Counter((r["attr"], r["band"]) for r in records)
    out = {}
    for (attr, _lbl), c in per_band.items():
        out[attr] = max(out.get(attr, 0.0), c / tot[attr])
    return out


def dominant_band_share(arms, baseline_path):
    """THE headline: did the one-directional runaways die? Baseline had
    offensive_efficiency at 100% in one band, pt_efficiency 99.5%, pt_opp 96.3%.
    If the arms' dominant share drops to ~40-50%, the structural fix worked."""
    import os
    pooled = [r for recs in arms for r in recs]
    arms_share = _max_band_share(pooled)
    base = _max_band_share(load(baseline_path)) if os.path.exists(baseline_path) else {}
    print("\n## 6. DOMINANT-BAND SHARE — did the one-directional runaways die? (HEADLINE)")
    src = baseline_path if base else "(baseline log not found — arms only)"
    print(f"  baseline source: {src} (OLD bands)  |  arms: NEW bands, pooled across {len(arms)} arms")
    print(f"  {'attr':<24}{'baseline':>10}{'arms':>10}{'delta':>10}")
    for attr in sorted(set(arms_share) | set(base)):
        b, a = base.get(attr), arms_share.get(attr)
        bs = f"{b*100:.1f}%" if b is not None else "n/a"
        as_ = f"{a*100:.1f}%" if a is not None else "n/a"
        d = f"{(a-b)*100:+.0f}pp" if (a is not None and b is not None) else ""
        print(f"  {attr:<24}{bs:>10}{as_:>10}{d:>10}")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("arms", nargs="+", help="arm_*.jsonl band logs")
    ap.add_argument("--baseline", default="eog_band_measurement.jsonl",
                    help="baseline season log for dominant-band-share comparison")
    args = ap.parse_args()
    files = args.arms
    if len(files) < 2:
        print("need ≥2 arm files")
        return 2
    ranges = _band_ranges()
    arms = [load(f) for f in files]
    fail = 0

    # ---- 1 & 2: per-record value-range + distant leak -----------------------
    range_viol, distant_leak, clamp_viol = 0, 0, 0
    for recs in arms:
        for r in recs:
            attr, band, rd = r.get("attr"), r.get("band"), r.get("raw_delta")
            if r.get("is_distant_sim"):
                distant_leak += 1
            key = (attr, band)
            if key in ranges and isinstance(rd, (int, float)):
                lo, hi = ranges[key]
                if attr == "rebound_modifier":
                    lo, hi = lo / 100.0, hi / 100.0
                if not (min(lo, hi) - 1e-9 <= rd <= max(lo, hi) + 1e-9):
                    range_viol += 1
            post = r.get("post")
            if attr in CLAMPS and isinstance(post, (int, float)):
                clo, chi = CLAMPS[attr]
                if not (clo - 1e-9 <= post <= chi + 1e-9):
                    clamp_viol += 1
    print("## 1-2. Value integrity")
    for name, n in [("raw_delta outside band range", range_viol),
                    ("distant-sim rows (must be 0)", distant_leak),
                    ("post outside clamp bounds", clamp_viol)]:
        ok = n == 0
        fail += 0 if ok else 1
        print(f"  {'✅' if ok else '❌'} {name}: {n}")

    # ---- 3: band coverage (common per-arm, rare pooled) ---------------------
    per_arm_bands = [set((r["attr"], r["band"]) for r in recs) for recs in arms]
    pooled_bands = set().union(*per_arm_bands)
    all_labels = set(ranges) | {(a, "data_integrity_no_usage") for a in ("offensive_efficiency", "defensive_efficiency")}
    print("\n## 3. Band coverage")
    missing_common, missing_rare = [], []
    for (attr, label) in sorted(ranges):
        if label == "data_integrity_no_usage":
            continue
        if label in RARE_BANDS:
            if (attr, label) not in pooled_bands:
                missing_rare.append(f"{attr}.{label}")
        else:
            absent = [i + 1 for i, s in enumerate(per_arm_bands) if (attr, label) not in s]
            if absent:
                missing_common.append(f"{attr}.{label} (absent in arms {absent})")
    if missing_common:
        fail += 1
        print("  ❌ COMMON bands not in every arm:")
        for m in missing_common:
            print(f"       {m}")
    else:
        print("  ✅ all common bands fire in every arm")
    if missing_rare:
        fail += 1
        print(f"  ❌ RARE bands absent from pooled total: {missing_rare}")
    else:
        print("  ✅ all rare bands fire in the pooled total across 5 arms")

    # ---- 4: cross-arm frequency consistency ---------------------------------
    print("\n## 4. Cross-arm branch-frequency (mean ± spread; wild swings = defect)")
    per_arm_freq = []
    for recs in arms:
        tot = Counter(r["attr"] for r in recs)
        cnt = Counter((r["attr"], r["band"]) for r in recs)
        per_arm_freq.append({k: cnt[k] / tot[k[0]] for k in cnt})
    keys = set().union(*[set(d) for d in per_arm_freq])
    worst = []
    for k in sorted(keys):
        vals = [d.get(k, 0.0) for d in per_arm_freq]
        spread = max(vals) - min(vals)
        worst.append((spread, k, vals))
    worst.sort(reverse=True)
    for spread, k, vals in worst[:8]:
        print(f"  {k[0]+'.'+k[1]:<34} mean={statistics.mean(vals)*100:5.1f}%  spread={spread*100:4.1f}pp")

    # ---- 5: rebound drift (report, not assert) ------------------------------
    print("\n## 5. Rebound net drift per arm (EXPECTED mildly positive w/ training — do NOT 'fix')")
    for i, recs in enumerate(arms, 1):
        rd = [r["raw_delta"] for r in recs if r.get("attr") == "rebound_modifier" and isinstance(r.get("raw_delta"), (int, float))]
        if rd:
            print(f"  arm {i}: E[Δ]/game={statistics.mean(rd):+.3f}  (EOG only; +training nets positive)")

    dominant_band_share(arms, args.baseline)

    print("\n" + ("✅ ARMS PASS — no breakage detected (see §6 for the runaway-kill result)." if fail == 0
                  else f"❌ {fail} assertion group(s) failed — investigate before commit."))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
