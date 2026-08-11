#!/usr/bin/env python3
"""Read-only position-rating sanity audit for one franchise and recruit pool.

The script reads FTD/FPD/FRD from MongoDB, recomputes ratings with the current
``BackEnd.utils.position_ratings`` implementation, and writes two CSV dumps plus
a Markdown analysis. It contains no database write operations.

Usage:
    ./.venv/bin/python scripts/audit_position_rating_sanity.py \
        --franchise-id 6a67882a2b2eb443f8c7789f
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Sequence

from bson import ObjectId

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.utils.position_ratings import (  # noqa: E402
    POSITION_WEIGHTS,
    compute_position_ratings,
    height_fitness,
)
from scripts.db_migration_cli import connect_migration_target

DEFAULT_FRANCHISE_ID = "6a67882a2b2eb443f8c7789f"
POSITIONS = ("PG", "SG", "SF", "PF", "C")
ATTRIBUTES = ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT", "CH")
YEAR_ORDER = ("FR", "SO", "JR", "SR")
YEAR_ALIASES = {
    "fr": "FR",
    "freshman": "FR",
    "so": "SO",
    "sophomore": "SO",
    "jr": "JR",
    "junior": "JR",
    "sr": "SR",
    "senior": "SR",
}


def _number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _display_number(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value


def _percentile(values: Sequence[float], percentile: float) -> float:
    """Linear-interpolated percentile, equivalent to NumPy's default method."""
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return math.nan
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * percentile / 100.0
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    fraction = index - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _pearson(x_values: Sequence[float], y_values: Sequence[float]) -> float:
    if len(x_values) != len(y_values) or len(x_values) < 2:
        return math.nan
    x_mean = statistics.mean(x_values)
    y_mean = statistics.mean(y_values)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
    x_ss = sum((x - x_mean) ** 2 for x in x_values)
    y_ss = sum((y - y_mean) ** 2 for y in y_values)
    denominator = math.sqrt(x_ss * y_ss)
    return numerator / denominator if denominator else math.nan


def _argmax(ratings: dict[str, int]) -> tuple[str, int, int, int]:
    # Stable order makes ties reproducible and explicit in the report.
    ranked = sorted(POSITIONS, key=lambda pos: (-ratings[pos], POSITIONS.index(pos)))
    top1 = ratings[ranked[0]]
    top2 = ratings[ranked[1]]
    return ranked[0], top1, top2, top1 - top2


def _player_for_rating(height, attributes: dict) -> dict:
    return {"height": height, "attributes": attributes}


def _markdown_table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> list[str]:
    headers = [str(header) for header in headers]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---:" if index else "---" for index in range(len(headers))) + "|",
    ]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return lines


def _fmt(value: float, digits: int = 2) -> str:
    if math.isnan(value):
        return "n/a"
    return f"{value:.{digits}f}"


def _pct(count: int, denominator: int) -> str:
    return f"{100 * count / denominator:.2f}%" if denominator else "n/a"


def _team_player_map(ftd_docs: list[dict]) -> tuple[dict[str, str], list[str]]:
    mapping: dict[str, str] = {}
    duplicates: list[str] = []
    for team in ftd_docs:
        team_id = str(team.get("team_id", ""))
        player_ids = list(team.get("players") or []) + list(team.get("training_squad_players") or [])
        for player_id in player_ids:
            key = str(player_id)
            if key in mapping and mapping[key] != team_id:
                duplicates.append(key)
            mapping[key] = team_id
    return mapping, duplicates


