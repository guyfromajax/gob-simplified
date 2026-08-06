/**
 * AnimationEngine Tests
 * 
 * Tests for the centralized animation routing and execution system
 */

import { AnimationEngine } from '../AnimationEngine.js';

// Mock Phaser scene
const createMockScene = () => ({
  events: {
    on: jest.fn(),
    off: jest.fn(),
    emit: jest.fn()
  },
  time: {
    delayedCall: jest.fn()
  },
  stateMachine: {
    is: jest.fn(() => false),
    state: 'HalfCourt'
  },
  offenseTeamId: 'home_team',
  possessionFlipInProgress: false
});

// Mock context
const createMockContext = () => ({
  playerSprites: {},
  ballSprite: {},
  simData: { home_team_id: 'home_team', away_team_id: 'away_team' },
  onUpdate: jest.fn(),
  onAction: jest.fn()
});

describe('AnimationEngine', () => {
  let engine;
  let mockScene;
  let mockContext;

  beforeEach(() => {
    mockScene = createMockScene();
    mockContext = createMockContext();
    engine = new AnimationEngine(mockScene);
  });

  describe('Initialization', () => {
    test('should initialize with default handlers', () => {
      const status = engine.getStatus();
      expect(status.registeredHandlers).toContain('FREE_THROW');
      expect(status.registeredHandlers).toContain('FAST_BREAK');
      expect(status.registeredHandlers).toContain('DEFAULT');
    });

    test('should not be processing initially', () => {
      const status = engine.getStatus();
      expect(status.isProcessing).toBe(false);
    });
  });

  describe('Handler Determination', () => {
    test('should route fast break turns correctly', () => {
      const turnData = { fast_break: true, result_type: 'MAKE' };
      const handler = engine.determineHandler(turnData);
      expect(handler).toBe(engine.animationHandlers.get('FAST_BREAK'));
    });

    test('should route free throw turns correctly', () => {
      const turnData = { result_type: 'FREE_THROW' };
      const handler = engine.determineHandler(turnData);
      expect(handler).toBe(engine.animationHandlers.get('FREE_THROW'));
    });

    test('should route shot attempts correctly', () => {
      const turnData = { result_type: 'MAKE', shooter: 'Player1' };
      const handler = engine.determineHandler(turnData);
      expect(handler).toBe(engine.animationHandlers.get('SHOT_ATTEMPT'));
    });

    test('should route rebounds correctly', () => {
      const turnData = { rebounderId: 'Player1', result_type: 'DREB' };
      const handler = engine.determineHandler(turnData);
      expect(handler).toBe(engine.animationHandlers.get('REBOUND'));
    });

    test('should use default handler for unknown types', () => {
      const turnData = { result_type: 'UNKNOWN_TYPE' };
      const handler = engine.determineHandler(turnData);
      expect(handler).toBe(engine.animationHandlers.get('DEFAULT'));
    });
  });

  describe('Final Turn UESS hold', () => {
    test('_isFinalTurnSchemaShot detects make/miss/block only', () => {
      expect(engine._isFinalTurnSchemaShot({ final_turn: true, result_type: 'MISS' })).toBe(true);
      expect(engine._isFinalTurnSchemaShot({ final_turn: false, result_type: 'MISS' })).toBe(false);
    });
  });

  describe('Shot Attempt Detection', () => {
    test('should detect shot attempts by result type', () => {
      expect(engine.isShotAttempt({ result_type: 'MAKE' })).toBe(true);
      expect(engine.isShotAttempt({ result_type: 'MISS' })).toBe(true);
    });

    test('should detect shot attempts by shooter', () => {
      expect(engine.isShotAttempt({ shooter: 'Player1' })).toBe(true);
    });

    test('should detect shot attempts by shot score', () => {
      expect(engine.isShotAttempt({ shot_score: 100 })).toBe(true);
    });

    test('should not detect non-shot attempts', () => {
      expect(engine.isShotAttempt({ result_type: 'TURNOVER' })).toBe(false);
      expect(engine.isShotAttempt({})).toBe(false);
    });
  });

  describe('Rebound Detection', () => {
    test('should detect rebounds by rebounderId', () => {
      expect(engine.isRebound({ rebounderId: 'Player1' })).toBe(true);
    });

    test('should detect rebounds by rebound type', () => {
      expect(engine.isRebound({ rebound_type: 'DREB' })).toBe(true);
    });

    test('should detect rebounds by result type', () => {
      expect(engine.isRebound({ result_type: 'OREB' })).toBe(true);
      expect(engine.isRebound({ result_type: 'DREB' })).toBe(true);
    });

    test('should not detect non-rebounds', () => {
      expect(engine.isRebound({ result_type: 'MAKE' })).toBe(false);
      expect(engine.isRebound({})).toBe(false);
    });
  });

  describe('Turn Processing', () => {
    test('should process turns without errors', async () => {
      const turnData = { result_type: 'MAKE', shooter: 'Player1' };
      
      // Mock the handler to avoid actual execution
      const mockHandler = jest.fn().mockResolvedValue();
      engine.animationHandlers.set('SHOT_ATTEMPT', mockHandler);
      
      await engine.processTurn(turnData, mockContext);
      
      expect(mockHandler).toHaveBeenCalledWith(turnData, mockContext);
    });

    test('should prevent concurrent processing', async () => {
      const turnData1 = { result_type: 'MAKE' };
      const turnData2 = { result_type: 'MISS' };
      
      // Mock handler that takes time
      const mockHandler = jest.fn().mockImplementation(() => 
        new Promise(resolve => setTimeout(resolve, 100))
      );
      engine.animationHandlers.set('SHOT_ATTEMPT', mockHandler);
      
      // Start first turn
      const promise1 = engine.processTurn(turnData1, mockContext);
      
      // Try to start second turn immediately
      const promise2 = engine.processTurn(turnData2, mockContext);
      
      await Promise.all([promise1, promise2]);
      
      // First handler should be called, second should be skipped
      expect(mockHandler).toHaveBeenCalledTimes(1);
    });

    test('should handle processing errors gracefully', async () => {
      const turnData = { result_type: 'MAKE' };
      
      // Mock handler that throws error
      const mockHandler = jest.fn().mockRejectedValue(new Error('Test error'));
      engine.animationHandlers.set('SHOT_ATTEMPT', mockHandler);
      
      await expect(engine.processTurn(turnData, mockContext)).rejects.toThrow('Test error');
      
      // Should reset processing flag even after error
      expect(engine.getStatus().isProcessing).toBe(false);
    });
  });

  describe('Handler Registration', () => {
    test('should allow custom handler registration', () => {
      const customHandler = jest.fn();
      engine.registerHandler('CUSTOM_TYPE', customHandler);
      
      const status = engine.getStatus();
      expect(status.registeredHandlers).toContain('CUSTOM_TYPE');
    });

    test('should use custom handlers when registered', () => {
      const customHandler = jest.fn();
      engine.registerHandler('CUSTOM_TYPE', customHandler);
      
      const turnData = { result_type: 'CUSTOM_TYPE' };
      const handler = engine.determineHandler(turnData);
      
      expect(handler).toBe(customHandler);
    });
  });

  describe('Dependency Injection', () => {
    test('should accept ball controller and state machine', () => {
      const mockBallController = {};
      const mockStateMachine = {};
      
      engine.injectDependencies(mockBallController, mockStateMachine);
      
      const status = engine.getStatus();
      expect(status.hasBallController).toBe(true);
      expect(status.hasStateMachine).toBe(true);
    });
  });

  describe('Edge Cases', () => {
    test('should handle null turn data', () => {
      expect(() => engine.determineHandler(null)).not.toThrow();
    });

    test('should handle undefined turn data', () => {
      expect(() => engine.determineHandler(undefined)).not.toThrow();
    });

    test('should handle empty turn data', () => {
      const handler = engine.determineHandler({});
      expect(handler).toBe(engine.animationHandlers.get('DEFAULT'));
    });

    test('should handle malformed turn data', () => {
      const turnData = { result_type: null, fast_break: undefined };
      const handler = engine.determineHandler(turnData);
      expect(handler).toBe(engine.animationHandlers.get('DEFAULT'));
    });
  });
});

