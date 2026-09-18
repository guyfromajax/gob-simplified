#!/usr/bin/env python3
"""Desktop-migration ratchets — freeze today's pile so it can only shrink.

Two large refactors are coming and feature work continues in parallel. Without
a gate, new code keeps adding to the pile and the migration never finishes.

  Gate A (WS-1): no NEW direct imports of collection handles from BackEnd/db.py.
                 Use the persistence adapter, not a direct db import.

  Gate B (WS-3): no NEW URL-state reads in FrontEnd/static (URLSearchParams,
                 location.search, .searchParams).
                 Use FranchiseContext, not location.search.

Allowlist: scripts/ci/migration_gates_allowlist.json
  - One entry per file, with that file's current match count.
  - FAIL if a file not on the allowlist matches, or an allowlisted count goes UP.
  - PASS if a count goes DOWN — print a note to update the allowlist so the
    ratchet tightens. When a file hits 0, remove it from the allowlist.

Regenerate / tighten the allowlist (after a real reduction, on an unmodified
checkout of the files you just cleaned):

    python scripts/ci/check_migration_gates.py --write-allowlist

Do not use --write-allowlist to paper over a new import or a new URL read.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST_PATH = Path(__file__).resolve().parent / "migration_gates_allowlist.json"

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "tests",
        "scripts",
        "_documentation_master",
        "reports",
    }
)
SKIP_FILE_PREFIXES = ("scratch_",)
SKIP_FILE_NAMES = frozenset({"BackEnd/db.py"})
TEST_FILE_RE = re.compile(r"(^|/)(test_[^/]+|[^/]+_test)\.py$")

GATE_A_HINT = "use the persistence adapter, not a direct db import"
GATE_B_HINT = "use FranchiseContext, not location.search"

GATE_B_PATTERNS = (
    ("URLSearchParams", re.compile(r"URLSearchParams")),
    ("location.search", re.compile(r"location\.search")),
    (".searchParams", re.compile(r"\.searchParams")),
)
GATE_B_SUFFIXES = frozenset({".js", ".html", ".htm", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"})


@dataclass
class Hit:
    path: str
    line: int
    pattern: str


@dataclass
class Scan:
    counts: dict[str, int] = field(default_factory=dict)
    hits: dict[str, list[Hit]] = field(default_factory=dict)

    def add(self, hit: Hit) -> None:
        self.hits.setdefault(hit.path, []).append(hit)
        self.counts[hit.path] = self.counts.get(hit.path, 0) + 1


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _walk_files(root: Path, suffixes: frozenset[str]):
    """Walk root, pruning skip-dirs so we never descend into node_modules / venv."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
        current = Path(dirpath)
        for name in filenames:
            path = current / name
            if path.suffix in suffixes:
                yield path


def _skip_gate_a_file(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    if rel in SKIP_FILE_NAMES:
        return True
    if name.startswith(SKIP_FILE_PREFIXES):
        return True
    if TEST_FILE_RE.search(rel):
        return True
    return False


def _resolve_from_import(path: Path, root: Path, module: str | None, level: int) -> str | None:
    rel = path.relative_to(root)
    pkg = list(rel.with_suffix("").parts[:-1])
    if level == 0:
        return module or ""
    if level > len(pkg):
        return None
    base = pkg[: len(pkg) - (level - 1)]
    if module:
        base += module.split(".")
    return ".".join(base)


def scan_gate_a(root: Path) -> Scan:
    """Count import statements that resolve to BackEnd.db (or `from BackEnd import db`)."""
    scan = Scan()
    for path in _walk_files(root, frozenset({".py"})):
        rel = _rel(path, root)
        if _skip_gate_a_file(rel):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=rel)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                resolved = _resolve_from_import(path, root, node.module, node.level)
                names = [alias.name for alias in node.names]
                if resolved == "BackEnd.db":
                    if node.level == 0:
                        pattern = "from BackEnd.db import"
                    elif node.level == 1:
                        pattern = "from .db import"
                    elif node.level == 2:
                        pattern = "from ..db import"
                    else:
                        pattern = f"from {'.' * node.level}db import"
                    scan.add(Hit(rel, node.lineno, pattern))
                elif resolved == "BackEnd" and "db" in names:
                    scan.add(Hit(rel, node.lineno, "from BackEnd import db"))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "BackEnd.db" or alias.name.startswith("BackEnd.db."):
                        scan.add(Hit(rel, alias.lineno if hasattr(alias, "lineno") else node.lineno, "import BackEnd.db"))
    return scan


def _strip_line_comment(line: str, suffix: str) -> str:
    if suffix in {".html", ".htm"}:
        cut = line.find("<!--")
        if cut != -1:
            line = line[:cut]
    cut = line.find("//")
    if cut != -1:
        line = line[:cut]
    return line


