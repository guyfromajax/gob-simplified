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
    ranks = {"t1": 25, "t2": 14, "t3": 20, "t4": 12, "t5": 60, "t6": 3}
    names = {"t1": "Alpha", "t2": "Beta", "t3": "Gamma", "t4": "Delta", "t5": "Epsilon", "t6": "Zeta"}
    results = [
        _result_row("t1", "t2", 80, 72),   # gap 11 -> qualifies (away winner)
        _result_row("t4", "t3", 70, 75),   # gap 8 -> excluded (home winner, 20-12=8)
        _result_row("t6", "t5", 90, 95),   # gap 57 -> qualifies (home winner)
    ]

    story = franchise_routes._build_week_upset_report_story(5, results, ranks, names)

    assert story is not None
    assert story["headline"] == "Week 5 Upset Report"
    assert story["week"] == 5
    assert story["type"] == "upset_report"
    assert story["story_id"] == "w5-upset-report"
    # Sorted by rank gap descending: t5 over t6 (gap 57) first.
    assert story["lines"] == [
        "#60. Epsilon upset #3. Zeta by a score of 95-90.",
        "#25. Alpha upset #14. Beta by a score of 80-72.",
    ]


def test_upset_report_returns_none_when_no_games_qualify():
    ranks = {"t1": 10, "t2": 5}
    names = {"t1": "Alpha", "t2": "Beta"}
    # Gap of exactly 9 must NOT qualify (criteria is > 9).
    ranks_boundary = {"t1": 14, "t2": 5}
    results = [_result_row("t1", "t2", 80, 72)]

    assert franchise_routes._build_week_upset_report_story(3, results, ranks, names) is None
    assert franchise_routes._build_week_upset_report_story(3, results, ranks_boundary, names) is None


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
        _gain_record("Bo Jones", {"SC": 3, "SH": 3}, rt=30, pos="C", team_id="t1"),            # total 6 -> excluded (> 6 required)
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


def test_append_franchise_week_news_prepends_and_persists_on_doc(monkeypatch):
    franchise_id = ObjectId()
    team_a, team_b = str(ObjectId()), str(ObjectId())

    class _FakeFtdCollection:
        def find(self, _query, _projection=None):
            return [
                {"team_id": team_a, "natl_rank": 40},
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
    results = [_result_row(team_a, team_b, 88, 81)]  # gap 29 upset
    gains = [_gain_record("Al Smith", {"SC": 5, "SH": 4}, rt=33, pos="PG")]

    franchise_routes._append_franchise_week_news(franchise_id, franchise_doc, 2, results, gains)

    news = franchise_doc["season_news"]
    assert [story["story_id"] for story in news] == [
        "w2-upset-report",
        "w2-ps-all-stars",
        "w1-upset-report",
    ]
    assert news[0]["lines"] == ["#40. Underdog U upset #11. Favorite State by a score of 88-81."]


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
