"""The week-1 Office (season preview) and the all-season Top Recruits list.

Pure builders first, then the digest, then the route helper's reads on both stores
(Mongo for hosted, SQLite for the offline build).
"""
import pytest
from bson import ObjectId

from BackEnd.api import franchise_routes
from BackEnd.persistence import create_store
from BackEnd.utils import local_coach as lc
from BackEnd.utils import season_preview as sp
from BackEnd.utils.hidden_attrs import HIDDEN_ATTR_KEYS
from BackEnd.utils.local_coach import LOCAL_USER_ID
from BackEnd.utils.office_digest import build_office_digest

from tests.test_career_data import _mongomock_env, _sqlite_env

USER = "t50"
FID = "64b000000000000000000001"


def league():
    """128 teams, rank i+1, eight per conference in rank-striped order (team i is in conference i % 16 + 1)."""
    return [
        {"team_id": f"t{i}", "team_name": f"Team {i}", "natl_rank": i + 1, "conference": (i % 16) + 1,
         "W": 0, "L": 0, "PF": 0, "PA": 0}
        for i in range(128)
    ]


def no_hidden_keys(value, path="$"):
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in HIDDEN_ATTR_KEYS or key in {"attributes", "score", "components", "weights", "bonus"}:
                found.append(f"{path}.{key}")
            found.extend(no_hidden_keys(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(no_hidden_keys(item, f"{path}[{index}]"))
    return found


def player(pid, first, last, rt, *, pos="PG", year="Junior", archetype="Scorer", height=74, weight=190):
    ratings = {"PG": 20, "SG": 20, "SF": 20, "PF": 20, "C": 20}
    ratings[pos] = rt
    return {
        "player_id": pid,
        "meta": {"first_name": first, "last_name": last, "year": year, "height": height, "weight": weight,
                 "archetype": archetype},
        "position_ratings": ratings,
        # A real FPD doc has these; the preview must never carry them out.
        "attributes": {"SC": 50, "CH": 77, "anchor_CH": 77},
        "development": {"ch_seed": 77},
    }


# --- rankings ------------------------------------------------------------------------------------


def test_rankings_come_from_the_preseason_national_rank():
    # t50 is rank 51, in conference 3 (teams 2, 18, 34, 50, 66, ...) and region B (conferences 3-4).
    block = sp.rankings_block(league(), USER, 3)
    assert block == {
        "conference": {"rank": 4, "of": 8},
        "region": {"rank": 7, "of": 16},
        "national": {"rank": 51, "of": 128},
    }
    assert sp.rankings_block(league(), "nobody", 3) is None
    assert sp.rankings_block([], USER, 3) is None


def test_preseason_national_rankings_are_the_conference_by_national_rank_best_first():
    table = sp.preseason_rankings(league(), USER, 3)
    assert table["conference"] == 3
    assert [row["national_rank"] for row in table["rows"]] == [3, 19, 35, 51, 67, 83, 99, 115]
    assert [row["team_id"] for row in table["rows"] if row["is_user"]] == [USER]
    assert len(table["rows"]) == 8


def test_region_letters_pair_the_conferences():
    assert [sp.region_letter(c) for c in (1, 2, 3, 4, 15, 16)] == ["A", "A", "B", "B", "H", "H"]
    assert sp.region_letter(None) is None


# --- last season -----------------------------------------------------------------------------------


def trophies(season, *, furthest="region_semis", wins=18, losses=8, titles=(), class_signed=()):
    rows = [{"kind": "season_record", "franchise_id": FID, "season": season,
             "detail": {"wins": wins, "losses": losses, "furthest_round": furthest,
                        "class_signed": list(class_signed)}}]
    rows += [{"kind": kind, "franchise_id": FID, "season": season} for kind in titles]
    # Another save's season and another season of this one: never read.
    rows.append({"kind": "season_record", "franchise_id": "other", "season": season, "detail": {"wins": 1, "losses": 30}})
    rows.append({"kind": "season_record", "franchise_id": FID, "season": season - 1, "detail": {"wins": 2, "losses": 29}})
    return rows


def test_last_season_line_is_the_record_and_how_it_ended():
    assert sp.last_season_line(trophies(1), FID, 1) == {
        "wins": 18, "losses": 8, "finish": "lost in the Region semifinal",
    }
    assert sp.last_season_line(trophies(1, furthest="missed"), FID, 1)["finish"] == "missed the bracket"
    assert sp.last_season_line(trophies(1, furthest="national_final"), FID, 1)["finish"] == "lost in the National final"
    champion = sp.last_season_line(trophies(1, furthest="national_final", titles=("national", "region")), FID, 1)
    assert champion["finish"] == "won the National championship"
    # No brackets stored: the record alone.
    assert sp.last_season_line(trophies(1, furthest=None), FID, 1) == {"wins": 18, "losses": 8, "finish": None}
    assert sp.last_season_line([], FID, 1) is None


# --- roster sections ---------------------------------------------------------------------------


ROSTER = [
    player("p1", "Al", "Ace", 88, pos="C", year="Senior", height=82, weight=240),
    player("p2", "Bo", "Best", 74, pos="PG"),
    player("p3", "Cy", "Core", 71, pos="SF"),
    player("p4", "Di", "Deep", 66, pos="SG", year="Sophomore"),
    player("p5", "Ed", "Edge", 61, pos="PF"),
    player("p6", "Fa", "Fresh", 58, pos="PG", year="Freshman"),
    player("p7", "Gi", "Green", 52, pos="SG", year="Freshman"),
    player("p8", "Hu", "Walk", 33, pos="SF", year="Freshman", archetype="Walk On"),
    player("p9", "Iz", "Older", 41, pos="C", year="Junior", archetype="Walk On"),
]


def test_key_players_are_the_top_five_by_rt_with_the_roster_columns():
    rows = sp.key_players(sp.roster_rows(ROSTER))
    assert [row["name"] for row in rows] == ["Al Ace", "Bo Best", "Cy Core", "Di Deep", "Ed Edge"]
    assert rows[0] == {"player_id": "p1", "name": "Al Ace", "rt": 88, "pos": "C", "year": "SR", "height": 82, "weight": 240}
    assert no_hidden_keys(rows) == []


def test_walk_ons_are_this_seasons_arrivals():
    rows = sp.roster_rows(ROSTER)
    # Season 1: every walk-on was created with the franchise.
    first = sp.walk_on_rows(rows, season=1, pending_walk_ons=[])
    assert [row["name"] for row in first] == ["Iz Older", "Hu Walk"]
    assert first[0] == {"player_id": "p9", "name": "Iz Older", "pos": "C", "year": "JR", "rt": 41}
    # Season 2 on: only the ones the rollover brought in. An older walk-on is not listed again.
    later = sp.walk_on_rows(rows, season=3, pending_walk_ons=[{"player_id": "p8", "name": "Hu Walk"}])
    assert [row["name"] for row in later] == ["Hu Walk"]
    assert sp.walk_on_rows(rows, season=3, pending_walk_ons=[]) == []


def test_newcomers_are_last_seasons_class_now_on_the_roster():
    rows = sp.roster_rows(ROSTER)
    snapshot = {"season": 1, "graduated_seniors": 3,
                "signed_class": [{"player_id": "p6", "name": "Fa Fresh"}, {"player_id": "p7", "name": "Gi Green"},
                                 {"player_id": "gone", "name": "Left Early"}]}
    block = sp.newcomers_block(rows, season=2, last_season=snapshot, class_signed=[], walk_on_ids=["p8"])
    assert block == {
        "players": [{"player_id": "p6", "name": "Fa Fresh", "pos": "PG", "rt": 58},
                    {"player_id": "p7", "name": "Gi Green", "pos": "SG", "rt": 52}],
        "returning": 6,       # nine on the roster, less two signees and one new walk-on
        "lost_seniors": 3,
        "newcomers": 2,
    }
    # Season 1 has no prior class.
    assert sp.newcomers_block(rows, season=1, last_season=None, class_signed=[], walk_on_ids=[]) is None
    # No signee on the roster: the section is left out.
    assert sp.newcomers_block(rows, season=2, last_season={"signed_class": []}, class_signed=[], walk_on_ids=[]) is None


def test_newcomers_fall_back_to_the_season_review_names_on_a_save_without_the_snapshot():
    rows = sp.roster_rows(ROSTER)
    block = sp.newcomers_block(rows, season=2, last_season=None,
                               class_signed=[{"name": "Fa Fresh", "position": "PG"}], walk_on_ids=[])
    assert [row["name"] for row in block["players"]] == ["Fa Fresh"]
    # The rollover that would have counted the seniors ran before the snapshot existed.
    assert block["lost_seniors"] is None
    assert (block["returning"], block["newcomers"]) == (8, 1)


def test_all_americans_show_who_and_how_good_never_the_formula():
    projection = {"all_american_teams": {
        "first_team": [
            {"position": pos, "player_id": f"a{i}", "name": f"Star {i}", "team_id": USER if i == 2 else f"t{i}",
             "team_name": f"Team {i}", "rating": 91.4 - i, "rank": 1, "score": 88.12,
             "components": {"rating": 40, "stats": 30, "team": 18}, "games": 0, "stats": {"ppg": 0}}
            for i, pos in enumerate(("PG", "SG", "SF", "PF", "C"))
        ],
        "second_team": [{"position": "PG", "name": "Second", "team_id": "t9", "rating": 80}],
    }}
    rows = sp.all_americans(projection, USER)
    assert [row["position"] for row in rows] == ["PG", "SG", "SF", "PF", "C"]
    assert rows[0] == {"position": "PG", "player_id": "a0", "name": "Star 0", "team_id": "t0",
                       "team_name": "Team 0", "rt": 91, "is_user": False}
    assert [row["name"] for row in rows if row["is_user"]] == ["Star 2"]
    assert no_hidden_keys(rows) == []
    assert sp.all_americans(None, USER) == []


# --- schedule ----------------------------------------------------------------------------------


def schedule():
    """26 weeks; the user plays t9 (rank 10) in week 1, t0 (rank 1) in week 7, t3 in 12, t1 in 20."""
    weeks = []
    opponents = {1: "t9", 7: "t0", 12: "t3", 20: "t1"}
    for week in range(1, 27):
        opp = opponents.get(week, f"t{60 + week}")
        pair = (opp, USER) if week % 2 else (USER, opp)
        weeks.append([("t100", "t101"), pair])
    return weeks


def test_circle_these_are_the_three_toughest_opponents_in_week_order():
    games = sp.circle_these(schedule(), USER, league())
    assert [(game["week"], game["opponent"], game["rank"]) for game in games] == [
        (7, "Team 0", 1), (12, "Team 3", 4), (20, "Team 1", 2),
    ]
    assert [game["site"] for game in games] == ["home", "away", "away"]
    assert sp.circle_these([], USER, league()) == []


def test_last_meeting_comes_from_the_rollover_snapshot():
    snapshot = {"meetings": {"t9": {"week": 14, "user_score": 71, "opp_score": 64, "site": "home"},
                             "t3": {"week": 3, "user_score": 50, "opp_score": 62, "site": "away"}}}
    assert sp.last_meeting(snapshot, "t9") == {"won": True, "user_score": 71, "opp_score": 64, "week": 14}
    assert sp.last_meeting(snapshot, "t3")["won"] is False
    assert sp.last_meeting(snapshot, "t77") is None
    assert sp.last_meeting(None, "t9") is None


def test_the_rollover_snapshot_keeps_what_the_reset_wipes():
    franchise = {"current_season": 1, "results": {
        "1": [{"away_id": "t9", "home_id": USER, "away_score": 60, "home_score": 70}],
        "2": [{"away_id": USER, "home_id": "t3", "away_score": 55, "home_score": 66},
              {"away_id": "t1", "home_id": "t2", "away_score": 1, "home_score": 2}],
        "9": [{"away_id": USER, "home_id": "t9", "away_score": 58, "home_score": 61}],
    }}
    snapshot = sp.last_season_snapshot(
        franchise, USER, graduated_seniors=3,
        signed_class=[{"player_id": "r1", "name": "New Guy"}, {"player_id": "w1", "name": "Walk", "walk_on": True}],
    )
    assert snapshot["season"] == 1
    assert (snapshot["wins"], snapshot["losses"]) == (1, 2)
    # Two games against t9: the later one is the last meeting.
    assert snapshot["meetings"]["t9"] == {"week": 9, "user_score": 58, "opp_score": 61, "site": "away"}
    assert set(snapshot["meetings"]) == {"t9", "t3"}
    assert snapshot["graduated_seniors"] == 3
    assert snapshot["signed_class"] == [{"player_id": "r1", "name": "New Guy"}]


# --- recruits ----------------------------------------------------------------------------------


def recruit(rid, name, rt, region, lean=None, pos="SF"):
    ratings = {"PG": 10, "SG": 10, "SF": 10, "PF": 10, "C": 10}
    ratings[pos] = rt
    doc = {"recruit_id": rid, "name": name, "position_ratings": ratings, "Home Region": region,
           "attributes": {"SC": 40, "CH": 66}}
    if lean:
        doc["Lean"] = {"1": lean, "2": "t3"}
    return doc


def test_top_recruits_are_the_regions_five_best_with_their_top_lean():
    docs = [recruit(f"r{i}", f"Recruit {i}", 40 + i, "B", lean=USER if i == 7 else "t9") for i in range(8)]
    docs += [recruit("far", "Other Region", 99, "C", lean="t9"), recruit("nolean", "No Lean", 60, "b")]
    block = sp.top_recruits(docs, region="B", user_team_id=USER, team_name_map={"t9": "Team 9", USER: "My Team"})
    assert block["region"] == "B"
    assert [row["name"] for row in block["rows"]] == ["No Lean", "Recruit 7", "Recruit 6", "Recruit 5", "Recruit 4"]
    assert block["rows"][0] == {"recruit_id": "nolean", "name": "No Lean", "position": "SF", "rt": 60,
                                "lean_team_id": None, "lean_team_name": None, "lean_is_user": False}
    assert block["rows"][1]["lean_team_name"] == "My Team" and block["rows"][1]["lean_is_user"] is True
    assert block["rows"][2]["lean_team_name"] == "Team 9" and block["rows"][2]["lean_is_user"] is False
    assert no_hidden_keys(block) == []
    assert sp.top_recruits(docs, region="", user_team_id=USER, team_name_map={}) is None
    assert sp.top_recruits([], region="B", user_team_id=USER, team_name_map={}) == {"region": "B", "rows": []}


# --- the digest --------------------------------------------------------------------------------


def digest_ctx(week, **extra):
    franchise = {"_id": FID, "current_season": 2, "week": week, "schedule": schedule(), "results": {},
                 "pending_walk_on_welcome": [{"player_id": "p8", "name": "Hu Walk"}],
                 "last_season": {"season": 1, "graduated_seniors": 3,
                                 "signed_class": [{"player_id": "p6", "name": "Fa Fresh"}],
                                 "meetings": {"t9": {"week": 14, "user_score": 71, "opp_score": 64, "site": "home"}}}}
    next_game = {"week": week, "matchup_label": "vs", "opponent_team_id": "t9", "opponent_team_name": "Team 9",
                 "opponent_team_conference": 10, "record": {"wins": 0, "losses": 0}, "rank": 10}
    block = sp.build_season_preview({
        "franchise_doc": franchise, "user_team_id": USER, "user_conference": 3, "rankings": league(),
        "roster_docs": ROSTER, "trophies": trophies(1), "next_game": next_game,
    }) if week <= 1 else None
    recruits = sp.top_recruits([recruit("r1", "Top Kid", 70, "B", lean="t9")], region="B", user_team_id=USER,
                               team_name_map={"t9": "Team 9"})
    ctx = {"franchise_doc": franchise, "user_team_id": USER, "week": week, "rankings": league(),
           "user_conference": 3, "next_game": next_game, "season_preview_block": block, "top_recruits": recruits,
           "recruiting_wire": {"counts": {}, "events": []}}
    ctx.update(extra)
    return ctx


def test_week_one_digest_carries_every_preview_section():
    digest = build_office_digest(digest_ctx(1))
    assert digest["state"] == "first_week"
    preview = digest["season_preview"]
    assert preview["ready"] is True and preview["season"] == 2
    assert preview["outlook"] == {
        "conference": 3,
        "picked": {"rank": 4, "of": 8},
        "last_season": {"wins": 18, "losses": 8, "finish": "lost in the Region semifinal"},
    }
    assert preview["rankings"]["national"] == {"rank": 51, "of": 128}
    assert len(preview["key_players"]) == 5
    assert preview["newcomers"]["players"] == [{"player_id": "p6", "name": "Fa Fresh", "pos": "PG", "rt": 58}]
    assert (preview["newcomers"]["returning"], preview["newcomers"]["lost_seniors"], preview["newcomers"]["newcomers"]) == (7, 3, 1)
    assert [row["name"] for row in preview["walk_ons"]] == ["Hu Walk"]
    # The opener: the opponent's preseason rank, and last season's result against them.
    assert preview["opener"]["rank"] == 10
    assert preview["opener"]["last_meeting"] == {"won": True, "user_score": 71, "opp_score": 64, "week": 14}
    assert [game["week"] for game in preview["circle_these"]] == [7, 12, 20]
    assert [row["national_rank"] for row in preview["preseason_rankings"]["rows"]][:2] == [3, 19]
    assert digest["recruiting_wire"]["status"] == "No preseason leans"
    assert digest["top_recruits"]["rows"][0]["name"] == "Top Kid"
    assert no_hidden_keys(digest["season_preview"]) == [] and no_hidden_keys(digest["top_recruits"]) == []


def test_season_one_week_one_shows_the_pick_only_and_no_newcomers():
    ctx = digest_ctx(1)
    ctx["franchise_doc"]["current_season"] = 1
    ctx["franchise_doc"].pop("last_season")
    ctx["season_preview_block"] = sp.build_season_preview({
        "franchise_doc": ctx["franchise_doc"], "user_team_id": USER, "user_conference": 3, "rankings": league(),
        "roster_docs": ROSTER, "trophies": [], "next_game": ctx["next_game"],
    })
    preview = build_office_digest(ctx)["season_preview"]
    assert preview["outlook"]["last_season"] is None
    assert preview["outlook"]["picked"] == {"rank": 4, "of": 8}
    assert preview["newcomers"] is None
    assert preview["opener"]["last_meeting"] is None
    # Season 1 walk-ons are the ones created with the franchise.
    assert [row["name"] for row in preview["walk_ons"]] == ["Iz Older", "Hu Walk"]


def test_a_stale_snapshot_from_another_season_is_ignored():
    ctx = digest_ctx(1)
    ctx["franchise_doc"]["last_season"]["season"] = 5
    block = sp.build_season_preview({
        "franchise_doc": ctx["franchise_doc"], "user_team_id": USER, "user_conference": 3, "rankings": league(),
        "roster_docs": ROSTER, "trophies": trophies(1), "next_game": ctx["next_game"],
    })
    assert block["opener"]["last_meeting"] is None
    assert block["newcomers"] is None


def test_week_two_is_the_normal_office_plus_top_recruits():
    digest = build_office_digest(digest_ctx(2))
    assert digest["state"] == "regular"
    assert digest["season_preview"] is None
    assert digest["recruiting_wire"]["status"] == "No recruiting movement"
    assert digest["top_recruits"]["rows"][0]["name"] == "Top Kid"


def test_top_recruits_step_aside_from_signing_day():
    assert build_office_digest(digest_ctx(34))["top_recruits"] is not None
    assert build_office_digest(digest_ctx(35))["top_recruits"] is None
    assert build_office_digest(digest_ctx(36))["top_recruits"] is None


def test_a_failed_preview_read_leaves_the_preview_not_ready():
    digest = build_office_digest(digest_ctx(1, season_preview_block=None))
    assert digest["season_preview"]["ready"] is False
    assert "key_players" not in digest["season_preview"]


# --- the route helper's reads, on both stores ---------------------------------------------------


@pytest.fixture(params=["mongo", "sqlite"])
def store(request, tmp_path, monkeypatch):
    env = _mongomock_env(tmp_path) if request.param == "mongo" else _sqlite_env(tmp_path)
    s = create_store(env)
    monkeypatch.setattr(lc, "coach_collection", lambda: s.db["save_meta"])
    monkeypatch.setattr(lc, "users_collection", s.users_collection)
    monkeypatch.setattr(franchise_routes, "franchise_players_data_collection", s.franchise_players_data_collection)
    monkeypatch.setattr(franchise_routes, "franchise_recruits_data_collection", s.franchise_recruits_data_collection)
    return s


@pytest.mark.parametrize("owner_kind", ["local", "online"])
def test_the_office_preview_reads_work_on_both_stores(store, owner_kind):
    fid = str(ObjectId())
    if owner_kind == "local":
        owner = LOCAL_USER_ID
        store.db["save_meta"].update_one(
            {"_id": lc.LOCAL_COACH_ID},
            {"$set": {"trophies": [dict(t, franchise_id=fid) for t in trophies(1) if t["franchise_id"] == FID]}},
            upsert=True,
        )
    else:
        oid = ObjectId()
        owner = str(oid)
        store.users_collection.insert_one(
            {"_id": oid, "username": "coach",
             "trophies": [dict(t, franchise_id=fid) for t in trophies(1) if t["franchise_id"] == FID]}
        )
    for doc in ROSTER:
        store.franchise_players_data_collection.insert_one(dict(doc, franchise_id=fid))
    # Someone else's player, never on the user's roster list.
    store.franchise_players_data_collection.insert_one(dict(player("zz", "Not", "Mine", 99), franchise_id=fid))
    for i in range(7):
        store.franchise_recruits_data_collection.insert_one(
            dict(recruit(f"r{i}", f"Recruit {i}", 40 + i, "B", lean="t9"), franchise_id=fid)
        )
    store.franchise_recruits_data_collection.insert_one(dict(recruit("far", "Elsewhere", 99, "F"), franchise_id=fid))
    franchise = {"_id": ObjectId(fid), "user_id": owner, "current_season": 2, "week": 1, "schedule": schedule(),
                 "pending_walk_on_welcome": [{"player_id": "p8"}]}
    response = {"user_conference": 3, "user_region": "B", "rankings": league(),
                "team_name_map": {"t9": "Team 9"}, "next_game_summary": None}
    ids = [doc["player_id"] for doc in ROSTER]

    preview, recruits = franchise_routes._office_preview_blocks(response, franchise, USER, 1, ids)
    assert [row["name"] for row in preview["key_players"]] == ["Al Ace", "Bo Best", "Cy Core", "Di Deep", "Ed Edge"]
    assert preview["outlook"]["last_season"] == {"wins": 18, "losses": 8, "finish": "lost in the Region semifinal"}
    assert [row["name"] for row in preview["walk_ons"]] == ["Hu Walk"]
    assert [row["name"] for row in recruits["rows"]] == [f"Recruit {i}" for i in (6, 5, 4, 3, 2)]
    assert recruits["rows"][0]["lean_team_name"] == "Team 9"
    assert no_hidden_keys(preview) == [] and no_hidden_keys(recruits) == []

    # Week 2: no preview, Top Recruits still there. Week 35: neither.
    preview2, recruits2 = franchise_routes._office_preview_blocks(response, dict(franchise, week=2), USER, 2, ids)
    assert preview2 is None and len(recruits2["rows"]) == 5
    assert franchise_routes._office_preview_blocks(response, dict(franchise, week=35), USER, 35, ids) == (None, None)


# --- a real franchise through the real route ----------------------------------------------------


@pytest.mark.order("last")
def test_a_new_franchise_opens_on_the_season_preview_and_week_two_does_not():
    from fastapi.testclient import TestClient

    from BackEnd.api.api import app
    from BackEnd.db import db
    from tests.test_hidden_attrs import _seed_league, hidden_traces

    client = TestClient(app)
    team_name, team_id = _seed_league()
    created = client.post("/franchise/select-team", json={"team_name": team_name})
    assert created.status_code == 200, created.text
    fid = created.json()["franchise_id"]

    res = client.get(f"/franchise/command-center/data?franchise_id={fid}&team_id={team_id}")
    assert res.status_code == 200, res.text
    digest = res.json()["office_digest"]
    assert digest["state"] == "first_week"
    preview = digest["season_preview"]
    assert preview["ready"] is True and preview["season"] == 1
    # 128 teams, eight to a conference, sixteen to a region.
    assert preview["rankings"]["national"]["of"] == 128
    assert preview["rankings"]["conference"]["of"] == 8
    assert preview["rankings"]["region"]["of"] == 16
    assert preview["outlook"]["picked"] == preview["rankings"]["conference"]
    assert preview["outlook"]["last_season"] is None and preview["newcomers"] is None
    assert len(preview["preseason_rankings"]["rows"]) == 8
    assert [row["is_user"] for row in preview["preseason_rankings"]["rows"]].count(True) == 1
    ranks = [row["national_rank"] for row in preview["preseason_rankings"]["rows"]]
    assert ranks == sorted(ranks)
    # The roster: the two seeded players and the three walk-ons a new franchise creates.
    names = {row["name"] for row in preview["key_players"]}
    assert {"Alice One", "Bob Two"} <= names and len(preview["key_players"]) == 5
    assert len(preview["walk_ons"]) == 3
    assert len(preview["circle_these"]) == 3
    assert [game["week"] for game in preview["circle_these"]] == sorted(game["week"] for game in preview["circle_these"])
    assert digest["recruiting_wire"]["status"] == "No preseason leans"
    assert digest["top_recruits"] is not None and len(digest["top_recruits"]["rows"]) <= 5
    assert hidden_traces(digest) == []

    # Week 2: the normal Office. Top Recruits is still there.
    db.franchises.update_one({"_id": ObjectId(fid)}, {"$set": {"week": 2}, "$inc": {"browse_rev": 1}})
    later = client.get(f"/franchise/command-center/data?franchise_id={fid}&team_id={team_id}").json()["office_digest"]
    assert later["state"] != "first_week"
    assert later["season_preview"] is None
    assert later["top_recruits"] is not None
