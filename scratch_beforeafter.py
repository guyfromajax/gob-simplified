"""ACCEPTANCE C + F: full gameplay distribution BEFORE and AFTER the spot-key fix,
measured on the equiv-v3 harness with both gates armed.

Reverts the fix byte-exactly to measure BEFORE, restores, measures AFTER, and proves
the tree is byte-identical to where it started. Both harness runs print their own
GATE 1 (independence) and GATE 2 (FT-honour parity) results; a run that fails either
prints no comparison, so a silently-void arm cannot reach this report.
"""
import hashlib
import os
import pathlib
import subprocess
import sys

CONV = pathlib.Path("BackEnd/engine/defender_placement.py")
ORIGINAL = CONV.read_bytes()
SHA0 = hashlib.sha256(ORIGINAL).hexdigest()[:12]

FIXED_DISPATCH = 'elif "location" in pos_action or "spot" in pos_action:'
PREFIX_DISPATCH = 'elif "location" in pos_action:'

FIXED_READ = 'location = pos_action.get("location") or pos_action.get("spot") or "key"'
PREFIX_READ = 'location = pos_action.get("location", "key")'

FIXED_ELSE = '''raise ValueError(
                    f"pos_action for {position} at step {step_idx} carries no position key "
                    f"(want one of coords/location/spot, got {sorted(pos_action.keys())})"
                )'''
PREFIX_ELSE = '''coords = {"x": 50, "y": 25}
                coords_already_flipped = False'''

GAMES = os.environ.get("GAMES", "20")


def harness(label):
    print(f"\n{'#'*78}\n#  {label}\n{'#'*78}", flush=True)
    r = subprocess.run(
        [sys.executable, "scratch_harness.py"],
        env=dict(os.environ, GAMES=GAMES),
        capture_output=True, text=True,
    )
    print(r.stdout)
    if r.returncode != 0:
        print("STDERR:", r.stderr[-2000:])
    return r.stdout


def to_prefix():
    s = CONV.read_text()
    assert FIXED_DISPATCH in s and FIXED_READ in s and FIXED_ELSE in s, "fix anchors missing"
    s = s.replace(FIXED_DISPATCH, PREFIX_DISPATCH, 1)
    s = s.replace(FIXED_READ, PREFIX_READ, 1)
    s = s.replace(FIXED_ELSE, PREFIX_ELSE, 1)
    CONV.write_text(s)


def restore():
    CONV.write_bytes(ORIGINAL)
    assert hashlib.sha256(CONV.read_bytes()).hexdigest()[:12] == SHA0


to_prefix()
print(f"reverted to pre-fix (sha {hashlib.sha256(CONV.read_bytes()).hexdigest()[:12]})", flush=True)
before = harness(f"BEFORE — location-only dispatch, centre-court fallthrough  (n={GAMES} games/arm)")

restore()
print(f"restored to fixed (sha {hashlib.sha256(CONV.read_bytes()).hexdigest()[:12]} == {SHA0})", flush=True)
after = harness(f"AFTER — location-or-spot dispatch, fallthrough raises  (n={GAMES} games/arm)")

pathlib.Path("/tmp/ba_before.txt").write_text(before)
pathlib.Path("/tmp/ba_after.txt").write_text(after)
print(f"\nTREE RESTORED: {CONV} sha {hashlib.sha256(CONV.read_bytes()).hexdigest()[:12]} == {SHA0}")
