"""
New Training Execution System - Implements logic from training_execution.md brief

This module implements the new training execution system with:
- Pre-training conditions
- New training point application logic
- Clamps and validation
- Training report generation
"""

import math
import random
import logging
from typing import List, Dict, Tuple, Optional, Any
from BackEnd.constants import ALL_ATTRS
from BackEnd.constants.momentum import MO_MIN, MO_MAX
from BackEnd.utils.playbook_settings_utils import resolve_playbook_percentage
from BackEnd.utils.defense_identity import (
    DEFENSE_ID_TO_PLAYBOOK_ZONE_KEY,
    PLAYBOOK_MAN_KEY_TO_DEFENSE_ID,
    PLAYBOOK_ZONE_KEY_TO_DEFENSE_ID,
    _SCOUTING_DEFENSE_LEGACY_KEYS_BY_CANONICAL,
    canonical_scouting_defense_key,
    defense_display_name,
)
from BackEnd.utils.team_play_utils import iter_team_plays

logger = logging.getLogger(__name__)


def _normalize_scouting_defense_keys_for_training(scouting_data: Optional[Dict]) -> Dict:
    """
    Fold legacy `scouting_data['defense']` keys (e.g. Man, 2-3 Zone) onto canonical slugs before
    install training. `_apply_defense_training` only writes to `man` / `*-zone` keys; without this,
    FTD rows keyed by display names receive no effectiveness gains.
    """
    if not scouting_data or not isinstance(scouting_data, dict):
        return scouting_data or {}
    defense_block = scouting_data.get("defense")
    if not isinstance(defense_block, dict) or not defense_block:
        return dict(scouting_data)
    from BackEnd.models.team_manager import _remap_defense_scouting_keys_for_merge

    out = dict(scouting_data)
    out["defense"] = _remap_defense_scouting_keys_for_merge(defense_block)
    return out


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
    skip_pre_training_depreciation: bool = False,
    coaching_focus_custom_by_player: Optional[Dict[str, List[str]]] = None,
    training_playbook_focus: Optional[Dict[str, List[str]]] = None,
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
    scouting_data = _normalize_scouting_defense_keys_for_training(scouting_data)
    
    logger.warning(f"📚 [TRAINING] Initial plays_data keys: {list(plays_data.keys())}")
    logger.warning(f"📚 [TRAINING] Initial scouting_data keys: {list(scouting_data.keys()) if scouting_data else 'None'}")
    
    # Store original effectiveness values BEFORE any changes
    original_plays_effectiveness = {}
    for play_key, play_data, display_name in iter_team_plays(plays_data):
        eff = play_data.get("effectiveness", 0)
        original_key = play_data.get("play_id") or play_key
        original_plays_effectiveness[original_key] = eff
        logger.warning(f"📚 [TRAINING] Play '{display_name}': initial effectiveness = {eff}, play_type = {play_data.get('play_type', 'unknown')}")
    
    original_defenses_effectiveness = {}
    if scouting_data and "defense" in scouting_data:
        for defense_name, defense_data in scouting_data["defense"].items():
            if isinstance(defense_data, dict):
                eff = defense_data.get("effectiveness", 0)
                original_defenses_effectiveness[defense_name] = eff
                logger.warning(f"📚 [TRAINING] Defense '{defense_name}': initial effectiveness = {eff}")
    
    logger.warning(f"📚 [TRAINING] Total plays tracked: {len(original_plays_effectiveness)}")
    logger.warning(f"📚 [TRAINING] Total defenses tracked: {len(original_defenses_effectiveness)}")
    
    # Defense effectiveness share-decay runs at EOG (see build_eog_defensive_effectiveness_decay_ftd_updates); offense CMD at EOG separately.

    # Step 1: Apply pre-training conditions
    # Skip for first training (training camp) in franchise mode
    if not skip_pre_training_depreciation:
        players, team = apply_pre_training_conditions(players, team)
    else:
        logger.warning("⏭️ [TRAINING] Skipping pre-training conditions (first training/training camp)")
    
    # Step 2: Apply training points (pass original baselines for report calculation)
    players, team, training_report = apply_training_points(
        players, team, allocations, coaching_focus,
        is_training_camp=skip_pre_training_depreciation,
        original_baselines=original_player_baselines,
        original_team_baseline=original_team_baseline,
        coaching_focus_custom_by_player=coaching_focus_custom_by_player,
    )
    
    # Step 3: Apply play/defense training
    updated_plays, updated_scouting_data = apply_play_defense_training(
        plays_data,
        scouting_data,
        allocations,
        playbook_training_mode,
        strategy_settings,
        playbook_settings,
        coaching_focus,
        training_playbook_focus=training_playbook_focus,
    )
    
    # Calculate effectiveness changes for training report
    plays_effectiveness_changes = {}
    for play_key, play_data, _display_name in iter_team_plays(updated_plays):
        change_key = play_data.get("play_id") or play_key
        if change_key in original_plays_effectiveness:
            new_eff = play_data.get("effectiveness", 0)
            plays_effectiveness_changes[change_key] = new_eff - original_plays_effectiveness[change_key]
    
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

    # Structured Training Notes (Training_System.md → Training Notes Section); replaces flat energy-only list
    _legacy_energy = list(training_report.get("training_notes", []))
    from BackEnd.models.training_notes import build_structured_training_report_notes

    training_report["training_notes"] = build_structured_training_report_notes(
        is_training_camp=skip_pre_training_depreciation,
        players=players,
        original_player_baselines=original_player_baselines,
        team=team,
        plays_data=updated_plays,
        scouting_data=updated_scouting_data,
        legacy_energy_notes=_legacy_energy,
        training_camp_physique_notes=training_report.get("training_camp_physique_notes"),
    )

    return players, team, updated_plays, updated_scouting_data, training_report

# Player attributes excluding EM, MO, NG
TRAINABLE_PLAYER_ATTRS = [attr for attr in ALL_ATTRS if attr not in ["EM", "MO", "NG"]]

# Player Maximizer (top 3 / attributes 4–6 / custom picks): rank by anchor; CH excluded (team chemistry not a maximizer target)
PLAYER_MAXIMIZER_RANKING_ATTRS = tuple(a for a in TRAINABLE_PLAYER_ATTRS if a != "CH")

# Primary position from max RT → three focus attrs (Player Maximizer / Positional Focus)
POSITIONAL_FOCUS_ATTRS_BY_PRIMARY: Dict[str, Tuple[str, str, str]] = {
    "PG": ("PS", "BH", "IQ"),
    "SG": ("SH", "OD", "AG"),
    "SF": ("SC", "ST", "AG"),
    "PF": ("RB", "ID", "ST"),
    "C": ("SC", "ID", "ST"),
}
PRIMARY_POSITION_RT_ORDER: Tuple[str, ...] = ("PG", "SG", "SF", "PF", "C")


def primary_position_from_position_ratings(ratings: Optional[dict]) -> str:
    """Position with highest rating; ties broken by PG → C order."""
    if not ratings:
        return "PG"
    best_val = -1.0
    best_pos = "PG"
    for pos in PRIMARY_POSITION_RT_ORDER:
        raw = ratings.get(pos)
        if raw is None and isinstance(pos, str):
            raw = ratings.get(pos.upper())
        try:
            v = float(raw)
        except (TypeError, ValueError):
            v = 0.0
        if v > best_val:
            best_val = v
            best_pos = pos
    return best_pos


def positional_focus_attrs_for_player(player: dict) -> Tuple[str, str, str]:
    ratings = player.get("position_ratings") or {}
    pos = primary_position_from_position_ratings(ratings)
    return POSITIONAL_FOCUS_ATTRS_BY_PRIMARY.get(pos, POSITIONAL_FOCUS_ATTRS_BY_PRIMARY["PG"])


def normalize_coaching_focus_custom_by_player(
    coaching_focus: Optional[str],
    raw: Any,
    players: List[dict],
) -> Optional[Dict[str, List[str]]]:
    """
    Validate and normalize coaching_focus_custom_by_player for player-maximizer-custom.

    Expect coaching_focus radio value ``player-maximizer-custom``. When active, ``raw`` must be a
    dict mapping each training roster player's id (str) to a list of exactly **three** distinct
    attribute codes, all in PLAYER_MAXIMIZER_RANKING_ATTRS.

    Returns:
        None if focus is not custom (extra raw data is ignored).
        Dict[player_id, [attr_a, attr_b, attr_c]] when focus is custom.

    Raises:
        ValueError: invalid or incomplete payload.
    """
    _, sub = parse_coaching_focus(coaching_focus)
    if sub != "player-maximizer-custom":
        return None
    if not isinstance(raw, dict):
        raise ValueError(
            "Player Maximizer / Custom requires coaching_focus_custom_by_player (object mapping player id to three attributes)."
        )
    allowed = frozenset(PLAYER_MAXIMIZER_RANKING_ATTRS)
    roster_ids = {str(p["_id"]) for p in players if p.get("_id") is not None}
    if not roster_ids:
        raise ValueError("No players on roster for custom focus validation.")

    out: Dict[str, List[str]] = {}
    for pid in roster_ids:
        entry = raw.get(pid)
        if entry is None:
            entry = raw.get(str(pid))
        if not isinstance(entry, (list, tuple)) or len(entry) != 3:
            raise ValueError(
                f"Player Maximizer / Custom: player {pid} must have exactly three attributes (got invalid entry)."
            )
        a0, a1, a2 = str(entry[0]).strip(), str(entry[1]).strip(), str(entry[2]).strip()
        if a0 not in allowed or a1 not in allowed or a2 not in allowed:
            raise ValueError(
                f"Player Maximizer / Custom: player {pid} attributes must be from the allowed ranking set (not CH/EM/MO/NG)."
            )
        if len({a0, a1, a2}) != 3:
            raise ValueError(
                f"Player Maximizer / Custom: player {pid} must pick three different attributes."
            )
        out[pid] = [a0, a1, a2]

    if set(out.keys()) != roster_ids:
        missing = roster_ids - set(out.keys())
        raise ValueError(
            "Player Maximizer / Custom: coaching_focus_custom_by_player must include every roster player "
            f"(missing: {', '.join(sorted(missing))})."
        )

    return out


