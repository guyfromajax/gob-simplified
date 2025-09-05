/**
 * SimplifiedStateMachine Tests
 * 
 * Tests for the clean 4-state basketball animation system
 */

import { 
  SimplifiedStateMachine, 
  AnimationStates, 
  StateTransitions 
} from '../SimplifiedStateMachine.js';

describe('SimplifiedStateMachine', () => {
  let stateMachine;

  beforeEach(() => {
    stateMachine = new SimplifiedStateMachine();
  });

  describe('Initialization', () => {
    test('should initialize with IDLE state by default', () => {
      expect(stateMachine.getCurrentState()).toBe(AnimationStates.IDLE);
      expect(stateMachine.getPreviousState()).toBe(null);
    });

    test('should initialize with custom initial state', () => {
      const customStateMachine = new SimplifiedStateMachine(AnimationStates.POSSESSION);
      expect(customStateMachine.getCurrentState()).toBe(AnimationStates.POSSESSION);
    });

    test('should not be transitioning initially', () => {
      expect(stateMachine.getStatus().isTransitioning).toBe(false);
    });
  });

  describe('State Transitions', () => {
    test('should allow valid transitions from IDLE', () => {
      expect(stateMachine.transition(AnimationStates.POSSESSION)).toBe(true);
      expect(stateMachine.getCurrentState()).toBe(AnimationStates.POSSESSION);
      expect(stateMachine.getPreviousState()).toBe(AnimationStates.IDLE);
    });

    test('should allow valid transitions from POSSESSION', () => {
      stateMachine.transition(AnimationStates.POSSESSION);
      expect(stateMachine.transition(AnimationStates.SHOOTING)).toBe(true);
      expect(stateMachine.getCurrentState()).toBe(AnimationStates.SHOOTING);
    });

    test('should allow valid transitions from SHOOTING', () => {
      stateMachine.transition(AnimationStates.POSSESSION);
      stateMachine.transition(AnimationStates.SHOOTING);
      expect(stateMachine.transition(AnimationStates.REBOUNDING)).toBe(true);
      expect(stateMachine.getCurrentState()).toBe(AnimationStates.REBOUNDING);
    });

    test('should allow valid transitions from REBOUNDING', () => {
      stateMachine.transition(AnimationStates.POSSESSION);
      stateMachine.transition(AnimationStates.SHOOTING);
      stateMachine.transition(AnimationStates.REBOUNDING);
      expect(stateMachine.transition(AnimationStates.POSSESSION)).toBe(true);
      expect(stateMachine.getCurrentState()).toBe(AnimationStates.POSSESSION);
    });

    test('should prevent invalid transitions', () => {
      // IDLE cannot transition to IDLE (not in allowed transitions)
      expect(stateMachine.transition(AnimationStates.IDLE)).toBe(false);
      expect(stateMachine.getCurrentState()).toBe(AnimationStates.IDLE);
    });

    test('should prevent transitions to invalid states', () => {
      expect(stateMachine.transition('INVALID_STATE')).toBe(false);
      expect(stateMachine.getCurrentState()).toBe(AnimationStates.IDLE);
    });
  });

  describe('State Queries', () => {
    test('should correctly identify current state', () => {
      expect(stateMachine.is(AnimationStates.IDLE)).toBe(true);
      expect(stateMachine.is(AnimationStates.POSSESSION)).toBe(false);
    });

    test('should correctly identify multiple states', () => {
      expect(stateMachine.isAnyOf([AnimationStates.IDLE, AnimationStates.POSSESSION])).toBe(true);
      expect(stateMachine.isAnyOf([AnimationStates.SHOOTING, AnimationStates.REBOUNDING])).toBe(false);
    });

    test('should return correct possible transitions', () => {
      const possibleTransitions = stateMachine.getPossibleTransitions();
      expect(possibleTransitions).toContain(AnimationStates.POSSESSION);
      expect(possibleTransitions).toContain(AnimationStates.SHOOTING);
      expect(possibleTransitions).toContain(AnimationStates.REBOUNDING);
    });
  });

  describe('Transition History', () => {
    test('should record transition history', () => {
      stateMachine.transition(AnimationStates.POSSESSION);
      stateMachine.transition(AnimationStates.SHOOTING);
      
      const history = stateMachine.getTransitionHistory();
      expect(history).toHaveLength(2);
      expect(history[0].from).toBe(AnimationStates.IDLE);
      expect(history[0].to).toBe(AnimationStates.POSSESSION);
      expect(history[1].from).toBe(AnimationStates.POSSESSION);
      expect(history[1].to).toBe(AnimationStates.SHOOTING);
    });

    test('should limit transition history to prevent memory leaks', () => {
      // Create many transitions
      for (let i = 0; i < 60; i++) {
        stateMachine.transition(AnimationStates.POSSESSION);
        stateMachine.transition(AnimationStates.IDLE);
      }
      
      const history = stateMachine.getTransitionHistory();
      expect(history.length).toBeLessThanOrEqual(50);
    });

    test('should include context in transition history', () => {
      const context = { reason: 'test', data: { value: 123 } };
      stateMachine.transition(AnimationStates.POSSESSION, context);
      
      const history = stateMachine.getTransitionHistory();
      expect(history[0].context).toEqual(context);
    });
  });

  describe('Event Listeners', () => {
    test('should notify listeners on state change', () => {
      const listener = jest.fn();
      stateMachine.addListener('stateChange', listener);
      
      stateMachine.transition(AnimationStates.POSSESSION);
      
      expect(listener).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        AnimationStates.POSSESSION,
        {}
      );
    });

    test('should notify specific state listeners', () => {
      const possessionListener = jest.fn();
      stateMachine.addListener(AnimationStates.POSSESSION, possessionListener);
      
      stateMachine.transition(AnimationStates.POSSESSION);
      
      expect(possessionListener).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        AnimationStates.POSSESSION,
        {}
      );
    });

    test('should handle listener errors gracefully', () => {
      const errorListener = jest.fn().mockImplementation(() => {
        throw new Error('Listener error');
      });
      const normalListener = jest.fn();
      
      stateMachine.addListener('stateChange', errorListener);
      stateMachine.addListener('stateChange', normalListener);
      
      // Should not throw error
      expect(() => stateMachine.transition(AnimationStates.POSSESSION)).not.toThrow();
      
      // Normal listener should still be called
      expect(normalListener).toHaveBeenCalled();
    });

    test('should allow removing listeners', () => {
      const listener = jest.fn();
      stateMachine.addListener('stateChange', listener);
      stateMachine.removeListener('stateChange', listener);
      
      stateMachine.transition(AnimationStates.POSSESSION);
      
      expect(listener).not.toHaveBeenCalled();
    });
  });

  describe('Concurrent Transitions', () => {
    test('should prevent concurrent transitions', () => {
      // Mock a transition that takes time
      const originalTransition = stateMachine.transition.bind(stateMachine);
      stateMachine.transition = jest.fn().mockImplementation((newState) => {
        stateMachine.isTransitioning = true;
        return originalTransition(newState);
      });
      
      // First transition should work
      expect(stateMachine.transition(AnimationStates.POSSESSION)).toBe(true);
      
      // Second transition should be prevented
      expect(stateMachine.transition(AnimationStates.SHOOTING)).toBe(false);
    });
  });

  describe('Reset Functionality', () => {
    test('should reset to initial state', () => {
      stateMachine.transition(AnimationStates.POSSESSION);
      stateMachine.transition(AnimationStates.SHOOTING);
      
      stateMachine.reset();
      
      expect(stateMachine.getCurrentState()).toBe(AnimationStates.IDLE);
      expect(stateMachine.getPreviousState()).toBe(null);
      expect(stateMachine.getTransitionHistory()).toHaveLength(0);
    });

    test('should reset to custom initial state', () => {
      stateMachine.transition(AnimationStates.POSSESSION);
      stateMachine.transition(AnimationStates.SHOOTING);
      
      stateMachine.reset(AnimationStates.REBOUNDING);
      
      expect(stateMachine.getCurrentState()).toBe(AnimationStates.REBOUNDING);
      expect(stateMachine.getPreviousState()).toBe(null);
    });
  });

  describe('Debug Mode', () => {
    test('should enable debug logging', () => {
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();
      
      stateMachine.setDebug(true);
      stateMachine.transition(AnimationStates.POSSESSION);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'SimplifiedStateMachine: Transition',
        expect.objectContaining({
          from: AnimationStates.IDLE,
          to: AnimationStates.POSSESSION
        })
      );
      
      consoleSpy.mockRestore();
    });
  });

  describe('State Validation', () => {
    test('should validate state names', () => {
      expect(stateMachine.isValidState(AnimationStates.IDLE)).toBe(true);
      expect(stateMachine.isValidState(AnimationStates.POSSESSION)).toBe(true);
      expect(stateMachine.isValidState('INVALID_STATE')).toBe(false);
      expect(stateMachine.isValidState(null)).toBe(false);
      expect(stateMachine.isValidState(undefined)).toBe(false);
    });
  });

  describe('State Descriptions', () => {
    test('should provide state descriptions', () => {
      expect(stateMachine.getStateDescription(AnimationStates.IDLE))
        .toBe('No active animation - system is ready');
      expect(stateMachine.getStateDescription(AnimationStates.POSSESSION))
        .toBe('Team has ball and is setting up offense');
      expect(stateMachine.getStateDescription(AnimationStates.SHOOTING))
        .toBe('Shot attempt in progress');
      expect(stateMachine.getStateDescription(AnimationStates.REBOUNDING))
        .toBe('Rebound situation in progress');
    });

    test('should handle unknown states', () => {
      expect(stateMachine.getStateDescription('UNKNOWN_STATE'))
        .toBe('Unknown state');
    });
  });

  describe('Status Information', () => {
    test('should provide comprehensive status', () => {
      stateMachine.transition(AnimationStates.POSSESSION);
      stateMachine.transition(AnimationStates.SHOOTING);
      
      const status = stateMachine.getStatus();
      
      expect(status.currentState).toBe(AnimationStates.SHOOTING);
      expect(status.previousState).toBe(AnimationStates.POSSESSION);
      expect(status.isTransitioning).toBe(false);
      expect(status.transitionCount).toBe(2);
      expect(status.debug).toBe(false);
    });
  });
});

