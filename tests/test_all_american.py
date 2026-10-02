"""All-American selection: weekly projection and post-tournament final (mongomock + sqlite)."""

from __future__ import annotations

import copy

import pytest
from bson import ObjectId

import BackEnd.utils.all_american as aa
import BackEnd.utils.franchise_team_display as ftdisp
import BackEnd.utils.trophy_log as tl
from BackEnd.persistence import create_store
from tests.test_persistence_adapter import _mongomock_env, _sqlite_env

POSITIONS = ("PG", "SG", "SF", "PF", "C")
TEAM_NAMES = ("Alder", "Birch", "Cedar", "Dogwood", "Elm", "Fir")


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "week, attributes, stats, team",
    [
        (1, 100.0, 0.0, 0.0),
        (5, 68.9, 31.1, 0.0),      # 4/9 of the way from week 1 to week 10
        (10, 30.0, 70.0, 0.0),
        (18, 15.0, 70.0, 15.0),    # half way from week 10 to week 26
        (26, 0.0, 70.0, 30.0),
    ],
)
def test_weights_by_week(week, attributes, stats, team):
    assert aa.weights_percent(week) == {"attributes": attributes, "stats": stats, "team": team}
    assert sum(aa.weights_for_week(week).values()) == pytest.approx(1.0)


def test_weights_clamp_outside_the_season():
    assert aa.weights_percent(0) == aa.weights_percent(1)
    assert aa.weights_percent(31) == aa.weights_percent(26)


def test_stat_weights_are_the_brief():
    assert aa.STAT_WEIGHTS == {
        "PTS": 0.35, "REB": 0.15, "AST": 0.15, "STL": 0.10, "BLK": 0.10, "DEF%": 0.15,
    }
    assert sum(aa.STAT_WEIGHTS.values()) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Stats score and the games rule
# ---------------------------------------------------------------------------

def _player(pid, *, team="t1", position="PG", rating=70, **totals):
    base = {"GP": 10, "PTS": 0, "REB": 0, "AST": 0, "STL": 0, "BLK": 0, "DEF_A": 0, "DEF_S": 0}
    base.update(totals)
    return {
        "player_id": pid, "name": pid, "team_id": team, "team_name": team, "year": "Senior",
        "position": position, "rating": rating, "totals": base,
    }


def _score(players, *, week=26, games=10, ranks=None, team_count=128):
    return aa.score_players(
        players,
        weights=aa.weights_for_week(week),
        team_games={"t1": games, "t2": games, "t3": games},
        rank_by_team=ranks or {},
        team_count=team_count,
    )


def test_seventy_percent_of_team_games_is_needed_for_a_stats_score():
    # Team has played 10. Seven games (70%) qualifies; six does not.
    seven = _player("seven", GP=7, PTS=7 * 30)
    six = _player("six", GP=6, PTS=6 * 40)       # the better scorer, but short of games
    filler = _player("filler", GP=10, PTS=10 * 5)
    scored = {p["player_id"]: p for p in _score([seven, six, filler])}
    assert scored["six"]["components"]["stats"] == 0.0
    assert scored["six"]["line"] is None
    assert scored["seven"]["components"]["stats"] > 0.0
    # The position leader among those who qualify takes the full scoring share.
    assert scored["seven"]["components"]["stats"] == pytest.approx(35.0)
    pick = aa.select_teams(aa.rank_by_position(scored.values()))
    assert pick["first_team"][0]["player_id"] == "seven"
    assert pick["first_team"][0]["stats"]["PTS"] == 30.0


def test_stats_are_distance_above_the_position_average():
    # Averages: 10 points. 20 is the leader (1.0), 10 is the average (0), 0 is below (0).
    players = [_player("hi", PTS=200), _player("mid", PTS=100), _player("lo", PTS=0)]
    scored = {p["player_id"]: p["components"]["stats"] for p in _score(players)}
    assert scored == {"hi": pytest.approx(35.0), "mid": 0.0, "lo": 0.0}


