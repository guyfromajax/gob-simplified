#!/usr/bin/env python3
"""Static unused-export + unused-route inventory. Not a product file."""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "FrontEnd" / "static"
SEARCH_ROOTS = [
    ROOT / "FrontEnd" / "static",
    ROOT / "BackEnd",
    ROOT / "desktop",
    ROOT / "tests",
    ROOT / "scripts",
    ROOT / "netlify.toml",
    ROOT / "FrontEnd" / "static" / "_redirects",
]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def corpus() -> str:
    chunks = []
    for root in SEARCH_ROOTS:
        if root.is_file():
            chunks.append(read_text(root))
            continue
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if any(part in {".git", "node_modules", "__pycache__", "sounds"} for part in p.parts):
                continue
            if p.suffix.lower() not in {".js", ".html", ".css", ".py", ".mjs", ".toml", ".json", ".md"}:
                continue
            chunks.append(read_text(p))
    return "\n".join(chunks)


def shared_exports() -> list[tuple[str, str, int]]:
    out = []
    skip_dirs = {"phaser", "vendor"}
    for p in (STATIC / "js").rglob("*.js"):
        if any(part in skip_dirs for part in p.parts):
            continue
        if p.name.endswith(".test.js"):
            continue
        text = read_text(p)
        for i, line in enumerate(text.splitlines(), 1):
            m = re.match(r"^export (?:async )?function (\w+)", line)
            if m:
                out.append((m.group(1), str(p.relative_to(ROOT)), i))
    return out


def route_defs() -> list[tuple[str, str, int]]:
    pat = re.compile(
        r"@(?:app|router)\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)[\"']",
        re.I,
    )
    out = []
    for p in (ROOT / "BackEnd" / "api").glob("*.py"):
        text = read_text(p)
        for i, line in enumerate(text.splitlines(), 1):
            for m in pat.finditer(line):
                out.append((m.group(2), str(p.relative_to(ROOT)), i))
    return out


def hits(needle: str, blob: str, self_path: str | None = None) -> int:
    n = blob.count(needle)
    if self_path:
        n -= read_text(ROOT / self_path).count(needle)
    return n


def main() -> None:
    blob = corpus()
    print("=== unused-looking JS exports (zero extra hits) ===")
    for name, path, line in shared_exports():
        extra = hits(name, blob, path)
        if extra == 0:
            print(f"{path}:{line}  {name}")
    print("=== unused-looking FastAPI routes (zero extra hits) ===")
    skip_prefixes = ("/simulate", "/api/simulate", "/health")
    for path_str, file, line in route_defs():
        if any(path_str.startswith(p) for p in skip_prefixes):
            continue
        stem = path_str.split("{", 1)[0].rstrip("/")
        if not stem or stem == "/":
            continue
        extra = hits(stem, blob, file)
        if extra == 0:
            print(f"{file}:{line}  {path_str}")


if __name__ == "__main__":
    main()
