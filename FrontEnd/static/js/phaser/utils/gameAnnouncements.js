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

import {
  showAnnouncement,
  showAndOneAnnouncement,
  showSecondaryAnnouncement,
  buildSecondaryStopperPlayerData,
  getFastBreakPlayLabel,
  getHctTrapPlayLabel,
  getFcpPressPlayLabel,
  announceReboundHeadlineIfNeeded,
  isPassInterception,
} from './announcements.js';
import { resolveStealSfxFile, resolveInterceptionSfxFile } from './gameSfx.js';
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
      handleFreeThrowMissAnnouncement(turnData, scene, context, offenseTeam);
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

    case 'AIRBALL':
      handleAirballAnnouncement(turnData, scene, context, offenseTeam);
      break;

    // ========== TURNOVERS ==========
    case 'STEAL':
      handleStealAnnouncement(turnData, scene, context, defenseTeam);
      break;

    case 'TURNOVER':
      handleTurnoverAnnouncement(turnData, scene, context, offenseTeam);
      break;

    // ========== PRESSURE SYSTEMS (secondary tier) ==========
    case 'PRESSURE_FCP':
      showSecondaryAnnouncement("Press!", defenseTeam, null, {
        eventSubtitle: getFcpPressPlayLabel(turnData?.fcp_press_play),
      });
      break;

    case 'PRESSURE_HCT':
      showSecondaryAnnouncement("Trap!", defenseTeam, null, {
        eventSubtitle: getHctTrapPlayLabel(turnData?.hct_trap_play),
      });
      break;

    // ========== FAST BREAK (secondary tier) ==========
    case 'FAST_BREAK':
      if (isFastBreakEntryAnnouncementsEnabled()) {
        showSecondaryAnnouncement("Fast Break!", offenseTeam, null, {
          eventSubtitle: getFastBreakPlayLabel(turnData?.fast_break_play),
        });
      }
      break;

    case 'RIM_RUNNER_BATTED_OOB':
      showSecondaryAnnouncement("Batted Ball Out Of Bounds!", offenseTeam);
      break;

    // Generic batted-ball-out-of-bounds (HCT §14 pass contest, etc.). Offense
    // retains; this is NOT a turnover, so the turnover announce is suppressed
    // (see finalizeTurnAfterAnimation / announceFromTurnData bat_oob guards).
    case 'BATTED_OOB':
      showSecondaryAnnouncement("Batted Ball Out Of Bounds!", offenseTeam);
      break;

    // ========== SITUATIONAL LOGIC (Q4/OT) — secondary tier ==========
    case 'SLOW_IT_DOWN':
      showSecondaryAnnouncement("Slow It Down", offenseTeam);
      break;

    case 'QUICK_SHOT':
      showSecondaryAnnouncement("Quick Shot", offenseTeam);
      break;

    // ========== FINAL TURN (end of quarter/game) — secondary tier ==========
    case 'FINAL_SHOT':
      showSecondaryAnnouncement("Final Shot", offenseTeam, null, {
        quarter: turnData?.quarter ?? scene?.quarter ?? scene?.simData?.quarter ?? null,
        suppressCourtSfx: context?.suppressCourtSfx === true,
      });
      break;

    case 'DEFENSIVE_STOP':
      // Outlet denial / team stop: optional no headshot (e.g. Rim Runner outlet denied)
      if (context.noPlayerImage) {
        showSecondaryAnnouncement('Great Stop!', defenseTeam, null);
        break;
      }
      // Get stopper data if available
      const stopperId = context.stopperId || turnData.stopper_id;
      const stopperData = scene && stopperId
        ? buildSecondaryStopperPlayerData(scene, stopperId, scene.playerSprites)
        : null;
      showSecondaryAnnouncement("Great Stop!", defenseTeam, stopperData);
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

function handleFreeThrowMissAnnouncement(turnData, scene, context, offenseTeam) {
  const shooterId = context?.shooterId || turnData?.shooter_id;
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

  showAnnouncement("No Good", offenseTeam, playerData);
}

function handleReboundAnnouncement(turnData, scene, context) {
  const rebounderId = context?.rebounderId ?? turnData?.rebounderId ?? turnData?.rebounder_id;
  if (!rebounderId || !scene) return;

  const sid = String(rebounderId);
  const rebounderSprite =
    scene.playerSprites?.[sid] ?? scene.playerSprites?.[rebounderId] ?? null;
  if (!rebounderSprite) return;

  announceReboundHeadlineIfNeeded(scene, turnData, rebounderSprite, sid);
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

  // SFX is carried on the announcement payload and played by court.html
  // at overlay mount — synced to the visual appearance per
  // SFX_System.md "Block Announce: Trigger: immediately when the
  // Block announce appears."
  showAnnouncement("BLOCK!", blockerTeam, playerData, { sfx: 'duke-its-blocked.wav' });
}

