#!/usr/bin/env python3
"""
Update docs/To Do/total_team_attrs.md with rankings and values from gob-staging.

- Total team attributes = sum over all players on the team of (sum of that player's
  core attribute values: SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT).
- Prestige is read from the teams collection in gob-staging.
- Teams are ranked by total aggregate player attributes (descending).

Run from repo root with MONGO_URI pointing at a cluster that has gob-staging:
  .venv/bin/python scripts/update_total_team_attrs_doc.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Load env before importing BackEnd.db
def _load_env(filepath: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if filepath.exists():
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


for p in [ROOT / ".env.local", ROOT / ".env"]:
    for k, v in _load_env(p).items():
        os.environ.setdefault(k, v)

from pymongo import MongoClient

DB_NAME = "gob-staging"
# Core 12 attributes used for "total aggregate" (no anchor_* to avoid double-count)
ATTR_KEYS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]
DOC_PATH = ROOT / "docs" / "To Do" / "total_team_attrs.md"


def _player_attr_sum(attrs: dict) -> int:
    if not attrs:
        return 0
    total = 0
    for k in ATTR_KEYS:
        v = attrs.get(k)
        if isinstance(v, (int, float)):
            total += int(v)
    return total


def main() -> int:
    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("❌ MONGO_URI not set. Set it in .env or .env.local", file=sys.stderr)
        return 1

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[DB_NAME]
    players_coll = db["players"]
    teams_coll = db["teams"]

    # Team name -> total aggregate player attributes
    team_totals: dict[str, int] = {}
    for doc in players_coll.find({}, {"team": 1, "attributes": 1}):
        team = (doc.get("team") or "").strip()
        if not team:
            continue
        attrs = doc.get("attributes") or {}
        s = _player_attr_sum(attrs)
        team_totals[team] = team_totals.get(team, 0) + s

    # Team name -> prestige from teams collection
    team_prestige: dict[str, int] = {}
    for doc in teams_coll.find({}, {"name": 1, "prestige": 1}):
        name = (doc.get("name") or "").strip()
        if name:
            p = doc.get("prestige")
            team_prestige[name] = int(p) if p is not None else 0

    # Section 1: Rank by total team attributes (prestige on the right)
    sorted_by_attrs = sorted(
        team_totals.items(),
        key=lambda x: (-x[1], x[0]),
    )
    lines = [
        "| Rank | Team | Total team attributes | Prestige |",
        "|------|------|----------------------|----------|",
    ]
    for rank, (team_name, total) in enumerate(sorted_by_attrs, start=1):
        prestige = team_prestige.get(team_name, 0)
        lines.append(f"| {rank} | {team_name} | {total} | {prestige} |")

    # Section 2: Rank by prestige (total team attributes on the right)
    sorted_by_prestige = sorted(
        team_totals.keys(),
        key=lambda name: (-team_prestige.get(name, 0), name),
    )
    lines.append("")
    lines.append("## Ranked by Prestige")
    lines.append("")
    lines.append("| Rank | Team | Prestige | Total team attributes |")
    lines.append("|------|------|----------|----------------------|")
    for rank, team_name in enumerate(sorted_by_prestige, start=1):
        prestige = team_prestige.get(team_name, 0)
        total = team_totals.get(team_name, 0)
        lines.append(f"| {rank} | {team_name} | {prestige} | {total} |")

    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"✅ Updated {DOC_PATH} with {len(sorted_by_attrs)} teams (from {DB_NAME})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
