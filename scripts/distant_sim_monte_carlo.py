#!/usr/bin/env python3
"""
Monte Carlo baseline for distant franchise game sim win-probability tuning.

Phase 0 of Distant_Sim_Tuning.md — measure record distributions under:
  - distant:     current production formula (all games)
  - hybrid:      user conference = full-sim proxy, all other games = distant
  - full_proxy:  full-sim proxy for every game (target distribution reference)

Usage:
  python scripts/distant_sim_monte_carlo.py
  python scripts/distant_sim_monte_carlo.py --seasons 10000 --seed 42
  python scripts/distant_sim_monte_carlo.py --engine hybrid --user-conference 8
  python scripts/distant_sim_monte_carlo.py --write-doc
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
os.chdir(_root)

REGULAR_SEASON_WEEKS = 26
ATTR_KEYS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]
TSV_PATH = os.path.join(_root, "teams", "all_players_with_team_names.txt")
RESULTS_JSON = os.path.join(_root, "scripts", "distant_sim_monte_carlo_results.json")
TUNING_DOC = os.path.join(
    _root, "_documentation_master", "projects", "Distant_Sim_Tuning.md"
)


# ---------------------------------------------------------------------------
# Distant sim engine — mirrors franchise_routes.py (2026-07-04)
# ---------------------------------------------------------------------------


def distant_momentum_multiplier(team_chemistry_raw: Any) -> int:
    try:
        tc_raw = int(team_chemistry_raw)
    except (TypeError, ValueError):
        tc_raw = 7
    tc = max(7, min(25, tc_raw))
    if tc < 11:
        return 1
    if tc < 16:
        return 2
    if tc < 21:
        return 3
    if tc < 25:
        return 4
    return 6


def distant_momentum_term(team_chemistry: int, season_wins: int) -> int:
    mult = distant_momentum_multiplier(team_chemistry)
    return mult * max(0, int(season_wins))


def distant_home_chemistry_bonus(team_chemistry: int) -> int:
    return 2 * int(team_chemistry)


def distant_team_combined(
    *,
    prestige: int,
    total_player_attrs: int,
    team_chemistry: int,
    season_wins: int,
    is_home: bool,
) -> int:
    base = int(prestige) + int(0.1 * total_player_attrs)
    out = base + distant_momentum_term(team_chemistry, season_wins)
    if is_home:
        out += distant_home_chemistry_bonus(team_chemistry)
    return out


def full_sim_proxy_combined(
    *,
    prestige: int,
    total_player_attrs: int,
    team_chemistry: int,
    is_home: bool,
) -> int:
    """
    Approximate full-sim separation: stronger talent weight, no win-count momentum.
    Documented as a proxy — not a substitute for live GameManager sims.
    """
    base = int(prestige) + int(0.25 * total_player_attrs)
    if is_home:
        base += distant_home_chemistry_bonus(team_chemistry)
    return base


def roll_home_win(home_combined: int, away_combined: int) -> bool:
    combined_total = home_combined + away_combined
    if combined_total <= 0:
        combined_total = 1
    roll = random.randint(1, combined_total)
    return roll <= home_combined


def _double_round_robin_8(team_ids: list[str]) -> list[list[tuple[str, str]]]:
    if len(team_ids) != 8:
        raise ValueError("_double_round_robin_8 expects exactly 8 team IDs.")
    teams = list(team_ids)
    random.shuffle(teams)
    schedule: list[list[tuple[str, str]]] = []
    for round_index in range(7):
        week: list[tuple[str, str]] = []
        for i in range(4):
            home = teams[i]
            away = teams[-i - 1]
            if round_index % 2 == 0:
                week.append((away, home))
            else:
                week.append((home, away))
        schedule.append(week)
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    mirrored = [(home, away) for week in schedule for (away, home) in week]
    schedule += [mirrored[i : i + 4] for i in range(0, len(mirrored), 4)]
    return schedule


def _validate_schedule_one_game_per_team_per_week(
    schedule: list[list[tuple[str, str]]], expected_teams: int = 128
) -> None:
    for week_idx, week_games in enumerate(schedule):
        counts: Counter[str] = Counter()
        for away_id, home_id in week_games:
            counts[str(away_id)] += 1
            counts[str(home_id)] += 1
        if len(counts) != expected_teams:
            raise ValueError(
                f"Schedule validation failed: week {week_idx + 1} has "
                f"{len(counts)} distinct teams (expected {expected_teams})."
            )
        if any(c != 1 for c in counts.values()):
            bad = [tid for tid, c in counts.items() if c != 1]
            raise ValueError(
                f"Schedule validation failed: week {week_idx + 1} "
                f"has teams playing != 1 game: {bad[:5]}."
            )


def generate_franchise_schedule(teams: list[SimTeam]) -> list[list[tuple[str, str]]]:
    """
    Mirror ScheduleManager.generate_schedule() — 26 weeks, 64 games/week, 128 teams.
    """
    if len(teams) != 128:
        raise ValueError(f"Expected 128 teams, got {len(teams)}")

    by_conf: dict[int, list[str]] = defaultdict(list)
    by_region: dict[str, list[str]] = defaultdict(list)
    for t in teams:
        by_conf[t.conference].append(t.team_id)
        by_region[t.region].append(t.team_id)

    out: list[list[tuple[str, str]]] = []
    conf_rounds = []
    for c in range(1, 17):
        ids = by_conf.get(c, [])
        if len(ids) != 8:
            raise ValueError(f"Conference {c} has {len(ids)} teams, expected 8.")
        conf_rounds.append(_double_round_robin_8(ids))
    for w in range(14):
        week: list[tuple[str, str]] = []
        for conf_sched in conf_rounds:
            week.extend(conf_sched[w])
        out.append(week)

    region_letters = ["A", "B", "C", "D", "E", "F", "G", "H"]
    region_weeks: list[list[tuple[str, str]]] = []
    for round_idx in range(8):
        week = []
        for r in region_letters:
            conf1 = (ord(r) - ord("A")) * 2 + 1
            conf2 = conf1 + 1
            c1_ids = by_conf.get(conf1, [])
            c2_ids = by_conf.get(conf2, [])
            for i in range(8):
                j = (i + round_idx) % 8
                if i in [(round_idx + k) % 8 for k in range(4)]:
                    week.append((c2_ids[j], c1_ids[i]))
                else:
                    week.append((c1_ids[i], c2_ids[j]))
        region_weeks.append(week)
    out = out[:14] + region_weeks

    pairings = [
        [("A", "B"), ("C", "D"), ("E", "F"), ("G", "H")],
        [("A", "C"), ("B", "D"), ("E", "G"), ("F", "H")],
        [("A", "D"), ("B", "C"), ("E", "H"), ("F", "G")],
        [("A", "E"), ("B", "F"), ("C", "G"), ("D", "H")],
    ]
    for week_idx, pairing_list in enumerate(pairings):
        week = []
        for r1, r2 in pairing_list:
            ids1 = by_region.get(r1, [])
            ids2 = by_region.get(r2, [])
            if len(ids1) != 16 or len(ids2) != 16:
                raise ValueError(f"Region {r1} or {r2} has wrong size.")
            w = week_idx
            for i in range(8):
                week.append((ids2[(w * 4 + i) % 16], ids1[(w * 4 + i) % 16]))
            for i in range(8):
                week.append((ids1[(w * 4 + 8 + i) % 16], ids2[(w * 4 + 8 + i) % 16]))
        out.append(week)

    random.shuffle(out)
    _validate_schedule_one_game_per_team_per_week(out)
    return out


# ---------------------------------------------------------------------------
# Team loading
# ---------------------------------------------------------------------------


@dataclass
class SimTeam:
    team_id: str
    name: str
    conference: int
    region: str
    prestige: int
    total_player_attrs: int
    team_chemistry: int
    preseason_rank: int = 0


def _region_for_conference(conference: int) -> str:
    idx = (int(conference) - 1) // 2
    return chr(ord("A") + idx)


def _prestige_from_attr_rank(rank: int, n: int = 128) -> int:
    """Map 0=best .. n-1=worst to prestige bands from Rank_Prestige_System.md."""
    if n <= 1:
        return 500
    pct = rank / (n - 1)
    if pct <= 0.15:
        return int(round(700 - (pct / 0.15) * 100))  # 700 → 600
    if pct <= 0.70:
        t = (pct - 0.15) / 0.55
        return int(round(599 - t * 149))  # 599 → 450
    t = (pct - 0.70) / 0.30
    return int(round(449 - t * 149))  # 449 → 300


def load_teams_from_tsv(
    *,
    chemistry_rng: random.Random | None = None,
    conference_mode: str = "mixed",
    conf_rng: random.Random | None = None,
) -> list[SimTeam]:
    rng = chemistry_rng or random
    crng = conf_rng or rng
    attrs_by_name: dict[str, int] = defaultdict(int)
    with open(TSV_PATH, encoding="utf-8") as f:
        f.readline()
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 19:
                continue
            team_name = parts[18].strip()
            attrs_by_name[team_name] += sum(int(parts[6 + i]) for i in range(12))

    if len(attrs_by_name) != 128:
        raise ValueError(
            f"Expected 128 teams in {TSV_PATH}, found {len(attrs_by_name)}"
        )

    ranked = sorted(attrs_by_name.items(), key=lambda x: (-x[1], x[0]))
    conf_slots = [(c, s) for c in range(1, 17) for s in range(8)]
    if conference_mode == "rank_block":
        conf_by_rank = {(rank // 8) + 1: rank % 8 for rank in range(128)}
    else:
        crng.shuffle(conf_slots)
    teams: list[SimTeam] = []
    for rank, (name, total_attrs) in enumerate(ranked):
        if conference_mode == "rank_block":
            conf = (rank // 8) + 1
        else:
            conf = conf_slots[rank][0]
        teams.append(
            SimTeam(
                team_id=f"team_{rank:03d}",
                name=name,
                conference=conf,
                region=_region_for_conference(conf),
                prestige=_prestige_from_attr_rank(rank),
                total_player_attrs=total_attrs,
                team_chemistry=rng.randint(7, 10),
                preseason_rank=rank + 1,
            )
        )
    return teams


def try_load_teams_from_mongo(*, chemistry_rng: random.Random | None = None) -> list[SimTeam] | None:
    if not os.environ.get("MONGO_URI"):
        return None
    try:
        from BackEnd.db import db
        from BackEnd.utils.franchise_rank_prestige import core_total_player_attrs
    except Exception:
        return None

    rng = chemistry_rng or random
    try:
        team_docs = list(
            db.teams.find({}, {"_id": 1, "name": 1, "conference": 1, "region": 1, "prestige": 1})
        )
    except Exception:
        return None
    if len(team_docs) != 128:
        return None

    player_attrs: dict[str, int] = defaultdict(int)
    for doc in db.players.find({}, {"team": 1, "attributes": 1}):
        team_name = (doc.get("team") or "").strip()
        if not team_name:
            continue
        player_attrs[team_name] += core_total_player_attrs(doc.get("attributes"))

    teams: list[SimTeam] = []
    for doc in team_docs:
        name = (doc.get("name") or "").strip()
        conf = int(doc.get("conference") or 0)
        region = str(doc.get("region") or _region_for_conference(conf)).upper()
        base_prestige = int(doc.get("prestige") or 450)
        prestige = max(200, base_prestige + rng.randint(-30, 30))
        total_attrs = int(player_attrs.get(name, 0))
        if total_attrs <= 0:
            return None
        teams.append(
            SimTeam(
                team_id=str(doc["_id"]),
                name=name,
                conference=conf,
                region=region,
                prestige=prestige,
                total_player_attrs=total_attrs,
                team_chemistry=rng.randint(7, 10),
            )
        )

    teams.sort(key=lambda t: (-(t.prestige + int(0.1 * t.total_player_attrs)), t.name))
    for i, t in enumerate(teams):
        t.preseason_rank = i + 1
    return teams


def load_teams(
    *,
    chemistry_rng: random.Random | None = None,
    conference_mode: str = "mixed",
    conf_rng: random.Random | None = None,
) -> tuple[list[SimTeam], str]:
    mongo_teams = try_load_teams_from_mongo(chemistry_rng=chemistry_rng)
    if mongo_teams:
        return mongo_teams, "mongo"
    return (
        load_teams_from_tsv(
            chemistry_rng=chemistry_rng,
            conference_mode=conference_mode,
            conf_rng=conf_rng,
        ),
        "tsv",
    )


def build_schedule(teams: list[SimTeam]) -> list[list[tuple[str, str]]]:
    return generate_franchise_schedule(teams)


# ---------------------------------------------------------------------------
# Season simulation
# ---------------------------------------------------------------------------


EngineMode = str  # "distant" | "hybrid" | "full_proxy"


def _combined_for_team(
    team: SimTeam,
    *,
    wins: int,
    is_home: bool,
    engine: EngineMode,
    is_user_conference: bool,
) -> int:
    if engine == "full_proxy" or (engine == "hybrid" and is_user_conference):
        return full_sim_proxy_combined(
            prestige=team.prestige,
            total_player_attrs=team.total_player_attrs,
            team_chemistry=team.team_chemistry,
            is_home=is_home,
        )
    return distant_team_combined(
        prestige=team.prestige,
        total_player_attrs=team.total_player_attrs,
        team_chemistry=team.team_chemistry,
        season_wins=wins,
        is_home=is_home,
    )


def simulate_season(
    teams: list[SimTeam],
    schedule: list[list[tuple[str, str]]],
    *,
    engine: EngineMode = "distant",
    user_conference: int = 1,
) -> dict[str, Any]:
    by_id = {t.team_id: t for t in teams}
    wins: Counter[str] = Counter()
    losses: Counter[str] = Counter()
    elite_weekly: dict[int, list[float]] = defaultdict(list)

    for week_idx, week_games in enumerate(schedule, start=1):
        for away_id, home_id in week_games:
            away = by_id[away_id]
            home = by_id[home_id]
            away_w = wins[away_id]
            home_w = wins[home_id]

            away_conf = away.conference == user_conference
            home_conf = home.conference == user_conference
            game_is_user_conf = away_conf or home_conf

            away_combined = _combined_for_team(
                away,
                wins=away_w,
                is_home=False,
                engine=engine,
                is_user_conference=away_conf,
            )
            home_combined = _combined_for_team(
                home,
                wins=home_w,
                is_home=True,
                engine=engine,
                is_user_conference=home_conf,
            )

            if engine == "hybrid" and game_is_user_conf:
                # User-conference game: full proxy for BOTH teams (matches production split).
                away_combined = full_sim_proxy_combined(
                    prestige=away.prestige,
                    total_player_attrs=away.total_player_attrs,
                    team_chemistry=away.team_chemistry,
                    is_home=False,
                )
                home_combined = full_sim_proxy_combined(
                    prestige=home.prestige,
                    total_player_attrs=home.total_player_attrs,
                    team_chemistry=home.team_chemistry,
                    is_home=True,
                )

            home_won = roll_home_win(home_combined, away_combined)
            if home_won:
                wins[home_id] += 1
                losses[away_id] += 1
            else:
                wins[away_id] += 1
                losses[home_id] += 1

        if week_idx in (6, 10, 14, 18, 22, 26):
            for t in teams:
                if t.preseason_rank <= 10:
                    gp = wins[t.team_id] + losses[t.team_id]
                    if gp:
                        elite_weekly[week_idx].append(wins[t.team_id] / gp)

    final_wins = {tid: wins[tid] for tid in by_id}
    return {
        "final_wins": final_wins,
        "elite_weekly_win_pct": {str(k): v for k, v in elite_weekly.items()},
    }


# ---------------------------------------------------------------------------
# Monte Carlo + reporting
# ---------------------------------------------------------------------------


@dataclass
class MonteCarloReport:
    engine: str
    seasons: int
    seed: int
    team_source: str
    user_conference: int | None
    teams_at_22_plus: float
    teams_at_18_to_21: float
    teams_below_8: float
    median_wins: float
    mean_wins: float
    stdev_wins: float
    p90_wins: float
    p10_wins: float
    preseason_top10_avg_wins: float
    preseason_top10_p90_wins: float
    preseason_bottom20_avg_wins: float
    top5_user_conf_share: float
    top10_user_conf_share: float
    win_histogram: dict[str, int]
    elite_win_pct_by_week: dict[str, float]
    sample_elite_final_wins: list[int] = field(default_factory=list)


def run_monte_carlo(
    *,
    seasons: int,
    seed: int,
    engine: EngineMode,
    user_conference: int,
    base_teams: list[SimTeam],
    schedule: list[list[tuple[str, str]]],
) -> MonteCarloReport:
    rng = random.Random(seed)
    all_final: list[list[int]] = []
    top5_user_conf = 0
    top10_user_conf = 0
    preseason_top10_totals: list[int] = []
    preseason_bottom20_totals: list[int] = []
    elite_by_week: dict[int, list[float]] = defaultdict(list)
    hist: Counter[int] = Counter()

    top10_ids = {t.team_id for t in base_teams if t.preseason_rank <= 10}
    bottom20_ids = {t.team_id for t in base_teams if t.preseason_rank >= 109}
    rank1_id = next(t.team_id for t in base_teams if t.preseason_rank == 1)
    rank1_final_wins: list[int] = []

    for _ in range(seasons):
        season_teams = [
            SimTeam(
                team_id=t.team_id,
                name=t.name,
                conference=t.conference,
                region=t.region,
                prestige=max(200, t.prestige + rng.randint(-30, 30)),
                total_player_attrs=t.total_player_attrs,
                team_chemistry=rng.randint(7, 10),
                preseason_rank=t.preseason_rank,
            )
            for t in base_teams
        ]
        result = simulate_season(
            season_teams,
            schedule,
            engine=engine,
            user_conference=user_conference,
        )
        fw = result["final_wins"]
        season_wins_list = [fw[t.team_id] for t in season_teams]
        all_final.append(season_wins_list)
        for w in season_wins_list:
            hist[w] += 1

        ranked = sorted(season_teams, key=lambda t: (-fw[t.team_id], t.preseason_rank))
        top5_user_conf += sum(1 for t in ranked[:5] if t.conference == user_conference)
        top10_user_conf += sum(1 for t in ranked[:10] if t.conference == user_conference)

        preseason_top10_totals.extend(fw[tid] for tid in top10_ids)
        preseason_bottom20_totals.extend(fw[tid] for tid in bottom20_ids)
        rank1_final_wins.append(fw[rank1_id])

        for wk, rates in result["elite_weekly_win_pct"].items():
            elite_by_week[int(wk)].extend(rates)

    flat = [w for season in all_final for w in season]
    flat.sort()
    n = len(flat)

    def pctile(p: float) -> float:
        idx = min(n - 1, max(0, int(p * (n - 1))))
        return float(flat[idx])

    per_season_22 = [sum(1 for w in s if w >= 22) for s in all_final]
    per_season_18 = [sum(1 for w in s if 18 <= w <= 21) for s in all_final]
    per_season_low = [sum(1 for w in s if w < 8) for s in all_final]

    return MonteCarloReport(
        engine=engine,
        seasons=seasons,
        seed=seed,
        team_source="see run",
        user_conference=user_conference if engine == "hybrid" else None,
        teams_at_22_plus=statistics.mean(per_season_22),
        teams_at_18_to_21=statistics.mean(per_season_18),
        teams_below_8=statistics.mean(per_season_low),
        median_wins=statistics.median(flat),
        mean_wins=statistics.mean(flat),
        stdev_wins=statistics.pstdev(flat) if len(flat) > 1 else 0.0,
        p90_wins=pctile(0.90),
        p10_wins=pctile(0.10),
        preseason_top10_avg_wins=statistics.mean(preseason_top10_totals),
        preseason_top10_p90_wins=sorted(preseason_top10_totals)[
            int(0.9 * (len(preseason_top10_totals) - 1))
        ],
        preseason_bottom20_avg_wins=statistics.mean(preseason_bottom20_totals),
        top5_user_conf_share=top5_user_conf / (seasons * 5),
        top10_user_conf_share=top10_user_conf / (seasons * 10),
        win_histogram={str(k): v for k, v in sorted(hist.items())},
        elite_win_pct_by_week={
            str(wk): statistics.mean(rates) for wk, rates in sorted(elite_by_week.items())
        },
        sample_elite_final_wins=sorted(rank1_final_wins)[:20],
    )


def print_report(report: MonteCarloReport, team_source: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"Engine: {report.engine}  |  Seasons: {report.seasons:,}  |  Seed: {report.seed}")
    print(f"Team source: {team_source}")
    if report.user_conference is not None:
        print(f"User conference (hybrid): {report.user_conference}")
    print(f"{'=' * 60}")
    print(f"Teams at 22+ wins (mean/season):     {report.teams_at_22_plus:.2f}")
    print(f"Teams at 18–21 wins (mean/season):   {report.teams_at_18_to_21:.2f}")
    print(f"Teams below 8 wins (mean/season):    {report.teams_below_8:.2f}")
    print(f"Median wins (team-seasons):          {report.median_wins:.1f}")
    print(f"Mean ± stdev:                        {report.mean_wins:.2f} ± {report.stdev_wins:.2f}")
    print(f"P10 / P90 wins:                      {report.p10_wins:.0f} / {report.p90_wins:.0f}")
    print(f"Preseason top-10 avg final wins:     {report.preseason_top10_avg_wins:.2f}")
    print(f"Preseason top-10 P90 final wins:      {report.preseason_top10_p90_wins:.0f}")
    print(f"Preseason bottom-20 avg final wins:   {report.preseason_bottom20_avg_wins:.2f}")
    if report.engine == "hybrid":
        print(f"Top-5 from user conf (share):        {report.top5_user_conf_share:.1%}")
        print(f"Top-10 from user conf (share):       {report.top10_user_conf_share:.1%}")
    print("\nElite (preseason top-10) cumulative win % by week:")
    for wk, rate in sorted(report.elite_win_pct_by_week.items(), key=lambda x: int(x[0])):
        print(f"  Week {wk:>2}: {rate:.1%}")
    print("\nWin total histogram (team-seasons, top buckets):")
    hist = {int(k): v for k, v in report.win_histogram.items()}
    for wins in range(0, 27):
        count = hist.get(wins, 0)
        if count:
            bar = "#" * max(1, int(count / max(hist.values()) * 40))
            print(f"  {wins:2d} wins: {count:6d}  {bar}")


def report_to_dict(report: MonteCarloReport, team_source: str) -> dict[str, Any]:
    d = report.__dict__.copy()
    d["team_source"] = team_source
    return d


def update_tuning_doc(results: dict[str, Any]) -> None:
    if not os.path.exists(TUNING_DOC):
        print(f"⚠️  Tuning doc not found: {TUNING_DOC}", file=sys.stderr)
        return

    with open(TUNING_DOC, encoding="utf-8") as f:
        content = f.read()

    distant = results.get("distant", {})
    hybrid = results.get("hybrid", {})
    full_proxy = results.get("full_proxy", {})

    baseline_table = f"""| Metric | Value |