from BackEnd.constants import TEAM_ATTR_RANGES
TEAM_ATTR_CLAMPS = {
    "shot_threshold": TEAM_ATTR_RANGES["shot_threshold"],
    "discipline": (-10, 10),
    "fight": (-10, 10),
    "rebound_modifier": TEAM_ATTR_RANGES["rebound_modifier"],
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

# Archetype prefixes for coaching focus radio `value` from FrontEnd/static/training.html.
# Order: check multi-word prefixes; "authoritarian" last (authoritarian-discipline, etc.).
COACHING_FOCUS_ARCHETYPE_PREFIXES = (
    "systems-coach",
    "player-maximizer",
    "culture-builder",
    "authoritarian",
)

# Human-facing leaf labels for APIs/reports/logs. Radio/API `value` remains the dict key.
# NOTE: **Authoritarian** `authoritarian-teamwork` = UI **"Teamwork"** (PS/IQ + motion/zone install mult;
# flat **team_chemistry** +1–2; no shared Authoritarian **discipline** flat).
# **Culture Builder** `culture-builder-teamwork` = UI **"Team Building"** (flat **team_chemistry** +1–3 only;
# no shared Culture Builder **fight** flat).
# The shared `-teamwork` suffix on the Culture leaf is legacy for backward compatibility—do not conflate.
COACHING_FOCUS_LEAF_DISPLAY_NAME: Dict[str, str] = {
    "authoritarian-teamwork": "Teamwork",
    "culture-builder-teamwork": "Team Building",
    "player-maximizer-top-3": "Top 3",
    "player-maximizer-attributes-4-6": "Attributes 4–6",
    "player-maximizer-custom": "Custom",
    "player-maximizer-choose-attributes": "Choose Attributes",
    "player-maximizer-positional-focus": "Positional Focus",
}


def coaching_focus_leaf_display_name(sub_option: Optional[str]) -> Optional[str]:
    """Stable UI label for a coaching leaf `value`, if we define one; else None (client may derive)."""
    if not sub_option:
        return None
    return COACHING_FOCUS_LEAF_DISPLAY_NAME.get(sub_option)


def parse_coaching_focus(coaching_focus: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Normalize API/UI coaching_focus into (archetype, sub_option).

    sub_option is the full leaf value (e.g. systems-coach-offense) so it matches
    _should_amplify_player_attr / _should_amplify_team_attr and Systems Coach play training.
    Using split("-", 1) on the raw string breaks multi-word archetypes (systems, coach-offense).

    Returns:
        archetype: e.g. systems-coach, or None if empty input
        sub_option: full radio value when a leaf is selected; None if only archetype header
    """
    if coaching_focus is None:
        return None, None
    raw = str(coaching_focus).strip()
    if not raw:
        return None, None

    for prefix in COACHING_FOCUS_ARCHETYPE_PREFIXES:
        if raw == prefix:
            return prefix, None
        if raw.startswith(prefix + "-"):
            return prefix, raw

    # Unknown / future values: best-effort legacy behavior
    parts = raw.split("-", 1)
    archetype = parts[0] if parts else None
    sub_opt = parts[1] if len(parts) > 1 else None
    return archetype, sub_opt


# Zone defenses that share install training points in _apply_defense_training
TRAINING_ZONE_DEFENSE_NAMES = frozenset({"2-3-zone", "3-2-zone", "1-3-1-zone"})


def _scale_install_training_effectiveness_points(
    points: int,
    multiplier: Optional[float],
    apply_multiplier: bool,
) -> int:
    """
    Scale integer effectiveness (Command) gains from offense/defense install training.
    Used for Authoritarian / Execution (set plays, Man) and Authoritarian / Teamwork (motion, zones).
    """
    if not apply_multiplier or multiplier is None or points <= 0:
        return points
    return int(round(points * multiplier))


# Year-based pre-training decay (min, max) for random decrease per attribute. See Training_System.md.
PRE_TRAINING_DECAY_BY_YEAR = {
    "freshman": (-5, -2),
    "sophomore": (-4, -1),
    "junior": (-3, -1),
    "senior": (-2, 0),
}


def _pre_training_decay_range_for_year(year: str) -> Tuple[int, int]:
    """Return (min, max) for pre-training decay based on player year. Default: junior."""
    key = (year or "").strip().lower()
    return PRE_TRAINING_DECAY_BY_YEAR.get(key, (-3, -1))


def apply_pre_training_conditions(players: List[dict], team: dict) -> Tuple[List[dict], dict]:
    """
    Apply pre-training conditions to players only.
    
    Note: Team attribute decay has been removed. Team attributes are now updated
    at the end of each game via update_team_attributes_after_game() in franchise_routes.py.
    
    Pre-training conditions:
    - Player attributes (excluding EM, MO, NG): += randint(min, max) per player/attribute,
      where (min, max) is year-based: Freshman (-5,-1), Sophomore (-4,-1), Junior (-3,0), Senior (-2,0).
    
    Args:
        players: List of player dicts with attributes
        team: Team dict with team attributes (unchanged, kept for API compatibility)
    
    Returns:
        Tuple of (updated_players, unchanged_team)
    """
    for player in players:
        attrs = player.get("attributes", {})
        year = player.get("year", "")
        decay_min, decay_max = _pre_training_decay_range_for_year(year)
        for attr in TRAINABLE_PLAYER_ATTRS:
            anchor_key = f"anchor_{attr}"
            if anchor_key in attrs:
                decrease = random.randint(decay_min, decay_max)
                attrs[anchor_key] = max(PLAYER_ATTR_CLAMP[0], attrs[anchor_key] + decrease)
                attrs[attr] = attrs[anchor_key]
    
    return players, team


def apply_training_points(
    players: List[dict],
    team: dict,
    allocations: Dict[str, Dict],
    coaching_focus: Optional[str] = None,
    is_training_camp: bool = False,
    original_baselines: Optional[Dict] = None,
    original_team_baseline: Optional[Dict] = None,
    coaching_focus_custom_by_player: Optional[Dict[str, List[str]]] = None,
) -> Tuple[List[dict], dict, Dict]:
    """
    Apply training points to players and team based on allocations.
    
    Args:
        players: List of player dicts with attributes (already have pre-training conditions applied)
        team: Team dict with team attributes (already have pre-training conditions applied)
        allocations: Dict mapping category to allocation data
        coaching_focus: Optional coaching focus; radio `value` from training UI (see parse_coaching_focus)
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
    
    archetype, sub_option = parse_coaching_focus(coaching_focus)
    
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
        "conditioning": ["ND", "CH"],  # Conditioning: ND, CH, (Fight, 0.5x multiplier)
        "free_throws": ["FT"],     # Free Throws: FT, (Team Chemistry, 0.25x multiplier)
        "film_study": ["IQ", "CH"],  # Film Study: IQ, CH, (Team Chemistry, 0.25x multiplier)
    }
    
    # Map drills to team attribute multipliers
    # Format: {category: {subtype: [(team_attr, multiplier)], or for single-value categories: [(team_attr, multiplier)]}
    team_attr_multipliers = {
        "defensive_drills": {
            "inside": [("discipline", 0.25)],   # Inside Defense → Discipline 0.25x
            "outside": [("discipline", 0.25)]   # Outside Defense → Discipline 0.25x
        },
        "technical_drills": {
            "passing": [("discipline", 0.25)],  # Passing → Discipline 0.25x
            "ball_handling": [("discipline", 0.25)]  # Ball Handling → Discipline 0.25x
        },
        "weight_room": {
            "strength": [("fight", 0.5)]  # Strength Training → Fight 0.5x
        },
        "conditioning": [("fight", 0.5)],  # Conditioning → Fight 0.5x
        "free_throws": [("team_chemistry", 0.25)],  # Free Throws → Team Chemistry 0.25x
        "film_study": [("team_chemistry", 0.25)],  # Film Study → Team Chemistry 0.25x
        "scrimmages": [("team_chemistry", 0.25)]  # Scrimmages → Team Chemistry 0.25x
    }
    
    # Track team attribute contributions from multipliers (will sum and apply later)
    team_attr_contributions = {
        "discipline": 0.0,
        "fight": 0.0,
        "team_chemistry": 0.0
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
                                player,
                                attr,
                                points,
                                archetype,
                                sub_option,
                                multiplier,
                                player_baselines.get(player["_id"], {}).get(attr),
                                coaching_focus_custom_by_player=coaching_focus_custom_by_player,
                            )
                
                # Track team attribute contributions from multipliers
                if category in team_attr_multipliers:
                    multiplier_list = team_attr_multipliers[category]
                    if isinstance(multiplier_list, dict) and subtype in multiplier_list:
                        for team_attr, mult in multiplier_list[subtype]:
                            team_attr_contributions[team_attr] += points * mult
        elif isinstance(allocation_data, int):
            # Category with single value (e.g., conditioning: 3)
            if isinstance(attr_mapping, list):
                attrs_to_update = attr_mapping
                for attr in attrs_to_update:
                    # Apply multiplier for CH (0.5) in conditioning and film_study
                    multiplier = 0.5 if attr == "CH" and category in ["conditioning", "film_study"] else 1.0
                    for player in players:
                        _apply_player_training_points(
                            player,
                            attr,
                            allocation_data,
                            archetype,
                            sub_option,
                            multiplier,
                            player_baselines.get(player["_id"], {}).get(attr),
                            coaching_focus_custom_by_player=coaching_focus_custom_by_player,
                        )
            
            # Track team attribute contributions from multipliers (single-value categories)
            if category in team_attr_multipliers:
                multiplier_list = team_attr_multipliers[category]
                if isinstance(multiplier_list, list):
                    for team_attr, mult in multiplier_list:
                        team_attr_contributions[team_attr] += allocation_data * mult
    
    # Handle special focus effects that apply to all players
    if sub_option == "culture-builder-inspire":
        # EM/morale lift + MO tick; CH/FT amplification is culture-builder-confidence
        for player in players:
            attrs = player.get("attributes", {})
            em_improvement = random.randint(2, 5)
            mo_improvement = random.randint(1, 2)
            attrs["EM"] = min(100, attrs.get("EM", 0) + em_improvement)
            # MO is bounded to its defined scale [MO_MIN, MO_MAX] (single source
            # of truth in BackEnd/constants/momentum.py).
            attrs["MO"] = max(MO_MIN, min(MO_MAX, attrs.get("MO", 0) + mo_improvement))
            # Update anchors
            attrs["anchor_EM"] = attrs["EM"]
            attrs["anchor_MO"] = attrs["MO"]
    
    if sub_option == "culture-builder-community":
        # Improve EM for all players
        for player in players:
            attrs = player.get("attributes", {})
            # Home crowd band shift is applied at franchise game start via FTD
            # ``pending_community_engagement`` + Home_Crowd_System.md / Training_System.md
            em_improvement = random.randint(1, 2)
            attrs["EM"] = min(100, attrs.get("EM", 0) + em_improvement)
            attrs["anchor_EM"] = attrs["EM"]

    if sub_option == "culture-builder-teamwork":
        # API value `culture-builder-teamwork` = UI **Team Building** (not Authoritarian Teamwork).
        ch_lo, ch_hi = TEAM_ATTR_CLAMPS["team_chemistry"]
        team_ch_bump = random.randint(1, 3)
        cur_ch = team.get("team_chemistry", 0)
        team["team_chemistry"] = max(ch_lo, min(ch_hi, cur_ch + team_ch_bump))

    # Flat team-attribute bonuses/penalties from coaching focus, beyond normal gain amplification.
    # Culture Builder fight bump applies to Inspire / Confidence / Community only — not Team Building.
    if (
        archetype == "culture-builder"
        and sub_option != "culture-builder-teamwork"
        and "fight" in team
    ):
        fight_lo, fight_hi = TEAM_ATTR_CLAMPS["fight"]
        team["fight"] = max(fight_lo, min(fight_hi, team.get("fight", 0) + random.randint(1, 2)))

    # Culture Builder generally trades discipline for morale/culture work; Confidence is excluded.
    if archetype == "culture-builder" and sub_option != "culture-builder-confidence" and "discipline" in team:
        disc_lo, disc_hi = TEAM_ATTR_CLAMPS["discipline"]
        team["discipline"] = max(disc_lo, min(disc_hi, team.get("discipline", 0) + random.randint(-2, -1)))

    # Authoritarian discipline bump applies to Discipline / Rebounding / Execution — not Teamwork.
    if archetype == "authoritarian" and sub_option != "authoritarian-teamwork" and "discipline" in team:
        disc_lo, disc_hi = TEAM_ATTR_CLAMPS["discipline"]
        team["discipline"] = max(disc_lo, min(disc_hi, team.get("discipline", 0) + random.randint(1, 2)))

    # Authoritarian work generally costs fight/energy unless the focus is specifically Rebounding.
    if archetype == "authoritarian" and sub_option != "authoritarian-rebounding" and "fight" in team:
        fight_lo, fight_hi = TEAM_ATTR_CLAMPS["fight"]
        team["fight"] = max(fight_lo, min(fight_hi, team.get("fight", 0) + random.randint(-2, -1)))

    if sub_option == "authoritarian-teamwork":
        ch_lo, ch_hi = TEAM_ATTR_CLAMPS["team_chemistry"]
        ch_bump = random.randint(0, 1)
        cur_ch = team.get("team_chemistry", 0)
        team["team_chemistry"] = max(ch_lo, min(ch_hi, cur_ch + ch_bump))
    
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
    # Docs: Rebounding gives rebound_modifier 0.5 points per drill point.
    if "technical_drills" in normalized_allocations:
        rebounding_points = normalized_allocations["technical_drills"].get("rebounding", 0)
        if rebounding_points is not None:
            # Convert to effective team-attribute points using 0.5x accrual, then round half-up.
            effective_points = int((rebounding_points * 0.5) + 0.5)
            _apply_rebound_modifier_training(
                team, effective_points, archetype, sub_option, source="technical_drills"
            )
    
    # Handle scrimmages (if scrimmages category exists in allocations)
    # Scrimmages: Team Chemistry (0.5x multiplier), Shot Threshold (1 point), Rebounding (0.5x)
    # Note: Scrimmages category may not be in the frontend structure yet
    if "scrimmages" in normalized_allocations:
        scrimmage_points = normalized_allocations["scrimmages"]
        if isinstance(scrimmage_points, int) and scrimmage_points >= 0:
            # Track Team Chemistry contribution (0.5x multiplier) - will be applied with other contributions
            if scrimmage_points > 0 and "scrimmages" in team_attr_multipliers:
                for team_attr, mult in team_attr_multipliers["scrimmages"]:
                    team_attr_contributions[team_attr] += scrimmage_points * mult
            # Apply to Shot Threshold (decreases)
            _apply_shot_threshold_training(team, scrimmage_points, archetype, sub_option)
            # Apply to Rebounding (rebound_modifier) with 0.5x accrual, rounded half-up.
            effective_points = int((scrimmage_points * 0.5) + 0.5)
            _apply_rebound_modifier_training(
                team, effective_points, archetype, sub_option, source="scrimmages"
            )
    
    # Apply team attribute contributions from multipliers
    # Sum all contributions, round (0.5 rounds up, <0.5 rounds down), then apply
    # This must happen BEFORE breaks effect so breaks can multiply these gains
    for team_attr, total_points in team_attr_contributions.items():
        if total_points >= 0:
            # Round: 0.5 rounds up, <0.5 rounds down
            rounded_points = int(total_points + 0.5) if total_points >= 0.5 else int(total_points)
            _apply_team_training_points(team, team_attr, rounded_points, archetype, sub_option)
    
    # Momentum score (amplifier only, from coaching focus)
    # Amplifier: += random.randint(1,5)
    # TODO: Apply when direction is provided on how momentum_score training points are allocated
    
    # Apply breaks effect (multiplies all positive increments, adds Team Chemistry at 4-5 points)
    # This is applied after multiplier contributions so breaks can multiply those gains too
    if "breaks" in normalized_allocations:
        breaks_points = normalized_allocations["breaks"]
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

    # Training Camp bonus (first training only): CH/highest-RT cores, then year-based bonus.
    camp_physique_notes: List[str] = []
    if is_training_camp:
        _apply_training_camp_bonus(players, player_baselines)
        camp_physique_notes = _apply_training_camp_height_weight_bonuses(players)

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
            yr = player.get("year")
            if yr is not None and str(yr).strip():
                changes["year"] = str(yr).strip().lower()
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
            "sub_option": sub_option,
            "leaf_display_name": coaching_focus_leaf_display_name(sub_option),
        },
        "training_notes": training_notes,
        "training_camp_physique_notes": camp_physique_notes,
    }
    
    return players, team, training_report


