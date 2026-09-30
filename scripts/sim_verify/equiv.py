"""Engine regression check (equiv-v3) against the CURRENT reference.

  python -m scripts.sim_verify.equiv --check            # full: every cell, arm, seed (~2 min on 14 cores)
  python -m scripts.sim_verify.equiv --check --smoke    # CI subset (SMOKE_SEEDS on all four cells)
  python -m scripts.sim_verify.equiv --check --seeds 8000-8009 --cells 1 --arms sim
  python -m scripts.sim_verify.equiv --check --reference <file>   # e.g. verify a kill switch
  python -m scripts.sim_verify.equiv --recut --reason "..."       # DELIBERATE re-cut, see CLAUDE.md

The current reference is the file named in scripts/sim_verify/CURRENT_REFERENCE. Each
seed runs in its own process (scripts/sim_verify/worker.py) with PYTHONHASHSEED=0 on
mongomock, so every row is independent of every other and of the job count.

Exit codes: 0 match, 1 fingerprint drift, 2 a worker failed (crash, emitter failure,
or a game error), 64 bad usage.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from scripts.sim_verify import aggregate as A

REPO_ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
POINTER = HERE / "CURRENT_REFERENCE"
REFERENCES_DIR = REPO_ROOT / "_documentation_master" / "projects" / "references"

# CI smoke: these seeds on all four cells (2 footings x 2 arms) = 16 games.
SMOKE_SEEDS = (8000, 8001, 8002, 8003)

# Harness knobs the worker reads. They define the footing, so the runner sets them and
# never inherits a stray value from the caller's shell.
FOOTING_ENV = (
    "ALIGN_RNG", "EQUIV_POSTURE_CENSUS", "SCREEN_CENSUS", "MATCHUP_SITE_PROBE",
    "EQUIV_MAN_POSTURE", "SEED_PLAYS", "SEED_DEFENSES", "PROBE_GAMES", "SEED_BASE",
    "OUT", "ARM", "COND",
)
REF_NAME_RE = re.compile(r"^(equiv_v3_(?:reference|loose_baseline))_([0-9a-f]{7,12})(?:_(.*))?\.json$")


# ---------------------------------------------------------------------------
# reference selection
# ---------------------------------------------------------------------------

def _rel(path: Path) -> str:
    """Repo-relative when inside the repo (the pointer's normal form), else absolute."""
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(Path(path).resolve())


def current_reference_path() -> Path:
    for line in POINTER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return (REPO_ROOT / line).resolve()
    raise SystemExit(f"{POINTER} names no reference")


def load_reference(path: Path) -> dict[str, Any]:
    ref = json.loads(path.read_text(encoding="utf-8"))
    if "cells" not in ref or not all(k.startswith("SEED_DEFENSES=") for k in ref["cells"]):
        raise SystemExit(f"{path.name}: not an equiv-v3 reference with SEED_DEFENSES cells")
    return ref


def footing_posture(reference: dict[str, Any], path: Path) -> str:
    """The man posture a reference was cut at. The loose baselines do not say so in their
    footing text; the README and the file name do (equiv_v3_loose_baseline_* =
    EQUIV_MAN_POSTURE=loose, SEED_DEFENSES=1)."""
    if path.name.startswith("equiv_v3_loose_baseline_"):
        return "loose"
    match = re.search(r"EQUIV_MAN_POSTURE=(\w+)", str(reference.get("footing") or ""))
    return match.group(1) if match else ""


# ---------------------------------------------------------------------------
# running the worker
# ---------------------------------------------------------------------------

def worker_env(seed_defenses: int, arm: str, seed: int, out: Path, posture: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in FOOTING_ENV}
    env.update({
        "PYTHONHASHSEED": "0",
        "GOB_DB_MODE": "mongomock",
        "ENVIRONMENT": "test",
        "MONGO_DB_NAME": "gob-test",
        "SEED_PLAYS": "1",
        "SEED_DEFENSES": str(seed_defenses),
        "ARM": arm,
        "COND": "after",
        "SEED_BASE": str(seed),
        "PROBE_GAMES": "1",
        "OUT": str(out),
    })
    if posture:
        env["EQUIV_MAN_POSTURE"] = posture
    return env


def engine_flag_overrides() -> dict[str, str]:
    return {k: v for k, v in sorted(os.environ.items()) if k.startswith("GOB_") and k != "GOB_DB_MODE"}


def run_one(task: tuple[int, str, int], workdir: Path, posture: str) -> tuple[tuple[int, str, int], dict | None, str | None]:
    seed_defenses, arm, seed = task
    out = workdir / f"d{seed_defenses}_{arm}_{seed}.json"
    log = workdir / f"d{seed_defenses}_{arm}_{seed}.log"
    with open(log, "wb") as fh:
        proc = subprocess.run(
            [sys.executable, "-m", "scripts.sim_verify.worker"],
            cwd=str(REPO_ROOT), env=worker_env(seed_defenses, arm, seed, out, posture),
            stdout=fh, stderr=subprocess.STDOUT,
        )
    if proc.returncode != 0:
        tail = log.read_text(errors="replace").strip().splitlines()[-12:]
        why = "emitter failure" if proc.returncode == 3 else f"exit {proc.returncode}"
        return task, None, f"{why}:\n      " + "\n      ".join(tail)
    rows = json.loads(out.read_text())["rows"][f"after_{arm}"]
    row = rows[0]
    if row.get("err"):
        return task, None, f"game error: {row['err']}"
    return task, A.reference_row(row), None


def run_matrix(tasks: list[tuple[int, str, int]], jobs: int, posture: str):
    results: dict[tuple[int, str], dict[int, dict]] = {}
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="equiv-") as tmp:
        workdir = Path(tmp)
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            for (sd, arm, seed), row, err in pool.map(lambda t: run_one(t, workdir, posture), tasks):
                if err:
                    failures.append(f"{A.cell_name(sd)} {arm} seed {seed}: {err}")
                else:
                    results.setdefault((sd, arm), {})[seed] = row
    return results, failures


