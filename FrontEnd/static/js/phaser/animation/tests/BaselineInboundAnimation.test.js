/**
 * BASELINE_INBOUND Animation Tests
 * 
 * Validates that BASELINE_INBOUND turns animate properly and only once.
 * Tests the fix for double inbound pass bug.
 */

import { AnimationEngine } from '../AnimationEngine.js';
import { AnimationRouter } from '../AnimationRouter.js';
import { ShotAnimationSystem } from '../ShotAnimationSystem.js';
import { CLAMP_BOUNDS, clampGridCoords } from '../courtClamp.js';

// Mock dependencies
const createMockScene = () => ({
  game: {
    config: { width: 800, height: 600 }
  },
  simData: {
    home_team_id: 'HOME_TEAM_ID',
    away_team_id: 'AWAY_TEAM_ID',
    turns: []
  },
  homeTeamId: 'HOME_TEAM_ID',
  awayTeamId: 'AWAY_TEAM_ID',
  tweens: {
    killTweensOf: () => {},
    add: () => ({ stop: () => {} })
  },
  time: {
    delayedCall: (delay, callback) => setTimeout(callback, delay)
  },
  events: {
    once: () => {},
    emit: () => {}
  },
  stateMachine: {
    is: (state) => false,
    getCurrentState: () => 'IDLE',
    transition: () => {}
  },
  playerInfo: {},
  currentTurn: 0,
  currentPressureType: null,
  pressureSequenceActive: false,
  isInboundSetup: false,
  passInFlight: false,
  _previousTurnWasInbound: false,
  _previousTurnWasOpeningTip: false
});

const createMockBallSprite = () => ({
  setPosition: () => {},
  setVisible: () => {},
  x: 400,
  y: 300
});

const createMockPlayerSprites = () => ({
  'player1': { 
    team: 'home', 
    team_id: 'HOME_TEAM_ID', 
    x: 100, 
    y: 200,
    name: 'Player 1'
  },
  'player2': { 
    team: 'away', 
    team_id: 'AWAY_TEAM_ID', 
    x: 700, 
    y: 200,
    name: 'Player 2'
  }
});

const createMockBallController = () => ({
  ballSprite: createMockBallSprite(),
  attachToPlayer: () => {},
  detachFromPlayer: () => {},
  tweenTo: () => Promise.resolve(),
  isInFlight: false,
  onShotEnd: () => {},
  onPutbackEnd: () => {}
});

