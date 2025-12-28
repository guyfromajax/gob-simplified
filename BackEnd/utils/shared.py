import random
import logging
from BackEnd.constants import TURNOVER_CALC_DICT, POSITION_LIST, HCO_STRING_SPOTS


def format_height(value) -> str:
    """Convert total inches to a feet'inches" string.

    Accepts numbers or numeric strings; invalid or missing values yield
    an empty string.
    """
    if value in (None, ""):
        return ""
    try:
        inches = int(float(value))
    except (TypeError, ValueError):
        return ""
    feet, inches = divmod(inches, 12)
    return f"{feet}'{inches}\""

def weighted_random_from_dict(weight_dict: dict) -> str:
    if not weight_dict:
        raise ValueError("weighted_random_from_dict received an empty dict")

    total = sum(weight_dict.values())
    if total == 0:
        raise ValueError("All weights are zero in weighted_random_from_dict")

    rand_val = random.uniform(0, total)
    cumulative = 0
    for key, weight in weight_dict.items():
        cumulative += weight
        if rand_val <= cumulative:
            return key

    # fallback — should never hit if weights are valid
    return random.choice(list(weight_dict.keys()))


def apply_help_defense_if_triggered(game, playcall, is_three, defender, shot_score):
    """
    Determines if help defense is triggered and applies a penalty to the shot_score.
    Returns: updated_shot_score, help_defender (or None), help_defense_penalty
    """
    if is_three:
        return shot_score, None, 0

    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)

    base_help_chance_by_playcall = {
        "Attack": 0.70,
        "Inside": 0.20,
        "Set": 0.20,
        "Base": 0.30,
        "Freelance": 0.30,
        "Outside": 0.0
    }

    help_playcall = "Attack" if playcall == "Set" else playcall
    base_help_chance = base_help_chance_by_playcall.get(help_playcall, 0)

    # Adjust for aggression
    aggression = def_team.strategy_calls["aggression_call"]
    if aggression == "passive":
        base_help_chance += 0.20
    elif aggression == "aggressive":
        base_help_chance -= 0.20
    base_help_chance = max(0, min(1, base_help_chance))

    if random.random() >= base_help_chance:
        return shot_score, None, 0

    defender_pos = get_player_position(def_lineup, defender)

    possible_helpers = [pos for pos in def_lineup if pos != defender_pos]
    help_pos = random.choice(possible_helpers)
    help_defender = def_lineup[help_pos]
    help_attrs = help_defender.attributes

    if help_playcall == "Attack":
        help_score = (
            help_attrs["ID"] * 0.2 +
            help_attrs["OD"] * 0.2 +
            help_attrs["AG"] * 0.4 +
            help_attrs["IQ"] * 0.1 +
            help_attrs["CH"] * 0.1
        ) * random.randint(1, 6)
    else:
        help_score = (
            help_attrs["AG"] * 0.2 +
            help_attrs["IQ"] * 0.4 +
            help_attrs["CH"] * 0.4
        ) * random.randint(1, 6)

    penalty = help_score * 0.15
    return shot_score - penalty, help_defender, penalty

def get_fast_break_chance(game):
    """
    Determine fast break probability based on the OFFENSIVE team's aggression setting.
    Called after defensive rebounds or steals when the team is now on offense.
    """
    game_state = game.game_state
    off_team = game.offense_team  # Team that just got the rebound/steal (now on offense)
    level = off_team.strategy_settings.get("aggression", 2)
    return [0.0, 0.25, 0.5, 0.75, 1.0][level]

def get_time_elapsed(tempo_call):
    if tempo_call == "slow":
        return int(max(5, min(35, random.gauss(28, 6))))
    elif tempo_call == "normal":
        return int(max(5, min(35, random.gauss(22, 6))))
    elif tempo_call == "fast":
        return int(max(4, min(15, random.gauss(16, 4))))
    else:
        return int(max(5, min(35, random.gauss(22, 6))))  # Fallback

