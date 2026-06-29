"""Tests for the franchise News system (upset report + practice squad all-stars)."""
from bson import ObjectId

from BackEnd.api import franchise_routes


def test_join_with_and_grammar():
    assert franchise_routes._join_with_and([]) == ""
    assert franchise_routes._join_with_and(["Scoring"]) == "Scoring"
    assert franchise_routes._join_with_and(["Scoring", "Shooting"]) == "Scoring and Shooting"
    assert (
        franchise_routes._join_with_and(["Scoring", "Shooting", "Agility"])
        == "Scoring, Shooting, and Agility"
    )


def _result_row(away_id, home_id, away_score, home_score):
    return {
        "away_id": away_id,
        "home_id": home_id,
        "away_score": away_score,
        "home_score": home_score,
    }


def test_upset_report_qualification_boundary_and_format():
    ranks = {
        "t1": 95, "t2": 10,   # gap 85, loser 10 -> qualifies
        "t3": 59, "t4": 30,   # gap 29 -> excluded (must be > 29)
        "t5": 60, "t6": 3,    # gap 57, loser 3 -> qualifies
        "t7": 100, "t8": 20,  # gap 80, loser 20 -> qualifies
        "t9": 100, "t10": 65,  # gap 35 but loser rank > 64 -> excluded
    }
    names = {
        "t1": "Alpha", "t2": "Beta", "t3": "Gamma", "t4": "Delta",
        "t5": "Epsilon", "t6": "Zeta", "t7": "Eta", "t8": "Theta",
        "t9": "Iota", "t10": "Kappa",
    }
    results = [
        _result_row("t1", "t2", 80, 72),      # away winner
        _result_row("t3", "t4", 70, 75),      # home winner, gap exactly 29
        _result_row("t6", "t5", 90, 95),      # home winner (Epsilon over Zeta)
        _result_row("t7", "t8", 66, 60),      # away winner
        _result_row("t9", "t10", 77, 70),    # away winner, loser rank 65
    ]

    story = franchise_routes._build_week_upset_report_story(5, results, ranks, names)

    assert story is not None
    assert story["headline"] == "Week 5 Upset Report"
    assert story["week"] == 5
    assert story["type"] == "upset_report"
    assert story["story_id"] == "w5-upset-report"
    # Ascending by losing team's natl_rank (3, 10, 20).
    assert story["lines"] == [
        "#60. Epsilon upset #3. Zeta by a score of 95-90.",
        "#95. Alpha upset #10. Beta by a score of 80-72.",
        "#100. Eta upset #20. Theta by a score of 66-60.",
    ]


def test_upset_report_returns_none_when_no_games_qualify():
    ranks = {"t1": 10, "t2": 5}
    names = {"t1": "Alpha", "t2": "Beta"}
    # Gap of exactly 29 must NOT qualify (criteria is > 29).
    ranks_boundary = {"t1": 34, "t2": 5}
    results = [_result_row("t1", "t2", 80, 72)]

    assert franchise_routes._build_week_upset_report_story(3, results, ranks, names) is None
    assert franchise_routes._build_week_upset_report_story(3, results, ranks_boundary, names) is None


def test_upset_report_excludes_loser_rank_above_64():
    ranks = {"t1": 100, "t2": 65}  # gap 35 > 29, but loser rank > 64
    names = {"t1": "Alpha", "t2": "Beta"}
    results = [_result_row("t1", "t2", 80, 72)]

    assert franchise_routes._build_week_upset_report_story(3, results, ranks, names) is None


def _gain_record(name, deltas, rt=42, pos="PG", team_id="t-default"):
    return {
        "player_id": name.lower(),
        "name": name,
        "team_id": team_id,
        "deltas": deltas,
        "total_gain": sum(deltas.values()),
        "rt": rt,
        "pos": pos,
    }


