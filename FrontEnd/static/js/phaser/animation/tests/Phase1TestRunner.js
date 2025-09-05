/**
 * Phase 1 Test Runner
 * 
 * Executes all Phase 1 component tests and provides comprehensive reporting
 * for the new animation system components.
 */

import { AnimationEngine } from '../AnimationEngine.js';
import { SimplifiedStateMachine, AnimationStates } from '../SimplifiedStateMachine.js';
import { BallController } from '../BallController.js';
import { AnimationRouter } from '../AnimationRouter.js';

export class Phase1TestRunner {
  constructor() {
    this.testResults = {
      total: 0,
      passed: 0,
      failed: 0,
      errors: [],
      components: {
        AnimationEngine: { passed: 0, failed: 0, tests: [] },
        SimplifiedStateMachine: { passed: 0, failed: 0, tests: [] },
        BallController: { passed: 0, failed: 0, tests: [] },
        AnimationRouter: { passed: 0, failed: 0, tests: [] },
        Integration: { passed: 0, failed: 0, tests: [] }
      }
    };
    
    this.isRunning = false;
  }

  /**
   * Run all Phase 1 tests
   */
  async runAllTests() {
    if (this.isRunning) {
      console.warn('Phase1TestRunner: Tests already running');
      return;
    }

    this.isRunning = true;
    this.testResults = {
      total: 0,
      passed: 0,
      failed: 0,
      errors: [],
      components: {
        AnimationEngine: { passed: 0, failed: 0, tests: [] },
        SimplifiedStateMachine: { passed: 0, failed: 0, tests: [] },
        BallController: { passed: 0, failed: 0, tests: [] },
        AnimationRouter: { passed: 0, failed: 0, tests: [] },
        Integration: { passed: 0, failed: 0, tests: [] }
      }
    };

    console.log('🚀 Starting Phase 1 Animation System Tests...\n');

    try {
      // Run component tests
      await this.runComponentTests();
      
      // Run integration tests
      await this.runIntegrationTests();
      
      // Generate report
      this.generateReport();
      
    } catch (error) {
      console.error('❌ Test runner error:', error);
      this.testResults.errors.push({
        type: 'TestRunner',
        message: error.message,
        stack: error.stack
      });
    } finally {
      this.isRunning = false;
    }

    return this.testResults;
  }

  /**
   * Run individual component tests
   */
  async runComponentTests() {
    console.log('📋 Running Component Tests...\n');

    // Test AnimationEngine
    await this.testAnimationEngine();
    
    // Test SimplifiedStateMachine
    await this.testSimplifiedStateMachine();
    
    // Test BallController
    await this.testBallController();
    
    // Test AnimationRouter
    await this.testAnimationRouter();
  }

  /**
   * Test AnimationEngine component
   */
  async testAnimationEngine() {
    console.log('  🔧 Testing AnimationEngine...');
    
    try {
      // Test initialization
      const mockScene = this.createMockScene();
      const mockPlayerSprites = this.createMockPlayerSprites();
      const mockBallSprite = this.createMockBallSprite();
      const mockOnUpdate = jest.fn();
      
      const engine = new AnimationEngine(mockScene, mockPlayerSprites, mockBallSprite, mockOnUpdate);
      
      // Test basic functionality
      this.runTest('AnimationEngine initialization', () => {
        expect(engine.scene).toBe(mockScene);
        expect(engine.playerSprites).toBe(mockPlayerSprites);
        expect(engine.ballSprite).toBe(mockBallSprite);
        expect(engine.onUpdate).toBe(mockOnUpdate);
      }, 'AnimationEngine');
      
      // Test turn processing
      this.runTest('AnimationEngine turn processing', async () => {
        const turnData = { result_type: 'MAKE', index: 1 };
        await engine.processTurn(turnData);
        expect(engine.isProcessingTurn).toBe(false);
      }, 'AnimationEngine');
      
      console.log('    ✅ AnimationEngine tests passed\n');
      
    } catch (error) {
      console.log('    ❌ AnimationEngine tests failed:', error.message);
      this.recordTestFailure('AnimationEngine', 'Component tests', error);
    }
  }

