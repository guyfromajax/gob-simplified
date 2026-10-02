"""CH is a hidden attribute: the engine uses it, the browser never receives it.

Three guards:
  1. the strip itself (keys, rows that name the attribute, attribute-key lists; never mutates);
  2. every franchise route renders through it, bar a pinned list of exceptions;
  3. a real franchise's main client payloads carry no trace of it, while the database still does.
"""
import copy

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from BackEnd.api.api import app
from BackEnd.db import (
    db,
    franchise_players_data_collection,
    franchise_recruits_data_collection,
    franchise_team_data_collection,
)
from BackEnd.utils.hidden_attrs import (
    HIDDEN_ATTR_KEYS,
    VISIBLE_ATTR_LABELS,
    HiddenAttrsJSONResponse,
    scrub_hidden_attr_copy,
    strip_hidden_attrs,
    visible_attr_keys,
)

client = TestClient(app)

ATTR_CODES = {"SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ"}
ROW_FIELDS = ("attribute", "attr", "attr_key", "attribute_key")
# Copy that would name the attribute to the player.
HIDDEN_LABELS = ("Clutch",)


def hidden_traces(value, path="$"):
    """Every place a JSON value reveals a hidden attribute, as readable paths."""
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in HIDDEN_ATTR_KEYS:
                found.append(f"{path}.{key} (key)")
            if key in ROW_FIELDS and item in HIDDEN_ATTR_KEYS:
                found.append(f"{path}.{key} = {item!r} (row names it)")
            found.extend(hidden_traces(item, f"{path}.{key}"))
    elif isinstance(value, list):
        strings = [item for item in value if isinstance(item, str)]
        if len(ATTR_CODES.intersection(strings)) >= 3:
            found.extend(f"{path}[] = {item!r} (attribute-key list)" for item in strings if item in HIDDEN_ATTR_KEYS)
        for index, item in enumerate(value):
            found.extend(hidden_traces(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        found.extend(f"{path} mentions {label!r}" for label in HIDDEN_LABELS if label in value)
    return found


# --- 1. the strip ------------------------------------------------------------------------------


def test_strip_removes_the_attribute_its_anchor_and_its_seed():
    payload = {
        "players": [{
            "name": "A",
            "attributes": {"SC": 5, "CH": 77, "anchor_SC": 5, "anchor_CH": 77, "EM": 50},
            "development": {"ch_seed": 77, "peak_count": 2},
        }],
        "player_changes": {"A": {"SC": 1, "CH": 2}},
        "player_attribute_display_movements": {"p1": {"name": "A", "CH": {"from": 7, "to": 8}, "SC": {"from": 4, "to": 5}}},
    }
    before = copy.deepcopy(payload)
    out = strip_hidden_attrs(payload)
    assert hidden_traces(out) == []
    assert out["players"][0]["attributes"] == {"SC": 5, "anchor_SC": 5, "EM": 50}
    assert out["players"][0]["development"] == {"peak_count": 2}
    assert out["player_changes"] == {"A": {"SC": 1}}
    assert out["player_attribute_display_movements"]["p1"] == {"name": "A", "SC": {"from": 4, "to": 5}}
    # The engine's objects are never touched: routes share them with what gets saved.
    assert payload == before
    assert out["players"][0]["attributes"] is not payload["players"][0]["attributes"]


def test_strip_drops_rows_and_key_lists_that_name_it_and_nothing_else():
    payload = {
        "attribute_changes": [
            {"player_id": "p1", "attribute": "CH", "from": 7, "to": 8},
            {"player_id": "p1", "attribute": "SC", "from": 4, "to": 5},
        ],
        "exceptional_gains": [{"name": "A", "attribute": "CH"}],
        "attr_keys": ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "CH"],
        # Not attribute data: a bare "CH" outside an attribute-key list is left alone.
        "codes": ["CH", "NY"],
        "note": "CH",
    }
    out = strip_hidden_attrs(payload)
    assert out["attribute_changes"] == [{"player_id": "p1", "attribute": "SC", "from": 4, "to": 5}]
    assert out["exceptional_gains"] == []
    assert out["attr_keys"] == ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]
    assert out["codes"] == ["CH", "NY"]
    assert out["note"] == "CH"
    assert visible_attr_keys(["SC", "CH", "IQ"]) == ["SC", "IQ"]


