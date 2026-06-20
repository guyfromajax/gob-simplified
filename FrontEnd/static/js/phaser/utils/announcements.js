/**
 * Announcement system for significant game events
 * Shows animated text that pops from scoreboard to center screen
 */

import gameStore from '../../state/gameStore.js';
import { isFastBreakEntryAnnouncementsEnabled } from '../constants/fastBreakConstants.js';
import { isBonusFreeThrowFoulTurn } from './foulAnnouncementClassifier.js';
import {
  pickOffensiveFoulAnnouncementText,
  pickDefensiveFoulAnnouncementText,
} from './foulAnnouncementLanguage.js';
import {
  resolveStealSfxFile,
  resolveSecondaryAnnounceCourtSfxFile,
  resolveAnnounceMetaCourtSfxFile,
} from './gameSfx.js';

let currentAnnouncement = null;

export function playAnnouncementSfx(kind) {
  const filename = kind === 'shot_clock_violation' ? 'whistle-3.mp3' : 'whistle-1-lowervol.wav';
  try {
    const sfx = new Audio('/sounds/' + encodeURIComponent(filename));
    sfx.volume = 0.7;
    sfx.play().catch(() => {});
  } catch (e) {}
}

/**
 * Normalize the caller-supplied `meta.sfx` into a value `court.html` can play:
 *   - filename string (`.wav` / `.mp3`) → as-is
 *   - array (any mix of filenames / legacy kinds) → mapped to filename array
 *   - legacy kind string (`'foul'` / `'shot_clock_violation'`) → resolved filename
 *   - anything else → null
 *
 * Used by both `showAnnouncement` and `showAndOneAnnouncement` so primary-tier
 * SFX dispatch goes through one path: caller → `data.sfx` → court.html mount.
 */
function resolvePrimarySfxFromMeta(raw) {
  if (!raw) return null;
  if (Array.isArray(raw)) {
    const mapped = raw.map(resolvePrimarySfxFromMeta).filter(Boolean);
    return mapped.length ? mapped : null;
  }
  if (typeof raw !== 'string') return null;
  if (/\.(wav|mp3)$/i.test(raw)) return raw;
  return resolveAnnounceMetaCourtSfxFile(raw);
}

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

function resolveAnnouncementScene(meta) {
  return meta?.scene
    || (typeof window !== 'undefined' ? window.currentGameScene : null)
    || null;
}

function findPlayerSprite(scene, playerId) {
  if (!scene?.playerSprites || playerId == null || playerId === '') return null;
  const sid = String(playerId);
  const playerSprites = scene.playerSprites;
  let sprite = playerSprites[sid] || playerSprites[playerId] || null;
  if (!sprite) {
    for (const [key, candidate] of Object.entries(playerSprites)) {
      if (!candidate) continue;
      const candidateId = String(candidate.playerId ?? candidate.id ?? key);
      if (candidateId === sid) {
        sprite = candidate;
        break;
      }
    }
  }
  return sprite;
}

/**
 * Resolve which home/away side a featured player belongs to for initials-tile colors.
 * Prefers on-court sprite metadata, then team_id vs sim home id, then roster membership.
 * Falls back to `fallbackTeamSide` only when player membership cannot be determined.
 *
 * @param {import('phaser').Scene|null} scene
 * @param {string|number|null|undefined} playerId
 * @param {Object|null|undefined} playerData
 * @param {'home'|'away'|string|null|undefined} fallbackTeamSide
 * @returns {'home'|'away'|null}
 */
function resolvePlayerTeamSide(scene, playerId, playerData = null, fallbackTeamSide = null) {
  if (playerId == null || playerId === '') {
    return fallbackTeamSide === 'home' || fallbackTeamSide === 'away' ? fallbackTeamSide : null;
  }

  const sid = String(playerId);
  const sprite = findPlayerSprite(scene, sid);

  if (sprite?.team === 'home' || sprite?.team === 'away') {
    return sprite.team;
  }

  const homeId = scene?.simData?.home_team_id ?? scene?.homeTeamId;
  const teamId = sprite?.team_id ?? playerData?.teamId ?? playerData?.team_id;
  if (homeId != null && teamId != null) {
    return String(teamId) === String(homeId) ? 'home' : 'away';
  }

  const rosterPlayer = findRosterPlayer(sid);
  if (rosterPlayer) {
    const rosters = gameStore.getRosters() || {};
    const inHome = (rosters.home?.players || []).some(
      (player) => String(player?.playerId || player?._id || player?.id) === sid,
    );
    if (inHome) return 'home';
    const inAway = (rosters.away?.players || []).some(
      (player) => String(player?.playerId || player?._id || player?.id) === sid,
    );
    if (inAway) return 'away';
  }

  if (fallbackTeamSide === 'home' || fallbackTeamSide === 'away') {
    return fallbackTeamSide;
  }
  return null;
}

