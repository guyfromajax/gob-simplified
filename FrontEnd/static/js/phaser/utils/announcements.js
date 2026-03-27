/**
 * Announcement system for significant game events
 * Shows animated text that pops from scoreboard to center screen
 * Optionally triggers legacy effect hooks (no-ops; feedback is via announcement styling)
 */

import { triggerFoulEffect, triggerTurnoverEffect, triggerMadeShotFlash } from '../animation/negativeActionEffects.js';
import gameStore from '../../state/gameStore.js';
import { ENABLE_FAST_BREAK_ENTRY_ANNOUNCEMENTS } from '../constants/fastBreakConstants.js';
import { isBonusFreeThrowFoulTurn } from './foulAnnouncementClassifier.js';
import {
  pickOffensiveFoulAnnouncementText,
  pickDefensiveFoulAnnouncementText,
} from './foulAnnouncementLanguage.js';

let currentAnnouncement = null;

function getPlayerJerseyValue(player) {
  if (!player) return '';
  if (typeof player.jersey === 'number') return String(player.jersey);
  if (player.jersey !== undefined && player.jersey !== null && player.jersey !== '') return String(player.jersey);
  if (typeof player.jerseyNumber === 'number') return String(player.jerseyNumber);
  if (player.jerseyNumber !== undefined && player.jerseyNumber !== null && player.jerseyNumber !== '') return String(player.jerseyNumber);
  if (typeof player.jersey_number === 'number') return String(player.jersey_number);
  if (player.jersey_number !== undefined && player.jersey_number !== null && player.jersey_number !== '') return String(player.jersey_number);
  return '';
}

function getPlayerLastName(player) {
  if (!player) return '';
  const directLastName = String(player.last_name || player.lastName || '').trim();
  if (directLastName) return directLastName;
  const rawName = String(player.name || '').trim();
  if (!rawName) return '';
  const parts = rawName.split(/\s+/).filter(Boolean);
  return parts.length ? parts[parts.length - 1] : '';
}

function getPlayerPosition(player) {
  if (!player) return '';
  const p = String(player.position || player.primary_position || player.pos || '').trim().toUpperCase();
  if (p) return p;
  return '';
}

function findRosterPlayer(playerId) {
  if (!playerId) return null;
  const rosters = gameStore.getRosters() || {};
  const allPlayers = []
    .concat(Array.isArray(rosters.home?.players) ? rosters.home.players : [])
    .concat(Array.isArray(rosters.away?.players) ? rosters.away.players : []);
  return allPlayers.find((player) => String(player?.playerId || player?._id || player?.id) === String(playerId)) || null;
}

function buildAnnouncementPlayerLabel(playerData) {
  if (!playerData) return '';
  const rosterPlayer = findRosterPlayer(playerData.playerId);
  const jersey = getPlayerJerseyValue(rosterPlayer || playerData);
  const lastName = getPlayerLastName(rosterPlayer || playerData);
  if (!jersey && !lastName) return '';
  if (!jersey) return lastName;
  if (!lastName) return `#${jersey}`;
  return `#${jersey} ${lastName}`;
}

function createPlayerAnnouncementCard(playerData, scale = 1.0) {
  const wrapper = document.createElement('div');
  wrapper.className = 'announcement-player-card';
  wrapper.style.display = 'flex';
  wrapper.style.flexDirection = 'column';
  wrapper.style.alignItems = 'center';
  wrapper.style.justifyContent = 'flex-start';
  wrapper.style.gap = `${Math.max(4, Math.round(6 * scale))}px`;
  wrapper.style.flexShrink = '0';

  const container = document.createElement('div');
  container.className = 'announcement-headshot';
  container.style.width = `${60 * scale}px`;
  container.style.height = `${60 * scale}px`;
  container.style.flexShrink = '0';
  container.style.backgroundColor = playerData.secondaryColor || '#333333';
  container.style.backgroundSize = 'cover';
  container.style.backgroundPosition = 'center';

  const img = document.createElement('img');
  img.src = getPlayerImageUrl(playerData.photo, playerData.playerId);
  img.alt = 'Player';
  img.style.width = '100%';
  img.style.height = '100%';
  img.style.objectFit = 'cover';
  img.onerror = () => {
    img.src = getPlayerImageUrl(null, null);
  };
  container.appendChild(img);
  wrapper.appendChild(container);

  const labelText = buildAnnouncementPlayerLabel(playerData);
  if (labelText) {
    const label = document.createElement('div');
    label.className = 'announcement-player-label';
    label.textContent = labelText;
    label.style.fontSize = `${Math.max(0.7, 0.85 * scale)}rem`;
    label.style.fontWeight = '700';
    label.style.lineHeight = '1';
    label.style.textAlign = 'center';
    label.style.color = '#ffffff';
    label.style.textShadow = '0 1px 2px rgba(0, 0, 0, 0.8)';
    label.style.whiteSpace = 'nowrap';
    wrapper.appendChild(label);
  }

  return wrapper;
}

