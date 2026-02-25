/**
 * AnimationRouter Tests
 * 
 * Tests for the basic routing system that connects all Phase 1 components
 */

import { AnimationRouter } from '../AnimationRouter.js';
import { AnimationStates } from '../SimplifiedStateMachine.js';

// Mock dependencies
jest.mock('../AnimationEngine.js');
jest.mock('../SimplifiedStateMachine.js');
jest.mock('../BallController.js');
jest.mock('../turnPreparation.js', () => ({
  prepareTurnForAnimation: jest.fn().mockResolvedValue(undefined),
  finalizeTurnAfterAnimation: jest.fn().mockResolvedValue(undefined),
}));

// Mock debug flags
jest.mock('../../utils/debugFlags.js', () => ({
  DebugFlags: {
    ANIMATION_ROUTER: true
  }
}));

// Mock Phaser scene
const createMockScene = () => ({
  events: {
    on: jest.fn(),
    off: jest.fn(),
    emit: jest.fn()
  }
});

// Mock ball sprite
const createMockBallSprite = () => ({
  x: 100,
  y: 200,
  visible: false,
  setPosition: jest.fn(),
  setVisible: jest.fn(),
  setDepth: jest.fn()
});

// Mock player sprites
const createMockPlayerSprites = () => ({
  'player1': {
    playerId: 'player1',
    team: 'home',
    x: 150,
    y: 250
  },
  'player2': {
    playerId: 'player2',
    team: 'away',
    x: 200,
    y: 300
  }
});

// Mock turn data
const createMockTurnData = (resultType = 'MAKE', index = 1) => ({
  index,
  result_type: resultType,
  player_id: 'player1',
  possession_team_id: 'home'
});