function buildHeadshotInitialsForPlayer(scene, player, playerId, fallbackTeamSide) {
  const side = resolvePlayerTeamSide(scene, playerId, player, fallbackTeamSide);
  return buildHeadshotInitialsInfo(player, side);
}

/**
 * Resolve stopper portrait metadata for secondary Great Stop! ribbons.
 * Does not require scene.playerInfo — playerId alone is enough for headshot URL fallback.
 */
export function buildSecondaryStopperPlayerData(scene, stopperId, sprites = null) {
  if (stopperId == null || stopperId === '') return null;
  const sid = String(stopperId);
  const playerSprites = sprites || scene?.playerSprites || {};
  const playerInfo = scene?.playerInfo || {};

  let sprite = playerSprites[sid] || playerSprites[stopperId] || null;
  if (!sprite) {
    for (const [key, candidate] of Object.entries(playerSprites)) {
      if (!candidate) continue;
      const candidateId = String(candidate.playerId ?? candidate.id ?? key);
      if (candidateId === sid) {
        sprite = candidate;
        break;
      }
    }
  }

  let info = playerInfo[sid] || playerInfo[stopperId] || null;
  if (!info) {
    for (const [key, value] of Object.entries(playerInfo)) {
      if (String(key) === sid) {
        info = value;
        break;
      }
    }
  }

  return {
    playerId: sid,
    photo: sprite?.photo || info?.photo || null,
    name: sprite?.name || info?.name || '',
    jersey: info?.jersey ?? sprite?.jersey ?? '',
  };
}

/**
 * Build the team-aware initials-tile descriptor that court.html's
 * applyHeadshotFallback consumes when a per-player photo fails to load.
 * Mirrors the v2 on-court sprite fallback rule (home → tile=secondary/text=primary,
 * away → tile=primary/text=secondary). Returns null when team colors or name are
 * unresolvable — applyHeadshotFallback then falls back to generic_headshot.png.
 *
 * @param {Object|null} player - Roster or playerData object (used for name resolution)
 * @param {'home'|'away'|string} teamSide - Which team the player is on
 * @returns {{isHome:boolean, primaryColor:string, secondaryColor:string, name:string}|null}
 */
function buildHeadshotInitialsInfo(player, teamSide) {
  const side = teamSide === 'home' ? 'home' : (teamSide === 'away' ? 'away' : null);
  if (!side) return null;
  const colors = gameStore.getColors();
  const teamColors = side === 'home' ? colors?.home : colors?.away;
  if (!teamColors?.primary_color || !teamColors?.secondary_color) return null;
  let name = player?.name;
  if (!name && (player?.first_name || player?.last_name)) {
    name = `${player.first_name || ''} ${player.last_name || ''}`.trim();
  }
  return {
    isHome: side === 'home',
    primaryColor: teamColors.primary_color,
    secondaryColor: teamColors.secondary_color,
    name: name || '',
  };
}

/**
 * Normalize player headshot paths for the current host.
 * On localhost (Flask static), ensure `/static/` prefix; on production, strip it
 * so paths resolve against the deployed asset root (see preloadPlayerHeadshots.js).
 */
export function normalizeHeadshotUrl(url) {
  if (!url || typeof url !== 'string') return url;
  const isLocalhost =
    typeof window !== 'undefined' &&
    (window.location?.hostname === 'localhost' ||
      window.location?.hostname === '127.0.0.1');
  if (!isLocalhost && url.startsWith('/static/')) {
    return url.replace('/static', '');
  }
  if (isLocalhost && !url.startsWith('/static/') && url.startsWith('/images/')) {
    return `/static${url}`;
  }
  return url;
}