describe('BASELINE_INBOUND Animation Tests', () => {
  let scene, ballSprite, playerSprites, ballController;
  let animationEngine, animationRouter, shotSystem;
  let runInboundSetupCallCount = 0;
  let runInboundSetupCalls = [];

  beforeEach(() => {
    scene = createMockScene();
    ballSprite = createMockBallSprite();
    playerSprites = createMockPlayerSprites();
    ballController = createMockBallController();
    
    // Reset call tracking
    runInboundSetupCallCount = 0;
    runInboundSetupCalls = [];

    // Mock runInboundSetup to track calls
    jest.doMock('../turnAnimation.js', () => ({
      runInboundSetup: jest.fn((...args) => {
        runInboundSetupCallCount++;
        runInboundSetupCalls.push({
          args,
          stack: new Error().stack
        });
        return Promise.resolve();
      }),
      runSideInboundSetup: jest.fn(),
      runDefensiveReboundSetup: jest.fn(),
      getPlayerDuration: jest.fn(() => 1000)
    }));

    // Initialize systems
    animationEngine = new AnimationEngine(scene);
    animationRouter = new AnimationRouter(scene, animationEngine);
    shotSystem = new ShotAnimationSystem(scene, ballController, scene.stateMachine, playerSprites, {});
  });

  describe('BASELINE_INBOUND Turn Execution', () => {
    test('should execute BASELINE_INBOUND turn exactly once', async () => {
      const turnData = {
        result_type: 'BASELINE_INBOUND',
        current_turn: 'BASELINE_INBOUND',
        next_turn: 'HCO',
        offense_team_id: 'HOME_TEAM_ID',
        next_defensive_setup: null,
        oDestinations: {
          PG: { x: 50, y: 25 },
          SG: { x: 52, y: 22 },
          SF: { x: 54, y: 18 },
          PF: { x: 54, y: 30 },
          C: { x: 54, y: 14 }
        },
        dDestinations: {
          PG: { x: 45, y: 25 },
          SG: { x: 47, y: 22 },
          SF: { x: 49, y: 18 },
          PF: { x: 49, y: 30 },
          C: { x: 49, y: 14 }
        },
        ball_spot: { x: 50, y: 25 },
        animations: []
      };

      const context = {
        ballSprite: ballSprite,
        playerSprites: playerSprites
      };

      // Execute BASELINE_INBOUND turn
      await animationRouter.processTurn(turnData);

      // Verify runInboundSetup was called exactly once
      expect(runInboundSetupCallCount).toBe(1);
    });

    test('should not call runInboundSetup from made shot handlers when next_play_type is BASELINE_INBOUND', async () => {
      // Mock HCO MAKE turn with BASELINE_INBOUND next
      const hcoMakeTurnData = {
        result_type: 'MAKE',
        current_turn: 'HCO',
        next_play_type: 'BASELINE_INBOUND',
        next_defensive_setup: null,
        shooter_id: 'player1',
        possession_flips: true
      };

      // Try to call handleMadeShot (should skip runInboundSetup)
      await shotSystem.handleMadeShot({ x: 91, y: 25 }, hcoMakeTurnData);

      // Verify runInboundSetup was NOT called from handleMadeShot
      // (It should only be called from the BASELINE_INBOUND turn itself)
      expect(runInboundSetupCallCount).toBe(0);
    });
  });

  describe('Inbound clamp exemptions', () => {
    test('BASELINE_INBOUND keeps out-of-bounds inbound passer lane unmodified', () => {
      const inboundCoords = { x: CLAMP_BOUNDS.minX - 6, y: CLAMP_BOUNDS.maxY + 2 };
      const result = clampGridCoords(inboundCoords, { result_type: 'BASELINE_INBOUND' });
      expect(result).toEqual(inboundCoords);
    });

    test('SIDE_INBOUND keeps out-of-bounds inbound passer lane unmodified', () => {
      const inboundCoords = { x: CLAMP_BOUNDS.maxX + 6, y: CLAMP_BOUNDS.minY - 1 };
      const result = clampGridCoords(inboundCoords, { result_type: 'SIDE_INBOUND' });
      expect(result).toEqual(inboundCoords);
    });
  });

  describe('Made Shot Handler Validation', () => {
    test('HCO MAKE should skip runInboundSetup when next_play_type is BASELINE_INBOUND', async () => {
      const hcoMakeTurnData = {
        result_type: 'MAKE',
        current_turn: 'HCO',
        next_play_type: 'BASELINE_INBOUND',
        next_defensive_setup: null,
        shooter_id: 'player1',
        possession_flips: true
      };

      await shotSystem.handleMadeShot({ x: 91, y: 25 }, hcoMakeTurnData);

      // Should not call runInboundSetup (BASELINE_INBOUND turn will handle it)
      expect(runInboundSetupCallCount).toBe(0);
    });

    test('PUTBACK_MAKE should skip runInboundSetup when next_play_type is BASELINE_INBOUND', async () => {
      // Import handleOrebTurn
      const { handleOrebTurn } = await import('../animateGameTurns.js');
      
      const putbackMakeTurnData = {
        result_type: 'PUTBACK_MAKE',
        next_play_type: 'BASELINE_INBOUND',
        next_defensive_setup: null,
        rebounderId: 'player1',
        possession_flips: true
      };

      await handleOrebTurn(scene, {
        playerSprites,
        ballSprite,
        turnData: putbackMakeTurnData,
        onUpdate: () => {}
      });

      // Should not call runInboundSetup (BASELINE_INBOUND turn will handle it)
      expect(runInboundSetupCallCount).toBe(0);
    });

    test('Free Throw MAKE should skip runInboundSetup when next_play_type is BASELINE_INBOUND', async () => {
      const ftMakeTurnData = {
        result_type: 'MAKE',
        current_turn: 'FREE_THROW',
        next_play_type: 'BASELINE_INBOUND',
        next_defensive_setup: null,
        shooter_id: 'player1',
        free_throws_remaining: 0
      };

      // Import FreeThrowAnimationSystem
      const { FreeThrowAnimationSystem } = await import('../FreeThrowAnimationSystem.js');
      const ftSystem = new FreeThrowAnimationSystem(scene, ballController, scene.stateMachine, playerSprites, {});

      await ftSystem.handleFinalMadeFreeThrow(ftMakeTurnData);

      // Should not call runInboundSetup (BASELINE_INBOUND turn will handle it)
      expect(runInboundSetupCallCount).toBe(0);
    });

    test('Fast Break MAKE should skip runInboundSetup when next_play_type is BASELINE_INBOUND', async () => {
      // Import animateFastBreakShot
      const { animateFastBreakShot } = await import('../fastBreak.js');
      
      const fbMakeTurnData = {
        result_type: 'MAKE',
        current_turn: 'FAST_BREAK',
        next_play_type: 'BASELINE_INBOUND',
        next_defensive_setup: null,
        shooter_id: 'player1'
      };

      await animateFastBreakShot(scene, fbMakeTurnData, playerSprites, ballSprite, 800, 600);

      // Should not call runInboundSetup (BASELINE_INBOUND turn will handle it)
      expect(runInboundSetupCallCount).toBe(0);
    });
  });

  describe('Double Animation Prevention', () => {
    test('should not call runInboundSetup twice for the same BASELINE_INBOUND turn', async () => {
      const turnData = {
        result_type: 'BASELINE_INBOUND',
        current_turn: 'BASELINE_INBOUND',
        next_turn: 'HCO',
        offense_team_id: 'HOME_TEAM_ID',
        next_defensive_setup: null,
        oDestinations: {
          PG: { x: 50, y: 25 }
        },
        dDestinations: {
          PG: { x: 45, y: 25 }
        },
        ball_spot: { x: 50, y: 25 },
        animations: []
      };

      const context = {
        ballSprite: ballSprite,
        playerSprites: playerSprites
      };

      // Execute BASELINE_INBOUND turn
      await animationRouter.processTurn(turnData);

      // Verify runInboundSetup was called exactly once
      expect(runInboundSetupCallCount).toBe(1);
      expect(runInboundSetupCalls.length).toBe(1);
    });

    test('should track call stack to identify duplicate call sources', async () => {
      const turnData = {
        result_type: 'BASELINE_INBOUND',
        current_turn: 'BASELINE_INBOUND',
        next_turn: 'HCO',
        offense_team_id: 'HOME_TEAM_ID',
        next_defensive_setup: null,
        oDestinations: {
          PG: { x: 50, y: 25 }
        },
        dDestinations: {
          PG: { x: 45, y: 25 }
        },
        ball_spot: { x: 50, y: 25 },
        animations: []
      };

      const context = {
        ballSprite: ballSprite,
        playerSprites: playerSprites
      };

      await animationRouter.processTurn(turnData);

      // Verify all calls came from the same source (AnimationEngine.handleBaselineInbound)
      const callSources = runInboundSetupCalls.map(call => {
        const stack = call.stack || '';
        return stack.includes('handleBaselineInbound') || stack.includes('executeInboundSequence');
      });

      // All calls should come from the correct source
      expect(callSources.every(source => source === true)).toBe(true);
    });
  });

  describe('FCP/HCT Pressure Setup', () => {
    test('should handle FCP pressure setup in BASELINE_INBOUND turn', async () => {
      const turnData = {
        result_type: 'BASELINE_INBOUND',
        current_turn: 'BASELINE_INBOUND',
        next_turn: 'FCP',
        offense_team_id: 'HOME_TEAM_ID',
        next_defensive_setup: 'FCP',
        offense_setup_positions: {
          PG: { location: 'lower bird' },
          SF: { location: 'inbound_left' }
        },
        oDestinations: {
          PG: { x: 50, y: 25 }
        },
        dDestinations: {
          PG: { x: 45, y: 25 }
        },
        ball_spot: { x: 50, y: 25 },
        animations: []
      };

      const context = {
        ballSprite: ballSprite,
        playerSprites: playerSprites
      };

      await animationRouter.processTurn(turnData);

      // Verify FCP state was set
      expect(scene.currentPressureType).toBe('FCP');
      expect(scene.pressureSequenceActive).toBe(true);
      
      // Verify runInboundSetup was called exactly once
      expect(runInboundSetupCallCount).toBe(1);
    });

    test('should handle HCT pressure setup in BASELINE_INBOUND turn', async () => {
      const turnData = {
        result_type: 'BASELINE_INBOUND',
        current_turn: 'BASELINE_INBOUND',
        next_turn: 'HCT',
        offense_team_id: 'HOME_TEAM_ID',
        next_defensive_setup: 'HCT',
        offense_setup_positions: {
          PG: { location: 'lower bird' },
          SF: { location: 'inbound_left' }
        },
        oDestinations: {
          PG: { x: 50, y: 25 }
        },
        dDestinations: {
          PG: { x: 45, y: 25 }
        },
        ball_spot: { x: 50, y: 25 },
        animations: []
      };

      const context = {
        ballSprite: ballSprite,
        playerSprites: playerSprites
      };

      await animationRouter.processTurn(turnData);

      // Verify HCT state was set
      expect(scene.currentPressureType).toBe('HCT');
      expect(scene.pressureSequenceActive).toBe(true);
      
      // Verify runInboundSetup was called exactly once
      expect(runInboundSetupCallCount).toBe(1);
    });
  });
});

