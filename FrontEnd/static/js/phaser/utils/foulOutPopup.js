function franchiseCtx() {
  return typeof window !== 'undefined' ? window.FranchiseContext : null;
}
function liveParams() {
  return franchiseCtx().toSearchParams();
}
function emptyParams() {
  return franchiseCtx().createParams();
}
function currentSearch() {
  const s = liveParams().toString();
  return s ? '?' + s : '';
}
function cloneParams(params) {
  const out = emptyParams();
  if (params && typeof params.forEach === 'function') {
    params.forEach((value, key) => out.set(key, value));
  }
  return out;
}

/**
 * Shows a foul out popup when a player reaches 5 fouls
 * @param {Object} options
 * @param {Object} options.player - Player object with player_id, name, photo, team
 * @param {string} options.gameId - The game ID
 * @param {string} options.mode - Game mode: 'single' or 'franchise'
 * @param {string} options.quarter - Current quarter
 * @param {string} [options.franchiseId] - Franchise ID (for franchise mode)
 * @param {string} [options.homeTeam] - Home team name
 * @param {string} [options.awayTeam] - Away team name
 * @param {string} [options.homeId] - Home team ID
 * @param {string} [options.awayId] - Away team ID
 * @param {string} [options.myTeamSide] - User's team side ('home' or 'away')
 * @param {string} [options.userTeamId] - User's team ID
 * @param {string} [options.foulOutPlayerId] - Fouling-out player's id from turn (single source of truth for image; same as shooting-foul uses turnData.foul_player_id)
 */
