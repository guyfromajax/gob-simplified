"""The 19 __file__-relative path sites must go through bundle_root / bundle_path."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "BackEnd"
ALLOWED = {
    BACKEND / "runtime_paths.py",
}


def test_backend_non_test_modules_do_not_use_file_for_paths():
    offenders: list[str] = []
    for path in BACKEND.rglob("*.py"):
        if "tests" in path.parts:
            continue
        if path.resolve() in {p.resolve() for p in ALLOWED}:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "__file__":
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert offenders == [], "route these through bundle_path / bundle_root:\n" + "\n".join(offenders)