def test_ps_all_stars_qualification_and_line_format():
    team_names = {"t1": "Morristown", "t2": "Lancaster"}
    gains = [
        _gain_record("Al Smith", {"SC": 4, "SH": 3, "ID": 1}, rt=38, pos="SG", team_id="t1"),  # total 8 -> qualifies
        _gain_record("Bo Jones", {"SC": 2, "SH": 2}, rt=30, pos="C", team_id="t1"),            # total 4 -> excluded (> 4 required)
        _gain_record("Cy Brown", {"SC": 4, "SH": 4, "RB": 4}, rt=51, pos="PF", team_id="t2"),  # total 12 -> qualifies, 3-way tie
    ]

    story = franchise_routes._build_ps_all_stars_story(7, gains, team_names)

    assert story is not None
    assert story["headline"] == "Practice Squad All-Stars"
    assert story["week"] == 7
    assert story["type"] == "ps_all_stars"
    assert story["story_id"] == "w7-ps-all-stars"
    # Sorted by total gain descending; tie grammar uses commas + "and".
    assert story["lines"] == [
        "Cy Brown of Lancaster increased by 12 attribute points this week. "
        "His strongest gains were in Scoring, Shooting, and Rebounding. "
        "He's now a 51 rated PF.",
        "Al Smith of Morristown increased by 8 attribute points this week. "
        "His strongest gains were in Scoring. "
        "He's now a 38 rated SG.",
    ]


def test_ps_all_stars_limits_to_top_10_with_tie_overflow():
    # 14 qualifiers: gains 21..12 then four players tied at 11.
    gains = [
        _gain_record(f"Player {i}", {"SC": 21 - i}) for i in range(9)  # 21..13
    ] + [
        _gain_record("Tenth Man", {"SC": 11}),
        _gain_record("Tie A", {"SC": 11}),
        _gain_record("Tie B", {"SC": 11}),
        _gain_record("Tie C", {"SC": 11}),
        _gain_record("Below Cut", {"SC": 10}),
    ]

    story = franchise_routes._build_ps_all_stars_story(9, gains, {})

    assert story is not None
    # 9 above the tie + 4 tied at the 10th spot = 13 lines; the 10-gain player is dropped.
    assert len(story["lines"]) == 13
    assert not any("Below Cut" in line for line in story["lines"])
    assert sum(1 for line in story["lines"] if "increased by 11 attribute points" in line) == 4
    # No team map provided: no " of " clause.
    assert story["lines"][0].startswith("Player 0 increased by 21 attribute points")


def test_ps_all_stars_two_way_tie_uses_and():
    gains = [_gain_record("Ed Davis", {"AG": 5, "ST": 5, "IQ": -1}, rt=44, pos="SF")]

    story = franchise_routes._build_ps_all_stars_story(2, gains, {})

    assert story is not None
    assert "His strongest gains were in Agility and Strength." in story["lines"][0]


def test_ps_all_stars_returns_none_when_nobody_qualifies():
    gains = [_gain_record("Al Smith", {"SC": 2, "SH": 2})]
    assert franchise_routes._build_ps_all_stars_story(4, gains, {}) is None
    assert franchise_routes._build_ps_all_stars_story(4, [], {}) is None


def _recruit_doc(recruit_id, name, rt, archetype="Sharp Shooter"):
    return {
        "recruit_id": recruit_id,
        "name": name,
        "archetype": archetype,
        "position_ratings": {"PG": rt},
    }


def test_recruiting_leans_top_rated_section_format_sort_and_rt_boundary():
    recruit_by_id = {
        "r1": _recruit_doc("r1", "Max High", 62, archetype="Floor General"),
        "r2": _recruit_doc("r2", "Mid Guy", 50),
        "r3": _recruit_doc("r3", "Boundary Bob", 49),  # RT must exceed 49
    }
    events = [
        {"recruit_id": "r2", "team_id": "t1"},
        {"recruit_id": "r1", "team_id": "t2"},
        {"recruit_id": "r3", "team_id": "t1"},
    ]

    story = franchise_routes._build_recruiting_leans_story(
        6, events, {}, {"t1": "Alpha", "t2": "Beta"}, recruit_by_id, {}, None,
    )

    assert story is not None
    assert story["headline"] == "Updated Recruiting Leans Announced"
    assert story["week"] == 6
    assert story["type"] == "recruiting_leans"
    assert story["story_id"] == "w6-recruiting-leans"
    # RT descending; Boundary Bob (49) excluded; no conference section appended.
    assert story["lines"] == [
        "Top Rated Recruit Announcements",
        "Max High who is a 62 rated Floor General has announced a lean toward Beta.",
        "Mid Guy who is a 50 rated Sharp Shooter has announced a lean toward Alpha.",
    ]


