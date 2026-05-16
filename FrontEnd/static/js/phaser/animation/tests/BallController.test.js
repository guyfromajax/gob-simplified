/**
 * BallController Tests
 * 
 * Tests for the single source of truth ball ownership system
 */

import { BallController } from '../BallController.js';
import { BALL_ATTACH_OFFSET } from '../../setup/markerConfig.js';

// Mock Phaser ball sprite
const createMockBallSprite = () => ({
  x: 100,
  y: 200,
  visible: false,
  depth: 0,
  setPosition: jest.fn(),
  setVisible: jest.fn(),
  setDepth: jest.fn()
});

// Mock Phaser scene
const createMockScene = () => ({
  events: {
    on: jest.fn(),
    off: jest.fn(),
    emit: jest.fn()
  }
});

// Mock player sprite
const createMockPlayerSprite = (playerId = 'player1', team = 'home') => ({
  playerId,
  team,
  x: 150,
  y: 250,
  depth: 10
});

describe('BallController', () => {
  let ballController;
  let mockBallSprite;
  let mockScene;

  beforeEach(() => {
    mockBallSprite = createMockBallSprite();
    mockScene = createMockScene();
    ballController = new BallController(mockScene, mockBallSprite);
  });

  describe('Initialization', () => {
    test('should initialize with correct default state', () => {
      const state = ballController.getState();
      expect(state.currentOwner).toBe(null);
      expect(state.pendingOwner).toBe(null);
      expect(state.isAttached).toBe(false);
      expect(state.isDetached).toBe(false);
      expect(state.isInFlight).toBe(false);
      expect(state.isMoving).toBe(false);
    });

    test('should initialize ball sprite correctly', () => {
      expect(mockBallSprite.setVisible).toHaveBeenCalledWith(false);
      expect(mockBallSprite.setDepth).toHaveBeenCalledWith(1000);
    });

    test('should handle missing ball sprite gracefully', () => {
      const controller = new BallController(mockScene, null);
      expect(controller.getState().currentOwner).toBe(null);
    });
  });

  describe('Ball Attachment', () => {
    test('should attach ball to valid player', () => {
      const playerSprite = createMockPlayerSprite();
      const result = ballController.attachToPlayer(playerSprite);
      
      expect(result).toBe(true);
      expect(ballController.getCurrentOwner()).toBe(playerSprite);
      expect(ballController.isBallAttached()).toBe(true);
      expect(mockBallSprite.setVisible).toHaveBeenCalledWith(true);
    });

    test('should position ball on player correctly', () => {
      const playerSprite = createMockPlayerSprite();
      ballController.attachToPlayer(playerSprite);

      // Default offset is BALL_ATTACH_OFFSET (hip anchor for headshot marker; {0,0} when flag is off).
      expect(mockBallSprite.setPosition).toHaveBeenCalledWith(
        150 + BALL_ATTACH_OFFSET.x,
        250 + BALL_ATTACH_OFFSET.y,
      );
      expect(mockBallSprite.setDepth).toHaveBeenCalledWith(11); // player depth + 1
    });

    test('should use custom offset when provided', () => {
      const playerSprite = createMockPlayerSprite();
      const options = { offset: { x: 5, y: -15 } };
      ballController.attachToPlayer(playerSprite, options);
      
      expect(mockBallSprite.setPosition).toHaveBeenCalledWith(155, 235);
    });

    test('should not attach to invalid player sprite', () => {
      const invalidPlayer = { x: 'invalid', y: 200 };
      const result = ballController.attachToPlayer(invalidPlayer);
      
      expect(result).toBe(false);
      expect(ballController.getCurrentOwner()).toBe(null);
    });

    test('should not attach when ball is in flight', () => {
      const playerSprite = createMockPlayerSprite();
      ballController.startFlight({ x: 200, y: 300 });
      
      const result = ballController.attachToPlayer(playerSprite);
      
      expect(result).toBe(false);
      expect(ballController.getCurrentOwner()).toBe(null);
    });

    test('should record ownership change in history', () => {
      const playerSprite = createMockPlayerSprite();
      ballController.attachToPlayer(playerSprite);
      
      const history = ballController.getOwnershipHistory();
      expect(history).toHaveLength(1);
      expect(history[0].from).toBe(null);
      expect(history[0].to).toBe('player1');
      expect(history[0].reason).toBe('attach');
    });
  });

  describe('Ball Detachment', () => {
    test('should detach ball from current owner', () => {
      const playerSprite = createMockPlayerSprite();
      ballController.attachToPlayer(playerSprite);
      
      const result = ballController.detachFromPlayer();
      
      expect(result).toBe(true);
      expect(ballController.getCurrentOwner()).toBe(null);
      expect(ballController.isBallAttached()).toBe(false);
      expect(ballController.isBallInFlight()).toBe(false);
    });

    test('should not detach when ball is not attached', () => {
      const result = ballController.detachFromPlayer();
      
      expect(result).toBe(false);
    });

    test('should hide ball when detached and not in flight', () => {
      const playerSprite = createMockPlayerSprite();
      ballController.attachToPlayer(playerSprite);
      ballController.detachFromPlayer();
      
      expect(mockBallSprite.setVisible).toHaveBeenCalledWith(false);
    });

    test('should record detachment in history', () => {
      const playerSprite = createMockPlayerSprite();
      ballController.attachToPlayer(playerSprite);
      ballController.detachFromPlayer('test_reason');
      
      const history = ballController.getOwnershipHistory();
      expect(history).toHaveLength(2);
      expect(history[1].from).toBe('player1');
      expect(history[1].to).toBe(null);
      expect(history[1].reason).toBe('test_reason');
    });
  });

  describe('Pending Owner', () => {
    test('should set pending owner', () => {
      const playerSprite = createMockPlayerSprite();
      const result = ballController.setPendingOwner(playerSprite);
      
      expect(result).toBe(true);
      expect(ballController.getPendingOwner()).toBe(playerSprite);
    });

    test('should clear pending owner', () => {
      const playerSprite = createMockPlayerSprite();
      ballController.setPendingOwner(playerSprite);
      ballController.clearPendingOwner();
      
      expect(ballController.getPendingOwner()).toBe(null);
    });

    test('should not set invalid pending owner', () => {
      const invalidPlayer = { x: 'invalid' };
      const result = ballController.setPendingOwner(invalidPlayer);
      
      expect(result).toBe(false);
      expect(ballController.getPendingOwner()).toBe(null);
    });
  });

  describe('Ball Flight', () => {
    test('should start ball flight', () => {
      const targetPosition = { x: 300, y: 400 };
      const result = ballController.startFlight(targetPosition);
      
      expect(result).toBe(true);
      expect(ballController.isBallInFlight()).toBe(true);
      expect(ballController.isBallMoving()).toBe(true);
      expect(mockBallSprite.setVisible).toHaveBeenCalledWith(true);
    });

    test('should not start flight when already in flight', () => {
      const targetPosition = { x: 300, y: 400 };
      ballController.startFlight(targetPosition);
      
      const result = ballController.startFlight({ x: 400, y: 500 });
      
      expect(result).toBe(false);
    });

    test('should end ball flight', () => {
      const targetPosition = { x: 300, y: 400 };
      ballController.startFlight(targetPosition);
      
      const newOwner = createMockPlayerSprite('player2');
      const result = ballController.endFlight(newOwner);
      
      expect(result).toBe(true);
      expect(ballController.isBallInFlight()).toBe(false);
      expect(ballController.isBallMoving()).toBe(false);
      expect(ballController.getCurrentOwner()).toBe(newOwner);
    });

    test('should end flight without new owner', () => {
      const targetPosition = { x: 300, y: 400 };
      ballController.startFlight(targetPosition);
      
      const result = ballController.endFlight();
      
      expect(result).toBe(true);
      expect(ballController.isBallInFlight()).toBe(false);
      expect(ballController.getCurrentOwner()).toBe(null);
      expect(mockBallSprite.setVisible).toHaveBeenCalledWith(false);
    });

    test('should not end flight when not in flight', () => {
      const result = ballController.endFlight();
      
      expect(result).toBe(false);
    });
  });

  describe('Position Updates', () => {
    test('should update ball position', () => {
      ballController.updatePosition(250, 350);
      
      expect(mockBallSprite.setPosition).toHaveBeenCalledWith(250, 350);
    });

    test('should follow attached player during position updates', () => {
      const playerSprite = createMockPlayerSprite();
      ballController.attachToPlayer(playerSprite);
      
      // Update player position
      playerSprite.x = 200;
      playerSprite.y = 300;
      
      ballController.updatePosition(200, 300);

      // Should reposition ball on player, anchored at hip via BALL_ATTACH_OFFSET.
      expect(mockBallSprite.setPosition).toHaveBeenCalledWith(
        200 + BALL_ATTACH_OFFSET.x,
        300 + BALL_ATTACH_OFFSET.y,
      );
    });
  });

  describe('Callbacks', () => {
    test('should notify attachment callbacks', () => {
      const callback = jest.fn();
      ballController.onAttachment(callback);
      
      const playerSprite = createMockPlayerSprite();
      ballController.attachToPlayer(playerSprite);
      
      expect(callback).toHaveBeenCalledWith(null, playerSprite, {});
    });

    test('should notify detachment callbacks', () => {
      const callback = jest.fn();
      ballController.onDetachment(callback);
      
      const playerSprite = createMockPlayerSprite();
      ballController.attachToPlayer(playerSprite);
      ballController.detachFromPlayer('test_reason');
      
      expect(callback).toHaveBeenCalledWith(playerSprite, 'test_reason', {});
    });

    test('should handle callback errors gracefully', () => {
      const errorCallback = jest.fn().mockImplementation(() => {
        throw new Error('Callback error');
      });
      const normalCallback = jest.fn();
      
      ballController.onAttachment(errorCallback);
      ballController.onAttachment(normalCallback);
      
      const playerSprite = createMockPlayerSprite();
      
      // Should not throw error
      expect(() => ballController.attachToPlayer(playerSprite)).not.toThrow();
      
      // Normal callback should still be called
      expect(normalCallback).toHaveBeenCalled();
    });
  });

  describe('State Queries', () => {
    test('should return correct ball state', () => {
      const playerSprite = createMockPlayerSprite();
      ballController.attachToPlayer(playerSprite);
      
      const state = ballController.getState();
      
      expect(state.currentOwner).toBe('player1');
      expect(state.isAttached).toBe(true);
      expect(state.isDetached).toBe(false);
      expect(state.isInFlight).toBe(false);
      expect(state.isMoving).toBe(false);
    });

    test('should return correct state during flight', () => {
      const playerSprite = createMockPlayerSprite();
      ballController.attachToPlayer(playerSprite);
      ballController.startFlight({ x: 300, y: 400 });
      
      const state = ballController.getState();
      
      expect(state.isInFlight).toBe(true);
      expect(state.isMoving).toBe(true);
    });
  });

  describe('History Management', () => {
    test('should limit ownership history to prevent memory leaks', () => {
      // Create many ownership changes
      for (let i = 0; i < 60; i++) {
        const playerSprite = createMockPlayerSprite(`player${i}`);
        ballController.attachToPlayer(playerSprite);
        ballController.detachFromPlayer();
      }
      
      const history = ballController.getOwnershipHistory();
      expect(history.length).toBeLessThanOrEqual(50);
    });

    test('should return limited history', () => {
      // Create some ownership changes
      for (let i = 0; i < 5; i++) {
        const playerSprite = createMockPlayerSprite(`player${i}`);
        ballController.attachToPlayer(playerSprite);
        ballController.detachFromPlayer();
      }
      
      const history = ballController.getOwnershipHistory(3);
      expect(history).toHaveLength(3);
    });
  });

  describe('Reset Functionality', () => {
    test('should reset to initial state', () => {
      const playerSprite = createMockPlayerSprite();
      ballController.attachToPlayer(playerSprite);
      ballController.startFlight({ x: 300, y: 400 });
      
      ballController.reset();
      
      const state = ballController.getState();
      expect(state.currentOwner).toBe(null);
      expect(state.pendingOwner).toBe(null);
      expect(state.isAttached).toBe(false);
      expect(state.isDetached).toBe(false);
      expect(state.isInFlight).toBe(false);
      expect(state.isMoving).toBe(false);
      expect(mockBallSprite.setVisible).toHaveBeenCalledWith(false);
    });
  });

  describe('Debug Mode', () => {
    test('should enable debug logging', () => {
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();
      
      ballController.setDebug(true);
      const playerSprite = createMockPlayerSprite();
      ballController.attachToPlayer(playerSprite);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'BallController: Ball attached to player',
        expect.objectContaining({
          playerId: 'player1',
          team: 'home'
        })
      );
      
      consoleSpy.mockRestore();
    });
  });

  describe('Edge Cases', () => {
    test('should handle null player sprite', () => {
      const result = ballController.attachToPlayer(null);
      expect(result).toBe(false);
    });

    test('should handle undefined player sprite', () => {
      const result = ballController.attachToPlayer(undefined);
      expect(result).toBe(false);
    });

    test('should handle player sprite without playerId', () => {
      const playerSprite = { x: 100, y: 200, team: 'home' };
      const result = ballController.attachToPlayer(playerSprite);
      expect(result).toBe(false);
    });

    test('should handle position updates with no ball sprite', () => {
      const controller = new BallController(mockScene, null);
      expect(() => controller.updatePosition(100, 200)).not.toThrow();
    });
  });

  describe('Integration Scenarios', () => {
    test('should handle complete pass sequence', () => {
      const passer = createMockPlayerSprite('passer');
      const receiver = createMockPlayerSprite('receiver');
      
      // Attach to passer
      ballController.attachToPlayer(passer);
      expect(ballController.getCurrentOwner()).toBe(passer);
      
      // Start pass
      ballController.startFlight({ x: 200, y: 300 });
      expect(ballController.isBallInFlight()).toBe(true);
      
      // End pass to receiver
      ballController.endFlight(receiver);
      expect(ballController.getCurrentOwner()).toBe(receiver);
      expect(ballController.isBallInFlight()).toBe(false);
    });

    test('should handle shot sequence', () => {
      const shooter = createMockPlayerSprite('shooter');
      
      // Attach to shooter
      ballController.attachToPlayer(shooter);
      
      // Start shot
      ballController.startFlight({ x: 100, y: 50 });
      
      // Miss shot (no new owner)
      ballController.endFlight();
      expect(ballController.getCurrentOwner()).toBe(null);
      expect(ballController.isBallInFlight()).toBe(false);
    });

    test('should handle rebound sequence', () => {
      const shooter = createMockPlayerSprite('shooter');
      const rebounder = createMockPlayerSprite('rebounder');
      
      // Shooter takes shot
      ballController.attachToPlayer(shooter);
      ballController.startFlight({ x: 100, y: 50 });
      ballController.endFlight(); // Miss
      
      // Rebounder gets ball
      ballController.attachToPlayer(rebounder);
      expect(ballController.getCurrentOwner()).toBe(rebounder);
    });
  });
});
