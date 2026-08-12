#!/usr/bin/env python3
"""
Compare two [EOG-BAND] logs record-by-record — the RESTORE-VALIDATION check.

Protocol: snapshot → seeded 1-week run (pool OFF) → restore → same seed again.
Identical starting state + identical RNG ⇒ identical output, IFF the restore set is
complete. Any divergence means a hole. This compares actual records, not aggregate
stats (a partial restore can leave summary numbers barely moved yet differ per row).

Records are matched by (week, team_id_label, attr) — unique per team-game. For each
matched pair it compares the band-selecting INPUTS, the band label, and raw_delta/pre.
This tool REPORTS divergence; it does NOT diagnose the cause — input divergence is
consistent with a restore hole OR global-random nondeterminism (training + EOG draw
from global random, which pymongo consumes non-reproducibly). Diagnosis requires the
RNG-free checks: `eog_arm_snapshot.py --verify` (captured collections revert?) and
`eog_db_sweep.py` (did anything outside the capture set change?).

  • inputs identical, only band/raw_delta/pre differ → the sim started from the same
    state (identical inputs prove it); only the global-random EOG deltas diverged.
  • INPUTS differ, or a key present in only one run → runs diverged from divergent
    state OR from training nondeterminism propagating into game inputs — UNDETERMINED
    here; consult --verify + the sweep.

Exit 0 = fully identical. Exit 4 = inputs identical, only deltas diverge. Exit 3 =
input/structural divergence, cause undetermined (see --verify + sweep).

Usage: python scripts/eog_band_diff.py runA.jsonl runB.jsonl
"""
from __future__ import annotations

import json
import sys

TAG = "[EOG-BAND] "
HEADER_TAG = "[EOG-BAND-HEADER] "


def load(path: str) -> dict:
    """(week, team, attr) -> record. Headers ignored (utc/git_sha differ by design)."""
    out = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith(HEADER_TAG):
                continue
            payload = line[len(TAG):] if line.startswith(TAG) else line
            try:
                r = json.loads(payload)
            except json.JSONDecodeError:
                continue
            out[(r.get("week"), r.get("team_id_label"), r.get("attr"))] = r
    return out


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    a, b = load(sys.argv[1]), load(sys.argv[2])
    keys = set(a) | set(b)
    only_a = [k for k in keys if k not in b]
    only_b = [k for k in keys if k not in a]

    input_diffs, delta_only_diffs, identical = [], [], 0
    for k in sorted(set(a) & set(b)):
        ra, rb = a[k], b[k]
        if ra.get("inputs") != rb.get("inputs"):
            input_diffs.append(k)
        elif (ra.get("band"), ra.get("raw_delta"), ra.get("pre")) != (rb.get("band"), rb.get("raw_delta"), rb.get("pre")):
            delta_only_diffs.append(k)
        else:
            identical += 1

    print(f"records: A={len(a)} B={len(b)}  matched={len(set(a) & set(b))}")
    print(f"  identical:            {identical}")
    print(f"  INPUTS differ:        {len(input_diffs)}   (restore hole → contaminated start)")
    print(f"  delta-only differ:    {len(delta_only_diffs)}   (EOG global-random nondeterminism)")
    print(f"  key only in A / only in B: {len(only_a)} / {len(only_b)}   (structural → restore hole)")

    def sample(label, ks):
        for k in ks[:5]:
            print(f"    {label} {k}")
            if label == "INPUT-DIFF":
                print(f"      A.inputs={a[k].get('inputs')}")
                print(f"      B.inputs={b[k].get('inputs')}")

    if input_diffs:
        sample("INPUT-DIFF", input_diffs)
    if only_a or only_b:
        sample("ONLY-A", only_a); sample("ONLY-B", only_b)

    if input_diffs or only_a or only_b:
        print("\n⚠️  RUNS DIVERGED (inputs and/or structure) — cause UNDETERMINED from this "
              "tool alone. Input divergence is consistent with a restore hole OR global-random "
              "nondeterminism (training/EOG on global random, pymongo consumes it). Diagnose "
              "with `eog_arm_snapshot.py --verify` and `eog_db_sweep.py`: if BOTH are clean, "
              "this is nondeterminism and the restore is complete; if either is dirty, it's a "
              "restore hole. Do NOT run arms until those are checked.")
        return 3
    if delta_only_diffs:
        print("\n⚠️  Inputs identical everywhere (same starting state), but some EOG deltas "
              "diverge → global-random/pymongo nondeterminism only. Not a restore-completeness "
              "signal; the arms (unseeded) are unaffected.")
        return 4
    print("\n✅ FULLY IDENTICAL — same start and a deterministic pipeline for this run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