def test_recruiting_leans_combines_multiple_teams_for_one_recruit():
    recruit_by_id = {"r1": _recruit_doc("r1", "Max High", 70)}
    events = [
        {"recruit_id": "r1", "team_id": "t1"},
        {"recruit_id": "r1", "team_id": "t2"},
        {"recruit_id": "r1", "team_id": "t1"},  # duplicate event ignored
    ]

    story = franchise_routes._build_recruiting_leans_story(
        4, events, {}, {"t1": "Alpha", "t2": "Beta"}, recruit_by_id, {}, None,
    )

    assert story["lines"][1] == (
        "Max High who is a 70 rated Sharp Shooter has announced a lean toward Alpha and Beta."
    )


def test_recruiting_leans_conference_section_grouping_and_sorting():
    recruit_by_id = {
        "r1": _recruit_doc("r1", "Al Low", 28),
        "r2": _recruit_doc("r2", "Bo Mid", 41),
        "r3": _recruit_doc("r3", "Cy Top", 55),
        "r4": _recruit_doc("r4", "Out Of Conf", 60),
    }
    events = [
        {"recruit_id": "r1", "team_id": "t1"},
        {"recruit_id": "r2", "team_id": "t1"},
        {"recruit_id": "r3", "team_id": "t2"},
        {"recruit_id": "r4", "team_id": "t9"},  # team outside user's conference
    ]
    conference_by_team_id = {"t1": "3", "t2": "3", "t9": "7"}
    rank_by_team_id = {"t1": 88, "t2": 12, "t9": 1}

    story = franchise_routes._build_recruiting_leans_story(
        10, events, rank_by_team_id, {"t1": "Alpha", "t2": "Beta", "t9": "Niner"},
        recruit_by_id, conference_by_team_id, "3",
    )

    # Cy Top (55) also hits the Top Rated section, and Out Of Conf (60) qualifies
    # there even though his team isn't in the user's conference.
    assert story["lines"] == [
        "Top Rated Recruit Announcements",
        "Out Of Conf who is a 60 rated Sharp Shooter has announced a lean toward Niner.",
        "Cy Top who is a 55 rated Sharp Shooter has announced a lean toward Beta.",
        "",
        "Conference 3 Lean Announcements",
        "Beta",  # natl_rank 12 lists before rank 88
        "Cy Top (55)",
        "Alpha",
        "Bo Mid (41), Al Low (28)",  # recruits sorted by RT descending
    ]


def test_recruiting_leans_conference_only_runs_without_top_rated_section():
    recruit_by_id = {"r1": _recruit_doc("r1", "Al Low", 30)}
    events = [{"recruit_id": "r1", "team_id": "t1"}]

    story = franchise_routes._build_recruiting_leans_story(
        8, events, {"t1": 40}, {"t1": "Alpha"}, recruit_by_id, {"t1": "5"}, "5",
    )

    assert story["lines"] == [
        "Conference 5 Lean Announcements",
        "Alpha",
        "Al Low (30)",
    ]


def test_recruiting_leans_returns_none_when_nothing_qualifies():
    recruit_by_id = {"r1": _recruit_doc("r1", "Al Low", 30)}
    # Low RT and the team is outside the user's conference.
    events = [{"recruit_id": "r1", "team_id": "t1"}]

    assert franchise_routes._build_recruiting_leans_story(
        3, events, {}, {"t1": "Alpha"}, recruit_by_id, {"t1": "2"}, "6",
    ) is None
    assert franchise_routes._build_recruiting_leans_story(
        3, [], {}, {}, {}, {}, "6",
    ) is None