def test_the_trace_walker_sees_every_form():
    """The guard below is only as good as this walker: prove it catches each shape."""
    assert hidden_traces({"attributes": {"CH": 1}}) == ["$.attributes.CH (key)"]
    assert hidden_traces({"a": [{"attributes": {"anchor_CH": 1}}]}) == ["$.a[0].attributes.anchor_CH (key)"]
    assert hidden_traces({"development": {"ch_seed": 9}}) == ["$.development.ch_seed (key)"]
    assert hidden_traces([{"attribute": "CH"}]) == ["$[0].attribute = 'CH' (row names it)"]
    assert hidden_traces({"attr_keys": ["SC", "SH", "ID", "CH"]}) == ["$.attr_keys[] = 'CH' (attribute-key list)"]
    assert hidden_traces({"lines": ["His strongest gains were in Clutch."]}) == ["$.lines[0] mentions 'Clutch'"]
    assert hidden_traces({"attributes": {"SC": 1}, "team": ["CH", "NY"]}) == []


# --- 2. every franchise route renders through the strip ------------------------------------------

# Team Builder round-trips whole player rows (walk-ons, the slot roster) through the client and
# saves what comes back, so stripping there would lose the attribute on Apply. Pinned: adding to
# this list is a decision, not an accident.
KEEPS_FULL_ATTRIBUTES = {
    "/franchise/team-builder",
    "/franchise/team-builder/slot-roster",
    "/franchise/team-builder/league-context",
    "/franchise/team-builder/position-ratings",
    "/franchise/team-builder/drafts",
    "/franchise/team-builder/drafts/{replaced_object_id}",
    "/franchise/team-builder/wizard-walk-ons",
    "/franchise/team-builder/portraits/assign",
    "/franchise/team-builder/portraits/reroll",
    "/franchise/team-builder/portraits/pick",
    "/franchise/team-builder/portraits/catalog",
    "/franchise/team-builder/apply",
}
# The court's own routes: the Phaser client reads CH for the pass-receive sound (gameSfx.js),
# and autoset posts roster attributes back. Left as they are, for Jamie to decide.
COURT_ROUTES_STILL_CARRYING_IT = {
    "/roster/{team_identifier}",
    "/api/init-game",
    "/api/simulate-turn",
    "/api/simulate-quarter",
    "/api/call-timeout",
    "/api/autoset-lineup",
    "/api/game/{game_id}",
    "/api/game/{game_id}/resume-state",
    "/api/game/{game_id}/lineup-for-matchups",
}


def _json_routes():
    """Every API route, whether the app lists included routers flat or keeps them as routers."""
    routes = []
    for route in app.routes:
        original = getattr(route, "original_router", None)
        routes.extend(original.routes if original is not None else [route])
    return [route for route in routes if getattr(route, "response_class", None) is not None and hasattr(route, "path")]


def _response_class(route):
    """The class a route renders with (FastAPI wraps an unset one in a default placeholder)."""
    declared = route.response_class
    return getattr(declared, "value", declared)


def test_every_franchise_route_strips_hidden_attributes():
    franchise = [route for route in _json_routes() if route.path.startswith("/franchise")]
    assert len(franchise) > 80, "the franchise router is mounted"
    unguarded = sorted({
        route.path for route in franchise
        if not issubclass(_response_class(route), HiddenAttrsJSONResponse)
    })
    assert unguarded == sorted(KEEPS_FULL_ATTRIBUTES)


def test_the_player_page_routes_strip_and_the_court_routes_are_the_known_exceptions():
    by_path = {route.path: route for route in _json_routes()}
    for path in ("/player/{player_id}", "/teams/{team_id}/players"):
        assert issubclass(_response_class(by_path[path]), HiddenAttrsJSONResponse), path
    for path in COURT_ROUTES_STILL_CARRYING_IT:
        assert path in by_path, f"{path} is gone: update the list of routes that still carry CH"
        assert not issubclass(
            _response_class(by_path[path]), HiddenAttrsJSONResponse
        ), f"{path} now strips CH: take it off the exceptions list (and out of UX_System.md)"


# --- 3. a real franchise's client payloads -----------------------------------------------------


