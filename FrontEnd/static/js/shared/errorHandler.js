/**
 * Error Handler Utility for Missing Required Pointers
 * Phase 1.1: Provides explicit error screens with recovery flows
 */

/**
 * Show error screen for missing required pointer
 * @param {Object} options - Error configuration
 * @param {string} options.missingPointer - The missing pointer (game_id, franchise_id, tournament_id)
 * @param {string} options.message - Detailed error message
 * @param {string} options.mode - Current game mode (single, franchise, tournament)
 * @param {Object} options.recoveryOptions - Recovery flow options
 * @param {string} options.recoveryOptions.redirectTo - Where to redirect (lineup, mode-select, franchise-select, etc.)
 * @param {Object} options.recoveryOptions.redirectParams - Parameters for redirect URL
 * @param {string} options.recoveryOptions.redirectLabel - Label for redirect button
 */
function showMissingPointerError({
  missingPointer,
  message,
  mode = 'single',
  recoveryOptions = {}
}) {
  const {
    redirectTo = 'lineup',
    redirectParams = {},
    redirectLabel = 'Go Back'
  } = recoveryOptions;

  // Build recovery URL based on redirect target
  let recoveryUrl = '/';
  switch (redirectTo) {
    case 'lineup':
      recoveryUrl = buildLineupUrl(redirectParams);
      break;
    case 'mode-select':
      recoveryUrl = '/mode-select.html';
      break;
    case 'franchise-select':
      recoveryUrl = '/franchise-select-team.html';
      break;
    case 'tournament-select':
      recoveryUrl = '/tournament-select.html';
      break;
    case 'homepage':
      recoveryUrl = '/homepage.html';
      break;
    default:
      recoveryUrl = redirectTo;
  }

  // Create error screen HTML
  const errorHtml = `
    <div class="error-screen" style="
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: #1e1e1e;
      color: #fff;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      z-index: 10000;
      font-family: 'Bebas Neue', 'Inter', sans-serif;
      padding: 20px;
      box-sizing: border-box;
    ">
      <div class="error-content" style="
        max-width: 600px;
        text-align: center;
        background: #2a2a2a;
        padding: 40px;
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
      ">
        <h1 style="
          font-size: 48px;
          margin-bottom: 20px;
          color: #ff6200;
        ">⚠️ Error</h1>
        <h2 style="
          font-size: 24px;
          margin-bottom: 20px;
          color: #fff;
        ">Missing Required ${missingPointer.toUpperCase().replace('_', ' ')}</h2>
        <p style="
          font-size: 16px;
          line-height: 1.6;
          margin-bottom: 30px;
          color: #ccc;
        ">${message}</p>
        <div style="
          display: flex;
          gap: 15px;
          justify-content: center;
          flex-wrap: wrap;
        ">
          <button onclick="window.location.href='${recoveryUrl}'" style="
            background: #ff6200;
            color: #fff;
            border: none;
            padding: 12px 30px;
            font-size: 18px;
            font-family: 'Bebas Neue', sans-serif;
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.3s;
          " onmouseover="this.style.background='#ff7a33'" onmouseout="this.style.background='#ff6200'">
            ${redirectLabel}
          </button>
          <button onclick="window.location.href='/homepage.html'" style="
            background: #444;
            color: #fff;
            border: none;
            padding: 12px 30px;
            font-size: 18px;
            font-family: 'Bebas Neue', sans-serif;
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.3s;
          " onmouseover="this.style.background='#555'" onmouseout="this.style.background='#444'">
            Go to Homepage
          </button>
        </div>
      </div>
    </div>
  `;

  // Replace page content with error screen
  document.body.innerHTML = errorHtml;
  document.title = 'Error - Missing Required Pointer';

  // Log to console for debugging
  console.error(`❌ [ERROR HANDLER] Missing ${missingPointer}: ${message}`);
}

/**
 * Build lineup URL from params
 */
function buildLineupUrl(params) {
  const urlParams = new URLSearchParams();
  
  if (params.home) urlParams.set('home', params.home);
  if (params.away) urlParams.set('away', params.away);
  if (params.home_id) urlParams.set('home_id', params.home_id);
  if (params.away_id) urlParams.set('away_id', params.away_id);
  if (params.my_team) urlParams.set('my_team', params.my_team);
  if (params.mode) urlParams.set('mode', params.mode);
  if (params.quarter) urlParams.set('quarter', params.quarter);
  if (params.period) urlParams.set('period', params.period);
  if (params.franchise_id) urlParams.set('franchise_id', params.franchise_id);
  if (params.tournament_id) urlParams.set('tournament_id', params.tournament_id);
  if (params.week) urlParams.set('week', params.week);
  if (params.team_id) urlParams.set('team_id', params.team_id);
  
  return `/set-lineup.html?${urlParams.toString()}`;
}

// Make available on window object (no ES6 export to avoid module syntax issues)
if (typeof window !== 'undefined') {
  window.ErrorHandler = {
    showMissingPointerError
  };
}

