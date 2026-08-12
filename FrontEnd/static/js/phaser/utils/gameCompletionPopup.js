import { launchPostGamePressConference } from './postGamePressConference.js';
import { getOrStartFranchisePhaseB } from './franchisePhaseBClient.js';
import {
  isPgpcSammyReminderSuppressed,
  showPgpcSammyReminderModal,
} from './pgpcSammyReminderModal.js';

/**
 * Franchise EOG: when true, primary CTA opens post-game press conference (PGPC) while phase B runs.
 * When false, EOG shows Box Score + Go To Locker Room; PGPC / Sammy / press-conference modules stay in the codebase for a quick revert.
 */
export const FRANCHISE_PGPC_AT_EOG_ENABLED = false;

/**
 * Resolve championship-moments overlay for the live-game path. When the just-
 * completed franchise game is the user's conference / region / national
 * championship, render the matching Variation A/B overlay and return true to
 * tell the caller to skip the standard EOG modal entirely.
 */
async function maybeShowChampionshipMomentForLiveGame({
  franchiseId,
  gameId,
  homeTeam,
  awayTeam,
  finalScore,
  teamId,
  userTeamSide,
}) {
  if (typeof API_CONFIG === 'undefined' || !API_CONFIG.buildUrl) return false;
  let momentResp;
  try {
    const url = `${API_CONFIG.buildUrl('/franchise/championship-moments/context')}?franchise_id=${encodeURIComponent(franchiseId)}&game_id=${encodeURIComponent(gameId)}`;
    const res = await fetch(url, {
      method: 'GET',
      headers: API_CONFIG.getAuthHeaders ? API_CONFIG.getAuthHeaders() : {},
    });
    if (!res.ok) return false;
    momentResp = await res.json();
  } catch (err) {
    console.warn('[gameCompletionPopup] championship-context fetch failed:', err);
    return false;
  }
  if (!momentResp || !momentResp.is_championship || !momentResp.moment) return false;

  // Lazy-load the moments module — it is only included on the FCC page by default.
  if (typeof window === 'undefined' || !window.ChampionshipMoments) {
    try {
      const staticBase = (window.API_CONFIG && window.API_CONFIG.getStaticPath)
        ? window.API_CONFIG.getStaticPath()
        : '';
      await new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = `${staticBase}/js/shared/championshipMoments.js`;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
      });
    } catch (err) {
      console.warn('[gameCompletionPopup] failed to load championshipMoments.js:', err);
      return false;
    }
  }
  if (!window.ChampionshipMoments) return false;

  const moment = momentResp.moment;

  // Sync the background scoreboard so the page beneath the overlay reads FINAL.
  syncBackgroundScoreboardFromFinalScore(finalScore);

  // Build navigation targets that mirror the standard EOG buttons.
  const lockerParams = new URLSearchParams();
  lockerParams.set('franchise_id', franchiseId);
  if (teamId) lockerParams.set('team_id', teamId);
  const lockerRoomUrl = `/franchise-command-center.html?${lockerParams.toString()}`;

  const boxScoreParams = new URLSearchParams();
  if (gameId) boxScoreParams.set('game_id', gameId);
  if (homeTeam) boxScoreParams.set('home', homeTeam);
  if (awayTeam) boxScoreParams.set('away', awayTeam);
  boxScoreParams.set('mode', 'franchise');
  boxScoreParams.set('franchise_id', franchiseId);
  if (teamId) boxScoreParams.set('team_id', teamId);
  if (userTeamSide === 'home' || userTeamSide === 'away') {
    boxScoreParams.set('my_team', userTeamSide);
  }
  const boxScoreUrl = `/box-score.html?${boxScoreParams.toString()}`;

  await window.ChampionshipMoments.showMoment(moment, {
    lockerRoomUrl,
    boxScoreUrl,
  });
  return true;
}

/**
 * Push final scores (and a simple FINAL clock readout) to the court scoreboard DOM
 * so the background behind the EOG modal matches the popup, not a stale Q1/0–0 state.
 */
