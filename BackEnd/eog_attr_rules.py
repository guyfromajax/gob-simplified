import random


def calculate_fb_opp_modifier_change(opponent_scouting: dict) -> int:
    """Calculate EOG fb_opp_modifier change from opponent fast-break performance."""
    opponent_fb_rate = opponent_scouting.get("fb_rate", 0)
    opponent_fb_entries = opponent_scouting.get("fb_entries", 0)
    if opponent_fb_rate < 20:
        return random.randint(0, 2)
    if opponent_fb_rate > 55 or opponent_fb_entries > 12:
        return random.randint(-3, -2)
    return random.randint(-1, 0)


def calculate_pt_opp_modifier_change(opponent_scouting: dict) -> int:
    """Calculate EOG pt_opp_modifier change from opponent press/trap performance."""
    opponent_pt_rate = opponent_scouting.get("pt_combined_rate", 0)
    opponent_pt_attempts = opponent_scouting.get("pt_total_attempts", 0)
    if opponent_pt_rate < 20:
        return random.randint(1, 2)
    if opponent_pt_rate > 50 or opponent_pt_attempts > 12:
        return random.randint(-3, -2)
    return random.randint(-2, -1)