/** Build player image URL with static prefix (localhost vs production). Prefer explicit photo; else /players/{playerId}.png when id known; else generic. Card img onerror maps to generic. */
function getPlayerImageUrl(photo, playerId) {
  const base = (typeof window !== 'undefined' && window.API_CONFIG?.buildStaticPath)
    ? window.API_CONFIG.buildStaticPath('/images/players/')
    : ((typeof window !== 'undefined' && (window.location?.hostname === 'localhost' || window.location?.hostname === '127.0.0.1')) ? '/static/images/players/' : '/images/players/');
  const filename = playerId ? `${playerId}.png` : 'generic_headshot.png';
  return photo || `${base}${filename}`;
}

/** Resolve team secondary color from scene (home/away by team_id). Returns hex string or fallback. */
export function getSecondaryColorForTeam(scene, teamId) {
  if (!scene?.simData || teamId == null) return '#333333';
  const colors = gameStore.getColors();
  const homeId = scene.simData.home_team_id;
  const awayId = scene.simData.away_team_id;
  const isHome = String(teamId) === String(homeId);
  const side = isHome ? colors.home : colors.away;
  return side?.secondary_color || '#333333';
}

/**
 * Trigger visual effects for fouls/turnovers
 * @param {Object} scene - Phaser scene
 * @param {string} playerId - Player ID to apply effect to
 * @param {string} effectType - 'foul' or 'turnover'
 */
function triggerVisualEffect(scene, playerId, effectType) {
  if (!scene || !playerId) return;
  
  const sprite = scene.playerSprites?.[playerId];
  if (!sprite) return;
  
  // Call the appropriate effect function
  if (effectType === 'foul') {
    triggerFoulEffect(scene, playerId);
  } else if (effectType === 'turnover') {
    triggerTurnoverEffect(scene, playerId);
  }
}

/**
 * Show AND-1 announcement with two rows (made shot + foul) — uses new announcement strip.
 * @param {string} team - Team that made the shot
 * @param {Object} shooterData - Shooter data { playerId, photo, teamName }
 * @param {Object} foulPlayerData - Fouling player data { playerId, photo, teamName }
 */
export function showAndOneAnnouncement(team, shooterData, foulPlayerData) {
  const shooterRoster = shooterData ? findRosterPlayer(shooterData.playerId) : null;
  const foulerRoster = foulPlayerData ? findRosterPlayer(foulPlayerData.playerId) : null;
  const shooter = shooterRoster || shooterData;
  const fouler = foulerRoster || foulPlayerData;
  const data = {
    type: 'foul',
    foulEventText: "It's Good!",
    shooterPhotoUrl: getPlayerImageUrl(shooterData?.photo, shooterData?.playerId),
    shooterJersey: getPlayerJerseyValue(shooter) ? `#${getPlayerJerseyValue(shooter)}` : '',
    shooterLastName: getPlayerLastName(shooter) || '',
    foulerPhotoUrl: getPlayerImageUrl(foulPlayerData?.photo, foulPlayerData?.playerId),
    foulerJersey: getPlayerJerseyValue(fouler) ? `#${getPlayerJerseyValue(fouler)}` : '',
    foulerLastName: getPlayerLastName(fouler) || '',
  };
  try {
    const sfx = new Audio('/sounds/' + encodeURIComponent('whistle-1.mp3'));
    sfx.volume = 0.7;
    sfx.play().catch(() => {});
  } catch (e) {}
  if (typeof window !== 'undefined' && window.showAnnouncementOverlay) {
    window.showAnnouncementOverlay(data);
  }
}

/**
 * Helper to create headshot element
 * @param {Object} playerData - { playerId, photo, teamName, secondaryColor }
 * @param {number} scale - Size multiplier (1.0 = full, 0.6 = 60%)
 * Headshot background uses team secondary color (no team background image).
 */
function createHeadshotElement(playerData, scale = 1.0) {
  return createPlayerAnnouncementCard(playerData, scale);
}