/**
 * Legacy-path helper: announce Airball! when shot_variant is AIRBALL.
 * Schema playback stamps step.end.announcement on [ball_flight] instead;
 * this covers ballManager / ShotAnimationSystem / fastBreak paths.
 */
export function announceAirballIfNeeded(turnData, scene, context = {}) {
  if (!turnData || !scene) return;
  if (String(turnData.shot_variant || '').toUpperCase() !== 'AIRBALL') return;
  if (String(turnData.result_type || '').toUpperCase() === 'MAKE') return;
  if (turnData._airballAnnounced) return;
  turnData._airballAnnounced = true;
  announceGameEvent('AIRBALL', turnData, scene, context);
}

function handleAirballAnnouncement(turnData, scene, context, offenseTeam) {
  const shooterId = context.shooterId || turnData.shooter_id;
  let playerData = null;

  if (scene && shooterId) {
    const shooterSprite = scene.playerSprites?.[shooterId];
    if (shooterSprite) {
      playerData = {
        playerId: shooterId,
        photo: shooterSprite.photo || null,
        teamName: shooterSprite.team_id,
        secondaryColor: getSecondaryColorForTeam(scene, shooterSprite.team_id),
      };
    }
  }

  // `airball.wav` fires from the shot-result SFX at ball-miss. The announcement
  // additionally plays `airball-emotion.wav` (a reaction stinger) at overlay
  // mount via meta.sfx — see SFX_System.md "Airball Announce".
  showAnnouncement('Airball!', offenseTeam, playerData, { sfx: 'airball-emotion.wav', scene });
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

  showAnnouncement("Shooting Foul!", 'neutral', playerData, { sfx: 'whistle-1-lowervol.wav' });
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

  const foulText = turnData?.otb_foul ? "Over The Back!" : pickOffensiveFoulAnnouncementText(turnData);
  showAnnouncement(foulText, defenseTeam, playerData, { sfx: 'whistle-1-lowervol.wav' });

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

  const foulText = turnData?.otb_foul
    ? "Over The Back!"
    : (turnData?.quick_foul
      ? "Quick Foul!"
      : (turnData?.reach_in_foul ? "Reaching In!" : pickDefensiveFoulAnnouncementText(turnData)));
  showAnnouncement(foulText, offenseTeam, playerData, { sfx: 'whistle-1-lowervol.wav' });

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

  // CHARGE plays both the foul whistle and the dedicated stinger
  // (`duke-charging.wav` per SFX_System.md). Payload carries both;
  // court.html plays each at mount.
  showAnnouncement("CHARGE!", defenseTeam, playerData, {
    sfx: ['whistle-1-lowervol.wav', 'duke-charging.wav'],
  });

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

  showAnnouncement("BLOCKING FOUL!", offenseTeam, playerData, { sfx: 'whistle-1-lowervol.wav' });

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

  // Steal voice tied to the announce appearance — court.html plays `meta.sfx` at
  // overlay mount (SFX_System.md §Steal / §Interception Announce). A pass
  // interception swaps the headline + voice; a reach-in/strip stays "STEAL!".
  const interception = isPassInterception(turnData, context);
  showAnnouncement(interception ? "INTERCEPTION!" : "STEAL!", defenseTeam, playerData, {
    sfx: interception ? resolveInterceptionSfxFile() : resolveStealSfxFile(),
  });

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
        "SHOT_CLOCK": "Shot Clock Violation!",
        "TEN_SECOND": "10-Second Violation!",
        "OVER_BACK": "Over & Back!"
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
      "SHOT_CLOCK": "Shot Clock Violation!",
      "TEN_SECOND": "10-Second Violation!",
      "OVER_BACK": "Over & Back!"
    };
    turnoverText = typeMap[turnoverType] || "TURNOVER!";
  }
  
  // Shot Clock Violation uses whistle-3.mp3; other turnovers use the foul
  // whistle. Carried on payload so court.html plays at overlay mount.
  const turnoverSfxFile = turnoverText === 'Shot Clock Violation!'
    ? 'whistle-3.mp3'
    : 'whistle-1-lowervol.wav';
  showAnnouncement(turnoverText, offenseTeam, playerData, { sfx: turnoverSfxFile });
}
