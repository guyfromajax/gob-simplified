"""
Transition Registry for GOB Game Engine

This module provides a centralized registry of all valid game state transitions
as defined in docs/transitions.md. It serves as the single source of truth for
transition validation and testing.

SS&S Principle: Centralized transition logic ensures consistency and makes it
easy to validate, test, and maintain the transition system.
"""

from typing import Dict, List, Tuple, Optional
from enum import Enum


class TurnType(Enum):
    """Enumeration of all turn types in the game."""
    OPENING_TIP = "OPENING_TIP"
    INBOUND_PASS = "INBOUND_PASS"  # Baseline inbound
    SIDE_INBOUND_PASS = "SIDE_INBOUND_PASS"  # SIP
    HCO = "HCO"
    OREB = "OREB"
    FREE_THROW = "FREE_THROW"
    FAST_BREAK = "FAST_BREAK"
    FCP = "FCP"
    HCT = "HCT"


class Transition:
    """Represents a single transition from one turn type to another."""
    
    def __init__(
        self,
        from_turn: TurnType,
        to_turn: TurnType,
        instigating_events: List[str],
        possession_change: bool = False,
        notes: Optional[str] = None
    ):
        self.from_turn = from_turn
        self.to_turn = to_turn
        self.instigating_events = instigating_events
        self.possession_change = possession_change
        self.notes = notes
    
    def __repr__(self):
        pc_str = " (PC)" if self.possession_change else ""
        return f"{self.from_turn.value} -> {self.to_turn.value}{pc_str}: {', '.join(self.instigating_events)}"
    
    def __eq__(self, other):
        if not isinstance(other, Transition):
            return False
        return (
            self.from_turn == other.from_turn and
            self.to_turn == other.to_turn and
            self.possession_change == other.possession_change
        )
    
    def __hash__(self):
        return hash((self.from_turn, self.to_turn, self.possession_change))


