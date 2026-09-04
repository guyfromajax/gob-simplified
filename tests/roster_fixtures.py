"""Playable universal rosters for mongomock.

Mongomock starts empty, so ``build_lineup_from_mongo`` (BackEnd/utils/db_utils.py) had no
bodies to seat. Its waterfall drops the NG floor to 0 and lifts foul limits to 4, then
raises on a roster it still cannot fill five slots from::

    ValueError: Team 'Bentley-Truman' has fewer than 5 eligible players even after
    relaxing NG and foul limits. Total roster: 0, last eligible: 0

Every test that tips off died there. The guard is satisfied, never weakened: these
players clear eligibility at the FIRST waterfall step (NG 1.0 is above the 0.8 floor,
zero fouls in an empty box score), so the relaxation branches stay as unexercised under
test as they are in production.

Document shapes are not hand-built. They come from the scripts that populate the real
universal collections — ``scripts/load_players_from_tsv_gob_staging.py`` for ``players``
and ``scripts/repopulate_teams_gob_staging.py`` for ``teams``. Those scripts' column
maps, source TSVs and row parser are imported rather than restated, and attribute /
box-score / metadata derivation is delegated to ``BackEnd.models.player.Player``, which
is what ``scripts/loader.py`` persists. A column added to either TSV therefore reaches
this fixture for free, and a column that MOVES breaks it loudly instead of quietly
seeding garbage attributes.
"""

from __future__ import annotations

import copy
import functools
import uuid
from typing import Any, Dict, List

from BackEnd.models.player import Player
from BackEnd.utils.position_ratings import compute_position_ratings
from scripts.load_players_from_tsv_gob_staging import (
    ATTR_KEYS,
    GENERIC_HEADSHOT,
    IDX,
    TSV_PATH,
    _int,
)
from scripts.repopulate_teams_gob_staging import TEAMS_FILE, parse_row

# Only the teams the suite actually tips off with. Seeding all 128 would change what the
# tournament-bracket and franchise-init tests see when they count `teams`.
#
# Seed them as a SET or not at all. Leaving one of a matchup's two teams empty is worse
# than seeding neither: `test_phase5_6_comprehensive_settings`, `test_settings_persistence`,
# `test_foul_out_timeout_persistence` and `test_turn_manager` all go red on a game whose
# home team has bodies and whose away team does not.
CANONICAL_TEAM_NAMES = ("Bentley-Truman", "Four Corners", "Lancaster", "Morristown")

# Stable ids, so a re-seed after some other test's ``delete_many({})`` reproduces the
# same roster rather than a fresh one. String ``_id`` matches `gob`, which
# BackEnd/utils/roster_loader.py looks players up in by str id.
_PLAYER_ID_NS = uuid.UUID("6f3f1d64-0f5d-5a5e-9c1a-2f0a4b6d8e10")

# Test modules that require an EMPTY ``players`` collection and are actively broken by a
# seeded one. They get the teams but not the rosters.
#
# test_putback_miss_rebound_stats: its ``_sync_lineup_to_roster`` helper branches on
# ``len(roster) >= 5``. With mongomock empty that branch was dead code and every test in
# the file silently ran the MockPlayer fallback. Seeded, the real branch runs and the
# file's forced putback MISS becomes a MAKE — not because the seeded players are better,
# but because the miss was never actually forced. Those tests pin the outcome by patching
# ``BackEnd.utils.shared.random.randint`` and setting ``shot_threshold`` to 1000, while
# the putback resolves through ``apply_uncontested_inside_attack_make``, which rolls
# ``BackEnd.utils.sim_random.sim_rng`` — a different, unpatched stream — against a
# threshold near 99. MockPlayers stood outside that helper's 11-foot gate so it never
# applied and the 1000 threshold decided the shot; real players stand inside it, so the
# shot drops ~98% of the time.
#
# Lift this by fixing the file, not by widening the list: patch the sim_random stream (or
# put the shooter outside the gate) so the miss is genuinely forced, then delete the entry
# and confirm the five tests still pass.
ROSTER_QUARANTINE = frozenset({"test_putback_miss_rebound_stats"})


@functools.lru_cache(maxsize=1)
def canonical_team_rows() -> Dict[str, Dict[str, Any]]:
    """name -> parsed teams/128_teams.txt row, via the production ``parse_row``."""
    wanted = set(CANONICAL_TEAM_NAMES)
    rows: Dict[str, Dict[str, Any]] = {}
    with open(TEAMS_FILE) as handle:
        for line in list(handle)[1:]:
            row = parse_row(line)
            if row and row["name"] in wanted:
                rows[row["name"]] = row
    missing = wanted - set(rows)
    if missing:
        raise RuntimeError(
            f"teams/128_teams.txt no longer carries test team(s) {sorted(missing)}; "
            "update CANONICAL_TEAM_NAMES to teams that exist."
        )
    return rows