/** Build player image URL with static prefix (localhost vs production). Prefer explicit photo; else /players/{playerId}.png when id known; else generic. Card img onerror maps to generic. */
export function getPlayerImageUrl(photo, playerId) {
  const base = (typeof window !== 'undefined' && window.API_CONFIG?.buildStaticPath)
    ? window.API_CONFIG.buildStaticPath('/images/players/')
    : ((typeof window !== 'undefined' && (window.location?.hostname === 'localhost' || window.location?.hostname === '127.0.0.1')) ? '/static/images/players/' : '/images/players/');
  const filename = playerId ? `${playerId}.png` : 'generic_headshot.png';
  return normalizeHeadshotUrl(photo || `${base}${filename}`);
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
/**
 * Show AND-1 announcement with two rows (made shot + foul) — uses new announcement strip.
 * @param {string} team - Team that made the shot
 * @param {Object} shooterData - Shooter data { playerId, photo, teamName }
 * @param {Object} foulPlayerData - Fouling player data { playerId, photo, teamName }
 */
export function showAndOneAnnouncement(team, shooterData, foulPlayerData, meta = null) {
  const scene = resolveAnnouncementScene(meta);
  const shooterRoster = shooterData ? findRosterPlayer(shooterData.playerId) : null;
  const foulerRoster = foulPlayerData ? findRosterPlayer(foulPlayerData.playerId) : null;
  const shooter = shooterRoster || shooterData;
  const fouler = foulerRoster || foulPlayerData;
  const shooterFallback = team === 'away' ? 'away' : 'home';
  const shooterTeamSide = resolvePlayerTeamSide(
    scene,
    shooterData?.playerId,
    shooterData,
    shooterFallback,
  );
  const foulerTeamSide = resolvePlayerTeamSide(
    scene,
    foulPlayerData?.playerId,
    foulPlayerData,
    shooterTeamSide === 'home' ? 'away' : shooterTeamSide === 'away' ? 'home' : null,
  );
  const data = {
    type: 'foul',
    foulEventText: "It's Good!",
    shooterPhotoUrl: getPlayerImageUrl(shooterData?.photo, shooterData?.playerId),
    shooterHeadshotInitials: shooterData ? buildHeadshotInitialsForPlayer(scene, shooter, shooterData.playerId, shooterFallback) : null,
    shooterJersey: getPlayerJerseyValue(shooter) ? `#${getPlayerJerseyValue(shooter)}` : '',
    shooterLastName: getPlayerLastName(shooter) || '',
    foulerPhotoUrl: getPlayerImageUrl(foulPlayerData?.photo, foulPlayerData?.playerId),
    foulerHeadshotInitials: foulPlayerData ? buildHeadshotInitialsForPlayer(scene, fouler, foulPlayerData.playerId, foulerTeamSide) : null,
    foulerJersey: getPlayerJerseyValue(fouler) ? `#${getPlayerJerseyValue(fouler)}` : '',
    foulerLastName: getPlayerLastName(fouler) || '',
    // AND-1 whistle carried on payload — court.html plays at overlay mount
    // per SFX_System.md. Caller override via `meta.sfx`.
    sfx: resolvePrimarySfxFromMeta(meta?.sfx) ?? 'whistle-1-lowervol.wav',
  };
  if (typeof window !== 'undefined' && window.showAnnouncementOverlay) {
    window.showAnnouncementOverlay(data);
  }
}

/**
 * Resolve the team primary color used for the secondary ribbon's left stripe / gradient.
 * Mirrors the existing convention (gameStore.getColors().{home|away}.primary_color)
 * already used across the app (bootGame.js, createPhaserPlayer.js, etc.).
 * @param {string} team 'home' | 'away' | anything else (defaults to orange accent)
 * @returns {string} hex color
 */
function resolveSecondaryStripeColor(team) {
  const colors = gameStore.getColors() || {};
  if (team === 'home') return colors.home?.primary_color || '#F79420';
  if (team === 'away') return colors.away?.primary_color || '#F79420';
  return '#F79420';
}

/**
 * Show a SECONDARY announcement — top-edge ribbon under the scoreboard.
 *
 * Used for non-critical context announcements that should not block sprite action
 * in the center of the court: Press, Trap, Fast Break (start), Slow It Down,
 * Quick Shot, Final Shot, FB Outlet Pass Denied, Fast Break / No Fast Break
 * (RR decision), and the FB defensive stop ("Great Stop!").
 *
 * Callers should pass 'home' or 'away' (NOT 'defense' / 'neutral') so the
 * left-edge stripe and gradient can resolve to the initiating team's primary
 * color. Dispatchers that currently track which side is defending should pass
 * that resolved side (e.g. defenseTeam) rather than the abstract 'defense'.
 *
 * @param {string} text Headline text (e.g., "Fast Break!"). Rendered upper-case.
 * @param {string} team 'home' | 'away'. Drives the left stripe + gradient color.
 * @param {Object|null} playerData Optional { playerId, photo, teamName } — when
 *   present, the ribbon shows the player's headshot + #jersey lastName chip.
 * @param {Object|null} meta Optional metadata:
 *   - `decisionPillText`, `decisionPillTone: 'good'|'bad'` — renders the decision pill
 *     in the lower-right corner of the ribbon using the existing pill design.
 *   - `eventSubtitle` — small-caps secondary label rendered to the right of the
 *     headline at 50% font-size (e.g. play name "Rim Runner" after "Fast Break!").
 */
export function showSecondaryAnnouncement(text, team = 'home', playerData = null, meta = null) {
  const scene = resolveAnnouncementScene(meta);
  const rosterPlayer = playerData ? findRosterPlayer(playerData.playerId) : null;
  const player = rosterPlayer || playerData;
  const photoUrl = playerData && (playerData.photo || playerData.playerId)
    ? getPlayerImageUrl(playerData.photo, playerData.playerId)
    : '';
  const jerseyVal = getPlayerJerseyValue(player);
  const lastName = getPlayerLastName(player) || '';
  // Single source of truth for secondary-tier SFX. Resolution order:
  //   1. `meta.sfx` filename string (".wav"/".mp3") — caller passes directly.
  //   2. `meta.sfx` legacy key string (no extension) — backend-stamped on
  //      schema announcements (e.g. "fb_outlet_denied_court", "steal").
  //   3. Headline-based fallback (Press!/Trap!/Fast Break!/etc.) — applies
  //      once-per-turn dedupe for the three repeating stingers.
  // `court.html`'s secondary overlay reads `data.sfx` and plays at mount,
  // synced to the visual entry per SFX_System.md.
  const rawMetaSfx = meta?.sfx;
  let sfxFile = null;
  if (typeof rawMetaSfx === 'string' && rawMetaSfx) {
    sfxFile = /\.(wav|mp3)$/i.test(rawMetaSfx)
      ? rawMetaSfx
      : resolveAnnounceMetaCourtSfxFile(rawMetaSfx);
  }
  if (!sfxFile) {
    sfxFile = resolveSecondaryAnnounceCourtSfxFile(text);
  }
  const data = {
    tier: 'secondary',
    type: 'standard',
    eventText: text || '',
    eventSubtitle: typeof meta?.eventSubtitle === 'string' ? meta.eventSubtitle : '',
    photoUrl,
    headshotInitials: playerData
      ? buildHeadshotInitialsForPlayer(scene, player, playerData.playerId, team)
      : null,
    jersey: jerseyVal ? `#${jerseyVal}` : '',
    lastName,
    teamColor: resolveSecondaryStripeColor(team),
    decisionPillText: typeof meta?.decisionPillText === 'string' ? meta.decisionPillText : '',
    decisionPillTone: meta?.decisionPillTone === 'bad' ? 'bad' : (meta?.decisionPillTone === 'good' ? 'good' : ''),
    // Momentum callout extras (Player_Momentum_System.md): right-side MO chip +
    // hot/cold flavor (drives the headline sigil + chip color). Cyan for cold —
    // never the red "bad" pill treatment.
    moValue: (typeof meta?.moValue === 'number' && Number.isFinite(meta.moValue)) ? meta.moValue : null,
    moFlavor: meta?.moFlavor === 'cold' ? 'cold' : (meta?.moFlavor === 'hot' ? 'hot' : ''),
    sfx: sfxFile,
  };
  if (String(text || '').trim() === 'Great Stop!' && !photoUrl && !lastName) {
    console.warn('[ANN] Great Stop secondary missing headshot payload', {
      playerId: playerData?.playerId ?? null,
      hasPlayerData: !!playerData,
      rosterHit: !!rosterPlayer,
    });
  }
  if (typeof window !== 'undefined' && window.showAnnouncementOverlay) {
    window.showAnnouncementOverlay(data);
  }
}

/**
 * Map a backend `fast_break_play` key to its display label for the secondary
 * announcement subtitle ("Fast Break!  Rim Runner"). Returns '' for unknown
 * keys and for `after_steal` (the preceding "Steal!" already conveys context,
 * so an additional subtitle would be redundant).
 *
 * Canonical keys mirror BackEnd/constants/fast_break_play_types.py.
 *
 * @param {string|null|undefined} playKey
 * @returns {string}
 */
export function getFastBreakPlayLabel(playKey) {
  switch (playKey) {
    case 'rim_runner': return 'Rim Runner';
    case 'triangle': return 'Triangle';
    case 'covert_release': return 'Covert Release';
    default: return '';
  }
}

/**
 * Map a backend `hct_trap_play` key to its display label for the secondary "Trap!"
 * announcement subtitle ("Trap!  Straight Pressure"). Returns '' for unknown keys.
 * Same eventSubtitle treatment/placement as the Fast Break play-name subtitle.
 *
 * Canonical keys mirror BackEnd/constants/hct_trap_play_types.py.
 *
 * @param {string|null|undefined} playKey
 * @returns {string}
 */
export function getHctTrapPlayLabel(playKey) {
  switch (playKey) {
    case 'standard_trap': return 'Standard Trap';
    case 'straight_pressure': return 'Straight Pressure';
    case 'diamond': return 'Diamond';
    default: return '';
  }
}

/**
 * Primary "Rebound!" headline when the rebounder secures the ball (center overlay).
 * Idempotent per turn when `turnData` is provided: sets `turnData._reboundHeadlineShown`
 * after a successful display so ballManager, ShotAnimationSystem, FT/FB paths, and
 * `announceGameEvent('REBOUND', ...)` cannot double-fire for the same backend turn.
 *
 * @param {import('phaser').Scene} scene
 * @param {object|null|undefined} turnData
 * @param {object|null|undefined} rebounderSprite
 * @param {string|number|null|undefined} rebounderId - Preferred id when sprite keys omit `playerId`
 * @returns {boolean} true if the headline was shown
 */
export function announceReboundHeadlineIfNeeded(scene, turnData, rebounderSprite, rebounderId = null) {
  if (!scene || !rebounderSprite) return false;
  if (turnData && turnData._reboundHeadlineShown) return false;

  const pid =
    rebounderId != null && rebounderId !== ''
      ? String(rebounderId)
      : String(rebounderSprite.playerId ?? rebounderSprite.id ?? '');
  if (!pid) return false;

  const rebounderTeam = rebounderSprite.team;
  const rebounderTeamId = rebounderSprite.team_id;
  const homeTeamField = scene.simData?.home_team;
  const awayTeamField = scene.simData?.away_team;
  const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
  const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
  const rebounderTeamName =
    rebounderTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;

  const playerData = {
    playerId: pid,
    photo: rebounderSprite.photo || null,
    teamName: rebounderTeamName,
    secondaryColor: getSecondaryColorForTeam(scene, rebounderTeamId),
  };

  showAnnouncement('Rebound!', rebounderTeam, playerData);
  if (turnData) turnData._reboundHeadlineShown = true;
  return true;
}

/**
 * Show an announcement — uses new announcement strip (standard variant).
 * @param {string} text - Text to display (e.g., "Fast Break!", "It's Good!")
 * @param {string} team - Context side for legacy callers ('home'|'away'|'defense'|'neutral').
 *   Does not drive initials-tile colors when `playerData` is present — see
 *   `resolvePlayerTeamSide()` / `buildHeadshotInitialsForPlayer()`.
 * @param {Object} playerData - Optional player data { playerId, photo, teamName } to show headshot
 * @param {Object|null} meta - Optional metadata { decisionPillText, decisionPillTone: 'good'|'bad', scene }
 */
export function showAnnouncement(text, team = 'home', playerData = null, meta = null) {
  const scene = resolveAnnouncementScene(meta);
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
    headshotInitials: playerData
      ? buildHeadshotInitialsForPlayer(scene, player, playerData.playerId, team)
      : null,
    jersey: jerseyVal ? `#${jerseyVal}` : '',
    lastName: getPlayerLastName(player) || '',
    position: getPlayerPosition(player) || '',
    decisionPillText: typeof meta?.decisionPillText === 'string' ? meta.decisionPillText : '',
    decisionPillTone: meta?.decisionPillTone === 'bad' ? 'bad' : (meta?.decisionPillTone === 'good' ? 'good' : ''),
    // Primary-tier SFX carried on payload — court.html plays at overlay mount
    // so audio is synced to the visual entry per SFX_System.md.
    // Accepts: filename string (`.wav`/`.mp3`), filename array, or a legacy
    // kind string (`'foul'` / `'shot_clock_violation'` resolved via
    // `resolveAnnounceMetaCourtSfxFile`).
    sfx: resolvePrimarySfxFromMeta(meta?.sfx),
  };
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

  // SS&S: offense_team_id is canonical; possession_team_id is legacy fallback.
  const offenseTeamId = turnData.offense_team_id
    ?? turnData.possession_team_id
    ?? scene?.offenseTeamId;
  const isHomeTeamEvent = homeTeamId && offenseTeamId != null
    && String(offenseTeamId) === String(homeTeamId);
  const offenseTeam = isHomeTeamEvent ? 'home' : 'away';
  const defenseTeam = isHomeTeamEvent ? 'away' : 'home';
  
  if (timing === 'start') {
    // NOTE: This branch is currently unreachable — turnPreparation.js dispatches
    // start announcements via gameAnnouncements.announceGameEvent() and
    // animateGameTurns.js only calls announceFromTurnData with timing: 'end'.
    // Kept routed to the secondary tier so the contract is consistent if revived.
    if (turnData.fast_break && isFastBreakEntryAnnouncementsEnabled()) {
      showSecondaryAnnouncement("Fast Break!", offenseTeam, null, {
        eventSubtitle: getFastBreakPlayLabel(turnData.fast_break_play),
      });
    }

    const isInboundSettingUpPressure = turnData.result_type === 'BASELINE_INBOUND';
    if (isInboundSettingUpPressure && turnData.next_defensive_setup === 'FCP') {
      showSecondaryAnnouncement("Press!", defenseTeam);
    }
    if (isInboundSettingUpPressure && turnData.next_defensive_setup === 'HCT') {
      showSecondaryAnnouncement("Trap!", defenseTeam, null, {
        eventSubtitle: getHctTrapPlayLabel(turnData.hct_trap_play),
      });
    }
  } else if (timing === 'end') {
    // Announcements at turn end (after animation)
    // Note: "It's Good!" and "Rebound!" use animation-timed helpers (`ballManager`, `ShotAnimationSystem`,
    // `announceReboundHeadlineIfNeeded` in `announcements.js`) for precise timing when the ball reaches rim/rebounder.

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
      showAnnouncement("CHARGE!", defenseTeam, playerData, scene ? { scene } : null);
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

      // Foul whistle carried on payload — court.html plays at overlay mount
      // per SFX_System.md (single source for primary-tier SFX).
      const foulMeta = scene ? { scene, sfx: 'whistle-1-lowervol.wav' } : { sfx: 'whistle-1-lowervol.wav' };
      if (turnData.otb_foul) {
        showAnnouncement("Over The Back!", foulTeam === 'OFFENSE' ? defenseTeam : offenseTeam, playerData, foulMeta);
      } else if (isBlockingFoul) {
        showAnnouncement("BLOCKING FOUL!", offenseTeam, playerData, foulMeta);
      } else if (foulTeam === 'OFFENSE') {
        showAnnouncement(pickOffensiveFoulAnnouncementText(turnData), defenseTeam, playerData, foulMeta);
      } else {
        // Defensive foul: situational Force Foul → "Quick Foul!"; else "DEFENSIVE FOUL!"
        // Bonus fouls (FOUL -> FREE_THROW) stay in this path and should not be reclassified as shooting fouls.
        let defensiveFoulText = pickDefensiveFoulAnnouncementText(turnData);
        if (isQuickFoul) defensiveFoulText = "Quick Foul!";
        if (isBonusFoul && !isQuickFoul) defensiveFoulText = pickDefensiveFoulAnnouncementText(turnData);
        showAnnouncement(defensiveFoulText, offenseTeam, playerData, foulMeta);
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

      // Steal voice tied to "STEAL!" announce appearance (SFX_System.md
      // §Steal Announce). court.html plays `meta.sfx` at overlay mount.
      showAnnouncement("STEAL!", defenseTeam, playerData, {
        sfx: resolveStealSfxFile(),
        ...(scene ? { scene } : {}),
      });
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
          "BACKCOURT": "BACKCOURT VIOLATION!",
          "TEN_SECOND": "10-Second Violation!"
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
      // Whistle carried on payload — court.html plays at mount; Shot Clock
      // Violation uses whistle-3.mp3, other turnovers use whistle-1-lowervol.
      const turnoverSfxFile = turnoverText === 'Shot Clock Violation!' ? 'whistle-3.mp3' : 'whistle-1-lowervol.wav';
      const turnoverMeta = { sfx: turnoverSfxFile };
      if (scene) turnoverMeta.scene = scene;
      showAnnouncement(turnoverText, offenseTeam, playerData, turnoverMeta);
      return;
    }
  }
}
