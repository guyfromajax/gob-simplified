/**
 * SimplifiedStateMachine - Clean Basketball State Management
 * 
 * Replaces the complex 8-state system with a simple 4-state system
 * that matches real basketball flow and eliminates transition conflicts.
 * 
 * States:
 * - IDLE: No active animation
 * - POSSESSION: Team has the ball and is setting up offense
 * - SHOOTING: Shot attempt in progress
 * - REBOUNDING: Rebound situation in progress
 */

export const AnimationStates = {
  IDLE: 'IDLE',
  POSSESSION: 'POSSESSION', 
  SHOOTING: 'SHOOTING',
  REBOUNDING: 'REBOUNDING'
};

export const StateTransitions = {
  [AnimationStates.IDLE]: [
    AnimationStates.POSSESSION,
    AnimationStates.SHOOTING,
    AnimationStates.REBOUNDING
  ],
  [AnimationStates.POSSESSION]: [
    AnimationStates.SHOOTING,
    AnimationStates.REBOUNDING,
    AnimationStates.IDLE
  ],
  [AnimationStates.SHOOTING]: [
    AnimationStates.REBOUNDING,
    AnimationStates.POSSESSION,
    AnimationStates.IDLE
  ],
  [AnimationStates.REBOUNDING]: [
    AnimationStates.POSSESSION,
    AnimationStates.SHOOTING,
    AnimationStates.IDLE
  ]
};

export class SimplifiedStateMachine {
  constructor(initialState = AnimationStates.IDLE) {
    this.currentState = initialState;
    this.previousState = null;
    this.transitionHistory = [];
    this.listeners = new Map();
    this.isTransitioning = false;
    
    // Debug logging
    this.debug = false;
  }

  /**
   * Transition to a new state
   */
  transition(newState, context = {}) {
    if (this.isTransitioning) {
      console.warn('SimplifiedStateMachine: Already transitioning, skipping', {
        from: this.currentState,
        to: newState
      });
      return false;
    }

    if (!this.isValidTransition(newState)) {
      console.error('SimplifiedStateMachine: Invalid transition', {
        from: this.currentState,
        to: newState,
        allowedTransitions: StateTransitions[this.currentState]
      });
      return false;
    }

    this.isTransitioning = true;

    try {
      const oldState = this.currentState;
      this.previousState = oldState;
      this.currentState = newState;

      // Record transition
      this.transitionHistory.push({
        from: oldState,
        to: newState,
        timestamp: Date.now(),
        context
      });

      // Keep only last 50 transitions to prevent memory leaks
      if (this.transitionHistory.length > 50) {
        this.transitionHistory = this.transitionHistory.slice(-50);
      }

      if (this.debug) {
        console.log('SimplifiedStateMachine: Transition', {
          from: oldState,
          to: newState,
          context
        });
      }

      // Notify listeners
      this.notifyListeners(oldState, newState, context);

      return true;

    } finally {
      this.isTransitioning = false;
    }
  }

  /**
   * Check if a transition is valid
   */
  isValidTransition(newState) {
    const allowedTransitions = StateTransitions[this.currentState] || [];
    return allowedTransitions.includes(newState);
  }

  /**
   * Get current state
   */
  getCurrentState() {
    return this.currentState;
  }

  /**
   * Get previous state
   */
  getPreviousState() {
    return this.previousState;
  }

  /**
   * Check if currently in a specific state
   */
  is(state) {
    return this.currentState === state;
  }

  /**
   * Check if currently in any of the given states
   */
  isAnyOf(states) {
    return states.includes(this.currentState);
  }

  /**
   * Get transition history
   */
  getTransitionHistory(limit = 10) {
    return this.transitionHistory.slice(-limit);
  }

  /**
   * Add a state change listener
   */
  addListener(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
  }

  /**
   * Remove a state change listener
   */
  removeListener(event, callback) {
    if (this.listeners.has(event)) {
      const callbacks = this.listeners.get(event);
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  /**
   * Notify all listeners of a state change
   */
  notifyListeners(fromState, toState, context) {
    // Notify general state change listeners
    if (this.listeners.has('stateChange')) {
      this.listeners.get('stateChange').forEach(callback => {
        try {
          callback(fromState, toState, context);
        } catch (error) {
          console.error('SimplifiedStateMachine: Listener error', error);
        }
      });
    }

    // Notify specific state listeners
    if (this.listeners.has(toState)) {
      this.listeners.get(toState).forEach(callback => {
        try {
          callback(fromState, toState, context);
        } catch (error) {
          console.error('SimplifiedStateMachine: Listener error', error);
        }
      });
    }
  }

  /**
   * Reset to initial state
   */
  reset(initialState = AnimationStates.IDLE) {
    this.currentState = initialState;
    this.previousState = null;
    this.transitionHistory = [];
    this.isTransitioning = false;
  }

  /**
   * Enable/disable debug logging
   */
  setDebug(enabled) {
    this.debug = enabled;
  }

  /**
   * Get current status
   */
  getStatus() {
    return {
      currentState: this.currentState,
      previousState: this.previousState,
      isTransitioning: this.isTransitioning,
      transitionCount: this.transitionHistory.length,
      debug: this.debug
    };
  }

  /**
   * Get all possible transitions from current state
   */
  getPossibleTransitions() {
    return StateTransitions[this.currentState] || [];
  }

  /**
   * Check if a state is valid
   */
  isValidState(state) {
    return Object.values(AnimationStates).includes(state);
  }

  /**
   * Get state description for debugging
   */
  getStateDescription(state = this.currentState) {
    const descriptions = {
      [AnimationStates.IDLE]: 'No active animation - system is ready',
      [AnimationStates.POSSESSION]: 'Team has ball and is setting up offense',
      [AnimationStates.SHOOTING]: 'Shot attempt in progress',
      [AnimationStates.REBOUNDING]: 'Rebound situation in progress'
    };
    return descriptions[state] || 'Unknown state';
  }
}

export default SimplifiedStateMachine;
