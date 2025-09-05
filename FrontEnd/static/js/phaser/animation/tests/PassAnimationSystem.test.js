/**
 * PassAnimationSystem Tests
 * 
 * Tests for the universal pass animation system that handles all pass scenarios
 */

import { PassAnimationSystem } from '../PassAnimationSystem.js';
import { AnimationStates } from '../SimplifiedStateMachine.js';

// Mock dependencies
jest.mock('../SimplifiedStateMachine.js');
jest.mock('../utils/debugFlags.js', () => ({
  DebugFlags: {
    PASS_ANIMATION: true
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
  is: jest.fn().mockReturnValue(true),
  transitionTo: jest.fn()
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
    team: 'home',
    position: 'SG',
    x: 200,
    y: 300
  },
  'player3': {
    playerId: 'player3',
    team: 'away',
    position: 'PG',
    x: 300,
    y: 350
  }
});

// Mock turn data
const createMockPassTurnData = (resultType = 'MAKE', passType = 'assist') => ({
  index: 1,
  passer_id: 'player1',
  receiver_id: 'player2',
  pass_type: passType,
  result_type: resultType,
  team_id: 'home_team'
});

describe('PassAnimationSystem', () => {
  let passSystem;
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
    
    // Create pass system
    passSystem = new PassAnimationSystem(
      mockScene,
      mockBallController,
      mockStateMachine,
      mockPlayerSprites
    );
  });

  describe('Initialization', () => {
    test('should initialize with correct configuration', () => {
      expect(passSystem.scene).toBe(mockScene);
      expect(passSystem.ballController).toBe(mockBallController);
      expect(passSystem.stateMachine).toBe(mockStateMachine);
      expect(passSystem.playerSprites).toBe(mockPlayerSprites);
      
      expect(passSystem.passConfig).toHaveProperty('flightDuration');
      expect(passSystem.passConfig).toHaveProperty('passTypes');
      expect(passSystem.passConfig).toHaveProperty('receiverOffset');
      expect(passSystem.passConfig).toHaveProperty('useArc');
    });

    test('should start with no active pass', () => {
      expect(passSystem.activePass).toBe(null);
      expect(passSystem.passQueue).toHaveLength(0);
    });
  });

  describe('Pass Processing', () => {
    test('should process a successful pass correctly', async () => {
      const turnData = createMockPassTurnData('MAKE', 'assist');
      
      await passSystem.processPass(turnData);
      
      // Verify state transition to POSSESSION
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.POSSESSION,
        expect.objectContaining({
          reason: 'pass_successful',
          receiver_id: 'player2'
        })
      );
      
      // Verify ball controller calls
      expect(mockBallController.detachFromPlayer).toHaveBeenCalledWith('pass');
      expect(mockBallController.startFlight).toHaveBeenCalled();
      expect(mockBallController.endFlight).toHaveBeenCalled();
    });

    test('should process a failed pass correctly', async () => {
      const turnData = createMockPassTurnData('MISS', 'assist');
      
      await passSystem.processPass(turnData);
      
      // Verify state transition to IDLE
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        expect.objectContaining({
          reason: 'pass_failed',
          passer_id: 'player1'
        })
      );
      
      // Verify ball controller calls
      expect(mockBallController.detachFromPlayer).toHaveBeenCalledWith('pass');
      expect(mockBallController.startFlight).toHaveBeenCalled();
      expect(mockBallController.endFlight).toHaveBeenCalled();
    });

    test('should queue passes when already processing', async () => {
      const pass1 = createMockPassTurnData('MAKE', 'assist');
      const pass2 = createMockPassTurnData('MAKE', 'outlet');
      
      // Mock processing to take time
      mockScene.tweens.add.mockImplementation(() => ({
        onComplete: jest.fn(),
        onUpdate: jest.fn()
      }));
      
      // Start processing first pass
      const processPromise = passSystem.processPass(pass1);
      
      // Try to process second pass while first is processing
      passSystem.processPass(pass2);
      
      // Verify second pass was queued
      expect(passSystem.passQueue).toContain(pass2);
      
      // Wait for first pass to complete
      await processPromise;
    });

    test('should handle invalid pass data gracefully', async () => {
      const invalidTurnData = { invalid: true };
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      await passSystem.processPass(invalidTurnData);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'PassAnimationSystem: Error processing pass',
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });

    test('should handle missing passer sprite gracefully', async () => {
      const turnData = createMockPassTurnData('MAKE', 'assist');
      turnData.passer_id = 'nonexistent_player';
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      await passSystem.processPass(turnData);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'PassAnimationSystem: Error processing pass',
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });

    test('should handle missing receiver sprite gracefully', async () => {
      const turnData = createMockPassTurnData('MAKE', 'assist');
      turnData.receiver_id = 'nonexistent_player';
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      await passSystem.processPass(turnData);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'PassAnimationSystem: Error processing pass',
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });
  });

  describe('Pass Types', () => {
    test('should handle assist pass', async () => {
      const turnData = createMockPassTurnData('MAKE', 'assist');
      
      await passSystem.processPass(turnData);
      
      // Verify assist-specific configuration was used
      expect(mockBallController.startFlight).toHaveBeenCalledWith(
        expect.any(Object),
        expect.objectContaining({
          duration: passSystem.passConfig.passTypes.assist.duration,
          ease: passSystem.passConfig.passTypes.assist.ease
        })
      );
    });

    test('should handle outlet pass', async () => {
      const turnData = createMockPassTurnData('MAKE', 'outlet');
      
      await passSystem.processPass(turnData);
      
      // Verify outlet-specific configuration was used
      expect(mockBallController.startFlight).toHaveBeenCalledWith(
        expect.any(Object),
        expect.objectContaining({
          duration: passSystem.passConfig.passTypes.outlet.duration,
          ease: passSystem.passConfig.passTypes.outlet.ease
        })
      );
    });

    test('should handle kickout pass', async () => {
      const turnData = createMockPassTurnData('MAKE', 'kickout');
      
      await passSystem.processPass(turnData);
      
      // Verify kickout-specific configuration was used
      expect(mockBallController.startFlight).toHaveBeenCalledWith(
        expect.any(Object),
        expect.objectContaining({
          duration: passSystem.passConfig.passTypes.kickout.duration,
          ease: passSystem.passConfig.passTypes.kickout.ease
        })
      );
    });

    test('should handle inbound pass', async () => {
      const turnData = createMockPassTurnData('MAKE', 'inbound');
      
      await passSystem.processPass(turnData);
      
      // Verify inbound-specific configuration was used
      expect(mockBallController.startFlight).toHaveBeenCalledWith(
        expect.any(Object),
        expect.objectContaining({
          duration: passSystem.passConfig.passTypes.inbound.duration,
          ease: passSystem.passConfig.passTypes.inbound.ease
        })
      );
    });

    test('should handle fast break pass', async () => {
      const turnData = createMockPassTurnData('MAKE', 'fast_break');
      
      await passSystem.processPass(turnData);
      
      // Verify fast break-specific configuration was used
      expect(mockBallController.startFlight).toHaveBeenCalledWith(
        expect.any(Object),
        expect.objectContaining({
          duration: passSystem.passConfig.passTypes.fast_break.duration,
          ease: passSystem.passConfig.passTypes.fast_break.ease
        })
      );
    });

    test('should use default configuration for unknown pass types', async () => {
      const turnData = createMockPassTurnData('MAKE', 'unknown_type');
      
      await passSystem.processPass(turnData);
      
      // Verify default configuration was used
      expect(mockBallController.startFlight).toHaveBeenCalledWith(
        expect.any(Object),
        expect.objectContaining({
          duration: passSystem.passConfig.passTypes.default.duration,
          ease: passSystem.passConfig.passTypes.default.ease
        })
      );
    });
  });

  describe('Receiver Positioning', () => {
    test('should position receiver for inbound pass', async () => {
      const turnData = createMockPassTurnData('MAKE', 'inbound');
      
      await passSystem.processPass(turnData);
      
      // Verify tween was created for receiver positioning
      expect(mockScene.tweens.add).toHaveBeenCalledWith(
        expect.objectContaining({
          targets: mockPlayerSprites['player2'],
          duration: 400,
          ease: 'Power2'
        })
      );
    });

    test('should position receiver for fast break pass', async () => {
      const turnData = createMockPassTurnData('MAKE', 'fast_break');
      
      await passSystem.processPass(turnData);
      
      // Verify tween was created for receiver positioning
      expect(mockScene.tweens.add).toHaveBeenCalledWith(
        expect.objectContaining({
          targets: mockPlayerSprites['player2'],
          duration: 200,
          ease: 'Power2'
        })
      );
    });

    test('should position receiver at target position when specified', async () => {
      const turnData = createMockPassTurnData('MAKE', 'assist');
      turnData.receiver_target_position = { x: 300, y: 400 };
      
      await passSystem.processPass(turnData);
      
      // Verify tween was created for receiver positioning
      expect(mockScene.tweens.add).toHaveBeenCalledWith(
        expect.objectContaining({
          targets: mockPlayerSprites['player2'],
          x: 300,
          y: 400,
          duration: 300,
          ease: 'Power2'
        })
      );
    });
  });

  describe('Pass Animation', () => {
    test('should animate ball from passer to receiver', async () => {
      const turnData = createMockPassTurnData('MAKE', 'assist');
      
      await passSystem.processPass(turnData);
      
      // Verify ball was positioned and made visible
      expect(mockBallController.ballSprite.setPosition).toHaveBeenCalled();
      expect(mockBallController.ballSprite.setVisible).toHaveBeenCalledWith(true);
      
      // Verify tween was created for ball animation
      expect(mockScene.tweens.add).toHaveBeenCalledWith(
        expect.objectContaining({
          targets: mockBallController.ballSprite,
          duration: passSystem.passConfig.passTypes.assist.duration,
          ease: passSystem.passConfig.passTypes.assist.ease
        })
      );
    });

    test('should handle missing ball sprite gracefully', async () => {
      mockBallController.ballSprite = null;
      
      const turnData = createMockPassTurnData('MAKE', 'assist');
      
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
      
      await passSystem.processPass(turnData);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'PassAnimationSystem: No ball sprite available'
      );
      
      consoleSpy.mockRestore();
    });
  });

  describe('Arc Effect', () => {
    test('should add arc effect when enabled', async () => {
      const turnData = createMockPassTurnData('MAKE', 'assist');
      
      await passSystem.processPass(turnData);
      
      // Verify tween was created with arc effect
      expect(mockScene.tweens.add).toHaveBeenCalledWith(
        expect.objectContaining({
          targets: mockBallController.ballSprite,
          onUpdate: expect.any(Function)
        })
      );
    });

    test('should calculate arc height based on pass distance', () => {
      const passerSprite = mockPlayerSprites['player1'];
      const receiverSprite = mockPlayerSprites['player2'];
      
      // Mock ball sprite for arc calculation
      const mockBallSprite = {
        x: 175, // Midpoint between passer and receiver
        y: 275,
        setPosition: jest.fn()
      };
      
      const arcHeight = passSystem.calculateTweenProgress(
        mockBallSprite, 
        passerSprite, 
        receiverSprite
      );
      
      expect(arcHeight).toBeGreaterThan(0);
      expect(arcHeight).toBeLessThanOrEqual(1);
    });
  });

  describe('Position Calculations', () => {
    test('should calculate inbound position correctly', () => {
      const turnData = createMockPassTurnData('MAKE', 'inbound');
      turnData.team_id = 'home_team';
      
      const position = passSystem.calculateInboundPosition(turnData);
      
      expect(position.x).toBe(50); // Near baseline for home team
      expect(position.y).toBe(300); // Middle of court (600/2)
    });

    test('should calculate fast break position correctly', () => {
      const turnData = createMockPassTurnData('MAKE', 'fast_break');
      turnData.team_id = 'home_team';
      
      const receiverSprite = mockPlayerSprites['player2'];
      const position = passSystem.calculateFastBreakPosition(receiverSprite, turnData);
      
      // Should move further down court for home team
      expect(position.x).toBeGreaterThan(receiverSprite.x);
      expect(position.x).toBeLessThanOrEqual(passSystem.passConfig.courtBounds.maxX);
    });
  });

  describe('Queue Management', () => {
    test('should process queued passes', async () => {
      const pass1 = createMockPassTurnData('MAKE', 'assist');
      const pass2 = createMockPassTurnData('MAKE', 'outlet');
      
      passSystem.passQueue = [pass2];
      
      await passSystem.processPassQueue();
      
      // Verify second pass was processed
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.POSSESSION,
        expect.objectContaining({
          receiver_id: 'player2'
        })
      );
    });

    test('should handle empty queue', async () => {
      passSystem.passQueue = [];
      
      await passSystem.processPassQueue();
      
      // Should not throw error
      expect(mockStateMachine.transitionTo).not.toHaveBeenCalled();
    });
  });

  describe('Error Handling', () => {
    test('should handle pass processing errors gracefully', async () => {
      const turnData = createMockPassTurnData('MAKE', 'assist');
      
      // Mock error in state machine
      mockStateMachine.transitionTo.mockImplementation(() => {
        throw new Error('State machine error');
      });
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      await passSystem.processPass(turnData);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'PassAnimationSystem: Error processing pass',
        expect.any(Error)
      );
      
      // Verify system was reset to safe state
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        expect.objectContaining({
          reason: 'pass_error'
        })
      );
      
      consoleSpy.mockRestore();
    });

    test('should hide ball on error', async () => {
      const turnData = createMockPassTurnData('MAKE', 'assist');
      
      // Mock error
      mockStateMachine.transitionTo.mockImplementation(() => {
        throw new Error('Test error');
      });
      
      await passSystem.processPass(turnData);
      
      // Verify ball was hidden
      expect(mockBallController.ballSprite.setVisible).toHaveBeenCalledWith(false);
    });
  });

  describe('Configuration', () => {
    test('should update configuration', () => {
      const newConfig = {
        flightDuration: 600,
        useArc: false
      };
      
      passSystem.updateConfig(newConfig);
      
      expect(passSystem.passConfig.flightDuration).toBe(600);
      expect(passSystem.passConfig.useArc).toBe(false);
    });

    test('should preserve existing configuration when updating', () => {
      const originalConfig = { ...passSystem.passConfig };
      const newConfig = { flightDuration: 600 };
      
      passSystem.updateConfig(newConfig);
      
      expect(passSystem.passConfig.flightDuration).toBe(600);
      expect(passSystem.passConfig.useArc).toBe(originalConfig.useArc);
      expect(passSystem.passConfig.passTypes).toEqual(originalConfig.passTypes);
    });
  });

  describe('System Status', () => {
    test('should return correct status', () => {
      const status = passSystem.getStatus();
      
      expect(status).toHaveProperty('activePass');
      expect(status).toHaveProperty('passQueue');
      expect(status).toHaveProperty('isProcessing');
      expect(status).toHaveProperty('passConfig');
      
      expect(status.activePass).toBe(null);
      expect(status.passQueue).toBe(0);
      expect(status.isProcessing).toBe(false);
    });

    test('should return correct status during processing', async () => {
      const turnData = createMockPassTurnData('MAKE', 'assist');
      
      // Mock processing to take time
      mockScene.tweens.add.mockImplementation(() => ({
        onComplete: jest.fn(),
        onUpdate: jest.fn()
      }));
      
      const processPromise = passSystem.processPass(turnData);
      
      // Check status during processing
      const status = passSystem.getStatus();
      expect(status.activePass).toBe(turnData.index);
      expect(status.isProcessing).toBe(true);
      
      await processPromise;
    });
  });

  describe('System Reset', () => {
    test('should reset system correctly', () => {
      // Set up some state
      passSystem.activePass = createMockPassTurnData('MAKE', 'assist');
      passSystem.passQueue = [createMockPassTurnData('MAKE', 'outlet')];
      
      passSystem.reset();
      
      expect(passSystem.activePass).toBe(null);
      expect(passSystem.passQueue).toHaveLength(0);
      expect(mockBallController.ballSprite.setVisible).toHaveBeenCalledWith(false);
    });
  });

  describe('Integration Scenarios', () => {
    test('should handle complete pass sequence', async () => {
      const turnData = createMockPassTurnData('MAKE', 'assist');
      
      await passSystem.processPass(turnData);
      
      // Verify complete sequence
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.POSSESSION,
        expect.objectContaining({
          reason: 'pass_successful',
          receiver_id: 'player2'
        })
      );
      
      expect(mockBallController.detachFromPlayer).toHaveBeenCalledWith('pass');
      expect(mockBallController.startFlight).toHaveBeenCalled();
      expect(mockBallController.endFlight).toHaveBeenCalled();
    });

    test('should handle multiple pass types', async () => {
      const passTypes = [
        { pass_type: 'assist', expected_duration: 400 },
        { pass_type: 'outlet', expected_duration: 300 },
        { pass_type: 'kickout', expected_duration: 350 },
        { pass_type: 'inbound', expected_duration: 600 },
        { pass_type: 'fast_break', expected_duration: 250 }
      ];
      
      for (const passType of passTypes) {
        const turnData = createMockPassTurnData('MAKE', passType.pass_type);
        
        await passSystem.processPass(turnData);
        
        // Verify each pass type was processed with correct configuration
        expect(mockBallController.startFlight).toHaveBeenCalledWith(
          expect.any(Object),
          expect.objectContaining({
            duration: passType.expected_duration
          })
        );
      }
    });
  });
});
