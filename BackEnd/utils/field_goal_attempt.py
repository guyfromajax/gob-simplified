"""Official field-goal attempt stat policy."""


def record_official_field_goal_attempt(
    player,
    *,
    made: bool,
    shooting_foul: bool,
    is_three: bool = False,
) -> bool:
    """Record FGA/3PTA unless a shooting foul accompanied a miss.

    A made basket counts as an attempt even when the shooter is fouled (and-one).
    """
    if shooting_foul and not made:
        return False
    player.record_stat("FGA")
    if is_three:
        player.record_stat("3PTA")
    return True