def resolve_offensive_rebound(game, rebounder):
    """Resolve an offensive rebound by choosing a putback or a kick-out.

    Returns an event dictionary describing the outcome.
    """

    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)

    # If no offensive rebounder is available, treat as a defensive rebound.
    if rebounder is None:
        logging.warning("resolve_offensive_rebound called with no rebounder; treating as defensive rebound")
        return {
            "event_type": "DEFENSIVE_REBOUND",
            "rebounderId": None,
            "timeElapsed": 0,
            "possession_flips": True,
        }

    if random.random() < 0.90:  # 90% putback attempt, 10% kickout
        attrs = rebounder.attributes
        shot_score = (
            attrs["SC"] * 0.6 +
            attrs["CH"] * 0.2 +
            attrs["IQ"] * 0.2
        ) * random.randint(1, 6)
        time_elapsed = random.randint(2, 5)

        defender_pos = random.choice(["C", "C", "C", "PF", "PF", "SF", "SF", "SG", "PG"])
        defender = def_team.lineup[defender_pos]
        defense_attrs = defender.attributes
        defense_penalty = (
            defense_attrs["ID"] * 0.6 +
            defense_attrs["ST"] * 0.2 +
            defense_attrs["IQ"] * 0.1 +
            defense_attrs["CH"] * 0.1
        ) * random.randint(1, 6) * 0.7
        shot_score -= defense_penalty

        # Track defensive attempt for putback
        defender.record_stat("DEF_A")

        made = shot_score >= off_team.team_attributes["shot_threshold"]
        
        rebounder.record_stat("FGA")
        # print(f"📦 PUTBACK FGA: Recorded FGA for {get_name_safe(rebounder)}")
        # print(f"📦 PUTBACK DEBUG: shot_score={shot_score}, threshold={off_team.team_attributes['shot_threshold']}, made={made}")

        event = {
            "event_type": "PUTBACK_ATTEMPT",
            "shooterId": getattr(rebounder, "player_id", None),
            "timeElapsed": time_elapsed,
            "result": "MAKE" if made else "MISS",
            "possession_flips": False,
        }

        if made:
            # print(f"📦 PUTBACK MAKE DEBUG: About to call apply_scoring for {get_name_safe(rebounder)}")
            # print(f"📦 PUTBACK MAKE DEBUG: rebounder object={rebounder}, player_id={getattr(rebounder, 'player_id', None)}")
            # print(f"📦 PUTBACK MAKE DEBUG: rebounder current PTS before scoring={rebounder.stats['game'].get('PTS', 0)}")
            apply_scoring(game, off_team, rebounder, 2, ["FGM"])
            # print(f"📦 PUTBACK MAKE DEBUG: rebounder PTS after scoring={rebounder.stats['game'].get('PTS', 0)}")
            # Putbacks are always from the paint
            rebounder.record_stat("PIP", amount=2)
            # print(f"📦 PUTBACK FGM: Recorded FGM for {get_name_safe(rebounder)}")
            # print(f"📦 PUTBACK PIP: Recorded 2 PIP for {get_name_safe(rebounder)}")
            event["points"] = 2
            event["possession_flips"] = True
        else:
            # Track defensive success for missed putback
            defender.record_stat("DEF_S")
            new_rebounder, new_team, new_stat = determine_rebounder(game)
            # Debug: Log when putback miss rebound stat is recorded
            logging.info(f"🏀 Putback Miss Rebound: {get_name_safe(new_rebounder)} credited with {new_stat} (putback miss)")
            new_rebounder.record_stat(new_stat)
            # DON'T flip possession here - let turn_manager handle it after the rebound
            # This ensures the shot animates to the correct basket before possession flips
            event["possession_flips"] = False
            
            # Determine ballSpot based on where the rebound HAPPENS, not where they'll attack next
            # For a putback, the rebound happens at the SAME basket as the putback attempt
            # The putback happened at the basket the original offensive team was attacking
            # Home team attacks away basket (x: 91), away team attacks home basket (x: 9)
            if new_stat == "DREB":
                # Defensive rebound - happens at the SAME basket where putback occurred
                # Putback happened at the basket off_team was attacking
                ballSpot = {"x": 91, "y": 25} if off_team == game.home_team else {"x": 9, "y": 25}
            else:
                # Offensive rebound - same team continues attacking same basket
                ballSpot = {"x": 91, "y": 25} if off_team == game.home_team else {"x": 9, "y": 25}
            
            # Add rebound information for frontend animation
            event["rebound"] = {
                "rebounderId": getattr(new_rebounder, "player_id", None),
                "rebounder_player_id": getattr(new_rebounder, "player_id", None),
                "rebound_type": new_stat,
                "ballSpot": ballSpot
            }

        return event

    # Kick out to PG
    pg = off_team.lineup.get("PG")
    duration = random.randint(1, 3)
    from_coords = getattr(rebounder, "coords", {"x": 25, "y": 50})
    to_coords = getattr(pg, "coords", {"x": 25, "y": 50}) if pg else {"x": 25, "y": 50}

    return {
        "event_type": "KICKOUT_RESET",
        "rebounderId": getattr(rebounder, "player_id", None),
        "pgId": getattr(pg, "player_id", None) if pg else None,
        "pass": {
            "fromCoords": from_coords,
            "toCoords": to_coords,
            "duration": duration,
        },
        "timeElapsed": duration,
    }

def calculate_screen_score(screen_attrs):
    """
    Calculates screen effectiveness score using weighted attributes:
    ST (0.5), AG (0.2), IQ (0.2), CH (0.1) scaled by RNG 1–6
    """
    base_score = (
        screen_attrs["ST"] * 0.5 +
        screen_attrs["AG"] * 0.2 +
        screen_attrs["IQ"] * 0.2 +
        screen_attrs["CH"] * 0.1
    )
    return base_score * random.randint(1, 6)

