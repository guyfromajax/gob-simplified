/**
 * Test Configuration for Phase 1 Animation System
 * 
 * Configuration and utilities for running Phase 1 component tests
 */

export const TestConfig = {
  // Test environment settings
  environment: {
    isDevelopment: true,
    enableDebugLogging: true,
    mockPhaserComponents: true
  },

  // Test data generators
  dataGenerators: {
    // Generate mock turn data
    createTurnData: (resultType, index = 1, additionalData = {}) => ({
      index,
      result_type: resultType,
      player_id: 'player1',
      team_id: 'home',
      timestamp: Date.now(),
      ...additionalData
    }),

    // Generate mock player sprite
    createPlayerSprite: (playerId = 'player1', team = 'home', x = 150, y = 250) => ({
      playerId,
      team,
      x,
      y,
      depth: 10,
      visible: true
    }),

    // Generate mock ball sprite
    createBallSprite: (x = 100, y = 200) => ({
      x,
      y,
      visible: false,
      depth: 0,
      setPosition: jest.fn(),
      setVisible: jest.fn(),
      setDepth: jest.fn()
    }),

    // Generate mock scene
    createScene: () => ({
      events: {
        on: jest.fn(),
        off: jest.fn(),
        emit: jest.fn()
      },
      time: {
        now: Date.now()
      }
    })
  },

  // Test scenarios
  scenarios: {
    // Basketball turn types
    turnTypes: [
      'FREE_THROW',
      'FAST_BREAK', 
      'SIDE_INBOUND',
      'TURNOVER',
      'MAKE',
      'MISS',
      'REBOUND'
    ],

    // State transitions
    stateTransitions: [
      { from: 'IDLE', to: 'POSSESSION', trigger: 'ball_attached' },
      { from: 'POSSESSION', to: 'SHOOTING', trigger: 'ball_detached_for_shot' },
      { from: 'SHOOTING', to: 'REBOUNDING', trigger: 'shot_missed' },
      { from: 'REBOUNDING', to: 'POSSESSION', trigger: 'rebound_caught' },
      { from: 'POSSESSION', to: 'IDLE', trigger: 'turnover' }
    ],

    // Basketball sequences
    sequences: [
      {
        name: 'Shot Sequence',
        turns: [
          { type: 'MISS', description: 'Player takes shot' },
          { type: 'REBOUND', description: 'Defensive rebound' }
        ]
      },
      {
        name: 'Pass Sequence', 
        turns: [
          { type: 'MAKE', description: 'Player makes pass' }
        ]
      },
      {
        name: 'Turnover Sequence',
        turns: [
          { type: 'TURNOVER', description: 'Player commits turnover' }
        ]
      },
      {
        name: 'Free Throw Sequence',
        turns: [
          { type: 'FREE_THROW', description: 'First free throw' },
          { type: 'FREE_THROW', description: 'Second free throw' }
        ]
      },
      {
        name: 'Fast Break Sequence',
        turns: [
          { type: 'FAST_BREAK', description: 'Fast break initiated' },
          { type: 'MISS', description: 'Fast break shot missed' },
          { type: 'REBOUND', description: 'Defensive rebound' }
        ]
      }
    ]
  },

  // Test utilities
  utilities: {
    // Wait for async operations
    wait: (ms) => new Promise(resolve => setTimeout(resolve, ms)),

    // Create test promise that resolves after condition
    waitForCondition: (condition, timeout = 1000) => {
      return new Promise((resolve, reject) => {
        const startTime = Date.now();
        const check = () => {
          if (condition()) {
            resolve();
          } else if (Date.now() - startTime > timeout) {
            reject(new Error('Condition timeout'));
          } else {
            setTimeout(check, 10);
          }
        };
        check();
      });
    },

    // Mock console methods
    mockConsole: () => {
      const originalConsole = { ...console };
      console.log = jest.fn();
      console.warn = jest.fn();
      console.error = jest.fn();
      return () => {
        Object.assign(console, originalConsole);
      };
    },

    // Create test error
    createTestError: (message = 'Test error') => new Error(message)
  },

  // Test expectations
  expectations: {
    // Component initialization expectations
    componentInit: {
      AnimationEngine: {
        hasScene: true,
        hasPlayerSprites: true,
        hasBallSprite: true,
        hasOnUpdate: true,
        isProcessingTurn: false
      },
      SimplifiedStateMachine: {
        initialState: 'IDLE',
        canTransition: true,
        hasListeners: true
      },
      BallController: {
        currentOwner: null,
        isAttached: false,
        isInFlight: false,
        hasBallSprite: true
      },
      AnimationRouter: {
        hasStateMachine: true,
        hasBallController: true,
        hasAnimationEngine: true,
        isInitialized: true
      }
    },

    // State transition expectations
    stateTransitions: {
      'IDLE → POSSESSION': { valid: true, trigger: 'ball_attached' },
      'POSSESSION → SHOOTING': { valid: true, trigger: 'ball_detached_for_shot' },
      'SHOOTING → REBOUNDING': { valid: true, trigger: 'shot_missed' },
      'REBOUNDING → POSSESSION': { valid: true, trigger: 'rebound_caught' },
      'POSSESSION → IDLE': { valid: true, trigger: 'turnover' },
      'IDLE → SHOOTING': { valid: false, reason: 'Invalid transition' },
      'SHOOTING → POSSESSION': { valid: false, reason: 'Invalid transition' }
    }
  }
};

export default TestConfig;
