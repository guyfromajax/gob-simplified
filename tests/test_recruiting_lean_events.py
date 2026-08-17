"""Unit tests for diff_lean — the pure half of lean-movement reporting.

diff_lean is where the real bugs live: slot comparison, displacement detection,
telling moved_down from dropped_you, and rival_took_your_top firing only when the
user actually held #1. No DB, no fixtures beyond literal ladders.
"""

import pytest

from BackEnd.utils.recruiting_lean_events import (
    DISPLACED,
    DROPPED_YOU,
    GAINED_YOU,
    MOVED_DOWN,
    MOVED_UP,
    RIVAL_TOOK_YOUR_TOP,
    diff_lean,
    normalize_lean,
    rank_of,
    render_lean_event,
    summarize_kinds,
)

US = "user-team"
RIVAL = "rival-team"
OTHER = "other-team"
THIRD = "third-team"

NAMES = {US: "Kettle Falls", RIVAL: "Fairview", OTHER: "Brackenridge", THIRD: "Halloway"}


def name_of(team_id):
    return NAMES.get(team_id, "")


def ladder(one=None, two=None, three=None):
    return {"1": one, "2": two, "3": three}


def kinds(events):
    return [e["kind"] for e in events]


def only(events, kind):
    matching = [e for e in events if e["kind"] == kind]
    assert len(matching) == 1, f"expected exactly one {kind}, got {kinds(events)}"
    return matching[0]


# --------------------------------------------------------------------------
# No-change
# --------------------------------------------------------------------------

def test_identical_ladders_produce_nothing():
    same = ladder(US, RIVAL, OTHER)
    assert diff_lean(same, dict(same), user_team_id=US) == []


def test_empty_to_empty_produces_nothing():
    assert diff_lean(None, None, user_team_id=US) == []


def test_change_not_involving_user_produces_nothing():
    """The write-time filter: churn on a ladder the user is not on is not persisted."""
    old = ladder(RIVAL, OTHER, None)
    new = ladder(RIVAL, OTHER, THIRD)
    assert diff_lean(old, new, user_team_id=US) == []


def test_no_user_team_produces_nothing():
    old = ladder(RIVAL, None, None)
    new = ladder(RIVAL, OTHER, None)
    assert diff_lean(old, new, user_team_id=None) == []


# --------------------------------------------------------------------------
# The "open" sentinel is a vacancy, not a rival
# --------------------------------------------------------------------------

def test_open_sentinel_normalizes_to_vacancy():
    assert normalize_lean({"1": "open", "2": None, "3": ""}) == {"1": None, "2": None, "3": None}


def test_filling_an_open_slot_is_a_gain_not_a_displacement():
    """"open" must never be reported as a team knocked off the ladder."""
    old = ladder("open", None, None)
    new = ladder(US, None, None)
    events = diff_lean(old, new, user_team_id=US)
    assert kinds(events) == [GAINED_YOU]
    assert only(events, GAINED_YOU)["rank"] == 1


def test_rank_of_ignores_open_and_blank():
    assert rank_of(normalize_lean({"1": "open", "2": US, "3": ""}), US) == 2


# --------------------------------------------------------------------------
# gained_you
# --------------------------------------------------------------------------

def test_gained_you_on_empty_ladder():
    events = diff_lean(ladder(), ladder(US), user_team_id=US)
    event = only(events, GAINED_YOU)
    assert event["rank"] == 1
    assert event["prev_rank"] is None


def test_gained_you_at_third_behind_rivals():
    old = ladder(RIVAL, OTHER, None)
    new = ladder(RIVAL, OTHER, US)
    event = only(diff_lean(old, new, user_team_id=US), GAINED_YOU)
    assert event["rank"] == 3
    assert event["top_team_id"] == RIVAL


# --------------------------------------------------------------------------
# dropped_you — must be distinguishable from moved_down
# --------------------------------------------------------------------------

def test_dropped_you_when_pushed_off_the_bottom():
    old = ladder(RIVAL, OTHER, US)
    new = ladder(RIVAL, OTHER, THIRD)
    event = only(diff_lean(old, new, user_team_id=US), DROPPED_YOU)
    assert event["prev_rank"] == 3
    assert event["rank"] is None


def test_dropped_you_from_the_top_is_a_drop_not_a_rival_takeover():
    """Off the ladder entirely is dropped_you even though a rival now holds #1."""
    old = ladder(US, RIVAL, OTHER)
    new = ladder(RIVAL, OTHER, THIRD)
    events = diff_lean(old, new, user_team_id=US)
    assert DROPPED_YOU in kinds(events)
    assert RIVAL_TOOK_YOUR_TOP not in kinds(events)
    assert only(events, DROPPED_YOU)["top_team_id"] == RIVAL


def test_moved_down_is_not_reported_as_dropped():
    old = ladder(US, RIVAL, None)
    new = ladder(RIVAL, US, None)
    assert DROPPED_YOU not in kinds(diff_lean(old, new, user_team_id=US))


