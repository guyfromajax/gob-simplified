#!/usr/bin/env python3
"""
Dry-run 26 weeks of user auto-training versus CPU distant training.

This script reads one franchise snapshot from Mongo, clones the selected user
team and CPU team in memory, simulates training weeks 1-26, and prints deltas.
It does not write to Mongo.

Examples:
  python scripts/training_delta_dry_run.py --db gob-staging
  python scripts/training_delta_dry_run.py --db gob-staging --franchise-id 64... --cpu-team "Providence"
  python scripts/training_delta_dry_run.py --db gob --user-team "Lancaster" --cpu-team "Providence" --seed 7
"""

from __future__ import annotations

import argparse
import copy
import logging
import os
import random
import sys
from pathlib import Path
from statistics import mean
from typing import Any

from bson import ObjectId
from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def _load_env(filepath: Path) -> None:
    if not filepath.exists():
        return
    for line in filepath.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


for env_path in (ROOT / ".env.local", ROOT / ".env"):
    _load_env(env_path)


PLAYER_ATTR_CLAMP = (1, None)
TEAM_ATTR_CLAMPS: dict[str, tuple[Any, Any]] = {}
TRAINABLE_PLAYER_ATTRS: list[str] = []
execute_training = None
compute_position_ratings = None


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=os.environ.get("MONGO_DB_NAME", "gob-staging"), help="Mongo database name")
    parser.add_argument("--franchise-id", help="Franchise _id. Defaults to most recent franchise with FTD rows.")
    parser.add_argument("--user-team", help="Optional user team selector: ObjectId/string id/name/mascot")
    parser.add_argument("--cpu-team", help="Optional CPU team selector: ObjectId/string id/name/mascot")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible auto-training/template picks")
    parser.add_argument("--weeks", type=int, default=26, help="Training weeks to simulate")
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
        query: dict[str, Any]
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


def _recompute_player_ratings(players: list[dict]) -> None:
    for player in players:
        meta = player.get("meta") or {}
        player_for_ratings = {
            "attributes": player.get("attributes") or {},
            "height": meta.get("height"),
            "name": f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(),
        }
        player["position_ratings"] = compute_position_ratings(player_for_ratings)


def _simulate_user_training(
    players: list[dict],
    team_attrs: dict,
    ftd_doc: dict,
    rng: random.Random,
    weeks: int,
) -> tuple[list[dict], dict, dict, dict]:
    plays_data = copy.deepcopy(ftd_doc.get("plays") or {})
    scouting_data = copy.deepcopy(ftd_doc.get("scouting_data") or {})
    strategy_settings = copy.deepcopy(ftd_doc.get("strategy_settings") or {})
    playbook_settings = copy.deepcopy(ftd_doc.get("playbook_settings") or {})

    for week in range(1, weeks + 1):
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
        _recompute_player_ratings(players)
    return players, team_attrs, plays_data, scouting_data


