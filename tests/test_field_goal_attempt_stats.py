from BackEnd.utils.field_goal_attempt import record_official_field_goal_attempt


class RecordingPlayer:
    def __init__(self):
        self.recorded = []

    def record_stat(self, stat):
        self.recorded.append(stat)


def test_clean_miss_counts_as_field_goal_attempt():
    player = RecordingPlayer()

    assert record_official_field_goal_attempt(
        player, made=False, shooting_foul=False
    )
    assert player.recorded == ["FGA"]


def test_missed_shooting_foul_does_not_count_as_attempt():
    player = RecordingPlayer()

    assert not record_official_field_goal_attempt(
        player, made=False, shooting_foul=True
    )
    assert player.recorded == []


def test_and_one_counts_as_make_and_attempt():
    player = RecordingPlayer()

    assert record_official_field_goal_attempt(
        player, made=True, shooting_foul=True
    )
    assert player.recorded == ["FGA"]


def test_missed_three_point_shooting_foul_counts_neither_attempt():
    player = RecordingPlayer()

    assert not record_official_field_goal_attempt(
        player, made=False, shooting_foul=True, is_three=True
    )
    assert player.recorded == []


def test_made_three_point_shooting_foul_counts_both_attempts():
    player = RecordingPlayer()

    assert record_official_field_goal_attempt(
        player, made=True, shooting_foul=True, is_three=True
    )
    assert player.recorded == ["FGA", "3PTA"]