def choose_rebounder(rebounders, side):
    pool = rebounders.get(side, {})
    if not pool:
        logging.warning("choose_rebounder called with empty pool for %s", side)
        return None
    players = list(pool.keys())
    weights = list(pool.values())
    return random.choices(players, weights=weights, k=1)[0]

def generate_pass_chain(game, shooter_pos):
    
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    positions = ["PG", "SG", "SF", "PF", "C"]
    chain = ["PG"]  # Start with PG
    last_added = "PG"

    tempo = off_team.strategy_calls["tempo_call"]
    if tempo == "slow":
        num_passes = 3
    elif tempo == "fast":
        num_passes = 1
    else:
        num_passes = 2

    while len(chain) < num_passes:
        candidate = random.choice(positions)
        if candidate != last_added and candidate != shooter_pos:
            chain.append(candidate)
            last_added = candidate

    chain.append(shooter_pos)  # Shooter always last
    return chain

def clean_mongo_ids(doc: dict) -> dict:
    """
    Converts MongoDB ObjectId fields to strings so FastAPI can serialize them.
    """
    if "_id" in doc and hasattr(doc["_id"], "__str__"):
        doc["_id"] = str(doc["_id"])
    return doc

def get_name_safe(p):

    if isinstance(p, dict):
        return p.get("name", "")
    return getattr(p, "name", "")

def default_rebounder_dict():
    return {
        "offense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3},
        "defense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3}
    }

def determine_rebounder(game):
    
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    rebounder_dict = default_rebounder_dict()

    o_pos = choose_rebounder(rebounder_dict, "offense")
    d_pos = choose_rebounder(rebounder_dict, "defense")
    o_rebounder = off_lineup[o_pos]
    d_rebounder = def_lineup[d_pos]

    o_score = calculate_rebound_score(o_rebounder)
    d_score = calculate_rebound_score(d_rebounder)

    off_mod = off_team.team_attributes["rebound_modifier"]
    def_mod = def_team.team_attributes["rebound_modifier"]
    bias = def_mod - off_mod
    def_prob = min(0.95, max(0.55, 0.75 + bias))

    total_score = d_score + o_score
    d_weight = (d_score / total_score) if total_score else 0.5
    o_weight = 1 - d_weight
    d_weight += (def_prob - 0.5)
    d_weight = min(0.95, max(0.05, d_weight))
    o_weight = 1 - d_weight

    new_team = def_team if random.random() < d_weight else off_team
    new_rebounder = d_rebounder if new_team == def_team else o_rebounder
    new_stat = "DREB" if new_team == def_team else "OREB"
    # new_rebounder.record_stat(new_stat)
    # print(f"+1 rebound for {get_name_safe(new_rebounder)} / utils/shared - determine_rebounder")

    return new_rebounder, new_team, new_stat

def get_team_thresholds(game):
    
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)

    off_attr = off_team.team_attributes
    def_attr = def_team.team_attributes

    return {
        "turnover_modifier": off_attr.get("turnover_modifier", 10),
        "d_foul_modifier": def_attr.get("foul_modifier", 10),
        "o_foul_modifier": off_attr.get("foul_modifier", 10)
    }

def get_foul_and_turnover_positions(pass_count):
    return {
        "turnover": random.choice(TURNOVER_CALC_DICT[pass_count]),
        "o_foul": random.choice(POSITION_LIST),
        "d_foul": random.choice(POSITION_LIST)
    }

def get_player_position(team_lineup, player_obj):
    return next((pos for pos, p in team_lineup.items() if p == player_obj), None)

def get_player_by_pos(pos, offense_lineup, defense_lineup):
    if pos in offense_lineup:
        return offense_lineup[pos]
    elif pos in defense_lineup:
        return defense_lineup[pos]
    else:
        return None


def get_quarter_index_from_game(game):
    return game.game_state["quarter"] - 1

def scale_score_to_100(raw_score):
    """
    Universal helper function to scale raw scores to 1-100 range where midpoint = 50.
    
    Assumes consistent pattern:
    - Attributes range: 1-100 (midpoint = 50)
    - Die roll: 1-6 (midpoint = 3.5)
    - Attribute weights sum to 1.0
    - Raw midpoint: 50 * 3.5 = 175
    - Raw range: 1 (min) to 600 (max)
    
    Scaling formula: ((raw - 175) / 425) * 50 + 50
    - Maps raw 175 → scaled 50 (midpoint)
    - Maps raw 1 → scaled ~29.5 (minimum)
    - Maps raw 600 → scaled 100 (maximum)
    
    Args:
        raw_score: Raw score value (typically 1-600)
    
    Returns:
        int: Scaled score (1-100, with midpoint = 50)
    """
    return int(round(((raw_score - 175) / 425) * 50 + 50))

