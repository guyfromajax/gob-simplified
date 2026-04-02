/**
 * SS&S Game Announcement System
 * 
 * Central dispatcher for ALL game announcements.
 * Replaces scattered announcement calls across multiple files.
 * 
 * Usage:
 *   announceGameEvent('SHOT_MAKE', turnData, scene);
 *   announceGameEvent('REBOUND', turnData, scene, { rebounderId: '...' });
 *   announceGameEvent('PRESSURE_FCP', turnData, scene);
 */

import { showAnnouncement, showAndOneAnnouncement } from './announcements.js';
import { triggerFoulEffect, triggerTurnoverEffect, triggerMadeShotFlash } from '../animation/negativeActionEffects.js';
import {
  pickOffensiveFoulAnnouncementText,
  pickDefensiveFoulAnnouncementText,
} from './foulAnnouncementLanguage.js';
import gameStore from '../../state/gameStore.js';
import { isFastBreakEntryAnnouncementsEnabled } from '../constants/fastBreakConstants.js';

function getSecondaryColorForTeam(scene, teamId) {
  if (!scene?.simData || teamId == null) return '#333333';
  const colors = gameStore.getColors();
  const homeId = scene.simData.home_team_id;
  const awayId = scene.simData.away_team_id;
  const isHome = String(teamId) === String(homeId);
  const side = isHome ? colors.home : colors.away;
  return side?.secondary_color || '#333333';
}

/**
 * Central game event announcement dispatcher
 * 
 * @param {string} eventType - Type of event to announce
 * @param {Object} turnData - Turn data from backend
 * @param {Object} scene - Phaser scene
 * @param {Object} context - Additional context (rebounderId, shooterId, etc.)
 */
export function announceGameEvent(eventType, turnData, scene, context = {}) {
  // Game announcement

  // Get team context
  const homeTeamId = scene?.simData?.home_team_id;
  const offenseTeamId = turnData?.offense_team_id || scene?.offenseTeamId;
  const isHomeOffense = homeTeamId && String(offenseTeamId) === String(homeTeamId);
  const offenseTeam = isHomeOffense ? 'home' : 'away';
  const defenseTeam = isHomeOffense ? 'away' : 'home';

  // Route to appropriate announcement handler
  switch (eventType) {
    // ========== SHOT RESULTS ==========
    case 'SHOT_MAKE':
      handleShotMakeAnnouncement(turnData, scene, context, offenseTeam);
      break;

    case 'SHOT_MAKE_AND_ONE':
      handleAndOneAnnouncement(turnData, scene, context, offenseTeam);
      break;

    // ========== FREE THROW RESULTS ==========
    case 'FT_MAKE':
      handleFreeThrowMakeAnnouncement(turnData, scene, context, offenseTeam);
      break;

    case 'FT_MISS':
      // FT misses are silent unless it's for special cases
      // Last FT miss is silent (rebound announcement takes priority)
      break;

    // ========== REBOUNDS ==========
    case 'REBOUND':
      handleReboundAnnouncement(turnData, scene, context);
      break;

    // ========== FOULS ==========
    case 'FOUL_SHOOTING':
      handleShootingFoulAnnouncement(turnData, scene, context);
      break;

    case 'FOUL_OFFENSIVE':
      handleOffensiveFoulAnnouncement(turnData, scene, context, defenseTeam);
      break;

    case 'FOUL_DEFENSIVE':
      handleDefensiveFoulAnnouncement(turnData, scene, context, offenseTeam);
      break;

    case 'CHARGE':
      handleChargeAnnouncement(turnData, scene, context, defenseTeam);
      break;

    case 'BLOCKING_FOUL':
      handleBlockingFoulAnnouncement(turnData, scene, context, offenseTeam);
      break;

    case 'BLOCK':
      handleBlockAnnouncement(turnData, scene, context);
      break;

    // ========== TURNOVERS ==========
    case 'STEAL':
      handleStealAnnouncement(turnData, scene, context, defenseTeam);
      break;

    case 'TURNOVER':
      handleTurnoverAnnouncement(turnData, scene, context, offenseTeam);
      break;

    // ========== PRESSURE SYSTEMS ==========
    case 'PRESSURE_FCP':
      showAnnouncement("Press!", 'defense');
      break;

    case 'PRESSURE_HCT':
      showAnnouncement("Trap!", 'defense');
      break;

    // ========== FAST BREAK ==========
    case 'FAST_BREAK':
      if (isFastBreakEntryAnnouncementsEnabled()) {
        showAnnouncement("Fast Break!", offenseTeam);
      }
      break;

    case 'RIM_RUNNER_BATTED_OOB':
      showAnnouncement("Batted Ball Out Of Bounds!", offenseTeam);
      break;

    // ========== SITUATIONAL LOGIC (Q4/OT) ==========
    case 'SLOW_IT_DOWN':
      showAnnouncement("Slow It Down", offenseTeam);
      break;

    case 'QUICK_SHOT':
      showAnnouncement("Quick Shot", offenseTeam);
      break;

    // ========== FINAL TURN (end of quarter/game) ==========
    case 'FINAL_SHOT':
      showAnnouncement("Final Shot", offenseTeam);
      break;

    case 'DEFENSIVE_STOP':
      // Outlet denial / team stop: optional no headshot (e.g. Rim Runner outlet denied)
      if (context.noPlayerImage) {
        showAnnouncement('Great Stop!', defenseTeam, null);
        break;
      }
      // Get stopper data if available
      const stopperId = context.stopperId || turnData.stopper_id;
      let stopperData = null;
      if (scene && stopperId) {
        const stopperSprite = scene.playerSprites?.[stopperId];
        if (stopperSprite) {
          stopperData = {
            playerId: stopperId,
            photo: stopperSprite.photo || null,
            teamName: stopperSprite.team_id,
            secondaryColor: getSecondaryColorForTeam(scene, stopperSprite.team_id)
          };
        }
      }
      showAnnouncement("Great Stop!", defenseTeam, stopperData);
      break;

    // ========== SPECIAL EVENTS ==========
    case 'DOUBLE_TEAM':
      showAnnouncement("DOUBLE TEAM!", 'neutral', null);
      break;

    default:
      console.warn(`⚠️ Unknown announcement event type: ${eventType}`);
  }
}