# ---------------------------------------------------------------------------
# comparison
# ---------------------------------------------------------------------------

def _fmt_delta(a, b) -> str:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        d = b - a
        d = round(d, 3) if isinstance(d, float) else d
        return f"{a} -> {b} ({'+' if d > 0 else ''}{d})"
    return f"{a} -> {b}"


def compare(expected: dict, actual: dict, *, full: bool, ref_cells: dict, run_cells: dict) -> list[str]:
    """Readable drift lines; empty when every compared row matches."""
    lines: list[str] = []
    for key in sorted(actual, key=lambda k: (-k[0], A.ARM_ORDER.index(k[1]))):
        sd, arm = key
        want = expected.get(key, {})
        got = actual[key]
        moved = []
        for seed in sorted(got):
            if seed not in want:
                lines.append(f"  {A.cell_name(sd)} {arm} seed {seed}: not in the reference")
                continue
            diffs = [f"{f} {_fmt_delta(want[seed][f], got[seed][f])}"
                     for f in A.ROW_FIELDS if want[seed][f] != got[seed][f]]
            if diffs:
                moved.append(seed)
                lines.append(f"  {A.cell_name(sd)} {arm} seed {seed}: " + "; ".join(diffs))
        if moved:
            seeds = [s for s in got if s in want]
            for field in ("points_per_team", "draws", "turns", "possessions"):
                ref_mean = sum(want[s][field] for s in seeds) / len(seeds)
                run_mean = sum(got[s][field] for s in seeds) / len(seeds)
                if ref_mean != run_mean:
                    lines.append(f"    {A.cell_name(sd)} {arm} mean {field} over {len(seeds)} seeds: "
                                 f"{ref_mean:.3f} -> {run_mean:.3f} ({run_mean - ref_mean:+.3f})")
            lines.append(f"    {A.cell_name(sd)} {arm}: {len(moved)}/{len(seeds)} seeds moved")
    if full:
        for name, cell in run_cells.items():
            want_gap = (ref_cells.get(name) or {}).get("arm_gap_sim_minus_played")
            got_gap = cell.get("arm_gap_sim_minus_played")
            if want_gap and got_gap and (want_gap["mean"], want_gap["ci95"]) != (got_gap["mean"], got_gap["ci95"]):
                lines.append(f"  {name} arm gap (sim - played): mean {_fmt_delta(want_gap['mean'], got_gap['mean'])}, "
                             f"ci95 {_fmt_delta(want_gap['ci95'], got_gap['ci95'])}")
    return lines


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def plan(reference: dict, *, smoke: bool, seeds_spec: str | None, cells_spec: str | None,
         arms_spec: str | None) -> tuple[list[tuple[int, str, int]], bool]:
    per_seed = A.cells_to_per_seed(reference["cells"])
    ref_seeds = A.seeds_in(per_seed)
    if smoke:
        seeds = list(SMOKE_SEEDS)
    elif seeds_spec:
        seeds = A.parse_seed_spec(seeds_spec)
    else:
        seeds = ref_seeds
    cells = sorted({k[0] for k in per_seed}, reverse=True)
    if cells_spec:
        cells = [c for c in cells if str(c) in {s.strip() for s in cells_spec.split(",")}]
    arms = [a for a in A.ARM_ORDER if not arms_spec or a in {s.strip() for s in arms_spec.split(",")}]
    tasks = [(sd, arm, seed) for sd in cells for arm in arms if (sd, arm) in per_seed for seed in seeds]
    full = (not smoke and not seeds_spec and not cells_spec and not arms_spec)
    return tasks, full


