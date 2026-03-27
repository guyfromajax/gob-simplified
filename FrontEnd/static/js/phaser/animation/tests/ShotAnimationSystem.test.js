/**
 * ShotAnimationSystem Tests
 * 
 * Tests for the universal shot animation system that handles all shot types
 */

import { ShotAnimationSystem } from '../ShotAnimationSystem.js';
import { AnimationStates } from '../SimplifiedStateMachine.js';
import { CLAMP_BOUNDS } from '../courtClamp.js';

// Mock dependencies
jest.mock('../SimplifiedStateMachine.js');
jest.mock('../utils/debugFlags.js', () => ({
  DebugFlags: {
    SHOT_ANIMATION: true
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
  transitionTo: jest.fn()
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
const createMockShotTurnData = (resultType = 'MAKE', shooterId = 'player1') => ({
  index: 1,
  result_type: resultType,
  shooter_id: shooterId,
  possession_team_id: 'home_team',
  shot_type: 'jump_shot'
});

describe('ShotAnimationSystem', () => {
  let shotSystem;
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
    
    // Create shot system
    shotSystem = new ShotAnimationSystem(
      mockScene,
      mockBallController,
      mockStateMachine,
      mockPlayerSprites
    );
  });

  describe('Initialization', () => {
    test('should initialize with correct configuration', () => {
      expect(shotSystem.scene).toBe(mockScene);
      expect(shotSystem.ballController).toBe(mockBallController);
      expect(shotSystem.stateMachine).toBe(mockStateMachine);
      expect(shotSystem.playerSprites).toBe(mockPlayerSprites);
      
      expect(shotSystem.shotConfig).toHaveProperty('flightDuration');
      expect(shotSystem.shotConfig).toHaveProperty('bounceDuration');
      expect(shotSystem.shotConfig).toHaveProperty('homeRim');
      expect(shotSystem.shotConfig).toHaveProperty('awayRim');
    });

    test('should start with no active shot', () => {
      expect(shotSystem.activeShot).toBe(null);
      expect(shotSystem.shotQueue).toHaveLength(0);
    });
  });

  describe('Shot Processing', () => {
    test('should process a made shot correctly', async () => {
      const turnData = createMockShotTurnData('MAKE');
      
      await shotSystem.processShot(turnData);
      
      // Verify state transitions
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.SHOOTING,
        expect.objectContaining({
          reason: 'shot_initiated',
          shooter_id: 'player1'
        })
      );
      
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        expect.objectContaining({
          reason: 'shot_made',
          shooter_id: 'player1'
        })
      );
      
      // Verify ball controller calls
      expect(mockBallController.detachFromPlayer).toHaveBeenCalledWith('shot');
      expect(mockBallController.startFlight).toHaveBeenCalled();
      expect(mockBallController.endFlight).toHaveBeenCalled();
    });

    test('should process a missed shot correctly', async () => {
      const turnData = createMockShotTurnData('MISS');
      
      await shotSystem.processShot(turnData);
      
      // Verify state transitions
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.SHOOTING,
        expect.objectContaining({
          reason: 'shot_initiated'
        })
      );
      
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.REBOUNDING,
        expect.objectContaining({
          reason: 'shot_missed',
          shooter_id: 'player1'
        })
      );
      
      // Verify ball controller calls
      expect(mockBallController.detachFromPlayer).toHaveBeenCalledWith('shot');
      expect(mockBallController.startFlight).toHaveBeenCalled();
      expect(mockBallController.endFlight).toHaveBeenCalled();
    });

    test('should queue shots when already processing', async () => {
      const turn1 = createMockShotTurnData('MAKE', 'player1');
      const turn2 = createMockShotTurnData('MISS', 'player2');
      
      // Mock processing to take time
      mockScene.tweens.add.mockImplementation(() => ({
        onComplete: jest.fn(),
        onUpdate: jest.fn()
      }));
      
      // Start processing first shot
      const processPromise = shotSystem.processShot(turn1);
      
      // Try to process second shot while first is processing
      shotSystem.processShot(turn2);
      
      // Verify second shot was queued
      expect(shotSystem.shotQueue).toContain(turn2);
      
      // Wait for first shot to complete
      await processPromise;
    });

    test('should handle invalid shot data gracefully', async () => {
      const invalidTurnData = { result_type: 'INVALID' };
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      await shotSystem.processShot(invalidTurnData);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'ShotAnimationSystem: Error processing shot',
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });

    test('should handle missing shooter sprite gracefully', async () => {
      const turnData = createMockShotTurnData('MAKE', 'nonexistent_player');
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      await shotSystem.processShot(turnData);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'ShotAnimationSystem: Error processing shot',
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });
  });

  describe('Ball Flight Animation', () => {
    test('should animate ball flight from shooter to rim', async () => {
      const turnData = createMockShotTurnData('MAKE');
      
      await shotSystem.processShot(turnData);
      
      // Verify tween was created
      expect(mockScene.tweens.add).toHaveBeenCalledWith(
        expect.objectContaining({
          targets: mockBallController.ballSprite,
          x: expect.any(Number),
          y: expect.any(Number),
          duration: shotSystem.shotConfig.flightDuration,
          ease: shotSystem.shotConfig.flightEase
        })
      );
      
      // Verify ball was positioned and made visible
      expect(mockBallController.ballSprite.setPosition).toHaveBeenCalled();
      expect(mockBallController.ballSprite.setVisible).toHaveBeenCalledWith(true);
    });

    test('should handle missing ball sprite gracefully', async () => {
      mockBallController.ballSprite = null;
      
      const turnData = createMockShotTurnData('MAKE');
      
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
      
      await shotSystem.processShot(turnData);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'ShotAnimationSystem: No ball sprite available'
      );
      
      consoleSpy.mockRestore();
    });
  });

  describe('Shot Outcomes', () => {
    test('should handle made shot correctly', async () => {
      const turnData = createMockShotTurnData('MAKE');
      
      await shotSystem.processShot(turnData);
      
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

    test('should handle missed shot with bounce', async () => {
      const turnData = createMockShotTurnData('MISS');
      
      await shotSystem.processShot(turnData);
      
      // Verify bounce animation was created
      expect(mockScene.tweens.add).toHaveBeenCalledWith(
        expect.objectContaining({
          targets: mockBallController.ballSprite,
          x: expect.any(Number),
          y: expect.any(Number),
          duration: shotSystem.shotConfig.bounceDuration,
          ease: shotSystem.shotConfig.bounceEase
        })
      );
    });
  });

  describe('Rim Coordinate Calculation', () => {
    test('should use home rim for home team shots', async () => {
      const turnData = createMockShotTurnData('MAKE');
      turnData.team_id = 'home_team';
      
      await shotSystem.processShot(turnData);
      
      // Verify home rim coordinates were used
      expect(mockScene.tweens.add).toHaveBeenCalledWith(
        expect.objectContaining({
          x: shotSystem.shotConfig.homeRim.x,
          y: shotSystem.shotConfig.homeRim.y
        })
      );
    });

    test('should use away rim for away team shots', async () => {
      const turnData = createMockShotTurnData('MAKE');
      turnData.team_id = 'away_team';
      
      await shotSystem.processShot(turnData);
      
      // Verify away rim coordinates were used
      expect(mockScene.tweens.add).toHaveBeenCalledWith(
        expect.objectContaining({
          x: shotSystem.shotConfig.awayRim.x,
          y: shotSystem.shotConfig.awayRim.y
        })
      );
    });
  });

  describe('Bounce Calculation', () => {
    test('should calculate bounce coordinates within court bounds', () => {
      const rimCoords = { x: 100, y: 200 };
      const turnData = createMockShotTurnData('MISS');
      
      const bounceCoords = shotSystem.calculateBounceCoords(rimCoords, turnData);
      
      // Verify bounce coordinates are within bounds
      expect(bounceCoords.x).toBeGreaterThanOrEqual(20);
      expect(bounceCoords.x).toBeLessThanOrEqual(780); // 800 - 20
      expect(bounceCoords.y).toBeGreaterThanOrEqual(20);
      expect(bounceCoords.y).toBeLessThanOrEqual(580); // 600 - 20
    });

    test('should generate random bounce coordinates', () => {
      const rimCoords = { x: 100, y: 200 };
      const turnData = createMockShotTurnData('MISS');
      
      const bounce1 = shotSystem.calculateBounceCoords(rimCoords, turnData);
      const bounce2 = shotSystem.calculateBounceCoords(rimCoords, turnData);
      
      // Bounces should be different (random)
      expect(bounce1.x).not.toBe(bounce2.x);
      expect(bounce1.y).not.toBe(bounce2.y);
    });
  });

  describe('Clamp policy integration', () => {
    test('animatePlayerToReboundSpot keeps target inside canonical clamp bounds', async () => {
      const playerSprite = mockPlayerSprites.player1;
      const width = mockScene.game.config.width;
      const height = mockScene.game.config.height;
      let capturedTweenConfig = null;

      mockScene.tweens.add.mockImplementationOnce((config) => {
        capturedTweenConfig = config;
        if (typeof config.onComplete === 'function') config.onComplete();
        return { stop: jest.fn() };
      });

      await shotSystem.animatePlayerToReboundSpot(
        playerSprite,
        { x: 0, y: 0 },
        CLAMP_BOUNDS.maxX + 30,
        CLAMP_BOUNDS.maxY + 30
      );

      expect(capturedTweenConfig).toBeTruthy();
      expect(capturedTweenConfig.x).toBeGreaterThanOrEqual((CLAMP_BOUNDS.minX / 100) * width);
      expect(capturedTweenConfig.x).toBeLessThanOrEqual((CLAMP_BOUNDS.maxX / 100) * width);
      expect(capturedTweenConfig.y).toBeGreaterThanOrEqual((CLAMP_BOUNDS.minY / 100) * height);
      expect(capturedTweenConfig.y).toBeLessThanOrEqual((CLAMP_BOUNDS.maxY / 100) * height);
    });
  });

  describe('Error Handling', () => {
    test('should handle shot processing errors gracefully', async () => {
      const turnData = createMockShotTurnData('MAKE');
      
      // Mock error in state machine
      mockStateMachine.transitionTo.mockImplementation(() => {
        throw new Error('State machine error');
      });
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      await shotSystem.processShot(turnData);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'ShotAnimationSystem: Error processing shot',
        expect.any(Error)
      );
      
      // Verify system was reset to safe state
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        expect.objectContaining({
          reason: 'shot_error'
        })
      );
      
      consoleSpy.mockRestore();
    });

    test('should reset to safe state on error', async () => {
      const turnData = createMockShotTurnData('MAKE');
      
      // Mock error
      mockStateMachine.transitionTo.mockImplementation(() => {
        throw new Error('Test error');
      });
      
      await shotSystem.processShot(turnData);
      
      // Verify ball was hidden
      expect(mockBallController.ballSprite.setVisible).toHaveBeenCalledWith(false);
    });
  });

  describe('Configuration', () => {
    test('should update configuration', () => {
      const newConfig = {
        flightDuration: 1000,
        bounceDuration: 800
      };
      
      shotSystem.updateConfig(newConfig);
      
      expect(shotSystem.shotConfig.flightDuration).toBe(1000);
      expect(shotSystem.shotConfig.bounceDuration).toBe(800);
    });

    test('should preserve existing configuration when updating', () => {
      const originalConfig = { ...shotSystem.shotConfig };
      const newConfig = { flightDuration: 1000 };
      
      shotSystem.updateConfig(newConfig);
      
      expect(shotSystem.shotConfig.flightDuration).toBe(1000);
      expect(shotSystem.shotConfig.bounceDuration).toBe(originalConfig.bounceDuration);
      expect(shotSystem.shotConfig.homeRim).toEqual(originalConfig.homeRim);
    });
  });

  describe('System Status', () => {
    test('should return correct status', () => {
      const status = shotSystem.getStatus();
      
      expect(status).toHaveProperty('activeShot');
      expect(status).toHaveProperty('shotQueue');
      expect(status).toHaveProperty('isProcessing');
      expect(status).toHaveProperty('shotConfig');
      
      expect(status.activeShot).toBe(null);
      expect(status.shotQueue).toBe(0);
      expect(status.isProcessing).toBe(false);
    });

    test('should return correct status during processing', async () => {
      const turnData = createMockShotTurnData('MAKE');
      
      // Mock processing to take time
      mockScene.tweens.add.mockImplementation(() => ({
        onComplete: jest.fn(),
        onUpdate: jest.fn()
      }));
      
      const processPromise = shotSystem.processShot(turnData);
      
      // Check status during processing
      const status = shotSystem.getStatus();
      expect(status.activeShot).toBe(turnData.index);
      expect(status.isProcessing).toBe(true);
      
      await processPromise;
    });
  });

  describe('System Reset', () => {
    test('should reset system correctly', () => {
      // Set up some state
      shotSystem.activeShot = createMockShotTurnData('MAKE');
      shotSystem.shotQueue = [createMockShotTurnData('MISS')];
      
      shotSystem.reset();
      
      expect(shotSystem.activeShot).toBe(null);
      expect(shotSystem.shotQueue).toHaveLength(0);
      expect(mockBallController.ballSprite.setVisible).toHaveBeenCalledWith(false);
    });
  });

  describe('Integration Scenarios', () => {
    test('should handle complete shot sequence', async () => {
      const turnData = createMockShotTurnData('MISS');
      
      await shotSystem.processShot(turnData);
      
      // Verify complete sequence
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.SHOOTING,
        expect.objectContaining({ reason: 'shot_initiated' })
      );
      
      expect(mockBallController.detachFromPlayer).toHaveBeenCalledWith('shot');
      expect(mockBallController.startFlight).toHaveBeenCalled();
      expect(mockBallController.endFlight).toHaveBeenCalled();
      
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.REBOUNDING,
        expect.objectContaining({ reason: 'shot_missed' })
      );
    });

    test('should handle multiple shot types', async () => {
      const shotTypes = [
        { result_type: 'MAKE', shot_type: 'jump_shot' },
        { result_type: 'MISS', shot_type: 'layup' },
        { result_type: 'MAKE', shot_type: 'three_pointer' },
        { result_type: 'MISS', shot_type: 'free_throw' }
      ];
      
      for (const shotType of shotTypes) {
        const turnData = createMockShotTurnData(shotType.result_type);
        turnData.shot_type = shotType.shot_type;
        
        await shotSystem.processShot(turnData);
        
        // Verify each shot was processed
        expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
          AnimationStates.SHOOTING,
          expect.objectContaining({ shot_type: shotType.shot_type })
        );
      }
    });
  });
});
