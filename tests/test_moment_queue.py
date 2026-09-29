"""Office moment queue v2: tiers, priority, cap, style/sting, deferral, weekly fold.

Every store-backed case runs on mongomock and SQLite.
"""

import inspect
from pathlib import Path

from bson import ObjectId
import pytest

import BackEnd.utils.career_data as cd
from BackEnd.api import franchise_routes as fr
from BackEnd.persistence import create_store
from BackEnd.utils.moment_queue import (
    STING_MILESTONE,
    STING_SEASON_PEAK,
    build_moment_queue,
    collect_moments,
)
from BackEnd.utils.season_moments import user_in_bracket
from tests.test_persistence_adapter import _mongomock_env

ROOT = Path(__file__).resolve().parents[1]

USER = "aaaaaaaaaaaaaaaaaaaaaaaa"
OPP = "bbbbbbbbbbbbbbbbbbbbbbbb"


def _eligible(kind="modal", **extra):
    return {"eligible": True, "kind": kind, **extra}


def _queue(**kwargs):
    return build_moment_queue(**kwargs)


def _all_kinds(**overrides):
    """Every kind eligible at once, so order and tier are checked together."""
    kwargs = dict(
        championship_moments=[{"id": "c1"}],
        season_review={"eligible": True, "season": 3},
        elimination={"eligible": True, "round_name": "Region Tourney Championship"},
        bracket_reveal_modal=_eligible(reveal_key="region:3"),
        user_in_revealed_bracket=True,
        signed_class={"eligible": True, "count": 4, "recruits": [{"name": "Dee"}]},
        walk_on_welcome_modal={"eligible": True, "count": 2},
        region_bye_modal_eligible=True,
        conference_rs_region_modal=_eligible(),
        first_archetype={"eligible": True, "archetype": "grinder"},
        bracket_update_modal=_eligible(update_key="update:region:3:31"),
        recruit_visit_modal={"eligible": True, "recruit": {"name": "Ellis Clemons"}},
        archetype_evolution_pending="scorer",
    )
    kwargs.update(overrides)
    return kwargs


# --- 1 + 2. kinds, tiers, priority -------------------------------------------------------------


def test_every_kind_has_its_tier_and_priority_in_order():
    rows = collect_moments(**_all_kinds())

    assert [(row["kind"], row["tier"], row["priority"]) for row in rows] == [
        ("championship", "SEASON_PEAK", 10),
        ("season_review", "SEASON_PEAK", 15),
        ("elimination", "MILESTONE", 20),
        ("bracket_reveal", "MILESTONE", 30),
        ("signed_class", "MILESTONE", 40),
        ("walk_on_welcome", "MILESTONE", 50),
        ("region_bye", "MILESTONE", 60),
        ("conference_rs_region", "MILESTONE", 65),
        ("first_archetype", "MILESTONE", 70),
        ("bracket_update", "WEEKLY", 80),
        ("recruit_visit", "WEEKLY", 90),
        ("archetype_evolution", "WEEKLY", 100),
    ]


def test_weekly_tier_order_is_update_then_visit_then_evolution_then_reveal_not_in():
    rows = collect_moments(**_all_kinds(user_in_revealed_bracket=False))
    weekly = [row["kind"] for row in rows if row["tier"] == "WEEKLY"]
    assert weekly == ["bracket_update", "recruit_visit", "archetype_evolution", "bracket_reveal"]


def test_durations_match_the_ladder():
    rows = {row["kind"]: row.get("duration") for row in collect_moments(**_all_kinds())}
    assert rows == {
        "championship": "long",
        "season_review": "long",
        "elimination": "short",
        "bracket_reveal": "long",
        "signed_class": "long",
        "walk_on_welcome": "long",
        "region_bye": "short",
        "conference_rs_region": "short",
        "first_archetype": "short",
        # Weekly items never pop, so they carry no duration.
        "bracket_update": None,
        "recruit_visit": None,
        "archetype_evolution": None,
    }


