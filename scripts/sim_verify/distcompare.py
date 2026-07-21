"""
Pooled distributional comparison between two arms (e.g. pre-B vs post-B).

Each arm = one or more refstats CSVs. Compares, per stat column, the pooled
means and spreads, and reports Welch's t (unequal variance) plus an F-ratio on
the variances. Splits CPU and PS since they are different populations.

usage: distcompare.py "<globA>" "<globB>" [labelA labelB]
"""
import csv
import glob
import math
import statistics as st
import sys

COLS = ["final_score", "possessions", "FGM", "FGA", "FG_pct", "TPM", "TPA",
        "TP_pct", "FTM", "FTA", "FT_pct", "TO", "OREB", "DREB", "REB",
        "AST", "STL", "BLK", "PF"]


def load(pattern, kind):
    rows = []
    files = sorted(glob.glob(pattern))
    for p in files:
        with open(p) as fh:
            rows += [r for r in csv.DictReader(fh) if r["kind"] == kind]
    return rows, files


def welch(a, b):
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan"), float("nan")
    ma, mb = st.mean(a), st.mean(b)
    va, vb = st.variance(a), st.variance(b)
    se = math.sqrt(va / na + vb / nb)
    t = (mb - ma) / se if se else 0.0
    f = (vb / va) if va else float("nan")
    return t, f


def main():
    gA, gB = sys.argv[1], sys.argv[2]
    la = sys.argv[3] if len(sys.argv) > 3 else "A"
    lb = sys.argv[4] if len(sys.argv) > 4 else "B"

    for kind in ("cpu_full", "practice_squad"):
        A, fa = load(gA, kind)
        B, fb = load(gB, kind)
        if not A or not B:
            continue
        print(f"\n{'='*92}\n{kind.upper()}   {la}: {len(A)} rows / {len(fa)} files    "
              f"{lb}: {len(B)} rows / {len(fb)} files\n{'='*92}")
        print(f"{'stat':<14}{la+' mean':>12}{lb+' mean':>12}{'delta':>10}"
              f"{'Welch t':>10}{la+' sd':>10}{lb+' sd':>10}{'F(var)':>9}  flag")
        print("-" * 92)
        flagged = []
        for c in COLS:
            try:
                xa = [float(r[c]) for r in A]
                xb = [float(r[c]) for r in B]
            except (KeyError, ValueError):
                continue
            t, f = welch(xa, xb)
            sa, sb = st.pstdev(xa), st.pstdev(xb)
            # |t| > 3 on this many rows is a real shift, not sampling noise
            flag = "  <-- SHIFT" if abs(t) > 3 else ""
            if flag:
                flagged.append(c)
            print(f"{c:<14}{st.mean(xa):>12.3f}{st.mean(xb):>12.3f}"
                  f"{st.mean(xb)-st.mean(xa):>+10.3f}{t:>10.2f}{sa:>10.2f}{sb:>10.2f}{f:>9.3f}{flag}")
        print("-" * 92)
        if flagged:
            print(f"⚠️  {len(flagged)} column(s) shifted beyond |t|>3: {', '.join(flagged)}")
        else:
            print("✅ no column shifted beyond |t|>3 — distributions consistent")


if __name__ == "__main__":
    main()