// ========== INDIVIDUAL ANNOUNCEMENT HANDLERS ==========

function handleShotMakeAnnouncement(turnData, scene, context, offenseTeam) {
  const shooterId = context.shooterId || turnData.shooter_id;
  let playerData = null;

  if (scene && shooterId) {
    const shooterSprite = scene.playerSprites?.[shooterId];
    if (shooterSprite) {
      playerData = {
        playerId: shooterId,
        photo: shooterSprite.photo || null,
        teamName: shooterSprite.team_id,
        secondaryColor: getSecondaryColorForTeam(scene, shooterSprite.team_id)
      };
    }
  }

  showAnnouncement("It's Good!", offenseTeam, playerData);
}

function handleAndOneAnnouncement(turnData, scene, context, offenseTeam) {
  const shooterId = context.shooterId || turnData.shooter_id;
  const foulerId = context.foulerId || turnData.foul_player_id;

  let shooterData = null;
  let foulerData = null;

  if (scene && shooterId) {
    const shooterSprite = scene.playerSprites?.[shooterId];
    if (shooterSprite) {
      shooterData = {
        playerId: shooterId,
        photo: shooterSprite.photo || null,
        teamName: shooterSprite.team_id,
        secondaryColor: getSecondaryColorForTeam(scene, shooterSprite.team_id)
      };
    }
  }

  if (scene && foulerId) {
    const foulerSprite = scene.playerSprites?.[foulerId];
    if (foulerSprite) {
      foulerData = {
        playerId: foulerId,
        photo: foulerSprite.photo || null,
        teamName: foulerSprite.team_id,
        secondaryColor: getSecondaryColorForTeam(scene, foulerSprite.team_id)
      };
    }
  }

  if (shooterData && foulerData) {
    showAndOneAnnouncement(offenseTeam, shooterData, foulerData);
  } else {
    // Fallback to simple announcement
    showAnnouncement("It's Good! And 1!", offenseTeam, shooterData);
  }
}

function handleFreeThrowMakeAnnouncement(turnData, scene, context, offenseTeam) {
  const shooterId = context.shooterId || turnData.shooter_id;
  let playerData = null;

  if (scene && shooterId) {
    const shooterSprite = scene.playerSprites?.[shooterId];
    if (shooterSprite) {
      playerData = {
        playerId: shooterId,
        photo: shooterSprite.photo || null,
        teamName: shooterSprite.team_id,
        secondaryColor: getSecondaryColorForTeam(scene, shooterSprite.team_id)
      };
    }
  }

  // Show "It's Good!" for FT makes (same as regular shots)
  showAnnouncement("It's Good!", offenseTeam, playerData);
}