def test_recruiting_results_is_never_queued_as_itself():
    rows = collect_moments(
        conference_rs_region_modal=_eligible(),
        signed_class={"eligible": True, "count": 2, "recruits": []},
    )
    assert "recruiting_results" not in [row["kind"] for row in rows]
    # The signing class is queued under its own kind, keyed to the existing seen stamp.
    signed = next(row for row in rows if row["kind"] == "signed_class")
    assert signed["seen_key"] == "recruiting_results_modal_seen_season"


# --- 5. style and sting ------------------------------------------------------------------------


def test_style_and_sting_are_server_decided():
    rows = {row["kind"]: row for row in collect_moments(**_all_kinds())}

    for kind in ("championship", "season_review"):
        assert (rows[kind]["style"], rows[kind]["sting"]) == ("gold", STING_SEASON_PEAK)
    for kind in ("bracket_reveal", "signed_class", "walk_on_welcome", "region_bye",
                 "conference_rs_region", "first_archetype"):
        assert (rows[kind]["style"], rows[kind]["sting"]) == ("gold", STING_MILESTONE)
    # Elimination is dignified: no gold, no sound.
    assert (rows["elimination"]["style"], rows["elimination"]["sting"]) == ("quiet", None)
    for kind in ("bracket_update", "recruit_visit", "archetype_evolution"):
        assert (rows[kind]["style"], rows[kind]["sting"]) == (None, None)


# --- 4. cap ------------------------------------------------------------------------------------


def test_a_championship_and_its_review_are_the_only_pair_that_shows_together():
    q = _queue(**_all_kinds())

    assert [m["kind"] for m in q["moments_for_this_visit"]] == ["championship", "season_review"]
    # Nothing else rides along, however short it is.
    assert len(q["moments_for_this_visit"]) == 2


def test_a_season_peak_shows_alone():
    q = _queue(
        season_review={"eligible": True, "season": 3},
        elimination={"eligible": True},
        region_bye_modal_eligible=True,
    )
    assert [m["kind"] for m in q["moments_for_this_visit"]] == ["season_review"]
    assert [m["kind"] for m in q["moments"] if m["tier"] != "WEEKLY"] == [
        "season_review", "elimination", "region_bye",
    ]


def test_cap_one_when_the_first_is_long():
    q = _queue(
        bracket_reveal_modal=_eligible(),
        user_in_revealed_bracket=True,
        region_bye_modal_eligible=True,
    )
    assert [m["kind"] for m in q["moments_for_this_visit"]] == ["bracket_reveal"]


def test_cap_two_when_the_first_is_short():
    q = _queue(
        elimination={"eligible": True},
        region_bye_modal_eligible=True,
        conference_rs_region_modal=_eligible(),
    )
    assert [m["kind"] for m in q["moments_for_this_visit"]] == ["elimination", "region_bye"]
    assert "conference_rs_region" not in [m["kind"] for m in q["moments_for_this_visit"]]


def test_a_short_first_does_not_pull_up_a_weekly_second():
    q = _queue(region_bye_modal_eligible=True, bracket_update_modal=_eligible())
    assert [m["kind"] for m in q["moments_for_this_visit"]] == ["region_bye"]
    assert [m["kind"] for m in q["weekly_card_items"]] == ["bracket_update"]


# --- 1. bracket reveal in vs not in ------------------------------------------------------------


def test_bracket_reveal_is_a_milestone_only_when_the_user_is_in_it():
    payload = _eligible(reveal_key="conference:4")
    in_it = collect_moments(bracket_reveal_modal=payload, user_in_revealed_bracket=True)[0]
    assert (in_it["tier"], in_it["priority"], in_it["duration"]) == ("MILESTONE", 30, "long")
    assert "href" not in in_it

    folded = collect_moments(bracket_reveal_modal=payload, user_in_revealed_bracket=False)[0]
    assert (folded["tier"], folded["priority"]) == ("WEEKLY", 110)
    assert folded["href"] == "/franchise-command-center.html?tab=tournament-view"
    # Either way it is the same moment, so the seen key does not change.
    assert in_it["seen_key"] == folded["seen_key"] == "conference:4"


