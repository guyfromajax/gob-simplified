"""Exact-diff two refstats CSVs. Reports which stat columns moved, and where."""
import csv
import sys
from collections import Counter

KEY = ("kind", "matchup", "seed", "side")


def load(p):
    rows = {}
    with open(p) as fh:
        for r in csv.DictReader(fh):
            rows[tuple(r[k] for k in KEY)] = r
    return rows


def main(a_path, b_path):
    A, B = load(a_path), load(b_path)
    print(f"A: {a_path}  ({len(A)} rows)")
    print(f"B: {b_path}  ({len(B)} rows)")

    only_a, only_b = set(A) - set(B), set(B) - set(A)
    if only_a or only_b:
        print(f"⚠️  key mismatch: {len(only_a)} only-in-A, {len(only_b)} only-in-B")
        for k in list(only_a)[:3]:
            print("   A-only:", k)
        for k in list(only_b)[:3]:
            print("   B-only:", k)

    shared = sorted(set(A) & set(B))
    col_moves = Counter()
    rows_changed = 0
    examples = []
    for k in shared:
        ra, rb = A[k], B[k]
        diffs = {c: (ra[c], rb[c]) for c in ra
                 if c not in KEY and ra.get(c) != rb.get(c)}
        if diffs:
            rows_changed += 1
            for c in diffs:
                col_moves[c] += 1
            if len(examples) < 8:
                examples.append((k, diffs))

    print()
    if not rows_changed and not only_a and not only_b:
        print(f"✅ EXACT MATCH — all {len(shared)} rows byte-identical across every column.")
        return 0

    print(f"❌ {rows_changed}/{len(shared)} rows differ")
    print(f"\n{'column':<18}{'rows moved':>12}")
    print("-" * 30)
    for c, n in col_moves.most_common():
        print(f"{c:<18}{n:>12}")
    print("\nfirst differing rows:")
    for k, d in examples:
        print(f"  {k}")
        for c, (x, y) in list(d.items())[:6]:
            print(f"      {c}: {x} -> {y}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
