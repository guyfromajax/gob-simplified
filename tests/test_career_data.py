"""Chapter 7 career data: GP mirror, season GP, season review, milestones, coach-career.

Every store test runs on mongomock AND SQLite, for the desktop coach AND an online
user, because the two must hold the same shape.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

import BackEnd.utils.career_data as cd
import BackEnd.utils.community_highlights as ch
import BackEnd.utils.franchise_geek_points as fgp
import BackEnd.utils.franchise_team_display as ftdisp
import BackEnd.utils.local_coach as lc
import BackEnd.utils.team_slug as ts
import BackEnd.utils.trophy_log as tl
from BackEnd.api import franchise_routes
from BackEnd.api.api import app
from BackEnd.local_identity import LOCAL_PRINCIPAL, LOCAL_USER_ID
from BackEnd.persistence import create_store
from BackEnd.utils.auth import get_current_user
from BackEnd.utils.team_builder_leak_detector import scan_json_for_replaced_name
from tests.test_persistence_adapter import _mongomock_env, _sqlite_env

ROOT = Path(__file__).resolve().parents[1]
SIM_MODULES = (
    "BackEnd/main.py",
    "BackEnd/utils/cpu_week_pool.py",
    "BackEnd/utils/sim_random.py",
    "BackEnd/utils/stat_updater.py",
    "BackEnd/utils/headless_simulation.py",
    "BackEnd/models/game_manager.py",
)
CORE_NAME = "Providence"
DISPLAY_NAME = "Lancaster"
TEAM_KEY = "PROVIDENCE"
GP = 17


@pytest.fixture(params=["mongo", "sqlite"])
def store(request, tmp_path, monkeypatch):
    env = _mongomock_env(tmp_path) if request.param == "mongo" else _sqlite_env(tmp_path)
    s = create_store(env)
    monkeypatch.setattr(lc, "coach_collection", lambda: s.db["save_meta"])
    monkeypatch.setattr(lc, "users_collection", s.users_collection)
    monkeypatch.setattr(tl, "users_collection", s.users_collection)
    monkeypatch.setattr(tl, "franchises_collection", s.franchises_collection)
    monkeypatch.setattr(ftdisp, "teams_collection", s.teams_collection)
    monkeypatch.setattr(fgp, "db", s.db)
    monkeypatch.setattr(fgp, "users_collection", s.users_collection)
    monkeypatch.setattr(cd, "db", s.db)
    monkeypatch.setattr(cd, "franchise_players_data_collection", s.franchise_players_data_collection)
    monkeypatch.setattr(cd, "franchise_team_data_collection", s.franchise_team_data_collection)
    monkeypatch.setattr(ts, "teams_collection", s.teams_collection)
    ts.clear_name_to_team_id_cache()
    yield s
    ts.clear_name_to_team_id_cache()


@pytest.fixture(params=["local", "online"])
def owner(request, store):
    if request.param == "local":
        return LOCAL_USER_ID
    oid = ObjectId()
    store.users_collection.insert_one({"_id": oid, "username": "online-coach"})
    return str(oid)


def _seed(store, owner, *, season=2, week=36, **extra):
    """A Team Builder franchise: user team core 'Providence' shown as 'Lancaster'."""
    user_tid, cpu_tid, fid = ObjectId(), ObjectId(), ObjectId()
    store.teams_collection.insert_many([
        {"_id": user_tid, "name": CORE_NAME, "team_id": TEAM_KEY, "conference": 3, "region": "B"},
        {"_id": cpu_tid, "name": "Concord", "team_id": "CONCORD", "conference": 3, "region": "B"},
    ])
    doc = {
        "_id": fid,
        "user_id": owner,
        "current_season": season,
        "week": week,
        "user_team_id": DISPLAY_NAME,
        "user_team_object_id": str(user_tid),
        "team_builder": {
            "replaced_object_id": str(user_tid),
            "replaced_name": CORE_NAME,
            "name": DISPLAY_NAME,
            "abbreviation": "LAN",
            "asset_strategy": "generated",
        },
        **extra,
    }
    store.franchises_collection.insert_one(doc)
    return doc, str(user_tid), str(cpu_tid)


def _coach_doc(store, owner):
    if owner == LOCAL_USER_ID:
        return store.db["save_meta"].find_one({"_id": lc.LOCAL_COACH_ID}) or {}
    return store.users_collection.find_one({"_id": ObjectId(owner)}) or {}


def _fixed_gp(monkeypatch):
    """Pin the GP draw and count the calls: one delta per award, written once."""
    calls: list[tuple[int, int]] = []

    def fake_randint(lo, hi):
        calls.append((lo, hi))
        return GP

    monkeypatch.setattr(fgp.random, "randint", fake_randint)
    return calls


# --- 1. Geek Points mirror -------------------------------------------------------------------


def test_win_award_gives_the_desktop_coach_the_same_delta_as_online(store, owner, monkeypatch):
    doc, user_tid, _ = _seed(store, owner)
    calls = _fixed_gp(monkeypatch)

    fgp.maybe_award_franchise_win_geek_points(
        owner_user_id=owner,
        user_team_id_str=user_tid,
        winner_team_id=user_tid,
        week=1,
        eos_game_meta=None,
        franchise_id=doc["_id"],
        season=doc["current_season"],
    )

    coach = _coach_doc(store, owner)
    # One draw, one write: the same rule and the same fields on either coach doc.
    assert calls == [(13, 20)]
    assert coach["geek_points"] == GP
    assert coach["geek_points_by_team"][TEAM_KEY] == GP


def test_loss_award_mirrors_and_never_writes_the_other_coach(store, monkeypatch):
    online = ObjectId()
    store.users_collection.insert_one({"_id": online})
    local_doc, local_tid, local_cpu = _seed(store, LOCAL_USER_ID)
    online_doc, online_tid, online_cpu = _seed(store, str(online))
    _fixed_gp(monkeypatch)

    for own, doc, tid, cpu in (
        (LOCAL_USER_ID, local_doc, local_tid, local_cpu),
        (str(online), online_doc, online_tid, online_cpu),
    ):
        fgp.maybe_award_franchise_loss_geek_points(
            owner_user_id=own,
            user_team_id_str=tid,
            winner_team_id=cpu,
            participant_team_ids=(tid, cpu),
            week=1,
            franchise_id=doc["_id"],
            season=doc["current_season"],
        )

    local = store.db["save_meta"].find_one({"_id": lc.LOCAL_COACH_ID})
    remote = store.users_collection.find_one({"_id": online})
    assert local["geek_points"] == remote["geek_points"] == GP
    assert store.users_collection.find_one({"_id": LOCAL_USER_ID}) is None


def test_a_game_the_user_did_not_play_awards_nothing(store, owner, monkeypatch):
    doc, user_tid, cpu_tid = _seed(store, owner)
    _fixed_gp(monkeypatch)
    fgp.maybe_award_franchise_win_geek_points(
        owner_user_id=owner, user_team_id_str=user_tid, winner_team_id=cpu_tid,
        week=1, eos_game_meta=None, franchise_id=doc["_id"], season=2,
    )
    fgp.maybe_award_franchise_loss_geek_points(
        owner_user_id=owner, user_team_id_str=user_tid, winner_team_id=cpu_tid,
        participant_team_ids=(cpu_tid, "other"), week=1,
        franchise_id=doc["_id"], season=2,
    )
    assert "geek_points" not in _coach_doc(store, owner)


# --- 2. season GP buckets --------------------------------------------------------------------


def test_season_gp_accumulates_per_franchise_and_season(store, owner, monkeypatch):
    doc, user_tid, _ = _seed(store, owner)
    fid = str(doc["_id"])
    _fixed_gp(monkeypatch)

    for season in (2, 2, 3):
        fgp.maybe_award_franchise_win_geek_points(
            owner_user_id=owner, user_team_id_str=user_tid, winner_team_id=user_tid,
            week=1, eos_game_meta=None, franchise_id=fid, season=season,
        )

    coach = _coach_doc(store, owner)
    assert coach["season_gp"] == {f"{fid}:2": GP * 2, f"{fid}:3": GP}
    assert coach["geek_points"] == GP * 3
    assert cd.read_season_gp(owner) == {f"{fid}:2": GP * 2, f"{fid}:3": GP}
    assert cd.season_gp_for(cd.read_season_gp(owner), fid, 2) == GP * 2
    assert cd.season_gp_for(cd.read_season_gp(owner), fid, 9) is None


def test_a_caller_without_franchise_context_still_buckets_the_season(store, owner, monkeypatch):
    """The CPU-week sim block cannot pass them; the owner's one franchise resolves it."""
    doc, user_tid, _ = _seed(store, owner, week=5)
    _fixed_gp(monkeypatch)

    fgp.maybe_award_franchise_win_geek_points(
        owner_user_id=owner, user_team_id_str=user_tid, winner_team_id=user_tid,
        week=5, eos_game_meta=None,
    )

    assert _coach_doc(store, owner)["season_gp"] == {f"{doc['_id']}:2": GP}


