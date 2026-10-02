"""Tests for the franchise News system (upset report + practice squad all-stars)."""
import pytest
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
        "He's now rated C+ at PF.",
        "Al Smith of Morristown increased by 8 attribute points this week. "
        "His strongest gains were in Scoring. "
        "He's now rated D at SG.",
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
        "Max High, a Floor General rated B, has announced a lean toward Beta.",
        "Mid Guy, a Sharp Shooter rated C+, has announced a lean toward Alpha.",
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
        "Max High, a Sharp Shooter rated B+, has announced a lean toward Alpha and Beta."
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
        "Out Of Conf, a Sharp Shooter rated B, has announced a lean toward Niner.",
        "Cy Top, a Sharp Shooter rated C+, has announced a lean toward Beta.",
        "",
        "Conference 3 Lean Announcements",
        "Beta",  # natl_rank 12 lists before rank 88
        "Cy Top (C+)",
        "Alpha",
        "Bo Mid (C), Al Low (F)",  # recruits remain sorted by numeric RT descending
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
        "Al Low (D)",
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
        lambda team_ids=None, franchise=None: {str(rival_oid): "Rival U"},
    )
    monkeypatch.setattr(
        franchise_routes,
        "db",
        types.SimpleNamespace(teams=_FakeTeamsCollection([
            {"_id": user_team_oid, "conference": 4},
            {"_id": rival_oid, "conference": 4},
        ])),
    )
    monkeypatch.setattr(
        franchise_routes,
        "_build_weekly_recruiting_report_story",
        lambda *_a, **_k: {
            "story_id": "w4-recruiting-report",
            "week": 4,
            "type": "recruiting_report",
            "headline": "Week 4 Recruiting Report",
            "rich_lines": [
                {"type": "heading", "text": "National Recruit Rankings"},
                {
                    "type": "ranking_table",
                    "columns": ["Rank", "Team", "Score"],
                    "rows": [{"rank": 1, "team_id": "x", "team": "X", "score": 10}],
                },
            ],
        },
    )

    franchise_doc = {
        "user_team_id": "Morristown",
        "user_team_object_id": str(user_team_oid),
    }
    events = [{"recruit_id": "r1", "team_id": str(rival_oid)}]

    franchise_routes._append_franchise_week_news(franchise_id, franchise_doc, 3, [], [], events)

    stories = franchise_doc.get("season_news") or []
    report = next((s for s in stories if s.get("type") == "recruiting_report"), None)
    assert report is not None
    assert report["headline"] == "Week 4 Recruiting Report"
    assert report["story_id"] == "w4-recruiting-report"
    assert not any(s.get("type") == "recruiting_leans" for s in stories)
    texts = [line.get("text") for line in report["rich_lines"] if line.get("text")]
    assert "National Recruit Rankings" in texts
    # The redundant outer heading is gone; the conference sub-heading stays.
    assert "Recruiting Leans Announced" not in texts
    # The conference is named the way the rest of the app names it: region letter + number.
    assert "Conference B4 Lean Announcements" in texts
    assert "Conference 4 Lean Announcements" not in texts
    # The team and its recruit are a block, not two text lines that run together.
    assert "Rival U" not in texts and "Al Low (D)" not in texts
    blocks = [line for line in report["rich_lines"] if line.get("type") == "team_recruits"]
    assert blocks == [{
        "type": "team_recruits",
        "team_id": str(rival_oid),
        "team_name": "Rival U",
        "recruits": [{"recruit_id": "r1", "name": "Al Low", "rt": 31}],
    }]


def _conference_case():
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
    return (
        events,
        {"t1": 88, "t2": 12, "t9": 1},
        {"t1": "Alpha", "t2": "Beta", "t9": "Niner"},
        recruit_by_id,
        {"t1": "3", "t2": "3", "t9": "7"},
        "3",
    )


