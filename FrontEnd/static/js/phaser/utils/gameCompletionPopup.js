import { launchPostGamePressConference } from './postGamePressConference.js';
import {
  isPgpcSammyReminderSuppressed,
  showPgpcSammyReminderModal,
} from './pgpcSammyReminderModal.js';

/**
 * Shows a game completion popup with Box Score and Go To Locker Room buttons
 * @param {Object} options
 * @param {string} options.gameId - The game ID
 * @param {string} options.mode - Game mode: 'single', 'tournament', or 'franchise'
 * @param {string} [options.tournamentId] - Tournament ID (for tournament mode)
 * @param {string} [options.franchiseId] - Franchise ID (for franchise mode)
 * @param {string} [options.teamId] - Team ID (ObjectId) for navigation anchor
 * @param {'home'|'away'|string} [options.userTeamSide] - User's bench side (from URL/scene); used for WIN/LOSS when IDs match fails
 * @param {Object} [options.finalScore] - Final score object with homeTeam, awayTeam, homeScore, awayScore
 * @param {Object} [options.gameData] - Full game document for POTG calculation (optional)
 */
export async function showGameCompletionPopup({ gameId, mode, tournamentId, franchiseId, teamId, userTeamSide, finalScore, homeTeam, awayTeam, gameData }) {
  // Remove any existing popup
  const existingPopup = document.querySelector('.game-completion-popup');
  if (existingPopup) {
    existingPopup.remove();
  }

  // ✅ SS&S: Fallback to reading teamId / user side from URL params if not provided
  if (typeof window !== 'undefined') {
    const urlParams = new URLSearchParams(window.location.search);
    if (!teamId) {
      teamId = urlParams.get('team_id') || urlParams.get('home_id') || urlParams.get('away_id');
    }
    if (!userTeamSide) {
      const fromUrl = urlParams.get('my_team');
      if (fromUrl === 'home' || fromUrl === 'away') {
        userTeamSide = fromUrl;
      }
    }
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

  let potg = null;
  let potgImageUrl = '';
  let resolvedGameDoc = gameData || null;
  const staticBase = (typeof window !== 'undefined' && window.API_CONFIG?.getStaticPath)
    ? window.API_CONFIG.getStaticPath()
    : ((typeof window !== 'undefined' && (window.location?.hostname === 'localhost' || window.location?.hostname === '127.0.0.1')) ? '/static' : '');
  try {
    const { calculatePlayerOfTheGame } = await import((staticBase || '') + '/js/shared/potg.js');
    if (!resolvedGameDoc && gameId && typeof fetch === 'function' && typeof API_CONFIG !== 'undefined') {
      const resp = await fetch(API_CONFIG.buildUrl(`/api/game/${gameId}`), {
        headers: API_CONFIG.getAuthHeaders ? API_CONFIG.getAuthHeaders() : {},
      });
      if (resp.ok) {
        resolvedGameDoc = await resp.json();
      }
    }
    const scoreOverride = finalScore ? {
      [finalScore.homeTeam || homeTeam || 'Home Team']: Number(finalScore.homeScore || 0),
      [finalScore.awayTeam || awayTeam || 'Away Team']: Number(finalScore.awayScore || 0),
    } : null;
    if (resolvedGameDoc) {
      potg = calculatePlayerOfTheGame(resolvedGameDoc, { gameId, scoreOverride });
      if (potg?.playerId) {
        potgImageUrl = `${staticBase}/images/players/${potg.playerId}.png`;
      }
    }
  } catch (err) {
    console.warn('[gameCompletionPopup] Failed to calculate POTG:', err);
  }

  const homeTeamName = finalScore?.homeTeam || 'Home';
  const awayTeamName = finalScore?.awayTeam || 'Away';
  // Banner + box-score `banner_team`: use game-document names when loaded so paths match box-score `getTeamContext()`.
  const teamsFromDoc = resolvedGameDoc?.teams || {};
  const docHomeId = resolvedGameDoc?.home_team_id;
  const docAwayId = resolvedGameDoc?.away_team_id;
  const teamRec = (id) => {
    if (id == null || !teamsFromDoc || typeof teamsFromDoc !== 'object') return null;
    return teamsFromDoc[id] || teamsFromDoc[String(id)] || null;
  };
  const canonicalHomeName =
    teamRec(docHomeId)?.name ||
    (resolvedGameDoc?.home_team && typeof resolvedGameDoc.home_team === 'object' ? resolvedGameDoc.home_team.name : null) ||
    homeTeamName;
  const canonicalAwayName =
    teamRec(docAwayId)?.name ||
    (resolvedGameDoc?.away_team && typeof resolvedGameDoc.away_team === 'object' ? resolvedGameDoc.away_team.name : null) ||
    awayTeamName;
  const homeScore = Number(finalScore?.homeScore || 0);
  const awayScore = Number(finalScore?.awayScore || 0);
  const homeWon = homeScore > awayScore;
  const awayWon = awayScore > homeScore;
  const homeTeamId = String(resolvedGameDoc?.home_team_id || resolvedGameDoc?.homeTeamId || '');
  const awayTeamId = String(resolvedGameDoc?.away_team_id || resolvedGameDoc?.awayTeamId || '');
  const currentTeamId = String(teamId || '');
  const passedSide = userTeamSide === 'home' || userTeamSide === 'away' ? userTeamSide : null;
  let resolvedUserTeamSide = passedSide;
  if (!resolvedUserTeamSide && currentTeamId && homeTeamId && currentTeamId === homeTeamId) {
    resolvedUserTeamSide = 'home';
  } else if (!resolvedUserTeamSide && currentTeamId && awayTeamId && currentTeamId === awayTeamId) {
    resolvedUserTeamSide = 'away';
  }
  const userTeamName = resolvedUserTeamSide === 'away'
    ? canonicalAwayName
    : resolvedUserTeamSide === 'home'
    ? canonicalHomeName
    : null;

  let userTeamPrimaryColor = '#F79420';
  if (resolvedUserTeamSide === 'home' && docHomeId) {
    const ub = teamRec(docHomeId);
    if (ub && typeof ub === 'object') {
      const col = ub.colors?.primary_color || ub.colors?.primary;
      if (col && typeof col === 'string') userTeamPrimaryColor = col;
    }
  } else if (resolvedUserTeamSide === 'away' && docAwayId) {
    const ub = teamRec(docAwayId);
    if (ub && typeof ub === 'object') {
      const col = ub.colors?.primary_color || ub.colors?.primary;
      if (col && typeof col === 'string') userTeamPrimaryColor = col;
    }
  }
  const bannerUrl = userTeamName && typeof getTeamAssetPath === 'function'
    ? getTeamAssetPath(userTeamName, 'banner_primary')
    : '/images/teams/general/general_banner_primary.jpg';
  const outcomeKnown = resolvedUserTeamSide !== null;
  const userWon = outcomeKnown
    ? (resolvedUserTeamSide === 'away' ? awayWon : homeWon)
    : null;
  const outcomeLabel = !outcomeKnown ? 'FINAL' : (userWon ? 'WIN' : 'LOSS');
  const outcomeBadgeClass = !outcomeKnown ? 'is-final' : (userWon ? 'is-win' : 'is-loss');
  const winnerName = homeWon ? homeTeamName : awayTeamName;
  const loserName = homeWon ? awayTeamName : homeTeamName;
  const winnerScore = homeWon ? homeScore : awayScore;
  const loserScore = homeWon ? awayScore : homeScore;
  const potgStatsLine = potg
    ? `${potg.stats.pts} PTS · ${potg.stats.reb} REB · ${potg.stats.ast} AST · ${potg.stats.defPct} DEF%`
    : '';

  const franchisePhaseBPending =
    mode === 'franchise' &&
    finalScore &&
    (finalScore.franchisePhaseBPending ||
      (finalScore.franchiseCompleteWeekPayload
        ? {
            franchise_id: finalScore.franchiseCompleteWeekPayload.franchise_id,
            week: finalScore.franchiseCompleteWeekPayload.week,
          }
        : null));

  // Box Score URL — after user side is resolved so `my_team` matches header banner on box-score.
  // post_game_phase_b=1: opened from EOG while phase B is pending; box-score shows "Sim Computer Games" when localStorage matches.
  const boxScoreParams = new URLSearchParams();
  if (gameId) boxScoreParams.set('game_id', gameId);
  if (homeTeam) boxScoreParams.set('home', homeTeam);
  if (awayTeam) boxScoreParams.set('away', awayTeam);
  if (mode) boxScoreParams.set('mode', mode);
  if (tournamentId) boxScoreParams.set('tournament_id', tournamentId);
  if (franchiseId) boxScoreParams.set('franchise_id', franchiseId);
  if (teamId) boxScoreParams.set('team_id', teamId);
  if (resolvedUserTeamSide === 'home' || resolvedUserTeamSide === 'away') {
    boxScoreParams.set('my_team', resolvedUserTeamSide);
    if (userTeamName) {
      boxScoreParams.set('banner_team', userTeamName);
    }
  }
  if (franchisePhaseBPending) {
    boxScoreParams.set('post_game_phase_b', '1');
  }
  const boxScoreUrl = `/box-score.html?${boxScoreParams.toString()}`;

  const lockerActionHtml = franchisePhaseBPending
    ? `<button type="button" class="completion-button locker-room-button franchise-pgpc-button">Post-Game Press Conference</button>`
    : `<a href="${lockerRoomUrl}" class="completion-button locker-room-button">Go To Locker Room</a>`;

  const actionsSectionHtml = franchisePhaseBPending
    ? `
      <section class="gc-section gc-actions-section">
        <div class="button-container gc-actions-pgpc-only">
          ${lockerActionHtml}
        </div>
      </section>
    `
    : `
      <section class="gc-section gc-actions-section">
        <div class="button-container">
          <a href="${boxScoreUrl}" class="completion-button box-score-button">Box Score</a>
          ${lockerActionHtml}
        </div>
      </section>
    `;

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

  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('last_box_score_url', boxScoreUrl);
    localStorage.setItem('last_box_score_gameId', gameId || '');
    console.log('💾 Saved box score URL to localStorage for debugging');
  }

  // Create popup
  const popup = document.createElement('div');
  popup.className = 'game-completion-popup';
  popup.innerHTML = `
    <div class="game-completion-content" style="background-image: linear-gradient(
      to bottom,
      rgba(13,17,36,0.15) 0%,
      rgba(13,17,36,0.5) 50%,
      rgba(13,17,36,0.92) 75%,
      rgba(13,17,36,0.98) 100%
    ), linear-gradient(
      to right,
      rgba(13,17,36,0.0) 0%,
      rgba(13,17,36,0.0) 30%,
      rgba(13,17,36,0.7) 60%,
      rgba(13,17,36,0.85) 100%
    ), url('${bannerUrl}');">
      <div class="gc-header-row">
        <div class="gc-eyebrow">Game Complete</div>
        <div class="gc-outcome-badge ${outcomeBadgeClass}">${outcomeLabel}</div>
      </div>
      ${finalScore ? `
        <section class="gc-section gc-result-section">
          <div class="final-score-display">
            <div class="score-line">
              <div class="team-score-winner">
                <span class="team-name">${winnerName}</span>
                <span class="score">${winnerScore}</span>
              </div>
              <div class="score-divider">vs</div>
              <div class="team-score-loser">
                <span class="team-name">${loserName}</span>
                <span class="score">${loserScore}</span>
              </div>
            </div>
          </div>
        </section>
      ` : ''}
      ${potg ? `
        <section class="gc-section gc-potg-section">
          <div class="potg-card">
            <div class="potg-label">Player Of The Game</div>
            <div class="potg-content-row">
              <img
                class="potg-image"
                src="${potgImageUrl || (staticBase + '/images/players/generic_headshot.png')}"
                alt="${potg.name}"
                onerror="this.onerror=null;this.src='${staticBase}/images/players/generic_headshot.png';"
              />
              <div class="potg-info">
                <div class="potg-player-name">${potg.name}</div>
                <div class="potg-stats-line">${potgStatsLine}</div>
              </div>
            </div>
          </div>
        </section>
      ` : ''}
      ${actionsSectionHtml}
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
        background: rgba(0,0,0,0.65);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
        padding: 18px;
      }

      .game-completion-content {
        background-color: rgba(13, 17, 36, 0.97);
        background-size: cover;
        background-position: center;
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 16px;
        padding: 22px 24px 28px;
        display: flex;
        flex-direction: column;
        gap: 18px;
        align-items: stretch;
        width: min(560px, 100%);
        box-shadow: 0 24px 48px rgba(0,0,0,0.5);
        animation: gc-modal-in 200ms ease;
      }

      .gc-header-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
      }

      .gc-eyebrow {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 18px;
        color: rgba(255,255,255,0.5);
        letter-spacing: 0.1em;
        text-transform: uppercase;
        line-height: 1;
      }

      .gc-outcome-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 4px 12px;
        border-radius: 999px;
        border: 1px solid transparent;
        font-family: 'Bebas Neue', sans-serif;
        font-size: 14px;
        letter-spacing: 0.08em;
      }

      .gc-outcome-badge.is-win {
        background: rgba(52,236,39,0.15);
        border-color: rgba(52,236,39,0.4);
        color: #34EC27;
      }

      .gc-outcome-badge.is-loss {
        background: rgba(255,109,109,0.15);
        border-color: rgba(255,109,109,0.4);
        color: #ff6d6d;
      }

      .gc-outcome-badge.is-final {
        background: rgba(255,255,255,0.08);
        border-color: rgba(255,255,255,0.2);
        color: rgba(255,255,255,0.75);
      }

      .gc-section {
        border-top: 1px solid rgba(255,255,255,0.08);
        padding-top: 16px;
      }

      .gc-result-section {
        border-top: none;
        padding-top: 0;
      }

      .final-score-display {
        margin: 0 auto;
        width: 100%;
      }

      .score-line {
        margin: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        gap: 16px;
        text-align: center;
      }

      .team-score-winner,
      .team-score-loser {
        display: inline-flex;
        align-items: baseline;
        gap: 8px;
      }

      .team-score-winner {
        color: #ffffff;
      }

      .team-score-loser {
        color: rgba(255,255,255,0.4);
      }

      .score-line .team-name {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 20px;
        line-height: 0.95;
      }

      .score-divider {
        font-family: 'Inter', sans-serif;
        font-size: 13px;
        color: rgba(255,255,255,0.35);
        text-transform: lowercase;
      }

      .score-line .score {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 52px;
        line-height: 0.95;
        text-shadow: 0 2px 12px rgba(0,0,0,0.6);
      }

      .button-container {
        display: flex;
        flex-direction: row;
        gap: 12px;
        width: 100%;
        margin-top: 20px;
      }

      .gc-actions-pgpc-only .completion-button {
        flex: 1;
      }

      .potg-image {
        width: 72px;
        height: 72px;
        border-radius: 8px;
        border: 2px solid rgba(247,148,32,0.4);
        object-fit: cover;
        object-position: center top;
        background: rgba(255,255,255,0.08);
      }

      .potg-card {
        background: rgba(0,0,0,0.72);
        border: 1px solid rgba(255,255,255,0.08);
        border-left: 3px solid #F79420;
        border-radius: 12px;
        padding: 16px 20px;
      }

      .potg-label {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 13px;
        color: #F79420;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        line-height: 1;
      }

      .potg-content-row {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-top: 10px;
      }

      .potg-info {
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 4px;
        min-width: 0;
      }

      .potg-player-name {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 22px;
        color: #ffffff;
        line-height: 1;
      }

      .potg-stats-line {
        font-family: 'Inter', sans-serif;
        font-size: 13px;
        color: rgba(255,255,255,0.6);
        line-height: 1.45;
      }

      .completion-button {
        flex: 1;
        padding: 0 18px;
        font-size: 16px;
        border: 1px solid transparent;
        border-radius: 10px;
        cursor: pointer;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        height: 44px;
        transition: all 0.14s ease;
        font-family: 'Bebas Neue', sans-serif;
        letter-spacing: 0.03em;
      }

      .box-score-button {
        flex: 1;
        background: rgba(255,255,255,0.06);
        color: rgba(255,255,255,0.8);
        border-color: rgba(255,255,255,0.14);
      }

      .box-score-button:hover {
        background: rgba(255,255,255,0.1);
        border-color: rgba(255,255,255,0.2);
        transform: translateY(-1px);
      }

      .game-completion-popup .completion-button.locker-room-button {
        margin: 0;
      }

      .locker-room-button {
        flex: 2;
        background: #34EC27;
        color: #15181f;
        border-color: rgba(52, 236, 39, 0.5);
      }

      .locker-room-button:hover {
        filter: brightness(1.06);
        transform: translateY(-1px);
      }

      @keyframes gc-modal-in {
        from {
          opacity: 0;
          transform: scale(0.96);
        }
        to {
          opacity: 1;
          transform: scale(1);
        }
      }

      @media (max-width: 760px) {
        .game-completion-content {
          padding: 18px 16px 16px;
          gap: 14px;
        }

        .gc-header-row {
          align-items: flex-start;
        }

        .score-line {
          gap: 10px;
          flex-wrap: wrap;
        }

        .score-line .team-name {
          font-size: 18px;
        }

        .score-line .score {
          font-size: 42px;
        }

        .potg-content-row {
          align-items: flex-start;
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

  const pgpcBtn = popup.querySelector('.franchise-pgpc-button');
  if (pgpcBtn && franchisePhaseBPending && typeof API_CONFIG !== 'undefined' && API_CONFIG.buildUrl) {
    pgpcBtn.addEventListener('click', (e) => {
      e.preventDefault();
      if (document.getElementById('pgpc-sammy-reminder-backdrop')) return;
      if (typeof window.playSound === 'function') window.playSound('click-tiny.wav');

      const beginPgpc = () => {
        pgpcBtn.disabled = true;
        launchPostGamePressConference({
          franchisePhaseBPending,
          userTeamName,
          gameId,
          lockerRoomUrl,
          onCloseParentPopup: () => {
            try {
              popup.remove();
            } catch (_) {}
          },
        });
      };

      if (isPgpcSammyReminderSuppressed()) {
        beginPgpc();
        return;
      }

      showPgpcSammyReminderModal({
        userTeamName,
        userPrimaryColor: userTeamPrimaryColor,
        onGotIt: beginPgpc,
      });
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