def _simulate_cpu_distant_training(
    db,
    players: list[dict],
    team_attrs: dict,
    rng: random.Random,
    weeks: int,
) -> tuple[list[dict], dict]:
    templates_by_type = {
        "tc": list(db.distant_training.find({"training_type": "tc"})),
        "regular": list(db.distant_training.find({"training_type": "regular"})),
    }
    if not templates_by_type["tc"]:
        raise SystemExit("No distant_training templates found for training_type='tc'")
    if not templates_by_type["regular"]:
        raise SystemExit("No distant_training templates found for training_type='regular'")

    players_by_id = {str(player["_id"]): player for player in players}
    player_order = [str(player["_id"]) for player in players]

    for week in range(1, weeks + 1):
        training_type = "tc" if week == 1 else "regular"
        template = copy.deepcopy(rng.choice(templates_by_type[training_type]))
        for attr_name, delta in (template.get("team_values") or {}).items():
            if attr_name not in TEAM_ATTR_CLAMPS or not isinstance(delta, (int, float)):
                continue
            current = team_attrs.get(attr_name, 0)
            if not isinstance(current, (int, float)):
                continue
            lower, upper = TEAM_ATTR_CLAMPS[attr_name]
            delta_val = float(delta) if attr_name == "rebound_modifier" else int(delta)
            new_val = current + delta_val
            if upper is not None:
                new_val = max(lower, min(upper, new_val))
            else:
                new_val = max(lower, new_val)
            team_attrs[attr_name] = round(new_val, 2) if attr_name == "rebound_modifier" else int(round(new_val))

        players_template = template.get("players") or {}
        for i, pid in enumerate(player_order[:12]):
            player = players_by_id.get(pid)
            deltas = players_template.get(f"player_{i}") or {}
            if not player or not isinstance(deltas, dict):
                continue
            attrs = player.setdefault("attributes", {})
            for attr_name, delta in deltas.items():
                if not isinstance(delta, (int, float)):
                    continue
                current = attrs.get(attr_name, attrs.get(f"anchor_{attr_name}", 0))
                try:
                    cur = int(current) if isinstance(current, (int, float)) else 0
                except (TypeError, ValueError):
                    cur = 0
                new_val = max(PLAYER_ATTR_CLAMP[0], cur + int(delta))
                attrs[attr_name] = new_val
                attrs[f"anchor_{attr_name}"] = new_val
        _recompute_player_ratings(players)
    return players, team_attrs


def _team_attr_delta(start: dict, end: dict) -> list[tuple[str, Any, Any, Any]]:
    rows = []
    for attr in TEAM_REPORT_ATTRS:
        if attr not in start and attr not in end:
            continue
        before = start.get(attr, 0)
        after = end.get(attr, 0)
        delta = round(after - before, 2) if isinstance(before, float) or isinstance(after, float) else after - before
        rows.append((attr, before, after, delta))
    return rows


def _avg(values: list[float]) -> float:
    return round(mean(values), 2) if values else 0.0


def _player_attr_summary(start_players: list[dict], end_players: list[dict]) -> list[tuple[str, float, float, float]]:
    start_by_id = {str(p["_id"]): p for p in start_players}
    end_by_id = {str(p["_id"]): p for p in end_players}
    rows = []
    for attr in TRAINABLE_PLAYER_ATTRS:
        before_vals = []
        after_vals = []
        for pid, start_player in start_by_id.items():
            end_player = end_by_id.get(pid)
            if not end_player:
                continue
            before_vals.append(float((start_player.get("attributes") or {}).get(attr, 0) or 0))
            after_vals.append(float((end_player.get("attributes") or {}).get(attr, 0) or 0))
        before = _avg(before_vals)
        after = _avg(after_vals)
        rows.append((attr, before, after, round(after - before, 2)))
    return rows


def _rating_summary(start_players: list[dict], end_players: list[dict]) -> list[tuple[str, float, float, float]]:
    start_by_id = {str(p["_id"]): p for p in start_players}
    end_by_id = {str(p["_id"]): p for p in end_players}
    rows = []
    for pos in ["PG", "SG", "SF", "PF", "C", "overall"]:
        before_vals = []
        after_vals = []
        for pid, start_player in start_by_id.items():
            end_player = end_by_id.get(pid)
            if not end_player:
                continue
            if pos == "overall":
                before_vals.append(float((start_player.get("position_ratings") or {}).get("overall", 0) or 0))
                after_vals.append(float((end_player.get("position_ratings") or {}).get("overall", 0) or 0))
            else:
                before_vals.append(float((start_player.get("position_ratings") or {}).get(pos, 0) or 0))
                after_vals.append(float((end_player.get("position_ratings") or {}).get(pos, 0) or 0))
        before = _avg(before_vals)
        after = _avg(after_vals)
        rows.append((pos, before, after, round(after - before, 2)))
    return rows


def _effectiveness_values(block: Any) -> list[float]:
    vals = []
    if isinstance(block, dict):
        for value in block.values():
            if isinstance(value, dict):
                eff = value.get("effectiveness")
                if isinstance(eff, (int, float)):
                    vals.append(float(eff))
    return vals


