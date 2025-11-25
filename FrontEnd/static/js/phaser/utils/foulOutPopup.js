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
export function showFoulOutPopup({ player, gameId, mode, quarter, clock, tournamentId, franchiseId, homeTeam, awayTeam, homeId, awayId, myTeamSide, userTeamId }) {
  // Remove any existing popup
  const existingPopup = document.querySelector('.foul-out-popup');
  if (existingPopup) {
    existingPopup.remove();
  }

  // Build lineup selection URL with game context
  const params = new URLSearchParams();
  
  // Team information (required for set-lineup to work)
  if (homeTeam) params.set('home', homeTeam);
  if (awayTeam) params.set('away', awayTeam);
  if (homeId) params.set('home_id', homeId);
  if (awayId) params.set('away_id', awayId);
  if (myTeamSide) params.set('my_team', myTeamSide);
  if (userTeamId) params.set('user_team_id', userTeamId);
  
  // Game context
  if (gameId) params.set('game_id', gameId);
  if (quarter) params.set('quarter', quarter);
  params.set('period', `Q${quarter}`);
  if (clock) params.set('clock', clock); // ✅ Preserve clock time when navigating to lineup
  if (tournamentId) params.set('tournament_id', tournamentId);
  if (franchiseId) params.set('franchise_id', franchiseId);
  if (mode) params.set('mode', mode);
  
  // Fallback: try to get team info from current URL if not provided
  if (!homeTeam || !awayTeam) {
  const urlParams = new URLSearchParams(window.location.search);
    if (!homeTeam) homeTeam = urlParams.get('home');
    if (!awayTeam) awayTeam = urlParams.get('away');
    if (!homeId) homeId = urlParams.get('home_id');
    if (!awayId) awayId = urlParams.get('away_id');
    if (!myTeamSide) myTeamSide = urlParams.get('my_team');
    if (!userTeamId) userTeamId = urlParams.get('user_team_id');
    
    if (homeTeam) params.set('home', homeTeam);
    if (awayTeam) params.set('away', awayTeam);
    if (homeId) params.set('home_id', homeId);
    if (awayId) params.set('away_id', awayId);
    if (myTeamSide) params.set('my_team', myTeamSide);
    if (userTeamId) params.set('user_team_id', userTeamId);
  }
  
  const lineupUrl = `/static/set-lineup.html?${params.toString()}`;

  // Create popup
  const popup = document.createElement('div');
  popup.className = 'foul-out-popup';
  popup.innerHTML = `
    <div class="foul-out-content">
      <div class="foul-out-header">
        <div class="foul-out-player-image-container">
          ${player.photo ? 
            `<img src="${player.photo}" alt="${player.name}" class="foul-out-player-image" onerror="this.src='/static/images/default-player.png'">` :
            `<div class="foul-out-player-placeholder">${player.name?.charAt(0) || 'P'}</div>`
          }
        </div>
        <h2 class="foul-out-title">FOULED OUT!</h2>
      </div>
      <div class="foul-out-player-name">${player.name || 'Player'}</div>
      <div class="foul-out-button-container">
        <a href="${lineupUrl}" class="foul-out-button sub-players-button">Sub Players</a>
      </div>
    </div>
  `;

  // Add styles if not already present
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
        background: rgba(0, 0, 0, 0.85);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10001;
      }

      .foul-out-content {
        background: #222;
        border: 4px solid #e74c3c;
        border-radius: 12px;
        padding: 40px 50px;
        display: flex;
        flex-direction: column;
        gap: 25px;
        align-items: center;
        min-width: 400px;
        box-shadow: 0 4px 20px rgba(231, 76, 60, 0.5);
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
        border: 3px solid #e74c3c;
        background: #1a1a1a;
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
        color: #e74c3c;
        background: #1a1a1a;
      }

      .foul-out-title {
        font-size: 48px;
        font-weight: bold;
        color: #e74c3c;
        margin: 0;
        font-family: 'Bebas Neue', sans-serif;
        letter-spacing: 3px;
        text-shadow: 0 0 10px rgba(231, 76, 60, 0.8);
      }

      .foul-out-player-name {
        font-size: 24px;
        font-weight: bold;
        color: #fff;
        text-align: center;
        margin: 0;
      }

      .foul-out-button-container {
        display: flex;
        gap: 20px;
        width: 100%;
        justify-content: center;
        margin-top: 10px;
      }

      .foul-out-button {
        padding: 15px 40px;
        font-size: 20px;
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
        box-shadow: 0 4px 8px rgba(255, 152, 0, 0.4);
      }
    `;
    document.head.appendChild(style);
  }

  document.body.appendChild(popup);
}

