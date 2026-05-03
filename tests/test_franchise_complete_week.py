import logging
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from BackEnd.api.api import app
from BackEnd.api import franchise_routes
from BackEnd.db import db
from bson import ObjectId

client = TestClient(app)


def _fake_franchise_cpu_full_sim(_home_name: str, _away_name: str) -> tuple[int, int, dict]:
    """Avoid full ``run_simulation`` (needs 5+ player rosters) in API tests."""
    return (54, 58, {})


def _week_result_for_pair(week_results: list, id_a: ObjectId, id_b: ObjectId) -> dict:
    want = {str(id_a), str(id_b)}
    for r in week_results:
        if {str(r["away_id"]), str(r["home_id"])} == want:
            return r
    raise AssertionError(f"No result row for matchup {want} in {week_results}")


def setup_franchise():
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})
    ids = [ObjectId() for _ in range(4)]
    teams = [
        {"_id": ids[0], "name": "A", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
        {"_id": ids[1], "name": "B", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
        {"_id": ids[2], "name": "C", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
        {"_id": ids[3], "name": "D", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
    ]
    db.teams.insert_many(teams)
    schedule = [[(ids[0], ids[1]), (ids[2], ids[3])]]
    fid = db.franchises.insert_one(
        {
            "schedule": schedule,
            "week": 1,
            "user_team_id": "A",
            "user_team_object_id": str(ids[0]),
        }
    ).inserted_id
    return str(fid), ids


def test_complete_week_saves_and_simulates():
    franchise_id, ids = setup_franchise()
    payload = {
        "franchise_id": franchise_id,
        "week": 1,
        "result": {"team1_id": "A", "team2_id": "B", "team1_score": 70, "team2_score": 60},
    }
    with patch.object(
        franchise_routes,
        "_run_franchise_cpu_full_simulation_core",
        side_effect=_fake_franchise_cpu_full_sim,
    ):
        res = client.post("/franchise/complete-week", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert len(data["results"]) == 2

    # Franchise mode does not mutate universal ``teams`` W/L/PF (see ``_save_game_result``).
    franchise_doc = db.franchises.find_one({"_id": ObjectId(franchise_id)})
    week_results = franchise_doc.get("results", {}).get("1") or []
    assert len(week_results) == 2
    ab = _week_result_for_pair(week_results, ids[0], ids[1])
    assert int(ab["away_score"]) == 70 and int(ab["home_score"]) == 60
    cd = _week_result_for_pair(week_results, ids[2], ids[3])
    assert int(cd["away_score"]) == 54 and int(cd["home_score"]) == 58

    # Idempotent second call
    with patch.object(
        franchise_routes,
        "_run_franchise_cpu_full_simulation_core",
        side_effect=_fake_franchise_cpu_full_sim,
    ):
        res2 = client.post("/franchise/complete-week", json=payload)
    assert res2.status_code == 200
    games = list(
        db.games.find(
            {
                "week": 1,
                "$or": [
                    {"team1_id": ids[0], "team2_id": ids[1]},
                    {"team1_id": ids[1], "team2_id": ids[0]},
                ],
            }
        )
    )
    assert len(games) == 1

    franchise_doc = db.franchises.find_one({"_id": ObjectId(franchise_id)})
    assert franchise_doc["week"] == 2
    assert "1" in franchise_doc.get("results", {})
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})


def test_complete_week_accepts_canonical_team_ids_single_word():
    """Regression: Play Quarter sends LANCASTER / SOUTH_LANCASTER; backend must resolve via name."""
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})
    id_l = ObjectId()
    id_sl = ObjectId()
    db.teams.insert_many([
        {"_id": id_l, "name": "Lancaster", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
        {"_id": id_sl, "name": "South Lancaster", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
    ])
    fid = db.franchises.insert_one({
        "schedule": [[(id_l, id_sl)]],
        "week": 1,
    }).inserted_id
    payload = {
        "franchise_id": str(fid),
        "week": 1,
        "result": {
            "team1_id": "LANCASTER",
            "team2_id": "SOUTH_LANCASTER",
            "team1_score": 76,
            "team2_score": 59,
        },
    }
    res = client.post("/franchise/complete-week", json=payload)
    assert res.status_code == 200, res.json()
    data = res.json()
    assert len(data["results"]) >= 1
    franchise_doc = db.franchises.find_one({"_id": fid})
    week_results = franchise_doc.get("results", {}).get("1") or []
    row = _week_result_for_pair(week_results, id_l, id_sl)
    assert int(row["away_score"]) == 76 and int(row["home_score"]) == 59
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})


def test_complete_week_accepts_canonical_team_ids_multi_word():
    """Regression: canonical keys with underscores (FOUR_CORNERS, LITTLE_YORK) resolve to team name."""
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})
    id_fc = ObjectId()
    id_ly = ObjectId()
    db.teams.insert_many([
        {"_id": id_fc, "name": "Four Corners", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
        {"_id": id_ly, "name": "Little York", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
    ])
    fid = db.franchises.insert_one({
        "schedule": [[(id_fc, id_ly)]],
        "week": 1,
    }).inserted_id
    payload = {
        "franchise_id": str(fid),
        "week": 1,
        "result": {
            "team1_id": "FOUR_CORNERS",
            "team2_id": "LITTLE_YORK",
            "team1_score": 80,
            "team2_score": 72,
        },
    }
    res = client.post("/franchise/complete-week", json=payload)
    assert res.status_code == 200, res.json()
    data = res.json()
    assert len(data["results"]) >= 1
    franchise_doc = db.franchises.find_one({"_id": fid})
    week_results = franchise_doc.get("results", {}).get("1") or []
    row = _week_result_for_pair(week_results, id_fc, id_ly)
    assert int(row["away_score"]) == 80 and int(row["home_score"]) == 72
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})