export async function showFoulOutPopup({ player, gameId, mode, quarter, clock, franchiseId, homeTeam, awayTeam, homeId, awayId, myTeamSide, userTeamId, foulOutPlayerId: foulOutPlayerIdFromTurn }) {
  // Remove any existing popup
  const existingPopup = document.querySelector('.foul-out-popup');
  if (existingPopup) {
    existingPopup.remove();
  }

  // ✅ SS&S: Use unified navigation helper for consistent parameter building
  // Fallback: try to get team info and CURRENT LINEUP from current URL if not provided
  const urlParams = liveParams();
  if (!homeTeam) homeTeam = urlParams.get('home');
  if (!awayTeam) awayTeam = urlParams.get('away');
  if (!homeId) homeId = urlParams.get('home_id');
  if (!awayId) awayId = urlParams.get('away_id');
  if (!myTeamSide) myTeamSide = urlParams.get('my_team');
  if (!userTeamId) userTeamId = urlParams.get('user_team_id');
  
  // ✅ FOUL OUT: Build current lineup for user's team from URL (same pattern as timeout/quarter flows)
  const effectiveMyTeamSide = myTeamSide || urlParams.get('my_team');
  const lineup = {};
  if (effectiveMyTeamSide === 'home' || effectiveMyTeamSide === 'away') {
    const positions = ['PG', 'SG', 'SF', 'PF', 'C'];
    positions.forEach(pos => {
      const key = `${effectiveMyTeamSide}_${pos.toLowerCase()}`;
      const playerId = urlParams.get(key);
      if (playerId) {
        lineup[pos] = playerId;
      }
    });
  }

  // ✅ FOUL OUT: Remove fouled-out player from user's lineup (user must replace this slot)
  try {
    const foulOutPlayerId = (foulOutPlayerIdFromTurn != null && foulOutPlayerIdFromTurn !== '') ? String(foulOutPlayerIdFromTurn) : (player?.player_id || player?.playerId || player?.id);
    const foulOutPlayerTeam = player?.team;
    const userTeamName = effectiveMyTeamSide === 'home' ? homeTeam : awayTeam;

    if (foulOutPlayerId && foulOutPlayerTeam && userTeamName && foulOutPlayerTeam === userTeamName) {
      Object.entries(lineup).forEach(([pos, playerId]) => {
        if (playerId === foulOutPlayerId) {
          delete lineup[pos];
          console.log(`✅ [FOUL-OUT] Cleared ${pos} slot for fouled-out player ${player.name} (${foulOutPlayerId})`);
        }
      });
    }
  } catch (err) {
    console.warn('⚠️ [FOUL-OUT] Failed to clear fouled-out player from lineup', err);
  }

  // ✅ FOUL OUT: Also preserve the other team's lineup from URL so both sides stay consistent
  const otherLineupParams = {};
  if (effectiveMyTeamSide === 'home' || effectiveMyTeamSide === 'away') {
    const otherTeamSide = effectiveMyTeamSide === 'home' ? 'away' : 'home';
    const positions = ['PG', 'SG', 'SF', 'PF', 'C'];
    positions.forEach(pos => {
      const key = `${otherTeamSide}_${pos.toLowerCase()}`;
      const playerId = urlParams.get(key);
      if (playerId) {
        otherLineupParams[`${otherTeamSide}_${pos.toLowerCase()}`] = playerId;
      }
    });
  }
  
  // Build params using unified helper
  // ✅ SS&S: Use global helper (works in both regular scripts and modules)
  const helper = window.TimeoutNavigationHelper;
  if (!helper) {
    console.error('❌ [FOUL-OUT] TimeoutNavigationHelper not loaded!');
    return;
  }

  // ✅ FOUL OUT SCORES: Capture displayed scores from DOM so lineup header shows what user
  // saw at foul-out time. Mirrors the timeoutButtonManager pattern — without this the lineup
  // page falls back to a DB read that can return stale (start-of-quarter) scores.
  let homeScore = null;
  let awayScore = null;
  const homeScoreEl = document.getElementById('home-score');
  const awayScoreEl = document.getElementById('away-score');
  if (homeScoreEl && awayScoreEl) {
    const h = homeScoreEl.textContent?.trim();
    const a = awayScoreEl.textContent?.trim();
    if (h !== undefined && h !== '' && !isNaN(Number(h))) homeScore = Number(h);
    if (a !== undefined && a !== '' && !isNaN(Number(a))) awayScore = Number(a);
  }

  const params = helper.buildGameNavigationParams({
    sourceParams: urlParams,
    targetQuarter: quarter,
    gameId: gameId,
    resumeFromTimeout: true, // ✅ FOUL OUT: Always resuming from timeout (any quarter)
    lineup: lineup, // ✅ Pre-populated with current lineup (user's team), minus fouled-out player
    myTeamSide: effectiveMyTeamSide,
    clock: clock,
    overrides: {
      home: homeTeam,
      away: awayTeam,
      home_id: homeId,
      away_id: awayId,
      my_team: myTeamSide,
      user_team_id: userTeamId,
      mode: mode,
      franchise_id: franchiseId,
      home_score: homeScore ?? undefined,
      away_score: awayScore ?? undefined
    }
  });

  // ✅ FOUL OUT: Manually add other team's lineup params (helper only adds user's team)
  Object.entries(otherLineupParams).forEach(([key, value]) => {
    params.set(key, value);
  });
  
  const lineupUrl = `/set-lineup.html?${params.toString()}`;

  // Image: id only, same as Defensive Foul announcement — do not use player.photo.
  const imagePlayerId = (foulOutPlayerIdFromTurn != null && foulOutPlayerIdFromTurn !== '') ? String(foulOutPlayerIdFromTurn) : (player?.player_id ?? player?.playerId ?? player?.id);
  const playerId = imagePlayerId != null ? String(imagePlayerId) : '';
  const hostname = typeof window !== 'undefined' ? window.location.hostname : '';
  const staticPrefix = (hostname === 'localhost' || hostname === '127.0.0.1') ? '/static' : '';
  let photoUrl = '';
  if (playerId) {
    photoUrl = (typeof window !== 'undefined' && window.API_CONFIG?.getPlayerImageUrl)
      ? window.API_CONFIG.getPlayerImageUrl(playerId, { size: 'card' })
      : staticPrefix + `/images/players/${playerId}.png`;
  }
  const defaultPlayerImg = staticPrefix + '/images/players/generic_headshot.png';
  const safePhotoUrl = photoUrl ? photoUrl.replace(/"/g, '&quot;') : '';
  const safeDefaultImg = defaultPlayerImg.replace(/"/g, '&quot;');
  const safeName = (player?.name || 'Player').replace(/"/g, '&quot;');
  const initialContent = photoUrl
    ? `<img src="${safePhotoUrl}" alt="${safeName}" class="foul-out-player-image" onerror="this.onerror=null;this.src='${safeDefaultImg}'">`
    : `<div class="foul-out-player-placeholder">${(player?.name || 'P').charAt(0)}</div>`;
  const safeDisplayName = (player?.name || 'Player')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Functional Modal shell (same as timeout gate) + portrait / name subject
  const popup = document.createElement('div');
  // `gob` so design tokens resolve (court.html links gob-tokens.css).
  popup.className = 'foul-out-popup gob';
  popup.setAttribute('role', 'dialog');
  popup.setAttribute('aria-modal', 'true');
  popup.setAttribute('aria-labelledby', 'foul-out-title');
  popup.innerHTML = `
    <div class="foul-out-content">
      <div class="foul-out-modal-accent"></div>
      <div class="foul-out-modal-body">
        <div class="foul-out-player-image-container">
          ${initialContent}
        </div>
        <h2 id="foul-out-title" class="foul-out-title">Fouled Out!</h2>
        <div class="foul-out-player-name">${safeDisplayName}</div>
      </div>
      <div class="foul-out-button-container">
        <a href="${lineupUrl}" class="foul-out-button sub-players-button" data-gob-replace>Sub Players</a>
      </div>
    </div>
  `;

  if (!document.getElementById('foul-out-popup-styles')) {
    const style = document.createElement('style');
    style.id = 'foul-out-popup-styles';
    style.textContent = `
      .foul-out-popup {
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.72);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10001;
        padding: 20px;
      }

      .foul-out-content {
        width: min(420px, calc(100vw - 40px));
        background: rgba(22, 26, 36, 0.98);
        border: 1px solid var(--white-12);
        border-radius: var(--radius-14);
        box-shadow: 0 24px 48px rgba(0, 0, 0, 0.5),
                    inset 0 1px 0 var(--white-6);
        overflow: hidden;
        display: flex;
        flex-direction: column;
        text-align: center;
      }

      /* Decorative top accent — neutral, not orange (orange is reserved for saves). */
      .foul-out-modal-accent {
        height: 3px;
        width: 100%;
        background: var(--white-28);
        flex-shrink: 0;
      }

      .foul-out-modal-body {
        padding: 24px 28px 16px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 12px;
      }

      .foul-out-player-image-container {
        width: 96px;
        height: 128px;
        border-radius: var(--radius-10);
        overflow: hidden;
        border: 1px solid var(--white-18);
        background: var(--white-6);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      .foul-out-player-image {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }

      .foul-out-player-placeholder {
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 48px;
        font-weight: 700;
        font-family: 'Bebas Neue', sans-serif;
        color: var(--text-38);
        background: var(--white-6);
      }

      .foul-out-title {
        font-size: 28px;
        color: var(--text-100);
        margin: 0;
        font-family: 'Bebas Neue', sans-serif;
        letter-spacing: 0.04em;
        line-height: 1;
      }

      .foul-out-player-name {
        font-size: 14px;
        font-weight: 600;
        font-family: Inter, system-ui, sans-serif;
        color: var(--text-60);
        text-align: center;
        margin: 0;
        letter-spacing: 0.02em;
        text-transform: uppercase;
      }

      .foul-out-button-container {
        display: flex;
        gap: 10px;
        width: 100%;
        justify-content: stretch;
        padding: 0 28px 24px;
        box-sizing: border-box;
      }

      .foul-out-button {
        appearance: none;
        flex: 1;
        height: 42px;
        border-radius: var(--radius-10);
        cursor: pointer;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        transition: filter 0.14s ease, transform 0.14s ease;
        font-family: 'Bebas Neue', sans-serif;
        font-size: 16px;
        letter-spacing: 0.04em;
        border: 1px solid transparent;
      }

      /* Corrective navigation to the lineup, not the game/week Advance action, so
         neutral (prominent) — not green (Advance) and not orange (saves). */
      .sub-players-button {
        background: var(--white-10);
        border-color: var(--white-28);
        color: var(--text-100);
      }

      .sub-players-button:hover {
        filter: brightness(1.06);
        transform: translateY(-1px);
      }
    `;
    document.head.appendChild(style);
  }

  const subBtn = popup.querySelector('.sub-players-button');
  if (subBtn) {
    subBtn.addEventListener('click', () => {
      if (typeof window.playSound === 'function') window.playSound('click-tiny.wav');
    });
  }
  document.body.appendChild(popup);
}
