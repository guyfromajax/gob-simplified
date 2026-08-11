#!/usr/bin/env python3
"""
Dry-run 26 weeks of user Auto-Train + random EOG team-attribute bands.

Read-only: loads one franchise roster from Mongo so execute_training can run,
clones team attributes in memory, and never writes to Mongo.

Season model (confirmed):
  - Start from franchise init ranges (randomized).
  - Each week 1-26: Auto-Train, then one EOG pass (no bye weeks).
  - Week 1 = training camp (30 pts); weeks 2-26 = 24 pts.
  - Each EOG week: random W/L, then for each attribute pick one outcome band
    uniformly at random and roll the delta inside that band.
  - Reports user team_attributes only.

Examples:
  python scripts/team_attr_season_dry_run.py --db gob-staging --seed 42
  python scripts/team_attr_season_dry_run.py --db gob-staging --weeks 26 --seed 7
"""

from __future__ import annotations

import argparse
import copy
import logging
import random
import sys
from pathlib import Path
from typing import Any

from bson import ObjectId


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target


TEAM_ATTR_CLAMPS: dict[str, tuple[Any, Any]] = {}
execute_training = None

UI_AUTO_TRAIN_FOCUS_OPTIONS = [
    "authoritarian-discipline",
    "authoritarian-rebounding",
    "authoritarian-execution",
    "authoritarian-teamwork",
    "systems-coach-offense",
    "systems-coach-defense",
    "systems-coach-fast-breaks",
    "systems-coach-press-trap",
    "player-maximizer-top-3",
    "player-maximizer-attributes-4-6",
    "player-maximizer-positional-focus",
    "culture-builder-inspire",
    "culture-builder-community",
    "culture-builder-teamwork",
    "culture-builder-confidence",
]

TEAM_REPORT_ATTRS = [
    "shot_threshold",
    "discipline",
    "fight",
    "team_chemistry",
    "offensive_efficiency",
    "defensive_efficiency",
    "fb_efficiency",
    "pt_efficiency",
    "fb_opp_modifier",
    "pt_opp_modifier",
    "rebound_modifier",
]