def test_career_gp_still_lands_when_the_season_cannot_be_resolved(store, owner, monkeypatch):
    """Two saves coaching the same team in the same week: bucket skipped, total kept."""
    doc_a, user_tid, _ = _seed(store, owner, week=5)
    store.franchises_collection.insert_one({
        **{k: v for k, v in doc_a.items() if k != "_id"},
        "_id": ObjectId(),
    })
    _fixed_gp(monkeypatch)

    fgp.maybe_award_franchise_win_geek_points(
        owner_user_id=owner, user_team_id_str=user_tid, winner_team_id=user_tid,
        week=5, eos_game_meta=None,
    )

    coach = _coach_doc(store, owner)
    assert coach["geek_points"] == GP
    assert "season_gp" not in coach


# --- 3 + 4. season review snapshot ------------------------------------------------------------


def _pick(pid, name, team_id):
    return {"player_id": pid, "name": name, "team_id": team_id, "team_name": "x", "score": 1.0}


def _fpd(fid, pid, first, *, pts, reb=40, ast=20, gp=20, stl=None, position="SF", year="junior"):
    season = {"GP": gp, "PTS": pts, "REB": reb, "AST": ast}
    if stl is not None:
        season["STL"] = stl
    return {
        "franchise_id": str(fid),
        "player_id": pid,
        "meta": {"first_name": first, "last_name": "Hall", "position": position, "year": year},
        "season": season,
    }