def _apply_player_training_points(
    player: dict,
    attr: str,
    points: int,
    archetype: Optional[str] = None,
    sub_option: Optional[str] = None,
    multiplier: float = 1.0,
    starting_baseline: Optional[int] = None,
    coaching_focus_custom_by_player: Optional[Dict[str, List[str]]] = None,
):
    """
    Apply training points to a single player attribute.
    
    Base ranges (Player Attributes). See Training_System.md.
    - 0 points: += random.randint(-2, -1)
    - 1 point: += random.randint(0, 1)
    - 2 points: += random.randint(2, 3)
    - 3 points: += random.randint(2, 4)
    - 4 points: += random.randint(3, 5)
    - 5 points: += random.randint(3, 6)
    
    Year-based adjustments: leave minimums as is, only change maximums.
    - Freshman: +5 to max
    - Sophomore: +3 to max
    - Junior: +2 to max
    - Senior: +1 to max
    
    Focus amplifier: Applied based on sub_option selection
    Multiplier: For attributes like CH that get 0.5 multiplier
    """
    attrs = player.get("attributes", {})
    anchor_key = f"anchor_{attr}"
    
    # Get player year: only adjust max. Freshman +5, Sophomore +3, Junior +2, Senior +1.
    year = player.get("year", "").lower() if player.get("year") else ""
    max_adjustment = {"freshman": 5, "sophomore": 3, "junior": 2, "senior": 1}.get(year, 2)
    
    # Base range (min, max) by points. Doc: 0→(-2,-1), 1→(0,1), 2→(2,3), 3→(2,4), 4→(3,5), 5→(3,6)
    if points == 0:
        base_min, base_max = -2, -1
    elif points == 1:
        base_min, base_max = 0, 1
    elif points == 2:
        base_min, base_max = 2, 3
    elif points == 3:
        base_min, base_max = 2, 4
    elif points == 4:
        base_min, base_max = 3, 5
    elif points == 5:
        base_min, base_max = 3, 6
    else:
        base_min, base_max = 3, 6
    
    adjusted_max = base_max + max_adjustment
    increase = random.randint(base_min, adjusted_max)
    
    # Apply multiplier (for CH in conditioning/film_study)
    increase = int(increase * multiplier)

    # If the player started training above 100 in this attribute, positive gains are halved.
    if (starting_baseline or 0) > 100 and increase > 0:
        increase = int(math.floor((increase * 0.5) + 0.5))
    
    # Check if this attribute should be amplified based on focus
    should_amplify = False
    
    # Handle Player Maximizer special cases (top 3 / next 3 / positional / custom)
    if sub_option in ["player-maximizer-top-3", "player-maximizer-attributes-4-6"]:
        # Rank by anchor for PLAYER_MAXIMIZER_RANKING_ATTRS (CH excluded; EM/MO/NG not in list)
        player_attrs = {a: attrs.get(f"anchor_{a}", 0) for a in PLAYER_MAXIMIZER_RANKING_ATTRS}
        sorted_attrs = sorted(
            player_attrs.items(),
            key=lambda x: (-(x[1] if isinstance(x[1], (int, float)) else 0), x[0]),
        )
        
        if sub_option == "player-maximizer-top-3":
            # Top 3 attributes
            top_attrs = [a[0] for a in sorted_attrs[:3]]
            should_amplify = attr in top_attrs
        elif sub_option == "player-maximizer-attributes-4-6":
            # Attributes 4-6
            next_attrs = [a[0] for a in sorted_attrs[3:6]]
            should_amplify = attr in next_attrs
    elif sub_option == "player-maximizer-positional-focus":
        triple = positional_focus_attrs_for_player(player)
        should_amplify = attr in triple
    elif sub_option == "player-maximizer-custom" and coaching_focus_custom_by_player:
        pid = str(player.get("_id", ""))
        chosen = coaching_focus_custom_by_player.get(pid) or []
        should_amplify = attr in chosen
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