def test_defensive_rate_needs_five_attempts_per_team_game():
    # 10 team games: 50 attempts is the floor (the old 130 over a 26-game season).
    enough = _player("enough", DEF_A=50, DEF_S=40)
    short = _player("short", DEF_A=49, DEF_S=49)
    other = _player("other", DEF_A=60, DEF_S=30)
    scored = {p["player_id"]: p for p in _score([enough, short, other])}
    assert scored["short"]["line"]["DEF%"] is None
    assert scored["enough"]["line"]["DEF%"] == pytest.approx(0.8)
    assert scored["enough"]["components"]["stats"] == pytest.approx(15.0)
    assert scored["short"]["components"]["stats"] == 0.0


def test_team_score_is_national_rank():
    assert aa.team_score(1, 128) == 100.0
    assert aa.team_score(128, 128) == 0.0
    assert aa.team_score(None, 128) == 0.0
    scored = _score([_player("a", team="t1"), _player("b", team="t2")], ranks={"t1": 1, "t2": 128})
    by = {p["player_id"]: p["components"]["team"] for p in scored}
    assert by == {"a": 100.0, "b": 0.0}


def test_each_position_is_scored_against_its_own_position():
    guards = [_player("g1", PTS=200), _player("g2", PTS=100)]
    centers = [_player("c1", position="C", PTS=100), _player("c2", position="C", PTS=50)]
    scored = {p["player_id"]: p["components"]["stats"] for p in _score(guards + centers)}
    # Both leaders get the full share, though the center scores half as much.
    assert scored["g1"] == pytest.approx(35.0)
    assert scored["c1"] == pytest.approx(35.0)


# ---------------------------------------------------------------------------
# Bonus points
# ---------------------------------------------------------------------------

def test_team_bonus_is_cumulative():
    champ, runner, semi, conf_only, nobody = "champ", "runner", "semi", "conf", "nobody"
    doc = {
        "conference_tournaments": {
            "1": {"champion": champ}, "2": {"champion": conf_only}, "3": {"champion": None},
        },
        "region_tournaments": {
            "A": {"final": [{"home_team": champ, "away_team": nobody, "winner": champ}]},
            "B": {"final": [{"home_team": runner, "away_team": "x", "winner": runner}]},
            "C": {"final": [{"home_team": semi, "away_team": "y", "winner": semi}]},
            "D": {"final": [{"home_team": "R1_0", "away_team": "R1_1", "winner": None}]},
        },
        "national_tournament": {
            "bracket": {
                "round1": [],
                # round2 is the national semifinal.
                "round2": [
                    {"home_team": champ, "away_team": semi},
                    {"home_team": runner, "away_team": "other"},
                ],
                "final": [{"home_team": champ, "away_team": runner, "winner": champ}],
            },
            "champion": champ,
        },
    }
    points = aa.team_bonus_points(doc)
    assert points[champ] == 1 + 2 + 2 + 5      # conference + region + semifinal + title
    assert points[runner] == 2 + 2             # region + semifinal
    assert points[semi] == 2 + 2
    assert points[conf_only] == 1
    assert points["other"] == 2
    assert nobody not in points


@pytest.mark.parametrize(
    "place, field, points",
    [(1, 20, 5), (2, 20, 5), (3, 20, 3), (5, 20, 3), (6, 20, 1), (10, 20, 1), (11, 20, 0),
     (1, 1, 5), (0, 20, 0), (1, 0, 0)],
)
def test_individual_bonus_tiers(place, field, points):
    # Top 10% +5, top 25% +3, top 50% +1. One tier: the best one, not a sum.
    assert aa.individual_bonus(place, field) == points


