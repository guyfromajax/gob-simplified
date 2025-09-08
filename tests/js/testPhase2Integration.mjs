/**
 * Phase 2 Integration Test
 * 
 * Quick test to verify the BallControllerAdapter is working correctly
 * with the updated critical systems.
 */

import adapter from '../../FrontEnd/static/js/phaser/animation/BallControllerAdapter.js';

async function testPhase2Integration() {
  console.log('🧪 Testing Phase 2 Integration...');
  
  try {
    // Test 1: Verify adapter functions exist
    console.log('  ✓ Test 1: Verify adapter functions exist');
    const requiredFunctions = [
      'initializeBallController',
      'attachBallToPlayer', 
      'detachBall',
      'getCurrentOwner',
      'getBallController'
    ];
    
    for (const funcName of requiredFunctions) {
      if (typeof adapter[funcName] !== 'function') {
        throw new Error(`Missing function: ${funcName}`);
      }
    }
    
    // Test 2: Verify adapter can be initialized
    console.log('  ✓ Test 2: Verify adapter can be initialized');
    const mockScene = {
      events: { on: () => {}, off: () => {} },
      currentBallOwnerRef: { value: null },
      ballDetached: false
    };
    const mockBallSprite = { x: 0, y: 0, setPosition: () => {}, setVisible: () => {} };
    
    const controller = adapter.initializeBallController(mockScene, mockBallSprite);
    if (!controller) {
      throw new Error('Failed to initialize BallController');
    }
    
    // Test 3: Verify adapter functions work
    console.log('  ✓ Test 3: Verify adapter functions work');
    const mockPlayerSprite = { playerId: 'test', team_id: 'home', x: 100, y: 200 };
    
    adapter.attachBallToPlayer(mockScene, mockBallSprite, mockPlayerSprite);
    if (mockScene.currentBallOwnerRef.value !== mockPlayerSprite) {
      throw new Error('Ball not attached correctly');
    }
    
    adapter.detachBall(mockScene, mockBallSprite);
    if (mockScene.ballDetached !== true) {
      throw new Error('Ball not detached correctly');
    }
    
    console.log('✅ Phase 2 Integration Test Passed!');
    console.log('🎯 Ready for manual testing in the prototype.');
    
  } catch (error) {
    console.error('❌ Phase 2 Integration Test Failed:', error.message);
    process.exit(1);
  }
}

// Run the test
await testPhase2Integration();