def calculate_rebound_score(player):
    attr = player.attributes
    return (attr["RB"] * 0.5 + attr["ST"] * 0.3 + attr["IQ"] * 0.2) * random.randint(1, 6)

def calculate_outlet_pass_score(outlet_passer):
    """
    Calculate outlet pass score based on outlet passer's attributes.
    Score is scaled to 1-100 range where midpoint (average attributes + average die) = 50.
    
    Raw formula: (PS * 0.6 + ST * 0.2 + IQ * 0.2) * random(1-6)
    - Attributes range: 1-100 (midpoint = 50)
    - Die roll: 1-6 (midpoint = 3.5)
    - Raw midpoint: (50 * 0.6 + 50 * 0.2 + 50 * 0.2) * 3.5 = 175
    - Raw range: 1 (min) to 600 (max)
    
    Scaling formula: ((raw - 175) / 425) * 50 + 50
    - Maps raw 175 → scaled 50
    - Maps raw 1 → scaled ~29.5
    - Maps raw 600 → scaled 100
    
    Args:
        outlet_passer: Player object making the outlet pass
    
    Returns:
        int: Scaled outlet pass score (1-100, with midpoint = 50)
    """
    attr = outlet_passer.attributes
    # Calculate raw score
    raw_score = (attr["PS"] * 0.6 + attr["ST"] * 0.2 + attr["IQ"] * 0.2) * random.randint(1, 6)
    
    # Scale to 1-100 using universal scaling function
    return scale_score_to_100(raw_score)

def resolve_steal_attempt(offense_value, defense_value, soft_steal, hard_steal, soft_foul, hard_foul):
    """
    Resolve outcome of a steal attempt.
    
    Args:
        offense_value: Ball handler's protection value (bh_score)
        defense_value: Defender's steal attempt value (pressure)
        soft_steal: Soft steal threshold (default: -100)
        hard_steal: Hard steal threshold (default: -200)
        soft_foul: Soft foul threshold (default: 100)
        hard_foul: Hard foul threshold (default: 200)
    
    Returns:
        One of:
        - "STEAL" - Steal successful, possession changes
        - "D_FOUL" - Defensive foul on steal attempt, offense retains possession
        - "NO_EVENT" - No event, play continues normally
    """
    import random
    from BackEnd.constants import SOFT_PROB
    
    delta = offense_value - defense_value  # negative => defense won the contest
    
    # 1) Steal outcomes (defense wins)
    if delta <= hard_steal:
        return "STEAL"
    if delta <= soft_steal:
        # Soft steal band: partial probability to calibrate to baseline rates
        if random.random() < SOFT_PROB:
            return "STEAL"
    
    # 2) Defensive foul outcomes (offense wins / defender reaches)
    if delta >= hard_foul:
        return "D_FOUL"
    if delta >= soft_foul:
        if random.random() < SOFT_PROB:
            return "D_FOUL"
    
    # 3) Otherwise nothing happens; possession continues
    return "NO_EVENT"


def apply_scoring(game, team, player, points, stats):
    """Record player scoring stats and update team points.

    Parameters:
        game: GameManager object
        team: TeamManager object receiving the points
        player: Player object recording the stats
        points: int number of points scored
        stats: iterable of stat strings to record on the player
    """
    for stat in stats:
        player.record_stat(stat)
    
    record_team_points(game, team, points)

def record_team_points(game, team, points):
    """
    Updates total game score and per-quarter score for the given team.
    
    Parameters:
    - game: GameManager object
    - team: TeamManager object (e.g., game.offense_team)
    - points: int, number of points to add
    """
    game.score[team.name] += points
    quarter_index = game.game_state["quarter"] - 1
    team.points_by_quarter[quarter_index] += points

def unpack_game_context(game):
    
    return (
        game.game_state,
        game.offense_team,
        game.defense_team,
        game.offense_team.lineup,
        game.defense_team.lineup,
    )

