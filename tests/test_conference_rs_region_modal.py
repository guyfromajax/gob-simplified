from bson import ObjectId

from BackEnd.api import franchise_routes as fr


USER_ID = "aaaaaaaaaaaaaaaaaaaaaaaa"
OPPONENT_ID = "bbbbbbbbbbbbbbbbbbbbbbbb"


def _doc(lost_round="round1", *, seed=1, winner=OPPONENT_ID, seen=None):
    bracket = {"round1": [], "round2": [], "final": []}
    bracket[lost_round] = [
        {"away_team": USER_ID, "home_team": OPPONENT_ID, "winner": winner}
    ]
    doc = {
        "current_season": 4,
        "eos_tournament_active": True,
        "conference_tournaments": {
            "3": {"seeds": {USER_ID: seed, OPPONENT_ID: 2}, "bracket": bracket}
        },
    }
    if seen is not None:
        doc[fr.CONFERENCE_RS_REGION_MODAL_SEEN_SEASON_FIELD] = seen
    return doc


def test_payload_identifies_first_round_semifinal_and_final_losses():
    assert fr._build_conference_rs_region_modal_payload(
        _doc("round1"), USER_ID, {"conference": 3}
    )["lost_round"] == "round1"
    assert fr._build_conference_rs_region_modal_payload(
        _doc("round2"), USER_ID, {"conference": 3}
    )["lost_round"] == "round2"
    assert fr._build_conference_rs_region_modal_payload(
        _doc("final"), USER_ID, {"conference": 3}
    )["lost_round"] == "final"


def test_payload_requires_number_one_seed_and_completed_loss():
    assert fr._build_conference_rs_region_modal_payload(
        _doc(seed=2), USER_ID, {"conference": 3}
    ) is None
    assert fr._build_conference_rs_region_modal_payload(
        _doc(winner=None), USER_ID, {"conference": 3}
    ) is None
    assert fr._build_conference_rs_region_modal_payload(
        _doc(winner=USER_ID), USER_ID, {"conference": 3}
    ) is None


def test_payload_is_once_per_season():
    assert fr._build_conference_rs_region_modal_payload(
        _doc(seen=4), USER_ID, {"conference": 3}
    ) is None
    assert fr._build_conference_rs_region_modal_payload(
        _doc(seen=3), USER_ID, {"conference": 3}
    )["eligible"] is True


def test_mark_seen_persists_current_season(monkeypatch):
    franchise_id = ObjectId()
    doc = {"_id": franchise_id, "current_season": 4}
    monkeypatch.setattr(fr, "verify_franchise_owned_by_user", lambda *_: doc)
    captured = []
    monkeypatch.setattr(fr.db.franchises, "update_one", lambda query, update: captured.append((query, update)))
    response = fr.mark_conference_rs_region_modal_seen(
        fr.ConferenceRsRegionModalSeenRequest(franchise_id=str(franchise_id)),
        user={"user_id": "owner"},
    )
    assert response == {"seen": True, "season": 4}
    assert captured == [
        ({"_id": franchise_id}, {"$set": {fr.CONFERENCE_RS_REGION_MODAL_SEEN_SEASON_FIELD: 4}})
    ]