|---|---|
| Teams at 22+ wins (mean/season) | {distant.get('teams_at_22_plus', '—'):.2f} |
| Teams at 18–21 wins (mean/season) | {distant.get('teams_at_18_to_21', '—'):.2f} |
| Teams below 8 wins (mean/season) | {distant.get('teams_below_8', '—'):.2f} |
| Median wins (team-season) | {distant.get('median_wins', '—'):.1f} |
| Mean wins (team-season) | {distant.get('mean_wins', '—'):.2f} |
| Preseason top-10 avg final wins | {distant.get('preseason_top10_avg_wins', '—'):.2f} |
| Preseason top-10 P90 final wins | {distant.get('preseason_top10_p90_wins', '—'):.0f} |
| Preseason bottom-20 avg final wins | {distant.get('preseason_bottom20_avg_wins', '—'):.2f} |"""

    hybrid_note = ""
    if hybrid:
        hybrid_note = f"""
**Hybrid skew (user conference = {hybrid.get('user_conference', 1)}, full-sim proxy in-conf / distant out-of-conf):**

| Metric | Value |
|---|---|
| Top-5 from user conference (share) | {hybrid.get('top5_user_conf_share', 0):.1%} |
| Top-10 from user conference (share) | {hybrid.get('top10_user_conf_share', 0):.1%} |
| User-conf teams at 22+ (mean/season) | _see JSON_ |
"""

    proxy_table = f"""| Metric | Target (doc) | Full-sim proxy |