def _seed_roster(store, doc, user_tid, players):
    store.franchise_team_data_collection.insert_one({
        "franchise_id": doc["_id"],
        "team_id": ObjectId(user_tid),
        "players": [p["player_id"] for p in players],
        "natl_rank": 4,
    })
    store.franchise_players_data_collection.insert_many(players)


def test_season_record_snapshot_carries_the_review_fields(store, owner, monkeypatch):
    doc, user_tid, cpu_tid = _seed(store, owner)
    doc["results"] = {
        "1": [{"home_id": user_tid, "away_id": cpu_tid, "home_score": 80, "away_score": 70}],
        "2": [{"home_id": cpu_tid, "away_id": user_tid, "home_score": 75, "away_score": 60}],
    }
    doc["awards"] = {"all_american_teams": {
        "first_team": [_pick("p2", "Bea Hall", user_tid), _pick("c1", "Cpu", cpu_tid)],
        "third_team": [_pick("p3", "Cy Hall", user_tid)],
    }}
    doc["week_35_recruiting_results"] = {"signed_players": [
        {"team_id": user_tid, "name": "Dee Prospect", "pos": "PG", "home_region": "B",
         "rt": 71, "potential_rt_ratcheted": 84},
        {"team_id": user_tid, "name": "Walk On", "walk_on": True, "pos": "C"},
        {"team_id": cpu_tid, "name": "Not Ours", "pos": "SG"},
    ]}
    _seed_roster(store, doc, user_tid, [
        _fpd(doc["_id"], "p1", "Ada", pts=400, stl=30),
        _fpd(doc["_id"], "p2", "Bea", pts=100),
        _fpd(doc["_id"], "p3", "Cy", pts=60),
    ])
    _fixed_gp(monkeypatch)
    fgp.maybe_award_franchise_win_geek_points(
        owner_user_id=owner, user_team_id_str=user_tid, winner_team_id=user_tid,
        week=1, eos_game_meta=None, franchise_id=doc["_id"], season=2,
    )

    for _ in range(2):  # idempotent replay
        tl.record_season_record_trophy(doc)

    trophies = _coach_doc(store, owner)["trophies"]
    assert len(trophies) == 1
    detail = trophies[0]["detail"]
    assert detail["wins"] == 1 and detail["losses"] == 1
    assert detail["national_rank"] == 4
    assert detail["season_gp"] == GP
    # An All-American leads the review even on fewer points; PPG fills the rest.
    assert [p["name"] for p in detail["best_players"]] == ["Bea Hall", "Cy Hall", "Ada Hall"]
    assert [p.get("all_american") for p in detail["best_players"]] == [
        "all_american_1", "all_american_3", None]
    assert detail["best_players"][0]["stats"] == {"ppg": 5, "rpg": 2, "apg": 1}
    assert detail["best_players"][0]["position"] == "SF"
    assert detail["best_players"][0]["class_year"] == "JR"
    # STL is on Ada's season line only, so only her row carries spg.
    assert detail["best_players"][2]["stats"] == {"ppg": 20, "rpg": 2, "apg": 1, "spg": 1.5}
    assert detail["class_signed"] == [
        {"name": "Dee Prospect", "position": "PG", "home_region": "B",
         "rt_now": 71, "rt_potential": 84}
    ]
    # region_tournaments never stores a seeds map, so the field is omitted, not derived.
    assert "region_seed" not in detail