  /**
   * Test SimplifiedStateMachine component
   */
  async testSimplifiedStateMachine() {
    console.log('  🔄 Testing SimplifiedStateMachine...');
    
    try {
      const stateMachine = new SimplifiedStateMachine(AnimationStates.IDLE);
      
      // Test initialization
      this.runTest('StateMachine initialization', () => {
        expect(stateMachine.state).toBe(AnimationStates.IDLE);
        expect(stateMachine.is(AnimationStates.IDLE)).toBe(true);
      }, 'SimplifiedStateMachine');
      
      // Test state transitions
      this.runTest('StateMachine valid transition', () => {
        const result = stateMachine.transitionTo(AnimationStates.POSSESSION);
        expect(result).toBe(true);
        expect(stateMachine.state).toBe(AnimationStates.POSSESSION);
      }, 'SimplifiedStateMachine');
      
      // Test invalid transition
      this.runTest('StateMachine invalid transition', () => {
        const result = stateMachine.transitionTo(AnimationStates.SHOOTING);
        expect(result).toBe(false);
        expect(stateMachine.state).toBe(AnimationStates.POSSESSION);
      }, 'SimplifiedStateMachine');
      
      console.log('    ✅ SimplifiedStateMachine tests passed\n');
      
    } catch (error) {
      console.log('    ❌ SimplifiedStateMachine tests failed:', error.message);
      this.recordTestFailure('SimplifiedStateMachine', 'Component tests', error);
    }
  }

  /**
   * Test BallController component
   */
  async testBallController() {
    console.log('  ⚽ Testing BallController...');
    
    try {
      const mockScene = this.createMockScene();
      const mockBallSprite = this.createMockBallSprite();
      const mockPlayerSprite = this.createMockPlayerSprites()['player1'];
      
      const ballController = new BallController(mockScene, mockBallSprite);
      
      // Test initialization
      this.runTest('BallController initialization', () => {
        expect(ballController.currentOwner).toBe(null);
        expect(ballController.isAttached).toBe(false);
        expect(ballController.isInFlight).toBe(false);
      }, 'BallController');
      
      // Test ball attachment
      this.runTest('BallController attachment', () => {
        const result = ballController.attachToPlayer(mockPlayerSprite);
        expect(result).toBe(true);
        expect(ballController.getCurrentOwner()).toBe(mockPlayerSprite);
        expect(ballController.isBallAttached()).toBe(true);
      }, 'BallController');
      
      // Test ball detachment
      this.runTest('BallController detachment', () => {
        const result = ballController.detachFromPlayer();
        expect(result).toBe(true);
        expect(ballController.getCurrentOwner()).toBe(null);
        expect(ballController.isBallAttached()).toBe(false);
      }, 'BallController');
      
      console.log('    ✅ BallController tests passed\n');
      
    } catch (error) {
      console.log('    ❌ BallController tests failed:', error.message);
      this.recordTestFailure('BallController', 'Component tests', error);
    }
  }

  /**
   * Test AnimationRouter component
   */
  async testAnimationRouter() {
    console.log('  🎯 Testing AnimationRouter...');
    
    try {
      const mockScene = this.createMockScene();
      const mockPlayerSprites = this.createMockPlayerSprites();
      const mockBallSprite = this.createMockBallSprite();
      const mockOnUpdate = jest.fn();
      
      const router = new AnimationRouter(mockScene, mockPlayerSprites, mockBallSprite, mockOnUpdate);
      
      // Test initialization
      this.runTest('AnimationRouter initialization', () => {
        expect(router.stateMachine).toBeDefined();
        expect(router.ballController).toBeDefined();
        expect(router.animationEngine).toBeDefined();
        expect(router.isInitialized).toBe(true);
      }, 'AnimationRouter');
      
      // Test turn processing
      this.runTest('AnimationRouter turn processing', async () => {
        const turnData = { result_type: 'MAKE', index: 1 };
        await router.processTurn(turnData);
        expect(router.isProcessing).toBe(false);
      }, 'AnimationRouter');
      
      // Test status
      this.runTest('AnimationRouter status', () => {
        const status = router.getStatus();
        expect(status).toHaveProperty('isProcessing');
        expect(status).toHaveProperty('currentTurn');
        expect(status).toHaveProperty('stateMachine');
        expect(status).toHaveProperty('ballController');
        expect(status).toHaveProperty('isInitialized');
      }, 'AnimationRouter');
      
      console.log('    ✅ AnimationRouter tests passed\n');
      
    } catch (error) {
      console.log('    ❌ AnimationRouter tests failed:', error.message);
      this.recordTestFailure('AnimationRouter', 'Component tests', error);
    }
  }