def _total_player_attr_gain(start_players: list[dict], end_players: list[dict]) -> float:
    start_by_id = {str(p["_id"]): p for p in start_players}
    end_by_id = {str(p["_id"]): p for p in end_players}
    total = 0.0
    for pid, start_player in start_by_id.items():
        end_player = end_by_id.get(pid)
        if not end_player:
            continue
        start_attrs = start_player.get("attributes") or {}
        end_attrs = end_player.get("attributes") or {}
        for attr in TRAINABLE_PLAYER_ATTRS:
            total += float(end_attrs.get(attr, 0) or 0) - float(start_attrs.get(attr, 0) or 0)
    return round(total, 2)


def _total_team_attr_gain(start: dict, end: dict) -> float:
    total = 0.0
    for attr in TEAM_REPORT_ATTRS:
        before = start.get(attr, 0)
        after = end.get(attr, 0)
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            total += float(after) - float(before)
    return round(total, 2)


def _position_rating_gain_sum(start_players: list[dict], end_players: list[dict]) -> float:
    return round(sum(row[3] for row in _rating_summary(start_players, end_players) if row[0] != "overall"), 2)


def _total_effectiveness_gain(start_values: list[float], end_values: list[float]) -> float:
    return round(sum(end_values) - sum(start_values), 2)


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
    global PLAYER_ATTR_CLAMP, TEAM_ATTR_CLAMPS, TRAINABLE_PLAYER_ATTRS, execute_training, compute_position_ratings
    args = parse_args()
    logging.getLogger().setLevel(logging.ERROR)

    from BackEnd.models.training_execution_v2 import (  # noqa: WPS433
        PLAYER_ATTR_CLAMP as _PLAYER_ATTR_CLAMP,
        TEAM_ATTR_CLAMPS as _TEAM_ATTR_CLAMPS,
        TRAINABLE_PLAYER_ATTRS as _TRAINABLE_PLAYER_ATTRS,
        execute_training as _execute_training,
    )
    from BackEnd.utils.position_ratings import compute_position_ratings as _compute_position_ratings  # noqa: WPS433

    PLAYER_ATTR_CLAMP = _PLAYER_ATTR_CLAMP
    TEAM_ATTR_CLAMPS = _TEAM_ATTR_CLAMPS
    TRAINABLE_PLAYER_ATTRS = _TRAINABLE_PLAYER_ATTRS
    execute_training = _execute_training
    compute_position_ratings = _compute_position_ratings

    rng = random.Random(args.seed)

    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("MONGO_URI not set. Add it to .env.local/.env or export it.", file=sys.stderr)
        return 1

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[args.db]
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

    cpu_candidates = [doc for doc in ftd_docs if str(doc.get("team_id")) != str(user_team.get("_id"))]
    cpu_team = _find_team_doc(db, args.cpu_team, cpu_candidates)
    if not cpu_team:
        raise SystemExit("Could not resolve CPU team")
    cpu_ftd = _find_ftd(ftd_docs, cpu_team)

    user_start_players = _load_players_for_training(db, franchise_id, user_ftd, user_team)
    cpu_start_players = _load_players_for_training(db, franchise_id, cpu_ftd, cpu_team)
    if not user_start_players:
        raise SystemExit(f"No FPD players found for user team {_team_label(user_team)}")
    if not cpu_start_players:
        raise SystemExit(f"No FPD players found for CPU team {_team_label(cpu_team)}")

    user_start_team = copy.deepcopy(user_ftd.get("team_attributes") or {})
    cpu_start_team = copy.deepcopy(cpu_ftd.get("team_attributes") or {})

    user_end_players, user_end_team, user_end_plays, user_end_scouting = _simulate_user_training(
        copy.deepcopy(user_start_players),
        copy.deepcopy(user_start_team),
        copy.deepcopy(user_ftd),
        rng,
        args.weeks,
    )
    cpu_end_players, cpu_end_team = _simulate_cpu_distant_training(
        db,
        copy.deepcopy(cpu_start_players),
        copy.deepcopy(cpu_start_team),
        rng,
        args.weeks,
    )

    print("READ-ONLY training delta dry run")
    print(f"Database: {args.db}")
    print(f"Franchise: {franchise_id}")
    print(f"Seed: {args.seed}")
    print(f"Weeks simulated: {args.weeks}")
    print(f"User team: {_team_label(user_team)} ({user_team.get('_id')})")
    print(f"CPU team:  {_team_label(cpu_team)} ({cpu_team.get('_id')})")
    print("\nNo Mongo writes were performed.")

    start_play_eff = _effectiveness_values(user_ftd.get("plays") or {})
    end_play_eff = _effectiveness_values(user_end_plays)
    start_def_eff = _effectiveness_values((user_ftd.get("scouting_data") or {}).get("defense") or {})
    end_def_eff = _effectiveness_values((user_end_scouting or {}).get("defense") or {})
    user_player_attr_gain = _total_player_attr_gain(user_start_players, user_end_players)
    cpu_player_attr_gain = _total_player_attr_gain(cpu_start_players, cpu_end_players)
    user_play_gain = _total_effectiveness_gain(start_play_eff, end_play_eff)
    user_def_gain = _total_effectiveness_gain(start_def_eff, end_def_eff)
    _print_table(
        "Full-Season Side-by-Side Totals",
        ["bucket", "user_auto_train", "cpu_distant_training", "note"],
        [
            (
                "roster_player_attr_total_gain",
                user_player_attr_gain,
                cpu_player_attr_gain,
                "sum of all trainable attr deltas across roster",
            ),
            (
                "roster_player_attr_avg_gain_per_player",
                round(user_player_attr_gain / max(1, len(user_start_players)), 2),
                round(cpu_player_attr_gain / max(1, len(cpu_start_players)), 2),
                "total attr gain divided by loaded roster size",
            ),
            (
                "team_attr_total_gain",
                _total_team_attr_gain(user_start_team, user_end_team),
                _total_team_attr_gain(cpu_start_team, cpu_end_team),
                "sum of reported numeric team attr deltas",
            ),
            (
                "position_rating_avg_delta_sum",
                _position_rating_gain_sum(user_start_players, user_end_players),
                _position_rating_gain_sum(cpu_start_players, cpu_end_players),
                "sum of average PG/SG/SF/PF/C rating deltas",
            ),
            (
                "offensive_play_effectiveness_total_gain",
                user_play_gain,
                "n/a",
                "CPU distant training does not train plays",
            ),
            (
                "defensive_row_effectiveness_total_gain",
                user_def_gain,
                "n/a",
                "CPU distant training does not train scouting rows",
            ),
            (
                "combined_play_def_effectiveness_total_gain",
                round(user_play_gain + user_def_gain, 2),
                "n/a",
                "user-only trainable surface",
            ),
        ],
    )

    _print_table("User Team Attribute Deltas", ["attr", "before", "after", "delta"], _team_attr_delta(user_start_team, user_end_team))
    _print_table("CPU Team Attribute Deltas", ["attr", "before", "after", "delta"], _team_attr_delta(cpu_start_team, cpu_end_team))
    _print_table("User Avg Player Attribute Deltas", ["attr", "before", "after", "delta"], _player_attr_summary(user_start_players, user_end_players))
    _print_table("CPU Avg Player Attribute Deltas", ["attr", "before", "after", "delta"], _player_attr_summary(cpu_start_players, cpu_end_players))
    _print_table("User Avg Position Rating Deltas", ["rating", "before", "after", "delta"], _rating_summary(user_start_players, user_end_players))
    _print_table("CPU Avg Position Rating Deltas", ["rating", "before", "after", "delta"], _rating_summary(cpu_start_players, cpu_end_players))

    _print_table(
        "User Play/Defense Effectiveness Deltas",
        ["bucket", "before_avg", "after_avg", "delta"],
        [
            ("offense_plays", _avg(start_play_eff), _avg(end_play_eff), round(_avg(end_play_eff) - _avg(start_play_eff), 2)),
            ("defense_rows", _avg(start_def_eff), _avg(end_def_eff), round(_avg(end_def_eff) - _avg(start_def_eff), 2)),
            ("cpu_distant_training", "n/a", "n/a", "does_not_train_plays_or_scouting"),
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