def test_snapshot_omits_every_field_whose_source_is_absent(store, owner):
    doc, user_tid, _ = _seed(store, owner)
    tl.record_season_record_trophy(doc)
    assert _coach_doc(store, owner)["trophies"][0]["detail"] == {"wins": 0, "losses": 0}


def test_region_seed_is_reported_when_a_seeds_map_exists(store, owner):
    doc, user_tid, _ = _seed(store, owner)
    doc["region_tournaments"] = {"B": {"seeds": {user_tid: 3}, "round1": [], "final": []}}
    assert cd.region_seed(doc, user_tid) == 3
    assert cd.region_seed({"region_tournaments": {"B": {"round1": []}}}, user_tid) is None


def test_best_players_keeps_roster_order_on_equal_points(store, owner):
    doc, user_tid, _ = _seed(store, owner)
    _seed_roster(store, doc, user_tid, [
        _fpd(doc["_id"], "p1", "Ada", pts=200),
        _fpd(doc["_id"], "p2", "Bea", pts=200),
        _fpd(doc["_id"], "p3", "Cy", pts=200),
        _fpd(doc["_id"], "p4", "Dee", pts=200),
    ])
    for _ in range(3):
        rows = cd.best_players(doc, user_tid, {})
        assert [r["player_id"] for r in rows] == ["p1", "p2", "p3"]


def test_class_signed_omits_fields_the_signing_entry_lacks(store, owner):
    doc, user_tid, _ = _seed(store, owner)
    doc["week_35_recruiting_results"] = {"signed_players": [
        {"team_id": user_tid, "name": "Sparse", "pos": "PF", "home_region": "--"},
    ]}
    assert cd.class_signed(doc, user_tid) == [{"name": "Sparse", "position": "PF"}]


# --- 5. milestones --------------------------------------------------------------------------


def _conference_tournaments(user_tid, cpu_tid):
    return {"3": {
        "seeds": {user_tid: 2, cpu_tid: 1},
        "bracket": {"round1": [{"away_team": cpu_tid, "home_team": user_tid, "winner": None}],
                    "round2": [], "final": []},
    }}


def test_each_milestone_is_recorded_once_per_coach(store, owner):
    doc, user_tid, cpu_tid = _seed(store, owner)
    signed = [{"team_id": user_tid, "name": "One"}, {"team_id": user_tid, "name": "Two", "walk_on": True}]
    later, later_tid, later_cpu = _seed(store, owner, season=5)

    for _ in range(2):
        tl.record_first_signing_class_milestone(doc, signed)
        tl.record_first_bracket_milestone(doc, _conference_tournaments(user_tid, cpu_tid))
        tl.record_first_archetype_milestone(doc, "motivator")
    # A second season, and a second program, add nothing: these are career firsts.
    tl.record_first_signing_class_milestone(later, [{"team_id": later_tid, "name": "Three"}])
    tl.record_first_bracket_milestone(later, _conference_tournaments(later_tid, later_cpu))
    tl.record_first_archetype_milestone(later, "tactician")

    trophies = _coach_doc(store, owner)["trophies"]
    assert [t["kind"] for t in trophies] == list(tl.MILESTONE_KINDS)
    by_kind = {t["kind"]: t for t in trophies}
    assert by_kind["milestone_first_bracket"]["key"] == "coach:milestone_first_bracket"
    assert by_kind["milestone_first_signing_class"]["detail"] == {"signed": 1}
    assert by_kind["milestone_first_bracket"]["detail"] == {"seed": 2}
    assert by_kind["milestone_first_archetype"]["detail"] == {"archetype": "motivator"}
    assert all(t["team_name"] == DISPLAY_NAME for t in trophies)