def _player_doc(row: List[str], team_name: str) -> Dict[str, Any]:
    """One universal ``players`` document, shaped as the loader scripts write them."""
    height = _int(row[IDX["height"]], 75)
    first_name = row[IDX["first_name"]].strip()
    last_name = row[IDX["last_name"]].strip()
    jersey = _int(row[IDX["jersey"]])
    player_id = str(
        uuid.uuid5(_PLAYER_ID_NS, f"{team_name}|{first_name}|{last_name}|{jersey}")
    )
    raw = {
        "_id": player_id,
        "first_name": first_name,
        "last_name": last_name,
        "team": team_name,
        "year": row[IDX["year"]].strip(),
        "jersey": jersey,
        "height": height,
        "weight": _int(row[IDX["weight"]], 200),
        **{key: _int(row[IDX[key]], 0) for key in ATTR_KEYS},
    }
    # Player owns anchor derivation, the NG default of 1.0, the MO clamp and the empty
    # box scores. Deriving them here instead would be the drift this fixture avoids.
    player = Player(raw)
    return {
        "_id": player_id,
        "player_id": player_id,
        "first_name": player.first_name,
        "last_name": player.last_name,
        "team": player.team,
        "year": player.year,
        "jersey": player.jersey,
        "height": player.height,
        "weight": player.weight,
        "attributes": player.attributes,
        "position_ratings": compute_position_ratings(
            {"height": height, "attributes": player.attributes}
        ),
        "photo": GENERIC_HEADSHOT,
        "stats": player.stats,
        "metadata": player.metadata,
    }


@functools.lru_cache(maxsize=1)
def canonical_rosters() -> Dict[str, List[Dict[str, Any]]]:
    """name -> 12 universal player documents, parsed once per session."""
    wanted = set(CANONICAL_TEAM_NAMES)
    by_team: Dict[str, List[Dict[str, Any]]] = {name: [] for name in wanted}
    with open(TSV_PATH) as handle:
        for line in list(handle)[1:]:
            row = line.rstrip("\n\r").split("\t")
            if len(row) <= IDX["team"]:
                continue
            team_name = row[IDX["team"]].strip()
            if team_name in wanted:
                by_team[team_name].append(_player_doc(row, team_name))
    short = {name: len(docs) for name, docs in by_team.items() if len(docs) < 5}
    if short:
        raise RuntimeError(
            f"teams/all_players_with_team_names.txt cannot fill a lineup for {short}; "
            "build_lineup_from_mongo needs at least five players per team."
        )
    return by_team


def seed_universal_rosters(
    teams_collection, players_collection, *, module_name: str | None = None
) -> None:
    """Idempotently put the canonical teams and their rosters in mongomock.

    Runs before every test because a dozen tests clear ``players`` or ``teams`` outright
    (see the block-list note in conftest). The common case costs one count.

    ``module_name`` is the bare stem of the test file. Modules in ``ROSTER_QUARANTINE``
    get the teams and an explicitly emptied roster — emptied rather than merely skipped,
    because the mongomock database outlives the test that seeded it.
    """
    team_rows = canonical_team_rows()

    for name, row in team_rows.items():
        teams_collection.update_one(
            {"name": name},
            {"$set": {"name": name, "team_id": row["team_id"]}},
            upsert=True,
        )

    if module_name in ROSTER_QUARANTINE:
        players_collection.delete_many({"team": {"$in": list(team_rows)}})
        return

    rosters = canonical_rosters()
    expected = sum(len(docs) for docs in rosters.values())
    if players_collection.count_documents({"team": {"$in": list(team_rows)}}) == expected:
        return

    for name, docs in rosters.items():
        present = {
            doc["_id"] for doc in players_collection.find({"team": name}, {"_id": 1})
        }
        missing = [copy.deepcopy(doc) for doc in docs if doc["_id"] not in present]
        if not missing:
            continue
        # The universal team's ObjectId, stamped on each player as production does. It is
        # read after the upsert above because a prior test may have dropped `teams`.
        team_oid = (teams_collection.find_one({"name": name}, {"_id": 1}) or {}).get("_id")
        for doc in missing:
            doc["team_id"] = team_oid
        players_collection.insert_many(missing)
