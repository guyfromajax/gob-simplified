"""
New Training Execution System - Implements logic from training_execution.md brief

This module implements the new training execution system with:
- Pre-training conditions
- New training point application logic
- Clamps and validation
- Training report generation
"""

import random
from typing import List, Dict, Tuple, Optional
from BackEnd.constants import ALL_ATTRS


def execute_training(
    players: List[dict],
    team: dict,
    allocations: Dict,
    coaching_focus: Optional[str] = None
) -> Tuple[List[dict], dict, Dict]:
    """
    Main training execution function.
    
    This function:
    1. Stores original baselines (before any changes)
    2. Applies pre-training conditions
    3. Applies training points
    4. Clamps all values
    5. Returns training report data with changes from original baselines
    
    Args:
        players: List of player dicts with attributes
        team: Team dict with team attributes
        allocations: Training point allocations (frontend format)
        coaching_focus: Optional coaching focus selection
    
    Returns:
        Tuple of (updated_players, updated_team, training_report_data)
    """
    # Store original baselines BEFORE any changes
    original_player_baselines = {
        p["_id"]: {attr: p.get("attributes", {}).get(f"anchor_{attr}", 0) 
                   for attr in TRAINABLE_PLAYER_ATTRS}
        for p in players
    }
    original_team_baseline = {k: team.get(k, 0) for k in TEAM_ATTR_CLAMPS.keys()}
    
    # Step 1: Apply pre-training conditions
    players, team = apply_pre_training_conditions(players, team)
    
    # Step 2: Apply training points (pass original baselines for report calculation)
    players, team, training_report = apply_training_points(
        players, team, allocations, coaching_focus,
        original_baselines=original_player_baselines,
        original_team_baseline=original_team_baseline
    )
    
    return players, team, training_report

# Player attributes excluding EM, MO, NG
TRAINABLE_PLAYER_ATTRS = [attr for attr in ALL_ATTRS if attr not in ["EM", "MO", "NG"]]

# Team attribute clamps (lower, upper)
TEAM_ATTR_CLAMPS = {
    "shot_threshold": (-200, 200),
    "turnover_modifier": (-10, 10),
    "foul_modifier": (-10, 10),
    "rebound_modifier": (0.8, 1.2),
    "momentum_score": (-10, 10),
    "offensive_efficiency": (-10, 10),
    "team_chemistry": (7, 25),
    "defensive_efficiency": (-10, 10),
    "fb_efficiency": (-10, 10),
    "pt_efficiency": (-10, 10),
    "fb_opp_modifier": (-10, 10),
    "pt_opp_modifier": (-10, 10),
}

# Player attribute clamps (lower, upper)
PLAYER_ATTR_CLAMP = (1, None)  # Min 1, no max


def apply_pre_training_conditions(players: List[dict], team: dict) -> Tuple[List[dict], dict]:
    """
    Apply pre-training conditions to players and team.
    
    Pre-training conditions:
    - Player attributes (excluding EM, MO, NG): += randint(-2, 0) for each player/attribute
    - Rebound modifier: += random choice [-0.1, 0]
    - Shot threshold: += random.randint(0, 15)
    - Team chemistry: N/A (no change)
    - All other team attributes: += random choice [-2, -1, 0]
    
    Args:
        players: List of player dicts with attributes
        team: Team dict with team attributes
    
    Returns:
        Tuple of (updated_players, updated_team)
    """
    # Apply to each player
    for player in players:
        attrs = player.get("attributes", {})
        for attr in TRAINABLE_PLAYER_ATTRS:
            anchor_key = f"anchor_{attr}"
            if anchor_key in attrs:
                # Apply random decrease: randint(-2, 0) inclusive
                decrease = random.randint(-2, 0)
                attrs[anchor_key] = max(PLAYER_ATTR_CLAMP[0], attrs[anchor_key] + decrease)
                # Also update base attribute
                attrs[attr] = attrs[anchor_key]
    
    # Apply to team attributes
    # Rebound modifier: random choice [-0.1, 0]
    if "rebound_modifier" in team:
        team["rebound_modifier"] += random.choice([-0.1, 0])
        # Clamp
        team["rebound_modifier"] = max(
            TEAM_ATTR_CLAMPS["rebound_modifier"][0],
            min(TEAM_ATTR_CLAMPS["rebound_modifier"][1], team["rebound_modifier"])
        )
    
    # Shot threshold: += random.randint(0, 15)
    if "shot_threshold" in team:
        team["shot_threshold"] += random.randint(0, 15)
        # Clamp
        team["shot_threshold"] = max(
            TEAM_ATTR_CLAMPS["shot_threshold"][0],
            min(TEAM_ATTR_CLAMPS["shot_threshold"][1], team["shot_threshold"])
        )
    
    # All other team attributes (excluding shot_threshold, rebound_modifier, team_chemistry)
    exclude_attrs = ["shot_threshold", "rebound_modifier", "team_chemistry"]
    for attr_name, (lower, upper) in TEAM_ATTR_CLAMPS.items():
        if attr_name in exclude_attrs:
            continue
        if attr_name in team:
            # Apply random decrease: random choice [-2, -1, 0]
            decrease = random.choice([-2, -1, 0])
            team[attr_name] += decrease
            # Clamp
            team[attr_name] = max(lower, min(upper, team[attr_name]))
    
    return players, team


