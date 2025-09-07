/**
 * Phase 1 Integration Tests
 * 
 * Comprehensive tests for all Phase 1 components working together:
 * - AnimationEngine
 * - SimplifiedStateMachine  
 * - BallController
 * - AnimationRouter
 * 
 * These tests ensure the new animation system can handle real basketball scenarios
 */

import { AnimationRouter } from '../AnimationRouter.js';
import { AnimationStates } from '../SimplifiedStateMachine.js';
import { BallController } from '../BallController.js';
import SimplifiedStateMachine from '../SimplifiedStateMachine.js';
import AnimationEngine from '../AnimationEngine.js';

// Mock dependencies
jest.mock('../AnimationEngine.js');
jest.mock('../SimplifiedStateMachine.js');
jest.mock('../BallController.js');

// Mock debug flags
jest.mock('../../utils/debugFlags.js', () => ({
  DebugFlags: {
    ANIMATION_ROUTER: true,
    ANIMATION_ENGINE: true,
    FSM: true,
    POSSESSION: true
  }
}));

// Mock Phaser scene
const createMockScene = () => ({
  events: {
    on: jest.fn(),
    off: jest.fn(),
    emit: jest.fn()
  },
  time: {
    now: Date.now()
  }
});

// Mock ball sprite
const createMockBallSprite = () => ({
  x: 100,
  y: 200,
  visible: false,
  depth: 0,
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
    y: 250,
    depth: 10
  },
  'player2': {
    playerId: 'player2',
    team: 'away',
    x: 200,
    y: 300,
    depth: 10
  },
  'player3': {
    playerId: 'player3',
    team: 'home',
    x: 180,
    y: 280,
    depth: 10
  }
});

// Mock turn data for different scenarios
const createMockTurnData = (resultType, index = 1, additionalData = {}) => ({
  index,
  result_type: resultType,
  player_id: 'player1',
  possession_team_id: 'home',
  ...additionalData
});