def cmd_check(args) -> int:
    ref_path = Path(args.reference).resolve() if args.reference else current_reference_path()
    reference = load_reference(ref_path)
    posture = args.posture if args.posture is not None else footing_posture(reference, ref_path)
    tasks, full = plan(reference, smoke=args.smoke, seeds_spec=args.seeds,
                       cells_spec=args.cells, arms_spec=args.arms)
    if not tasks:
        print("nothing to run (check --seeds / --cells / --arms)")
        return 64
    seeds = sorted({t[2] for t in tasks})
    print(f"equiv-v3 check against {_rel(ref_path)} (tree {reference.get('sha')})")
    print(f"  {'full' if full else 'subset'}: {len(tasks)} games = cells "
          f"{sorted({A.cell_name(t[0]) for t in tasks}, reverse=True)} x arms "
          f"{[a for a in A.ARM_ORDER if any(t[1] == a for t in tasks)]} x seeds {A.format_seeds(seeds)}"
          f"{' (posture ' + posture + ')' if posture else ''}, {args.jobs} jobs")
    overrides = engine_flag_overrides()
    if overrides:
        print(f"  engine flag overrides from the environment: {overrides}")
    started = time.perf_counter()
    actual, failures = run_matrix(tasks, args.jobs, posture)
    elapsed = time.perf_counter() - started
    if failures:
        print(f"WORKER FAILURE ({len(failures)}) after {elapsed:.1f}s:")
        for line in failures:
            print("  " + line)
        return 2
    expected = A.cells_to_per_seed(reference["cells"])
    run_cells = A.build_cells(actual)
    drift = compare(expected, actual, full=full, ref_cells=reference["cells"], run_cells=run_cells)
    if args.save_run:
        Path(args.save_run).write_text(A.dumps(A.build_reference(reference, run_cells)))
    if drift:
        print(f"FINGERPRINT DRIFT against {ref_path.name} ({elapsed:.1f}s):")
        for line in drift:
            print(line)
        print("If this change is intended, re-cut deliberately (CLAUDE.md, 'Engine regression check').")
        return 1
    print(f"MATCH: {len(tasks)}/{len(tasks)} games identical on fp, draws, points, turns, possessions"
          f"{' and both arm gaps' if full else ''} ({elapsed:.1f}s)")
    return 0


def _git(*argv: str) -> str:
    return subprocess.run(["git", *argv], cwd=str(REPO_ROOT), check=True,
                          capture_output=True, text=True).stdout.strip()