# Registry of all valid transitions (43 total pairs)
TRANSITION_REGISTRY: List[Transition] = [
    # Opening Tip Transitions (1)
    Transition(TurnType.OPENING_TIP, TurnType.HCO, ["Opening Tip"]),
    
    # Inbound Pass Transitions (3)
    Transition(TurnType.INBOUND_PASS, TurnType.HCO, ["Inbound Pass Complete"]),
    Transition(TurnType.INBOUND_PASS, TurnType.FCP, ["Inbound Pass Complete, FCP Setup"]),
    Transition(TurnType.INBOUND_PASS, TurnType.HCT, ["Inbound Pass Complete, HCT Setup"]),
    
    # Side Inbound Pass Transitions (1)
    Transition(TurnType.SIDE_INBOUND_PASS, TurnType.HCO, ["Side Inbound Pass Complete"]),
    
    # HCO Transitions (8)
    Transition(TurnType.HCO, TurnType.INBOUND_PASS, ["Made Shot, No Foul"], possession_change=True),
    Transition(TurnType.HCO, TurnType.FREE_THROW, [
        "Made Shot, Foul",
        "Missed Shot, Foul",
        "Non-Shooting Defensive Foul, Bonus Situation"
    ]),
    Transition(TurnType.HCO, TurnType.OREB, ["Missed Shot, OREB"]),
    Transition(TurnType.HCO, TurnType.HCO, [
        "Missed Shot, DREB, HCO next step",
        "Steal, HCO next step"
    ], possession_change=True),
    Transition(TurnType.HCO, TurnType.FAST_BREAK, [
        "Missed Shot, DREB, Fast Break next step",
        "Steal, Fast Break next step"
    ], possession_change=True),
    Transition(TurnType.HCO, TurnType.SIDE_INBOUND_PASS, [
        "Non-Shooting Defensive Foul, No Bonus",
        "Missed Shot, Non-Shooting Defensive Foul"
    ]),
    Transition(TurnType.HCO, TurnType.SIDE_INBOUND_PASS, [
        "Offensive Foul",
        "Dead Ball Turnover",
        "Missed Shot, Offensive Foul"
    ], possession_change=True),
    
    # OREB Transitions (9)
    Transition(TurnType.OREB, TurnType.INBOUND_PASS, ["Made Shot, No Foul"], possession_change=True),
    Transition(TurnType.OREB, TurnType.FREE_THROW, [
        "Made Shot, Foul",
        "Missed Shot, Foul"
    ]),
    Transition(TurnType.OREB, TurnType.HCO, ["Kickout Pass"]),
    Transition(TurnType.OREB, TurnType.HCO, [
        "Missed Shot, DREB, HCO next step"
    ], possession_change=True),
    Transition(TurnType.OREB, TurnType.FAST_BREAK, [
        "Missed Shot, DREB, Fast Break next step"
    ], possession_change=True),
    Transition(TurnType.OREB, TurnType.OREB, ["Missed Shot, OREB"]),
    Transition(TurnType.OREB, TurnType.SIDE_INBOUND_PASS, [
        "Missed Shot, Offensive Foul"
    ], possession_change=True),
    Transition(TurnType.OREB, TurnType.SIDE_INBOUND_PASS, [
        "Missed shot, Non-Shooting Defensive Foul"
    ]),
    
    # Free Throw Transitions (7)
    Transition(TurnType.FREE_THROW, TurnType.INBOUND_PASS, ["Final FT Made"], possession_change=True),
    Transition(TurnType.FREE_THROW, TurnType.OREB, ["Final FT Missed, OREB"]),
    Transition(TurnType.FREE_THROW, TurnType.HCO, [
        "Final FT Missed, DREB, HCO next step"
    ], possession_change=True),
    Transition(TurnType.FREE_THROW, TurnType.FAST_BREAK, [
        "Final FT Missed, DREB, Fast Break next step"
    ]),
    Transition(TurnType.FREE_THROW, TurnType.SIDE_INBOUND_PASS, [
        "Final Free Throw Missed, Defensive Foul, No Bonus Situation"
    ]),
    Transition(TurnType.FREE_THROW, TurnType.FREE_THROW, [
        "Final Free Throw Missed, Defensive Foul, Bonus Situation"
    ], possession_change=True),
    Transition(TurnType.FREE_THROW, TurnType.SIDE_INBOUND_PASS, [
        "Final Free Throw Missed, Offensive Foul"
    ], possession_change=True),
    
    # Fast Break Transitions (8)
    Transition(TurnType.FAST_BREAK, TurnType.HCO, ["Defensive Stop"]),
    Transition(TurnType.FAST_BREAK, TurnType.INBOUND_PASS, ["Made Shot, No Foul"], possession_change=True),
    Transition(TurnType.FAST_BREAK, TurnType.FREE_THROW, [
        "Made Shot, Foul",
        "Missed Shot, Foul",
        "Non-Shooting Defensive Foul, Bonus Situation"
    ]),
    Transition(TurnType.FAST_BREAK, TurnType.OREB, ["Missed Shot, OREB"]),
    Transition(TurnType.FAST_BREAK, TurnType.HCO, [
        "Missed Shot, DREB, HCO next step",
        "Steal, HCO next step"
    ], possession_change=True),
    Transition(TurnType.FAST_BREAK, TurnType.FAST_BREAK, [
        "Missed Shot, DREB, Fast Break next step",
        "Steal, Fast Break next step"
    ]),
    Transition(TurnType.FAST_BREAK, TurnType.SIDE_INBOUND_PASS, [
        "Non-Shooting Defensive Foul, No Bonus Situation"
    ]),
    Transition(TurnType.FAST_BREAK, TurnType.SIDE_INBOUND_PASS, [
        "Offensive Foul",
        "Dead Ball Turnover"
    ], possession_change=True),
    
    # FCP/HCT Transitions (8)
    # Note: FCP and HCT share the same transition patterns
    Transition(TurnType.FCP, TurnType.HCO, ["Press/Trap Break, HCO next step"]),
    Transition(TurnType.HCT, TurnType.HCO, ["Press/Trap Break, HCO next step"]),
    Transition(TurnType.FCP, TurnType.INBOUND_PASS, ["Press/Trap Break, Made Shot Attempt, No Foul"]),
    Transition(TurnType.HCT, TurnType.INBOUND_PASS, ["Press/Trap Break, Made Shot Attempt, No Foul"]),
    Transition(TurnType.FCP, TurnType.FREE_THROW, [
        "Press/Trap Break, Made Shot Attempt, Shooting Foul",
        "Press/Trap Break, Missed Shot Attempt, No Foul",
        "Non-shooting Defensive Foul, Bonus Situation"
    ]),
    Transition(TurnType.HCT, TurnType.FREE_THROW, [
        "Press/Trap Break, Made Shot Attempt, Shooting Foul",
        "Press/Trap Break, Missed Shot Attempt, No Foul",
        "Non-shooting Defensive Foul, Bonus Situation"
    ]),
    Transition(TurnType.FCP, TurnType.OREB, ["Press/Trap Break, Missed Shot Attempt, OREB"]),
    Transition(TurnType.HCT, TurnType.OREB, ["Press/Trap Break, Missed Shot Attempt, OREB"]),
    Transition(TurnType.FCP, TurnType.HCO, [
        "Press/Trap Break, Missed Shot Attempt, DREB, HCO next step",
        "Steal, HCO as next step"
    ], possession_change=True),
    Transition(TurnType.HCT, TurnType.HCO, [
        "Press/Trap Break, Missed Shot Attempt, DREB, HCO next step",
        "Steal, HCO as next step"
    ], possession_change=True),
    Transition(TurnType.FCP, TurnType.FAST_BREAK, [
        "Press/Trap Break, Missed Shot Attempt, DREB, Fast Break next step",
        "Steal, Fast Break as next step"
    ], possession_change=True),
    Transition(TurnType.HCT, TurnType.FAST_BREAK, [
        "Press/Trap Break, Missed Shot Attempt, DREB, Fast Break next step",
        "Steal, Fast Break as next step"
    ], possession_change=True),
    Transition(TurnType.FCP, TurnType.SIDE_INBOUND_PASS, [
        "Offensive Foul",
        "Dead Ball Turnover"
    ], possession_change=True),
    Transition(TurnType.HCT, TurnType.SIDE_INBOUND_PASS, [
        "Offensive Foul",
        "Dead Ball Turnover"
    ], possession_change=True),
    Transition(TurnType.FCP, TurnType.SIDE_INBOUND_PASS, ["Non-Shooting Defensive Foul"]),
    Transition(TurnType.HCT, TurnType.SIDE_INBOUND_PASS, ["Non-Shooting Defensive Foul"]),
]


