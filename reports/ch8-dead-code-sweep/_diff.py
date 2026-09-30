#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from PIL import Image

SHOTS = Path(__file__).resolve().parent / "shots"


def pct(before: Path, after: Path) -> float:
    a = Image.open(before).convert("RGB")
    b = Image.open(after).convert("RGB")
    if a.size != b.size:
        return 100.0
    pa, pb = a.tobytes(), b.tobytes()
    changed = sum(1 for i in range(0, len(pa), 3) if pa[i : i + 3] != pb[i : i + 3])
    return 100.0 * changed / (a.size[0] * a.size[1])


def main() -> None:
    befores = sorted(SHOTS.glob("before-*-1280.png"))
    rows = []
    for before in befores:
        name = before.name.replace("before-", "after-", 1)
        after = SHOTS / name
        if not after.is_file():
            print("MISSING", name)
            continue
        p = pct(before, after)
        key = before.name[len("before-") : -len("-1280.png")]
        rows.append((key, p))
        flag = "  ** >0.5%" if p > 0.5 else ""
        print(f"{p:7.3f}%  {key}{flag}")
    print("pairs", len(rows), "max", max((r[1] for r in rows), default=0))


if __name__ == "__main__":
    main()