def _training_camp_bonus_range_for_ch(ch_value: int) -> Optional[Tuple[int, int]]:
    """Return training-camp bonus range based on CH value (Training_System.md)."""
    if ch_value > 80:
        return (4, 10)
    if ch_value > 60:
        return (3, 8)
    if ch_value > 40:
        return (2, 6)
    if ch_value > 20:
        return (1, 4)
    return None


def _training_camp_core_attrs_for_position(position: str) -> List[str]:
    """Return core attributes for a highest-RT position in training camp."""
    pos = (position or "").upper()
    if pos == "PG":
        return ["PS", "BH", "IQ"]
    if pos == "SG":
        return ["SH", "FT", "OD"]
    if pos == "SF":
        sf_random = random.sample(["SC", "SH", "ID", "OD"], 2)
        return ["AG"] + sf_random
    if pos == "PF":
        return ["RB", "ST", "ID"]
    if pos == "C":
        return ["SC", "ST", "ID"]
    return []


def _top_two_rt_positions(player: dict) -> List[str]:
    """
    Top two positions by RT for training-camp year bonus.
    Two tied for first -> those two. More than two tied for first -> pick two at random.
    Unique first, multiple tied for second -> first + random among second tier.
    """
    ratings = player.get("position_ratings") or {}
    valid_positions = ["PG", "SG", "SF", "PF", "C"]
    items: List[Tuple[str, int]] = []
    for pos in valid_positions:
        raw = ratings.get(pos)
        if isinstance(raw, (int, float)):
            r = int(raw)
        else:
            try:
                r = int(raw or 0)
            except (TypeError, ValueError):
                r = 0
        items.append((pos, r))
    distinct_rts = sorted({r for _, r in items}, reverse=True)
    max_rt = distinct_rts[0]
    first_group = [pos for pos, r in items if r == max_rt]
    if len(first_group) >= 2:
        if len(first_group) == 2:
            return first_group
        return random.sample(first_group, 2)
    first_pos = first_group[0]
    second_rt = distinct_rts[1]
    second_group = [pos for pos, r in items if r == second_rt]
    return [first_pos, random.choice(second_group)]


def _training_camp_core_attrs_union_for_positions(positions: List[str]) -> List[str]:
    ordered: List[str] = []
    seen: set[str] = set()
    for pos in positions:
        for attr in _training_camp_core_attrs_for_position(pos):
            if attr not in seen:
                seen.add(attr)
                ordered.append(attr)
    return ordered


TRAINING_CAMP_YEAR_BONUS_RANGES = {
    "senior": (-5, 10),
    "junior": (-5, 10),
    "sophomore": (-8, 15),
    "freshman": (-10, 22),
}


def _apply_training_camp_attribute_delta(
    player: dict,
    attr: str,
    delta: int,
    player_baselines: Dict[Any, Dict[str, int]],
) -> None:
    """Apply a single camp delta; positive gains halved if session-start baseline > 100."""
    pid = player.get("_id")
    start = 0
    if pid is not None and player_baselines:
        start = int((player_baselines.get(pid) or {}).get(attr, 0) or 0)
    if delta > 0 and start > 100:
        delta = int(math.floor((delta * 0.5) + 0.5))

    attrs = player.get("attributes", {})
    anchor_key = f"anchor_{attr}"
    if anchor_key not in attrs and attr not in attrs:
        return
    current = int(attrs.get(anchor_key, attrs.get(attr, 0)) or 0)
    attrs[anchor_key] = current + delta
    attrs[attr] = attrs[anchor_key]


def _apply_training_camp_year_bonus(
    players: List[dict],
    player_baselines: Dict[Any, Dict[str, int]],
) -> None:
    """Second training-camp block: top-two-position cores + ND/IQ/FT/CH + one random (all players)."""
    extra_pool_exclude = {"EM", "MO", "NG", "RT"}

    for player in players:
        year = (player.get("year") or "").strip().lower()
        roll_range = TRAINING_CAMP_YEAR_BONUS_RANGES.get(year)
        if not roll_range:
            continue

        two_pos = _top_two_rt_positions(player)
        if len(two_pos) < 2:
            continue

        attr_list = _training_camp_core_attrs_union_for_positions(two_pos)
        seen = set(attr_list)
        for a in ("ND", "IQ", "FT", "CH"):
            if a not in seen:
                seen.add(a)
                attr_list.append(a)

        pool = [
            a
            for a in TRAINABLE_PLAYER_ATTRS
            if a not in seen and a not in extra_pool_exclude
        ]
        if pool:
            extra = random.choice(pool)
            attr_list.append(extra)

        lo, hi = roll_range
        for attr in attr_list:
            delta = random.randint(lo, hi)
            _apply_training_camp_attribute_delta(player, attr, delta, player_baselines)


def _highest_rt_position(player: dict) -> Optional[str]:
    """Pick one highest-RT position (random tie-break) from player.position_ratings."""
    ratings = player.get("position_ratings") or {}
    if not isinstance(ratings, dict):
        return None
    valid_positions = ["PG", "SG", "SF", "PF", "C"]
    scored_positions = [(pos, ratings.get(pos)) for pos in valid_positions if isinstance(ratings.get(pos), (int, float))]
    if not scored_positions:
        return None
    max_rt = max(score for _, score in scored_positions)
    tied = [pos for pos, score in scored_positions if score == max_rt]
    return random.choice(tied) if tied else None


_TRAINING_CAMP_PHYSIQUE_CLOSINGS = (
    "this offseason.",
    "during the offseason.",
    "over the summer.",
    "since last season.",
    "since last year.",
)


def _training_camp_inch_phrase(n: int) -> str:
    if n == 1:
        return "one inch"
    return f"{n} inches"


def _training_camp_pound_phrase(n: int) -> str:
    if n == 1:
        return "one pound"
    return f"{n} pounds"


def _roll_training_camp_height_delta(year: str) -> int:
    if year == "sophomore":
        return random.choices([0, 1, 2], weights=[60, 30, 10], k=1)[0]
    if year == "freshman":
        return random.choices([0, 1, 2, 3, 4, 5], weights=[20, 20, 30, 20, 5, 5], k=1)[0]
    return 0