def apply_training_points(
    players: List[dict],
    team: dict,
    allocations: Dict[str, Dict],
    coaching_focus: Optional[str] = None,
    original_baselines: Optional[Dict] = None,
    original_team_baseline: Optional[Dict] = None
) -> Tuple[List[dict], dict, Dict]:
    """
    Apply training points to players and team based on allocations.
    
    Args:
        players: List of player dicts with attributes (already have pre-training conditions applied)
        team: Team dict with team attributes (already have pre-training conditions applied)
        allocations: Dict mapping category to allocation data
        coaching_focus: Optional coaching focus (archetype-suboption format)
        original_baselines: Optional dict of original player baselines (before pre-training conditions)
        original_team_baseline: Optional dict of original team baseline (before pre-training conditions)
    
    Returns:
        Tuple of (updated_players, updated_team, training_report_data)
    """
    # Use provided baselines or calculate from current state
    if original_baselines is None:
        player_baselines = {
            p["_id"]: {attr: p.get("attributes", {}).get(f"anchor_{attr}", 0) 
                       for attr in TRAINABLE_PLAYER_ATTRS}
            for p in players
        }
    else:
        player_baselines = original_baselines
    
    if original_team_baseline is None:
        team_baseline = {k: team.get(k, 0) for k in TEAM_ATTR_CLAMPS.keys()}
    else:
        team_baseline = original_team_baseline
    
    # Parse coaching focus (format: "archetype" or "archetype-suboption")
    archetype = None
    sub_option = None
    if coaching_focus:
        parts = coaching_focus.split("-", 1)
        archetype = parts[0]
        if len(parts) > 1:
            sub_option = parts[1]
    
    # Normalize allocations from frontend structure to flat structure
    # Frontend sends: {player_drills: {offense: {inside: 3, outside: 2}, ...}, team_drills: {...}, general: {...}}
    # We need to flatten this to: {offensive_drills: {inside: 3, outside: 2}, ...}
    normalized_allocations = _normalize_allocations(allocations)
    
    # Map training categories to player attributes (from training_execution.md)
    player_category_map = {
        "offensive_drills": {
            "inside": ["SC"],      # Inside Offense: SC
            "outside": ["SH"]      # Outside Offense: SH
        },
        "defensive_drills": {
            "inside": ["ID"],      # Inside Defense: ID
            "outside": ["OD"]      # Outside Defense: OD
        },
        "technical_drills": {
            "passing": ["PS"],     # Passing: PS
            "ball_handling": ["BH"],  # Ball Handling: BH
            "rebounding": ["RB"]   # Rebounding: RB
        },
        "weight_room": {
            "strength": ["ST"],    # Strength Training: ST
            "agility": ["AG"]      # Agility Training: AG
        },
        "conditioning": ["ND", "CH"],  # Conditioning: ND, CH (0.5 multiplier)
        "free_throws": ["FT"],     # Free Throws: FT
        "film_study": ["IQ", "CH"],  # Film Study: IQ, CH (0.5 multiplier)
    }
    
    # Map team drill categories to team attributes (from training_execution.md)
    team_category_map = {
        "team_offense": {
            "install": "offensive_efficiency"  # Offense: Offense Efficiency
        },
        "team_defense": {
            "install": "defensive_efficiency"  # Defense: Defense Efficiency
        },
        "fast_breaks": {
            "offense_install": "fb_efficiency",  # Fast Break Offense: Fast Break Efficiency
            "defense_install": "fb_opp_modifier"  # Fast Break Defense: fb_opp_modifier
        },
        "presses_traps": {
            "defense_install": "pt_efficiency",  # P/T Defense: PT Efficiency
            "offense_install": "pt_opp_modifier"  # P/T Offense: pt_opp_modifier
        },
        # Scrimmages: Team Chemistry, Shot Threshold, Rebounding (handled separately)
    }
    
    # Apply player training points
    for category, allocation_data in normalized_allocations.items():
        if category not in player_category_map:
            continue
        
        attr_mapping = player_category_map[category]
        
        # Handle different allocation formats
        if isinstance(allocation_data, dict):
            # Category with subtypes (e.g., offensive_drills: {inside: 3, outside: 2})
            for subtype, points in allocation_data.items():
                if subtype in attr_mapping:
                    attrs_to_update = attr_mapping[subtype]
                    for attr in attrs_to_update:
                        # Apply multiplier for CH (0.5) in conditioning and film_study
                        multiplier = 0.5 if attr == "CH" and category in ["conditioning", "film_study"] else 1.0
                        for player in players:
                            _apply_player_training_points(
                                player, attr, points, archetype, sub_option, multiplier
                            )
        elif isinstance(allocation_data, int):
            # Category with single value (e.g., conditioning: 3)
            if isinstance(attr_mapping, list):
                attrs_to_update = attr_mapping
                for attr in attrs_to_update:
                    # Apply multiplier for CH (0.5) in conditioning and film_study
                    multiplier = 0.5 if attr == "CH" and category in ["conditioning", "film_study"] else 1.0
                    for player in players:
                        _apply_player_training_points(
                            player, attr, allocation_data, archetype, sub_option, multiplier
                        )
    
    # Handle special focus effects that apply to all players
    if sub_option == "culture-builder-inspire":
        # Improve EM, MO by random.randint(1,2) for all players
        for player in players:
            attrs = player.get("attributes", {})
            em_improvement = random.randint(1, 2)
            mo_improvement = random.randint(1, 2)
            attrs["EM"] = min(100, attrs.get("EM", 0) + em_improvement)
            attrs["MO"] = min(10, attrs.get("MO", 0) + mo_improvement)
            # Update anchors
            attrs["anchor_EM"] = attrs["EM"]
            attrs["anchor_MO"] = attrs["MO"]
    
    if sub_option == "culture-builder-community":
        # Improve EM for all players
        for player in players:
            attrs = player.get("attributes", {})
            # Note: Max Crowd factor for upcoming home game, Min Crowd factor for upcoming away game
            # will be handled separately when game is created
            em_improvement = random.randint(1, 2)
            attrs["EM"] = min(100, attrs.get("EM", 0) + em_improvement)
            attrs["anchor_EM"] = attrs["EM"]
    
    # Apply team training points
    for category, allocation_data in normalized_allocations.items():
        if category not in team_category_map:
            continue
        
        attr_mapping = team_category_map[category]
        
        if isinstance(allocation_data, dict):
            for subtype, points in allocation_data.items():
                if subtype in attr_mapping:
                    team_attr = attr_mapping[subtype]
                    _apply_team_training_points(team, team_attr, points, archetype, sub_option)
    
    # Handle special team attributes
    # Rebound modifier (from technical_drills rebounding)
    if "technical_drills" in normalized_allocations:
        rebounding_points = normalized_allocations["technical_drills"].get("rebounding", 0)
        if rebounding_points > 0:
            _apply_rebound_modifier_training(team, rebounding_points, archetype, sub_option)
    
    # Handle scrimmages (if scrimmages category exists in allocations)
    # Scrimmages: Team Chemistry, Shot Threshold, Rebounding
    # Note: Scrimmages category may not be in the frontend structure yet
    if "scrimmages" in normalized_allocations:
        scrimmage_points = normalized_allocations["scrimmages"]
        if isinstance(scrimmage_points, int) and scrimmage_points > 0:
            # Apply to Team Chemistry
            _apply_team_training_points(team, "team_chemistry", scrimmage_points, archetype, sub_option)
            # Apply to Shot Threshold (decreases)
            _apply_shot_threshold_training(team, scrimmage_points)
            # Apply to Rebounding (rebound_modifier)
            _apply_rebound_modifier_training(team, scrimmage_points, archetype, sub_option)
    
    # Momentum score (amplifier only, from coaching focus)
    # Amplifier: += random.randint(1,5)
    # TODO: Apply when direction is provided on how momentum_score training points are allocated
    
    # Apply breaks effect (multiplies all positive increments)
    if "general" in normalized_allocations:
        breaks_points = normalized_allocations["general"].get("breaks", 0)
        if breaks_points is not None and breaks_points > 0:
            _apply_breaks_effect(players, team, breaks_points, player_baselines, team_baseline)
    
    # Apply NG reductions from scrimmages and conditioning
    # Track which players had reductions for training report notes
    scrimmage_reduced_players = []
    conditioning_reduced_players = []
    
    # Handle scrimmages NG reduction
    if "scrimmages" in normalized_allocations:
        scrimmage_points = normalized_allocations["scrimmages"]
        if isinstance(scrimmage_points, int) and scrimmage_points in [3, 4, 5]:
            scrimmage_reduced_players = _apply_ng_reduction_from_scrimmages(players, scrimmage_points)
    
    # Handle conditioning NG reduction
    if "conditioning" in normalized_allocations:
        conditioning_points = normalized_allocations["conditioning"]
        if isinstance(conditioning_points, int) and conditioning_points in [3, 4, 5]:
            conditioning_reduced_players = _apply_ng_reduction_from_conditioning(players, conditioning_points)
    
    # Clamp all values
    for player in players:
        attrs = player.get("attributes", {})
        for attr in TRAINABLE_PLAYER_ATTRS:
            anchor_key = f"anchor_{attr}"
            if anchor_key in attrs:
                attrs[anchor_key] = max(PLAYER_ATTR_CLAMP[0], attrs[anchor_key])
                attrs[attr] = attrs[anchor_key]
    
    for attr_name, (lower, upper) in TEAM_ATTR_CLAMPS.items():
        if attr_name in team:
            if upper is not None:
                team[attr_name] = max(lower, min(upper, team[attr_name]))
            else:
                team[attr_name] = max(lower, team[attr_name])
    
    # Calculate changes for training report
    player_changes = {}
    for player in players:
        pid = player["_id"]
        name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
        changes = {}
        for attr in TRAINABLE_PLAYER_ATTRS:
            old_val = player_baselines[pid].get(attr, 0)
            new_val = player.get("attributes", {}).get(f"anchor_{attr}", 0)
            delta = new_val - old_val
            if delta != 0:
                changes[attr] = delta
        if changes:
            player_changes[name] = changes
    
    team_changes = {}
    for attr_name in TEAM_ATTR_CLAMPS.keys():
        old_val = team_baseline.get(attr_name, 0)
        new_val = team.get(attr_name, 0)
        delta = new_val - old_val
        if delta != 0:
            team_changes[attr_name] = delta
    
    # Build training notes based on NG reductions
    training_notes = []
    
    # Add conditioning notes
    if len(conditioning_reduced_players) > 1:
        training_notes.append("Multiple players will start the next game with reduced energy due to the amount of conditioning.")
    elif len(conditioning_reduced_players) == 1:
        player_name = conditioning_reduced_players[0]
        training_notes.append(f"{player_name} will start the next game with reduced energy due to the amount of conditioning.")
    
    # Add scrimmages notes
    if len(scrimmage_reduced_players) > 1:
        training_notes.append("Multiple players will start the next game with reduced energy due to the amount of scrimmages.")
    elif len(scrimmage_reduced_players) == 1:
        player_name = scrimmage_reduced_players[0]
        training_notes.append(f"{player_name} will start the next game with reduced energy due to the amount of scrimmages.")
    
    training_report = {
        "player_changes": player_changes,
        "team_changes": team_changes,
        "coaching_focus": {
            "archetype": archetype,
            "sub_option": sub_option
        },
        "training_notes": training_notes
    }
    
    return players, team, training_report


