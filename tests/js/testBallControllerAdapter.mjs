/**
 * BallController Adapter Test
 * 
 * Tests the backward compatibility layer between old and new ball systems
 */

import adapter from '../../FrontEnd/static/js/phaser/animation/BallControllerAdapter.js';

const {
  initializeBallController, 
  attachBallToPlayer, 
  detachBall,
  getCurrentOwner
} = adapter;

function createMockScene() {
  return {
    events: {
      on: () => {},
      off: () => {}
    },
    currentBallOwnerRef: { value: null },
    ballDetached: false,
    possessionFlipInProgress: false,
    offenseTeamId: 'home',
    playerSprites: {},
    stateMachine: {
      is: () => false
    }
  };
}

function createMockBallSprite() {
  return {
    x: 0,
    y: 0,
    setPosition: () => {},
    setVisible: () => {},
    setDepth: () => {},
    visible: true
  };
}

function createMockPlayerSprite() {
  return {
    playerId: 'player1',
    team_id: 'home',
    team: 'home',
    x: 100,
    y: 200
  };
}

async function testAdapter() {
  console.log('🧪 Testing BallController Adapter...');
  
  // Create mocks
  const scene = createMockScene();
  const ballSprite = createMockBallSprite();
  const playerSprite = createMockPlayerSprite();
  
  scene.playerSprites['player1'] = playerSprite;
  
  try {
    // Test 1: Initialize BallController
    console.log('  ✓ Test 1: Initialize BallController');
    const controller = initializeBallController(scene, ballSprite);
    if (!controller) {
      throw new Error('Failed to initialize BallController');
    }
    
    // Test 2: Attach ball to player
    console.log('  ✓ Test 2: Attach ball to player');
    attachBallToPlayer(scene, ballSprite, playerSprite, { depth: 50 });
    
    if (scene.currentBallOwnerRef.value !== playerSprite) {
      throw new Error('Ball not attached to player');
    }
    
    if (scene.ballDetached !== false) {
      throw new Error('Ball should not be detached');
    }
    
    // Test 3: Get current owner
    console.log('  ✓ Test 3: Get current owner');
    const owner = getCurrentOwner(scene);
    if (owner !== playerSprite) {
      throw new Error('Current owner mismatch');
    }
    
    // Test 4: Detach ball
    console.log('  ✓ Test 4: Detach ball');
    detachBall(scene, ballSprite);
    
    if (scene.ballDetached !== true) {
      throw new Error('Ball should be detached');
    }
    
    // Test 5: Possession flip restriction
    console.log('  ✓ Test 5: Possession flip restriction');
    scene.possessionFlipInProgress = true;
    scene.offenseTeamId = 'away';
    playerSprite.team_id = 'home';
    
    attachBallToPlayer(scene, ballSprite, playerSprite);
    
    if (scene.currentBallOwnerRef.value !== null) {
      throw new Error('Ball should not attach during possession flip');
    }
    
    // Test 6: Rebound state restriction
    console.log('  ✓ Test 6: Rebound state restriction');
    scene.possessionFlipInProgress = false;
    scene.stateMachine.is = () => true; // Simulate rebound state
    scene.rebounderId = 'player2';
    
    attachBallToPlayer(scene, ballSprite, playerSprite);
    
    if (scene.currentBallOwnerRef.value !== null) {
      throw new Error('Ball should not attach to non-rebounder during rebound state');
    }
    
    console.log('✅ All tests passed! BallController Adapter is working correctly.');
    
  } catch (error) {
    console.error('❌ Test failed:', error.message);
    process.exit(1);
  }
}

// Run the test
await testAdapter();