def test_user_in_bracket_reads_both_slots_of_every_round():
    bracket = {
        "round1": [{"home_team": OPP, "away_team": "cccc"}],
        "final": [{"home_team": "R1_0", "away_team": USER}],
    }
    assert user_in_bracket(bracket, USER) is True
    assert user_in_bracket(bracket, OPP) is True
    assert user_in_bracket(bracket, "dddd") is False
    assert user_in_bracket(None, USER) is False


# --- 1. first archetype vs evolution -----------------------------------------------------------


def test_first_archetype_pops_and_an_evolution_folds():
    first = collect_moments(first_archetype={"eligible": True, "archetype": "grinder"})[0]
    assert (first["tier"], first["priority"], first["duration"]) == ("MILESTONE", 70, "short")
    assert first["seen_key"] == "archetype_reveal_seen"

    evolved = collect_moments(archetype_evolution_pending="scorer")[0]
    assert (evolved["tier"], evolved["priority"]) == ("WEEKLY", 100)
    assert evolved["seen_key"] == "archetype_evolution_pending"


def test_first_archetype_payload_gate():
    from BackEnd.utils.season_moments import first_archetype_payload

    assert first_archetype_payload(
        {"lead_archetype": "grinder", "archetype_reveal_seen": False,
         "archetype_evolution_pending": ""}
    ) == {"eligible": True, "archetype": "grinder"}
    # No games yet, reveal already seen, or an evolution instead: not a first establish.
    assert first_archetype_payload({"lead_archetype": "", "archetype_reveal_seen": False}) is None
    assert first_archetype_payload(
        {"lead_archetype": "grinder", "archetype_reveal_seen": True}) is None
    assert first_archetype_payload(
        {"lead_archetype": "grinder", "archetype_reveal_seen": False,
         "archetype_evolution_pending": "scorer"}) is None
    assert first_archetype_payload(None) is None


# --- 6. the "also" row -------------------------------------------------------------------------


def test_also_is_the_highest_priority_weekly_item():
    q = _queue(
        bracket_update_modal=_eligible(),
        recruit_visit_modal={"eligible": True, "recruit": {"name": "Ellis Clemons"}},
        archetype_evolution_pending="scorer",
    )
    assert q["also"] == {
        "kind": "bracket_update",
        "title": "Tournament update",
        "line": "The tournament bracket moved this week.",
        "href": "/franchise-command-center.html?tab=tournament-view",
    }
    # weekly_card_items stays the full ordered list.
    assert [row["kind"] for row in q["weekly_card_items"]] == [
        "bracket_update", "recruit_visit", "archetype_evolution",
    ]
    assert all(row.get("href") for row in q["weekly_card_items"])


def test_also_is_null_without_a_weekly_item():
    assert _queue(region_bye_modal_eligible=True)["also"] is None


def test_the_archetype_row_has_no_link_on_desktop():
    online = collect_moments(archetype_evolution_pending="scorer")[0]
    assert online["href"] == "/coaching-archetypes.html"
    desktop = collect_moments(archetype_evolution_pending="scorer", archetype_href=None)[0]
    assert "href" not in desktop
    assert _queue(archetype_evolution_pending="scorer", archetype_href=None)["also"]["href"] is None


# --- 7. deferral -------------------------------------------------------------------------------


def test_deferral_to_the_next_visit():
    first = _queue(
        elimination={"eligible": True},
        region_bye_modal_eligible=True,
        conference_rs_region_modal=_eligible(),
    )
    assert [m["kind"] for m in first["moments_for_this_visit"]] == ["elimination", "region_bye"]
    # Nothing was dropped: the unshown item is still in `moments` and still eligible.
    assert "conference_rs_region" in [m["kind"] for m in first["moments"]]
    nxt = _queue(conference_rs_region_modal=_eligible())
    assert [m["kind"] for m in nxt["moments_for_this_visit"]] == ["conference_rs_region"]