def _apply_player_training_points(
    player: dict,
    attr: str,
    points: int,
    archetype: Optional[str] = None,
    sub_option: Optional[str] = None,
    multiplier: float = 1.0
):
    """
    Apply training points to a single player attribute.
    
    Logic:
    - 1 point: += random.randint(1, 3)
    - 2 points: += random.randint(2, 5)
    - 3 points: += random.randint(3, 7)
    - 4 points: += random.randint(3, 8)
    - 5 points: += random.randint(3, 9)
    
    Focus amplifier: Applied based on sub_option selection
    Multiplier: For attributes like CH that get 0.5 multiplier
    """
    if points == 0:
        return
    
    attrs = player.get("attributes", {})
    anchor_key = f"anchor_{attr}"
    
    # Get base increase based on points
    if points == 1:
        increase = random.randint(1, 3)
    elif points == 2:
        increase = random.randint(2, 5)
    elif points == 3:
        increase = random.randint(3, 7)
    elif points == 4:
        increase = random.randint(3, 8)
    elif points == 5:
        increase = random.randint(3, 9)
    else:
        # For points > 5, use same logic as 5 points
        increase = random.randint(3, 9)
    
    # Apply multiplier (for CH in conditioning/film_study)
    increase = int(increase * multiplier)
    
    # Check if this attribute should be amplified based on focus
    should_amplify = False
    
    # Handle Player Maximizer special cases (top 3 / next 3 attributes)
    if sub_option in ["player-maximizer-top-3", "player-maximizer-attributes-4-6"]:
        # Get player's top attributes (excluding CH, EM, MO, NG)
        player_attrs = {a: attrs.get(f"anchor_{a}", 0) for a in TRAINABLE_PLAYER_ATTRS}
        sorted_attrs = sorted(player_attrs.items(), key=lambda x: x[1], reverse=True)
        
        if sub_option == "player-maximizer-top-3":
            # Top 3 attributes
            top_attrs = [a[0] for a in sorted_attrs[:3]]
            should_amplify = attr in top_attrs
        elif sub_option == "player-maximizer-attributes-4-6":
            # Attributes 4-6
            next_attrs = [a[0] for a in sorted_attrs[3:6]]
            should_amplify = attr in next_attrs
    else:
        # Standard amplification check
        should_amplify = _should_amplify_player_attr(attr, archetype, sub_option)
    
    # Apply focus amplifier if applicable
    if should_amplify:
        focus_multiplier = random.choice([1.5, 1.6, 1.7, 1.8])
        increase = int(increase * focus_multiplier)
    
    # Apply increase
    current_val = attrs.get(anchor_key, 0)
    attrs[anchor_key] = current_val + increase
    attrs[attr] = attrs[anchor_key]  # Update base attribute too


