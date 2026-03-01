/**
 * Shows a game completion popup with Box Score and Go To Locker Room buttons
 * @param {Object} options
 * @param {string} options.gameId - The game ID
 * @param {string} options.mode - Game mode: 'single', 'tournament', or 'franchise'
 * @param {string} [options.tournamentId] - Tournament ID (for tournament mode)
 * @param {string} [options.franchiseId] - Franchise ID (for franchise mode)
 * @param {string} [options.teamId] - Team ID (ObjectId) for navigation anchor
 * @param {Object} [options.finalScore] - Final score object with homeTeam, awayTeam, homeScore, awayScore
 * @param {Object} [options.gameData] - Full game document for POTG calculation (optional)
 */
export async function showGameCompletionPopup({ gameId, mode, tournamentId, franchiseId, teamId, finalScore, homeTeam, awayTeam, gameData }) {
  // Remove any existing popup
  const existingPopup = document.querySelector('.game-completion-popup');
  if (existingPopup) {
    existingPopup.remove();
  }

  // ✅ SS&S: Fallback to reading teamId from URL params if not provided
  if (!teamId && typeof window !== 'undefined') {
    const urlParams = new URLSearchParams(window.location.search);
    teamId = urlParams.get('team_id') || urlParams.get('home_id') || urlParams.get('away_id');
  }

  // Determine locker room URL based on mode
  let lockerRoomUrl;
  switch (mode) {
    case 'tournament':
      lockerRoomUrl = '/tournament.html';
      const tournamentParams = new URLSearchParams();
      if (tournamentId) {
        tournamentParams.set('tournament_id', tournamentId);
      }
      // ✅ SS&S: Include team_id (ObjectId) for complete navigation anchor
      if (teamId) {
        tournamentParams.set('team_id', teamId);
      }
      if (tournamentParams.toString()) {
        lockerRoomUrl += `?${tournamentParams.toString()}`;
      }
      break;
    case 'franchise':
      lockerRoomUrl = '/franchise-command-center.html';
      const franchiseParams = new URLSearchParams();
      if (franchiseId) {
        franchiseParams.set('franchise_id', franchiseId);
      }
      // ✅ SS&S: Include team_id (ObjectId) for complete navigation anchor
      if (teamId) {
        franchiseParams.set('team_id', teamId);
      }
      if (franchiseParams.toString()) {
        lockerRoomUrl += `?${franchiseParams.toString()}`;
      }
      break;
    default:
      lockerRoomUrl = '/mode-select.html';
  }

  // Box Score URL - include mode, IDs, and team names for proper navigation
  const boxScoreParams = new URLSearchParams();
  if (gameId) boxScoreParams.set('game_id', gameId);
  if (homeTeam) boxScoreParams.set('home', homeTeam);
  if (awayTeam) boxScoreParams.set('away', awayTeam);
  // ✅ SS&S: Include mode and mode-specific IDs for proper "Go To Locker Room" navigation
  if (mode) boxScoreParams.set('mode', mode);
  if (tournamentId) boxScoreParams.set('tournament_id', tournamentId);
  if (franchiseId) boxScoreParams.set('franchise_id', franchiseId);
  if (teamId) boxScoreParams.set('team_id', teamId);
  const boxScoreUrl = `/box-score.html?${boxScoreParams.toString()}`;
  
  console.log('📊 Box Score URL constructed:', {
    gameId,
    homeTeam,
    awayTeam,
    boxScoreUrl,
    finalScore,
    hasGameId: !!gameId,
    gameIdType: typeof gameId,
    gameIdLength: gameId ? gameId.length : 0
  });
  
  // Also log to localStorage for persistence across page navigation
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('last_box_score_url', boxScoreUrl);
    localStorage.setItem('last_box_score_gameId', gameId || '');
    console.log('💾 Saved box score URL to localStorage for debugging');
  }

  let potg = null;
  try {
    const staticBase = (typeof window !== 'undefined' && window.API_CONFIG?.getStaticPath)
      ? window.API_CONFIG.getStaticPath()
      : '';
    const { calculatePlayerOfTheGame } = await import(`${staticBase}/js/shared/potg.js`);
    let potgGameData = gameData || null;
    if (!potgGameData && gameId && typeof fetch === 'function' && typeof API_CONFIG !== 'undefined') {
      const resp = await fetch(API_CONFIG.buildUrl(`/api/game/${gameId}`), {
        headers: API_CONFIG.getAuthHeaders ? API_CONFIG.getAuthHeaders() : {},
      });
      if (resp.ok) {
        potgGameData = await resp.json();
      }
    }
    const scoreOverride = finalScore ? {
      [finalScore.homeTeam || homeTeam || 'Home Team']: Number(finalScore.homeScore || 0),
      [finalScore.awayTeam || awayTeam || 'Away Team']: Number(finalScore.awayScore || 0),
    } : null;
    if (potgGameData) {
      potg = calculatePlayerOfTheGame(potgGameData, { gameId, scoreOverride });
    }
  } catch (err) {
    console.warn('[gameCompletionPopup] Failed to calculate POTG:', err);
  }

  // Create popup
  const popup = document.createElement('div');
  popup.className = 'game-completion-popup';
  popup.innerHTML = `
    <div class="game-completion-content">
      <h2>Game Complete!</h2>
      ${finalScore ? `
        <div class="final-score-display">
          <div class="score-line">
            <div class="team-score-left">
              <span class="team-name">${finalScore.homeTeam || 'Home'}</span>
              <span class="score">${finalScore.homeScore || 0}</span>
            </div>
            <div class="team-score-right">
              <span class="team-name">${finalScore.awayTeam || 'Away'}</span>
              <span class="score">${finalScore.awayScore || 0}</span>
            </div>
          </div>
        </div>
      ` : ''}
      ${potg ? `
        <div class="potg-image-row">
          <img
            class="potg-image"
            src="${potg.photo}"
            alt="${potg.name}"
            onerror="this.onerror=null;this.src='/images/players/default.png';"
          />
        </div>
        <div class="potg-stats-row">
          <span style="color: ${potg.teamColor || '#1a1a2e'};">${potg.stats.pts} PTS&nbsp;&nbsp;&nbsp;${potg.stats.reb} REB&nbsp;&nbsp;&nbsp;${potg.stats.ast} AST</span>
        </div>
        <div class="potg-stats-row">
          <span style="color: ${potg.teamColor || '#1a1a2e'};">${potg.stats.stl} STL&nbsp;&nbsp;&nbsp;${potg.stats.blk} BLK&nbsp;&nbsp;&nbsp;${potg.stats.defPct} DEF%</span>
        </div>
      ` : ''}
      <div class="button-container">
        <a href="${boxScoreUrl}" class="completion-button box-score-button">Box Score</a>
        <a href="${lockerRoomUrl}" class="completion-button locker-room-button">Go To Locker Room</a>
      </div>
    </div>
  `;

  // Add styles if not already present
  if (!document.getElementById('game-completion-popup-styles')) {
    const style = document.createElement('style');
    style.id = 'game-completion-popup-styles';
    style.textContent = `
      .game-completion-popup {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.85);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
      }

      .game-completion-content {
        background: #fff;
        border: 6px solid #c0c0c0;
        border-radius: 12px;
        padding: 40px 60px;
        display: flex;
        flex-direction: column;
        gap: 30px;
        align-items: center;
        min-width: 400px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
      }

      .game-completion-content h2 {
        font-size: 36px;
        font-weight: bold;
        color: #333;
        margin: 0;
        font-family: 'Bebas Neue', sans-serif;
        letter-spacing: 2px;
      }

      .final-score-display {
        margin: 10px 0;
      }

      .score-line {
        font-size: 24px;
        font-weight: 700;
        color: #333;
        margin: 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
        width: 100%;
        gap: 40px;
      }

      .team-score-left,
      .team-score-right {
        display: flex;
        align-items: center;
        gap: 10px;
      }

      .team-score-left {
        justify-content: flex-start;
      }

      .team-score-right {
        justify-content: flex-end;
      }

      .score-line .team-name {
        font-weight: 700;
      }

      .score-line .score {
        font-size: 32px;
        font-weight: 700;
        color: #1a1a2e;
      }

      .button-container {
        display: flex;
        gap: 20px;
        width: 100%;
        justify-content: center;
      }

      .potg-image-row {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        margin: 4px 0;
      }

      .potg-image {
        width: 120px;
        height: 120px;
        border-radius: 50%;
        border: 3px solid #d7d7d7;
        object-fit: cover;
        object-position: top;
        background: #f2f2f2;
      }

      .potg-stats-row {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 28px;
        letter-spacing: 1px;
        color: #1a1a2e;
        text-align: center;
        line-height: 1.1;
      }

      .completion-button {
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

      .box-score-button {
        background: #4a90e2;
        color: #fff;
      }

      .box-score-button:hover {
        background: #357abd;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(74, 144, 226, 0.3);
      }

      .locker-room-button {
        background: #ff9800;
        color: #fff;
      }

      .locker-room-button:hover {
        background: #f57c00;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(255, 152, 0, 0.3);
      }
    `;
    document.head.appendChild(style);
  }

  document.body.appendChild(popup);

  // Single game: delete completed game from DB when user leaves via "Go To Locker Room" (not when viewing Box Score)
  const lockerRoomBtn = popup.querySelector('.locker-room-button');
  const boxScoreBtn = popup.querySelector('.box-score-button');
  if (boxScoreBtn) {
    boxScoreBtn.addEventListener('click', () => {
      if (typeof window.playSound === 'function') window.playSound('click-tiny.wav');
    });
  }
  if (lockerRoomBtn) {
    lockerRoomBtn.addEventListener('click', () => {
      if (typeof window.playSound === 'function') window.playSound('click-tiny.wav');
    });
  }
  if (lockerRoomBtn && mode === 'single' && gameId) {
    lockerRoomBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      try {
        if (typeof API_CONFIG !== 'undefined' && API_CONFIG.buildUrl && API_CONFIG.getAuthHeaders) {
          await fetch(API_CONFIG.buildUrl('/api/games/delete-completed-single'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...API_CONFIG.getAuthHeaders() },
            body: JSON.stringify({ game_id: gameId }),
          });
        }
      } catch (err) {
        console.warn('[gameCompletionPopup] delete-completed-single failed:', err);
      }
      window.location.href = lockerRoomUrl;
    });
  }
}