def test_recruiting_report_lean_section_is_structured_story_content():
    content = franchise_routes._recruiting_leans_content(*_conference_case())
    story = franchise_routes._merge_recruiting_report_with_leans(None, content, report_week=11)
    assert story["story_id"] == "w11-recruiting-report"
    assert story["rich_lines"] == [
        {"type": "gap"},
        {"type": "heading", "text": "Top Rated Recruit Announcements"},
        {"type": "text", "text": "Out Of Conf, a Sharp Shooter rated B, has announced a lean toward Niner."},
        {"type": "text", "text": "Cy Top, a Sharp Shooter rated C+, has announced a lean toward Beta."},
        {"type": "gap"},
        {"type": "heading", "text": "Conference B3 Lean Announcements"},
        # Teams by national rank (12 before 88), recruits by RT.
        {"type": "team_recruits", "team_id": "t2", "team_name": "Beta",
         "recruits": [{"recruit_id": "r3", "name": "Cy Top", "rt": 55}]},
        {"type": "team_recruits", "team_id": "t1", "team_name": "Alpha",
         "recruits": [{"recruit_id": "r2", "name": "Bo Mid", "rt": 41},
                      {"recruit_id": "r1", "name": "Al Low", "rt": 28}]},
    ]
    assert not any(line.get("text") == "Recruiting Leans Announced" for line in story["rich_lines"])


def test_structured_lean_section_names_the_same_teams_and_recruits_as_the_plain_lines():
    """The block shape changes how the section is stored, not who is in it."""
    case = _conference_case()
    lines = franchise_routes._build_recruiting_leans_lines(*case)
    rich = franchise_routes._recruiting_leans_section_rich_lines(franchise_routes._recruiting_leans_content(*case))
    flat = []
    for line in rich:
        if line["type"] == "gap":
            flat.append("")
        elif line["type"] in ("heading", "text"):
            flat.append(line["text"])
        else:
            flat.append(line["team_name"])
            flat.append(", ".join(
                f"{r['name']} ({franchise_routes.format_rt_display(r['rt'])})" for r in line["recruits"]
            ))
    # Only the conference's name differs: the plain lines say "Conference 3".
    assert "Conference 3 Lean Announcements" in lines and "Conference B3 Lean Announcements" in flat
    flat = [line.replace("Conference B3 ", "Conference 3 ") for line in flat]
    assert flat[0] == "" and flat[1:] == lines


def test_lean_section_with_only_conference_leans_has_no_top_rated_heading():
    content = franchise_routes._recruiting_leans_content(
        [{"recruit_id": "r1", "team_id": "t1"}], {"t1": 5}, {"t1": "Alpha"},
        {"r1": _recruit_doc("r1", "Al Low", 28)}, {"t1": "5"}, "5",
    )
    rich = franchise_routes._recruiting_leans_section_rich_lines(content)
    assert [line["type"] for line in rich] == ["gap", "heading", "team_recruits"]
    assert rich[1]["text"] == "Conference C5 Lean Announcements"