describe('Phase 1 Integration Tests', () => {
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

  describe('Complete Basketball Scenarios', () => {
    test('should handle complete shot sequence: possession → shot → miss → rebound', async () => {
      // 1. Start with possession
      animationRouter.stateMachine.state = AnimationStates.POSSESSION;
      animationRouter.ballController.attachToPlayer(mockPlayerSprites['player1']);
      
      // 2. Take shot
      const shotTurn = createMockTurnData('MISS', 1, { 
        shooter_id: 'player1',
        shot_type: 'jump_shot'
      });
      
      await animationRouter.processTurn(shotTurn);
      
      // Verify state transitions
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.SHOOTING,
        { turnData: shotTurn }
      );
      
      // 3. Handle rebound
      const reboundTurn = createMockTurnData('REBOUND', 2, {
        rebounder_id: 'player2',
        rebound_type: 'defensive'
      });
      
      await animationRouter.processTurn(reboundTurn);
      
      // Verify rebound state transition
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.REBOUNDING,
        { turnData: reboundTurn }
      );
      
      // Verify ball controller was used correctly
      expect(animationRouter.ballController.attachToPlayer).toHaveBeenCalled();
      expect(animationRouter.ballController.detachFromPlayer).toHaveBeenCalled();
    });

    test('should handle complete pass sequence: possession → pass → possession', async () => {
      // 1. Start with possession
      animationRouter.stateMachine.state = AnimationStates.POSSESSION;
      animationRouter.ballController.attachToPlayer(mockPlayerSprites['player1']);
      
      // 2. Make pass
      const passTurn = createMockTurnData('MAKE', 1, {
        passer_id: 'player1',
        receiver_id: 'player3',
        pass_type: 'assist'
      });
      
      await animationRouter.processTurn(passTurn);
      
      // Verify state remains in POSSESSION
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.POSSESSION,
        { turnData: passTurn }
      );
      
      // Verify ball controller handled the pass
      expect(animationRouter.ballController.attachToPlayer).toHaveBeenCalled();
    });

    test('should handle turnover sequence: possession → turnover → idle', async () => {
      // 1. Start with possession
      animationRouter.stateMachine.state = AnimationStates.POSSESSION;
      animationRouter.ballController.attachToPlayer(mockPlayerSprites['player1']);
      
      // 2. Turnover
      const turnoverTurn = createMockTurnData('TURNOVER', 1, {
        player_id: 'player1',
        turnover_type: 'bad_pass'
      });
      
      await animationRouter.processTurn(turnoverTurn);
      
      // Verify transition to IDLE
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        { turnData: turnoverTurn }
      );
      
      // Verify ball was detached
      expect(animationRouter.ballController.detachFromPlayer).toHaveBeenCalled();
    });

    test('should handle free throw sequence: shooting → make → possession', async () => {
      // 1. Start with shooting state
      animationRouter.stateMachine.state = AnimationStates.SHOOTING;
      
      // 2. Make free throw
      const freeThrowTurn = createMockTurnData('FREE_THROW', 1, {
        shooter_id: 'player1',
        ft_context: { attempt: 1, total: 2 }
      });
      
      await animationRouter.processTurn(freeThrowTurn);
      
      // Verify transition to SHOOTING
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.SHOOTING,
        { turnData: freeThrowTurn }
      );
      
      // 3. Handle made free throw
      const makeTurn = createMockTurnData('MAKE', 2, {
        shooter_id: 'player1',
        result_type: 'MAKE'
      });
      
      await animationRouter.processTurn(makeTurn);
      
      // Verify transition to IDLE (end of free throw sequence)
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        { turnData: makeTurn }
      );
    });

    test('should handle fast break sequence: possession → fast break → shot', async () => {
      // 1. Start with possession
      animationRouter.stateMachine.state = AnimationStates.POSSESSION;
      animationRouter.ballController.attachToPlayer(mockPlayerSprites['player1']);
      
      // 2. Fast break
      const fastBreakTurn = createMockTurnData('FAST_BREAK', 1, {
        outlet_passer: 'player1',
        fast_break_receiver: 'player3',
        fast_break: true
      });
      
      await animationRouter.processTurn(fastBreakTurn);
      
      // Verify transition to POSSESSION
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.POSSESSION,
        { turnData: fastBreakTurn }
      );
      
      // 3. Fast break shot
      const shotTurn = createMockTurnData('MISS', 2, {
        shooter_id: 'player3',
        shot_type: 'fast_break_layup'
      });
      
      await animationRouter.processTurn(shotTurn);
      
      // Verify transition to REBOUNDING
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.REBOUNDING,
        { turnData: shotTurn }
      );
    });
  });

  describe('State Machine Coordination', () => {
    test('should coordinate state machine with ball controller', async () => {
      // Test ball attachment triggers state change
      const playerSprite = mockPlayerSprites['player1'];
      
      // Simulate ball attachment
      animationRouter.handleBallAttachment(null, playerSprite);
      
      // Verify state machine transitioned to POSSESSION
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.POSSESSION,
        { reason: 'ball_attached', playerId: 'player1' }
      );
    });

    test('should coordinate state machine with ball detachment', async () => {
      const playerSprite = mockPlayerSprites['player1'];
      
      // Simulate ball detachment for shot
      animationRouter.handleBallDetachment(playerSprite, 'shot');
      
      // Verify state machine transitioned to SHOOTING
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.SHOOTING,
        { reason: 'ball_detached_for_shot', playerId: 'player1' }
      );
    });

    test('should handle state change events correctly', async () => {
      const stateChangeData = {
        prevState: AnimationStates.IDLE,
        newState: AnimationStates.POSSESSION,
        context: { playerId: 'player1' }
      };
      
      // Mock ball controller state
      animationRouter.ballController.isBallAttached.mockReturnValue(false);
      animationRouter.findPlayerSprite.mockReturnValue(mockPlayerSprites['player1']);
      
      // Handle state change
      animationRouter.handleStateChange(stateChangeData);
      
      // Verify ball was attached to player
      expect(animationRouter.ballController.attachToPlayer).toHaveBeenCalledWith(
        mockPlayerSprites['player1']
      );
    });
  });

  describe('Animation Engine Integration', () => {
    test('should route turns to animation engine correctly', async () => {
      const turnData = createMockTurnData('MAKE');
      
      await animationRouter.processTurn(turnData);
      
      // Verify animation engine was called
      expect(animationRouter.animationEngine.processTurn).toHaveBeenCalledWith(turnData);
    });

    test('should handle animation engine errors gracefully', async () => {
      const turnData = createMockTurnData('MAKE');
      const error = new Error('Animation engine error');
      
      animationRouter.animationEngine.processTurn.mockRejectedValue(error);
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      await animationRouter.processTurn(turnData);
      
      // Verify error was handled
      expect(consoleSpy).toHaveBeenCalledWith(
        'AnimationRouter: Error processing turn',
        error
      );
      
      // Verify system was reset to safe state
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        { reason: 'error_recovery' }
      );
      
      consoleSpy.mockRestore();
    });
  });

  describe('Queue Management', () => {
    test('should handle multiple queued turns correctly', async () => {
      const turn1 = createMockTurnData('MAKE', 1);
      const turn2 = createMockTurnData('MISS', 2);
      const turn3 = createMockTurnData('REBOUND', 3);
      
      // Mock processing to take time
      animationRouter.animationEngine.processTurn.mockImplementation(() => 
        new Promise(resolve => setTimeout(resolve, 50))
      );
      
      // Start processing first turn
      const processPromise = animationRouter.processTurn(turn1);
      
      // Queue additional turns
      animationRouter.processTurn(turn2);
      animationRouter.processTurn(turn3);
      
      // Wait for all turns to complete
      await processPromise;
      
      // Verify all turns were processed
      expect(animationRouter.animationEngine.processTurn).toHaveBeenCalledWith(turn1);
      expect(animationRouter.animationEngine.processTurn).toHaveBeenCalledWith(turn2);
      expect(animationRouter.animationEngine.processTurn).toHaveBeenCalledWith(turn3);
    });

    test('should maintain turn order in queue', async () => {
      const turns = [
        createMockTurnData('MAKE', 1),
        createMockTurnData('MISS', 2),
        createMockTurnData('REBOUND', 3)
      ];
      
      // Mock processing
      animationRouter.animationEngine.processTurn.mockImplementation(() => 
        new Promise(resolve => setTimeout(resolve, 10))
      );
      
      // Queue all turns
      turns.forEach(turn => animationRouter.processTurn(turn));
      
      // Wait for processing
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // Verify turns were processed in order
      expect(animationRouter.animationEngine.processTurn).toHaveBeenNthCalledWith(1, turns[0]);
      expect(animationRouter.animationEngine.processTurn).toHaveBeenNthCalledWith(2, turns[1]);
      expect(animationRouter.animationEngine.processTurn).toHaveBeenNthCalledWith(3, turns[2]);
    });
  });

  describe('Error Recovery', () => {
    test('should recover from component errors', async () => {
      const turnData = createMockTurnData('MAKE');
      const error = new Error('Component error');
      
      // Mock error in animation engine
      animationRouter.animationEngine.processTurn.mockRejectedValue(error);
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      await animationRouter.processTurn(turnData);
      
      // Verify error recovery
      expect(consoleSpy).toHaveBeenCalledWith(
        'AnimationRouter: Error occurred',
        expect.objectContaining({
          error: 'Component error',
          turnData,
          currentState: AnimationStates.IDLE
        })
      );
      
      // Verify system was reset
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        { reason: 'error_recovery' }
      );
      
      expect(animationRouter.ballController.reset).toHaveBeenCalled();
      
      consoleSpy.mockRestore();
    });

    test('should handle invalid state transitions gracefully', async () => {
      const turnData = createMockTurnData('INVALID_TYPE');
      
      // Mock invalid state transition
      animationRouter.stateMachine.canTransitionTo.mockReturnValue(false);
      
      await animationRouter.processTurn(turnData);
      
      // Verify warning was logged
      expect(console.warn).toHaveBeenCalledWith(
        'AnimationRouter: Cannot transition to state',
        undefined
      );
      
      // Verify turn was still processed
      expect(animationRouter.animationEngine.processTurn).toHaveBeenCalledWith(turnData);
    });
  });

  describe('System Status and Monitoring', () => {
    test('should provide comprehensive system status', () => {
      const status = animationRouter.getStatus();
      
      // Verify all status components are present
      expect(status).toHaveProperty('isProcessing');
      expect(status).toHaveProperty('currentTurn');
      expect(status).toHaveProperty('stateMachine');
      expect(status).toHaveProperty('ballController');
      expect(status).toHaveProperty('animationEngine');
      expect(status).toHaveProperty('queue');
      expect(status).toHaveProperty('isInitialized');
      
      // Verify status values
      expect(status.isProcessing).toBe(false);
      expect(status.currentTurn).toBe(null);
      expect(status.isInitialized).toBe(true);
      expect(status.queue.length).toBe(0);
    });

    test('should provide system information', () => {
      const info = animationRouter.getSystemInfo();
      
      // Verify system info structure
      expect(info).toHaveProperty('components');
      expect(info).toHaveProperty('status');
      expect(info).toHaveProperty('capabilities');
      
      // Verify component names
      expect(info.components.stateMachine).toBe('SimplifiedStateMachine');
      expect(info.components.ballController).toBe('BallController');
      expect(info.components.animationEngine).toBe('AnimationEngine');
      
      // Verify capabilities
      expect(info.capabilities.canProcessTurns).toBe(true);
      expect(info.capabilities.canHandleStateTransitions).toBe(true);
      expect(info.capabilities.canManageBallOwnership).toBe(true);
      expect(info.capabilities.canQueueAnimations).toBe(true);
    });
  });

  describe('System Reset and Recovery', () => {
    test('should reset entire system correctly', () => {
      // Set up some state
      animationRouter.isProcessing = true;
      animationRouter.currentTurn = createMockTurnData('MAKE');
      animationRouter.animationQueue = [createMockTurnData('MISS')];
      
      // Reset system
      animationRouter.reset();
      
      // Verify reset
      expect(animationRouter.isProcessing).toBe(false);
      expect(animationRouter.currentTurn).toBe(null);
      expect(animationRouter.animationQueue).toHaveLength(0);
      
      // Verify components were reset
      expect(animationRouter.stateMachine.transitionTo).toHaveBeenCalledWith(
        AnimationStates.IDLE,
        { reason: 'system_reset' }
      );
      expect(animationRouter.ballController.reset).toHaveBeenCalled();
    });

    test('should handle system reset during processing', () => {
      // Set up processing state
      animationRouter.isProcessing = true;
      animationRouter.currentTurn = createMockTurnData('MAKE');
      
      // Reset system
      animationRouter.reset();
      
      // Verify processing was stopped
      expect(animationRouter.isProcessing).toBe(false);
      expect(animationRouter.currentTurn).toBe(null);
    });
  });

  describe('Debug and Monitoring', () => {
    test('should enable debug mode across components', () => {
      animationRouter.setDebug(true);
      
      // Verify ball controller debug was enabled
      expect(animationRouter.ballController.setDebug).toHaveBeenCalledWith(true);
    });

    test('should disable debug mode across components', () => {
      animationRouter.setDebug(false);
      
      // Verify ball controller debug was disabled
      expect(animationRouter.ballController.setDebug).toHaveBeenCalledWith(false);
    });
  });

  describe('Real-World Basketball Scenarios', () => {
    test('should handle complex possession sequence', async () => {
      // 1. Defensive rebound
      const reboundTurn = createMockTurnData('REBOUND', 1, {
        rebounder_id: 'player2',
        rebound_type: 'defensive'
      });
      
      await animationRouter.processTurn(reboundTurn);
      
      // 2. Outlet pass
      const outletTurn = createMockTurnData('MAKE', 2, {
        passer_id: 'player2',
        receiver_id: 'player1',
        pass_type: 'outlet'
      });
      
      await animationRouter.processTurn(outletTurn);
      
      // 3. Half court offense
      const offenseTurn = createMockTurnData('MAKE', 3, {
        player_id: 'player1',
        action_type: 'dribble'
      });
      
      await animationRouter.processTurn(offenseTurn);
      
      // Verify all turns were processed
      expect(animationRouter.animationEngine.processTurn).toHaveBeenCalledTimes(3);
    });

    test('should handle free throw sequence with multiple attempts', async () => {
      // 1. First free throw
      const ft1Turn = createMockTurnData('FREE_THROW', 1, {
        shooter_id: 'player1',
        ft_context: { attempt: 1, total: 2 }
      });
      
      await animationRouter.processTurn(ft1Turn);
      
      // 2. Second free throw
      const ft2Turn = createMockTurnData('FREE_THROW', 2, {
        shooter_id: 'player1',
        ft_context: { attempt: 2, total: 2 }
      });
      
      await animationRouter.processTurn(ft2Turn);
      
      // Verify both free throws were processed
      expect(animationRouter.animationEngine.processTurn).toHaveBeenCalledTimes(2);
    });

    test('should handle fast break with shot and rebound', async () => {
      // 1. Fast break
      const fastBreakTurn = createMockTurnData('FAST_BREAK', 1, {
        outlet_passer: 'player2',
        fast_break_receiver: 'player1',
        fast_break: true
      });
      
      await animationRouter.processTurn(fastBreakTurn);
      
      // 2. Fast break shot
      const shotTurn = createMockTurnData('MISS', 2, {
        shooter_id: 'player1',
        shot_type: 'fast_break_layup'
      });
      
      await animationRouter.processTurn(shotTurn);
      
      // 3. Defensive rebound
      const reboundTurn = createMockTurnData('REBOUND', 3, {
        rebounder_id: 'player2',
        rebound_type: 'defensive'
      });
      
      await animationRouter.processTurn(reboundTurn);
      
      // Verify all turns were processed
      expect(animationRouter.animationEngine.processTurn).toHaveBeenCalledTimes(3);
    });
  });
});
