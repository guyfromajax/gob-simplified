"""League ranks for the Team Attributes measures on GET /franchise/team-data.

develop has no ``measures[]`` on that route. This module is the field set the
route attaches. It does not build the roster-page family rows.

Direction comes from how the sim consumes the stored number. ``fight`` and
``discipline`` are left unranked: each one helps the team in one check and
hurts it in another, so neither end is "best" until that call is made.

``rank_delta`` uses the user team's prior ``team_measures`` snapshot
(``office_week_snapshots`` / ``TEAM_MEASURE_KEYS``). Chemistry is not in that
snapshot, so its delta stays null. This module does not write snapshots.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from bson import ObjectId

from BackEnd.utils.office_digest import CHEMISTRY_MAX, TEAM_MEASURE_KEYS

# Order is the Team Attributes list. scale_max is Chemistry's 25; the others
# have no display scale.
MEASURE_SPECS: tuple[dict[str, Any], ...] = (
    {"key": "team_chemistry", "label": "Chemistry", "direction": "higher_better", "scale_max": CHEMISTRY_MAX},
    {"key": "fight", "label": "Fight", "direction": None, "scale_max": None},
    {"key": "discipline", "label": "Discipline", "direction": None, "scale_max": None},
    {"key": "shot_threshold", "label": "Shooting", "direction": "lower_better", "scale_max": None},
    {"key": "rebound_modifier", "label": "Rebounding", "direction": "higher_better", "scale_max": None},
    {"key": "defensive_efficiency", "label": "Defensive efficiency", "direction": "higher_better", "scale_max": None},
)

MEASURE_KEYS: tuple[str, ...] = tuple(spec["key"] for spec in MEASURE_SPECS)

# Snapshot keys that can move a rank. Chemistry is absent from TEAM_MEASURE_KEYS
# on purpose; skip it even if a snapshot happens to carry the key.
_DELTA_KEYS = frozenset(TEAM_MEASURE_KEYS) - {"team_chemistry"}


def _id_text(value: Any) -> Optional[str]:
    """ObjectId, a bare id string, or SQLite's ``{"$oid": "..."}`` extract."""
    if value is None:
        return None
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict) and "$oid" in value:
        return str(value["$oid"])
    text = str(value).strip()
    if text.startswith("{") and "$oid" in text:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return text
        if isinstance(parsed, dict) and parsed.get("$oid"):
            return str(parsed["$oid"])
    return text or None


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _values_from_attributes(attributes: Mapping[str, Any] | None) -> dict[str, Optional[float]]:
    attrs = attributes or {}
    return {key: _number(attrs.get(key)) for key in MEASURE_KEYS}


def competition_ranks(scored: Mapping[str, float], *, higher_better: bool) -> dict[str, int]:
    """Standard competition ranking. Ties share a place; the next place skips.

    ``1, 2, 2, 4``. Rank 1 is the best end of ``higher_better``.
    """
    ordered = sorted(scored.items(), key=lambda item: item[1], reverse=higher_better)
    ranks: dict[str, int] = {}
    index = 0
    count = len(ordered)
    while index < count:
        end = index + 1
        while end < count and ordered[end][1] == ordered[index][1]:
            end += 1
        place = index + 1
        for cursor in range(index, end):
            ranks[ordered[cursor][0]] = place
        index = end
    return ranks


def percentile(value: float, values: list[float], *, higher_better: bool) -> int | float:
    """0–100, 100 at the best end. Ties at an end share that end.

    ``100 × (teams strictly worse) / (teams strictly better + teams strictly worse)``.
    A one-team board, or a board where every stored value is equal, is 100.
    """
    better = 0
    worse = 0
    for other in values:
        if other == value:
            continue
        other_is_better = other > value if higher_better else other < value
        if other_is_better:
            better += 1
        else:
            worse += 1
    span = better + worse
    if span == 0:
        return 100
    rounded = round(100.0 * worse / span, 1)
    if float(rounded).is_integer():
        return int(rounded)
    return rounded