@pytest.mark.parametrize("conference, label", [("1", "A1"), ("2", "A2"), ("3", "B3"), ("16", "H16")])
def test_conference_heading_uses_the_app_label(conference, label):
    content = franchise_routes._recruiting_leans_content(
        [{"recruit_id": "r1", "team_id": "t1"}], {"t1": 5}, {"t1": "Alpha"},
        {"r1": _recruit_doc("r1", "Al Low", 28)}, {"t1": conference}, conference,
    )
    rich = franchise_routes._recruiting_leans_section_rich_lines(content)
    assert rich[1] == {"type": "heading", "text": f"Conference {label} Lean Announcements"}


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
        lambda team_ids=None, franchise=None: {team_a: "Underdog U", team_b: "Favorite State"},
    )
    monkeypatch.setattr(
        franchise_routes,
        "_build_weekly_recruiting_report_story",
        lambda *_a, **_k: None,
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


def test_append_franchise_week_news_skips_after_lean_window(monkeypatch):
    franchise_doc = {}
    franchise_routes._append_franchise_week_news(ObjectId(), franchise_doc, 35, [], [])
    assert "season_news" not in franchise_doc


def test_recruiting_results_story_carries_exact_headline_and_content_into_week_one():
    source = {
        "story_id": "s1-recruiting-results",
        "week": 36,
        "type": "recruiting_results",
        "headline": "Season 1 Recruiting Results",
        "rich_lines": [
            {"type": "heading", "text": "National Recruit Rankings"},
            {"type": "ranking_table", "rows": [{"rank": 1, "team": "Ocean City", "score": 91}]},
        ],
    }
    franchise_doc = {"current_season": 1, "season_news": [source]}

    carried = franchise_routes._carryover_recruiting_results_story(franchise_doc)

    assert carried is not source
    assert carried["story_id"] == "s1-recruiting-results"
    assert carried["headline"] == source["headline"]
    assert carried["rich_lines"] == source["rich_lines"]
    assert carried["week"] == 1
    assert carried["source_week"] == 36
    assert carried["carried_from_season"] == 1
    assert carried["carried_into_season"] == 2


def test_recruiting_results_carryover_requires_the_previous_seasons_exact_story():
    franchise_doc = {
        "current_season": 2,
        "season_news": [
            {"story_id": "s1-recruiting-results", "type": "recruiting_results"},
            {"story_id": "s2-recruiting-results", "type": "other"},
        ],
    }
    assert franchise_routes._carryover_recruiting_results_story(franchise_doc) is None


def test_franchise_news_headlines_excludes_upset_and_limits():
    franchise_doc = {
        "season_news": [
            {
                "story_id": "w8-upset-report",
                "week": 8,
                "type": "upset_report",
                "headline": "Week 8 Upset Report",
                "lines": ["x"],
            },
            {
                "story_id": "w9-recruiting-report",
                "week": 9,
                "type": "recruiting_report",
                "headline": "Week 9 Recruiting Report",
                "rich_lines": [],
            },
            {
                "story_id": "w8-ps-all-stars",
                "week": 8,
                "type": "ps_all_stars",
                "headline": "Practice Squad All-Stars",
                "lines": ["y"],
            },
            {
                "story_id": "w7-upset-report",
                "week": 7,
                "type": "upset_report",
                "headline": "Week 7 Upset Report",
                "lines": ["z"],
            },
            {
                "story_id": "w7-recruiting-movement",
                "week": 7,
                "type": "recruiting_movement",
                "headline": "Your Recruiting Board Moved",
                "lines": ["m"],
            },
        ]
    }
    headlines = franchise_routes._franchise_news_headlines(franchise_doc)
    assert [h["story_id"] for h in headlines] == [
        "w9-recruiting-report",
        "w8-ps-all-stars",
        "w7-recruiting-movement",
    ]
    assert all(set(h.keys()) == {"story_id", "headline", "week"} for h in headlines)


def test_weekly_report_story_carries_movement_the_user_row_and_the_caption(monkeypatch):
    """The weekly builder reads last week's stored report, the user's team and the
    durable rank, and hands them to the story: movement, the foot row, the caption."""
    from BackEnd.utils.recruiting_report_news import WEEKLY_SCORE_CAPTION

    teams = [f"t{i:02d}" for i in range(1, 31)]            # 30 teams with points
    user = "t30"                                            # the weakest: outside the top 25

    def recruits_for(order):
        # One recruit per team, rated so the teams rank in ``order``.
        return [
            {"recruit_id": f"r-{tid}", "Lean": {"1": tid}, "position_ratings": {"PG": 90 - place}}
            for place, tid in enumerate(order)
        ]

    state = {"recruits": recruits_for(teams)}

    class _Recruits:
        def find(self, _query, _projection=None):
            return list(state["recruits"])

    monkeypatch.setattr(franchise_routes, "franchise_recruits_data_collection", _Recruits())
    monkeypatch.setattr(
        franchise_routes, "_persist_recruiting_ranks_from_scores",
        lambda _fid, _scores: {user: {"recruiting_rank": 30}},
    )
    monkeypatch.setattr(
        franchise_routes, "_format_team_name_map",
        lambda team_ids=None, franchise=None: {tid: tid.upper() for tid in teams},
    )
    monkeypatch.setattr(franchise_routes, "_user_team_region_letter", lambda _doc: "A")
    monkeypatch.setattr(franchise_routes, "_region_team_ids_for_letter", lambda _letter: set(teams[:4]))
    monkeypatch.setattr(franchise_routes, "get_user_team_from_franchise", lambda _doc: ("T30", user))

    doc = {"_id": ObjectId(), "season_news": []}
    first = franchise_routes._build_weekly_recruiting_report_story(doc["_id"], doc, 1)
    national = next(line for line in first["rich_lines"] if line.get("table") == "national")
    assert national["caption"] == WEEKLY_SCORE_CAPTION
    assert len(national["rows"]) == 25
    assert national["user_row"]["team_id"] == user and national["user_row"]["rank"] == 30
    # Week 1: nothing to move against.
    assert all("move" not in row and "new" not in row for row in national["rows"])
    assert "move" not in national["user_row"]

    # Next week t02 passes t01, and the story is built with last week's in season_news.
    doc["season_news"] = [first]
    state["recruits"] = recruits_for([teams[1], teams[0]] + teams[2:])
    second = franchise_routes._build_weekly_recruiting_report_story(doc["_id"], doc, 2)
    rows = {row["team_id"]: row for row in
            next(line for line in second["rich_lines"] if line.get("table") == "national")["rows"]}
    assert rows["t02"]["rank"] == 1 and rows["t02"]["move"] == 1
    assert rows["t01"]["rank"] == 2 and rows["t01"]["move"] == -1
    assert rows["t03"]["move"] == 0
    region = next(line for line in second["rich_lines"] if line.get("table") == "region")
    assert {row["team_id"]: row["move"] for row in region["rows"]} == {"t02": 1, "t01": -1, "t03": 0, "t04": 0}

    # A week whose previous report is missing (none was published) shows no movement.
    third = franchise_routes._build_weekly_recruiting_report_story(doc["_id"], doc, 4)
    national = next(line for line in third["rich_lines"] if line.get("table") == "national")
    assert all("move" not in row and "new" not in row for row in national["rows"])


# ---------------------------------------------------------------------------
# Upset Report: each line stores its game
# ---------------------------------------------------------------------------

def _upset_case():
    ranks = {"t1": 95, "t2": 10, "t5": 60, "t6": 3, "t3": 59, "t4": 30}
    names = {"t1": "Alpha", "t2": "Beta", "t5": "Epsilon", "t6": "Zeta", "t3": "Gamma", "t4": "Delta"}
    results = [
        _result_row("t1", "t2", 80, 72),      # Alpha (away) upsets Beta
        _result_row("t6", "t5", 90, 95),      # Epsilon (home) upsets Zeta
        _result_row("t3", "t4", 70, 75),      # no upset
    ]
    return results, ranks, names


def test_upset_lines_store_their_game_and_keep_the_same_text():
    results, ranks, names = _upset_case()
    # Keyed (away id, home id), as the result rows are.
    game_ids = {("t1", "t2"): "g-alpha-beta", ("t6", "t5"): "g-zeta-epsilon", ("t3", "t4"): "g-no-upset"}
    story = franchise_routes._build_week_upset_report_story(5, results, ranks, names, game_id_by_matchup=game_ids)
    assert story["rich_lines"] == [
        {"type": "game_result", "text": "#60. Epsilon upset #3. Zeta by a score of 95-90.", "game_id": "g-zeta-epsilon"},
        {"type": "game_result", "text": "#95. Alpha upset #10. Beta by a score of 80-72.", "game_id": "g-alpha-beta"},
    ]
    # The plain lines are the same sentences, in the same order.
    assert story["lines"] == [line["text"] for line in story["rich_lines"]]


def test_upset_line_with_no_stored_game_has_no_game_id():
    results, ranks, names = _upset_case()
    story = franchise_routes._build_week_upset_report_story(
        5, results, ranks, names, game_id_by_matchup={("t1", "t2"): "g-alpha-beta"},
    )
    by_text = {line["text"]: line for line in story["rich_lines"]}
    assert by_text["#95. Alpha upset #10. Beta by a score of 80-72."]["game_id"] == "g-alpha-beta"
    assert "game_id" not in by_text["#60. Epsilon upset #3. Zeta by a score of 95-90."]
    # No lookup at all: every line is written, none has a game.
    bare = franchise_routes._build_week_upset_report_story(5, results, ranks, names)
    assert [line["type"] for line in bare["rich_lines"]] == ["game_result", "game_result"]
    assert not any("game_id" in line for line in bare["rich_lines"])


def test_the_game_lookup_runs_only_when_the_week_has_an_upset():
    results, ranks, names = _upset_case()
    calls = []

    def lookup():
        calls.append(1)
        return {("t1", "t2"): "g1"}

    assert franchise_routes._build_week_upset_report_story(
        5, [_result_row("t3", "t4", 70, 75)], ranks, names, game_id_by_matchup=lookup) is None
    assert calls == []
    story = franchise_routes._build_week_upset_report_story(5, results, ranks, names, game_id_by_matchup=lookup)
    assert calls == [1]
    assert any(line.get("game_id") == "g1" for line in story["rich_lines"])


def test_week_game_ids_keeps_one_week_and_survives_a_failed_read(monkeypatch):
    import BackEnd.utils.schedule_browse as schedule_browse

    seen = {}

    def fake(franchise_id, stamp=None):
        seen["args"] = (franchise_id, stamp)
        return {(4, "a", "b"): "g-week-4", (5, "a", "b"): "g-week-5", (5, "c", "d"): "g-week-5b"}

    monkeypatch.setattr(schedule_browse, "matchup_game_ids", fake)
    assert franchise_routes._week_game_ids("fid", 5) == {("a", "b"): "g-week-5", ("c", "d"): "g-week-5b"}
    # Its own stamp, so a cache keyed on the stored franchise cannot answer for a week
    # whose results are not stored yet.
    assert seen["args"][0] == "fid" and seen["args"][1] != None  # noqa: E711

    def broken(_franchise_id, stamp=None):
        raise RuntimeError("no games collection")

    monkeypatch.setattr(schedule_browse, "matchup_game_ids", broken)
    assert franchise_routes._week_game_ids("fid", 5) == {}


def test_append_week_news_stores_the_game_on_each_upset_line(monkeypatch):
    franchise_id = ObjectId()
    team_a, team_b = str(ObjectId()), str(ObjectId())

    class _Ftd:
        def find(self, _query, _projection=None):
            return [{"team_id": team_a, "natl_rank": 50}, {"team_id": team_b, "natl_rank": 11}]

    monkeypatch.setattr(franchise_routes, "franchise_team_data_collection", _Ftd())
    monkeypatch.setattr(
        franchise_routes, "_format_team_name_map",
        lambda team_ids=None, franchise=None: {team_a: "Underdog U", team_b: "Favorite State"},
    )
    monkeypatch.setattr(franchise_routes, "_build_weekly_recruiting_report_story", lambda *_a, **_k: None)
    asked = []

    def week_ids(fid, week):
        asked.append((fid, week))
        return {(team_a, team_b): "game-123"}

    monkeypatch.setattr(franchise_routes, "_week_game_ids", week_ids)
    doc = {"season_news": []}
    franchise_routes._append_franchise_week_news(franchise_id, doc, 2, [_result_row(team_a, team_b, 88, 81)], [])
    story = doc["season_news"][0]
    assert story["story_id"] == "w2-upset-report"
    assert story["rich_lines"] == [{
        "type": "game_result",
        "text": "#50. Underdog U upset #11. Favorite State by a score of 88-81.",
        "game_id": "game-123",
    }]
    assert asked == [(franchise_id, 2)]
