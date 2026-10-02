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


def test_compute_recruiting_rank_fields_full_128_includes_zeros():
    from BackEnd.utils.recruiting_report_news import (
        FTD_RECRUITING_RANK,
        FTD_RECRUITING_REGION_RANK,
        FTD_RECRUITING_SCORE,
        compute_recruiting_rank_fields,
    )

    team_ids = [f"t{i}" for i in range(1, 9)]
    region_by = {tid: ("A" if i <= 4 else "B") for i, tid in enumerate(team_ids, start=1)}
    scores = {"t1": 100, "t2": 50, "t5": 80}
    ranked = compute_recruiting_rank_fields(
        scores, team_ids, region_by, rng=random.Random(0)
    )
    assert len(ranked) == 8
    assert ranked["t1"][FTD_RECRUITING_RANK] == 1
    assert ranked["t1"][FTD_RECRUITING_SCORE] == 100
    assert ranked["t5"][FTD_RECRUITING_RANK] == 2
    assert ranked["t2"][FTD_RECRUITING_RANK] == 3
    # Zero-point teams still receive national places 4..8
    zero_places = sorted(
        ranked[tid][FTD_RECRUITING_RANK]
        for tid in team_ids
        if ranked[tid][FTD_RECRUITING_SCORE] == 0
    )
    assert zero_places == [4, 5, 6, 7, 8]
    # Region A: t1, t2, then two zeros → places 1..4
    assert ranked["t1"][FTD_RECRUITING_REGION_RANK] == 1
    assert ranked["t2"][FTD_RECRUITING_REGION_RANK] == 2
    assert {
        ranked["t3"][FTD_RECRUITING_REGION_RANK],
        ranked["t4"][FTD_RECRUITING_REGION_RANK],
    } == {3, 4}
    # Region B: t5 first
    assert ranked["t5"][FTD_RECRUITING_REGION_RANK] == 1



# ---------------------------------------------------------------------------
# Rank movement, the user's own row, and the score caption
# ---------------------------------------------------------------------------

NAMES = {key: key.upper() for key in "abcdefghij"}


def _report(week, scores, **kwargs):
    return build_recruiting_rankings_story(
        story_id=f"w{week}-recruiting-report",
        week=week,
        headline=f"Week {week} Recruiting Report",
        story_type="recruiting_report",
        scores=scores,
        team_name_map=NAMES,
        user_region_letter="A",
        region_team_ids={"a", "b", "c", "d"},
        **kwargs,
    )


def _tables(story):
    return {line["table"]: line for line in story["rich_lines"] if line.get("type") == "ranking_table"}


def _by_team(table):
    return {row["team_id"]: row for row in table["rows"]}


def test_week_one_and_a_week_with_no_prior_report_carry_no_movement():
    story = _report(1, {"a": 50, "b": 40})
    for table in _tables(story).values():
        for row in table["rows"]:
            assert "move" not in row and "new" not in row
    # No report last week (previous_story is None) is the same.
    story = _report(7, {"a": 50, "b": 40}, previous_story=None)
    assert all("move" not in row and "new" not in row for row in _tables(story)["national"]["rows"])


def test_movement_is_against_last_weeks_same_table_rose_fell_unchanged_new():
    last = _report(2, {"a": 90, "b": 80, "c": 70, "d": 60}, national_limit=4)
    assert [row["team_id"] for row in _tables(last)["national"]["rows"]] == ["a", "b", "c", "d"]
    # This week: c rises two places, b falls one, a holds, and e is in the table for the
    # first time (d drops out of it).
    this = _report(3, {"a": 95, "c": 92, "b": 85, "e": 70, "d": 5}, national_limit=4, previous_story=last)
    national = _by_team(_tables(this)["national"])
    assert [row["team_id"] for row in _tables(this)["national"]["rows"]] == ["a", "c", "b", "e"]
    assert national["c"]["move"] == 1 and "new" not in national["c"]       # 3rd -> 2nd: rose
    assert national["b"]["move"] == -1                                       # 2nd -> 3rd: fell
    assert national["a"]["move"] == 0                                        # unchanged
    assert national["e"].get("new") is True and "move" not in national["e"]  # not ranked last week
    # The region table moves against last week's region table, not the national one.
    region_last = _by_team(_tables(last)["region"])
    region = _by_team(_tables(this)["region"])
    assert [region_last[t]["rank"] for t in "abcd"] == [1, 2, 3, 4]
    assert [region[t]["rank"] for t in "acbd"] == [1, 2, 3, 4]
    assert region["c"]["move"] == 1 and region["b"]["move"] == -1
    assert region["a"]["move"] == 0 and region["d"]["move"] == 0
    assert not any(row.get("new") for row in _tables(this)["region"]["rows"])