def test_individual_bonus_needs_two_tournament_games():
    def entry(pid, games, points):
        return {
            "player_id": pid, "position": "PG",
            "tournament_totals": {"GP": games, "PTS": points * games, "REB": 0, "AST": 0,
                                  "STL": 0, "BLK": 0, "DEF_A": 0, "DEF_S": 0},
        }
    # The best scorer played one game, so he is out of the field of four.
    field = [entry("one-game", 1, 40), entry("a", 3, 30), entry("b", 2, 20),
             entry("c", 2, 10), entry("d", 2, 5)]
    bonus = aa.tournament_bonus_by_player(field)
    assert "one-game" not in bonus
    assert bonus["a"] == 5          # 1st of 4: top 10% (ceil(0.4) = 1)
    assert bonus["b"] == 1          # 2nd of 4: top 50%
    assert "c" not in bonus and "d" not in bonus


# ---------------------------------------------------------------------------
# Third team
# ---------------------------------------------------------------------------

def test_third_team_rank_is_stable_and_seeded_by_franchise_and_season():
    first = [aa.third_team_rank("f1", 3, pos) for pos in POSITIONS]
    assert first == [aa.third_team_rank("f1", 3, pos) for pos in POSITIONS]
    assert set(first) <= {3, 4}
    seen = {
        tuple(aa.third_team_rank(f"f{n}", season, pos) for pos in POSITIONS)
        for n in range(8) for season in (1, 2)
    }
    assert len(seen) > 1        # it does vary between franchises and seasons


# ---------------------------------------------------------------------------
# Store-backed: projection, freeze, final
# ---------------------------------------------------------------------------

@pytest.fixture(params=["mongo", "sqlite"])
def store(request, tmp_path, monkeypatch):
    env = _mongomock_env(tmp_path) if request.param == "mongo" else _sqlite_env(tmp_path)
    s = create_store(env)
    monkeypatch.setattr(aa, "_store", lambda: s)
    monkeypatch.setattr(ftdisp, "teams_collection", s.teams_collection)
    return s


def _ratings(position, value):
    ratings = {pos: value - 30 for pos in POSITIONS}
    ratings[position] = value
    return ratings


def _seed_league(store, *, week=1, games=0, season=4):
    """Six teams, each with one player at every position. Team 0 is the best."""
    fid = ObjectId()
    team_ids = [ObjectId() for _ in TEAM_NAMES]
    store.teams_collection.insert_many(
        [{"_id": tid, "name": name, "team_id": name.upper()} for tid, name in zip(team_ids, TEAM_NAMES)]
    )
    fpd, ftd = [], []
    for t, tid in enumerate(team_ids):
        roster = []
        for p, position in enumerate(POSITIONS):
            pid = f"{TEAM_NAMES[t][0].lower()}-{position.lower()}"
            roster.append(pid)
            quality = len(team_ids) - t          # 6 for the best team, 1 for the worst
            fpd.append({
                "franchise_id": str(fid),
                "player_id": pid,
                "meta": {"first_name": TEAM_NAMES[t], "last_name": position,
                         "team": TEAM_NAMES[t], "team_id": str(tid), "year": "Senior"},
                "position_ratings": _ratings(position, 60 + quality * 5 + p),
                "season": {
                    "GP": games, "PTS": games * quality * 4, "REB": games * quality,
                    "OREB": 0, "DREB": games * quality, "AST": games * quality,
                    "STL": games * quality // 2, "BLK": games * quality // 2,
                    "DEF_A": games * 6, "DEF_S": games * quality,
                },
            })
        # A practice-squad player: on the roster list, never in the pool.
        bench = f"{TEAM_NAMES[t][0].lower()}-ps"
        fpd.append({
            "franchise_id": str(fid), "player_id": bench,
            "meta": {"first_name": "Practice", "last_name": "Squad", "team_id": str(tid), "year": "Freshman"},
            "position_ratings": _ratings("PG", 110), "season": {},
        })
        ftd.append({
            "franchise_id": fid, "team_id": tid, "natl_rank": t + 1,
            "players": roster + [bench], "training_squad_players": [bench],
        })
    store.franchise_players_data_collection.insert_many(fpd)
    store.franchise_team_data_collection.insert_many(ftd)

    results = {}
    for w in range(1, games + 1):
        results[str(w)] = [
            {"home_id": str(team_ids[i]), "away_id": str(team_ids[i + 1]),
             "home_score": 70, "away_score": 60}
            for i in range(0, len(team_ids), 2)
        ]
    doc = {
        "_id": fid, "week": week, "current_season": season, "results": results,
        "user_team_object_id": str(team_ids[-1]), "season_news": [],
    }
    store.franchises_collection.insert_one(copy.deepcopy(doc))
    return doc, team_ids


