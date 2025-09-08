/**
 * BallController Adapter Tests
 * 
 * Tests the backward compatibility layer between old and new ball systems
 */

import { 
  initializeBallController, 
  getBallController, 
  attachBallToPlayer, 
  detachBall,
  getCurrentOwner,
  setCurrentOwner,
  clearCurrentOwner
} from '../BallControllerAdapter.js';

describe('BallController Adapter', () => {
  let mockScene;
  let mockBallSprite;
  let mockPlayerSprite;

  beforeEach(() => {
    // Reset global state
    globalBallController = null;
    
    // Create mock scene
    mockScene = {
      events: {
        on: jest.fn(),
        off: jest.fn()
      },
      currentBallOwnerRef: { value: null },
      ballDetached: false,
      possessionFlipInProgress: false,
      offenseTeamId: 'home',
      playerSprites: {}
    };

    // Create mock ball sprite
    mockBallSprite = {
      x: 0,
      y: 0,
      setPosition: jest.fn(),
      setVisible: jest.fn(),
      setDepth: jest.fn(),
      visible: true
    };

    // Create mock player sprite
    mockPlayerSprite = {
      playerId: 'player1',
      team_id: 'home',
      team: 'home',
      x: 100,
      y: 200
    };

    mockScene.playerSprites['player1'] = mockPlayerSprite;
  });

  describe('Initialization', () => {
    test('should initialize global BallController', () => {
      const controller = initializeBallController(mockScene, mockBallSprite);
      
      expect(controller).toBeDefined();
      expect(getBallController()).toBe(controller);
    });

    test('should warn if already initialized', () => {
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
      
      initializeBallController(mockScene, mockBallSprite);
      initializeBallController(mockScene, mockBallSprite);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'BallControllerAdapter: Global BallController already initialized'
      );
      
      consoleSpy.mockRestore();
    });
  });

  describe('attachBallToPlayer', () => {
    beforeEach(() => {
      initializeBallController(mockScene, mockBallSprite);
    });

    test('should attach ball to player successfully', () => {
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();
      
      attachBallToPlayer(mockScene, mockBallSprite, mockPlayerSprite);
      
      expect(mockScene.currentBallOwnerRef.value).toBe(mockPlayerSprite);
      expect(mockScene.ballDetached).toBe(false);
      
      consoleSpy.mockRestore();
    });

    test('should skip attach during possession flip', () => {
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();
      mockScene.possessionFlipInProgress = true;
      
      attachBallToPlayer(mockScene, mockBallSprite, mockPlayerSprite);
      
      expect(mockScene.currentBallOwnerRef.value).toBe(null);
      expect(consoleSpy).toHaveBeenCalledWith(
        'BallControllerAdapter: Skipping attach due to possessionFlipInProgress'
      );
      
      consoleSpy.mockRestore();
    });

    test('should handle debug info', () => {
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();
      const debugInfo = { shooterId: 'shooter1', reboundSpot: { x: 10, y: 20 } };
      
      attachBallToPlayer(mockScene, mockBallSprite, mockPlayerSprite, { debugInfo });
      
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

    test('should handle depth option', () => {
      attachBallToPlayer(mockScene, mockBallSprite, mockPlayerSprite, { depth: 100 });
      
      expect(mockBallSprite.setDepth).toHaveBeenCalledWith(100);
    });
  });

  describe('detachBall', () => {
    beforeEach(() => {
      initializeBallController(mockScene, mockBallSprite);
    });

    test('should detach ball successfully', () => {
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();
      
      detachBall(mockScene, mockBallSprite);
      
      expect(mockScene.ballDetached).toBe(true);
      expect(consoleSpy).toHaveBeenCalledWith('BallControllerAdapter: Ball detached');
      
      consoleSpy.mockRestore();
    });
  });

  describe('Helper Functions', () => {
    beforeEach(() => {
      initializeBallController(mockScene, mockBallSprite);
    });

    test('getCurrentOwner should return current owner', () => {
      attachBallToPlayer(mockScene, mockBallSprite, mockPlayerSprite);
      
      const owner = getCurrentOwner(mockScene);
      expect(owner).toBe(mockPlayerSprite);
    });

    test('setCurrentOwner should attach ball to player', () => {
      setCurrentOwner(mockScene, 'player1');
      
      expect(mockScene.currentBallOwnerRef.value).toBe(mockPlayerSprite);
    });

    test('clearCurrentOwner should detach ball', () => {
      attachBallToPlayer(mockScene, mockBallSprite, mockPlayerSprite);
      clearCurrentOwner(mockScene);
      
      expect(mockScene.ballDetached).toBe(true);
    });
  });

  describe('Error Handling', () => {
    test('should handle missing BallController gracefully', () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      attachBallToPlayer(mockScene, mockBallSprite, mockPlayerSprite);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'BallControllerAdapter: Cannot attach ball - BallController not initialized'
      );
      
      consoleSpy.mockRestore();
    });
  });
});