function handleReboundAnnouncement(turnData, scene, context) {
  const rebounderId = context.rebounderId || turnData.rebounderId || turnData.rebounder_id;
  if (!rebounderId || !scene) return;

  const rebounderSprite = scene.playerSprites?.[rebounderId];
  if (!rebounderSprite) return;

  const rebounderTeam = rebounderSprite.team; // "home" or "away"
  const playerData = {
    playerId: rebounderId,
    photo: rebounderSprite.photo || null,
    teamName: rebounderSprite.team_id,
    secondaryColor: getSecondaryColorForTeam(scene, rebounderSprite.team_id)
  };

  showAnnouncement("Rebound!", rebounderTeam, playerData);
}

function handleBlockAnnouncement(turnData, scene, context) {
  const blockerId = context.blockerId || turnData.blocker_id;
  if (!blockerId || !scene) return;

  const blockerSprite = scene.playerSprites?.[blockerId];
  if (!blockerSprite) return;

  const blockerTeam = blockerSprite.team;
  const playerData = {
    playerId: blockerId,
    photo: blockerSprite.photo || null,
    teamName: blockerSprite.team_id,
    secondaryColor: getSecondaryColorForTeam(scene, blockerSprite.team_id)
  };

  showAnnouncement("BLOCK!", blockerTeam, playerData);
}

function handleShootingFoulAnnouncement(turnData, scene, context) {
  const foulerId = context.foulerId || turnData.foul_player_id;
  let playerData = null;

  if (scene && foulerId) {
    const foulerSprite = scene.playerSprites?.[foulerId];
    if (foulerSprite) {
      playerData = {
        playerId: foulerId,
        photo: foulerSprite.photo || null,
        teamName: foulerSprite.team_id,
        secondaryColor: getSecondaryColorForTeam(scene, foulerSprite.team_id)
      };
    }
  }

  showAnnouncement("Shooting Foul!", 'neutral', playerData);
}

function handleOffensiveFoulAnnouncement(turnData, scene, context, defenseTeam) {
  const foulerId = context.foulerId || turnData.foul_player_id;
  let playerData = null;

  if (scene && foulerId) {
    const foulerSprite = scene.playerSprites?.[foulerId];
    if (foulerSprite) {
      playerData = {
        playerId: foulerId,
        photo: foulerSprite.photo || null,
        teamName: foulerSprite.team_id,
        secondaryColor: getSecondaryColorForTeam(scene, foulerSprite.team_id)
      };
    }
  }

  const foulText = pickOffensiveFoulAnnouncementText(turnData);
  showAnnouncement(foulText, defenseTeam, playerData);

  // Trigger visual effect
  if (scene && foulerId) {
    triggerFoulEffect(scene, foulerId);
  }
}

function handleDefensiveFoulAnnouncement(turnData, scene, context, offenseTeam) {
  const foulerId = context.foulerId || turnData.foul_player_id;
  let playerData = null;

  if (scene && foulerId) {
    const foulerSprite = scene.playerSprites?.[foulerId];
    if (foulerSprite) {
      playerData = {
        playerId: foulerId,
        photo: foulerSprite.photo || null,
        teamName: foulerSprite.team_id,
        secondaryColor: getSecondaryColorForTeam(scene, foulerSprite.team_id)
      };
    }
  }

  const foulText = pickDefensiveFoulAnnouncementText(turnData);
  showAnnouncement(foulText, offenseTeam, playerData);

  // Trigger visual effect
  if (scene && foulerId) {
    triggerFoulEffect(scene, foulerId);
  }
}

function handleChargeAnnouncement(turnData, scene, context, defenseTeam) {
  const foulerId = context.foulerId || turnData.foul_player_id || turnData.shooter_id;
  let playerData = null;

  if (scene && foulerId) {
    const foulerSprite = scene.playerSprites?.[foulerId];
    if (foulerSprite) {
      playerData = {
        playerId: foulerId,
        photo: foulerSprite.photo || null,
        teamName: foulerSprite.team_id,
        secondaryColor: getSecondaryColorForTeam(scene, foulerSprite.team_id)
      };
    }
  }

  showAnnouncement("CHARGE!", defenseTeam, playerData);

  // Trigger visual effect
  if (scene && foulerId) {
    triggerFoulEffect(scene, foulerId);
  }
}

