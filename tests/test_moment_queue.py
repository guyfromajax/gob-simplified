"""Office moment queue: order, cap, deferral, weekly fold. Mongomock + SQLite."""

from bson import ObjectId
import pytest

from BackEnd.api import franchise_routes as fr
from BackEnd.persistence import create_store
from BackEnd.utils.moment_queue import build_moment_queue, collect_moments
from tests.test_persistence_adapter import _mongomock_env

USER = "aaaaaaaaaaaaaaaaaaaaaaaa"
OPP = "bbbbbbbbbbbbbbbbbbbbbbbb"


def _eligible(kind="modal"):
    return {"eligible": True, "kind": kind}


def _queue(**kwargs):
    return build_moment_queue(**kwargs)


def test_priority_order():
    rows = collect_moments(
        championship_moments=[{"id": "c1"}],
        bracket_reveal_modal=_eligible(),
        walk_on_welcome_modal={"eligible": True, "count": 2},
        conference_rs_region_modal=_eligible(),
        region_bye_modal_eligible=True,
        archetype_evolution_pending="scorer",
        bracket_update_modal=_eligible(),
        recruit_visit_modal={"eligible": True, "recruit": {"name": "Ellis Clemons"}},
    )
    assert [row["kind"] for row in rows] == [
        "championship",
        "bracket_reveal",
        "walk_on_welcome",
        "conference_rs_region",
        "region_bye",
        "archetype_evolution",
        "bracket_update",
        "recruit_visit",
    ]
    assert rows[0]["tier"] == "SEASON_PEAK"
    assert rows[0]["duration"] == "long"
    assert rows[6]["tier"] == "WEEKLY"
    assert rows[7]["tier"] == "WEEKLY"


def test_recruiting_results_is_never_queued():
    rows = collect_moments(
        conference_rs_region_modal=_eligible(),
        recruit_visit_modal={"eligible": True, "recruit": {"name": "Ellis"}},
    )
    assert "recruiting_results" not in [row["kind"] for row in rows]


def test_cap_one_when_first_is_long():
    q = _queue(
        championship_moments=[{"id": "c1"}],
        conference_rs_region_modal=_eligible(),
        region_bye_modal_eligible=True,
    )
    assert [m["kind"] for m in q["moments_for_this_visit"]] == ["championship"]
    assert [m["kind"] for m in q["moments"] if m["tier"] != "WEEKLY"] == [
        "championship",
        "conference_rs_region",
        "region_bye",
    ]


def test_cap_two_when_first_is_short_and_second_is_popup():
    q = _queue(
        conference_rs_region_modal=_eligible(),
        region_bye_modal_eligible=True,
        archetype_evolution_pending="scorer",
    )
    assert [m["kind"] for m in q["moments_for_this_visit"]] == [
        "conference_rs_region",
        "region_bye",
    ]
    assert any(m["kind"] == "archetype_evolution" for m in q["moments"])
    assert "archetype_evolution" not in [m["kind"] for m in q["moments_for_this_visit"]]


def test_weekly_items_fold_off_the_popup_list():
    q = _queue(
        conference_rs_region_modal=_eligible(),
        bracket_update_modal=_eligible(),
        recruit_visit_modal={"eligible": True, "recruit": {"name": "Ellis Clemons"}},
    )
    assert [m["kind"] for m in q["moments_for_this_visit"]] == ["conference_rs_region"]
    assert [m["kind"] for m in q["weekly_card_items"]] == ["bracket_update", "recruit_visit"]
    assert all(m["kind"] not in ("bracket_update", "recruit_visit") for m in q["moments_for_this_visit"])


def test_deferral_to_the_next_visit():
    first = _queue(
        conference_rs_region_modal=_eligible(),
        region_bye_modal_eligible=True,
        archetype_evolution_pending="scorer",
    )
    assert [m["kind"] for m in first["moments_for_this_visit"]] == [
        "conference_rs_region",
        "region_bye",
    ]
    nxt = _queue(archetype_evolution_pending="scorer")
    assert [m["kind"] for m in nxt["moments_for_this_visit"]] == ["archetype_evolution"]


def _store_env(kind, tmp_path):
    if kind == "mongo":
        return _mongomock_env(tmp_path)
    return _mongomock_env(
        tmp_path,
        GOB_PERSISTENCE="sqlite",
        GOB_SQLITE_PATH=str(tmp_path / "moment-queue.sqlite"),
    )


@pytest.mark.parametrize("kind", ["mongo", "sqlite"])
def test_seen_endpoint_defers_remaining_moments(kind, tmp_path, monkeypatch):
    store = create_store(_store_env(kind, tmp_path))
    franchise_id = ObjectId()
    store.franchises_collection.insert_one({
        "_id": franchise_id,
        "user_id": "coach-1",
        "current_season": 4,
        "week": 28,
        "eos_tournament_active": True,
        "conference_tournaments": {
            "3": {
                "seeds": {USER: 1, OPP: 2},
                "bracket": {
                    "round1": [{"away_team": USER, "home_team": OPP, "winner": OPP}],
                },
            }
        },
    })
    monkeypatch.setattr(fr, "db", store.db)
    monkeypatch.setattr(
        fr,
        "verify_franchise_owned_by_user",
        lambda *_: store.franchises_collection.find_one({"_id": franchise_id}),
    )

    team_doc = {"conference": 3}
    first_doc = store.franchises_collection.find_one({"_id": franchise_id})
    conference = fr._build_conference_rs_region_modal_payload(first_doc, USER, team_doc)
    first = _queue(
        conference_rs_region_modal=conference,
        region_bye_modal_eligible=True,
        archetype_evolution_pending="scorer",
        recruit_visit_modal={"eligible": True, "recruit": {"name": "Ellis Clemons"}},
    )
    assert conference and conference["eligible"] is True
    assert [m["kind"] for m in first["moments_for_this_visit"]] == [
        "conference_rs_region",
        "region_bye",
    ]
    assert [m["kind"] for m in first["weekly_card_items"]] == ["recruit_visit"]

    fr.mark_conference_rs_region_modal_seen(
        fr.ConferenceRsRegionModalSeenRequest(franchise_id=str(franchise_id)),
        user={"user_id": "coach-1"},
    )
    updated = store.franchises_collection.find_one({"_id": franchise_id})
    assert updated[fr.CONFERENCE_RS_REGION_MODAL_SEEN_SEASON_FIELD] == 4
    conference_after = fr._build_conference_rs_region_modal_payload(updated, USER, team_doc)
    nxt = _queue(
        conference_rs_region_modal=conference_after,
        region_bye_modal_eligible=True,
        archetype_evolution_pending="scorer",
        recruit_visit_modal={"eligible": True, "recruit": {"name": "Ellis Clemons"}},
    )
    assert conference_after is None
    assert [m["kind"] for m in nxt["moments_for_this_visit"]] == [
        "region_bye",
        "archetype_evolution",
    ]
    assert [m["kind"] for m in nxt["weekly_card_items"]] == ["recruit_visit"]
