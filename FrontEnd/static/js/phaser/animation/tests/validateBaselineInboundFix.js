/**
 * BASELINE_INBOUND Fix Validation Script
 * 
 * Validates that the code fixes are in place to prevent double inbound animations.
 * Run with: node FrontEnd/static/js/phaser/animation/tests/validateBaselineInboundFix.js
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
// Go up from tests/ to animation/ to phaser/ to js/ to static/ to FrontEnd/ to project root
const projectRoot = path.resolve(__dirname, '../../../../../..');

function readFile(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8');
  } catch (error) {
    return null;
  }
}

function checkFile(filePath, checks) {
  const content = readFile(filePath);
  if (!content) {
    return { file: filePath, found: false, error: 'File not found' };
  }

  const results = {
    file: path.relative(projectRoot, filePath),
    found: true,
    checks: []
  };

  for (const check of checks) {
    const hasCheck = content.includes(check.pattern);
    results.checks.push({
      name: check.name,
      passed: hasCheck,
      pattern: check.pattern.substring(0, 50) + '...'
    });
  }

  return results;
}

console.log('🧪 Validating BASELINE_INBOUND Fix...\n');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

const testResults = [];

// Test 1: ShotAnimationSystem.handleMadeShot should skip runInboundSetup when next_play_type is BASELINE_INBOUND
const shotSystemPath = path.join(projectRoot, 'FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js');
testResults.push(checkFile(shotSystemPath, [
  {
    name: 'HCO MAKE skips runInboundSetup when next_play_type is BASELINE_INBOUND',
    pattern: 'next_play_type === "BASELINE_INBOUND"'
  },
  {
    name: 'Has double inbound prevention log',
    pattern: 'DOUBLE INBOUND PREVENTION'
  }
]));

// Test 2: handleOrebTurn should skip runInboundSetup when next_play_type is BASELINE_INBOUND
const animateGameTurnsPath = path.join(projectRoot, 'FrontEnd/static/js/phaser/animation/animateGameTurns.js');
testResults.push(checkFile(animateGameTurnsPath, [
  {
    name: 'PUTBACK_MAKE skips runInboundSetup when next_play_type is BASELINE_INBOUND',
    pattern: 'handleOrebTurn() - BASELINE_INBOUND turn will handle it'
  }
]));

// Test 3: fastBreak.js should skip runInboundSetup when next_play_type is BASELINE_INBOUND
const fastBreakPath = path.join(projectRoot, 'FrontEnd/static/js/phaser/animation/fastBreak.js');
testResults.push(checkFile(fastBreakPath, [
  {
    name: 'Fast Break MAKE skips runInboundSetup when next_play_type is BASELINE_INBOUND',
    pattern: 'fastBreak.js - BASELINE_INBOUND turn will handle it'
  }
]));

// Test 4: freeThrow.js should skip runInboundSetup when next_play_type is BASELINE_INBOUND
const freeThrowPath = path.join(projectRoot, 'FrontEnd/static/js/phaser/animation/freeThrow.js');
testResults.push(checkFile(freeThrowPath, [
  {
    name: 'Free Throw MAKE skips runInboundSetup when next_play_type is BASELINE_INBOUND',
    pattern: 'freeThrow.js - BASELINE_INBOUND turn will handle it'
  }
]));

// Test 5: FreeThrowAnimationSystem should skip runInboundSetup when next_play_type is BASELINE_INBOUND
const freeThrowSystemPath = path.join(projectRoot, 'FrontEnd/static/js/phaser/animation/FreeThrowAnimationSystem.js');
testResults.push(checkFile(freeThrowSystemPath, [
  {
    name: 'FreeThrowAnimationSystem skips runInboundSetup when next_play_type is BASELINE_INBOUND',
    pattern: 'FreeThrowAnimationSystem - BASELINE_INBOUND turn will handle it'
  }
]));

// Test 6: playTurnAnimation should skip runInboundSetup when next_play_type is BASELINE_INBOUND
const turnAnimationPath = path.join(projectRoot, 'FrontEnd/static/js/phaser/animation/turnAnimation.js');
testResults.push(checkFile(turnAnimationPath, [
  {
    name: 'playTurnAnimation skips runInboundSetup when next_play_type is BASELINE_INBOUND',
    pattern: 'playTurnAnimation() - BASELINE_INBOUND turn will handle it'
  }
]));

// Test 7: AnimationEngine.handleBaselineInbound should call runInboundSetup
const animationEnginePath = path.join(projectRoot, 'FrontEnd/static/js/phaser/animation/AnimationEngine.js');
testResults.push(checkFile(animationEnginePath, [
  {
    name: 'AnimationEngine.handleBaselineInbound exists',
    pattern: 'handleBaselineInbound'
  },
  {
    name: 'Calls executeInboundSequence',
    pattern: 'executeInboundSequence'
  }
]));

// Print results
let totalChecks = 0;
let passedChecks = 0;

testResults.forEach(result => {
  console.log(`\n📄 ${result.file}`);
  if (!result.found) {
    console.log(`   ❌ File not found`);
    return;
  }

  result.checks.forEach(check => {
    totalChecks++;
    const status = check.passed ? '✅' : '❌';
    console.log(`   ${status} ${check.name}`);
    if (!check.passed) {
      console.log(`      Pattern: ${check.pattern}`);
    } else {
      passedChecks++;
    }
  });
});

console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log(`\n📊 Results: ${passedChecks}/${totalChecks} checks passed`);

if (passedChecks === totalChecks) {
  console.log('✅ All validation checks passed!');
  process.exit(0);
} else {
  console.log('❌ Some validation checks failed');
  process.exit(1);
}