def test_milestones_need_the_fact_to_be_true(store, owner):
    doc, user_tid, cpu_tid = _seed(store, owner)
    # Walk-ons are not a signing class; a bracket without the user team is not theirs.
    assert tl.record_first_signing_class_milestone(
        doc, [{"team_id": user_tid, "name": "W", "walk_on": True}]) is False
    assert tl.record_first_bracket_milestone(
        doc, _conference_tournaments(cpu_tid, "other")) is False
    assert tl.record_first_archetype_milestone(doc, "") is False
    assert _coach_doc(store, owner).get("trophies") is None


def test_first_archetype_milestone_fires_offline_at_the_same_write_point(store, monkeypatch):
    doc, user_tid, _ = _seed(store, LOCAL_USER_ID)
    monkeypatch.setattr(ch, "franchises_collection", store.franchises_collection)
    store.db["save_meta"].update_one(
        {"_id": lc.LOCAL_COACH_ID}, {"$set": {"lead_archetype": "motivator"}}, upsert=True
    )

    # First establish: lead_before empty. Records the milestone, queues no evolution.
    ch.record_archetype_change_if_any(doc["_id"], LOCAL_USER_ID, "")
    coach = _coach_doc(store, LOCAL_USER_ID)
    assert [t["kind"] for t in coach["trophies"]] == ["milestone_first_archetype"]
    assert not coach.get("archetype_evolution_pending")

    # A later change is an evolution: pending lands on the desktop coach doc.
    store.db["save_meta"].update_one(
        {"_id": lc.LOCAL_COACH_ID}, {"$set": {"lead_archetype": "tactician"}}
    )
    ch.record_archetype_change_if_any(doc["_id"], LOCAL_USER_ID, "motivator")
    coach = _coach_doc(store, LOCAL_USER_ID)
    assert coach["archetype_evolution_pending"] == "tactician"
    assert [t["kind"] for t in coach["trophies"]] == ["milestone_first_archetype"]


def test_command_center_reads_the_desktop_archetype_signals(store):
    store.db["save_meta"].update_one(
        {"_id": lc.LOCAL_COACH_ID},
        {"$set": {"lead_archetype": "tactician", "archetype_evolution_pending": "tactician"}},
        upsert=True,
    )
    local = franchise_routes._coach_archetype_signals(dict(LOCAL_PRINCIPAL))
    assert local == {
        "archetype_evolution_pending": "tactician",
        "lead_archetype": "tactician",
        "archetype_reveal_seen": False,
    }
    # Online still reads the authenticated principal.
    online = franchise_routes._coach_archetype_signals(
        {"user_id": str(ObjectId()), "archetype_evolution_pending": "grinder",
         "lead_archetype": "grinder", "archetype_reveal_seen": True}
    )
    assert online["archetype_evolution_pending"] == "grinder"
    assert online["archetype_reveal_seen"] is True


def _reveal_route_env(store, monkeypatch):
    import BackEnd.utils.browse_cache as browse_cache
    import BackEnd.utils.ownership as ownership

    monkeypatch.setattr(ownership, "franchises_collection", store.franchises_collection)
    monkeypatch.setattr(browse_cache, "franchise_collection", lambda: store.franchises_collection)


def test_offline_first_archetype_reveal_is_marked_seen_on_the_save(store, monkeypatch):
    """Offline the seen flag has nowhere remote to go: it is saved on this computer."""
    from BackEnd.utils.season_moments import first_archetype_payload

    _reveal_route_env(store, monkeypatch)
    doc, _, _ = _seed(store, LOCAL_USER_ID, browse_rev=4)
    store.db["save_meta"].update_one(
        {"_id": lc.LOCAL_COACH_ID}, {"$set": {"lead_archetype": "tactician"}}, upsert=True
    )
    before = franchise_routes._coach_archetype_signals(dict(LOCAL_PRINCIPAL))
    assert first_archetype_payload(before) == {"eligible": True, "archetype": "tactician"}

    request = franchise_routes.ArchetypeRevealSeenRequest(franchise_id=str(doc["_id"]))
    out = franchise_routes.mark_archetype_reveal_seen_offline(request, user=dict(LOCAL_PRINCIPAL))
    assert out == {"archetype_reveal_seen": True}

    after = franchise_routes._coach_archetype_signals(dict(LOCAL_PRINCIPAL))
    assert after["archetype_reveal_seen"] is True
    assert after["lead_archetype"] == "tactician", "the rest of the coach doc is untouched"
    assert first_archetype_payload(after) is None, "the reveal is not offered a second time"
    # The Office read is keyed on browse_rev: without the bump the next load would be
    # a 304 of the body that still carried the moment.
    assert store.franchises_collection.find_one({"_id": doc["_id"]})["browse_rev"] == 5

    # A second call changes nothing but the revision.
    franchise_routes.mark_archetype_reveal_seen_offline(request, user=dict(LOCAL_PRINCIPAL))
    assert franchise_routes._coach_archetype_signals(dict(LOCAL_PRINCIPAL))["archetype_reveal_seen"] is True