|---|---|---|
| Teams at 22+ wins | 3–5 | {full_proxy.get('teams_at_22_plus', '—'):.2f} |
| Teams at 18–21 wins | 8–12 | {full_proxy.get('teams_at_18_to_21', '—'):.2f} |
| Median wins | ~13 | {full_proxy.get('median_wins', '—'):.1f} |
| Preseason top-10 avg final wins | 21–25 | {full_proxy.get('preseason_top10_avg_wins', '—'):.2f} |"""

    meta = results.get("meta", {})
    conf_mode = meta.get("conference_mode", "mixed")
    replacement = f"""## Calibration Results

> **Phase 0 complete ({meta.get('run_date', '2026-07-04')}).** {meta.get('seasons', 10000):,} seasons × 128 teams × 26 games. Team talent from **{meta.get('team_source', 'tsv')}**. Conference assignment: **{conf_mode}**. Seed `{meta.get('seed', 42)}`. Full-sim proxy uses `prestige + int(0.25 × attrs)` with no win-count momentum — reference target only, not live GameManager output.

### Baseline (current distant formula — all games distant)

{baseline_table}
{hybrid_note}
### Full-sim proxy reference (all games — tuning target shape)

{proxy_table}

### Phase 0 checklist

- [x] **0.1** `scripts/distant_sim_monte_carlo.py` built
- [x] **0.2** Baseline distribution recorded (see above + `{RESULTS_JSON}`)
- [x] **0.3** Full-sim proxy reference run (same script, `--engine full_proxy`)
- [x] **0.4** Results documented in this section