describe('State Transitions Matrix', () => {
  test('should have correct transition rules', () => {
    // IDLE can go to any state
    expect(StateTransitions[AnimationStates.IDLE]).toContain(AnimationStates.POSSESSION);
    expect(StateTransitions[AnimationStates.IDLE]).toContain(AnimationStates.SHOOTING);
    expect(StateTransitions[AnimationStates.IDLE]).toContain(AnimationStates.REBOUNDING);
    
    // POSSESSION can go to SHOOTING, REBOUNDING, or IDLE
    expect(StateTransitions[AnimationStates.POSSESSION]).toContain(AnimationStates.SHOOTING);
    expect(StateTransitions[AnimationStates.POSSESSION]).toContain(AnimationStates.REBOUNDING);
    expect(StateTransitions[AnimationStates.POSSESSION]).toContain(AnimationStates.IDLE);
    
    // SHOOTING can go to REBOUNDING, POSSESSION, or IDLE
    expect(StateTransitions[AnimationStates.SHOOTING]).toContain(AnimationStates.REBOUNDING);
    expect(StateTransitions[AnimationStates.SHOOTING]).toContain(AnimationStates.POSSESSION);
    expect(StateTransitions[AnimationStates.SHOOTING]).toContain(AnimationStates.IDLE);
    
    // REBOUNDING can go to POSSESSION, SHOOTING, or IDLE
    expect(StateTransitions[AnimationStates.REBOUNDING]).toContain(AnimationStates.POSSESSION);
    expect(StateTransitions[AnimationStates.REBOUNDING]).toContain(AnimationStates.SHOOTING);
    expect(StateTransitions[AnimationStates.REBOUNDING]).toContain(AnimationStates.IDLE);
  });
});

