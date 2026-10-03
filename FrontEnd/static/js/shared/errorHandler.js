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
 * Error Handler Utility for State & Persistence Errors
 * Phase 1.1 & Phase 4: Provides explicit error screens with recovery flows and telemetry
 */

/**
 * Log error telemetry (Phase 4)
 */
function logErrorTelemetry(errorType, errorDetails) {
  const timestamp = new Date().toISOString();
  const logData = {
    timestamp,
    errorType,
    ...errorDetails
  };
  
  // Log to console
  console.error(`🔴 [ERROR TELEMETRY] ${errorType}:`, logData);
  
  // Store in sessionStorage for monitoring (last 10 errors)
  try {
    const errorLog = JSON.parse(sessionStorage.getItem('errorTelemetry') || '[]');
    errorLog.push(logData);
    // Keep only last 10 errors
    if (errorLog.length > 10) {
      errorLog.shift();
    }
    sessionStorage.setItem('errorTelemetry', JSON.stringify(errorLog));
  } catch (e) {
    // Ignore sessionStorage errors (may not be available)
  }
}

/**
 * Show error screen for missing required pointer
 * @param {Object} options - Error configuration
 * @param {string} options.missingPointer - The missing pointer (game_id, franchise_id)
 * @param {string} options.message - Detailed error message
 * @param {string} options.mode - Current game mode (single, franchise)
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
  // ✅ Phase 4: Log error telemetry
  logErrorTelemetry('MISSING_POINTER', {
    missingPointer,
    message,
    mode,
    recoveryAction: recoveryOptions.redirectTo || 'lineup',
    url: window.location.href
  });
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
    case 'homepage':
      recoveryUrl = '/homepage.html';
      break;
    default:
      recoveryUrl = redirectTo;
  }

  // Create error screen HTML
  const errorHtml = `
    <div class="error-screen gob-scope" style="
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: var(--bg);
      color: var(--text-100);
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      z-index: 10000;
      font-family: var(--font-display);
      padding: 20px;
      box-sizing: border-box;
    ">
      <div class="error-content" style="
        max-width: 600px;
        text-align: center;
        background: var(--surface-2);
        border: 1px solid var(--line);
        padding: 40px;
        border-radius: var(--radius-8);
        box-shadow: 0 4px 20px var(--black-50);
      ">
        <h1 style="
          font-size: var(--fs-48);
          margin-bottom: 20px;
          color: var(--text-100);
        ">⚠️ Error</h1>
        <h2 style="
          font-size: var(--fs-24);
          margin-bottom: 20px;
          color: var(--text-100);
        ">Missing Required ${missingPointer.toUpperCase().replace('_', ' ')}</h2>
        <p style="
          font-size: var(--fs-16);
          line-height: 1.6;
          margin-bottom: 30px;
          color: var(--text-87);
        ">${message}</p>
        <div style="
          display: flex;
          gap: 15px;
          justify-content: center;
          flex-wrap: wrap;
        ">
          <button onclick="window.location.href='${recoveryUrl}'" style="
            background: var(--white-10);
            color: var(--text-100);
            border: 1px solid var(--white-28);
            padding: 12px 30px;
            font-size: var(--fs-18);
            font-family: var(--font-display);
            border-radius: var(--radius-4);
            cursor: pointer;
            transition: background 0.3s;
          " onmouseover="this.style.background='var(--white-18)'" onmouseout="this.style.background='var(--white-10)'">
            ${redirectLabel}
          </button>
          <button onclick="window.location.href='/homepage.html'" style="
            background: transparent;
            color: var(--text-87);
            border: 1px solid var(--line-strong);
            padding: 12px 30px;
            font-size: var(--fs-18);
            font-family: var(--font-display);
            border-radius: var(--radius-4);
            cursor: pointer;
            transition: background 0.3s;
          " onmouseover="this.style.background='var(--white-6)'" onmouseout="this.style.background='transparent'">
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
  const urlParams = emptyParams();
  
  if (params.home) urlParams.set('home', params.home);
  if (params.away) urlParams.set('away', params.away);
  if (params.home_id) urlParams.set('home_id', params.home_id);
  if (params.away_id) urlParams.set('away_id', params.away_id);
  if (params.my_team) urlParams.set('my_team', params.my_team);
  if (params.mode) urlParams.set('mode', params.mode);
  if (params.quarter) urlParams.set('quarter', params.quarter);
  if (params.period) urlParams.set('period', params.period);
  if (params.franchise_id) urlParams.set('franchise_id', params.franchise_id);
  if (params.week) urlParams.set('week', params.week);
  if (params.team_id) urlParams.set('team_id', params.team_id);
  
  return `/set-lineup.html?${urlParams.toString()}`;
}

/**
 * Show error screen for missing truth (document not found)
 * Phase 4: Error screen for when pointer exists but document doesn't
 * @param {Object} options - Error configuration
 * @param {string} options.pointerType - The pointer type (game_id, franchise_id)
 * @param {string} options.pointerValue - The pointer value that was invalid
 * @param {string} options.message - Detailed error message
 * @param {string} options.mode - Current game mode (single, franchise)
 * @param {Object} options.recoveryOptions - Recovery flow options
 */
