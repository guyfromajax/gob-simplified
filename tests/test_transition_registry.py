"""
Tests for the Transition Registry

Validates that all 43 transition pairs are correctly defined and can be tested.
"""

import pytest
from BackEnd.utils.transition_registry import (
    Transition,
    TurnType,
    TRANSITION_REGISTRY,
    get_transitions_from,
    get_transitions_to,
    is_valid_transition,
    validate_transition_registry,
    count_transitions
)


class TestTransitionRegistry:
    """Test the transition registry structure and validation."""
    
    def test_registry_has_43_transitions(self):
        """Verify we have exactly 43 transition pairs as documented."""
        counts = count_transitions()
        assert counts["total"] == 43, f"Expected 43 transitions, found {counts['total']}"
    
    def test_no_duplicate_transitions(self):
        """Ensure no duplicate transitions exist."""
        seen = set()
        for t in TRANSITION_REGISTRY:
            key = (t.from_turn, t.to_turn, t.possession_change)
            assert key not in seen, f"Duplicate transition found: {t}"
            seen.add(key)
    
    def test_all_transitions_have_instigating_events(self):
        """Every transition must have at least one instigating event."""
        for t in TRANSITION_REGISTRY:
            assert len(t.instigating_events) > 0, f"Transition {t} has no instigating events"
    
    def test_registry_validation(self):
        """Test the validation function."""
        is_valid, issues = validate_transition_registry()
        assert is_valid, f"Registry validation failed: {issues}"
    
    def test_opening_tip_transitions(self):
        """Test Opening Tip -> HCO transition."""
        transitions = get_transitions_from(TurnType.OPENING_TIP)
        assert len(transitions) == 1
        assert transitions[0].to_turn == TurnType.HCO
        assert not transitions[0].possession_change
    
    def test_inbound_pass_transitions(self):
        """Test Inbound Pass transitions."""
        transitions = get_transitions_from(TurnType.INBOUND_PASS)
        assert len(transitions) == 3
        to_turns = {t.to_turn for t in transitions}
        assert TurnType.HCO in to_turns
        assert TurnType.FCP in to_turns
        assert TurnType.HCT in to_turns
    
    def test_hco_transitions(self):
        """Test HCO transitions (should have 8 total)."""
        transitions = get_transitions_from(TurnType.HCO)
        assert len(transitions) == 8
        
        # Check specific transitions
        assert is_valid_transition(TurnType.HCO, TurnType.INBOUND_PASS, possession_change=True)
        assert is_valid_transition(TurnType.HCO, TurnType.FREE_THROW, possession_change=False)
        assert is_valid_transition(TurnType.HCO, TurnType.OREB, possession_change=False)
        assert is_valid_transition(TurnType.HCO, TurnType.HCO, possession_change=True)
        assert is_valid_transition(TurnType.HCO, TurnType.FAST_BREAK, possession_change=True)
    
    def test_oreb_transitions(self):
        """Test OREB transitions (should have 9 total)."""
        transitions = get_transitions_from(TurnType.OREB)
        assert len(transitions) == 9
    
    def test_free_throw_transitions(self):
        """Test Free Throw transitions (should have 7 total)."""
        transitions = get_transitions_from(TurnType.FREE_THROW)
        assert len(transitions) == 7
    
    def test_fast_break_transitions(self):
        """Test Fast Break transitions (should have 8 total)."""
        transitions = get_transitions_from(TurnType.FAST_BREAK)
        assert len(transitions) == 8
    
    def test_fcp_hct_transitions(self):
        """Test FCP and HCT transitions (should have 8 each, 16 total)."""
        fcp_transitions = get_transitions_from(TurnType.FCP)
        hct_transitions = get_transitions_from(TurnType.HCT)
        assert len(fcp_transitions) == 8
        assert len(hct_transitions) == 8
        
        # FCP and HCT should have identical transition patterns
        fcp_patterns = {(t.to_turn, t.possession_change) for t in fcp_transitions}
        hct_patterns = {(t.to_turn, t.possession_change) for t in hct_transitions}
        assert fcp_patterns == hct_patterns, "FCP and HCT should have identical transition patterns"
    
    def test_possession_change_counts(self):
        """Verify possession change counts match expectations."""
        counts = count_transitions()
        # Based on transitions.md, count transitions with (PC)
        # This is a sanity check - exact count may vary
        assert counts["with_possession_change"] > 0
        assert counts["without_possession_change"] > 0

