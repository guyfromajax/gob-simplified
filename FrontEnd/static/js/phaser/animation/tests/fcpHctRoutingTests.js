/**
 * FCP/HCT Routing Tests
 * 
 * Tests all possible FCP/HCT outcomes to verify correct routing:
 * 1. HCO (break press/trap, establish HCO)
 * 2. SHOT (break press/trap, attempt shot) - MAKE
 * 3. SHOT (break press/trap, attempt shot) - MISS
 * 4. D_FOUL (defensive foul)
 * 5. O_FOUL (offensive foul)
 * 6. STEAL
 * 7. DEAD_BALL_TURNOVER
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
  
  // Import the detection logic (we'll need to extract it or test it directly)
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
  
  testCases.forEach(testCase => {
    const isFCPHCT = testCase.turn.fcp_shot === true || testCase.turn.hct_shot === true || 
                     testCase.turn.next_defensive_setup === "FCP" || testCase.turn.next_defensive_setup === "HCT" ||
                     testCase.turn.fcp_foul === true || testCase.turn.hct_foul === true;
    
    const isFCPHCTShotAttempt = (testCase.turn.result_type === "MAKE" || testCase.turn.result_type === "MISS") &&
                                 (testCase.turn.fcp_shot === true || testCase.turn.hct_shot === true || 
                                  testCase.turn.next_defensive_setup === "FCP" || testCase.turn.next_defensive_setup === "HCT");
    
    const passed = (isFCPHCT === testCase.expected) || 
                   (testCase.expected && isFCPHCTShotAttempt && (testCase.turn.result_type === "MAKE" || testCase.turn.result_type === "MISS"));
    
    console.log(`${passed ? '✅' : '❌'} ${testCase.name}`);
    console.log(`   isFCPHCT: ${isFCPHCT}, isFCPHCTShotAttempt: ${isFCPHCTShotAttempt}`);
    console.log(`   Flags: fcp_shot=${testCase.turn.fcp_shot}, hct_shot=${testCase.turn.hct_shot}, next_defensive_setup=${testCase.turn.next_defensive_setup}`);
    console.log(`   Result: ${testCase.turn.result_type}`);
    if (!passed) {
      console.log(`   ⚠️  EXPECTED: ${testCase.expected ? 'detected' : 'not detected'}, GOT: ${isFCPHCT ? 'detected' : 'not detected'}`);
    }
    console.log('');
  });
}

/**
 * Test AnimationEngine routing
 */
async function testAnimationEngineRouting() {
  console.log('🧪 Testing AnimationEngine Routing');
  console.log('=====================================\n');
  
  // We'll need to mock the AnimationEngine or import it
  // For now, let's test the determineHandler logic conceptually
  
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
    
    const passed = handler === testCase.expectedHandler;
    
    console.log(`${passed ? '✅' : '❌'} ${testCase.name}`);
    console.log(`   Expected: ${testCase.expectedHandler}, Got: ${handler}`);
    console.log(`   Result Type: ${testCase.turn.result_type}`);
    if (!passed) {
      console.log(`   ⚠️  MISROUTED!`);
    }
    console.log('');
  });
}

/**
 * Run all tests
 */
export function runFCPHCTTests() {
  console.log('🚀 Running FCP/HCT Routing Tests');
  console.log('=====================================\n');
  
  testFCPHCTDetection();
  console.log('\n');
  testAnimationEngineRouting();
  
  console.log('✅ Tests Complete');
}

/**
 * Test actual turn data from the game
 * Call this from browser console during a game to test real FCP/HCT turns
 */
export function testRealTurnData(turnData, turnIndex = null) {
  console.log('🧪 Testing Real Turn Data');
  console.log('=====================================\n');
  console.log('Turn Data:', turnData);
  console.log('Turn Index:', turnIndex);
  console.log('');
  
  // Test detection logic
  const isFCPHCT = turnData.fcp_shot === true || turnData.hct_shot === true || 
                   turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT" ||
                   turnData.fcp_foul === true || turnData.hct_foul === true;
  
  const isFCPHCTShotAttempt = (turnData.result_type === "MAKE" || turnData.result_type === "MISS") &&
                               (turnData.fcp_shot === true || turnData.hct_shot === true || 
                                turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT");
  
  console.log('Detection Results:');
  console.log(`  isFCPHCT: ${isFCPHCT}`);
  console.log(`  isFCPHCTShotAttempt: ${isFCPHCTShotAttempt}`);
  console.log('');
  
  console.log('Flags:');
  console.log(`  fcp_shot: ${turnData.fcp_shot}`);
  console.log(`  hct_shot: ${turnData.hct_shot}`);
  console.log(`  fcp_foul: ${turnData.fcp_foul}`);
  console.log(`  hct_foul: ${turnData.hct_foul}`);
  console.log(`  next_defensive_setup: ${turnData.next_defensive_setup}`);
  console.log('');
  
  console.log('Result Type:', turnData.result_type);
  console.log('');
  
  // Test routing
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
  
  let expectedHandler = null;
  if (turnData.result_type && nonShotResultTypes.has(turnData.result_type)) {
    expectedHandler = 'DEFAULT';
  } else if (!nonShotResultTypes.has(turnData.result_type) && isShotAttempt(turnData)) {
    expectedHandler = 'SHOT_ATTEMPT';
  } else {
    expectedHandler = 'DEFAULT';
  }
  
  console.log('Expected Routing:');
  console.log(`  Handler: ${expectedHandler}`);
  console.log(`  Should be FCP/HCT: ${isFCPHCT}`);
  console.log(`  Should route to ShotSystem: ${isFCPHCTShotAttempt}`);
  console.log('');
  
  if (isFCPHCT && !isFCPHCTShotAttempt) {
    console.log('✅ Will route to playTurnAnimation (setup turn)');
  } else if (isFCPHCTShotAttempt) {
    console.log('✅ Will route to ShotAnimationSystem (shot attempt)');
  } else {
    console.log('⚠️  NOT DETECTED AS FCP/HCT - will route as regular turn');
  }
}

// Auto-run if in browser console
if (typeof window !== 'undefined') {
  window.runFCPHCTTests = runFCPHCTTests;
  window.testRealTurnData = testRealTurnData;
  console.log('💡 Run tests with:');
  console.log('   - runFCPHCTTests() - Run all test cases');
  console.log('   - testRealTurnData(turnData, turnIndex) - Test actual turn from game');
}