def get_transitions_from(from_turn: TurnType) -> List[Transition]:
    """Get all valid transitions from a given turn type."""
    return [t for t in TRANSITION_REGISTRY if t.from_turn == from_turn]


def get_transitions_to(to_turn: TurnType) -> List[Transition]:
    """Get all valid transitions to a given turn type."""
    return [t for t in TRANSITION_REGISTRY if t.to_turn == to_turn]


def is_valid_transition(
    from_turn: TurnType,
    to_turn: TurnType,
    possession_change: bool = False
) -> bool:
    """Check if a transition is valid according to the registry."""
    return any(
        t.from_turn == from_turn and
        t.to_turn == to_turn and
        t.possession_change == possession_change
        for t in TRANSITION_REGISTRY
    )


def get_transition(
    from_turn: TurnType,
    to_turn: TurnType,
    possession_change: bool = False
) -> Optional[Transition]:
    """Get a specific transition if it exists."""
    for t in TRANSITION_REGISTRY:
        if (t.from_turn == from_turn and
            t.to_turn == to_turn and
            t.possession_change == possession_change):
            return t
    return None


def count_transitions() -> Dict[str, int]:
    """Count transitions by type for validation."""
    total = len(TRANSITION_REGISTRY)
    by_from = {}
    by_to = {}
    with_pc = sum(1 for t in TRANSITION_REGISTRY if t.possession_change)
    
    for turn_type in TurnType:
        by_from[turn_type.value] = len(get_transitions_from(turn_type))
        by_to[turn_type.value] = len(get_transitions_to(turn_type))
    
    return {
        "total": total,
        "with_possession_change": with_pc,
        "without_possession_change": total - with_pc,
        "by_from_turn": by_from,
        "by_to_turn": by_to
    }


def validate_transition_registry() -> Tuple[bool, List[str]]:
    """
    Validate the transition registry for completeness and correctness.
    
    Returns:
        (is_valid, list_of_issues)
    """
    issues = []
    
    # Check total count (should be 43)
    if len(TRANSITION_REGISTRY) != 43:
        issues.append(f"Expected 43 transitions, found {len(TRANSITION_REGISTRY)}")
    
    # Check for duplicates
    seen = set()
    for t in TRANSITION_REGISTRY:
        key = (t.from_turn, t.to_turn, t.possession_change)
        if key in seen:
            issues.append(f"Duplicate transition: {t}")
        seen.add(key)
    
    # Check that all transitions have instigating events
    for t in TRANSITION_REGISTRY:
        if not t.instigating_events:
            issues.append(f"Transition {t} has no instigating events")
    
    return len(issues) == 0, issues