def summarize_game_state(game, exclude_animations=True):
    """
    Summarize game state for persistence/API responses.
    Uses nested team structure and always excludes animations from saves.
    
    Args:
        game: GameManager instance
        exclude_animations: Always True for saves (animations only for real-time frontend)
    """
    
    def _collect_player_ids(obj, acc):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("playerId", "player_id"):
                    if isinstance(v, list):
                        acc.update(str(pid) for pid in v if pid is not None)
                    elif v is not None:
                        acc.add(str(v))
                else:
                    _collect_player_ids(v, acc)
        elif isinstance(obj, list):
            for item in obj:
                _collect_player_ids(item, acc)

    referenced_ids = set()
    _collect_player_ids(game.turns, referenced_ids)

    players = []
    for team_key, team_obj in [("home", game.home_team), ("away", game.away_team)]:
        for pos, player in team_obj.lineup.items():
            coords = getattr(player, "coords", None) or {"x": 0, "y": 0}
            players.append({
                "playerId": player.player_id,
                "name": getattr(player, "name", None) or f"{getattr(player, 'first_name', '')} {getattr(player, 'last_name', '')}".strip(),
                "team": team_key,
                "team_id": team_obj.team_id,
                "pos": pos,
                "jersey": player.jersey,
                "photo": getattr(player, "photo", None),  # Player headshot image
                "primary_color": getattr(team_obj, "primary_color", "#000000"),
                "secondary_color": getattr(team_obj, "secondary_color", "#ffffff"),
                "x": coords.get("x", 0),
                "y": coords.get("y", 0),
                "stats": player.stats.get("game", {}),  # Include game stats for persistence
                "attributes": {
                    "EM": player.attributes.get("EM", 0),
                    "CH": player.attributes.get("CH", 0),
                    "MO": player.attributes.get("MO", 0),
                    "NG": player.attributes.get("NG", 1.0)
                }
            })

    # Only include non-lineup players if we're including animations (full turn data)
    # For turn-by-turn mode, only current lineup is needed (turns are empty or stale)
    # Check both exclude_animations flag AND if there are actual NEW turns to reference
    has_fresh_turns = len(game.turns) > 0 and not exclude_animations
    if has_fresh_turns:
        included_ids = {p["playerId"] for p in players}
        for pid in referenced_ids:
            if pid in included_ids:
                continue
            player_obj = game.home_team.get_player_by_id(pid) or game.away_team.get_player_by_id(pid)
            if player_obj:
                team_key = "home" if game.home_team.get_player_by_id(pid) else "away"
                team_obj = game.home_team if team_key == "home" else game.away_team
                coords = getattr(player_obj, "coords", None) or {"x": 0, "y": 0}
                players.append({
                    "playerId": player_obj.player_id,
                    "name": getattr(player_obj, "name", None) or f"{getattr(player_obj, 'first_name', '')} {getattr(player_obj, 'last_name', '')}".strip(),
                    "team": team_key,
                    "team_id": team_obj.team_id,
                    "pos": getattr(player_obj, "position", None) or getattr(player_obj, "pos", None),
                    "jersey": player_obj.jersey,
                    "photo": getattr(player_obj, "photo", None),  # Player headshot image
                    "primary_color": getattr(team_obj, "primary_color", "#000000"),
                    "secondary_color": getattr(team_obj, "secondary_color", "#ffffff"),
                    "x": coords.get("x", 0),
                    "y": coords.get("y", 0),
                    "stats": player_obj.stats.get("game", {}),  # Include game stats for persistence
                    "attributes": {
                        "EM": player_obj.attributes.get("EM", 0),
                        "CH": player_obj.attributes.get("CH", 0),
                        "MO": player_obj.attributes.get("MO", 0),
                        "NG": player_obj.attributes.get("NG", 1.0)
                    }
                })
            else:
                players.append({
                    "playerId": pid,
                    "name": "",
                    "team": None,
                    "team_id": None,
                    "pos": None,
                    "jersey": None,
                    "primary_color": "#000000",
                    "secondary_color": "#ffffff",
                    "x": 0,
                    "y": 0,
                })
            included_ids.add(pid)

    team_info = {
        "home": {
            "team_id": game.home_team.team_id,
            "player_ids": [p["playerId"] for p in players if p["team"] == "home"],
            "primary_color": game.home_team.primary_color,
            "secondary_color": game.home_team.secondary_color,
        },
        "away": {
            "team_id": game.away_team.team_id,
            "player_ids": [p["playerId"] for p in players if p["team"] == "away"],
            "primary_color": game.away_team.primary_color,
            "secondary_color": game.away_team.secondary_color,
        },
    }
    # print(f"Home team primary color: {game.home_team.primary_color}")
    # print(f"Home team secondary color: {game.home_team.secondary_color}")
    # print(f"Away team primary color: {game.away_team.primary_color}")
    # print(f"Away team secondary color: {game.away_team.secondary_color}")

    home_team_obj = {
        "name": game.home_team.name,
        "team_id": game.home_team.team_id,
        "score": game.score.get(game.home_team.name, 0),
        "colors": {
            "primary_color": game.home_team.primary_color,
            "secondary_color": game.home_team.secondary_color,
        },
    }

    away_team_obj = {
        "name": game.away_team.name,
        "team_id": game.away_team.team_id,
        "score": game.score.get(game.away_team.name, 0),
        "colors": {
            "primary_color": game.away_team.primary_color,
            "secondary_color": game.away_team.secondary_color,
        },
    }

    cumulative_box = game.get_box_score()

    # ✅ FIX: Use in-memory plays from team objects (they have updated game_stats)
    # Instead of creating fresh copies from database, use the plays that were updated during gameplay
    # This preserves game_stats (times_run, successes, player_points) that were tracked during the game
    from copy import deepcopy
    
    # Get plays from home team (in-memory, with updated game_stats)
    home_plays = deepcopy(getattr(game.home_team, 'plays', {}))
    # Get plays from away team (in-memory, with updated game_stats)
    away_plays = deepcopy(getattr(game.away_team, 'plays', {}))
    
    # If teams don't have plays loaded, fallback to database (shouldn't happen in normal flow)
    if not home_plays and not away_plays:
        try:
            from BackEnd.api.gameplan_routes import populate_team_plays
            populated_plays = populate_team_plays()
            home_plays = populated_plays.copy()
            away_plays = populated_plays.copy()
        except Exception as e:
            print(f"🚨 Error in populate_team_plays: {e}")
            home_plays = {}
            away_plays = {}
    
    # ✅ PRESERVE playbook_settings from database when saving game state
    # This ensures slot_assignments and other playbook settings persist across timeout/quarter saves
    home_playbook_settings = {}
    away_playbook_settings = {}
    home_actual_team_id = None
    away_actual_team_id = None
    
    if exclude_animations and hasattr(game, 'game_id') and game.game_id:
        # Only preserve playbook_settings when saving to database (exclude_animations=True)
        # and game_id exists (game has been initialized)
        try:
            from BackEnd.db import games_collection, db
            from bson import ObjectId
            
            # Try both UUID string and ObjectId formats for game_id
            saved_game = games_collection.find_one({"_id": game.game_id})
            if not saved_game:
                try:
                    saved_game = games_collection.find_one({"_id": ObjectId(game.game_id)})
                except:
                    pass
            
            if saved_game:
                teams = saved_game.get("teams", {})
                
                # ✅ Find teams by matching team name (most reliable method)
                # Iterate through all teams in document and match by name
                for tid in teams.keys():
                    team_data = teams.get(tid, {})
                    # Try to get team name from various sources
                    team_name = None
                    try:
                        # Try to get team name from teams collection
                        team_doc = db.teams.find_one({"_id": ObjectId(tid)})
                        if not team_doc:
                            team_doc = db.teams.find_one({"team_id": tid})
                        if team_doc:
                            team_name = team_doc.get("name")
                    except:
                        pass
                    
                    # Match by team name
                    if team_name == game.home_team.name:
                        home_actual_team_id = tid
                    if team_name == game.away_team.name:
                        away_actual_team_id = tid
                
                # Fallback: try direct lookup with team_id (in case key is team_id string)
                if not home_actual_team_id and game.home_team.team_id in teams:
                    home_actual_team_id = game.home_team.team_id
                if not away_actual_team_id and game.away_team.team_id in teams:
                    away_actual_team_id = game.away_team.team_id
                
                # Get playbook_settings for each team (if they exist)
                if home_actual_team_id:
                    home_team_data = teams.get(home_actual_team_id, {})
                    home_playbook_settings = home_team_data.get("playbook_settings", {})
                if away_actual_team_id:
                    away_team_data = teams.get(away_actual_team_id, {})
                    away_playbook_settings = away_team_data.get("playbook_settings", {})
                
                if home_playbook_settings or away_playbook_settings:
                    logging.info(f"✅ Preserved playbook_settings: home={bool(home_playbook_settings)} (key={home_actual_team_id}), away={bool(away_playbook_settings)} (key={away_actual_team_id})")
                else:
                    logging.warning(f"⚠️ No playbook_settings found in database: teams keys={list(teams.keys())[:3]}, home_team.name={game.home_team.name}, away_team.name={game.away_team.name}")
        except Exception as e:
            # If we can't load playbook_settings, continue without them (non-critical)
            logging.warning(f"⚠️ Could not preserve playbook_settings from database: {e}", exc_info=True)
    
    # Create team objects with all necessary data for game state persistence
    # ✅ Use resolved team_id keys if we found them, otherwise use game.home_team.team_id
    # This ensures we use the same key format that was used when saving playbook_settings
    home_key = home_actual_team_id if home_actual_team_id else game.home_team.team_id
    away_key = away_actual_team_id if away_actual_team_id else game.away_team.team_id
    
    teams_obj = {
        home_key: {
            "strategy_settings": getattr(game.home_team, 'strategy_settings', {}),
            "strategy_calls": getattr(game.home_team, 'strategy_calls', {}),  # ✅ SS&S: Persist playcall overrides
            "plays": home_plays,  # ✅ FIX: Use in-memory plays with updated game_stats
            "attributes": getattr(game.home_team, 'team_attributes', {}),
            "scouting": getattr(game.home_team, 'scouting_data', {}),
            "playbook_settings": home_playbook_settings  # ✅ Preserve from database
        },
        away_key: {
            "strategy_settings": getattr(game.away_team, 'strategy_settings', {}),
            "strategy_calls": getattr(game.away_team, 'strategy_calls', {}),  # ✅ SS&S: Persist playcall overrides
            "plays": away_plays,  # ✅ FIX: Use in-memory plays with updated game_stats
            "attributes": getattr(game.away_team, 'team_attributes', {}),
            "scouting": getattr(game.away_team, 'scouting_data', {}),
            "playbook_settings": away_playbook_settings  # ✅ Preserve from database
        }
    }
    
    # print(f"🔍 DEBUG: Created teams object with keys: {list(teams_obj.keys())}")
    # print(f"🔍 DEBUG: Home team plays: {len(teams_obj[game.home_team.team_id]['plays'])}")
    # print(f"🔍 DEBUG: Away team plays: {len(teams_obj[game.away_team.team_id]['plays'])}")

    # Process turns: exclude animations for database persistence, keep for real-time frontend
    from copy import deepcopy
    
    # For database saves, don't store turns at all (only need game state metadata)
    # Turns are only needed for real-time frontend display, not for persistence
    if exclude_animations:
        turns = []  # Empty array - don't save turns to database (prevents document size issues)
    else:
        turns = deepcopy(game.turns)  # Keep full turns with animations for real-time frontend
    
    # Get cumulative box scores
    cumulative_box = game.get_box_score()

    # Build nested team objects with all team-related data
    home_team_data = {
        "name": game.home_team.name,
        "team_id": game.home_team.team_id,
        "mascot": game.home_team.mascot,
        "colors": {
            "primary_color": game.home_team.primary_color,
            "secondary_color": game.home_team.secondary_color,
        },
        "score": game.score.get(game.home_team.name, 0),
        "points_by_quarter": game.game_state["points_by_quarter"].get(game.home_team.name, [0, 0, 0, 0]),
        "team_fouls": game.home_team.team_fouls,
        "timeouts": getattr(game.home_team, 'timeouts', 4),  # Default to 4 if not set (backward compatibility)
        
        # Team attributes (needed for S3 tab in Team Box Score)
        "attributes": getattr(game.home_team, 'team_attributes', {}),
        
        # ✅ Removed redundant fields (already in teams object):
        # - plays (was 75KB with embedded skeletons!)
        # - strategy_settings
        # - scouting
        # Frontend should read from teams object instead
        
        # Player stats (for frontend display)
        "box_score": cumulative_box.get(game.home_team.name, {}),
        
        # Team totals (aggregated from players)
        "totals": game.team_totals.get(game.home_team.name, {})
    }
    
    away_team_data = {
        "name": game.away_team.name,
        "team_id": game.away_team.team_id,
        "mascot": game.away_team.mascot,
        "colors": {
            "primary_color": game.away_team.primary_color,
            "secondary_color": game.away_team.secondary_color,
        },
        "score": game.score.get(game.away_team.name, 0),
        "points_by_quarter": game.game_state["points_by_quarter"].get(game.away_team.name, [0, 0, 0, 0]),
        "team_fouls": game.away_team.team_fouls,
        "timeouts": getattr(game.away_team, 'timeouts', 4),  # Default to 4 if not set (backward compatibility)
        
        # Team attributes (needed for S3 tab in Team Box Score)
        "attributes": getattr(game.away_team, 'team_attributes', {}),
        
        # ✅ Removed redundant fields (already in teams object):
        # - plays (was 75KB with embedded skeletons!)
        # - strategy_settings
        # - scouting
        # Frontend should read from teams object instead
        
        # Player stats (for frontend display)
        "box_score": cumulative_box.get(game.away_team.name, {}),
        
        # Team totals (aggregated from players)
        "totals": game.team_totals.get(game.away_team.name, {})
    }

    # Streamlined structure with nested teams
    return {
        # Game metadata
        "game_id": str(game.game_id) if hasattr(game, 'game_id') else None,
        "quarter": game.quarter,
        "is_final": game.quarter > 4 and game.score.get(game.home_team.name, 0) != game.score.get(game.away_team.name, 0),
        "opening_tip_winner": game.game_state.get("opening_tip_winner"),
        "game_stats_initialized": game.game_state.get("game_stats_initialized", False),  # Preserve stats initialization flag
        "user_team_side": game.game_state.get("user_team_side"),  # ✅ SS&S: Save user_team_side for persistent override checking
        "timeout_next_play_type": game.game_state.get("timeout_next_play_type"),  # ✅ TIMEOUT: Save next_play_type for resume
        "timeout_offense_team_id": game.game_state.get("timeout_offense_team_id"),  # ✅ TIMEOUT: Save possession team for resume
        "clock": game.game_state.get("clock", "8:00"),  # ✅ TIMEOUT: Save clock for resume (same as quarter breaks)
        "time_remaining": game.game_state.get("time_remaining", 480),  # ✅ TIMEOUT: Save time_remaining for resume (same as quarter breaks)
        
        # Top-level score map for backward compatibility (some code expects summary["score"])
        "score": {
            game.home_team.name: home_team_data["score"],
            game.away_team.name: away_team_data["score"]
        },
        
        # Top-level team IDs for frontend compatibility (used by animation system)
        "home_team_id": game.home_team.team_id,
        "away_team_id": game.away_team.team_id,
        
        # Nested team data (all team info in one place)
        "home_team": home_team_data,
        "away_team": away_team_data,
        
        # Teams object (by team_id) for game state persistence with strategy, plays, attributes, scouting
        "teams": teams_obj,
        
        # Game data
        "turns": turns,  # Animations excluded for database saves
        "text_log": game.text_log,
        
        # Players array (for frontend rendering and stats persistence)
        "players": players,
    }

