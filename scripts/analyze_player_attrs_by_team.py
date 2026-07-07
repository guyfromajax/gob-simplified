#!/usr/bin/env python3
"""
Analyze gob-staging universal players collection by team.

Groups players by team, computes core-12 attribute totals, RT distribution
(using current position ratings code), and height distribution.
Writes report to _documentation_master/projects/Player_Attr_Analysis.md
sectioned by conference (1-16).
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


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

from BackEnd.utils.position_ratings import compute_position_ratings

DB_NAME = "gob-staging"
ATTR_KEYS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]
OUTPUT_PATH = ROOT / "_documentation_master" / "projects" / "Player_Attr_Analysis.md"
TEAMS_FILE = ROOT / "teams" / "128_teams.txt"

RT_BUCKETS = [
    ("80+", lambda rt: rt >= 80),
    ("60-79", lambda rt: 60 <= rt <= 79),
    ("40-59", lambda rt: 40 <= rt <= 59),
    ("20-39", lambda rt: 20 <= rt <= 39),
    ("0-19", lambda rt: 0 <= rt <= 19),
]

HEIGHT_BUCKETS = [
    ("Extra Short (<70)", lambda h: h < 70),
    ("Short (70-72)", lambda h: 70 <= h <= 72),
    ("Normal (73-75)", lambda h: 73 <= h <= 75),
    ("Plus (76-78)", lambda h: 76 <= h <= 78),
    ("Tall (79+)", lambda h: h >= 79),
]


def _player_attr_sum(attrs: dict) -> int:
    if not attrs:
        return 0
    total = 0
    for k in ATTR_KEYS:
        v = attrs.get(k)
        if isinstance(v, (int, float)):
            total += int(v)
    return total


def _best_rt(player: dict) -> int:
    ratings = compute_position_ratings(player, profile="player")
    return max(ratings.values()) if ratings else 0


def _height_inches(player: dict) -> int | None:
    height = player.get("height")
    if height is None:
        attrs = player.get("attributes") or {}
        height = attrs.get("height")
    if height is None:
        return None
    try:
        return int(height)
    except (TypeError, ValueError):
        return None


def _load_team_sort_order() -> dict[str, int]:
    """Return team name -> canonical id from 128_teams.txt (for within-conference ordering)."""
    mapping: dict[str, int] = {}
    if not TEAMS_FILE.exists():
        return mapping
    for line in TEAMS_FILE.read_text(encoding="utf-8").splitlines()[1:]:
        parts = line.strip().split("\t")
        if len(parts) < 9:
            continue
        try:
            team_id = int(parts[0])
            team_name = parts[1].strip()
            int(parts[6])
            int(parts[8])
        except (ValueError, IndexError):
            continue
        mapping[team_name] = team_id
    return mapping


def main() -> int:
    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("MONGO_URI not set", file=sys.stderr)
        return 1

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[DB_NAME]
    players_coll = db["players"]
    teams_coll = db["teams"]

    team_conference: dict[str, int] = {}
    for doc in teams_coll.find({}, {"name": 1, "conference": 1}):
        name = (doc.get("name") or "").strip()
        conf = doc.get("conference")
        if name and conf is not None:
            team_conference[name] = int(conf)

    team_sort_order = _load_team_sort_order()

    team_stats: dict[str, dict] = defaultdict(
        lambda: {
            "attr_total": 0,
            "player_count": 0,
            "rt_counts": {label: 0 for label, _ in RT_BUCKETS},
            "height_counts": {label: 0 for label, _ in HEIGHT_BUCKETS},
            "height_unknown": 0,
        }
    )

    player_count = 0
    for doc in players_coll.find({}, {"team": 1, "height": 1, "attributes": 1}):
        team = (doc.get("team") or "").strip()
        if not team:
            continue
        player_count += 1
        stats = team_stats[team]
        stats["player_count"] += 1
        stats["attr_total"] += _player_attr_sum(doc.get("attributes") or {})

        rt = _best_rt(doc)
        for label, pred in RT_BUCKETS:
            if pred(rt):
                stats["rt_counts"][label] += 1
                break

        height = _height_inches(doc)
        if height is None:
            stats["height_unknown"] += 1
        else:
            for label, pred in HEIGHT_BUCKETS:
                if pred(height):
                    stats["height_counts"][label] += 1
                    break

    conferences: dict[int, list[str]] = defaultdict(list)
    for team_name in team_stats:
        conf = team_conference.get(team_name, 0)
        conferences[conf].append(team_name)

    def sort_key(name: str) -> tuple:
        return (team_sort_order.get(name, 9999), name)

    for conf in conferences:
        conferences[conf].sort(key=sort_key)

    lines = [
        "# Player Attribute Analysis (gob-staging)",
        "",
        f"Source: `{DB_NAME}.players` universal collection",
        f"Total players analyzed: {player_count}",
        f"Total teams: {len(team_stats)}",
        "",
        "Core 12 attributes: SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT",
        "RT = highest position rating (computed via `compute_position_ratings`, profile=`player`)",
        "",
    ]

    for conf_num in range(1, 17):
        lines.append(f"## Conference {conf_num}")
        lines.append("")
        teams_in_conf = conferences.get(conf_num, [])
        if not teams_in_conf:
            lines.append("_No teams found._")
            lines.append("")
            continue

        for team_name in teams_in_conf:
            stats = team_stats[team_name]
            lines.append(f"### {team_name}")
            lines.append("")
            lines.append(f"- **Total core-12 attribute value:** {stats['attr_total']:,}")
            lines.append(f"- **Players:** {stats['player_count']}")
            lines.append("")
            lines.append("**Players by RT range (highest RT):**")
            for label, _ in RT_BUCKETS:
                lines.append(f"- {label}: {stats['rt_counts'][label]}")
            lines.append("")
            lines.append("**Players by height:**")
            for label, _ in HEIGHT_BUCKETS:
                lines.append(f"- {label}: {stats['height_counts'][label]}")
            if stats["height_unknown"]:
                lines.append(f"- Unknown height: {stats['height_unknown']}")
            lines.append("")

    if conferences.get(0):
        lines.append("## Unassigned Conference")
        lines.append("")
        for team_name in sorted(conferences[0], key=sort_key):
            stats = team_stats[team_name]
            lines.append(f"### {team_name}")
            lines.append("")
            lines.append(f"- **Total core-12 attribute value:** {stats['attr_total']:,}")
            lines.append(f"- **Players:** {stats['player_count']}")
            lines.append("")
            lines.append("**Players by RT range (highest RT):**")
            for label, _ in RT_BUCKETS:
                lines.append(f"- {label}: {stats['rt_counts'][label]}")
            lines.append("")
            lines.append("**Players by height:**")
            for label, _ in HEIGHT_BUCKETS:
                lines.append(f"- {label}: {stats['height_counts'][label]}")
            if stats["height_unknown"]:
                lines.append(f"- Unknown height: {stats['height_unknown']}")
            lines.append("")

    ranked_teams = sorted(
        team_stats.items(),
        key=lambda item: (-item[1]["attr_total"], item[0]),
    )
    lines.append("## Team Rankings by Total Core-12 Attribute Value")
    lines.append("")
    lines.append("| Rank | Team | Conference | Total | RT Summary |")
    lines.append("|------|------|------------|------:|------------|")
    for rank, (team_name, stats) in enumerate(ranked_teams, start=1):
        conf = team_conference.get(team_name, "—")
        rt_summary = ", ".join(
            f"{label}: {stats['rt_counts'][label]}" for label, _ in RT_BUCKETS
        )
        lines.append(
            f"| {rank} | {team_name} | {conf} | {stats['attr_total']:,} | {rt_summary} |"
        )
    lines.append("")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Analyzed {player_count} players across {len(team_stats)} teams")
    print(f"Report written to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
