"""Unit tests for recruiting report / results scoring and ranking."""

import random

from BackEnd.utils.recruiting_report_news import (
    build_recruiting_rankings_story,
    rank_teams_by_points,
    recruit_max_rt,
    team_points_from_lean_lists,
    team_points_from_signings,
)


def test_recruit_max_rt_uses_best_position():
    assert recruit_max_rt({"position_ratings": {"PG": 40, "SG": 72, "SF": 55}}) == 72
    assert recruit_max_rt({"position_ratings": {}}) == 0
    assert recruit_max_rt({}) == 0


def test_lean_slot_weights_round_to_ints():
    recruits = [
        {
            "position_ratings": {"PG": 101},
            "Lean": {"1": "t1", "2": "t2", "3": "t3"},
        },
        {
            "position_ratings": {"C": 50},
            "Lean": {"1": "t1", "2": "open", "3": None},
        },
    ]
    scores = team_points_from_lean_lists(recruits, recruit_max_rt)
    # 101 + 50 = 151 for slot1; round(101*0.5)=50; round(101*0.25)=25
    assert scores == {"t1": 151, "t2": 50, "t3": 25}


def test_signings_score_only_signing_team_full_rt():
    signed = [
        {"team_id": "a", "rt": 80},
        {"team_id": "a", "rt": 20},
        {"team_id": "b", "rt": 40},
        {"team_id": "", "rt": 99},
        {"team_id": "c", "rt": 0},
    ]
    assert team_points_from_signings(signed) == {"a": 100, "b": 40}


def test_rank_omits_zero_and_breaks_ties_randomly():
    scores = {"a": 10, "b": 10, "c": 0, "d": 5}
    names = {"a": "Alpha", "b": "Beta", "c": "Gamma", "d": "Delta"}
    ranked = rank_teams_by_points(scores, names, limit=10, rng=random.Random(0))
    assert [r["score"] for r in ranked] == [10, 10, 5]
    assert {r["team_id"] for r in ranked} == {"a", "b", "d"}
    assert [r["rank"] for r in ranked] == [1, 2, 3]
    # Same seed → same order
    ranked2 = rank_teams_by_points(scores, names, limit=10, rng=random.Random(0))
    assert [r["team_id"] for r in ranked2] == [r["team_id"] for r in ranked]


def test_rank_respects_limit():
    scores = {f"t{i}": 100 - i for i in range(30)}
    names = {f"t{i}": f"Team{i}" for i in range(30)}
    ranked = rank_teams_by_points(scores, names, limit=25, rng=random.Random(1))
    assert len(ranked) == 25
    assert ranked[0]["rank"] == 1
    assert ranked[-1]["rank"] == 25


def test_rank_include_team_ids_keeps_zeros():
    scores = {"a": 20, "b": 0}
    names = {"a": "Alpha", "b": "Beta", "c": "Gamma"}
    ranked = rank_teams_by_points(
        scores,
        names,
        limit=16,
        rng=random.Random(0),
        include_team_ids={"a", "b", "c"},
        include_zeros=True,
    )
    assert len(ranked) == 3
    assert ranked[0]["team_id"] == "a"
    assert ranked[0]["score"] == 20
    assert {r["team_id"] for r in ranked[1:]} == {"b", "c"}
    assert all(r["score"] == 0 for r in ranked[1:])


def test_build_story_includes_national_and_region_tables():
    scores = {"a": 100, "b": 90, "c": 80, "d": 10}
    names = {"a": "Alpha", "b": "Beta", "c": "Gamma", "d": "Delta", "e": "Echo"}
    story = build_recruiting_rankings_story(
        story_id="w2-recruiting-report",
        week=2,
        headline="Week 2 Recruiting Report",
        story_type="recruiting_report",
        scores=scores,
        team_name_map=names,
        user_region_letter="A",
        region_team_ids={"a", "d", "e"},
        national_limit=25,
        region_limit=16,
    )
    assert story is not None
    assert story["headline"] == "Week 2 Recruiting Report"
    assert story["story_id"] == "w2-recruiting-report"
    types = [line.get("type") for line in story["rich_lines"]]
    assert "ranking_table" in types
    headings = [
        line.get("text")
        for line in story["rich_lines"]
        if line.get("type") == "heading"
    ]
    assert "National Recruit Rankings" in headings
    assert "Region A" in headings
    ranking_tables = [
        line for line in story["rich_lines"] if line.get("type") == "ranking_table"
    ]
    assert len(ranking_tables) == 2
    assert ranking_tables[0]["column_split"] == [13, 12]
    assert ranking_tables[1]["column_split"] == [8, 8]
    # Region lists all region teams (including 0-point Echo), score-desc.
    assert [r["team_id"] for r in ranking_tables[1]["rows"]] == ["a", "d", "e"]
    assert ranking_tables[1]["rows"][2]["score"] == 0


def test_build_story_none_when_no_points():
    assert (
        build_recruiting_rankings_story(
            story_id="x",
            week=1,
            headline="Week 1 Recruiting Report",
            story_type="recruiting_report",
            scores={"a": 0},
            team_name_map={"a": "Alpha"},
            user_region_letter="A",
            region_team_ids={"a"},
        )
        is None
    )