  /**
   * Run integration tests
   */
  async runIntegrationTests() {
    console.log('🔗 Running Integration Tests...\n');
    
    try {
      // Test complete basketball sequence
      await this.testCompleteBasketballSequence();
      
      // Test error recovery
      await this.testErrorRecovery();
      
      // Test queue management
      await this.testQueueManagement();
      
      console.log('  ✅ Integration tests passed\n');
      
    } catch (error) {
      console.log('  ❌ Integration tests failed:', error.message);
      this.recordTestFailure('Integration', 'Integration tests', error);
    }
  }

  /**
   * Test complete basketball sequence
   */
  async testCompleteBasketballSequence() {
    console.log('    🏀 Testing complete basketball sequence...');
    
    try {
      const mockScene = this.createMockScene();
      const mockPlayerSprites = this.createMockPlayerSprites();
      const mockBallSprite = this.createMockBallSprite();
      const mockOnUpdate = jest.fn();
      
      const router = new AnimationRouter(mockScene, mockPlayerSprites, mockBallSprite, mockOnUpdate);
      
      // Test shot sequence: possession → shot → miss → rebound
      this.runTest('Complete shot sequence', async () => {
        // 1. Start with possession
        router.stateMachine.state = AnimationStates.POSSESSION;
        router.ballController.attachToPlayer(mockPlayerSprites['player1']);
        
        // 2. Take shot
        const shotTurn = { result_type: 'MISS', index: 1, shooter_id: 'player1' };
        await router.processTurn(shotTurn);
        
        // 3. Handle rebound
        const reboundTurn = { result_type: 'REBOUND', index: 2, rebounder_id: 'player2' };
        await router.processTurn(reboundTurn);
        
        // Verify all turns were processed
        expect(router.animationEngine.processTurn).toHaveBeenCalledTimes(2);
      }, 'Integration');
      
      console.log('      ✅ Complete basketball sequence test passed');
      
    } catch (error) {
      console.log('      ❌ Complete basketball sequence test failed:', error.message);
      throw error;
    }
  }

  /**
   * Test error recovery
   */
  async testErrorRecovery() {
    console.log('    🛡️ Testing error recovery...');
    
    try {
      const mockScene = this.createMockScene();
      const mockPlayerSprites = this.createMockPlayerSprites();
      const mockBallSprite = this.createMockBallSprite();
      const mockOnUpdate = jest.fn();
      
      const router = new AnimationRouter(mockScene, mockPlayerSprites, mockBallSprite, mockOnUpdate);
      
      // Test error handling
      this.runTest('Error recovery', async () => {
        const turnData = { result_type: 'MAKE', index: 1 };
        const error = new Error('Test error');
        
        // Mock error in animation engine
        router.animationEngine.processTurn.mockRejectedValue(error);
        
        // Process turn with error
        await router.processTurn(turnData);
        
        // Verify system was reset to safe state
        expect(router.stateMachine.transitionTo).toHaveBeenCalledWith(
          AnimationStates.IDLE,
          { reason: 'error_recovery' }
        );
        expect(router.ballController.reset).toHaveBeenCalled();
      }, 'Integration');
      
      console.log('      ✅ Error recovery test passed');
      
    } catch (error) {
      console.log('      ❌ Error recovery test failed:', error.message);
      throw error;
    }
  }

  /**
   * Test queue management
   */
  async testQueueManagement() {
    console.log('    📋 Testing queue management...');
    
    try {
      const mockScene = this.createMockScene();
      const mockPlayerSprites = this.createMockPlayerSprites();
      const mockBallSprite = this.createMockBallSprite();
      const mockOnUpdate = jest.fn();
      
      const router = new AnimationRouter(mockScene, mockPlayerSprites, mockBallSprite, mockOnUpdate);
      
      // Test queue handling
      this.runTest('Queue management', async () => {
        const turn1 = { result_type: 'MAKE', index: 1 };
        const turn2 = { result_type: 'MISS', index: 2 };
        
        // Mock processing to take time
        router.animationEngine.processTurn.mockImplementation(() => 
          new Promise(resolve => setTimeout(resolve, 10))
        );
        
        // Start processing first turn
        const processPromise = router.processTurn(turn1);
        
        // Queue second turn
        router.processTurn(turn2);
        
        // Wait for processing
        await processPromise;
        
        // Verify both turns were processed
        expect(router.animationEngine.processTurn).toHaveBeenCalledTimes(2);
      }, 'Integration');
      
      console.log('      ✅ Queue management test passed');
      
    } catch (error) {
      console.log('      ❌ Queue management test failed:', error.message);
      throw error;
    }
  }

