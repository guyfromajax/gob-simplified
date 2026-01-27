"""
New Training Execution System - Implements logic from training_execution.md brief

This module implements the new training execution system with:
- Pre-training conditions
- New training point application logic
- Clamps and validation
- Training report generation
"""

import random
import logging
from typing import List, Dict, Tuple, Optional
from BackEnd.constants import ALL_ATTRS

logger = logging.getLogger(__name__)


def execute_training(
    players: List[dict],
    team: dict,
    allocations: Dict,
    coaching_focus: Optional[str] = None,
    plays_data: Optional[Dict] = None,
    strategy_settings: Optional[Dict] = None,
    playbook_settings: Optional[Dict] = None,
    scouting_data: Optional[Dict] = None,
    playbook_training_mode: str = "current-playbooks",
    skip_pre_training_depreciation: bool = False
) -> Tuple[List[dict], dict, Dict, Dict, Dict]:
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
    
    # Initialize plays and scouting_data if not provided
    if plays_data is None:
        plays_data = {}
    if scouting_data is None:
        scouting_data = {}
    
    logger.warning(f"📚 [TRAINING] Initial plays_data keys: {list(plays_data.keys())}")
    logger.warning(f"📚 [TRAINING] Initial scouting_data keys: {list(scouting_data.keys()) if scouting_data else 'None'}")
    
    # Store original effectiveness values BEFORE any changes
    original_plays_effectiveness = {}
    for play_name, play_data in plays_data.items():
        if isinstance(play_data, dict):
            eff = play_data.get("effectiveness", 0)
            original_plays_effectiveness[play_name] = eff
            logger.warning(f"📚 [TRAINING] Play '{play_name}': initial effectiveness = {eff}, play_type = {play_data.get('play_type', 'unknown')}")
    
    original_defenses_effectiveness = {}
    if scouting_data and "defense" in scouting_data:
        for defense_name, defense_data in scouting_data["defense"].items():
            if isinstance(defense_data, dict):
                eff = defense_data.get("effectiveness", 0)
                original_defenses_effectiveness[defense_name] = eff
                logger.warning(f"📚 [TRAINING] Defense '{defense_name}': initial effectiveness = {eff}")
    
    logger.warning(f"📚 [TRAINING] Total plays tracked: {len(original_plays_effectiveness)}")
    logger.warning(f"📚 [TRAINING] Total defenses tracked: {len(original_defenses_effectiveness)}")
    
    # Step 0: Reduce play/defense effectiveness by 5-15 (pre-training decay)
    # Skip for first training (training camp) in franchise mode
    if not skip_pre_training_depreciation:
        plays_data = _apply_pre_training_effectiveness_decay(plays_data)
        scouting_data = _apply_pre_training_defense_decay(scouting_data)
    else:
        logger.warning("⏭️ [TRAINING] Skipping pre-training depreciation (first training/training camp)")
    
    # Step 1: Apply pre-training conditions
    # Skip for first training (training camp) in franchise mode
    if not skip_pre_training_depreciation:
        players, team = apply_pre_training_conditions(players, team)
    else:
        logger.warning("⏭️ [TRAINING] Skipping pre-training conditions (first training/training camp)")
    
    # Step 2: Apply training points (pass original baselines for report calculation)
    players, team, training_report = apply_training_points(
        players, team, allocations, coaching_focus,
        original_baselines=original_player_baselines,
        original_team_baseline=original_team_baseline
    )
    
    # Step 3: Apply play/defense training
    updated_plays, updated_scouting_data = apply_play_defense_training(
        plays_data,
        scouting_data,
        allocations,
        playbook_training_mode,
        strategy_settings,
        playbook_settings,
        coaching_focus
    )
    
    # Calculate effectiveness changes for training report
    plays_effectiveness_changes = {}
    for play_name, original_eff in original_plays_effectiveness.items():
        if play_name in updated_plays:
            new_eff = updated_plays[play_name].get("effectiveness", 0)
            plays_effectiveness_changes[play_name] = new_eff - original_eff
    
    defenses_effectiveness_changes = {}
    if updated_scouting_data and "defense" in updated_scouting_data:
        for defense_name, original_eff in original_defenses_effectiveness.items():
            if defense_name in updated_scouting_data["defense"]:
                new_eff = updated_scouting_data["defense"][defense_name].get("effectiveness", 0)
                defenses_effectiveness_changes[defense_name] = new_eff - original_eff
    
    # Add effectiveness changes to training report
    training_report["plays_effectiveness_changes"] = plays_effectiveness_changes
    training_report["defenses_effectiveness_changes"] = defenses_effectiveness_changes
    training_report["plays_data"] = updated_plays
    training_report["scouting_data"] = updated_scouting_data
    
    return players, team, updated_plays, updated_scouting_data, training_report

# Player attributes excluding EM, MO, NG
TRAINABLE_PLAYER_ATTRS = [attr for attr in ALL_ATTRS if attr not in ["EM", "MO", "NG"]]