def test_movement_reads_a_report_stored_before_tables_were_named():
    # The old stored shape: no "table" key, national first and region second.
    last = _report(2, {"a": 90, "b": 80, "c": 70}, national_limit=3)
    for line in last["rich_lines"]:
        line.pop("table", None)
    this = _report(3, {"b": 99, "a": 90, "c": 70}, national_limit=3, previous_story=last)
    national = _by_team(_tables(this)["national"])
    assert national["b"]["move"] == 1 and national["a"]["move"] == -1 and national["c"]["move"] == 0


def test_user_team_outside_the_table_gets_a_foot_row_with_its_real_rank():
    scores = {"a": 90, "b": 80, "c": 70, "d": 60, "e": 50}
    story = _report(4, scores, national_limit=3, user_team_id="e")
    national = _tables(story)["national"]
    assert [row["team_id"] for row in national["rows"]] == ["a", "b", "c"]
    assert national["user_row"] == {"rank": 5, "team_id": "e", "team": "E", "score": 50}
    # In the table already: no foot row.
    assert "user_row" not in _tables(_report(4, scores, national_limit=3, user_team_id="b"))["national"]
    # No user team named: no foot row.
    assert "user_row" not in _tables(_report(4, scores, national_limit=3))["national"]
    # No points: the durable full-league rank, score 0.
    story = _report(4, scores, national_limit=3, user_team_id="j", user_zero_rank=97)
    assert _tables(story)["national"]["user_row"] == {"rank": 97, "team_id": "j", "team": "J", "score": 0}
    # No points and no durable rank to show: no row rather than an invented rank.
    assert "user_row" not in _tables(_report(4, scores, national_limit=3, user_team_id="j"))["national"]


def test_the_foot_row_moves_only_against_a_known_earlier_rank():
    last = _report(4, {"a": 90, "b": 80, "c": 70, "d": 60, "e": 50}, national_limit=3, user_team_id="e")
    this = _report(5, {"a": 90, "b": 80, "c": 70, "e": 65, "d": 60}, national_limit=3,
                   user_team_id="e", previous_story=last)
    assert _tables(this)["national"]["user_row"]["move"] == 1               # 5th -> 4th
    # Last week's story had no row for this team: unknown, so no mark (and never "new").
    this = _report(5, {"a": 90, "b": 80, "c": 70, "d": 60, "e": 50}, national_limit=3,
                   user_team_id="d", previous_story=last)
    foot = _tables(this)["national"]["user_row"]
    assert "move" not in foot and "new" not in foot
    # Last week in the table, this week below it: a fall.
    this = _report(5, {"a": 90, "b": 80, "d": 75, "e": 72, "c": 70}, national_limit=3,
                   user_team_id="c", previous_story=last)
    assert _tables(this)["national"]["user_row"]["move"] == -2              # 3rd -> 5th


def test_score_caption_is_stored_on_the_national_table_only():
    from BackEnd.utils.recruiting_report_news import RESULTS_SCORE_CAPTION, WEEKLY_SCORE_CAPTION

    story = _report(2, {"a": 50, "b": 40}, score_caption=WEEKLY_SCORE_CAPTION)
    tables = _tables(story)
    assert tables["national"]["caption"] == WEEKLY_SCORE_CAPTION
    assert "caption" not in tables["region"]
    assert "caption" not in _tables(_report(2, {"a": 50}))["national"]
    # The formula is hidden: the caption says what Score is for, never how it is built.
    assert WEEKLY_SCORE_CAPTION == "Class strength so far"
    assert RESULTS_SCORE_CAPTION == "Class strength"
    for caption in (WEEKLY_SCORE_CAPTION, RESULTS_SCORE_CAPTION):
        assert not any(word in caption.lower() for word in (
            "rating", "choice", "half", "quarter", "full", "signed", "lean", "adds", "%",
        ))
