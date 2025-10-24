/**
 * Quick Structure Validation Script
 * 
 * Run this to check for common structural issues before testing.
 * Usage: Import and call validateInboundPassStructure()
 */

import { AnimationEngine } from './AnimationEngine.js';
import PassAnimationSystem from './PassAnimationSystem.js';

export function validateInboundPassStructure() {
  const issues = [];
  
  try {
    // Check if required classes exist
    if (typeof PassAnimationSystem === 'undefined') {
      issues.push('PassAnimationSystem class not found');
    }
    
    if (typeof AnimationEngine === 'undefined') {
      issues.push('AnimationEngine class not found');
    }
    
    // Check if required methods exist
    if (typeof PassAnimationSystem !== 'undefined') {
      const passSystem = new PassAnimationSystem({}, {}, {}, {});
      
      if (typeof passSystem.processPass !== 'function') {
        issues.push('PassAnimationSystem.processPass method missing');
      }
      
      if (typeof passSystem.validatePassData !== 'function') {
        issues.push('PassAnimationSystem.validatePassData method missing');
      }
      
      if (typeof passSystem.executeInboundSequence !== 'function') {
        issues.push('PassAnimationSystem.executeInboundSequence method missing');
      }
    }
    
    // Check if required handlers are registered
    if (typeof AnimationEngine !== 'undefined') {
      const animationEngine = new AnimationEngine({});
      
      if (!animationEngine.animationHandlers.has('BASELINE_INBOUND')) {
        issues.push('BASELINE_INBOUND handler not registered in AnimationEngine');
      }
      
      if (!animationEngine.animationHandlers.has('SIDE_INBOUND')) {
        issues.push('SIDE_INBOUND handler not registered in AnimationEngine');
      }
    }
    
    // Test data validation
    if (typeof PassAnimationSystem !== 'undefined') {
      const passSystem = new PassAnimationSystem({}, {}, {}, {});
      
      const validData = {
        result_type: 'BASELINE_INBOUND',
        oDestinations: { PG: { x: 50, y: 25 } },
        dDestinations: { PG: { x: 45, y: 25 } },
        ball_spot: { x: 50, y: 25 },
        possession_team_id: 'HOME_TEAM_ID'
      };
      
      if (!passSystem.validatePassData(validData)) {
        issues.push('Valid BASELINE_INBOUND data validation failed');
      }
      
      const invalidData = {
        result_type: 'BASELINE_INBOUND'
        // Missing required fields
      };
      
      if (passSystem.validatePassData(invalidData)) {
        issues.push('Invalid BASELINE_INBOUND data validation passed (should fail)');
      }
    }
    
  } catch (error) {
    issues.push(`Validation error: ${error.message}`);
  }
  
  return {
    isValid: issues.length === 0,
    issues: issues
  };
}

// Console logging version for browser use
export function logValidationResults() {
  const result = validateInboundPassStructure();
  
  if (result.isValid) {
    console.log('✅ Inbound pass structure validation passed!');
  } else {
    console.log('❌ Inbound pass structure validation failed:');
    result.issues.forEach(issue => {
      console.log(`   - ${issue}`);
    });
  }
  
  return result;
}