  /**
   * Run a single test
   */
  runTest(testName, testFunction, component) {
    try {
      testFunction();
      this.recordTestSuccess(component, testName);
    } catch (error) {
      this.recordTestFailure(component, testName, error);
    }
  }

  /**
   * Record test success
   */
  recordTestSuccess(component, testName) {
    this.testResults.total++;
    this.testResults.passed++;
    this.testResults.components[component].passed++;
    this.testResults.components[component].tests.push({
      name: testName,
      status: 'passed',
      error: null
    });
  }

  /**
   * Record test failure
   */
  recordTestFailure(component, testName, error) {
    this.testResults.total++;
    this.testResults.failed++;
    this.testResults.components[component].failed++;
    this.testResults.components[component].tests.push({
      name: testName,
      status: 'failed',
      error: error.message
    });
    this.testResults.errors.push({
      component,
      test: testName,
      message: error.message,
      stack: error.stack
    });
  }

  /**
   * Generate comprehensive test report
   */
  generateReport() {
    console.log('📊 Phase 1 Test Results Summary\n');
    console.log('=' .repeat(50));
    
    // Overall results
    const passRate = ((this.testResults.passed / this.testResults.total) * 100).toFixed(1);
    console.log(`Total Tests: ${this.testResults.total}`);
    console.log(`Passed: ${this.testResults.passed} (${passRate}%)`);
    console.log(`Failed: ${this.testResults.failed}`);
    console.log(`Errors: ${this.testResults.errors.length}\n`);
    
    // Component results
    console.log('Component Results:');
    console.log('-'.repeat(30));
    
    Object.entries(this.testResults.components).forEach(([component, results]) => {
      const componentPassRate = results.passed + results.failed > 0 
        ? ((results.passed / (results.passed + results.failed)) * 100).toFixed(1)
        : '0.0';
      
      console.log(`${component}:`);
      console.log(`  Passed: ${results.passed}`);
      console.log(`  Failed: ${results.failed}`);
      console.log(`  Pass Rate: ${componentPassRate}%`);
      
      if (results.failed > 0) {
        console.log(`  Failed Tests:`);
        results.tests.filter(test => test.status === 'failed').forEach(test => {
          console.log(`    - ${test.name}: ${test.error}`);
        });
      }
      console.log('');
    });
    
    // Error details
    if (this.testResults.errors.length > 0) {
      console.log('Error Details:');
      console.log('-'.repeat(30));
      this.testResults.errors.forEach((error, index) => {
        console.log(`${index + 1}. ${error.component} - ${error.test}`);
        console.log(`   ${error.message}`);
        if (error.stack) {
          console.log(`   Stack: ${error.stack.split('\n')[0]}`);
        }
        console.log('');
      });
    }
    
    // Final status
    if (this.testResults.failed === 0) {
      console.log('🎉 All Phase 1 tests passed! The new animation system is ready for Phase 2.');
    } else {
      console.log('⚠️  Some tests failed. Please review the errors above before proceeding to Phase 2.');
    }
    
    console.log('=' .repeat(50));
  }

  /**
   * Create mock scene for testing
   */
  createMockScene() {
    return {
      events: {
        on: jest.fn(),
        off: jest.fn(),
        emit: jest.fn()
      },
      time: {
        now: Date.now()
      }
    };
  }

  /**
   * Create mock ball sprite for testing
   */
  createMockBallSprite() {
    return {
      x: 100,
      y: 200,
      visible: false,
      depth: 0,
      setPosition: jest.fn(),
      setVisible: jest.fn(),
      setDepth: jest.fn()
    };
  }

  /**
   * Create mock player sprites for testing
   */
  createMockPlayerSprites() {
    return {
      'player1': {
        playerId: 'player1',
        team: 'home',
        x: 150,
        y: 250,
        depth: 10
      },
      'player2': {
        playerId: 'player2',
        team: 'away',
        x: 200,
        y: 300,
        depth: 10
      }
    };
  }
}

export default Phase1TestRunner;