# Band vocabulary imported from the SINGLE source of truth (Task 8) so the harness
# never drifts from production. rebound_modifier bands are stored as cents (int) and
# divided by 100 at roll time, matching eog_attr_rules. NOTE: this random-pick model
# ignores thresholds by design; the concentration/volume attrs now carry atrophy
# bands too, so a uniform pick over-samples atrophy vs the real threshold-gated
# distribution — the harness models a band vocabulary, not the game (use the real
# [EOG-BAND] measurement for distributions).
from BackEnd.constants.eog_attr_bands import (  # noqa: E402
    EOG_BANDS,
    FIGHT_BANDS,
    CHEMISTRY_BANDS,
    ST_FG_45_TO_50_WIN,
    ST_FG_45_TO_50_LOSS,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    parser.add_argument("--franchise-id", help="Franchise _id. Defaults to most recent franchise with FTD rows.")
    parser.add_argument("--user-team", help="Optional user team selector: ObjectId/string id/name/mascot")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--weeks", type=int, default=26, help="Season weeks to simulate")
    parser.add_argument(
        "--verbose-weeks",
        action="store_true",
        help="Print per-week training/EOG deltas",
    )
    return parser.parse_args()


def _oid_or_none(value: Any) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


def _team_label(team_doc: dict | None, fallback: Any = "") -> str:
    if not team_doc:
        return str(fallback)
    name = team_doc.get("name") or team_doc.get("team") or ""
    mascot = team_doc.get("mascot") or ""
    label = f"{name} {mascot}".strip()
    return label or str(team_doc.get("_id") or fallback)


def _find_franchise(db, franchise_id: str | None) -> dict:
    if franchise_id:
        oid = _oid_or_none(franchise_id)
        query = {"_id": oid} if oid else {"_id": franchise_id}
        franchise = db.franchises.find_one(query)
        if not franchise:
            raise SystemExit(f"No franchise found for --franchise-id {franchise_id!r}")
        return franchise

    for franchise in db.franchises.find(sort=[("_id", -1)]):
        if db.franchise_team_data.find_one({"franchise_id": franchise["_id"]}):
            return franchise
    raise SystemExit("No franchise with franchise_team_data rows found")


def _find_team_doc(db, selector: str | None, ftd_docs: list[dict], default_team_oid: Any = None) -> dict | None:
    if selector:
        oid = _oid_or_none(selector)
        queries = []
        if oid:
            queries.append({"_id": oid})
        queries.extend(
            [
                {"_id": selector},
                {"team_id": selector},
                {"name": {"$regex": f"^{selector}$", "$options": "i"}},
                {"mascot": {"$regex": f"^{selector}$", "$options": "i"}},
            ]
        )
        for query in queries:
            doc = db.teams.find_one(query)
            if doc:
                return doc
        raise SystemExit(f"No team found for selector {selector!r}")

    if default_team_oid is not None:
        return db.teams.find_one({"_id": default_team_oid})

    if ftd_docs:
        return db.teams.find_one({"_id": ftd_docs[0].get("team_id")})
    return None


def _find_ftd(ftd_docs: list[dict], team_doc: dict) -> dict:
    team_id = team_doc.get("_id")
    team_id_str = str(team_id)
    for doc in ftd_docs:
        if doc.get("team_id") == team_id or str(doc.get("team_id")) == team_id_str:
            return doc
    raise SystemExit(f"No FTD row found for team {_team_label(team_doc)} ({team_id})")


def _player_order(ftd_doc: dict, team_doc: dict | None) -> list[str]:
    raw = ftd_doc.get("players") or (team_doc or {}).get("player_ids") or []
    return [str(pid) for pid in raw]


def _load_players_for_training(db, franchise_id: ObjectId, ftd_doc: dict, team_doc: dict | None) -> list[dict]:
    player_ids = _player_order(ftd_doc, team_doc)
    fpd_docs = {
        str(doc.get("player_id")): doc
        for doc in db.franchise_players_data.find(
            {"franchise_id": str(franchise_id), "player_id": {"$in": player_ids}}
        )
    }
    core_docs = {
        str(doc["_id"]): doc
        for doc in db.players.find({"_id": {"$in": player_ids}}, {"height": 1, "weight": 1})
    }
    players = []
    for pid in player_ids:
        fpd = fpd_docs.get(pid)
        if not fpd:
            continue
        meta = dict(fpd.get("meta") or {})
        core = core_docs.get(pid) or {}
        if meta.get("height") is None and core.get("height") is not None:
            meta["height"] = core["height"]
        if meta.get("weight") is None and core.get("weight") is not None:
            meta["weight"] = core["weight"]
        players.append(
            {
                "_id": pid,
                "first_name": meta.get("first_name", ""),
                "last_name": meta.get("last_name", ""),
                "team": _team_label(team_doc, ftd_doc.get("team_id")),
                "attributes": copy.deepcopy(fpd.get("attributes") or {}),
                "position_ratings": copy.deepcopy(fpd.get("position_ratings") or {}),
                "year": meta.get("year"),
                "meta": meta,
            }
        )
    return players


def _auto_train_allocations(total_points: int, rng: random.Random) -> dict:
    allocations = {
        "player_drills": {
            "offense": {"inside": 1, "outside": 1},
            "defense": {"inside": 1, "outside": 1},
            "technical": {"passing": 1, "ball_handling": 1, "rebounding": 1},
            "weight_room": {"strength": 1, "agility": 1},
        },
        "team_drills": {
            "team_offense": {"install": 1},
            "team_defense": {"install": 1},
            "fast_breaks": {"offense_install": 1, "defense_install": 1},
            "scrimmages": 1,
            "presses_traps": {"defense_install": 1, "offense_install": 1},
        },
        "general": {"conditioning": 1, "free_throws": 1, "film_study": 1, "breaks": 1},
    }
    sliders = [
        ("player_drills", "offense", "inside"),
        ("player_drills", "offense", "outside"),
        ("player_drills", "defense", "inside"),
        ("player_drills", "defense", "outside"),
        ("player_drills", "technical", "passing"),
        ("player_drills", "technical", "ball_handling"),
        ("player_drills", "technical", "rebounding"),
        ("player_drills", "weight_room", "strength"),
        ("player_drills", "weight_room", "agility"),
        ("team_drills", "team_offense", "install"),
        ("team_drills", "team_defense", "install"),
        ("team_drills", "fast_breaks", "offense_install"),
        ("team_drills", "fast_breaks", "defense_install"),
        ("team_drills", "scrimmages", None),
        ("team_drills", "presses_traps", "defense_install"),
        ("team_drills", "presses_traps", "offense_install"),
        ("general", None, "conditioning"),
        ("general", None, "free_throws"),
        ("general", None, "film_study"),
        ("general", None, "breaks"),
    ]
    rng.shuffle(sliders)
    for category, subcategory, key in sliders[: max(0, total_points - 20)]:
        if category == "team_drills" and subcategory == "scrimmages":
            allocations[category][subcategory] = 2
        elif subcategory is None:
            allocations[category][key] = 2
        else:
            allocations[category][subcategory][key] = 2
    return allocations


def _random_franchise_start_attrs(rng: random.Random) -> dict:
    from BackEnd.constants.shot_threshold_scale import FRANCHISE_INIT_HI, FRANCHISE_INIT_LO

    # Matches TeamManager.init_team_attributes("franchise") ranges, rolled with --seed.
    return {
        "shot_threshold": rng.randint(FRANCHISE_INIT_LO, FRANCHISE_INIT_HI),
        "discipline": rng.randint(-1, 1),
        "fight": rng.randint(-1, 1),
        "rebound_modifier": 0.2,
        "offensive_efficiency": rng.randint(-1, 1),
        "team_chemistry": rng.randint(7, 10),
        "defensive_efficiency": rng.randint(-1, 1),
        "fb_efficiency": rng.randint(-1, 1),
        "pt_efficiency": rng.randint(-1, 1),
        "fb_opp_modifier": rng.randint(-1, 1),
        "pt_opp_modifier": rng.randint(-1, 1),
        "momentum_score": 0,
    }


def _roll_int_range(rng: random.Random, lo: int, hi: int) -> int:
    return rng.randint(lo, hi)


def _roll_float_range(rng: random.Random, lo: float, hi: float) -> float:
    # Match code style used for rebound_modifier (centi-steps).
    lo_cents = int(round(lo * 100))
    hi_cents = int(round(hi * 100))
    if lo_cents > hi_cents:
        lo_cents, hi_cents = hi_cents, lo_cents
    return rng.randint(lo_cents, hi_cents) / 100.0


def _apply_clamp(attr: str, current: Any, delta: Any) -> tuple[Any, Any]:
    lower, upper = TEAM_ATTR_CLAMPS[attr]
    if attr == "rebound_modifier":
        new_val = float(current) + float(delta)
        clamped = max(float(lower), min(float(upper), new_val))
        applied = round(clamped - float(current), 2)
        return round(clamped, 2), applied
    new_val = int(current) + int(delta)
    clamped = max(int(lower), min(int(upper), new_val))
    return clamped, clamped - int(current)


def _roll_eog_deltas(rng: random.Random, is_winner: bool) -> dict[str, Any]:
    """Pick one band per attribute at random, then roll inside that band."""
    changes: dict[str, Any] = {}
    band_labels: dict[str, str] = {}

    for attr, bands in EOG_BANDS.items():
        label, (lo, hi) = rng.choice(bands)
        if attr == "shot_threshold" and label == "fg_45_to_50":
            if is_winner:
                lo, hi = ST_FG_45_TO_50_WIN
            else:
                lo, hi = ST_FG_45_TO_50_LOSS
        if attr == "rebound_modifier":
            # Bands are cents in the config; /100 to the 0.0-1.0 scale.
            changes[attr] = round(_roll_int_range(rng, int(lo), int(hi)) / 100.0, 2)
        else:
            changes[attr] = _roll_int_range(rng, int(lo), int(hi))
        band_labels[attr] = label

    fight_label, (flo, fhi) = FIGHT_BANDS[is_winner]
    changes["fight"] = _roll_int_range(rng, flo, fhi)
    band_labels["fight"] = fight_label

    chem_label, (clo, chi) = rng.choice(CHEMISTRY_BANDS[is_winner])
    changes["team_chemistry"] = _roll_int_range(rng, clo, chi)
    band_labels["team_chemistry"] = chem_label

    changes["_bands"] = band_labels
    return changes


def _snapshot_attrs(attrs: dict) -> dict:
    return {k: copy.deepcopy(attrs.get(k, 0)) for k in TEAM_REPORT_ATTRS}


def _delta_map(before: dict, after: dict) -> dict[str, Any]:
    out = {}
    for attr in TEAM_REPORT_ATTRS:
        b = before.get(attr, 0)
        a = after.get(attr, 0)
        if isinstance(b, float) or isinstance(a, float):
            out[attr] = round(float(a) - float(b), 2)
        else:
            out[attr] = int(a) - int(b)
    return out


def _print_table(title: str, headers: list[str], rows: list[tuple]) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    widths = [len(h) for h in headers]
    str_rows = []
    for row in rows:
        srow = [str(x) for x in row]
        str_rows.append(srow)
        widths = [max(widths[i], len(srow[i])) for i in range(len(headers))]
    print("  ".join(headers[i].ljust(widths[i]) for i in range(len(headers))))
    print("  ".join("-" * widths[i] for i in range(len(headers))))
    for row in str_rows:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))))


