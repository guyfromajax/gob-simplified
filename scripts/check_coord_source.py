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

# Scope: ALL engine decision/resolver modules — every *.py under BackEnd/engine
# EXCEPT the step emitters. Emitters are the render source of truth and are
# ALLOWED to read player.coords (they author where players are drawn); decision
# logic must read the emitter's output instead. (2026-07-07: widened from the 5
# FB modules to all turns once the FB decision path hit 0 — a ratchet so a new
# stale seed in ANY turn fails CI. Discovery found the player.coords-read pattern
# is FB-concentrated; other turns start near 0.)
def _scope():
    import glob
    out = []
    for path in sorted(glob.glob(os.path.join(REPO, "BackEnd/engine/*.py"))):
        base = os.path.basename(path)
        if base.endswith("_emitter.py") or "step_emitter" in base:
            continue
        out.append(os.path.relpath(path, REPO))
    return out


SCOPE = _scope()

# Per-scope baseline of KNOWN stale-seed sites (drive to 0 as turns migrate).
# Update DOWN only, never up — an increase is a regression the guard must catch.
BASELINE = 0  # placeholder; set from the run below

# Stale sources = reading a player's MUTABLE position: the FB helpers
# (_coord_of / _lineup_starts_by_pos, both wrap player.coords) and direct
# ``X.coords`` attribute reads. Dict access (``["coords"]`` = emitter step data)
# is NOT flagged. Writes (``X.coords = ...``) are excluded separately.
PATTERNS = [
    re.compile(r"\b_lineup_starts_by_pos\s*\("),
    re.compile(r"\b_coord_of\s*\("),
    re.compile(r"\.coords\b"),
]
WRITE_PATTERN = re.compile(r"\.coords\s*=")          # X.coords = ... is a write, not a decision read
OK_ANNOTATION = "# coord-source-ok:"


def _exempt(line: str) -> bool:
    s = line.strip()
    if s.startswith(("#", "from ", "import ", "def _lineup_starts_by_pos", "def _coord_of")):
        return True
    if s.startswith(('"""', "'''")):      # single-line / opening docstring prose
        return True
    if OK_ANNOTATION in line:             # explicit render-consistent/infra exemption
        return True
    if "logging." in line or "logger." in line:   # log strings mention coords for debugging, not decisions
        return True
    return False


def _code_part(line: str) -> str:
    """The line with any trailing ``# ...`` comment stripped, so ``.coords``
    mentioned in an explanatory comment isn't matched as a read. (Naive on ``#``
    inside string literals — acceptable; exemptions are checked on the full line
    first.)"""
    return line.split("#", 1)[0]


def violations():
    hits = []
    for rel in SCOPE:
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            continue
        in_docstring = False
        with open(path, "r", encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                # Skip docstring bodies (prose that may mention .coords / helpers).
                fences = line.count('"""') + line.count("'''")
                if in_docstring:
                    if fences % 2 == 1:
                        in_docstring = False
                    continue
                if fences % 2 == 1:
                    in_docstring = True
                    continue
                if _exempt(line):
                    continue
                code = _code_part(line)
                if WRITE_PATTERN.search(code):   # X.coords = ... is a write, not a read
                    continue
                if any(p.search(code) for p in PATTERNS):
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
