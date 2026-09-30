"""scripts/sim_verify: the reconstructed aggregator reproduces the committed references,
and CURRENT_REFERENCE names a real, current file. No simulation runs here (that is the
engine-equiv CI job)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.sim_verify import aggregate as A
from scripts.sim_verify import equiv as E

REFS = Path(__file__).resolve().parents[1] / "_documentation_master" / "projects" / "references"
# Every reference cut by the current aggregator shape (5cc98ee3e onward). Older files
# also carried per-arm summary stats from an earlier aggregator; their per-seed rows are
# still readable by --check (see test_old_references_are_still_checkable).
CURRENT_SHAPE = [
    "equiv_v3_reference_f600628a4_agspread.json",
    "equiv_v3_reference_1f4af0ede_loosesag_nogate.json",
    "equiv_v3_reference_09f1b0ca9_boxout.json",
    "equiv_v3_reference_f2a060488_manhelpshade.json",
    "equiv_v3_reference_32db56c77_helpshade.json",
    "equiv_v3_reference_5ea94694f_sinkescape.json",
    "equiv_v3_reference_5cc98ee3e_freeze.json",
    "equiv_v3_loose_baseline_f600628a4_agspread.json",
    "equiv_v3_loose_baseline_1f4af0ede_loosesag.json",
    "equiv_v3_loose_baseline_ef00985ce.json",
]


@pytest.mark.parametrize("name", CURRENT_SHAPE)
def test_aggregator_rebuilds_reference_byte_for_byte(name):
    raw = (REFS / name).read_text(encoding="utf-8")
    ref = json.loads(raw)
    rebuilt = A.build_reference(ref, A.build_cells(A.cells_to_per_seed(ref["cells"])))
    assert A.dumps(rebuilt) == raw


def test_old_references_are_still_checkable():
    for path in sorted(REFS.glob("equiv_v3_reference_*.json")):
        per_seed = A.cells_to_per_seed(json.loads(path.read_text())["cells"])
        assert per_seed, path.name
        for rows in per_seed.values():
            assert len(rows) == 40, path.name
            assert all(set(row) == set(A.ROW_FIELDS) for row in rows.values()), path.name


def test_pointer_names_the_current_reference():
    path = E.current_reference_path()
    assert path.is_file()
    assert path.parent == REFS
    ref = E.load_reference(path)
    assert set(ref["cells"]) == {"SEED_DEFENSES=1", "SEED_DEFENSES=0"}
    readme = (REFS / "README.md").read_text(encoding="utf-8")
    # The README marks exactly this file CURRENT in its reference table.
    assert f"**`{path.name}`**" in readme


def test_smoke_plan_covers_every_cell_and_arm():
    ref = E.load_reference(E.current_reference_path())
    tasks, full = E.plan(ref, smoke=True, seeds_spec=None, cells_spec=None, arms_spec=None)
    assert not full
    assert {(t[0], t[1]) for t in tasks} == {(1, "sim"), (1, "played"), (0, "sim"), (0, "played")}
    assert sorted({t[2] for t in tasks}) == list(E.SMOKE_SEEDS)
    full_tasks, is_full = E.plan(ref, smoke=False, seeds_spec=None, cells_spec=None, arms_spec=None)
    assert is_full and len(full_tasks) == 160


def test_loose_baseline_posture_comes_from_its_name():
    path = REFS / "equiv_v3_loose_baseline_f600628a4_agspread.json"
    assert E.footing_posture(json.loads(path.read_text()), path) == "loose"
    main = E.current_reference_path()
    assert E.footing_posture(json.loads(main.read_text()), main) == ""


def test_compare_reports_which_metric_moved():
    want = {(1, "sim"): {8000: {"fp": "a", "draws": 10, "points_per_team": 80.0, "turns": 400, "possessions": 30}}}
    got = {(1, "sim"): {8000: {"fp": "b", "draws": 12, "points_per_team": 81.5, "turns": 400, "possessions": 30}}}
    lines = E.compare(want, got, full=False, ref_cells={}, run_cells={})
    assert "SEED_DEFENSES=1 sim seed 8000: fp a -> b; draws 10 -> 12 (+2); points_per_team 80.0 -> 81.5 (+1.5)" in lines[0]
    assert not E.compare(want, want, full=False, ref_cells={}, run_cells={})


def test_loose_pointer_names_the_current_loose_baseline():
    path = E.current_loose_baseline_path()
    assert path.is_file() and path.name.startswith("equiv_v3_loose_baseline_")
    readme = (REFS / "README.md").read_text(encoding="utf-8")
    assert f"**`{path.name}`**" in readme
    ref = E.load_reference(path)
    assert E.footing_posture(ref, path) == "loose"
    tasks, full = E.plan(ref, smoke=True, seeds_spec=None, cells_spec=None, arms_spec=None,
                         smoke_seeds=E.SMOKE_LOOSE_SEEDS)
    assert not full
    assert {(t[0], t[1]) for t in tasks} == {(1, "sim"), (1, "played")}
    assert sorted({t[2] for t in tasks}) == sorted(E.SMOKE_LOOSE_SEEDS)