def _normalize_allocations(allocations: Dict) -> Dict:
    """
    Normalize allocations from frontend structure to backend structure.
    
    Frontend sends:
    {
        player_drills: {
            offense: {inside: 3, outside: 2},
            defense: {inside: 1, outside: 2},
            technical: {passing: 1, ball_handling: 1, rebounding: 1},
            weight_room: {strength: 1, agility: 1}
        },
        team_drills: {
            team_offense: {install: 2},
            team_defense: {install: 2},
            fast_breaks: {offense_install: 1, defense_install: 1},
            presses_traps: {defense_install: 1, offense_install: 1}
        },
        general: {
            conditioning: 2,
            free_throws: 2,
            film_study: 2,
            breaks: 1
        }
    }
    
    Backend expects:
    {
        offensive_drills: {inside: 3, outside: 2},
        defensive_drills: {inside: 1, outside: 2},
        technical_drills: {passing: 1, ball_handling: 1, rebounding: 1},
        weight_room: {strength: 1, agility: 1},
        team_offense: {install: 2},
        team_defense: {install: 2},
        fast_breaks: {offense_install: 1, defense_install: 1},
        presses_traps: {defense_install: 1, offense_install: 1},
        conditioning: 2,
        free_throws: 2,
        film_study: 2,
        breaks: 1
    }
    """
    normalized = {}
    
    if "player_drills" in allocations:
        player_drills = allocations["player_drills"]
        if "offense" in player_drills:
            normalized["offensive_drills"] = player_drills["offense"]
        if "defense" in player_drills:
            normalized["defensive_drills"] = player_drills["defense"]
        if "technical" in player_drills:
            normalized["technical_drills"] = player_drills["technical"]
        if "weight_room" in player_drills:
            normalized["weight_room"] = player_drills["weight_room"]
    
    if "team_drills" in allocations:
        team_drills = allocations["team_drills"]
        if "team_offense" in team_drills:
            normalized["team_offense"] = team_drills["team_offense"]
        if "team_defense" in team_drills:
            normalized["team_defense"] = team_drills["team_defense"]
        if "fast_breaks" in team_drills:
            normalized["fast_breaks"] = team_drills["fast_breaks"]
        if "presses_traps" in team_drills:
            normalized["presses_traps"] = team_drills["presses_traps"]
    
    if "general" in allocations:
        general = allocations["general"]
        if "conditioning" in general:
            normalized["conditioning"] = general["conditioning"]
        if "free_throws" in general:
            normalized["free_throws"] = general["free_throws"]
        if "film_study" in general:
            normalized["film_study"] = general["film_study"]
        if "breaks" in general:
            normalized["breaks"] = general["breaks"]
        if "scrimmages" in general:
            normalized["scrimmages"] = general["scrimmages"]
    
    # Also check team_drills for scrimmages
    if "team_drills" in allocations:
        team_drills = allocations["team_drills"]
        if "scrimmages" in team_drills:
            normalized["scrimmages"] = team_drills["scrimmages"]
    
    return normalized


