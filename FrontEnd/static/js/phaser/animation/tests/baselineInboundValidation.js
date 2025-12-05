/**
 * BASELINE_INBOUND Validation Script
 * 
 * Validates that BASELINE_INBOUND animations execute properly and only once.
 * Run this in the browser console during a game to validate the fix.
 */

export function validateBaselineInboundAnimations() {
  console.log('🧪 Starting BASELINE_INBOUND Animation Validation...');
  
  let runInboundSetupCallCount = 0;
  let runInboundSetupCalls = [];
  let baselineInboundTurns = [];
  let madeShotTurns = [];

  // Track runInboundSetup calls
  const originalLog = console.log;
  console.log = function(...args) {
    const message = args[0];
    if (typeof message === 'string' && message.includes('[RUN INBOUND SETUP]')) {
      runInboundSetupCallCount++;
      runInboundSetupCalls.push({
        timestamp: Date.now(),
        args: args[1] || {},
        stack: new Error().stack
      });
      console.log(`📍 [VALIDATION] runInboundSetup call #${runInboundSetupCallCount}`, args[1]);
    }
    originalLog.apply(console, args);
  };

  // Track BASELINE_INBOUND turns
  const trackBaselineInbound = (turnData) => {
    if (turnData.result_type === 'BASELINE_INBOUND') {
      baselineInboundTurns.push({
        timestamp: Date.now(),
        turnData: { ...turnData }
      });
      console.log('📍 [VALIDATION] BASELINE_INBOUND turn detected', turnData);
    }
  };

  // Track made shots
  const trackMadeShot = (turnData) => {
    if (turnData.result_type === 'MAKE' || turnData.result_type === 'PUTBACK_MAKE') {
      if (turnData.next_play_type === 'BASELINE_INBOUND') {
        madeShotTurns.push({
          timestamp: Date.now(),
          turnData: { ...turnData },
          shouldSkipInbound: true
        });
        console.log('📍 [VALIDATION] Made shot with BASELINE_INBOUND next', turnData);
      }
    }
  };

  // Validation function
  const validateResults = () => {
    console.log('\n📊 Validation Results:');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    
    // Check 1: Each BASELINE_INBOUND turn should call runInboundSetup exactly once
    console.log(`\n1. BASELINE_INBOUND Turns: ${baselineInboundTurns.length}`);
    console.log(`   runInboundSetup Calls: ${runInboundSetupCallCount}`);
    
    if (baselineInboundTurns.length > 0) {
      const expectedCalls = baselineInboundTurns.length;
      if (runInboundSetupCallCount === expectedCalls) {
        console.log(`   ✅ PASS: Each BASELINE_INBOUND turn called runInboundSetup exactly once`);
      } else {
        console.log(`   ❌ FAIL: Expected ${expectedCalls} calls, got ${runInboundSetupCallCount}`);
        console.log(`   ⚠️  This indicates double animation bug!`);
      }
    }

    // Check 2: Made shots should NOT call runInboundSetup when next_play_type is BASELINE_INBOUND
    console.log(`\n2. Made Shots with BASELINE_INBOUND next: ${madeShotTurns.length}`);
    if (madeShotTurns.length > 0) {
      const madeShotCallCount = runInboundSetupCalls.filter(call => {
        // Check if call came from a made shot handler (not from BASELINE_INBOUND turn)
        const stack = call.stack || '';
        return !stack.includes('handleBaselineInbound') && 
               !stack.includes('executeInboundSequence');
      }).length;
      
      if (madeShotCallCount === 0) {
        console.log(`   ✅ PASS: Made shots correctly skipped runInboundSetup`);
      } else {
        console.log(`   ❌ FAIL: Made shots called runInboundSetup ${madeShotCallCount} times`);
        console.log(`   ⚠️  This indicates double animation bug!`);
      }
    }

    // Check 3: No duplicate calls for same turn
    console.log(`\n3. Duplicate Call Detection:`);
    const callTimestamps = runInboundSetupCalls.map(c => c.timestamp);
    const duplicates = callTimestamps.filter((ts, i) => callTimestamps.indexOf(ts) !== i);
    if (duplicates.length === 0) {
      console.log(`   ✅ PASS: No duplicate calls detected`);
    } else {
      console.log(`   ❌ FAIL: Found ${duplicates.length} duplicate calls`);
      console.log(`   ⚠️  This indicates double animation bug!`);
    }

    console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
  };

  // Return validation functions
  return {
    trackBaselineInbound,
    trackMadeShot,
    validateResults,
    getStats: () => ({
      runInboundSetupCallCount,
      baselineInboundTurns: baselineInboundTurns.length,
      madeShotTurns: madeShotTurns.length
    })
  };
}

// Export for use in browser console
if (typeof window !== 'undefined') {
  window.validateBaselineInboundAnimations = validateBaselineInboundAnimations;
}

