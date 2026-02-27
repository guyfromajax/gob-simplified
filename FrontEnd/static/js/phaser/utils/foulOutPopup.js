/**
 * Shows a foul out popup when a player reaches 5 fouls
 * @param {Object} options
 * @param {Object} options.player - Player object with player_id, name, photo, team
 * @param {string} options.gameId - The game ID
 * @param {string} options.mode - Game mode: 'single', 'tournament', or 'franchise'
 * @param {string} options.quarter - Current quarter
 * @param {string} [options.tournamentId] - Tournament ID (for tournament mode)
 * @param {string} [options.franchiseId] - Franchise ID (for franchise mode)
 * @param {string} [options.homeTeam] - Home team name
 * @param {string} [options.awayTeam] - Away team name
 * @param {string} [options.homeId] - Home team ID
 * @param {string} [options.awayId] - Away team ID
 * @param {string} [options.myTeamSide] - User's team side ('home' or 'away')
 * @param {string} [options.userTeamId] - User's team ID
 */
export async function showFoulOutPopup({ player, gameId, mode, quarter, clock, tournamentId, franchiseId, homeTeam, awayTeam, homeId, awayId, myTeamSide, userTeamId }) {
  console.log('[FOUL-OUT POPUP] showFoulOutPopup called', { playerId: player?.player_id ?? player?.playerId, name: player?.name });
  // Remove any existing popup
  const existingPopup = document.querySelector('.foul-out-popup');
  if (existingPopup) {
    existingPopup.remove();
  }

  // ✅ SS&S: Use unified navigation helper for consistent parameter building
  // Fallback: try to get team info and CURRENT LINEUP from current URL if not provided
  const urlParams = new URLSearchParams(window.location.search);
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
    const foulOutPlayerId = player?.player_id || player?.playerId || player?.id;
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
      tournament_id: tournamentId,
      franchise_id: franchiseId
    }
  });

  // ✅ FOUL OUT: Manually add other team's lineup params (helper only adds user's team)
  Object.entries(otherLineupParams).forEach(([key, value]) => {
    params.set(key, value);
  });
  
  const lineupUrl = `/set-lineup.html?${params.toString()}`;

  // Resolve player image URL — same rule as announcement system (announcements.js): bare path, no API_CONFIG dependency.
  const rawId = player?.player_id ?? player?.playerId ?? player?.id;
  const playerId = rawId != null ? String(rawId) : '';
  const rawPhoto = player?.photo || player?.image_url;
  let photoUrl = '';
  if (rawPhoto && typeof rawPhoto === 'string' && rawPhoto.trim()) {
    const t = rawPhoto.trim();
    if (t.startsWith('http://') || t.startsWith('https://')) {
      photoUrl = t;
    } else {
      const base = typeof window !== 'undefined' ? window.location.origin : '';
      photoUrl = t.startsWith('/') ? `${base}${t}` : `${base}/${t}`;
    }
  }
  if (!photoUrl && playerId) {
    photoUrl = `/images/players/${playerId}.png`;
  }
  let defaultPlayerImg = '/images/players/default.png';
  // Prepend /static only for local dev (backend serves from /static/). Netlify and production use root.
  const hostname = typeof window !== 'undefined' ? window.location.hostname : '';
  const staticPrefix = (hostname === 'localhost' || hostname === '127.0.0.1') ? '/static' : '';
  if (photoUrl && !photoUrl.startsWith('http')) {
    photoUrl = staticPrefix + photoUrl;
  }
  defaultPlayerImg = staticPrefix + defaultPlayerImg;
  // DEBUG: remove after fixing foul-out image
  console.log('[FOUL-OUT POPUP] image URL debug', {
    hostname,
    staticPrefix,
    playerId,
    rawPhoto: rawPhoto || null,
    photoUrlFinal: photoUrl || null,
    defaultPlayerImgFinal: defaultPlayerImg,
    showingImg: !!photoUrl
  });
  const safePhotoUrl = photoUrl.replace(/"/g, '&quot;');
  const safeDefaultImg = defaultPlayerImg.replace(/"/g, '&quot;');
  const safeName = (player?.name || 'Player').replace(/"/g, '&quot;');
  const initialContent = photoUrl
    ? `<img src="${safePhotoUrl}" alt="${safeName}" class="foul-out-player-image" onerror="this.onerror=null;this.src='${safeDefaultImg}'">`
    : `<div class="foul-out-player-placeholder">${(player?.name || 'P').charAt(0)}</div>`;

  // Create popup (same design as end-of-quarter and timeout: white content, gray border)
  const popup = document.createElement('div');
  popup.className = 'foul-out-popup';
  popup.innerHTML = `
    <div class="foul-out-content">
      <div class="foul-out-header">
        <div class="foul-out-player-image-container">
          ${initialContent}
        </div>
        <h2 class="foul-out-title">FOULED OUT!</h2>
      </div>
      <div class="foul-out-player-name">${(player?.name || 'Player').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
      <div class="foul-out-button-container">
        <a href="${lineupUrl}" class="foul-out-button sub-players-button">Sub Players</a>
      </div>
    </div>
  `;

  // Add styles if not already present (same design as end-of-quarter and timeout popups)
  if (!document.getElementById('foul-out-popup-styles')) {
    const style = document.createElement('style');
    style.id = 'foul-out-popup-styles';
    style.textContent = `
      .foul-out-popup {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.7);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10001;
      }

      .foul-out-content {
        background: #fff;
        border: 6px solid #c0c0c0;
        border-radius: 12px;
        padding: 40px 60px;
        display: flex;
        flex-direction: column;
        gap: 30px;
        align-items: center;
        min-width: 400px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
        text-align: center;
      }

      .foul-out-header {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 20px;
      }

      .foul-out-player-image-container {
        width: 120px;
        height: 160px;
        border-radius: 8px;
        overflow: hidden;
        border: 3px solid #c0c0c0;
        background: #f5f5f5;
        display: flex;
        align-items: center;
        justify-content: center;
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
        font-size: 60px;
        font-weight: bold;
        color: #999;
        background: #f5f5f5;
      }

      .foul-out-title {
        font-size: 36px;
        font-weight: bold;
        color: #333;
        margin: 0;
        font-family: 'Bebas Neue', sans-serif;
        letter-spacing: 2px;
      }

      .foul-out-player-name {
        font-size: 24px;
        font-weight: bold;
        color: #333;
        text-align: center;
        margin: 0;
      }

      .foul-out-button-container {
        display: flex;
        gap: 20px;
        width: 100%;
        justify-content: center;
      }

      .foul-out-button {
        padding: 15px 40px;
        font-size: 18px;
        font-weight: bold;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        text-decoration: none;
        display: inline-block;
        transition: all 0.3s;
        font-family: 'Inter', sans-serif;
      }

      .sub-players-button {
        background: #ff9800;
        color: #fff;
      }

      .sub-players-button:hover {
        background: #f57c00;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(255, 152, 0, 0.3);
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
  const img = popup.querySelector('.foul-out-player-image');
  if (img) {
    img.addEventListener('error', () => {
      console.warn('[FOUL-OUT POPUP] image failed to load', { src: img.src });
    });
  }
}