def _advance(store, doc, *, week, games):
    """Play up to ``games`` regular-season games for everyone and set the week."""
    for row in list(store.franchise_players_data_collection.find({"franchise_id": str(doc["_id"])})):
        if row["player_id"].endswith("-ps"):
            continue
        quality = 6 - TEAM_NAMES.index(row["meta"]["team"])
        store.franchise_players_data_collection.update_one(
            {"franchise_id": str(doc["_id"]), "player_id": row["player_id"]},
            {"$set": {"season": {
                "GP": games, "PTS": games * quality * 4, "REB": games * quality, "OREB": 0,
                "DREB": games * quality, "AST": games * quality, "STL": games * quality // 2,
                "BLK": games * quality // 2, "DEF_A": games * 6, "DEF_S": games * quality,
            }}},
        )
    team_ids = [str(t["team_id"]) for t in store.franchise_team_data_collection.find({"franchise_id": doc["_id"]})]
    doc["results"] = {
        str(w): [
            {"home_id": team_ids[i], "away_id": team_ids[i + 1], "home_score": 70, "away_score": 60}
            for i in range(0, len(team_ids), 2)
        ]
        for w in range(1, games + 1)
    }
    doc["week"] = week
    store.franchises_collection.update_one(
        {"_id": doc["_id"]}, {"$set": {"week": week, "results": doc["results"]}}
    )


def _stored(store, doc):
    return store.franchises_collection.find_one({"_id": doc["_id"]})


def test_one_player_per_position_on_each_team(store):
    doc, _teams = _seed_league(store, week=11, games=10)
    projection = aa.ensure_projection(doc)
    teams = projection["all_american_teams"]
    seen = set()
    for rank, key in enumerate(("first_team", "second_team", "third_team"), start=1):
        picks = teams[key]
        assert [p["position"] for p in picks] == list(POSITIONS)
        assert {p["rank"] for p in picks} == {rank}       # projections: third team is rank 3
        for pick in picks:
            assert pick["player_id"] not in seen
            seen.add(pick["player_id"])
            assert not pick["player_id"].endswith("-ps")  # practice squad is not in the pool
    assert len(seen) == 15
    # The best team is rank 1 at every position, the next is rank 2, then rank 3.
    assert {p["team_name"] for p in teams["first_team"]} == {"Alder"}
    assert {p["team_name"] for p in teams["second_team"]} == {"Birch"}
    assert {p["team_name"] for p in teams["third_team"]} == {"Cedar"}
    assert projection["week"] == 10
    assert projection["weights"] == {"attributes": 30.0, "stats": 70.0, "team": 0.0}


def test_preseason_is_attributes_only_and_publishes_the_story(store):
    doc, _teams = _seed_league(store, week=1, games=0)
    projection = aa.ensure_projection(doc)
    assert projection["week"] == 0 and projection["label"] == "Preseason"
    assert projection["weights"] == {"attributes": 100.0, "stats": 0.0, "team": 0.0}
    pick = projection["all_american_teams"]["first_team"][0]
    assert pick["score"] == pick["components"]["attributes"] == 100.0
    assert pick["stats"]["PTS"] is None
    news = _stored(store, doc)["season_news"]
    assert [s["story_id"] for s in news] == ["w1-all-americans"]
    assert news[0]["headline"] == "Preseason All-Americans announced"
    assert news[0]["type"] == "all_americans" and news[0]["week"] == 1


