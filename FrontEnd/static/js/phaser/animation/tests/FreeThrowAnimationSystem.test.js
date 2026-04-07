/**
 * FreeThrowAnimationSystem Tests
 * 
 * Tests for the universal free throw animation system that handles all free throw scenarios
 */

import { FreeThrowAnimationSystem } from '../FreeThrowAnimationSystem.js';
import { AnimationStates } from '../SimplifiedStateMachine.js';

// Mock dependencies
jest.mock('../SimplifiedStateMachine.js');
const mockSynchronizeBallState = jest.fn();
const mockAttachBallToPlayer = jest.fn();
const mockGetBallController = jest.fn(() => ({
  isAttached: false,
  currentOwner: null,
  isInFlight: false
}));
const mockAnimateRebound = jest.fn(async () => {});
const mockRunDefensiveReboundSetup = jest.fn(async () => {});

jest.mock('../BallControllerAdapter.js', () => ({
  synchronizeBallState: mockSynchronizeBallState,
  attachBallToPlayer: mockAttachBallToPlayer,
  getBallController: mockGetBallController
}));
jest.mock('../ballManager.js', () => ({
  animateRebound: mockAnimateRebound
}));
jest.mock('../turnAnimation.js', () => ({
  runDefensiveReboundSetup: mockRunDefensiveReboundSetup
}));
jest.mock('../utils/debugFlags.js', () => ({
  DebugFlags: {
    FREE_THROW_ANIMATION: true
  }
}));

// Mock Phaser scene
const createMockScene = () => ({
  game: {
    config: {
      width: 800,
      height: 600
    }
  },
  tweens: {
    add: jest.fn().mockReturnValue({
      onComplete: jest.fn(),
      onUpdate: jest.fn()
    })
  },
  homeTeamId: 'home_team'
});

// Mock ball controller
const createMockBallController = () => ({
  ballSprite: {
    x: 100,
    y: 200,
    visible: false,
    setPosition: jest.fn(),
    setVisible: jest.fn()
  },
  detachFromPlayer: jest.fn(),
  startFlight: jest.fn(),
  endFlight: jest.fn(),
  updatePosition: jest.fn()
});

// Mock state machine
const createMockStateMachine = () => ({
  transitionTo: jest.fn(),
  transition: jest.fn()
});

// Mock player sprites
const createMockPlayerSprites = () => ({
  'player1': {
    playerId: 'player1',
    team: 'home',
    position: 'PG',
    x: 150,
    y: 250
  },
  'player2': {
    playerId: 'player2',
    team: 'away',
    position: 'SG',
    x: 200,
    y: 300
  }
});

// Mock turn data
const createMockFreeThrowTurnData = (resultType = 'MAKE', ftContext = {}) => ({
  index: 1,
  result_type: 'FREE_THROW',
  shooter_id: 'player1',
  possession_team_id: 'home_team',
  ftContext: {
    attempt: 1,
    total: 1,
    type: 'single',
    ...ftContext
  },
  actual_result: resultType // The actual outcome (MAKE/MISS)
});