describe('Basketball Flow Integration', () => {
  let stateMachine;

  beforeEach(() => {
    stateMachine = new SimplifiedStateMachine();
  });

  test('should handle complete possession flow', () => {
    // Start with possession
    expect(stateMachine.transition(AnimationStates.POSSESSION)).toBe(true);
    
    // Take a shot
    expect(stateMachine.transition(AnimationStates.SHOOTING)).toBe(true);
    
    // Miss and rebound
    expect(stateMachine.transition(AnimationStates.REBOUNDING)).toBe(true);
    
    // Get possession back
    expect(stateMachine.transition(AnimationStates.POSSESSION)).toBe(true);
    
    // Make a shot and return to idle
    expect(stateMachine.transition(AnimationStates.SHOOTING)).toBe(true);
    expect(stateMachine.transition(AnimationStates.IDLE)).toBe(true);
  });

  test('should handle fast break flow', () => {
    // Start from rebound
    stateMachine.transition(AnimationStates.REBOUNDING);
    
    // Fast break to shooting
    expect(stateMachine.transition(AnimationStates.SHOOTING)).toBe(true);
    
    // Make shot, return to idle
    expect(stateMachine.transition(AnimationStates.IDLE)).toBe(true);
  });

  test('should handle turnover flow', () => {
    // Start with possession
    stateMachine.transition(AnimationStates.POSSESSION);
    
    // Turnover, return to idle
    expect(stateMachine.transition(AnimationStates.IDLE)).toBe(true);
  });
});
