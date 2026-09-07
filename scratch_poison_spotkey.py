"""Poison-test the pos_action key contract guard.

Each poison mutates the tree, runs the guard, records which tests failed and the
headline of the message, then restores the exact original bytes. Finishes by
proving the tree is byte-identical to where it started.
"""
import hashlib
import pathlib
import subprocess
import sys

CONV = pathlib.Path("BackEnd/engine/defender_placement.py")
OTHER = pathlib.Path("BackEnd/engine/attack_drive_clearance.py")
GUARD = "tests/test_pos_action_key_contract.py"

ORIGINALS = {p: p.read_bytes() for p in (CONV, OTHER)}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


BEFORE = {p: sha(p) for p in ORIGINALS}


def restore():
    for p, b in ORIGINALS.items():
        p.write_bytes(b)


def run_guard():
    r = subprocess.run(
        [sys.executable, "-m", "pytest", GUARD, "-q", "-p", "no:randomly", "--no-header",
         "-x" if False else "--tb=no", "-rf"],
        capture_output=True, text=True,
    )
    failed = sorted({
        line.split("::")[1].split()[0]
        for line in r.stdout.splitlines()
        if line.startswith("FAILED")
    })
    return failed, r.stdout


def detail(test):
    r = subprocess.run(
        [sys.executable, "-m", "pytest", f"{GUARD}::{test}", "-q", "-p", "no:randomly",
         "--no-header", "--tb=long"],
        capture_output=True, text=True,
    )
    lines = [l for l in r.stdout.splitlines() if l.startswith("E ")]
    return lines


POISONS = [
    (
        "P1 — revert the key check to location-only (the original bug)",
        CONV,
        'elif "location" in pos_action or "spot" in pos_action:',
        'elif "location" in pos_action:',
    ),
    (
        "P2 — add a SECOND, compliant dispatch in another module",
        OTHER,
        '    for pos in _OFFENSE_POSITIONS:\n        info = pos_actions.get(pos) or {}',
        '    for pos in _OFFENSE_POSITIONS:\n        info = pos_actions.get(pos) or {}\n'
        '        if "location" in info or "spot" in info:\n            pass',
    ),
    (
        "P3 — replace the strict raise with the court-centre substitution",
        CONV,
        'if _strict_pos_action_keys():\n                    raise ValueError(detail)',
        'if False:\n                    coords = {"x": 50, "y": 25}',
    ),
    (
        "P5 — keep the raise, but make the SOFT path invent a coordinate",
        CONV,
        '                step_mapping.pop()\n                continue',
        '                coords = {"x": 50, "y": 25}\n                coords_already_flipped = False',
    ),
    (
        "P6 — flip the production default to strict (would crash live games)",
        CONV,
        'return "PYTEST_CURRENT_TEST" in os.environ',
        'return True',
    ),
    (
        "P4 — a location-only dispatch in a THIRD module (new converter)",
        OTHER,
        '    for pos in _OFFENSE_POSITIONS:\n        info = pos_actions.get(pos) or {}',
        '    for pos in _OFFENSE_POSITIONS:\n        info = pos_actions.get(pos) or {}\n'
        '        if "location" in info:\n            pass',
    ),
]

print("=== BASELINE (unpoisoned) ===")
failed, _ = run_guard()
print(f"  failures: {failed or 'none — 7 passed'}")
print()

for name, path, old, new in POISONS:
    src = path.read_text()
    assert old in src, f"poison anchor not found for {name}"
    path.write_text(src.replace(old, new, 1))
    failed, _ = run_guard()
    print(f"=== {name} ===")
    print(f"  tests that FAILED: {failed or 'NONE — POISON SURVIVED, GUARD IS INEFFECTIVE'}")
    if failed:
        for line in detail(failed[0])[:6]:
            print(f"    {line}")
    restore()
    print()

print("=== TREE RESTORED ===")
after = {p: sha(p) for p in ORIGINALS}
for p in ORIGINALS:
    ok = BEFORE[p] == after[p]
    print(f"  {p}  {BEFORE[p]} -> {after[p]}  {'IDENTICAL' if ok else 'DIFFERS'}")
failed, _ = run_guard()
print(f"  guard on restored tree: {failed or 'clean, 7 passed'}")