def test_projection_updates_once_per_week_and_is_idempotent(store, monkeypatch):
    doc, _teams = _seed_league(store, week=1, games=0)
    calls = []
    real = aa.build_projection
    monkeypatch.setattr(aa, "build_projection", lambda d, c: calls.append(c) or real(d, c))
    aa.ensure_projection(doc)
    aa.ensure_projection(doc)
    aa.ensure_projection(_stored(store, doc))
    assert calls == [0]
    _advance(store, doc, week=2, games=1)
    aa.ensure_projection(_stored(store, doc))
    aa.ensure_projection(_stored(store, doc))
    assert calls == [0, 1]
    assert _stored(store, doc)["awards"]["all_american_projection"]["label"] == "After week 1"


def test_stories_publish_at_weeks_1_7_13_19_26_only(store):
    doc, _teams = _seed_league(store, week=1, games=0)
    for completed in range(0, 27):
        if completed:
            _advance(store, doc, week=completed + 1, games=completed)
        aa.ensure_projection(_stored(store, doc))
    news = _stored(store, doc)["season_news"]
    assert [s["story_id"] for s in news] == [
        "w26-all-americans", "w19-all-americans", "w13-all-americans",
        "w7-all-americans", "w1-all-americans",
    ]
    final_story = news[0]
    text = " ".join(line.get("text", "") for line in final_story["rich_lines"])
    assert "not final" in text
    assert "Tournament performance can still change them" in text
    assert "PG: Alder PG (Alder, SR)" in text


def test_week_26_scores_are_frozen_through_the_tournaments(store, monkeypatch):
    doc, _teams = _seed_league(store, week=27, games=26)
    frozen = aa.ensure_projection(doc)
    assert frozen["week"] == 26 and frozen["frozen"] is True
    assert frozen["includes_tournament_games"] is False
    snap = store.franchise_players_data_collection.find_one(
        {"franchise_id": str(doc["_id"]), "player_id": "a-pg"})["aa_w26"]
    assert snap["position"] == "PG" and snap["clean"] is True
    assert snap["totals"]["GP"] == 26
    assert snap["score"] == frozen["all_american_teams"]["first_team"][0]["score"]

    # Tournament weeks: stats keep growing, the projection does not move.
    monkeypatch.setattr(aa, "build_projection", lambda *_a: pytest.fail("recomputed during a tournament"))
    for week in range(28, 35):
        store.franchise_players_data_collection.update_many(
            {"franchise_id": str(doc["_id"])}, {"$inc": {"season.PTS": 50, "season.GP": 1}})
        store.franchises_collection.update_one({"_id": doc["_id"]}, {"$set": {"week": week}})
        kept = aa.ensure_projection(_stored(store, doc))
        assert kept["week"] == 26
        assert kept["all_american_teams"] == frozen["all_american_teams"]


def test_franchise_first_seen_mid_tournament_freezes_what_it_has(store):
    # Shipped while this franchise was already in week 30: no projection, no freeze yet.
    doc, _teams = _seed_league(store, week=30, games=26)
    projection = aa.ensure_projection(doc)
    assert projection["week"] == 26 and projection["includes_tournament_games"] is True
    snap = store.franchise_players_data_collection.find_one(
        {"franchise_id": str(doc["_id"]), "player_id": "a-pg"})["aa_w26"]
    assert snap["clean"] is False
    # No late "end of the regular season" story.
    assert _stored(store, doc).get("season_news") == []


