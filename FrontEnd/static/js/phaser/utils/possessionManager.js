/**
 * Centralized Possession Manager
 * Handles all possession changes with deduplication and validation
 * Maintains backward compatibility with existing emission system
 */

export class PossessionManager {
  constructor(scene) {
    this.scene = scene;
    this.currentOffenseTeamId = scene.offenseTeamId;
    this.pendingChanges = new Map();
    this.changeHistory = [];
    this.isProcessing = false;
    
    // Bind the centralized handler
    this.handlePossessionChange = this.handlePossessionChange.bind(this);
    
    // Listen for all possession change events
    this.scene.events?.on?.('possessionChange', this.handlePossessionChange);
  }

  /**
   * Centralized possession change handler
   * Prevents duplicates and race conditions
   */
  handlePossessionChange(payload = {}) {
    const { offenseTeamId, reason = 'unknown', metadata = {} } = payload;
    
    // Skip if already processing to prevent recursion
    if (this.isProcessing) {
      console.warn('PossessionManager: Skipping change during processing', { offenseTeamId, reason });
      return;
    }

    // Skip if same team (deduplication)
    if (this.currentOffenseTeamId === offenseTeamId) {
      console.warn('PossessionManager: Duplicate possession change prevented', { 
        teamId: offenseTeamId, 
        reason,
        stackTrace: new Error().stack?.split('\n').slice(1, 4)
      });
      return;
    }

    // Skip if in FastBreak state (existing behavior)
    if (this.scene.stateMachine?.is('FastBreak')) {
      console.log('PossessionManager: Skipping change in FastBreak state', { offenseTeamId, reason });
      return;
    }

    this.isProcessing = true;

    try {
      // Log the change
      console.log('PossessionManager: Processing possession change', {
        from: this.currentOffenseTeamId,
        to: offenseTeamId,
        reason,
        currentState: this.scene.stateMachine?.state,
        metadata
      });

      // Update the offense team
      this.currentOffenseTeamId = offenseTeamId; // Internal state for PossessionManager
      this.scene.offenseTeamId = offenseTeamId; // Single source of truth for scene

      // Record in history for debugging
      this.changeHistory.push({
        timestamp: Date.now(),
        from: this.scene.offenseTeamId,
        to: offenseTeamId,
        reason,
        state: this.scene.stateMachine?.state,
        metadata
      });

      // Keep only last 50 changes to prevent memory leaks
      if (this.changeHistory.length > 50) {
        this.changeHistory = this.changeHistory.slice(-50);
      }

      // Set possession flip flag
      this.scene.possessionFlipInProgress = true;
      this.scene.time.delayedCall(0, () => (this.scene.possessionFlipInProgress = false));

    } finally {
      this.isProcessing = false;
    }
  }

  /**
   * Get current possession info
   */
  getCurrentPossession() {
    return {
      offenseTeamId: this.currentOffenseTeamId,
      isProcessing: this.isProcessing,
      changeCount: this.changeHistory.length
    };
  }

  /**
   * Get possession change history for debugging
   */
  getChangeHistory(limit = 10) {
    return this.changeHistory.slice(-limit);
  }

  /**
   * Clean up event listeners
   */
  destroy() {
    this.scene.events?.off?.('possessionChange', this.handlePossessionChange);
  }
}

/**
 * Initialize possession manager for a scene
 * This should be called once when the scene is created
 */
export function initializePossessionManager(scene) {
  if (scene.possessionManager) {
    console.warn('PossessionManager already initialized for this scene');
    return scene.possessionManager;
  }

  scene.possessionManager = new PossessionManager(scene);
  return scene.possessionManager;
}