def check_defensive_foul(self, defender, is_three):
    """
    Returns True if a defensive foul is committed during a shot attempt.
    """
    if not defender:
        return False  # No defender, no foul

    attrs = defender.attributes
    discipline = attrs.get("ND", 5)  # ND = "No Dumb Fouls"

    # Base foul rate: higher on 3pt shots, but reduced by discipline
    base_foul_chance = 0.06 if is_three else 0.045
    foul_chance = max(0.01, base_foul_chance - (discipline * 0.0045))

    return random.random() < foul_chance

def calculate_gravity_score(attrs):
    return (
        attrs["SH"] * 0.3 +
        attrs["SC"] * 0.3 +
        attrs["IQ"] * 0.4
    )


def calculate_ball_handling_score(player):
    """
    Calculate ball handling score for an offensive player.
    Used for turnover and steal attempt calculations.
    
    Formula: (BH * 0.5 + AG * 0.2 + IQ * 0.2 + CH * 0.1) * random(1, 6)
    
    Args:
        player: Player object with attributes
    
    Returns:
        int: Ball handling score
    """
    attrs = player.attributes
    return (
        attrs["BH"] * 0.5 +
        attrs["AG"] * 0.2 +
        attrs["IQ"] * 0.2 +
        attrs["CH"] * 0.1
    ) * random.randint(1, 6)