def _play_tournaments(store, doc, team_ids):
    """Team 1 (Birch) wins everything; its PG has a monster tournament."""
    birch, alder, cedar = str(team_ids[1]), str(team_ids[0]), str(team_ids[2])
    fields = {
        "week": 35,
        "conference_tournaments": {"1": {"champion": birch}, "2": {"champion": cedar}},
        "region_tournaments": {
            "A": {"final": [{"home_team": birch, "away_team": alder, "winner": birch}]},
            "B": {"final": [{"home_team": cedar, "away_team": "z", "winner": cedar}]},
        },
        "national_tournament": {
            "bracket": {
                "round1": [], "round2": [{"home_team": birch, "away_team": cedar}],
                "final": [{"home_team": birch, "away_team": "w", "winner": birch}],
            },
            "champion": birch,
        },
    }
    store.franchises_collection.update_one({"_id": doc["_id"]}, {"$set": fields})
    fpd = store.franchise_players_data_collection
    # Every Birch player plays 8 tournament games, Cedar 5, Alder 1 (out at once).
    for prefix, games, points in (("b", 8, 12), ("c", 5, 10), ("a", 1, 40)):
        for position in POSITIONS:
            fpd.update_one(
                {"franchise_id": str(doc["_id"]), "player_id": f"{prefix}-{position.lower()}"},
                {"$inc": {"season.GP": games, "season.PTS": games * points}},
            )
    return birch, alder, cedar


def test_final_is_the_week_26_score_plus_bonus_and_is_stable(store):
    doc, team_ids = _seed_league(store, week=27, games=26)
    frozen = aa.ensure_projection(doc)
    week26 = {p["player_id"]: p["score"] for key in aa.TEAM_KEYS for p in frozen["all_american_teams"][key]}
    birch, _alder, _cedar = _play_tournaments(store, doc, team_ids)

    final = aa.compute_final(_stored(store, doc))
    again = aa.compute_final(_stored(store, doc))
    strip = lambda result: {key: result["all_american_teams"][key] for key in aa.TEAM_KEYS}
    assert strip(final) == strip(again)                       # stable across recomputes
    assert final["all_american_final"]["basis"] == "week_26"
    assert final["all_american_final"]["week26_clean"] is True

    picks = {p["player_id"]: p for key in aa.TEAM_KEYS for p in final["all_american_teams"][key]}
    b_pg = picks["b-pg"]
    # Birch: conference +1, region +2, semifinal +2, title +5 = 10. Best PG line of the
    # two who played two tournament games: top 10% of that field, +5.
    assert b_pg["bonus"] == {"team": 10, "individual": 5, "total": 15}
    assert b_pg["week26_score"] == week26["b-pg"]
    assert b_pg["score"] == pytest.approx(week26["b-pg"] + 15)
    # Alder played one tournament game and won nothing: no bonus of either kind.
    a_pg = picks["a-pg"]
    assert a_pg["bonus"] == {"team": 0, "individual": 0, "total": 0}
    assert a_pg["score"] == week26["a-pg"]
    # The displayed line is the frozen week-26 line, not the season with tournaments.
    assert a_pg["games"] == 26 and b_pg["games"] == 26

    # Third team: rank 3 or 4 by the franchise + season coin, first and second fixed.
    ranks = final["all_american_final"]["third_team_ranks"]
    assert ranks == {pos: aa.third_team_rank(str(doc["_id"]), 4, pos) for pos in POSITIONS}
    assert [p["rank"] for p in final["all_american_teams"]["third_team"]] == [ranks[pos] for pos in POSITIONS]
    assert {p["rank"] for p in final["all_american_teams"]["first_team"]} == {1}
    assert {p["rank"] for p in final["all_american_teams"]["second_team"]} == {2}
    for key in aa.TEAM_KEYS:
        assert [p["position"] for p in final["all_american_teams"][key]] == list(POSITIONS)
    # Projections always show rank 3.
    assert {p["rank"] for p in frozen["all_american_teams"]["third_team"]} == {3}
    assert birch == b_pg["team_id"]