def test_normalize_team_id_canonical_single_word_no_mongo():
    """Unit test: LANCASTER (no underscore) resolves via canonical->name without needing MongoDB."""
    id_lancaster = ObjectId()
    id_south_lancaster = ObjectId()
    call_count = [0]

    def fake_find_one(query):
        call_count[0] += 1
        if not isinstance(query, dict):
            return None
        # First call: by _id/name/code -> miss for "LANCASTER" / "SOUTH_LANCASTER"
        if "$or" in query:
            return None
        name_q = query.get("name")
        if isinstance(name_q, dict) and "$in" in name_q:
            for name in name_q["$in"]:
                if name == "Lancaster":
                    return {"_id": id_lancaster}
                if name in ("South Lancaster", "South-Lancaster"):
                    return {"_id": id_south_lancaster}
            return None
        if name_q == "Lancaster":
            return {"_id": id_lancaster}
        if name_q == "South Lancaster":
            return {"_id": id_south_lancaster}
        return None

    mock_teams = MagicMock()
    mock_teams.find_one.side_effect = fake_find_one
    mock_db = MagicMock()
    mock_db.teams = mock_teams
    with patch.object(franchise_routes, "db", mock_db):
        out1 = franchise_routes._normalize_team_id("LANCASTER")
        out2 = franchise_routes._normalize_team_id("SOUTH_LANCASTER")
    assert out1 == id_lancaster
    assert out2 == id_south_lancaster