def _apply_team_training_points(team: dict, team_attr: str, points: int, archetype: Optional[str] = None, sub_option: Optional[str] = None):
    """
    Apply training points to a team attribute.
    
    Logic for all team attributes (excluding shot_threshold, rebound_modifier, momentum_score):
    - 1 point: += random.randint(1, 2)
    - 2 points: += random.randint(2, 3)
    - 3 points: += random.randint(3, 5)
    - 4 points: += random.randint(3, 6)
    - 5 points: += random.randint(3, 7)
    - Amplifier: += incremental random.randint(1, 3)
    """
    if points == 0 or team_attr not in TEAM_ATTR_CLAMPS:
        return
    
    # Get base increase
    if points == 1:
        increase = random.randint(1, 2)
    elif points == 2:
        increase = random.randint(2, 3)
    elif points == 3:
        increase = random.randint(3, 5)
    elif points == 4:
        increase = random.randint(3, 6)
    elif points == 5:
        increase = random.randint(3, 7)
    else:
        increase = random.randint(3, 7)
    
    # Apply amplifier (incremental add)
    amplifier = random.randint(1, 3)
    final_increase = increase + amplifier
    
    # Apply focus amplifier if this attribute is amplified by the selected focus
    if _should_amplify_team_attr(team_attr, archetype, sub_option):
        focus_multiplier = random.choice([1.5, 1.6, 1.7, 1.8])
        final_increase = int(final_increase * focus_multiplier)
    
    # Apply to team
    current_val = team.get(team_attr, 0)
    team[team_attr] = current_val + final_increase


def _apply_rebound_modifier_training(team: dict, points: int, archetype: Optional[str] = None, sub_option: Optional[str] = None):
    """
    Apply training points to rebound_modifier.
    
    Logic:
    - 1 point: += random choice [0.1, 0.2]
    - 2 points: += random choice [0.2, 0.3]
    - 3 points: += random choice [0.2, 0.3, 0.4]
    - 4 points: += random choice [0.2, 0.3, 0.4, 0.5]
    - 5 points: += random choice [0.3, 0.4, 0.5]
    - Amplifier: += incremental random choice [0.1, 0.2]
    """
    if points == 0:
        return
    
    # Get base increase
    if points == 1:
        increase = random.choice([0.1, 0.2])
    elif points == 2:
        increase = random.choice([0.2, 0.3])
    elif points == 3:
        increase = random.choice([0.2, 0.3, 0.4])
    elif points == 4:
        increase = random.choice([0.2, 0.3, 0.4, 0.5])
    elif points == 5:
        increase = random.choice([0.3, 0.4, 0.5])
    else:
        increase = random.choice([0.3, 0.4, 0.5])
    
    # Apply amplifier (incremental add)
    amplifier = random.choice([0.1, 0.2])
    final_increase = increase + amplifier
    
    # Apply focus amplifier if rebound_modifier is amplified by the selected focus
    if _should_amplify_team_attr("rebound_modifier", archetype, sub_option):
        focus_multiplier = random.choice([1.5, 1.6, 1.7, 1.8])
        final_increase = final_increase * focus_multiplier
    
    # Apply to team
    current_val = team.get("rebound_modifier", 1.0)
    team["rebound_modifier"] = current_val + final_increase