# --------------------------------------------------------------------------
# moved_up / moved_down
# --------------------------------------------------------------------------

@pytest.mark.parametrize("prev,now", [(3, 2), (3, 1), (2, 1)])
def test_moved_up_for_every_improving_pair(prev, now):
    old = {"1": None, "2": None, "3": None, str(prev): US}
    new = {"1": None, "2": None, "3": None, str(now): US}
    event = only(diff_lean(old, new, user_team_id=US), MOVED_UP)
    assert (event["prev_rank"], event["rank"]) == (prev, now)


def test_moved_down_from_two_to_three():
    old = ladder(RIVAL, US, OTHER)
    new = ladder(RIVAL, OTHER, US)
    event = only(diff_lean(old, new, user_team_id=US), MOVED_DOWN)
    assert (event["prev_rank"], event["rank"]) == (2, 3)


def test_moved_down_never_fires_from_rank_one():
    """Losing #1 is rival_took_your_top, which is strictly more informative."""
    old = ladder(US, RIVAL, None)
    new = ladder(RIVAL, US, None)
    assert MOVED_DOWN not in kinds(diff_lean(old, new, user_team_id=US))


# --------------------------------------------------------------------------
# rival_took_your_top — only when the user actually held #1
# --------------------------------------------------------------------------

def test_rival_took_your_top_when_bumped_from_first():
    old = ladder(US, RIVAL, None)
    new = ladder(RIVAL, US, None)
    event = only(diff_lean(old, new, user_team_id=US), RIVAL_TOOK_YOUR_TOP)
    assert event["rival_team_id"] == RIVAL
    assert (event["prev_rank"], event["rank"]) == (1, 2)


def test_rival_took_your_top_does_not_fire_when_user_was_second():
    """User was #2 and fell to #3; the #1 slot never belonged to them."""
    old = ladder(RIVAL, US, OTHER)
    new = ladder(RIVAL, OTHER, US)
    assert RIVAL_TOOK_YOUR_TOP not in kinds(diff_lean(old, new, user_team_id=US))


def test_rival_took_your_top_does_not_fire_when_user_keeps_first():
    old = ladder(US, RIVAL, OTHER)
    new = ladder(US, OTHER, RIVAL)
    assert RIVAL_TOOK_YOUR_TOP not in kinds(diff_lean(old, new, user_team_id=US))


def test_rival_took_your_top_does_not_fire_when_user_absent():
    old = ladder(RIVAL, None, None)
    new = ladder(OTHER, RIVAL, None)
    assert diff_lean(old, new, user_team_id=US) == []


# --------------------------------------------------------------------------
# displaced — a third party knocked off a ladder the user is on
# --------------------------------------------------------------------------

def test_displaced_third_party_while_user_holds_position():
    old = ladder(US, RIVAL, OTHER)
    new = ladder(US, RIVAL, THIRD)
    event = only(diff_lean(old, new, user_team_id=US), DISPLACED)
    assert event["displaced_team_id"] == OTHER
    assert event["rank"] == 1


def test_user_being_knocked_off_is_dropped_you_not_displaced():
    old = ladder(RIVAL, OTHER, US)
    new = ladder(RIVAL, OTHER, THIRD)
    assert DISPLACED not in kinds(diff_lean(old, new, user_team_id=US))


def test_displaced_not_reported_when_user_is_off_the_ladder():
    old = ladder(RIVAL, OTHER, None)
    new = ladder(RIVAL, THIRD, None)
    assert diff_lean(old, new, user_team_id=US) == []


# --------------------------------------------------------------------------
# displaced is suppressed when the SAME diff produced the user's own gain
# --------------------------------------------------------------------------

def test_gained_you_suppresses_a_paired_displacement():
    """Added at #3 while a rival falls off: the rival fell off BECAUSE we were added.

    Reporting both produced "added you at #3" followed by "dropped Lancaster — you're
    still #3", which claims continuity the player never had.
    """
    old = ladder(RIVAL, OTHER, THIRD)
    new = ladder(RIVAL, OTHER, US)
    events = diff_lean(old, new, user_team_id=US)
    assert kinds(events) == [GAINED_YOU]
    assert only(events, GAINED_YOU)["rank"] == 3


def test_moved_up_suppresses_a_paired_displacement():
    """Climbing #3 -> #1 pushes someone off; that is downstream of our own move."""
    old = ladder(RIVAL, OTHER, US)
    new = ladder(US, RIVAL, None)
    events = diff_lean(old, new, user_team_id=US)
    assert kinds(events) == [MOVED_UP]
    assert (only(events, MOVED_UP)["prev_rank"], only(events, MOVED_UP)["rank"]) == (3, 1)