def test_normalize_team_id_canonical_multi_word_no_mongo():
    """Unit test: FOUR_CORNERS, LITTLE_YORK resolve via canonical->name without needing MongoDB."""
    id_fc = ObjectId()
    id_ly = ObjectId()

    def fake_find_one(query):
        if not isinstance(query, dict):
            return None
        if "$or" in query:
            return None
        name_q = query.get("name")
        if isinstance(name_q, dict) and "$in" in name_q:
            for name in name_q["$in"]:
                if name in ("Four Corners", "Four-Corners"):
                    return {"_id": id_fc}
                if name in ("Little York", "Little-York"):
                    return {"_id": id_ly}
            return None
        if name_q == "Four Corners":
            return {"_id": id_fc}
        if name_q == "Little York":
            return {"_id": id_ly}
        return None

    mock_teams = MagicMock()
    mock_teams.find_one.side_effect = fake_find_one
    mock_db = MagicMock()
    mock_db.teams = mock_teams
    with patch.object(franchise_routes, "db", mock_db):
        out1 = franchise_routes._normalize_team_id("FOUR_CORNERS")
        out2 = franchise_routes._normalize_team_id("LITTLE_YORK")
    assert out1 == id_fc
    assert out2 == id_ly


def test_merge_phase_a_user_row_replaces_same_matchup():
    """User row merge overwrites the same away/home pairing (order-insensitive keys)."""
    existing = [
        {"away_id": "a", "home_id": "b", "away_score": 1, "home_score": 2},
        {"away_id": "c", "home_id": "d", "away_score": 3, "home_score": 4},
    ]
    user_row = {"away_id": "b", "home_id": "a", "away_score": 70, "home_score": 60}
    merged = franchise_routes._merge_phase_a_user_row_into_week_results(existing, user_row)
    assert len(merged) == 2
    ab = next(x for x in merged if set(map(str, [x["away_id"], x["home_id"]])) == {"a", "b"})
    assert ab["away_score"] == 70
    assert ab["home_score"] == 60


def test_find_user_matchup_eos_phase_b_fallback_when_week_games_omits_user():
    """Phase A persists bracket winner; get_eos_week_games skips that row — phase B uses saved results."""
    uid = ObjectId()
    peer = ObjectId()
    saved = [
        {
            "away_id": str(uid),
            "home_id": str(peer),
            "away_score": 10,
            "home_score": 8,
        }
    ]
    # No row contains uid (user R1 already has winner in DB / excluded from incomplete list)
    week_games = [(peer, ObjectId())]
    t1, t2 = franchise_routes._find_user_franchise_week_matchup_normalized_ids(
        week_games,
        str(uid),
        week=27,
        saved_week_results=saved,
    )
    assert {str(t1), str(t2)} == {str(uid), str(peer)}


def test_try_finalize_franchise_week_logs_waiting_when_schedule_incomplete(caplog):
    """Observability: incomplete slate logs outcome=waiting before refusing closure."""
    t1, t2, t3, t4 = ObjectId(), ObjectId(), ObjectId(), ObjectId()
    week_games = [(t1, t2), (t3, t4)]
    results = [
        {
            "away_id": str(t1),
            "home_id": str(t2),
            "away_score": 70,
            "home_score": 60,
        }
    ]
    with caplog.at_level(logging.INFO, logger="BackEnd.api.franchise_routes"):
        out = franchise_routes._try_finalize_franchise_week_if_complete(
            franchise_doc={},
            franchise_id=ObjectId(),
            franchise_id_str="deadbeefdeadbeefdeadbeef",
            week=1,
            week_games=week_games,
            results=results,
            user_team_id_str=None,
        )
    assert out is None
    assert any(
        "[TRY-FINALIZE-WEEK]" in r.message and "outcome=waiting" in r.message
        for r in caplog.records
    )