def _roll_training_camp_weight_delta(year: str, height_after: int) -> int:
    if year == "sophomore":
        if height_after > 75:
            return random.randint(0, 10)
        return random.randint(0, 5)
    if year == "freshman":
        if height_after > 75:
            return random.randint(10, 30)
        if height_after > 72:
            return random.randint(5, 15)
        return random.randint(0, 10)
    return 0


def _training_camp_physique_line(name: str, dh: int, dw: int) -> str:
    closing = random.choice(_TRAINING_CAMP_PHYSIQUE_CLOSINGS)
    if dh and dw:
        return (
            f"{name} grew {_training_camp_inch_phrase(dh)} and "
            f"gained {_training_camp_pound_phrase(dw)} {closing}"
        )
    if dh:
        return f"{name} grew {_training_camp_inch_phrase(dh)} {closing}"
    return f"{name} gained {_training_camp_pound_phrase(dw)} {closing}"


def _apply_training_camp_height_weight_bonuses(players: List[dict]) -> List[str]:
    """Training camp only: sophomore/freshman height then weight; one report line per player with any gain."""
    lines: List[str] = []
    for player in players:
        meta = player.get("meta")
        if not isinstance(meta, dict):
            continue
        yr_raw = meta.get("year") if meta.get("year") is not None else player.get("year")
        year = str(yr_raw or "").strip().lower()
        if year not in ("freshman", "sophomore"):
            continue
        try:
            h0 = int(meta["height"])
        except (KeyError, TypeError, ValueError):
            continue
        try:
            w0 = int(meta["weight"])
        except (KeyError, TypeError, ValueError):
            continue
        dh = _roll_training_camp_height_delta(year)
        new_h = h0 + dh
        dw = _roll_training_camp_weight_delta(year, new_h)
        if dh == 0 and dw == 0:
            continue
        meta["height"] = new_h
        meta["weight"] = w0 + dw
        name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip() or str(
            player.get("_id", "")
        )
        lines.append(_training_camp_physique_line(name, dh, dw))
    return lines


def _apply_training_camp_bonus(
    players: List[dict],
    player_baselines: Dict[Any, Dict[str, int]],
) -> None:
    """Training camp: (1) CH / highest-RT core bonus, (2) year-based bonus on expanded attr set."""
    for player in players:
        attrs = player.get("attributes", {})
        ch_value = int(attrs.get("anchor_CH", attrs.get("CH", 0)) or 0)
        bonus_range = _training_camp_bonus_range_for_ch(ch_value)
        if bonus_range:
            highest_pos = _highest_rt_position(player)
            if highest_pos:
                core_attrs = _training_camp_core_attrs_for_position(highest_pos)
                for attr in core_attrs:
                    delta = random.randint(bonus_range[0], bonus_range[1])
                    _apply_training_camp_attribute_delta(player, attr, delta, player_baselines)

    _apply_training_camp_year_bonus(players, player_baselines)


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

    `fight` and `discipline` share the same point-bucket → delta table (`fight_discipline_training_ranges`).
    """
    if team_attr not in TEAM_ATTR_CLAMPS:
        return

    standard_ranges = {
        0: (-2, -1),
        1: (0, 2),
        2: (1, 2),
        3: (2, 3),
        4: (2, 4),
        5: (2, 5),
    }
    # Shared by Strength+Conditioning → fight and defense/passing/BH → discipline.
    fight_discipline_training_ranges = {
        0: (-4, -3),
        1: (-1, 1),
        2: (0, 2),
        3: (1, 3),
        4: (2, 4),
        5: (3, 5),
    }
    chemistry_ranges = {
        0: (-3, -1),
        1: (0, 1),
        2: (1, 2),
        3: (2, 3),
        4: (2, 4),
        5: (2, 5),
    }

    if team_attr in ("fight", "discipline"):
        ranges = fight_discipline_training_ranges
    elif team_attr == "team_chemistry":
        ranges = chemistry_ranges
    else:
        ranges = standard_ranges

    points_bucket = max(0, min(5, int(points)))
    low, high = ranges[points_bucket]
    delta = random.randint(low, high)

    # Apply focus amplifier if this attribute is amplified by the selected focus
    if delta > 0 and _should_amplify_team_attr(team_attr, archetype, sub_option):
        focus_multiplier = random.choice([1.5, 1.6, 1.7, 1.8])
        delta = int(delta * focus_multiplier)

    current_val = team.get(team_attr, 0)
    team[team_attr] = current_val + delta
    lower, upper = TEAM_ATTR_CLAMPS[team_attr]
    team[team_attr] = max(lower, min(upper, team[team_attr]))


def _apply_rebound_modifier_training(team: dict, points: int, archetype: Optional[str] = None, sub_option: Optional[str] = None, source: str = "technical_drills"):
    """
    Apply training points to rebound_modifier.
    
    Args:
        team: Team dict
        points: Training points allocated (0-5)
        archetype: Optional coaching focus archetype
        sub_option: Optional coaching focus sub-option
        source: "technical_drills" or "scrimmages" - determines which range to use
    
    Technical Drills / Scrimmages ranges (in 0.01 increments).
    - <1 effective point: -0.05 to -0.03
    - 1-2 effective points: +0.03 to +0.05
    - 3-4 effective points: +0.03 to +0.07
    - 5+ effective points: +0.03 to +0.10
    """
    # Both technical drills and scrimmages use the same effective-point tuning.
    if points < 1:
        increase = random.randint(-5, -3) / 100.0
    elif points in (1, 2):
        increase = random.randint(3, 5) / 100.0
    elif points in (3, 4):
        increase = random.randint(3, 7) / 100.0
    else:
        increase = random.randint(3, 10) / 100.0
    
    final_increase = increase
    
    # Apply focus amplifier if rebound_modifier is amplified by the selected focus
    if final_increase > 0 and _should_amplify_team_attr("rebound_modifier", archetype, sub_option):
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
    Apply training points to shot_threshold (doc ranges).
    
    - 0 points: += random.randint(5, 15)
    - 1 point: += random.randint(0, 5)
    - 2 points: -= random.randint(3, 8)
    - 3 points: -= random.randint(5, 11)
    - 4 points: -= random.randint(5, 15)
    - 5+ points: -= random.randint(5, 20)
    """
    lower, upper = TEAM_ATTR_CLAMPS["shot_threshold"]
    current_val = team.get("shot_threshold", lower)

    if points == 0:
        increase = random.randint(5, 15)
        team["shot_threshold"] = max(lower, min(upper, current_val + increase))
        return

    if points == 1:
        increase = random.randint(0, 5)
        team["shot_threshold"] = max(lower, min(upper, current_val + increase))
        return

    # 2–5: decrease threshold
    if points == 2:
        decrease = random.randint(3, 8)
    elif points == 3:
        decrease = random.randint(5, 11)
    elif points == 4:
        decrease = random.randint(5, 15)
    elif points == 5:
        decrease = random.randint(5, 20)
    else:
        decrease = random.randint(5, 20)
    team["shot_threshold"] = max(lower, min(upper, current_val - decrease))


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
        # Per-player picks (coaching_focus_custom_by_player) handled in _apply_player_training_points
        return False
    elif sub_option == "player-maximizer-positional-focus":
        return False  # Handled in _apply_player_training_points via position_ratings
    
    # Culture Builder Options
    elif sub_option == "culture-builder-inspire":
        # Flat EM/MO block only; team_chemistry via _should_amplify_team_attr
        return False
    elif sub_option == "culture-builder-community":
        return attr == "EM"  # Improves EM, Max Crowd factor for upcoming home game, Min Crowd factor for upcoming away game
    elif sub_option == "culture-builder-teamwork":
        return False  # Team Building (`culture-builder-teamwork`): flat team_ch only—not Authoritarian Teamwork
    elif sub_option == "culture-builder-confidence":
        return attr in ["CH", "FT"]
    
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
    - 3: random.choice([1, 1.05, 1.1]), team chemistry += randint(-1,1), discipline/fight += randint(-1,0)
    - 4: random.choice([1, 1.05, 1.1, 1.1]), team chemistry += randint(-2,1), discipline/fight += randint(-2,-1)
    - 5: random.choice([1, 1.05, 1.1, 1.15]), team chemistry += randint(-3,1), discipline/fight += randint(-3,-1)
    
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
        team["team_chemistry"] += random.randint(-1, 1)
        team["team_chemistry"] = max(
            TEAM_ATTR_CLAMPS["team_chemistry"][0],
            min(TEAM_ATTR_CLAMPS["team_chemistry"][1], team["team_chemistry"])
        )
        if "discipline" in team:
            team["discipline"] += random.randint(-1, 0)
            team["discipline"] = max(
                TEAM_ATTR_CLAMPS["discipline"][0],
                min(TEAM_ATTR_CLAMPS["discipline"][1], team["discipline"])
            )
        if "fight" in team:
            team["fight"] += random.randint(-1, 0)
            team["fight"] = max(
                TEAM_ATTR_CLAMPS["fight"][0],
                min(TEAM_ATTR_CLAMPS["fight"][1], team["fight"])
            )
    elif breaks_points == 4:
        multiplier = random.choice([1, 1.05, 1.1, 1.1])
        # Also adjust team chemistry, discipline, and fight
        team["team_chemistry"] += random.randint(-2, 1)
        team["team_chemistry"] = max(
            TEAM_ATTR_CLAMPS["team_chemistry"][0],
            min(TEAM_ATTR_CLAMPS["team_chemistry"][1], team["team_chemistry"])
        )
        if "discipline" in team:
            team["discipline"] += random.randint(-2, -1)
            team["discipline"] = max(
                TEAM_ATTR_CLAMPS["discipline"][0],
                min(TEAM_ATTR_CLAMPS["discipline"][1], team["discipline"])
            )
        if "fight" in team:
            team["fight"] += random.randint(-2, -1)
            team["fight"] = max(
                TEAM_ATTR_CLAMPS["fight"][0],
                min(TEAM_ATTR_CLAMPS["fight"][1], team["fight"])
            )
    elif breaks_points == 5:
        multiplier = random.choice([1, 1.05, 1.1, 1.15])
        # Also adjust team chemistry, discipline, and fight
        team["team_chemistry"] += random.randint(-3, 1)
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
        team["team_chemistry"] += random.randint(-3, 1)
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