def scan_gate_b(root: Path) -> Scan:
    """Count lines under FrontEnd/static that mention a URL-state pattern."""
    scan = Scan()
    static = root / "FrontEnd" / "static"
    if not static.is_dir():
        return scan
    for path in _walk_files(static, GATE_B_SUFFIXES):
        rel = _rel(path, root)
        for lineno, raw in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            code = _strip_line_comment(raw, path.suffix)
            matched = [name for name, pat in GATE_B_PATTERNS if pat.search(code)]
            if matched:
                scan.add(Hit(rel, lineno, " / ".join(matched)))
    return scan


def load_allowlist(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "gate_a": {k: int(v) for k, v in data.get("gate_a", {}).get("files", {}).items()},
        "gate_b": {k: int(v) for k, v in data.get("gate_b", {}).get("files", {}).items()},
    }


def write_allowlist(path: Path, gate_a: Scan, gate_b: Scan) -> None:
    payload = {
        "gate_a": {
            "description": (
                "WS-1: import statements that resolve to BackEnd.db. "
                "Count may fall, never rise."
            ),
            "files": {k: gate_a.counts[k] for k in sorted(gate_a.counts)},
        },
        "gate_b": {
            "description": (
                "WS-3: FrontEnd/static lines matching URLSearchParams, "
                "location.search, or .searchParams. Count may fall, never rise."
            ),
            "files": {k: gate_b.counts[k] for k in sorted(gate_b.counts)},
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def evaluate(name: str, hint: str, found: Scan, allowed: dict[str, int]) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    notes: list[str] = []
    for path, count in sorted(found.counts.items()):
        baseline = allowed.get(path)
        if baseline is None:
            hit = found.hits[path][0]
            failures.append(
                f"{name} FAILED: {path}\n"
                f"  pattern: {hit.pattern}\n"
                f"  allowlisted: 0  found: {count}\n"
                f"  this file is not on the allowlist — {hint}"
            )
        elif count > baseline:
            hit = found.hits[path][-1]
            failures.append(
                f"{name} FAILED: {path}\n"
                f"  pattern: {hit.pattern}\n"
                f"  allowlisted: {baseline}  found: {count}\n"
                f"  count went up — {hint}"
            )
        elif count < baseline:
            notes.append(
                f"{name} {path}: count fell {baseline} → {count}. "
                f"Update {ALLOWLIST_PATH.relative_to(ROOT).as_posix()} so the ratchet tightens."
            )
    for path, baseline in sorted(allowed.items()):
        if path not in found.counts:
            notes.append(
                f"{name} {path}: now clean (0, was {baseline}). "
                f"Remove it from {ALLOWLIST_PATH.relative_to(ROOT).as_posix()}."
            )
    return failures, notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root (default: inferred)")
    parser.add_argument(
        "--write-allowlist",
        action="store_true",
        help="Rewrite the allowlist from the current tree (tighten after a real reduction)",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=ALLOWLIST_PATH,
        help="Allowlist JSON path",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    allowlist_path = args.allowlist if args.allowlist.is_absolute() else (root / args.allowlist)

    gate_a = scan_gate_a(root)
    gate_b = scan_gate_b(root)

    if args.write_allowlist:
        write_allowlist(allowlist_path, gate_a, gate_b)
        print(
            f"Wrote {allowlist_path}\n"
            f"  Gate A: {len(gate_a.counts)} files, {sum(gate_a.counts.values())} imports\n"
            f"  Gate B: {len(gate_b.counts)} files, {sum(gate_b.counts.values())} lines"
        )
        return 0

    if not allowlist_path.is_file():
        print(f"Allowlist missing: {allowlist_path}", file=sys.stderr)
        print("Run with --write-allowlist to generate it from the current tree.", file=sys.stderr)
        return 2

    allowed = load_allowlist(allowlist_path)
    failures: list[str] = []
    notes: list[str] = []
    for name, hint, scan, bucket in (
        ("Gate A", GATE_A_HINT, gate_a, "gate_a"),
        ("Gate B", GATE_B_HINT, gate_b, "gate_b"),
    ):
        f, n = evaluate(name, hint, scan, allowed[bucket])
        failures.extend(f)
        notes.extend(n)

    for note in notes:
        print(f"NOTE: {note}")

    if failures:
        print()
        for item in failures:
            print(item)
            print()
        print(
            f"Migration gates failed: {len(failures)} violation(s).\n"
            "These gates freeze the desktop-migration pile at today's size so it "
            "only ever shrinks. Do not add a new BackEnd.db import or a new "
            "URLSearchParams / location.search / .searchParams read. If you just "
            "removed sites, re-run with --write-allowlist to tighten the ratchet."
        )
        return 1

    print(
        f"Migration gates passed.\n"
        f"  Gate A: {sum(gate_a.counts.values())} imports in {len(gate_a.counts)} files\n"
        f"  Gate B: {sum(gate_b.counts.values())} lines in {len(gate_b.counts)} files"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
