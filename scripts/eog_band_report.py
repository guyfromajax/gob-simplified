#!/usr/bin/env python3
"""
eog_band_report.py — parse a season's [EOG-BAND] instrumentation into tables.

Reads the JSONL file written by calculate_attr_changes when GOB_EOG_BAND_LOG=1
(see BackEnd/api/franchise_routes.py). Each line is `[EOG-BAND] {json}`.

Emits three tables, each split by is_distant_sim (distant games bypass the usage
logic for six attributes, so their bands are not comparable to live games):

  1. Branch frequency — per attribute, share of team-games hitting each band.
  2. Saturation       — per attribute, share of team-games with clamped=true,
                        and the median week a team first rails.
  3. Input histograms — distribution of the raw inputs that set thresholds,
                        especially distinct_plays_run, pt_total_attempts,
                        fb_total, and defensive_max_share.

Usage:
    python scripts/eog_band_report.py [path]
    # path defaults to $GOB_EOG_BAND_LOG_FILE or ./eog_band_log.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

TAG = "[EOG-BAND] "
HEADER_TAG = "[EOG-BAND-HEADER] "

# Raw inputs to histogram, by the attribute record that carries them.
HISTOGRAM_INPUTS = [
    ("offensive_efficiency", "distinct_plays_run", "int"),
    ("offensive_efficiency", "total_times_run", "int"),
    ("pt_efficiency", "pt_total_attempts", "int"),
    ("pt_opp_modifier", "pt_total_attempts", "int"),
    ("fb_efficiency", "fb_total", "int"),
    ("fb_opp_modifier", "opponent_fb_total", "int"),
    ("defensive_efficiency", "max_share", "float"),
]


def load_records(path: str) -> tuple[list[dict], list[dict]]:
    """Return (headers, data_records). Header lines carry run provenance."""
    headers: list[dict] = []
    records: list[dict] = []
    bad = 0
    with open(path, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith(HEADER_TAG):
                try:
                    headers.append(json.loads(line[len(HEADER_TAG):]))
                except json.JSONDecodeError:
                    bad += 1
                continue
            payload = line[len(TAG):] if line.startswith(TAG) else line
            try:
                records.append(json.loads(payload))
            except json.JSONDecodeError:
                bad += 1
    if bad:
        print(f"# warning: skipped {bad} unparseable line(s)", file=sys.stderr)
    return headers, records


def print_headers(headers: list[dict]) -> None:
    print("\n## Run provenance ([EOG-BAND-HEADER])")
    if not headers:
        print("  ⚠️  NO header record found — dataset provenance unknown "
              "(file predates header support, or was truncated).")
        return
    if len(headers) > 1:
        print(f"  {len(headers)} headers (file appended across runs); showing each:")
    for i, h in enumerate(headers):
        tag = f"  [{i + 1}] " if len(headers) > 1 else "  "
        flags = h.get("flags", {})
        print(f"{tag}utc={h.get('utc')}  git_sha={h.get('git_sha')}")
        print(f"{'    ' if len(headers) > 1 else '  '}flags: "
              f"ALL_GAMES_FULL_SIM={flags.get('FRANCHISE_ALL_GAMES_FULL_SIM')}  "
              f"ALL_TEAMS_AUTOTRAIN={flags.get('FRANCHISE_ALL_TEAMS_AUTOTRAIN')}  "
              f"CPU_SIM_USE_POOL={flags.get('FRANCHISE_CPU_SIM_USE_POOL')}")


def check_strict_distant(records: list[dict]) -> list[dict]:
    """Distant rows in the measured window (weeks 1-26) — these corrupt the six
    usage-gated attributes (they get randint(-2,1) instead of a real band). Returns
    the offending records."""
    return [
        r for r in records
        if r.get("is_distant_sim")
        and isinstance(r.get("week"), int)
        and 1 <= r["week"] <= REGULAR_SEASON_LAST_WEEK
    ]


def split_by_distant(records: list[dict]) -> dict[bool, list[dict]]:
    out: dict[bool, list[dict]] = {False: [], True: []}
    for rec in records:
        out[bool(rec.get("is_distant_sim"))].append(rec)
    return out


def _pct(n: int, d: int) -> str:
    return f"{(100.0 * n / d):5.1f}%" if d else "    -"


# Regular season = weeks 1-26; weeks 27-34 are the postseason EOG freeze
# (_finalize_team_attributes_for_game returns early → no [EOG-BAND] rows), and
# weeks 35-36 have no games. So a full season yields bands for weeks 1-26 only.
REGULAR_SEASON_LAST_WEEK = 26
POSTSEASON_FREEZE_WEEKS = range(27, 35)


def week_coverage(records: list[dict]) -> None:
    """Report which weeks actually produced bands. Saturation medians are taken
    over observed first-rail weeks (never divided by a fixed 34/26-week count),
    and frozen postseason weeks 27-34 are absent by design — not gaps/failures.
    """
    weeks = sorted({r["week"] for r in records if isinstance(r.get("week"), int)})
    print("\n## 0. Week coverage")
    if not weeks:
        print("  (no integer week values present)")
        return
    print(f"  weeks present: {weeks[0]}-{weeks[-1]}  (distinct={len(weeks)})")
    # Distinct game_ids per week — a full franchise week is 64 games (128 teams / 2).
    # Gate #1: week 1 must show 64. Any regular-season week != 64 means a game was
    # dropped from capture (worker log loss, EOG failure, etc.).
    games_by_week: dict[int, set] = defaultdict(set)
    for r in records:
        w = r.get("week")
        if isinstance(w, int):
            games_by_week[w].add(r.get("game_id"))
    print("  games captured per week (expect 64 each):")
    for w in weeks:
        n = len(games_by_week[w])
        flag = "" if n == 64 else "  ⚠️  != 64"
        print(f"    week {w:>2}: {n:>3} games{flag}")
    missing_regular = [w for w in range(1, REGULAR_SEASON_LAST_WEEK + 1) if w not in weeks]
    if missing_regular:
        print(f"  note: regular-season weeks with NO bands: {missing_regular} "
              f"(expected only if that week wasn't simulated)")
    leaked = [w for w in weeks if w in POSTSEASON_FREEZE_WEEKS]
    if leaked:
        print(f"  ⚠️  postseason freeze LEAK: bands found for frozen weeks {leaked} "
              f"— finalize should have returned early for weeks 27-34")
    else:
        print("  postseason weeks 27-34: correctly absent (EOG freeze), not counted as gaps")


def branch_frequency(records: list[dict]) -> None:
    per_attr_band: dict[str, Counter] = defaultdict(Counter)
    per_attr_total: Counter = Counter()
    for rec in records:
        attr = rec.get("attr")
        band = rec.get("band")
        per_attr_band[attr][band] += 1
        per_attr_total[attr] += 1

    print("\n## 1. Branch frequency (share of team-games per band)")
    for attr in sorted(per_attr_band):
        total = per_attr_total[attr]
        print(f"\n  {attr}  (n={total})")
        for band, count in per_attr_band[attr].most_common():
            print(f"    {str(band):<26} {count:>7}  {_pct(count, total)}")


def saturation(records: list[dict]) -> None:
    # Rail direction is derived from raw_delta's sign: a record is `clamped` only
    # when pre+raw_delta crossed a bound, so raw_delta>0 railed the CEILING (upper
    # clamp) and raw_delta<0 railed the FLOOR (lower clamp). `post` is the rail
    # value itself (e.g. shot_threshold 200 = ceiling, team_chemistry 7 = floor).
    # Direction matters for diagnosis: a whole league pinned at one rail is a
    # runaway feedback loop; a 50/50 split across both rails is a scale problem.
    per_attr_total: Counter = Counter()
    per_attr_clamped: Counter = Counter()
    # Net drift: E[delta]/game = mean(raw_delta) = Σ band_freq·band_midpoint (law of
    # total expectation). raw_delta is the pre-clamp band PRESSURE — it keeps showing
    # even when a saturated attr's applied delta is clamped to 0, so it's the tuning
    # target. 26-week projection = per-game drift × 26 (one EOG update per game).
    drift_sum: dict[str, float] = defaultdict(float)
    drift_n: Counter = Counter()
    # (franchise_id, team_id_label, attr) -> earliest railed week, per direction
    first_ceiling: dict[tuple, int] = {}
    first_floor: dict[tuple, int] = {}
    ceiling_vals: dict[str, set] = defaultdict(set)
    floor_vals: dict[str, set] = defaultdict(set)

    for rec in records:
        attr = rec.get("attr")
        per_attr_total[attr] += 1
        rd = rec.get("raw_delta")
        if isinstance(rd, (int, float)):
            drift_sum[attr] += rd
            drift_n[attr] += 1
        if not rec.get("clamped"):
            continue
        per_attr_clamped[attr] += 1
        if not isinstance(rd, (int, float)) or rd == 0:
            continue  # can't happen for a real clamp, but stay defensive
        week = rec.get("week")
        key = (rec.get("franchise_id"), rec.get("team_id_label"), attr)
        if rd > 0:  # ceiling
            ceiling_vals[attr].add(rec.get("post"))
            if isinstance(week, int) and week < first_ceiling.get(key, 10**9):
                first_ceiling[key] = week
        else:  # floor
            floor_vals[attr].add(rec.get("post"))
            if isinstance(week, int) and week < first_floor.get(key, 10**9):
                first_floor[key] = week

    ceil_weeks: dict[str, list] = defaultdict(list)
    for (_f, _t, attr), wk in first_ceiling.items():
        ceil_weeks[attr].append(wk)
    floor_weeks: dict[str, list] = defaultdict(list)
    for (_f, _t, attr), wk in first_floor.items():
        floor_weeks[attr].append(wk)

    def _rail_val(vals: set) -> str:
        clean = [v for v in vals if v is not None]
        if not clean:
            return "?"
        if len(set(clean)) == 1:
            v = clean[0]
            return f"{v:g}" if isinstance(v, (int, float)) else str(v)
        return "mixed"

    def _cell(teams: list, vals: set) -> str:
        if not teams:
            return f"{'0':>5} {'-':>6}  {'':>8}"
        med = f"wk{statistics.median(teams):.0f}"
        return f"{len(teams):>5} {med:>6}  {'@' + _rail_val(vals):>8}"

    print("\n## 2. Saturation & net drift  "
          "(E[Δ]/g = mean raw_delta = Σ band_freq·midpoint; 26wk = ×26)")
    print(f"  {'attr':<22} {'clamped%':>8} {'E[Δ]/g':>8} {'26wk':>8}   "
          f"{'CEILING t/medwk/@val':>22}   {'FLOOR t/medwk/@val':>22}")
    for attr in sorted(per_attr_total):
        total = per_attr_total[attr]
        clamped = per_attr_clamped[attr]
        n = drift_n.get(attr, 0)
        egm = (drift_sum[attr] / n) if n else 0.0
        proj = egm * 26
        print(f"  {attr:<22} {_pct(clamped, total):>8} {egm:>+8.3f} {proj:>+8.2f}   "
              f"{_cell(ceil_weeks.get(attr, []), ceiling_vals.get(attr, set())):>22}   "
              f"{_cell(floor_weeks.get(attr, []), floor_vals.get(attr, set())):>22}")


def _histogram(values: list, is_float: bool) -> None:
    if not values:
        print("      (no data)")
        return
    if is_float:
        # Bucket floats into 0.05-wide bins.
        buckets: Counter = Counter()
        for v in values:
            buckets[round(float(v) // 0.05 * 0.05, 2)] += 1
        keys = sorted(buckets)
        total = len(values)
        for k in keys:
            print(f"      [{k:.2f}, {k + 0.05:.2f})  {buckets[k]:>7}  {_pct(buckets[k], total)}")
        print(f"      min={min(values):.3f} max={max(values):.3f} "
              f"mean={statistics.mean(values):.3f} median={statistics.median(values):.3f}")
    else:
        buckets = Counter(int(v) for v in values)
        total = len(values)
        for k in sorted(buckets):
            print(f"      {k:>4}  {buckets[k]:>7}  {_pct(buckets[k], total)}")
        print(f"      min={min(values)} max={max(values)} "
              f"mean={statistics.mean(values):.2f} median={statistics.median(values):.1f}")


def input_histograms(records: list[dict]) -> None:
    by_attr: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        by_attr[rec.get("attr")].append(rec)

    print("\n## 3. Input histograms (threshold-setting raw inputs)")
    for attr, field, kind in HISTOGRAM_INPUTS:
        values = [
            r["inputs"][field]
            for r in by_attr.get(attr, [])
            if isinstance(r.get("inputs"), dict) and field in r["inputs"]
            and isinstance(r["inputs"][field], (int, float))
        ]
        print(f"\n  {attr}.{field}  (n={len(values)})")
        _histogram(values, is_float=(kind == "float"))


def report_section(title: str, records: list[dict]) -> None:
    print("\n" + "=" * 72)
    print(f"{title}   (team-game-attr rows: {len(records)})")
    print("=" * 72)
    if not records:
        print("  (no rows)")
        return
    week_coverage(records)
    branch_frequency(records)
    saturation(records)
    input_histograms(records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        default=os.environ.get("GOB_EOG_BAND_LOG_FILE", "eog_band_log.jsonl"),
        help="Path to the [EOG-BAND] JSONL file.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Hard-fail (exit 2) if any distant-sim row appears in weeks 1-26 — "
             "those corrupt the six usage-gated attributes' thresholds.",
    )
    args = parser.parse_args()

    if not os.path.exists(args.path):
        print(f"error: file not found: {args.path}", file=sys.stderr)
        return 1

    headers, records = load_records(args.path)
    print(f"# Loaded {len(records)} [EOG-BAND] records from {args.path}")
    print_headers(headers)

    offenders = check_strict_distant(records)
    if offenders:
        weeks = sorted({r["week"] for r in offenders})
        games = sorted({r.get("game_id") for r in offenders})
        msg = (f"{len(offenders)} distant-sim row(s) in weeks 1-26 "
               f"(weeks={weeks}, {len(games)} game(s)) — the six usage-gated "
               f"attributes are GARBAGE for those games. Re-run with "
               f"FRANCHISE_ALL_GAMES_FULL_SIM=1.")
        if args.strict:
            print(f"\n❌ STRICT FAIL: {msg}", file=sys.stderr)
            return 2
        print(f"\n⚠️  {msg}", file=sys.stderr)

    by_distant = split_by_distant(records)
    report_section("LIVE GAMES (is_distant_sim=false)", by_distant[False])
    report_section("DISTANT-SIM GAMES (is_distant_sim=true)", by_distant[True])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
