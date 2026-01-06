/**
 * Node.js test runner for FCP/HCT routing tests
 * Run with: node FrontEnd/js/phaser/animation/tests/runTests.js
 */

// Mock turn data for each FCP/HCT outcome
const mockTurns = {
  // HCT → HCO (break trap, establish HCO)
  hct_hco: {
    result_type: "HCO",
    next_defensive_setup: "HCT",
    animations: [{ playerId: "test", movement: [{ coords: { x: 50, y: 25 }, action: "stand" }] }]
  },
  
  // HCT → SHOT (MAKE) - break trap, attempt shot, make
  hct_shot_make: {
    result_type: "MAKE",
    hct_shot: true,
    shooter_id: "test_shooter",
    animations: [{ playerId: "test", movement: [{ coords: { x: 50, y: 25 }, action: "stand" }] }]
  },
  
  // HCT → SHOT (MISS) - break trap, attempt shot, miss
  hct_shot_miss: {
    result_type: "MISS",
    hct_shot: true,
    shooter_id: "test_shooter",
    animations: [{ playerId: "test", movement: [{ coords: { x: 50, y: 25 }, action: "stand" }] }]
  },
  
  // HCT → SHOT (MAKE) with next_defensive_setup instead of hct_shot
  hct_shot_make_next_setup: {
    result_type: "MAKE",
    next_defensive_setup: "HCT",
    shooter_id: "test_shooter",
    animations: [{ playerId: "test", movement: [{ coords: { x: 50, y: 25 }, action: "stand" }] }]
  },
  
  // HCT → D_FOUL (defensive foul)
  hct_d_foul: {
    result_type: "FOUL",
    hct_foul: true,
    animations: [{ playerId: "test", movement: [{ coords: { x: 50, y: 25 }, action: "stand" }] }]
  },
  
  // HCT → O_FOUL (offensive foul)
  hct_o_foul: {
    result_type: "FOUL",
    hct_foul: true,
    foul_team: "OFFENSE",
    animations: [{ playerId: "test", movement: [{ coords: { x: 50, y: 25 }, action: "stand" }] }]
  },
  
  // HCT → STEAL
  hct_steal: {
    result_type: "STEAL",
    next_defensive_setup: "HCT",
    animations: [{ playerId: "test", movement: [{ coords: { x: 50, y: 25 }, action: "stand" }] }]
  },
  
  // HCT → DEAD_BALL_TURNOVER
  hct_dead_ball: {
    result_type: "DEAD_BALL_TURNOVER",
    next_defensive_setup: "HCT",
    animations: [{ playerId: "test", movement: [{ coords: { x: 50, y: 25 }, action: "stand" }] }]
  },
  
  // FCP → HCO
  fcp_hco: {
    result_type: "HCO",
    next_defensive_setup: "FCP",
    animations: [{ playerId: "test", movement: [{ coords: { x: 50, y: 25 }, action: "stand" }] }]
  },
  
  // FCP → SHOT (MAKE)
  fcp_shot_make: {
    result_type: "MAKE",
    fcp_shot: true,
    shooter_id: "test_shooter",
    animations: [{ playerId: "test", movement: [{ coords: { x: 50, y: 25 }, action: "stand" }] }]
  },
  
  // FCP → SHOT (MISS)
  fcp_shot_miss: {
    result_type: "MISS",
    fcp_shot: true,
    shooter_id: "test_shooter",
    animations: [{ playerId: "test", movement: [{ coords: { x: 50, y: 25 }, action: "stand" }] }]
  },
  
  // FCP → D_FOUL
  fcp_d_foul: {
    result_type: "FOUL",
    fcp_foul: true,
    animations: [{ playerId: "test", movement: [{ coords: { x: 50, y: 25 }, action: "stand" }] }]
  },
  
  // FCP → STEAL
  fcp_steal: {
    result_type: "STEAL",
    next_defensive_setup: "FCP",
    animations: [{ playerId: "test", movement: [{ coords: { x: 50, y: 25 }, action: "stand" }] }]
  },
  
  // Edge case: HCT shot attempt without flags (after BASELINE_INBOUND)
  hct_shot_make_no_flags: {
    result_type: "MAKE",
    shooter_id: "test_shooter",
    animations: [{ playerId: "test", movement: [{ coords: { x: 50, y: 25 }, action: "stand" }] }]
    // Missing: hct_shot, next_defensive_setup
  }
};

/**
 * Test FCP/HCT detection logic
 */
