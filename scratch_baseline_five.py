"""Identify the 5 tests that fail on HEAD's dispatch but pass with the fix, and
establish whether they are STABLE (the fix really fixes them) or FLAKY (run-to-run
variance, in which case the empty baseline delta is luck, not evidence).

Runs the full suite twice per condition. A test that fails in one repetition and
passes in the other is flaky regardless of condition.
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
    r = subprocess.run([sys.executable, "-m", "pytest", *TEST_FILES, *CMD],
                       capture_output=True, text=True)
    got = sorted(l.split()[1] for l in r.stdout.splitlines() if l.startswith("FAILED"))
    assert len(got) > 50, f"suite did not run: {r.stdout[-300:]}"
    return set(got)


def to_head():
    s = CONV.read_text()
    s = s.replace(FIXED_DISPATCH, 'elif "location" in pos_action:', 1)
    s = s.replace(FIXED_READ, 'location = pos_action.get("location", "key")', 1)
    s = s.replace(FIXED_ELSE,
                  'coords = {"x": 50, "y": 25}\n                coords_already_flipped = False', 1)
    CONV.write_text(s)


runs = {}
print("running FIXED x2 ...", flush=True)
runs["fixed_1"], runs["fixed_2"] = suite(), suite()
to_head()
print("running HEAD x2 ...", flush=True)
runs["head_1"], runs["head_2"] = suite(), suite()
CONV.write_bytes(ORIGINAL)
assert hashlib.sha256(CONV.read_bytes()).hexdigest()[:12] == SHA0

for k, v in runs.items():
    print(f"  {k}: {len(v)} failures")

print("\n=== WITHIN-CONDITION STABILITY (flake detection) ===")
for cond in ("fixed", "head"):
    a, b = runs[f"{cond}_1"], runs[f"{cond}_2"]
    unstable = (a ^ b)
    print(f"  {cond}: repetition 1 vs 2 differ on {len(unstable)} tests"
          f"{' -> ' + ', '.join(sorted(unstable)[:8]) if unstable else ' -> STABLE'}")

fixed_set = runs["fixed_1"] & runs["fixed_2"]
head_set = runs["head_1"] & runs["head_2"]

print("\n=== FAILS ON HEAD, PASSES WITH THE FIX (stable in both reps) ===")
for t in sorted(head_set - fixed_set):
    print(f"  {t}")
print("\n=== FAILS WITH THE FIX, PASSED ON HEAD (stable in both reps) ===")
for t in sorted(fixed_set - head_set) or ["  none"]:
    print(f"  {t}")

print("\n=== vs the committed baseline file ===")
print(f"  baseline: {len(BASELINE)}")
print(f"  HEAD stable set:  {len(head_set)}  NEW vs baseline: "
      f"{sorted(head_set - set(BASELINE))}")
print(f"  FIXED stable set: {len(fixed_set)}  NEW vs baseline: "
      f"{sorted(fixed_set - set(BASELINE))}")
print(f"\nTREE RESTORED: sha {hashlib.sha256(CONV.read_bytes()).hexdigest()[:12]} == {SHA0}")