/**
 * Show an announcement — uses new announcement strip (standard variant).
 * @param {string} text - Text to display (e.g., "Fast Break!", "It's Good!")
 * @param {string} team - 'home', 'away', 'defense', or 'neutral' (unused by strip; kept for API)
 * @param {Object} playerData - Optional player data { playerId, photo, teamName } to show headshot
 */
export function showAnnouncement(text, team = 'home', playerData = null) {
  const rosterPlayer = playerData ? findRosterPlayer(playerData.playerId) : null;
  const player = rosterPlayer || playerData;
  const photoUrl = playerData && (playerData.photo || playerData.playerId)
    ? getPlayerImageUrl(playerData.photo, playerData.playerId)
    : '';
  const jerseyVal = getPlayerJerseyValue(player);
  const data = {
    type: 'standard',
    eventText: text || '',
    photoUrl,
    jersey: jerseyVal ? `#${jerseyVal}` : '',
    lastName: getPlayerLastName(player) || '',
    position: getPlayerPosition(player) || '',
  };
  const isFoulAnnouncement = text && (text.includes('FOUL') || text.includes('Foul'));
  const isDeadBallTurnoverAnnouncement = text && text.includes('Turnover') && text !== 'STEAL!';
  const isShotClockViolation = text === 'Shot Clock Violation!';
  if (isShotClockViolation) {
    try {
      const sfx = new Audio('/sounds/' + encodeURIComponent('whistle-3.mp3'));
      sfx.volume = 0.7;
      sfx.play().catch(() => {});
    } catch (e) {}
  } else if (isFoulAnnouncement || isDeadBallTurnoverAnnouncement) {
    try {
      const sfx = new Audio('/sounds/' + encodeURIComponent('whistle-1.mp3'));
      sfx.volume = 0.7;
      sfx.play().catch(() => {});
    } catch (e) {}
  }
  if (typeof window !== 'undefined' && window.showAnnouncementOverlay) {
    window.showAnnouncementOverlay(data);
  }
}

/**
 * Determine and show announcement based on turn data
 * @param {Object} turnData - Turn data from backend
 * @param {string} timing - 'start' or 'end' of turn
 * @param {string} homeTeamId - Home team ID for determining team colors
 * @param {Object} scene - Optional scene object for accessing player data
 */