describe('FreeThrowAnimationSystem', () => {
  let ftSystem;
  let mockScene;
  let mockBallController;
  let mockStateMachine;
  let mockPlayerSprites;

  beforeEach(() => {
    // Reset all mocks
    jest.clearAllMocks();
    
    // Create mock objects
    mockScene = createMockScene();
    mockBallController = createMockBallController();
    mockStateMachine = createMockStateMachine();
    mockPlayerSprites = createMockPlayerSprites();
    
    // Create free throw system
    ftSystem = new FreeThrowAnimationSystem(
      mockScene,
      mockBallController,
      mockStateMachine,
      mockPlayerSprites
    );
  });

  describe('Initialization', () => {
    test('should initialize with correct configuration', () => {
      expect(ftSystem.scene).toBe(mockScene);
      expect(ftSystem.ballController).toBe(mockBallController);
      expect(ftSystem.stateMachine).toBe(mockStateMachine);
      expect(ftSystem.playerSprites).toBe(mockPlayerSprites);
      
      expect(ftSystem.ftConfig).toHaveProperty('ftLine');
      expect(ftSystem.ftConfig).toHaveProperty('ftSpot');
      expect(ftSystem.ftConfig).toHaveProperty('shotDuration');
      expect(ftSystem.ftConfig).toHaveProperty('bounceDuration');
      expect(ftSystem.ftConfig).toHaveProperty('homeRim');
      expect(ftSystem.ftConfig).toHaveProperty('awayRim');
    });

    test('should start with no active sequence', () => {
      expect(ftSystem.activeSequence).toBe(null);
      expect(ftSystem.sequenceQueue).toHaveLength(0);
      expect(ftSystem.currentAttempt).toBe(0);
      expect(ftSystem.totalAttempts).toBe(0);
    });
  });

  describe('Free Throw Processing', () => {
    test('should process a made free throw correctly', async () => {
      const turnData = createMockFreeThrowTurnData('MAKE');
      
      await ftSystem.processFreeThrow(turnData);
      
      // Verify state transitions
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.SHOOTING,
        expect.objectContaining({
          reason: 'free_throw_initiated',
          shooter_id: 'player1'
        })
      );
      
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        expect.objectContaining({
          reason: 'free_throw_sequence_complete',
          shooter_id: 'player1',
          made: true
        })
      );
      
      // Verify ball controller calls
      expect(mockBallController.detachFromPlayer).toHaveBeenCalledWith('free_throw_shot');
      expect(mockBallController.startFlight).toHaveBeenCalled();
      expect(mockBallController.endFlight).toHaveBeenCalled();
    });

    test('should process a missed free throw correctly', async () => {
      const turnData = createMockFreeThrowTurnData('MISS');
      
      await ftSystem.processFreeThrow(turnData);
      
      // Verify state transitions
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.SHOOTING,
        expect.objectContaining({
          reason: 'free_throw_initiated'
        })
      );
      
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.REBOUNDING,
        expect.objectContaining({
          reason: 'free_throw_missed',
          shooter_id: 'player1'
        })
      );
      
      // Verify ball controller calls
      expect(mockBallController.detachFromPlayer).toHaveBeenCalledWith('free_throw_shot');
      expect(mockBallController.startFlight).toHaveBeenCalled();
      expect(mockBallController.endFlight).toHaveBeenCalled();
    });

    test('should queue free throws when already processing', async () => {
      const ft1 = createMockFreeThrowTurnData('MAKE');
      const ft2 = createMockFreeThrowTurnData('MISS');
      
      // Mock processing to take time
      mockScene.tweens.add.mockImplementation(() => ({
        onComplete: jest.fn(),
        onUpdate: jest.fn()
      }));
      
      // Start processing first free throw
      const processPromise = ftSystem.processFreeThrow(ft1);
      
      // Try to process second free throw while first is processing
      ftSystem.processFreeThrow(ft2);
      
      // Verify second free throw was queued
      expect(ftSystem.sequenceQueue).toContain(ft2);
      
      // Wait for first free throw to complete
      await processPromise;
    });

    test('should handle invalid free throw data gracefully', async () => {
      const invalidTurnData = { result_type: 'INVALID' };
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      await ftSystem.processFreeThrow(invalidTurnData);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'FreeThrowAnimationSystem: Error processing free throw',
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });

    test('should handle missing shooter sprite gracefully', async () => {
      const turnData = createMockFreeThrowTurnData('MAKE');
      turnData.shooter_id = 'nonexistent_player';
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      await ftSystem.processFreeThrow(turnData);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'FreeThrowAnimationSystem: Error processing free throw',
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });
  });

  describe('Free Throw Positioning', () => {
    test('should position shooter at free throw line', async () => {
      const turnData = createMockFreeThrowTurnData('MAKE');
      
      await ftSystem.processFreeThrow(turnData);
      
      // Verify tween was created for shooter positioning
      expect(mockScene.tweens.add).toHaveBeenCalledWith(
        expect.objectContaining({
          targets: mockPlayerSprites['player1'],
          duration: ftSystem.ftConfig.setupDuration,
          ease: ftSystem.ftConfig.setupEase
        })
      );
    });

    test('should calculate correct free throw position for home team', () => {
      const turnData = createMockFreeThrowTurnData('MAKE');
      turnData.possession_team_id = 'home_team';
      
      const position = ftSystem.calculateFreeThrowPosition(turnData);
      
      expect(position.x).toBe(ftSystem.ftConfig.ftLine.x);
      expect(position.y).toBe(ftSystem.ftConfig.ftLine.y);
    });

    test('should calculate correct free throw position for away team', () => {
      const turnData = createMockFreeThrowTurnData('MAKE');
      turnData.possession_team_id = 'away_team';
      
      const position = ftSystem.calculateFreeThrowPosition(turnData);
      
      expect(position.x).toBe(800 - ftSystem.ftConfig.ftLine.x); // Opposite side
      expect(position.y).toBe(ftSystem.ftConfig.ftLine.y);
    });
  });

  describe('Free Throw Shot Animation', () => {
    test('should animate ball from shooter to rim', async () => {
      const turnData = createMockFreeThrowTurnData('MAKE');
      
      await ftSystem.processFreeThrow(turnData);
      
      // Verify ball was positioned and made visible
      expect(mockBallController.ballSprite.setPosition).toHaveBeenCalled();
      expect(mockBallController.ballSprite.setVisible).toHaveBeenCalledWith(true);
      
      // Verify tween was created for ball animation
      expect(mockScene.tweens.add).toHaveBeenCalledWith(
        expect.objectContaining({
          targets: mockBallController.ballSprite,
          duration: ftSystem.ftConfig.shotDuration,
          ease: ftSystem.ftConfig.shotEase
        })
      );
    });

    test('should handle missing ball sprite gracefully', async () => {
      mockBallController.ballSprite = null;
      
      const turnData = createMockFreeThrowTurnData('MAKE');
      
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
      
      await ftSystem.processFreeThrow(turnData);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'FreeThrowAnimationSystem: No ball sprite available'
      );
      
      consoleSpy.mockRestore();
    });
  });

  describe('Free Throw Outcomes', () => {
    test('should handle made free throw correctly', async () => {
      const turnData = createMockFreeThrowTurnData('MAKE');
      
      await ftSystem.processFreeThrow(turnData);
      
      // Verify ball goes through rim (no bounce)
      expect(mockScene.tweens.add).toHaveBeenCalledWith(
        expect.objectContaining({
          targets: mockBallController.ballSprite,
          y: expect.any(Number),
          duration: 200,
          ease: 'Power2'
        })
      );
      
      // Verify ball is hidden after going through rim
      expect(mockBallController.ballSprite.setVisible).toHaveBeenCalledWith(false);
    });

    test('should handle missed free throw with bounce', async () => {
      const turnData = createMockFreeThrowTurnData('MISS');
      
      await ftSystem.processFreeThrow(turnData);
      
      // Verify bounce animation was created
      expect(mockScene.tweens.add).toHaveBeenCalledWith(
        expect.objectContaining({
          targets: mockBallController.ballSprite,
          x: expect.any(Number),
          y: expect.any(Number),
          duration: ftSystem.ftConfig.bounceDuration,
          ease: ftSystem.ftConfig.bounceEase
        })
      );
    });

    test('should scrub stale state and attach rebounder on final missed FT DREB before HCO setup', async () => {
      const turnData = createMockFreeThrowTurnData('MISS', {
        attempt: 1,
        total: 1
      });
      turnData.rebound_type = 'DREB';
      turnData.next_play_type = 'HCO';
      turnData.rebounderId = 'player2';

      await ftSystem.handleFinalMissedFreeThrow(turnData, { grid: { x: 50, y: 25 } });

      expect(mockSynchronizeBallState).toHaveBeenCalledWith(
        mockScene,
        expect.objectContaining({
          clearShotState: true,
          clearPutbackState: true,
          clearPassState: true,
          allowAttachment: true
        })
      );
      expect(mockAnimateRebound).toHaveBeenCalledWith(
        expect.objectContaining({
          scene: mockScene,
          rebounderId: 'player2',
          preserveBallPosition: true
        })
      );
      expect(mockAttachBallToPlayer).toHaveBeenCalledWith(
        mockScene,
        mockBallController.ballSprite,
        mockPlayerSprites.player2,
        expect.objectContaining({
          reason: 'ft_final_miss_dreb_pre_outlet'
        })
      );
      expect(mockRunDefensiveReboundSetup).toHaveBeenCalled();
    });

    test('should use rebounder_player_id fallback for final missed FT DREB attach', async () => {
      const turnData = createMockFreeThrowTurnData('MISS', {
        attempt: 1,
        total: 1
      });
      turnData.rebound_type = 'DREB';
      turnData.next_play_type = 'HCO';
      turnData.rebounder_player_id = 'player2';

      await ftSystem.handleFinalMissedFreeThrow(turnData, { grid: { x: 50, y: 25 } });

      expect(mockAnimateRebound).toHaveBeenCalledWith(
        expect.objectContaining({
          rebounderId: 'player2'
        })
      );
      expect(mockAttachBallToPlayer).toHaveBeenCalledWith(
        mockScene,
        mockBallController.ballSprite,
        mockPlayerSprites.player2,
        expect.objectContaining({
          reason: 'ft_final_miss_dreb_pre_outlet'
        })
      );
    });
  });

  describe('Free Throw Context', () => {
    test('should determine free throw context correctly', () => {
      const turnData = createMockFreeThrowTurnData('MAKE', {
        attempt: 2,
        total: 3,
        type: 'and_one'
      });
      
      const context = ftSystem.determineFreeThrowContext(turnData);
      
      expect(context.attempt).toBe(2);
      expect(context.total).toBe(3);
      expect(context.type).toBe('and_one');
      expect(context.isFinal).toBe(false);
    });

    test('should handle missing free throw context', () => {
      const turnData = createMockFreeThrowTurnData('MAKE');
      delete turnData.ftContext;
      
      const context = ftSystem.determineFreeThrowContext(turnData);
      
      expect(context.attempt).toBe(1);
      expect(context.total).toBe(1);
      expect(context.type).toBe('single');
      expect(context.isFinal).toBe(true);
    });
  });

  describe('Rim Coordinate Calculation', () => {
    test('should use home rim for home team free throws', async () => {
      const turnData = createMockFreeThrowTurnData('MAKE');
      turnData.possession_team_id = 'home_team';
      
      await ftSystem.processFreeThrow(turnData);
      
      // Verify home rim coordinates were used
      expect(mockScene.tweens.add).toHaveBeenCalledWith(
        expect.objectContaining({
          x: ftSystem.ftConfig.homeRim.x,
          y: ftSystem.ftConfig.homeRim.y
        })
      );
    });

    test('should use away rim for away team free throws', async () => {
      const turnData = createMockFreeThrowTurnData('MAKE');
      turnData.possession_team_id = 'away_team';
      
      await ftSystem.processFreeThrow(turnData);
      
      // Verify away rim coordinates were used
      expect(mockScene.tweens.add).toHaveBeenCalledWith(
        expect.objectContaining({
          x: ftSystem.ftConfig.awayRim.x,
          y: ftSystem.ftConfig.awayRim.y
        })
      );
    });
  });

  describe('Bounce Calculation', () => {
    test('should calculate bounce coordinates within court bounds', () => {
      const rimCoords = { x: 100, y: 200 };
      const turnData = createMockFreeThrowTurnData('MISS');
      
      const bounceCoords = ftSystem.calculateBounceCoords(rimCoords, turnData);
      
      // Verify bounce coordinates are within bounds
      expect(bounceCoords.x).toBeGreaterThanOrEqual(ftSystem.ftConfig.courtBounds.minX);
      expect(bounceCoords.x).toBeLessThanOrEqual(ftSystem.ftConfig.courtBounds.maxX);
      expect(bounceCoords.y).toBeGreaterThanOrEqual(ftSystem.ftConfig.courtBounds.minY);
      expect(bounceCoords.y).toBeLessThanOrEqual(ftSystem.ftConfig.courtBounds.maxY);
    });

    test('should generate random bounce coordinates', () => {
      const rimCoords = { x: 100, y: 200 };
      const turnData = createMockFreeThrowTurnData('MISS');
      
      const bounce1 = ftSystem.calculateBounceCoords(rimCoords, turnData);
      const bounce2 = ftSystem.calculateBounceCoords(rimCoords, turnData);
      
      // Bounces should be different (random)
      expect(bounce1.x).not.toBe(bounce2.x);
      expect(bounce1.y).not.toBe(bounce2.y);
    });
  });

  describe('Queue Management', () => {
    test('should process queued free throw sequences', async () => {
      const ft1 = createMockFreeThrowTurnData('MAKE');
      const ft2 = createMockFreeThrowTurnData('MISS');
      
      ftSystem.sequenceQueue = [ft2];
      
      await ftSystem.processSequenceQueue();
      
      // Verify second free throw was processed
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.SHOOTING,
        expect.objectContaining({
          shooter_id: 'player1'
        })
      );
    });

    test('should handle empty queue', async () => {
      ftSystem.sequenceQueue = [];
      
      await ftSystem.processSequenceQueue();
      
      // Should not throw error
      expect(mockStateMachine.transitionTo).not.toHaveBeenCalled();
    });
  });

  describe('Error Handling', () => {
    test('should handle free throw processing errors gracefully', async () => {
      const turnData = createMockFreeThrowTurnData('MAKE');
      
      // Mock error in state machine
      mockStateMachine.transitionTo.mockImplementation(() => {
        throw new Error('State machine error');
      });
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      await ftSystem.processFreeThrow(turnData);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'FreeThrowAnimationSystem: Error processing free throw',
        expect.any(Error)
      );
      
      // Verify system was reset to safe state
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        expect.objectContaining({
          reason: 'free_throw_error'
        })
      );
      
      consoleSpy.mockRestore();
    });

    test('should hide ball on error', async () => {
      const turnData = createMockFreeThrowTurnData('MAKE');
      
      // Mock error
      mockStateMachine.transitionTo.mockImplementation(() => {
        throw new Error('Test error');
      });
      
      await ftSystem.processFreeThrow(turnData);
      
      // Verify ball was hidden
      expect(mockBallController.ballSprite.setVisible).toHaveBeenCalledWith(false);
    });
  });

  describe('Configuration', () => {
    test('should update configuration', () => {
      const newConfig = {
        shotDuration: 1200,
        bounceDuration: 800
      };
      
      ftSystem.updateConfig(newConfig);
      
      expect(ftSystem.ftConfig.shotDuration).toBe(1200);
      expect(ftSystem.ftConfig.bounceDuration).toBe(800);
    });

    test('should preserve existing configuration when updating', () => {
      const originalConfig = { ...ftSystem.ftConfig };
      const newConfig = { shotDuration: 1200 };
      
      ftSystem.updateConfig(newConfig);
      
      expect(ftSystem.ftConfig.shotDuration).toBe(1200);
      expect(ftSystem.ftConfig.bounceDuration).toBe(originalConfig.bounceDuration);
      expect(ftSystem.ftConfig.ftLine).toEqual(originalConfig.ftLine);
    });
  });

  describe('System Status', () => {
    test('should return correct status', () => {
      const status = ftSystem.getStatus();
      
      expect(status).toHaveProperty('activeSequence');
      expect(status).toHaveProperty('sequenceQueue');
      expect(status).toHaveProperty('isProcessing');
      expect(status).toHaveProperty('currentAttempt');
      expect(status).toHaveProperty('totalAttempts');
      expect(status).toHaveProperty('ftConfig');
      
      expect(status.activeSequence).toBe(null);
      expect(status.sequenceQueue).toBe(0);
      expect(status.isProcessing).toBe(false);
      expect(status.currentAttempt).toBe(0);
      expect(status.totalAttempts).toBe(0);
    });

    test('should return correct status during processing', async () => {
      const turnData = createMockFreeThrowTurnData('MAKE');
      
      // Mock processing to take time
      mockScene.tweens.add.mockImplementation(() => ({
        onComplete: jest.fn(),
        onUpdate: jest.fn()
      }));
      
      const processPromise = ftSystem.processFreeThrow(turnData);
      
      // Check status during processing
      const status = ftSystem.getStatus();
      expect(status.activeSequence).toBe(turnData.index);
      expect(status.isProcessing).toBe(true);
      
      await processPromise;
    });
  });

  describe('System Reset', () => {
    test('should reset system correctly', () => {
      // Set up some state
      ftSystem.activeSequence = createMockFreeThrowTurnData('MAKE');
      ftSystem.sequenceQueue = [createMockFreeThrowTurnData('MISS')];
      ftSystem.currentAttempt = 2;
      ftSystem.totalAttempts = 3;
      
      ftSystem.reset();
      
      expect(ftSystem.activeSequence).toBe(null);
      expect(ftSystem.sequenceQueue).toHaveLength(0);
      expect(ftSystem.currentAttempt).toBe(0);
      expect(ftSystem.totalAttempts).toBe(0);
      expect(mockBallController.ballSprite.setVisible).toHaveBeenCalledWith(false);
    });
  });

  describe('Integration Scenarios', () => {
    test('should handle complete free throw sequence', async () => {
      const turnData = createMockFreeThrowTurnData('MAKE');
      
      await ftSystem.processFreeThrow(turnData);
      
      // Verify complete sequence
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.SHOOTING,
        expect.objectContaining({
          reason: 'free_throw_initiated',
          shooter_id: 'player1'
        })
      );
      
      expect(mockBallController.detachFromPlayer).toHaveBeenCalledWith('free_throw_shot');
      expect(mockBallController.startFlight).toHaveBeenCalled();
      expect(mockBallController.endFlight).toHaveBeenCalled();
    });

    test('should handle multiple free throw scenarios', async () => {
      const scenarios = [
        { result: 'MAKE', context: { attempt: 1, total: 1 }, expected_state: 'IDLE' },
        { result: 'MISS', context: { attempt: 1, total: 1 }, expected_state: 'REBOUNDING' },
        { result: 'MAKE', context: { attempt: 2, total: 3 }, expected_state: 'POSSESSION' },
        { result: 'MISS', context: { attempt: 2, total: 3 }, expected_state: 'REBOUNDING' }
      ];
      
      for (const scenario of scenarios) {
        const turnData = createMockFreeThrowTurnData(scenario.result, scenario.context);
        
        await ftSystem.processFreeThrow(turnData);
        
        // Verify each scenario was processed correctly
        expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
          expect.any(String),
          expect.objectContaining({
            shooter_id: 'player1'
          })
        );
      }
    });
  });
});