def test_mid_season_franchise_without_a_freeze_still_gets_a_final(store):
    # Already at week 35 when this shipped: no projection, no frozen scores.
    doc, team_ids = _seed_league(store, week=27, games=26)
    _play_tournaments(store, doc, team_ids)
    final = aa.compute_final(_stored(store, doc))
    assert final["all_american_final"]["basis"] == "season_to_date"
    assert final["all_american_final"]["week26_clean"] is False
    for key in aa.TEAM_KEYS:
        assert [p["position"] for p in final["all_american_teams"][key]] == list(POSITIONS)
    picks = {p["player_id"]: p for key in aa.TEAM_KEYS for p in final["all_american_teams"][key]}
    assert picks["b-pg"]["bonus"] == {"team": 10, "individual": 0, "total": 10}


def test_stored_shape_keeps_trophy_log_and_career_data_working(store):
    from BackEnd.utils.career_data import _user_all_american_kind_by_player

    doc, team_ids = _seed_league(store, week=27, games=26)
    aa.ensure_projection(doc)
    _play_tournaments(store, doc, team_ids)
    stored = _stored(store, doc)
    stored["user_team_object_id"] = str(team_ids[1])          # the user coaches Birch
    stored["user_id"] = "owner-1"
    awards = {**(stored.get("awards") or {}), **aa.compute_final(stored)}
    assert set(awards["all_american_teams"]) == {"first_team", "second_team", "third_team"}
    assert "all_american_projection" in awards                # the projection is kept beside it
    pick = awards["all_american_teams"]["first_team"][0]
    assert {"player_id", "name", "team_id", "team_name", "year", "position", "score", "stats"} <= set(pick)

    user_picks = tl._user_all_american_picks(stored, awards)
    assert user_picks and {kind for kind, _ in user_picks} <= {"all_american_1", "all_american_2", "all_american_3"}
    assert all(p["team_id"] == str(team_ids[1]) for _, p in user_picks)
    kinds = dict(_user_all_american_kind_by_player(awards, str(team_ids[1])))
    assert set(kinds.values()) <= {"all_american_1", "all_american_2", "all_american_3"}
    assert set(kinds) == {p["player_id"] for _, p in user_picks}


def test_awards_payload_projected_then_final(store):
    doc, team_ids = _seed_league(store, week=5, games=4)
    assert aa.awards_payload(doc) == {"status": "unavailable", "all_american_teams": None}
    aa.ensure_projection(doc)
    body = aa.awards_payload(doc)
    assert body["status"] == "projected" and body["label"] == "After week 4"
    assert body["stats_basis"] == "per_game"
    assert len(body["all_american_teams"]["first_team"]) == 5

    doc["awards"] = {**doc["awards"], **aa.compute_final(doc)}
    body = aa.awards_payload(doc)
    assert body["status"] == "final" and body["label"] == "Final"
    assert [p["position"] for p in body["all_american_teams"]["third_team"]] == list(POSITIONS)


def test_user_team_is_listed_at_its_training_position(store):
    doc, team_ids = _seed_league(store, week=11, games=10)
    # The user coaches Fir (last team) and trains his PG as a shooting guard.
    store.franchise_players_data_collection.update_one(
        {"franchise_id": str(doc["_id"]), "player_id": "f-pg"}, {"$set": {"training_position": "SG"}})
    # The same change on a CPU team is ignored: its roster shows the best position.
    store.franchise_players_data_collection.update_one(
        {"franchise_id": str(doc["_id"]), "player_id": "a-pg"}, {"$set": {"training_position": "SG"}})
    players = {p["player_id"]: p for p in aa.load_league(doc)["players"]}
    assert players["f-pg"]["position"] == "SG"
    assert players["f-pg"]["rating"] == 35        # his SG rating (65 at PG), not his best
    assert players["a-pg"]["position"] == "PG"