def calculate_defender_pressure_score(defender, defense_call):
    """
    Calculate defensive pressure score for a defender.
    Used for turnover and steal attempt calculations.
    
    Formula: (OD * 0.3 + AG * 0.3 + IQ * 0.2 + CH * 0.2) * random(1, 6)
    Zone defense modifier: pressure *= 0.9
    
    Args:
        defender: Defender player object with attributes
        defense_call: Defense playcall string (e.g., "Man", "2-3 Zone")
    
    Returns:
        int: Defender pressure score
    """
    from BackEnd.utils.defense_utils import is_zone_defense
    
    def_attrs = defender.attributes
    pressure = (
        def_attrs["OD"] * 0.3 +
        def_attrs["AG"] * 0.3 +
        def_attrs["IQ"] * 0.2 +
        def_attrs["CH"] * 0.2
    ) * random.randint(1, 6)
    
    if is_zone_defense(defense_call):
        pressure *= 0.9
    
    return int(pressure)

def get_away_player_coords(playerCoords):
        
        """
        Gets individual player coordinates if the away team has the ball.
        Flips coordinates around the center of the court (x=50).
        """

        ySpot = playerCoords["y"]    
        coordsX = playerCoords["x"]
        # Flip around center: if x=30 (home side), flip to x=70 (away side)
        # Formula: new_x = 100 - old_x
        xSpot = 100 - coordsX
        playerCoords = {"x": xSpot, "y": ySpot}

        return playerCoords

def getAwayTeamCoords(coordsDict):
       for position, coords in coordsDict.items():
           ySpot = coords["y"]
           coordsX = coords["x"]
           # Flip around center: if x=30 (home side), flip to x=70 (away side)
           # Formula: new_x = 100 - old_x
           xSpot = 100 - coordsX
           coordsDict[position] = {"x": xSpot, "y": ySpot}
       return coordsDict

def update_player_coords_from_animations(game, animations):
    for anim in animations:
        pid = anim["playerId"]
        for team in [game.home_team, game.away_team]:
            for player in team.lineup.values():
                if player is not None and hasattr(player, 'player_id') and player.player_id == pid:
                    player.coords = anim["end"]

def serialize_lineup(lineup_dict):
    return {
        pos: player.player_id if hasattr(player, 'player_id') else player
        for pos, player in lineup_dict.items()
    }


