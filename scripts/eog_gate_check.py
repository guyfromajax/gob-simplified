#!/usr/bin/env python3
"""
Measurement gate: verify BOTH the captured data shape AND that the treatment is active.

The week-1 gate for the identity season passed on data shape (1,408 rows, 64 game_ids,
11 attrs) while identity was COMPLETELY INACTIVE — all 128 teams on flat-neutral all-2s
sliders. That is the same family of error as an exact-diff that compares nothing: the
check was green because it was measuring the wrong thing.

So this gate asserts the treatment too:
  * every team carries a persisted identity (vision pair)
  * strategy sliders VARY across the league (zero variance == treatment inactive)
  * the vision distribution is reported for eyeballing against the single-mode shape

Exits non-zero if the treatment is not active, so it can gate a season run.

usage: eog_gate_check.py <band_log.jsonl> [--franchise-id ID] [--expect-rows 1408]
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
import json
import os
import sys
from collections import Counter

TAG = "[EOG-BAND] "
HDR = "[EOG-BAND-HEADER] "

# Observed in the single-game-mode identity run. Franchise may legitimately differ —
# reported for comparison, never asserted.
SINGLE_MODE_REFERENCE = {
    "offense": "Run and Gun / Spread / Inside-Out / Attack / Motion",
    "note": "single-mode shape was ~40/35/24/19/10 offensive, ~32/31/26/23/16 defensive",
}


def check_data_shape(path: str, expect_rows: int) -> tuple[bool, list[str]]:
    notes: list[str] = []
    ok = True
    if not os.path.exists(path):
        return False, [f"band log not found: {path}"]
    hdrs: list[dict] = []
    attrs: Counter = Counter()
    weeks: Counter = Counter()
    games: set = set()
    bad = 0
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        if line.startswith(HDR):
            try:
                hdrs.append(json.loads(line[len(HDR):]))
            except json.JSONDecodeError:
                bad += 1
            continue
        try:
            r = json.loads(line[len(TAG):] if line.startswith(TAG) else line)
        except json.JSONDecodeError:
            bad += 1
            continue
        if not isinstance(r, dict) or not isinstance(r.get("attr"), str):
            bad += 1
            continue
        attrs[r["attr"]] += 1
        weeks[r.get("week")] += 1
        if r.get("game_id"):
            games.add(r["game_id"])

    total = sum(attrs.values())
    notes.append(f"band rows          : {total}"
                 + (f"   (expected {expect_rows})" if expect_rows else ""))
    notes.append(f"distinct game_ids  : {len(games)}")
    notes.append(f"distinct attrs     : {len(attrs)}  rows/attr={sorted(set(attrs.values()))}")
    notes.append(f"weeks present      : {sorted(w for w in weeks if w is not None)}")
    notes.append(f"header records     : {len(hdrs)}")
    for h in hdrs:
        notes.append(f"   git_sha={h.get('git_sha')} flags={h.get('flags')}")
    notes.append(f"unparseable        : {bad}")
    if expect_rows and total != expect_rows:
        ok = False
        notes.append(f"❌ row count {total} != expected {expect_rows}")
    if bad:
        ok = False
        notes.append(f"❌ {bad} unparseable line(s)")
    if len(attrs) != 11:
        ok = False
        notes.append(f"❌ expected 11 attrs, got {len(attrs)}")
    return ok, notes


def check_treatment(franchise_id: str) -> tuple[bool, list[str]]:
    from BackEnd.utils.franchise_identity import franchise_identity_summary

    s = franchise_identity_summary(franchise_id)
    notes = [
        f"teams                    : {s['teams']}",
        f"teams with an identity   : {s['teams_with_identity']}",
    ]
    ok = True
    if s["teams"] == 0:
        return False, notes + ["❌ no FTD documents for this franchise"]
    if s["teams_with_identity"] < s["teams"]:
        ok = False
        notes.append(f"❌ {s['teams'] - s['teams_with_identity']} team(s) have NO persisted "
                     f"identity — treatment is not fully active")

    notes.append("offensive visions        : " + json.dumps(s["offensive_visions"]))
    notes.append("defensive visions        : " + json.dumps(s["defensive_visions"]))
    notes.append(f"   (single-mode reference: {SINGLE_MODE_REFERENCE['note']})")

    notes.append("slider variance across the league:")
    zero = []
    for k, v in sorted(s["slider_variance"].items(), key=lambda x: -x[1]):
        notes.append(f"   {k:<12} var={v:<8} distinct={s['slider_distinct_values'].get(k)}")
        if v == 0:
            zero.append(k)
    # The identity draw always varies these three; if they are flat the treatment is off.
    critical = [k for k in ("aggression", "hc_trap", "fc_press") if k in zero]
    if critical:
        ok = False
        notes.append(f"❌ ZERO VARIANCE on {critical} — every team identical. "
                     f"The treatment is INACTIVE; a season run would measure nothing.")
    elif zero:
        notes.append(f"⚠️  zero variance on {zero} (not identity-driven sliders — check "
                     f"whether that is expected)")
    return ok, notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", nargs="?",
                    default=os.environ.get("GOB_EOG_BAND_LOG_FILE", "eog_band_log.jsonl"))
    ap.add_argument("--franchise-id",
                    default=os.environ.get("GOB_MEASUREMENT_FRANCHISE_ID"))
    ap.add_argument("--expect-rows", type=int, default=1408,
                    help="expected band rows (1408 = one week). 0 to skip.")
    ap.add_argument("--skip-data", action="store_true",
                    help="only run the treatment check (no band log yet)")
    args = ap.parse_args()

    all_ok = True
    if not args.skip_data:
        print("=" * 68)
        print("DATA SHAPE")
        print("=" * 68)
        ok, notes = check_data_shape(args.path, args.expect_rows)
        for n in notes:
            print("  " + n)
        all_ok &= ok

    print("\n" + "=" * 68)
    print("TREATMENT ACTIVE  (identity persisted + sliders actually vary)")
    print("=" * 68)
    if not args.franchise_id:
        print("  ❌ no --franchise-id / GOB_MEASUREMENT_FRANCHISE_ID")
        all_ok = False
    else:
        ok, notes = check_treatment(args.franchise_id)
        for n in notes:
            print("  " + n)
        all_ok &= ok

    print("\n" + ("✅ GATE PASSED — safe to run the season"
                  if all_ok else "❌ GATE FAILED — do not start the season"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
