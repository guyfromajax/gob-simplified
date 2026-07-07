#!/usr/bin/env python3
"""Coord-source guardrail (UESS §1 enforcement).

Game *decision* logic must read player positions from the emitter's rendered
step coords, NEVER from `player.coords` / a re-derived start. The concrete stale
sources are `_lineup_starts_by_pos(...)` and `_coord_of(...)` (both read
`player.coords`) and direct `player.coords` reads.

This guard greps the scoped DECISION/RESOLVER modules for those call sites and
fails if the count EXCEEDS the recorded baseline — a ratchet: new violations are
blocked, and the baseline is driven to 0 as each turn is migrated to
emit-then-resolve. A legitimate render-consistent seed (e.g. bh_start from the
resolver-authored `rr_to`) or a line inside an emitter can be exempted with a
trailing `# coord-source-ok: <reason>` comment.

Run: `python scripts/check_coord_source.py`  (no DB; pure file read)
See: _documentation_master/05_UESS_System/Coord_Source_Registry.md
"""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Scoped decision/resolver modules (expand as more turns are migrated).
SCOPE = [
    "BackEnd/engine/fb_drive_resolution.py",
    "BackEnd/engine/rim_runner_drive_integration.py",
    "BackEnd/engine/covert_release_drive_integration.py",
    "BackEnd/engine/after_steal_drive_integration.py",
    "BackEnd/engine/rim_runner_fast_break.py",
]

# Per-scope baseline of KNOWN stale-seed call sites (drive to 0 as turns migrate).
# Update DOWN only, never up — an increase is a regression the guard must catch.
BASELINE = 20  # 2026-07-07: FB decision path pre-emit-then-resolve migration. Drive to 0.

# The concrete stale sources: both helpers read player.coords. Their CALL sites in
# decision code are the violations (helper definitions / docstrings are exempt).
PATTERNS = [
    re.compile(r"\b_lineup_starts_by_pos\s*\("),
    re.compile(r"\b_coord_of\s*\("),
]
OK_ANNOTATION = "# coord-source-ok:"


def _exempt(line: str) -> bool:
    s = line.strip()
    if s.startswith(("#", "from ", "import ", "def _lineup_starts_by_pos", "def _coord_of")):
        return True
    if "``" in line:                      # docstring prose mentioning the helper
        return True
    if OK_ANNOTATION in line:             # explicit render-consistent/infra exemption
        return True
    return False


def violations():
    hits = []
    for rel in SCOPE:
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                if _exempt(line):
                    continue
                if any(p.search(line) for p in PATTERNS):
                    hits.append((rel, i, line.strip()))
    return hits


def main():
    hits = violations()
    print(f"coord-source guard: {len(hits)} stale-seed site(s) (baseline {BASELINE})\n")
    for rel, ln, text in hits:
        print(f"  {rel}:{ln}: {text}")
    if len(hits) > BASELINE:
        print(f"\nFAIL: {len(hits)} > baseline {BASELINE} — a NEW stale coord seed was "
              f"introduced in decision code. Read from the emitter's rendered step "
              f"coords, or exempt with `# coord-source-ok: <reason>`.")
        return 1
    if len(hits) < BASELINE:
        print(f"\nProgress: {len(hits)} < baseline {BASELINE} — lower BASELINE to "
              f"{len(hits)} to lock in the win.")
    else:
        print("\nOK: at baseline (no new violations).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