def _apply_shot_threshold_training(team: dict, points: int):
    """
    Apply training points to shot_threshold (decreases threshold, lower is better).
    
    Logic:
    - 1 point: -= random.randint(10, 25)
    - 2 points: -= random.randint(15, 35)
    - 3 points: -= random.randint(20, 45)
    - 4 points: -= random.randint(20, 55)
    - 5 points: -= random.randint(20, 65)
    - Amplifier: *= random.choice([1.3, 1.4, 1.5, 1.6])
    """
    if points == 0:
        return
    
    # Get base decrease
    if points == 1:
        decrease = random.randint(10, 25)
    elif points == 2:
        decrease = random.randint(15, 35)
    elif points == 3:
        decrease = random.randint(20, 45)
    elif points == 4:
        decrease = random.randint(20, 55)
    elif points == 5:
        decrease = random.randint(20, 65)
    else:
        decrease = random.randint(20, 65)
    
    # Apply amplifier (multiply)
    amplifier = random.choice([1.3, 1.4, 1.5, 1.6])
    final_decrease = int(decrease * amplifier)
    
    # Apply to team (subtract, lower is better)
    current_val = team.get("shot_threshold", 0)
    team["shot_threshold"] = current_val - final_decrease


def _should_amplify_player_attr(attr: str, archetype: Optional[str], sub_option: Optional[str]) -> bool:
    """
    Check if a player attribute should be amplified based on focus selection.
    
    Returns True if the attribute should get focus amplification.
    """
    if not sub_option:
        return False
    
    # Authoritarian Options
    if sub_option == "authoritarian-discipline":
        return attr in ["BH"]  # Amplifies BH, foul_modifier, turnover_modifier
    elif sub_option == "authoritarian-rebounding":
        return attr == "RB"  # Amplifies RB, rebound_modifier
    elif sub_option == "authoritarian-teamwork":
        return attr == "PS"  # Amplifies PS, Motion Play Effectiveness Scores, Zone Defense Effectiveness Scores
    elif sub_option == "authoritarian-execution":
        return False  # Amplifies Set Play Effectiveness Scores, Man Defense Effectiveness Scores (handled separately)
    
    # Systems Coach Options
    elif sub_option == "systems-coach-offense":
        return False  # Amplifies offense efficiency gains, offensive play effectiveness scores (handled separately)
    elif sub_option == "systems-coach-defense":
        return False  # Amplifies defense efficiency gains, defense play effectiveness scores (handled separately)
    elif sub_option == "systems-coach-fast-breaks":
        return False  # Amplifies fb efficiency gains, fb defense gains (handled separately)
    elif sub_option == "systems-coach-press-trap":
        return False  # Amplifies pt efficiency gains, pt offense gains (handled separately)
    
    # Player Maximizer Options
    elif sub_option == "player-maximizer-top-3":
        # Amplifies gains to the player's top 3 attributes (excluding CH, EM, MO, NG)
        # This will be handled per-player in the calling function
        return False
    elif sub_option == "player-maximizer-attributes-4-6":
        # Amplifies gains to the player's top 4-6 highest attributes (excluding CH, EM, MO, NG)
        # This will be handled per-player in the calling function
        return False
    elif sub_option == "player-maximizer-custom":
        # Custom attributes chosen by user (to be built later)
        return False
    elif sub_option == "player-maximizer-opportunity":
        return False  # Improves Non-Successful Set Play Skeleton Shot Scores, Improves all Motion Shot Scores (handled separately)
    
    # Culture Builder Options
    elif sub_option == "culture-builder-inspire":
        return attr in ["EM", "MO"]  # Improves EM, MO by random.randint(1,2), amplifies Team Chemistry gains
    elif sub_option == "culture-builder-community":
        return attr == "EM"  # Improves EM, Max Crowd factor for upcoming home game, Min Crowd factor for upcoming away game
    elif sub_option == "culture-builder-teamwork":
        return attr == "PS"  # Amplifies Team Chemistry gains, Improves Motion Play Effectiveness Scores, Zone Defense Effectiveness Scores
    elif sub_option == "culture-builder-confidence":
        return False  # Improves Set Play Effectiveness Scores, Man Defense Effectiveness Scores (handled separately)
    
    return False


