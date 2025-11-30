/**
 * Robust offenseTeamId resolver
 * Ensures offenseTeamId is always defined for every turn (except pre-opening tip)
 * 
 * Fallback chain (in order of preference):
 * 1. turnData.possession_team_id (backend guarantee - always set, represents team on offense DURING the turn)
 * 2. scene.offenseTeamId (scene state - kept in sync by PossessionManager)
 * 3. Derive from passInfo - find passer's team_id from playerSprites
 * 4. Derive from animations - find ball handler's team_id from playerSprites
 * 5. Derive from simData - use home_team_id or away_team_id based on first animation player
 * 6. Last resort: simData.home_team_id (should never reach here)
 * 
 * @param {Object} params
 * @param {Object} params.scene - Phaser scene
 * @param {Object} params.turnData - Turn data from backend
 * @param {Object} [params.playerSprites] - Map of playerId -> sprite (optional, for derivation)
 * @param {Object} [params.passInfo] - Pass info from detectPassAtStep (optional, for derivation)
 * @returns {string|null} offenseTeamId (should never be null except pre-opening tip)
 */
export function resolveOffenseTeamId({ scene, turnData, playerSprites = null, passInfo = null }) {
  // Priority 1: turnData.possession_team_id (backend guarantee - always set for every turn)
  // Represents the team on offense DURING this turn (set before any possession flips)
  if (turnData?.possession_team_id) {
    return turnData.possession_team_id;
  }
  
  // Priority 2: scene.offenseTeamId (scene state - kept in sync by PossessionManager)
  if (scene?.offenseTeamId) {
    return scene.offenseTeamId;
  }
  
  // Priority 3: Derive from passInfo - find passer's team_id from playerSprites
  if (passInfo?.passerId && playerSprites) {
    const passerSprite = playerSprites[passInfo.passerId];
    if (passerSprite?.team_id) {
      return passerSprite.team_id;
    }
  }
  
  // Priority 4: Derive from animations - find ball handler's team_id from playerSprites
  if (turnData?.animations && Array.isArray(turnData.animations) && playerSprites) {
    // Find first player with ball at step 0
    for (const anim of turnData.animations) {
      if (anim.hasBallAtStep && anim.hasBallAtStep[0] === true) {
        const sprite = playerSprites[anim.playerId];
        if (sprite?.team_id) {
          return sprite.team_id;
        }
      }
    }
    // Fallback: use first animation player's team_id
    if (turnData.animations.length > 0) {
      const firstAnim = turnData.animations[0];
      const sprite = playerSprites[firstAnim.playerId];
      if (sprite?.team_id) {
        return sprite.team_id;
      }
    }
  }
  
  // Priority 5: Derive from simData - use home_team_id or away_team_id
  // This is a last resort and should rarely be needed
  const simData = scene?.simData;
  if (simData) {
    // Try to determine from first player in animations
    if (turnData?.animations && Array.isArray(turnData.animations) && turnData.animations.length > 0) {
      const firstAnim = turnData.animations[0];
      // Check if we can find this player in simData.players
      if (simData.players && Array.isArray(simData.players)) {
        const player = simData.players.find(p => 
          (p.playerId ?? p.player_id) === firstAnim.playerId
        );
        if (player?.team_id) {
          return player.team_id;
        }
        // Fallback: use team field to determine team_id
        if (player?.team === "home" && simData.home_team_id) {
          return simData.home_team_id;
        }
        if (player?.team === "away" && simData.away_team_id) {
          return simData.away_team_id;
        }
      }
    }
    
    // Last resort: use home_team_id (should never reach here)
    if (simData.home_team_id) {
      console.warn('⚠️ [offenseTeamIdResolver] Using home_team_id as last resort - this should not happen!', {
        turnData: {
          possession_team_id: turnData?.possession_team_id,
          result_type: turnData?.result_type
        },
        sceneOffenseTeamId: scene?.offenseTeamId
      });
      return simData.home_team_id;
    }
  }
  
  // Should never reach here - log error
  console.error('❌ [offenseTeamIdResolver] Failed to resolve offenseTeamId!', {
    turnData: {
      possession_team_id: turnData?.possession_team_id,
      result_type: turnData?.result_type,
      hasAnimations: !!turnData?.animations,
      animationCount: turnData?.animations?.length || 0
    },
    sceneOffenseTeamId: scene?.offenseTeamId,
    hasPlayerSprites: !!playerSprites,
    hasPassInfo: !!passInfo,
    hasSimData: !!scene?.simData
  });
  
  return null; // Only returns null for pre-opening tip or data corruption
}