function testFCPHCTDetection() {
  console.log('🧪 Testing FCP/HCT Detection Logic');
  console.log('=====================================\n');
  
  const testCases = [
    { name: 'HCT → HCO', turn: mockTurns.hct_hco, expected: true },
    { name: 'HCT → SHOT (MAKE) with hct_shot', turn: mockTurns.hct_shot_make, expected: true },
    { name: 'HCT → SHOT (MISS) with hct_shot', turn: mockTurns.hct_shot_miss, expected: true },
    { name: 'HCT → SHOT (MAKE) with next_defensive_setup', turn: mockTurns.hct_shot_make_next_setup, expected: true },
    { name: 'HCT → D_FOUL', turn: mockTurns.hct_d_foul, expected: true },
    { name: 'HCT → O_FOUL', turn: mockTurns.hct_o_foul, expected: true },
    { name: 'HCT → STEAL', turn: mockTurns.hct_steal, expected: true },
    { name: 'HCT → DEAD_BALL_TURNOVER', turn: mockTurns.hct_dead_ball, expected: true },
    { name: 'FCP → HCO', turn: mockTurns.fcp_hco, expected: true },
    { name: 'FCP → SHOT (MAKE)', turn: mockTurns.fcp_shot_make, expected: true },
    { name: 'FCP → SHOT (MISS)', turn: mockTurns.fcp_shot_miss, expected: true },
    { name: 'FCP → D_FOUL', turn: mockTurns.fcp_d_foul, expected: true },
    { name: 'FCP → STEAL', turn: mockTurns.fcp_steal, expected: true },
    { name: 'HCT → SHOT (MAKE) NO FLAGS (edge case)', turn: mockTurns.hct_shot_make_no_flags, expected: false }
  ];
  
  let passed = 0;
  let failed = 0;
  
  testCases.forEach(testCase => {
    const isFCPHCT = testCase.turn.fcp_shot === true || testCase.turn.hct_shot === true || 
                     testCase.turn.next_defensive_setup === "FCP" || testCase.turn.next_defensive_setup === "HCT" ||
                     testCase.turn.fcp_foul === true || testCase.turn.hct_foul === true;
    
    const isFCPHCTShotAttempt = (testCase.turn.result_type === "MAKE" || testCase.turn.result_type === "MISS") &&
                                 (testCase.turn.fcp_shot === true || testCase.turn.hct_shot === true || 
                                  testCase.turn.next_defensive_setup === "FCP" || testCase.turn.next_defensive_setup === "HCT");
    
    const testPassed = (isFCPHCT === testCase.expected) || 
                       (testCase.expected && isFCPHCTShotAttempt && (testCase.turn.result_type === "MAKE" || testCase.turn.result_type === "MISS"));
    
    if (testPassed) {
      passed++;
    } else {
      failed++;
    }
    
    const status = testPassed ? '✅' : '❌';
    console.log(`${status} ${testCase.name}`);
    console.log(`   isFCPHCT: ${isFCPHCT}, isFCPHCTShotAttempt: ${isFCPHCTShotAttempt}`);
    console.log(`   Flags: fcp_shot=${testCase.turn.fcp_shot}, hct_shot=${testCase.turn.hct_shot}, next_defensive_setup=${testCase.turn.next_defensive_setup}`);
    console.log(`   Result: ${testCase.turn.result_type}`);
    if (!testPassed) {
      console.log(`   ⚠️  EXPECTED: ${testCase.expected ? 'detected' : 'not detected'}, GOT: ${isFCPHCT ? 'detected' : 'not detected'}`);
    }
    console.log('');
  });
  
  console.log(`\n📊 Detection Tests: ${passed} passed, ${failed} failed\n`);
  return { passed, failed };
}

/**
 * Test AnimationEngine routing
 */