def _should_amplify_team_attr(team_attr: str, archetype: Optional[str], sub_option: Optional[str]) -> bool:
    """
    Check if a team attribute should be amplified based on focus selection.
    
    Returns True if the attribute should get focus amplification.
    """
    if not sub_option:
        return False
    
    # Authoritarian Options
    if sub_option == "authoritarian-discipline":
        return team_attr in ["foul_modifier", "turnover_modifier"]  # Amplifies BH, foul_modifier, turnover_modifier
    elif sub_option == "authoritarian-rebounding":
        return team_attr == "rebound_modifier"  # Amplifies RB, rebound_modifier
    
    # Systems Coach Options
    elif sub_option == "systems-coach-offense":
        return team_attr == "offensive_efficiency"  # Amplifies offense efficiency gains
    elif sub_option == "systems-coach-defense":
        return team_attr == "defensive_efficiency"  # Amplifies defense efficiency gains
    elif sub_option == "systems-coach-fast-breaks":
        return team_attr in ["fb_efficiency", "fb_opp_modifier"]  # Amplifies fb efficiency gains, fb defense gains
    elif sub_option == "systems-coach-press-trap":
        return team_attr in ["pt_efficiency", "pt_opp_modifier"]  # Amplifies pt efficiency gains, pt offense gains
    
    # Culture Builder Options
    elif sub_option == "culture-builder-inspire":
        return team_attr == "team_chemistry"  # Amplifies Team Chemistry gains
    
    return False


def _apply_breaks_effect(
    players: List[dict],
    team: dict,
    breaks_points: int,
    original_player_baselines: Dict,
    original_team_baseline: Dict
):
    """
    Apply breaks effect to all positive increments from this training session.
    
    Logic:
    - 0: random.choice([0.85, 0.9, 0.95]) - applied to all positive increments
    - 1: random.choice([0.9, 0.95, 1, 1, 1])
    - 2: random.choice([0.95, 1, 1, 1, 1])
    - 3: random.choice([0.9, 0.95, 1])
    - 4: random.choice([0.9, 0.95, 1]), and team chemistry += random.randint(-1,1)
    - 5: random.choice([0.9, 0.95, 1]), and team chemistry += random.randint(-3,3)
    
    Note: Only applies to positive increments (gains), not losses.
    Calculates change from original baseline, if positive, multiplies the increment by multiplier.
    """
    if breaks_points == 0:
        multiplier = random.choice([0.85, 0.9, 0.95])
    elif breaks_points == 1:
        multiplier = random.choice([0.9, 0.95, 1, 1, 1])
    elif breaks_points == 2:
        multiplier = random.choice([0.95, 1, 1, 1, 1])
    elif breaks_points == 3:
        multiplier = random.choice([0.9, 0.95, 1])
    elif breaks_points == 4:
        multiplier = random.choice([0.9, 0.95, 1])
        # Also adjust team chemistry
        team["team_chemistry"] += random.randint(-1, 1)
        team["team_chemistry"] = max(
            TEAM_ATTR_CLAMPS["team_chemistry"][0],
            min(TEAM_ATTR_CLAMPS["team_chemistry"][1], team["team_chemistry"])
        )
    elif breaks_points == 5:
        multiplier = random.choice([0.9, 0.95, 1])
        # Also adjust team chemistry
        team["team_chemistry"] += random.randint(-3, 3)
        team["team_chemistry"] = max(
            TEAM_ATTR_CLAMPS["team_chemistry"][0],
            min(TEAM_ATTR_CLAMPS["team_chemistry"][1], team["team_chemistry"])
        )
    else:
        # For breaks > 5, use same as 5
        multiplier = random.choice([0.9, 0.95, 1])
        team["team_chemistry"] += random.randint(-3, 3)
        team["team_chemistry"] = max(
            TEAM_ATTR_CLAMPS["team_chemistry"][0],
            min(TEAM_ATTR_CLAMPS["team_chemistry"][1], team["team_chemistry"])
        )
    
    # Apply multiplier to positive player attribute increments
    for player in players:
        pid = player["_id"]
        attrs = player.get("attributes", {})
        original_baseline = original_player_baselines.get(pid, {})
        
        for attr in TRAINABLE_PLAYER_ATTRS:
            anchor_key = f"anchor_{attr}"
            original_val = original_baseline.get(attr, 0)
            current_val = attrs.get(anchor_key, 0)
            increment = current_val - original_val
            
            # Only apply to positive increments
            if increment > 0:
                # Calculate new value: original + (increment * multiplier)
                new_val = original_val + int(increment * multiplier)
                attrs[anchor_key] = new_val
                attrs[attr] = new_val
    
    # Apply multiplier to positive team attribute increments
    for attr_name in TEAM_ATTR_CLAMPS.keys():
        if attr_name in team:
            original_val = original_team_baseline.get(attr_name, 0)
            current_val = team[attr_name]
            increment = current_val - original_val
            
            # Only apply to positive increments
            if increment > 0:
                # Calculate new value: original + (increment * multiplier)
                new_val = original_val + int(increment * multiplier)
                team[attr_name] = new_val