def main() -> int:
    global TEAM_ATTR_CLAMPS, execute_training
    args = parse_args()
    logging.getLogger().setLevel(logging.ERROR)

    from BackEnd.models.training_execution_v2 import (  # noqa: WPS433
        TEAM_ATTR_CLAMPS as _TEAM_ATTR_CLAMPS,
        execute_training as _execute_training,
    )

    TEAM_ATTR_CLAMPS = _TEAM_ATTR_CLAMPS
    execute_training = _execute_training

    # Seed both the local RNG and the module global used inside execute_training.
    random.seed(args.seed)
    rng = random.Random(args.seed)

    connection = connect_migration_target(args.db, write=False)
    db = connection.database
    franchise = _find_franchise(db, args.franchise_id)
    franchise_id = franchise["_id"]
    ftd_docs = list(db.franchise_team_data.find({"franchise_id": franchise_id}))
    if not ftd_docs:
        raise SystemExit(f"No FTD rows found for franchise_id={franchise_id}")

    user_default_oid = _oid_or_none(franchise.get("user_team_object_id")) or franchise.get("user_team_object_id")
    user_team = _find_team_doc(db, args.user_team, ftd_docs, default_team_oid=user_default_oid)
    if not user_team:
        raise SystemExit("Could not resolve user team")
    user_ftd = _find_ftd(ftd_docs, user_team)

    players = _load_players_for_training(db, franchise_id, user_ftd, user_team)
    if not players:
        raise SystemExit(f"No FPD players found for user team {_team_label(user_team)}")

    team_attrs = _random_franchise_start_attrs(rng)
    start_attrs = _snapshot_attrs(team_attrs)

    plays_data = copy.deepcopy(user_ftd.get("plays") or {})
    scouting_data = copy.deepcopy(user_ftd.get("scouting_data") or {})
    strategy_settings = copy.deepcopy(user_ftd.get("strategy_settings") or {})
    playbook_settings = copy.deepcopy(user_ftd.get("playbook_settings") or {})

    training_totals = {attr: 0.0 for attr in TEAM_REPORT_ATTRS}
    eog_totals = {attr: 0.0 for attr in TEAM_REPORT_ATTRS}
    wins = 0
    losses = 0
    week_rows: list[tuple] = []

    for week in range(1, args.weeks + 1):
        before_train = _snapshot_attrs(team_attrs)
        total_points = 30 if week == 1 else 24
        allocations = _auto_train_allocations(total_points, rng)
        coaching_focus = rng.choice(UI_AUTO_TRAIN_FOCUS_OPTIONS)
        players, team_attrs, plays_data, scouting_data, _report = execute_training(
            copy.deepcopy(players),
            copy.deepcopy(team_attrs),
            allocations,
            coaching_focus=coaching_focus,
            plays_data=copy.deepcopy(plays_data),
            strategy_settings=copy.deepcopy(strategy_settings),
            playbook_settings=copy.deepcopy(playbook_settings),
            scouting_data=copy.deepcopy(scouting_data),
            playbook_training_mode="current-playbooks",
            skip_pre_training_depreciation=(week == 1),
        )
        after_train = _snapshot_attrs(team_attrs)
        train_delta = _delta_map(before_train, after_train)
        for attr, delta in train_delta.items():
            training_totals[attr] += float(delta)

        is_winner = bool(rng.getrandbits(1))
        if is_winner:
            wins += 1
        else:
            losses += 1

        eog_roll = _roll_eog_deltas(rng, is_winner)
        band_labels = eog_roll.pop("_bands")
        applied_eog: dict[str, Any] = {}
        for attr in TEAM_REPORT_ATTRS:
            if attr not in eog_roll:
                continue
            new_val, applied = _apply_clamp(attr, team_attrs.get(attr, 0), eog_roll[attr])
            team_attrs[attr] = new_val
            applied_eog[attr] = applied
            eog_totals[attr] += float(applied)

        after_eog = _snapshot_attrs(team_attrs)
        if args.verbose_weeks:
            week_rows.append(
                (
                    week,
                    "W" if is_winner else "L",
                    coaching_focus,
                    {k: train_delta[k] for k in TEAM_REPORT_ATTRS},
                    {k: applied_eog.get(k, 0) for k in TEAM_REPORT_ATTRS},
                    {k: band_labels.get(k, "") for k in TEAM_REPORT_ATTRS},
                    after_eog,
                )
            )
        else:
            # keep end-of-week snapshot only for compact summary path
            week_rows.append((week, "W" if is_winner else "L", after_eog))

    end_attrs = _snapshot_attrs(team_attrs)
    net = _delta_map(start_attrs, end_attrs)

    print("READ-ONLY user team-attribute season dry run")
    print(f"Database: {args.db}")
    print(f"Franchise: {franchise_id}")
    print(f"User team roster source: {_team_label(user_team)}")
    print(f"Seed: {args.seed}")
    print(f"Weeks: {args.weeks} (camp week 1 @ 30 pts, then 24 pts; no byes)")
    print(f"Record (random W/L): {wins}-{losses}")
    print("Model: Auto-Train allocations + full-engine EOG outcome bands")

    _print_table(
        "Season Team Attribute Net",
        ["attribute", "start", "end", "net", "training_sum", "eog_sum"],
        [
            (
                attr,
                start_attrs[attr],
                end_attrs[attr],
                net[attr],
                round(training_totals[attr], 2) if attr == "rebound_modifier" else int(round(training_totals[attr])),
                round(eog_totals[attr], 2) if attr == "rebound_modifier" else int(round(eog_totals[attr])),
            )
            for attr in TEAM_REPORT_ATTRS
        ],
    )

    if args.verbose_weeks:
        print("\nPer-week detail")
        print("---------------")
        for week, result, focus, train_delta, eog_delta, bands, after in week_rows:
            print(f"\nWeek {week} | {result} | focus={focus}")
            for attr in TEAM_REPORT_ATTRS:
                print(
                    f"  {attr:22} train={train_delta[attr]:+}  "
                    f"eog[{bands[attr]}]={eog_delta[attr]:+}  "
                    f"end={after[attr]}"
                )
    else:
        _print_table(
            "End-of-Week Snapshot",
            ["week", "result"] + TEAM_REPORT_ATTRS,
            [
                (week, result, *[after[attr] for attr in TEAM_REPORT_ATTRS])
                for week, result, after in week_rows
            ],
        )

    print("\nNotes")
    print("-----")
    print("- shot_threshold is golf-score (lower is better).")
    print("- training_sum / eog_sum are post-clamp applied deltas accumulated each week.")
    print("- rebound_modifier net can differ slightly from training_sum+eog_sum due to rounding.")
    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