def test_append_week_news_resolves_user_conference_from_string_team_id(monkeypatch):
    """franchise.user_team_object_id is stored as an ObjectId *string*; the news flow
    must still resolve the user's conference so the conference leans section generates."""
    import types

    franchise_id = ObjectId()
    user_team_oid = ObjectId()
    rival_oid = ObjectId()

    class _FakeFtdCollection:
        def find(self, _query, _projection=None):
            return [
                {"team_id": str(user_team_oid), "natl_rank": 30},
                {"team_id": str(rival_oid), "natl_rank": 8},
            ]

    class _FakeTeamsCollection:
        def __init__(self, docs):
            self._docs = {doc["_id"]: doc for doc in docs}

        def find(self, query, _projection=None):
            return [self._docs[oid] for oid in query["_id"]["$in"] if oid in self._docs]

        def find_one(self, query, _projection=None):
            # Like real Mongo: an ObjectId _id never matches a string key.
            return self._docs.get(query["_id"])

    class _FakeRecruitsCollection:
        def find(self, _query, _projection=None):
            return [_recruit_doc("r1", "Al Low", 31, archetype="Slasher")]

    monkeypatch.setattr(franchise_routes, "franchise_team_data_collection", _FakeFtdCollection())
    monkeypatch.setattr(franchise_routes, "franchise_recruits_data_collection", _FakeRecruitsCollection())
    monkeypatch.setattr(
        franchise_routes,
        "_format_team_name_map",
        lambda team_ids=None: {str(rival_oid): "Rival U"},
    )
    monkeypatch.setattr(
        franchise_routes,
        "db",
        types.SimpleNamespace(teams=_FakeTeamsCollection([
            {"_id": user_team_oid, "conference": 4},
            {"_id": rival_oid, "conference": 4},
        ])),
    )

    franchise_doc = {
        "user_team_id": "Morristown",
        "user_team_object_id": str(user_team_oid),
    }
    events = [{"recruit_id": "r1", "team_id": str(rival_oid)}]

    franchise_routes._append_franchise_week_news(franchise_id, franchise_doc, 3, [], [], events)

    stories = franchise_doc.get("season_news") or []
    leans_story = next((s for s in stories if s.get("type") == "recruiting_leans"), None)
    assert leans_story is not None
    assert leans_story["lines"] == [
        "Conference 4 Lean Announcements",
        "Rival U",
        "Al Low (31)",
    ]


def test_append_franchise_week_news_prepends_and_persists_on_doc(monkeypatch):
    franchise_id = ObjectId()
    team_a, team_b = str(ObjectId()), str(ObjectId())

    class _FakeFtdCollection:
        def find(self, _query, _projection=None):
            return [
                {"team_id": team_a, "natl_rank": 50},
                {"team_id": team_b, "natl_rank": 11},
            ]

    monkeypatch.setattr(franchise_routes, "franchise_team_data_collection", _FakeFtdCollection())
    monkeypatch.setattr(
        franchise_routes,
        "_format_team_name_map",
        lambda team_ids=None: {team_a: "Underdog U", team_b: "Favorite State"},
    )

    franchise_doc = {
        "season_news": [
            {"story_id": "w1-upset-report", "week": 1, "headline": "Week 1 Upset Report", "lines": []}
        ]
    }
    results = [_result_row(team_a, team_b, 88, 81)]  # gap 39 upset, loser rank 11
    gains = [_gain_record("Al Smith", {"SC": 5, "SH": 4}, rt=33, pos="PG")]

    franchise_routes._append_franchise_week_news(franchise_id, franchise_doc, 2, results, gains)

    news = franchise_doc["season_news"]
    assert [story["story_id"] for story in news] == [
        "w2-upset-report",
        "w2-ps-all-stars",
        "w1-upset-report",
    ]
    assert news[0]["lines"] == ["#50. Underdog U upset #11. Favorite State by a score of 88-81."]


def test_append_franchise_week_news_skips_eos_weeks(monkeypatch):
    franchise_doc = {}
    franchise_routes._append_franchise_week_news(ObjectId(), franchise_doc, 27, [], [])
    assert "season_news" not in franchise_doc


def test_franchise_news_headlines_limit_and_shape():
    franchise_doc = {
        "season_news": [
            {"story_id": f"w{week}-upset-report", "week": week, "headline": f"Week {week} Upset Report", "lines": ["x"]}
            for week in range(8, 0, -1)
        ]
    }
    headlines = franchise_routes._franchise_news_headlines(franchise_doc)
    assert len(headlines) == 5
    assert headlines[0] == {"story_id": "w8-upset-report", "headline": "Week 8 Upset Report", "week": 8}
    assert all(set(h.keys()) == {"story_id", "headline", "week"} for h in headlines)