def test_try_finalize_franchise_week_ran_closure_when_schedule_complete(caplog):
    """Week closure runs and logs outcome=ran_closure when results cover the schedule."""
    t1, t2, t3, t4 = ObjectId(), ObjectId(), ObjectId(), ObjectId()
    week_games = [(t1, t2), (t3, t4)]
    results = [
        {"away_id": str(t1), "home_id": str(t2), "away_score": 70, "home_score": 60},
        {"away_id": str(t3), "home_id": str(t4), "away_score": 55, "home_score": 58},
    ]
    fake_payload = {"week": 1, "results": []}
    with patch.object(
        franchise_routes,
        "_finalize_franchise_week_after_cpu_games",
        return_value=fake_payload,
    ):
        with caplog.at_level(logging.INFO, logger="BackEnd.api.franchise_routes"):
            out = franchise_routes._try_finalize_franchise_week_if_complete(
                franchise_doc={},
                franchise_id=ObjectId(),
                franchise_id_str="deadbeefdeadbeefdeadbeef",
                week=1,
                week_games=week_games,
                results=results,
                user_team_id_str=None,
            )
    assert out == fake_payload
    assert any(
        "[TRY-FINALIZE-WEEK]" in r.message and "outcome=ran_closure" in r.message
        for r in caplog.records
    )


def test_start_cpu_sims_partial_persists_without_advancing_week():
    """POST start-cpu-sims runs non-user CPUs only; franchise week does not advance."""
    franchise_id, ids = setup_franchise()
    with patch.object(
        franchise_routes,
        "_run_franchise_cpu_full_simulation_core",
        side_effect=_fake_franchise_cpu_full_sim,
    ):
        res = client.post(
            "/franchise/complete-week/start-cpu-sims",
            json={"franchise_id": franchise_id, "week": 1},
        )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data.get("phase") == "start_cpu_sims"
    assert data.get("results_count") == 1
    doc = db.franchises.find_one({"_id": ObjectId(franchise_id)})
    assert doc.get("week") == 1
    rows = doc.get("results", {}).get("1") or []
    assert len(rows) == 1
    cd = _week_result_for_pair(rows, ids[2], ids[3])
    assert int(cd["away_score"]) == 54 and int(cd["home_score"]) == 58
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})


def test_start_cpu_sims_409_when_phase_a_already_done():
    """After phase A, start-cpu-sims is rejected; client should use phase-b."""
    franchise_id, ids = setup_franchise()
    db.franchises.update_one(
        {"_id": ObjectId(franchise_id)},
        {"$set": {"post_game_status.phase_a_user_week": 1}},
    )
    res = client.post(
        "/franchise/complete-week/start-cpu-sims",
        json={"franchise_id": franchise_id, "week": 1},
    )
    assert res.status_code == 409
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})


def test_start_cpu_then_phase_a_phase_b_advances_week():
    """CPU sims at start-cpu-sims; phase A adds user row; phase B finalizes and advances week."""
    franchise_id, ids = setup_franchise()
    with patch.object(
        franchise_routes,
        "_run_franchise_cpu_full_simulation_core",
        side_effect=_fake_franchise_cpu_full_sim,
    ):
        rs = client.post(
            "/franchise/complete-week/start-cpu-sims",
            json={"franchise_id": franchise_id, "week": 1},
        )
    assert rs.status_code == 200, rs.text

    payload = {
        "franchise_id": franchise_id,
        "week": 1,
        "result": {"team1_id": "A", "team2_id": "B", "team1_score": 70, "team2_score": 60},
    }
    with patch.object(
        franchise_routes,
        "_run_franchise_cpu_full_simulation_core",
        side_effect=_fake_franchise_cpu_full_sim,
    ):
        ra = client.post("/franchise/complete-week/phase-a", json=payload)
    assert ra.status_code == 200, ra.text

    with patch.object(
        franchise_routes,
        "_run_franchise_cpu_full_simulation_core",
        side_effect=_fake_franchise_cpu_full_sim,
    ):
        rb = client.post(
            "/franchise/complete-week/phase-b",
            json={"franchise_id": franchise_id, "week": 1},
        )
    assert rb.status_code == 200, rb.text
    doc = db.franchises.find_one({"_id": ObjectId(franchise_id)})
    assert doc["week"] == 2
    assert len(doc.get("results", {}).get("1") or []) == 2
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})