// Integration tests
describe('AnimationEngine Integration', () => {
  let engine;
  let mockScene;
  let mockContext;

  beforeEach(() => {
    mockScene = createMockScene();
    mockContext = createMockContext();
    engine = new AnimationEngine(mockScene);
  });

  test('should handle complete turn sequence', async () => {
    const turns = [
      { result_type: 'FREE_THROW', ftContext: { ftIndex: 1, ftTotal: 2 } },
      { result_type: 'FREE_THROW', ftContext: { ftIndex: 2, ftTotal: 2 } },
      { result_type: 'MAKE', shooter: 'Player1' },
      { fast_break: true, result_type: 'MISS' }
    ];

    // Mock all handlers
    const mockHandlers = {
      'FREE_THROW': jest.fn().mockResolvedValue(),
      'SHOT_ATTEMPT': jest.fn().mockResolvedValue(),
      'FAST_BREAK': jest.fn().mockResolvedValue()
    };

    engine.animationHandlers.set('FREE_THROW', mockHandlers.FREE_THROW);
    engine.animationHandlers.set('SHOT_ATTEMPT', mockHandlers.SHOT_ATTEMPT);
    engine.animationHandlers.set('FAST_BREAK', mockHandlers.FAST_BREAK);

    // Process all turns
    for (const turn of turns) {
      await engine.processTurn(turn, mockContext);
    }

    // Verify correct handlers were called
    expect(mockHandlers.FREE_THROW).toHaveBeenCalledTimes(2);
    expect(mockHandlers.SHOT_ATTEMPT).toHaveBeenCalledTimes(1);
    expect(mockHandlers.FAST_BREAK).toHaveBeenCalledTimes(1);
  });
});