function handleBlockingFoulAnnouncement(turnData, scene, context, offenseTeam) {
  const foulerId = context.foulerId || turnData.foul_player_id || turnData.defenderId;
  let playerData = null;

  if (scene && foulerId) {
    const foulerSprite = scene.playerSprites?.[foulerId];
    if (foulerSprite) {
      playerData = {
        playerId: foulerId,
        photo: foulerSprite.photo || null,
        teamName: foulerSprite.team_id,
        secondaryColor: getSecondaryColorForTeam(scene, foulerSprite.team_id)
      };
    }
  }

  showAnnouncement("BLOCKING FOUL!", offenseTeam, playerData);

  // Trigger visual effect
  if (scene && foulerId) {
    triggerFoulEffect(scene, foulerId);
  }
}

function handleStealAnnouncement(turnData, scene, context, defenseTeam) {
  const stealerId = context.stealerId || turnData.stealer_id || turnData.defender_id;
  let playerData = null;

  if (scene && stealerId) {
    const stealerSprite = scene.playerSprites?.[stealerId];
    if (stealerSprite) {
      playerData = {
        playerId: stealerId,
        photo: stealerSprite.photo || null,
        teamName: stealerSprite.team_id,
        secondaryColor: getSecondaryColorForTeam(scene, stealerSprite.team_id)
      };
    }
  }

  showAnnouncement("STEAL!", defenseTeam, playerData);

  // Trigger visual effect on victim
  const victimId = context.victimId || turnData.victim_id;
  if (scene && victimId) {
    triggerTurnoverEffect(scene, victimId);
  }
}

function handleTurnoverAnnouncement(turnData, scene, context, offenseTeam) {
  const victimId = context.victimId || turnData.victim_id;
  let playerData = null;

  if (scene && victimId) {
    const victimSprite = scene.playerSprites?.[victimId];
    if (victimSprite) {
      playerData = {
        playerId: victimId,
        photo: victimSprite.photo || null,
        teamName: victimSprite.team_id,
        secondaryColor: getSecondaryColorForTeam(scene, victimSprite.team_id)
      };
    }
  }

  // Determine turnover type
  const turnoverType = context.turnoverType || turnData.turnover_type;
  
  // ✅ FIX: For dead ball turnovers (DEAD BALL result_type), randomly choose "Travel!" or "Double Dribble!" (50/50)
  let turnoverText;
  if (turnData.result_type === 'DEAD BALL' || turnData.result_type === 'TURNOVER') {
    // Check if it's a dead ball turnover (not a steal)
    const isDeadBallTurnover = turnData.result_type === 'DEAD BALL' || 
                               (!turnData.text?.toLowerCase().includes('steal') && 
                                !turnData.stealer_id && 
                                !turnData.defender_id);
    
    if (isDeadBallTurnover && !turnoverType) {
      // Randomly choose between Travel and Double Dribble (50/50)
      turnoverText = Math.random() < 0.5 ? "Travel!" : "Double Dribble!";
    } else {
      // Use existing type mapping (includes shot clock violation from stopper path)
      const typeMap = {
        "TRAVEL": "Travel!",
        "DOUBLE_DRIBBLE": "Double Dribble!",
        "OUT_OF_BOUNDS": "OUT OF BOUNDS!",
        "BAD_PASS": "BAD PASS!",
        "SHOT_CLOCK": "Shot Clock Violation!"
      };
      turnoverText = typeMap[turnoverType] || "TURNOVER!";
    }
  } else {
    // Fallback for other turnover types
    const typeMap = {
      "TRAVEL": "Travel!",
      "DOUBLE_DRIBBLE": "Double Dribble!",
      "OUT_OF_BOUNDS": "OUT OF BOUNDS!",
      "BAD_PASS": "BAD PASS!",
      "SHOT_CLOCK": "Shot Clock Violation!"
    };
    turnoverText = typeMap[turnoverType] || "TURNOVER!";
  }
  
  showAnnouncement(turnoverText, offenseTeam, playerData);

  // Trigger visual effect
  if (scene && victimId) {
    triggerTurnoverEffect(scene, victimId);
  }
}

