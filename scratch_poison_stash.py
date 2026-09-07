"""ACCEPTANCE F principle 8 — POISON-STASH, not exact-diff.

The baseline delta came back empty. That is either (a) the change genuinely breaks
no assertion, or (b) the suite never observes this branch, in which case a green
baseline is not evidence of anything. Principle 8 says decide that by poisoning,
not by staring at a diff.

Poison A: revert the fix entirely (location-only dispatch + centre fallthrough).
Poison B: keep the fix but corrupt the resolved coordinate, so every spot resolves
          to a WRONG real coordinate. This separates "suite sees this code" from
          "suite sees centre-court specifically".

If the suite returns 114 under both poisons, it is blind to this branch and the
empty delta carries no information about correctness.
"""
import hashlib
import pathlib
import subprocess
import sys

CONV = pathlib.Path("BackEnd/engine/defender_placement.py")
ORIGINAL = CONV.read_bytes()
SHA0 = hashlib.sha256(ORIGINAL).hexdigest()[:12]
BASELINE = sorted(
    l.strip() for l in pathlib.Path("tests/baseline_failures.txt").read_text().splitlines()
    if l.strip() and not l.startswith("#")
)

# The glob must be expanded here: subprocess has no shell, so a literal
# "tests/test_*.py" collects nothing and the suite silently "passes".
TEST_FILES = sorted(str(p) for p in pathlib.Path("tests").glob("test_*.py"))
CMD = ["-o", "addopts=", "--maxfail=99999", "--continue-on-collection-errors",
       "--timeout=60", "--timeout-method=thread", "-q", "--tb=line", "-rf"]

FIXED_DISPATCH = 'elif "location" in pos_action or "spot" in pos_action:'
FIXED_READ = 'location = pos_action.get("location") or pos_action.get("spot") or "key"'
FIXED_ELSE = '''raise ValueError(
                    f"pos_action for {position} at step {step_idx} carries no position key "
                    f"(want one of coords/location/spot, got {sorted(pos_action.keys())})"
                )'''


def suite():
    r = subprocess.run(
        [sys.executable, "-m", "pytest", *TEST_FILES, *CMD],
        capture_output=True, text=True,
    )
    got = sorted(
        line.split()[1] for line in r.stdout.splitlines() if line.startswith("FAILED")
    )
    assert len(got) > 50, (
        f"only {len(got)} failures collected — the suite did not really run; "
        f"tail: {r.stdout[-400:]}"
    )
    new = [t for t in got if t not in BASELINE]
    fixed = [t for t in BASELINE if t not in got]
    return got, new, fixed


def report(label, got, new, fixed):
    print(f"\n=== {label} ===")
    print(f"  failures: {len(got)}  (baseline {len(BASELINE)})")
    print(f"  NEW:   {len(new)}")
    for t in new[:12]:
        print(f"      + {t}")
    print(f"  FIXED: {len(fixed)}")
    for t in fixed[:12]:
        print(f"      - {t}")
    if not new and not fixed:
        print("  -> delta EMPTY: the suite did not notice this mutation")


POISONS = [
    ("POISON A — fix fully reverted (location-only + centre fallthrough)",
     [(FIXED_DISPATCH, 'elif "location" in pos_action:'),
      (FIXED_READ, 'location = pos_action.get("location", "key")'),
      (FIXED_ELSE, 'coords = {"x": 50, "y": 25}\n                coords_already_flipped = False')]),
    ("POISON B — fix kept, but every resolved spot corrupted to a wrong real coord",
     [(FIXED_READ, FIXED_READ + '\n                location = "basketSpot" if location != "basketSpot" else "key"')]),
]

got, new, fixed = suite()
report("CONTROL — fix in place", got, new, fixed)

for label, subs in POISONS:
    s = CONV.read_text()
    for old, repl in subs:
        assert old in s, f"anchor missing for {label}: {old[:50]}"
        s = s.replace(old, repl, 1)
    CONV.write_text(s)
    got, new, fixed = suite()
    report(label, got, new, fixed)
    CONV.write_bytes(ORIGINAL)
    assert hashlib.sha256(CONV.read_bytes()).hexdigest()[:12] == SHA0

print(f"\nTREE RESTORED: sha {hashlib.sha256(CONV.read_bytes()).hexdigest()[:12]} == {SHA0}")