def build_eog_offensive_play_effectiveness_decay_ftd_updates(
    game_team_plays: Dict[str, Any],
    ftd_plays: Dict[str, Any],
) -> Dict[str, Any]:
    """
    End-of-game: optionally reduce each offensive play's CMD (effectiveness) on FTD.

    Let ``usage_int = int(100 * times_run / total_times_run)`` when ``total_times_run > 0``,
    else 0. Let ``success_rate_pct = (successes / times_run) * 100`` when ``times_run > 0``,
    else 0 (``successes`` from ``game_stats``).

    Decay is ``usage_int`` only when ``4 * usage_int < success_rate_pct``; otherwise decay is 0.
    New effectiveness is ``max(0, current_ftd_effectiveness - decay)``. Only keys that change
    are included (Mongo ``$set`` paths ``plays.<storage_key>.effectiveness``).

    ``total_times_run`` is the sum of ``game_stats.times_run`` over the team's offensive plays
    for that game (same shape as training / stat rollup). Defense EOG decay is separate.
    """
    if not isinstance(game_team_plays, dict) or not isinstance(ftd_plays, dict):
        return {}

    total_times_run = 0
    times_by_storage_key: Dict[str, int] = {}
    for storage_key, play_data, _display_name in iter_team_plays(game_team_plays):
        if not isinstance(play_data, dict):
            continue
        gs = play_data.get("game_stats") or {}
        if not isinstance(gs, dict):
            continue
        tr = int(gs.get("times_run", 0) or 0)
        times_by_storage_key[storage_key] = tr
        if tr > 0:
            total_times_run += tr

    set_doc: Dict[str, Any] = {}
    for storage_key, play_data, display_name in iter_team_plays(game_team_plays):
        if not isinstance(play_data, dict):
            continue
        tr = times_by_storage_key.get(storage_key, 0)
        gs_loop = play_data.get("game_stats") or {}
        if not isinstance(gs_loop, dict):
            gs_loop = {}
        successes = int(gs_loop.get("successes", 0) or 0)
        if total_times_run > 0 and tr > 0:
            usage_int = int(100.0 * float(tr) / float(total_times_run))
            success_rate_pct = (float(successes) / float(tr)) * 100.0
            decay = usage_int if (4 * usage_int < success_rate_pct) else 0
        else:
            decay = 0
        ftd_row = ftd_plays.get(storage_key)
        if not isinstance(ftd_row, dict):
            logger.warning(
                "📉 [EOG-PLAY-EFF] Skipping %s (storage_key=%s): no matching FTD play row",
                display_name,
                storage_key,
            )
            continue
        try:
            current_eff = int(ftd_row.get("effectiveness", 0) or 0)
        except (TypeError, ValueError):
            current_eff = 0
        new_eff = max(0, current_eff - decay)
        if new_eff != current_eff:
            set_doc[f"plays.{storage_key}.effectiveness"] = new_eff
            logger.warning(
                "📉 [EOG-PLAY-EFF] %s: effectiveness %s → %s (times_run=%s total=%s decay=%s)",
                display_name,
                current_eff,
                new_eff,
                tr,
                total_times_run,
                decay,
            )
    return set_doc


def _defense_row_game_used(defense_row: Any) -> int:
    """Defensive possessions in this call from persisted game scouting (parallel to plays.game_stats.times_run)."""
    if not isinstance(defense_row, dict):
        return 0
    gs = defense_row.get("game_stats")
    if isinstance(gs, dict):
        raw = gs.get("used")
        if raw is not None:
            try:
                return max(0, int(raw))
            except (TypeError, ValueError):
                pass
    raw = defense_row.get("used")
    try:
        return max(0, int(raw or 0))
    except (TypeError, ValueError):
        return 0


def _ftd_defense_storage_key(ftd_defense: Dict[str, Any], game_row_key: str) -> Optional[str]:
    """Pick the FTD `scouting_data.defense` key that holds the row for this game's defense dict key."""
    if not isinstance(ftd_defense, dict) or not game_row_key:
        return None
    candidates: List[str] = [str(game_row_key).strip()]
    ck = canonical_scouting_defense_key(str(game_row_key))
    if ck:
        candidates.append(ck)
        candidates.extend(list(_SCOUTING_DEFENSE_LEGACY_KEYS_BY_CANONICAL.get(ck, ())))
    seen: set[str] = set()
    for c in candidates:
        if not c or c in seen:
            continue
        seen.add(c)
        row = ftd_defense.get(c)
        if isinstance(row, dict):
            return c
    return None


