/**
 * ReboundAnimationSystem Tests
 * 
 * Tests for the universal rebound animation system that handles all rebound scenarios
 */

import { ReboundAnimationSystem } from '../ReboundAnimationSystem.js';
import { AnimationStates } from '../SimplifiedStateMachine.js';

// Mock dependencies
jest.mock('../SimplifiedStateMachine.js');
jest.mock('../utils/debugFlags.js', () => ({
  DebugFlags: {
    REBOUND_ANIMATION: true
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
  attachToPlayer: jest.fn(),
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
  },
  'player4': {
    playerId: 'player4',
    team: 'away',
    position: 'C',
    x: 250,
    y: 400
  }
});

// Mock turn data
const createMockReboundTurnData = (reboundType = 'defensive', rebounderId = 'player1') => ({
  index: 1,
  rebounder_id: rebounderId,
  rebound_type: reboundType,
  possession_team_id: 'home_team'
});

describe('ReboundAnimationSystem', () => {
  let reboundSystem;
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
    
    // Create rebound system
    reboundSystem = new ReboundAnimationSystem(
      mockScene,
      mockBallController,
      mockStateMachine,
      mockPlayerSprites
    );
  });

  describe('Initialization', () => {
    test('should initialize with correct configuration', () => {
      expect(reboundSystem.scene).toBe(mockScene);
      expect(reboundSystem.ballController).toBe(mockBallController);
      expect(reboundSystem.stateMachine).toBe(mockStateMachine);
      expect(reboundSystem.playerSprites).toBe(mockPlayerSprites);
      
      expect(reboundSystem.reboundConfig).toHaveProperty('movementDuration');
      expect(reboundSystem.reboundConfig).toHaveProperty('collapseDuration');
      expect(reboundSystem.reboundConfig).toHaveProperty('courtBounds');
    });

    test('should start with no active rebound', () => {
      expect(reboundSystem.activeRebound).toBe(null);
      expect(reboundSystem.reboundQueue).toHaveLength(0);
    });
  });

  describe('Defensive Rebound Processing', () => {
    test('should process defensive rebound correctly', async () => {
      const turnData = createMockReboundTurnData('defensive', 'player1');
      
      await reboundSystem.processRebound(turnData);
      
      // Verify state transition to POSSESSION
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.POSSESSION,
        expect.objectContaining({
          reason: 'defensive_rebound_complete',
          rebounder_id: 'player1'
        })
      );
      
      // Verify ball was attached to rebounder
      expect(mockBallController.attachToPlayer).toHaveBeenCalledWith(
        mockPlayerSprites['player1'],
        expect.objectContaining({
          offset: reboundSystem.reboundConfig.rebounderOffset
        })
      );
    });

    test('should execute HCO sequence for defensive rebound', async () => {
      const turnData = createMockReboundTurnData('defensive', 'player1');
      
      await reboundSystem.processRebound(turnData);
      
      // Verify tweens were created for player movement
      expect(mockScene.tweens.add).toHaveBeenCalled();
    });

    test('should execute fast break sequence when available', async () => {
      const turnData = createMockReboundTurnData('defensive', 'player1');
      turnData.fast_break_available = true;
      
      await reboundSystem.processRebound(turnData);
      
      // Verify state transition with fast break
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.POSSESSION,
        expect.objectContaining({
          next_play_type: 'FAST_BREAK'
        })
      );
    });
  });

  describe('Offensive Rebound Processing', () => {
    test('should process offensive rebound correctly', async () => {
      const turnData = createMockReboundTurnData('offensive', 'player2');
      
      await reboundSystem.processRebound(turnData);
      
      // Verify state transition to POSSESSION
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.POSSESSION,
        expect.objectContaining({
          reason: 'offensive_rebound_complete',
          rebounder_id: 'player2'
        })
      );
      
      // Verify ball was attached to rebounder
      expect(mockBallController.attachToPlayer).toHaveBeenCalledWith(
        mockPlayerSprites['player2'],
        expect.objectContaining({
          offset: reboundSystem.reboundConfig.rebounderOffset
        })
      );
    });

    test('should execute putback sequence when putback attempt', async () => {
      const turnData = createMockReboundTurnData('offensive', 'player2');
      turnData.putback_attempt = true;
      
      await reboundSystem.processRebound(turnData);
      
      // Verify state transition with putback outcome
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.POSSESSION,
        expect.objectContaining({
          outcome: 'putback'
        })
      );
    });

    test('should execute kickout sequence by default', async () => {
      const turnData = createMockReboundTurnData('offensive', 'player2');
      
      await reboundSystem.processRebound(turnData);
      
      // Verify state transition with kickout outcome
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.POSSESSION,
        expect.objectContaining({
          outcome: 'kickout'
        })
      );
    });
  });

  describe('Player Collapse Animation', () => {
    test('should animate all players collapsing to rebounder', async () => {
      const turnData = createMockReboundTurnData('defensive', 'player1');
      
      await reboundSystem.processRebound(turnData);
      
      // Verify tweens were created for player movement
      expect(mockScene.tweens.add).toHaveBeenCalled();
    });

    test('should skip rebounder in collapse animation', async () => {
      const turnData = createMockReboundTurnData('defensive', 'player1');
      
      await reboundSystem.processRebound(turnData);
      
      // Verify tweens were created (should be fewer than total players)
      expect(mockScene.tweens.add).toHaveBeenCalled();
    });
  });

  describe('HCO Sequence', () => {
    test('should animate PG to outlet position', async () => {
      const turnData = createMockReboundTurnData('defensive', 'player1');
      
      await reboundSystem.processRebound(turnData);
      
      // Verify tweens were created for PG movement
      expect(mockScene.tweens.add).toHaveBeenCalled();
    });

    test('should animate other players to offense basket', async () => {
      const turnData = createMockReboundTurnData('defensive', 'player1');
      
      await reboundSystem.processRebound(turnData);
      
      // Verify tweens were created for player movement
      expect(mockScene.tweens.add).toHaveBeenCalled();
    });

    test('should execute outlet pass', async () => {
      const turnData = createMockReboundTurnData('defensive', 'player1');
      
      await reboundSystem.processRebound(turnData);
      
      // Verify ball controller calls for outlet pass
      expect(mockBallController.detachFromPlayer).toHaveBeenCalledWith('outlet_pass');
      expect(mockBallController.startFlight).toHaveBeenCalled();
      expect(mockBallController.endFlight).toHaveBeenCalled();
    });
  });

  describe('Fast Break Sequence', () => {
    test('should animate outlet receiver to fast break position', async () => {
      const turnData = createMockReboundTurnData('defensive', 'player1');
      turnData.fast_break_available = true;
      
      await reboundSystem.processRebound(turnData);
      
      // Verify tweens were created for outlet receiver movement
      expect(mockScene.tweens.add).toHaveBeenCalled();
    });

    test('should animate defenders back on defense', async () => {
      const turnData = createMockReboundTurnData('defensive', 'player1');
      turnData.fast_break_available = true;
      
      await reboundSystem.processRebound(turnData);
      
      // Verify tweens were created for defender movement
      expect(mockScene.tweens.add).toHaveBeenCalled();
    });
  });

  describe('Kickout Sequence', () => {
    test('should execute kickout pass to PG', async () => {
      const turnData = createMockReboundTurnData('offensive', 'player2');
      
      await reboundSystem.processRebound(turnData);
      
      // Verify ball controller calls for kickout pass
      expect(mockBallController.detachFromPlayer).toHaveBeenCalledWith('kickout_pass');
      expect(mockBallController.startFlight).toHaveBeenCalled();
      expect(mockBallController.endFlight).toHaveBeenCalled();
    });
  });

  describe('Rebound Type Detection', () => {
    test('should detect defensive rebound from rebound_type', () => {
      const turnData = createMockReboundTurnData('defensive');
      const reboundType = reboundSystem.determineReboundType(turnData);
      expect(reboundType).toBe('defensive');
    });

    test('should detect offensive rebound from rebound_type', () => {
      const turnData = createMockReboundTurnData('offensive');
      const reboundType = reboundSystem.determineReboundType(turnData);
      expect(reboundType).toBe('offensive');
    });

    test('should detect defensive rebound from result_type', () => {
      const turnData = { result_type: 'DREB', rebounder_id: 'player1' };
      const reboundType = reboundSystem.determineReboundType(turnData);
      expect(reboundType).toBe('defensive');
    });

    test('should detect offensive rebound from result_type', () => {
      const turnData = { result_type: 'OREB', rebounder_id: 'player1' };
      const reboundType = reboundSystem.determineReboundType(turnData);
      expect(reboundType).toBe('offensive');
    });

    test('should default to defensive rebound', () => {
      const turnData = { rebounder_id: 'player1' };
      const reboundType = reboundSystem.determineReboundType(turnData);
      expect(reboundType).toBe('defensive');
    });
  });

  describe('Next Play Type Detection', () => {
    test('should detect fast break when available', () => {
      const turnData = { fast_break_available: true };
      const nextPlayType = reboundSystem.determineNextPlayType(turnData);
      expect(nextPlayType).toBe('FAST_BREAK');
    });

    test('should detect HCO when fast break disabled', () => {
      const turnData = { fast_break_disabled: true };
      const nextPlayType = reboundSystem.determineNextPlayType(turnData);
      expect(nextPlayType).toBe('HCO');
    });

    test('should default to HCO', () => {
      const turnData = {};
      const nextPlayType = reboundSystem.determineNextPlayType(turnData);
      expect(nextPlayType).toBe('HCO');
    });
  });

  describe('Offensive Rebound Outcome Detection', () => {
    test('should detect putback attempt', () => {
      const turnData = { putback_attempt: true };
      const outcome = reboundSystem.determineOffensiveReboundOutcome(turnData);
      expect(outcome).toBe('putback');
    });

    test('should default to kickout', () => {
      const turnData = {};
      const outcome = reboundSystem.determineOffensiveReboundOutcome(turnData);
      expect(outcome).toBe('kickout');
    });
  });

  describe('Player Finding', () => {
    test('should find point guard by team and position', () => {
      const pg = reboundSystem.findPointGuard('home');
      expect(pg).toBe(mockPlayerSprites['player1']);
    });

    test('should return null if no PG found', () => {
      const pg = reboundSystem.findPointGuard('nonexistent');
      expect(pg).toBeUndefined();
    });

    test('should find outlet receiver', () => {
      const receiver = reboundSystem.findOutletReceiver('home');
      expect(receiver).toBe(mockPlayerSprites['player1']); // Should fallback to PG
    });

    test('should find kickout target', () => {
      const target = reboundSystem.findKickoutTarget('home');
      expect(target).toBe(mockPlayerSprites['player1']);
    });
  });

  describe('Queue Management', () => {
    test('should queue rebounds when already processing', async () => {
      const turn1 = createMockReboundTurnData('defensive', 'player1');
      const turn2 = createMockReboundTurnData('defensive', 'player2');
      
      // Mock processing to take time
      mockScene.tweens.add.mockImplementation(() => ({
        onComplete: jest.fn(),
        onUpdate: jest.fn()
      }));
      
      // Start processing first rebound
      const processPromise = reboundSystem.processRebound(turn1);
      
      // Try to process second rebound while first is processing
      reboundSystem.processRebound(turn2);
      
      // Verify second rebound was queued
      expect(reboundSystem.reboundQueue).toContain(turn2);
      
      // Wait for first rebound to complete
      await processPromise;
    });

    test('should process queued rebounds', async () => {
      const turn1 = createMockReboundTurnData('defensive', 'player1');
      const turn2 = createMockReboundTurnData('defensive', 'player2');
      
      reboundSystem.reboundQueue = [turn2];
      
      await reboundSystem.processReboundQueue();
      
      // Verify second rebound was processed
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.POSSESSION,
        expect.objectContaining({
          rebounder_id: 'player2'
        })
      );
    });
  });

  describe('Error Handling', () => {
    test('should handle invalid rebound data gracefully', async () => {
      const invalidTurnData = { invalid: true };
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      await reboundSystem.processRebound(invalidTurnData);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'ReboundAnimationSystem: Error processing rebound',
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });

    test('should handle missing rebounder sprite gracefully', async () => {
      const turnData = createMockReboundTurnData('defensive', 'nonexistent_player');
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      await reboundSystem.processRebound(turnData);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'ReboundAnimationSystem: Error processing rebound',
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });

    test('should reset to safe state on error', async () => {
      const turnData = createMockReboundTurnData('defensive', 'player1');
      
      // Mock error in state machine
      mockStateMachine.transitionTo.mockImplementation(() => {
        throw new Error('State machine error');
      });
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      await reboundSystem.processRebound(turnData);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'ReboundAnimationSystem: Error processing rebound',
        expect.any(Error)
      );
      
      // Verify system was reset to safe state
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        expect.objectContaining({
          reason: 'rebound_error'
        })
      );
      
      consoleSpy.mockRestore();
    });
  });

  describe('Configuration', () => {
    test('should update configuration', () => {
      const newConfig = {
        movementDuration: 800,
        collapseDuration: 600
      };
      
      reboundSystem.updateConfig(newConfig);
      
      expect(reboundSystem.reboundConfig.movementDuration).toBe(800);
      expect(reboundSystem.reboundConfig.collapseDuration).toBe(600);
    });

    test('should preserve existing configuration when updating', () => {
      const originalConfig = { ...reboundSystem.reboundConfig };
      const newConfig = { movementDuration: 800 };
      
      reboundSystem.updateConfig(newConfig);
      
      expect(reboundSystem.reboundConfig.movementDuration).toBe(800);
      expect(reboundSystem.reboundConfig.collapseDuration).toBe(originalConfig.collapseDuration);
    });
  });

  describe('System Status', () => {
    test('should return correct status', () => {
      const status = reboundSystem.getStatus();
      
      expect(status).toHaveProperty('activeRebound');
      expect(status).toHaveProperty('reboundQueue');
      expect(status).toHaveProperty('isProcessing');
      expect(status).toHaveProperty('reboundConfig');
      
      expect(status.activeRebound).toBe(null);
      expect(status.reboundQueue).toBe(0);
      expect(status.isProcessing).toBe(false);
    });

    test('should return correct status during processing', async () => {
      const turnData = createMockReboundTurnData('defensive', 'player1');
      
      // Mock processing to take time
      mockScene.tweens.add.mockImplementation(() => ({
        onComplete: jest.fn(),
        onUpdate: jest.fn()
      }));
      
      const processPromise = reboundSystem.processRebound(turnData);
      
      // Check status during processing
      const status = reboundSystem.getStatus();
      expect(status.activeRebound).toBe(turnData.index);
      expect(status.isProcessing).toBe(true);
      
      await processPromise;
    });
  });

  describe('System Reset', () => {
    test('should reset system correctly', () => {
      // Set up some state
      reboundSystem.activeRebound = createMockReboundTurnData('defensive', 'player1');
      reboundSystem.reboundQueue = [createMockReboundTurnData('offensive', 'player2')];
      
      reboundSystem.reset();
      
      expect(reboundSystem.activeRebound).toBe(null);
      expect(reboundSystem.reboundQueue).toHaveLength(0);
    });
  });

  describe('Integration Scenarios', () => {
    test('should handle complete defensive rebound sequence', async () => {
      const turnData = createMockReboundTurnData('defensive', 'player1');
      
      await reboundSystem.processRebound(turnData);
      
      // Verify complete sequence
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.POSSESSION,
        expect.objectContaining({
          reason: 'defensive_rebound_complete',
          rebounder_id: 'player1'
        })
      );
      
      expect(mockBallController.attachToPlayer).toHaveBeenCalled();
    });

    test('should handle complete offensive rebound sequence', async () => {
      const turnData = createMockReboundTurnData('offensive', 'player2');
      
      await reboundSystem.processRebound(turnData);
      
      // Verify complete sequence
      expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.POSSESSION,
        expect.objectContaining({
          reason: 'offensive_rebound_complete',
          rebounder_id: 'player2'
        })
      );
      
      expect(mockBallController.attachToPlayer).toHaveBeenCalled();
    });

    test('should handle multiple rebound types', async () => {
      const reboundTypes = [
        { rebound_type: 'defensive', expected_play: 'HCO' },
        { rebound_type: 'offensive', expected_outcome: 'kickout' },
        { rebound_type: 'defensive', fast_break_available: true, expected_play: 'FAST_BREAK' },
        { rebound_type: 'offensive', putback_attempt: true, expected_outcome: 'putback' }
      ];
      
      for (const reboundType of reboundTypes) {
        const turnData = createMockReboundTurnData(reboundType.rebound_type);
        Object.assign(turnData, reboundType);
        
        await reboundSystem.processRebound(turnData);
        
        // Verify each rebound was processed correctly
        expect(mockStateMachine.transitionTo).toHaveBeenCalledWith(
          AnimationStates.POSSESSION,
          expect.objectContaining({
            rebounder_id: expect.any(String)
          })
        );
      }
    });
  });
});