def _seed_league():
    """The canonical 128-team league, with two user-team players who have a CH and a growth profile."""
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})
    franchise_players_data_collection.delete_many({})
    franchise_recruits_data_collection.delete_many({})
    franchise_team_data_collection.delete_many({})
    db.players.delete_many({})

    team_ids = [ObjectId() for _ in range(128)]
    db.teams.insert_many([
        {
            "_id": team_ids[i],
            "name": f"Team{i}",
            "record": {"W": 0, "L": 0},
            "PF": 0,
            "PA": 0,
            "conference": (i % 16) + 1,
            "region": chr(ord("A") + ((i % 16) // 2)),
            "prestige": 500,
            "player_ids": [] if i > 0 else ["p1", "p2"],
        }
        for i in range(128)
    ])
    attrs = {k: 40 for k in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]}
    attrs.update({f"anchor_{k}": v for k, v in list(attrs.items())})
    attrs.update({"NG": 1, "EM": 50, "MO": 0, "CH": 77, "anchor_CH": 77})
    db.players.insert_many([
        {"_id": pid, "first_name": first, "last_name": last, "team": "Team0", "team_id": team_ids[0],
         "attributes": dict(attrs), "position_ratings": {"PG": 60},
         "development": {"ch_seed": 77, "peak_count": 1, "peak_rungs": [], "family_timing": {}, "ht_total": 0}}
        for pid, first, last in (("p1", "Alice", "One"), ("p2", "Bob", "Two"))
    ])
    return "Team0", str(team_ids[0])


@pytest.mark.order("last")
def test_no_main_client_payload_carries_the_hidden_attribute():
    team_name, team_id = _seed_league()
    created = client.post("/franchise/select-team", json={"team_name": team_name})
    assert created.status_code == 200, created.text
    fid = created.json()["franchise_id"]

    # The database keeps it: this is a display rule, not a data change.
    stored = franchise_players_data_collection.find_one({"franchise_id": fid, "attributes.CH": {"$exists": True}})
    assert stored is not None and "CH" in stored["attributes"]

    q = f"franchise_id={fid}"
    payloads = {
        "create": created,
        "state": client.get(f"/franchise/state?{q}"),
        "roster": client.get(f"/franchise/roster?{q}&team_name={team_name}"),
        "recruits": client.get(f"/franchise/recruits?{q}"),
        "recruiting-data": client.get(f"/franchise/recruiting-data?{q}&team_id={team_id}"),
        "command-center": client.get(f"/franchise/command-center/data?{q}"),
        "team-data": client.get(f"/franchise/team-data?{q}&team_id={team_id}"),
        "team-stats": client.get(f"/franchise/team-stats?{q}"),
        "training-points": client.get(f"/franchise/training-points?{q}&team_id={team_id}"),
        "training-squad-reports": client.get(f"/franchise/training-squad-reports?{q}"),
    }
    served = {name: res for name, res in payloads.items() if res.status_code == 200}
    # The payloads that hold players must be among the ones actually checked.
    for name in ("create", "state", "roster", "recruits"):
        assert name in served, f"{name}: HTTP {payloads[name].status_code} {payloads[name].text[:200]}"
    for name, res in served.items():
        assert hidden_traces(res.json()) == [], f"{name} reveals a hidden attribute"
    # The roster is where it would be if it leaked: players are there, with their visible attributes.
    roster = served["roster"].json()["players"]
    assert len(roster) >= 2
    assert all("SC" in (player.get("attributes") or {}) for player in roster)


def test_the_player_page_payload_has_no_hidden_attribute(monkeypatch):
    import BackEnd.api.api as api_module

    class _Players:
        def find_one(self, query, projection=None):
            if query.get("_id") != "p1":
                return None
            return {"_id": "p1", "first_name": "Alice", "last_name": "One",
                    "attributes": {"SC": 80, "anchor_SC": 80, "CH": 77, "anchor_CH": 77},
                    "development": {"ch_seed": 77, "peak_count": 1},
                    "position_ratings": {"PG": 92}}

    class _Empty:
        def find_one(self, query, projection=None):
            return None

    monkeypatch.setattr(api_module, "players_collection", _Players())
    monkeypatch.setattr(api_module, "franchise_players_data_collection", _Empty())
    res = client.get("/player/p1")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["attributes"] == {"SC": 80, "anchor_SC": 80}
    assert hidden_traces(body) == []


def test_the_practice_squad_report_and_office_rows_never_name_it():
    from BackEnd.api import franchise_routes
    from BackEnd.utils.office_digest import attribute_changes_from_report

    assert "CH" in franchise_routes.TRAINING_SQUAD_ATTR_KEYS, "the practice squad still develops it"
    assert "CH" not in visible_attr_keys(franchise_routes.TRAINING_SQUAD_ATTR_KEYS)
    assert "CH" not in franchise_routes.NEWS_ATTRIBUTE_FULL_NAMES
    rows = attribute_changes_from_report({
        "week": 5,
        "player_attribute_display_movements": {
            "p1": {"name": "Alice One", "CH": {"from": 7, "to": 8}, "SC": {"from": 4, "to": 5}},
        },
    })
    assert [row["attribute"] for row in rows] == ["SC"]


def test_practice_squad_news_copy_counts_and_names_visible_attributes_only():
    from BackEnd.api import franchise_routes

    builder = franchise_routes._build_ps_all_stars_story
    story = builder(
        7,
        [{"name": "Cal Riser", "team_id": "t1", "total_gain": 9, "rt": 55, "pos": "PG",
          "deltas": {"SC": 2, "SH": 2, "CH": 5}}],
        {"t1": "Team0"},
    )
    text = " ".join(story["lines"])
    assert "Clutch" not in text
    assert "increased by 4 attribute points" in text, "the number is the visible attributes' gain"
    assert "Scoring and Shooting" in text


# --- 4. copy stored before the attribute was hidden ------------------------------------------

OLD_STORY = {
    "story_id": "w7-ps-all-stars",
    "week": 7,
    "type": "ps_all_stars",
    "headline": "Practice Squad All-Stars",
    "lines": [
        "Cal Riser of Team0 increased by 9 attribute points this week. His strongest gains were in Shooting and Clutch. He's now rated C+ at PG.",
        "Dee Marsh of Team3 increased by 6 attribute points this week. His strongest gains were in Clutch. He's now rated D at C.",
        "Ian Foley increased by 7 attribute points this week. His strongest gains were in Scoring, Clutch, and Passing. He's now rated C at SF.",
        "Jon Voss increased by 5 attribute points this week. His strongest gains were in Clutch, Strength, Agility, and Basketball IQ. He's now rated C at PF.",
    ],
}


def test_stored_story_copy_is_scrubbed_of_the_attribute_name():
    lines = [scrub_hidden_attr_copy(line) for line in OLD_STORY["lines"]]
    assert lines == [
        "Cal Riser of Team0 increased by 9 attribute points this week. His strongest gains were in Shooting. He's now rated C+ at PG.",
        # Nothing left to name: the clause goes, the sentences around it stay.
        "Dee Marsh of Team3 increased by 6 attribute points this week. He's now rated D at C.",
        "Ian Foley increased by 7 attribute points this week. His strongest gains were in Scoring and Passing. He's now rated C at SF.",
        "Jon Voss increased by 5 attribute points this week. His strongest gains were in Strength, Agility, and Basketball IQ. He's now rated C at PF.",
    ]
    assert hidden_traces(lines) == []


def test_the_ordinary_word_clutch_is_not_the_attribute():
    for text in (
        "Clutch free throws sealed it in the final minute.",
        "How did your team stay so composed in clutch time?",
        "Clutch. That is the only word for that shot.",
        "A clutch three from Scoring leader Cal Riser.",
        "Shooting and Passing were the story tonight.",
    ):
        assert scrub_hidden_attr_copy(text) == text


def test_the_scrub_knows_every_attribute_name_the_copy_uses():
    from BackEnd.api import franchise_routes

    assert set(VISIBLE_ATTR_LABELS) == set(franchise_routes.NEWS_ATTRIBUTE_FULL_NAMES.values())


@pytest.mark.order("last")
def test_a_stored_old_story_is_served_scrubbed_and_stays_as_written():
    team_name, _team_id = _seed_league()
    created = client.post("/franchise/select-team", json={"team_name": team_name})
    assert created.status_code == 200, created.text
    fid = created.json()["franchise_id"]
    db.franchises.update_one({"_id": ObjectId(fid)}, {"$set": {"season_news": [copy.deepcopy(OLD_STORY)]}})

    res = client.get(f"/franchise/news?franchise_id={fid}")
    assert res.status_code == 200, res.text
    served = res.json()["news"]
    assert [story["story_id"] for story in served] == ["w7-ps-all-stars"]
    assert hidden_traces(served) == []
    assert served[0]["lines"][0].endswith("His strongest gains were in Shooting. He's now rated C+ at PG.")
    assert "strongest gains" not in served[0]["lines"][1]
    # Read-time only: the save still holds the story exactly as it was written.
    stored = db.franchises.find_one({"_id": ObjectId(fid)}, {"season_news": 1})["season_news"]
    assert stored[0]["lines"] == OLD_STORY["lines"]