def build_eog_defensive_effectiveness_decay_ftd_updates(
    game_team_scouting: Dict[str, Any],
    ftd_scouting_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    End-of-game: reduce each defense row's effectiveness on FTD by the integer share of team
    defensive playcalls (``game_stats.used``) for that game — same formula as offensive CMD decay
    (``int(100 * used / total_used)`` when ``total_used > 0``).
    """
    if not isinstance(game_team_scouting, dict) or not isinstance(ftd_scouting_data, dict):
        return {}
    game_def = game_team_scouting.get("defense")
    if not isinstance(game_def, dict):
        return {}
    ftd_def = ftd_scouting_data.get("defense")
    if not isinstance(ftd_def, dict):
        return {}

    times_by_game_key: Dict[str, int] = {}
    total_used = 0
    for gk, grow in game_def.items():
        if not isinstance(grow, dict):
            continue
        u = _defense_row_game_used(grow)
        times_by_game_key[str(gk)] = u
        if u > 0:
            total_used += u

    set_doc: Dict[str, Any] = {}
    if total_used <= 0:
        return set_doc

    for gk, grow in game_def.items():
        if not isinstance(grow, dict):
            continue
        u = times_by_game_key.get(str(gk), 0)
        decay = int(100.0 * float(u) / float(total_used))
        ftk = _ftd_defense_storage_key(ftd_def, str(gk))
        if not ftk:
            logger.warning(
                "📉 [EOG-DEF-EFF] Skipping defense game_key=%s: no matching FTD scouting_data.defense row",
                gk,
            )
            continue
        frow = ftd_def.get(ftk)
        if not isinstance(frow, dict):
            continue
        try:
            current_eff = int(frow.get("effectiveness", 0) or 0)
        except (TypeError, ValueError):
            current_eff = 0
        new_eff = max(0, current_eff - decay)
        if new_eff != current_eff:
            set_doc[f"scouting_data.defense.{ftk}.effectiveness"] = new_eff
            logger.warning(
                "📉 [EOG-DEF-EFF] %s: effectiveness %s → %s (used=%s total=%s decay=%s)",
                ftk,
                current_eff,
                new_eff,
                u,
                total_used,
                decay,
            )
    return set_doc


def _playbook_row_id_to_canonical_defense(row_id: str) -> Optional[str]:
    """Map GET /api/playbooks defense row id (e.g. man_normal, zone_23) to scouting_data['defense'] key."""
    s = str(row_id).strip()
    if not s:
        return None
    if s in PLAYBOOK_MAN_KEY_TO_DEFENSE_ID:
        return PLAYBOOK_MAN_KEY_TO_DEFENSE_ID[s]
    if s in PLAYBOOK_ZONE_KEY_TO_DEFENSE_ID:
        return PLAYBOOK_ZONE_KEY_TO_DEFENSE_ID[s]
    return canonical_scouting_defense_key(s)


def apply_play_defense_training(
    plays_data: Dict,
    scouting_data: Dict,
    allocations: Dict,
    playbook_training_mode: str,
    strategy_settings: Dict,
    playbook_settings: Dict,
    coaching_focus: Optional[str] = None,
    training_playbook_focus: Optional[Dict[str, List[str]]] = None,
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
    
    sub_option = parse_coaching_focus(coaching_focus)[1] if coaching_focus else None

    # Authoritarian / Execution: one roll per session; scales effectiveness gains on set plays + Man only (after distribution).
    authoritarian_execution_eff_mult: Optional[float] = None
    if sub_option == "authoritarian-execution":
        authoritarian_execution_eff_mult = random.choice([1.5, 1.6, 1.7, 1.8])
        logger.warning(
            f"🎯 [AUTHORITARIAN EXECUTION] Effectiveness gain multiplier for set plays & Man: "
            f"{authoritarian_execution_eff_mult}x"
        )

    # Authoritarian / Teamwork: same band; motion plays + zone defenses only (after distribution).
    authoritarian_teamwork_eff_mult: Optional[float] = None
    if sub_option == "authoritarian-teamwork":
        authoritarian_teamwork_eff_mult = random.choice([1.5, 1.6, 1.7, 1.8])
        logger.warning(
            f"🎯 [AUTHORITARIAN TEAMWORK] Effectiveness gain multiplier for motion plays & zone defenses: "
            f"{authoritarian_teamwork_eff_mult}x"
        )

    # Apply Systems Coach focus multiplier to playPoints if applicable
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
            playbook_settings,
            authoritarian_execution_eff_mult=authoritarian_execution_eff_mult,
            authoritarian_teamwork_eff_mult=authoritarian_teamwork_eff_mult,
            training_playbook_focus=training_playbook_focus,
        )
    
    # Apply defense training
    if defense_play_points > 0:
        logger.warning(f"📚 [TRAINING] Applying defense training with {defense_play_points} points")
        updated_scouting_data = _apply_defense_training(
            updated_scouting_data,
            defense_play_points,
            playbook_training_mode,
            strategy_settings,
            playbook_settings,
            authoritarian_execution_eff_mult=authoritarian_execution_eff_mult,
            authoritarian_teamwork_eff_mult=authoritarian_teamwork_eff_mult,
            training_playbook_focus=training_playbook_focus,
        )
    
    return updated_plays, updated_scouting_data


def _apply_offense_play_training(
    plays_data: Dict,
    total_points: int,
    playbook_training_mode: str,
    strategy_settings: Dict,
    playbook_settings: Dict,
    authoritarian_execution_eff_mult: Optional[float] = None,
    authoritarian_teamwork_eff_mult: Optional[float] = None,
    training_playbook_focus: Optional[Dict[str, List[str]]] = None,
) -> Dict:
    """
    Apply training points to offensive plays.
    
    Args:
        plays_data: Dict of plays with effectiveness/momentum
        total_points: Total training points to distribute
        playbook_training_mode: "current-playbooks", "all-plays-even", or "custom"
        strategy_settings: Game plan strategy settings (used for inside/outside/attack split)
        playbook_settings: Playbook percentage settings
        authoritarian_execution_eff_mult: If set, scale effectiveness gains on set plays only (Authoritarian / Execution)
        authoritarian_teamwork_eff_mult: If set, scale effectiveness gains on motion plays only (Authoritarian / Teamwork)
    
    Returns:
        Updated plays_data dict
    """
    import math
    
    updated_plays = plays_data.copy()
    
    logger.warning(f"🎯 [PLAY TRAINING] Starting offense play training with {len(updated_plays)} plays")
    logger.warning(f"🎯 [PLAY TRAINING] Total points: {total_points}, mode: {playbook_training_mode}")
    logger.warning(f"🎯 [PLAY TRAINING] Plays data structure: {list(updated_plays.keys())[:5] if updated_plays else 'empty'}")
    
    # Custom Training Playbook: even CMD split across selected offense play_ids only.
    if playbook_training_mode == "custom" and training_playbook_focus and total_points > 0:
        allowed_ids = {str(x) for x in (training_playbook_focus.get("offense") or [])}
        eligible: List[Tuple[Any, Dict, str]] = []
        for play_key, play_data, display_name in iter_team_plays(updated_plays):
            if not isinstance(play_data, dict):
                continue
            pid = str(play_data.get("play_id") or "") or str(play_key)
            if pid in allowed_ids and play_data.get("play_type") in ("motion", "set_play"):
                eligible.append((play_key, play_data, display_name))
        if not eligible:
            logger.warning("🎯 [PLAY TRAINING] CUSTOM offense: no matching plays for allowed ids; skipping offense CMD")
            return updated_plays
        points_per_play = math.floor(total_points / len(eligible))
        remainder = total_points - (points_per_play * len(eligible))
        for i, (play_key, play_data, display_name) in enumerate(eligible):
            points = points_per_play + (1 if i < remainder else 0)
            is_set_play = play_data.get("play_type") == "set_play"
            is_motion_play = play_data.get("play_type") == "motion"
            points = _scale_install_training_effectiveness_points(
                points, authoritarian_execution_eff_mult, is_set_play
            )
            points = _scale_install_training_effectiveness_points(
                points, authoritarian_teamwork_eff_mult, is_motion_play
            )
            old_effectiveness = play_data.get("effectiveness", 0)
            new_effectiveness = old_effectiveness + points
            updated_plays[play_key]["effectiveness"] = new_effectiveness
            logger.warning(
                f"🎯 [PLAY TRAINING] CUSTOM {display_name}: {old_effectiveness} → {new_effectiveness} (+{points})"
            )
        return updated_plays
    
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
        for play_key, play_data, display_name in iter_team_plays(updated_plays):
            all_plays.append((play_key, play_data, display_name))
        
        logger.warning(f"🎯 [PLAY TRAINING] Found {len(all_plays)} total plays for even distribution (all-plays-even mode)")
        
        if all_plays:
            points_per_play = math.floor(total_points / len(all_plays))
            remainder = total_points - (points_per_play * len(all_plays))
            
            for i, (play_key, play_data, display_name) in enumerate(all_plays):
                points = points_per_play + (1 if i < remainder else 0)
                is_set_play = play_data.get("play_type") == "set_play"
                is_motion_play = play_data.get("play_type") == "motion"
                points = _scale_install_training_effectiveness_points(
                    points, authoritarian_execution_eff_mult, is_set_play
                )
                points = _scale_install_training_effectiveness_points(
                    points, authoritarian_teamwork_eff_mult, is_motion_play
                )
                old_effectiveness = play_data.get("effectiveness", 0)
                new_effectiveness = old_effectiveness + points
                updated_plays[play_key]["effectiveness"] = new_effectiveness
                play_type = play_data.get("play_type", "unknown")
                logger.warning(f"🎯 [PLAY TRAINING] {display_name} ({play_type}): {old_effectiveness} → {new_effectiveness} (+{points})")
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
            for play_key, play_data, display_name in iter_team_plays(updated_plays):
                if isinstance(play_data, dict) and play_data.get("play_type") == "motion":
                    motion_plays.append((play_key, play_data, display_name))
            
            logger.warning(f"🎯 [PLAY TRAINING] Motion points: {motion_points}, found {len(motion_plays)} motion plays")
            logger.warning(f"🎯 [PLAY TRAINING] Motion playbook settings: {motion_playbook}")
            
            # Calculate total percentage for motion plays in playbook
            total_motion_pct = sum(motion_playbook.values())
            
            if total_motion_pct > 0:
                for play_key, play_data, display_name in motion_plays:
                    play_pct = resolve_playbook_percentage(
                        motion_playbook,
                        play_id=play_data.get("play_id"),
                        play_name=display_name,
                        default=0,
                    ) / total_motion_pct
                    points = math.floor(motion_points * play_pct)
                    if points > 0:
                        points = _scale_install_training_effectiveness_points(
                            points, authoritarian_teamwork_eff_mult, True
                        )
                        old_effectiveness = play_data.get("effectiveness", 0)
                        new_effectiveness = old_effectiveness + points
                        updated_plays[play_key]["effectiveness"] = new_effectiveness
                        logger.warning(f"🎯 [PLAY TRAINING] {display_name}: {old_effectiveness} → {new_effectiveness} (+{points}, {play_pct*100:.1f}%)")
            else:
                # No playbook percentages, distribute evenly
                points_per_play = math.floor(motion_points / len(motion_plays)) if motion_plays else 0
                remainder = motion_points - (points_per_play * len(motion_plays)) if motion_plays else 0
                for i, (play_key, play_data, display_name) in enumerate(motion_plays):
                    points = points_per_play + (1 if i < remainder else 0)
                    points = _scale_install_training_effectiveness_points(
                        points, authoritarian_teamwork_eff_mult, True
                    )
                    old_effectiveness = play_data.get("effectiveness", 0)
                    new_effectiveness = old_effectiveness + points
                    updated_plays[play_key]["effectiveness"] = new_effectiveness
                    logger.warning(f"🎯 [PLAY TRAINING] {display_name}: {old_effectiveness} → {new_effectiveness} (+{points}, even dist)")
        
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
                    set_playbook = playbook_settings.get("set_plays", {})
                    if not set_playbook:
                        set_playbook = playbook_settings.get(f"set_play_{focus}", {})
                    
                    # 🔍 DEBUG: Log set playbook lookup
                    logger.warning(f"🔍 [SET PLAY TRAINING DEBUG] {focus} focus:")
                    logger.warning(f"   - focus_points: {focus_points}")
                    logger.warning(f"   - set_playbook_key: 'set_plays'")
                    logger.warning(f"   - set_playbook found: {bool(set_playbook)}")
                    logger.warning(f"   - set_playbook keys: {list(set_playbook.keys()) if set_playbook else 'EMPTY'}")
                    
                    set_plays = []
                    # 🔍 DEBUG: First, log all set plays and their play_focus values
                    all_set_plays = []
                    for play_key, play_data, display_name in iter_team_plays(updated_plays):
                        if isinstance(play_data, dict) and play_data.get("play_type") == "set_play":
                            all_set_plays.append((display_name, play_data.get("play_focus", "MISSING")))
                            if play_data.get("play_focus") == focus:
                                set_plays.append((play_key, play_data, display_name))
                    
                    if all_set_plays:
                        logger.warning(f"🔍 [SET PLAY TRAINING DEBUG] All set plays in plays_data: {[(name, focus) for name, focus in all_set_plays]}")
                    
                    logger.warning(f"🎯 [PLAY TRAINING] {focus} focus points: {focus_points}, found {len(set_plays)} set plays")
                    if set_plays:
                        logger.warning(f"🔍 [SET PLAY TRAINING DEBUG] Set plays found: {[name for _, _, name in set_plays]}")
                    elif all_set_plays:
                        logger.warning(f"⚠️ [SET PLAY TRAINING DEBUG] No set plays matched focus '{focus}'! Available focuses: {set([f for _, f in all_set_plays])}")
                    
                    # Calculate total percentage for set plays in this focus
                    total_set_pct = sum(set_playbook.values())
                    logger.warning(f"🔍 [SET PLAY TRAINING DEBUG] total_set_pct: {total_set_pct}")
                    
                    if total_set_pct > 0:
                        for play_key, play_data, display_name in set_plays:
                            play_pct = resolve_playbook_percentage(
                                set_playbook,
                                play_id=play_data.get("play_id"),
                                play_name=display_name,
                                default=0,
                            ) / total_set_pct
                            points = math.floor(focus_points * play_pct)
                            if points > 0:
                                points = _scale_install_training_effectiveness_points(
                                    points, authoritarian_execution_eff_mult, True
                                )
                                old_effectiveness = play_data.get("effectiveness", 0)
                                new_effectiveness = old_effectiveness + points
                                updated_plays[play_key]["effectiveness"] = new_effectiveness
                                logger.warning(f"🎯 [PLAY TRAINING] {display_name}: {old_effectiveness} → {new_effectiveness} (+{points}, {play_pct*100:.1f}%)")
                    else:
                        # No playbook percentages, distribute evenly
                        points_per_play = math.floor(focus_points / len(set_plays)) if set_plays else 0
                        remainder = focus_points - (points_per_play * len(set_plays)) if set_plays else 0
                        for i, (play_key, play_data, display_name) in enumerate(set_plays):
                            points = points_per_play + (1 if i < remainder else 0)
                            points = _scale_install_training_effectiveness_points(
                                points, authoritarian_execution_eff_mult, True
                            )
                            old_effectiveness = play_data.get("effectiveness", 0)
                            new_effectiveness = old_effectiveness + points
                            updated_plays[play_key]["effectiveness"] = new_effectiveness
                            logger.warning(f"🎯 [PLAY TRAINING] {display_name}: {old_effectiveness} → {new_effectiveness} (+{points}, even dist)")
    
    return updated_plays


def _apply_defense_training(
    scouting_data: Dict,
    total_points: int,
    playbook_training_mode: str,
    strategy_settings: Dict,
    playbook_settings: Dict,
    authoritarian_execution_eff_mult: Optional[float] = None,
    authoritarian_teamwork_eff_mult: Optional[float] = None,
    training_playbook_focus: Optional[Dict[str, List[str]]] = None,
) -> Dict:
    """
    Apply training points to defensive plays.

    authoritarian_execution_eff_mult: If set, scale effectiveness gains on Man defense only (Authoritarian / Execution).
    authoritarian_teamwork_eff_mult: If set, scale effectiveness gains on zone defenses only (Authoritarian / Teamwork).
    
    Returns:
        Updated scouting_data dict
    """
    import math
    
    updated_scouting_data = scouting_data.copy() if scouting_data else {}
    
    # Ensure defense structure exists
    if "defense" not in updated_scouting_data:
        updated_scouting_data["defense"] = {}
    
    defense_data = updated_scouting_data["defense"]
    
    # Custom Training Playbook: even CMD split across unique canonical defenses from selected row ids.
    if playbook_training_mode == "custom" and training_playbook_focus and total_points > 0:
        seen_canon: List[str] = []
        for row_id in training_playbook_focus.get("defense") or []:
            ck = _playbook_row_id_to_canonical_defense(str(row_id))
            if ck and ck not in seen_canon and ck in defense_data:
                seen_canon.append(ck)
        if seen_canon:
            points_per = math.floor(total_points / len(seen_canon))
            remainder = total_points - (points_per * len(seen_canon))
            for i, defense_name in enumerate(seen_canon):
                points = points_per + (1 if i < remainder else 0)
                is_man = defense_name == "man"
                is_zone = defense_name in TRAINING_ZONE_DEFENSE_NAMES
                points = _scale_install_training_effectiveness_points(
                    points, authoritarian_execution_eff_mult, is_man
                )
                points = _scale_install_training_effectiveness_points(
                    points, authoritarian_teamwork_eff_mult, is_zone
                )
                old_eff = defense_data[defense_name].get("effectiveness", 0)
                defense_data[defense_name]["effectiveness"] = old_eff + points
                logger.warning(
                    f"📚 [TRAINING] CUSTOM defense '{defense_name}': {old_eff} → {old_eff + points} (+{points})"
                )
            return updated_scouting_data
        logger.warning("📚 [TRAINING] CUSTOM defense: no matching scouting rows; skipping defense CMD")
        return updated_scouting_data
    
    # Check if we should use playbook settings or default to even distribution
    use_playbooks = (
        playbook_training_mode == "current-playbooks" and
        playbook_settings and
        strategy_settings
    )
    
    if not use_playbooks or playbook_training_mode == "all-plays-even":
        # Even distribution across all defensive plays (Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone)
        defense_types = ["man", "2-3-zone", "3-2-zone", "1-3-1-zone"]
        valid_defenses = [d for d in defense_types if d in defense_data]
        
        if valid_defenses:
            points_per_defense = math.floor(total_points / len(valid_defenses))
            remainder = total_points - (points_per_defense * len(valid_defenses))
            
            for i, defense_name in enumerate(valid_defenses):
                points = points_per_defense + (1 if i < remainder else 0)
                if defense_name in defense_data:
                    is_man = defense_name == "man"
                    is_zone = defense_name in TRAINING_ZONE_DEFENSE_NAMES
                    points = _scale_install_training_effectiveness_points(
                        points, authoritarian_execution_eff_mult, is_man
                    )
                    points = _scale_install_training_effectiveness_points(
                        points, authoritarian_teamwork_eff_mult, is_zone
                    )
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
            # For now, we only have one man defense row (`man`)
            # When more man defenses are added, we can use playbook_settings.get("man_defense", {})
            if "man" in defense_data:
                scaled_man = _scale_install_training_effectiveness_points(
                    man_points, authoritarian_execution_eff_mult, True
                )
                old_eff = defense_data["man"].get("effectiveness", 0)
                defense_data["man"]["effectiveness"] = old_eff + scaled_man
                logger.warning(f"📚 [TRAINING] Defense 'man': effectiveness {old_eff} → {old_eff + scaled_man} (+{scaled_man} points)")
        
        # Distribute zone defense points
        if zone_points > 0:
            zone_playbook = playbook_settings.get("zone_defense", {})
            zone_defenses = list(PLAYBOOK_ZONE_KEY_TO_DEFENSE_ID.values())
            valid_zone_defenses = [d for d in zone_defenses if d in defense_data]
            
            # Calculate total percentage for zone defenses in playbook
            total_zone_pct = sum(zone_playbook.values())
            
            if total_zone_pct > 0:
                for defense_id in valid_zone_defenses:
                    pb_key = DEFENSE_ID_TO_PLAYBOOK_ZONE_KEY.get(defense_id)
                    raw_pct = 0
                    if pb_key:
                        raw_pct = zone_playbook.get(pb_key, 0)
                    if not raw_pct:
                        raw_pct = zone_playbook.get(defense_id, 0)
                    if not raw_pct:
                        legacy = defense_display_name(defense_id)
                        raw_pct = zone_playbook.get(legacy, 0)
                    defense_pct = raw_pct / total_zone_pct
                    points = math.floor(zone_points * defense_pct)
                    if points > 0:
                        points = _scale_install_training_effectiveness_points(
                            points, authoritarian_teamwork_eff_mult, True
                        )
                        old_eff = defense_data[defense_id].get("effectiveness", 0)
                        defense_data[defense_id]["effectiveness"] = old_eff + points
                        logger.warning(f"📚 [TRAINING] Zone defense '{defense_id}': effectiveness {old_eff} → {old_eff + points} (+{points} points, {defense_pct*100:.1f}% of {zone_points})")
            else:
                # No playbook percentages, distribute evenly
                points_per_defense = math.floor(zone_points / len(valid_zone_defenses)) if valid_zone_defenses else 0
                remainder = zone_points - (points_per_defense * len(valid_zone_defenses)) if valid_zone_defenses else 0
                for i, defense_id in enumerate(valid_zone_defenses):
                    points = points_per_defense + (1 if i < remainder else 0)
                    points = _scale_install_training_effectiveness_points(
                        points, authoritarian_teamwork_eff_mult, True
                    )
                    old_eff = defense_data[defense_id].get("effectiveness", 0)
                    defense_data[defense_id]["effectiveness"] = old_eff + points
                    logger.warning(f"📚 [TRAINING] Zone defense '{defense_id}': effectiveness {old_eff} → {old_eff + points} (+{points} points, even distribution)")
    
    return updated_scouting_data
