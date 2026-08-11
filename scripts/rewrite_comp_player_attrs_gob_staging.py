#!/usr/bin/env python3
"""
Rewrite comp player profile attributes on gob-staging (conferences 2–16).

Uses players_backup for pre-rewrite RT position assignment. Preserves each
player's core-12 sum, height, weight, and year. Does NOT touch the gob database.

Run from repo root:
  .venv/bin/python scripts/rewrite_comp_player_attrs_gob_staging.py --dry-run
  .venv/bin/python scripts/rewrite_comp_player_attrs_gob_staging.py --yes
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import random

from pymongo import UpdateOne

from BackEnd.script_db import STAGING_DB, ScriptDatabaseError, connect_script_database
from BackEnd.utils.position_ratings import compute_position_ratings

DB_NAME = STAGING_DB
RANDOM_SEED = 42

PROFILE_ATTRS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]
POSITIONS = ["PG", "SG", "SF", "PF", "C"]

# Percentile counts on the 1,440-player rewrite pool (conf 2–16).
FIVE_STAR_COUNT = 14
FOUR_STAR_COUNT = 58
TIER5_AVERAGE_COUNT = 101   # top 7% of 1440 ≈ top 35% of tier 5
TIER4_AVERAGE_COUNT = 86    # bottom 6% of 1440 ≈ bottom 30% of tier 4
TIER_SIZE = 288             # 1440 / 5

BAND_BY_TIER = {
    1: "Top 20%",
    2: "61–80",
    3: "41–60",
    4: "21–40",
    5: "Bottom 20%",
}

BAND_TIER_RANGES: dict[str, dict[str, tuple[int, int]]] = {
    "Top 20%": {
        "STRONG": (65, 90),
        "SECONDARY": (45, 79),
        "STANDARD": (1, 65),
        "WEAK": (1, 44),
    },
    "61–80": {
        "STRONG": (45, 70),
        "SECONDARY": (35, 55),
        "STANDARD": (1, 45),
        "WEAK": (1, 35),
    },
    "41–60": {
        "STRONG": (40, 60),
        "SECONDARY": (32, 47),
        "STANDARD": (1, 40),
        "WEAK": (1, 29),
    },
    "21–40": {
        "STRONG": (31, 50),
        "SECONDARY": (25, 37),
        "STANDARD": (1, 31),
        "WEAK": (1, 21),
    },
    "Bottom 20%": {
        "STRONG": (20, 40),
        "SECONDARY": (14, 30),
        "STANDARD": (1, 17),
        "WEAK": (1, 2),
    },
}

WILDCARD_RANGES: dict[str, tuple[int, int]] = {
    "Top 20%": (45, 90),
    "61–80": (35, 70),
    "41–60": (32, 60),
    "21–40": (25, 50),
    "Bottom 20%": (14, 40),
}

# (strong_attrs, secondary_attrs) — standard = remaining profile attrs.
ARCHETYPE_CONFIGS: dict[str, tuple[list[str], list[str]]] = {
    "Five-Star": (list(PROFILE_ATTRS), []),
    "Four-Star": ([], list(PROFILE_ATTRS)),
    "Defensive Wizard": (["ID", "OD"], ["ST", "AG"]),
    "All-Around Scorer": (["SH", "SC"], ["ST", "AG"]),
    "Classic PG": (["BH", "PS"], ["OD", "IQ"]),
    "Classic SG": (["SH"], ["OD"]),
    "Classic SF": (["SC", "OD"], ["AG"]),
    "Classic PF": (["RB"], ["ST"]),
    "Classic C": (["ID", "ST"], ["RB", "SC"]),
    "Pure Shooter": (["SH", "FT"], []),
    "Intangibles": (["IQ", "ND"], []),
    "Athlete": (["AG", "ST", "ND"], []),
    "Inside Defender": (["ST", "ID"], []),
    "Outside Defender": (["AG", "OD"], []),
    "Average": ([], []),
    "Below Average": ([], []),
    "Outside Dual Threat": (["SH", "AG"], []),
    "Driver": (["SC", "AG"], []),
    "Outside C": (["ST", "SH"], []),
    "Three & D": (["SH"], ["ID", "OD"]),
    "Athletic Shooter": (["SH", "AG"], []),
    "Inside Scorer": (["SC", "ST"], ["RB", "ID"]),
    "Outlet Passer": (["PS", "ST"], ["RB", "ID"]),
    "Scoring PF": (["RB", "SC"], ["ST"]),
    "Defensive PF": (["RB", "ID"], ["ST"]),
    "All-Around Wing": (["AG"], ["SC", "SH", "OD", "ID"]),
    "Scoring PG": (["BH", "PS"], ["SC", "SH"]),
}

# Doc had duplicate Intangibles on PG/PF (115%/110%). Corrected to 100% totals.
POSITION_ARCHETYPE_WEIGHTS: dict[str, list[tuple[str, int]]] = {
    "PG": [
        ("Classic PG", 50),
        ("All-Around Scorer", 10),
        ("Intangibles", 10),
        ("Outside Defender", 15),
        ("Scoring PG", 15),
    ],
    "SG": [
        ("Classic SG", 40),
        ("Defensive Wizard", 5),
        ("All-Around Scorer", 10),
        ("Pure Shooter", 15),
        ("Intangibles", 5),
        ("Outside Defender", 10),
        ("Outside Dual Threat", 10),
        ("Athletic Shooter", 5),
    ],
    "SF": [
        ("Classic SF", 30),
        ("Defensive Wizard", 10),
        ("All-Around Scorer", 10),
        ("Intangibles", 5),
        ("Athlete", 10),
        ("Outside Dual Threat", 10),
        ("Driver", 10),
        ("Three & D", 10),
        ("All-Around Wing", 5),
    ],
    "PF": [
        ("Classic PF", 40),
        ("Intangibles", 5),
        ("Inside Defender", 10),
        ("Three & D", 5),
        ("Inside Scorer", 10),
        ("Scoring PF", 15),
        ("Defensive PF", 15),
    ],
    "C": [
        ("Classic C", 40),
        ("Inside Defender", 20),
        ("Outside C", 15),
        ("Inside Scorer", 20),
        ("Outlet Passer", 5),
    ],
}


def _core_sum(attrs: dict) -> int:
    total = 0
    for key in PROFILE_ATTRS:
        val = attrs.get(key)
        if isinstance(val, (int, float)):
            total += int(val)
    return total


def _rank_key(player: dict) -> tuple:
    attrs = player.get("attributes") or {}
    return (-_core_sum(attrs), str(player["_id"]))


def _tier_key_asc(player: dict) -> tuple:
    attrs = player.get("attributes") or {}
    return (_core_sum(attrs), str(player["_id"]))


def _archetype_pools(archetype: str) -> tuple[list[str], list[str], list[str]]:
    strong, secondary = ARCHETYPE_CONFIGS[archetype]
    standard = [a for a in PROFILE_ATTRS if a not in strong and a not in secondary]
    return list(strong), list(secondary), standard


def _best_rt_position(ratings: dict[str, int | float]) -> str:
    best_rating = None
    tied: list[str] = []
    for pos in POSITIONS:
        rating = ratings.get(pos)
        if not isinstance(rating, (int, float)):
            continue
        rating = int(rating)
        if best_rating is None or rating > best_rating:
            best_rating = rating
            tied = [pos]
        elif rating == best_rating:
            tied.append(pos)
    if not tied:
        return random.choice(POSITIONS)
    return random.choice(tied)


def _weighted_archetype(position: str) -> str:
    choices = POSITION_ARCHETYPE_WEIGHTS[position]
    archetypes = [name for name, _ in choices]
    weights = [weight for _, weight in choices]
    return random.choices(archetypes, weights=weights, k=1)[0]


def _roll_profile_attrs(archetype: str, band: str) -> dict[str, int]:
    strong, secondary, standard = _archetype_pools(archetype)
    ranges = BAND_TIER_RANGES[band]
    attrs: dict[str, int] = {}

    for attr in PROFILE_ATTRS:
        if archetype == "Below Average":
            lo, hi = ranges["WEAK"]
        elif attr in strong:
            lo, hi = ranges["STRONG"]
        elif attr in secondary:
            lo, hi = ranges["SECONDARY"]
        else:
            lo, hi = ranges["STANDARD"]
        attrs[attr] = random.randint(lo, hi)

    if random.randint(1, 4) == 1:
        _, _, std_pool = _archetype_pools(archetype)
        if len(std_pool) >= 2:
            reroll_attrs = random.sample(std_pool, 2)
        elif std_pool:
            reroll_attrs = std_pool[:]
        else:
            reroll_attrs = []
        w_lo, w_hi = WILDCARD_RANGES[band]
        for attr in reroll_attrs:
            attrs[attr] = random.randint(w_lo, w_hi)

    return attrs


def _split_budget(total: int, w1: float, w2: float) -> tuple[int, int, int]:
    w3 = max(0.0, 1.0 - w1 - w2)
    weights = [w1, w2, w3]
    weight_sum = sum(weights)
    if weight_sum <= 0:
        third = total // 3
        return third, third, total - (2 * third)
    weights = [w / weight_sum for w in weights]
    b1 = int(total * weights[0])
    b2 = int(total * weights[1])
    b3 = total - b1 - b2
    return b1, b2, b3


def _apply_pool(
    attrs: dict[str, int],
    pool: list[str],
    budget: int,
    delta_sign: int,
) -> int:
    """Apply +/-1 adjustments; return unspent budget."""
    remaining = budget
    attempts = 0
    max_attempts = max(budget * len(pool) * 4, 1)
    while remaining > 0 and pool and attempts < max_attempts:
        attempts += 1
        attr = random.choice(pool)
        current = attrs[attr]
        if delta_sign > 0:
            if current >= 100:
                continue
            attrs[attr] = current + 1
            remaining -= 1
        else:
            if current <= 1:
                continue
            attrs[attr] = current - 1
            remaining -= 1
    return remaining


def _reconcile(attrs: dict[str, int], target_sum: int, archetype: str) -> dict[str, int]:
    result = dict(attrs)
    delta = target_sum - sum(result[a] for a in PROFILE_ATTRS)
    if delta == 0:
        return result

    strong, secondary, standard = _archetype_pools(archetype)
    abs_delta = abs(delta)
    adding = delta > 0

    if adding:
        b_strong, b_secondary, b_standard = _split_budget(
            abs_delta,
            random.uniform(0.45, 0.70),
            random.uniform(0.20, 0.35),
        )
        pool_order = [
            (strong, b_strong),
            (secondary, b_secondary),
            (standard, b_standard),
        ]
        spill_order = [strong, secondary, standard]
    else:
        b_standard, b_secondary, b_strong = _split_budget(
            abs_delta,
            random.uniform(0.45, 0.70),
            random.uniform(0.20, 0.35),
        )
        pool_order = [
            (standard, b_standard),
            (secondary, b_secondary),
            (strong, b_strong),
        ]
        spill_order = [standard, secondary, strong]

    sign = 1 if adding else -1
    leftover = 0
    for pool, budget in pool_order:
        if not pool or budget <= 0:
            continue
        leftover += _apply_pool(result, pool, budget, sign)

    spill_idx = 0
    guard = 0
    while leftover > 0 and spill_idx < len(spill_order) and guard < leftover * len(PROFILE_ATTRS) * 8:
        guard += 1
        pool = spill_order[spill_idx]
        if not pool:
            spill_idx += 1
            continue
        before = leftover
        leftover = _apply_pool(result, pool, leftover, sign)
        if leftover == before:
            spill_idx += 1

    # Final exact correction on any adjustable attrs if pools were exhausted.
    guard = 0
    while sum(result[a] for a in PROFILE_ATTRS) != target_sum and guard < 100_000:
        guard += 1
        current_delta = target_sum - sum(result[a] for a in PROFILE_ATTRS)
        if current_delta == 0:
            break
        sign = 1 if current_delta > 0 else -1
        order = spill_order if sign > 0 else list(reversed(spill_order))
        moved = False
        for pool in order:
            if not pool:
                continue
            for attr in random.sample(pool, len(pool)):
                if sign > 0 and result[attr] < 100:
                    result[attr] += 1
                    moved = True
                    break
                if sign < 0 and result[attr] > 1:
                    result[attr] -= 1
                    moved = True
                    break
            if moved:
                break
        if not moved:
            for attr in random.sample(PROFILE_ATTRS, len(PROFILE_ATTRS)):
                if sign > 0 and result[attr] < 100:
                    result[attr] += 1
                    break
                if sign < 0 and result[attr] > 1:
                    result[attr] -= 1
                    break

    final_delta = target_sum - sum(result[a] for a in PROFILE_ATTRS)
    if final_delta != 0:
        raise RuntimeError(f"Reconcile failed for {archetype}: delta={final_delta}")
    return result


def _assign_quintile_tiers(players: list[dict]) -> dict[str, int]:
    ranked = sorted(players, key=_rank_key)
    tiers: dict[str, int] = {}
    for idx, player in enumerate(ranked):
        tier = min(idx // TIER_SIZE + 1, 5)
        tiers[str(player["_id"])] = tier
    return tiers


def _assign_archetypes(
    players: list[dict],
    tiers: dict[str, int],
    backup_by_id: dict[str, dict],
) -> dict[str, str]:
    ranked = sorted(players, key=_rank_key)
    assignments: dict[str, str] = {}

    five_star_ids = {str(p["_id"]) for p in ranked[:FIVE_STAR_COUNT]}
    for pid in five_star_ids:
        assignments[pid] = "Five-Star"

    tier1_remaining = [
        p for p in ranked[:TIER_SIZE] if str(p["_id"]) not in five_star_ids
    ]
    four_star_players = random.sample(tier1_remaining, FOUR_STAR_COUNT)
    for player in four_star_players:
        assignments[str(player["_id"])] = "Four-Star"

    tier5_players = [p for p in ranked if tiers[str(p["_id"])] == 5]
    tier5_sorted = sorted(tier5_players, key=_rank_key)
    tier5_average = tier5_sorted[:TIER5_AVERAGE_COUNT]
    for player in tier5_average:
        assignments[str(player["_id"])] = "Average"
    for player in tier5_sorted[TIER5_AVERAGE_COUNT:]:
        assignments[str(player["_id"])] = "Below Average"

    tier4_players = [p for p in ranked if tiers[str(p["_id"])] == 4]
    tier4_sorted = sorted(tier4_players, key=_tier_key_asc)
    for player in tier4_sorted[:TIER4_AVERAGE_COUNT]:
        pid = str(player["_id"])
        if pid not in assignments:
            assignments[pid] = "Average"

    for player in players:
        pid = str(player["_id"])
        if pid in assignments:
            continue
        backup = backup_by_id.get(pid)
        if not backup:
            raise RuntimeError(f"Missing players_backup doc for {pid}")
        height = backup.get("height")
        if height is None:
            height = (backup.get("attributes") or {}).get("height")
        ratings = compute_position_ratings(
            {"height": height, "attributes": backup.get("attributes") or {}},
            profile="player",
        )
        position = _best_rt_position(ratings)
        assignments[pid] = _weighted_archetype(position)

    return assignments


def _rewrite_player_attrs(
    player: dict,
    backup: dict,
    archetype: str,
    tier: int,
) -> dict:
    attrs_in = player.get("attributes") or {}
    target_sum = _core_sum(attrs_in)
    band = BAND_BY_TIER[tier]

    rolled = _roll_profile_attrs(archetype, band)
    final_profile = _reconcile(rolled, target_sum, archetype)

    existing_attrs = dict(attrs_in)
    for key in PROFILE_ATTRS:
        existing_attrs[key] = final_profile[key]
        existing_attrs[f"anchor_{key}"] = final_profile[key]

    ch = random.randint(1, 100)
    existing_attrs["CH"] = ch
    existing_attrs["anchor_CH"] = ch

    height = player.get("height")
    if height is None:
        height = backup.get("height")
    ratings = compute_position_ratings(
        {"height": height, "attributes": existing_attrs},
        profile="player",
    )

    return {
        "attributes": existing_attrs,
        "position_ratings": ratings,
        "archetype": archetype,
    }


def _build_update(player_id, payload: dict) -> UpdateOne:
    return UpdateOne({"_id": player_id}, {"$set": payload})


def main() -> int:
    parser = argparse.ArgumentParser(description="Rewrite gob-staging comp player attributes")
    parser.add_argument("--dry-run", action="store_true", help="Compute assignments without writing")
    parser.add_argument("--yes", action="store_true", help="Required to write changes")
    args = parser.parse_args()

    if not args.dry_run and not args.yes:
        print("Pass --yes to write, or --dry-run to preview.", file=sys.stderr)
        return 1

    random.seed(RANDOM_SEED)

    connection = connect_script_database(
        target=DB_NAME,
        access="write" if args.yes else "read",
        pristine_env=dict(os.environ),
        repo_root=ROOT,
    )
    db = connection.database

    conf1_names = {
        t["name"] for t in db.teams.find({"conference": 1}, {"name": 1})
    }
    if len(conf1_names) != 8:
        print(f"Expected 8 conference-1 teams, found {len(conf1_names)}", file=sys.stderr)
        return 1

    backup_count = db.players_backup.count_documents({})
    if backup_count == 0:
        print("players_backup is empty — run backup script first.", file=sys.stderr)
        return 1

    all_players = list(db.players.find({}))
    conf1_players = [p for p in all_players if p.get("team") in conf1_names]
    rewrite_players = [p for p in all_players if p.get("team") not in conf1_names]

    if len(rewrite_players) != 1440:
        print(f"Expected 1440 rewrite players, found {len(rewrite_players)}", file=sys.stderr)
        return 1

    backup_by_id = {str(doc["_id"]): doc for doc in db.players_backup.find({})}
    missing_backup = [p for p in rewrite_players if str(p["_id"]) not in backup_by_id]
    if missing_backup:
        print(f"Missing backup for {len(missing_backup)} rewrite players", file=sys.stderr)
        return 1

    tiers = _assign_quintile_tiers(rewrite_players)
    archetypes = _assign_archetypes(rewrite_players, tiers, backup_by_id)

    counts = Counter(archetypes.values())
    print(f"Conference 1 teams ({len(conf1_names)}): {sorted(conf1_names)}")
    print(f"Rewrite pool: {len(rewrite_players)} players")
    print(f"Archetype distribution ({sum(counts.values())} assigned):")
    for name, count in counts.most_common():
        print(f"  {name}: {count}")

    rewrite_payloads: dict[str, dict] = {}
    errors: list[str] = []
    for player in rewrite_players:
        pid = str(player["_id"])
        target_sum = _core_sum(player.get("attributes") or {})
        try:
            payload = _rewrite_player_attrs(
                player,
                backup_by_id[pid],
                archetypes[pid],
                tiers[pid],
            )
        except RuntimeError as exc:
            errors.append(f"{pid}: {exc}")
            continue
        profile_sum = sum(payload["attributes"][a] for a in PROFILE_ATTRS)
        if profile_sum != target_sum:
            errors.append(f"{pid}: sum mismatch ({profile_sum} != {target_sum})")
            continue
        rewrite_payloads[pid] = payload

    if errors:
        print(f"Validation errors: {len(errors)}", file=sys.stderr)
        for line in errors[:10]:
            print(f"  {line}", file=sys.stderr)
        return 1

    ops: list[UpdateOne] = []
    for player in rewrite_players:
        pid = str(player["_id"])
        ops.append(_build_update(player["_id"], rewrite_payloads[pid]))

    for player in conf1_players:
        ops.append(
            UpdateOne({"_id": player["_id"]}, {"$set": {"archetype": ""}})
        )

    if args.dry_run:
        print(f"Dry run OK — would write {len(ops)} updates ({len(rewrite_players)} rewrites + {len(conf1_players)} conf1 archetype clears).")
        return 0

    result = db.players.bulk_write(ops, ordered=False)
    meta = {
        "_id": "latest",
        "script": "rewrite_comp_player_attrs_gob_staging.py",
        "random_seed": RANDOM_SEED,
        "rewrite_count": len(rewrite_players),
        "conf1_archetype_clear_count": len(conf1_players),
        "archetype_counts": dict(counts),
        "completed_at": datetime.now(timezone.utc),
    }
    db.players_rewrite_meta.replace_one({"_id": "latest"}, meta, upsert=True)

    print(f"Modified {result.modified_count} player documents.")
    print("Metadata written to players_rewrite_meta.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ScriptDatabaseError as exc:
        print(f"Refusing unsafe database operation: {exc}", file=sys.stderr)
        sys.exit(2)