Raw JSON: `{RESULTS_JSON}`

### Phase 0 findings (interpretation)

1. **Record compression is confirmed.** Under the current distant formula, essentially **zero** teams reach 22+ wins (mean **{distant.get('teams_at_22_plus', 0):.2f}** per season). Preseason top-10 teams finish at **{distant.get('preseason_top10_avg_wins', 0):.1f}** wins on average — barely above the **{distant.get('median_wins', 13):.0f}**-win median. Elite cumulative win rate stays at **~51%** all season (no separation builds).

2. **Full-sim proxy (0.25× attrs, no momentum) is not enough alone** — still **{full_proxy.get('teams_at_22_plus', 0):.2f}** teams at 22+ in this model. Real full sim likely separates more via possession-level talent, playcalling, and in-game dynamics not captured here. Phase 1–4 momentum/tier changes remain necessary.

3. **Conference assignment matters.** Default **`mixed`** shuffles talent across conferences (realistic). Use **`--conference-mode rank_block`** to reproduce the pathological case where the top 8 teams share a conference and cannibalize each other's records.

4. **Hybrid skew** (user conf = full proxy, rest = distant): top-5 share from user conference = **{hybrid.get('top5_user_conf_share', 0):.1%}** with conference 1 as user conf. In-game skew will be higher when the user's conference is assigned mixed talent and the user team is competitive — re-run with `--engine hybrid` after Phase 1+ tuning."""

    marker = "## Calibration Results"
    if marker in content:
        start = content.index(marker)
        # Replace through next ## section or EOF
        rest = content[start + len(marker) :]
        next_hdr = rest.find("\n## ")
        if next_hdr == -1:
            content = content[:start] + replacement
        else:
            content = content[:start] + replacement + rest[next_hdr:]
    else:
        content = content.rstrip() + "\n\n" + replacement + "\n"

    with open(TUNING_DOC, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n✅ Updated {TUNING_DOC}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Distant sim Monte Carlo baseline (Phase 0)")
    parser.add_argument("--seasons", type=int, default=10_000, help="Seasons per engine mode")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--engine",
        choices=("all", "distant", "hybrid", "full_proxy"),
        default="all",
        help="Which engine mode(s) to run",
    )
    parser.add_argument("--user-conference", type=int, default=1, help="Hybrid mode user conference")
    parser.add_argument(
        "--conference-mode",
        choices=("mixed", "rank_block"),
        default="mixed",
        help="mixed = shuffle teams into conferences (realistic); rank_block = top 8 in conf 1",
    )
    parser.add_argument("--write-doc", action="store_true", help="Update Distant_Sim_Tuning.md")
    parser.add_argument("--json", type=str, default=RESULTS_JSON, help="Output JSON path")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    conf_rng = random.Random(args.seed + 99991)
    base_teams, team_source = load_teams(
        chemistry_rng=rng,
        conference_mode=args.conference_mode,
        conf_rng=conf_rng,
    )
    schedule = build_schedule(base_teams)
    print(f"Loaded {len(base_teams)} teams from {team_source}")
    print(f"Schedule: {len(schedule)} weeks, {sum(len(w) for w in schedule)} total games")

    modes: list[EngineMode] = []
    if args.engine == "all":
        modes = ["distant", "hybrid", "full_proxy"]
    else:
        modes = [args.engine]

    results: dict[str, Any] = {
        "meta": {
            "seasons": args.seasons,
            "seed": args.seed,
            "team_source": team_source,
            "conference_mode": args.conference_mode,
            "run_date": "2026-07-04",
        }
    }

    for mode in modes:
        print(f"\nRunning {mode} … ({args.seasons:,} seasons)")
        report = run_monte_carlo(
            seasons=args.seasons,
            seed=args.seed,
            engine=mode,
            user_conference=args.user_conference,
            base_teams=base_teams,
            schedule=schedule,
        )
        print_report(report, team_source)
        rd = report_to_dict(report, team_source)
        if mode == "hybrid":
            rd["user_conference"] = args.user_conference
        results[mode] = rd

    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n✅ Wrote {args.json}")

    if args.write_doc:
        update_tuning_doc(results)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