def test_bystander_displacement_survives_without_user_movement():
    """A rival displacing another rival on a ladder we already sit on is real news."""
    old = ladder(US, RIVAL, OTHER)
    new = ladder(US, RIVAL, THIRD)
    events = diff_lean(old, new, user_team_id=US)
    assert kinds(events) == [DISPLACED]
    assert only(events, DISPLACED)["displaced_team_id"] == OTHER


def test_displacement_survives_alongside_a_user_slide():
    """Only gains suppress it — a slide is our own loss, not the cause of theirs."""
    old = ladder(RIVAL, US, OTHER)
    new = ladder(RIVAL, THIRD, US)
    events = diff_lean(old, new, user_team_id=US)
    assert set(kinds(events)) == {MOVED_DOWN, DISPLACED}
    assert only(events, DISPLACED)["displaced_team_id"] == OTHER


def test_displacement_survives_alongside_rival_took_your_top():
    old = ladder(US, RIVAL, OTHER)
    new = ladder(RIVAL, US, THIRD)
    events = diff_lean(old, new, user_team_id=US)
    assert set(kinds(events)) == {RIVAL_TOOK_YOUR_TOP, DISPLACED}


def test_suppression_does_not_change_wire_counts():
    """wire_counts already excludes displaced, so the feed changes but counts do not."""
    from BackEnd.utils.recruiting_lean_events import wire_counts
    paired = diff_lean(ladder(RIVAL, OTHER, THIRD), ladder(RIVAL, OTHER, US), user_team_id=US)
    assert wire_counts(paired) == {"moved": 1, "dropped": 0}


# --------------------------------------------------------------------------
# Purity + passthrough
# --------------------------------------------------------------------------

def test_diff_lean_does_not_mutate_its_arguments():
    old = ladder(US, RIVAL, None)
    new = ladder(RIVAL, US, None)
    old_copy, new_copy = dict(old), dict(new)
    diff_lean(old, new, user_team_id=US)
    assert old == old_copy and new == new_copy


def test_actor_and_cause_pass_through():
    events = diff_lean(
        ladder(), ladder(US), user_team_id=US,
        actor_team_id=US, cause={"type": "win", "opponent_team_id": RIVAL},
    )
    event = only(events, GAINED_YOU)
    assert event["actor_team_id"] == US
    assert event["cause"] == {"type": "win", "opponent_team_id": RIVAL}


def test_summarize_kinds_counts_per_kind():
    events = [{"kind": GAINED_YOU}, {"kind": DROPPED_YOU}, {"kind": GAINED_YOU}]
    assert summarize_kinds(events) == {GAINED_YOU: 2, DROPPED_YOU: 1}


# --------------------------------------------------------------------------
# Copy — sentences with causes
# --------------------------------------------------------------------------

def test_copy_reads_as_sentences_for_every_kind():
    recruit = "DeAndre Pope"
    cases = {
        GAINED_YOU: (
            diff_lean(ladder(RIVAL, OTHER, None), ladder(RIVAL, OTHER, US), user_team_id=US),
            "DeAndre Pope added you at #3",
        ),
        DROPPED_YOU: (
            diff_lean(ladder(US, OTHER, None), ladder(RIVAL, OTHER, None), user_team_id=US),
            "DeAndre Pope dropped you — Fairview moved to #1",
        ),
        MOVED_UP: (
            diff_lean(
                ladder(RIVAL, US, None), ladder(US, RIVAL, None), user_team_id=US,
                cause={"type": "win", "opponent_team_id": OTHER},
            ),
            "DeAndre Pope moved you to #1 — after the Brackenridge win",
        ),
        RIVAL_TOOK_YOUR_TOP: (
            diff_lean(ladder(US, RIVAL, None), ladder(RIVAL, US, None), user_team_id=US),
            "DeAndre Pope moved Fairview to #1 — you're now #2",
        ),
    }
    for kind, (events, expected) in cases.items():
        event = only(events, kind)
        assert render_lean_event(event, recruit, name_of) == expected


def test_copy_for_moved_down_and_displaced():
    down = only(
        diff_lean(ladder(RIVAL, US, OTHER), ladder(RIVAL, OTHER, US), user_team_id=US),
        MOVED_DOWN,
    )
    assert render_lean_event(down, "Marcus Bell", name_of) == "Marcus Bell moved you down to #3"

    displaced = only(
        diff_lean(ladder(US, RIVAL, OTHER), ladder(US, RIVAL, THIRD), user_team_id=US),
        DISPLACED,
    )
    assert (
        render_lean_event(displaced, "Andre Whitlock", name_of)
        == "Andre Whitlock dropped Brackenridge — you're still #1"
    )


def test_copy_drops_unknown_name_clauses_rather_than_rendering_blanks():
    event = only(diff_lean(ladder(), ladder(US), user_team_id=US), GAINED_YOU)
    line = render_lean_event(event, "Unknown Recruit", lambda _tid: "")
    assert line == "Unknown Recruit added you at #1"
    assert "—" not in line