# --- store-backed: route-level detectors -------------------------------------------------------


def _store_env(kind, tmp_path):
    if kind == "mongo":
        return _mongomock_env(tmp_path)
    return _mongomock_env(
        tmp_path,
        GOB_PERSISTENCE="sqlite",
        GOB_SQLITE_PATH=str(tmp_path / "moment-queue.sqlite"),
    )


@pytest.fixture(params=["mongo", "sqlite"])
def store(request, tmp_path, monkeypatch):
    built = create_store(_store_env(request.param, tmp_path))
    monkeypatch.setattr(fr, "db", built.db)
    monkeypatch.setattr(cd, "db", built.db)
    monkeypatch.setattr(cd, "franchise_players_data_collection", built.franchise_players_data_collection)
    monkeypatch.setattr(cd, "franchise_team_data_collection", built.franchise_team_data_collection)
    return built


def _seed(store, *, week=31, season=3, **extra):
    doc = {
        "_id": ObjectId(),
        "user_id": "coach-1",
        "current_season": season,
        "week": week,
        "eos_tournament_active": True,
        "user_team_object_id": ObjectId(USER),
        "conference_tournaments": {
            "3": {
                "seeds": {USER: 2, OPP: 1},
                "bracket": {"round1": [], "round2": [],
                            "final": [{"home_team": OPP, "away_team": USER,
                                       "winner": OPP, "score": {"home": 70, "away": 61},
                                       "game_id": "g-conf"}]},
            }
        },
        "region_tournaments": {
            "B": {"round1": [], "current_round": 2,
                  "final": [{"home_team": USER, "away_team": OPP, "winner": OPP,
                             "score": {"home": 58, "away": 66}, "game_id": "g-region"}]},
        },
    }
    doc.update(extra)
    store.franchises_collection.insert_one(doc)
    return store.franchises_collection.find_one({"_id": doc["_id"]})


def _response(**extra):
    response = {
        "team_name_map": {OPP: "Kingsport"},
        "region_qualified": True,
        "office_digest": {
            "what_moved": {
                "record": {"wins": 24, "losses": 9},
                "conference_standing": {"now": 2},
                "national_rank": {"now": 11},
            },
        },
    }
    response.update(extra)
    return response


def _build(store, doc, response, *, week=31, signals=None, is_local=False):
    return fr._build_moment_queue_for_command_center(
        response,
        doc,
        USER,
        {"conference": 3, "region": "B"},
        week,
        signals or {"archetype_evolution_pending": "", "lead_archetype": "",
                    "archetype_reveal_seen": True},
        is_local=is_local,
    )


def test_elimination_reports_the_region_loss_and_omits_absent_seeds(store):
    doc = _seed(store)
    response = _response()

    queue = _build(store, doc, response)

    elimination = response["elimination"]
    assert elimination["eligible"] is True
    assert elimination["tier"] == "region"
    assert elimination["round_name"] == "Region Tourney Championship"
    assert elimination["score"] == {"user": 58, "opponent": 66}
    assert elimination["opponent_team_id"] == OPP
    assert elimination["opponent_team_name"] == "Kingsport"
    assert elimination["record"] == {"wins": 24, "losses": 9}
    assert elimination["conference_place"] == 2
    assert elimination["national_rank"] == 11
    # region_tournaments never stores a seeds map, so neither seed is reported.
    assert "user_seed" not in elimination and "opponent_seed" not in elimination
    assert [m["kind"] for m in queue["moments_for_this_visit"]] == ["elimination"]


def test_a_conference_loss_reports_its_stored_seeds(store):
    doc = _seed(store, week=29, region_tournaments={})
    response = _response(region_qualified=False)

    _build(store, doc, response, week=29)

    elimination = response["elimination"]
    assert elimination["tier"] == "conference"
    assert elimination["round_name"] == "Conference Tourney Championship"
    assert (elimination["user_seed"], elimination["opponent_seed"]) == (2, 1)


