"""
Persist CPU team identity onto franchise team data (FTD).

WHY THIS EXISTS
---------------
``TeamManager.__init__`` only runs the identity assignment when NO ``strategy_settings``
are supplied. In franchise mode settings are ALWAYS supplied — franchise creation seeds
every FTD with a flat-neutral all-2s dict (``get_default_settings()``), which
``prepare_ftd_for_new_game`` passes straight into the constructor. The identity branch
therefore never executed in franchise mode, and every one of the 128 teams played with
identical neutral sliders.

That was caught by a week-1 measurement gate: all 128 teams showed
``aggression = hc_trap = fc_press = offense = tempo = 2``, zero variance, no visions.

The fix is not to change the constructor. It is to make the settings FTD supplies be
identity-derived instead of neutral — then the existing branch does the right thing
unchanged.

WHEN IDENTITY IS ASSIGNED
-------------------------
Keyed on SEASON, which covers both requirements with one mechanism:

* **franchise creation** — no ``identity`` sub-document exists yet -> assign.
* **season init** — ``identity.assigned_season`` no longer matches the franchise's
  current season -> reassign. Attributes reset each season and rosters turn over
  wholesale, so last season's identity is not meaningful.
* **constants change** — ``identity.constants_version`` no longer matches
  ``team_identity.CONSTANTS_VERSION`` -> reassign rather than silently reuse a pair
  derived under different scales.

Otherwise it is a no-op, so this is safe to call on a hot path.

NOTE ON PLACEMENT: franchise creation seeds FTD documents BEFORE rosters are attached
(``ensure_team_objects_exist`` writes ``strategy_settings`` with no ``players`` key), so
identity cannot be computed at that exact site — there is no five to project. Assignment
therefore happens at the first point each season where rosters are guaranteed to exist.

SCHEMA (``ftd.identity``)
-------------------------
    offensive_vision   str
    defensive_vision   str
    assigned_season    int
    assigned_week      int
    fuel_capacity      int
    signals            {signal: z-score}
    scores             {"offense": {vision: score}, "defense": {vision: score}}
    constants_version  int

``ftd.strategy_settings`` is overwritten with the identity-derived draw at the same time.
Storing the pair AND the derived sliders is deliberate: the deferred five-week
re-evaluation needs to read the vision that produced the sliders.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, Optional

from bson import ObjectId
from pymongo.operations import UpdateOne

from BackEnd.utils.team_identity import CONSTANTS_VERSION, assign_identity

logger = logging.getLogger(__name__)


def _as_oid(value):
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except Exception:
        return value


def _player_view(fpd_doc: dict) -> SimpleNamespace:
    """Adapt an FPD document to the attribute surface team_identity reads
    (``player_id``, ``attributes``, ``position_ratings``)."""
    return SimpleNamespace(
        player_id=str(fpd_doc.get("player_id") or ""),
        attributes=fpd_doc.get("attributes") or {},
        position_ratings=fpd_doc.get("position_ratings") or {},
    )


def identity_is_current(ftd_doc: dict, season: int) -> bool:
    ident = ftd_doc.get("identity")
    if not isinstance(ident, dict):
        return False
    if ident.get("constants_version") != CONSTANTS_VERSION:
        return False
    return ident.get("assigned_season") == season


def ensure_franchise_identities(
    franchise_id,
    season: int,
    week: int = 1,
    *,
    force: bool = False,
    rng=None,
) -> dict[str, Any]:
    """Assign + persist identity for every team in a franchise that needs one.

    Idempotent: teams whose identity already matches ``season`` and the current
    ``CONSTANTS_VERSION`` are skipped unless ``force``. Returns a summary dict.
    """
    from BackEnd.db import franchise_players_data_collection, franchise_team_data_collection

    fid = _as_oid(franchise_id)
    ftd_docs = list(
        franchise_team_data_collection.find(
            {"franchise_id": {"$in": [fid, str(fid)]}},
            {"team_id": 1, "players": 1, "identity": 1},
        )
    )
    if not ftd_docs:
        return {"teams": 0, "assigned": 0, "skipped": 0, "no_five": 0}

    pending = [d for d in ftd_docs if force or not identity_is_current(d, season)]
    if not pending:
        return {"teams": len(ftd_docs), "assigned": 0,
                "skipped": len(ftd_docs), "no_five": 0}

    roster_ids: list[str] = []
    for d in pending:
        roster_ids.extend(str(p) for p in (d.get("players") or []) if p)
    fpd_map: dict[str, dict] = {}
    if roster_ids:
        # franchise_id is stored as an ObjectId on FTD but as a STRING on FPD. Match on
        # either rather than assuming — querying FPD with the ObjectId silently returns
        # zero documents, which presents as "no five could be resolved" for every team.
        for doc in franchise_players_data_collection.find(
            {"franchise_id": {"$in": [fid, str(fid)]},
             "player_id": {"$in": roster_ids}},
            {"player_id": 1, "attributes": 1, "position_ratings": 1},
        ):
            fpd_map[str(doc.get("player_id"))] = doc

    ops: list[UpdateOne] = []
    assigned = no_five = 0
    for d in pending:
        players = [
            _player_view(fpd_map[str(pid)])
            for pid in (d.get("players") or [])
            if str(pid) in fpd_map
        ]
        result = assign_identity(players, rng=rng) if players else None
        if not result:
            no_five += 1
            logger.warning(
                "[IDENTITY] franchise=%s team=%s: could not resolve a five from %d "
                "roster player(s); leaving existing strategy_settings in place.",
                fid, d.get("team_id"), len(players),
            )
            continue
        ops.append(
            UpdateOne(
                {"_id": d["_id"]},
                {"$set": {
                    "strategy_settings": result["strategy_settings"],
                    "identity": {
                        "offensive_vision": result["offensive_vision"],
                        "defensive_vision": result["defensive_vision"],
                        "assigned_season": season,
                        "assigned_week": week,
                        "fuel_capacity": result["fuel_capacity"],
                        "signals": result["signals"],
                        "scores": result["scores"],
                        "constants_version": result["constants_version"],
                    },
                }},
            )
        )
        assigned += 1

    if ops:
        franchise_team_data_collection.bulk_write(ops, ordered=False)

    summary = {
        "teams": len(ftd_docs),
        "assigned": assigned,
        "skipped": len(ftd_docs) - len(pending),
        "no_five": no_five,
    }
    logger.info("[IDENTITY] franchise=%s season=%s -> %s", fid, season, summary)
    return summary


def franchise_identity_summary(franchise_id) -> dict[str, Any]:
    """Read-only view used by measurement gates: vision distribution and slider variance
    across the league. Zero variance means the treatment is NOT active."""
    from BackEnd.db import franchise_team_data_collection

    fid = _as_oid(franchise_id)
    docs = list(
        franchise_team_data_collection.find(
            {"franchise_id": {"$in": [fid, str(fid)]}},
            {"identity": 1, "strategy_settings": 1},
        )
    )
    off: dict[str, int] = {}
    dfn: dict[str, int] = {}
    with_identity = 0
    for d in docs:
        ident = d.get("identity")
        if isinstance(ident, dict) and ident.get("offensive_vision"):
            with_identity += 1
            off[ident["offensive_vision"]] = off.get(ident["offensive_vision"], 0) + 1
            dv = ident.get("defensive_vision")
            if dv:
                dfn[dv] = dfn.get(dv, 0) + 1

    variance: dict[str, float] = {}
    distinct: dict[str, int] = {}
    keys = ("offense", "inside", "attack", "outside", "fast_breaks", "tempo",
            "alterations", "defense", "aggression", "hc_trap", "fc_press", "rebounding")
    for k in keys:
        vals = [
            float((d.get("strategy_settings") or {}).get(k))
            for d in docs
            if isinstance((d.get("strategy_settings") or {}).get(k), (int, float))
        ]
        if len(vals) > 1:
            mean = sum(vals) / len(vals)
            variance[k] = round(sum((v - mean) ** 2 for v in vals) / len(vals), 4)
            distinct[k] = len(set(vals))
    return {
        "teams": len(docs),
        "teams_with_identity": with_identity,
        "offensive_visions": dict(sorted(off.items(), key=lambda x: -x[1])),
        "defensive_visions": dict(sorted(dfn.items(), key=lambda x: -x[1])),
        "slider_variance": variance,
        "slider_distinct_values": distinct,
    }