describe('AnimationRouter', () => {
  let animationRouter;
  let mockScene;
  let mockBallSprite;
  let mockPlayerSprites;
  let mockOnUpdate;

  beforeEach(() => {
    // Reset all mocks
    jest.clearAllMocks();
    
    // Create mock objects
    mockScene = createMockScene();
    mockBallSprite = createMockBallSprite();
    mockPlayerSprites = createMockPlayerSprites();
    mockOnUpdate = jest.fn();
    
    // Create router instance
    animationRouter = new AnimationRouter(
      mockScene,
      mockPlayerSprites,
      mockBallSprite,
      mockOnUpdate
    );
  });

  describe('Initialization', () => {
    test('should initialize with all components', () => {
      expect(animationRouter.stateMachine).toBeDefined();
      expect(animationRouter.ballController).toBeDefined();
      expect(animationRouter.animationEngine).toBeDefined();
      expect(animationRouter.isInitialized).toBe(true);
    });

    test('should set up event handlers', () => {
      expect(animationRouter.ballController.onAttachment).toHaveBeenCalled();
      expect(animationRouter.ballController.onDetachment).toHaveBeenCalled();
      expect(animationRouter.stateMachine.on).toHaveBeenCalled();
    });

    test('should start in IDLE state', () => {
      expect(animationRouter.stateMachine.state).toBe(AnimationStates.IDLE);
    });

    test('should not initialize twice', () => {
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
      
      animationRouter.initialize();
      
      expect(consoleSpy).toHaveBeenCalledWith('AnimationRouter: Already initialized');
      
      consoleSpy.mockRestore();
    });
  });

  describe('Turn Processing', () => {
    test('should process a simple turn', async () => {
      const turnData = createMockTurnData('MAKE');
      
      await animationRouter.processTurn(turnData);
      
      expect(animationRouter.animationEngine.processTurn).toHaveBeenCalledWith(turnData);
      expect(animationRouter.currentTurn).toBe(null);
    });

    test('should queue turns when already processing', async () => {
      const turn1 = createMockTurnData('MAKE', 1);
      const turn2 = createMockTurnData('MISS', 2);
      
      // Mock processing to take time
      animationRouter.animationEngine.processTurn.mockImplementation(() => 
        new Promise(resolve => setTimeout(resolve, 100))
      );
      
      // Start processing first turn
      const processPromise = animationRouter.processTurn(turn1);
      
      // Try to process second turn while first is processing
      animationRouter.processTurn(turn2);
      
      // Wait for first turn to complete
      await processPromise;
      
      expect(animationRouter.animationQueue).toContain(turn2);
    });

    test('should handle processing errors gracefully', async () => {
      const turnData = createMockTurnData('MAKE');
      const error = new Error('Processing error');
      
      animationRouter.animationEngine.processTurn.mockRejectedValue(error);
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      await animationRouter.processTurn(turnData);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'AnimationRouter: Error processing turn',
        error
      );
      
      consoleSpy.mockRestore();
    });
  });

  describe('State Transitions', () => {
    test('should transition to SHOOTING for FREE_THROW', async () => {
      const turnData = createMockTurnData('FREE_THROW');
      
      await animationRouter.processTurn(turnData);
      
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.SHOOTING,
        { turnData }
      );
    });

    test('should transition to POSSESSION for FAST_BREAK', async () => {
      const turnData = createMockTurnData('FAST_BREAK');
      
      await animationRouter.processTurn(turnData);
      
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.POSSESSION,
        { turnData }
      );
    });

    test('should transition to REBOUNDING for MISS after SHOOTING', async () => {
      // First set state to SHOOTING
      animationRouter.stateMachine.state = AnimationStates.SHOOTING;
      
      const turnData = createMockTurnData('MISS');
      
      await animationRouter.processTurn(turnData);
      
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.REBOUNDING,
        { turnData }
      );
    });

    test('should transition to IDLE for TURNOVER', async () => {
      const turnData = createMockTurnData('TURNOVER');
      
      await animationRouter.processTurn(turnData);
      
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        { turnData }
      );
    });

    test('should handle unknown turn types gracefully', async () => {
      const turnData = createMockTurnData('UNKNOWN_TYPE');
      
      await animationRouter.processTurn(turnData);
      
      // Should not throw error and should attempt to maintain current state
      expect(animationRouter.animationEngine.processTurn).toHaveBeenCalledWith(turnData);
    });
  });

  describe('Ball Attachment Handling', () => {
    test('should handle ball attachment events', () => {
      const previousOwner = null;
      const newOwner = mockPlayerSprites['player1'];
      const options = {};
      
      animationRouter.handleBallAttachment(previousOwner, newOwner, options);
      
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.POSSESSION,
        { reason: 'ball_attached', playerId: 'player1' }
      );
    });

    test('should not transition if already in POSSESSION state', () => {
      animationRouter.stateMachine.state = AnimationStates.POSSESSION;
      
      const previousOwner = null;
      const newOwner = mockPlayerSprites['player1'];
      
      animationRouter.handleBallAttachment(previousOwner, newOwner);
      
      expect(animationRouter.stateMachine.transitionTo).not.toHaveBeenCalled();
    });
  });

  describe('Ball Detachment Handling', () => {
    test('should transition to SHOOTING for shot detachment', () => {
      const previousOwner = mockPlayerSprites['player1'];
      
      animationRouter.handleBallDetachment(previousOwner, 'shot');
      
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.SHOOTING,
        { reason: 'ball_detached_for_shot', playerId: 'player1' }
      );
    });

    test('should transition to IDLE for turnover detachment', () => {
      const previousOwner = mockPlayerSprites['player1'];
      
      animationRouter.handleBallDetachment(previousOwner, 'turnover');
      
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        { reason: 'turnover', playerId: 'player1' }
      );
    });

    test('should maintain state for pass detachment', () => {
      const previousOwner = mockPlayerSprites['player1'];
      
      animationRouter.handleBallDetachment(previousOwner, 'pass');
      
      expect(animationRouter.stateMachine.transitionTo).not.toHaveBeenCalled();
    });
  });

  describe('State Change Handling', () => {
    test('should handle IDLE state changes', () => {
      const data = {
        prevState: AnimationStates.POSSESSION,
        newState: AnimationStates.IDLE,
        context: {}
      };
      
      animationRouter.ballController.isBallAttached.mockReturnValue(true);
      
      animationRouter.handleStateChange(data);
      
      expect(animationRouter.ballController.detachFromPlayer).toHaveBeenCalledWith('state_idle');
    });

    test('should handle POSSESSION state changes', () => {
      const data = {
        prevState: AnimationStates.IDLE,
        newState: AnimationStates.POSSESSION,
        context: { playerId: 'player1' }
      };
      
      animationRouter.ballController.isBallAttached.mockReturnValue(false);
      animationRouter.findPlayerSprite.mockReturnValue(mockPlayerSprites['player1']);
      
      animationRouter.handleStateChange(data);
      
      expect(animationRouter.ballController.attachToPlayer).toHaveBeenCalledWith(
        mockPlayerSprites['player1']
      );
    });

    test('should handle SHOOTING state changes', () => {
      const data = {
        prevState: AnimationStates.POSSESSION,
        newState: AnimationStates.SHOOTING,
        context: {}
      };
      
      animationRouter.handleStateChange(data);
      
      // Should not detach ball in shooting state
      expect(animationRouter.ballController.detachFromPlayer).not.toHaveBeenCalled();
    });

    test('should handle REBOUNDING state changes', () => {
      const data = {
        prevState: AnimationStates.SHOOTING,
        newState: AnimationStates.REBOUNDING,
        context: {}
      };
      
      animationRouter.ballController.isBallAttached.mockReturnValue(true);
      
      animationRouter.handleStateChange(data);
      
      expect(animationRouter.ballController.detachFromPlayer).toHaveBeenCalledWith('rebound');
    });
  });

  describe('Player Sprite Finding', () => {
    test('should find existing player sprite', () => {
      const playerSprite = animationRouter.findPlayerSprite('player1');
      
      expect(playerSprite).toBe(mockPlayerSprites['player1']);
    });

    test('should return null for non-existent player', () => {
      const playerSprite = animationRouter.findPlayerSprite('nonexistent');
      
      expect(playerSprite).toBe(null);
    });
  });

  describe('Queue Processing', () => {
    test('should process queued turns', async () => {
      const turn1 = createMockTurnData('MAKE', 1);
      const turn2 = createMockTurnData('MISS', 2);
      
      animationRouter.animationQueue = [turn2];
      
      await animationRouter.processQueue();
      
      expect(animationRouter.animationEngine.processTurn).toHaveBeenCalledWith(turn2);
    });

    test('should handle empty queue', async () => {
      animationRouter.animationQueue = [];
      
      await animationRouter.processQueue();
      
      expect(animationRouter.animationEngine.processTurn).not.toHaveBeenCalled();
    });
  });

  describe('Error Handling', () => {
    test('should handle errors and reset to safe state', () => {
      const error = new Error('Test error');
      const turnData = createMockTurnData('MAKE');
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      animationRouter.handleError(error, turnData);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'AnimationRouter: Error occurred',
        expect.objectContaining({
          error: 'Test error',
          turnData,
          currentState: AnimationStates.IDLE
        })
      );
      
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        { reason: 'error_recovery' }
      );
      
      expect(animationRouter.ballController.reset).toHaveBeenCalled();
      
      consoleSpy.mockRestore();
    });
  });

  describe('Status and Information', () => {
    test('should return comprehensive status', () => {
      const status = animationRouter.getStatus();
      
      expect(status).toHaveProperty('isProcessing');
      expect(status).toHaveProperty('currentTurn');
      expect(status).toHaveProperty('stateMachine');
      expect(status).toHaveProperty('ballController');
      expect(status).toHaveProperty('animationEngine');
      expect(status).toHaveProperty('queue');
      expect(status).toHaveProperty('isInitialized');
    });

    test('should return system information', () => {
      const info = animationRouter.getSystemInfo();
      
      expect(info).toHaveProperty('components');
      expect(info).toHaveProperty('status');
      expect(info).toHaveProperty('capabilities');
      
      expect(info.components).toHaveProperty('stateMachine');
      expect(info.components).toHaveProperty('ballController');
      expect(info.components).toHaveProperty('animationEngine');
    });
  });

  describe('System Reset', () => {
    test('should reset entire system', () => {
      animationRouter.isProcessing = true;
      animationRouter.currentTurn = createMockTurnData('MAKE');
      animationRouter.animationQueue = [createMockTurnData('MISS')];
      
      animationRouter.reset();
      
      expect(animationRouter.isProcessing).toBe(false);
      expect(animationRouter.currentTurn).toBe(null);
      expect(animationRouter.animationQueue).toHaveLength(0);
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        { reason: 'system_reset' }
      );
      expect(animationRouter.ballController.reset).toHaveBeenCalled();
    });
  });

  describe('Debug Mode', () => {
    test('should enable debug mode', () => {
      animationRouter.setDebug(true);
      
      expect(animationRouter.ballController.setDebug).toHaveBeenCalledWith(true);
    });

    test('should disable debug mode', () => {
      animationRouter.setDebug(false);
      
      expect(animationRouter.ballController.setDebug).toHaveBeenCalledWith(false);
    });
  });

  describe('Integration Scenarios', () => {
    test('should handle complete shot sequence', async () => {
      // Start with possession
      animationRouter.stateMachine.state = AnimationStates.POSSESSION;
      
      // Take shot
      const shotTurn = createMockTurnData('MISS');
      await animationRouter.processTurn(shotTurn);
      
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.REBOUNDING,
        { turnData: shotTurn }
      );
    });

    test('should handle complete pass sequence', async () => {
      // Start with possession
      animationRouter.stateMachine.state = AnimationStates.POSSESSION;
      
      // Make pass
      const passTurn = createMockTurnData('MAKE');
      await animationRouter.processTurn(passTurn);
      
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.POSSESSION,
        { turnData: passTurn }
      );
    });

    test('should handle turnover sequence', async () => {
      // Start with possession
      animationRouter.stateMachine.state = AnimationStates.POSSESSION;
      
      // Turnover
      const turnoverTurn = createMockTurnData('TURNOVER');
      await animationRouter.processTurn(turnoverTurn);
      
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        { turnData: turnoverTurn }
      );
    });
  });

  describe('Clock interpolation (Phase 2)', () => {
    let clockScene;
    let mockGameClock;
    let mockShotClock;
    let mockTweensAdd;
    let clockRouter;

    beforeEach(() => {
      jest.clearAllMocks();
      mockGameClock = { syncWithBackend: jest.fn(), pause: jest.fn(), resume: jest.fn() };
      mockShotClock = { syncWithBackend: jest.fn(), pause: jest.fn(), resume: jest.fn() };
      mockTweensAdd = jest.fn(() => ({ remove: jest.fn() }));
      clockScene = {
        ...createMockScene(),
        gameClock: mockGameClock,
        shotClock: mockShotClock,
        tweens: { add: mockTweensAdd },
        simData: {},
        isPaused: false,
      };
      clockRouter = new AnimationRouter(
        clockScene,
        createMockPlayerSprites(),
        createMockBallSprite(),
        jest.fn()
      );
    });

    test('syncs both clocks to contract start when turn has snake_case clock fields', async () => {
      const turnData = {
        ...createMockTurnData('MAKE'),
        clock_start: 600,
        clock_end: 597,
        shot_clock_start: 24,
        shot_clock_end: 21,
        real_time_elapsed_ms: 1050,
      };
      await clockRouter.processTurn(turnData);
      expect(mockGameClock.syncWithBackend).toHaveBeenCalledWith(600);
      expect(mockShotClock.syncWithBackend).toHaveBeenCalledWith(24);
      expect(mockTweensAdd).toHaveBeenCalled();
    });

    test('syncs both clocks and runs tween when turn uses camelCase clock contract', async () => {
      const turnData = {
        ...createMockTurnData('MISS'),
        clockStart: 720,
        clockEnd: 717,
        shotClockStart: 18,
        shotClockEnd: 15,
        realTimeElapsedMs: 1050,
      };
      await clockRouter.processTurn(turnData);
      expect(mockGameClock.syncWithBackend).toHaveBeenCalledWith(720);
      expect(mockShotClock.syncWithBackend).toHaveBeenCalledWith(18);
      expect(mockTweensAdd).toHaveBeenCalledWith(
        expect.objectContaining({
          duration: 1050,
          ease: 'Linear',
        })
      );
    });

    test('adds tween when only shot clock moves (game clock unchanged)', async () => {
      const turnData = {
        ...createMockTurnData('MAKE'),
        clock_start: 600,
        clock_end: 600,
        shot_clock_start: 24,
        shot_clock_end: 21,
        real_time_elapsed_ms: 1050,
      };
      await clockRouter.processTurn(turnData);
      expect(mockGameClock.syncWithBackend).toHaveBeenCalledWith(600);
      expect(mockShotClock.syncWithBackend).toHaveBeenCalledWith(24);
      expect(mockTweensAdd).toHaveBeenCalled();
      const tweenConfig = mockTweensAdd.mock.calls[0][0];
      expect(typeof tweenConfig.onUpdate).toBe('function');
      tweenConfig.onUpdate();
      expect(mockShotClock.syncWithBackend).toHaveBeenCalledTimes(2);
    });

    test('does not add tween when durationMs is 0', async () => {
      const turnData = {
        ...createMockTurnData('SIDE_INBOUND'),
        clock_start: 600,
        clock_end: 600,
        shot_clock_start: 30,
        shot_clock_end: 30,
        real_time_elapsed_ms: 0,
      };
      await clockRouter.processTurn(turnData);
      expect(mockTweensAdd).not.toHaveBeenCalled();
    });

    test('tween onUpdate interpolates shot clock from start to end', async () => {
      const turnData = {
        ...createMockTurnData('MAKE'),
        clock_start: 600,
        clock_end: 597,
        shot_clock_start: 24,
        shot_clock_end: 21,
        real_time_elapsed_ms: 1050,
      };
      await clockRouter.processTurn(turnData);
      const tweenConfig = mockTweensAdd.mock.calls[0][0];
      const progressObj = Array.isArray(tweenConfig.targets) ? tweenConfig.targets[0] : tweenConfig.targets;
      progressObj.p = 0;
      tweenConfig.onUpdate();
      expect(mockShotClock.syncWithBackend).toHaveBeenNthCalledWith(2, 24);
      progressObj.p = 1;
      tweenConfig.onUpdate();
      expect(mockShotClock.syncWithBackend).toHaveBeenLastCalledWith(21);
    });
  });
});
