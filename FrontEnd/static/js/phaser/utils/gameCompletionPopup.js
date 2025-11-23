/**
 * Shows a game completion popup with Box Score and Go To Locker Room buttons
 * @param {Object} options
 * @param {string} options.gameId - The game ID
 * @param {string} options.mode - Game mode: 'single', 'tournament', or 'franchise'
 * @param {string} [options.tournamentId] - Tournament ID (for tournament mode)
 * @param {string} [options.franchiseId] - Franchise ID (for franchise mode)
 * @param {Object} [options.finalScore] - Final score object with homeTeam, awayTeam, homeScore, awayScore
 */
export function showGameCompletionPopup({ gameId, mode, tournamentId, franchiseId, finalScore }) {
  // Remove any existing popup
  const existingPopup = document.querySelector('.game-completion-popup');
  if (existingPopup) {
    existingPopup.remove();
  }

  // Determine locker room URL based on mode
  let lockerRoomUrl;
  switch (mode) {
    case 'tournament':
      lockerRoomUrl = '/static/tournament.html';
      if (tournamentId) {
        lockerRoomUrl += `?tournament_id=${tournamentId}`;
      }
      break;
    case 'franchise':
      lockerRoomUrl = '/franchise/command-center';
      if (franchiseId) {
        lockerRoomUrl += `?franchise_id=${franchiseId}`;
      }
      break;
    default:
      lockerRoomUrl = '/static/mode-select.html';
  }

  // Box Score URL
  const boxScoreUrl = `/static/box-score.html?game_id=${gameId}`;

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
}

