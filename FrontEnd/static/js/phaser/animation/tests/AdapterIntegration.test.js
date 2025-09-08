/**
 * BallController Adapter Integration Tests
 * 
 * Tests that the adapter works correctly with existing animation systems
 */

import { initializeBallController } from '../BallControllerAdapter.js';
import { attachBallToPlayer, detachBall } from '../BallControllerAdapter.js';

describe('BallController Adapter Integration', () => {
  let mockScene;
  let mockBallSprite;
  let mockPlayerSprite;

  beforeEach(() => {
    // Create realistic mock scene
    mockScene = {
      events: {
        on: jest.fn(),
        off: jest.fn()
      },
      currentBallOwnerRef: { value: null },
      ballDetached: false,
      possessionFlipInProgress: false,
      offenseTeamId: 'home',
      playerSprites: {},
      stateMachine: {
        is: jest.fn().mockReturnValue(false)
      }
    };

    // Create realistic mock ball sprite
    mockBallSprite = {
      x: 0,
      y: 0,
      setPosition: jest.fn(),
      setVisible: jest.fn(),
      setDepth: jest.fn(),
      visible: true
    };

    // Create realistic mock player sprite
    mockPlayerSprite = {
      playerId: 'player1',
      team_id: 'home',
      team: 'home',
      x: 100,
      y: 200
    };

    mockScene.playerSprites['player1'] = mockPlayerSprite;
  });

  describe('Backward Compatibility', () => {
    test('should work with old system function signatures', () => {
      // Initialize the adapter
      initializeBallController(mockScene, mockBallSprite);
      
      // Test old system function signature
      attachBallToPlayer(mockScene, mockBallSprite, mockPlayerSprite, { depth: 50 });
      
      // Verify old system state is updated
      expect(mockScene.currentBallOwnerRef.value).toBe(mockPlayerSprite);
      expect(mockScene.ballDetached).toBe(false);
      expect(mockBallSprite.setDepth).toHaveBeenCalledWith(50);
    });

    test('should handle old system possession flip logic', () => {
      initializeBallController(mockScene, mockBallSprite);
      
      // Simulate possession flip
      mockScene.possessionFlipInProgress = true;
      mockScene.offenseTeamId = 'away';
      mockPlayerSprite.team_id = 'home';
      
      attachBallToPlayer(mockScene, mockBallSprite, mockPlayerSprite);
      
      // Should not attach due to possession flip
      expect(mockScene.currentBallOwnerRef.value).toBe(null);
    });

    test('should handle old system rebound state logic', () => {
      initializeBallController(mockScene, mockBallSprite);
      
      // Simulate rebound state
      mockScene.stateMachine.is.mockReturnValue(true);
      mockScene.rebounderId = 'player2';
      
      attachBallToPlayer(mockScene, mockBallSprite, mockPlayerSprite);
      
      // Should not attach due to rebound state restriction
      expect(mockScene.currentBallOwnerRef.value).toBe(null);
    });

    test('should handle old system debug info format', () => {
      initializeBallController(mockScene, mockBallSprite);
      
      const debugInfo = {
        shooterId: 'shooter1',
        reboundSpot: { x: 10, y: 20 }
      };
      
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();
      
      attachBallToPlayer(mockScene, mockBallSprite, mockPlayerSprite, { debugInfo });
      
      // Verify debug info is logged in old system format
      expect(consoleSpy).toHaveBeenCalledWith(
        'BallControllerAdapter: Ball attached',
        expect.objectContaining({
          type: 'ballAttach',
          shooterId: 'shooter1',
          reboundSpot: { x: 10, y: 20 },
          playerId: 'player1',
          team: 'home'
        })
      );
      
      consoleSpy.mockRestore();
    });
  });

  describe('State Management', () => {
    test('should maintain consistent state between old and new systems', () => {
      initializeBallController(mockScene, mockBallSprite);
      
      // Attach using old system
      attachBallToPlayer(mockScene, mockBallSprite, mockPlayerSprite);
      
      // Verify both systems have consistent state
      expect(mockScene.currentBallOwnerRef.value).toBe(mockPlayerSprite);
      expect(mockScene.ballDetached).toBe(false);
      
      // Detach using old system
      detachBall(mockScene, mockBallSprite);
      
      // Verify both systems have consistent state
      expect(mockScene.ballDetached).toBe(true);
    });
  });

  describe('Error Scenarios', () => {
    test('should handle missing scene gracefully', () => {
      initializeBallController(mockScene, mockBallSprite);
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      attachBallToPlayer(null, mockBallSprite, mockPlayerSprite);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'BallControllerAdapter: Cannot attach ball - BallController not initialized'
      );
      
      consoleSpy.mockRestore();
    });

    test('should handle missing ball sprite gracefully', () => {
      initializeBallController(mockScene, mockBallSprite);
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      attachBallToPlayer(mockScene, null, mockPlayerSprite);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'BallControllerAdapter: Cannot attach ball - BallController not initialized'
      );
      
      consoleSpy.mockRestore();
    });

    test('should handle missing player sprite gracefully', () => {
      initializeBallController(mockScene, mockBallSprite);
      
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
      
      attachBallToPlayer(mockScene, mockBallSprite, null);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'BallControllerAdapter: Cannot attach ball - BallController not initialized'
      );
      
      consoleSpy.mockRestore();
    });
  });
});