def build_measures(
    rows: list[dict[str, Any]],
    team_id: Any,
    prior_measures: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """One measure object per spec, for ``team_id``, ranked across ``rows``.

    A row is ``{"team_id", "values"}``. A missing or non-numeric value is left
    out of ``rank_of``. ``prior_measures`` is the user team's snapshot
    ``team_measures``; pass None for any other team. Positive ``rank_delta``
    means the team climbed (its rank number got smaller).
    """
    key = str(team_id)
    by_team: dict[str, dict[str, Optional[float]]] = {}
    for row in rows:
        tid = row.get("team_id")
        if tid is None:
            continue
        by_team[str(tid)] = dict(row.get("values") or {})
    own = by_team.get(key) or {measure: None for measure in MEASURE_KEYS}

    measures: list[dict[str, Any]] = []
    for spec in MEASURE_SPECS:
        measure_key = spec["key"]
        direction = spec["direction"]
        value = own.get(measure_key)
        entry: dict[str, Any] = {
            "key": measure_key,
            "label": spec["label"],
            "value": value,
            "scale_max": spec["scale_max"],
            "direction": direction,
            "rank": None,
            "rank_of": None,
            "percentile": None,
            "rank_delta": None,
        }
        if direction not in ("higher_better", "lower_better"):
            measures.append(entry)
            continue
        higher_better = direction == "higher_better"
        scored = {
            tid: values[measure_key]
            for tid, values in by_team.items()
            if _number(values.get(measure_key)) is not None
        }
        # _number already ran at load; keep the float that was stored.
        scored = {tid: float(number) for tid, number in scored.items()}
        if key not in scored:
            measures.append(entry)
            continue
        ranks = competition_ranks(scored, higher_better=higher_better)
        board = list(scored.values())
        entry["rank"] = ranks[key]
        entry["rank_of"] = len(scored)
        entry["percentile"] = percentile(scored[key], board, higher_better=higher_better)
        entry["rank_delta"] = _rank_delta(
            measure_key,
            key,
            scored,
            higher_better=higher_better,
            prior_measures=prior_measures,
            current_rank=entry["rank"],
        )
        measures.append(entry)
    return measures


def _rank_delta(
    measure_key: str,
    team_id: str,
    scored: Mapping[str, float],
    *,
    higher_better: bool,
    prior_measures: Mapping[str, Any] | None,
    current_rank: int,
) -> Optional[int]:
    if measure_key not in _DELTA_KEYS or not prior_measures:
        return None
    prior_value = _number(prior_measures.get(measure_key))
    if prior_value is None or team_id not in scored:
        return None
    prior_board = dict(scored)
    prior_board[team_id] = prior_value
    prior_rank = competition_ranks(prior_board, higher_better=higher_better)[team_id]
    return int(prior_rank) - int(current_rank)


def load_measure_rows(collection: Any, franchise_id: Any) -> list[dict[str, Any]]:
    """Projected read of every franchise team's six measure values.

    SQLite extracts the scalars and does not decode the rest of the team
    document. Mongo uses the same dotted inclusion.
    """
    from BackEnd.persistence.sqlite_collection import SqliteCollection

    fid = franchise_id if isinstance(franchise_id, ObjectId) else ObjectId(str(franchise_id))
    fields = ["team_id", *[f"team_attributes.{key}" for key in MEASURE_KEYS]]
    filt = {"franchise_id": fid}
    if isinstance(collection, SqliteCollection):
        raw_rows = collection.projected_tuples(filt, fields)
        rows: list[dict[str, Any]] = []
        for raw in raw_rows:
            team_id = _id_text(raw[0])
            if team_id is None:
                continue
            values = {
                key: _number(value)
                for key, value in zip(MEASURE_KEYS, raw[1:])
            }
            rows.append({"team_id": team_id, "values": values})
        return rows

    projection = {"team_id": 1}
    for key in MEASURE_KEYS:
        projection[f"team_attributes.{key}"] = 1
    rows = []
    for doc in collection.find(filt, projection):
        team_id = doc.get("team_id")
        if team_id is None:
            continue
        rows.append({
            "team_id": str(team_id),
            "values": _values_from_attributes(doc.get("team_attributes")),
        })
    return rows


def measures_for_team(
    collection: Any,
    franchise_id: Any,
    team_id: Any,
    prior_measures: Mapping[str, Any] | None = None,
    own_attributes: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Ranks for one team. ``own_attributes`` fills in only when the scan missed the team."""
    rows = load_measure_rows(collection, franchise_id)
    key = str(team_id)
    if not any(row["team_id"] == key for row in rows):
        rows.append({"team_id": key, "values": _values_from_attributes(own_attributes)})
    return build_measures(rows, key, prior_measures)
