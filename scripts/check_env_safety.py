#!/usr/bin/env python3
"""Reject unsafe environment and Mongo access patterns outside reviewed boundaries."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = ("BackEnd", "scripts", ".github")
SOURCE_SUFFIXES = frozenset({".py", ".sh", ".yml", ".yaml"})
SKIP_PATHS = frozenset({"scripts/check_env_safety.py"})

# Every exception is path- and rule-specific. Adding one is a security decision.
RULE_EXCEPTIONS: dict[str, frozenset[str]] = {
    "dotenv_loader": frozenset(
        {
            "BackEnd/env_config.py",
            "BackEnd/script_db.py",
        }
    ),
    "mongo_client": frozenset({"BackEnd/db.py", "BackEnd/script_db.py"}),
    # These boundaries inspect and reject file-supplied authorization; they never
    # grant it. Tests cover that fail-closed behavior.
    "file_db_authorization": frozenset(
        {"BackEnd/env_config.py", "BackEnd/script_db.py"}
    ),
    # One reviewed external script-secret boundary; it rejects repository paths and
    # permissions other than 0600.
    "manual_dotenv_parser": frozenset({"scripts/script_secrets.py"}),
}

_PRODUCTION_URI = re.compile(r"mongodb(?:\+srv)?://[^\s'\"]+/gob(?:[?\s'\"]|$)", re.I)


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    rule: str
    detail: str


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _python_violations(path: str, text: str) -> list[Violation]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    found: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in {"load_dotenv", "dotenv_values", "find_dotenv"}:
                found.append(Violation(path, node.lineno, "dotenv_loader", name))
            if name == "MongoClient":
                found.append(Violation(path, node.lineno, "mongo_client", name))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names]
            if "MongoClient" in names:
                found.append(Violation(path, node.lineno, "mongo_client", "direct import"))
    return found


def _text_violations(path: str, text: str) -> list[Violation]:
    found: list[Violation] = []
    lines = text.splitlines()
    for line_number, line in enumerate(lines, 1):
        if ".env.production" in line:
            found.append(Violation(path, line_number, "production_dotenv", line.strip()))
        if _PRODUCTION_URI.search(line):
            found.append(Violation(path, line_number, "production_uri_literal", "Mongo production URI literal"))

    # Detect the characteristic hand-written KEY=VALUE parser and fallback list.
    if (
        re.search(r"split\(\s*['\"]=['\"]\s*,\s*1\s*\)", text)
        and re.search(r"(?:read_text|open\s*\()", text)
        and re.search(r"(?:^|[/.'\"])\.?[A-Za-z0-9_-]*\.env(?:$|['\"])", text, re.M)
    ):
        line = text[: re.search(r"split\(\s*['\"]=['\"]", text).start()].count("\n") + 1
        found.append(Violation(path, line, "manual_dotenv_parser", "manual KEY=VALUE dotenv parsing"))

    local_index = text.find('".env.local"')
    if local_index < 0:
        local_index = text.find("'.env.local'")
    plain_env = min(
        (index for index in (text.find('".env"'), text.find("'.env'")) if index >= 0),
        default=-1,
    )
    if local_index >= 0 and plain_env >= 0:
        segment = text[min(local_index, plain_env) : max(local_index, plain_env) + 40]
        if any(marker in segment for marker in ("for ", " in (", " in [", "else")):
            line = text[: min(local_index, plain_env)].count("\n") + 1
            found.append(Violation(path, line, "dotenv_fallback", ".env.local/.env fallback"))

    return found


def scan_repository(root: Path = ROOT) -> list[Violation]:
    violations: list[Violation] = []
    for source_root in SOURCE_ROOTS:
        base = root / source_root
        if not base.exists():
            continue
        for file_path in sorted(p for p in base.rglob("*") if p.is_file() and p.suffix in SOURCE_SUFFIXES):
            relative = file_path.relative_to(root).as_posix()
            if relative in SKIP_PATHS or "tests" in file_path.relative_to(root).parts:
                continue
            text = file_path.read_text(encoding="utf-8", errors="replace")
            candidates = _text_violations(relative, text)
            if file_path.suffix == ".py":
                candidates.extend(_python_violations(relative, text))
            # Authorization may only be read from the pristine process snapshot.
            # A dotenv parser in the same file plus this key is always unsafe.
            if "GOB_DB_ACCESS" in text and any(
                item.rule in {"dotenv_loader", "manual_dotenv_parser"}
                for item in candidates
            ):
                line = text[: text.find("GOB_DB_ACCESS")].count("\n") + 1
                candidates.append(
                    Violation(
                        relative,
                        line,
                        "file_db_authorization",
                        "GOB_DB_ACCESS alongside file loading",
                    )
                )
            for violation in candidates:
                if relative not in RULE_EXCEPTIONS.get(violation.rule, frozenset()):
                    violations.append(violation)
    return sorted(violations, key=lambda item: (item.path, item.line, item.rule))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    violations = scan_repository(args.root.resolve())
    if violations:
        for item in violations:
            print(f"{item.path}:{item.line}: {item.rule}: {item.detail}")
        print(f"Environment safety check failed: {len(violations)} violation(s).", file=sys.stderr)
        return 1
    print("Environment safety check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