def test_offline_archetype_route_refuses_an_online_coach(store, monkeypatch):
    """Online keeps its own path (PATCH /api/auth/archetype-reveal-seen); this route is not it."""
    from fastapi import HTTPException

    _reveal_route_env(store, monkeypatch)
    oid = ObjectId()
    store.users_collection.insert_one({"_id": oid, "username": "online-coach", "lead_archetype": "grinder"})
    doc, _, _ = _seed(store, str(oid), browse_rev=2)
    request = franchise_routes.ArchetypeRevealSeenRequest(franchise_id=str(doc["_id"]))
    with pytest.raises(HTTPException) as denied:
        franchise_routes.mark_archetype_reveal_seen_offline(request, user={"user_id": str(oid)})
    assert denied.value.status_code == 404
    assert "archetype_reveal_seen" not in store.users_collection.find_one({"_id": oid})
    assert store.db["save_meta"].find_one({"_id": lc.LOCAL_COACH_ID}) is None
    assert store.franchises_collection.find_one({"_id": doc["_id"]})["browse_rev"] == 2
    # Someone else's franchise is still refused before anything else.
    with pytest.raises(HTTPException) as foreign:
        franchise_routes.mark_archetype_reveal_seen_offline(request, user=dict(LOCAL_PRINCIPAL))
    assert foreign.value.status_code == 403


def test_offline_archetype_evolution_row_is_cleared_on_the_save(store, monkeypatch):
    """The "Coaching archetype evolved" weekly row is cleared on this computer, so it shows once."""
    from BackEnd.utils.moment_queue import build_moment_queue

    def weekly_kinds():
        signals = franchise_routes._coach_archetype_signals(dict(LOCAL_PRINCIPAL))
        queue = build_moment_queue(archetype_evolution_pending=signals["archetype_evolution_pending"])
        return [row["kind"] for row in queue["weekly_card_items"]]

    _reveal_route_env(store, monkeypatch)
    doc, _, _ = _seed(store, LOCAL_USER_ID, browse_rev=7)
    store.db["save_meta"].update_one(
        {"_id": lc.LOCAL_COACH_ID},
        {"$set": {"lead_archetype": "tactician", "archetype_reveal_seen": True,
                  "archetype_evolution_pending": "tactician"}},
        upsert=True,
    )
    assert weekly_kinds() == ["archetype_evolution"]

    request = franchise_routes.ArchetypeRevealSeenRequest(franchise_id=str(doc["_id"]))
    out = franchise_routes.clear_archetype_evolution_offline(request, user=dict(LOCAL_PRINCIPAL))
    assert out == {"archetype_evolution_pending": ""}

    after = franchise_routes._coach_archetype_signals(dict(LOCAL_PRINCIPAL))
    assert after == {"archetype_evolution_pending": "", "lead_archetype": "tactician", "archetype_reveal_seen": True}
    assert weekly_kinds() == [], "the row is not offered a second time"
    # Removed, not blanked: SQLite cannot project a field that holds an empty string.
    assert "archetype_evolution_pending" not in store.db["save_meta"].find_one({"_id": lc.LOCAL_COACH_ID})
    # Without the bump the next Office read would be a 304 of the body that still had the row.
    assert store.franchises_collection.find_one({"_id": doc["_id"]})["browse_rev"] == 8

    # A later evolution sets the key again and the row comes back, once.
    store.db["save_meta"].update_one(
        {"_id": lc.LOCAL_COACH_ID}, {"$set": {"archetype_evolution_pending": "grinder"}}
    )
    assert weekly_kinds() == ["archetype_evolution"]


