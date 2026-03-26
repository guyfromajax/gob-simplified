#!/usr/bin/env python3
"""
Mechanical aid for position snapshot coverage (see
docs/docs_1_systems/00_General_Systems/Position_Checkpoints_and_Snapshot_Schema.md §8).

Run from repo root:
  python scripts/audit_position_snapshots.py

Prints:
  - Files under BackEnd/ that reference attach_position_snapshots (with call counts)
  - Suggested ripgrep follow-ups for manual review

This does not prove every turn path is covered; it keeps the wiring map honest.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    backend = root / "BackEnd"
    if not backend.is_dir():
        print("Expected BackEnd/ next to scripts/", file=sys.stderr)
        return 1

    needle_attach = "attach_position_snapshots"
    needle_key = "position_snapshots"
    per_attach: Counter[str] = Counter()
    per_key: Counter[str] = Counter()
    for path in sorted(backend.rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        na = len(re.findall(re.escape(needle_attach), text))
        if na:
            rel = path.relative_to(root)
            per_attach[str(rel)] = na
        nk = len(re.findall(r"\bposition_snapshots\b", text))
        if nk:
            rel = path.relative_to(root)
            per_key[str(rel)] = nk

    print("attach_position_snapshots references (BackEnd/**/*.py)\n")
    for f, n in sorted(per_attach.items(), key=lambda x: (-x[1], x[0])):
        print(f"  {n:2d}  {f}")
    print(f"\nTotal files: {len(per_attach)}  Total references: {sum(per_attach.values())}")

    print("\nOccurrences of `position_snapshots` (includes ledger, attach, inline OREB dicts)\n")
    for f, n in sorted(per_key.items(), key=lambda x: (-x[1], x[0])):
        print(f"  {n:2d}  {f}")
    print(f"\nTotal files: {len(per_key)}")
    print("\nSuggested manual greps (new early-return results):")
    print('  rg \'"result_type"\' BackEnd/engine/phase_resolution.py')
    print("  rg 'return result' BackEnd/engine/phase_resolution.py")
    print("  rg 'DEFENSIVE_STOP' BackEnd/engine/phase_resolution.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