def _apply_ng_reduction_from_scrimmages(players: List[dict], scrimmage_points: int) -> List[str]:
    """
    Apply NG reduction to players based on scrimmage points.
    
    Logic:
    - scrimmages == 3: reduce_ng_list = [0, 0.01, 0.01, 0.02]
    - scrimmages == 4: reduce_ng_list = [0, 0.01, 0.02, 0.02, 0.03]
    - scrimmages == 5: reduce_ng_list = [0.01, 0.02, 0.03, 0.03, 0.04]
    
    Special case: If player ND > 79:
    - scrimmages == 3: omit them (no reduction)
    - scrimmages == 4: apply scrimmages == 3 list
    - scrimmages == 5: apply scrimmages == 4 list
    
    Args:
        players: List of player dicts with attributes
        scrimmage_points: Number of scrimmage points (3, 4, or 5)
    
    Returns:
        List of player names who had NG reductions
    """
    if scrimmage_points not in [3, 4, 5]:
        return []
    
    # Define reduction lists
    reduce_ng_lists = {
        3: [0, 0.01, 0.01, 0.02],
        4: [0, 0.01, 0.02, 0.02, 0.03],
        5: [0.01, 0.02, 0.03, 0.03, 0.04]
    }
    
    reduced_players = []
    
    for player in players:
        attrs = player.get("attributes", {})
        nd = attrs.get("ND", 0)
        ng = attrs.get("NG", 1.0)
        
        # Determine which list to use based on ND
        if nd > 79:
            # Special handling for high ND players
            if scrimmage_points == 3:
                # Omit them (no reduction)
                continue
            elif scrimmage_points == 4:
                # Use scrimmages == 3 list
                reduce_ng_list = reduce_ng_lists[3]
            elif scrimmage_points == 5:
                # Use scrimmages == 4 list
                reduce_ng_list = reduce_ng_lists[4]
        else:
            # Normal players use the list for their scrimmage points
            reduce_ng_list = reduce_ng_lists[scrimmage_points]
        
        # Apply reduction
        reduction = random.choice(reduce_ng_list)
        if reduction > 0:
            new_ng = max(0.0, ng - reduction)  # Clamp to 0 minimum
            attrs["NG"] = round(new_ng, 2)
            
            # Track player name for notes
            first_name = player.get("first_name", "")
            last_name = player.get("last_name", "")
            player_name = f"{first_name} {last_name}".strip()
            if player_name:
                reduced_players.append(player_name)
    
    return reduced_players


def _apply_ng_reduction_from_conditioning(players: List[dict], conditioning_points: int) -> List[str]:
    """
    Apply NG reduction to players based on conditioning points.
    
    Logic:
    - conditioning == 3: reduce_ng_list = [0, 0.01, 0.01, 0.02]
    - conditioning == 4: reduce_ng_list = [0, 0.01, 0.02, 0.02, 0.03]
    - conditioning == 5: reduce_ng_list = [0.01, 0.02, 0.03, 0.03, 0.04]
    
    Special case: If player ND > 79:
    - conditioning == 3: omit them (no reduction)
    - conditioning == 4: apply conditioning == 3 list
    - conditioning == 5: apply conditioning == 4 list
    
    Args:
        players: List of player dicts with attributes
        conditioning_points: Number of conditioning points (3, 4, or 5)
    
    Returns:
        List of player names who had NG reductions
    """
    if conditioning_points not in [3, 4, 5]:
        return []
    
    # Define reduction lists (same as scrimmages)
    reduce_ng_lists = {
        3: [0, 0.01, 0.01, 0.02],
        4: [0, 0.01, 0.02, 0.02, 0.03],
        5: [0.01, 0.02, 0.03, 0.03, 0.04]
    }
    
    reduced_players = []
    
    for player in players:
        attrs = player.get("attributes", {})
        nd = attrs.get("ND", 0)
        ng = attrs.get("NG", 1.0)
        
        # Determine which list to use based on ND
        if nd > 79:
            # Special handling for high ND players
            if conditioning_points == 3:
                # Omit them (no reduction)
                continue
            elif conditioning_points == 4:
                # Use conditioning == 3 list
                reduce_ng_list = reduce_ng_lists[3]
            elif conditioning_points == 5:
                # Use conditioning == 4 list
                reduce_ng_list = reduce_ng_lists[4]
        else:
            # Normal players use the list for their conditioning points
            reduce_ng_list = reduce_ng_lists[conditioning_points]
        
        # Apply reduction
        reduction = random.choice(reduce_ng_list)
        if reduction > 0:
            new_ng = max(0.0, ng - reduction)  # Clamp to 0 minimum
            attrs["NG"] = round(new_ng, 2)
            
            # Track player name for notes
            first_name = player.get("first_name", "")
            last_name = player.get("last_name", "")
            player_name = f"{first_name} {last_name}".strip()
            if player_name:
                reduced_players.append(player_name)
    
    return reduced_players

