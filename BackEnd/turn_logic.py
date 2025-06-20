from BackEnd.main import resolve_free_throw, resolve_fast_break, resolve_half_court_offense


def resolve_turn(game_state):
    off_team = game_state["offense_team"]
    # print(f"game_state: {game_state}")
    if game_state["offensive_state"] == "FREE_THROW":
        return resolve_free_throw(game_state)

    # Only allow fast break if last play ended with a defensive rebound or steal
    # ✅ Fast break check — only if previous result was a rebound or steal
    elif game_state["offensive_state"] == "FAST_BREAK":
        game_state["offensive_state"] = ""
        return resolve_fast_break(game_state)
    
    return resolve_half_court_offense(game_state)