export function announceFromTurnData(turnData, timing = 'start', homeTeamId = null, scene = null) {
  // 🔍 DEBUG: Log all announcement calls to track duplicates
  console.log('📢 [ANNOUNCEMENT CALL]', {
    result_type: turnData?.result_type,
    play_type: turnData?.play_type,
    timing: timing,
    text: turnData?.text?.substring(0, 50) || 'N/A',
    turn_index: turnData?.turn_index || turnData?.index,
    caller: new Error().stack.split('\n')[2]?.trim() // Show caller
  });

  // Determine which team triggered the event
  const offenseTeamId = turnData.possession_team_id;
  const isHomeTeamEvent = homeTeamId && String(offenseTeamId) === String(homeTeamId);
  const offenseTeam = isHomeTeamEvent ? 'home' : 'away';
  const defenseTeam = isHomeTeamEvent ? 'away' : 'home';
  
  if (timing === 'start') {
    // Announcements at turn start
    if (turnData.fast_break && ENABLE_FAST_BREAK_ENTRY_ANNOUNCEMENTS) {
      showAnnouncement("Fast Break!", offenseTeam);
      // Don't return - may have more announcements at end
    }
    
    // Check multiple ways FCP/HCT can be indicated
    // Note: Don't return after these - shots from Press/Trap should also announce results
    // ✅ FIX: Only announce when pressure is actually active, not when it's just being set up
    // next_defensive_setup indicates what will happen NEXT, not what's happening NOW
    // Only check next_defensive_setup for BASELINE_INBOUND turns (inbound passes that set up pressure)
    // For all other turns (HCO, MAKE, MISS, etc.), only check actual pressure flags (fcp_shot, hct_shot, fcp_foul, hct_foul)
    const isInboundSettingUpPressure = turnData.result_type === 'BASELINE_INBOUND';
    
    // ✅ SS&S: Only announce pressure context ONCE when it's first applied (BASELINE_INBOUND)
    // Don't re-announce for every subsequent turn in the pressure sequence
    // Removed text.includes('PRESS!') and text.includes('TRAP!') checks to prevent duplicates
    if (isInboundSettingUpPressure && turnData.next_defensive_setup === 'FCP') {
      showAnnouncement("Press!", 'defense');
      // Don't return - may have shot result to announce later
    }
    
    if (isInboundSettingUpPressure && turnData.next_defensive_setup === 'HCT') {
      showAnnouncement("Trap!", 'defense');
      // Don't return - may have shot result to announce later
    }
  } else if (timing === 'end') {
    // Announcements at turn end (after animation)
    // Note: "It's Good!" and "Rebound!" are now handled directly in ballManager.js
    // for precise timing when ball reaches rim/rebounder

    // Charge: offensive foul on drive - announce "Charge!" (not "Offensive Foul!")
    if (turnData.result_type === 'CHARGE') {
      const foulerId = turnData.foul_player_id || turnData.shooter_id;
      let playerData = null;
      if (scene && foulerId) {
        const foulPlayerSprite = scene.playerSprites?.[foulerId];
        if (foulPlayerSprite) {
          const homeTeamField = scene.simData?.home_team;
          const awayTeamField = scene.simData?.away_team;
          const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
          const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
          const foulPlayerTeamName = foulPlayerSprite.team_id === scene.homeTeamId ? homeTeamName : awayTeamName;
          playerData = {
            playerId: foulerId,
            photo: foulPlayerSprite?.photo || null,
            teamName: foulPlayerTeamName,
            secondaryColor: getSecondaryColorForTeam(scene, foulPlayerSprite.team_id)
          };
        }
      }
      showAnnouncement("CHARGE!", defenseTeam, playerData);
      if (scene && foulerId && typeof triggerVisualEffect === 'function') {
        triggerVisualEffect(scene, foulerId, 'foul');
      }
      return;
    }
    
    if (turnData.result_type === 'FOUL') {
      // FOUL turns should always announce foul type, including bonus fouls that lead to free throws.
      // True shooting fouls are emitted as shot result turns (MAKE/MISS) and are announced there.
      const isBonusFoul = isBonusFreeThrowFoulTurn(turnData);
      const foulTeam = turnData.foul_team || 'OFFENSE'; // Default to offense if not specified
      const isQuickFoul = !!turnData.quick_foul;
      const isBlockingFoul = foulTeam === 'DEFENSE' && turnData.text?.toLowerCase().includes('blocking foul');

      // Extract foul player data for headshot display
      let playerData = null;
      if (scene && turnData.foul_player_id) {
        const foulPlayerId = turnData.foul_player_id;
        const foulPlayerSprite = scene.playerSprites?.[foulPlayerId];
        const foulPlayerTeamId = foulPlayerSprite?.team_id;
        
        // Handle both new nested structure (object) and old flat structure (string)
        const homeTeamField = scene.simData?.home_team;
        const awayTeamField = scene.simData?.away_team;
        const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
        const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
        const foulPlayerTeamName = foulPlayerTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;

        playerData = {
          playerId: foulPlayerId,
          photo: foulPlayerSprite?.photo || null,
          teamName: foulPlayerTeamName,
          secondaryColor: getSecondaryColorForTeam(scene, foulPlayerTeamId)
        };
      }

      if (isBlockingFoul) {
        showAnnouncement("BLOCKING FOUL!", offenseTeam, playerData);
      } else if (foulTeam === 'OFFENSE') {
        // Offensive foul - show in defense team color (they benefited)
        showAnnouncement(pickOffensiveFoulAnnouncementText(turnData), defenseTeam, playerData);
      } else {
        // Defensive foul: situational Force Foul → "Quick Foul!"; else "DEFENSIVE FOUL!"
        // Bonus fouls (FOUL -> FREE_THROW) stay in this path and should not be reclassified as shooting fouls.
        let defensiveFoulText = pickDefensiveFoulAnnouncementText(turnData);
        if (isQuickFoul) defensiveFoulText = "Quick Foul!";
        if (isBonusFoul && !isQuickFoul) defensiveFoulText = pickDefensiveFoulAnnouncementText(turnData);
        showAnnouncement(defensiveFoulText, offenseTeam, playerData);
      }
      
      // Trigger visual effect on fouling player
      if (scene && turnData.foul_player_id) {
        triggerVisualEffect(scene, turnData.foul_player_id, 'foul');
      }
      return;
    }
    
    // Handle STEAL announcements (result_type can be 'STEAL' from FCP/HCT or 'TURNOVER' from regular play)
    if (turnData.result_type === 'STEAL' || (turnData.result_type === 'TURNOVER' && turnData.text?.toLowerCase().includes('steal'))) {
      let playerData = null;
      
      if (scene && turnData.defender_id) {
        const stealerId = turnData.defender_id;
        const stealerSprite = scene.playerSprites?.[stealerId];
        const stealerTeamId = stealerSprite?.team_id;
        
        // Handle both new nested structure (object) and old flat structure (string)
        const homeTeamField = scene.simData?.home_team;
        const awayTeamField = scene.simData?.away_team;
        const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
        const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
        const stealerTeamName = stealerTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;

        playerData = {
          playerId: stealerId,
          photo: stealerSprite?.photo || null,
          teamName: stealerTeamName,
          secondaryColor: getSecondaryColorForTeam(scene, stealerTeamId)
        };
      }

      showAnnouncement("STEAL!", defenseTeam, playerData);
      
      // Trigger visual effect on turnover victim (ball handler who got stolen from)
      if (scene && turnData.victim_id) {
        triggerVisualEffect(scene, turnData.victim_id, 'turnover');
      }
      return;
    }
    
    // Handle all turnover types: TURNOVER, DEAD BALL (from HCT/FCP), and non-steal STEAL results
    if (turnData.result_type === 'TURNOVER' || turnData.result_type === 'DEAD BALL') {
      // Non-steal turnovers - show victim's photo in offense team color
      let playerData = null;
      
      if (scene && turnData.victim_id) {
        const victimId = turnData.victim_id;
        const victimSprite = scene.playerSprites?.[victimId];
        const victimTeamId = victimSprite?.team_id;
        
        // Handle both new nested structure (object) and old flat structure (string)
        const homeTeamField = scene.simData?.home_team;
        const awayTeamField = scene.simData?.away_team;
        const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
        const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
        const victimTeamName = victimTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;

        playerData = {
          playerId: victimId,
          photo: victimSprite?.photo || null,
          teamName: victimTeamName,
          secondaryColor: getSecondaryColorForTeam(scene, victimTeamId)
        };
      }

      // Determine turnover type from dedicated field or text parsing
      // ✅ FIX: For dead ball turnovers, randomly choose "Travel!" or "Double Dribble!" (50/50)
      let turnoverText = "TURNOVER!";
      
      // Check if this is a dead ball turnover (not a steal)
      const isDeadBallTurnover = turnData.result_type === 'DEAD BALL' || 
                                 (turnData.result_type === 'TURNOVER' && 
                                  !turnData.text?.toLowerCase().includes('steal') && 
                                  !turnData.stealer_id && 
                                  !turnData.defender_id);
      
      if (isDeadBallTurnover && !turnData.turnover_type) {
        // Randomly choose between Travel and Double Dribble (50/50)
        turnoverText = Math.random() < 0.5 ? "Travel!" : "Double Dribble!";
      } else if (turnData.turnover_type) {
        // Check if backend provides specific turnover_type field
        const typeMap = {
          "TRAVEL": "Travel!",
          "DOUBLE_DRIBBLE": "Double Dribble!",
          "OUT_OF_BOUNDS": "OUT OF BOUNDS!",
          "BAD_PASS": "BAD PASS!",
          "PALMING": "PALMING!",
          "ILLEGAL_DRIBBLE": "ILLEGAL DRIBBLE!",
          "SHOT_CLOCK": "SHOT CLOCK VIOLATION!",
          "BACKCOURT": "BACKCOURT VIOLATION!"
        };
        turnoverText = typeMap[turnData.turnover_type] || "TURNOVER!";
      } else {
        // Fallback: parse from text
        const textLower = turnData.text?.toLowerCase() || '';
        if (textLower.includes('travel')) {
          turnoverText = "Travel!";
        } else if (textLower.includes('double dribble')) {
          turnoverText = "Double Dribble!";
        } else if (textLower.includes('out of bounds')) {
          turnoverText = "OUT OF BOUNDS!";
        } else if (textLower.includes('errant pass') || textLower.includes('bad pass')) {
          turnoverText = "BAD PASS!";
        } else if (textLower.includes('dribbles it off his foot')) {
          turnoverText = "TURNOVER!";
        } else if (textLower.includes('shot clock')) {
          turnoverText = "SHOT CLOCK VIOLATION!";
        }
      }
      
      console.log(`📢 Announcing turnover: ${turnoverText} (result_type: ${turnData.result_type}, source: ${turnData.offensive_state || 'HCO'})`);
      showAnnouncement(turnoverText, offenseTeam, playerData);
      
      // Trigger visual effect on turnover victim
      if (scene && turnData.victim_id) {
        triggerVisualEffect(scene, turnData.victim_id, 'turnover');
      }
      return;
    }
  }
}