def cmd_recut(args) -> int:
    if os.environ.get("CI"):
        print("refusing to re-cut in CI: a re-cut is a deliberate, reviewed local step")
        return 64
    if not args.reason or not args.reason.strip():
        print("--reason is required (it becomes the reference note and the commit message)")
        return 64
    dirty = _git("status", "--porcelain", "--", "BackEnd", "scripts/sim_verify", "tests/roster_fixtures.py")
    if dirty:
        print("refusing to re-cut: engine/harness files have uncommitted changes, so the "
              "reference would not describe a commit:\n" + dirty)
        return 64
    old_path = Path(args.reference).resolve() if args.reference else current_reference_path()
    old = load_reference(old_path)
    match = REF_NAME_RE.match(old_path.name)
    if not match:
        print(f"cannot derive a new name from {old_path.name}")
        return 64
    prefix = match.group(1)
    sha = _git("rev-parse", "--short=9", "HEAD")
    slug = re.sub(r"[^a-z0-9]+", "", (args.slug or "recut").lower()) or "recut"
    new_path = REFERENCES_DIR / f"{prefix}_{sha}_{slug}.json"
    if new_path.exists():
        print(f"{new_path.name} already exists")
        return 64
    posture = args.posture if args.posture is not None else footing_posture(old, old_path)
    tasks, _ = plan(old, smoke=False, seeds_spec=None, cells_spec=None, arms_spec=None)
    passes = []
    for label in ("first pass", "second pass (double re-baseline)"):
        print(f"re-cut {label}: {len(tasks)} games, {args.jobs} jobs ...")
        actual, failures = run_matrix(tasks, args.jobs, posture)
        if failures:
            print("WORKER FAILURE, no reference written:")
            for line in failures:
                print("  " + line)
            return 2
        passes.append(A.build_cells(actual))
    if passes[0] != passes[1]:
        print("the two passes differ: the engine is not deterministic here, no reference written")
        return 2
    header = {"sha": sha, "note": args.reason.strip(), "footing": old["footing"], "flags": old["flags"]}
    new_path.write_text(A.dumps(A.build_reference(header, passes[0])))
    moved = sum(1 for key, rows in A.cells_to_per_seed(passes[0]).items()
                for seed, row in rows.items()
                if A.cells_to_per_seed(old["cells"]).get(key, {}).get(seed) != row)
    if old_path == current_reference_path():
        POINTER.write_text(_rel(new_path) + "\n")
        print(f"pointer updated: {_rel(POINTER)} -> {new_path.name}")
    print(f"wrote {_rel(new_path)} ({moved} of {len(tasks)} rows differ from {old_path.name})")
    print("next: update 'flags' in the new file if a flag flipped, move the old file to 'Superseded' in")
    print(f"      {_rel(REFERENCES_DIR / 'README.md')} with the switch that reproduces it, then commit:")
    print(f'      git commit -m "equiv re-cut: {args.reason.strip()}"')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.sim_verify.equiv", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="compare the engine against the reference")
    mode.add_argument("--recut", action="store_true", help="write a new reference (deliberate; see CLAUDE.md)")
    parser.add_argument("--smoke", action="store_true", help=f"CI subset: seeds {SMOKE_SEEDS} on every cell and arm")
    parser.add_argument("--seeds", help="seed spec, e.g. 8000-8039 or 8000,8005")
    parser.add_argument("--cells", help="SEED_DEFENSES values, e.g. 1 or 1,0")
    parser.add_argument("--arms", help="sim, played or sim,played")
    parser.add_argument("--reference", help="reference file (default: the one CURRENT_REFERENCE names)")
    parser.add_argument("--posture", help="override EQUIV_MAN_POSTURE (default: from the reference; '' for none)")
    parser.add_argument("--jobs", type=int, default=max(1, os.cpu_count() or 1), help="parallel games")
    parser.add_argument("--save-run", help="also write this run as a reference-shaped JSON file")
    parser.add_argument("--reason", help="--recut: why the engine moved (reference note + commit message)")
    parser.add_argument("--slug", help="--recut: short name suffix for the new file, e.g. boxout")
    args = parser.parse_args(argv)
    if args.recut:
        return cmd_recut(args)
    return cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