def test_offline_archetype_evolution_route_refuses_an_online_coach(store, monkeypatch):
    """Online keeps the account's key (PATCH /api/auth/archetype-evolution-seen); this route is not it."""
    from fastapi import HTTPException

    _reveal_route_env(store, monkeypatch)
    oid = ObjectId()
    store.users_collection.insert_one(
        {"_id": oid, "username": "online-coach", "archetype_evolution_pending": "grinder"}
    )
    doc, _, _ = _seed(store, str(oid), browse_rev=2)
    request = franchise_routes.ArchetypeRevealSeenRequest(franchise_id=str(doc["_id"]))
    with pytest.raises(HTTPException) as denied:
        franchise_routes.clear_archetype_evolution_offline(request, user={"user_id": str(oid)})
    assert denied.value.status_code == 404
    assert store.users_collection.find_one({"_id": oid})["archetype_evolution_pending"] == "grinder"
    assert store.db["save_meta"].find_one({"_id": lc.LOCAL_COACH_ID}) is None
    assert store.franchises_collection.find_one({"_id": doc["_id"]})["browse_rev"] == 2
    # Someone else's franchise is still refused before anything else.
    with pytest.raises(HTTPException) as foreign:
        franchise_routes.clear_archetype_evolution_offline(request, user=dict(LOCAL_PRINCIPAL))
    assert foreign.value.status_code == 403


# --- 6 + 7. coach-career ---------------------------------------------------------------------


@pytest.fixture
def as_user():
    def _set(user):
        app.dependency_overrides[get_current_user] = lambda: dict(user)
    yield _set
    app.dependency_overrides.pop(get_current_user, None)


def _season_record(fid, season, wins, losses, gp):
    return {
        "key": f"{fid}:{season}:season_record:t", "season": season, "kind": "season_record",
        "team_id": "t", "team_name": DISPLAY_NAME, "franchise_id": fid,
        "at": None, "detail": {"wins": wins, "losses": losses, "season_gp": gp},
    }


def _title(fid, season, kind):
    return {"key": f"{fid}:{season}:{kind}:t", "season": season, "kind": kind, "team_id": "t",
            "team_name": DISPLAY_NAME, "franchise_id": fid, "at": None}


def test_top_seasons_rank_by_gp_then_win_rate_with_live_seasons(store, owner):
    doc, user_tid, cpu_tid = _seed(store, owner, season=4, week=12)
    fid = str(doc["_id"])
    other = str(ObjectId())
    doc["results"] = {
        "1": [{"home_id": user_tid, "away_id": cpu_tid, "home_score": 80, "away_score": 70}],
        "2": [{"home_id": user_tid, "away_id": cpu_tid, "home_score": 81, "away_score": 70}],
        "3": [{"home_id": cpu_tid, "away_id": user_tid, "home_score": 90, "away_score": 60}],
    }
    store.franchises_collection.update_one({"_id": doc["_id"]}, {"$set": {"results": doc["results"]}})
    trophies = [
        _season_record(fid, 1, 20, 10, 500),
        _season_record(fid, 2, 30, 4, 900),
        _season_record(other, 3, 10, 20, 500),
        _title(fid, 2, "national"),
    ]
    coach = {"trophies": trophies, "record": {"wins": 60, "losses": 34}, "geek_points": 4060,
             "season_gp": {f"{fid}:4": 700}}
    franchises = list(store.franchises_collection.find({"user_id": owner}))

    extras = cd.coach_career_extras(coach, franchises)

    assert [(r["season"], r["season_gp"]) for r in extras["top_seasons"]] == [
        (2, 900), (4, 700), (1, 500), (3, 500)]
    # Equal GP: the better win % ranks first (season 1 at .667 over season 3 at .333).
    assert [r["franchise_id"] for r in extras["top_seasons"][2:]] == [fid, other]
    live = extras["top_seasons"][1]
    assert live["in_progress"] is True and live["week"] == 12
    assert (live["wins"], live["losses"]) == (2, 1)
    assert live["team_name"] == DISPLAY_NAME and live["team_slug"] == "lancaster"
    assert live["finish"] is None
    best = extras["top_seasons"][0]
    assert best["in_progress"] is False and best["week"] is None
    assert best["finish"] == "National Champions"
    assert extras["seasons_completed"] == 3
    assert extras["programs"] == 2
    assert extras["geek_points"] == 4060
    assert extras["win_pct_display"] == ".638"


def test_finish_label_prefers_a_title_then_the_round():
    assert cd.finish_label({"furthest_round": "region_final"}, {"conf_t"}) == "Conference Tournament Champions"
    assert cd.finish_label({"furthest_round": "region_final"}, set()) == "Region Final"
    assert cd.finish_label({"furthest_round": "missed"}, set()) == "Missed the Bracket"
    assert cd.finish_label({}, set()) is None


