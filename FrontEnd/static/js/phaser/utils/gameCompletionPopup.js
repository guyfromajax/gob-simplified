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
  let potgImageUrl = '';
  const staticBase = (typeof window !== 'undefined' && window.API_CONFIG?.getStaticPath)
    ? window.API_CONFIG.getStaticPath()
    : ((typeof window !== 'undefined' && (window.location?.hostname === 'localhost' || window.location?.hostname === '127.0.0.1')) ? '/static' : '');
  try {
    const { calculatePlayerOfTheGame } = await import((staticBase || '') + '/js/shared/potg.js');
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
      if (potg?.playerId) {
        potgImageUrl = `${staticBase}/images/players/${potg.playerId}.png`;
      }
    }
  } catch (err) {
    console.warn('[gameCompletionPopup] Failed to calculate POTG:', err);
  }

  const homeTeamName = finalScore?.homeTeam || 'Home';
  const awayTeamName = finalScore?.awayTeam || 'Away';
  const homeScore = Number(finalScore?.homeScore || 0);
  const awayScore = Number(finalScore?.awayScore || 0);
  const homeWon = homeScore > awayScore;
  const awayWon = awayScore > homeScore;

  // Create popup
  const popup = document.createElement('div');
  popup.className = 'game-completion-popup';
  popup.innerHTML = `
    <div class="game-completion-content">
      <h2>Game Complete!</h2>
      ${finalScore ? `
        <section class="gc-section gc-result-section">
          <div class="final-score-display">
            <div class="score-line">
              <div class="team-score-left ${homeWon ? 'winner' : ''} ${awayWon ? 'loser' : ''}">
                <span class="team-name">${homeTeamName}</span>
                <span class="score">${homeScore}</span>
              </div>
              <div class="score-divider">vs</div>
              <div class="team-score-right ${awayWon ? 'winner' : ''} ${homeWon ? 'loser' : ''}">
                <span class="team-name">${awayTeamName}</span>
                <span class="score">${awayScore}</span>
              </div>
            </div>
          </div>
        </section>
      ` : ''}
      ${potg ? `
        <section class="gc-section gc-potg-section">
          <div class="potg-card">
            <div class="potg-meta-row" style="color: ${potg.teamColor || '#1a1a2e'};">Player Of The Game</div>
            <div class="potg-image-row">
              <img
                class="potg-image"
                src="${potgImageUrl || (staticBase + '/images/players/generic_headshot.png')}"
                alt="${potg.name}"
                onerror="this.onerror=null;this.src='${staticBase}/images/players/generic_headshot.png';"
              />
            </div>
            <div class="potg-meta-row potg-player-name" style="color: ${potg.teamColor || '#1a1a2e'};">${potg.name}</div>
            <div class="potg-stats-grid" style="color: ${potg.teamColor || '#1a1a2e'};">
              <div>${potg.stats.pts} PTS</div>
              <div>${potg.stats.reb} REB</div>
              <div>${potg.stats.ast} AST</div>
              <div>${potg.stats.stl} STL</div>
              <div>${potg.stats.blk} BLK</div>
              <div>${potg.stats.defPct} DEF%</div>
            </div>
          </div>
        </section>
      ` : ''}
      <section class="gc-section gc-actions-section">
        <div class="button-container">
          <a href="${boxScoreUrl}" class="completion-button box-score-button">Box Score</a>
          <a href="${lockerRoomUrl}" class="completion-button locker-room-button">Go To Locker Room</a>
        </div>
      </section>
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
        background: rgba(9, 14, 29, 0.86);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
        padding: 18px;
      }

      .game-completion-content {
        background:
          linear-gradient(180deg, rgba(248, 249, 252, 0.98) 0%, rgba(240, 242, 247, 0.98) 100%);
        border: 1px solid rgba(16, 30, 61, 0.18);
        border-radius: 14px;
        padding: 26px 30px 22px;
        display: flex;
        flex-direction: column;
        gap: 14px;
        align-items: stretch;
        width: min(760px, 100%);
        box-shadow:
          0 24px 60px rgba(0, 0, 0, 0.45),
          0 2px 0 rgba(255, 255, 255, 0.25) inset;
      }

      .game-completion-content h2 {
        font-size: 56px;
        font-weight: bold;
        color: #1a1a2e;
        margin: 0;
        font-family: 'Bebas Neue', sans-serif;
        letter-spacing: 1.6px;
        line-height: 0.95;
        text-align: center;
      }

      .gc-section {
        border-top: 1px solid rgba(26, 26, 46, 0.1);
        padding-top: 12px;
      }

      .gc-result-section {
        border-top: none;
        padding-top: 2px;
      }

      .final-score-display {
        margin: 0;
        padding: 10px 14px;
        background: rgba(255, 255, 255, 0.62);
        border: 1px solid rgba(26, 26, 46, 0.1);
        border-radius: 10px;
      }

      .score-line {
        font-size: 20px;
        font-weight: 700;
        color: #2e3043;
        margin: 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
        width: 100%;
        gap: 18px;
      }

      .score-divider {
        font-family: 'Bebas Neue', sans-serif;
        letter-spacing: 1.2px;
        font-size: 20px;
        color: rgba(26, 26, 46, 0.45);
        text-transform: uppercase;
      }

      .team-score-left,
      .team-score-right {
        display: flex;
        align-items: center;
        gap: 8px;
        flex: 1;
      }

      .team-score-left {
        justify-content: flex-start;
      }

      .team-score-right {
        justify-content: flex-end;
      }

      .score-line .team-name {
        font-weight: 700;
        opacity: 0.8;
        font-size: 46px;
        font-family: 'Bebas Neue', sans-serif;
        letter-spacing: 1px;
        line-height: 0.95;
      }

      .team-score-left.winner .team-name,
      .team-score-right.winner .team-name {
        opacity: 1;
        color: #16172a;
      }

      .team-score-left.loser .team-name,
      .team-score-right.loser .team-name {
        opacity: 0.56;
      }

      .score-line .score {
        font-size: 56px;
        font-weight: 700;
        color: #202445;
        font-family: 'Bebas Neue', sans-serif;
        letter-spacing: 0.8px;
        line-height: 0.95;
      }

      .team-score-left.winner .score,
      .team-score-right.winner .score {
        color: #121739;
      }

      .team-score-left.loser .score,
      .team-score-right.loser .score {
        color: rgba(32, 36, 69, 0.7);
      }

      .button-container {
        display: grid;
        grid-template-columns: 1fr 1.45fr;
        gap: 12px;
        width: 100%;
        align-items: stretch;
      }

      .potg-image-row {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        margin: 4px 0 2px;
      }

      .potg-image {
        width: 136px;
        height: 136px;
        border-radius: 50%;
        border: 4px solid rgba(26, 26, 46, 0.14);
        object-fit: cover;
        object-position: top;
        background: #eef0f4;
        box-shadow:
          0 0 0 4px rgba(255, 255, 255, 0.78),
          0 10px 24px rgba(0, 0, 0, 0.18);
      }

      .potg-card {
        background: rgba(255, 255, 255, 0.72);
        border: 1px solid rgba(26, 26, 46, 0.1);
        border-radius: 10px;
        padding: 10px 14px 12px;
      }

      .potg-stats-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 8px 10px;
        margin-top: 6px;
        font-family: 'Bebas Neue', sans-serif;
        font-size: 22px;
        letter-spacing: 1px;
        text-align: center;
        line-height: 1;
      }

      .potg-meta-row {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 30px;
        letter-spacing: 1px;
        text-align: center;
        line-height: 1;
      }

      .potg-player-name {
        margin-top: 2px;
        font-size: 34px;
      }

      .completion-button {
        padding: 14px 18px;
        font-size: 19px;
        font-weight: bold;
        border: 1px solid transparent;
        border-radius: 8px;
        cursor: pointer;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 56px;
        transition: all 0.2s ease;
        font-family: 'Bebas Neue', sans-serif;
        letter-spacing: 0.2px;
      }

      .box-score-button {
        background: rgba(255, 255, 255, 0.72);
        color: #1d2343;
        border-color: rgba(29, 35, 67, 0.34);
      }

      .box-score-button:hover {
        background: rgba(255, 255, 255, 0.96);
        border-color: rgba(29, 35, 67, 0.58);
        transform: translateY(-1px);
      }

      .locker-room-button {
        background: #ff9800;
        color: #fff;
        border-color: #f18900;
        box-shadow: 0 10px 22px rgba(255, 152, 0, 0.32);
      }

      .locker-room-button:hover {
        background: #f28b00;
        transform: translateY(-1px);
        box-shadow: 0 12px 24px rgba(255, 152, 0, 0.4);
      }

      @media (max-width: 760px) {
        .game-completion-content {
          padding: 18px 16px 16px;
          gap: 10px;
        }

        .game-completion-content h2 {
          font-size: 44px;
        }

        .score-line {
          gap: 8px;
        }

        .score-line .team-name {
          font-size: 34px;
        }

        .score-line .score {
          font-size: 46px;
        }

        .potg-meta-row {
          font-size: 24px;
        }

        .potg-player-name {
          font-size: 30px;
        }

        .potg-stats-grid {
          font-size: 19px;
          gap: 6px 8px;
        }

        .button-container {
          grid-template-columns: 1fr;
        }

        .completion-button {
          width: 100%;
        }
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