function testAnimationEngineRouting() {
  console.log('🧪 Testing AnimationEngine Routing');
  console.log('=====================================\n');
  
  const testCases = [
    { name: 'HCT → HCO', turn: mockTurns.hct_hco, expectedHandler: 'DEFAULT' },
    { name: 'HCT → SHOT (MAKE) with hct_shot', turn: mockTurns.hct_shot_make, expectedHandler: 'SHOT_ATTEMPT' },
    { name: 'HCT → SHOT (MISS) with hct_shot', turn: mockTurns.hct_shot_miss, expectedHandler: 'SHOT_ATTEMPT' },
    { name: 'HCT → SHOT (MAKE) with next_defensive_setup', turn: mockTurns.hct_shot_make_next_setup, expectedHandler: 'SHOT_ATTEMPT' },
    { name: 'HCT → D_FOUL', turn: mockTurns.hct_d_foul, expectedHandler: 'DEFAULT' },
    { name: 'HCT → O_FOUL', turn: mockTurns.hct_o_foul, expectedHandler: 'DEFAULT' },
    { name: 'HCT → STEAL', turn: mockTurns.hct_steal, expectedHandler: 'DEFAULT' },
    { name: 'HCT → DEAD_BALL_TURNOVER', turn: mockTurns.hct_dead_ball, expectedHandler: 'DEFAULT' },
    { name: 'FCP → HCO', turn: mockTurns.fcp_hco, expectedHandler: 'DEFAULT' },
    { name: 'FCP → SHOT (MAKE)', turn: mockTurns.fcp_shot_make, expectedHandler: 'SHOT_ATTEMPT' },
    { name: 'FCP → SHOT (MISS)', turn: mockTurns.fcp_shot_miss, expectedHandler: 'SHOT_ATTEMPT' },
    { name: 'FCP → D_FOUL', turn: mockTurns.fcp_d_foul, expectedHandler: 'DEFAULT' },
    { name: 'FCP → STEAL', turn: mockTurns.fcp_steal, expectedHandler: 'DEFAULT' },
    { name: 'HCT → SHOT (MAKE) NO FLAGS (edge case)', turn: mockTurns.hct_shot_make_no_flags, expectedHandler: 'SHOT_ATTEMPT' }
  ];
  
  const nonShotResultTypes = new Set([
    "FOUL", "FREE_THROW", "TURNOVER", "DEAD_BALL", "DEAD_BALL_TURNOVER",
    "SIDE_INBOUND", "BASELINE_INBOUND", "PUTBACK_MAKE", 
    "PUTBACK_MISS", "OREB_KICKOUT", "DEFENSIVE_STOP", "OPENING_TIP",
    "HCO", "STEAL"
  ]);
  
  function isShotAttempt(turnData) {
    return turnData.result_type === "MAKE" || 
           turnData.result_type === "MISS" ||
           turnData.shooter ||
           turnData.shooter_id ||
           turnData.shot_score !== undefined;
  }
  
  let passed = 0;
  let failed = 0;
  
  testCases.forEach(testCase => {
    let handler = null;
    
    // Simulate determineHandler logic
    if (testCase.turn.result_type && nonShotResultTypes.has(testCase.turn.result_type)) {
      handler = 'DEFAULT';
    } else if (!nonShotResultTypes.has(testCase.turn.result_type) && isShotAttempt(testCase.turn)) {
      handler = 'SHOT_ATTEMPT';
    } else {
      handler = 'DEFAULT';
    }
    
    const testPassed = handler === testCase.expectedHandler;
    
    if (testPassed) {
      passed++;
    } else {
      failed++;
    }
    
    const status = testPassed ? '✅' : '❌';
    console.log(`${status} ${testCase.name}`);
    console.log(`   Expected: ${testCase.expectedHandler}, Got: ${handler}`);
    console.log(`   Result Type: ${testCase.turn.result_type}`);
    if (!testPassed) {
      console.log(`   ⚠️  MISROUTED!`);
    }
    console.log('');
  });
  
  console.log(`\n📊 Routing Tests: ${passed} passed, ${failed} failed\n`);
  return { passed, failed };
}

/**
 * Run all tests
 */
function runFCPHCTTests() {
  console.log('🚀 Running FCP/HCT Routing Tests');
  console.log('=====================================\n');
  
  const detectionResults = testFCPHCTDetection();
  console.log('\n');
  const routingResults = testAnimationEngineRouting();
  
  console.log('=====================================');
  console.log('📊 Final Results:');
  console.log(`   Detection: ${detectionResults.passed} passed, ${detectionResults.failed} failed`);
  console.log(`   Routing: ${routingResults.passed} passed, ${routingResults.failed} failed`);
  console.log(`   Total: ${detectionResults.passed + routingResults.passed} passed, ${detectionResults.failed + routingResults.failed} failed`);
  console.log('=====================================\n');
  
  if (detectionResults.failed === 0 && routingResults.failed === 0) {
    console.log('✅ All tests passed!');
  } else {
    console.log('❌ Some tests failed. Review the output above.');
  }
}

// Run tests
runFCPHCTTests();