def test_win_pct_display_is_three_decimals_and_absent_before_any_game():
    assert cd.win_pct_display({"wins": 73, "losses": 22}) == ".768"
    assert cd.win_pct_display({"wins": 2, "losses": 0}) == "1.000"
    assert cd.win_pct_display({"wins": 0, "losses": 0}) is None
    assert cd.win_pct_display(None) is None


def test_coach_career_route_returns_the_computed_career_local(store, monkeypatch, as_user):
    monkeypatch.setattr(franchise_routes, "local_coach_doc", lc.local_coach_doc)
    monkeypatch.setattr(franchise_routes, "db", store.db)
    doc, user_tid, _ = _seed(store, LOCAL_USER_ID, season=3, week=9)
    fid = str(doc["_id"])
    store.db["save_meta"].update_one(
        {"_id": lc.LOCAL_COACH_ID},
        {"$set": {
            "record": {"wins": 73, "losses": 22, "total_games": 95, "win_rate": 77},
            "championships_total": {"conf_rs": 1, "conf_t": 1, "region": 1, "national": 0},
            "geek_points": 4060,
            "season_gp": {f"{fid}:3": 620},
            "trophies": [_season_record(fid, 1, 18, 12, 400), _season_record(fid, 2, 25, 8, 800)],
        }},
        upsert=True,
    )
    as_user(LOCAL_PRINCIPAL)

    body = TestClient(app).get("/franchise/coach-career").json()

    assert body["record"]["win_rate"] == 77
    assert body["win_pct_display"] == ".768"
    assert body["geek_points"] == 4060
    assert body["seasons_completed"] == 2
    assert body["programs"] == 1
    assert [(r["season"], r["season_gp"], r["in_progress"]) for r in body["top_seasons"]] == [
        (2, 800, False), (3, 620, True), (1, 400, False)]
    assert not scan_json_for_replaced_name(body, CORE_NAME)


def test_coach_career_route_is_empty_but_shaped_for_a_new_coach(store, monkeypatch, as_user):
    monkeypatch.setattr(franchise_routes, "local_coach_doc", lc.local_coach_doc)
    monkeypatch.setattr(franchise_routes, "db", store.db)
    as_user(LOCAL_PRINCIPAL)

    body = TestClient(app).get("/franchise/coach-career").json()

    assert body["record"]["win_rate"] == 0
    assert body["win_pct_display"] is None
    assert (body["geek_points"], body["seasons_completed"], body["programs"]) == (0, 0, 0)
    assert body["top_seasons"] == [] and body["trophies"] == []


def test_coach_career_route_computes_the_same_shape_online(as_user):
    users = franchise_routes._store.users_collection
    user_oid, fid = ObjectId(), str(ObjectId())
    users.insert_one({
        "_id": user_oid, "username": "online-coach",
        "record": {"wins": 12, "losses": 8, "total_games": 20, "win_rate": 60},
        "geek_points": 310,
        "season_gp": {f"{fid}:1": 310},
        "trophies": [_season_record(fid, 1, 12, 8, 310), _title(fid, 1, "region")],
    })
    as_user({"user_id": str(user_oid), "email": "o@example.com"})
    try:
        body = TestClient(app).get("/franchise/coach-career").json()
        assert body["win_pct_display"] == ".600"
        assert body["geek_points"] == 310
        assert body["seasons_completed"] == 1
        assert body["programs"] == 1
        assert body["top_seasons"][0]["finish"] == "Region Champions"
        assert not scan_json_for_replaced_name(body, CORE_NAME)
    finally:
        users.delete_one({"_id": user_oid})


# --- 8. guard -------------------------------------------------------------------------------


def test_sim_and_persist_internals_never_mention_career_data():
    for rel in SIM_MODULES:
        text = (ROOT / rel).read_text()
        assert "career_data" not in text, rel
        assert "season_gp" not in text, rel
    src = inspect.getsource(franchise_routes._complete_week_finish_cpu_and_persist)
    for token in ("career_data", "season_gp", "milestone", "franchise_id=franchise_id,\n            season"):
        assert token not in src, token
    # The GP helpers take the franchise context as optional keywords, so the CPU-week
    # block keeps its existing call.
    for fn in (fgp.maybe_award_franchise_win_geek_points, fgp.maybe_award_franchise_loss_geek_points):
        params = inspect.signature(fn).parameters
        assert params["franchise_id"].default is None
        assert params["season"].default is None