function showMissingTruthError({
  pointerType,
  pointerValue,
  message,
  mode = 'single',
  recoveryOptions = {}
}) {
  // ✅ Phase 4: Log error telemetry
  logErrorTelemetry('MISSING_TRUTH', {
    pointerType,
    pointerValue,
    message,
    mode,
    recoveryAction: recoveryOptions.redirectTo || 'mode-select',
    url: window.location.href
  });

  const {
    redirectTo = 'mode-select',
    redirectParams = {},
    redirectLabel = 'Go to Mode Select'
  } = recoveryOptions;

  // Build recovery URL
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
    case 'homepage':
      recoveryUrl = '/homepage.html';
      break;
    default:
      recoveryUrl = redirectTo;
  }

  // Create error screen HTML
  const errorHtml = `
    <div class="error-screen gob-scope" style="
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: var(--bg);
      color: var(--text-100);
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      z-index: 10000;
      font-family: var(--font-display);
      padding: 20px;
      box-sizing: border-box;
    ">
      <div class="error-content" style="
        max-width: 600px;
        text-align: center;
        background: var(--surface-2);
        border: 1px solid var(--line);
        padding: 40px;
        border-radius: var(--radius-8);
        box-shadow: 0 4px 20px var(--black-50);
      ">
        <h1 style="
          font-size: var(--fs-48);
          margin-bottom: 20px;
          color: var(--text-100);
        ">❌ Error</h1>
        <h2 style="
          font-size: var(--fs-24);
          margin-bottom: 20px;
          color: var(--text-100);
        ">Document Not Found</h2>
        <p style="
          font-size: var(--fs-16);
          line-height: 1.6;
          margin-bottom: 15px;
          color: var(--text-87);
        ">The ${pointerType.replace('_', ' ')} you're looking for doesn't exist in the database.</p>
        <p style="
          font-size: var(--fs-14);
          line-height: 1.6;
          margin-bottom: 30px;
          color: var(--text-60);
          font-style: italic;
        ">${message}</p>
        <div style="
          display: flex;
          gap: 15px;
          justify-content: center;
          flex-wrap: wrap;
        ">
          <button onclick="window.location.href='${recoveryUrl}'" style="
            background: var(--white-10);
            color: var(--text-100);
            border: 1px solid var(--white-28);
            padding: 12px 30px;
            font-size: var(--fs-18);
            font-family: var(--font-display);
            border-radius: var(--radius-4);
            cursor: pointer;
            transition: background 0.3s;
          " onmouseover="this.style.background='var(--white-18)'" onmouseout="this.style.background='var(--white-10)'">
            ${redirectLabel}
          </button>
          <button onclick="window.location.href='/homepage.html'" style="
            background: transparent;
            color: var(--text-87);
            border: 1px solid var(--line-strong);
            padding: 12px 30px;
            font-size: var(--fs-18);
            font-family: var(--font-display);
            border-radius: var(--radius-4);
            cursor: pointer;
            transition: background 0.3s;
          " onmouseover="this.style.background='var(--white-6)'" onmouseout="this.style.background='transparent'">
            Go to Homepage
          </button>
        </div>
      </div>
    </div>
  `;

  // Replace page content with error screen
  document.body.innerHTML = errorHtml;
  document.title = 'Error - Document Not Found';

  // Log to console for debugging
  console.error(`❌ [ERROR HANDLER] Missing truth for ${pointerType} (${pointerValue}): ${message}`);
}