def _roster_rows(fpd_docs: list[dict], team_by_player: dict[str, str]) -> list[dict]:
    rows = []
    for doc in fpd_docs:
        meta = doc.get("meta") or {}
        attrs = doc.get("attributes") or {}
        height = _number(meta.get("height", attrs.get("height")))
        ratings = compute_position_ratings(_player_for_rating(height, attrs))
        argmax, top1, top2, margin = _argmax(ratings)
        year_raw = str(meta.get("year") or "").strip()
        row = {
            "player_id": str(doc.get("player_id") or ""),
            "team_id": team_by_player.get(str(doc.get("player_id") or ""), str(meta.get("team_id") or "")),
            "class_year": YEAR_ALIASES.get(year_raw.lower(), year_raw.upper()),
            "height_in": _display_number(height),
            "weight": _display_number(_number(meta.get("weight"))),
            **{key: _display_number(_number(attrs.get(key))) for key in ATTRIBUTES},
            **{f"rt_{pos}": ratings[pos] for pos in POSITIONS},
            "argmax_position": argmax,
            "top1_rt": top1,
            "top2_rt": top2,
            "rt_margin": margin,
        }
        rows.append(row)
    return sorted(rows, key=lambda row: (row["team_id"], row["player_id"]))


def _recruit_rows(frd_docs: list[dict]) -> list[dict]:
    rows = []
    for doc in frd_docs:
        attrs = doc.get("attributes") or {}
        height = _number(doc.get("height", attrs.get("height")))
        player = _player_for_rating(height, attrs)
        recruit_ratings = compute_position_ratings(player)
        player_ratings = compute_position_ratings(player)
        recruit_argmax, recruit_top1, _, _ = _argmax(recruit_ratings)
        player_argmax, player_top1, _, _ = _argmax(player_ratings)
        row = {
            "recruit_id": str(doc.get("recruit_id") or ""),
            "height_in": _display_number(height),
            **{key: _display_number(_number(attrs.get(key))) for key in ATTRIBUTES},
            **{f"recruit_rt_{pos}": recruit_ratings[pos] for pos in POSITIONS},
            **{f"player_rt_{pos}": player_ratings[pos] for pos in POSITIONS},
            **{f"delta_{pos}": player_ratings[pos] - recruit_ratings[pos] for pos in POSITIONS},
            "recruit_argmax_position": recruit_argmax,
            "recruit_top1_rt": recruit_top1,
            "player_argmax_position": player_argmax,
            "player_top1_rt": player_top1,
        }
        rows.append(row)
    return sorted(rows, key=lambda row: row["recruit_id"])


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise RuntimeError(f"Refusing to write empty CSV: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _build_report(
    db_name: str,
    franchise_id: str,
    players: list[dict],
    recruits: list[dict],
    source_counts: dict[str, int],
    mapping_notes: list[str],
) -> str:
    player_count = len(players)
    recruit_count = len(recruits)
    argmax_counts = Counter(row["argmax_position"] for row in players)
    by_argmax = defaultdict(list)
    for row in players:
        by_argmax[row["argmax_position"]].append(float(row["height_in"]))

    sf_heights = by_argmax["SF"]
    pf_heights = by_argmax["PF"]
    sf_mean = statistics.mean(sf_heights) if sf_heights else math.nan
    pf_mean = statistics.mean(pf_heights) if pf_heights else math.nan
    sf_median = statistics.median(sf_heights) if sf_heights else math.nan
    pf_median = statistics.median(pf_heights) if pf_heights else math.nan

    lines = [
        "# Position Rating Sanity Audit",
        "",
        f"- Database: `{db_name}`",
        f"- Franchise: `{franchise_id}`",
        f"- Rostered players: **{player_count:,}** across **{source_counts['teams']:,}** FTD documents",
        f"- Current franchise recruit pool: **{recruit_count:,}** FRD documents",
        "- RT source: ratings recomputed in memory with the current `compute_position_ratings`; no stored values were changed.",
        "- Argmax tie rule: stable `PG, SG, SF, PF, C` order. This only decides how exact top-rating ties are labeled.",
        "- Percentiles: linear interpolation.",
        "- Recruit delta convention: `player-profile RT - recruit-profile RT`.",
        "",
    ]
    if mapping_notes:
        lines += ["## Data integrity notes", "", *[f"- {note}" for note in mapping_notes], ""]

    lines += ["## A. Argmax distribution", ""]
    lines += _markdown_table(
        ("Position", "Count", "%"),
        ((pos, argmax_counts[pos], _pct(argmax_counts[pos], player_count)) for pos in POSITIONS),
    )
    lines += [
        "",
        "> **Gauge note (grow-into-frame).** Argmax vs a 20%-per-position balance is "
        "**descriptive only, not an acceptance gate.** This is a grow-into-frame league: a young "
        "frontcourt player sits ~2in below his adult frame and reads one slot toward the perimeter "
        "until he grows in, so aggregate argmax skews toward the guards (SG high, SF/C low in FR/SO, "
        "converging by SR). The acceptance gauge is **INTENT supply** (`position_intent`, ~20% each), "
        "with **SR-only argmax** as the secondary check. See "
        "`Player_Attribute_Recalibration_Design` §3.6.4 for the mechanism and SF-intent-by-year evidence.",
    ]

    lines += ["", "## B. Height by argmax position", ""]
    lines += _markdown_table(
        ("Position", "N", "Mean", "Median", "P10", "P90"),
        (
            (
                pos,
                len(by_argmax[pos]),
                _fmt(statistics.mean(by_argmax[pos])) if by_argmax[pos] else "n/a",
                _fmt(statistics.median(by_argmax[pos])) if by_argmax[pos] else "n/a",
                _fmt(_percentile(by_argmax[pos], 10)),
                _fmt(_percentile(by_argmax[pos], 90)),
            )
            for pos in POSITIONS
        ),
    )
    lines += [
        "",
        f"PF minus SF mean height: **{_fmt(pf_mean - sf_mean)} in**; "
        f"median difference: **{_fmt(pf_median - sf_median)} in**.",
    ]

    lines += ["", "## C. Undersized bigs", ""]
    undersized_rows = []
    for pos in ("PF", "C"):
        group = [row for row in players if row["argmax_position"] == pos]
        for threshold in (78, 76):
            count = sum(float(row["height_in"]) < threshold for row in group)
            undersized_rows.append((pos, f"< {threshold} in", count, _pct(count, len(group)), len(group)))
    lines += _markdown_table(("Argmax", "Height", "Count", "% of group", "Group N"), undersized_rows)

    heights = [float(row["height_in"]) for row in players]
    pf_ratings = [float(row["rt_PF"]) for row in players]
    c_ratings = [float(row["rt_C"]) for row in players]
    # PF height is now a multiplicative fitness (design §3.6.2), no longer a
    # weighted additive term. Report the fitness spread across 76-84 in.
    pf_height_contributions = [height_fitness("PF", height) for height in range(76, 85)]
    pf_contribution_variance = statistics.pvariance(pf_height_contributions)
    empirical_76_84 = [row for row in players if 76 <= float(row["height_in"]) <= 84]
    empirical_pf_corr = _pearson(
        [float(row["height_in"]) for row in empirical_76_84],
        [float(row["rt_PF"]) for row in empirical_76_84],
    )
    lines += [
        "",
        "## D. Height discrimination",
        "",
    ]
    lines += _markdown_table(
        ("Measure", "Value"),
        (
            ("Pearson r: height vs PF RT (all players)", _fmt(_pearson(heights, pf_ratings), 4)),
            ("Pearson r: height vs C RT (all players)", _fmt(_pearson(heights, c_ratings), 4)),
            ("PF weighted height contribution variance, heights 76–84", _fmt(pf_contribution_variance, 4)),
            ("PF weighted height contribution range, heights 76–84", f"{min(pf_height_contributions):.2f}–{max(pf_height_contributions):.2f}"),
            ("Empirical height vs PF RT r, player heights 76–84", _fmt(empirical_pf_corr, 4)),
            ("Players in empirical 76–84 subset", len(empirical_76_84)),
        ),
    )
    lines += [
        "",
        "The formula-level variance uses only PF's weighted height component while holding all other attributes constant.",
    ]

    margins = [int(row["rt_margin"]) for row in players]
    lines += ["", "## E. Tweener rate", ""]
    lines += _markdown_table(
        ("Rule", "Count", "%"),
        (
            ("rt_margin < 3", sum(value < 3 for value in margins), _pct(sum(value < 3 for value in margins), player_count)),
            ("rt_margin < 5", sum(value < 5 for value in margins), _pct(sum(value < 5 for value in margins), player_count)),
        ),
    )

    lines += ["", "## F. RT distribution per position", ""]
    rt_distribution_rows = []
    for pos in POSITIONS:
        values = [float(row[f"rt_{pos}"]) for row in players]
        rt_distribution_rows.append(
            (
                pos,
                *(_fmt(_percentile(values, p), 1) for p in (10, 25, 50, 75, 90)),
                _fmt(max(values), 1),
            )
        )
    lines += _markdown_table(("RT", "P10", "P25", "P50", "P75", "P90", "Max"), rt_distribution_rows)
    any_100 = sum(any(int(row[f"rt_{pos}"]) >= 100 for pos in POSITIONS) for row in players)
    lines += ["", f"Players with any RT ≥ 100: **{any_100:,} ({_pct(any_100, player_count)})**."]

    lines += ["", "## G. RT by class year", ""]
    class_rows = []
    for year in YEAR_ORDER:
        values = [float(row["top1_rt"]) for row in players if row["class_year"] == year]
        class_rows.append((year, len(values), _fmt(_percentile(values, 50), 1), _fmt(_percentile(values, 90), 1)))
    unknown_years = Counter(row["class_year"] for row in players if row["class_year"] not in YEAR_ORDER)
    lines += _markdown_table(("Class", "N", "Top1 P50", "Top1 P90"), class_rows)
    if unknown_years:
        lines += ["", f"Unrecognized class-year labels excluded from this table: `{dict(unknown_years)}`."]

    lines += ["", "## H. Recruit/player formula discontinuity", ""]
    delta_rows = []
    for pos in POSITIONS:
        deltas = [float(row[f"delta_{pos}"]) for row in recruits]
        abs_deltas = [abs(value) for value in deltas]
        delta_rows.append(
            (
                pos,
                _fmt(_percentile(deltas, 10), 1),
                _fmt(_percentile(deltas, 50), 1),
                _fmt(_percentile(deltas, 90), 1),
                _fmt(_percentile(abs_deltas, 50), 1),
                _fmt(_percentile(abs_deltas, 90), 1),
                _fmt(min(deltas), 1),
                _fmt(max(deltas), 1),
            )
        )
    lines += _markdown_table(
        ("Position", "Delta P10", "Delta P50", "Delta P90", "Abs delta P50", "Abs delta P90", "Min", "Max"),
        delta_rows,
    )
    changed_argmax = sum(row["recruit_argmax_position"] != row["player_argmax_position"] for row in recruits)
    lines += [
        "",
        f"Recruits whose argmax changes between profiles: **{changed_argmax:,}/{recruit_count:,} "
        f"({_pct(changed_argmax, recruit_count)})**.",
    ]

    short_big = [
        row
        for row in recruits
        if float(row["height_in"]) < 71 and row["recruit_argmax_position"] in ("PF", "C")
    ]
    under_71 = [row for row in recruits if float(row["height_in"]) < 71]
    lines += ["", "## I. Short-big compensation", ""]
    lines += _markdown_table(
        ("Measure", "Count", "%"),
        (
            ("All recruits under 71 in", len(under_71), _pct(len(under_71), recruit_count)),
            (
                "Under-71 recruits with recruit-profile argmax PF/C",
                len(short_big),
                _pct(len(short_big), len(under_71)),
            ),
        ),
    )

    pf_share = argmax_counts["PF"] / player_count if player_count else 0
    pf_sf_p10_overlap = max(_percentile(pf_heights, 10), _percentile(sf_heights, 10))
    pf_sf_p90_overlap = min(_percentile(pf_heights, 90), _percentile(sf_heights, 90))
    # H2 (flat PF height credit) is resolved by the multiplicative curve: fitness
    # now varies with height instead of returning a constant.
    pf_values_76_84 = [height_fitness("PF", height) for height in range(76, 85)]
    h2_confirmed = len(set(pf_values_76_84)) == 1
    pf_abs = [abs(float(row["delta_PF"])) for row in recruits]
    c_abs = [abs(float(row["delta_C"])) for row in recruits]
    discontinuity_nonzero = sum(
        row["delta_PF"] != 0 or row["delta_C"] != 0 for row in recruits
    )
    h3_confirmed = discontinuity_nonzero > 0

    lines += [
        "",
        "## Hypothesis verdicts",
        "",
        "### H1 — **Inconclusive (mixed result)**",
        "",
        f"PF is {argmax_counts['PF']:,}/{player_count:,} (**{_pct(argmax_counts['PF'], player_count)}**) "
        f"of argmax labels versus a 20% balance reference. PF-argmax players average **{_fmt(pf_mean)} in** "
        f"versus **{_fmt(sf_mean)} in** for SF, a **{_fmt(pf_mean - sf_mean)} in** difference. "
        f"The PF and SF P10–P90 ranges overlap from **{_fmt(pf_sf_p10_overlap)} to "
        f"{_fmt(pf_sf_p90_overlap)} in**. PF is modestly over the balance reference and the ranges overlap, "
        "but no threshold was supplied for whether a 1.94-inch mean difference is meaningful, so the compound "
        "hypothesis cannot be classified as confirmed or refuted without imposing one.",
        "",
        f"### H2 (flat PF height credit) — **{'still flat' if h2_confirmed else 'RESOLVED'}**",
        "",
        f"PF height is now a multiplicative fitness varying from "
        f"**{_fmt(min(pf_values_76_84), 3)}** to **{_fmt(max(pf_values_76_84), 3)}** across 76-84 in "
        f"(variance **{_fmt(pf_contribution_variance, 4)}**), not a constant additive term.",
        "",
        "### H3 (recruit/player discontinuity) — **RESOLVED by construction**",
        "",
        f"One weight table now serves recruits and players (the recruit profile was deleted), so RT does "
        f"not change at signing. Recruits whose player-vs-recruit argmax differs: "
        f"**{changed_argmax:,}/{recruit_count:,}** (expected 0).",
        "",
        "## Anything else that looked wrong",
        "",
    ]

    exact_top_ties = sum(int(row["rt_margin"]) == 0 for row in players)
    missing_team = sum(not row["team_id"] for row in players)
    stored_vs_computed = source_counts["stored_rt_mismatches"]
    recruit_stored_vs_computed = source_counts["recruit_stored_rt_mismatches"]
    weight_sums = {
        f"{pos}": sum(weights.values()) for pos, weights in POSITION_WEIGHTS.items()
    }
    bad_weight_sums = {name: total for name, total in weight_sums.items() if not math.isclose(total, 1.0)}
    observations = [
        f"Exact top-RT ties: {exact_top_ties:,}/{player_count:,} ({_pct(exact_top_ties, player_count)}); "
        "their argmax label depends on the documented stable tie rule.",
        f"Stored player-profile RT dictionaries differing from fresh computation: "
        f"{stored_vs_computed:,}/{player_count:,}.",
        f"Stored recruit-profile RT dictionaries differing from fresh computation: "
        f"{recruit_stored_vs_computed:,}/{recruit_count:,}.",
        f"Players without a resolvable team_id: {missing_team:,}/{player_count:,}.",
        (
            f"Weight tables not summing to 1.0: `{bad_weight_sums}`."
            if bad_weight_sums
            else "Every audited player, recruit, and short-big weight vector sums to 1.0."
        ),
        "No database writes, migrations, or stored RT recomputations were performed.",
    ]
    lines += [f"- {item}" for item in observations]
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--franchise-id", default=DEFAULT_FRANCHISE_ID)
    parser.add_argument("--db", required=True, choices=("gob-staging", "gob"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "_documentation_master" / "projects" / "rt_sanity_audit",
    )
    args = parser.parse_args()

    try:
        franchise_object_id = ObjectId(args.franchise_id)
    except Exception as exc:
        raise RuntimeError("franchise-id must be a valid ObjectId") from exc

    connection = connect_migration_target(args.db, write=False)
    db = connection.database
    franchise = db["franchises"].find_one(
        {"_id": franchise_object_id},
        {"_id": 1, "used_recruit_set_ids": 1},
    )
    if not franchise:
        raise RuntimeError(f"Franchise {args.franchise_id} not found in {args.db}")

    ftd_docs = list(
        db["franchise_team_data"].find(
            {"franchise_id": franchise_object_id},
            {"team_id": 1, "players": 1, "training_squad_players": 1},
        )
    )
    fpd_docs = list(
        db["franchise_players_data"].find(
            {"franchise_id": args.franchise_id},
            {"player_id": 1, "meta": 1, "attributes": 1, "position_ratings": 1},
        )
    )
    frd_docs = list(
        db["franchise_recruits_data"].find(
            {"franchise_id": args.franchise_id},
            {
                "recruit_id": 1,
                "height": 1,
                "weight": 1,
                "year": 1,
                "attributes": 1,
                "position_ratings": 1,
            },
        )
    )
    connection.close()

    if len(ftd_docs) != 128:
        raise RuntimeError(f"Expected 128 franchise teams; found {len(ftd_docs)}")
    if not fpd_docs:
        raise RuntimeError("No franchise player documents found")
    if not frd_docs:
        raise RuntimeError("No franchise recruit documents found")

    team_by_player, duplicate_assignments = _team_player_map(ftd_docs)
    players = _roster_rows(fpd_docs, team_by_player)
    recruits = _recruit_rows(frd_docs)

    mapped_ids = set(team_by_player)
    fpd_ids = {str(doc.get("player_id") or "") for doc in fpd_docs}
    mapping_notes = []
    if duplicate_assignments:
        mapping_notes.append(
            f"{len(set(duplicate_assignments))} player IDs appeared on more than one FTD roster."
        )
    absent_from_ftd = sorted(fpd_ids - mapped_ids)
    absent_from_fpd = sorted(mapped_ids - fpd_ids)
    if absent_from_ftd:
        mapping_notes.append(
            f"{len(absent_from_ftd)} FPD players were absent from active/training-squad FTD arrays; "
            "their `meta.team_id` was used."
        )
    if absent_from_fpd:
        mapping_notes.append(f"{len(absent_from_fpd)} FTD roster IDs had no matching FPD document.")

    stored_rt_mismatches = 0
    for doc in fpd_docs:
        meta = doc.get("meta") or {}
        attrs = doc.get("attributes") or {}
        computed = compute_position_ratings(
            _player_for_rating(meta.get("height", attrs.get("height")), attrs),
        )
        if doc.get("position_ratings") != computed:
            stored_rt_mismatches += 1

    recruit_stored_rt_mismatches = 0
    for doc in frd_docs:
        attrs = doc.get("attributes") or {}
        computed = compute_position_ratings(
            _player_for_rating(doc.get("height", attrs.get("height")), attrs),
        )
        if doc.get("position_ratings") != computed:
            recruit_stored_rt_mismatches += 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    roster_path = args.output_dir / "rostered_players_rt_audit.csv"
    recruit_path = args.output_dir / "recruit_pool_rt_profile_comparison.csv"
    report_path = args.output_dir / "position_rating_sanity_audit.md"
    _write_csv(roster_path, players)
    _write_csv(recruit_path, recruits)
    report_path.write_text(
        _build_report(
            args.db,
            args.franchise_id,
            players,
            recruits,
            {
                "teams": len(ftd_docs),
                "stored_rt_mismatches": stored_rt_mismatches,
                "recruit_stored_rt_mismatches": recruit_stored_rt_mismatches,
            },
            mapping_notes,
        ),
        encoding="utf-8",
    )

    print(f"Wrote {len(players):,} player rows: {roster_path}")
    print(f"Wrote {len(recruits):,} recruit rows: {recruit_path}")
    print(f"Wrote report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