# Team attribute clamps (lower, upper)
TEAM_ATTR_CLAMPS = {
    "shot_threshold": (-10, 190),
    "discipline": (-10, 10),
    "fight": (-10, 10),
    "rebound_modifier": (0.0, 0.4),
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
    Apply pre-training conditions to players only.
    
    Note: Team attribute decay has been removed. Team attributes are now updated
    at the end of each game via update_team_attributes_after_game() in franchise_routes.py.
    
    Pre-training conditions:
    - Player attributes (excluding EM, MO, NG): += randint(-4, -1) for each player/attribute
    
    Args:
        players: List of player dicts with attributes
        team: Team dict with team attributes (unchanged, kept for API compatibility)
    
    Returns:
        Tuple of (updated_players, unchanged_team)
    """
    # Apply to each player
    for player in players:
        attrs = player.get("attributes", {})
        for attr in TRAINABLE_PLAYER_ATTRS:
            anchor_key = f"anchor_{attr}"
            if anchor_key in attrs:
                # Apply random decrease: randint(-4, -1) inclusive
                decrease = random.randint(-4, -1)
                attrs[anchor_key] = max(PLAYER_ATTR_CLAMP[0], attrs[anchor_key] + decrease)
                # Also update base attribute
                attrs[attr] = attrs[anchor_key]
    
    # Team attributes are no longer decayed here - they are updated at end of game
    # via update_team_attributes_after_game() in franchise_routes.py
    # Return team unchanged
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
    logger.warning(f"🔋 [TRAINING] Raw allocations received: {allocations}")
    normalized_allocations = _normalize_allocations(allocations)
    logger.warning(f"🔋 [TRAINING] Normalized allocations keys: {list(normalized_allocations.keys())}")
    
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
            _apply_rebound_modifier_training(team, rebounding_points, archetype, sub_option, source="technical_drills")
    
    # Handle scrimmages (if scrimmages category exists in allocations)
    # Scrimmages: Team Chemistry, Shot Threshold, Rebounding
    # Note: Scrimmages category may not be in the frontend structure yet
    if "scrimmages" in normalized_allocations:
        scrimmage_points = normalized_allocations["scrimmages"]
        if isinstance(scrimmage_points, int) and scrimmage_points > 0:
            # Apply to Team Chemistry
            _apply_team_training_points(team, "team_chemistry", scrimmage_points, archetype, sub_option)
            # Apply to Shot Threshold (decreases)
            _apply_shot_threshold_training(team, scrimmage_points, archetype, sub_option)
            # Apply to Rebounding (rebound_modifier)
            _apply_rebound_modifier_training(team, scrimmage_points, archetype, sub_option, source="scrimmages")
    
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
        logger.warning(f"🔋 [TRAINING] Checking scrimmages NG reduction: points={scrimmage_points}, type={type(scrimmage_points)}")
        if isinstance(scrimmage_points, int) and scrimmage_points in [3, 4, 5]:
            logger.warning(f"🔋 [TRAINING] Applying scrimmages NG reduction for {scrimmage_points} points")
            scrimmage_reduced_players = _apply_ng_reduction_from_scrimmages(players, scrimmage_points)
        else:
            logger.warning(f"🔋 [TRAINING] Skipping scrimmages NG reduction: points={scrimmage_points} not in [3, 4, 5]")
    else:
        logger.warning(f"🔋 [TRAINING] No scrimmages in normalized_allocations: {list(normalized_allocations.keys())}")
    
    # Handle conditioning NG reduction
    if "conditioning" in normalized_allocations:
        conditioning_points = normalized_allocations["conditioning"]
        logger.warning(f"🔋 [TRAINING] Checking conditioning NG reduction: points={conditioning_points}, type={type(conditioning_points)}")
        if isinstance(conditioning_points, int) and conditioning_points in [3, 4, 5]:
            logger.warning(f"🔋 [TRAINING] Applying conditioning NG reduction for {conditioning_points} points")
            conditioning_reduced_players = _apply_ng_reduction_from_conditioning(players, conditioning_points)
        else:
            logger.warning(f"🔋 [TRAINING] Skipping conditioning NG reduction: points={conditioning_points} not in [3, 4, 5]")
    else:
        logger.warning(f"🔋 [TRAINING] No conditioning in normalized_allocations: {list(normalized_allocations.keys())}")
    
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
    
    Base ranges:
    - 1 point: += random.randint(1, 3)
    - 2 points: += random.randint(2, 4)
    - 3 points: += random.randint(3, 6)
    - 4 points: += random.randint(4, 7)
    - 5 points: += random.randint(4, 9)
    
    Year-based adjustments:
    - Freshman: +1 to min, +4 to max
    - Sophomore: +1 to min, +2 to max
    - Junior: no change (base ranges)
    - Senior: -1 to max only
    
    Focus amplifier: Applied based on sub_option selection
    Multiplier: For attributes like CH that get 0.5 multiplier
    """
    if points == 0:
        return
    
    attrs = player.get("attributes", {})
    anchor_key = f"anchor_{attr}"
    
    # Get player year and calculate year adjustments
    year = player.get("year", "").lower() if player.get("year") else ""
    min_adjustment = 0
    max_adjustment = 0
    if year == "freshman":
        min_adjustment = 1
        max_adjustment = 4
    elif year == "sophomore":
        min_adjustment = 1
        max_adjustment = 2
    elif year == "junior":
        min_adjustment = 0
        max_adjustment = 0
    elif year == "senior":
        min_adjustment = 0
        max_adjustment = -1
    
    # Get base increase based on points, with year adjustments to min and max
    if points == 1:
        base_min, base_max = 1, 3
    elif points == 2:
        base_min, base_max = 2, 4
    elif points == 3:
        base_min, base_max = 3, 6
    elif points == 4:
        base_min, base_max = 4, 7
    elif points == 5:
        base_min, base_max = 4, 9
    else:
        # For points > 5, use same logic as 5 points
        base_min, base_max = 3, 9
    
    adjusted_min = base_min + min_adjustment
    adjusted_max = max(adjusted_min, base_max + max_adjustment)  # Ensure max >= min
    increase = random.randint(adjusted_min, adjusted_max)
    
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
        logger.warning(f"🔋 [NORMALIZE] team_drills keys: {list(team_drills.keys())}")
        if "team_offense" in team_drills:
            normalized["team_offense"] = team_drills["team_offense"]
        if "team_defense" in team_drills:
            normalized["team_defense"] = team_drills["team_defense"]
        if "fast_breaks" in team_drills:
            normalized["fast_breaks"] = team_drills["fast_breaks"]
        if "presses_traps" in team_drills:
            normalized["presses_traps"] = team_drills["presses_traps"]
        if "scrimmages" in team_drills:
            logger.warning(f"🔋 [NORMALIZE] Found scrimmages in team_drills: {team_drills['scrimmages']}")
            normalized["scrimmages"] = team_drills["scrimmages"]
        else:
            logger.warning(f"🔋 [NORMALIZE] scrimmages NOT in team_drills. team_drills keys: {list(team_drills.keys())}")
    
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


def _apply_rebound_modifier_training(team: dict, points: int, archetype: Optional[str] = None, sub_option: Optional[str] = None, source: str = "technical_drills"):
    """
    Apply training points to rebound_modifier.
    
    Args:
        team: Team dict
        points: Training points allocated (1-5)
        archetype: Optional coaching focus archetype
        sub_option: Optional coaching focus sub-option
        source: "technical_drills" or "scrimmages" - determines which range to use
    
    Technical Drills ranges (in 0.01 increments):
    - 1 point: +0.01 to +0.06
    - 2 points: +0.03 to +0.08
    - 3 points: +0.04 to +0.10
    - 4 points: +0.04 to +0.12
    - 5 points: +0.04 to +0.14
    
    Scrimmages ranges (in 0.01 increments):
    - 1 point: +0.01 to +0.03
    - 2 points: +0.02 to +0.05
    - 3 points: +0.03 to +0.08
    - 4 points: +0.03 to +0.09
    - 5 points: +0.03 to +0.10
    """
    if points == 0:
        return
    
    # Get base increase based on source and points
    if source == "technical_drills":
        if points == 1:
            increase = random.randint(1, 6) / 100.0  # 0.01 to 0.06
        elif points == 2:
            increase = random.randint(3, 8) / 100.0  # 0.03 to 0.08
        elif points == 3:
            increase = random.randint(4, 10) / 100.0  # 0.04 to 0.10
        elif points == 4:
            increase = random.randint(4, 12) / 100.0  # 0.04 to 0.12
        elif points == 5:
            increase = random.randint(4, 14) / 100.0  # 0.04 to 0.14
        else:
            increase = random.randint(4, 14) / 100.0  # Default to 5-point range
    else:  # scrimmages
        if points == 1:
            increase = random.randint(1, 3) / 100.0  # 0.01 to 0.03
        elif points == 2:
            increase = random.randint(2, 5) / 100.0  # 0.02 to 0.05
        elif points == 3:
            increase = random.randint(3, 8) / 100.0  # 0.03 to 0.08
        elif points == 4:
            increase = random.randint(3, 9) / 100.0  # 0.03 to 0.09
        elif points == 5:
            increase = random.randint(3, 10) / 100.0  # 0.03 to 0.10
        else:
            increase = random.randint(3, 10) / 100.0  # Default to 5-point range
    
    final_increase = increase
    
    # Apply focus amplifier if rebound_modifier is amplified by the selected focus
    if _should_amplify_team_attr("rebound_modifier", archetype, sub_option):
        focus_multiplier = random.choice([1.5, 1.6, 1.7, 1.8])
        final_increase = final_increase * focus_multiplier
    
    # Apply to team
    current_val = team.get("rebound_modifier", 0.2)  # Default to 0.2 (center)
    team["rebound_modifier"] = current_val + final_increase
    
    # Clamp to valid range [0.0, 0.4]
    team["rebound_modifier"] = max(
        TEAM_ATTR_CLAMPS["rebound_modifier"][0],
        min(TEAM_ATTR_CLAMPS["rebound_modifier"][1], team["rebound_modifier"])
    )


def _apply_shot_threshold_training(team: dict, points: int, archetype: Optional[str] = None, sub_option: Optional[str] = None):
    """
    Apply training points to shot_threshold (decreases threshold, lower is better).
    
    Logic:
    - 1 point: -= random.randint(5, 15)
    - 2 points: -= random.randint(10, 20)
    - 3 points: -= random.randint(10, 30)
    - 4 points: -= random.randint(10, 35)
    - 5 points: -= random.randint(10, 40)
    - Amplifier: *= random.choice([1.3, 1.4, 1.5, 1.6]) (only if "authoritarian-discipline" or "culture-builder-confidence" focus is selected)
    """
    if points == 0:
        return
    
    # Get base decrease
    if points == 1:
        decrease = random.randint(5, 15)
    elif points == 2:
        decrease = random.randint(10, 20)
    elif points == 3:
        decrease = random.randint(10, 30)
    elif points == 4:
        decrease = random.randint(10, 35)
    elif points == 5:
        decrease = random.randint(10, 40)
    else:
        decrease = random.randint(10, 40)
    
    # Apply amplifier (multiply) - only if specific coaching focus is selected
    final_decrease = decrease
    if sub_option in ["authoritarian-discipline", "culture-builder-confidence"]:
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
        return attr in ["BH"]  # Amplifies BH, fight, discipline
    elif sub_option == "authoritarian-rebounding":
        return attr == "RB"  # Amplifies RB, rebound_modifier
    elif sub_option == "authoritarian-teamwork":
        return attr in ["PS", "IQ"]  # Amplifies PS, IQ, Motion Play Effectiveness Scores, Zone Defense Effectiveness Scores
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
        return team_attr in ["fight", "discipline"]  # Amplifies BH, fight, discipline
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
    - 2: random.choice([1, 1, 1.05, 1.1])
    - 3: random.choice([1, 1.05, 1.1])
    - 4: random.choice([1, 1.05, 1.1, 1.1]), and team chemistry += random.randint(-1,1), discipline += random.randint(-2,0), fight += random.randint(-2,0)
    - 5: random.choice([1, 1.05, 1.1, 1.15]), and team chemistry += random.randint(-3,3), discipline += random.randint(-3,-1), fight += random.randint(-3,-1)
    
    Note: Only applies to positive increments (gains), not losses.
    Calculates change from original baseline, if positive, multiplies the increment by multiplier.
    """
    if breaks_points == 0:
        multiplier = random.choice([0.85, 0.9, 0.95])
    elif breaks_points == 1:
        multiplier = random.choice([0.9, 0.95, 1, 1, 1])
    elif breaks_points == 2:
        multiplier = random.choice([1, 1, 1.05, 1.1])
    elif breaks_points == 3:
        multiplier = random.choice([1, 1.05, 1.1])
    elif breaks_points == 4:
        multiplier = random.choice([1, 1.05, 1.1, 1.1])
        # Also adjust team chemistry, discipline, and fight
        team["team_chemistry"] += random.randint(-1, 1)
        team["team_chemistry"] = max(
            TEAM_ATTR_CLAMPS["team_chemistry"][0],
            min(TEAM_ATTR_CLAMPS["team_chemistry"][1], team["team_chemistry"])
        )
        if "discipline" in team:
            team["discipline"] += random.randint(-2, 0)
            team["discipline"] = max(
                TEAM_ATTR_CLAMPS["discipline"][0],
                min(TEAM_ATTR_CLAMPS["discipline"][1], team["discipline"])
            )
        if "fight" in team:
            team["fight"] += random.randint(-2, 0)
            team["fight"] = max(
                TEAM_ATTR_CLAMPS["fight"][0],
                min(TEAM_ATTR_CLAMPS["fight"][1], team["fight"])
            )
    elif breaks_points == 5:
        multiplier = random.choice([1, 1.05, 1.1, 1.15])
        # Also adjust team chemistry, discipline, and fight
        team["team_chemistry"] += random.randint(-3, 3)
        team["team_chemistry"] = max(
            TEAM_ATTR_CLAMPS["team_chemistry"][0],
            min(TEAM_ATTR_CLAMPS["team_chemistry"][1], team["team_chemistry"])
        )
        if "discipline" in team:
            team["discipline"] += random.randint(-3, -1)
            team["discipline"] = max(
                TEAM_ATTR_CLAMPS["discipline"][0],
                min(TEAM_ATTR_CLAMPS["discipline"][1], team["discipline"])
            )
        if "fight" in team:
            team["fight"] += random.randint(-3, -1)
            team["fight"] = max(
                TEAM_ATTR_CLAMPS["fight"][0],
                min(TEAM_ATTR_CLAMPS["fight"][1], team["fight"])
            )
    else:
        # For breaks > 5, use same as 5
        multiplier = random.choice([1, 1.05, 1.1, 1.15])
        team["team_chemistry"] += random.randint(-3, 3)
        team["team_chemistry"] = max(
            TEAM_ATTR_CLAMPS["team_chemistry"][0],
            min(TEAM_ATTR_CLAMPS["team_chemistry"][1], team["team_chemistry"])
        )
        if "discipline" in team:
            team["discipline"] += random.randint(-3, -1)
            team["discipline"] = max(
                TEAM_ATTR_CLAMPS["discipline"][0],
                min(TEAM_ATTR_CLAMPS["discipline"][1], team["discipline"])
            )
        if "fight" in team:
            team["fight"] += random.randint(-3, -1)
            team["fight"] = max(
                TEAM_ATTR_CLAMPS["fight"][0],
                min(TEAM_ATTR_CLAMPS["fight"][1], team["fight"])
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
            
            # For shot_threshold, a decrease (negative increment) is a positive gain
            if attr_name == "shot_threshold" and increment < 0:
                # Decrease is a positive gain - apply multiplier to make it more negative
                decrease_amount = abs(increment)
                new_decrease = int(decrease_amount * multiplier)
                new_val = original_val - new_decrease
                team[attr_name] = new_val
            elif increment > 0:
                # Only apply to positive increments (for all other attributes)
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
    logger.warning(f"🔋 [NG REDUCTION - SCRIMMAGES] Starting NG reduction for {len(players)} players with {scrimmage_points} scrimmage points")
    
    if scrimmage_points not in [3, 4, 5]:
        logger.warning(f"🔋 [NG REDUCTION - SCRIMMAGES] Skipping - scrimmage_points ({scrimmage_points}) not in [3, 4, 5]")
        return []
    
    # Define reduction lists
    reduce_ng_lists = {
        3: [0, 0.01, 0.01, 0.02],
        4: [0, 0.01, 0.02, 0.02, 0.03],
        5: [0.01, 0.02, 0.03, 0.03, 0.04]
    }
    
    reduced_players = []
    skipped_high_nd = 0
    zero_reductions = 0
    
    for player in players:
        attrs = player.get("attributes", {})
        nd = attrs.get("ND", 0)
        ng = attrs.get("NG", 1.0)
        first_name = player.get("first_name", "")
        last_name = player.get("last_name", "")
        player_name = f"{first_name} {last_name}".strip()
        
        # Determine which list to use based on ND
        if nd > 79:
            # Special handling for high ND players
            if scrimmage_points == 3:
                # Omit them (no reduction)
                logger.warning(f"🔋 [NG REDUCTION - SCRIMMAGES] Skipping {player_name} (ND={nd} > 79, scrimmages=3)")
                skipped_high_nd += 1
                continue
            elif scrimmage_points == 4:
                # Use scrimmages == 3 list
                reduce_ng_list = reduce_ng_lists[3]
                logger.warning(f"🔋 [NG REDUCTION - SCRIMMAGES] {player_name} (ND={nd} > 79) using scrimmages=3 list for scrimmages=4")
            elif scrimmage_points == 5:
                # Use scrimmages == 4 list
                reduce_ng_list = reduce_ng_lists[4]
                logger.warning(f"🔋 [NG REDUCTION - SCRIMMAGES] {player_name} (ND={nd} > 79) using scrimmages=4 list for scrimmages=5")
        else:
            # Normal players use the list for their scrimmage points
            reduce_ng_list = reduce_ng_lists[scrimmage_points]
        
        # Apply reduction
        reduction = random.choice(reduce_ng_list)
        if reduction > 0:
            new_ng = max(0.0, ng - reduction)  # Clamp to 0 minimum
            attrs["NG"] = round(new_ng, 2)
            logger.warning(f"🔋 [NG REDUCTION - SCRIMMAGES] {player_name}: NG {ng:.2f} → {attrs['NG']:.2f} (reduction: -{reduction:.2f}, ND={nd}, list={reduce_ng_list})")
            
            # Track player name for notes
            if player_name:
                reduced_players.append(player_name)
        else:
            zero_reductions += 1
            logger.warning(f"🔋 [NG REDUCTION - SCRIMMAGES] {player_name}: No reduction (rolled 0, ND={nd}, list={reduce_ng_list})")
    
    logger.warning(f"🔋 [NG REDUCTION - SCRIMMAGES] Summary: {len(reduced_players)} players reduced, {skipped_high_nd} skipped (high ND), {zero_reductions} rolled zero reduction")
    
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
    logger.warning(f"🔋 [NG REDUCTION - CONDITIONING] Starting NG reduction for {len(players)} players with {conditioning_points} conditioning points")
    
    if conditioning_points not in [3, 4, 5]:
        logger.warning(f"🔋 [NG REDUCTION - CONDITIONING] Skipping - conditioning_points ({conditioning_points}) not in [3, 4, 5]")
        return []
    
    # Define reduction lists (same as scrimmages)
    reduce_ng_lists = {
        3: [0, 0.01, 0.01, 0.02],
        4: [0, 0.01, 0.02, 0.02, 0.03],
        5: [0.01, 0.02, 0.03, 0.03, 0.04]
    }
    
    reduced_players = []
    skipped_high_nd = 0
    zero_reductions = 0
    
    for player in players:
        attrs = player.get("attributes", {})
        nd = attrs.get("ND", 0)
        ng = attrs.get("NG", 1.0)
        first_name = player.get("first_name", "")
        last_name = player.get("last_name", "")
        player_name = f"{first_name} {last_name}".strip()
        
        # Determine which list to use based on ND
        if nd > 79:
            # Special handling for high ND players
            if conditioning_points == 3:
                # Omit them (no reduction)
                logger.warning(f"🔋 [NG REDUCTION - CONDITIONING] Skipping {player_name} (ND={nd} > 79, conditioning=3)")
                skipped_high_nd += 1
                continue
            elif conditioning_points == 4:
                # Use conditioning == 3 list
                reduce_ng_list = reduce_ng_lists[3]
                logger.warning(f"🔋 [NG REDUCTION - CONDITIONING] {player_name} (ND={nd} > 79) using conditioning=3 list for conditioning=4")
            elif conditioning_points == 5:
                # Use conditioning == 4 list
                reduce_ng_list = reduce_ng_lists[4]
                logger.warning(f"🔋 [NG REDUCTION - CONDITIONING] {player_name} (ND={nd} > 79) using conditioning=4 list for conditioning=5")
        else:
            # Normal players use the list for their conditioning points
            reduce_ng_list = reduce_ng_lists[conditioning_points]
        
        # Apply reduction
        reduction = random.choice(reduce_ng_list)
        if reduction > 0:
            new_ng = max(0.0, ng - reduction)  # Clamp to 0 minimum
            attrs["NG"] = round(new_ng, 2)
            logger.warning(f"🔋 [NG REDUCTION - CONDITIONING] {player_name}: NG {ng:.2f} → {attrs['NG']:.2f} (reduction: -{reduction:.2f}, ND={nd}, list={reduce_ng_list})")
            
            # Track player name for notes
            if player_name:
                reduced_players.append(player_name)
        else:
            zero_reductions += 1
            logger.warning(f"🔋 [NG REDUCTION - CONDITIONING] {player_name}: No reduction (rolled 0, ND={nd}, list={reduce_ng_list})")
    
    logger.warning(f"🔋 [NG REDUCTION - CONDITIONING] Summary: {len(reduced_players)} players reduced, {skipped_high_nd} skipped (high ND), {zero_reductions} rolled zero reduction")
    
    return reduced_players


def _apply_pre_training_effectiveness_decay(plays_data: Dict) -> Dict:
    """
    Reduce all plays' effectiveness scores by 5-15 before training.
    Only applies to plays with effectiveness > 0.
    Minimum value is 0 (cannot be negative).
    
    Returns:
        Updated plays_data dict
    """
    updated_plays = plays_data.copy() if plays_data else {}
    
    for play_name, play_data in updated_plays.items():
        if isinstance(play_data, dict):
            current_effectiveness = play_data.get("effectiveness", 0)
            if current_effectiveness > 0:
                decay = random.randint(5, 15)
                new_effectiveness = max(0, current_effectiveness - decay)
                play_data["effectiveness"] = new_effectiveness
                logger.warning(f"📉 [PLAY DECAY] {play_name}: {current_effectiveness} → {new_effectiveness} (decay: -{decay})")
    
    return updated_plays


def _apply_pre_training_defense_decay(scouting_data: Dict) -> Dict:
    """
    Reduce all defenses' effectiveness scores by 5-15 before training.
    Only applies to defenses with effectiveness > 0.
    Minimum value is 0 (cannot be negative).
    
    Returns:
        Updated scouting_data dict
    """
    updated_scouting_data = scouting_data.copy() if scouting_data else {}
    
    if "defense" in updated_scouting_data:
        for defense_name, defense_data in updated_scouting_data["defense"].items():
            if isinstance(defense_data, dict):
                current_effectiveness = defense_data.get("effectiveness", 0)
                if current_effectiveness > 0:
                    decay = random.randint(5, 15)
                    new_effectiveness = max(0, current_effectiveness - decay)
                    defense_data["effectiveness"] = new_effectiveness
                    logger.warning(f"📉 [DEFENSE DECAY] {defense_name}: {current_effectiveness} → {new_effectiveness} (decay: -{decay})")
    
    return updated_scouting_data


def apply_play_defense_training(
    plays_data: Dict,
    scouting_data: Dict,
    allocations: Dict,
    playbook_training_mode: str,
    strategy_settings: Dict,
    playbook_settings: Dict,
    coaching_focus: Optional[str] = None
) -> Tuple[Dict, Dict]:
    """
    Apply training to plays and defenses based on training mode and settings.
    
    Args:
        plays_data: Dict of plays with effectiveness/momentum
        scouting_data: Dict of scouting data with defense effectiveness/momentum
        allocations: Training point allocations
        playbook_training_mode: "current-playbooks", "all-plays-even", or "custom"
        strategy_settings: Game plan strategy settings (offense, defense, inside, outside, attack, etc.)
        playbook_settings: Playbook percentage settings
        coaching_focus: Optional coaching focus for targeted training
    
    Returns:
        Tuple of (updated_plays, updated_scouting_data)
    """
    import math
    
    updated_plays = plays_data.copy() if plays_data else {}
    updated_scouting_data = scouting_data.copy() if scouting_data else {}
    
    # Get offense and defense install points
    team_drills = allocations.get("team_drills", {})
    offense_install = team_drills.get("team_offense", {}).get("install", 0)
    defense_install = team_drills.get("team_defense", {}).get("install", 0)
    
    # Calculate total playPoints for offense and defense
    offense_play_points = 0
    defense_play_points = 0
    
    if offense_install == 1:
        offense_play_points = random.randint(80, 120)
    elif offense_install == 2:
        offense_play_points = random.randint(100, 150)
    elif offense_install == 3:
        offense_play_points = random.randint(150, 200)
    elif offense_install == 4:
        offense_play_points = random.randint(150, 220)
    elif offense_install == 5:
        offense_play_points = random.randint(150, 250)
    
    if defense_install == 1:
        defense_play_points = random.randint(80, 120)
    elif defense_install == 2:
        defense_play_points = random.randint(100, 150)
    elif defense_install == 3:
        defense_play_points = random.randint(150, 200)
    elif defense_install == 4:
        defense_play_points = random.randint(150, 220)
    elif defense_install == 5:
        defense_play_points = random.randint(150, 250)
    
    # Apply Systems Coach focus multiplier to playPoints if applicable
    if coaching_focus:
        parts = coaching_focus.split("-", 1)
        archetype = parts[0] if len(parts) > 0 else None
        sub_option = parts[1] if len(parts) > 1 else None
        
        if sub_option == "systems-coach-offense" and offense_play_points > 0:
            focus_multiplier = random.choice([1.5, 1.6, 1.7, 1.8])
            offense_play_points = int(offense_play_points * focus_multiplier)
            logger.warning(f"🎯 [SYSTEMS COACH - OFFENSE] Applied {focus_multiplier}x multiplier to offense playPoints: {offense_play_points}")
        
        elif sub_option == "systems-coach-defense" and defense_play_points > 0:
            focus_multiplier = random.choice([1.5, 1.6, 1.7, 1.8])
            defense_play_points = int(defense_play_points * focus_multiplier)
            logger.warning(f"🎯 [SYSTEMS COACH - DEFENSE] Applied {focus_multiplier}x multiplier to defense playPoints: {defense_play_points}")
    
    logger.warning(f"📚 [TRAINING] Offense playPoints: {offense_play_points}, Defense playPoints: {defense_play_points}")
    
    # Apply offense training
    if offense_play_points > 0:
        logger.warning(f"📚 [TRAINING] Applying offense training with {offense_play_points} points")
        updated_plays = _apply_offense_play_training(
            updated_plays,
            offense_play_points,
            playbook_training_mode,
            strategy_settings,
            playbook_settings
        )
    
    # Apply defense training
    if defense_play_points > 0:
        logger.warning(f"📚 [TRAINING] Applying defense training with {defense_play_points} points")
        updated_scouting_data = _apply_defense_training(
            updated_scouting_data,
            defense_play_points,
            playbook_training_mode,
            strategy_settings,
            playbook_settings
        )
    
    return updated_plays, updated_scouting_data


def _apply_offense_play_training(
    plays_data: Dict,
    total_points: int,
    playbook_training_mode: str,
    strategy_settings: Dict,
    playbook_settings: Dict
) -> Dict:
    """
    Apply training points to offensive plays.
    
    Args:
        plays_data: Dict of plays with effectiveness/momentum
        total_points: Total training points to distribute
        playbook_training_mode: "current-playbooks", "all-plays-even", or "custom"
        strategy_settings: Game plan strategy settings (used for inside/outside/attack split)
        playbook_settings: Playbook percentage settings
    
    Returns:
        Updated plays_data dict
    """
    import math
    
    updated_plays = plays_data.copy()
    
    logger.warning(f"🎯 [PLAY TRAINING] Starting offense play training with {len(updated_plays)} plays")
    logger.warning(f"🎯 [PLAY TRAINING] Total points: {total_points}, mode: {playbook_training_mode}")
    logger.warning(f"🎯 [PLAY TRAINING] Plays data structure: {list(updated_plays.keys())[:5] if updated_plays else 'empty'}")
    
    # Check if we should use playbook settings or default to even distribution
    use_playbooks = (
        playbook_training_mode == "current-playbooks" and
        playbook_settings and
        strategy_settings
    )
    
    if not use_playbooks or playbook_training_mode == "all-plays-even":
        # Even distribution across ALL plays (motion AND set plays)
        # plays_data is a dict where keys are play names and values are play data
        all_plays = []
        for play_name, play_data in updated_plays.items():
            if isinstance(play_data, dict):
                all_plays.append((play_name, play_data))
        
        logger.warning(f"🎯 [PLAY TRAINING] Found {len(all_plays)} total plays for even distribution (all-plays-even mode)")
        
        if all_plays:
            points_per_play = math.floor(total_points / len(all_plays))
            remainder = total_points - (points_per_play * len(all_plays))
            
            for i, (play_name, play_data) in enumerate(all_plays):
                points = points_per_play + (1 if i < remainder else 0)
                old_effectiveness = play_data.get("effectiveness", 0)
                new_effectiveness = old_effectiveness + points
                updated_plays[play_name]["effectiveness"] = new_effectiveness
                play_type = play_data.get("play_type", "unknown")
                logger.warning(f"🎯 [PLAY TRAINING] {play_name} ({play_type}): {old_effectiveness} → {new_effectiveness} (+{points})")
    else:
        # Use playbook settings with layered filtering
        # Filter 1: strategy_settings["offense"] determines motion/set split
        offense_setting = strategy_settings.get("offense", 2)  # Default to 50/50
        
        if offense_setting == 0:
            motion_pct = 1.0
            set_pct = 0.0
        elif offense_setting == 1:
            motion_pct = 0.75
            set_pct = 0.25
        elif offense_setting == 2:
            motion_pct = 0.5
            set_pct = 0.5
        elif offense_setting == 3:
            motion_pct = 0.25
            set_pct = 0.75
        else:  # offense_setting == 4
            motion_pct = 0.0
            set_pct = 1.0
        
        motion_points = math.floor(total_points * motion_pct)
        set_points = total_points - motion_points
        
        # 🔍 DEBUG: Log motion/set split
        logger.warning(f"🔍 [PLAY TRAINING DEBUG] Motion/Set split:")
        logger.warning(f"   - total_points: {total_points}")
        logger.warning(f"   - motion_pct: {motion_pct}, motion_points: {motion_points}")
        logger.warning(f"   - set_pct: {set_pct}, set_points: {set_points}")
        logger.warning(f"   - strategy_settings['offense']: {strategy_settings.get('offense') if strategy_settings else 'N/A'}")
        
        # Distribute motion points
        if motion_points > 0:
            motion_playbook = playbook_settings.get("motion", {})
            motion_plays = []
            for play_name, play_data in updated_plays.items():
                if isinstance(play_data, dict) and play_data.get("play_type") == "motion":
                    motion_plays.append((play_name, play_data))
            
            logger.warning(f"🎯 [PLAY TRAINING] Motion points: {motion_points}, found {len(motion_plays)} motion plays")
            logger.warning(f"🎯 [PLAY TRAINING] Motion playbook settings: {motion_playbook}")
            
            # Calculate total percentage for motion plays in playbook
            total_motion_pct = sum(motion_playbook.values())
            
            if total_motion_pct > 0:
                for play_name, play_data in motion_plays:
                    play_pct = motion_playbook.get(play_name, 0) / total_motion_pct
                    points = math.floor(motion_points * play_pct)
                    if points > 0:
                        old_effectiveness = play_data.get("effectiveness", 0)
                        new_effectiveness = old_effectiveness + points
                        updated_plays[play_name]["effectiveness"] = new_effectiveness
                        logger.warning(f"🎯 [PLAY TRAINING] {play_name}: {old_effectiveness} → {new_effectiveness} (+{points}, {play_pct*100:.1f}%)")
            else:
                # No playbook percentages, distribute evenly
                points_per_play = math.floor(motion_points / len(motion_plays)) if motion_plays else 0
                remainder = motion_points - (points_per_play * len(motion_plays)) if motion_plays else 0
                for i, (play_name, play_data) in enumerate(motion_plays):
                    points = points_per_play + (1 if i < remainder else 0)
                    old_effectiveness = play_data.get("effectiveness", 0)
                    new_effectiveness = old_effectiveness + points
                    updated_plays[play_name]["effectiveness"] = new_effectiveness
                    logger.warning(f"🎯 [PLAY TRAINING] {play_name}: {old_effectiveness} → {new_effectiveness} (+{points}, even dist)")
        
        # Distribute set play points
        if set_points > 0:
            # Filter 2: strategy_settings determine Inside/Outside/Attack split
            inside_setting = strategy_settings.get("inside", 2)
            outside_setting = strategy_settings.get("outside", 2)
            attack_setting = strategy_settings.get("attack", 2)
            
            # 🔍 DEBUG: Log set play distribution
            logger.warning(f"🔍 [SET PLAY TRAINING DEBUG] set_points: {set_points}")
            logger.warning(f"🔍 [SET PLAY TRAINING DEBUG] strategy_settings: inside={inside_setting}, outside={outside_setting}, attack={attack_setting}")
            
            total_focus = inside_setting + outside_setting + attack_setting
            if total_focus == 0:
                # Default to even split
                inside_pct = 1.0 / 3.0
                outside_pct = 1.0 / 3.0
                attack_pct = 1.0 / 3.0
            else:
                inside_pct = inside_setting / total_focus
                outside_pct = outside_setting / total_focus
                attack_pct = attack_setting / total_focus
            
            inside_points = math.floor(set_points * inside_pct)
            outside_points = math.floor(set_points * outside_pct)
            attack_points = set_points - inside_points - outside_points
            
            # Distribute points for each focus
            for focus, focus_points in [("inside", inside_points), ("outside", outside_points), ("attack", attack_points)]:
                if focus_points > 0:
                    set_playbook_key = f"set_play_{focus}"
                    set_playbook = playbook_settings.get(set_playbook_key, {})
                    
                    # 🔍 DEBUG: Log set playbook lookup
                    logger.warning(f"🔍 [SET PLAY TRAINING DEBUG] {focus} focus:")
                    logger.warning(f"   - focus_points: {focus_points}")
                    logger.warning(f"   - set_playbook_key: '{set_playbook_key}'")
                    logger.warning(f"   - set_playbook found: {bool(set_playbook)}")
                    logger.warning(f"   - set_playbook keys: {list(set_playbook.keys()) if set_playbook else 'EMPTY'}")
                    
                    set_plays = []
                    # 🔍 DEBUG: First, log all set plays and their play_focus values
                    all_set_plays = []
                    for play_name, play_data in updated_plays.items():
                        if isinstance(play_data, dict) and play_data.get("play_type") == "set_play":
                            all_set_plays.append((play_name, play_data.get("play_focus", "MISSING")))
                            if play_data.get("play_focus") == focus:
                                set_plays.append((play_name, play_data))
                    
                    if all_set_plays:
                        logger.warning(f"🔍 [SET PLAY TRAINING DEBUG] All set plays in plays_data: {[(name, focus) for name, focus in all_set_plays]}")
                    
                    logger.warning(f"🎯 [PLAY TRAINING] {focus} focus points: {focus_points}, found {len(set_plays)} set plays")
                    if set_plays:
                        logger.warning(f"🔍 [SET PLAY TRAINING DEBUG] Set plays found: {[name for name, _ in set_plays]}")
                    elif all_set_plays:
                        logger.warning(f"⚠️ [SET PLAY TRAINING DEBUG] No set plays matched focus '{focus}'! Available focuses: {set([f for _, f in all_set_plays])}")
                    
                    # Calculate total percentage for set plays in this focus
                    total_set_pct = sum(set_playbook.values())
                    logger.warning(f"🔍 [SET PLAY TRAINING DEBUG] total_set_pct: {total_set_pct}")
                    
                    if total_set_pct > 0:
                        for play_name, play_data in set_plays:
                            play_pct = set_playbook.get(play_name, 0) / total_set_pct
                            points = math.floor(focus_points * play_pct)
                            if points > 0:
                                old_effectiveness = play_data.get("effectiveness", 0)
                                new_effectiveness = old_effectiveness + points
                                updated_plays[play_name]["effectiveness"] = new_effectiveness
                                logger.warning(f"🎯 [PLAY TRAINING] {play_name}: {old_effectiveness} → {new_effectiveness} (+{points}, {play_pct*100:.1f}%)")
                    else:
                        # No playbook percentages, distribute evenly
                        points_per_play = math.floor(focus_points / len(set_plays)) if set_plays else 0
                        remainder = focus_points - (points_per_play * len(set_plays)) if set_plays else 0
                        for i, (play_name, play_data) in enumerate(set_plays):
                            points = points_per_play + (1 if i < remainder else 0)
                            old_effectiveness = play_data.get("effectiveness", 0)
                            new_effectiveness = old_effectiveness + points
                            updated_plays[play_name]["effectiveness"] = new_effectiveness
                            logger.warning(f"🎯 [PLAY TRAINING] {play_name}: {old_effectiveness} → {new_effectiveness} (+{points}, even dist)")
    
    return updated_plays


def _apply_defense_training(
    scouting_data: Dict,
    total_points: int,
    playbook_training_mode: str,
    strategy_settings: Dict,
    playbook_settings: Dict
) -> Dict:
    """
    Apply training points to defensive plays.
    
    Returns:
        Updated scouting_data dict
    """
    import math
    
    updated_scouting_data = scouting_data.copy() if scouting_data else {}
    
    # Ensure defense structure exists
    if "defense" not in updated_scouting_data:
        updated_scouting_data["defense"] = {}
    
    defense_data = updated_scouting_data["defense"]
    
    # Check if we should use playbook settings or default to even distribution
    use_playbooks = (
        playbook_training_mode == "current-playbooks" and
        playbook_settings and
        strategy_settings
    )
    
    if not use_playbooks or playbook_training_mode == "all-plays-even":
        # Even distribution across all defensive plays (Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone)
        defense_types = ["Man", "2-3 Zone", "3-2 Zone", "1-3-1 Zone"]
        valid_defenses = [d for d in defense_types if d in defense_data]
        
        if valid_defenses:
            points_per_defense = math.floor(total_points / len(valid_defenses))
            remainder = total_points - (points_per_defense * len(valid_defenses))
            
            for i, defense_name in enumerate(valid_defenses):
                points = points_per_defense + (1 if i < remainder else 0)
                if defense_name in defense_data:
                    old_eff = defense_data[defense_name].get("effectiveness", 0)
                    defense_data[defense_name]["effectiveness"] = old_eff + points
                    logger.warning(f"📚 [TRAINING] Defense '{defense_name}': effectiveness {old_eff} → {old_eff + points} (+{points} points, even distribution)")
    else:
        # Use playbook settings with layered filtering
        # Filter 1: strategy_settings["defense"] determines man/zone split
        defense_setting = strategy_settings.get("defense", 2)  # Default to 50/50
        
        if defense_setting == 0:
            man_pct = 1.0
            zone_pct = 0.0
        elif defense_setting == 1:
            man_pct = 0.75
            zone_pct = 0.25
        elif defense_setting == 2:
            man_pct = 0.5
            zone_pct = 0.5
        elif defense_setting == 3:
            man_pct = 0.25
            zone_pct = 0.75
        else:  # defense_setting == 4
            man_pct = 0.0
            zone_pct = 1.0
        
        man_points = math.floor(total_points * man_pct)
        zone_points = total_points - man_points
        
        # Distribute man defense points
        if man_points > 0:
            # For now, we only have one man defense ("Man")
            # When more man defenses are added, we can use playbook_settings.get("man_defense", {})
            if "Man" in defense_data:
                old_eff = defense_data["Man"].get("effectiveness", 0)
                defense_data["Man"]["effectiveness"] = old_eff + man_points
                logger.warning(f"📚 [TRAINING] Defense 'Man': effectiveness {old_eff} → {old_eff + man_points} (+{man_points} points)")
        
        # Distribute zone defense points
        if zone_points > 0:
            zone_playbook = playbook_settings.get("zone_defense", {})
            zone_defenses = ["2-3 Zone", "3-2 Zone", "1-3-1 Zone"]
            valid_zone_defenses = [d for d in zone_defenses if d in defense_data]
            
            # Calculate total percentage for zone defenses in playbook
            total_zone_pct = sum(zone_playbook.values())
            
            if total_zone_pct > 0:
                for defense_name in valid_zone_defenses:
                    defense_pct = zone_playbook.get(defense_name, 0) / total_zone_pct
                    points = math.floor(zone_points * defense_pct)
                    if points > 0:
                        old_eff = defense_data[defense_name].get("effectiveness", 0)
                        defense_data[defense_name]["effectiveness"] = old_eff + points
                        logger.warning(f"📚 [TRAINING] Zone defense '{defense_name}': effectiveness {old_eff} → {old_eff + points} (+{points} points, {defense_pct*100:.1f}% of {zone_points})")
            else:
                # No playbook percentages, distribute evenly
                points_per_defense = math.floor(zone_points / len(valid_zone_defenses)) if valid_zone_defenses else 0
                remainder = zone_points - (points_per_defense * len(valid_zone_defenses)) if valid_zone_defenses else 0
                for i, defense_name in enumerate(valid_zone_defenses):
                    points = points_per_defense + (1 if i < remainder else 0)
                    old_eff = defense_data[defense_name].get("effectiveness", 0)
                    defense_data[defense_name]["effectiveness"] = old_eff + points
                    logger.warning(f"📚 [TRAINING] Zone defense '{defense_name}': effectiveness {old_eff} → {old_eff + points} (+{points} points, even distribution)")
    
    return updated_scouting_data