function syncBackgroundScoreboardFromFinalScore(finalScore) {
  if (typeof document === 'undefined' || !finalScore) return;
  const hs = Number(finalScore.homeScore);
  const as = Number(finalScore.awayScore);
  if (!Number.isFinite(hs) || !Number.isFinite(as)) return;

  const homeScoreEl = document.getElementById('home-score');
  const awayScoreEl = document.getElementById('away-score');
  if (homeScoreEl) homeScoreEl.textContent = String(hs);
  if (awayScoreEl) awayScoreEl.textContent = String(as);

  const quarterEl = document.getElementById('quarter');
  if (quarterEl) quarterEl.textContent = 'FINAL';

  const gameClockEl = document.getElementById('game-clock');
  if (gameClockEl) gameClockEl.textContent = '0:00';

  const shotClockEl = document.getElementById('shot-clock');
  if (shotClockEl) shotClockEl.textContent = '0';
}

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

  syncBackgroundScoreboardFromFinalScore(finalScore);

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

  // Championship Announce Moments — for franchise EOS championship games we
  // replace the standard EOG modal with the Variation A (conference/region) or
  // Variation B (national) overlay before doing any of the standard EOG work.
  if (mode === 'franchise' && franchiseId && gameId) {
    try {
      const handled = await maybeShowChampionshipMomentForLiveGame({
        franchiseId,
        gameId,
        lockerRoomUrl: null, // built below
        homeTeam,
        awayTeam,
        finalScore,
        teamId,
        userTeamSide,
      });
      if (handled) return;
    } catch (err) {
      console.warn('[gameCompletionPopup] championship-moments check failed:', err);
    }
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
        const api = typeof window !== 'undefined' ? window.API_CONFIG : null;
        potgImageUrl = potg.portraitSource === 'recruit' && potg.imageId && api?.getRecruitImageUrl
          ? api.getRecruitImageUrl(potg.imageId, { size: 'modal' })
          : api?.getPlayerImageUrl
            ? api.getPlayerImageUrl(potg.playerId, { size: 'modal' })
            : `${staticBase}/images/players/${potg.playerId}.png`;
      }
    }
  } catch (err) {
    console.warn('[gameCompletionPopup] Failed to calculate POTG:', err);
  }

  // §3.1a + total chrome snapshot: score keys stay core; labels/colours from lookupTeamChrome.
  const teamsFromDoc = resolvedGameDoc?.teams || {};
  const docHomeId = resolvedGameDoc?.home_team_id;
  const docAwayId = resolvedGameDoc?.away_team_id;
  const teamRec = (id) => {
    if (id == null || !teamsFromDoc || typeof teamsFromDoc !== 'object') return null;
    return teamsFromDoc[id] || teamsFromDoc[String(id)] || null;
  };
  const homeTeamData = finalScore?.homeTeamData || teamRec(docHomeId);
  const awayTeamData = finalScore?.awayTeamData || teamRec(docAwayId);
  const legacyHome =
    resolvedGameDoc?.home_team && typeof resolvedGameDoc.home_team === 'object'
      ? resolvedGameDoc.home_team
      : null;
  const legacyAway =
    resolvedGameDoc?.away_team && typeof resolvedGameDoc.away_team === 'object'
      ? resolvedGameDoc.away_team
      : null;

  let urlHomeDisplay = null;
  let urlAwayDisplay = null;
  try {
    const sp = new URLSearchParams(window.location.search);
    urlHomeDisplay = sp.get('home_display');
    urlAwayDisplay = sp.get('away_display');
  } catch (_) {}

  const homeCore =
    homeTeamData?.name ||
    legacyHome?.name ||
    finalScore?.homeTeam ||
    homeTeam ||
    'Home';
  const awayCore =
    awayTeamData?.name ||
    legacyAway?.name ||
    finalScore?.awayTeam ||
    awayTeam ||
    'Away';

  if (typeof ensureTeamBuilderChromeSnapshot === 'function') {
    try {
      await ensureTeamBuilderChromeSnapshot(franchiseId);
    } catch (e) {
      console.warn('[gameCompletionPopup] chrome snapshot failed:', e);
    }
  }

  const homeChrome =
    typeof lookupTeamChrome === 'function'
      ? lookupTeamChrome(homeCore, {
          label: homeTeamData?.display_name || legacyHome?.display_name || urlHomeDisplay || homeCore,
          primary_color:
            homeTeamData?.colors?.primary_color ||
            homeTeamData?.primary_color ||
            legacyHome?.colors?.primary_color,
          secondary_color:
            homeTeamData?.colors?.secondary_color ||
            homeTeamData?.secondary_color ||
            legacyHome?.colors?.secondary_color,
        })
      : {
          label: homeTeamData?.display_name || urlHomeDisplay || homeCore,
          primary_color: homeTeamData?.colors?.primary_color || '#F79420',
          secondary_color: homeTeamData?.colors?.secondary_color,
        };
  const awayChrome =
    typeof lookupTeamChrome === 'function'
      ? lookupTeamChrome(awayCore, {
          label: awayTeamData?.display_name || legacyAway?.display_name || urlAwayDisplay || awayCore,
          primary_color:
            awayTeamData?.colors?.primary_color ||
            awayTeamData?.primary_color ||
            legacyAway?.colors?.primary_color,
          secondary_color:
            awayTeamData?.colors?.secondary_color ||
            awayTeamData?.secondary_color ||
            legacyAway?.colors?.secondary_color,
        })
      : {
          label: awayTeamData?.display_name || urlAwayDisplay || awayCore,
          primary_color: awayTeamData?.colors?.primary_color || '#4065AF',
          secondary_color: awayTeamData?.colors?.secondary_color,
        };

  const homeLabel = homeChrome.label || homeCore;
  const awayLabel = awayChrome.label || awayCore;

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
  // Chrome label for banner / pulse / PGPC / score line user side.
  const userTeamName = resolvedUserTeamSide === 'away'
    ? awayLabel
    : resolvedUserTeamSide === 'home'
    ? homeLabel
    : null;

  let userTeamPrimaryColor = '#F79420';
  if (resolvedUserTeamSide === 'home' && homeChrome?.primary_color) {
    userTeamPrimaryColor = homeChrome.primary_color;
  } else if (resolvedUserTeamSide === 'away' && awayChrome?.primary_color) {
    userTeamPrimaryColor = awayChrome.primary_color;
  } else if (resolvedUserTeamSide === 'home' && homeTeamData && typeof homeTeamData === 'object') {
    const col = homeTeamData.colors?.primary_color || homeTeamData.colors?.primary;
    if (col && typeof col === 'string') userTeamPrimaryColor = col;
  } else if (resolvedUserTeamSide === 'away' && awayTeamData && typeof awayTeamData === 'object') {
    const col = awayTeamData.colors?.primary_color || awayTeamData.colors?.primary;
    if (col && typeof col === 'string') userTeamPrimaryColor = col;
  }
  // Banner key = chrome label (snapshot) so watermark agrees with .team-name.
  const bannerUrl = userTeamName && typeof getTeamAssetPath === 'function'
    ? getTeamAssetPath(userTeamName, 'banner_primary')
    : '/images/teams/general/general_banner_primary.jpg';
  const outcomeKnown = resolvedUserTeamSide !== null;
  const userWon = outcomeKnown
    ? (resolvedUserTeamSide === 'away' ? awayWon : homeWon)
    : null;
  const outcomeLabel = !outcomeKnown ? 'FINAL' : (userWon ? 'WIN' : 'LOSS');
  const outcomeBadgeClass = !outcomeKnown ? 'is-final' : (userWon ? 'is-win' : 'is-loss');
  const winnerName = homeWon ? homeLabel : awayLabel;
  const loserName = homeWon ? awayLabel : homeLabel;
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

  const franchisePgpcOnly =
    Boolean(franchisePhaseBPending) && FRANCHISE_PGPC_AT_EOG_ENABLED;

  // Box Score URL — after user side is resolved so `my_team` matches header banner on box-score.
  // post_game_phase_b=1: opened from EOG while phase B is pending; box-score shows "Sim Computer Games" when localStorage matches.
  const boxScoreParams = new URLSearchParams();
  if (gameId) boxScoreParams.set('game_id', gameId);
  // Identity URL params stay core (never display_name).
  const homeParam = homeTeam || homeCore;
  const awayParam = awayTeam || awayCore;
  if (homeParam) boxScoreParams.set('home', homeParam);
  if (awayParam) boxScoreParams.set('away', awayParam);
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

  const lockerActionHtml = franchisePgpcOnly
    ? `<button type="button" class="completion-button locker-room-button franchise-pgpc-button">Post-Game Press Conference</button>`
    : `<a href="${lockerRoomUrl}" class="completion-button locker-room-button">Go To Locker Room</a>`;

  // FTE v2 tutorial: same Sammy chrome as the standard modal, but with an
  // eyebrow ("Your Debut") and a win/loss message inserted above the final
  // score, and no Box Score button (the tutorial game is throwaway).
  const isTutorial = mode === 'tutorial';
  const eyebrowText = isTutorial ? 'Your Debut' : 'Game Complete';
  let tutorialMessageHtml = '';
  if (isTutorial && outcomeKnown) {
    const messageCopy = userWon
      ? 'Congrats on winning your first game Coach!'
      : "That was a tough one Coach — but we're confident you'll bounce back.";
    tutorialMessageHtml = `
      <section class="gc-section gc-tutorial-message-section">
        <div class="gc-tutorial-message">${messageCopy}</div>
      </section>
    `;
  }

  const actionsSectionHtml = franchisePgpcOnly
    ? `
      <section class="gc-section gc-actions-section">
        <div class="button-container gc-actions-pgpc-only">
          ${lockerActionHtml}
        </div>
      </section>
    `
    : isTutorial
    ? `
      <section class="gc-section gc-actions-section">
        <div class="button-container">
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
        <div class="gc-eyebrow">${eyebrowText}</div>
        <div class="gc-outcome-badge ${outcomeBadgeClass}">${outcomeLabel}</div>
      </div>
      ${tutorialMessageHtml}
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

      /* FTE v2 tutorial: win/loss flavor message above the final score. */
      .gc-tutorial-message-section {
        border-top: none;
        padding-top: 0;
      }
      .gc-tutorial-message {
        font-family: 'Inter', sans-serif;
        font-size: 1.05rem;
        font-weight: 600;
        line-height: 1.4;
        color: rgba(255, 255, 255, 0.92);
        text-align: center;
        margin: 0;
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
  const potgImg = popup.querySelector('.potg-image');
  if (potgImg && potg?.playerId) {
    potgImg.addEventListener('error', function onPotgImageError() {
      potgImg.removeEventListener('error', onPotgImageError);
      const api = window.API_CONFIG;
      const ensure = potg.portraitSource === 'recruit' && potg.imageId
        ? api?.ensureRecruitImage?.(potg.imageId)
        : potg.imageId
          ? api?.ensurePlayerImage?.(api.currentFranchiseId?.(), potg.playerId)
          : Promise.resolve({ status: 'skip' });
      Promise.resolve(ensure).then(() => {
        potgImg.addEventListener('error', function onPotgRetryError() {
          potgImg.removeEventListener('error', onPotgRetryError);
          potgImg.src = api?.getGenericHeadshotUrl
            ? api.getGenericHeadshotUrl({ size: 'modal' })
            : `${staticBase}/images/players/generic_headshot.png`;
        });
        const retryUrl = potg.portraitSource === 'recruit' && potg.imageId
          ? api?.getRecruitImageUrl?.(potg.imageId, { size: 'modal' })
          : api?.getPlayerImageUrl?.(potg.playerId, { size: 'modal' });
        if (!retryUrl) {
          potgImg.dispatchEvent(new Event('error'));
          return;
        }
        potgImg.src = `${retryUrl}${retryUrl.includes('?') ? '&' : '?'}r=1`;
      });
    });
  }

  if (franchisePhaseBPending && typeof API_CONFIG !== 'undefined' && API_CONFIG.buildUrl) {
    getOrStartFranchisePhaseB(franchisePhaseBPending).catch((err) => {
      console.warn('[gameCompletionPopup] background phase-b failed to start:', err);
    });
  }

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
  if (
    pgpcBtn &&
    franchisePgpcOnly &&
    typeof API_CONFIG !== 'undefined' &&
    API_CONFIG.buildUrl
  ) {
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

  if (
    lockerRoomBtn &&
    mode === 'franchise' &&
    franchisePhaseBPending &&
    !FRANCHISE_PGPC_AT_EOG_ENABLED &&
    typeof API_CONFIG !== 'undefined' &&
    API_CONFIG.buildUrl
  ) {
    lockerRoomBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      let okToNavigate = false;
      try {
        try {
          popup.remove();
        } catch (_) {}
        const pulseTeamName = userTeamName || '';
        const overlayTitle = pulseTeamName || 'Your team';
        const statLines = window.PageLoadOverlay && window.PageLoadOverlay.buildPostgameStatFeed
          ? window.PageLoadOverlay.buildPostgameStatFeed(resolvedGameDoc, { userTeamSide: resolvedUserTeamSide })
          : [];
        if (window.PageLoadOverlay && window.PageLoadOverlay.show) {
          window.PageLoadOverlay.show({
            variant: 'pulse',
            title: statLines.length ? '' : overlayTitle,
            label: 'Simulating Computer Games',
            subtitle: '',
            statLines,
            statIntervalMs: 8000,
            teamName: pulseTeamName,
            assetKey: 'banner_primary',
          });
        }
        const res = await getOrStartFranchisePhaseB(franchisePhaseBPending);
        if (res.ok) {
          okToNavigate = true;
          if (window.FranchiseLS && franchiseId) {
            window.FranchiseLS.clearPendingAndEog(franchiseId);
          } else if (typeof localStorage !== 'undefined') {
            localStorage.removeItem('franchise_complete_week_pending');
            localStorage.removeItem('franchise_eog_pgpc_snapshot');
          }
        } else {
          try {
            console.error(
              '[gameCompletionPopup] phase-b failed before FCC navigation:',
              res.status,
              await res.text()
            );
          } catch (_) {}
          alert('Could not finish the week (computer games). Try again.');
        }
      } catch (err) {
        console.error('[gameCompletionPopup] phase-b error before FCC navigation:', err);
        alert('Could not finish the week (computer games). Try again.');
      } finally {
        if (window.PageLoadOverlay && window.PageLoadOverlay.hide) {
          window.PageLoadOverlay.hide();
        }
      }
      if (okToNavigate) {
        window.location.assign(lockerRoomUrl);
      }
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

  // FTE v2 tutorial: on locker-room click, publish the debut entry, mark the
  // tutorial complete, delete the throwaway game doc (single-mode precedent),
  // then navigate to mode-select. Each call is best-effort — a publish or
  // complete failure should still let the user reach mode-select.
  if (lockerRoomBtn && isTutorial && gameId) {
    lockerRoomBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      const haveApi = typeof API_CONFIG !== 'undefined' && API_CONFIG.buildUrl && API_CONFIG.getAuthHeaders;
      const headers = { 'Content-Type': 'application/json', ...(haveApi ? API_CONFIG.getAuthHeaders() : {}) };

      if (haveApi && outcomeKnown && userTeamName) {
        const opponentName = resolvedUserTeamSide === 'home' ? awayLabel : homeLabel;
        const userScore = resolvedUserTeamSide === 'home' ? homeScore : awayScore;
        const opponentScore = resolvedUserTeamSide === 'home' ? awayScore : homeScore;
        try {
          await fetch(API_CONFIG.buildUrl('/api/community/debut'), {
            method: 'POST',
            headers,
            body: JSON.stringify({
              user_team_name: userTeamName,
              opponent_name: opponentName,
              user_won: !!userWon,
              user_score: userScore,
              opponent_score: opponentScore,
            }),
          });
        } catch (err) {
          console.warn('[gameCompletionPopup][tutorial] debut publish failed:', err);
        }
      }

      if (haveApi) {
        try {
          await fetch(API_CONFIG.buildUrl('/api/auth/tutorial-complete'), {
            method: 'POST',
            headers,
          });
        } catch (err) {
          console.warn('[gameCompletionPopup][tutorial] tutorial-complete failed:', err);
        }
        try {
          await fetch(API_CONFIG.buildUrl('/api/games/delete-completed-single'), {
            method: 'POST',
            headers,
            body: JSON.stringify({ game_id: gameId }),
          });
        } catch (err) {
          console.warn('[gameCompletionPopup][tutorial] delete-completed-single failed:', err);
        }
      }

      window.location.href = '/mode-select.html';
    });
  }
}