/**
 * Show error screen for version mismatch
 * Phase 4: Error screen for when cache version doesn't match expected version
 * @param {Object} options - Error configuration
 * @param {string} options.cacheType - The cache type (ongoing_games, gameStore, etc.)
 * @param {string} options.expectedVersion - Expected version
 * @param {string} options.actualVersion - Actual version found
 * @param {string} options.message - Detailed error message
 * @param {Object} options.recoveryOptions - Recovery flow options
 */
function showVersionMismatchError({
  cacheType,
  expectedVersion,
  actualVersion,
  message,
  recoveryOptions = {}
}) {
  // ✅ Phase 4: Log error telemetry
  logErrorTelemetry('VERSION_MISMATCH', {
    cacheType,
    expectedVersion,
    actualVersion,
    message,
    recoveryAction: recoveryOptions.redirectTo || 'reload',
    url: window.location.href
  });

  const {
    redirectTo = 'reload',
    redirectLabel = 'Reload Page'
  } = recoveryOptions;

  // Build recovery action
  let recoveryAction = "window.location.reload()";
  if (redirectTo !== 'reload') {
    recoveryAction = `window.location.href='${redirectTo}'`;
  }

  // Create error screen HTML
  const errorHtml = `
    <div class="error-screen gob-scope" style="
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: var(--bg);
      color: var(--text-100);
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      z-index: 10000;
      font-family: var(--font-display);
      padding: 20px;
      box-sizing: border-box;
    ">
      <div class="error-content" style="
        max-width: 600px;
        text-align: center;
        background: var(--surface-2);
        border: 1px solid var(--line);
        padding: 40px;
        border-radius: var(--radius-8);
        box-shadow: 0 4px 20px var(--black-50);
      ">
        <h1 style="
          font-size: var(--fs-48);
          margin-bottom: 20px;
          color: var(--text-100);
        ">⚠️ Version Mismatch</h1>
        <h2 style="
          font-size: var(--fs-24);
          margin-bottom: 20px;
          color: var(--text-100);
        ">Cache Out of Sync</h2>
        <p style="
          font-size: var(--fs-16);
          line-height: 1.6;
          margin-bottom: 15px;
          color: var(--text-87);
        ">The cached data is out of date and needs to be refreshed.</p>
        <p style="
          font-size: var(--fs-14);
          line-height: 1.6;
          margin-bottom: 30px;
          color: var(--text-60);
          font-style: italic;
        ">${message}</p>
        <div style="
          display: flex;
          gap: 15px;
          justify-content: center;
          flex-wrap: wrap;
        ">
          <button onclick="${recoveryAction}" style="
            background: var(--white-10);
            color: var(--text-100);
            border: 1px solid var(--white-28);
            padding: 12px 30px;
            font-size: var(--fs-18);
            font-family: var(--font-display);
            border-radius: var(--radius-4);
            cursor: pointer;
            transition: background 0.3s;
          " onmouseover="this.style.background='var(--white-18)'" onmouseout="this.style.background='var(--white-10)'">
            ${redirectLabel}
          </button>
          <button onclick="window.location.href='/homepage.html'" style="
            background: transparent;
            color: var(--text-87);
            border: 1px solid var(--line-strong);
            padding: 12px 30px;
            font-size: var(--fs-18);
            font-family: var(--font-display);
            border-radius: var(--radius-4);
            cursor: pointer;
            transition: background 0.3s;
          " onmouseover="this.style.background='var(--white-6)'" onmouseout="this.style.background='transparent'">
            Go to Homepage
          </button>
        </div>
      </div>
    </div>
  `;

  // Replace page content with error screen
  document.body.innerHTML = errorHtml;
  document.title = 'Error - Version Mismatch';

  // Log to console for debugging
  console.error(`❌ [ERROR HANDLER] Version mismatch for ${cacheType}: Expected ${expectedVersion}, got ${actualVersion}`);
}

// Make available on window object (no ES6 export to avoid module syntax issues)
if (typeof window !== 'undefined') {
  window.ErrorHandler = {
    showMissingPointerError,
    showMissingTruthError,
    showVersionMismatchError,
    logErrorTelemetry
  };
}