def test_a_conference_loss_is_not_elimination_when_the_region_still_awaits(store):
    doc = _seed(store, week=29, region_tournaments={})
    response = _response(region_qualified=True)

    _build(store, doc, response, week=29)

    assert response["elimination"] is None


def test_elimination_is_once_per_season(store):
    doc = _seed(store, elimination_seen_season=3)
    response = _response()

    _build(store, doc, response)

    assert response["elimination"] is None
    # A new season re-arms it without anything clearing the stamp.
    later = _seed(store, season=4, elimination_seen_season=3)
    other = _response()
    _build(store, later, other)
    assert other["elimination"]["season"] == 4


def test_season_review_waits_for_the_season_to_be_over(store):
    doc = _seed(store, week=31)
    response = _response()
    _build(store, doc, response, week=31)
    assert response["season_review"] is None

    over = _seed(store, week=35, national_tournament={"champion": OPP})
    after = _response()
    queue = _build(store, over, after, week=35)
    assert after["season_review"]["eligible"] is True
    assert after["season_review"]["season"] == 3
    assert [m["kind"] for m in queue["moments_for_this_visit"]] == ["season_review"]

    seen = _seed(store, week=35, national_tournament={"champion": OPP},
                 season_review_seen_season=3)
    nxt = _response()
    _build(store, seen, nxt, week=35)
    assert nxt["season_review"] is None


def test_signed_class_is_blocked_until_the_hub_reveal_is_seen(store):
    signed = {"signed_players": [
        {"team_id": USER, "name": "Dee Prospect", "pos": "PG", "home_region": "B",
         "rt": 71, "potential_rt_ratcheted": 84},
        {"team_id": USER, "name": "Walk On", "walk_on": True, "pos": "C"},
    ]}
    doc = _seed(store, week=36, week_35_recruiting_ran=True, week_35_recruiting_results=signed)
    modal = fr._build_recruiting_results_modal_payload(doc, USER)
    assert modal and modal["eligible"] is True

    response = _response(recruiting_results_modal=modal)
    _build(store, doc, response, week=36)
    assert response["signed_class"] is None, "the hub reveal has not played yet"

    revealed = _seed(store, week=36, week_35_recruiting_ran=True,
                     week_35_recruiting_results=signed, week_35_reveal_seen_season=3)
    after = _response(recruiting_results_modal=fr._build_recruiting_results_modal_payload(revealed, USER))
    _build(store, revealed, after, week=36)

    payload = after["signed_class"]
    assert payload["count"] == 1
    assert payload["recruits"] == [
        {"name": "Dee Prospect", "position": "PG", "home_region": "B",
         "rt_now": 71, "rt_potential": 84},
    ]


def test_the_desktop_queue_drops_the_archetype_link(store):
    doc = _seed(store, week=10, eos_tournament_active=False,
                conference_tournaments={}, region_tournaments={})
    response = _response()

    queue = _build(
        store, doc, response, week=10,
        signals={"archetype_evolution_pending": "scorer", "lead_archetype": "scorer",
                 "archetype_reveal_seen": True},
        is_local=True,
    )

    row = next(m for m in queue["weekly_card_items"] if m["kind"] == "archetype_evolution")
    assert "href" not in row
    assert queue["also"]["kind"] == "archetype_evolution"


# --- guard -------------------------------------------------------------------------------------

SIM_MODULES = (
    "BackEnd/models/game_simulation.py",
    "BackEnd/utils/cpu_week_pool.py",
    "BackEnd/utils/sim_rng.py",
    "BackEnd/utils/stat_updater.py",
)


def test_sim_internals_never_mention_the_queue_or_exceptional_gains():
    for rel in SIM_MODULES:
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text()
        assert "moment_queue" not in text, rel
        assert "exceptional" not in text, rel
    src = inspect.getsource(fr._complete_week_finish_cpu_and_persist)
    assert "moment_queue" not in src
    assert "exceptional" not in src
