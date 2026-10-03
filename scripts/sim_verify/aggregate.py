"""Build equiv-v3 reference files from worker rows.

Reconstructed 2026-09-30. The original aggregator (/tmp/refcut_equivv3.py) was never
committed. This one is rebuilt from the reference files themselves and
_documentation_master/projects/references/README.md, and is proven against them:
feeding a committed reference's own per-seed rows and header back through
``build_reference`` + ``dumps`` reproduces the file byte for byte (see
tests/test_sim_verify_aggregate.py).

Shape (every reference from ``..._merged`` onward):

  {"sha", "note", "footing", "flags",
   "cells": {"SEED_DEFENSES=1": {"sim": {"per_seed": {"8000": ROW, ...}},
                                 "played": {"per_seed": {...}},
                                 "arm_gap_sim_minus_played": GAP},
             "SEED_DEFENSES=0": {...}}}

  ROW = {"fp", "draws", "points_per_team", "turns", "possessions"}   (from the worker)
  GAP = {"mean", "ci95", "n", "note"}: paired per-seed sim - played points_per_team,
        mean and 1.96 x SEM (sample SD), both rounded to 3 places.

Assumptions, from the files rather than the lost script:
  * cells are ordered SEED_DEFENSES=1 before SEED_DEFENSES=0, arms sim before played;
  * per_seed keys are the seed as a string, ascending;
  * json.dumps(indent=1), ASCII-escaped, no trailing newline;
  * a cell with only one arm has no arm gap (the sim-only references).
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

ROW_FIELDS = ("fp", "draws", "points_per_team", "turns", "possessions")
ARM_ORDER = ("sim", "played")
GAP_NOTE = "paired per-seed difference, not quadrature"
HEADER_KEYS = ("sha", "note", "footing", "flags")


def cell_name(seed_defenses: int) -> str:
    return f"SEED_DEFENSES={int(seed_defenses)}"


def seed_defenses_of(cell: str) -> int:
    return int(str(cell).split("=", 1)[1])


def reference_row(worker_row: Mapping[str, Any]) -> dict[str, Any]:
    """The five fields a reference stores for one seed."""
    return {field: worker_row[field] for field in ROW_FIELDS}


def arm_gap(sim: Mapping[str, Mapping[str, Any]], played: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    seeds = [s for s in sim if s in played]
    diffs = [sim[s]["points_per_team"] - played[s]["points_per_team"] for s in seeds]
    n = len(diffs)
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / (n - 1) if n > 1 else 0.0
    ci95 = 1.96 * (var ** 0.5) / (n ** 0.5)
    return {"mean": round(mean, 3), "ci95": round(ci95, 3), "n": n, "note": GAP_NOTE}


def build_cells(per_seed: Mapping[tuple[int, str], Mapping[int, Mapping[str, Any]]]) -> dict[str, Any]:
    """``per_seed[(seed_defenses, arm)][seed] = reference row`` -> the ``cells`` block."""
    cells: dict[str, Any] = {}
    for seed_defenses in sorted({key[0] for key in per_seed}, reverse=True):
        cell: dict[str, Any] = {}
        for arm in ARM_ORDER:
            rows = per_seed.get((seed_defenses, arm))
            if rows is None:
                continue
            cell[arm] = {"per_seed": {str(seed): dict(rows[seed]) for seed in sorted(rows)}}
        if "sim" in cell and "played" in cell:
            cell["arm_gap_sim_minus_played"] = arm_gap(cell["sim"]["per_seed"], cell["played"]["per_seed"])
        cells[cell_name(seed_defenses)] = cell
    return cells


def cells_to_per_seed(cells: Mapping[str, Any]) -> dict[tuple[int, str], dict[int, dict[str, Any]]]:
    """Inverse of ``build_cells`` for a loaded reference (dict or list per_seed)."""
    out: dict[tuple[int, str], dict[int, dict[str, Any]]] = {}
    for name, cell in cells.items():
        for arm in ARM_ORDER:
            if arm not in cell:
                continue
            raw = cell[arm]["per_seed"]
            if isinstance(raw, list):
                rows = {int(r["seed"]): reference_row(r) for r in raw}
            else:
                rows = {int(seed): dict(row) for seed, row in raw.items()}
            out[(seed_defenses_of(name), arm)] = rows
    return out


def build_reference(header: Mapping[str, Any], cells: Mapping[str, Any]) -> dict[str, Any]:
    ref = {key: header[key] for key in HEADER_KEYS if key in header}
    ref["cells"] = dict(cells)
    return ref


def dumps(reference: Mapping[str, Any]) -> str:
    return json.dumps(reference, indent=1)


def seeds_in(per_seed: Mapping[tuple[int, str], Mapping[int, Any]]) -> list[int]:
    seeds: set[int] = set()
    for rows in per_seed.values():
        seeds.update(rows)
    return sorted(seeds)


def parse_seed_spec(spec: str) -> list[int]:
    """'8000-8039' or '8000,8003,8010-8012'."""
    seeds: list[int] = []
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            seeds.extend(range(int(lo), int(hi) + 1))
        else:
            seeds.append(int(part))
    return sorted(set(seeds))


def format_seeds(seeds: Iterable[int]) -> str:
    seeds = sorted(seeds)
    if seeds and seeds == list(range(seeds[0], seeds[-1] + 1)):
        return f"{seeds[0]}-{seeds[-1]}" if len(seeds) > 1 else str(seeds[0])
    return ",".join(str(s) for s in seeds)