def test_phase_a_then_phase_b_then_second_phase_b_is_idempotent():
    """Split complete-week: phase A persists user row; phase B runs CPU + closure; repeat phase B is no-op."""
    franchise_id, ids = setup_franchise()
    payload = {
        "franchise_id": franchise_id,
        "week": 1,
        "result": {"team1_id": "A", "team2_id": "B", "team1_score": 70, "team2_score": 60},
    }
    with patch.object(
        franchise_routes,
        "_run_franchise_cpu_full_simulation_core",
        side_effect=_fake_franchise_cpu_full_sim,
    ):
        ra = client.post("/franchise/complete-week/phase-a", json=payload)
    assert ra.status_code == 200, ra.text
    doc_mid = db.franchises.find_one({"_id": ObjectId(franchise_id)})
    assert doc_mid.get("week") == 1
    assert doc_mid.get("post_game_status", {}).get("phase_a_user_week") == 1

    with patch.object(
        franchise_routes,
        "_run_franchise_cpu_full_simulation_core",
        side_effect=_fake_franchise_cpu_full_sim,
    ):
        rb = client.post(
            "/franchise/complete-week/phase-b",
            json={"franchise_id": franchise_id, "week": 1},
        )
    assert rb.status_code == 200, rb.text
    assert rb.json().get("idempotent") is False
    doc_done = db.franchises.find_one({"_id": ObjectId(franchise_id)})
    assert doc_done["week"] == 2
    assert len(doc_done.get("results", {}).get("1") or []) == 2

    rb2 = client.post(
        "/franchise/complete-week/phase-b",
        json={"franchise_id": franchise_id, "week": 1},
    )
    assert rb2.status_code == 200
    assert rb2.json().get("idempotent") is True
    assert rb2.json().get("results") == []

    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})


def test_eos_advance_conference_when_four_r1_winners_and_round2_empty():
    """Stuck R1 (repair) + empty R2: advance_conference_bracket must build semis."""
    from BackEnd.api import franchise_routes

    ids = [str(ObjectId()) for _ in range(8)]
    r1 = [
        {"home_team": ids[0], "away_team": ids[1], "winner": ids[0], "game_id": "g0", "score": {}},
        {"home_team": ids[2], "away_team": ids[3], "winner": ids[2], "game_id": "g1", "score": {}},
        {"home_team": ids[4], "away_team": ids[5], "winner": ids[4], "game_id": "g2", "score": {}},
        {"home_team": ids[6], "away_team": ids[7], "winner": ids[6], "game_id": "g3", "score": {}},
    ]
    doc = {
        "conference_tournaments": {
            "1": {
                "current_round": 1,
                "bracket": {"round1": r1, "round2": [], "final": []},
            }
        }
    }
    n = franchise_routes._eos_advance_all_conference_brackets_until_idle(doc)
    assert n == 1
    br = doc["conference_tournaments"]["1"]["bracket"]
    assert len(br.get("round2") or []) == 2
    assert int(doc["conference_tournaments"]["1"]["current_round"]) == 2


def test_phase_b_http_idempotent_when_franchise_week_already_advanced(caplog):
    """Second phase-B style call after week advance: HTTP 200, idempotent, no CPU work."""
    db.franchises.delete_many({})
    fid = db.franchises.insert_one({"week": 2, "schedule": [[]]}).inserted_id
    with caplog.at_level(logging.INFO, logger="BackEnd.api.franchise_routes"):
        res = client.post(
            "/franchise/complete-week/phase-b",
            json={"franchise_id": str(fid), "week": 1},
        )
    assert res.status_code == 200
    data = res.json()
    assert data.get("idempotent") is True
    assert data.get("phase") == "b"
    assert data.get("results") == []
    assert any(
        "[COMPLETE-WEEK-PHASE-B]" in r.message and "already_finalized" in r.message
        for r in caplog.records
    )
    db.franchises.delete_many({})

